"""
Builds the PyxelWidgets application (the designer in a window, see
pyxelwidgets.designer.window) for the system it runs on, with PyInstaller:

    python packaging/build.py            # macOS: dist/PyxelWidgets.app, Windows/Linux: dist/PyxelWidgets/
    python packaging/build.py --reuse    # keep the build environment's packages (faster rebuilds)

It makes its own virtual environment in build/app-venv with the package and its
extras (osc, network, desktop, app), so the Python running it only needs venv.
The result is also zipped as dist/PyxelWidgets-<version>-<system>-<machine>.zip.
See packaging/README.md for each system's requirements.
"""

import argparse
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import venv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build'
DIST = ROOT / 'dist'
ENV = BUILD / 'app-venv'
NAME = 'PyxelWidgets'
BUNDLE_ID = 'io.github.nullmember.pyxelwidgets'

EXTRAS = 'app,osc,network,desktop'

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

def pyinstaller(icon_folder: pathlib.Path) -> None:
    icon = icon_folder / {'macos': 'icon.icns', 'windows': 'icon.ico'}.get(system(), 'icon.png')
    command = [
        env_python(), '-m', 'PyInstaller', ROOT / 'packaging' / 'app.py',
        '--name', NAME, '--windowed', '--noconfirm', '--clean',
        '--icon', icon,
        '--distpath', DIST, '--workpath', BUILD / 'pyinstaller', '--specpath', BUILD,
        # Devices, outputs and widgets are found by name (layouts say "novation.LaunchpadMiniMK3"), not by imports
        '--collect-submodules', 'pyxelwidgets',
        '--collect-data', 'pyxelwidgets',
        '--collect-submodules', 'pythonosc',
        '--collect-submodules', 'pynput',
        '--collect-submodules', 'zeroconf',
        '--osx-bundle-identifier', BUNDLE_ID,
    ]
    if system() == 'linux':
        command += ['--collect-submodules', 'qtpy']
    run(*command, cwd = BUILD)

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
    })
    with plist_path.open('wb') as file:
        plistlib.dump(plist, file)
    run('codesign', '--force', '--deep', '--sign', '-', app)
    return app

def archive(built: pathlib.Path) -> pathlib.Path:
    machine = platform.machine().lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
    target = DIST / f'{NAME}-{version()}-{system()}-{machine}.zip'
    target.unlink(missing_ok = True)
    if system() == 'macos':
        # ditto keeps the bundle's symlinks and signature
        run('ditto', '-c', '-k', '--keepParent', built, target)
    else:
        shutil.make_archive(str(target.with_suffix('')), 'zip', built.parent, built.name)
    return target

def main(argv = None) -> None:
    parser = argparse.ArgumentParser(description = __doc__.split('\n\n')[0])
    parser.add_argument('--reuse', action = 'store_true', help = "reuse build/app-venv's packages (still reinstalls this package)")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        sys.exit('PyxelWidgets needs Python 3.10 or later')
    BUILD.mkdir(exist_ok = True)
    prepare(args.reuse)
    pyinstaller(icons())
    built = mac_bundle() if system() == 'macos' else DIST / NAME
    target = archive(built)
    print(f'\nBuilt {built}\nZipped {target}')

if __name__ == '__main__':
    main()
