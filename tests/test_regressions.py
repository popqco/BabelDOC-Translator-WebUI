"""Phase 1-3 修复项的回归测试。

覆盖此前从未被测试的关键路径：
- 文件名含 glob 特殊字符时的产物发现
- 批次启动即持久化历史 + 收尾 upsert（崩溃可恢复）
- 重试保留用户队列、继承提示词/QPS、接受 interrupted 批次
- 收尾不覆盖手动补打的 ZIP；活动批次补打写回 zip_path
- ZIP 条目多重同名递增后缀
- 孤儿 running 记录启动时降级为 interrupted
"""
import zipfile
from pathlib import Path

import pytest

import core.task_manager as tm_mod
from core.task_manager import TaskManager, DocumentTask, BatchRecord
from core.translator_adapter import TranslatorAdapter


@pytest.fixture
def tm():
    return TaskManager()


def _make_pdf(path: Path):
    path.write_bytes(b"%PDF-1.4 minimal")
    return path


# ---------- 产物发现 ----------

def test_discover_outputs_special_chars(tmp_path):
    """文件名含 [ ] * ? 与空格时必须仍能发现产物（旧 glob 实现会误报 FileNotFound）"""
    work = tmp_path / "work"
    work.mkdir()
    _make_pdf(work / "Report[2024] v2.zh.mono.pdf")
    _make_pdf(work / "Report[2024] v2.zh.dual.pdf")

    res = TranslatorAdapter.discover_outputs(work, "Report[2024] v2", True, True)
    assert res["mono"].name == "Report[2024] v2.zh.mono.pdf"
    assert res["dual"].name == "Report[2024] v2.zh.dual.pdf"


def test_discover_outputs_missing_raises(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(FileNotFoundError):
        TranslatorAdapter.discover_outputs(work, "abc", True, False)


# ---------- 历史 upsert 与启动即持久化 ----------

def test_record_history_entry_upserts(tm):
    batch = BatchRecord(batch_id="batch_up", created_at="now", output_dir="x",
                        status="running", options={"system_prompt": "SP", "qps": "7"})
    tm._record_history_entry(batch)
    first_len = len(tm.history_records)
    batch.status = "completed"
    batch.zip_path = "done.zip"
    tm._record_history_entry(batch)
    assert len(tm.history_records) == first_len, "同 batch_id 收尾时不得重复插入"
    rec = next(r for r in tm.history_records if r["batch_id"] == "batch_up")
    assert rec["status"] == "completed" and rec["zip_path"] == "done.zip"
    assert rec["options"]["system_prompt"] == "SP" and rec["options"]["qps"] == "7"


def test_start_batch_persists_running_record(tm, tmp_path, monkeypatch):
    """批次启动即写历史（status=running），中途崩溃后记录可见可恢复"""
    src = _make_pdf(tmp_path / "doc.pdf")
    tm.add_to_pending([str(src)])
    tm.pending_queue[0]["hash"] = "hashstart01"

    out_dir = tmp_path / "BatchOut"
    out_dir.mkdir()

    # 假内核：不真正调用 BabelDOC
    produced = out_dir / "doc.zh.mono.pdf"
    _make_pdf(produced)
    monkeypatch.setattr(tm_mod, "ensure_offline_assets", lambda: None)
    monkeypatch.setattr(tm_mod.TranslatorAdapter, "translate_single",
                        staticmethod(lambda **kw: {"mono": str(produced), "dual": None, "success": True, "error": None}))

    ok, msg = tm.start_batch({
        "output_mono": True, "output_dual": False, "generate_zip": False,
        "zip_delivery_mode": "both", "lang_in": "en", "lang_out": "zh",
        "model": "m", "qps": "4", "translate_table_text": True,
        "system_prompt": "KEEP", "current_prompt_title": "T",
        "output_dir": str(out_dir),
    })
    assert ok, msg

    # 启动后立即有 running 记录
    rec = next(r for r in tm.history_records if r["status"] == "running")
    assert rec["options"]["system_prompt"] == "KEEP"

    tm.active_thread.join(timeout=10)
    rec = next(r for r in tm.history_records if r["batch_id"] == rec["batch_id"])
    assert rec["status"] == "completed", "worker 收尾必须 upsert 同一条记录"


# ---------- 重试 ----------

def _insert_failed_history(tm, batch_id, out_dir, failed_pdf):
    rec = {
        "batch_id": batch_id, "created_at": "now", "output_dir": str(out_dir),
        "status": "interrupted", "options": {"system_prompt": "KEEP_PROMPT", "qps": "9",
                                             "lang_in": "en", "lang_out": "zh"},
        "zip_path": None, "summary_message": "",
        "tasks": [{
            "id": "t1", "original_path": str(failed_pdf), "filename": failed_pdf.name,
            "file_hash": "feedc0de12", "status": "failed", "mono_output": None,
            "dual_output": None, "cached_input_path": str(failed_pdf),
            "error_message": "boom", "start_time": None, "end_time": None,
        }],
    }
    tm.history_records.insert(0, rec)
    return rec


def test_retry_preserves_pending_queue_and_prompt(tm, tmp_path, monkeypatch):
    queued = _make_pdf(tmp_path / "queued.pdf")
    failed = _make_pdf(tmp_path / "failed.pdf")
    out_dir = tmp_path / "BatchRetry"
    out_dir.mkdir()
    tm.add_to_pending([str(queued)])
    tm.pending_queue[0]["hash"] = "hashqueue01"

    rec = _insert_failed_history(tm, "batch_regress_retry", out_dir, failed)

    produced = out_dir / "failed.zh.mono.pdf"
    _make_pdf(produced)
    monkeypatch.setattr(tm_mod, "ensure_offline_assets", lambda: None)
    monkeypatch.setattr(tm_mod.TranslatorAdapter, "translate_single",
                        staticmethod(lambda **kw: {"mono": str(produced), "dual": None, "success": True, "error": None}))

    ok, msg = tm.retry_failed_tasks(rec["batch_id"],
                                    {"base_url": "u", "api_key": "k", "model": "m"})
    assert ok, msg

    # 用户排队的文件必须随重试批次一起进入执行（旧实现直接 clear 丢掉）
    task_names = [t.filename for t in tm.active_batch.tasks]
    assert "queued.pdf" in task_names
    # 原批次的提示词与 QPS 必须被继承
    assert tm.active_batch.options["system_prompt"] == "KEEP_PROMPT"
    assert tm.active_batch.options["qps"] == "9"
    # 重试归回原批次成果根目录（start_batch 会在其下新建 Batch_<ts> 子目录）
    assert Path(tm.active_batch.output_dir).parent == out_dir

    tm.active_thread.join(timeout=10)
    assert tm.active_batch.status == "completed"


# ---------- finalize 与补打 ----------

def test_finalize_keeps_manual_zip(tm, tmp_path):
    """generate_zip 关闭时收尾不得覆盖用户手动补打的 zip_path"""
    out_dir = tmp_path / "BatchZip"
    out_dir.mkdir()
    mono_f = _make_pdf(out_dir / "a.mono.pdf")
    batch = BatchRecord(
        batch_id="batch_manualzip", created_at="now", output_dir=str(out_dir),
        status="running",
        options={"output_mono": True, "output_dual": False, "generate_zip": False,
                 "zip_delivery_mode": "both"},
        tasks=[DocumentTask(id="t1", original_path="x", filename="a.pdf", file_hash="h",
                            status="success", mono_output=str(mono_f))],
    )
    batch.zip_path = str(out_dir / "manual.zip")
    tm.active_batch = batch
    tm._finalize_batch()
    assert batch.zip_path == str(out_dir / "manual.zip")


def test_repack_active_batch_writes_back_zip_path(tm, tmp_path):
    out_dir = tmp_path / "BatchActive"
    out_dir.mkdir()
    _make_pdf(out_dir / "doc_abc.mono.pdf")
    batch = BatchRecord(batch_id="batch_active_repack", created_at="now",
                        output_dir=str(out_dir), status="running", options={})
    tm.active_batch = batch

    ok, res = tm.pack_existing_batch_zip("batch_active_repack")
    assert ok
    assert batch.zip_path == res, "活动批次补打必须写回 BatchRecord 本体"
    assert Path(res).exists()


def test_safe_create_zip_duplicate_arcnames(tm, tmp_path):
    """多个同名 PDF 打包时条目必须逐次递增后缀，不得产生重复条目"""
    d1 = tmp_path / "d1"
    d1.mkdir()
    d2 = tmp_path / "d2"
    d2.mkdir()
    d3 = tmp_path / "d3"
    d3.mkdir()
    a1 = _make_pdf(d1 / "same.mono.pdf")
    a2 = _make_pdf(d2 / "same.mono.pdf")
    a3 = _make_pdf(d3 / "same.mono.pdf")

    zip_path = tmp_path / "dup.zip"
    assert TranslatorAdapter.safe_create_zip([a1, a2, a3], zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert len(names) == len(set(names)), "ZIP 内不得出现重复条目"


# ---------- 孤儿批次恢复 ----------

def test_orphan_running_record_demoted_on_load(tm):
    """上次进程退出残留的 running 记录，启动加载时应降级为 interrupted"""
    rec = {"batch_id": "batch_orphan_demo", "created_at": "now",
           "output_dir": "", "status": "running", "options": {}, "tasks": []}
    tm.history_records.insert(0, rec)
    tm._save_history()

    loaded = tm._load_history()
    orphan = next(r for r in loaded if r["batch_id"] == "batch_orphan_demo")
    assert orphan["status"] == "interrupted"

    # interrupted 批次的失败/取消任务应可重试
    ok, _ = tm.retry_failed_tasks("batch_orphan_demo", {})
    assert not ok  # 无输入文件可重试，但不能因为状态过滤而拒绝


# ---------- 并发卫生 ----------

def test_log_buffer_capped(tm):
    for i in range(6000):
        tm.log(f"line {i}\n")
    assert len(tm.logs) == 5000
    assert tm.logs[-1] == "line 5999\n"


# ---------- 未翻译回退检测 ----------

def _make_text_pdf(tmp_path, name, text):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), text)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return path


def test_looks_untranslated_detection(tmp_path):
    """内核限流静默回退（输出原文）必须被识别，避免把英文回退当成功"""
    from core.translator_adapter import _looks_untranslated

    en = _make_text_pdf(tmp_path, "en.pdf",
                        "Peak Pulse Power (8/20us) Ppp 75 W. Ultra low leakage nA level. Package DFN1006-3.")
    assert _looks_untranslated(en, "zh") is True

    zh = _make_text_pdf(tmp_path, "zh.pdf",
                        "特性 峰值脉冲功率 静电放电 符合以下标准 工作温度范围 存储温度范围")
    assert _looks_untranslated(zh, "zh") is False

    # 非中文目标语言不做判定
    assert _looks_untranslated(en, "en") is False
