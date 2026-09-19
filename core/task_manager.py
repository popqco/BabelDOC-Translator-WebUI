import os
import sys
import time
import json
import shutil
import hashlib
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable

from core.config import get_base_dir, load_app_config
from core.translator_adapter import TranslatorAdapter, ensure_offline_assets

BASE_DIR = get_base_dir()

def calc_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class WindowsJobManager:
    """封装 Windows Job Object，安全追踪并杀死子进程树"""
    def __init__(self):
        self.job = None
        self._init_job()

    def _init_job(self):
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryLimit", ctypes.c_size_t),
                    ("PeakJobMemoryLimit", ctypes.c_size_t),
                ]

            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
            JobObjectExtendedLimitInformation = 9

            job = kernel32.CreateJobObjectW(None, None)
            if job:
                info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                kernel32.SetInformationJobObject(
                    job,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info)
                )
                self.job = job
        except Exception as e:
            print(f"[WARN] Failed to create Job Object: {e}")

    def assign_process(self, pid: int):
        if not self.job:
            return
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            h_proc = kernel32.OpenProcess(0x1F0FFF, False, pid)
            if h_proc:
                kernel32.AssignProcessToJobObject(self.job, h_proc)
                kernel32.CloseHandle(h_proc)
        except Exception as e:
            print(f"[WARN] Assign process to Job Object failed: {e}")

    def terminate_all(self):
        if not self.job:
            return
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.TerminateJobObject(self.job, 1)
            kernel32.CloseHandle(self.job)
        except Exception:
            pass
        self.job = None
        self._init_job()


@dataclass
class DocumentTask:
    id: str
    original_path: str
    filename: str
    file_hash: str
    status: str  # "pending", "processing", "success", "failed", "cancelled"
    mono_output: Optional[str] = None
    dual_output: Optional[str] = None
    cached_input_path: Optional[str] = None
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class BatchRecord:
    batch_id: str
    created_at: str
    output_dir: str
    status: str  # "running", "completed", "stopped", "failed"
    options: dict
    tasks: list[DocumentTask] = field(default_factory=list)
    zip_path: Optional[str] = None
    summary_message: str = ""


class TaskManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.lock = threading.RLock()
        self.job_manager = WindowsJobManager()

        self.storage_dir = BASE_DIR / "data" / "tasks"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_dir / "history.json"

        # 运行态状态
        self.active_batch: Optional[BatchRecord] = None
        self.active_thread: Optional[threading.Thread] = None
        self.stop_requested_mode: Optional[str] = None  # None, "stop_after_current", "cancel_immediately"
        self.current_proc_holder = {"proc": None}

        # 下一个批次的预备待翻译队列
        self.pending_queue: list[dict] = []  # [{"path": str, "name": str, "hash": str}]

        # 增量日志缓冲区
        self.logs: list[str] = []
        self.history_records: list[dict] = self._load_history()

        # 启动后执行一次 7 天输入缓存自动清理
        self.cleanup_expired_cache(days=7)

    def _load_history(self) -> list[dict]:
        records: list[dict] = []
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    records = [r for r in loaded if isinstance(r, dict)]
            except Exception as e:
                print(f"Error loading task history: {e}")

        # 跨电脑迁移后，历史记录里的绝对路径可能失效；统一打标，UI 据此提示
        for record in records:
            self._mark_history_availability(record)
        return records

    @staticmethod
    def _mark_history_availability(record: dict) -> None:
        """检查历史批次引用的文件/目录在本机是否仍存在，并在记录上打 available 标记。"""
        out_dir = record.get("output_dir") or ""
        record["available"] = bool(out_dir) and os.path.isdir(out_dir)

        zip_path = record.get("zip_path")
        if zip_path and not os.path.isfile(zip_path):
            record["zip_path"] = None

        for task in record.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            for key in ("mono_output", "dual_output"):
                p = task.get(key)
                if p and not os.path.isfile(p):
                    task[key] = None

    def _save_history(self):
        try:
            tmp_f = self.history_file.with_suffix(".tmp")
            with open(tmp_f, "w", encoding="utf-8") as f:
                json.dump(self.history_records, f, ensure_ascii=False, indent=2)
            tmp_f.replace(self.history_file)
        except Exception as e:
            print(f"Error saving task history: {e}")

    def log(self, msg: str):
        with self.lock:
            self.logs.append(msg)

    def get_logs(self) -> str:
        with self.lock:
            return "".join(self.logs)

    # ================= 队列管理 =================
    def add_to_pending(self, file_paths: list[str]) -> tuple[int, list[str]]:
        """添加文件到待翻译队列，并按 hash 排重"""
        with self.lock:
            added = 0
            existing_hashes = {item["hash"] for item in self.pending_queue}
            for p_str in file_paths:
                p = Path(p_str)
                if not p.exists() or not p.is_file():
                    continue
                f_hash = calc_file_hash(p)
                if f_hash not in existing_hashes:
                    self.pending_queue.append({
                        "path": str(p),
                        "name": p.name,
                        "hash": f_hash
                    })
                    existing_hashes.add(f_hash)
                    added += 1
            return added, [item["name"] for item in self.pending_queue]

    def remove_from_pending(self, index: int) -> list[str]:
        with self.lock:
            if 0 <= index < len(self.pending_queue):
                self.pending_queue.pop(index)
            return [item["name"] for item in self.pending_queue]

    def clear_pending(self):
        with self.lock:
            self.pending_queue.clear()

    # ================= 运行中追加文件 =================
    def append_to_active_batch(self, file_paths: list[str]) -> tuple[int, str]:
        """
        在批次运行过程中拖入新文件：
        若是正在翻译状态且未处于收尾打包/停止阶段，直接追加至当前活动批次的待处理队列！
        """
        with self.lock:
            if not self.active_batch or self.active_batch.status != "running":
                added, names = self.add_to_pending(file_paths)
                return added, "已加入下一批待翻译队列"

            if self.stop_requested_mode is not None:
                added, names = self.add_to_pending(file_paths)
                return added, "当前批次正在停止，已为您加入下一批待翻译队列"

            existing_hashes = {t.file_hash for t in self.active_batch.tasks}
            batch_dir = Path(self.active_batch.output_dir)
            cache_dir = batch_dir / ".input_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            added_count = 0
            for p_str in file_paths:
                p = Path(p_str)
                if not p.exists() or not p.is_file():
                    continue
                f_hash = calc_file_hash(p)
                if f_hash in existing_hashes:
                    continue

                # 暂存输入副本以备 7 天内重试
                cached_p = cache_dir / f"{p.stem}_{f_hash[:8]}{p.suffix}"
                try:
                    shutil.copyfile(p, cached_p)
                except Exception:
                    cached_p = p

                task = DocumentTask(
                    id=f"task_{len(self.active_batch.tasks)+1}_{int(time.time())}",
                    original_path=str(p),
                    filename=p.name,
                    file_hash=f_hash,
                    status="pending",
                    cached_input_path=str(cached_p)
                )
                self.active_batch.tasks.append(task)
                existing_hashes.add(f_hash)
                added_count += 1

            self.log(f"\n[动态追加] 成功向当前批次追加 {added_count} 个待翻译文档！\n")
            return added_count, f"已动态追加 {added_count} 个文件至当前运行批次"

    # ================= 停止控制 =================
    def request_stop(self, mode: str):
        """
        mode: "stop_after_current" | "cancel_immediately"
        """
        with self.lock:
            if not self.active_batch or self.active_batch.status != "running":
                return
            self.stop_requested_mode = mode
            if mode == "stop_after_current":
                self.log("\n[用户指令] 已请求【完成当前文档后停止】，后续排队文档将取消...\n")
            elif mode == "cancel_immediately":
                self.log("\n[用户指令] 已请求【立即取消整批任务】，正在强制终止当前翻译进程...\n")
                # 终止当前进程与 Job
                proc = self.current_proc_holder.get("proc")
                if proc:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                self.job_manager.terminate_all()

    # ================= 批次执行主循环 =================
    def start_batch(self, options: dict) -> bool:
        with self.lock:
            if self.active_thread and self.active_thread.is_alive():
                return False
            if not self.pending_queue:
                return False

            queue_snapshot = list(self.pending_queue)
            self.pending_queue.clear()
            self.stop_requested_mode = None
            self.logs.clear()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_id = f"batch_{timestamp}"

            base_out_dir = Path(options.get("output_dir") or BASE_DIR / "outputs")
            batch_dir = base_out_dir / f"Batch_{timestamp}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            cache_dir = batch_dir / ".input_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            tasks = []
            for idx, item in enumerate(queue_snapshot, start=1):
                orig_p = Path(item["path"])
                cached_p = cache_dir / f"{orig_p.stem}_{item['hash'][:8]}{orig_p.suffix}"
                try:
                    shutil.copyfile(orig_p, cached_p)
                except Exception:
                    cached_p = orig_p

                task = DocumentTask(
                    id=f"task_{idx}_{int(time.time())}",
                    original_path=item["path"],
                    filename=item["name"],
                    file_hash=item["hash"],
                    status="pending",
                    cached_input_path=str(cached_p)
                )
                tasks.append(task)

            self.active_batch = BatchRecord(
                batch_id=batch_id,
                created_at=datetime.now().isoformat(),
                output_dir=str(batch_dir),
                status="running",
                options=options,
                tasks=tasks
            )

            self.active_thread = threading.Thread(target=self._run_batch_worker, daemon=True)
            self.active_thread.start()
            return True

    def _run_batch_worker(self):
        batch = self.active_batch
        opts = batch.options
        batch_dir = Path(batch.output_dir)

        output_mono = opts.get("output_mono", False)
        output_dual = opts.get("output_dual", True)
        generate_zip = opts.get("generate_zip", False)
        zip_delivery_mode = opts.get("zip_delivery_mode", "both")

        self.log(f"=== 启动批次任务 {batch.batch_id} ===\n")
        self.log(f"输出配置: 仅译文(mono)={output_mono}, 双语对照(dual)={output_dual}, 打包ZIP={generate_zip} ({zip_delivery_mode})\n")
        self.log(f"成果存放目录: {batch_dir}\n")

        ensure_offline_assets()

        curr_idx = 0
        while True:
            with self.lock:
                if self.stop_requested_mode == "cancel_immediately":
                    # 将剩余所有 task 标记为 cancelled
                    for t in batch.tasks:
                        if t.status in ("pending", "processing"):
                            t.status = "cancelled"
                            t.error_message = "用户立即取消整批任务"
                    break

                # 寻找下一个待处理任务
                pending_tasks = [t for t in batch.tasks if t.status == "pending"]
                if not pending_tasks:
                    break
                task = pending_tasks[0]

                if self.stop_requested_mode == "stop_after_current":
                    for t in batch.tasks:
                        if t.status == "pending":
                            t.status = "cancelled"
                            t.error_message = "用户请求在当前文档后停止"
                    break

                task.status = "processing"
                task.start_time = time.time()
                curr_idx += 1
                total_cnt = len(batch.tasks)

            # 单文档独立隔离工作目录
            doc_work_dir = batch_dir / f".work_{task.id}"
            doc_work_dir.mkdir(parents=True, exist_ok=True)

            input_pdf = Path(task.cached_input_path or task.original_path)
            try:
                result = TranslatorAdapter.translate_single(
                    input_pdf=input_pdf,
                    work_dir=doc_work_dir,
                    base_url=opts.get("base_url", ""),
                    api_key=opts.get("api_key", ""),
                    model=opts.get("model", ""),
                    lang_in=opts.get("lang_in", "en"),
                    lang_out=opts.get("lang_out", "zh"),
                    output_mono=output_mono,
                    output_dual=output_dual,
                    qps=opts.get("qps", "4"),
                    translate_table_text=opts.get("translate_table_text", True),
                    system_prompt=opts.get("system_prompt", ""),
                    file_idx=curr_idx,
                    total_files=total_cnt,
                    log_cb=self.log,
                    job_object=self.job_manager.job,
                    proc_holder=self.current_proc_holder
                )

                # 将成果从隔离工作区移动至批次成果根目录（解决同名冲突）
                mono_final = None
                dual_final = None

                if result.get("mono"):
                    src = Path(result["mono"])
                    dst = batch_dir / src.name
                    if dst.exists():
                        dst = batch_dir / f"{src.stem}_{task.file_hash[:6]}{src.suffix}"
                    shutil.move(str(src), str(dst))
                    mono_final = str(dst)

                if result.get("dual"):
                    src = Path(result["dual"])
                    dst = batch_dir / src.name
                    if dst.exists():
                        dst = batch_dir / f"{src.stem}_{task.file_hash[:6]}{src.suffix}"
                    shutil.move(str(src), str(dst))
                    dual_final = str(dst)

                with self.lock:
                    task.status = "success"
                    task.mono_output = mono_final
                    task.dual_output = dual_final
                    task.end_time = time.time()

                # 清理临时单文档工作目录
                shutil.rmtree(doc_work_dir, ignore_errors=True)

            except Exception as e:
                with self.lock:
                    if self.stop_requested_mode == "cancel_immediately":
                        task.status = "cancelled"
                        task.error_message = "用户立即取消"
                    else:
                        task.status = "failed"
                        task.error_message = str(e)
                    task.end_time = time.time()
                self.log(f"✗ 处理 {task.filename} 出现异常: {e}\n")
                shutil.rmtree(doc_work_dir, ignore_errors=True)

        # 批次全部文档处理完毕，进入交付收尾与可选打包阶段
        self._finalize_batch()

    def _finalize_batch(self):
        batch = self.active_batch
        opts = batch.options
        batch_dir = Path(batch.output_dir)
        generate_zip = opts.get("generate_zip", False)
        zip_delivery_mode = opts.get("zip_delivery_mode", "both")

        success_tasks = [t for t in batch.tasks if t.status == "success"]
        failed_tasks = [t for t in batch.tasks if t.status == "failed"]
        cancelled_tasks = [t for t in batch.tasks if t.status == "cancelled"]

        # 统计实际生成的成果文件清单
        produced_pdfs: list[Path] = []
        for t in success_tasks:
            if t.mono_output and Path(t.mono_output).exists():
                produced_pdfs.append(Path(t.mono_output))
            if t.dual_output and Path(t.dual_output).exists():
                produced_pdfs.append(Path(t.dual_output))

        zip_archive_path = None
        if generate_zip and produced_pdfs:
            self.log("\n>>> 正在进行成果两步提交安全打包 ZIP...\n")
            zip_file = batch_dir / f"{batch.batch_id}_Archive.zip"
            try:
                TranslatorAdapter.safe_create_zip(produced_pdfs, zip_file, verify_content=True)
                zip_archive_path = str(zip_file)
                self.log(f"✓ 成功生成并校验交付包: {zip_file.name}\n")

                # 若选择 zip_only 交付模式，在 ZIP 校验成功后清理独立 PDF
                if zip_delivery_mode == "zip_only":
                    self.log(">>> [交付模式: 仅保留 ZIP] 正在清理本地独立 PDF...\n")
                    for p in produced_pdfs:
                        try:
                            p.unlink()
                        except Exception as e:
                            self.log(f"[WARN] 清理独立 PDF 失败 {p.name}: {e}\n")
                    self.log("✓ 独立 PDF 已安全清理，仅保留完整 ZIP 包！\n")
            except Exception as e:
                self.log(f"[ERROR] ZIP 打包或校验失败: {e}，将完整保留原 PDF 文件！\n")

        with self.lock:
            batch.zip_path = zip_archive_path
            if self.stop_requested_mode:
                batch.status = "stopped"
            elif failed_tasks and not success_tasks:
                batch.status = "failed"
            else:
                batch.status = "completed"

            summary = f"批次处理完毕: 成功 {len(success_tasks)} 个"
            if failed_tasks:
                summary += f", 失败 {len(failed_tasks)} 个"
            if cancelled_tasks:
                summary += f", 取消 {len(cancelled_tasks)} 个"
            batch.summary_message = summary

            # 持久化至历史记录
            self._record_history_entry(batch)

        self.log(f"\n=== {summary} ===\n")

    def _record_history_entry(self, batch: BatchRecord):
        # 序列化入历史文件
        record = {
            "batch_id": batch.batch_id,
            "created_at": batch.created_at,
            "output_dir": batch.output_dir,
            "status": batch.status,
            "options": {
                "output_mono": batch.options.get("output_mono"),
                "output_dual": batch.options.get("output_dual"),
                "generate_zip": batch.options.get("generate_zip"),
                "zip_delivery_mode": batch.options.get("zip_delivery_mode"),
                "lang_in": batch.options.get("lang_in"),
                "lang_out": batch.options.get("lang_out"),
                "model": batch.options.get("model"),
                "translate_table_text": batch.options.get("translate_table_text"),
                "current_prompt_title": batch.options.get("current_prompt_title")
            },
            "zip_path": batch.zip_path,
            "summary_message": batch.summary_message,
            "tasks": [asdict(t) for t in batch.tasks]
        }
        # 插入到最前
        self.history_records.insert(0, record)
        # 最多保留 100 条批次历史
        self.history_records = self.history_records[:100]
        self._save_history()

    # ================= 补打 ZIP (事后手动打包) =================
    def pack_existing_batch_zip(self, batch_id: str, delete_standalone_pdfs: bool = False) -> tuple[bool, str]:
        with self.lock:
            # 找到对应批次
            target_record = None
            if self.active_batch and self.active_batch.batch_id == batch_id:
                target_record = asdict(self.active_batch)
            else:
                for r in self.history_records:
                    if r["batch_id"] == batch_id:
                        target_record = r
                        break

            if not target_record:
                return False, "未找到指定的批次记录"

            batch_dir = Path(target_record["output_dir"])
            # 寻找该目录下所有成功生成的 pdf
            pdfs = list(batch_dir.glob("*.mono.pdf")) + list(batch_dir.glob("*.dual.pdf"))
            if not pdfs:
                return False, "该批次输出目录下未发现可打包的 PDF 文件"

            zip_file = batch_dir / f"{batch_id}_Archive.zip"
            try:
                TranslatorAdapter.safe_create_zip(pdfs, zip_file, verify_content=True)
                if delete_standalone_pdfs:
                    for p in pdfs:
                        try: p.unlink()
                        except Exception: pass

                # 更新历史记录中的 zip_path
                target_record["zip_path"] = str(zip_file)
                self._save_history()
                return True, str(zip_file)
            except Exception as e:
                return False, f"补打 ZIP 失败: {e}"

    # ================= 失败文档重试 =================
    def retry_failed_tasks(self, batch_id: str, current_connection_cfg: dict) -> bool:
        """
        重试指定批次中失败或已取消的文件：
        保留原方案的语言、提示词、输出模式，应用最新的 Base URL、API Key 与 Model！
        """
        with self.lock:
            if self.active_thread and self.active_thread.is_alive():
                return False

            target = None
            for r in self.history_records:
                if r["batch_id"] == batch_id:
                    target = r
                    break

            if not target:
                return False

            failed_tasks = [t for t in target["tasks"] if t["status"] in ("failed", "cancelled")]
            if not failed_tasks:
                return False

            # 重新组装待翻译队列
            self.pending_queue.clear()
            for t in failed_tasks:
                cached_p = Path(t.get("cached_input_path") or "")
                orig_p = Path(t.get("original_path") or "")
                valid_p = None
                if cached_p.exists():
                    valid_p = cached_p
                elif orig_p.exists():
                    valid_p = orig_p

                if valid_p:
                    self.pending_queue.append({
                        "path": str(valid_p),
                        "name": t["filename"],
                        "hash": t["file_hash"]
                    })

            if not self.pending_queue:
                return False

            # 构造新的执行参数：继承原任务语言与模板参数，覆盖当前连接配置
            merged_opts = dict(target["options"])
            merged_opts.update({
                "base_url": current_connection_cfg.get("base_url"),
                "api_key": current_connection_cfg.get("api_key"),
                "model": current_connection_cfg.get("model"),
                "output_dir": target["output_dir"]  # 归回原批次成果目录
            })

            return self.start_batch(merged_opts)

    # ================= 7天过期输入缓存清理 =================
    def cleanup_expired_cache(self, days: int = 7):
        try:
            now = datetime.now()
            cutoff = now - timedelta(days=days)

            # 遍历所有 outputs 目录下的 .input_cache
            base_out = BASE_DIR / "outputs"
            if base_out.exists():
                for cache_folder in base_out.glob("*/.input_cache"):
                    if cache_folder.is_dir():
                        for item in cache_folder.glob("*"):
                            mtime = datetime.fromtimestamp(item.stat().st_mtime)
                            if mtime < cutoff:
                                try: item.unlink()
                                except Exception: pass

            # 遍历用户自定义 output_dir 中的 .input_cache
            cfg = load_app_config()
            user_out = Path(cfg.get("output_dir", ""))
            if user_out.exists() and user_out != base_out:
                for cache_folder in user_out.glob("*/.input_cache"):
                    if cache_folder.is_dir():
                        for item in cache_folder.glob("*"):
                            mtime = datetime.fromtimestamp(item.stat().st_mtime)
                            if mtime < cutoff:
                                try: item.unlink()
                                except Exception: pass
        except Exception as e:
            print(f"Error cleaning expired cache: {e}")