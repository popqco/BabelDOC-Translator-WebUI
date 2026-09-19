import os
import sys

# 本机若开着系统代理（Clash 等），Gradio 对 127.0.0.1 的启动自检会被代理
# 拦截并返回 502。强制回环地址直连，不影响对外 API 的代理设置。
_no_proxy = os.environ.get("NO_PROXY", "")
for _host in ("127.0.0.1", "localhost"):
    if _host not in _no_proxy.split(","):
        _no_proxy = f"{_no_proxy},{_host}" if _no_proxy else _host
os.environ["NO_PROXY"] = os.environ["no_proxy"] = _no_proxy

import time
import socket
import threading
import webview
from ui.view import create_ui

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def start_server(demo, port):
    # Quiet server launch in subthread
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        prevent_thread_lock=True,
        show_error=True,
        quiet=True
    )

def main():
    demo = create_ui()
    # 默认随机空闲端口；设置 BABELDOC_PORT 可固定（便于排障/防火墙放行）
    port = int(os.environ.get("BABELDOC_PORT") or 0) or find_free_port()
    
    # Start web server in background daemon thread
    server_thread = threading.Thread(target=start_server, args=(demo, port), daemon=True)
    server_thread.start()
    
    # Wait until port is ready
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                break
        except Exception:
            time.sleep(0.1)

    # Launch native desktop window via WebView2
    window = webview.create_window(
        title="BabelDOC 科技文档翻译器",
        url=url,
        width=1380,
        height=900,
        min_size=(1000, 680),
        background_color="#FAF9F5"
    )
    
    # Start native window loop (blocking until window is closed)
    webview.start(gui="edgechromium")
    
    # When window closes, cleanly exit python process
    os._exit(0)

if __name__ == "__main__":
    main()
