import os
import sys
import time
import threading
import webview
import main

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def start_native_app():
    # 1. Start PyShare local server in background daemon thread
    server_thread = threading.Thread(target=main.start_server, daemon=True)
    server_thread.start()

    # Wait until server is bound and ready
    for _ in range(30):
        if getattr(main, 'httpd', None) is not None:
            break
        time.sleep(0.1)

    # 2. Render exact Web UI in native desktop window with pywebview (Edge WebView2)
    window_url = f"http://127.0.0.1:{main.ACTUAL_PORT}/"
    icon_path = get_resource_path("app_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    window = webview.create_window(
        title="PyShare — High-Speed File Transfer Studio",
        url=window_url,
        width=1240,
        height=780,
        min_size=(1050, 680),
        background_color="#060913",
        text_select=True
    )
    
    # Run native window with icon
    webview.start(icon=icon_path, debug=False)

    # Safe shutdown on window close
    try:
        main.stop_tunnel()
        if getattr(main, 'zc', None):
            try:
                main.zc.unregister_all_services()
                main.zc.close()
            except Exception:
                pass
        if getattr(main, 'httpd', None):
            main.httpd.shutdown()
            main.httpd.server_close()
    except Exception:
        pass
    sys.exit(0)

if __name__ == "__main__":
    start_native_app()
