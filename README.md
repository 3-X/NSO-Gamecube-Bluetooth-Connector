# NSO GameCube Controller - Xbox 360 Emulator

Use your Nintendo Switch Online GameCube controller as an Xbox 360 controller on Windows via Bluetooth.

## Features

- **Xbox 360 Controller Emulation** - Works with any game that supports Xbox controllers
- **Live Input Visualization** - See your inputs in real-time
- **Stick Calibration Wizard** - Fix drift and ensure full range of motion
- **Dead Zone Adjustment** - Fine-tune stick sensitivity
- **Save/Load Settings** - Your calibration persists between sessions

## Download

### Assets

| File | Description |
|------|-------------|
| [**NSO_GC_Controller_Setup.exe**](https://github.com/jschultz299/NSO-GC-Adapter/releases/latest/download/NSO_GC_Controller_Setup.exe) | Windows Installer (recommended) |
| [**NSO_GC_Controller.exe**](https://github.com/jschultz299/NSO-GC-Adapter/releases/latest/download/NSO_GC_Controller.exe) | Standalone executable (portable) |

> See all versions on the [Releases](https://github.com/jschultz299/NSO-GC-Adapter/releases) page

## Requirements

### ViGEmBus Driver (Required)

This application requires the **ViGEmBus driver** to emulate an Xbox 360 controller.

1. Download the latest ViGEmBus release: https://github.com/nefarius/ViGEmBus/releases/latest
2. Run `ViGEmBus_Setup_x64.msi` (or x86 for 32-bit systems)
3. **Restart your computer** after installation

The installer will prompt you to download ViGEmBus if it's not detected.

## Installation

1. **Install ViGEmBus** (see above)
2. **Download and run** [NSO_GC_Controller_Setup.exe](./installer_output/NSO_GC_Controller_Setup.exe)
3. Follow the installation wizard
4. Launch "NSO GameCube Controller" from the Start Menu or Desktop

## Usage

### Connecting Your Controller

1. Put your NSO GameCube controller in pairing mode (hold the sync button)
2. Pair it with Windows via Bluetooth settings
3. Launch the application
4. Click **"Scan"** to find your controller, or enter the Bluetooth address manually
5. Click **"Connect"**

### Starting Emulation

1. After connecting, click **"Start Emulation"**
2. Your controller now appears as an Xbox 360 controller to games
3. Test it in Windows Game Controllers or any game

### Calibration

If your sticks have drift or don't reach full range:

1. Go to the **Calibration** tab
2. Click the axis you want to calibrate (e.g., "Left Stick X")
3. Follow the on-screen instructions to move the stick to min/center/max positions
4. Settings are saved automatically

### Dead Zones

Adjust dead zones in the **Dead Zones** tab if you experience:
- **Drift**: Increase the dead zone
- **Lack of precision**: Decrease the dead zone

## Button Mapping

| GameCube | Xbox 360 |
|----------|----------|
| A, B, X, Y | A, B, X, Y |
| Z | RB (Right Bumper) |
| ZL | LB (Left Bumper) |
| Start | Start |
| Screenshot | Back |
| Home | Guide |
| L Click | LS (Left Stick) |
| R Click | RS (Right Stick) |
| D-Pad | D-Pad |
| L Trigger | LT |
| R Trigger | RT |
| Left Stick | Left Stick |
| C-Stick | Right Stick |

## Troubleshooting

### "ViGEmBus driver not installed"

1. Download ViGEmBus from https://github.com/nefarius/ViGEmBus/releases/latest
2. Install it and restart your computer
3. Relaunch the application

### Controller not found

1. Make sure the controller is paired in Windows Bluetooth settings
2. Check that the controller is powered on
3. Try clicking "Scan" to auto-detect the controller address

### Emulation not working in games

1. Make sure emulation is active (green "Emulation: Active" status)
2. Some games may need to be restarted after starting emulation
3. Check Windows Game Controllers to verify the Xbox controller appears

## Building from Source

### Requirements

- Python 3.10+
- Windows 10/11

### Setup

```bash
pip install vgamepad bleak
```

### Run

```bash
python nso_gc_gui_2.py
```

### Build Executable

```bash
# Install build tools
pip install pyinstaller

# Run build script
build.bat
```

The standalone exe will be in `dist/NSO_GC_Controller.exe`.

To create an installer, install [Inno Setup](https://jrsoftware.org/isdl.php) and run `build.bat` again.

## License

MIT License
