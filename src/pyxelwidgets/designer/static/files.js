// Files (new, open, save, download), dialogs and the welcome card

import { state, $, fill, el, api } from './core.js';
import { prefs, savePrefs, sendHidden } from './prefs.js';
import { openDrawer } from './drawer.js';
import { change, flushSync, setStatus } from './history.js';
import { held, padUp } from './preview.js';
import { render } from './board.js';
import { renderToolbar, renderDirty } from './properties.js';
import { hidePadInfo } from './padinfo.js';

function dirty() {
  return JSON.stringify(state.layout) !== state.saved;
}

export function addRecent(file) {
  if (!file) return;
  prefs.recent = [file, ...(prefs.recent || []).filter((other) => other !== file)].slice(0, 8);
  savePrefs();
}

// A layout the server loaded (opened, new, saved as): it becomes the current one
function useLayout(reply) {
  state.layout = reply.layout;
  state.layout.devices = state.layout.devices || [];
  state.layout.widgets = state.layout.widgets || [];
  state.file = reply.file;
  state.saved = JSON.stringify(state.layout);
  state.history = [];
  state.future = [];
  state.selection = null;
  state.frameSize = [0, 0];
  addRecent(reply.file);
  render();
  sendHidden();
}

// A modal dialog of its own, removed once closed
export function newDialog() {
  const dialog = el('dialog');
  dialog.addEventListener('close', () => dialog.remove());
  document.body.append(dialog);
  return dialog;
}

// A small dialog: resolves with the value of `fields` (by name) on OK, or null
export function ask({ title, text = null, fields = [], ok = 'OK', extra = null }) {
  const dialog = newDialog();
  return new Promise((resolve) => {
    const inputs = fields.map((field) => el('input', { type: 'text', id: `ask-${field.name}`, value: field.value ?? '', placeholder: field.placeholder || '' }));
    const finish = (value) => {
      dialog.onclose = null;
      dialog.close();
      resolve(value);
    };
    fill(dialog,
      el('h3', {}, title),
      text ? el('p', { class: 'hint' }, text) : null,
      fields.length ? el('div', { class: 'fields' }, fields.map((field, i) => [
        el('label', { for: `ask-${field.name}` }, field.label), el('div', { class: 'control' }, inputs[i])])) : null,
      extra ? extra(finish) : null,
      el('div', { class: 'buttons' },
        el('button', { onclick: () => finish(null) }, 'Cancel'),
        el('button', { class: 'primary', id: 'ask-ok', onclick: () => finish(Object.fromEntries(fields.map((field, i) => [field.name, inputs[i].value.trim()]))) }, ok)));
    dialog.onclose = () => resolve(null);
    for (const input of inputs) input.addEventListener('keydown', (e) => { if (e.key === 'Enter') $('ask-ok').click(); });
    dialog.showModal();
    inputs[0]?.select();
  });
}

async function confirmDiscard() {
  if (!dirty() || (!state.file && !state.layout.widgets.length && !state.layout.devices.length)) return true;
  return !!(await ask({ title: 'Discard unsaved changes?', text: `${state.file || 'This layout'} has changes that aren't saved.`, ok: 'Discard' }));
}

export async function save() {
  if (!state.file) return saveAs();
  const reply = await api('POST', '/api/save', { layout: state.layout });
  if (reply.ok) {
    state.saved = JSON.stringify(state.layout);
    renderDirty();
    setStatus(`Saved ${state.file}`, 'ok');
  } else {
    setStatus(reply.error, 'error');
  }
}

// The system's file dialog (shown by the server, so only for a browser on its computer):
// the chosen path, null when cancelled, undefined when there is none (ask in the page instead)
async function pickFile(mode, path) {
  if (state.noFileDialog) return undefined;
  const reply = await api('POST', '/api/pick', { mode, path });
  if (reply.unavailable) {
    state.noFileDialog = true;
    return undefined;
  }
  if (!reply.ok) setStatus(reply.error, 'error');
  return reply.ok ? reply.path : null;
}

export async function saveAs() {
  const suggestion = state.file || `${prefs.lastDirectory || ''}layout.json`;
  let path = await pickFile('save', suggestion);
  if (path === undefined) {
    const answer = await ask({ title: 'Save as', fields: [{ name: 'path', label: 'file', value: suggestion, placeholder: 'folder/name.json' }], ok: 'Save' });
    path = answer?.path;
  }
  if (!path) return;
  await flushSync();
  const reply = await api('POST', '/api/save', { layout: state.layout, path });
  if (!reply.ok) return setStatus(reply.error, 'error');
  prefs.lastDirectory = reply.file.replace(/[^\\/]*$/, '');
  state.file = reply.file;
  state.saved = JSON.stringify(state.layout);
  addRecent(reply.file);
  render();
  setStatus(`Saved ${reply.file}`, 'ok');
}

async function openPath(path) {
  if (!(await confirmDiscard())) return;
  const reply = await api('POST', '/api/open', { path });
  if (!reply.ok) return setStatus(`Can't open ${path}: ${reply.error}`, 'error');
  useLayout(reply);
  setStatus(`Opened ${reply.file}`, 'ok');
}

async function newLayout(template = null) {
  if (!(await confirmDiscard())) return;
  const reply = await api('POST', '/api/new', { template });
  if (!reply.ok) return setStatus(reply.error, 'error');
  useLayout(reply);
  setStatus(template ? `New layout from the ${template} template: Save asks where to keep it` : 'New layout', 'ok');
}

async function templates() {
  state.templates ||= (await api('GET', '/api/templates')).templates || [];
  return state.templates;
}

async function showNew() {
  const list = await templates();
  const dialog = newDialog();
  fill(dialog,
    el('h3', {}, 'New layout'),
    el('div', { class: 'choices' },
      el('button', { onclick: () => { dialog.close(); newLayout(); } }, el('b', {}, 'Empty'), el('small', {}, 'A 9x9 grid, nothing on it')),
      list.map((template) => el('button', { dataset: { template: template.name }, onclick: () => { dialog.close(); newLayout(template.name); } },
        el('b', {}, template.title), el('small', {}, template.doc)))),
    el('div', { class: 'buttons' }, el('button', { onclick: () => dialog.close() }, 'Cancel')));
  dialog.showModal();
}

export async function showOpen() {
  const picked = await pickFile('open', state.file || prefs.lastDirectory || null);
  if (picked !== undefined) return picked && openPath(picked);
  const recent = prefs.recent || [];
  const answer = await ask({
    title: 'Open a layout',
    fields: [{ name: 'path', label: 'file', value: state.file || '', placeholder: 'folder/name.json' }],
    ok: 'Open',
    extra: (finish) => [
      recent.length ? [el('p', { class: 'hint' }, 'Recent'), el('ul', { class: 'recent-list' }, recent.map((file) =>
        el('li', { title: file, onclick: () => finish({ path: file }) }, file)))] : null,
      el('p', { class: 'hint' }, el('button', { class: 'link', onclick: () => { finish(null); $('open-file').click(); } },
        'Or import one from this computer (Save then asks where to keep it)…')),
    ],
  });
  if (answer?.path) openPath(answer.path);
}

function download() {
  const blob = new Blob([JSON.stringify(state.layout, null, 2) + '\n'], { type: 'application/json' });
  const link = el('a', { href: URL.createObjectURL(blob), download: state.file ? state.file.split(/[\\/]/).pop() : 'layout.json' });
  link.click();
  URL.revokeObjectURL(link.href);
}

// A layout file from this computer: no path on the server, so Save asks where to keep it
export async function importFile(file) {
  try {
    const layout = JSON.parse(await file.text());
    if (!(await confirmDiscard())) return;
    const reply = await api('POST', '/api/new', { layout });
    if (!reply.ok) throw new Error(reply.error);
    useLayout(reply);
    setStatus(`Imported ${file.name}: Save asks where to keep it`, 'ok');
  } catch (error) {
    setStatus(`Can't open ${file.name}: ${error.message}`, 'error');
  }
}

export function showFileMenu() {
  const list = $('file-list');
  if (!list.hidden) return (list.hidden = true);
  const item = (label, action, keys = null, attrs = {}) => el('button', { role: 'menuitem', ...attrs, onclick: () => { list.hidden = true; action(); } },
    label, keys ? el('span', { class: 'keys' }, keys) : null);
  const recent = (prefs.recent || []).filter((file) => file !== state.file);
  fill(list,
    item('New…', showNew, null, { id: 'menu-new' }),
    item('Open…', showOpen, null, { id: 'menu-open' }),
    recent.length ? [el('div', { class: 'head' }, 'Recent'), recent.map((file) => item(file, () => openPath(file), null, { class: 'recent', title: file }))] : null,
    el('hr'),
    item('Save', save, 'Ctrl+S'),
    item('Save as…', saveAs, 'Ctrl+Shift+S', { id: 'menu-save-as' }),
    el('hr'),
    item('Download', download),
    item('Import from this computer…', () => $('open-file').click()));
  list.hidden = false;
  setTimeout(() => window.addEventListener('pointerdown', function close(event) {
    if (!event.target.closest('.menu-wrap')) list.hidden = true;
    window.removeEventListener('pointerdown', close);
  }), 0);
}

// ---------------------------------------------------------------- starting out

async function detectDevices() {
  const { devices } = await api('GET', '/api/detect');
  return devices || [];
}

function addDeviceOfType(type) {
  change((layout) => {
    layout.devices.push({ type, x: 0, y: 0, options: {} });
    state.selection = { kind: 'device', index: layout.devices.length - 1 };
  });
}

export async function showDetect() {
  const found = await detectDevices();
  const dialog = newDialog();
  fill(dialog,
    el('h3', {}, 'Devices plugged in'),
    found.length
      ? el('div', { class: 'choices' }, found.map((device) => el('button', { onclick: () => { dialog.close(); addDeviceOfType(device.type); } },
        el('b', {}, device.model), el('small', {}, `Add it (${device.type})`))))
      : el('p', { class: 'hint' }, 'None found. Plug one in, or pick one from the list next to Add.'),
    el('div', { class: 'buttons' }, el('button', { onclick: () => dialog.close() }, 'Close')));
  dialog.showModal();
}

// An empty layout invites a template, the device you play on, or the palette
export async function renderWelcome() {
  const empty = !state.layout.widgets.length && !state.layout.devices.length && state.mode === 'edit' && !state.welcomeClosed;
  let card = document.querySelector('.welcome');
  if (!empty) return card?.remove();
  if (card) return;
  card = el('div', { class: 'welcome' });
  $('stage').append(card);
  const list = await templates();
  fill(card, el('div', { class: 'card' },
    el('div', { class: 'props-head' }, el('h3', {}, 'Start a layout'),
      el('button', { class: 'link', title: 'Close', onclick: () => { state.welcomeClosed = true; card.remove(); } }, '✕')),
    el('p', { class: 'hint' }, 'From a template:'),
    el('div', { class: 'choices' }, list.map((template) => el('button', { dataset: { template: template.name }, onclick: () => newLayout(template.name) },
      el('b', {}, template.title), el('small', {}, template.doc)))),
    el('p', { class: 'hint' }, 'Or add the device you play on, then drag widgets from the palette onto the grid.'),
    el('div', { class: 'found' }, el('button', {
      id: 'welcome-detect',
      onclick: async (event) => {
        const found = await detectDevices();
        event.target.replaceWith(found.length
          ? el('div', { class: 'found' }, found.map((device) => el('button', { onclick: () => addDeviceOfType(device.type) }, `Add ${device.model}`)))
          : el('p', { class: 'hint' }, 'No device found: plug one in, or pick one under Devices.'));
      },
    }, 'Detect connected devices'))));
}

export function setMode(mode) {
  state.mode = mode;
  for (const pointer of held.keys()) padUp({ pointerId: pointer });
  if (mode === 'try') openDrawer('events');
  hidePadInfo();
  renderToolbar();
}
