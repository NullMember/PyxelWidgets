# Packaging the PyxelWidgets app

The app is the designer in a window of its own (`pyxelwidgets.designer.window`,
the system's web view through pywebview). The same thing runs from a
development install with `pyxelwidgets app [layout.json]`.

Each system's build has to be made on that system:

```sh
python packaging/build.py            # fresh build environment in build/app-venv
python packaging/build.py --reuse    # keep its packages: faster rebuilds
```

The result goes into `dist/`, along with a zip named
`PyxelWidgets-<version>-<system>-<machine>.zip`:

| System  | Result                          | Web view                                   |
|---------|---------------------------------|--------------------------------------------|
| macOS   | `dist/PyxelWidgets.app`         | WKWebView (built in)                       |
| Windows | `dist/PyxelWidgets/PyxelWidgets.exe` | WebView2 (built into Windows 10/11)   |
| Linux   | `dist/PyxelWidgets/PyxelWidgets` | Qt WebEngine (inside the build)           |

The build includes the `osc`, `network`, `desktop` and `app` extras, so
REAPER/OSC, network MIDI, keyboard/mouse output and the window all work.

## Requirements

- **All systems:** Python 3.10 or later with `venv`, and an internet connection
  for the first build (it downloads the packages).
- **macOS:** nothing else. The app is signed ad hoc, so on another Mac the
  first launch needs right-click → Open (or
  `xattr -dr com.apple.quarantine PyxelWidgets.app`). On first launch macOS
  asks about the local network (WebGrid, OSC, network MIDI). The first launch
  of a new build takes several seconds while macOS checks it.
- **Windows:** use Python 3.12 or 3.13 from python.org (pywebview needs
  pythonnet, which may not support the newest Python yet). SmartScreen warns
  about an unsigned program: *More info → Run anyway*.
- **Linux:** a desktop session (X11 or Wayland). Qt's web view comes with the
  build. Ubuntu/Debian may need `sudo apt install libxcb-cursor0` for Qt and
  `python3-venv`. MIDI uses ALSA, so the user has to be able to open
  `/dev/snd/seq` (normally the case).

## Player mode

```sh
PyxelWidgets layout.json --perform --play         # Windows/Linux
open -a PyxelWidgets --args layout.json --perform --play   # macOS
```

`--perform` opens in Perform mode (no editing grid; devices, outputs and the
transport keep running), `--play` starts the transport, `--offline` doesn't
connect devices. The Mode menu switches between Edit, Try and Perform.

## Where things are kept

The app's output (errors, device messages) goes to `PyxelWidgets.log`,
rewritten at each launch, in:

- macOS: `~/Library/Application Support/PyxelWidgets/`
- Windows: `%APPDATA%\PyxelWidgets\`
- Linux: `~/.local/share/PyxelWidgets/`

Please send that file along with test reports.

The window's storage (preferences, the clipboard, recent files) lives in the
web view's storage for `http://127.0.0.1:8770`. The server takes the first
free port from 8770 to 8779, so a second copy of the app starts with
separate preferences. Snippets you save go to `~/.pyxelwidgets/snippets`, as
with the browser designer.

## Icon

`packaging/icon.py` draws the icon with numpy and writes PNG/ICO/ICNS files
with the standard library. Running it alone rewrites the designer's favicon
(`src/pyxelwidgets/designer/static/icon.png`).
