// Side panels, splitters and the shortcuts dialog

import { $, fill, el } from './core.js';
import { prefs, savePrefs } from './prefs.js';
import { renderBoard, renderOverlay, clamp } from './board.js';
import { newDialog } from './files.js';

export function renderPanels() {
  prefs.panels ||= { left: true, right: true, leftWidth: 290, rightWidth: 360 };
  const panels = prefs.panels;
  document.body.classList.toggle('no-left', !panels.left);
  document.body.classList.toggle('no-right', !panels.right);
  document.documentElement.style.setProperty('--left', `${panels.leftWidth}px`);
  document.documentElement.style.setProperty('--right', `${panels.rightWidth}px`);
  $('toggle-left').classList.toggle('active', panels.left);
  $('toggle-right').classList.toggle('active', panels.right);
}

export function togglePanel(side, shown = !prefs.panels[side]) {
  prefs.panels[side] = shown;
  savePrefs();
  renderPanels();
  renderBoard();
  renderOverlay();
}

// The grid alone (F), or back to the panels as they were
export function toggleFocus() {
  const panels = prefs.panels;
  if (panels.left || panels.right) {
    panels.before = { left: panels.left, right: panels.right };
    panels.left = panels.right = false;
  } else {
    Object.assign(panels, panels.before || { left: true, right: true });
  }
  savePrefs();
  renderPanels();
  renderBoard();
  renderOverlay();
}

export function bindSplitters() {
  for (const [id, side, sign] of [['split-left', 'leftWidth', 1], ['split-right', 'rightWidth', -1]]) {
    $(id).addEventListener('pointerdown', (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const start = prefs.panels[side];
      $(id).classList.add('active');
      const move = (e) => {
        prefs.panels[side] = clamp(start + sign * (e.clientX - startX), 200, 560);
        renderPanels();
        renderBoard();
        renderOverlay();
      };
      const up = () => {
        $(id).classList.remove('active');
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        savePrefs();
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    });
  }
}

const SHORTCUTS = [
  ['E / T', 'Edit or Try mode'],
  ['Alt + click', 'press a pad while editing'],
  ['Space', 'play or stop the transport'],
  ['Ctrl/Cmd + Z, Ctrl/Cmd + Shift + Z', 'undo, redo'],
  ['Ctrl/Cmd + S', 'save'],
  ['Ctrl/Cmd + C, X, V', 'copy, cut and paste widgets (also between layouts)'],
  ['Ctrl/Cmd + D', 'duplicate'],
  ['Ctrl/Cmd + A', 'select everything in the group'],
  ['Shift + click, drag on empty pads or the grid\'s frame', 'select several on the grid'],
  ['Shift + click, Ctrl/Cmd + click in Layers', 'select a range of layers, add or remove one'],
  ['Double-click a layer name, F2', 'rename the widget'],
  ['Ctrl/Cmd + G, Ctrl/Cmd + Shift + G', 'group, ungroup'],
  ['Arrows, Shift + arrows', 'move, resize'],
  ['Delete', 'delete'],
  ['Wheel, Ctrl/Cmd + + / − / 0', 'zoom (the toolbar sets whether the wheel zooms or scrolls)'],
  ['Drag around the grid, two-finger scroll, middle button drag, Shift + wheel', 'move around the grid'],
  ['Pinch, Ctrl/Cmd + wheel', 'zoom'],
  ['[ and ]', 'show or hide the left or right panel'],
  ['F', 'the grid alone (again: back)'],
  ['`', 'show or hide the drawer'],
  ['M', 'the messages and links window'],
  ['In that window: click, Shift + click, Ctrl/Cmd + click', 'pick one, a range, one more (picked ones are edited together)'],
  ['In that window: Ctrl/Cmd + C, X, V, D, A, Delete', 'copy, cut, paste onto the selected widgets, duplicate, pick all, delete'],
  ['Escape', 'select nothing (in the window: close it)'],
  ['?', 'this list'],
];

export function showShortcuts() {
  const dialog = newDialog();
  fill(dialog,
    el('h3', {}, 'Keyboard shortcuts'),
    el('table', { class: 'keys' }, SHORTCUTS.map(([keys, what]) => el('tr', {},
      el('td', {}, keys.split(', ').map((key, i) => [i ? ', ' : null, el('kbd', {}, key)])), el('td', {}, what)))),
    el('div', { class: 'buttons' }, el('button', { onclick: () => dialog.close() }, 'Close')));
  dialog.showModal();
}
