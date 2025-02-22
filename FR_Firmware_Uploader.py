from flask import Flask, request, render_template_string, jsonify
import serial.tools.list_ports
import subprocess
import re

app = Flask(__name__)

debug_line_number = 22
robot_ID_line_number = 12

HAS_PTO_DAC_line_number = 26
IS_MOTORS_REVERSED_line_number = 24

TEMPLATE = """
<!doctype html>
<html>
	<head>
		<title>FR Firmware Uploader</title>
		<script>
function submitForm(e) {
    e.preventDefault(); // Prevent the default form submission
    const form = e.target;
    const statusMessage = document.getElementById('statusMessage');

    // Handling the form based on its name attribute
    if (form.name === 'uploadForm') {
        // Update message for uploading
        statusMessage.innerText = 'Compiling and uploading...';
    } else if (form.name === 'refreshPortsForm') {
        // Update message for checking ports
        statusMessage.innerText = 'Checking ports...';
    }

    // Determine if it's a GET or POST request
    const method = form.method.toUpperCase();
    let url = form.action;
    let options = {
        method: method,
        headers: {},
    };

    // Add form data for POST requests
    if (method === "POST") {
        const formData = new FormData(form);
        options.body = formData;
    }

    // Make the fetch request
    fetch(url, options)
        .then(response => response.json())
        .then(data => {
            // Update the status message with the response
            statusMessage.innerText = data.message;

            // Additional actions based on form, for example, refreshing COM ports
            if (form.name === 'refreshPortsForm') {
                updateComPorts();
            }
        })
        .catch(error => {
            console.error('Fetch error:', error);
            statusMessage.innerText = 'An error occurred.';
        });
}

// Update COM Ports list without reloading the page
function updateComPorts() {
    const comPortSelect = document.getElementById('comPortSelect');
    fetch('/ports')
        .then(response => response.json())
        .then(data => {
            comPortSelect.innerHTML = '<option value="">Select COM Port</option>';
            data.ports.forEach(port => {
                const option = new Option(port, port);
                comPortSelect.add(option);
            });
        })
        .catch(error => console.error('Error updating COM ports:', error));
}

// Initial setup for the COM port selection
function checkComPortSelected() {
    const uploadButton = document.getElementById('uploadButton');
    const comPortSelect = document.getElementById('comPortSelect');
    uploadButton.disabled = comPortSelect.value === "";
}

function toggleDebug() {
    const isChecked = document.getElementById('debugToggle').checked;
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.innerText = 'Updating debug mode...';

    fetch('/toggle_debug', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ debug: isChecked }),
    })
    .then(response => response.json())
    .then(data => {
        statusMessage.innerText = data.message;
    })
    .catch(error => {
        console.error('Fetch error:', error);
        statusMessage.innerText = 'An error occurred while updating debug mode.';
    });
}

function toggleSetting(toggleId, endpoint) {
    const isChecked = document.getElementById(toggleId).checked;
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.innerText = `Updating ${toggleId}...`;

    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled: isChecked }),
    })
    .then(response => response.json())
    .then(data => {
        statusMessage.innerText = data.message;
    })
    .catch(error => {
        console.error('Fetch error:', error);
        statusMessage.innerText = 'An error occurred while updating.';
    });
}


document.addEventListener('DOMContentLoaded', function() {
    // Setup initial state or actions on DOM ready, if necessary
    checkComPortSelected();
});
</script>

	</head>
	<body onload="checkComPortSelected();">
		<h2>Current BOT ID</h2>
		<p id="currentRobotId">{{ current_robot_id if current_robot_id else "Not set" }}</p>
		<h2>Enter new BOT ID to be added to code</h2>
		<form action="/" method="post" onsubmit="submitForm(event);">
			<input type="text" name="number" required>
			<input type="submit" value="OK">
			{% if update_msg %}
			<p>{{ update_msg }}</p>
			{% endif %}
		</form>
        <h2>Debug Mode</h2>
        <label>
            <input type="checkbox" id="debugToggle"> Debug
        </label>
        <button onclick="toggleDebug()">Apply</button>

        <h2>This bot has DAC?</h2> 
        <label>
            <input type="checkbox" id="hasPtoDacToggle"> Yes this bot has DAC
        </label>
        <button onclick="toggleSetting('hasPtoDacToggle', '/toggle_has_pto_dac')">Apply</button>

        <h2>Is Motors Reversed?</h2>
        <label>
            <input type="checkbox" id="isMotorsReversedToggle"> Yes Motors Reversed
        </label>
        <button onclick="toggleSetting('isMotorsReversedToggle', '/toggle_is_motors_reversed')">Apply</button>

		<h2>Select COM Port and Upload</h2>
		<form name="uploadForm" action="/" method="post" onsubmit="submitForm(event);">
            <select id="comPortSelect" name="com_port" onchange="checkComPortSelected();">
                <option value="">Select COM Port</option>
                {% for port in ports %}
                <option value="{{ port.device }}">{{ port.device }}</option>
                {% endfor %}
            </select>
            <!-- Hidden input to indicate the 'upload' action -->
            <input type="hidden" name="upload" value="1">
            <input type="submit" id="uploadButton" name="submit" value="Upload">
        </form>
		<form name="refreshPortsForm" action="/ports" method="get" onsubmit="submitForm(event);">
			<input type="submit" value="Check Ports">
		</form>
		<p id="statusMessage"></p>
	</body>
</html>
"""

def get_current_robot_id(file_path):
    try:
        with open(file_path, "r") as file:
            lines = file.readlines()
            if len(lines) >= robot_ID_line_number:
                robot_id_line = lines[robot_ID_line_number-1]  # Assuming the ID is on the 14th line
                match = re.search(r'String ROBOT_ID = "(.*?)";', robot_id_line)
                if match:
                    return match.group(1)  # Return the ID as a string
    except FileNotFoundError:
        print("File not found.")
    return None

def update_robot_id_in_code(new_id):
    file_path = "hustler_stm32_master_v1\hustler_stm32_master_v1.ino"  # Adjust the file name/path as needed
    with open(file_path, "r") as file:
        lines = file.readlines()
    
    if len(lines) >= robot_ID_line_number:  # Check if there are at least 14 lines
        lines[robot_ID_line_number-1] = f"String ROBOT_ID = " + f"\"{new_id}\""+ ";\n"  # Update the 14th line (index starts at 0)

    with open(file_path, "w") as file:
        file.writelines(lines)

@app.route('/', methods=['GET', 'POST'])
def home():
    ports = serial.tools.list_ports.comports()
    file_path = "hustler_stm32_master_v1\hustler_stm32_master_v1.ino"
    current_robot_id = get_current_robot_id(file_path)
    
    if request.method == 'POST':
        if 'number' in request.form:
            number = request.form['number']
            update_robot_id_in_code(number)
            return jsonify(message="BOT ID added to the code.")
        
        elif 'upload' in request.form and request.form['com_port']:
            com_port = request.form['com_port']
            # Adjust the paths and parameters as needed for your setup
            compile_command = "arduino-cli.exe compile -p NODE_F446ZE --fqbn STMicroelectronics:stm32:Nucleo_144:pnum=NUCLEO_F446ZE,xserial=generic,usb=none,xusb=FS,opt=osstd,dbg=none,rtlib=nano,upload_method=MassStorage hustler_stm32_master_v1" 
            upload_command = "arduino-cli.exe upload -p NODE_F446ZE --fqbn STMicroelectronics:stm32:Nucleo_144:pnum=NUCLEO_F446ZE,xserial=generic,usb=none,xusb=FS,opt=osstd,dbg=none,rtlib=nano,upload_method=MassStorage hustler_stm32_master_v1"
            
            
            # Run compile command
            compile_process = subprocess.run(compile_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if compile_process.returncode != 0:
                return jsonify(message="Compile failed.")
            else: 
            # Run upload command
                upload_process = subprocess.run(upload_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return jsonify(message="Upload successful." if upload_process.returncode == 0 else "Upload failed.")
            
    return render_template_string(TEMPLATE, ports=ports, current_robot_id=current_robot_id)

@app.route('/toggle_debug', methods=['POST'])
def toggle_debug():
    data = request.get_json()
    debug_state = data.get('debug')
    file_path = "hustler_stm32_master_v1\hustler_stm32_master_v1.ino"

    try:
        with open(file_path, "r") as file:
            lines = file.readlines()

        if len(lines) >= debug_line_number:
            lines[debug_line_number-1] = "#define DEBUG 1\n" if debug_state else "#define DEBUG 0\n"  # Update the 25th line

        with open(file_path, "w") as file:
            file.writelines(lines)

        return jsonify(message="Debug mode updated successfully.")
    except FileNotFoundError:
        print("File not found.")
        return jsonify(message="Error: File not found."), 404

@app.route('/toggle_has_pto_dac', methods=['POST'])
def toggle_has_pto_dac():
    data = request.get_json()
    enabled = data.get('enabled')
    file_path = "hustler_stm32_master_v1\hustler_stm32_master_v1.ino"

    try:
        with open(file_path, "r") as file:
            lines = file.readlines()

        if len(lines) >= HAS_PTO_DAC_line_number:
            lines[HAS_PTO_DAC_line_number-1] = "#define HAS_PTO_DAC 1 // if DAC 1 if PWM 0\n" if enabled else "#define HAS_PTO_DAC 0 // if DAC 1 if PWM 0\n"  # Update the specific line

        with open(file_path, "w") as file:
            file.writelines(lines)

        return jsonify(message="HAS PTO DAC mode updated successfully.")
    except FileNotFoundError:
        print("File not found.")
        return jsonify(message="Error: File not found."), 404

@app.route('/toggle_is_motors_reversed', methods=['POST'])
def toggle_is_motors_reversed():
    data = request.get_json()
    enabled = data.get('enabled')
    file_path = "hustler_stm32_master_v1\hustler_stm32_master_v1.ino"

    try:
        with open(file_path, "r") as file:
            lines = file.readlines()

        if len(lines) >= IS_MOTORS_REVERSED_line_number:
            lines[IS_MOTORS_REVERSED_line_number-1] = "bool IS_MOTORS_REVERSED = 1;\n" if enabled else "bool IS_MOTORS_REVERSED = 0;\n"  # Update the specific line

        with open(file_path, "w") as file:
            file.writelines(lines)

        return jsonify(message="IS MOTORS REVERSED mode updated successfully.")
    except FileNotFoundError:
        print("File not found.")
        return jsonify(message="Error: File not found."), 404


@app.route('/ports', methods=['GET'])
def ports():
    ports = serial.tools.list_ports.comports()
    ports_list = [port.device for port in ports]
    return jsonify(ports=ports_list)

if __name__ == '__main__':
    app.run(debug=True)


# pyinstaller --onefile .\FR_Firmware_Uploader.py