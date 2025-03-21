import os
import subprocess
import requests
from flask import Flask, request, render_template_string, jsonify
import serial.tools.list_ports
import webbrowser
from threading import Timer
from packaging import version  # Used to compare version strings properly

app = Flask(__name__)

# GitHub Repo Info
GITHUB_REPO = "farmrobo-dev/FR_Firmware_Uploader"
FIRMWARE_FOLDER = "bin"
LOCAL_VERSION_FILE = os.path.join(FIRMWARE_FOLDER, "version.txt")

# Template (HTML code, unchanged for now)
TEMPLATE = """
<!doctype html>
<html>
    <head>
        <title>FR Firmware Uploader</title>
        <style>
            /* CSS styles for the layout */
            body {
                font-family: Arial, sans-serif;
                background-color: #ffd700;
                margin: 0;
                padding: 20px;
            }

            h1 {
                font-size: 36px;  /* Larger title font */
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }

            h2 {
                font-size: 28px;
                text-align: center;
                color: #333;
                margin-top: 20px;
            }

            h3 {
                font-size: 20px;
                margin-top: 20px;
                color: #555;
            }

            p, button {
                font-size: 16px;
                color: #555;
                text-align: center;
            }

            #statusMessage {
                font-size: 22px; /* Larger font for status messages */
                font-weight: bold;
                color: #d9534f;
                text-align: center;
                margin-top: 20px;
            }

            button {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                margin: 10px;
                cursor: pointer;
                border-radius: 5px;
            }

            button:hover {
                background-color: #0056b3;
            }

            #latestVersionMessage {
                font-size: 18px;
                color: #28a745;
                margin-top: 10px;
                text-align: center;
            }

            select {
                padding: 10px;
                margin-top: 10px;
                font-size: 16px;
                width: 250px;
                display: block;
                margin: 20px auto;
            }

            form {
                text-align: center;
            }

            .container {
                width: 80%;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }

            .checkbox-container {
                text-align: center;
                margin-top: 20px;
            }
        </style>
        <script>
            // JavaScript functions to handle form submission and interactions
            function submitForm(e) {
                e.preventDefault();
                const form = e.target;
                const statusMessage = document.getElementById('statusMessage');
                statusMessage.innerText = form.name === 'uploadForm' ? 'Uploading...' : 'Checking ports...';

                const method = form.method.toUpperCase();
                let url = form.action;
                let options = { method: method, headers: {} };

                if (method === "POST") {
                    const formData = new FormData(form);
                    options.body = formData;
                }

                fetch(url, options)
                    .then(response => response.json())
                    .then(data => statusMessage.innerText = data.message)
                    .catch(error => {
                        console.error('Fetch error:', error);
                        statusMessage.innerText = 'An error occurred.';
                    });
            }

            function checkComPortSelected() {
                // Always enable the "Upload Latest Firmware" button
                document.getElementById('uploadLatestButton').disabled = false;
            }

            function checkForUpdates() {
                fetch('/check-update')
                    .then(response => response.json())
                    .then(data => {
                        if (data.update_available) {
                            document.getElementById('statusMessage').innerText = `New firmware available: ${data.latest_version}.`;
                            document.getElementById('uploadLatestButton').innerText = `Upload ${data.latest_version}`;
                            document.getElementById('latestVersionMessage').innerText = `Latest release: ${data.latest_version}`;
                        } else {
                            document.getElementById('statusMessage').innerText = data.message;
                        }
                    });
            }

            function uploadLatestRelease() {
                fetch('/upload-latest-release')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('statusMessage').innerText = data.message;
                    });
            }

            function downloadLatestRelease() {
                fetch('/download-latest-release')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('statusMessage').innerText = data.message;
                    });
            }

            document.addEventListener('DOMContentLoaded', checkComPortSelected);
        </script>
    </head>
    <body onload="checkComPortSelected();">
        <div class="container">
            <h1>FR Firmware Uploader</h1>
            
            <div>
                <h2>Current Firmware Version: <span id="firmwareVersion">{{ firmware_version }}</span></h2>

                <!-- Check for Latest Firmware Update and Download -->
                <button onclick="checkForUpdates()">Check for Latest Firmware Update</button>
                <button onclick="downloadLatestRelease()" style="margin-left: 20px;">Download Latest Release</button>
                <p id="latestVersionMessage"></p>
            </div>

            <!-- External Temp Sensor Checkbox -->
            <div class="checkbox-container">
                <h3>Has External Temp Sensor?</h3>
                <label>
                    <input type="checkbox" id="externalTempSensor" name="externalTempSensor"> Yes
                </label>
            </div>

            <!-- COM Port and Upload -->
            <h3>Select COM Port and Upload</h3>
            <form name="uploadForm" action="/upload" method="post" onsubmit="submitForm(event);">
                <select id="comPortSelect" name="com_port" onchange="checkComPortSelected();">
                    <option value="">Select COM Port</option>
                    {% for port in ports %}
                    <option value="{{ port.device }}">{{ port.device }}</option>
                    {% endfor %}
                </select>
                <input type="hidden" id="hasExternalTempSensor" name="has_external_temp_sensor" value="0">
            </form>
            <form name="refreshPortsForm" action="/ports" method="get" onsubmit="submitForm(event);">
                <input type="submit" value="Check Ports">
            </form>

            <!-- Upload Latest Firmware -->
            <h3>Upload Latest Firmware</h3>
            <button id="uploadLatestButton" onclick="uploadLatestRelease()" style="margin-left: 20px;">Upload Latest Firmware</button>
            
            <p id="statusMessage"></p>
        </div>

        <script>
            // Listen for changes in the checkbox and update the hidden form input
            document.getElementById('externalTempSensor').addEventListener('change', function() {
                document.getElementById('hasExternalTempSensor').value = this.checked ? '1' : '0';
            });
        </script>
      <script>
    function downloadLatestRelease() {
        const statusMessage = document.getElementById('statusMessage');
        statusMessage.innerText = 'Downloading...';  // Display 'Downloading...' when button is clicked

        fetch('/download-latest-release')
            .then(response => response.json())
            .then(data => {
                statusMessage.innerText = data.message;  // Show the final message after the download is finished
            })
            .catch(error => {
                console.error('Fetch error:', error);
                statusMessage.innerText = 'An error occurred during the download.';
            });
    }
</script>

    </body>
</html>
"""

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

# Get the local firmware version
def get_local_version():
    if os.path.exists(LOCAL_VERSION_FILE):
        with open(LOCAL_VERSION_FILE, "r") as f:
            return f.read().strip()
    return "v1.0.0"

# Get the latest firmware version from GitHub
def get_latest_firmware_version():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        release_data = response.json()
        return release_data.get("tag_name", "v1.0.0"), release_data.get("assets", [])
    except requests.RequestException:
        return "v1.0.0", []  # Return a default value if GitHub is unreachable

def download_firmware(assets):
    download_folder = FIRMWARE_FOLDER  # Change to bin folder
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)  # Ensure the folder exists

    for asset in assets:
        asset_url = asset["browser_download_url"]
        file_name = os.path.join(download_folder, asset["name"])
        try:
            response = requests.get(asset_url, timeout=10)
            response.raise_for_status()
            with open(file_name, "wb") as f:
                f.write(response.content)
            print(f"Downloaded {file_name}")  # Print the download confirmation
        except requests.RequestException:
            print(f"Failed to download {asset_url}")  # Log an error if download fails

@app.route('/')
def home():
    ports = serial.tools.list_ports.comports()
    local_version = get_local_version()
    return render_template_string(TEMPLATE, ports=ports, firmware_version=local_version)

@app.route('/ports', methods=['GET'])
def list_ports():
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return jsonify(ports=ports)

@app.route('/check-update', methods=['GET'])
def check_update():
    latest_version, assets = get_latest_firmware_version()
    local_version = get_local_version()

    if latest_version == "v0.0.0":
        return jsonify(update_available=False, latest_version=local_version, message="No internet connection. Skipping update.")

    # Use packaging.version for version comparison
    if version.parse(latest_version) > version.parse(local_version):
        return jsonify(update_available=True, latest_version=latest_version)
    
    return jsonify(update_available=False, latest_version=local_version, message="Firmware is up to date.")

@app.route('/download-latest-release', methods=['GET'])
def download_latest_release():
    # Send initial message
    download_status = {
        'message': 'Downloading...'
    }
    
    # Get the latest firmware version and assets
    latest_version, assets = get_latest_firmware_version()

    if latest_version == "v0.0.0":
        return jsonify(message="No internet connection. Cannot download firmware.")

    # Download the firmware files
    download_firmware(assets)
    
    # Once download is done, update the status message
    with open(LOCAL_VERSION_FILE, "w") as f:
        f.write(latest_version)

    # Return final message
    download_status['message'] = 'Downloaded Successfully.'
    return jsonify(download_status)

@app.route('/upload-latest-release', methods=['GET'])
def upload_latest_release():
    latest_version, assets = get_latest_firmware_version()
    local_version = get_local_version()

    if latest_version == "v0.0.0":
        return jsonify(message="No internet connection. Cannot update firmware.")

    # Use packaging.version for version comparison
    # if version.parse(latest_version) > version.parse(local_version):
        # Download the firmware files (both)
        # download_firmware(assets)

    # Determine which firmware file to use based on the checkbox state
    has_external_temp_sensor = request.args.get("has_external_temp_sensor", "0") == "1"
    firmware_file = "FR_R1_Firmware_external.ino.bin" if has_external_temp_sensor else "FR_R1_Firmware.ino.bin"


    # Build the upload command for the latest firmware release
    upload_command = f"win\\massStorageCopy.bat -I bin\\{firmware_file} -O NODE_F446ZE"

    try:
        subprocess.run(upload_command, shell=True, check=True)
        return jsonify(message=f"Firmware {latest_version} uploaded successfully.")
    except subprocess.CalledProcessError:
        return jsonify(message="Upload failed."), 500
    
    # return jsonify(message="Firmware is already up to date.")

if __name__ == '__main__':
    Timer(1, open_browser).start()  # Open browser after 1 second
    app.run(debug=False)  # Set debug to False for production

## pyinstaller --onefile --hide-console minimize-early .\FR_Firmware_Uploader.py
