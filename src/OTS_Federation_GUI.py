"""
OTS_Federation_GUI.py - TAK Federation Setup Helper
=====================================================

Usage:
    python3 src/OTS_Federation_GUI.py

Description:
    This tool provides a simple graphical interface to help configure
    TAK Federation between two OpenTAK servers.  It lets you specify
    the remote (target) server address and port, browse for a PEM trust
    certificate, and copy that certificate into the correct local
    directory so the TAK server can use it for federation.

    Optional fields (local server name, admin username/password) are
    included for future extensions and are not required for the MVP.

Requirements:
    - Python 3.6+
    - Tkinter  (ships with the standard Python distribution on Windows,
      macOS, and most Linux distros; on Debian/Ubuntu install with:
        sudo apt-get install python3-tk)

Steps performed by this tool:
    1. Validate that Remote Server Address, Remote Port, and a trust
       certificate file have been provided.
    2. Copy (upload) the selected PEM certificate to the local TAK
       certificate directory:
           <user home>/tak/certs/  (created if it does not exist)
    3. Display a confirmation message with the saved certificate path
       and a reminder to restart the TAK server.

Notes:
    - The tool does NOT modify server.xml automatically.  After running
      this tool, add the <Federation> block to your server.xml manually
      (see README.md for an example snippet).
    - Make sure the TAK server process has read access to the certificate
      directory.

Author:  OTS-Federations-easy project
License: MIT
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default local directory where the trust certificate will be saved.
# Falls back to ~/tak/certs if the environment variable is not set.
DEFAULT_CERT_DIR = os.path.join(os.path.expanduser("~"), "tak", "certs")

# Default federation port used by most TAK server installations.
DEFAULT_FEDERATION_PORT = "8089"

# Window title
APP_TITLE = "OTS Federation Setup Helper"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def save_certificate(src_path: str, dest_dir: str) -> str:
    """
    Copy the PEM certificate from *src_path* into *dest_dir*.

    Creates *dest_dir* (including any intermediate directories) if it does
    not already exist.  Returns the full destination path on success.

    Raises:
        ValueError: if *src_path* does not exist or is not a regular file.
        OSError:    if the directory cannot be created or the file cannot
                    be copied.
    """
    if not os.path.isfile(src_path):
        raise ValueError(f"Certificate file not found: {src_path}")

    os.makedirs(dest_dir, exist_ok=True)

    filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, filename)

    # Avoid overwriting silently – the GUI warns the user instead.
    shutil.copy2(src_path, dest_path)
    return dest_path


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

        self._build_ui()
        self._center_window()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Construct and lay out all widgets."""

        # Outer padding frame
        outer = ttk.Frame(self, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")

        # ---- Section: Remote Server ----------------------------------------
        remote_frame = ttk.LabelFrame(outer, text="Remote Server (required)", padding=10)
        remote_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(remote_frame, text="Remote Server Address:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._remote_addr = ttk.Entry(remote_frame, width=36)
        self._remote_addr.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)
        self._remote_addr.insert(0, "")

        ttk.Label(remote_frame, text="Remote Federation Port:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._remote_port = ttk.Entry(remote_frame, width=10)
        self._remote_port.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4)
        self._remote_port.insert(0, DEFAULT_FEDERATION_PORT)

        remote_frame.columnconfigure(1, weight=1)

        # ---- Section: Trust Certificate ------------------------------------
        cert_frame = ttk.LabelFrame(outer, text="Trust Certificate (required)", padding=10)
        cert_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(cert_frame, text="Certificate File (.pem):").grid(
            row=0, column=0, sticky="w", pady=4
        )
        cert_entry = ttk.Entry(cert_frame, textvariable=self._cert_path_var, width=30)
        cert_entry.grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=4)
        ttk.Button(cert_frame, text="Browse…", command=self._browse_cert).grid(
            row=0, column=2, pady=4
        )

        ttk.Label(cert_frame, text="Save to Directory:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._cert_dest_dir = ttk.Entry(cert_frame, width=36)
        self._cert_dest_dir.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)
        self._cert_dest_dir.insert(0, DEFAULT_CERT_DIR)

        cert_frame.columnconfigure(1, weight=1)

        # ---- Section: Local Server (optional) ------------------------------
        local_frame = ttk.LabelFrame(outer, text="Local Server (optional)", padding=10)
        local_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(local_frame, text="Local Server Name:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._local_name = ttk.Entry(local_frame, width=36)
        self._local_name.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(local_frame, text="Admin Username:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._admin_user = ttk.Entry(local_frame, width=36)
        self._admin_user.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(local_frame, text="Admin Password:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self._admin_pass = ttk.Entry(local_frame, width=36, show="*")
        self._admin_pass.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=4)

        local_frame.columnconfigure(1, weight=1)

        # ---- Buttons -------------------------------------------------------
        btn_frame = ttk.Frame(outer)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="e", pady=(4, 0))

        ttk.Button(btn_frame, text="Reset", command=self._reset_fields).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(
            btn_frame,
            text="Save Certificate & Configure",
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
        status_bar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

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
            self._status_var.set(f"Certificate selected: {os.path.basename(path)}")

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
        self._status_var.set("Fields reset.")

    def _on_submit(self):
        """Validate inputs, save the certificate, and show a result message."""

        # --- Collect values -------------------------------------------------
        remote_addr = self._remote_addr.get().strip()
        remote_port = self._remote_port.get().strip()
        cert_path = self._cert_path_var.get().strip()
        dest_dir = self._cert_dest_dir.get().strip()

        # --- Required field validation --------------------------------------
        errors = []

        if not remote_addr:
            errors.append("• Remote Server Address is required.")

        if not remote_port:
            errors.append("• Remote Federation Port is required.")
        else:
            try:
                port_num = int(remote_port)
                # Port 0 is excluded: TAK Federation requires an explicit,
                # fixed port; "any available port" is not a valid target.
                if not (1 <= port_num <= 65535):
                    raise ValueError
            except ValueError:
                errors.append("• Remote Federation Port must be a number between 1 and 65535.")

        if not cert_path:
            errors.append("• A trust certificate file (.pem) must be selected.")

        if not dest_dir:
            errors.append("• Save-to directory must not be empty.")

        if errors:
            messagebox.showerror(
                "Validation Error",
                "Please fix the following issues before continuing:\n\n"
                + "\n".join(errors),
            )
            self._status_var.set("Validation failed – see error dialog.")
            return

        # --- Warn before overwriting ----------------------------------------
        dest_path = os.path.join(dest_dir, os.path.basename(cert_path))
        if os.path.exists(dest_path):
            overwrite = messagebox.askyesno(
                "File Exists",
                f"The file\n\n  {dest_path}\n\nalready exists.\n\nOverwrite it?",
            )
            if not overwrite:
                self._status_var.set("Cancelled – certificate not saved.")
                return

        # --- Save certificate -----------------------------------------------
        try:
            saved_path = save_certificate(cert_path, dest_dir)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Error Saving Certificate", str(exc))
            self._status_var.set("Error saving certificate.")
            return

        # --- Success --------------------------------------------------------
        success_msg = (
            f"Trust certificate saved successfully!\n\n"
            f"  Saved to:  {saved_path}\n\n"
            f"Next steps:\n"
            f"  1. Open your TAK server's server.xml.\n"
            f"  2. Add a <Federation> block with:\n"
            f"       <remoteHost>{remote_addr}</remoteHost>\n"
            f"       <remotePort>{remote_port}</remotePort>\n"
            f"       <caFile>{saved_path}</caFile>\n"
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
