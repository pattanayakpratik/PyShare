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
import re
import sys
import time
import json
import glob
import socket
import http.client
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
        # Never touch the developer's real ~/.pyshare_config.json (PIN-mode tests save settings)
        cls._real_config_file = main.CONFIG_FILE
        main.CONFIG_FILE = os.path.join(cls.test_dir, "pyshare_test_config.json")
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
        main.CONFIG_FILE = cls._real_config_file
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

    # =========================================================================
    # 6. PROTOCOL CORRECTNESS, EVENT-STREAM ISOLATION & ORIGIN HARDENING
    # =========================================================================
    def _client_login(self, ip):
        """Log in as a remote client device (X-Forwarded-For => non-host) and return its token."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/login", body=f"pin={main.CURRENT_PIN}&nickname=Audit",
                     headers={"X-Forwarded-For": ip, "Content-Type": "application/x-www-form-urlencoded"})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 200, "Client login failed")
        return re.search(r"pyshare_session=([a-f0-9]+)", res.getheader("Set-Cookie")).group(1)

    def _open_sse(self, extra_headers=""):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.sendall(f"GET /api/events HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n{extra_headers}\r\n".encode())
        sock.settimeout(0.25)
        return sock

    @staticmethod
    def _read_sse(sock, seconds):
        """Read an SSE socket for up to `seconds`; returns (text, closed_by_server)."""
        buf, end = b"", time.time() + seconds
        while time.time() < end:
            try:
                chunk = sock.recv(65536)
                if not chunk:
                    return buf.decode("utf-8", "replace"), True
                buf += chunk
            except socket.timeout:
                pass
        return buf.decode("utf-8", "replace"), False

    def test_sec_11_unsatisfiable_range_response_completes(self):
        """SEC-11: A 416 response must declare an empty body so keep-alive clients don't hang."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/view/legit.txt", headers={"Range": "bytes=999999-"})
        res = conn.getresponse()
        self.assertEqual(res.status, 416)
        self.assertEqual(res.getheader("Content-Length"), "0")
        self.assertEqual(res.read(), b"")
        # The same keep-alive connection must still serve the next request.
        conn.request("GET", "/view/legit.txt")
        res2 = conn.getresponse()
        self.assertEqual(res2.status, 200)
        self.assertEqual(res2.read(), b"Legitimate shared content")
        conn.close()
        print("  [PASS] SEC-11: 416 Range Not Satisfiable completes cleanly on keep-alive connections")

    def test_sec_12_client_event_stream_excludes_host_only_data(self):
        """SEC-12: Clients must never receive the live PIN, peer IPs, join requests, tunnel URL or log."""
        token = self._client_login("10.77.0.12")
        client = self._open_sse(f"Cookie: pyshare_session={token}\r\nX-Forwarded-For: 10.77.0.12\r\n")
        host = self._open_sse()
        try:
            client_text, _ = self._read_sse(client, 0.6)
            host_text, _ = self._read_sse(host, 0.6)
            main.broadcast_sse("pin", {"pin": "4242", "ttl": 20, "mode": "rotating"})
            main.broadcast_sse("peers", [{"id": "x", "ip": "10.0.0.9"}])
            main.broadcast_sse("join_request", {"id": "r", "nickname": "Guest", "ip": "10.0.0.8"})
            main.broadcast_sse("tunnel", {"status": "active", "url": "https://secret.trycloudflare.com"})
            main.broadcast_sse("log", {"time": "00:00", "msg": "secret activity"})
            main.broadcast_sse("files", main.get_files_data())
            more, _ = self._read_sse(client, 1.0)
            client_text += more
            more, _ = self._read_sse(host, 1.0)
            host_text += more
        finally:
            client.close()
            host.close()

        self.assertIn("event: files", client_text, "Client should still get file list updates")
        self.assertIn("event: clipboard", client_text, "Client should still get the chat snapshot")
        for leaked in ("event: pin", "event: peers", "event: join_request", "event: tunnel", "event: log",
                       "4242", "secret.trycloudflare.com", "secret activity"):
            self.assertNotIn(leaked, client_text, f"Host-only data leaked to client stream: {leaked!r}")
        for expected in ("event: pin", "event: peers", "event: join_request", "event: tunnel", "event: log"):
            self.assertIn(expected, host_text, f"Host stream missing {expected!r}")
        print("  [PASS] SEC-12: Host-only live events are never pushed to client devices")

    def test_sec_13_revoked_session_event_stream_is_closed(self):
        """SEC-13: Revoking a device must end its open event stream right away."""
        token = self._client_login("10.77.0.13")
        client = self._open_sse(f"Cookie: pyshare_session={token}\r\nX-Forwarded-For: 10.77.0.13\r\n")
        try:
            self._read_sse(client, 0.5)
            with main.state_lock:
                sid = main.SESSIONS[token]["id"]
            req = urllib.request.Request(f"{self.base_url}/api/peers/disconnect",
                                         data=json.dumps({"id": sid}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=3) as res:
                self.assertEqual(json.loads(res.read())["removed"], 1)
            _, closed = self._read_sse(client, 3.0)
        finally:
            client.close()
        self.assertTrue(closed, "Revoked device's event stream stayed open")
        print("  [PASS] SEC-13: Revoked sessions lose their live event stream immediately")

    def test_sec_14_dns_rebinding_host_header_rejected(self):
        """SEC-14: Loopback requests carrying a foreign Host header (DNS rebinding) get no Host privileges."""
        for bad_host in ("attacker.example", f"attacker.example:{self.port}", "127.0.0.1.attacker.example"):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
            conn.putrequest("GET", "/api/pin", skip_host=True)
            conn.putheader("Host", bad_host)
            conn.endheaders()
            res = conn.getresponse()
            res.read()
            conn.close()
            self.assertEqual(res.status, 401, f"Host privileges granted for Host: {bad_host}")

        with urllib.request.urlopen(f"{self.base_url}/api/pin", timeout=3) as res:
            self.assertEqual(res.status, 200, "Legitimate loopback Host must keep access")
        print("  [PASS] SEC-14: DNS-rebinding Host header spoofing blocked")

    def test_sec_15_lan_discovery_beacon_sanitized(self):
        """SEC-15: Spoofed LAN beacons cannot inject links or junk into the room list."""
        room = main.parse_discovery_beacon(
            {"app": "PyShare", "ip": "192.168.1.50", "port": 8011,
             "url": "javascript:alert(document.cookie)", "room": "Evil\nRoom" + "X" * 200}, "192.168.1.50", 1.0)
        self.assertEqual(room["url"], "http://192.168.1.50:8011", "Room URL must be rebuilt from ip:port")
        self.assertNotIn("\n", room["room"])
        self.assertLessEqual(len(room["room"]), 64)

        bad_beacons = [
            {"app": "PyShare", "ip": "javascript:alert(1)", "port": 8011},
            {"app": "PyShare", "ip": "192.168.1.50", "port": "8011\"><script>"},
            {"app": "PyShare", "ip": "192.168.1.50", "port": 70000},
            {"app": "NotPyShare", "ip": "192.168.1.50", "port": 8011},
            "not-a-dict",
        ]
        for beacon in bad_beacons:
            self.assertIsNone(main.parse_discovery_beacon(beacon, "192.168.1.50", 1.0), f"Accepted bad beacon {beacon!r}")
        print("  [PASS] SEC-15: LAN discovery beacons validated and room URLs rebuilt server-side")

    def test_sec_17_second_server_cannot_share_listening_port(self):
        """SEC-17: A second PyShare server must not bind a port another instance is listening on.

        With Windows SO_REUSEADDR both bind and the OS splits clients between them, so phones hit
        the instance without their session (random 401s, chat messages silently not sent)."""
        first = main.FastThreadingTCPServer(('127.0.0.1', 0), main.FinalFileHandler)
        try:
            port = first.server_address[1]
            with self.assertRaises(OSError, msg="Second server bound an in-use port (port sharing)"):
                second = main.FastThreadingTCPServer(('127.0.0.1', port), main.FinalFileHandler)
                second.server_close()
        finally:
            first.server_close()
        print("  [PASS] SEC-17: Second instance cannot hijack/share an in-use port")

    def test_sec_16_inline_handlers_never_splice_quoted_values(self):
        """SEC-16: Frontend inline on*="..." handlers must pass values via jsArg(), never '${...}'.

        escapeHtml() output is decoded back to raw quotes before an inline handler runs, so
        '${escapeHtml(x)}' inside onclick lets a filename/nickname/message execute code."""
        frontend = os.path.join(PROJECT_ROOT, "frontend")
        unsafe = re.compile(r'''\bon[a-z]+="[^"]*'\$\{''')
        offenders = []
        for path in glob.glob(os.path.join(frontend, "*.js")) + glob.glob(os.path.join(frontend, "*.html")):
            if path.endswith(".min.js"):
                continue
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if unsafe.search(line):
                        offenders.append(f"{os.path.basename(path)}:{lineno}")
        self.assertEqual(offenders, [], "Inline handlers splice quoted template values: " + ", ".join(offenders))
        print("  [PASS] SEC-16: Inline event handlers pass untrusted values safely via jsArg()")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPyShareSecurityAudit)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
