# The apps

The apps are the designer in a window of their own, with everything included.
They need no Python. Download them from the
[releases page](https://github.com/NullMember/PyxelWidgets/releases).

## Desktop (macOS, Windows, Linux)

| System | Download | Install |
|--------|----------|---------|
| macOS 14+ (Apple silicon) | `PyxelWidgets-<version>-macos-arm64.zip` | Unzip, move *PyxelWidgets* to Applications, open it. |
| Windows 10/11 | `PyxelWidgets-<version>-windows-x86_64.zip` | Unzip anywhere, run `PyxelWidgets.exe`. SmartScreen may warn about an unknown program: *More info → Run anyway*. |
| Linux x86_64 (Ubuntu 22.04 or newer, or similar; tried on a Steam Deck's desktop mode) | `PyxelWidgets-<version>-linux-x86_64.tar.gz` | `tar xzf` it, run `PyxelWidgets/PyxelWidgets`. Debian/Ubuntu may need `sudo apt install libxcb-cursor0`. |

On first use, macOS asks whether PyxelWidgets may find devices on your local
network (for Web Grid, OSC and network MIDI) and use Bluetooth (for Bluetooth
MIDI devices). Allow what you use. The keyboard and mouse output also needs
System Settings > Privacy & Security > Accessibility.

The window works like the designer in a browser (see [the designer](designer.md)),
plus menus: File, Mode (Edit, Try, Perform) and Transport.

The apps have been tried on macOS, Windows and a Steam Deck (SteamOS).

With Python installed, `pip install "pyxelwidgets[app]"` then
`pyxelwidgets app` gives the same window.

### Player mode

To play a finished layout, open it in Perform mode with the transport
running:

```sh
PyxelWidgets layout.json --perform --play                    # Windows, Linux
open -a PyxelWidgets --args layout.json --perform --play     # macOS
```

`--offline` opens without connecting devices and outputs.

### Without a window

`--headless` plays a layout on its devices and outputs, like
`pyxelwidgets run`: for a computer that sits under the desk, or a login item.

```sh
PyxelWidgets --headless layout.json --play
PyxelWidgets.app/Contents/MacOS/PyxelWidgets --headless layout.json --play   # macOS
```

`--server` runs only the designer's server: open the address it prints in any
browser. Add `--host 0.0.0.0` to let other computers on your network open it
(the address carries a key); the *Share* button does the same while the app
runs.

### Where things are

The app writes what it prints to `PyxelWidgets.log`, new at each launch.
Please attach it to bug reports. It's in:

- macOS: `~/Library/Application Support/PyxelWidgets/`
- Windows: `%APPDATA%\PyxelWidgets\`
- Linux: `~/.local/share/PyxelWidgets/`

Your own snippets are in `~/.pyxelwidgets/snippets`, and remembered Bluetooth
devices are in `~/.pyxelwidgets/bluetooth.json`.

## Android

`PyxelWidgets-<version>-android.apk` runs on Android 7 and later (64-bit
phones and tablets). Open the file on the phone and allow your browser or file
manager to install apps when Android asks.

The app is the designer, sized for a landscape screen, with:

- **USB MIDI:** plug a controller in through a USB-C (OTG) adapter. A
  Launchpad works like on a computer.
- **Bluetooth MIDI:** the *Bluetooth* button under Devices scans, pairs and
  connects BLE MIDI devices. The phone can also be a Bluetooth MIDI device
  for a computer: add a *Bluetooth MIDI (BLE)* output, and the phone
  advertises under its Bluetooth name.
- **Network MIDI:** add a *Network MIDI* output. The phone announces it, and on
  a Mac it shows in Audio MIDI Setup's network *Directory*.
- **A touch grid:** in Perform mode, *Play on this screen* turns the screen
  into pads (multi-touch). *◀ Designer* or Back returns.
- **Playing in the background:** the layout keeps playing with the screen off
  or another app in front. A notification says it's running; its *Quit*
  stops it.
- **Editing from a computer:** *Share* in the toolbar shows an address to open
  on a laptop on the same Wi-Fi.

Layouts are saved in the app's folder,
`Android/data/com.nullmember.pyxelwidgets/files`, which a computer can reach
over USB. *Import from this computer* in the File menu opens a layout from
anywhere on the phone, and *Download* saves one wherever you choose.
