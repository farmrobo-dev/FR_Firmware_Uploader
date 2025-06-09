# FR Firmware Uploader

## Overview

**FR Firmware Uploader** is a cross-platform tool for managing and uploading firmware to FarmRobo and similar embedded devices. It provides a graphical interface for selecting firmware versions, downloading the latest releases from GitHub, and uploading firmware to devices via serial (COM) ports. The tool is designed to simplify firmware management for developers, testers, and field engineers.

---

## Features

- **Download Latest Firmware:** Fetches the latest firmware release directly from the official GitHub repository.
- **Version Management:** Displays both the current local firmware version and the latest available version.
- **Device Selection:** Choose device configuration (R1-TEMP, R1-TOOLS, R1-ACTUATOR) and COM port for upload.
- **Custom Firmware Upload:** Supports uploading user-selected firmware binaries.
- **Serial Monitor:** Built-in serial monitor with selectable baud rate, line ending, and view mode (text/hex), plus timestamping.
- **Logging:** Real-time log output for all actions and errors.
- **Multi-Tab UI:** Separate tabs for standard firmware upload and custom firmware upload.

---

## Folder Structure

```
FR_Firmware_Uploader/
├── bin/                  # Downloaded and local firmware binaries
│   ├── R1-IT-CAN-BTS.bin
│   └── ...               # Other firmware files
├── win/
│   └── massStorageCopy.bat   # Batch script for uploading firmware (Windows)
├── frm.py                # Main application (Tkinter GUI)
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── ...                    # Other files (build scripts, configs, etc.)
```

---

## Getting Started

### Prerequisites

- **Python 3.8+** (Tested on Python 3.10+)
- **pip** (Python package manager)
- **Windows** (batch upload script is Windows-specific, but core logic is cross-platform)
- **GitHub access** (for downloading latest firmware releases)

### Installation

1. **Clone the repository:**
    ```sh
    git clone https://github.com/farmrobo-dev/FR_Firmware_Uploader.git
    cd FR_Firmware_Uploader
    ```

2. **(OPTIONAL) Create a virtual environment:**
    ```sh
    python -m venv venv
    venv\Scripts\activate  # On Windows
    ```

3. **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

### Usage

1. **Run the application:**
    ```sh
    python frm.py
    ```

2. **Main Tab:**
    - Click **Check for Updates** to see if a new firmware is available.
    - Click **Download Latest Release** to fetch the newest firmware from GitHub.
    - Select device configuration and COM port.
    - Click **Upload Selected Firmware** to flash the device.

3. **Custom Upload Tab:**
    - Browse and select any `.bin` firmware file.
    - Select COM port and upload.

4. **Serial Monitor:**
    - Use the built-in monitor to view device output, change baud rate, and toggle timestamping.

---

## Notes

- **Firmware Folder:** Downloaded firmware is stored in the `bin/` directory.
- **Batch Script:** Firmware upload uses `win/massStorageCopy.bat` (ensure this script exists and is executable).
- **COM Ports:** The tool auto-detects available serial ports; refresh as needed.
- **Logging:** All actions and errors are logged in the GUI for troubleshooting.

---

## Contributing

Pull requests and issues are welcome! Please follow standard Python style and document any new features.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Tkinter](https://docs.python.org/3/library/tkinter.html) for GUI
- [PySerial](https://pyserial.readthedocs.io/) for serial communication
- [Requests](https://docs.python-requests.org/) for GitHub API access
- FarmRobo community and contributors
