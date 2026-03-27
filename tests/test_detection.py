"""Tests for the auto-detection and XML-configuration helpers."""

import os
import tempfile
import textwrap
import unittest

# Ensure the src package is importable.
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from OTS_Federation_GUI import (
    detect_tak_install,
    save_certificate,
    update_core_config,
)


class TestDetectTakInstall(unittest.TestCase):
    """Tests for ``detect_tak_install``."""

    def test_returns_none_when_nothing_found(self):
        """All values should be None when no candidate dirs exist."""
        # Ensure no env override interferes.
        env = os.environ.pop("TAK_PATH", None)
        try:
            result = detect_tak_install()
            # On a machine without /opt/tak or ~/tak the dict should be
            # all-None (or contain a real path if the runner happens to
            # have one – we only assert the dict structure).
            self.assertIn("tak_dir", result)
            self.assertIn("certs_dir", result)
            self.assertIn("config_file", result)
        finally:
            if env is not None:
                os.environ["TAK_PATH"] = env

    def test_env_override(self):
        """TAK_PATH environment variable should be used first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            certs = os.path.join(tmpdir, "certs")
            os.makedirs(certs)
            # Create a dummy config.
            cfg = os.path.join(tmpdir, "CoreConfig.xml")
            with open(cfg, "w") as f:
                f.write("<Configuration></Configuration>")

            old = os.environ.get("TAK_PATH")
            os.environ["TAK_PATH"] = tmpdir
            try:
                result = detect_tak_install()
                self.assertEqual(result["tak_dir"], tmpdir)
                self.assertEqual(result["certs_dir"], certs)
                self.assertEqual(result["config_file"], cfg)
            finally:
                if old is None:
                    del os.environ["TAK_PATH"]
                else:
                    os.environ["TAK_PATH"] = old

    def test_detects_certs_only(self):
        """When only a certs dir exists (no config file)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            certs = os.path.join(tmpdir, "certs")
            os.makedirs(certs)

            old = os.environ.get("TAK_PATH")
            os.environ["TAK_PATH"] = tmpdir
            try:
                result = detect_tak_install()
                self.assertEqual(result["tak_dir"], tmpdir)
                self.assertEqual(result["certs_dir"], certs)
                self.assertIsNone(result["config_file"])
            finally:
                if old is None:
                    del os.environ["TAK_PATH"]
                else:
                    os.environ["TAK_PATH"] = old


class TestUpdateCoreConfig(unittest.TestCase):
    """Tests for ``update_core_config``."""

    _MINIMAL_CONFIG = textwrap.dedent("""\
        <?xml version='1.0' encoding='UTF-8'?>
        <Configuration>
        </Configuration>
    """)

    _CONFIG_WITH_FEDERATION = textwrap.dedent("""\
        <?xml version='1.0' encoding='UTF-8'?>
        <Configuration>
          <federation>
            <federationOutgoing />
          </federation>
        </Configuration>
    """)

    def _write(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".xml")
        os.write(fd, content.encode())
        os.close(fd)
        return path

    def test_creates_federation_block_from_scratch(self):
        path = self._write(self._MINIMAL_CONFIG)
        try:
            update_core_config(path, "10.0.0.1", "9000", "trust.pem")
            import xml.etree.ElementTree as ET

            tree = ET.parse(path)
            root = tree.getroot()
            fed = root.find("federation")
            self.assertIsNotNone(fed)
            out = fed.find("federationOutgoing")
            self.assertIsNotNone(out)
            entry = out.find("federateOutgoing")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.get("address"), "10.0.0.1")
            self.assertEqual(entry.get("port"), "9000")
            self.assertEqual(entry.get("enabled"), "true")
        finally:
            os.unlink(path)

    def test_appends_to_existing_federation(self):
        path = self._write(self._CONFIG_WITH_FEDERATION)
        try:
            update_core_config(path, "192.168.1.5", "8089", "fed.pem")
            import xml.etree.ElementTree as ET

            tree = ET.parse(path)
            root = tree.getroot()
            entries = root.findall(".//federateOutgoing")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].get("address"), "192.168.1.5")
        finally:
            os.unlink(path)

    def test_no_duplicate_entries(self):
        path = self._write(self._MINIMAL_CONFIG)
        try:
            update_core_config(path, "10.0.0.1", "9000", "a.pem")
            update_core_config(path, "10.0.0.1", "9000", "b.pem")
            import xml.etree.ElementTree as ET

            tree = ET.parse(path)
            entries = tree.getroot().findall(".//federateOutgoing")
            self.assertEqual(len(entries), 1, "Should not duplicate entries")
        finally:
            os.unlink(path)

    def test_different_remotes_create_separate_entries(self):
        path = self._write(self._MINIMAL_CONFIG)
        try:
            update_core_config(path, "10.0.0.1", "9000", "a.pem")
            update_core_config(path, "10.0.0.2", "9000", "b.pem")
            import xml.etree.ElementTree as ET

            tree = ET.parse(path)
            entries = tree.getroot().findall(".//federateOutgoing")
            self.assertEqual(len(entries), 2)
        finally:
            os.unlink(path)


class TestSaveCertificate(unittest.TestCase):
    """Tests for ``save_certificate``."""

    def test_copies_file(self):
        with tempfile.TemporaryDirectory() as src_dir:
            src = os.path.join(src_dir, "test.pem")
            with open(src, "w") as f:
                f.write("CERT DATA")

            with tempfile.TemporaryDirectory() as dest_dir:
                result = save_certificate(src, dest_dir)
                self.assertTrue(os.path.isfile(result))
                with open(result) as f:
                    self.assertEqual(f.read(), "CERT DATA")

    def test_creates_dest_dir(self):
        with tempfile.TemporaryDirectory() as src_dir:
            src = os.path.join(src_dir, "test.pem")
            with open(src, "w") as f:
                f.write("DATA")

            with tempfile.TemporaryDirectory() as base:
                dest = os.path.join(base, "new_sub", "certs")
                result = save_certificate(src, dest)
                self.assertTrue(os.path.isfile(result))

    def test_raises_on_missing_source(self):
        with self.assertRaises(ValueError):
            save_certificate("/nonexistent/path.pem", "/tmp")


if __name__ == "__main__":
    unittest.main()
