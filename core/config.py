import os
import sys
import json
import threading
from pathlib import Path


def get_base_dir() -> Path:
    """Project root: exe dir when frozen, otherwise repo root."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()


def get_config_path() -> Path:
    """Portable first: use data/ inside project when writable, else %APPDATA%."""
    portable_dir = BASE_DIR / "data"
    try:
        portable_dir.mkdir(parents=True, exist_ok=True)
        test_file = portable_dir / ".perm_check"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return portable_dir / "config.json"
    except Exception:
        pass
    appdata = Path(os.environ.get("APPDATA", Path.home())) / "BabelDOC-Hardware"
    appdata.mkdir(parents=True, exist_ok=True)
    return appdata / "config.json"


CONFIG_FILE = get_config_path()


def get_default_output_dir() -> str:
    """Default output folder: <home>/Documents/BabelDOC-output."""
    home = os.environ.get("USERPROFILE") or str(Path.home())
    return str(Path(home) / "Documents" / "BabelDOC-output")


def get_venv_python(prefer_windowless: bool = False) -> str:
    """Auto-detect a usable interpreter; never hard-code a drive letter.

    Order:
      1. python.exe next to the current interpreter (if running as pythonw.exe,
         the translation subprocess still needs python.exe to capture stdout)
      2. venv / .venv bundled inside the project (portable deployment)
      3. the current interpreter itself
    """
    exe_name = "pythonw.exe" if prefer_windowless else "python.exe"
    candidates = []
    try:
        cur = Path(sys.executable).resolve()
        candidates.append(cur.parent / exe_name)
    except Exception:
        pass

    candidates.extend([
        BASE_DIR / "venv" / "Scripts" / exe_name,
        BASE_DIR / ".venv" / "Scripts" / exe_name,
    ])

    for c in candidates:
        try:
            if c and Path(c).exists():
                return str(c)
        except Exception:
            continue
    return sys.executable


def _sanitize_output_dir(raw) -> str:
    """Fall back to the default folder when the path was copied from another
    machine (drive missing, or parent directories gone, e.g. old user profile)."""
    default = get_default_output_dir()
    if not raw or not isinstance(raw, str) or not raw.strip():
        return default
    try:
        p = Path(raw.strip())
        if p.exists() or p.parent.exists():
            return str(p)
        return default
    except Exception:
        return default


DEFAULT_CONFIG = {
    "base_url": "https://moyuu.cc/v1",
    "api_key": "",
    "model": "gemini-3.1-flash-lite-preview",
    "lang_in": "en",
    "lang_out": "zh",
    "qps": "4",
    "translate_table_text": True,
    "current_prompt_title": "🛠️ 硬件工程师 / 芯片规格书 (Datasheet)",
    "output_mono": False,
    "output_dual": True,
    "generate_zip": False,
    "zip_delivery_mode": "both",
    "output_dir": get_default_output_dir(),
}


# 配置读写的进程内互斥锁：save 是"读-改-写"，不加锁时并发保存会互相覆盖丢失更新。
# 可重入：save_app_config 内部会复用 load_app_config
_CONFIG_LOCK = threading.RLock()


def load_app_config() -> dict:
    with _CONFIG_LOCK:
        cfg = DEFAULT_CONFIG.copy()
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cfg.update(data)
            except Exception as e:
                print(f"Error loading config: {e}")

        cfg["output_dir"] = _sanitize_output_dir(cfg.get("output_dir"))
        return cfg


def save_app_config(cfg: dict):
    with _CONFIG_LOCK:
        try:
            current = load_app_config()
            current.update(cfg)
            current["output_dir"] = _sanitize_output_dir(current.get("output_dir"))
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = CONFIG_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            tmp_file.replace(CONFIG_FILE)
        except Exception as e:
            print(f"Error saving config: {e}")
