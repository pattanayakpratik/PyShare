import os
import sys

# Ensure backend directory is in sys.path for direct or module execution
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import time
import threading
import ctypes
import webbrowser
import atexit
import webview
from PIL import Image, ImageDraw
import pystray
import main

# Windows Single-Instance Mutex
MUTEX_NAME = "Global\\PyShare_Desktop_App_Mutex"
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
WINDOW_TITLE = "PyShare — High-Speed File Transfer Studio"

def ensure_single_instance():
    """Ensure only one instance of PyShare Desktop App runs at any time on Windows."""
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        
        if last_error == ERROR_ALREADY_EXISTS:
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
            print("[*] Another instance of PyShare is already running. Focused existing window.")
            sys.exit(0)
            
        return mutex
    except Exception as e:
        print(f"[*] Single-instance check warning: {e}")
        return None

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_tray_icon_image():
    """Load app icon for system tray, with resilient fallback."""
    icon_path = get_resource_path("app_icon.png")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception:
            pass
    ico_path = get_resource_path("app_icon.ico")
    if os.path.exists(ico_path):
        try:
            return Image.open(ico_path)
        except Exception:
            pass
            
    # Fallback procedural icon
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 58, 58), fill=(0, 240, 255), outline=(100, 200, 255), width=3)
    return img

def start_native_app():
    # 0. Single instance check
    instance_mutex = ensure_single_instance()

    # 1. Start PyShare local server in background daemon thread
    server_thread = threading.Thread(target=main.start_server, daemon=True)
    server_thread.start()

    # Wait until server is bound and ready
    for _ in range(30):
        if getattr(main, 'httpd', None) is not None:
            break
        time.sleep(0.1)

    window_url = f"http://127.0.0.1:{main.ACTUAL_PORT}/"
    icon_path = get_resource_path("app_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    # Load persisted window geometry
    cfg = main.load_app_config()
    win_w = cfg.get("window_width", 1240)
    win_h = cfg.get("window_height", 780)
    win_x = cfg.get("window_x", None)
    win_y = cfg.get("window_y", None)

    window = webview.create_window(
        title=WINDOW_TITLE,
        url=window_url,
        width=win_w,
        height=win_h,
        x=win_x,
        y=win_y,
        min_size=(1050, 680),
        background_color="#060913",
        text_select=True
    )

    force_exit = False
    tray_icon = None
    first_minimize_notified = False

    def save_geometry():
        try:
            cur_cfg = main.load_app_config()
            cur_cfg["window_width"] = window.width
            cur_cfg["window_height"] = window.height
            cur_cfg["window_x"] = window.x
            cur_cfg["window_y"] = window.y
            main.save_app_config(cur_cfg)
        except Exception:
            pass

    def restore_window():
        try:
            window.show()
            window.restore()
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[*] Restore window notice: {e}")

    def on_window_closing():
        nonlocal first_minimize_notified
        if not force_exit:
            save_geometry()
            try:
                window.hide()
                if tray_icon and not first_minimize_notified:
                    first_minimize_notified = True
                    tray_icon.notify("PyShare is running in the background. Double-click tray icon to open.", "PyShare")
            except Exception:
                pass
            return False
        return True

    window.events.closing += on_window_closing

    def cleanup_and_exit():
        try:
            if tray_icon:
                tray_icon.stop()
        except Exception:
            pass
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

    def exit_application():
        nonlocal force_exit
        force_exit = True
        save_geometry()
        cleanup_and_exit()
        try:
            window.destroy()
        except Exception:
            pass
        sys.exit(0)

    def open_received_folder():
        try:
            rec_dir = getattr(main, 'UPLOAD_DIR', None)
            if rec_dir and os.path.exists(rec_dir):
                os.startfile(rec_dir)
        except Exception as e:
            print(f"[*] Open folder notice: {e}")

    def open_in_browser():
        try:
            webbrowser.open(window_url)
        except Exception:
            pass

    def check_updates_action():
        restore_window()
        try:
            window.evaluate_js("if (typeof checkForUpdates === 'function') { checkForUpdates(true); }")
        except Exception:
            webbrowser.open("https://github.com/pattanayakpratik/PyShare/releases")

    # Connect desktop notification hook
    def on_desktop_notification(title, message):
        if tray_icon:
            try:
                tray_icon.notify(message, title)
            except Exception:
                pass

    main.DESKTOP_NOTIFY_HOOK = on_desktop_notification

    # Initialize System Tray
    tray_image = load_tray_icon_image()
    tray_menu = pystray.Menu(
        pystray.MenuItem("Show PyShare Studio", lambda: restore_window(), default=True),
        pystray.MenuItem("Open Received Files", lambda: open_received_folder()),
        pystray.MenuItem("Open in Web Browser", lambda: open_in_browser()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Check for Updates...", lambda: check_updates_action()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit PyShare", lambda: exit_application())
    )

    tray_icon = pystray.Icon("PyShare", tray_image, "PyShare — File Transfer Studio", tray_menu)

    def run_tray():
        try:
            tray_icon.run()
        except Exception as e:
            print(f"[*] Tray error: {e}")

    tray_thread = threading.Thread(target=run_tray, daemon=True)
    tray_thread.start()

    atexit.register(cleanup_and_exit)

    # Run native window with icon
    webview.start(icon=icon_path, debug=False)

    # If window was destroyed directly, perform clean shutdown
    cleanup_and_exit()
    sys.exit(0)

if __name__ == "__main__":
    start_native_app()
