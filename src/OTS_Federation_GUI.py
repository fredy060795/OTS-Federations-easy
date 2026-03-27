"""
OTS_Federation_GUI.py - TAK Federation Setup Helper
=====================================================

Usage:
    python3 src/OTS_Federation_GUI.py

Description:
    This tool provides a simple graphical interface to help configure
    TAK Federation between two OpenTAK servers.  The tool automatically
    detects the local OpenTAK server installation (certificate directory
    and CoreConfig.xml) so the user only needs to enter the remote server
    details and select a trust certificate – the system does the rest.

    The auto-detection searches well-known installation paths:
        /opt/tak          – standard Linux / Docker installation
        ~/tak             – home-directory installation
        TAK_PATH env var  – custom override

    Optional fields (local server name, admin username/password) are
    included for future extensions and are not required for the MVP.

Requirements:
    - Python 3.6+
    - Tkinter  (ships with the standard Python distribution on Windows,
      macOS, and most Linux distros; on Debian/Ubuntu install with:
        sudo apt-get install python3-tk)

Steps performed by this tool:
    1. Auto-detect the local OpenTAK server installation paths.
    2. Validate that Remote Server Address, Remote Port, and a trust
       certificate file have been provided.
    3. Copy (upload) the selected PEM certificate to the detected (or
       manually chosen) TAK certificate directory.
    4. Optionally update CoreConfig.xml with the federation outgoing
       connection block.
    5. Display a confirmation message with the saved certificate path
       and a reminder to restart the TAK server.

Notes:
    - Make sure the TAK server process has read access to the certificate
      directory.

Author:  OTS-Federations-easy project
License: MIT
"""

import os
import shutil
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default local directory where the trust certificate will be saved.
# Falls back to ~/tak/certs if the environment variable is not set.
DEFAULT_CERT_DIR = os.path.join(os.path.expanduser("~"), "tak", "certs")

# Default federation port used by most TAK server installations.
DEFAULT_FEDERATION_PORT = "9000"

# Window title
APP_TITLE = "OTS Federation Setup Helper"

# Well-known OpenTAK Server installation directories (searched in order).
_CANDIDATE_TAK_DIRS: List[str] = [
    "/opt/tak",
    os.path.join(os.path.expanduser("~"), "tak"),
]

# Config file names to look for inside a TAK directory.
_CONFIG_FILENAMES = ("CoreConfig.xml", "TAKIgniteConfig.xml")


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------

def detect_tak_install() -> Dict[str, Optional[str]]:
    """Return auto-detected paths for the local OpenTAK server.

    The function probes a list of well-known directories (and the
    ``TAK_PATH`` environment variable) for the presence of a TAK
    certificate directory and a configuration file.

    Returns a dict with keys ``"tak_dir"``, ``"certs_dir"``, and
    ``"config_file"``.  Each value is either an absolute path string
    or ``None`` if the item was not found.
    """
    result: Dict[str, Optional[str]] = {
        "tak_dir": None,
        "certs_dir": None,
        "config_file": None,
    }

    candidates = list(_CANDIDATE_TAK_DIRS)

    # Honour a user-supplied override via environment variable.
    env_path = os.environ.get("TAK_PATH")
    if env_path:
        candidates.insert(0, env_path)

    for base in candidates:
        if not os.path.isdir(base):
            continue

        result["tak_dir"] = base

        # --- Certs directory ------------------------------------------------
        certs = os.path.join(base, "certs")
        if os.path.isdir(certs):
            result["certs_dir"] = certs

        # --- Configuration file ---------------------------------------------
        for cfg_name in _CONFIG_FILENAMES:
            cfg_path = os.path.join(base, cfg_name)
            if os.path.isfile(cfg_path):
                result["config_file"] = cfg_path
                break

        # If we found a TAK dir, stop searching further candidates.
        if result["certs_dir"] or result["config_file"]:
            break

    return result


# ---------------------------------------------------------------------------
# XML configuration helpers
# ---------------------------------------------------------------------------

def update_core_config(
    config_path: str,
    remote_addr: str,
    remote_port: str,
    cert_filename: str,
) -> None:
    """Add or update a federation outgoing entry in *config_path*.

    The function reads the CoreConfig.xml (or TAKIgniteConfig.xml),
    ensures a ``<federation>`` element exists, and adds a
    ``<federationOutgoing>`` child with a ``<federateOutgoing>``
    entry for the given remote server.

    Raises ``OSError`` / ``ET.ParseError`` on I/O or parse failures.
    """
    tree = ET.parse(config_path)
    root = tree.getroot()

    # Locate or create <federation>
    federation = root.find("federation")
    if federation is None:
        federation = ET.SubElement(root, "federation")

    # Locate or create <federationOutgoing>
    fed_outgoing = federation.find("federationOutgoing")
    if fed_outgoing is None:
        fed_outgoing = ET.SubElement(federation, "federationOutgoing")

    # Avoid duplicates: check if this remote already exists.
    for existing in fed_outgoing.findall("federateOutgoing"):
        if (
            existing.get("address") == remote_addr
            and existing.get("port") == remote_port
        ):
            # Already configured – update the display name and return.
            existing.set("display", f"Federation-{remote_addr}")
            tree.write(config_path, xml_declaration=True, encoding="UTF-8")
            return

    # Create new <federateOutgoing> entry
    entry = ET.SubElement(fed_outgoing, "federateOutgoing")
    entry.set("display", f"Federation-{remote_addr}")
    entry.set("address", remote_addr)
    entry.set("port", remote_port)
    entry.set("reconnectInterval", "30")
    entry.set("enabled", "true")
    entry.set("protocol", "ssl")
    entry.set("fallback", "")

    tree.write(config_path, xml_declaration=True, encoding="UTF-8")


# ---------------------------------------------------------------------------
# Certificate helper
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
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Construct and lay out all widgets."""

        # Outer padding frame
        outer = ttk.Frame(self, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")

        # ---- Section: Detected TAK Installation ----------------------------
        detect_frame = ttk.LabelFrame(
            outer, text="OpenTAK Server (auto-detected)", padding=10
        )
        detect_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(detect_frame, text="TAK Directory:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._tak_dir_var = tk.StringVar(value="detecting…")
        ttk.Label(detect_frame, textvariable=self._tak_dir_var).grid(
            row=0, column=1, sticky="w", padx=(8, 0), pady=4
        )

        ttk.Label(detect_frame, text="Certs Directory:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self._certs_dir_var = tk.StringVar(value="detecting…")
        ttk.Label(detect_frame, textvariable=self._certs_dir_var).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=4
        )

        ttk.Label(detect_frame, text="Config File:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self._config_var = tk.StringVar(value="detecting…")
        ttk.Label(detect_frame, textvariable=self._config_var).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=4
        )

        ttk.Button(
            detect_frame, text="Re-Detect", command=self._run_auto_detect
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        detect_frame.columnconfigure(1, weight=1)

        # ---- Section: Remote Server ----------------------------------------
        remote_frame = ttk.LabelFrame(
            outer, text="Remote Server (required)", padding=10
        )
        remote_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

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
        cert_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

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
            row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )

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
            row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )

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
            row=5, column=0, columnspan=2, sticky="e", pady=(4, 0)
        )

        ttk.Button(
            btn_frame, text="Reset", command=self._reset_fields
        ).pack(side="left", padx=(0, 8))
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
        status_bar.grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def _run_auto_detect(self):
        """Run path auto-detection and update the UI labels."""
        self._detected = detect_tak_install()

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
            self._status_var.set(f"Auto-detected TAK installation at {tak_dir}")
        else:
            self._status_var.set(
                "TAK installation not detected – please set paths manually."
            )

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
        """Validate inputs, save the certificate, and show a result message."""

        # --- Collect values -------------------------------------------------
        remote_addr = self._remote_addr.get().strip()
        remote_port = self._remote_port.get().strip()
        cert_path = self._cert_path_var.get().strip()
        dest_dir = self._cert_dest_dir.get().strip()
        auto_config = self._auto_config_var.get()

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
                f"The file\n\n  {dest_path}\n\nalready exists.\n\n"
                f"Overwrite it?",
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

        # --- Auto-configure CoreConfig.xml ----------------------------------
        config_updated = False
        config_file = self._detected.get("config_file")
        if auto_config and config_file:
            try:
                update_core_config(
                    config_file,
                    remote_addr,
                    remote_port,
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
