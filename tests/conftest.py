"""测试隔离：所有运行时状态（data/ 下的配置、历史、暂存）重定向到临时目录。

测试进程与真实应用共享 TaskManager 单例，若不隔离会直接读写仓库内
data/config.json 与 history.json（其中含真实 API Key 与用户历史）。
本 conftest 以 session 级 fixture 在导入后、首次实例化前重定向路径，
singleton 的派生目录（storage_dir / pending_dir / history_file）随之落到临时目录。
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def isolated_runtime(tmp_path_factory):
    """把 config / task_manager 的 BASE_DIR 与 CONFIG_FILE 指向会话级临时目录。

    直接赋值（而非 monkeypatch）：单例在首个测试创建后路径即固化，
    后续测试必须继续命中同一临时目录，不能被 fixture 自动还原。
    """
    import core.config as config_mod
    import core.task_manager as tm_mod

    runtime_root = tmp_path_factory.mktemp("runtime")
    data_dir = runtime_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    config_mod.BASE_DIR = runtime_root
    config_mod.CONFIG_FILE = data_dir / "config.json"
    tm_mod.BASE_DIR = runtime_root
    yield runtime_root


@pytest.fixture(autouse=True)
def reset_task_manager():
    """每个用例前后重置单例的运行态，保证用例互不污染。"""
    from core.task_manager import TaskManager

    tm = TaskManager()
    tm.pending_queue.clear()
    tm.active_batch = None
    tm.active_thread = None
    tm.stop_requested_mode = None
    tm.current_proc_holder["proc"] = None
    tm.logs.clear()
    tm.history_records = tm._load_history()
    yield tm
    tm.pending_queue.clear()
    tm.active_batch = None
    tm.active_thread = None
    tm.stop_requested_mode = None
    tm.logs.clear()
