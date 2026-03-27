#!/usr/bin/env python3
"""
OTS_Federation_CLI.py - TAK Federation Setup Helper (Terminal / CLI)
=====================================================================

Usage:
    python3 src/OTS_Federation_CLI.py

Description:
    Pure terminal interface for the TAK Federation Setup Helper.
    Works over SSH, on headless servers, and in any console environment
    — no graphical display (X11 / Wayland / Tkinter) required.

    This CLI provides the same functionality as the GUI version:
        - Local & SSH mode
        - Auto-detection & search of TAK installations
        - Directory verification
        - Manual review before changes
        - Certificate management
        - Auto-configuration of CoreConfig.xml

Author:  OTS-Federations-easy project
License: MIT
"""

import os
import sys
import tempfile
import xml.etree.ElementTree as ET

# Ensure the src directory is on the import path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from federation_core import (
    DEFAULT_CERT_DIR,
    DEFAULT_FEDERATION_PORT,
    ServerConnection,
    _sh_quote,
    build_change_summary,
    detect_tak_install,
    save_certificate,
    search_tak_directories,
    update_core_config,
    verify_tak_directory,
)

# ---------------------------------------------------------------------------
# Terminal I/O helpers
# ---------------------------------------------------------------------------

def _print_header(title: str) -> None:
    """Print a section header."""
    width = max(len(title) + 4, 50)
    print()
    print("═" * width)
    print(f"  {title}")
    print("═" * width)


def _print_status(msg: str) -> None:
    """Print a status message."""
    print(f"  → {msg}")


def _print_error(msg: str) -> None:
    """Print an error message."""
    print(f"  ✗ ERROR: {msg}")


def _print_success(msg: str) -> None:
    """Print a success message."""
    print(f"  ✓ {msg}")


def _prompt(label: str, default: str = "") -> str:
    """Prompt the user for input with an optional default value."""
    if default:
        raw = input(f"  {label} [{default}]: ").strip()
        return raw if raw else default
    return input(f"  {label}: ").strip()


def _prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt the user for a yes/no answer."""
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"  {question} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "j", "ja")


def _prompt_choice(options: list, prompt_text: str = "Select") -> int:
    """Display numbered options and return the selected index (0-based)."""
    for i, opt in enumerate(options, 1):
        print(f"    [{i}] {opt}")
    while True:
        raw = input(f"  {prompt_text} (1-{len(options)}): ").strip()
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return idx - 1
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


# ---------------------------------------------------------------------------
# CLI workflow
# ---------------------------------------------------------------------------

def run_cli(input_func=None) -> None:
    """Main CLI workflow — mirrors the GUI step by step."""

    # Allow overriding input for testing
    if input_func is not None:
        import builtins
        builtins.input = input_func

    _print_header("OTS Federation Setup Helper (Terminal)")
    print("  Configure TAK Federation from the command line.")
    print("  No graphical display required.\n")

    # ------------------------------------------------------------------
    # Step 1: Connection Mode
    # ------------------------------------------------------------------
    _print_header("Step 1: Connection Mode")
    mode_idx = _prompt_choice(
        ["Local (directly on this server)", "SSH (connect to remote TAK server)"],
        prompt_text="Select connection mode",
    )

    conn: ServerConnection
    if mode_idx == 1:
        # SSH mode
        print()
        ssh_host = _prompt("SSH Host")
        ssh_user = _prompt("SSH User (leave empty for current user)", default="")
        ssh_port = _prompt("SSH Port", default="22")

        try:
            port_num = int(ssh_port)
        except ValueError:
            port_num = 22

        conn = ServerConnection(
            ssh_host=ssh_host or None,
            ssh_user=ssh_user or None,
            ssh_port=port_num,
        )

        # Test connection
        if _prompt_yes_no("Test SSH connection now?", default=True):
            _print_status("Testing SSH connection…")
            rc, output = conn.run_command("echo ok")
            if rc == 0 and "ok" in output:
                _print_success(f"Connection to {conn.label} successful!")
            else:
                _print_error(f"Could not connect to {conn.label}: {output}")
                if not _prompt_yes_no("Continue anyway?"):
                    print("\n  Aborted.\n")
                    return
    else:
        conn = ServerConnection()
        _print_success("Local mode selected.")

    # ------------------------------------------------------------------
    # Step 2: Detect TAK Installation
    # ------------------------------------------------------------------
    _print_header("Step 2: Detect TAK Installation")
    _print_status("Searching for TAK installation…")

    detected = detect_tak_install(conn)

    tak_dir = detected.get("tak_dir")
    certs_dir = detected.get("certs_dir")
    config_file = detected.get("config_file")

    if tak_dir:
        _print_success(f"TAK Directory:   {tak_dir}")
    else:
        print("  ✗ TAK Directory:   not found")

    if certs_dir:
        _print_success(f"Certs Directory: {certs_dir}")
    else:
        print("  ✗ Certs Directory: not found")

    if config_file:
        _print_success(f"Config File:     {config_file}")
    else:
        print("  ✗ Config File:     not found")

    # Offer search / verify / manual override if not found
    if not tak_dir:
        print()
        action_idx = _prompt_choice(
            [
                "Search filesystem for TAK installations",
                "Enter TAK directory path manually",
                "Continue without TAK directory",
            ],
            prompt_text="Choose action",
        )

        if action_idx == 0:
            _print_status("Searching filesystem (this may take a moment)…")
            hits = search_tak_directories(conn)
            if hits:
                print(f"\n  Found {len(hits)} installation(s):")
                sel = _prompt_choice(hits, prompt_text="Select TAK directory")
                tak_dir = hits[sel]
                # Re-detect with the chosen path
                old_env = os.environ.get("TAK_PATH")
                os.environ["TAK_PATH"] = tak_dir
                try:
                    detected = detect_tak_install(conn)
                finally:
                    if old_env is None:
                        os.environ.pop("TAK_PATH", None)
                    else:
                        os.environ["TAK_PATH"] = old_env
                tak_dir = detected.get("tak_dir")
                certs_dir = detected.get("certs_dir")
                config_file = detected.get("config_file")
                _print_success(f"Selected: {tak_dir}")
            else:
                _print_error("No TAK installations found.")

        elif action_idx == 1:
            tak_dir = _prompt("TAK directory path")
            certs_sub = tak_dir + "/certs" if tak_dir else None
            detected["tak_dir"] = tak_dir
            # Check if certs subdir exists
            if certs_sub:
                old_env = os.environ.get("TAK_PATH")
                os.environ["TAK_PATH"] = tak_dir
                try:
                    detected = detect_tak_install(conn)
                finally:
                    if old_env is None:
                        os.environ.pop("TAK_PATH", None)
                    else:
                        os.environ["TAK_PATH"] = old_env
                tak_dir = detected.get("tak_dir")
                certs_dir = detected.get("certs_dir")
                config_file = detected.get("config_file")

    # Verify if desired
    if tak_dir and _prompt_yes_no("Verify TAK directory?", default=True):
        lines = verify_tak_directory(tak_dir, conn)
        print()
        for line in lines:
            print(f"  {line}")

    # ------------------------------------------------------------------
    # Step 3: Remote Server
    # ------------------------------------------------------------------
    _print_header("Step 3: Remote Server Configuration")
    remote_addr = _prompt("Remote Server Address (IP or hostname)")
    remote_port = _prompt("Remote Federation Port", default=DEFAULT_FEDERATION_PORT)

    # Validate port
    try:
        port_val = int(remote_port)
        if not (1 <= port_val <= 65535):
            raise ValueError
    except ValueError:
        _print_error(f"Invalid port: {remote_port} – using default {DEFAULT_FEDERATION_PORT}")
        remote_port = DEFAULT_FEDERATION_PORT

    # ------------------------------------------------------------------
    # Step 4: Trust Certificate
    # ------------------------------------------------------------------
    _print_header("Step 4: Trust Certificate")
    cert_path = _prompt("Path to trust certificate (.pem file)")

    # Use detected certs_dir as default destination
    default_dest = certs_dir if certs_dir else DEFAULT_CERT_DIR
    cert_dest_dir = _prompt("Save certificate to directory", default=default_dest)

    # ------------------------------------------------------------------
    # Step 5: Auto-Configure
    # ------------------------------------------------------------------
    _print_header("Step 5: Auto-Configure")
    auto_config = False
    if config_file:
        auto_config = _prompt_yes_no(
            f"Update {os.path.basename(config_file)} with federation outgoing entry?",
            default=True,
        )
    else:
        print("  No config file detected – skipping auto-configuration.")
        print("  You will need to edit CoreConfig.xml manually.")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    errors = []
    if not remote_addr:
        errors.append("• Remote Server Address is required.")
    if not remote_port:
        errors.append("• Remote Federation Port is required.")
    if not cert_path:
        errors.append("• A trust certificate file (.pem) must be selected.")
    if not cert_dest_dir:
        errors.append("• Save-to directory must not be empty.")
    if auto_config and not config_file:
        errors.append("• Auto-configure is enabled but no config file was detected.")
    if conn.is_remote and not conn.ssh_host:
        errors.append("• SSH mode is selected but no SSH host is set.")

    if errors:
        _print_header("Validation Errors")
        for err in errors:
            print(f"  {err}")
        print("\n  Please restart and correct the above issues.\n")
        return

    # ------------------------------------------------------------------
    # Step 6: Review
    # ------------------------------------------------------------------
    _print_header("Step 6: Review Planned Changes")
    summary = build_change_summary(
        cert_src=cert_path,
        cert_dest_dir=cert_dest_dir,
        remote_addr=remote_addr,
        remote_port=remote_port,
        auto_config=auto_config,
        config_file=config_file,
        conn=conn,
    )
    print()
    for line in summary.splitlines():
        print(f"  {line}")
    print()

    if not _prompt_yes_no("Apply these changes?", default=False):
        print("\n  Cancelled. No changes were made.\n")
        return

    # ------------------------------------------------------------------
    # Step 7: Apply Changes
    # ------------------------------------------------------------------
    _print_header("Applying Changes")

    # --- Copy certificate ---
    _print_status("Copying certificate…")
    if conn.is_remote:
        conn.run_command(f"mkdir -p {_sh_quote(cert_dest_dir)}")
        ok, msg = conn.copy_file_to_server(cert_path, cert_dest_dir)
        if not ok:
            _print_error(f"Failed to copy certificate via SCP: {msg}")
            return
        saved_path = msg
    else:
        try:
            saved_path = save_certificate(cert_path, cert_dest_dir)
        except (ValueError, OSError) as exc:
            _print_error(f"Error saving certificate: {exc}")
            return

    _print_success(f"Certificate saved to: {saved_path}")

    # --- Auto-configure CoreConfig.xml ---
    config_updated = False
    if auto_config and config_file:
        _print_status("Updating configuration…")

        if conn.is_remote:
            rc, remote_content = conn.run_command(
                f"cat {_sh_quote(config_file)}"
            )
            if rc != 0:
                _print_error(f"Could not read remote config: {remote_content}")
            else:
                tmp_path = None
                try:
                    fd, tmp_path = tempfile.mkstemp(suffix=".xml")
                    with os.fdopen(fd, "w") as f:
                        f.write(remote_content)
                    update_core_config(
                        tmp_path, remote_addr, remote_port,
                        os.path.basename(cert_path),
                    )
                    ok, msg = conn.copy_file_to_server(
                        tmp_path, os.path.dirname(config_file)
                    )
                    if ok:
                        base = os.path.basename(tmp_path)
                        cfg_dir = os.path.dirname(config_file)
                        remote_tmp = cfg_dir + "/" + base
                        conn.run_command(
                            f"mv {_sh_quote(remote_tmp)} "
                            f"{_sh_quote(config_file)}"
                        )
                        config_updated = True
                    else:
                        _print_error(f"Could not upload updated config: {msg}")
                except (OSError, ET.ParseError) as exc:
                    _print_error(f"Config update failed: {exc}")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
        else:
            try:
                update_core_config(
                    config_file, remote_addr, remote_port,
                    os.path.basename(cert_path),
                )
                config_updated = True
            except (OSError, ET.ParseError) as exc:
                _print_error(
                    f"Certificate was saved but config could not be updated: {exc}\n"
                    f"  You may need to edit it manually."
                )

    # --- Final status ---
    _print_header("Result")
    if config_updated:
        _print_success("Federation configured successfully!")
        print(f"\n  Certificate saved to: {saved_path}")
        print(f"  Config updated:       {config_file}")
        print(f"\n  Next step: Restart the TAK server service.\n")
    else:
        _print_success("Trust certificate saved successfully!")
        print(f"\n  Saved to: {saved_path}")
        print(f"\n  Next steps:")
        print(f"    1. Open your TAK server's CoreConfig.xml.")
        print(f'    2. Add a federation outgoing entry with:')
        print(f'         address="{remote_addr}"')
        print(f'         port="{remote_port}"')
        print(f"    3. Restart the TAK server service.")
        print(f"\n  See README.md for a full configuration example.\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        run_cli()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. No changes were made.\n")
        sys.exit(1)
    except EOFError:
        print("\n\n  Input ended. No changes were made.\n")
        sys.exit(1)
