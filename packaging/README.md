# Packaging the PyxelWidgets app

The app is the designer in a window of its own (`pyxelwidgets.designer.window`,
the system's web view through pywebview). The same thing runs from a
development install with `pyxelwidgets app [layout.json]`.

Each system's build has to be made on that system:

```sh
python packaging/build.py            # fresh build environment in build/app-venv
python packaging/build.py --reuse    # keep its packages: faster rebuilds
```

The result goes into `dist/`, along with an archive named
`PyxelWidgets-<version>-<system>-<machine>.zip` (`.tar.gz` on Linux, which
keeps the build's symlinks):

| System  | Result                          | Web view                                   |
|---------|---------------------------------|--------------------------------------------|
| macOS   | `dist/PyxelWidgets.app`         | WKWebView (built in)                       |
| Windows | `dist/PyxelWidgets/PyxelWidgets.exe` | WebView2 (built into Windows 10/11)   |
| Linux   | `dist/PyxelWidgets/PyxelWidgets` | Qt WebEngine (inside the build, trimmed to what the window loads) |

The build includes the `osc`, `network`, `desktop` and `app` extras, so
REAPER/OSC, network MIDI, keyboard/mouse output and the window all work.

## Releases

`.github/workflows/release.yml` builds the macOS, Windows and Linux apps with
this script, plus the Android app and the Python package, on every version tag
(`v1.2.3`, matching `pyxelwidgets.__version__` and a `## 1.2.3` section in
`CHANGELOG.md`), and publishes them to a GitHub release and PyPI. Run by hand
(Actions > Release > Run workflow) it only builds.

**macOS signing.** With `PYXELWIDGETS_SIGN_IDENTITY` set to a "Developer ID
Application" certificate in the keychain, the build signs every binary with
the hardened runtime (`packaging/entitlements.plist`) instead of ad hoc. With
notary credentials it's also notarized and stapled, so it opens on any Mac
without warnings: `PYXELWIDGETS_NOTARY_PROFILE` (a profile saved with
`xcrun notarytool store-credentials`) or `PYXELWIDGETS_NOTARY_KEY` (path to an
App Store Connect API key `.p8`) with `PYXELWIDGETS_NOTARY_KEY_ID` and
`PYXELWIDGETS_NOTARY_ISSUER`. CI gets them from the secrets listed at the top
of `release.yml`.

**Android signing.** `android/keystore.properties` (not committed) or the
`PYXELWIDGETS_STORE_FILE`, `_STORE_PASSWORD`, `_KEY_ALIAS` and
`_KEY_PASSWORD` environment variables give the release key
(`store_file = ...`, `store_password = ...`, `key_alias = ...`,
`key_password = ...`); without it, release builds use the debug key. The
version comes from the Python package (versionCode = major·10000 +
minor·100 + patch).

## Requirements

- **All systems:** Python 3.10 or later with `venv`, and an internet connection
  for the first build (it downloads the packages).
- **macOS:** nothing else. Without a signing identity the app is signed ad
  hoc, so on another Mac the first launch needs right-click → Open (or
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

## Headless

```sh
PyxelWidgets --headless layout.json [--play] [--fps 30] [--quiet] [--import my_widgets.py]
PyxelWidgets.app/Contents/MacOS/PyxelWidgets --headless layout.json --play   # macOS
```

This plays the layout on its devices and outputs without a window, like
`pyxelwidgets run`: unplugged devices reconnect, stored presets are saved to
the layout file, and Ctrl+C or SIGTERM stops it. Started from a terminal it
prints there; otherwise (a service, a login item) it prints to the log file
below. On Windows the program is a windowed one, so a command prompt gets its
prompt back at once and the output goes to the log: stop it with Task Manager
or `taskkill /im PyxelWidgets.exe`.

## Designer server without a window, and sharing

```sh
PyxelWidgets --server [layout.json] [--host 0.0.0.0] [--play]
```

`--server` runs only the designer's server (stopped with Ctrl+C or SIGTERM):
open the printed address in a browser. With `--host 0.0.0.0` (also for the
window) other computers on the network can open it, for example to edit a
phone's or a Raspberry Pi's layouts from a bigger screen. The *Share* button
in the designer's toolbar does the same while it runs, and can stop it again.

Other computers need a key: the shared address carries it
(`http://192.168.1.27:8770/?key=…`), a cookie remembers it, and it's kept in
`~/.pyxelwidgets/share-key` so bookmarks keep working (delete that file for a
new key). Anyone with the address can edit layouts and open and save files on
the computer running it, so share only on networks you trust.

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
