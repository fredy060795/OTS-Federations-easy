# OTS-Federations-easy

A simple graphical tool to set up TAK Federation between two OpenTAK servers.
Supports **local** and **SSH** operation with **directory verification**,
**search**, and **manual review before changes**.

## Features

- **Local & SSH mode** – work directly on the TAK server or connect to a
  remote server over SSH (key-based / agent-based auth).
- **Auto-detection** – the tool automatically finds the local OpenTAK server
  installation (`/opt/tak`, `~/tak`, or a custom `TAK_PATH` environment
  variable) and pre-fills the certificate directory and configuration file
  paths.
- **Directory search** – scan the filesystem for TAK installations when
  auto-detection does not find them.
- **Directory verification** – verify that a directory is a valid OpenTAK
  installation (checks for `certs/`, `CoreConfig.xml`, etc.).
- **Review before changes** – every planned action (copy certificate, update
  config) is shown in a review dialog for approval before anything is written.
- **Certificate management** – browse for a `.pem` trust certificate and copy
  it into the TAK `certs/` directory with one click.
- **Auto-configuration** – optionally update `CoreConfig.xml` with a
  `<federationOutgoing>` entry so the user does not have to edit XML manually.
- **Validation** – all required fields are checked before any changes are made.

## Quick Start

```bash
python3 src/OTS_Federation_GUI.py
```

1. Select **Connection Mode** (Local or SSH).
2. The tool auto-detects your OpenTAK server paths on startup (use
   **Search…** if auto-detect doesn't find it, **Verify** to check a
   detected directory).
3. Enter the **Remote Server Address** and **Port**.
4. Browse for the partner server's **trust certificate** (`.pem`).
5. Click **Review & Apply…** – review the planned changes and confirm.
6. Restart the TAK server.

## Requirements

- Python 3.6+
- Tkinter (`sudo apt-get install python3-tk` on Debian/Ubuntu)
- For SSH mode: `ssh` and `scp` on PATH with key-based authentication

## Environment Variables

| Variable   | Description                                      |
|------------|--------------------------------------------------|
| `TAK_PATH` | Override the auto-detected TAK installation path |

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```