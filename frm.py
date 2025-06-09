import os
import subprocess
import requests
import serial.tools.list_ports
import webbrowser
from threading import Thread
from packaging import version
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import asyncio  # Import asyncio
import serial
import datetime

# GitHub Repo Info
GITHUB_REPO = "farmrobo-dev/FR_Firmware_Uploader"
FIRMWARE_FOLDER = "bin"
LOCAL_VERSION_FILE = os.path.join(FIRMWARE_FOLDER, "version.txt")

# --- Helper Functions ---
def get_local_version():
    """Reads the local firmware version from file."""
    try:
        if os.path.exists(LOCAL_VERSION_FILE):
            with open(LOCAL_VERSION_FILE, "r") as f:
                return f.read().strip()
    except Exception as e:
        log_message(f"Error reading local version: {e}")
        return "v0.0.0"
    return "v0.0.0"

def get_latest_firmware_version():
    """Fetches the latest firmware version and assets from GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        release_data = response.json()
        return release_data.get("tag_name", "v1.0.0"), release_data.get("assets", [])
    except requests.RequestException as e:
        log_message(f"Network error getting latest version: {e}")
        return "v0.0.0", []

def download_firmware(assets):
    """Downloads firmware files from the provided asset list."""
    download_folder = FIRMWARE_FOLDER
    if not os.path.exists(download_folder):
        try:
            os.makedirs(download_folder)
        except OSError as e:
            log_message(f"Error creating download folder: {e}")
            return  # Stop if folder creation fails

    for asset in assets:
        asset_url = asset["browser_download_url"]
        file_name = os.path.join(download_folder, asset["name"])
        try:
            response = requests.get(asset_url, timeout=10)
            response.raise_for_status()
            with open(file_name, "wb") as f:
                f.write(response.content)
            log_message(f"Downloaded {file_name}")
        except requests.RequestException as e:
            log_message(f"Failed to download {asset_url}: {e}")

def upload_firmware(firmware_path):  # Modified to take firmware path
    """Uploads the provided firmware to the device."""
    global com_port_dropdown

    com_port = com_port_dropdown.get()
    if not com_port:
        show_message("Error", "Please select a COM port.")
        return

    # Construct the full path to the batch file
    script_path = os.path.abspath(os.path.join("win", "massStorageCopy.bat"))

    # Check if the batch file and firmware file exist
    if not os.path.exists(script_path):
        log_message(f"Batch file not found: {script_path}.  Ensure it exists.")
        show_message(
            "Error", f"Batch file not found: {script_path}.  Ensure it exists."
        )
        return

    if not os.path.exists(firmware_path):
        log_message(f"Firmware file not found: {firmware_path}.  Ensure it exists.")
        show_message(
            "Error", f"Firmware file not found: {firmware_path}.  Ensure it exists."
        )
        return

    # Construct the upload command as a list
    upload_command = [script_path, "-I", firmware_path, "-O", "NODE_F446ZE"]

    try:
        log_message(f"Uploading firmware from: {firmware_path}")
        result = subprocess.run(
            upload_command,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            log_message(f"Firmware uploaded successfully.")
            show_message("Success", "Firmware uploaded successfully!")
        else:
            log_message(f"Upload failed. Error: {result.stderr}")
            show_message("Error", f"Upload failed. Error: {result.stderr}")

    except FileNotFoundError:
        log_message(
            f"File not found: {firmware_path}. Please ensure the file exists."
        )
        show_message(
            "Error", f"File not found: {firmware_path}.  Ensure it exists."
        )
    except Exception as e:
        log_message(f"An unexpected error occurred during upload: {e}")
        show_message("Error", f"An unexpected error occurred during upload: {e}")

def upload_selected_firmware_threaded():
    """Uploads the firmware based on the dropdown selections."""
    r1_temp = r1_temp_dropdown.get()
    r1_tools = r1_tools_dropdown.get()
    r1_actuator = r1_actuator_dropdown.get()

    firmware_file = f"R1-{r1_temp}-{r1_tools}-{r1_actuator}.bin"
    firmware_path = os.path.abspath(os.path.join("bin", firmware_file))

    if not os.path.exists(firmware_path):
        show_message("Error", f"Firmware file not found: {firmware_file}")
        return

    log_message(f"Selected Firmware: {firmware_file}")
    thread = Thread(target=lambda: upload_firmware(firmware_path))
    thread.start()

def check_for_updates():
    """Checks for updates on GitHub and updates the UI."""
    latest_version, assets = get_latest_firmware_version()
    local_version = get_local_version()

    if latest_version == "v0.0.0":
        log_message("No internet connection. Skipping update check.")
        return

    if version.parse(latest_version) > version.parse(local_version):
        log_message(f"New firmware available: {latest_version}.")
        latest_version_label.config(text=f"Latest release: {latest_version}")
        download_button.config(state=tk.NORMAL)  # Enable download button
    else:
        log_message("Firmware is up to date.")
        show_message("Info", "Firmware is up to date.")

def download_latest_release():
    """Downloads the latest firmware release in a separate thread."""

    def download_thread():
        latest_version, assets = get_latest_firmware_version()

        if latest_version == "v0.0.0":
            log_message("No internet connection. Cannot download firmware.")
            return

        download_firmware(assets)
        try:
            with open(LOCAL_VERSION_FILE, "w") as f:
                f.write(latest_version)
        except Exception as e:
            log_message(f"Error writing local version file: {e}")
            return
        log_message("Downloaded Successfully.")
        show_message("Success", "Firmware Downloaded Successfully!")

    thread = Thread(target=download_thread)
    thread.start()

def refresh_com_ports():
    """Refreshes the list of available COM ports."""
    com_ports = [port.device for port in serial.tools.list_ports.comports()]
    global com_port_dropdown, serial_monitor_tab1, serial_monitor_tab2
    # Update the main firmware uploader dropdown
    com_port_dropdown["values"] = com_ports
    if com_ports and com_port_dropdown["values"]:  # Select first port if available
        com_port_dropdown.set(com_ports[0])

    # Update the serial monitor dropdowns in both tabs
    serial_monitor_tab1.update_com_ports(com_ports)
    serial_monitor_tab2.update_com_ports(com_ports)

def refresh_local_data():
    """Refreshes the local data (e.g., from the bin folder)."""
    log_message("Refreshing local data...")
    #  Add code here to resync or reload local data from the 'bin' folder if needed.
    # For example, reload the local version:
    local_version = get_local_version()
    current_version_label.config(text=f"Current Firmware Version: {local_version}")
    log_message("Local data refreshed.")

# --- Custom Upload Functions ---
def browse_firmware_file():
    """Opens a file dialog to select a firmware file."""
    filename = filedialog.askopenfilename(
        title="Select Firmware File",
        filetypes=(("Firmware Files", "*.bin;*.hex;*.ino.bin"), ("All files", "*.*")),
    )
    if filename:
        custom_firmware_path.set(filename)

def upload_custom_firmware_threaded():
    """Uploads the custom firmware file in a separate thread."""
    firmware_path = custom_firmware_path.get()
    if not firmware_path:
        show_message("Error", "Please select a custom firmware file.")
        return

    thread = Thread(
        target=lambda: upload_firmware(firmware_path)
    )  # Pass Firmware Path
    thread.start()

def show_message(title, message):
    """Displays a message box to the right of the main window."""
    x = root.winfo_x() + root.winfo_width() + 10  # X position to the right
    y = root.winfo_y() + 50  # Y position (adjust as needed)
    messagebox.showinfo(title, message)

# --- Serial Monitor Implementation ---
class SerialMonitor(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.port = None  # store the active serial port

        self.serial_connection = None  # store the serial connection object
        self.is_monitoring = False  # flag to indicate if monitoring is active

        # --- Configuration ---
        config_frame = ttk.Frame(self)
        config_frame.pack(pady=5)

        # Monitor Mode
        ttk.Label(config_frame, text="Monitor Mode:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.monitor_mode = tk.StringVar(value="serial")
        ttk.Radiobutton(
            config_frame, text="Serial", variable=self.monitor_mode, value="serial"
        ).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(
            config_frame, text="TCP", variable=self.monitor_mode, value="tcp"
        ).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)

        # View Mode
        ttk.Label(config_frame, text="View Mode:").grid(
            row=0, column=3, sticky=tk.W, padx=5, pady=5
        )
        self.view_mode = tk.StringVar(value="text")
        ttk.Radiobutton(
            config_frame, text="Text", variable=self.view_mode, value="text"
        ).grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(
            config_frame, text="HEX", variable=self.view_mode, value="hex"
        ).grid(row=0, column=5, sticky=tk.W, padx=5, pady=5)

        # Port Selection
        ttk.Label(config_frame, text="Port:").grid(
            row=0, column=6, sticky=tk.W, padx=5, pady=5
        )
        self.port_list = [port.device for port in serial.tools.list_ports.comports()]
        self.port_dropdown = ttk.Combobox(
            config_frame, values=self.port_list, state="readonly", width=8
        )
        self.port_dropdown.grid(row=0, column=7, sticky=tk.W, padx=5, pady=5)
        if self.port_list:
            self.port_dropdown.set(self.port_list[0])  # Select the first port

        # Baud Rate
        ttk.Label(config_frame, text="Baud Rate:").grid(
            row=0, column=8, sticky=tk.W, padx=5, pady=5
        )
        self.baud_rates = [
            300,
            1200,
            2400,
            4800,
            9600,
            19200,
            38400,
            57600,
            74800,
            115200,
            230400,
            250000,
        ]
        self.baud_rate_dropdown = ttk.Combobox(
            config_frame, values=self.baud_rates, state="readonly", width=6
        )
        self.baud_rate_dropdown.grid(row=0, column=9, sticky=tk.W, padx=5, pady=5)
        self.baud_rate_dropdown.set(115200)  # Default Baud Rate

        # Timestamp Button (added beside Baud Rate)
        self.timestamp_var = tk.BooleanVar(value=False)  # Initially off
        self.timestamp_check = ttk.Checkbutton(
            config_frame, text="Timestamp", variable=self.timestamp_var
        )
        self.timestamp_check.grid(
            row=0, column=10, sticky=tk.W, padx=5, pady=5
        )  # Adjusted column

        # Line Ending
        ttk.Label(config_frame, text="Line Ending:").grid(
            row=0, column=11, sticky=tk.W, padx=5, pady=5
        )
        self.line_endings = ["None", "LF", "CR", "CRLF"]
        self.line_ending_dropdown = ttk.Combobox(
            config_frame, values=self.line_endings, state="readonly", width=5
        )
        self.line_ending_dropdown.grid(
            row=0, column=12, sticky=tk.W, padx=5, pady=5
        )
        self.line_ending_dropdown.set("None")  # Default Line Ending

        # Start/Stop Button
        self.start_stop_button = ttk.Button(
            config_frame, text="Start Monitoring", command=self.toggle_monitoring
        )
        self.start_stop_button.grid(row=0, column=13, pady=10, padx=5)

        # Refresh Button
        self.refresh_button = ttk.Button(
            config_frame, text="Refresh Ports", command=self.refresh_ports
        )
        self.refresh_button.grid(row=0, column=14, pady=10, padx=5)  # Add beside Start/Stop

        # Text Area for Serial Output
        self.serial_text = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, width=80, height=20  # Increased height
        )
        self.serial_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.pack(fill=tk.BOTH, expand=True)

    def refresh_ports(self):
        """Refreshes the list of available COM ports."""
        com_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.update_com_ports(com_ports)

    def toggle_monitoring(self):
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        """Starts monitoring the serial port."""
        port_name = self.port_dropdown.get()
        baud_rate = int(self.baud_rate_dropdown.get())
        line_ending = self.line_ending_dropdown.get()

        try:
            self.serial_connection = serial.Serial(port_name, baud_rate, timeout=0.1)
            self.is_monitoring = True
            self.start_stop_button.config(text="Stop Monitoring")
            log_message(f"Monitoring serial port {port_name} at {baud_rate} baud.")
            self.read_serial_data()  # Start reading data in a loop
        except serial.SerialException as e:
            log_message(f"Error opening serial port: {e}")
            messagebox.showerror("Error", f"Failed to open serial port: {e}")

    def stop_monitoring(self):
        """Stops monitoring the serial port."""
        if self.serial_connection:
            try:
                self.serial_connection.close()
                self.is_monitoring = False
                self.start_stop_button.config(text="Start Monitoring")
                log_message(f"---- Closed the serial port {self.port_dropdown.get()} ----")
            except serial.SerialException as e:
                log_message(f"Error closing serial port: {e}")
                messagebox.showerror("Error", f"Failed to close serial port: {e}")
        else:
            log_message("Serial port is not open.")

    def read_serial_data(self):
        """Reads data from the serial port and updates the text area."""
        if self.is_monitoring and self.serial_connection:
            try:
                data = self.serial_connection.read(self.serial_connection.in_waiting)
                if data:
                    self.process_data(data)
            except serial.SerialException as e:
                log_message(f"Error reading from serial port: {e}")
                messagebox.showerror("Error", f"Error reading from serial port: {e}")
                self.stop_monitoring()  # Stop monitoring on error
        # Schedule the next read after 10ms
        self.after(10, self.read_serial_data)

    def process_data(self, data):
        """Processes the received data based on the view mode."""
        view_mode = self.view_mode.get()
        try:
            text = ""  # Initialize text variable
            if view_mode == "text":
                try:
                    text = data.decode("utf-8", errors="replace")  # Decode bytes to string
                except UnicodeDecodeError as e:
                    log_message(f"Unicode Decode Error: {e}")
                    text = "[ERROR: Could not decode data]"
            elif view_mode == "hex":
                hex_data = " ".join([f"{x:02X}" for x in data])  # Convert bytes to hex string
                text = hex_data

            # Add timestamp if enabled
            if self.timestamp_var.get():
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Format time
                text = f"[{timestamp}] {text}"  # Prepend timestamp

            self.serial_text.insert(tk.END, text)
            self.serial_text.see(tk.END)  # Autoscroll

        except Exception as e:
            log_message(f"Error processing received data: {e}")

    def update_com_ports(self, com_ports):
        """Updates the COM port list in the dropdown."""
        self.port_list = com_ports
        self.port_dropdown["values"] = self.port_list
        if self.port_list and self.port_dropdown["values"]:
            self.port_dropdown.set(self.port_list[0])

# --- GUI Setup ---
root = tk.Tk()
root.title("FR Firmware Uploader")
root.geometry("1200x750")  # Increased width for side-by-side layout

# Style
style = ttk.Style()
style.configure("TButton", padding=5, relief="flat")
style.configure("TLabel", padding=5)
style.configure("TCombobox", padding=5)

# UI Elements
notebook = ttk.Notebook(root)

# ---- Function to create main content and right side area ----
def create_tab_with_right_side(parent):
    main_content_frame = ttk.Frame(parent)
    main_content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    right_side_frame = ttk.Frame(parent, width=600)  # Fixed width for right side
    right_side_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=10, pady=10)

    return main_content_frame, right_side_frame

# Tab 1: FarmRobo Firmware
tab1 = ttk.Frame(notebook)
notebook.add(tab1, text="FarmRobo Firmware")

# Create main content area and right side area for tab1
main_content_tab1, right_side_tab1 = create_tab_with_right_side(tab1)

# Grid Layout for components in main_content_tab1
main_content_tab1.grid_columnconfigure(0, weight=1)
main_content_tab1.grid_columnconfigure(1, weight=1)

# Current Firmware Version
current_version = get_local_version()
current_version_label = ttk.Label(
    main_content_tab1, text=f"Current Firmware Version: {current_version}"
)
current_version_label.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

# Check for Updates Button
check_update_button = ttk.Button(
    main_content_tab1, text="Check for Updates", command=check_for_updates
)
check_update_button.grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

# Refresh Button (side of check for updates)
refresh_button = ttk.Button(
    main_content_tab1, text="Refresh", command=refresh_local_data
)
refresh_button.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

# Download Button
download_button = ttk.Button(
    main_content_tab1, text="Download Latest Release", command=download_latest_release
)
download_button.grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
#download_button.config(state=tk.DISABLED)  # Initially disabled

# --- R1-TEMP Dropdowns ---
r1_temp_label = ttk.Label(main_content_tab1, text="R1-TEMP:")
r1_temp_label.grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)

r1_temp_options = ["IT", "ET"]
r1_temp_dropdown = ttk.Combobox(main_content_tab1, values=r1_temp_options, state="readonly")
r1_temp_dropdown.grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
r1_temp_dropdown.set("IT")  # Default selection

# --- R1-TOOLS Dropdowns ---
r1_tools_label = ttk.Label(main_content_tab1, text="R1-TOOLS:")
r1_tools_label.grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)

r1_tools_options = ["CAN", "THR"]
r1_tools_dropdown = ttk.Combobox(main_content_tab1, values=r1_tools_options, state="readonly")
r1_tools_dropdown.grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
r1_tools_dropdown.set("CAN")  # Default selection

# --- R1-ACTUATOR Dropdowns ---
r1_actuator_label = ttk.Label(main_content_tab1, text="R1-ACTUATOR:")
r1_actuator_label.grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)

r1_actuator_options = ["BTS", "CYT"]
r1_actuator_dropdown = ttk.Combobox(main_content_tab1, values=r1_actuator_options, state="readonly")
r1_actuator_dropdown.grid(row=8, column=0, sticky=tk.W, padx=10, pady=5)
r1_actuator_dropdown.set("BTS")  # Default selection

# COM Port Selection
com_port_label = ttk.Label(main_content_tab1, text="Select COM Port:")
com_port_label.grid(row=9, column=0, sticky=tk.W, padx=10, pady=5)

com_ports = [port.device for port in serial.tools.list_ports.comports()]
com_port_dropdown = ttk.Combobox(main_content_tab1, values=com_ports, state="readonly")
com_port_dropdown.grid(row=10, column=0, sticky=tk.W, padx=10, pady=5)
if com_ports:  # Select first port if available
    com_port_dropdown.set(com_ports[0])

refresh_ports_button = ttk.Button(
    main_content_tab1, text="Refresh COM Ports", command=refresh_com_ports
)
refresh_ports_button.grid(row=11, column=0, sticky=tk.W, padx=10, pady=5, columnspan=2)  # Span across columns

# Upload Latest Firmware Button
upload_button = ttk.Button(
    main_content_tab1, text="Upload Selected Firmware", command=upload_selected_firmware_threaded
)  # Use threaded version
upload_button.grid(row=12, column=0, sticky=tk.W, padx=10, pady=5)

# Latest Version Message
latest_version_label = ttk.Label(main_content_tab1, text="Latest release: Unknown")
latest_version_label.grid(row=13, column=0, sticky=tk.W, padx=10, pady=5)

# Serial Monitor and Log in right_side_tab1
serial_monitor_tab1 = SerialMonitor(right_side_tab1)
serial_monitor_tab1.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

log_label_tab1 = ttk.Label(right_side_tab1, text="Log:")  # noqa: F841
log_label_tab1.pack()
log_text_tab1 = scrolledtext.ScrolledText(
    right_side_tab1, wrap=tk.WORD, width=60, height=5  # Reduced height
)
log_text_tab1.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Tab 2: Custom Upload
tab2 = ttk.Frame(notebook)
notebook.add(tab2, text="Custom Upload")

# Create main content area and right side area for tab2
main_content_tab2, right_side_tab2 = create_tab_with_right_side(tab2)

# Custom Firmware Path
custom_firmware_path = tk.StringVar()
custom_firmware_label = ttk.Label(main_content_tab2, text="Custom Firmware File:")
custom_firmware_label.pack(pady=5)

custom_firmware_entry = ttk.Entry(
    main_content_tab2, textvariable=custom_firmware_path, width=50
)
custom_firmware_entry.pack(pady=5, padx=10)

browse_button = ttk.Button(
    main_content_tab2, text="Browse", command=browse_firmware_file
)
browse_button.pack(pady=5)

# Upload Custom Firmware Button
upload_custom_button = ttk.Button(
    main_content_tab2, text="Upload Custom Firmware", command=upload_custom_firmware_threaded
)
upload_custom_button.pack(pady=5)

# Serial Monitor and Log in right_side_tab2
serial_monitor_tab2 = SerialMonitor(right_side_tab2)
serial_monitor_tab2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

log_label_tab2 = ttk.Label(right_side_tab2, text="Log:")  # noqa: F841
log_label_tab2.pack()
log_text_tab2 = scrolledtext.ScrolledText(
    right_side_tab2, wrap=tk.WORD, width=60, height=5  # Reduced height
)
log_text_tab2.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# --- Redirect log messages to the correct tab based on the active tab ---
def log_message(message):
    """Logs a message to the text area in the GUI based on the active tab."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message_with_timestamp = f"[{timestamp}] {message}\n"

    active_tab = notebook.index(notebook.select())  # Get the index of the selected tab

    if active_tab == 0:  # FarmRobo Firmware Tab
        log_text_tab1.insert(tk.END, log_message_with_timestamp)
        log_text_tab1.see(tk.END)
        tab1.update_idletasks()
    elif active_tab == 1:  # Custom Upload Tab
        log_text_tab2.insert(tk.END, log_message_with_timestamp)
        log_text_tab2.see(tk.END)
        tab2.update_idletasks()

# --- Main ---
if __name__ == "__main__":
    # Create a dummy log_text before creating any objects.
    log_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=5)  # create once before

    root.mainloop()