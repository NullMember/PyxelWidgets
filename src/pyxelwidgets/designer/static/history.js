// Undo/redo, syncing the layout to the preview, the status line

import { state, $, api } from './core.js';
import { widgetAt, widgetSelection } from './model.js';
import { outputsOf } from './mappings.js';
import { spreadChange } from './rules.js';
import { render } from './board.js';
import { renderDirty } from './properties.js';

export function change(mutate) {
  state.history.push(JSON.stringify(state.layout));
  if (state.history.length > 300) state.history.shift();
  state.future = [];
  const broadcast = state.broadcast;
  const before = broadcast && JSON.parse(JSON.stringify(broadcast.rep));
  mutate(state.layout);
  if (broadcast) spreadChange(broadcast.kind, before, broadcast.rep, broadcast.others);
  render();
  scheduleSync();
}

function replaceLayout(layout) {
  state.history.push(JSON.stringify(state.layout));
  state.future = [];
  state.layout = layout;
  state.selection = null;
  render();
  scheduleSync();
}

export function undo() {
  if (!state.history.length) return;
  state.future.push(JSON.stringify(state.layout));
  state.layout = JSON.parse(state.history.pop());
  checkSelection();
  render();
  scheduleSync();
}

export function redo() {
  if (!state.future.length) return;
  state.history.push(JSON.stringify(state.layout));
  state.layout = JSON.parse(state.future.pop());
  checkSelection();
  render();
  scheduleSync();
}

function checkSelection() {
  const selection = state.selection;
  if (selection?.kind === 'widget') {
    const exists = (path) => { try { return !!widgetAt(path); } catch { return false; } };
    const paths = selection.paths.filter(exists);
    state.selection = widgetSelection(paths, exists(selection.path) ? selection.path : undefined);
  } else if (selection?.kind === 'device' && !state.layout.devices[selection.index]) {
    state.selection = null;
  } else if (selection?.kind === 'output' && !outputsOf()[selection.index]) {
    state.selection = null;
  }
}

let syncTimer = null;
let syncing = Promise.resolve();
function scheduleSync() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(sync, 120);
  renderDirty();
}

// Send a pending layout change now; resolves once the preview has it
export function flushSync() {
  if (syncTimer !== null) sync();
  return syncing;
}

function sync() {
  clearTimeout(syncTimer);
  syncTimer = null;
  syncing = syncing.then(putLayout, putLayout);
  return syncing;
}

let putting = false;
async function putLayout() {
  putting = true;
  try {
    const reply = await api('PUT', '/api/layout', state.layout);
    if (reply.ok) {
      if (state.error) setStatus('');
      state.error = null;
      state.revision = reply.revision;
    } else {
      state.error = reply.error;
      setStatus(reply.error, 'error');
    }
  } finally {
    putting = false;
  }
}

// Whether no change of this page is waiting or on its way to the preview
export function syncIdle() {
  return syncTimer === null && !putting;
}

// The preview's layout changed elsewhere (another window, or another computer through Share): take it,
// as a step undo can go back from; the last change wins when two pages edit at once
let adopting = false;
export async function adoptRemote() {
  if (adopting) return;
  adopting = true;
  try {
    const reply = await api('GET', '/api/layout');
    if (!reply.ok || !syncIdle() || reply.revision === state.revision) return;
    state.revision = reply.revision;
    const layout = reply.layout;
    layout.devices = layout.devices || [];
    layout.widgets = layout.widgets || [];
    const same = JSON.stringify(layout) === JSON.stringify(state.layout);
    const moved = reply.file !== state.file;
    if (!same) {
      state.history.push(JSON.stringify(state.layout));
      if (state.history.length > 300) state.history.shift();
      state.future = [];
      state.layout = layout;
    }
    state.file = reply.file;
    if (reply.saved) state.saved = JSON.stringify(state.layout);
    if (!same || moved) {
      checkSelection();
      render();
      setStatus('The layout was changed elsewhere (another window or computer)', 'ok');
    }
    renderDirty();
  } finally {
    adopting = false;
  }
}

let statusTimer = null;
export function setStatus(text, kind = '') {
  const status = $('status');
  status.textContent = text;
  status.className = kind;
  clearTimeout(statusTimer);
  if (kind === 'ok') statusTimer = setTimeout(() => setStatus(state.error || '', state.error ? 'error' : ''), 2500);
}
