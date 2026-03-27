"""
federation_core.py - Shared business logic for TAK Federation Setup
====================================================================

This module contains all the non-GUI business logic used by both the
graphical (Tkinter) and terminal (CLI) frontends.

Functions and classes exported:
    - ServerConnection
    - detect_tak_install
    - verify_tak_directory
    - search_tak_directories
    - build_change_summary
    - update_core_config
    - save_certificate

Author:  OTS-Federations-easy project
License: MIT
"""

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default local directory where the trust certificate will be saved.
# Falls back to ~/tak/certs if the environment variable is not set.
DEFAULT_CERT_DIR = os.path.join(os.path.expanduser("~"), "tak", "certs")

# Default federation port used by most TAK server installations.
DEFAULT_FEDERATION_PORT = "9000"

# Well-known OpenTAK Server installation directories (searched in order).
_CANDIDATE_TAK_DIRS: List[str] = [
    "/opt/tak",
    os.path.join(os.path.expanduser("~"), "tak"),
]

# Config file names to look for inside a TAK directory.
_CONFIG_FILENAMES = ("CoreConfig.xml", "TAKIgniteConfig.xml")

# Directories / files whose presence indicates a valid TAK installation.
_EXPECTED_TAK_SUBDIRS = ("certs",)
_EXPECTED_TAK_FILES = ("CoreConfig.xml", "TAKIgniteConfig.xml")

# Common base paths to search when scanning for TAK installations.
_SEARCH_ROOTS: List[str] = ["/opt", "/home", "/root", "/var/lib"]


# ---------------------------------------------------------------------------
# Server connection abstraction (local vs. SSH)
# ---------------------------------------------------------------------------

class ServerConnection:
    """Run commands and copy files either locally or over SSH.

    When *ssh_host* is ``None`` the connection operates locally.
    Otherwise commands are executed via ``ssh`` and files are copied
    with ``scp``.

    Only key-based / agent-based SSH authentication is supported
    (no interactive password prompts).
    """

    def __init__(
        self,
        ssh_host: Optional[str] = None,
        ssh_user: Optional[str] = None,
        ssh_port: int = 22,
    ) -> None:
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user or ""
        self.ssh_port = ssh_port

    @property
    def is_remote(self) -> bool:
        return bool(self.ssh_host)

    @property
    def label(self) -> str:
        if not self.is_remote:
            return "local"
        user_prefix = f"{self.ssh_user}@" if self.ssh_user else ""
        return f"{user_prefix}{self.ssh_host}:{self.ssh_port}"

    # -- command execution ---------------------------------------------------

    def run_command(self, cmd: str, timeout: int = 30) -> Tuple[int, str]:
        """Run *cmd* and return ``(returncode, combined_output)``.

        On the local machine the command is executed via the shell.
        On a remote host it is wrapped in an ``ssh`` invocation.
        """
        if self.is_remote:
            ssh_cmd: List[str] = [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
                "-p", str(self.ssh_port),
            ]
            if self.ssh_user:
                ssh_cmd += ["-l", self.ssh_user]
            ssh_cmd += [self.ssh_host, cmd]
            full_cmd = ssh_cmd
            use_shell = False
        else:
            full_cmd = cmd  # type: ignore[assignment]
            use_shell = True

        try:
            proc = subprocess.run(
                full_cmd,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (proc.stdout + proc.stderr).strip()
            return proc.returncode, output
        except FileNotFoundError:
            return 1, "ssh client not found on PATH"
        except subprocess.TimeoutExpired:
            return 1, f"Command timed out after {timeout}s"

    # -- file transfer -------------------------------------------------------

    def copy_file_to_server(
        self, local_path: str, remote_dir: str
    ) -> Tuple[bool, str]:
        """Copy *local_path* into *remote_dir*.

        Returns ``(success, message)``.
        """
        if not self.is_remote:
            # Local copy.
            try:
                os.makedirs(remote_dir, exist_ok=True)
                dest = os.path.join(remote_dir, os.path.basename(local_path))
                shutil.copy2(local_path, dest)
                return True, dest
            except OSError as exc:
                return False, str(exc)

        # Remote copy via scp.
        target = (
            f"{self.ssh_user}@{self.ssh_host}:{remote_dir}/"
            if self.ssh_user
            else f"{self.ssh_host}:{remote_dir}/"
        )
        scp_cmd: List[str] = [
            "scp",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-P", str(self.ssh_port),
            local_path,
            target,
        ]
        try:
            proc = subprocess.run(
                scp_cmd, capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                dest = f"{remote_dir}/{os.path.basename(local_path)}"
                return True, dest
            return False, (proc.stdout + proc.stderr).strip()
        except FileNotFoundError:
            return False, "scp client not found on PATH"
        except subprocess.TimeoutExpired:
            return False, "scp timed out"


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------

def detect_tak_install(
    conn: Optional[ServerConnection] = None,
) -> Dict[str, Optional[str]]:
    """Return auto-detected paths for the OpenTAK server.

    The function probes a list of well-known directories (and the
    ``TAK_PATH`` environment variable) for the presence of a TAK
    certificate directory and a configuration file.

    When *conn* is ``None`` or a local connection the check is done
    via ``os.path``.  When *conn* is a remote SSH connection the
    check is done via ``ssh test -d`` / ``test -f`` commands.

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

    use_ssh = conn is not None and conn.is_remote

    for base in candidates:
        if use_ssh:
            rc, _ = conn.run_command(f"test -d {_sh_quote(base)}")
            if rc != 0:
                continue
        else:
            if not os.path.isdir(base):
                continue

        result["tak_dir"] = base

        # --- Certs directory ------------------------------------------------
        certs = base + "/certs"
        if use_ssh:
            rc, _ = conn.run_command(f"test -d {_sh_quote(certs)}")
            if rc == 0:
                result["certs_dir"] = certs
        else:
            if os.path.isdir(certs):
                result["certs_dir"] = certs

        # --- Configuration file ---------------------------------------------
        for cfg_name in _CONFIG_FILENAMES:
            cfg_path = base + "/" + cfg_name
            if use_ssh:
                rc, _ = conn.run_command(f"test -f {_sh_quote(cfg_path)}")
                if rc == 0:
                    result["config_file"] = cfg_path
                    break
            else:
                if os.path.isfile(cfg_path):
                    result["config_file"] = cfg_path
                    break

        # If we found a TAK dir, stop searching further candidates.
        if result["certs_dir"] or result["config_file"]:
            break

    return result


# ---------------------------------------------------------------------------
# Directory verification & search
# ---------------------------------------------------------------------------

def verify_tak_directory(
    path: str,
    conn: Optional[ServerConnection] = None,
) -> List[str]:
    """Verify that *path* looks like a valid TAK installation.

    Returns a list of human-readable status lines.  An empty list is
    never returned – there is always at least a header line.  Lines
    starting with ``✓`` indicate a passed check, ``✗`` a failed check.
    """
    lines: List[str] = [f"Verifying: {path}"]
    use_ssh = conn is not None and conn.is_remote

    def _exists_dir(p: str) -> bool:
        if use_ssh:
            rc, _ = conn.run_command(f"test -d {_sh_quote(p)}")
            return rc == 0
        return os.path.isdir(p)

    def _exists_file(p: str) -> bool:
        if use_ssh:
            rc, _ = conn.run_command(f"test -f {_sh_quote(p)}")
            return rc == 0
        return os.path.isfile(p)

    # Check base directory.
    if _exists_dir(path):
        lines.append(f"  ✓ Directory exists: {path}")
    else:
        lines.append(f"  ✗ Directory NOT found: {path}")
        return lines

    # Check expected sub-directories.
    for subdir in _EXPECTED_TAK_SUBDIRS:
        full = path + "/" + subdir
        if _exists_dir(full):
            lines.append(f"  ✓ Sub-directory exists: {subdir}/")
        else:
            lines.append(f"  ✗ Sub-directory missing: {subdir}/")

    # Check expected config files (at least one should exist).
    found_config = False
    for fname in _EXPECTED_TAK_FILES:
        full = path + "/" + fname
        if _exists_file(full):
            lines.append(f"  ✓ Config file found: {fname}")
            found_config = True
        else:
            lines.append(f"  ✗ Config file missing: {fname}")
    if not found_config:
        lines.append("  ⚠ No config file found – is this a valid TAK installation?")

    return lines


def search_tak_directories(
    conn: Optional[ServerConnection] = None,
) -> List[str]:
    """Search common filesystem locations for TAK installations.

    Returns a (possibly empty) list of directory paths that look like
    they contain a TAK installation (i.e. contain a ``certs/``
    sub-directory **or** a ``CoreConfig.xml``).
    """
    use_ssh = conn is not None and conn.is_remote
    hits: List[str] = []

    # Build a find command that looks for CoreConfig.xml or a certs/ dir
    # under well-known roots (limited depth to keep it fast).
    roots = " ".join(_sh_quote(r) for r in _SEARCH_ROOTS)
    find_cmd = (
        f"find {roots} -maxdepth 4 "
        f"\\( -name CoreConfig.xml -o -name TAKIgniteConfig.xml \\) "
        f"-type f 2>/dev/null"
    )

    if use_ssh:
        rc, output = conn.run_command(find_cmd, timeout=15)
    else:
        try:
            proc = subprocess.run(
                find_cmd, shell=True, capture_output=True, text=True, timeout=15
            )
            rc, output = proc.returncode, (proc.stdout + proc.stderr).strip()
        except subprocess.TimeoutExpired:
            return hits

    if rc == 0 and output:
        for line in output.splitlines():
            line = line.strip()
            if line:
                parent = line.rsplit("/", 1)[0] if "/" in line else line
                if parent not in hits:
                    hits.append(parent)

    return hits


def build_change_summary(
    cert_src: str,
    cert_dest_dir: str,
    remote_addr: str,
    remote_port: str,
    auto_config: bool,
    config_file: Optional[str],
    conn: Optional[ServerConnection] = None,
) -> str:
    """Build a human-readable summary of all planned changes.

    The summary is intended to be shown to the user in a review dialog
    **before** any writes are performed.
    """
    target = conn.label if conn else "local"
    lines: List[str] = [
        "═══════════════════════════════════════════",
        "          REVIEW PLANNED CHANGES",
        "═══════════════════════════════════════════",
        "",
        f"Target:  {target}",
        "",
        "──── 1. Copy trust certificate ────",
        f"  From:  {cert_src}",
        f"  To:    {cert_dest_dir}/{os.path.basename(cert_src)}",
        "",
    ]

    if auto_config and config_file:
        lines += [
            "──── 2. Update configuration ────",
            f"  File:  {config_file}",
            f"  Add federation outgoing entry:",
            f"    address = {remote_addr}",
            f"    port    = {remote_port}",
            f"    enabled = true",
            "",
        ]
    else:
        lines += [
            "──── 2. Configuration ────",
            "  (no automatic config update – manual edit required)",
            "",
        ]

    lines += [
        "──── 3. Post-action ────",
        "  Restart the TAK server service.",
        "",
        "═══════════════════════════════════════════",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shell quoting helper
# ---------------------------------------------------------------------------

def _sh_quote(s: str) -> str:
    """Minimally quote *s* for safe use in a POSIX shell command."""
    # We wrap in single quotes and escape embedded single quotes.
    return "'" + s.replace("'", "'\\''") + "'"


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
