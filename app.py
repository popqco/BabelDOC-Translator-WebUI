import os
import sys

# 本机若开着系统代理（Clash 等），Gradio 对 127.0.0.1 的启动自检会被代理
# 拦截并返回 502。强制回环地址直连，不影响对外 API 的代理设置。
_no_proxy = os.environ.get("NO_PROXY", "")
for _host in ("127.0.0.1", "localhost"):
    if _host not in _no_proxy.split(","):
        _no_proxy = f"{_no_proxy},{_host}" if _no_proxy else _host
os.environ["NO_PROXY"] = os.environ["no_proxy"] = _no_proxy

import threading
import webview
from ui.view import create_ui
from core.task_manager import TaskManager


def alert_error(message: str):
    """桌面窗口尚未建立时的原生错误弹窗（不依赖 webview 可用性）。"""
    try:
        import ctypes
        # MB_ICONERROR
        ctypes.windll.user32.MessageBoxW(None, message, "BabelDOC 翻译器启动失败", 0x10)
    except Exception:
        print(message)


def start_server(demo, result):
    try:
        demo.launch(
            server_name="127.0.0.1",
            # 传入 None 让 Gradio 自选空闲端口，消除"先探测后绑定"的竞态窗口；
            # 需要固定端口时通过 BABELDOC_PORT 环境变量指定（便于排障/防火墙放行）
            server_port=result["port"],
            prevent_thread_lock=True,
            quiet=True
        )
        result["url"] = demo.local_url or f"http://127.0.0.1:{demo.server_port}"
    except Exception as e:
        result["error"] = str(e)
    finally:
        result["event"].set()


def on_closing():
    """窗口关闭前确认：批次运行中时防止误关导致任务静默中断。"""
    try:
        tm = TaskManager()
        with tm.lock:
            running = bool(tm.active_batch and tm.active_batch.status == "running")
        if running:
            import ctypes
            # MB_OKCANCEL | MB_ICONWARNING
            choice = ctypes.windll.user32.MessageBoxW(
                None,
                "仍有翻译批次正在运行。\n\n关闭窗口会中断当前批次：已完成文件保留，"
                "未完成任务将标记为中断（重启后可见，可重试）。\n\n确定要关闭吗？",
                "BabelDOC 翻译器",
                0x1 | 0x30,
            )
            if choice != 1:  # IDOK
                return False
    except Exception:
        pass
    return True


def main():
    demo = create_ui()

    raw_port = os.environ.get("BABELDOC_PORT", "").strip()
    fixed_port = None
    if raw_port:
        try:
            fixed_port = int(raw_port)
        except ValueError:
            print(f"[WARN] BABELDOC_PORT={raw_port!r} 不是合法端口号，忽略并使用随机端口。")

    result = {"event": threading.Event(), "url": None, "error": None, "port": fixed_port}
    server_thread = threading.Thread(target=start_server, args=(demo, result), daemon=True)
    server_thread.start()

    # 等待 Web 服务就绪；失败/超时则明确报错退出，绝不打开死地址的窗口
    if not result["event"].wait(timeout=60):
        alert_error("Web 服务启动超时（60 秒）。请检查本机防火墙或代理设置后重试。")
        sys.exit(1)
    if result["error"] or not result["url"]:
        alert_error(f"Web 服务启动失败：{result['error'] or '未知错误'}")
        sys.exit(1)

    window = webview.create_window(
        title="BabelDOC 科技文档翻译器",
        url=result["url"],
        width=1380,
        height=900,
        min_size=(1000, 680),
        background_color="#FAF9F5"
    )
    window.events.closing += on_closing

    # 阻塞直至窗口关闭
    webview.start(gui="edgechromium")

    # 窗口已关闭：将仍在运行的批次标记为中断并落盘历史，再安全退出
    try:
        TaskManager().finalize_interrupted()
    except Exception:
        pass
    os._exit(0)


if __name__ == "__main__":
    main()
