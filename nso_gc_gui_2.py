#!/usr/bin/env python3
"""
NSO GameCube Controller - Xbox 360 Emulator with GUI
Features:
- Live input visualization
- Stick calibration wizard
- Dead zone adjustment
- Save/load settings
- Xbox 360 controller emulation via ViGEmBus

Requirements:
    pip install vgamepad bleak
    Install ViGEmBus: https://github.com/nefarius/ViGEmBus/releases
"""

import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional
from bleak import BleakClient, BleakScanner

try:
    import vgamepad as vg
    VGAMEPAD_AVAILABLE = True
except ImportError:
    VGAMEPAD_AVAILABLE = False
    print("Warning: vgamepad not installed. Xbox emulation disabled.")
    print("Install with: pip install vgamepad")

# Controller BLE address (can be changed in GUI)
DEFAULT_CONTROLLER_ADDRESS = "3C:A9:AB:5F:70:B1"
INPUT_CHAR_UUID = "ab7de9be-89fe-49ad-828f-118f09df7fd2"
SETTINGS_FILE = "nso_gc_settings.json"

# ============================================================================
# Protocol Constants
# ============================================================================

BYTE4_Y = 0x01
BYTE4_X = 0x02
BYTE4_B = 0x04
BYTE4_A = 0x08
BYTE4_R_CLICK = 0x40
BYTE4_Z = 0x80

BYTE5_START = 0x02
BYTE5_HOME = 0x10
BYTE5_SCREENSHOT = 0x20
BYTE5_CHAT = 0x40

BYTE6_DPAD_DOWN = 0x01
BYTE6_DPAD_UP = 0x02
BYTE6_DPAD_RIGHT = 0x04
BYTE6_DPAD_LEFT = 0x08
BYTE6_L_CLICK = 0x40
BYTE6_ZL = 0x80


@dataclass
class CalibrationData:
    """Calibration values for analog inputs."""
    # Left Stick X (12-bit)
    left_x_min: int = 248
    left_x_center: int = 2048
    left_x_max: int = 3848
    
    # Left Stick Y (8-bit)
    left_y_min: int = 55
    left_y_center: int = 131
    left_y_max: int = 207
    
    # C-Stick X (12-bit)
    c_x_min: int = 248
    c_x_center: int = 2048
    c_x_max: int = 3848
    
    # C-Stick Y (8-bit)
    c_y_min: int = 55
    c_y_center: int = 131
    c_y_max: int = 207
    
    # Triggers
    l_trigger_min: int = 30
    l_trigger_max: int = 230
    r_trigger_min: int = 30
    r_trigger_max: int = 230
    
    # Dead zones (0.0 to 0.5)
    left_stick_deadzone: float = 0.05
    c_stick_deadzone: float = 0.05
    trigger_deadzone: float = 0.02


@dataclass
class ControllerState:
    """Current state of all controller inputs."""
    # Buttons
    a: bool = False
    b: bool = False
    x: bool = False
    y: bool = False
    z: bool = False
    start: bool = False
    home: bool = False
    screenshot: bool = False
    chat: bool = False
    l_click: bool = False
    r_click: bool = False
    zl: bool = False
    dpad_up: bool = False
    dpad_down: bool = False
    dpad_left: bool = False
    dpad_right: bool = False
    
    # Raw analog values (before calibration)
    left_x_raw: int = 0
    left_y_raw: int = 0
    c_x_raw: int = 0
    c_y_raw: int = 0
    l_trigger_raw: int = 0
    r_trigger_raw: int = 0
    
    # Calibrated analog values (-1.0 to 1.0 for sticks, 0.0 to 1.0 for triggers)
    left_stick_x: float = 0.0
    left_stick_y: float = 0.0
    c_stick_x: float = 0.0
    c_stick_y: float = 0.0
    l_trigger: float = 0.0
    r_trigger: float = 0.0


class NSO_GC_Controller_App:
    def __init__(self, root):
        self.root = root
        self.root.title("NSO GameCube Controller - Xbox Emulator")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # State
        self.connected = False
        self.emulating = False
        self.client: Optional[BleakClient] = None
        self.gamepad = None
        self.loop = None
        self.thread = None
        self.controller_address = DEFAULT_CONTROLLER_ADDRESS
        
        # Data
        self.calibration = CalibrationData()
        self.state = ControllerState()
        self.packet_count = 0
        
        # Calibration wizard state
        self.calibrating = False
        self.calibration_step = 0
        self.calibration_axis = ""
        self.calibration_samples = []
        
        # Load saved settings
        self.load_settings()
        
        # Build UI
        self.setup_ui()
        
        # Start UI update loop
        self.update_ui()
    
    def setup_ui(self):
        """Build the user interface."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 1: Main Control
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Controller")
        self.setup_main_tab()
        
        # Tab 2: Calibration
        self.cal_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cal_tab, text="Calibration")
        self.setup_calibration_tab()
        
        # Tab 3: Dead Zones
        self.dz_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dz_tab, text="Dead Zones")
        self.setup_deadzone_tab()
        
        # Tab 4: Settings
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")
        self.setup_settings_tab()
    
    def setup_main_tab(self):
        """Setup the main controller visualization tab."""
        # Connection frame
        conn_frame = ttk.LabelFrame(self.main_tab, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        self.status_label = ttk.Label(conn_frame, text="Status: Disconnected", foreground="red")
        self.status_label.pack(side="left")
        
        self.packet_label = ttk.Label(conn_frame, text="Packets: 0")
        self.packet_label.pack(side="left", padx=20)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(side="right")
        
        # Emulation frame
        emu_frame = ttk.LabelFrame(self.main_tab, text="Xbox 360 Emulation", padding=10)
        emu_frame.pack(fill="x", padx=10, pady=5)
        
        self.emu_status = ttk.Label(emu_frame, text="Emulation: Off", foreground="gray")
        self.emu_status.pack(side="left")
        
        self.emu_btn = ttk.Button(emu_frame, text="Start Emulation", command=self.toggle_emulation)
        self.emu_btn.pack(side="right")
        
        if not VGAMEPAD_AVAILABLE:
            self.emu_btn.config(state="disabled")
            self.emu_status.config(text="vgamepad not installed", foreground="red")
        
        # Visualization frame
        viz_frame = ttk.LabelFrame(self.main_tab, text="Live Input", padding=10)
        viz_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Canvas for stick visualization
        self.canvas = tk.Canvas(viz_frame, width=500, height=250, bg="#1a1a2e")
        self.canvas.pack(pady=10)
        
        # Buttons display
        btn_frame = ttk.Frame(viz_frame)
        btn_frame.pack(fill="x", pady=5)
        
        self.btn_labels = {}
        buttons = ["A", "B", "X", "Y", "Z", "Start", "Home", "Scrn", "Chat", "L", "R", "ZL", 
                   "↑", "↓", "←", "→"]
        for i, btn in enumerate(buttons):
            lbl = ttk.Label(btn_frame, text=f" {btn} ", background="gray", width=5)
            lbl.grid(row=i // 8, column=i % 8, padx=2, pady=2)
            self.btn_labels[btn] = lbl
        
        # Values display
        val_frame = ttk.Frame(viz_frame)
        val_frame.pack(fill="x", pady=5)
        
        self.lx_label = ttk.Label(val_frame, text="LX: 0.00")
        self.lx_label.grid(row=0, column=0, padx=10)
        self.ly_label = ttk.Label(val_frame, text="LY: 0.00")
        self.ly_label.grid(row=0, column=1, padx=10)
        self.cx_label = ttk.Label(val_frame, text="CX: 0.00")
        self.cx_label.grid(row=0, column=2, padx=10)
        self.cy_label = ttk.Label(val_frame, text="CY: 0.00")
        self.cy_label.grid(row=0, column=3, padx=10)
        self.lt_label = ttk.Label(val_frame, text="LT: 0%")
        self.lt_label.grid(row=0, column=4, padx=10)
        self.rt_label = ttk.Label(val_frame, text="RT: 0%")
        self.rt_label.grid(row=0, column=5, padx=10)
        
        # Raw values
        raw_frame = ttk.Frame(viz_frame)
        raw_frame.pack(fill="x", pady=5)
        
        self.raw_label = ttk.Label(raw_frame, text="Raw: --", font=("Courier", 9))
        self.raw_label.pack()
    
    def setup_calibration_tab(self):
        """Setup the calibration tab."""
        # Instructions
        inst_frame = ttk.LabelFrame(self.cal_tab, text="Instructions", padding=10)
        inst_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(inst_frame, text="Calibrate each axis by moving it to its extremes.\n"
                  "This helps correct for stick drift and ensures full range of motion.",
                  wraplength=700).pack()
        
        # Current calibration values
        val_frame = ttk.LabelFrame(self.cal_tab, text="Current Calibration Values", padding=10)
        val_frame.pack(fill="x", padx=10, pady=5)
        
        self.cal_labels = {}
        axes = [
            ("Left Stick X", "left_x", "12-bit"),
            ("Left Stick Y", "left_y", "8-bit"),
            ("C-Stick X", "c_x", "12-bit"),
            ("C-Stick Y", "c_y", "8-bit"),
            ("L Trigger", "l_trigger", "8-bit"),
            ("R Trigger", "r_trigger", "8-bit"),
        ]
        
        for i, (name, key, bits) in enumerate(axes):
            ttk.Label(val_frame, text=f"{name} ({bits}):").grid(row=i, column=0, sticky="w", padx=5, pady=2)
            lbl = ttk.Label(val_frame, text="Min: --- Center: --- Max: ---")
            lbl.grid(row=i, column=1, sticky="w", padx=5, pady=2)
            self.cal_labels[key] = lbl
        
        self.update_calibration_display()
        
        # Calibration wizard
        wiz_frame = ttk.LabelFrame(self.cal_tab, text="Calibration Wizard", padding=10)
        wiz_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.cal_instruction = ttk.Label(wiz_frame, text="Connect controller and click an axis to calibrate",
                                          font=("Arial", 12))
        self.cal_instruction.pack(pady=10)
        
        self.cal_progress = ttk.Progressbar(wiz_frame, length=400, mode='determinate')
        self.cal_progress.pack(pady=10)
        
        self.cal_value_label = ttk.Label(wiz_frame, text="Current value: ---", font=("Courier", 11))
        self.cal_value_label.pack(pady=5)
        
        # Calibration buttons
        cal_btn_frame = ttk.Frame(wiz_frame)
        cal_btn_frame.pack(pady=10)
        
        ttk.Button(cal_btn_frame, text="Left Stick X", 
                   command=lambda: self.start_calibration("left_x")).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(cal_btn_frame, text="Left Stick Y", 
                   command=lambda: self.start_calibration("left_y")).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(cal_btn_frame, text="C-Stick X", 
                   command=lambda: self.start_calibration("c_x")).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(cal_btn_frame, text="C-Stick Y", 
                   command=lambda: self.start_calibration("c_y")).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(cal_btn_frame, text="L Trigger", 
                   command=lambda: self.start_calibration("l_trigger")).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(cal_btn_frame, text="R Trigger", 
                   command=lambda: self.start_calibration("r_trigger")).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Button(cal_btn_frame, text="Reset to Defaults", 
                   command=self.reset_calibration).grid(row=1, column=2, columnspan=2, padx=5, pady=5)
    
    def setup_deadzone_tab(self):
        """Setup the dead zone adjustment tab."""
        # Instructions
        inst_frame = ttk.LabelFrame(self.dz_tab, text="Dead Zones", padding=10)
        inst_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(inst_frame, text="Dead zones prevent small stick movements from registering.\n"
                  "Increase if you experience drift, decrease for more precision.",
                  wraplength=700).pack()
        
        # Sliders
        slider_frame = ttk.LabelFrame(self.dz_tab, text="Adjust Dead Zones", padding=10)
        slider_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Left Stick
        ttk.Label(slider_frame, text="Left Stick Dead Zone:").grid(row=0, column=0, sticky="w", pady=10)
        self.left_dz_var = tk.DoubleVar(value=self.calibration.left_stick_deadzone)
        self.left_dz_slider = ttk.Scale(slider_frame, from_=0, to=0.5, variable=self.left_dz_var,
                                         orient="horizontal", length=300, command=self.update_deadzone)
        self.left_dz_slider.grid(row=0, column=1, padx=10)
        self.left_dz_label = ttk.Label(slider_frame, text=f"{self.calibration.left_stick_deadzone:.0%}")
        self.left_dz_label.grid(row=0, column=2)
        
        # C-Stick
        ttk.Label(slider_frame, text="C-Stick Dead Zone:").grid(row=1, column=0, sticky="w", pady=10)
        self.c_dz_var = tk.DoubleVar(value=self.calibration.c_stick_deadzone)
        self.c_dz_slider = ttk.Scale(slider_frame, from_=0, to=0.5, variable=self.c_dz_var,
                                      orient="horizontal", length=300, command=self.update_deadzone)
        self.c_dz_slider.grid(row=1, column=1, padx=10)
        self.c_dz_label = ttk.Label(slider_frame, text=f"{self.calibration.c_stick_deadzone:.0%}")
        self.c_dz_label.grid(row=1, column=2)
        
        # Triggers
        ttk.Label(slider_frame, text="Trigger Dead Zone:").grid(row=2, column=0, sticky="w", pady=10)
        self.trig_dz_var = tk.DoubleVar(value=self.calibration.trigger_deadzone)
        self.trig_dz_slider = ttk.Scale(slider_frame, from_=0, to=0.3, variable=self.trig_dz_var,
                                         orient="horizontal", length=300, command=self.update_deadzone)
        self.trig_dz_slider.grid(row=2, column=1, padx=10)
        self.trig_dz_label = ttk.Label(slider_frame, text=f"{self.calibration.trigger_deadzone:.0%}")
        self.trig_dz_label.grid(row=2, column=2)
        
        # Visualization
        viz_frame = ttk.LabelFrame(self.dz_tab, text="Dead Zone Visualization", padding=10)
        viz_frame.pack(fill="x", padx=10, pady=5)
        
        self.dz_canvas = tk.Canvas(viz_frame, width=400, height=150, bg="#1a1a2e")
        self.dz_canvas.pack(pady=10)
    
    def setup_settings_tab(self):
        """Setup the settings tab."""
        # Controller address
        addr_frame = ttk.LabelFrame(self.settings_tab, text="Controller Address", padding=10)
        addr_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(addr_frame, text="Bluetooth Address:").pack(side="left")
        self.addr_var = tk.StringVar(value=self.controller_address)
        self.addr_entry = ttk.Entry(addr_frame, textvariable=self.addr_var, width=25)
        self.addr_entry.pack(side="left", padx=10)
        ttk.Button(addr_frame, text="Scan", command=self.scan_for_controller).pack(side="left")
        
        # Save/Load
        file_frame = ttk.LabelFrame(self.settings_tab, text="Settings File", padding=10)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(file_frame, text="Save Settings", command=self.save_settings).pack(side="left", padx=5)
        ttk.Button(file_frame, text="Load Settings", command=self.load_settings_dialog).pack(side="left", padx=5)
        ttk.Button(file_frame, text="Reset All", command=self.reset_all_settings).pack(side="left", padx=5)
        
        # Button mapping info
        map_frame = ttk.LabelFrame(self.settings_tab, text="Button Mapping (Xbox 360)", padding=10)
        map_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        mapping_text = """
        GameCube          Xbox 360
        ─────────────────────────────
        A, B, X, Y    →   A, B, X, Y
        Z             →   RB (Right Bumper)
        ZL            →   LB (Left Bumper)
        Start         →   Start
        Screenshot    →   Back
        Home          →   Guide
        L Click       →   LS (Left Stick)
        R Click       →   RS (Right Stick)
        D-Pad         →   D-Pad
        L Trigger     →   LT
        R Trigger     →   RT
        Left Stick    →   Left Stick
        C-Stick       →   Right Stick
        """
        
        ttk.Label(map_frame, text=mapping_text, font=("Courier", 10), justify="left").pack()
    
    def update_calibration_display(self):
        """Update the calibration values display."""
        self.cal_labels["left_x"].config(
            text=f"Min: {self.calibration.left_x_min}  Center: {self.calibration.left_x_center}  Max: {self.calibration.left_x_max}")
        self.cal_labels["left_y"].config(
            text=f"Min: {self.calibration.left_y_min}  Center: {self.calibration.left_y_center}  Max: {self.calibration.left_y_max}")
        self.cal_labels["c_x"].config(
            text=f"Min: {self.calibration.c_x_min}  Center: {self.calibration.c_x_center}  Max: {self.calibration.c_x_max}")
        self.cal_labels["c_y"].config(
            text=f"Min: {self.calibration.c_y_min}  Center: {self.calibration.c_y_center}  Max: {self.calibration.c_y_max}")
        self.cal_labels["l_trigger"].config(
            text=f"Min: {self.calibration.l_trigger_min}  Max: {self.calibration.l_trigger_max}")
        self.cal_labels["r_trigger"].config(
            text=f"Min: {self.calibration.r_trigger_min}  Max: {self.calibration.r_trigger_max}")
    
    def update_deadzone(self, *args):
        """Update dead zone values from sliders."""
        self.calibration.left_stick_deadzone = self.left_dz_var.get()
        self.calibration.c_stick_deadzone = self.c_dz_var.get()
        self.calibration.trigger_deadzone = self.trig_dz_var.get()
        
        self.left_dz_label.config(text=f"{self.calibration.left_stick_deadzone:.0%}")
        self.c_dz_label.config(text=f"{self.calibration.c_stick_deadzone:.0%}")
        self.trig_dz_label.config(text=f"{self.calibration.trigger_deadzone:.0%}")
    
    def start_calibration(self, axis: str):
        """Start calibration wizard for an axis."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Please connect the controller first.")
            return
        
        self.calibrating = True
        self.calibration_axis = axis
        self.calibration_step = 0
        self.calibration_samples = []
        
        if axis in ["l_trigger", "r_trigger"]:
            self.cal_instruction.config(text=f"Release {axis.replace('_', ' ').title()} completely, then click Continue")
        else:
            self.cal_instruction.config(text=f"Move {axis.replace('_', ' ').title()} to MINIMUM position, then click Continue")
        
        self.cal_progress["value"] = 0
        
        # Show continue button
        if hasattr(self, 'cal_continue_btn'):
            self.cal_continue_btn.destroy()
        self.cal_continue_btn = ttk.Button(self.cal_tab, text="Continue", command=self.calibration_next_step)
        self.cal_continue_btn.pack(pady=10)
    
    def calibration_next_step(self):
        """Process calibration step."""
        if not self.calibration_samples:
            messagebox.showwarning("No Data", "No samples collected. Make sure controller is connected.")
            return
        
        # Get average of samples
        avg_value = sum(self.calibration_samples) // len(self.calibration_samples)
        
        axis = self.calibration_axis
        
        if axis in ["l_trigger", "r_trigger"]:
            # Triggers only have min and max
            if self.calibration_step == 0:
                setattr(self.calibration, f"{axis}_min", avg_value)
                self.calibration_step = 1
                self.calibration_samples = []
                self.cal_instruction.config(text=f"Press {axis.replace('_', ' ').title()} fully, then click Continue")
                self.cal_progress["value"] = 50
            else:
                setattr(self.calibration, f"{axis}_max", avg_value)
                self.finish_calibration()
        else:
            # Sticks have min, center, max
            if self.calibration_step == 0:
                setattr(self.calibration, f"{axis}_min", avg_value)
                self.calibration_step = 1
                self.calibration_samples = []
                self.cal_instruction.config(text=f"Release {axis.replace('_', ' ').title()} to CENTER, then click Continue")
                self.cal_progress["value"] = 33
            elif self.calibration_step == 1:
                setattr(self.calibration, f"{axis}_center", avg_value)
                self.calibration_step = 2
                self.calibration_samples = []
                self.cal_instruction.config(text=f"Move {axis.replace('_', ' ').title()} to MAXIMUM position, then click Continue")
                self.cal_progress["value"] = 66
            else:
                setattr(self.calibration, f"{axis}_max", avg_value)
                self.finish_calibration()
    
    def finish_calibration(self):
        """Finish calibration wizard."""
        self.calibrating = False
        self.cal_progress["value"] = 100
        self.cal_instruction.config(text="Calibration complete!")
        self.update_calibration_display()
        
        if hasattr(self, 'cal_continue_btn'):
            self.cal_continue_btn.destroy()
        
        self.save_settings()
    
    def reset_calibration(self):
        """Reset calibration to defaults."""
        self.calibration = CalibrationData()
        self.update_calibration_display()
        self.left_dz_var.set(self.calibration.left_stick_deadzone)
        self.c_dz_var.set(self.calibration.c_stick_deadzone)
        self.trig_dz_var.set(self.calibration.trigger_deadzone)
        self.update_deadzone()
    
    def toggle_connection(self):
        """Connect or disconnect from controller."""
        if self.connected:
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        """Connect to the controller."""
        self.controller_address = self.addr_var.get()
        self.connect_btn.config(state="disabled")
        self.status_label.config(text="Status: Connecting...", foreground="orange")
        
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()
    
    def disconnect(self):
        """Disconnect from controller."""
        self.connected = False
        if self.emulating:
            self.toggle_emulation()
    
    def run_async_loop(self):
        """Run the async BLE loop in a thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.async_connect())
    
    async def async_connect(self):
        """Async connection handler."""
        try:
            device = await BleakScanner.find_device_by_address(self.controller_address, timeout=10.0)
            
            if not device:
                self.root.after(0, lambda: self.connection_failed("Controller not found"))
                return
            
            self.client = BleakClient(device)
            await self.client.connect(timeout=20.0)
            await self.client.start_notify(INPUT_CHAR_UUID, self.notification_handler)
            
            self.connected = True
            self.root.after(0, self.connection_success)
            
            while self.connected:
                await asyncio.sleep(0.1)
            
            await self.client.stop_notify(INPUT_CHAR_UUID)
            await self.client.disconnect()
            self.root.after(0, self.disconnected)
            
        except Exception as e:
            self.root.after(0, lambda: self.connection_failed(str(e)))
    
    def notification_handler(self, sender, data):
        """Handle incoming BLE notifications."""
        self.packet_count += 1
        self.parse_packet(data)
        
        # Update Xbox controller if emulating
        if self.emulating and self.gamepad:
            self.update_gamepad()
    
    def parse_packet(self, data: bytes):
        """Parse controller packet."""
        if len(data) < 62:
            return
        
        # Buttons
        byte4 = data[4]
        self.state.a = bool(byte4 & BYTE4_A)
        self.state.b = bool(byte4 & BYTE4_B)
        self.state.x = bool(byte4 & BYTE4_X)
        self.state.y = bool(byte4 & BYTE4_Y)
        self.state.z = bool(byte4 & BYTE4_Z)
        self.state.r_click = bool(byte4 & BYTE4_R_CLICK)
        
        byte5 = data[5]
        self.state.start = bool(byte5 & BYTE5_START)
        self.state.home = bool(byte5 & BYTE5_HOME)
        self.state.screenshot = bool(byte5 & BYTE5_SCREENSHOT)
        self.state.chat = bool(byte5 & BYTE5_CHAT)
        
        byte6 = data[6]
        self.state.dpad_up = bool(byte6 & BYTE6_DPAD_UP)
        self.state.dpad_down = bool(byte6 & BYTE6_DPAD_DOWN)
        self.state.dpad_left = bool(byte6 & BYTE6_DPAD_LEFT)
        self.state.dpad_right = bool(byte6 & BYTE6_DPAD_RIGHT)
        self.state.l_click = bool(byte6 & BYTE6_L_CLICK)
        self.state.zl = bool(byte6 & BYTE6_ZL)
        
        # Raw analog values
        self.state.left_x_raw = data[10] + ((data[11] & 0x0F) << 8)
        self.state.left_y_raw = data[12]
        self.state.c_x_raw = data[13] + ((data[14] & 0x0F) << 8)
        self.state.c_y_raw = data[15]
        self.state.l_trigger_raw = data[60]
        self.state.r_trigger_raw = data[61]
        
        # Calibrated values
        self.state.left_stick_x = self.apply_calibration(
            self.state.left_x_raw,
            self.calibration.left_x_min,
            self.calibration.left_x_center,
            self.calibration.left_x_max,
            self.calibration.left_stick_deadzone
        )
        self.state.left_stick_y = self.apply_calibration(
            self.state.left_y_raw,
            self.calibration.left_y_min,
            self.calibration.left_y_center,
            self.calibration.left_y_max,
            self.calibration.left_stick_deadzone
        )
        self.state.c_stick_x = self.apply_calibration(
            self.state.c_x_raw,
            self.calibration.c_x_min,
            self.calibration.c_x_center,
            self.calibration.c_x_max,
            self.calibration.c_stick_deadzone
        )
        self.state.c_stick_y = self.apply_calibration(
            self.state.c_y_raw,
            self.calibration.c_y_min,
            self.calibration.c_y_center,
            self.calibration.c_y_max,
            self.calibration.c_stick_deadzone
        )
        self.state.l_trigger = self.apply_trigger_calibration(
            self.state.l_trigger_raw,
            self.calibration.l_trigger_min,
            self.calibration.l_trigger_max,
            self.calibration.trigger_deadzone
        )
        self.state.r_trigger = self.apply_trigger_calibration(
            self.state.r_trigger_raw,
            self.calibration.r_trigger_min,
            self.calibration.r_trigger_max,
            self.calibration.trigger_deadzone
        )
        
        # Collect calibration samples
        if self.calibrating:
            axis = self.calibration_axis
            if axis == "left_x":
                self.calibration_samples.append(self.state.left_x_raw)
            elif axis == "left_y":
                self.calibration_samples.append(self.state.left_y_raw)
            elif axis == "c_x":
                self.calibration_samples.append(self.state.c_x_raw)
            elif axis == "c_y":
                self.calibration_samples.append(self.state.c_y_raw)
            elif axis == "l_trigger":
                self.calibration_samples.append(self.state.l_trigger_raw)
            elif axis == "r_trigger":
                self.calibration_samples.append(self.state.r_trigger_raw)
            
            # Keep last 20 samples
            if len(self.calibration_samples) > 20:
                self.calibration_samples.pop(0)
    
    def apply_calibration(self, raw: int, min_val: int, center: int, max_val: int, deadzone: float) -> float:
        """Apply calibration to a stick axis."""
        if raw < center:
            normalized = (raw - center) / (center - min_val)
        else:
            normalized = (raw - center) / (max_val - center)
        
        normalized = max(-1.0, min(1.0, normalized))
        
        # Apply deadzone
        if abs(normalized) < deadzone:
            return 0.0
        
        # Scale remaining range
        if normalized > 0:
            return (normalized - deadzone) / (1.0 - deadzone)
        else:
            return (normalized + deadzone) / (1.0 - deadzone)
    
    def apply_trigger_calibration(self, raw: int, min_val: int, max_val: int, deadzone: float) -> float:
        """Apply calibration to a trigger."""
        normalized = (raw - min_val) / (max_val - min_val)
        normalized = max(0.0, min(1.0, normalized))
        
        if normalized < deadzone:
            return 0.0
        
        return (normalized - deadzone) / (1.0 - deadzone)
    
    def update_gamepad(self):
        """Update the virtual Xbox controller."""
        if not self.gamepad:
            return
        
        self.gamepad.reset()
        
        # Buttons
        if self.state.a:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
        if self.state.b:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
        if self.state.x:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
        if self.state.y:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
        if self.state.z:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)
        if self.state.zl:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
        if self.state.start:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_START)
        if self.state.screenshot:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK)
        if self.state.home:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE)
        if self.state.l_click:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
        if self.state.r_click:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
        if self.state.dpad_up:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
        if self.state.dpad_down:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
        if self.state.dpad_left:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
        if self.state.dpad_right:
            self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
        
        # Analog
        self.gamepad.left_joystick_float(self.state.left_stick_x, self.state.left_stick_y)
        self.gamepad.right_joystick_float(self.state.c_stick_x, self.state.c_stick_y)
        self.gamepad.left_trigger_float(self.state.l_trigger)
        self.gamepad.right_trigger_float(self.state.r_trigger)
        
        self.gamepad.update()
    
    def connection_success(self):
        """Handle successful connection."""
        self.status_label.config(text="Status: Connected", foreground="green")
        self.connect_btn.config(text="Disconnect", state="normal")
    
    def connection_failed(self, error):
        """Handle connection failure."""
        self.status_label.config(text=f"Status: Failed", foreground="red")
        self.connect_btn.config(text="Connect", state="normal")
        messagebox.showerror("Connection Error", f"Failed to connect: {error}")
    
    def disconnected(self):
        """Handle disconnection."""
        self.status_label.config(text="Status: Disconnected", foreground="red")
        self.connect_btn.config(text="Connect", state="normal")
    
    def toggle_emulation(self):
        """Start or stop Xbox emulation."""
        if not VGAMEPAD_AVAILABLE:
            return
        
        if self.emulating:
            self.emulating = False
            if self.gamepad:
                self.gamepad.reset()
                self.gamepad.update()
                self.gamepad = None
            self.emu_status.config(text="Emulation: Off", foreground="gray")
            self.emu_btn.config(text="Start Emulation")
        else:
            if not self.connected:
                messagebox.showwarning("Not Connected", "Please connect the controller first.")
                return
            
            try:
                self.gamepad = vg.VX360Gamepad()
                self.emulating = True
                self.emu_status.config(text="Emulation: Active", foreground="green")
                self.emu_btn.config(text="Stop Emulation")
            except Exception as e:
                messagebox.showerror("Emulation Error", f"Failed to create virtual controller: {e}")
    
    def update_ui(self):
        """Update UI elements periodically."""
        # Update packet count
        self.packet_label.config(text=f"Packets: {self.packet_count}")
        
        # Update value labels
        self.lx_label.config(text=f"LX: {self.state.left_stick_x:+.2f}")
        self.ly_label.config(text=f"LY: {self.state.left_stick_y:+.2f}")
        self.cx_label.config(text=f"CX: {self.state.c_stick_x:+.2f}")
        self.cy_label.config(text=f"CY: {self.state.c_stick_y:+.2f}")
        self.lt_label.config(text=f"LT: {self.state.l_trigger:.0%}")
        self.rt_label.config(text=f"RT: {self.state.r_trigger:.0%}")
        
        # Update raw values
        self.raw_label.config(text=f"Raw: LX={self.state.left_x_raw} LY={self.state.left_y_raw} "
                                   f"CX={self.state.c_x_raw} CY={self.state.c_y_raw} "
                                   f"LT={self.state.l_trigger_raw} RT={self.state.r_trigger_raw}")
        
        # Update button indicators
        btn_map = {
            "A": self.state.a, "B": self.state.b, "X": self.state.x, "Y": self.state.y,
            "Z": self.state.z, "Start": self.state.start, "Home": self.state.home,
            "Scrn": self.state.screenshot, "Chat": self.state.chat,
            "L": self.state.l_click, "R": self.state.r_click, "ZL": self.state.zl,
            "↑": self.state.dpad_up, "↓": self.state.dpad_down,
            "←": self.state.dpad_left, "→": self.state.dpad_right,
        }
        
        for btn, pressed in btn_map.items():
            if btn in self.btn_labels:
                self.btn_labels[btn].config(background="green" if pressed else "gray")
        
        # Update calibration display if calibrating
        if self.calibrating and self.calibration_samples:
            avg = sum(self.calibration_samples) // len(self.calibration_samples)
            self.cal_value_label.config(text=f"Current value: {avg}")
        
        # Draw stick visualizations
        self.draw_sticks()
        self.draw_deadzone_viz()
        
        # Schedule next update
        self.root.after(33, self.update_ui)  # ~30fps
    
    def draw_sticks(self):
        """Draw stick position visualizations."""
        self.canvas.delete("all")
        
        # Left stick
        self.draw_stick_circle(100, 125, 80, self.state.left_stick_x, self.state.left_stick_y, 
                               self.calibration.left_stick_deadzone, "Left Stick")
        
        # C-Stick
        self.draw_stick_circle(300, 125, 80, self.state.c_stick_x, self.state.c_stick_y,
                               self.calibration.c_stick_deadzone, "C-Stick")
        
        # Triggers (spaced apart to avoid overlap)
        self.draw_trigger_bar(420, 50, 30, 150, self.state.l_trigger, "L")
        self.draw_trigger_bar(460, 50, 30, 150, self.state.r_trigger, "R")
    
    def draw_stick_circle(self, cx, cy, radius, x, y, deadzone, label):
        """Draw a single stick visualization."""
        # Outer circle
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                outline="#4a4a6a", width=2)

        # Deadzone circle
        dz_radius = radius * deadzone
        self.canvas.create_oval(cx - dz_radius, cy - dz_radius, cx + dz_radius, cy + dz_radius,
                                outline="#6a4a4a", width=1, dash=(2, 2))

        # Crosshairs
        self.canvas.create_line(cx - radius, cy, cx + radius, cy, fill="#3a3a5a")
        self.canvas.create_line(cx, cy - radius, cx, cy + radius, fill="#3a3a5a")

        # Stick position - grey when in deadzone, green when active
        stick_x = cx + (x * radius * 0.9)
        stick_y = cy - (y * radius * 0.9)

        # Check if stick is within deadzone (output is 0 when in deadzone)
        in_deadzone = (x == 0.0 and y == 0.0)
        fill_color = "#808080" if in_deadzone else "#00ff00"
        outline_color = "#606060" if in_deadzone else "#00aa00"

        self.canvas.create_oval(stick_x - 8, stick_y - 8, stick_x + 8, stick_y + 8,
                                fill=fill_color, outline=outline_color)

        # Label
        self.canvas.create_text(cx, cy + radius + 15, text=label, fill="white")
    
    def draw_trigger_bar(self, x, y, width, height, value, label):
        """Draw a trigger bar visualization."""
        # Background
        self.canvas.create_rectangle(x, y, x + width, y + height, outline="#4a4a6a", width=2)

        # Fill - grey when in deadzone (value is 0), green when active
        fill_height = height * value
        in_deadzone = (value == 0.0)
        fill_color = "#808080" if in_deadzone else "#00ff00"

        # Show a small bar even when in deadzone to indicate trigger position
        if in_deadzone:
            # Draw a thin grey bar at the bottom to show it's in deadzone
            self.canvas.create_rectangle(x + 2, y + height - 5, x + width - 2, y + height - 2,
                                          fill=fill_color, outline="")
        else:
            self.canvas.create_rectangle(x + 2, y + height - fill_height, x + width - 2, y + height - 2,
                                          fill=fill_color, outline="")

        # Label
        self.canvas.create_text(x + width // 2, y + height + 15, text=label, fill="white")
    
    def draw_deadzone_viz(self):
        """Draw deadzone visualization."""
        self.dz_canvas.delete("all")
        
        # Draw stick deadzone circle
        cx, cy = 100, 75
        radius = 60
        
        self.dz_canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    outline="#4a4a6a", width=2)
        
        dz = self.calibration.left_stick_deadzone
        dz_radius = radius * dz
        self.dz_canvas.create_oval(cx - dz_radius, cy - dz_radius, cx + dz_radius, cy + dz_radius,
                                    fill="#4a2a2a", outline="#8a4a4a")
        
        self.dz_canvas.create_text(cx, cy + radius + 15, text=f"Stick DZ: {dz:.0%}", fill="white")
        
        # Draw trigger deadzone
        tx, ty = 250, 25
        t_width, t_height = 30, 100
        
        self.dz_canvas.create_rectangle(tx, ty, tx + t_width, ty + t_height,
                                         outline="#4a4a6a", width=2)
        
        tdz = self.calibration.trigger_deadzone
        dz_height = t_height * tdz
        self.dz_canvas.create_rectangle(tx + 2, ty + t_height - dz_height, tx + t_width - 2, ty + t_height - 2,
                                         fill="#4a2a2a", outline="")
        
        self.dz_canvas.create_text(tx + t_width // 2, ty + t_height + 15, text=f"Trig DZ: {tdz:.0%}", fill="white")
    
    def scan_for_controller(self):
        """Scan for Nintendo controllers."""
        messagebox.showinfo("Scanning", "Scanning for controllers...\nMake sure your controller is in pairing mode.")
        
        async def do_scan():
            devices = await BleakScanner.discover(timeout=5.0)
            nintendo_devices = [d for d in devices if d.name and "Nintendo" in d.name]
            return nintendo_devices
        
        def run_scan():
            loop = asyncio.new_event_loop()
            devices = loop.run_until_complete(do_scan())
            loop.close()
            
            if devices:
                device = devices[0]
                self.root.after(0, lambda: self.addr_var.set(device.address))
                self.root.after(0, lambda: messagebox.showinfo("Found", f"Found: {device.name}\nAddress: {device.address}"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("Not Found", "No Nintendo controllers found."))
        
        threading.Thread(target=run_scan, daemon=True).start()
    
    def save_settings(self):
        """Save settings to file."""
        settings = {
            "controller_address": self.controller_address,
            "calibration": asdict(self.calibration)
        }
        
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
            print(f"Settings saved to {SETTINGS_FILE}")
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def load_settings(self):
        """Load settings from file."""
        if not os.path.exists(SETTINGS_FILE):
            return
        
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
            
            self.controller_address = settings.get("controller_address", DEFAULT_CONTROLLER_ADDRESS)
            
            cal_data = settings.get("calibration", {})
            for key, value in cal_data.items():
                if hasattr(self.calibration, key):
                    setattr(self.calibration, key, value)
            
            print(f"Settings loaded from {SETTINGS_FILE}")
        except Exception as e:
            print(f"Failed to load settings: {e}")
    
    def load_settings_dialog(self):
        """Open file dialog to load settings."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            initialfile=SETTINGS_FILE
        )
        if filepath:
            try:
                with open(filepath, "r") as f:
                    settings = json.load(f)
                
                self.controller_address = settings.get("controller_address", DEFAULT_CONTROLLER_ADDRESS)
                self.addr_var.set(self.controller_address)
                
                cal_data = settings.get("calibration", {})
                for key, value in cal_data.items():
                    if hasattr(self.calibration, key):
                        setattr(self.calibration, key, value)
                
                # Update UI
                self.update_calibration_display()
                self.left_dz_var.set(self.calibration.left_stick_deadzone)
                self.c_dz_var.set(self.calibration.c_stick_deadzone)
                self.trig_dz_var.set(self.calibration.trigger_deadzone)
                
                messagebox.showinfo("Loaded", f"Settings loaded from {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load settings: {e}")
    
    def reset_all_settings(self):
        """Reset all settings to defaults."""
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            self.reset_calibration()
            self.controller_address = DEFAULT_CONTROLLER_ADDRESS
            self.addr_var.set(self.controller_address)
            self.save_settings()
    
    def on_close(self):
        """Handle window close."""
        self.save_settings()
        self.connected = False
        if self.gamepad:
            self.gamepad.reset()
            self.gamepad.update()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = NSO_GC_Controller_App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
