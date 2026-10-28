"""
PyShare Launcher
================
Run with no arguments to start the Native Cyberpunk Glass Desktop GUI:
    python run.py

Or pass '--server' or '--headless' to run the Headless Web Server:
    python run.py --server
"""
import sys
import os

# Ensure the 'app' directory is in Python's search path
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

if __name__ == "__main__":
    if "--server" in sys.argv or "--headless" in sys.argv:
        import main
        main.start_server()
    else:
        try:
            import app_gui
            app_gui.start_native_app()
        except ImportError as e:
            print(f"[*] Native GUI dependencies not available ({e}).")
            print("[*] Starting PyShare in Web Server mode...")
            import main
            main.start_server()
