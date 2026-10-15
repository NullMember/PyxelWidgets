"""
Builds the PyxelWidgets application (the designer in a window, see
pyxelwidgets.designer.window) for the system it runs on, with PyInstaller:

    python packaging/build.py            # macOS: dist/PyxelWidgets.app, Windows/Linux: dist/PyxelWidgets/
    python packaging/build.py --reuse    # keep the build environment's packages (faster rebuilds)

It makes its own virtual environment in build/app-venv with the package and its
extras (osc, network, desktop, app), so the Python running it only needs venv.
The result is also archived as dist/PyxelWidgets-<version>-<system>-<machine>.zip
(.tar.gz on Linux, which keeps symlinks).
See packaging/README.md for each system's requirements.

On macOS, with ``PYXELWIDGETS_SIGN_IDENTITY`` set (a "Developer ID
Application" certificate in the keychain), the app is signed with it and the
hardened runtime; with ``PYXELWIDGETS_NOTARY_PROFILE`` (a ``xcrun notarytool
store-credentials`` profile) or ``PYXELWIDGETS_NOTARY_KEY``/``_KEY_ID``/``_ISSUER``
(an App Store Connect API key) it's notarized and stapled too. Otherwise it's
signed ad hoc.
"""

import argparse
import os
import pathlib
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import venv

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build'
DIST = ROOT / 'dist'
ENV = BUILD / 'app-venv'
NAME = 'PyxelWidgets'
BUNDLE_ID = 'com.nullmember.pyxelwidgets'

EXTRAS = 'app,osc,network,desktop,bluetooth'

def system() -> str:
    return {'darwin': 'macos', 'win32': 'windows'}.get(sys.platform, 'linux' if sys.platform.startswith('linux') else sys.platform)

def env_python() -> pathlib.Path:
    return ENV / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')

def run(*command, **options) -> None:
    print('$', ' '.join(str(part) for part in command), flush = True)
    subprocess.run([str(part) for part in command], check = True, **options)

def version() -> str:
    text = (ROOT / 'src' / 'pyxelwidgets' / '__init__.py').read_text(encoding = 'utf-8')
    return re.search(r"__version__ = '([^']+)'", text).group(1)

def prepare(reuse: bool) -> None:
    """The build environment: the package (not editable, so PyInstaller finds plain files) and its extras."""
    if not reuse and ENV.exists():
        shutil.rmtree(ENV)
    if not env_python().exists():
        venv.create(ENV, with_pip = True)
    python = env_python()
    run(python, '-m', 'pip', 'install', '--upgrade', 'pip')
    packages = [f'{ROOT}[{EXTRAS}]', 'pyinstaller >= 6']
    if system() == 'linux':
        # Qt's web view comes as wheels and travels inside the build; GTK's needs the system's WebKitGTK
        packages.append('pywebview[qt]')
    run(python, '-m', 'pip', 'install', '--upgrade', *packages)
    # The same version number with new code: pip would keep the old copy
    run(python, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', ROOT)

def icons() -> pathlib.Path:
    folder = BUILD / 'icon'
    run(env_python(), ROOT / 'packaging' / 'icon.py', folder)
    return folder

def pyinstaller(icon_folder: pathlib.Path, console: bool = False) -> None:
    icon = icon_folder / {'macos': 'icon.icns', 'windows': 'icon.ico'}.get(system(), 'icon.png')
    command = [
        env_python(), '-m', 'PyInstaller', ROOT / 'packaging' / 'app.py',
        '--name', NAME, '--console' if console else '--windowed', '--noconfirm', '--clean',
        '--icon', icon,
        '--distpath', DIST, '--workpath', BUILD / 'pyinstaller', '--specpath', BUILD,
        # Devices, outputs and widgets are found by name (layouts say "novation.LaunchpadMiniMK3"), not by imports
        '--collect-submodules', 'pyxelwidgets',
        '--collect-data', 'pyxelwidgets',
        '--collect-submodules', 'pythonosc',
        '--collect-submodules', 'pynput',
        '--collect-submodules', 'zeroconf',
        # bleak picks its backend (CoreBluetooth, WinRT, BlueZ) at run time
        '--collect-submodules', 'bleak',
        '--osx-bundle-identifier', BUNDLE_ID,
    ]
    if system() == 'linux':
        # Only the Qt modules pywebview's Qt window uses (collecting all of qtpy pulls in every PyQt6 module and its libraries)
        for module in QT_MODULES:
            command += ['--hidden-import', f'qtpy.{module}', '--hidden-import', f'PyQt6.{module}']
    run(*command, cwd = BUILD)
    if system() == 'linux':
        trim_qt()

#: What webview/platforms/qt.py imports
QT_MODULES = ('QtCore', 'QtGui', 'QtWidgets', 'QtNetwork', 'QtWebChannel', 'QtWebEngineCore', 'QtWebEngineWidgets')

#: Qt plugin folders the window can use (screens, themes, input, images, TLS); the rest (multimedia, sensors, SQL...) go
QT_PLUGINS = {'platforms', 'platformthemes', 'platforminputcontexts', 'imageformats', 'iconengines', 'tls',
              'xcbglintegrations', 'wayland-decoration-client', 'wayland-graphics-integration-client',
              'wayland-shell-integration', 'egldeviceintegrations', 'generic'}
#: Of the platforms: X11, Wayland and offscreen
QT_PLATFORMS = ('libqxcb', 'libqwayland', 'libqoffscreen')
#: Platform themes: the GTK one would load the build machine's GTK into the window
QT_THEMES_LEFT_OUT = ('libqgtk3',)
#: Libraries every Linux desktop has, that have to be the system's own: the C++
#: runtime and graphics libraries the GPU drivers load with them (an older
#: bundled libstdc++ kept Mesa from loading on a Steam Deck), ALSA (its plugins,
#: e.g. PipeWire's, follow the system's version) and fonts (the system's
#: configuration). The build machine is the oldest system supported, so the
#: system's are as new or newer.
HOST_LIBRARIES = ('libstdc++.so', 'libgcc_s.so', 'libgbm.so', 'libdrm.so', 'libEGL.so', 'libGL.so', 'libGLX.so',
                  'libGLdispatch.so', 'libxcb-glx.so', 'libvulkan.so', 'libasound.so', 'libfontconfig.so',
                  'libfreetype.so')

def trim_qt() -> None:
    """
    Leave out what the window never loads: Qt WebEngine's translations of
    its own menus (English is the fallback), QML, unused plugins, and the Qt
    libraries nothing kept links to (found with ldd from the PyQt6 modules,
    the kept plugins and QtWebEngineProcess).
    """
    internal = DIST / NAME / '_internal'
    qt = internal / 'PyQt6' / 'Qt6'
    for path in (qt / 'translations' / 'qtwebengine_locales').glob('*.pak'):
        if path.name != 'en-US.pak':
            path.unlink()
    shutil.rmtree(qt / 'qml', ignore_errors = True)
    for folder in (qt / 'plugins').iterdir():
        if folder.name not in QT_PLUGINS:
            shutil.rmtree(folder)
    for path in (qt / 'plugins' / 'platforms').iterdir():
        if not path.name.startswith(QT_PLATFORMS):
            path.unlink()
    for path in (qt / 'plugins' / 'platformthemes').glob('*'):
        if path.name.startswith(QT_THEMES_LEFT_OUT):
            path.unlink()
    for path in internal.iterdir():
        if path.name.startswith(HOST_LIBRARIES):
            print(f'Left out {path.name}: the system has its own', flush = True)
            path.unlink()
    roots = [*(internal / 'PyQt6').glob('*.so'), *(qt / 'plugins').rglob('*.so'), qt / 'libexec' / 'QtWebEngineProcess']
    environment = dict(os.environ, LD_LIBRARY_PATH = f'{qt / "lib"}:{internal}')
    needed = set()
    for root in roots:
        listing = subprocess.run(['ldd', str(root)], capture_output = True, text = True, env = environment).stdout
        needed.update(pathlib.Path(match).name for match in re.findall(r'=> (\S+) \(', listing)
                      if pathlib.Path(match).resolve().parent == (qt / 'lib').resolve())
    removed = 0
    for path in (qt / 'lib').iterdir():
        if path.name.startswith('lib') and '.so' in path.name and path.name not in needed:
            removed += path.stat().st_size
            path.unlink()
    # PyInstaller's links to them in _internal
    for path in internal.iterdir():
        if path.is_symlink() and not path.exists():
            path.unlink()
    print(f'Left out {removed / 2 ** 20:.0f} MB of Qt libraries', flush = True)

def mac_bundle() -> pathlib.Path:
    """Info.plist entries PyInstaller doesn't write, then a fresh ad-hoc signature (the plist is signed too)."""
    app = DIST / f'{NAME}.app'
    plist_path = app / 'Contents' / 'Info.plist'
    with plist_path.open('rb') as file:
        plist = plistlib.load(file)
    plist.update({
        'CFBundleShortVersionString': version(),
        'CFBundleVersion': version(),
        'CFBundleDisplayName': NAME,
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'LSApplicationCategoryType': 'public.app-category.music',
        # WebGrid, OSC and network MIDI talk to the local network; RTP-MIDI announces itself with Bonjour
        'NSLocalNetworkUsageDescription': 'PyxelWidgets talks to grids, DAWs and phones on your network (WebGrid, OSC, network MIDI).',
        'NSBonjourServices': ['_apple-midi._udp'],
        # Without it macOS stops the app the moment it uses Bluetooth
        'NSBluetoothAlwaysUsageDescription': 'PyxelWidgets connects to Bluetooth MIDI controllers and keyboards.',
    })
    with plist_path.open('wb') as file:
        plistlib.dump(plist, file)
    identity = os.environ.get('PYXELWIDGETS_SIGN_IDENTITY')
    if not identity:
        run('codesign', '--force', '--deep', '--sign', '-', app)
        return app
    entitlements = ROOT / 'packaging' / 'entitlements.plist'
    # Inside out: every library and executable, then the bundle (--deep doesn't apply options to nested code)
    nested = [path for path in app.rglob('*') if path.is_file() and not path.is_symlink()
              and (path.suffix in ('.so', '.dylib') or os.access(path, os.X_OK))]
    for path in sorted(nested, key = lambda path: -len(path.parts)):
        if path.parent.name == 'MacOS' and path.parent.parent.parent == app:
            continue
        run('codesign', '--force', '--timestamp', '--options', 'runtime', '--entitlements', entitlements, '--sign', identity, path)
    run('codesign', '--force', '--timestamp', '--options', 'runtime', '--entitlements', entitlements, '--sign', identity, app)
    run('codesign', '--verify', '--deep', '--strict', app)
    notarize(app)
    return app

def notarize(app: pathlib.Path) -> None:
    """Send the signed app to Apple's notary service and staple the ticket, when credentials are set."""
    profile = os.environ.get('PYXELWIDGETS_NOTARY_PROFILE')
    key = os.environ.get('PYXELWIDGETS_NOTARY_KEY')
    if profile:
        credentials = ['--keychain-profile', profile]
    elif key:
        credentials = ['--key', key, '--key-id', os.environ['PYXELWIDGETS_NOTARY_KEY_ID'],
                       '--issuer', os.environ['PYXELWIDGETS_NOTARY_ISSUER']]
    else:
        print('Not notarized: no PYXELWIDGETS_NOTARY_PROFILE or PYXELWIDGETS_NOTARY_KEY', flush = True)
        return
    upload = BUILD / f'{NAME}-notarize.zip'
    upload.unlink(missing_ok = True)
    run('ditto', '-c', '-k', '--keepParent', app, upload)
    run('xcrun', 'notarytool', 'submit', upload, *credentials, '--wait')
    run('xcrun', 'stapler', 'staple', app)
    upload.unlink()

def archive(built: pathlib.Path) -> pathlib.Path:
    machine = platform.machine().lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
    target = DIST / f'{NAME}-{version()}-{system()}-{machine}.zip'
    target.unlink(missing_ok = True)
    if system() == 'macos':
        # ditto keeps the bundle's symlinks and signature
        run('ditto', '-c', '-k', '--keepParent', built, target)
    elif system() == 'linux':
        # A tarball keeps PyInstaller's symlinks (a zip would store each linked library twice)
        target = target.with_name(target.name.replace('.zip', '.tar.gz'))
        target.unlink(missing_ok = True)
        with tarfile.open(target, 'w:gz') as archive:
            archive.add(built, arcname = built.name)
    else:
        shutil.make_archive(str(target.with_suffix('')), 'zip', built.parent, built.name)
    return target

def main(argv = None) -> None:
    parser = argparse.ArgumentParser(description = __doc__.split('\n\n')[0])
    parser.add_argument('--reuse', action = 'store_true', help = "reuse build/app-venv's packages (still reinstalls this package)")
    parser.add_argument('--console', action = 'store_true', help = 'a console program (Windows), which shows errors from before the log opens')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        sys.exit('PyxelWidgets needs Python 3.10 or later')
    BUILD.mkdir(exist_ok = True)
    prepare(args.reuse)
    pyinstaller(icons(), args.console)
    built = mac_bundle() if system() == 'macos' else DIST / NAME
    target = archive(built)
    print(f'\nBuilt {built}\nZipped {target}')

if __name__ == '__main__':
    main()
