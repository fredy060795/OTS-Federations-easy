# OTS-Federations-easy

A simple graphical tool that helps configure **TAK Federation** between two
[OpenTAK](https://opentakserver.io/) servers. It lets you specify the remote
server address and port, browse for a PEM trust certificate, and copy that
certificate into the correct local directory so the TAK server can use it for
federation.

## Features

- Enter the remote server address and federation port
- Browse for a `.pem` trust certificate and save it to the local TAK
  certificate directory (`~/tak/certs/` by default)
- Optional fields for local server name, admin username, and admin password
  (reserved for future extensions)
- Input validation with clear error messages
- Overwrite confirmation when a certificate file already exists

## Requirements

- **Python 3.6+**
- **Tkinter** – ships with the standard Python distribution on Windows and
  macOS. On Debian/Ubuntu install it with:

  ```bash
  sudo apt-get install python3-tk
  ```

## Installation

```bash
git clone https://github.com/fredy060795/OTS-Federations-easy.git
cd OTS-Federations-easy
```

No additional Python packages are required – only the standard library is used.

## Usage

```bash
python3 src/OTS_Federation_GUI.py
```

1. **Remote Server** – enter the address (IP or hostname) and the federation
   port (default `8089`) of the remote TAK server you want to federate with.
2. **Trust Certificate** – click *Browse…* to select the remote server's PEM
   certificate file, then confirm or change the local directory where the
   certificate will be saved.
3. Click **Save Certificate & Configure**. The tool validates your inputs,
   copies the certificate, and shows the next manual steps.

## server.xml Configuration Example

After running the tool, open your TAK server's `server.xml` and add a
`<Federation>` block similar to the following:

```xml
<Federation>
    <remoteHost>192.168.1.100</remoteHost>
    <remotePort>8089</remotePort>
    <caFile>/home/user/tak/certs/remote-server.pem</caFile>
</Federation>
```

Replace the values with the actual remote address, port, and the certificate
path shown by the tool. Then restart the TAK server service for the changes to
take effect.

## License

This project is released under the [MIT License](https://opensource.org/licenses/MIT).