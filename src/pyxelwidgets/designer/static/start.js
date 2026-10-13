// The start window, floating over the page: a new layout (empty or from a template), the device you
// play on with snippets that fit its grid, and an output for other software. It opens on an empty
// layout and from File > New, and closes itself once widgets are added or something else is pressed

import { state, $, el, fill, thumb } from './core.js';
import { deviceInfo, deviceSize } from './model.js';
import { addOutput, outputsOf } from './mappings.js';
import { change } from './history.js';
import { insertSnippet } from './snippets.js';
import { newLayout, templates, detectDevices } from './files.js';

// Outputs offered for other software: [type, title, what for]
const OUTPUTS = [
  ['midi_port.MidiPort', 'MIDI port', 'Notes and controls to a DAW or synth'],
  ['mackie.MackieControl', 'Mackie Control', 'A DAW mixer: faders, mutes, transport'],
  ['osc.REAPER', 'REAPER (OSC)', 'REAPER tracks and plug-ins'],
];

export function openStart() {
  state.start = { open: true, widgets: state.layout.widgets.length, found: null };
  renderStart();
}

// A press elsewhere on the page (not in a dialog it opened) closes it, like a popover
window.addEventListener('pointerdown', (event) => {
  if (state.start?.open && !event.target.closest('#start, dialog, #file-menu, .menu')) closeStart();
}, true);

export function closeStart() {
  if (!state.start?.open) return;
  state.start.open = false;
  renderStart();
}

// Called on every render: closes once widgets were added (from the palette, a snippet...)
export function renderStart() {
  const start = state.start;
  if (start?.open && state.layout.widgets.length !== start.widgets) start.open = false;
  let box = $('start');
  if (!start?.open) return box?.remove();
  const key = JSON.stringify([start.found, state.layout.devices, outputsOf().map((output) => output.type), !!state.templates, (state.snippets || []).length]);
  if (box && box.dataset.key === key) return;
  if (!box) {
    box = el('div', { id: 'start', class: 'start-window', role: 'dialog', 'aria-label': 'Start a layout' });
    document.body.append(box);
    if (!state.templates) templates().then(() => renderStart());
  }
  box.dataset.key = key;
  fill(box,
    el('div', { class: 'start-head' }, el('h3', {}, 'Start a layout'),
      el('button', { class: 'link', id: 'start-close', title: 'Close (Escape)', onclick: closeStart }, '✕')),
    el('section', {},
      el('h4', {}, '1. Start from'),
      el('div', { class: 'choices' },
        el('button', { dataset: { template: '' }, onclick: () => startEmpty() }, el('b', {}, 'Empty layout'), el('small', {}, 'A blank grid: add a device, then widgets')),
        (state.templates || []).map((template) => el('button', { dataset: { template: template.name }, onclick: async () => { if (await newLayout(template.name)) closeStart(); } },
          el('b', {}, template.title), el('small', {}, template.doc))))),
    el('section', {}, el('h4', {}, '2. The device you play on'), deviceStep()),
    el('section', {}, el('h4', {}, '3. Sending to software (optional)'),
      el('div', { class: 'choices' }, OUTPUTS.map(([type, title, doc]) => {
        const added = outputsOf().some((output) => output.type === type);
        return el('button', { dataset: { output: type }, disabled: added, onclick: () => addOutput(type) },
          el('b', {}, added ? `${title} ✓` : title), el('small', {}, added ? 'Added: give it messages from a widget\'s Behaviour' : doc));
      }))),
    el('div', { class: 'buttons' }, el('button', { class: 'primary', id: 'start-done', onclick: closeStart }, 'Done')));
}

async function startEmpty() {
  const blank = !state.layout.widgets.length && !state.layout.devices.length && !outputsOf().length;
  if (blank || await newLayout()) closeStart();
}

function deviceStep() {
  const devices = state.layout.devices;
  if (devices.length) {
    const [width, height] = deviceSize(devices[0]);
    const fitting = (state.snippets || [])
      .filter((entry) => entry.size[0] <= width && entry.size[1] <= height)
      // Those filling the grid first, then the biggest
      .sort((a, b) => (b.size[0] * b.size[1]) - (a.size[0] * a.size[1]));
    return [
      el('p', { class: 'hint' }, `${deviceInfo(devices[0])?.model || devices[0].type} added (${width}x${height}). A ready-made piece for it, or drag widgets from the palette:`),
      el('div', { class: 'snippet-choices' }, fitting.slice(0, 8).map((entry) => el('button', {
        dataset: { snippet: entry.id }, title: entry.doc, onclick: () => insertSnippet(entry.snippet, null),
      }, thumb(entry.preview, 40), el('span', {}, entry.title), el('small', {}, `${entry.size[0]}x${entry.size[1]}`)))),
    ];
  }
  if (state.start.found === null) {
    return [
      el('p', { class: 'hint' }, 'Plug in your controller, then:'),
      el('div', { class: 'found' }, el('button', {
        id: 'start-detect',
        onclick: async () => {
          state.start.found = await detectDevices();
          renderStart();
        },
      }, 'Detect connected devices')),
      el('p', { class: 'hint' }, 'Or pick one under Devices in the left panel.'),
    ];
  }
  if (!state.start.found.length) return el('p', { class: 'hint' }, 'No device found: plug one in and detect again, or pick one under Devices.');
  return el('div', { class: 'choices' }, state.start.found.map((device) => el('button', { onclick: () => addFirstDevice(device.type) },
    el('b', {}, `Add ${device.model}`), el('small', {}, device.type))));
}

// The first device of an empty layout: the surface takes its size
function addFirstDevice(type) {
  change((layout) => {
    const entry = { type, x: 0, y: 0, options: {} };
    if (!layout.widgets.length && !layout.devices.length) {
      const [width, height] = deviceSize(entry);
      layout.surface = { ...layout.surface, width, height };
    }
    layout.devices.push(entry);
    state.selection = { kind: 'device', index: layout.devices.length - 1 };
  });
}
