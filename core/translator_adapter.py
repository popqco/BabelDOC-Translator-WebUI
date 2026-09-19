import os
import shutil
import zipfile
import subprocess
from pathlib import Path
from core.config import get_base_dir, get_venv_python

BASE_DIR = get_base_dir()

def get_kernel32():
    """返回已声明 argtypes/restype 的 kernel32 实例。

    显式声明原型可避免 64 位 HANDLE 被默认 int 返回值截断的隐患；
    Job Object 的挂接与终止（task_manager / translator_adapter）共用此入口。
    """
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32

def ensure_offline_assets():
    local_fonts = BASE_DIR / "assets" / "fonts"
    local_models = BASE_DIR / "assets" / "models"
    cache_dir = Path.home() / ".cache" / "babeldoc"
    cache_fonts = cache_dir / "fonts"
    cache_models = cache_dir / "models"
    cache_fonts.mkdir(parents=True, exist_ok=True)
    cache_models.mkdir(parents=True, exist_ok=True)

    if local_fonts.exists():
        for f in local_fonts.glob("*.ttf"):
            dst = cache_fonts / f.name
            if not dst.exists() or dst.stat().st_size == 0:
                shutil.copyfile(f, dst)

    if local_models.exists():
        for m in local_models.glob("*"):
            if m.is_file():
                dst = cache_models / m.name
                if not dst.exists() or dst.stat().st_size == 0:
                    shutil.copyfile(m, dst)

class TranslatorAdapter:
    @staticmethod
    def discover_outputs(work_dir: Path, stem: str, output_mono: bool, output_dual: bool) -> dict:
        """在隔离工作目录中定位内核产物。

        内核（BabelDOC 0.6.4）以 f"{input_stem}.{lang_out}.mono/dual.pdf" 命名
        且不改写 stem，因此用 startswith/endswith 过滤而非 glob 模式——
        文件名含 [ ] * ? 时 glob 模式会失效。
        """
        produced = []
        if work_dir.exists():
            produced = sorted(
                (p for p in work_dir.iterdir() if p.is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

        mono_path = None
        dual_path = None

        if output_mono:
            mono_cands = [p for p in produced
                          if p.name.startswith(stem) and p.name.endswith(".mono.pdf")]
            if not mono_cands:
                raise FileNotFoundError(f"未找到内核生成的仅译文版 PDF: {stem}")
            mono_path = mono_cands[0]

        if output_dual:
            dual_cands = [p for p in produced
                          if p.name.startswith(stem) and p.name.endswith(".dual.pdf")]
            if not dual_cands:
                raise FileNotFoundError(f"未找到内核生成的双语对照版 PDF: {stem}")
            dual_path = dual_cands[0]

        return {"mono": mono_path, "dual": dual_path}

    @staticmethod
    def translate_single(
        input_pdf: Path,
        work_dir: Path,
        base_url: str,
        api_key: str,
        model: str,
        lang_in: str,
        lang_out: str,
        output_mono: bool = False,
        output_dual: bool = True,
        qps: str = "4",
        translate_table_text: bool = True,
        system_prompt: str = "",
        file_idx: int = 1,
        total_files: int = 1,
        progress_cb=None,
        log_cb=None,
        job_object=None,
        proc_holder=None
    ) -> dict:
        """
        在隔离的 work_dir 执行 BabelDOC 翻译。
        返回结构化字典:
        {
            "mono": Path | None,
            "dual": Path | None,
            "success": bool,
            "error": str | None
        }
        """
        if not output_mono and not output_dual:
            raise ValueError("至少需要选择一种 PDF 成果类型（仅译文 mono 或 双语对照 dual）！")

        work_dir.mkdir(parents=True, exist_ok=True)

        py_exec = get_venv_python(prefer_windowless=False)

        cmd = [
            py_exec,
            "-m", "babeldoc.main",
            "--files", str(input_pdf),
            "--output", str(work_dir),
            "--lang-in", lang_in.strip(),
            "--lang-out", lang_out.strip(),
            "--qps", str(qps),
            "--openai",
            "--openai-base-url", base_url.strip(),
            # BabelDOC 0.6.4 强制要求经 CLI 传入 key（main.py 校验，无环境变量回退），
            # 因此 key 会出现在子进程命令行中；本应用为单用户本机场景，风险可接受
            "--openai-api-key", api_key.strip(),
            "--openai-model", model.strip(),
        ]

        # 内核生成控制：若不输出某类型，则传对应禁参数
        if not output_mono:
            cmd.append("--no-mono")
        if not output_dual:
            cmd.append("--no-dual")

        if translate_table_text:
            cmd.append("--translate-table-text")
        if system_prompt and system_prompt.strip():
            cmd.extend(["--custom-system-prompt", system_prompt.strip()])

        base_pct = (file_idx - 1) / total_files
        file_span = 1.0 / total_files

        if progress_cb:
            progress_cb(base_pct + file_span * 0.1, f"[{file_idx}/{total_files}] 正在解析 {input_pdf.name} 版面与结构...")
        if log_cb:
            log_cb(f"\n>>> 开始处理 [{file_idx}/{total_files}]: {input_pdf.name}\n")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # 主进程为 pythonw（无控制台）时，控制台型子进程会被 Windows 分配
        # 一个可见的黑框窗口；用户顺手关掉它会直接杀死内核（0xC000013A）。
        # CREATE_NO_WINDOW 让子进程持有隐藏控制台，stdout 管道照常工作。
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        # 启动翻译进程
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=creationflags
        )

        if proc_holder is not None:
            proc_holder['proc'] = proc

        # 若提供了 Windows Job Object，将子进程挂载进 job，确保无泄漏
        if job_object:
            try:
                import ctypes
                kernel32 = get_kernel32()
                h_proc = kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
                if h_proc:
                    kernel32.AssignProcessToJobObject(job_object, h_proc)
                    kernel32.CloseHandle(h_proc)
                elif log_cb:
                    log_cb(f"[WARN] 打开子进程句柄失败（错误码 {ctypes.get_last_error()}），该进程不受 Job Object 保护\n")
            except Exception as e:
                if log_cb:
                    log_cb(f"[WARN] 挂载 Job Object 失败: {e}\n")

        try:
            for line in iter(proc.stdout.readline, ''):
                line = line.strip()
                if line:
                    if log_cb:
                        log_cb(line + "\n")
                    if "%" in line and progress_cb:
                        progress_cb(base_pct + file_span * 0.6, f"[{file_idx}/{total_files}] 翻译中: {input_pdf.name}")
        except Exception:
            # 读循环异常（如用户取消导致的 IO 错误）时回收子进程，防止孤儿进程
            try:
                proc.kill()
            except Exception:
                pass
            raise
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            if proc_holder is not None:
                proc_holder['proc'] = None

        code = proc.wait()

        if code != 0:
            raise RuntimeError(f"文件 {input_pdf.name} 内核执行异常，退出代码: {code}")

        # 检查隔离目录中实际生成的产物
        paths = TranslatorAdapter.discover_outputs(work_dir, input_pdf.stem, output_mono, output_dual)
        mono_path = paths["mono"]
        dual_path = paths["dual"]

        if log_cb:
            produced_names = []
            if mono_path:
                produced_names.append(mono_path.name)
            if dual_path:
                produced_names.append(dual_path.name)
            log_cb(f"✓ [{file_idx}/{total_files}] 成功生成: {', '.join(produced_names)}\n")

        return {
            "mono": mono_path,
            "dual": dual_path,
            "success": True,
            "error": None
        }

    @staticmethod
    def safe_create_zip(source_pdf_paths: list[Path], zip_path: Path, verify_content: bool = True) -> bool:
        """
        两步提交法安全打包 ZIP：
        1. 写入临时 .zip.tmp 文件
        2. 校验文件存在性、ZIP 目录完整性与 testzip
        3. 原子替换为正式 .zip 文件
        """
        if not source_pdf_paths:
            return False

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_zip = zip_path.with_name(f"{zip_path.name}.tmp")
        if tmp_zip.exists():
            tmp_zip.unlink()

        try:
            with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                seen_names = set()
                for p in source_pdf_paths:
                    if not p.exists():
                        raise FileNotFoundError(f"待打包文件不存在: {p}")
                    arcname = p.name
                    if arcname in seen_names:
                        # 逐次递增后缀，保证任意多次重名都能生成唯一条目
                        base, ext = os.path.splitext(p.name)
                        n = 1
                        while f"{base}_{n}{ext}" in seen_names:
                            n += 1
                        arcname = f"{base}_{n}{ext}"
                    seen_names.add(arcname)
                    zf.write(p, arcname=arcname)

            if verify_content:
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    corrupt = zf.testzip()
                    if corrupt is not None:
                        raise zipfile.BadZipFile(f"ZIP 校验发现损坏条目: {corrupt}")
                    names = zf.namelist()
                    if len(names) != len(source_pdf_paths):
                        raise ValueError(f"ZIP 条目数不一致: 预期 {len(source_pdf_paths)}, 实际 {len(names)}")

            # 原子重命名
            tmp_zip.replace(zip_path)
            return True
        except Exception:
            if tmp_zip.exists():
                try:
                    tmp_zip.unlink()
                except Exception:
                    pass
            raise