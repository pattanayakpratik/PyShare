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
