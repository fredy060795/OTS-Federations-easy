# OTS-Federations-easy

A simple graphical tool to set up TAK Federation between two OpenTAK servers.

## Features

- **Auto-detection** – the tool automatically finds the local OpenTAK server
  installation (`/opt/tak`, `~/tak`, or a custom `TAK_PATH` environment
  variable) and pre-fills the certificate directory and configuration file
  paths.
- **Certificate management** – browse for a `.pem` trust certificate and copy
  it into the TAK `certs/` directory with one click.
- **Auto-configuration** – optionally update `CoreConfig.xml` with a
  `<federationOutgoing>` entry so the user does not have to edit XML manually.
- **Validation** – all required fields are checked before any changes are made.

## Quick Start

```bash
python3 src/OTS_Federation_GUI.py
```

1. The tool auto-detects your OpenTAK server paths on startup.
2. Enter the **Remote Server Address** and **Port**.
3. Browse for the partner server's **trust certificate** (`.pem`).
4. Click **Save Certificate & Configure**.
5. Restart the TAK server.

## Requirements

- Python 3.6+
- Tkinter (`sudo apt-get install python3-tk` on Debian/Ubuntu)

## Environment Variables

| Variable   | Description                                      |
|------------|--------------------------------------------------|
| `TAK_PATH` | Override the auto-detected TAK installation path |

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```