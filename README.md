# FR Firmware Uploader

## Overview

**FR Firmware Uploader** is a tool designed to simplify the process of uploading firmware to embedded devices. It provides a user-friendly interface and automates many of the steps required for firmware deployment, making it easier for developers and engineers to manage firmware updates.

## Features

- Upload firmware binaries to supported devices
- Organize and manage multiple firmware versions
- Automated build and deployment process
- Support for various device types (e.g., CAN BMS, analog temp test, etc.)
- Clean build and distribution directories

## Project Structure

```
FR_Firmware_Uploader/
├── .gitignore
├── build/
│   └── frm/
│       ├── EXE-00.toc
│       ├── Analysis-00.toc
│       ├── PKG-00.toc
│       └── ...
├── dist/
│   └── bin/
│       ├── CAN_BMS.ino.bin
│       ├── analog_temp_test.ino.bin
│       └── ...
└── ...
```

- **.gitignore**: Specifies files and directories to be ignored by Git (e.g., build artifacts, binaries).
- **build/**: Contains intermediate build files and metadata generated during the build process.
- **dist/bin/**: Stores the compiled firmware binaries ready for upload.

## Getting Started

### Prerequisites

- Python 3.13 or later
- Required Python packages (see `requirements.txt` if available)
- Supported embedded device(s)

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/FR_Firmware_Uploader.git
    cd FR_Firmware_Uploader
    ```

2. (Optional) Create and activate a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

### Usage

1. Place your firmware binary files in the `dist/bin/` directory.
2. Run the uploader tool (replace with the actual command or script name):
    ```sh
    python uploader.py --file dist/bin/your_firmware.bin --device <device_port>
    ```
3. Follow on-screen instructions to complete the upload.

### Cleaning Build Artifacts

To remove build artifacts and binaries, use:
```sh
rm -rf build/ dist/
```
Or use the provided clean script if available.

## Contributing

Contributions are welcome! Please open issues or submit pull requests for bug fixes, new features, or improvements.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- Python community and open-source contributors
- Device manufacturers for documentation and support
