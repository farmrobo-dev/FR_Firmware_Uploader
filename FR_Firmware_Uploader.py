from flask import Flask, request, render_template_string, jsonify
import serial.tools.list_ports
import subprocess
import webbrowser
import os
import requests
from threading import Timer

app = Flask(__name__)

# GitHub Repo Info
GITHUB_REPO = "farmrobo-dev/FR_Firmware_Uploader"
FIRMWARE_FOLDER = "bin"
LOCAL_VERSION_FILE = os.path.join(FIRMWARE_FOLDER, "version.txt")

TEMPLATE = """ 
<!DOCTYPE html> 
<html>
<head>
    <title>FR Firmware Uploader</title>
    <script>
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

function checkForUpdates() {
    fetch('/check-update')
        .then(response => response.json())
        .then(data => {
            if (data.update_available) {
                document.getElementById('statusMessage').innerText = `New firmware available: ${data.latest_version}. Updating...`;
                fetch('/update-firmware')
                    .then(response => response.json())
                    .then(result => document.getElementById('statusMessage').innerText = result.message);
            } else {
                document.getElementById('statusMessage').innerText = data.message;
            }
        });
}
</script>
</head>
<body>
    <h2>FR Firmware Uploader</h2>
    <h3>Firmware Version: <span id="firmwareVersion">{{ firmware_version }}</span></h3>
    <button onclick="checkForUpdates()">Check for Updates</button>
    <h2>Select COM Port and Upload</h2>
    <form name="uploadForm" action="/upload" method="post" onsubmit="submitForm(event);">
        <select id="comPortSelect" name="com_port">
            <option value="">Select COM Port</option>
            {% for port in ports %}
            <option value="{{ port.device }}">{{ port.device }}</option>
            {% endfor %}
        </select>
        <input type="submit" value="Upload">
    </form>
    <p id="statusMessage"></p>
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
    return "v0.0.0"

# Get the latest firmware version from GitHub
def get_latest_firmware_version():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        release_data = response.json()
        return release_data.get("tag_name", "v0.0.0"), release_data.get("assets", [])
    except requests.RequestException:
        return "v0.0.0", []  # Return a default value if GitHub is unreachable

# Download the new firmware
def download_firmware(assets):
    if not os.path.exists(FIRMWARE_FOLDER):
        os.makedirs(FIRMWARE_FOLDER)  # Ensure bin/ folder exists

    for asset in assets:
        asset_url = asset["browser_download_url"]
        file_name = os.path.join(FIRMWARE_FOLDER, asset["name"])
        try:
            response = requests.get(asset_url, timeout=10)
            response.raise_for_status()
            with open(file_name, "wb") as f:
                f.write(response.content)
        except requests.RequestException:
            print(f"Failed to download {asset_url}")  # Log an error if download fails

@app.route('/')
def home():
    ports = serial.tools.list_ports.comports()
    local_version = get_local_version()
    return render_template_string(TEMPLATE, ports=ports, firmware_version=local_version)

@app.route('/check-update', methods=['GET'])
def check_update():
    latest_version, assets = get_latest_firmware_version()
    local_version = get_local_version()

    if latest_version == "v0.0.0":
        return jsonify(update_available=False, latest_version=local_version, message="No internet connection. Skipping update.")

    if latest_version > local_version:
        return jsonify(update_available=True, latest_version=latest_version)
    return jsonify(update_available=False, latest_version=local_version, message="Firmware is up to date.")

@app.route('/update-firmware', methods=['GET'])
def update_firmware():
    latest_version, assets = get_latest_firmware_version()
    local_version = get_local_version()

    if latest_version == "v0.0.0":
        return jsonify(message="No internet connection. Cannot update firmware.")

    if latest_version > local_version:
        download_firmware(assets)
        with open(LOCAL_VERSION_FILE, "w") as f:
            f.write(latest_version)
        return jsonify(message="Firmware updated successfully.")
    
    return jsonify(message="Firmware is already up to date.")

@app.route('/upload', methods=['POST'])
def upload():
    com_port = request.form.get('com_port')
    
    if not com_port:
        return jsonify(message="No COM port selected."), 400

    upload_command = "win\\massStorageCopy.bat -I bin\\FR_R1_Firmware.ino.bin -O NODE_F446ZE"
    try:
        subprocess.run(upload_command, shell=True, check=True)
        return jsonify(message="Upload completed successfully.")
    except subprocess.CalledProcessError:
        return jsonify(message="Upload failed."), 500

if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=False)
