"""Tests for SSH connection, directory verification/search, and review summary."""

import os
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from OTS_Federation_GUI import (
    ServerConnection,
    _sh_quote,
    build_change_summary,
    detect_tak_install,
    search_tak_directories,
    verify_tak_directory,
)


# ---------------------------------------------------------------------------
# ServerConnection
# ---------------------------------------------------------------------------

class TestServerConnection(unittest.TestCase):
    """Tests for the ``ServerConnection`` class."""

    def test_local_defaults(self):
        conn = ServerConnection()
        self.assertFalse(conn.is_remote)
        self.assertEqual(conn.label, "local")

    def test_ssh_connection(self):
        conn = ServerConnection(ssh_host="10.0.0.1", ssh_user="admin", ssh_port=2222)
        self.assertTrue(conn.is_remote)
        self.assertEqual(conn.label, "admin@10.0.0.1:2222")

    def test_ssh_no_user(self):
        conn = ServerConnection(ssh_host="myhost")
        self.assertTrue(conn.is_remote)
        self.assertEqual(conn.label, "myhost:22")

    def test_local_run_command(self):
        conn = ServerConnection()
        rc, output = conn.run_command("echo hello")
        self.assertEqual(rc, 0)
        self.assertIn("hello", output)

    def test_local_run_command_failure(self):
        conn = ServerConnection()
        rc, _ = conn.run_command("false")
        self.assertNotEqual(rc, 0)

    def test_local_copy_file(self):
        conn = ServerConnection()
        with tempfile.TemporaryDirectory() as src_dir:
            src = os.path.join(src_dir, "test.pem")
            with open(src, "w") as f:
                f.write("CERT DATA")

            with tempfile.TemporaryDirectory() as dest_dir:
                ok, path = conn.copy_file_to_server(src, dest_dir)
                self.assertTrue(ok)
                self.assertTrue(os.path.isfile(path))
                with open(path) as f:
                    self.assertEqual(f.read(), "CERT DATA")

    def test_local_copy_creates_dir(self):
        conn = ServerConnection()
        with tempfile.TemporaryDirectory() as src_dir:
            src = os.path.join(src_dir, "test.pem")
            with open(src, "w") as f:
                f.write("DATA")

            with tempfile.TemporaryDirectory() as base:
                dest = os.path.join(base, "new_sub")
                ok, path = conn.copy_file_to_server(src, dest)
                self.assertTrue(ok)
                self.assertTrue(os.path.isfile(path))


# ---------------------------------------------------------------------------
# Shell quoting
# ---------------------------------------------------------------------------

class TestShQuote(unittest.TestCase):
    def test_simple_path(self):
        self.assertEqual(_sh_quote("/opt/tak"), "'/opt/tak'")

    def test_path_with_spaces(self):
        self.assertEqual(_sh_quote("/my dir/tak"), "'/my dir/tak'")

    def test_path_with_single_quote(self):
        result = _sh_quote("it's a path")
        # The result should properly escape the single-quote.
        self.assertIn("it", result)
        self.assertIn("s a path", result)


# ---------------------------------------------------------------------------
# verify_tak_directory
# ---------------------------------------------------------------------------

class TestVerifyTakDirectory(unittest.TestCase):

    def test_directory_exists_with_certs_and_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "certs"))
            with open(os.path.join(tmpdir, "CoreConfig.xml"), "w") as f:
                f.write("<Configuration/>")

            lines = verify_tak_directory(tmpdir)
            text = "\n".join(lines)
            self.assertIn("✓ Directory exists", text)
            self.assertIn("✓ Sub-directory exists: certs/", text)
            self.assertIn("✓ Config file found: CoreConfig.xml", text)

    def test_directory_missing(self):
        lines = verify_tak_directory("/nonexistent/path/xyz")
        text = "\n".join(lines)
        self.assertIn("✗ Directory NOT found", text)

    def test_directory_exists_but_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lines = verify_tak_directory(tmpdir)
            text = "\n".join(lines)
            self.assertIn("✓ Directory exists", text)
            self.assertIn("✗ Sub-directory missing: certs/", text)
            self.assertIn("⚠ No config file found", text)

    def test_remote_verification_uses_ssh(self):
        """Verify that remote mode calls run_command with test -d / -f."""
        conn = ServerConnection(ssh_host="fakehost")
        # Mock run_command to simulate a remote server with /opt/tak + certs
        def fake_run(cmd, timeout=30):
            if "test -d '/opt/tak'" in cmd:
                return 0, ""
            if "test -d '/opt/tak/certs'" in cmd:
                return 0, ""
            if "test -f '/opt/tak/CoreConfig.xml'" in cmd:
                return 0, ""
            return 1, ""

        conn.run_command = fake_run  # type: ignore[assignment]
        lines = verify_tak_directory("/opt/tak", conn)
        text = "\n".join(lines)
        self.assertIn("✓ Directory exists", text)
        self.assertIn("✓ Sub-directory exists: certs/", text)
        self.assertIn("✓ Config file found: CoreConfig.xml", text)


# ---------------------------------------------------------------------------
# search_tak_directories
# ---------------------------------------------------------------------------

class TestSearchTakDirectories(unittest.TestCase):

    def test_search_local_with_temp_setup(self):
        """Test that the search finds a TAK dir under a custom root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tak_dir = os.path.join(tmpdir, "mytak")
            os.makedirs(tak_dir)
            cfg = os.path.join(tak_dir, "CoreConfig.xml")
            with open(cfg, "w") as f:
                f.write("<Configuration/>")

            # Patch _SEARCH_ROOTS to only look in our temp dir.
            import OTS_Federation_GUI as mod
            old_roots = mod._SEARCH_ROOTS
            mod._SEARCH_ROOTS = [tmpdir]
            try:
                hits = search_tak_directories()
            finally:
                mod._SEARCH_ROOTS = old_roots

            self.assertIn(tak_dir, hits)

    def test_search_returns_empty_when_nothing_found(self):
        """No results when no TAK installations exist."""
        import OTS_Federation_GUI as mod
        old_roots = mod._SEARCH_ROOTS
        with tempfile.TemporaryDirectory() as tmpdir:
            mod._SEARCH_ROOTS = [tmpdir]
            try:
                hits = search_tak_directories()
            finally:
                mod._SEARCH_ROOTS = old_roots
        self.assertEqual(hits, [])


# ---------------------------------------------------------------------------
# build_change_summary
# ---------------------------------------------------------------------------

class TestBuildChangeSummary(unittest.TestCase):

    def test_summary_with_auto_config(self):
        summary = build_change_summary(
            cert_src="/tmp/trust.pem",
            cert_dest_dir="/opt/tak/certs",
            remote_addr="10.0.0.1",
            remote_port="9000",
            auto_config=True,
            config_file="/opt/tak/CoreConfig.xml",
        )
        self.assertIn("REVIEW PLANNED CHANGES", summary)
        self.assertIn("Copy trust certificate", summary)
        self.assertIn("/tmp/trust.pem", summary)
        self.assertIn("/opt/tak/certs/trust.pem", summary)
        self.assertIn("Update configuration", summary)
        self.assertIn("10.0.0.1", summary)
        self.assertIn("9000", summary)

    def test_summary_without_auto_config(self):
        summary = build_change_summary(
            cert_src="/tmp/trust.pem",
            cert_dest_dir="/opt/tak/certs",
            remote_addr="10.0.0.1",
            remote_port="9000",
            auto_config=False,
            config_file=None,
        )
        self.assertIn("manual edit required", summary)
        self.assertNotIn("Update configuration", summary)

    def test_summary_shows_ssh_target(self):
        conn = ServerConnection(ssh_host="192.168.1.5", ssh_user="tak")
        summary = build_change_summary(
            cert_src="/tmp/trust.pem",
            cert_dest_dir="/opt/tak/certs",
            remote_addr="10.0.0.1",
            remote_port="9000",
            auto_config=False,
            config_file=None,
            conn=conn,
        )
        self.assertIn("tak@192.168.1.5", summary)


# ---------------------------------------------------------------------------
# detect_tak_install with ServerConnection
# ---------------------------------------------------------------------------

class TestDetectTakInstallWithSSH(unittest.TestCase):
    """Test that detect_tak_install works with a remote connection."""

    def test_detect_remote(self):
        """Simulate remote detection via mocked run_command."""
        conn = ServerConnection(ssh_host="fakehost")

        def fake_run(cmd, timeout=30):
            if "test -d '/opt/tak'" in cmd:
                return 0, ""
            if "test -d '/opt/tak/certs'" in cmd:
                return 0, ""
            if "test -f '/opt/tak/CoreConfig.xml'" in cmd:
                return 0, ""
            return 1, ""

        conn.run_command = fake_run  # type: ignore[assignment]

        result = detect_tak_install(conn)
        self.assertEqual(result["tak_dir"], "/opt/tak")
        self.assertEqual(result["certs_dir"], "/opt/tak/certs")
        self.assertEqual(result["config_file"], "/opt/tak/CoreConfig.xml")


if __name__ == "__main__":
    unittest.main()
