from flask import Flask, request, render_template_string, jsonify
import serial.tools.list_ports
import subprocess

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
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

function updateComPorts() {
    const comPortSelect = document.getElementById('comPortSelect');
    fetch('/ports')
        .then(response => response.json())
        .then(data => {
            comPortSelect.innerHTML = '<option value="">Select COM Port</option>';
            data.ports.forEach(port => comPortSelect.add(new Option(port, port)));
        })
        .catch(error => console.error('Error updating COM ports:', error));
}

function checkComPortSelected() {
    document.getElementById('uploadButton').disabled = document.getElementById('comPortSelect').value === "";
}

document.addEventListener('DOMContentLoaded', checkComPortSelected);
        </script>
    </head>
    <body onload="checkComPortSelected();">
        <h2>FR Firmware Uploader</h2>
        <h2>Has External Temp Sensor?</h2>
        <label>
            <input type="checkbox" id="externalTempSensor"> Yes
        </label>
        <h2>Select COM Port and Upload</h2>
        <form name="uploadForm" action="/upload" method="post" onsubmit="submitForm(event);">
            <select id="comPortSelect" name="com_port" onchange="checkComPortSelected();">
                <option value="">Select COM Port</option>
                {% for port in ports %}
                <option value="{{ port.device }}">{{ port.device }}</option>
                {% endfor %}
            </select>
            <input type="hidden" id="hasExternalTempSensor" name="has_external_temp_sensor" value="0">
            <input type="submit" id="uploadButton" value="Upload">
        </form>
        <form name="refreshPortsForm" action="/ports" method="get" onsubmit="submitForm(event);">
            <input type="submit" value="Check Ports">
        </form>
        <p id="statusMessage"></p>
        <script>
            document.getElementById('externalTempSensor').addEventListener('change', function() {
                document.getElementById('hasExternalTempSensor').value = this.checked ? '1' : '0';
            });
        </script>
    </body>
</html>
"""

@app.route('/', methods=['GET'])
def home():
    ports = serial.tools.list_ports.comports()
    return render_template_string(TEMPLATE, ports=ports)

@app.route('/ports', methods=['GET'])
def list_ports():
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return jsonify(ports=ports)

@app.route('/upload', methods=['POST'])
def upload():
    com_port = request.form.get('com_port')
    has_external_temp_sensor = request.form.get('has_external_temp_sensor') == '1'
    
    if not com_port:
        return jsonify(message="No COM port selected."), 400

    upload_command = "win\massStorageCopy.bat -I "
    upload_command += "bin\FR_R1_Firmware_external.ino.bin" if has_external_temp_sensor else "bin\FR_R1_Firmware.ino.bin"
    upload_command += " -O NODE_F446ZE"
    # print(upload_command)
    try:
        subprocess.run(upload_command, shell=True, check=True)
        return jsonify(message="Upload completed successfully.")
    except subprocess.CalledProcessError:
        return jsonify(message="Upload failed."), 500

if __name__ == '__main__':
    app.run(debug=True)

# pyinstaller --onefile .\FR_Firmware_Uploader.py