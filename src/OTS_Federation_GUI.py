"""
OTS_Federation_GUI.py - TAK Federation Setup Helper
=====================================================

Usage:
    python3 src/OTS_Federation_GUI.py

Description:
    This tool provides a simple graphical interface to help configure
    TAK Federation between two OpenTAK servers.  It can operate either
    **locally** (directly on the TAK server) or **via SSH** to a remote
    TAK server.

    Key features:
        - **SSH & local mode** – choose to work directly on the machine
          or connect to a remote TAK server over SSH.
        - **Auto-detection & search** – automatically find (or search for)
          the TAK installation directory on the target server.
        - **Directory verification** – verify that a directory really is a
          valid OpenTAK installation (expected sub-directories, config files).
        - **Manual review before changes** – every planned action (copy
          certificate, update config) is shown to the user for approval
          before anything is written.

    The auto-detection searches well-known installation paths:
        /opt/tak          – standard Linux / Docker installation
        ~/tak             – home-directory installation
        TAK_PATH env var  – custom override

Requirements:
    - Python 3.6+
    - Tkinter  (ships with the standard Python distribution on Windows,
      macOS, and most Linux distros; on Debian/Ubuntu install with:
        sudo apt-get install python3-tk)
    - For SSH mode: an ``ssh`` / ``scp`` client on PATH and key-based
      or agent-based authentication to the target server.

    For a terminal-only version that works without Tkinter (e.g. over
    SSH or on headless servers), use ``start.sh`` or run::

        python3 src/OTS_Federation_CLI.py

Author:  OTS-Federations-easy project
License: MIT
"""

import os
import sys
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

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

# Window title
APP_TITLE = "OTS Federation Setup Helper"


# ---------------------------------------------------------------------------
# Main GUI application
# ---------------------------------------------------------------------------

class FederationSetupApp(tk.Tk):
    """Main application window for the TAK Federation Setup Helper."""

    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.resizable(False, False)

        # Holds the path selected via the file dialog.
        self._cert_path_var = tk.StringVar()

        # Detected paths (populated by auto-detection).
        self._detected: Dict[str, Optional[str]] = {
            "tak_dir": None,
            "certs_dir": None,
            "config_file": None,
        }

        self._build_ui()
        self._center_window()

        # Run auto-detection on startup.
        self.after(100, self._run_auto_detect)

    # ------------------------------------------------------------------
    # Helper: build a ServerConnection from current UI state
    # ------------------------------------------------------------------

    def _get_connection(self) -> ServerConnection:
        """Return a ``ServerConnection`` based on the current UI mode."""
        if self._conn_mode_var.get() == "ssh":
            host = self._ssh_host.get().strip()
            user = self._ssh_user.get().strip() or None
            try:
                port = int(self._ssh_port.get().strip())
            except (ValueError, TypeError):
                port = 22
            return ServerConnection(
                ssh_host=host or None, ssh_user=user, ssh_port=port,
            )
        return ServerConnection()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Construct and lay out all widgets."""

        # Outer padding frame
        outer = ttk.Frame(self, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")

        row_idx = 0

        # ---- Section: Connection Mode --------------------------------------
        conn_frame = ttk.LabelFrame(
            outer, text="Connection Mode", padding=10
        )
        conn_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row_idx += 1

        self._conn_mode_var = tk.StringVar(value="local")
        ttk.Radiobutton(
            conn_frame, text="Local (directly on this server)",
            variable=self._conn_mode_var, value="local",
            command=self._on_conn_mode_changed,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=2)
        ttk.Radiobutton(
            conn_frame, text="SSH (connect to remote TAK server)",
            variable=self._conn_mode_var, value="ssh",
            command=self._on_conn_mode_changed,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=2)

        ttk.Label(conn_frame, text="SSH Host:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self._ssh_host = ttk.Entry(conn_frame, width=24)
        self._ssh_host.grid(row=2, column=1, sticky="ew", padx=(8, 4), pady=4)
        ttk.Label(conn_frame, text="User:").grid(
            row=2, column=2, sticky="w", padx=(4, 0), pady=4
        )
        self._ssh_user = ttk.Entry(conn_frame, width=12)
        self._ssh_user.grid(row=2, column=3, sticky="ew", padx=(4, 0), pady=4)
        ttk.Label(conn_frame, text="Port:").grid(
            row=3, column=0, sticky="w", pady=4
        )
        self._ssh_port = ttk.Entry(conn_frame, width=6)
        self._ssh_port.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=4)
        self._ssh_port.insert(0, "22")

        self._ssh_test_btn = ttk.Button(
            conn_frame, text="Test Connection", command=self._test_ssh
        )
        self._ssh_test_btn.grid(row=3, column=2, columnspan=2, sticky="w",
                                padx=(8, 0), pady=4)

        conn_frame.columnconfigure(1, weight=1)
        # Initially disable SSH fields.
        self._toggle_ssh_fields(False)

        # ---- Section: Detected TAK Installation ----------------------------
        detect_frame = ttk.LabelFrame(
            outer, text="OpenTAK Server (auto-detected)", padding=10
        )
        detect_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row_idx += 1

        ttk.Label(detect_frame, text="TAK Directory:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._tak_dir_var = tk.StringVar(value="detecting…")
        ttk.Label(detect_frame, textvariable=self._tak_dir_var).grid(
            row=0, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=4
        )

        ttk.Label(detect_frame, text="Certs Directory:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._certs_dir_var = tk.StringVar(value="detecting…")
        ttk.Label(detect_frame, textvariable=self._certs_dir_var).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=4
        )

        ttk.Label(detect_frame, text="Config File:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self._config_var = tk.StringVar(value="detecting…")
        ttk.Label(detect_frame, textvariable=self._config_var).grid(
            row=2, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=4
        )

        detect_btn_frame = ttk.Frame(detect_frame)
        detect_btn_frame.grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )
        ttk.Button(
            detect_btn_frame, text="Re-Detect", command=self._run_auto_detect
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            detect_btn_frame, text="Search…", command=self._search_tak
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            detect_btn_frame, text="Verify", command=self._verify_tak
        ).pack(side="left")

        detect_frame.columnconfigure(1, weight=1)

        # ---- Section: Remote Server ----------------------------------------
        remote_frame = ttk.LabelFrame(
            outer, text="Remote Server (required)", padding=10
        )
        remote_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row_idx += 1

        ttk.Label(remote_frame, text="Remote Server Address:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._remote_addr = ttk.Entry(remote_frame, width=36)
        self._remote_addr.grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=4
        )
        self._remote_addr.insert(0, "")

        ttk.Label(remote_frame, text="Remote Federation Port:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._remote_port = ttk.Entry(remote_frame, width=10)
        self._remote_port.grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=4
        )
        self._remote_port.insert(0, DEFAULT_FEDERATION_PORT)

        remote_frame.columnconfigure(1, weight=1)

        # ---- Section: Trust Certificate ------------------------------------
        cert_frame = ttk.LabelFrame(
            outer, text="Trust Certificate (required)", padding=10
        )
        cert_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row_idx += 1

        ttk.Label(cert_frame, text="Certificate File (.pem):").grid(
            row=0, column=0, sticky="w", pady=4
        )
        cert_entry = ttk.Entry(
            cert_frame, textvariable=self._cert_path_var, width=30
        )
        cert_entry.grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=4)
        ttk.Button(
            cert_frame, text="Browse…", command=self._browse_cert
        ).grid(row=0, column=2, pady=4)

        ttk.Label(cert_frame, text="Save to Directory:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._cert_dest_dir = ttk.Entry(cert_frame, width=36)
        self._cert_dest_dir.grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4
        )
        self._cert_dest_dir.insert(0, DEFAULT_CERT_DIR)

        cert_frame.columnconfigure(1, weight=1)

        # ---- Section: Auto-Configure ---------------------------------------
        config_frame = ttk.LabelFrame(
            outer, text="Auto-Configure (optional)", padding=10
        )
        config_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row_idx += 1

        self._auto_config_var = tk.BooleanVar(value=False)
        self._auto_config_check = ttk.Checkbutton(
            config_frame,
            text="Update CoreConfig.xml with federation outgoing entry",
            variable=self._auto_config_var,
        )
        self._auto_config_check.grid(
            row=0, column=0, sticky="w", pady=4
        )

        config_frame.columnconfigure(0, weight=1)

        # ---- Section: Local Server (optional) ------------------------------
        local_frame = ttk.LabelFrame(
            outer, text="Local Server (optional)", padding=10
        )
        local_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row_idx += 1

        ttk.Label(local_frame, text="Local Server Name:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._local_name = ttk.Entry(local_frame, width=36)
        self._local_name.grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(local_frame, text="Admin Username:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._admin_user = ttk.Entry(local_frame, width=36)
        self._admin_user.grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(local_frame, text="Admin Password:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self._admin_pass = ttk.Entry(local_frame, width=36, show="*")
        self._admin_pass.grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=4
        )

        local_frame.columnconfigure(1, weight=1)

        # ---- Buttons -------------------------------------------------------
        btn_frame = ttk.Frame(outer)
        btn_frame.grid(
            row=row_idx, column=0, columnspan=2, sticky="e", pady=(4, 0)
        )
        row_idx += 1

        ttk.Button(
            btn_frame, text="Reset", command=self._reset_fields
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            btn_frame,
            text="Review & Apply…",
            command=self._on_submit,
        ).pack(side="left")

        # ---- Status bar ----------------------------------------------------
        self._status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(
            outer,
            textvariable=self._status_var,
            relief="sunken",
            anchor="w",
            padding=(4, 2),
        )
        status_bar.grid(
            row=row_idx, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

    # ------------------------------------------------------------------
    # Connection-mode toggling
    # ------------------------------------------------------------------

    def _toggle_ssh_fields(self, enabled: bool):
        """Enable or disable the SSH entry fields."""
        state = "!disabled" if enabled else "disabled"
        for widget in (
            self._ssh_host, self._ssh_user, self._ssh_port,
            self._ssh_test_btn,
        ):
            widget.state([state])

    def _on_conn_mode_changed(self):
        is_ssh = self._conn_mode_var.get() == "ssh"
        self._toggle_ssh_fields(is_ssh)
        self._status_var.set(
            "SSH mode selected – fill in host details."
            if is_ssh else "Local mode selected."
        )

    def _test_ssh(self):
        """Test the SSH connection to the configured host."""
        conn = self._get_connection()
        if not conn.is_remote:
            messagebox.showinfo("SSH Test", "Not in SSH mode.")
            return
        self._status_var.set("Testing SSH connection…")
        self.update_idletasks()
        rc, output = conn.run_command("echo ok")
        if rc == 0 and "ok" in output:
            messagebox.showinfo("SSH Test", f"Connection successful!\n\n{conn.label}")
            self._status_var.set(f"SSH connection to {conn.label} OK")
        else:
            messagebox.showerror(
                "SSH Test Failed",
                f"Could not connect to {conn.label}.\n\n{output}"
            )
            self._status_var.set("SSH connection failed.")

    # ------------------------------------------------------------------
    # Auto-detection / Search / Verify
    # ------------------------------------------------------------------

    def _run_auto_detect(self):
        """Run path auto-detection and update the UI labels."""
        conn = self._get_connection()
        self._status_var.set("Detecting TAK installation…")
        self.update_idletasks()

        self._detected = detect_tak_install(conn)

        # TAK directory
        tak_dir = self._detected["tak_dir"]
        if tak_dir:
            self._tak_dir_var.set(tak_dir)
        else:
            self._tak_dir_var.set("not found")

        # Certs directory – also update the dest-dir entry.
        certs_dir = self._detected["certs_dir"]
        if certs_dir:
            self._certs_dir_var.set(certs_dir)
            self._cert_dest_dir.delete(0, tk.END)
            self._cert_dest_dir.insert(0, certs_dir)
        else:
            self._certs_dir_var.set("not found")

        # Config file – enable/disable auto-configure checkbox.
        config_file = self._detected["config_file"]
        if config_file:
            self._config_var.set(config_file)
            self._auto_config_var.set(True)
            self._auto_config_check.state(["!disabled"])
        else:
            self._config_var.set("not found")
            self._auto_config_var.set(False)
            self._auto_config_check.state(["disabled"])

        if tak_dir:
            self._status_var.set(
                f"Auto-detected TAK installation at {tak_dir}"
            )
        else:
            self._status_var.set(
                "TAK installation not detected – use Search or set paths manually."
            )

    def _search_tak(self):
        """Search the filesystem for TAK installations."""
        conn = self._get_connection()
        self._status_var.set("Searching for TAK installations…")
        self.update_idletasks()

        hits = search_tak_directories(conn)

        if not hits:
            messagebox.showinfo(
                "Search Results",
                "No TAK installations found on the target system.\n\n"
                "You can set the paths manually."
            )
            self._status_var.set("Search complete – no TAK installations found.")
            return

        # Let the user pick from the results.
        pick_win = tk.Toplevel(self)
        pick_win.title("Search Results – Select TAK Directory")
        pick_win.resizable(False, False)
        pick_win.transient(self)
        pick_win.grab_set()

        ttk.Label(
            pick_win,
            text="The following TAK installations were found.\n"
                 "Select one and click OK:",
            padding=10,
        ).pack(fill="x")

        listbox = tk.Listbox(pick_win, width=60, height=min(len(hits), 10))
        for h in hits:
            listbox.insert(tk.END, h)
        listbox.selection_set(0)
        listbox.pack(padx=10, pady=(0, 10))

        def _on_pick_ok():
            sel = listbox.curselection()
            if sel:
                chosen = hits[sel[0]]
                self._tak_dir_var.set(chosen)
                # Re-detect with the chosen path as override.
                old = os.environ.get("TAK_PATH")
                os.environ["TAK_PATH"] = chosen
                try:
                    self._run_auto_detect()
                finally:
                    if old is None:
                        os.environ.pop("TAK_PATH", None)
                    else:
                        os.environ["TAK_PATH"] = old
            pick_win.destroy()

        ttk.Button(pick_win, text="OK", command=_on_pick_ok).pack(pady=(0, 10))
        self._status_var.set(f"Search complete – {len(hits)} installation(s) found.")

    def _verify_tak(self):
        """Verify the currently detected TAK directory."""
        tak_dir = self._detected.get("tak_dir")
        if not tak_dir:
            messagebox.showwarning(
                "Verify",
                "No TAK directory detected yet.\nRun Detect or Search first."
            )
            return

        conn = self._get_connection()
        self._status_var.set("Verifying TAK directory…")
        self.update_idletasks()

        lines = verify_tak_directory(tak_dir, conn)
        messagebox.showinfo("Directory Verification", "\n".join(lines))
        self._status_var.set("Verification complete.")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_cert(self):
        """Open a file-chooser dialog and populate the certificate path entry."""
        path = filedialog.askopenfilename(
            title="Select Trust Certificate",
            filetypes=[("PEM certificate", "*.pem"), ("All files", "*.*")],
        )
        if path:
            self._cert_path_var.set(path)
            self._status_var.set(
                f"Certificate selected: {os.path.basename(path)}"
            )

    def _reset_fields(self):
        """Clear all form fields and reset defaults."""
        self._remote_addr.delete(0, tk.END)
        self._remote_port.delete(0, tk.END)
        self._remote_port.insert(0, DEFAULT_FEDERATION_PORT)
        self._cert_path_var.set("")
        self._cert_dest_dir.delete(0, tk.END)
        self._cert_dest_dir.insert(0, DEFAULT_CERT_DIR)
        self._local_name.delete(0, tk.END)
        self._admin_user.delete(0, tk.END)
        self._admin_pass.delete(0, tk.END)
        self._auto_config_var.set(False)
        self._status_var.set("Fields reset.")
        self._run_auto_detect()

    def _on_submit(self):
        """Validate → Review → Apply."""

        # --- Collect values -------------------------------------------------
        remote_addr = self._remote_addr.get().strip()
        remote_port = self._remote_port.get().strip()
        cert_path = self._cert_path_var.get().strip()
        dest_dir = self._cert_dest_dir.get().strip()
        auto_config = self._auto_config_var.get()
        conn = self._get_connection()

        # --- Required field validation --------------------------------------
        errors: List[str] = []

        if not remote_addr:
            errors.append("• Remote Server Address is required.")

        if not remote_port:
            errors.append("• Remote Federation Port is required.")
        else:
            try:
                port_num = int(remote_port)
                if not (1 <= port_num <= 65535):
                    raise ValueError
            except ValueError:
                errors.append(
                    "• Remote Federation Port must be a number "
                    "between 1 and 65535."
                )

        if not cert_path:
            errors.append(
                "• A trust certificate file (.pem) must be selected."
            )

        if not dest_dir:
            errors.append("• Save-to directory must not be empty.")

        if auto_config and not self._detected.get("config_file"):
            errors.append(
                "• Auto-configure is enabled but no CoreConfig.xml "
                "was detected. Uncheck the option or set the path "
                "manually."
            )

        if conn.is_remote and not conn.ssh_host:
            errors.append("• SSH mode is selected but no SSH host is set.")

        if errors:
            messagebox.showerror(
                "Validation Error",
                "Please fix the following issues before continuing:\n\n"
                + "\n".join(errors),
            )
            self._status_var.set("Validation failed – see error dialog.")
            return

        # --- Build & show review dialog ------------------------------------
        config_file = self._detected.get("config_file")
        summary = build_change_summary(
            cert_src=cert_path,
            cert_dest_dir=dest_dir,
            remote_addr=remote_addr,
            remote_port=remote_port,
            auto_config=auto_config,
            config_file=config_file,
            conn=conn,
        )

        approved = self._show_review_dialog(summary)
        if not approved:
            self._status_var.set("Cancelled by user during review.")
            return

        # --- Execute changes ------------------------------------------------
        self._apply_changes(
            cert_path=cert_path,
            dest_dir=dest_dir,
            remote_addr=remote_addr,
            remote_port=remote_port,
            auto_config=auto_config,
            config_file=config_file,
            conn=conn,
        )

    # ------------------------------------------------------------------
    # Review dialog
    # ------------------------------------------------------------------

    def _show_review_dialog(self, summary: str) -> bool:
        """Show a modal review dialog and return True if the user approves."""
        result = {"approved": False}

        dlg = tk.Toplevel(self)
        dlg.title("Review Planned Changes")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(
            dlg,
            text="Please review the following changes before applying:",
            padding=(10, 10, 10, 4),
        ).pack(fill="x")

        text_widget = tk.Text(dlg, width=55, height=20, wrap="word",
                              state="normal", font=("Courier", 10))
        text_widget.insert("1.0", summary)
        text_widget.configure(state="disabled")
        text_widget.pack(padx=10, pady=(0, 10))

        btn_frame = ttk.Frame(dlg, padding=(10, 0, 10, 10))
        btn_frame.pack(fill="x")

        def _approve():
            result["approved"] = True
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btn_frame, text="Apply Changes", command=_approve).pack(
            side="right"
        )

        self.wait_window(dlg)
        return result["approved"]

    # ------------------------------------------------------------------
    # Apply changes (after review)
    # ------------------------------------------------------------------

    def _apply_changes(
        self,
        cert_path: str,
        dest_dir: str,
        remote_addr: str,
        remote_port: str,
        auto_config: bool,
        config_file: Optional[str],
        conn: ServerConnection,
    ):
        """Execute the approved changes."""

        # --- Copy certificate -----------------------------------------------
        self._status_var.set("Copying certificate…")
        self.update_idletasks()

        if conn.is_remote:
            # Create dest dir on remote if needed.
            conn.run_command(f"mkdir -p {_sh_quote(dest_dir)}")
            ok, msg = conn.copy_file_to_server(cert_path, dest_dir)
            if not ok:
                messagebox.showerror(
                    "Error Copying Certificate",
                    f"Failed to copy certificate via SCP:\n\n{msg}"
                )
                self._status_var.set("Error copying certificate.")
                return
            saved_path = msg  # msg contains the remote path on success
        else:
            try:
                saved_path = save_certificate(cert_path, dest_dir)
            except (ValueError, OSError) as exc:
                messagebox.showerror("Error Saving Certificate", str(exc))
                self._status_var.set("Error saving certificate.")
                return

        # --- Auto-configure CoreConfig.xml ----------------------------------
        config_updated = False
        if auto_config and config_file:
            self._status_var.set("Updating configuration…")
            self.update_idletasks()

            if conn.is_remote:
                # For remote: we need to fetch the config, modify it, and
                # push it back. Use a temp file.
                import tempfile
                rc, remote_content = conn.run_command(
                    f"cat {_sh_quote(config_file)}"
                )
                if rc != 0:
                    messagebox.showwarning(
                        "Config Update Warning",
                        f"Could not read remote config:\n\n{remote_content}"
                    )
                else:
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
                        # Rename on remote to original config name.
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
                            messagebox.showwarning(
                                "Config Update Warning",
                                f"Could not upload updated config:\n\n{msg}"
                            )
                    except (OSError, ET.ParseError) as exc:
                        messagebox.showwarning(
                            "Config Update Warning",
                            f"Certificate was saved but config could not "
                            f"be updated:\n\n{exc}"
                        )
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
            else:
                try:
                    update_core_config(
                        config_file, remote_addr, remote_port,
                        os.path.basename(cert_path),
                    )
                    config_updated = True
                except (OSError, ET.ParseError) as exc:
                    messagebox.showwarning(
                        "Config Update Warning",
                        f"Certificate was saved but CoreConfig.xml could "
                        f"not be updated:\n\n{exc}\n\nYou may need to "
                        f"edit it manually.",
                    )

        # --- Success --------------------------------------------------------
        if config_updated:
            success_msg = (
                f"Federation configured successfully!\n\n"
                f"  Certificate saved to:  {saved_path}\n"
                f"  Config updated:  {config_file}\n\n"
                f"Next step:\n"
                f"  Restart the TAK server service.\n"
            )
        else:
            success_msg = (
                f"Trust certificate saved successfully!\n\n"
                f"  Saved to:  {saved_path}\n\n"
                f"Next steps:\n"
                f"  1. Open your TAK server's CoreConfig.xml.\n"
                f"  2. Add a federation outgoing entry with:\n"
                f"       address=\"{remote_addr}\"\n"
                f"       port=\"{remote_port}\"\n"
                f"  3. Restart the TAK server service.\n\n"
                f"See README.md for a full configuration example."
            )
        messagebox.showinfo("Federation Setup – Success", success_msg)
        self._status_var.set(f"Certificate saved to {saved_path}")

    # ------------------------------------------------------------------
    # Window utilities
    # ------------------------------------------------------------------

    def _center_window(self):
        """Center the window on screen after all widgets have been placed."""
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = FederationSetupApp()
    app.mainloop()
