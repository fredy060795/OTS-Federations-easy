"""Tests for the terminal/CLI interface."""

import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from OTS_Federation_CLI import (
    _print_error,
    _print_header,
    _print_status,
    _print_success,
    _prompt,
    _prompt_choice,
    _prompt_yes_no,
    run_cli,
)


class TestPrintHelpers(unittest.TestCase):
    """Test terminal output helper functions."""

    def test_print_header(self):
        with patch("sys.stdout", new_callable=StringIO) as out:
            _print_header("Test Header")
            output = out.getvalue()
            self.assertIn("Test Header", output)
            self.assertIn("═", output)

    def test_print_status(self):
        with patch("sys.stdout", new_callable=StringIO) as out:
            _print_status("Working…")
            self.assertIn("→ Working…", out.getvalue())

    def test_print_error(self):
        with patch("sys.stdout", new_callable=StringIO) as out:
            _print_error("Something failed")
            self.assertIn("✗ ERROR: Something failed", out.getvalue())

    def test_print_success(self):
        with patch("sys.stdout", new_callable=StringIO) as out:
            _print_success("Done!")
            self.assertIn("✓ Done!", out.getvalue())


class TestPrompt(unittest.TestCase):
    """Test interactive prompt helpers."""

    def test_prompt_with_input(self):
        with patch("builtins.input", return_value="hello"):
            result = _prompt("Enter value")
            self.assertEqual(result, "hello")

    def test_prompt_with_default(self):
        with patch("builtins.input", return_value=""):
            result = _prompt("Enter value", default="default_val")
            self.assertEqual(result, "default_val")

    def test_prompt_override_default(self):
        with patch("builtins.input", return_value="custom"):
            result = _prompt("Enter value", default="default_val")
            self.assertEqual(result, "custom")

    def test_prompt_yes_no_default_false(self):
        with patch("builtins.input", return_value=""):
            result = _prompt_yes_no("Continue?", default=False)
            self.assertFalse(result)

    def test_prompt_yes_no_default_true(self):
        with patch("builtins.input", return_value=""):
            result = _prompt_yes_no("Continue?", default=True)
            self.assertTrue(result)

    def test_prompt_yes_no_yes(self):
        with patch("builtins.input", return_value="y"):
            result = _prompt_yes_no("Continue?", default=False)
            self.assertTrue(result)

    def test_prompt_yes_no_no(self):
        with patch("builtins.input", return_value="n"):
            result = _prompt_yes_no("Continue?", default=True)
            self.assertFalse(result)

    def test_prompt_yes_no_ja(self):
        """German 'ja' should also be accepted."""
        with patch("builtins.input", return_value="ja"):
            result = _prompt_yes_no("Continue?", default=False)
            self.assertTrue(result)

    def test_prompt_choice(self):
        with patch("builtins.input", return_value="2"):
            with patch("sys.stdout", new_callable=StringIO):
                result = _prompt_choice(["Option A", "Option B", "Option C"])
                self.assertEqual(result, 1)  # 0-based index


class TestRunCliLocalWorkflow(unittest.TestCase):
    """Test the full CLI workflow with simulated local input."""

    def test_full_local_workflow(self):
        """Simulate a complete local federation setup via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up fake TAK installation
            tak_dir = os.path.join(tmpdir, "tak")
            certs_dir = os.path.join(tak_dir, "certs")
            os.makedirs(certs_dir)
            config_file = os.path.join(tak_dir, "CoreConfig.xml")
            with open(config_file, "w") as f:
                f.write(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    "<Configuration></Configuration>"
                )

            # Create fake certificate
            cert_file = os.path.join(tmpdir, "trust.pem")
            with open(cert_file, "w") as f:
                f.write("FAKE CERT DATA")

            inputs = iter([
                "1",            # Local mode
                "y",            # Verify: yes
                "10.0.0.1",    # Remote address
                "9000",         # Remote port (default)
                cert_file,      # Cert path
                certs_dir,      # Dest dir
                "y",            # Auto-configure
                "y",            # Apply
            ])

            def fake_input(prompt=""):
                return next(inputs)

            with patch.dict(os.environ, {"TAK_PATH": tak_dir}):
                with patch("sys.stdout", new_callable=StringIO) as out:
                    run_cli(input_func=fake_input)

            output = out.getvalue()
            self.assertIn("Federation configured successfully", output)
            self.assertIn("Certificate saved to", output)

            # Verify the config was actually updated
            import xml.etree.ElementTree as ET
            tree = ET.parse(config_file)
            root = tree.getroot()
            entry = root.find(".//federateOutgoing")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.get("address"), "10.0.0.1")
            self.assertEqual(entry.get("port"), "9000")

    def test_cancel_at_review(self):
        """User cancels at the review step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tak_dir = os.path.join(tmpdir, "tak")
            certs_dir = os.path.join(tak_dir, "certs")
            os.makedirs(certs_dir)
            config_file = os.path.join(tak_dir, "CoreConfig.xml")
            with open(config_file, "w") as f:
                f.write(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    "<Configuration></Configuration>"
                )

            cert_file = os.path.join(tmpdir, "trust.pem")
            with open(cert_file, "w") as f:
                f.write("FAKE CERT DATA")

            inputs = iter([
                "1",            # Local mode
                "n",            # Don't verify
                "10.0.0.1",    # Remote address
                "9000",         # Remote port
                cert_file,      # Cert path
                certs_dir,      # Dest dir
                "y",            # Auto-configure
                "n",            # Cancel at review
            ])

            def fake_input(prompt=""):
                return next(inputs)

            with patch.dict(os.environ, {"TAK_PATH": tak_dir}):
                with patch("sys.stdout", new_callable=StringIO) as out:
                    run_cli(input_func=fake_input)

            output = out.getvalue()
            self.assertIn("Cancelled", output)
            self.assertNotIn("Federation configured successfully", output)

    def test_workflow_without_auto_config(self):
        """Complete workflow without auto-configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tak_dir = os.path.join(tmpdir, "tak")
            certs_dir = os.path.join(tak_dir, "certs")
            os.makedirs(certs_dir)

            cert_file = os.path.join(tmpdir, "trust.pem")
            with open(cert_file, "w") as f:
                f.write("FAKE CERT DATA")

            inputs = iter([
                "1",            # Local mode
                "n",            # Don't verify
                "10.0.0.1",    # Remote address
                "9000",         # Remote port
                cert_file,      # Cert path
                certs_dir,      # Dest dir
                "y",            # Apply
            ])

            def fake_input(prompt=""):
                return next(inputs)

            with patch.dict(os.environ, {"TAK_PATH": tak_dir}):
                with patch("sys.stdout", new_callable=StringIO) as out:
                    run_cli(input_func=fake_input)

            output = out.getvalue()
            self.assertIn("Trust certificate saved successfully", output)
            self.assertIn("CoreConfig.xml", output)


if __name__ == "__main__":
    unittest.main()
