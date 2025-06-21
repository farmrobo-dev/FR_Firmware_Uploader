import os
import subprocess
import requests
import serial.tools.list_ports
import webbrowser
from threading import Thread
from packaging import version
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import serial
import datetime
import importlib  # GitHub Repo Info

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
            return

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


def upload_firmware(firmware_path, com_port, serial_monitor=None):  # Pass SerialMonitor instance
    """Uploads the provided firmware to the device, handling permission errors."""
    if not com_port:
        log_message("Error: Please select a COM port.")
        return

    script_path = os.path.abspath(os.path.join("win", "massStorageCopy.bat"))
    if not os.path.exists(script_path):
        log_message(f"Batch file not found: {script_path}. Ensure it exists.")
        return

    if not os.path.exists(firmware_path):
        log_message(f"Firmware file not found: {firmware_path}. Ensure it exists.")
        return

    upload_command = [script_path, "-I", firmware_path, "-O", "NODE_F446ZE", "-P", com_port]

    try:
        log_message(f"Uploading firmware from: {firmware_path} to {com_port}")

        # Stop Serial Monitoring Temporarily
        if serial_monitor and serial_monitor.is_monitoring:
            serial_monitor.stop_monitoring()
            log_message("Temporarily stopped serial monitoring for upload.")

        result = subprocess.run(upload_command, capture_output=True, text=True)

        if result.returncode == 0:
            log_message("Firmware uploaded successfully.")

        else:
            log_message(f"Upload failed. Error: {result.stderr}")

    except FileNotFoundError:
        log_message(f"File not found: {firmware_path}. Please ensure the file exists.")
    except PermissionError as e:
        log_message(
            f"PermissionError: Could not open port '{com_port}'. Access is denied.  Close any other applications using this port and try again. Error: {e}"
        )
    except Exception as e:
        log_message(f"An unexpected error occurred during upload: {e}")

    finally:
        # Restart Serial Monitoring (if it was running)
        if serial_monitor:  # added this logic to fix the serial data not showing again after uploading the bin file
            serial_monitor.start_monitoring()  # restart monitoring the serial data
            log_message("Restarted serial monitoring after upload.")


def upload_selected_firmware_threaded():
    """Uploads the firmware based on the dropdown selections."""
    r1_temp = r1_temp_dropdown.get()
    r1_tools = r1_tools_dropdown.get()
    r1_actuator = r1_actuator_dropdown.get()
    firmware_file = f"R1-{r1_temp}-{r1_tools}-{r1_actuator}.bin"
    firmware_path = os.path.abspath(os.path.join("bin", firmware_file))

    active_tab = notebook.index(notebook.select())
    if active_tab == 0:
        com_port = serial_monitor_tab1.port_dropdown.get()
        serial_monitor = serial_monitor_tab1  # Get SerialMonitor instance
    elif active_tab == 1:
        com_port = serial_monitor_tab2.port_dropdown.get()
        serial_monitor = serial_monitor_tab2  # Get SerialMonitor instance
    else:
        log_message("Error: No active tab selected")
        return

    if not os.path.exists(firmware_path):
        log_message(f"Firmware file not found: {firmware_file}")
        return

    log_message(f"Selected Firmware: {firmware_file}")
    thread = Thread(
        target=lambda: upload_firmware(firmware_path, com_port, serial_monitor)
    )  # Pass SerialMonitor instance
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
        download_button.config(state=tk.NORMAL)
    else:
        log_message("Firmware is up to date.")


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

    thread = Thread(target=download_thread)
    thread.start()


def refresh_com_ports():
    """Refreshes the list of available COM ports in both the main dropdown and the SerialMonitor."""
    com_ports = [port.device for port in serial.tools.list_ports.comports()]

    # Update SerialMonitor's COM port dropdowns
    serial_monitor_tab1.update_com_ports(com_ports)
    serial_monitor_tab2.update_com_ports(com_ports)

    log_message("COM ports refreshed in all locations.")


def refresh_local_data():
    """Refreshes the local data (e.g., from the bin folder)."""
    log_message("Refreshing local data...")
    local_version = get_local_version()
    current_version_label.config(text=f"Current Firmware Version: {local_version}")
    log_message("Local data refreshed.")


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

    active_tab = notebook.index(notebook.select())
    if active_tab == 0:
        com_port = serial_monitor_tab1.port_dropdown.get()
        serial_monitor = serial_monitor_tab1  # Get SerialMonitor instance
    elif active_tab == 1:
        com_port = serial_monitor_tab2.port_dropdown.get()
        serial_monitor = serial_monitor_tab2  # Get SerialMonitor instance
    else:
        log_message("Error: no active tab selected")
        return

    if not firmware_path:
        log_message("Error: Please select a custom firmware file.")
        return

    thread = Thread(
        target=lambda: upload_firmware(firmware_path, com_port, serial_monitor)
    )  # Pass SerialMonitor instance
    thread.start()


# --- Serial Monitor Implementation ---
class SerialMonitor(ttk.Frame):
    def __init__(self, parent, log_text_widget, all_log_texts, *args, **kwargs):  # Added log_text_widget
        super().__init__(parent, *args, **kwargs)
        self.serial_connection = None
        self.is_monitoring = False
        self.log_text = log_text_widget  # Store the log text widget
        self.parent = parent
        self.all_log_texts = all_log_texts  # Store references to all log text widgets
        self.receiving_data = False  # Control flag to prevent flickering
        self.auto_scroll = True # Enables autoscroll by default

        # --- Configuration Frame ---
        config_frame = ttk.Frame(self)
        config_frame.pack(fill=tk.X, pady=5)

        # Monitor Mode
        ttk.Label(config_frame, text="Monitor Mode:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.monitor_mode = tk.StringVar(value="serial")
        self.monitor_mode_dropdown = ttk.Combobox(
            config_frame,
            values=["serial", "tcp"],
            textvariable=self.monitor_mode,
            state="readonly",
            width=6,
        )
        self.monitor_mode_dropdown.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.monitor_mode_dropdown.set("serial")

        # View Mode
        ttk.Label(config_frame, text="View Mode:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.view_mode = tk.StringVar(value="text")
        self.view_mode_dropdown = ttk.Combobox(
            config_frame,
            values=["text", "hex"],
            textvariable=self.view_mode,
            state="readonly",
            width=5,
        )
        self.view_mode_dropdown.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.view_mode_dropdown.set("text")

        # Port Selection
        ttk.Label(config_frame, text="Port:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.port_list = [port.device for port in serial.tools.list_ports.comports()]
        self.port_dropdown = ttk.Combobox(config_frame, values=self.port_list, state="readonly", width=8)
        self.port_dropdown.grid(row=0, column=5, sticky=tk.W, padx=5, pady=5)
        if self.port_list:
            self.port_dropdown.set(self.port_list[0])

        # Baud Rate
        ttk.Label(config_frame, text="Baud Rate:").grid(row=0, column=6, sticky=tk.W, padx=5, pady=5)
        self.baud_rates = [300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 74800, 115200, 230400, 250000]
        self.baud_rate_dropdown = ttk.Combobox(
            config_frame, values=self.baud_rates, state="readonly", width=6
        )
        self.baud_rate_dropdown.grid(row=0, column=7, sticky=tk.W, padx=5, pady=5)
        self.baud_rate_dropdown.set(115200)

        # Timestamp
        self.timestamp_var = tk.BooleanVar(value=False)
        self.timestamp_check = ttk.Checkbutton(config_frame, text="Timestamp", variable=self.timestamp_var)
        self.timestamp_check.grid(row=0, column=8, sticky=tk.W, padx=5, pady=5)

        # Line Ending
        ttk.Label(config_frame, text="Line Ending:").grid(row=0, column=9, sticky=tk.W, padx=5, pady=5)
        self.line_endings = ["None", "LF", "CR", "CRLF"]
        self.line_ending_dropdown = ttk.Combobox(
            config_frame, values=self.line_endings, state="readonly", width=5
        )
        self.line_ending_dropdown.grid(row=0, column=10, sticky=tk.W, padx=5, pady=5)
        self.line_ending_dropdown.set("None")

        # Text Area for Serial Output
        self.serial_text = scrolledtext.ScrolledText(self, wrap=tk.NONE, width=80, height=20, state=tk.DISABLED)  # wrap=tk.NONE for single line
        # Disable initially

        # Add horizontal scrollbar
        self.x_scrollbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.serial_text.xview)
        self.y_scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.serial_text.yview) # Add the Y scrollbar

        # Configure scrollbars to work together
        self.serial_text.configure(xscrollcommand=self.x_scrollbar.set, yscrollcommand=self.y_scrollbar.set)


        # Buttons Frame (for Start Monitoring, Refresh Ports, Clear)
        buttons_frame = ttk.Frame(self)

        self.start_stop_button = ttk.Button(
            buttons_frame, text="Start Monitoring", command=self.toggle_monitoring, width=15
        )
        self.start_stop_button.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W + tk.E)

        self.refresh_button = ttk.Button(
            buttons_frame, text="Refresh Ports", command=self.refresh_ports_all, width=15
        )
        self.refresh_button.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        self.clear_button = ttk.Button(buttons_frame, text="Clear", command=self.clear_serial_text, width=15)
        self.clear_button.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W + tk.E)

        self.autoscroll_var = tk.BooleanVar(value=True)
        self.autoscroll_check = ttk.Checkbutton(buttons_frame, text="Autoscroll", variable=self.autoscroll_var, command=self.toggle_autoscroll)
        self.autoscroll_check.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        buttons_frame.grid_columnconfigure(2, weight=1)
        buttons_frame.grid_columnconfigure(3, weight=1)


        # Pack widgets in the correct order
        self.x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y) # Add this line
        buttons_frame.pack(fill=tk.X, pady=5)
        self.serial_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.serial_text.configure(xscrollcommand=self.x_scrollbar.set, yscrollcommand=self.y_scrollbar.set)  # Configure the scrollbar

    def toggle_autoscroll(self):
        self.auto_scroll = self.autoscroll_var.get() # Updates the autoscroll flag

    def clear_serial_text(self):
        """Clears the serial monitor text area."""
        self.serial_text.config(state=tk.NORMAL)  # Enable temporarily to clear
        self.serial_text.delete("1.0", tk.END)
        self.serial_text.config(state=tk.DISABLED)  # Disable again

    def refresh_ports(self):
        """Refreshes the list of available COM ports."""
        com_ports = [port.device for port in serial.tools.list_ports.comports()]
        self.update_com_ports(com_ports)

    def refresh_ports_all(self):
        """Refreshes the COM ports in both the dropdown and the combobox in the SerialMonitor."""
        refresh_com_ports()  # Refresh the main COM port dropdown
        self.refresh_ports()  # Refresh the SerialMonitor's COM port dropdown

    def toggle_monitoring(self):
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        """Starts monitoring the serial port."""
        port_name = self.port_dropdown.get()
        baud_rate = int(self.baud_rate_dropdown.get())
        try:
            self.serial_connection = serial.Serial(port_name, baud_rate, timeout=0.05)  # Reduced timeout
            self.is_monitoring = True
            self.receiving_data = False
            self.start_stop_button.config(text="Stop Monitoring")
            self.log_message(f"Monitoring serial port {port_name} at {baud_rate} baud.")

            # Disable scrollbar during monitoring
            # self.x_scrollbar.config(command="")
            self.serial_text.config(state=tk.NORMAL) #enable text before monitoring
            self.read_serial_data()

        except serial.SerialException as e:
            self.log_message(f"Error opening serial port: {e}")
        except Exception as e:
            self.log_message(f"An unexpected error occurred: {e}")

    def stop_monitoring(self):
        """Stops monitoring the serial port."""
        if self.serial_connection:
            try:
                self.is_monitoring = False
                self.start_stop_button.config(text="Start Monitoring")
                self.serial_connection.close()
                self.log_message(f"---- Closed the serial port {self.port_dropdown.get()} ----")

                # Enable scrollbar after stopping monitoring
                # self.x_scrollbar.config(command=self.serial_text.xview)
                self.serial_text.config(state=tk.DISABLED)  # Disable after stopping

            except serial.SerialException as e:
                self.log_message(f"Error closing serial port: {e}")
        else:
            self.log_message("Serial port is not open.")

    def read_serial_data(self):
        """Reads data from the serial port and updates the text area."""
        if self.is_monitoring and self.serial_connection:
            try:
                if not self.receiving_data:
                    self.receiving_data = True
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    if data:
                        self.process_data(data)
                    self.receiving_data = False
            except serial.SerialException as e:
                self.log_message(f"Error reading from serial port: {e}")
                self.stop_monitoring()
            except Exception as e:
                self.log_message(f"An unexpected error occurred: {e}")
                self.stop_monitoring()
        self.after(10, self.read_serial_data)  # Faster polling

    def process_data(self, data):
        """Processes the received data based on the view mode."""
        view_mode = self.view_mode.get()
        try:
            text = ""
            if view_mode == "text":
                try:
                    text = data.decode("utf-8", errors="replace")
                except UnicodeDecodeError as e:
                    self.log_message(f"Unicode Decode Error: {e}")
                    text = "[ERROR: Could not decode data]"
            elif view_mode == "hex":
                hex_data = " ".join([f"{x:02X}" for x in data])
                text = hex_data

            if self.timestamp_var.get():
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                text = f"{timestamp} -> {text}"  # Modified timestamp format

            # Update all serial text widgets
            for log_text in self.all_log_texts:
                log_text.serial_text.config(state=tk.NORMAL) #enable
                log_text.serial_text.insert(tk.END, text)
                if self.auto_scroll:
                    log_text.serial_text.see(tk.END)  # Autoscroll to the end
                log_text.serial_text.config(state=tk.DISABLED) #disable
            # self.serial_text.insert(tk.END, text)
            # self.serial_text.see(tk.END)
        except Exception as e:
            self.log_message(f"Error processing received data: {e}")

    def update_com_ports(self, com_ports):
        """Updates the COM port list in the dropdown."""
        self.port_list = com_ports
        self.port_dropdown["values"] = self.port_list
        if self.port_list and self.port_dropdown["values"]:
            self.port_dropdown.set(self.port_list[0])

    def log_message(self, message):
        """Logs a message to the log text widget."""
        log_message(message)  # Use the main log_message function

    def start_serial_monitoring(self):
        """Starts the serial monitor on the active tab."""
        active_tab = notebook.index(notebook.select())
        if active_tab == 0:
            serial_monitor_tab1.start_monitoring()
        elif active_tab == 1:
            serial_monitor_tab2.start_monitoring()


# --- GUI Setup ---
root = tk.Tk()
root.title("FR Firmware Uploader")
root.state("zoomed")  # maxmize window

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
    main_content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=10, pady=10)
    right_side_frame = ttk.Frame(parent)
    right_side_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
    return main_content_frame, right_side_frame


# Tab 1: FarmRobo Firmware
tab1 = ttk.Frame(notebook)
notebook.add(tab1, text="FarmRobo Firmware")

main_content_tab1, right_side_tab1 = create_tab_with_right_side(tab1)

# Configure grid layout for main_content_tab1
for i in range(13):
    main_content_tab1.grid_rowconfigure(i, weight=0)
main_content_tab1.grid_columnconfigure(0, weight=1)
main_content_tab1.grid_columnconfigure(1, weight=1)

# Log Text Widget for Tab 1 (Declare it first)
log_label_tab1 = ttk.Label(right_side_tab1, text="Log:")
log_label_tab1.pack()
log_text_tab1 = scrolledtext.ScrolledText(right_side_tab1, wrap=tk.WORD, width=60, height=5)
log_text_tab1.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Tab 2: Custom Upload
tab2 = ttk.Frame(notebook)
notebook.add(tab2, text="Custom Upload")

main_content_tab2, right_side_tab2 = create_tab_with_right_side(tab2)

# Log Text Widget for Tab 2
log_label_tab2 = ttk.Label(right_side_tab2, text="Log:")
log_label_tab2.pack()
log_text_tab2 = scrolledtext.ScrolledText(right_side_tab2, wrap=tk.WORD, width=60, height=5)
log_text_tab2.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Serial Monitor and Log in right_side_tab1 (Instantiate before other UI elements)
# Before you instantiate the SerialMonitor, create a list of all serial_text widgets.
all_log_texts = []
serial_monitor_tab1 = SerialMonitor(right_side_tab1, log_text_tab1, all_log_texts)  # Pass log_text_tab1
serial_monitor_tab1.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

# Serial Monitor and Log in right_side_tab2 (Instantiate before other UI elements)
serial_monitor_tab2 = SerialMonitor(right_side_tab2, log_text_tab2, all_log_texts)  # Pass log_text_tab2
serial_monitor_tab2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

all_log_texts.append(serial_monitor_tab1)
all_log_texts.append(serial_monitor_tab2)

# Current Firmware Version
current_version = get_local_version()
current_version_label = ttk.Label(main_content_tab1, text=f"Current Firmware Version: {current_version}")
current_version_label.grid(row=0, column=0, sticky=tk.W + tk.E, padx=10, pady=5)

# Check for Updates Button
check_update_button = ttk.Button(
    main_content_tab1, text="Check for Updates", command=check_for_updates, width=15
)
check_update_button.grid(row=1, column=0, sticky=tk.W + tk.E, padx=10, pady=5)

# Refresh Button
refresh_button = ttk.Button(main_content_tab1, text="Refresh", command=refresh_local_data, width=15)
refresh_button.grid(row=1, column=1, sticky=tk.W + tk.E, padx=10, pady=5)

# Download Button
download_button = ttk.Button(
    main_content_tab1, text="Download Latest Release", command=download_latest_release, width=15
)
download_button.grid(row=2, column=0, sticky=tk.W + tk.E, padx=10, pady=5)

# R1-TEMP Dropdowns
r1_temp_label = ttk.Label(main_content_tab1, text="R1-TEMP:")
r1_temp_label.grid(row=3, column=0, sticky=tk.W + tk.E, padx=10, pady=5)
r1_temp_options = ["IT", "ET"]
r1_temp_dropdown = ttk.Combobox(main_content_tab1, values=r1_temp_options, state="readonly")
r1_temp_dropdown.grid(row=4, column=0, sticky=tk.W + tk.E, padx=10, pady=5)
r1_temp_dropdown.set("IT")

# R1-TOOLS Dropdowns
r1_tools_label = ttk.Label(main_content_tab1, text="R1-TOOLS:")
r1_tools_label.grid(row=5, column=0, sticky=tk.W + tk.E, padx=10, pady=5)
r1_tools_options = ["CAN", "THR"]
r1_tools_dropdown = ttk.Combobox(main_content_tab1, values=r1_tools_options, state="readonly")
r1_tools_dropdown.grid(row=6, column=0, sticky=tk.W + tk.E, padx=10, pady=5)
r1_tools_dropdown.set("CAN")

# R1-ACTUATOR Dropdowns
r1_actuator_label = ttk.Label(main_content_tab1, text="R1-ACTUATOR:")
r1_actuator_label.grid(row=7, column=0, sticky=tk.W + tk.E, padx=10, pady=5)
r1_actuator_options = ["BTS", "CYT"]
r1_actuator_dropdown = ttk.Combobox(main_content_tab1, values=r1_actuator_options, state="readonly")
r1_actuator_dropdown.grid(row=8, column=0, sticky=tk.W + tk.E, padx=10, pady=5)
r1_actuator_dropdown.set("BTS")

# Upload Latest Firmware Button
upload_button = ttk.Button(
    main_content_tab1, text="Upload Selected Firmware", command=upload_selected_firmware_threaded, width=15
)
upload_button.grid(row=11, column=0, sticky=tk.W + tk.E, padx=10, pady=5)

# Latest Version Message
latest_version_label = ttk.Label(main_content_tab1, text="Latest release: Unknown")
latest_version_label.grid(row=12, column=0, sticky=tk.W + tk.E, padx=10, pady=5)

# Custom Firmware Path
custom_firmware_path = tk.StringVar()
custom_firmware_label = ttk.Label(main_content_tab2, text="Custom Firmware File:")
custom_firmware_label.pack(pady=5)
custom_firmware_entry = ttk.Entry(main_content_tab2, textvariable=custom_firmware_path, width=50)
custom_firmware_entry.pack(pady=5, padx=10)
browse_button = ttk.Button(main_content_tab2, text="Browse", command=browse_firmware_file, width=15)
browse_button.pack(pady=5)

# Upload Custom Firmware Button
upload_custom_button = ttk.Button(
    main_content_tab2, text="Upload Custom Firmware", command=upload_custom_firmware_threaded, width=25)
upload_custom_button.pack(pady=5)

notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)


def log_message(message):
    """Logs a message to the text area in the GUI based on the active tab."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message_with_timestamp = f"[{timestamp}] {message}\n"
    active_tab = notebook.index(notebook.select())
    if active_tab == 0:
        log_text_tab1.insert(tk.END, log_message_with_timestamp)
        log_text_tab1.see(tk.END)
        tab1.update_idletasks()
    elif active_tab == 1:
        log_text_tab2.insert(tk.END, log_message_with_timestamp)
        log_text_tab2.see(tk.END)
        tab2.update_idletasks()
    else:
        print("No active tab to log to.")



# --- Main ---
if __name__ == "__main__":
    # Test serial import
    try:
        import serial

        print("Serial module is installed.")
    except ImportError:
        print("Serial module is not installed.")
        install_serial = messagebox.askyesno(
            "Serial Module Not Found",
            "The 'serial' module is not installed. Do you want to install it now?",
        )
        if install_serial:
            try:
                import subprocess

                subprocess.check_call(["pip", "install", "pyserial"])
                print("Serial module installed successfully.")
                serial = importlib.import_module("serial")  # Reload the module
                messagebox.showinfo(
                    "Success",
                    "Serial module installed successfully. Please restart the application.",
                )
            except subprocess.CalledProcessError as e:
                print(f"Error installing serial module: {e}")
                messagebox.showerror("Error", f"Failed to install serial module: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while installing pyserial: {e}")
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred while installing pyserial: {e}",
                )
        else:
            messagebox.showinfo(
                "Info",
                "Without the serial module, serial communication will not be possible.",
            )

    log_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=5)
    root.mainloop()