import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime
from pathlib import Path
from core.config import get_base_dir, get_venv_python

BASE_DIR = get_base_dir()

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

        # 启动翻译进程
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env
        )

        if proc_holder is not None:
            proc_holder['proc'] = proc

        # 若提供了 Windows Job Object，将子进程挂载进 job，确保无泄漏
        if job_object:
            try:
                import ctypes
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                h_proc = kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
                if h_proc:
                    kernel32.AssignProcessToJobObject(job_object, h_proc)
                    kernel32.CloseHandle(h_proc)
            except Exception as e:
                if log_cb:
                    log_cb(f"[WARN] 挂载 Job Object 失败: {e}\n")

        for line in iter(proc.stdout.readline, ''):
            line = line.strip()
            if line:
                if log_cb:
                    log_cb(line + "\n")
                if "%" in line and progress_cb:
                    progress_cb(base_pct + file_span * 0.6, f"[{file_idx}/{total_files}] 翻译中: {input_pdf.name}")

        proc.stdout.close()
        code = proc.wait()

        if proc_holder is not None:
            proc_holder['proc'] = None

        if code != 0:
            raise RuntimeError(f"文件 {input_pdf.name} 内核执行异常，退出代码: {code}")

        # 检查隔离目录中实际生成的产物
        stem = input_pdf.stem
        mono_path = None
        dual_path = None

        if output_mono:
            # 查找 mono 候选文件
            mono_cands = list(work_dir.glob(f"{stem}*.mono.pdf")) or list(work_dir.glob("*mono.pdf"))
            if mono_cands:
                mono_cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                mono_path = mono_cands[0]
            else:
                raise FileNotFoundError(f"未找到内核生成的仅译文版 PDF: {stem}")

        if output_dual:
            # 查找 dual 候选文件
            dual_cands = list(work_dir.glob(f"{stem}*.dual.pdf")) or list(work_dir.glob("*dual.pdf"))
            if dual_cands:
                dual_cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                dual_path = dual_cands[0]
            else:
                raise FileNotFoundError(f"未找到内核生成的双语对照版 PDF: {stem}")

        if log_cb:
            produced_names = []
            if mono_path: produced_names.append(mono_path.name)
            if dual_path: produced_names.append(dual_path.name)
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
                        arcname = f"{p.parent.name}_{p.name}"
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
        except Exception as e:
            if tmp_zip.exists():
                try: tmp_zip.unlink()
                except Exception: pass
            raise e