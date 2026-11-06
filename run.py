"""
PyShare Launcher
================
Run with no arguments to start the Native Desktop GUI:
    python run.py

Or pass '--server', '--headless', or '--no-gui' to run the Headless Web Server:
    python run.py --server
"""
import sys
import os

# Ensure the 'backend' directory is in Python's search path
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")
APP_DIR = backend_dir if os.path.isdir(backend_dir) else os.path.join(root_dir, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

def main_launcher():
    """Main cross-platform entrypoint with graceful GUI to headless fallback."""
    # Optional uninstaller cleanup mode
    if "--uninstall" in sys.argv or "--cleanup" in sys.argv:
        delete_files = "--delete-files" in sys.argv
        if not delete_files and sys.stdin.isatty():
            try:
                ans = input("Do you want to delete shared and received files (PyShare_Files)? [y/N]: ").strip().lower()
                delete_files = ans in ('y', 'yes')
            except Exception:
                delete_files = False
        elif not delete_files and not sys.stdin.isatty() and sys.platform == "win32":
            try:
                import ctypes
                res = ctypes.windll.user32.MessageBoxW(
                    None,
                    "Do you want to delete all shared and received files in PyShare_Files?",
                    "PyShare Uninstall",
                    0x00000004 | 0x00000020 | 0x00000100
                )
                delete_files = (res == 6)  # IDYES = 6
            except Exception:
                delete_files = False

        import main
        result = main.cleanup_sharing_files(delete_shared=delete_files, delete_received=delete_files, delete_config=True)
        print("[*] PyShare uninstall cleanup complete:", result)
        return

    if "--server" in sys.argv or "--headless" in sys.argv or "--no-gui" in sys.argv:
        import main
        main.start_server()
        return

    # Check for headless environment on Linux / Unix (no DISPLAY or WAYLAND_DISPLAY)
    if sys.platform != "win32" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("[*] No GUI display detected in current environment.")
        print("[*] Starting PyShare in Headless Web Server mode...")
        import main
        main.start_server()
        return

    try:
        import app_gui
        app_gui.start_native_app()
    except (ImportError, Exception) as e:
        print(f"[*] Native GUI engine unavailable ({e}).")
        print("[*] Starting PyShare in Web Server mode...")
        import main
        main.start_server()

if __name__ == "__main__":
    main_launcher()
