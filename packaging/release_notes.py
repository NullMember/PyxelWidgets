"""
Release notes for a tag (v1.2.3): its section of CHANGELOG.md and what to
download. The release workflow passes them to the GitHub release.

    python packaging/release_notes.py v1.0.0
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

DOWNLOADS = '''
## Downloads

| System | File | First launch |
|--------|------|--------------|
| macOS (Apple silicon) | `PyxelWidgets-{version}-macos-arm64.zip` | Unzip and move PyxelWidgets to Applications. |
| Windows | `PyxelWidgets-{version}-windows-x86_64.zip` | Unzip and run `PyxelWidgets.exe`; SmartScreen may ask: *More info → Run anyway*. |
| Linux | `PyxelWidgets-{version}-linux-x86_64.zip` | Unzip and run `PyxelWidgets/PyxelWidgets` (needs `libxcb-cursor0` on Debian/Ubuntu). |
| Android 7+ | `PyxelWidgets-{version}-android.apk` | Open it on the phone and allow installing from your browser or file manager. |

The Python package: `pip install pyxelwidgets=={version}`, then `pyxelwidgets designer`.
See the [apps guide](https://github.com/NullMember/PyxelWidgets/blob/main/docs/apps.md) for more.
'''

def notes(tag: str) -> str:
    version = tag.removeprefix('v')
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding = 'utf-8')
    match = re.search(rf'^## {re.escape(version)}\n(.*?)(?=^## |\Z)', changelog, re.M | re.S)
    if match is None:
        raise SystemExit(f'CHANGELOG.md has no section "## {version}"')
    return match.group(1).strip() + '\n' + DOWNLOADS.format(version = version)

if __name__ == '__main__':
    print(notes(sys.argv[1]))
