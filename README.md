# OTS-Federations-easy

A simple tool to set up TAK Federation between two
[OpenTAK](https://opentakserver.io/) servers.
Available as a **graphical (Tkinter) interface** and as a **pure terminal /
CLI interface** that works over SSH and on headless servers.
Supports **local** and **SSH** operation with **directory verification**,
**search**, and **manual review before changes**.

## Features

- **Terminal / CLI mode** – run the tool entirely in the terminal via
  `./start.sh`.  Works over SSH, on headless servers, and in any
  console-only environment — no graphical display required.
- **GUI mode** – optional graphical interface via Tkinter
  (`python3 src/OTS_Federation_GUI.py`).
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
  config) is shown for approval before anything is written.
- **Certificate management** – select a `.pem` trust certificate and copy
  it into the TAK `certs/` directory.
- **Auto-configuration** – optionally update `CoreConfig.xml` with a
  `<federationOutgoing>` entry so the user does not have to edit XML manually.
- **Validation** – all required fields are checked before any changes are made.

## Requirements

- Python 3.6+
- For the **GUI**: Tkinter (`sudo apt-get install python3-tk` on Debian/Ubuntu)
- For the **CLI / terminal mode**: no extra dependencies — only the Python
  standard library is used.
- For SSH mode: `ssh` and `scp` on PATH with key-based authentication

## Installation

```bash
git clone https://github.com/fredy060795/OTS-Federations-easy.git
cd OTS-Federations-easy
```

## Quick Start

### Terminal / CLI (recommended for SSH & headless servers)

```bash
./start.sh
```

Or directly:

```bash
python3 src/OTS_Federation_CLI.py
```

The terminal interface guides you step by step:

1. Select **Connection Mode** (Local or SSH).
2. The tool auto-detects your OpenTAK server paths (with search & verify
   options if auto-detect doesn't find it).
3. Enter the **Remote Server Address** and **Port**.
4. Enter the path to the partner server's **trust certificate** (`.pem`).
5. Review the planned changes and confirm.
6. Restart the TAK server.

### GUI (requires Tkinter)

```bash
python3 src/OTS_Federation_GUI.py
```

## Environment Variables

| Variable   | Description                                      |
|------------|--------------------------------------------------|
| `TAK_PATH` | Override the auto-detected TAK installation path |

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

This project is released under the [MIT License](https://opensource.org/licenses/MIT).
