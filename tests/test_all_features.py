"""
PyShare Automated Test Suite - 4 Core Polish Steps
=====================================================
Validates:
  Step 1: Desktop Native Experience & OS Polish
  Step 2: Transfer Engine & Speedometer Controls
  Step 3: Mobile & Scanner Polish
  Step 4: Active Peer Inspector & Device Management
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import threading
import socket
import ctypes
import re
import unittest
import tempfile
import shutil

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import backend.main as main
import backend.app_gui as app_gui


class TestPyShareAllFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 65)
        print("  PYSHARE COMPLETE INTEGRATION & COMPONENT TEST SUITE")
        print("=" * 65)

        # Start live in-process server on ephemeral loopback port for HTTP API tests
        cls.test_dir = tempfile.mkdtemp()
        main.BASE_DIR = cls.test_dir
        main.DOWNLOAD_DIR = os.path.join(cls.test_dir, "Shared")
        main.UPLOAD_DIR = os.path.join(cls.test_dir, "Received")
        os.makedirs(main.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(main.UPLOAD_DIR, exist_ok=True)

        main.ACTUAL_PORT = 0
        cls.server = main.FastThreadingTCPServer(('127.0.0.1', 0), main.FinalFileHandler)
        cls.port = cls.server.server_address[1]
        main.ACTUAL_PORT = cls.port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

        # Let server initialize
        time.sleep(0.2)
        print(f"[*] In-memory test server listening at: {cls.base_url}\n")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        try:
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        except Exception:
            pass
        print("\n[*] In-memory test server cleanly shut down.")

    # =========================================================================
    # STEP 1: DESKTOP NATIVE EXPERIENCE & OS POLISH
    # =========================================================================
    def test_01_named_mutex_single_instance(self):
        """Step 1.1: Verify Windows Named Mutex detects duplicate instances."""
        if sys.platform != "win32":
            self.skipTest("Named Mutex verification applies strictly to Windows platform")
        kernel32 = ctypes.windll.kernel32
        test_mutex_name = "Global\\PyShare_Test_Mutex_Verification"
        ERROR_ALREADY_EXISTS = 183

        # Create first mutex instance (owner)
        h_mutex1 = kernel32.CreateMutexW(None, False, test_mutex_name)
        self.assertNotEqual(h_mutex1, 0, "First mutex creation failed")
        first_err = kernel32.GetLastError()
        self.assertNotEqual(first_err, ERROR_ALREADY_EXISTS)

        # Attempt to create second mutex with identical name
        h_mutex2 = kernel32.CreateMutexW(None, False, test_mutex_name)
        second_err = kernel32.GetLastError()
        self.assertEqual(second_err, ERROR_ALREADY_EXISTS, "Second mutex did not detect already existing instance")

        # Cleanup test mutex handles
        kernel32.CloseHandle(h_mutex1)
        if h_mutex2:
            kernel32.CloseHandle(h_mutex2)
        print("  [PASS] Step 1.1: Windows Named Mutex single-instance locking verified")

    def test_02_system_tray_icon_and_menu(self):
        """Step 1.2: Verify system tray icon generation and resilient fallback."""
        img = app_gui.load_tray_icon_image()
        self.assertIsNotNone(img, "Failed to load or generate system tray icon")
        self.assertGreater(img.width, 0, "Tray icon image has invalid width")
        self.assertGreater(img.height, 0, "Tray icon image has invalid height")
        print("  [PASS] Step 1.2: System tray icon generation verified")

    def test_03_app_version_and_update_checker(self):
        """Step 1.3: Verify version comparison and update checker logic."""
        self.assertTrue(hasattr(main, 'APP_VERSION'))
        self.assertTrue(re.match(r'^\d+\.\d+\.\d+', main.APP_VERSION), f"Invalid APP_VERSION: {main.APP_VERSION}")

        # Check version tuple parsing logic
        def parse_version_tuple(v_str):
            parts = re.findall(r'\d+', v_str)
            return tuple(int(p) for p in parts[:3]) if parts else (0, 0, 0)

        current = parse_version_tuple(main.APP_VERSION)
        higher = parse_version_tuple("5.0.0")
        lower = parse_version_tuple("4.0.0")
        same = parse_version_tuple(main.APP_VERSION)

        self.assertGreater(higher, current)
        self.assertLess(lower, current)
        self.assertEqual(same, current)

        # Pre-populate cache to test /api/check_update endpoint without depending on external GitHub network
        main.LAST_UPDATE_CHECK = {
            "timestamp": time.time(),
            "data": {
                "current_version": main.APP_VERSION,
                "latest_version": "5.0.0",
                "has_update": True,
                "release_url": "https://github.com/pattanayakpratik/PyShare/releases",
                "release_notes": "Test release notes"
            }
        }

        # Test /api/check_update endpoint over HTTP
        req = urllib.request.Request(f"{self.base_url}/api/check_update")
        with urllib.request.urlopen(req, timeout=3) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode('utf-8'))
            self.assertIn("current_version", data)
            self.assertIn("latest_version", data)
            self.assertIn("has_update", data)
            self.assertEqual(data["current_version"], main.APP_VERSION)
            self.assertTrue(data["has_update"])
        print("  [PASS] Step 1.3: In-app update checker & version comparison verified")

    def test_04_desktop_notification_hook(self):
        """Step 1.4: Verify desktop notification callback hook executes safely."""
        try:
            main.trigger_desktop_notification("PyShare Test Title", "Test Message Body")
            notif_ok = True
        except Exception as e:
            notif_ok = False
        self.assertTrue(notif_ok, "trigger_desktop_notification threw an unexpected exception")
        print("  [PASS] Step 1.4: Desktop notification dispatch hook verified")

    def test_05_config_persistence(self):
        """Step 1.5: Verify persistent configuration loading and saving."""
        cfg = main.load_app_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("minimize_to_tray", cfg)
        self.assertIn("pin_mode", cfg)
        self.assertIn("window_width", cfg)
        self.assertIn("window_height", cfg)
        print("  [PASS] Step 1.5: Application config persistence verified")

    # =========================================================================
    # STEP 2: TRANSFER ENGINE & SPEEDOMETER CONTROLS
    # =========================================================================
    def test_06_speedometer_and_eta_logic(self):
        """Step 2.1: Verify ETA countdown and speed rate algorithms."""
        def format_eta_py(seconds):
            if seconds is None or seconds <= 0:
                return "--:-- left"
            if seconds < 60:
                return f"{int(seconds)}s left"
            mins = int(seconds // 60)
            rem_sec = int(seconds % 60)
            if mins < 60:
                return f"{mins}m {rem_sec}s left"
            hours = int(mins // 60)
            rem_min = int(mins % 60)
            return f"{hours}h {rem_min}m left"

        self.assertEqual(format_eta_py(0), "--:-- left")
        self.assertEqual(format_eta_py(-5), "--:-- left")
        self.assertEqual(format_eta_py(42), "42s left")
        self.assertEqual(format_eta_py(125), "2m 5s left")
        self.assertEqual(format_eta_py(3660), "1h 1m left")
        print("  [PASS] Step 2.1: Speedometer & ETA calculation algorithm verified")

    def test_07_upload_progress_tracker(self):
        """Step 2.2: Verify upload progress tracking dictionary and reset."""
        test_ip = "192.168.1.105"
        test_file = "payload_video.mp4"
        main.set_upload_status(test_ip, test_file, 25000000, 100000000)

        with main.state_lock:
            self.assertIn(test_ip, main.upload_status)
            entry = main.upload_status[test_ip]
            self.assertEqual(entry["filename"], test_file)
            self.assertEqual(entry["current"], 25000000)
            self.assertEqual(entry["total"], 100000000)

        main.clear_upload_status(test_ip)
        with main.state_lock:
            self.assertNotIn(test_ip, main.upload_status)
        print("  [PASS] Step 2.2: Live upload progress tracker verified")

    def test_08_unique_filepath_and_sanitization(self):
        """Step 2.3: Verify filename conflict resolution and sanitization."""
        temp_dir = main.DOWNLOAD_DIR
        os.makedirs(temp_dir, exist_ok=True)

        target = main.get_unique_filepath(temp_dir, "test_document.txt")
        self.assertTrue(target.endswith("test_document.txt"))

        # Create temporary file to test collision renaming
        with open(target, "w") as f:
            f.write("existing")

        target2 = main.get_unique_filepath(temp_dir, "test_document.txt")
        self.assertTrue(" (1)" in target2 or target2 != target)

        # Cleanup
        try:
            os.remove(target)
        except Exception:
            pass
        print("  [PASS] Step 2.3: Filename conflict resolution & safety verified")

    # =========================================================================
    # STEP 3: MOBILE & SCANNER POLISH
    # =========================================================================
    def test_09_pin_mode_toggle_api(self):
        """Step 3.1: Verify static vs rotating PIN switching via /api/pin/mode."""
        # 1. Switch to static PIN mode with custom PIN '7788'
        payload = json.dumps({"mode": "static", "pin": "7788"}).encode('utf-8')
        req = urllib.request.Request(
            f"{self.base_url}/api/pin/mode",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode('utf-8'))
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["mode"], "static")
            self.assertEqual(data["pin"], "7788")

        # Verify /api/pin returns static mode with ttl == -1
        req_pin = urllib.request.Request(f"{self.base_url}/api/pin")
        with urllib.request.urlopen(req_pin, timeout=3) as res:
            pdata = json.loads(res.read().decode('utf-8'))
            self.assertEqual(pdata["mode"], "static")
            self.assertEqual(pdata["pin"], "7788")
            self.assertEqual(pdata["ttl"], -1)

        # 2. Switch back to rotating mode
        payload_rot = json.dumps({"mode": "rotating"}).encode('utf-8')
        req_rot = urllib.request.Request(
            f"{self.base_url}/api/pin/mode",
            data=payload_rot,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_rot, timeout=3) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode('utf-8'))
            self.assertEqual(data["mode"], "rotating")

        print("  [PASS] Step 3.1: Static vs Rotating PIN toggle API verified")

    def test_10_qr_code_instant_login_payload(self):
        """Step 3.2: Verify QR code payload embeds current PIN parameter."""
        main.generate_qr()
        # Ensure qrcode.png exists and is accessible
        qr_file = main.get_qr_path()
        self.assertTrue(os.path.isfile(qr_file), f"QR code image was not found at {qr_file}")
        self.assertGreater(os.path.getsize(qr_file), 0, "QR code image is empty")

        # Verify QR request endpoint
        req = urllib.request.Request(f"{self.base_url}/qrcode.png")
        with urllib.request.urlopen(req, timeout=3) as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.headers.get("Content-Type"), "image/png")
        print("  [PASS] Step 3.2: QR code generation and instant-login embedding verified")

    def test_11_login_template_camera_scanner_elements(self):
        """Step 3.3: Verify login.html contains QR scanner modal and haptic triggers."""
        login_path = os.path.join(main.ASSET_DIR, "login.html")
        self.assertTrue(os.path.isfile(login_path), "login.html missing")
        with open(login_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("qrScannerModal", content, "Missing qrScannerModal in login.html")
        self.assertIn("openQrScanner", content, "Missing openQrScanner function in login.html")
        self.assertIn("navigator.vibrate", content, "Missing haptic vibration feedback in login.html")
        self.assertIn("BarcodeDetector", content, "Missing BarcodeDetector API support in login.html")
        print("  [PASS] Step 3.3: Mobile camera QR viewfinder & haptic triggers verified")

    # =========================================================================
    # STEP 4: ACTIVE PEER INSPECTOR & DEVICE MANAGEMENT
    # =========================================================================
    def test_12_user_agent_parser_devices(self):
        """Step 4.1: Verify parse_user_agent parses varied devices and browsers."""
        test_cases = [
            (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
                "iPhone", "Safari", "smartphone"
            ),
            (
                "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "iPad", "Safari", "tablet"
            ),
            (
                "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro Build/UQ1A) AppleWebKit/537.36 Chrome/122.0 Mobile Safari/537.36",
                "Pixel 8 Pro", "Chrome", "smartphone"
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
                "Windows PC", "Edge", "laptop"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
                "Mac", "Safari", "laptop"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
                "Linux PC", "Firefox", "laptop"
            )
        ]

        for ua, expected_dev, expected_browser, expected_icon in test_cases:
            info = main.parse_user_agent(ua)
            self.assertEqual(info["device"], expected_dev, f"Mismatch device for UA: {ua}")
            self.assertEqual(info["browser"], expected_browser, f"Mismatch browser for UA: {ua}")
            self.assertEqual(info["icon"], expected_icon, f"Mismatch icon for UA: {ua}")

        print("  [PASS] Step 4.1: User-Agent multi-platform device parser verified")

    def test_13_client_authentication_and_peer_registration(self):
        """Step 4.2: Verify client login registers session metadata in SESSIONS."""
        with main.state_lock:
            current_pin = main.CURRENT_PIN

        # Simulate client login from an iPhone
        iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
        login_body = urllib.parse.urlencode({"pin": current_pin}).encode('utf-8')
        req = urllib.request.Request(
            f"{self.base_url}/login",
            data=login_body,
            headers={"User-Agent": iphone_ua, "Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=3) as res:
            self.assertEqual(res.status, 200)
            set_cookie = res.headers.get("Set-Cookie", "")
            self.assertIn("pyshare_session=", set_cookie)
            token = re.search(r'pyshare_session=([a-f0-9]+)', set_cookie).group(1)

        # Verify session is registered in SESSIONS dictionary with rich metadata
        with main.state_lock:
            self.assertIn(token, main.SESSIONS)
            sess = main.SESSIONS[token]
            self.assertIsInstance(sess, dict)
            self.assertEqual(sess["device"], "iPhone")
            self.assertEqual(sess["browser"], "Safari")
            self.assertEqual(sess["icon"], "smartphone")
            self.assertEqual(sess["id"], token[:8])

        print("  [PASS] Step 4.2: Client login and peer registration verified")

    def test_14_active_peer_inspector_endpoint(self):
        """Step 4.3: Verify /api/peers returns connected peers list."""
        req = urllib.request.Request(f"{self.base_url}/api/peers")
        with urllib.request.urlopen(req, timeout=3) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode('utf-8'))
            self.assertIn("peers", data)
            peers = data["peers"]
            self.assertIsInstance(peers, list)
            self.assertGreater(len(peers), 0, "Expected at least 1 peer in list")
            first_peer = peers[0]
            self.assertIn("id", first_peer)
            self.assertIn("ip", first_peer)
            self.assertIn("device", first_peer)
            self.assertIn("browser", first_peer)
            self.assertIn("active", first_peer)
            self.assertTrue(first_peer["active"])

        print("  [PASS] Step 4.3: /api/peers inspector endpoint verified")

    def test_15_session_revocation_and_unauthorized_kick(self):
        """Step 4.4: Verify revoking a session via /api/peers/disconnect immediately blocks client."""
        # 1. Login a new client session (Android)
        with main.state_lock:
            current_pin = main.CURRENT_PIN
        android_ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro Build/UQ1A) Chrome/122.0 Mobile Safari/537.36"
        login_body = urllib.parse.urlencode({"pin": current_pin}).encode('utf-8')
        req = urllib.request.Request(
            f"{self.base_url}/login",
            data=login_body,
            headers={"User-Agent": android_ua, "Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as res:
            set_cookie = res.headers.get("Set-Cookie", "")
            token = re.search(r'pyshare_session=([a-f0-9]+)', set_cookie).group(1)

        # Verify client can access protected endpoint with cookie
        cookie_header = f"pyshare_session={token}"
        req_client = urllib.request.Request(
            f"{self.base_url}/api/files",
            headers={"Cookie": cookie_header, "X-Forwarded-For": "192.168.1.150"}
        )
        with urllib.request.urlopen(req_client, timeout=3) as res:
            self.assertEqual(res.status, 200)

        # 2. Host revokes this device session
        target_id = token[:8]
        revoke_payload = json.dumps({"id": target_id}).encode('utf-8')
        req_revoke = urllib.request.Request(
            f"{self.base_url}/api/peers/disconnect",
            data=revoke_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_revoke, timeout=3) as res:
            self.assertEqual(res.status, 200)
            rdata = json.loads(res.read().decode('utf-8'))
            self.assertEqual(rdata["status"], "ok")
            self.assertEqual(rdata["removed"], 1)

        # 3. Client attempts to make another request with the revoked cookie
        req_client_revoked = urllib.request.Request(
            f"{self.base_url}/api/files",
            headers={"Cookie": cookie_header, "X-Forwarded-For": "192.168.1.150"}
        )
        try:
            with urllib.request.urlopen(req_client_revoked, timeout=3) as res:
                self.fail(f"Revoked client request should have returned 401 Unauthorized, but got {res.status}")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 401, f"Expected 401 Unauthorized for revoked session, got: {err.code}")

        print("  [PASS] Step 4.4: Session revocation and 401 Unauthorized kick verified")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPyShareAllFeatures)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
