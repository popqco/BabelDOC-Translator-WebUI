import os
import sys
import time
import shutil
import zipfile
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import load_app_config, save_app_config
from core.translator_adapter import TranslatorAdapter
from core.task_manager import TaskManager, DocumentTask, BatchRecord

class TestSelectiveOutputsAndTaskManager(unittest.TestCase):
    def setUp(self):
        # data/ 已由 conftest.isolated_runtime 重定向至临时目录，无需再备份真实数据
        self.test_root = BASE_DIR / "tests" / "test_scratch"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.fixture_a = self.test_root / "test_doc_a.pdf"
        self.fixture_b = self.test_root / "test_doc_b.pdf"
        self._create_dummy_pdf(self.fixture_a, "Doc A Content")
        self._create_dummy_pdf(self.fixture_b, "Doc B Content")

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def _create_dummy_pdf(self, path: Path, text: str):
        # Minimal valid PDF
        content = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 50 700 Td (" + text.encode() + b") Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000206 00000 n\n"
            b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n300\n%%EOF\n"
        )
        path.write_bytes(content)

    def test_01_config_persistence(self):
        """测试输出开关配置保存与重新读取"""
        test_cfg = {
            "output_mono": True,
            "output_dual": False,
            "generate_zip": True,
            "zip_delivery_mode": "zip_only",
            "output_dir": str(self.test_root / "CustomOut")
        }
        save_app_config(test_cfg)
        loaded = load_app_config()
        self.assertEqual(loaded["output_mono"], True)
        self.assertEqual(loaded["output_dual"], False)
        self.assertEqual(loaded["generate_zip"], True)
        self.assertEqual(loaded["zip_delivery_mode"], "zip_only")
        self.assertEqual(loaded["output_dir"], str(self.test_root / "CustomOut"))

    def test_02_safe_zip_creation_and_validation(self):
        """测试两步提交 ZIP 创建与损坏检测"""
        zip_target = self.test_root / "output.zip"
        # 正常打包
        ok = TranslatorAdapter.safe_create_zip([self.fixture_a, self.fixture_b], zip_target, verify_content=True)
        self.assertTrue(ok)
        self.assertTrue(zip_target.exists())
        self.assertFalse(zip_target.with_suffix(".zip.tmp").exists())

        with zipfile.ZipFile(zip_target, "r") as zf:
            self.assertEqual(len(zf.namelist()), 2)
            self.assertIsNone(zf.testzip())

        # 校验不存在文件时抛出异常且不残留临时文件
        non_existent = self.test_root / "none.pdf"
        with self.assertRaises(FileNotFoundError):
            TranslatorAdapter.safe_create_zip([non_existent], self.test_root / "fail.zip")
        self.assertFalse((self.test_root / "fail.zip.tmp").exists())

    def test_03_mock_matrix_outputs_and_delivery(self):
        """
        验证 3 种产物模式 (mono only, dual only, both) × 3 种交付模式 (no zip, both, zip_only)
        的实际磁盘落盘与状态更新
        """
        modes = [
            (True, False),  # mono only
            (False, True),  # dual only
            (True, True),   # both
        ]
        deliveries = [
            (False, "both"),     # no zip
            (True, "both"),      # PDF + ZIP
            (True, "zip_only"),  # 仅保留 ZIP
        ]

        tm = TaskManager()

        for mono_opt, dual_opt in modes:
            for zip_opt, zip_deliv in deliveries:
                batch_out = self.test_root / f"Batch_M{int(mono_opt)}_D{int(dual_opt)}_Z{int(zip_opt)}_{zip_deliv}"
                batch_out.mkdir(parents=True, exist_ok=True)

                # 模拟任务
                t1 = DocumentTask(
                    id="t1",
                    original_path=str(self.fixture_a),
                    filename=self.fixture_a.name,
                    file_hash="hash_a",
                    status="success"
                )
                if mono_opt:
                    mono_f = batch_out / f"{self.fixture_a.stem}.mono.pdf"
                    self._create_dummy_pdf(mono_f, "Mono content")
                    t1.mono_output = str(mono_f)
                if dual_opt:
                    dual_f = batch_out / f"{self.fixture_a.stem}.dual.pdf"
                    self._create_dummy_pdf(dual_f, "Dual content")
                    t1.dual_output = str(dual_f)

                batch = BatchRecord(
                    batch_id=f"test_{batch_out.name}",
                    created_at="2026-09-18T00:00:00",
                    output_dir=str(batch_out),
                    status="running",
                    options={
                        "output_mono": mono_opt,
                        "output_dual": dual_opt,
                        "generate_zip": zip_opt,
                        "zip_delivery_mode": zip_deliv
                    },
                    tasks=[t1]
                )
                tm.active_batch = batch
                tm._finalize_batch()

                # 断言落盘结果
                if zip_opt:
                    self.assertIsNotNone(batch.zip_path)
                    self.assertTrue(Path(batch.zip_path).exists())
                    with zipfile.ZipFile(batch.zip_path, "r") as zf:
                        expected_count = (1 if mono_opt else 0) + (1 if dual_opt else 0)
                        self.assertEqual(len(zf.namelist()), expected_count)

                    if zip_deliv == "zip_only":
                        # 独立 PDF 必须被安全清除
                        if mono_opt:
                            self.assertFalse((batch_out / f"{self.fixture_a.stem}.mono.pdf").exists())
                        if dual_opt:
                            self.assertFalse((batch_out / f"{self.fixture_a.stem}.dual.pdf").exists())
                    else:
                        # both 模式：PDF 和 ZIP 并存
                        if mono_opt:
                            self.assertTrue((batch_out / f"{self.fixture_a.stem}.mono.pdf").exists())
                        if dual_opt:
                            self.assertTrue((batch_out / f"{self.fixture_a.stem}.dual.pdf").exists())
                else:
                    self.assertIsNone(batch.zip_path)
                    if mono_opt:
                        self.assertTrue((batch_out / f"{self.fixture_a.stem}.mono.pdf").exists())
                    if dual_opt:
                        self.assertTrue((batch_out / f"{self.fixture_a.stem}.dual.pdf").exists())

    def test_04_repack_existing_batch(self):
        """测试事后手动补打 ZIP，不重新调用翻译"""
        tm = TaskManager()
        batch_out = self.test_root / "Batch_Repack"
        batch_out.mkdir(parents=True, exist_ok=True)
        pdf_f = batch_out / "sample.dual.pdf"
        self._create_dummy_pdf(pdf_f, "Dual content")

        batch_id = "batch_repack_01"
        tm.history_records.insert(0, {
            "batch_id": batch_id,
            "created_at": "2026-09-18T00:00:00",
            "output_dir": str(batch_out),
            "status": "completed",
            "options": {},
            "tasks": []
        })

        ok, zip_res = tm.pack_existing_batch_zip(batch_id, delete_standalone_pdfs=False)
        self.assertTrue(ok)
        self.assertTrue(Path(zip_res).exists())
        self.assertTrue(pdf_f.exists())  # 独立 PDF 仍然保留

    def test_05_expired_cache_cleanup(self):
        """测试 7 天过期输入缓存清理边界"""
        tm = TaskManager()
        cache_dir = self.test_root / "OutBatch" / ".input_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        old_file = cache_dir / "old_cached.pdf"
        new_file = cache_dir / "new_cached.pdf"
        self._create_dummy_pdf(old_file, "old")
        self._create_dummy_pdf(new_file, "new")

        # 将 old_file 修改时间修改为 10 天前
        past_time = time.time() - (10 * 86400)
        os.utime(str(old_file), (past_time, past_time))

        # 执行清理
        save_app_config({"output_dir": str(self.test_root)})
        tm.cleanup_expired_cache(days=7)

        self.assertFalse(old_file.exists(), "超过 7 天的缓存应被清理")
        self.assertTrue(new_file.exists(), "未超过 7 天的缓存应被保留")

if __name__ == "__main__":
    unittest.main(verbosity=2)