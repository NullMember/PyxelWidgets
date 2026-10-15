"""The packaged application's entry point (packaging/build.py): the designer in a window."""

import multiprocessing
import sys

import pyxelwidgets.designer.window

def log_output() -> None:
    """
    Started from a terminal, output goes there; otherwise (a double click; on Windows
    a windowed program has no stdout at all) to a log file, new each launch.
    """
    if sys.stdout is not None and sys.stdout.isatty():
        return
    folder = pyxelwidgets.designer.window.data_folder()
    folder.mkdir(parents = True, exist_ok = True)
    log = open(folder / 'PyxelWidgets.log', 'w', encoding = 'utf-8', buffering = 1)
    sys.stdout = sys.stderr = log

if __name__ == '__main__':
    # Frozen programs re-run themselves for child processes
    multiprocessing.freeze_support()
    if getattr(sys, 'frozen', False):
        log_output()
    pyxelwidgets.designer.window.main(prog = 'PyxelWidgets')
