"""The packaged application's entry point (packaging/build.py): the designer in a window."""

import multiprocessing
import sys

import pyxelwidgets.designer.window

def log_output() -> None:
    """A windowed program has no terminal (on Windows no stdout at all): its output goes to a log file, new each launch."""
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
