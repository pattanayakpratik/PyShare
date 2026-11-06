"""
PyShare Comprehensive Security Audit & Penetration Regression Test Suite
========================================================================
Validates:
  1. Path Traversal & File Boundary Confinement
  2. Host Impersonation & Authorization Boundary Enforcement
  3. PIN Brute-Force Rate Limiting & Lockout Protection
  4. Script Sandboxing, Header Injection & Content-Security-Policy
  5. Payload Limits & DoS Resource Exhaustion Defenses
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import threading
import tempfile
import shutil
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import backend.main as main


class TestPyShareSecurityAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 65)
        print("  PYSHARE DEEP SECURITY & DEFENSIVE INTEGRITY AUDIT")
        print("=" * 65)

        cls.test_dir = tempfile.mkdtemp()
        main.BASE_DIR = cls.test_dir
        main.DOWNLOAD_DIR = os.path.join(cls.test_dir, "Shared")
        main.UPLOAD_DIR = os.path.join(cls.test_dir, "Received")
        os.makedirs(main.DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(main.UPLOAD_DIR, exist_ok=True)

        # Place a dummy file in Shared and a secret file outside the root
        with open(os.path.join(main.DOWNLOAD_DIR, "legit.txt"), "w") as f:
            f.write("Legitimate shared content")

        cls.secret_file = os.path.join(cls.test_dir, "secret_system_data.key")
        with open(cls.secret_file, "w") as f:
            f.write("TOP_SECRET_PRIVATE_KEY")

        # Start live in-process server
        main.CURRENT_PIN = "5678"
        main.ACTUAL_PORT = 0
        cls.server = main.FastThreadingTCPServer(('127.0.0.1', 0), main.FinalFileHandler)
        cls.port = cls.server.server_address[1]
        main.ACTUAL_PORT = cls.port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)
        print(f"[*] In-memory audit server active at: {cls.base_url}\n")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.test_dir, ignore_errors=True)
        print("\n[*] Audit server shut down and temporary storage wiped.")

    # =========================================================================
    # 1. PATH TRAVERSAL & ARBITRARY FILE ACCESS
    # =========================================================================
    def test_sec_01_path_traversal_in_download_and_view(self):
        """SEC-1: Verify directory traversal sequences are blocked in download & view routes."""
        traversal_payloads = [
            "/download/../../../../Windows/win.ini",
            "/download/..%2f..%2f..%2fWindows%2fwin.ini",
            "/download/..%5c..%5cWindows%5cwin.ini",
            "/download/....//....//Windows/win.ini",
            "/view/../../secret_system_data.key",
            "/view/..%2fsecret_system_data.key",
            "/view/%2e%2e%2fsecret_system_data.key",
            "/download/secret_system_data.key"  # Exists in parent BASE_DIR but not in Shared/Received
        ]

        for path in traversal_payloads:
            req = urllib.request.Request(f"{self.base_url}{path}")
            try:
                with urllib.request.urlopen(req, timeout=2) as res:
                    self.fail(f"VULNERABILITY: Traversal payload succeeded ({path}) with status {res.status}")
            except urllib.error.HTTPError as err:
                self.assertIn(err.code, (400, 401, 404), f"Unexpected status {err.code} for payload: {path}")

        print("  [PASS] SEC-1: Path traversal attacks in download & view strictly neutralized")

    def test_sec_02_block_incomplete_part_files(self):
        """SEC-2: Verify .part and .tmp files cannot be viewed or downloaded."""
        part_file = os.path.join(main.DOWNLOAD_DIR, "partial_transfer.iso.part")
        with open(part_file, "w") as f:
            f.write("Incomplete data chunk")

        req = urllib.request.Request(f"{self.base_url}/download/partial_transfer.iso.part")
        try:
            with urllib.request.urlopen(req, timeout=2) as res:
                self.fail("VULNERABILITY: Incomplete .part file was served")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 404)

        try:
            os.remove(part_file)
        except Exception:
            pass
        print("  [PASS] SEC-2: Incomplete .part and temporary files barred from access")

    def test_sec_03_static_asset_directory_confinement(self):
        """SEC-3: Verify static assets router confines access strictly to ASSET_DIR."""
        traversal_assets = [
            "/..%2f..%2fbackend%2fmain.py",
            "/..\\..\\backend\\main.py",
            "/%2e%2e/%2e%2e/Windows/win.ini"
        ]
        for asset in traversal_assets:
            req = urllib.request.Request(f"{self.base_url}{asset}")
            try:
                with urllib.request.urlopen(req, timeout=2) as res:
                    self.fail(f"VULNERABILITY: Static asset traversal succeeded: {asset}")
            except urllib.error.HTTPError as err:
                self.assertIn(err.code, (400, 401, 404))

        print("  [PASS] SEC-3: Static asset router path confinement verified")

    # =========================================================================
    # 2. HOST IMPERSONATION & AUTHORIZATION BOUNDARY ENFORCEMENT
    # =========================================================================
    def test_sec_04_external_client_spoofing_host(self):
        """SEC-4: Verify external client headers (CF-Ray, X-Forwarded-For) cannot spoof host privileges."""
        # Simulated external proxy headers claiming to be localhost
        spoofed_headers = {
            "X-Forwarded-For": "198.51.100.42",
            "CF-Connecting-IP": "198.51.100.42",
            "CF-Ray": "8937492abf48-ORD"
        }

        # Attempt to access host-only endpoints with spoofed headers
        host_only_endpoints = [
            "/api/peers",
            "/api/tunnel",
            "/api/pin",
            "/api/open?folder=shared"
        ]

        for ep in host_only_endpoints:
            req = urllib.request.Request(f"{self.base_url}{ep}", headers=spoofed_headers)
            try:
                with urllib.request.urlopen(req, timeout=2) as res:
                    self.fail(f"VULNERABILITY: External proxy header bypassed host authentication on {ep}")
            except urllib.error.HTTPError as err:
                self.assertIn(err.code, (401, 403), f"Expected 401/403 for {ep}, got: {err.code}")

        print("  [PASS] SEC-4: Host privilege impersonation & proxy header spoofing blocked")

    def test_sec_05_csrf_cross_site_request_blocking(self):
        """SEC-5: Verify cross-site origin/referer requests to host actions are rejected."""
        csrf_headers = {
            "Origin": "https://malicious-website.com",
            "Referer": "https://malicious-website.com/attack.html",
            "Sec-Fetch-Site": "cross-site",
            "Content-Type": "application/json"
        }

        # Malicious site attempting to revoke a peer or change PIN mode
        req = urllib.request.Request(
            f"{self.base_url}/api/pin/mode",
            data=json.dumps({"mode": "static", "pin": "0000"}).encode('utf-8'),
            headers=csrf_headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=2) as res:
                self.fail("VULNERABILITY: Cross-site CSRF request succeeded")
        except urllib.error.HTTPError as err:
            self.assertIn(err.code, (401, 403), f"Expected 401/403 for cross-site CSRF, got {err.code}")

        print("  [PASS] SEC-5: Cross-Site Request Forgery (CSRF) defense verified")

    # =========================================================================
    # 3. PIN BRUTE-FORCE RATE LIMITING & LOCKOUT DEFENSES
    # =========================================================================
    def test_sec_06_pin_brute_force_lockout(self):
        """SEC-6: Verify rapid incorrect PIN attempts trigger automatic 429 lockout."""
        fake_ip = "198.51.100.99"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Forwarded-For": fake_ip
        }
        body = urllib.parse.urlencode({"pin": "9999"}).encode('utf-8')

        # Send repeated invalid attempts
        hit_lockout = False
        for attempt in range(1, 8):
            req = urllib.request.Request(f"{self.base_url}/login", data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=2) as res:
                    pass
            except urllib.error.HTTPError as err:
                if err.code == 429:
                    hit_lockout = True
                    break

        self.assertTrue(hit_lockout, "Server failed to enforce 429 lockout after repeated failed attempts")

        # Even correct PIN must be blocked during active lockout
        with main.state_lock:
            real_pin = main.CURRENT_PIN
        body_real = urllib.parse.urlencode({"pin": real_pin}).encode('utf-8')
        req_real = urllib.request.Request(f"{self.base_url}/login", data=body_real, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req_real, timeout=2) as res:
                self.fail("VULNERABILITY: Correct PIN succeeded while IP is actively locked out")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 429, "Locked-out client should receive 429 even with correct PIN")

        # Cleanup lockout for test IP
        with main.login_lock:
            main.login_attempts.pop(fake_ip, None)
            main.login_attempts.pop("127.0.0.1", None)

        print("  [PASS] SEC-6: PIN brute-force defense & 429 lockout rate limiting verified")

    # =========================================================================
    # 4. SCRIPT SANDBOXING, CONTENT-SECURITY-POLICY & HEADER INJECTION
    # =========================================================================
    def test_sec_07_stored_xss_prevention_csp_headers(self):
        """SEC-7: Verify previewing uploaded HTML/SVG files enforces strict CSP sandbox."""
        html_file = os.path.join(main.DOWNLOAD_DIR, "xss_probe.html")
        with open(html_file, "w") as f:
            f.write("<script>alert('xss')</script>")

        req = urllib.request.Request(f"{self.base_url}/view/xss_probe.html")
        with urllib.request.urlopen(req, timeout=2) as res:
            self.assertEqual(res.status, 200)
            csp = res.headers.get("Content-Security-Policy", "")
            self.assertIn("sandbox", csp, "Missing sandbox directive in CSP for scriptable file view")
            self.assertIn("default-src 'none'", csp, "Missing default-src 'none' directive in CSP")
            self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")

        try:
            os.remove(html_file)
        except Exception:
            pass
        print("  [PASS] SEC-7: Stored XSS defense via Content-Security-Policy sandbox verified")

    def test_sec_08_crlf_header_injection_sanitization(self):
        """SEC-8: Verify CRLF in filenames cannot inject arbitrary HTTP headers."""
        malicious_fn = "report.pdf\r\nInjected-Header: Pwned\r\n\r\n"
        sanitized = main.FinalFileHandler.format_content_disposition(malicious_fn)
        self.assertNotIn("\r", sanitized, "CR character detected in formatted Content-Disposition")
        self.assertNotIn("\n", sanitized, "LF character detected in formatted Content-Disposition")
        self.assertIn("filename=", sanitized)
        print("  [PASS] SEC-8: HTTP header CRLF injection defense verified")

    # =========================================================================
    # 5. PAYLOAD LIMITS & DOS RESOURCE EXHAUSTION DEFENSES
    # =========================================================================
    def test_sec_09_clipboard_and_login_payload_limits(self):
        """SEC-9: Verify oversized payloads (>64KB clipboard, >1KB login) are rejected with 413/400."""
        # 1. Login payload limit (1KB max)
        huge_login_body = ("pin=" + "A" * 2048).encode('utf-8')
        req_login = urllib.request.Request(
            f"{self.base_url}/login",
            data=huge_login_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req_login, timeout=2) as res:
                self.fail("Oversized login body was accepted")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 400)

        # 2. Clipboard payload limit (64KB max)
        huge_clip = json.dumps({"text": "X" * (80 * 1024)}).encode('utf-8')
        req_clip = urllib.request.Request(
            f"{self.base_url}/api/text",
            data=huge_clip,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req_clip, timeout=2) as res:
                self.fail("Oversized clipboard payload was accepted")
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 413, f"Expected 413 Payload Too Large, got {err.code}")

        print("  [PASS] SEC-9: Payload size caps & RAM DoS prevention verified")

    def test_sec_10_concurrent_zip_semaphore(self):
        """SEC-10: Verify concurrent ZIP generation semaphore blocks DoS disk/CPU starvation."""
        acquired = main.zip_semaphore.acquire(blocking=False)
        self.assertTrue(acquired, "Failed to acquire initial ZIP semaphore")

        # Attempt to acquire a second concurrent semaphore
        second_acquired = main.zip_semaphore.acquire(blocking=False)
        self.assertFalse(second_acquired, "Secondary ZIP semaphore was granted concurrently! (Risk of DoS)")

        # Release semaphore
        main.zip_semaphore.release()
        print("  [PASS] SEC-10: ZIP archive generation single-instance semaphore verified")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPyShareSecurityAudit)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
