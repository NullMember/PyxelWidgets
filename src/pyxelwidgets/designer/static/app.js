// PyxelWidgets Designer: edits a layout (see pyxelwidgets.parser) and shows a
// live preview rendered by the Python widgets through the designer server.
//
// Plain ES modules, no build step. core.js holds `state` and the DOM helpers; each
// other module is one part of the page (model, board, layers, properties, rules...).
// This one binds the toolbar, keys and stage, and starts the designer.

import { state, $, el, api, thumb } from './core.js';
import { prefs, savePrefs, sendHidden } from './prefs.js';
import { widgetAt } from './model.js';
import { addOutput } from './mappings.js';
import { openRules, closeRules, rulesKey, buildRules } from './rules.js';
import { drawerPrefs, openDrawer, renderDrawer, bindDrawer } from './drawer.js';
import { renderPanels, togglePanel, toggleFocus, bindSplitters, showShortcuts } from './panels.js';
import { undo, redo } from './history.js';
import { poll } from './preview.js';
import { render, renderBoard, panBy, zooming, setZoom, startMarquee } from './board.js';
import { startRename, renderTree, treeDragOver, treeDrop } from './layers.js';
import { select, renderToolbar } from './properties.js';
import { addWidget, clearGhost, dragOver, drop, addDevice, removeSelection, duplicate, copySelection,
  pasteWidgets, groupSelection, ungroup, selectAll, nudge } from './editing.js';
import { showPaletteTab, loadSnippets, renderSnippets, saveSnippet } from './snippets.js';
import { stopLearning } from './learn.js';
import { openStart, closeStart } from './start.js';
import { addRecent, save, saveAs, showOpen, importFile, showFileMenu, showDetect, setMode } from './files.js';

function bindToolbar() {
  $('mode-edit').onclick = () => setMode('edit');
  $('mode-try').onclick = () => setMode('try');
  $('mode-perform').onclick = () => setMode('perform');
  const board = $('board');
  board.addEventListener('dragover', dragOver);
  board.addEventListener('drop', drop);
  board.addEventListener('dragleave', (event) => { if (!board.contains(event.relatedTarget)) clearGhost(); });
  $('play').onclick = async () => {
    if (state.synced) return;
    state.playing = !state.playing;
    renderToolbar();
    await api('POST', '/api/play', { playing: state.playing });
  };
  $('tree').addEventListener('dragover', treeDragOver);
  $('tree').addEventListener('drop', treeDrop);
  $('zoom-in').onclick = () => setZoom((zooming.target ?? state.zoom) * 1.25);
  $('zoom-out').onclick = () => setZoom((zooming.target ?? state.zoom) / 1.25);
  $('zoom-fit').onclick = () => setZoom(1);
  $('wheel-mode').onclick = () => {
    prefs.wheel = prefs.wheel === 'scroll' ? 'zoom' : 'scroll';
    savePrefs();
    renderToolbar();
  };
  bindStage();
  $('undo').onclick = undo;
  $('redo').onclick = redo;
  $('save').onclick = save;
  $('file-menu').onclick = showFileMenu;
  $('detect-devices').onclick = showDetect;
  $('open-file').onchange = (e) => { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = ''; };
  $('add-device').onclick = addDevice;
  $('add-output').onclick = () => addOutput();
  $('snippet-size').onchange = (event) => {
    prefs.snippetSize = event.target.value;
    savePrefs();
    renderSnippets();
  };
  $('save-snippet').onclick = saveSnippet;
  $('tab-widgets').onclick = () => showPaletteTab('widgets');
  $('tab-snippets').onclick = () => showPaletteTab('snippets');
  showPaletteTab(prefs.paletteTab || 'widgets');
  $('toggle-left').onclick = () => togglePanel('left');
  $('toggle-right').onclick = () => togglePanel('right');
  $('help').onclick = showShortcuts;
  $('problems').onclick = () => openDrawer('problems');
  $('layer-search').addEventListener('input', renderTree);
  bindFolds();
  bindDrawer();
  bindSplitters();
  window.addEventListener('beforeunload', (event) => {
    if (state.file && JSON.stringify(state.layout) !== state.saved) event.preventDefault();
  });
  window.addEventListener('keydown', (event) => {
    if (event.target.closest('input, select, textarea')) return;
    if (event.target.closest('dialog')) return;
    if (event.key === 'Escape' && state.learning) return stopLearning();
    if (event.key === 'Escape' && state.start?.open) return closeStart();
    if (state.rules.open && state.rules.focused && rulesKey(event)) return;
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (mod && key === 'z') { event.preventDefault(); return event.shiftKey ? redo() : undo(); }
    if (mod && key === 'y') { event.preventDefault(); return redo(); }
    if (mod && (key === '=' || key === '+')) { event.preventDefault(); return setZoom((zooming.target ?? state.zoom) * 1.25); }
    if (mod && key === '-') { event.preventDefault(); return setZoom((zooming.target ?? state.zoom) / 1.25); }
    if (mod && key === '0') { event.preventDefault(); return setZoom(1); }
    if (mod && key === 's') { event.preventDefault(); return event.shiftKey ? saveAs() : save(); }
    if (mod && key === 'o') { event.preventDefault(); return showOpen(); }
    if (mod && key === 'd' && state.selection?.kind === 'widget') { event.preventDefault(); return duplicate(); }
    if (mod && key === 'c' && state.selection?.kind === 'widget' && !window.getSelection()?.toString()) { event.preventDefault(); return copySelection(); }
    if (mod && key === 'x' && state.selection?.kind === 'widget' && state.mode === 'edit') { event.preventDefault(); return copySelection(true); }
    if (mod && key === 'v' && state.mode === 'edit') { event.preventDefault(); return pasteWidgets(); }
    if (mod && key === 'a' && state.mode === 'edit') { event.preventDefault(); return selectAll(); }
    if (mod && key === 'g' && state.selection?.kind === 'widget') {
      event.preventDefault();
      const widget = widgetAt(state.selection.path);
      return event.shiftKey ? (widget.type === 'Group' && ungroup(state.selection.path)) : groupSelection();
    }
    if (mod) return;
    if (key === '?' ) return showShortcuts();
    if (key === '[') return togglePanel('left');
    if (key === ']') return togglePanel('right');
    if (key === 'f') return toggleFocus();
    if (key === '`') { drawerPrefs().open = !drawerPrefs().open; savePrefs(); return renderDrawer(); }
    if (key === 'm') return state.rules.open ? closeRules() : openRules();
    if (key === 'f2' && state.selection?.kind === 'widget' && state.mode === 'edit') { event.preventDefault(); return startRename(state.selection.path); }
    if (key === 'e') return setMode('edit');
    if (key === 't') return setMode('try');
    if (key === 'p') return setMode('perform');
    if (key === 'escape') return select(null);
    // A focused button handles Space itself
    if (key === ' ' && !event.target.closest('button')) { event.preventDefault(); return $('play').click(); }
    if (state.mode !== 'edit') return;
    if (key === 'delete' || key === 'backspace') { event.preventDefault(); return removeSelection(); }
    const arrows = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, 1], arrowdown: [0, -1] };
    if (arrows[key]) { event.preventDefault(); nudge(...arrows[key], event.shiftKey); }
  });
}

// The grid fills the stage (refitted when panels, the drawer or the window change size). Pinches
// and Ctrl/Cmd + wheel zoom around the pointer, two-finger trackpad scrolls move the grid; a mouse
// wheel zooms (or moves the grid, by the toolbar's choice); Shift + wheel, the middle button and
// dragging the space around the grid move it
function bindStage() {
  const stage = $('stage');
  new ResizeObserver(() => renderBoard()).observe(stage);
  stage.addEventListener('wheel', (event) => {
    const pinch = event.ctrlKey || event.metaKey;
    event.preventDefault();
    const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? stage.clientHeight : 1;
    if (!pinch && (prefs.wheel === 'scroll' || event.shiftKey || trackpad(event))) {
      // Shift + wheel: sideways
      const [dx, dy] = event.shiftKey && !event.deltaX ? [event.deltaY, 0] : [event.deltaX, event.deltaY];
      return panBy(-dx * scale, -dy * scale);
    }
    const pixels = event.deltaY * scale;
    // Pinches send small steps, wheels about 100 a notch
    setZoom((zooming.target ?? state.zoom) * Math.exp(-pixels * (event.ctrlKey && Math.abs(pixels) < 50 ? 0.01 : 0.002)), event);
  }, { passive: false });
  stage.addEventListener('pointerdown', (event) => {
    if (event.button === 1) return panStage(event);
    if (event.button !== 0) return;
    // Around the grid: drag to move it, click to select the surface; on the board's frame: a selection rectangle
    if (event.target.id === 'stage') panStage(event, () => { if (state.mode === 'edit') select(null); });
    else if (event.target.id === 'board') startMarquee(event);
  });
  // No autoscroll circle on middle clicks
  stage.addEventListener('mousedown', (event) => { if (event.button === 1) event.preventDefault(); });
}

// Whether a wheel event comes from a trackpad's two-finger scroll rather than a mouse wheel:
// sideways movement, or (Chrome, Safari) a legacy wheelDelta of 3 per pixel where wheels send
// notches of 120. A gesture keeps its kind (momentum scrolling can look like a wheel)
const gesture = { trackpad: false, last: 0 };
function trackpad(event) {
  const now = performance.now();
  if (now - gesture.last > 300) {
    gesture.trackpad = event.deltaMode === 0 && (event.deltaX !== 0
      || (event.wheelDeltaY ? event.wheelDeltaY === -3 * event.deltaY : !Number.isInteger(event.deltaY)));
  } else if (event.deltaMode === 0 && event.deltaX !== 0) gesture.trackpad = true;
  gesture.last = now;
  return gesture.trackpad;
}

// Drags the grid around; a press that doesn't move calls `clicked`
function panStage(event, clicked = null) {
  event.preventDefault();
  const stage = $('stage');
  const start = { x: event.clientX, y: event.clientY };
  let last = start, moved = false;
  const move = (e) => {
    if (!moved && Math.hypot(e.clientX - start.x, e.clientY - start.y) < 4) return;
    if (!moved) stage.classList.add('panning');
    moved = true;
    panBy(e.clientX - last.x, e.clientY - last.y);
    last = { x: e.clientX, y: e.clientY };
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    stage.classList.remove('panning');
    if (!moved && clicked) clicked();
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

function buildCatalog() {
  $('palette').replaceChildren(...Object.entries(state.catalog.widgets).map(([type, info]) =>
    el('button', {
      title: `${(info.doc || type).replace(/``/g, '')}\nClick to add, or drag onto the grid.`, onclick: () => addWidget(type), dataset: { type },
      draggable: 'true',
      ondragstart: (event) => {
        state.dragType = type;
        document.body.classList.add('dragging');
        event.dataTransfer.setData('text/plain', type);
        event.dataTransfer.effectAllowed = 'copy';
      },
      ondragend: () => { state.dragType = null; document.body.classList.remove('dragging'); clearGhost(); },
    },
      thumb(info.preview) || el('span', { class: 'glyph' }, type === 'ButtonGroup' ? 'BG' : type.slice(0, 2)),
      el('span', { class: 'label' }, type))));
  const groups = {};
  for (const device of state.catalog.devices) (groups[device.vendor || 'Other'] ||= []).push(device);
  $('device-type').replaceChildren(...Object.entries(groups).map(([vendor, devices]) =>
    el('optgroup', { label: vendor }, devices.map((device) => el('option', { value: device.type }, device.model)))));
  $('output-type').replaceChildren(...state.catalog.outputs.map((output) => el('option', { value: output.type }, output.model)));
}

// Sections of the left panel fold away; remembered in this browser
function bindFolds() {
  prefs.folds ||= {};
  for (const section of document.querySelectorAll('.fold')) {
    const name = section.dataset.fold;
    section.classList.toggle('collapsed', !!prefs.folds[name]);
    section.querySelector('.fold-head').addEventListener('click', (event) => {
      if (event.target.closest('button, input, select')) return;
      prefs.folds[name] = !prefs.folds[name];
      section.classList.toggle('collapsed', prefs.folds[name]);
      savePrefs();
    });
  }
}

async function start() {
  const [catalog, current] = await Promise.all([api('GET', '/api/catalog'), api('GET', '/api/layout')]);
  state.catalog = catalog;
  state.layout = current.layout;
  state.layout.devices = state.layout.devices || [];
  state.layout.widgets = state.layout.widgets || [];
  state.file = current.file;
  state.saved = JSON.stringify(state.layout);
  addRecent(state.file);
  buildCatalog();
  loadSnippets();
  renderPanels();
  bindToolbar();
  buildRules();
  render();
  sendHidden();
  poll();
  // An empty layout starts with the start window
  if (!state.layout.widgets.length && !state.layout.devices.length) openStart();
}

start();
