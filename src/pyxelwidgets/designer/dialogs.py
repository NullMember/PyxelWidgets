"""
The system's file dialogs, shown by the designer's server (which runs on the
user's computer) for Open and Save As. Each dialog runs in a process of its own,
since the server answers on threads and GUI toolkits want their main thread.
"""

import os
import pathlib
import shutil
import subprocess
import sys

__all__ = ['Unavailable', 'pick_file']

class Unavailable(OSError):
    """No file dialog can be shown here (no display, no dialog tool)."""

def pick_file(mode: str, path: str | None = None, *, title: str | None = None) -> str | None:
    """
    Ask for a layout file: ``mode`` is ``'open'`` (an existing file) or ``'save'``
    (a new or existing name; the dialog asks before replacing). ``path`` is where
    it starts. Returns the chosen path, or None when cancelled.
    """
    if mode not in ('open', 'save'):
        raise ValueError(f'mode must be open or save, not {mode!r}')
    title = title or ('Open a layout' if mode == 'open' else 'Save the layout as')
    start = pathlib.Path(path).expanduser() if path else pathlib.Path.cwd() / 'layout.json'
    folder = start if start.is_dir() else start.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent
    name = '' if start.is_dir() else start.name
    if sys.platform == 'darwin':
        return _mac(mode, title, folder, name)
    if sys.platform.startswith('linux') or 'bsd' in sys.platform:
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            raise Unavailable('No display for a file dialog')
        if shutil.which('zenity'):
            return _zenity(mode, title, folder, name)
        if shutil.which('kdialog'):
            return _kdialog(mode, title, folder, name)
    return _tk(mode, title, folder, name)

def _run(command: list[str]) -> str | None:
    """The dialog's printed path, or None when it was cancelled (a non-zero exit)."""
    try:
        done = subprocess.run(command, capture_output = True, text = True)
    except OSError as error:
        raise Unavailable(str(error)) from None
    chosen = done.stdout.strip()
    return chosen if done.returncode == 0 and chosen else None

def _quote(text: str) -> str:
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'

def _mac(mode: str, title: str, folder: pathlib.Path, name: str) -> str | None:
    where = f'default location (POSIX file {_quote(str(folder))})'
    if mode == 'open':
        choose = f'choose file with prompt {_quote(title)} of type {{"public.json", "json"}} {where}'
    else:
        choose = f'choose file name with prompt {_quote(title)} default name {_quote(name or "layout.json")} {where}'
    # activate brings the dialog in front of the browser
    return _run(['osascript', '-e', 'activate', '-e', f'POSIX path of ({choose})'])

def _zenity(mode: str, title: str, folder: pathlib.Path, name: str) -> str | None:
    command = ['zenity', '--file-selection', f'--title={title}', f'--filename={folder / name}',
               '--file-filter=Layouts | *.json', '--file-filter=All files | *']
    if mode == 'save':
        command += ['--save', '--confirm-overwrite']
    return _run(command)

def _kdialog(mode: str, title: str, folder: pathlib.Path, name: str) -> str | None:
    action = '--getopenfilename' if mode == 'open' else '--getsavefilename'
    return _run(['kdialog', '--title', title, action, str(folder / name), 'Layouts (*.json)'])

_TK = '''
import sys, tkinter, tkinter.filedialog
mode, title, folder, name = sys.argv[1:]
root = tkinter.Tk()
root.withdraw()
root.attributes('-topmost', True)
ask = tkinter.filedialog.askopenfilename if mode == 'open' else tkinter.filedialog.asksaveasfilename
options = dict(title = title, initialdir = folder, filetypes = [('Layouts', '*.json'), ('All files', '*')])
if mode == 'save':
    options.update(initialfile = name or 'layout.json', defaultextension = '.json')
print(ask(**options) or '')
'''

def _tk(mode: str, title: str, folder: pathlib.Path, name: str) -> str | None:
    try:
        done = subprocess.run([sys.executable, '-c', _TK, mode, title, str(folder), name], capture_output = True, text = True)
    except OSError as error:
        raise Unavailable(str(error)) from None
    if done.returncode != 0:
        # No tkinter, or no display
        raise Unavailable(done.stderr.strip().splitlines()[-1] if done.stderr.strip() else 'No file dialog')
    return done.stdout.strip() or None
