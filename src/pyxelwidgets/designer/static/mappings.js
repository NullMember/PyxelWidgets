// Outputs and messages (layout.outputs and layout.mappings) and their editors

import { state, $, fill, el, api } from './core.js';
import { trackValueSource } from './drawer.js';
import { change, setStatus } from './history.js';
import { render } from './board.js';
import { learnButton, learnedMessage } from './learn.js';
import { hardwareDot, connectButton, select, optionField, ADVANCED, group, optionFields } from './properties.js';

export const INTEGER_SOURCES = new Set(['x', 'y', 'cell', 'note', 'step', 'row', 'page', 'delta']);

export function outputsOf(layout = state.layout) {
  return layout.outputs || [];
}

export function outputInfo(output) {
  return state.catalog.outputs.find((info) => info.type === output?.type);
}

export function setMappings(layout, mappings) {
  if (mappings.length) layout.mappings = mappings;
  else delete layout.mappings;
}

export function uniqueOutputName(base) {
  const taken = new Set(outputsOf().map((output) => output.name));
  if (!taken.has(base)) return base;
  for (let i = 2; ; i++) if (!taken.has(`${base}${i}`)) return `${base}${i}`;
}

export function addOutput(type = $('output-type').value) {
  const info = state.catalog.outputs.find((output) => output.type === type);
  const base = { 'mackie.MackieControl': 'mackie', 'mackie.HUI': 'hui', 'osc.REAPER': 'reaper', 'osc.OSC': 'osc', 'desktop.Desktop': 'desktop' }[type] || 'midi';
  change((layout) => {
    const name = uniqueOutputName(base);
    // MIDI outputs start as a virtual port other software can pick
    const output = { name, type, ...(info?.midi ? { virtual: `PyxelWidgets ${name}` } : {}), options: {} };
    layout.outputs = [...outputsOf(layout), output];
    state.selection = { kind: 'output', index: layout.outputs.length - 1 };
  });
}

export function removeOutput(index) {
  change((layout) => {
    const [removed] = layout.outputs.splice(index, 1);
    if (!layout.outputs.length) delete layout.outputs;
    setMappings(layout, (layout.mappings || []).filter((mapping) => mapping.output !== removed.name));
    state.selection = null;
  });
}

export function renderOutputs() {
  const list = $('outputs');
  list.replaceChildren(...outputsOf().map((output, index) => {
    const selected = state.selection?.kind === 'output' && state.selection.index === index;
    const count = (state.layout.mappings || []).filter((mapping) => mapping.output === output.name).length;
    return el('li', { class: selected ? 'selected' : '', onclick: () => select({ kind: 'output', index }) },
      el('span', { class: 'swatch-output' }),
      el('span', { class: 'label' },
        el('span', { class: 'name' }, output.name),
        el('span', { class: 'type' }, `${outputInfo(output)?.model || output.type}${count ? ` · ${count} message${count > 1 ? 's' : ''}` : ''}`)),
      hardwareDot(index, 'outputs'),
      connectButton('outputs', index));
  }));
  if (!outputsOf().length) list.append(el('li', { class: 'hint' }, 'MIDI ports, OSC, Mackie Control or HUI that widgets send to.'));
}

export function outputProperties(panel, index) {
  const output = outputsOf()[index];
  const info = outputInfo(output);
  const port = (key, label, placeholder) => [
    el('label', { for: `output-${key}` }, label),
    el('div', { class: 'control' }, el('input', {
      type: 'text', id: `output-${key}`, value: output[key] || '', placeholder,
      onchange: (e) => change(() => { if (e.target.value.trim()) output[key] = e.target.value.trim(); else delete output[key]; }),
    })),
  ];
  const used = (state.layout.mappings || []).filter((mapping) => mapping.output === output.name);
  fill(panel,
    el('h3', {}, info?.model || output.type),
    el('p', { class: 'doc' }, info?.midi
      ? 'Other software (a DAW, a synth) picks the virtual port, or set existing input/output ports instead.'
      : output.type.startsWith('osc.') ? 'Sends OSC to host:send port and listens on the receive port.' : (info?.doc || '').replace(/``/g, '')),
    info && info.auto_connect === false ? el('p', { class: 'hint' },
      'Not connected by itself in the designer: press Connect in Outputs when its actions should happen for real. The event log shows them either way.') : null,
    el('div', { class: 'fields' },
      el('label', { for: 'output-name' }, 'name'),
      el('div', { class: 'control' }, el('input', {
        type: 'text', id: 'output-name', value: output.name,
        onchange: (e) => {
          const name = e.target.value.trim();
          if (!name || outputsOf().some((other) => other !== output && other.name === name)) {
            setStatus(`Output name "${name}" is empty or already used`, 'error');
            return render();
          }
          change((layout) => {
            for (const mapping of layout.mappings || []) if (mapping.output === output.name) mapping.output = name;
            output.name = name;
          });
        },
      })),
      info?.midi ? [port('virtual', 'virtual port', 'none'), port('input', 'input port', 'none'), port('output', 'output port', 'none')] : null,
      (info?.options || []).filter((option) => !ADVANCED.has(option.name)).flatMap((option) => optionField(output, option))),
    optionFields(output, (info?.options || []).filter((option) => ADVANCED.has(option.name))),
    el('p', { class: 'hint note' }, used.length
      ? `${used.length} message${used.length > 1 ? 's' : ''} from ${[...new Set(used.map((m) => m.widget))].join(', ')}.`
      : 'Select a widget and add a message to send its events here.'),
    el('div', { class: 'actions' }, el('button', { class: 'danger', onclick: () => removeOutput(index) }, 'Remove output')),
  );
}

// The event a new message is sent on: the widget's main one
export function defaultEvent(widget) {
  const events = state.catalog.widgets[widget.type]?.events || [];
  return ['Changed', 'Toggled', 'NoteOn', 'StepPlayed', 'RowPlayed', 'ClipStarted', 'TempoTapped', 'PresetRecalled', 'PageChanged', 'Pressed'].find((name) => events.includes(name)) || events[0];
}

// A useful first message for an event on an output
export function defaultMessage(widget, on, info) {
  const accepts = info?.messages || [];
  const source = (name, extra = {}) => ({ source: name, ...extra });
  const xy = widget.type === 'XY';
  if (accepts.includes('Hotkey')) {
    if (on === 'Changed' && xy) return { type: 'MouseMove', x: source('value_x'), y: source('value_y'), relative: false };
    if (on === 'Changed' && widget.type === 'Knob') return { type: 'Scroll', dx: 0, dy: source('delta') };
    if (on === 'Changed' && widget.type === 'Button') return { type: 'Key', keys: 'shift', state: source('value') };
    if (on === 'Changed') return { type: 'Scroll', dx: 0, dy: source('delta') };
    if (on === 'Toggled') return { type: 'Hotkey', keys: 'f{x+1}' };
    return { type: 'Hotkey', keys: 'ctrl+c' };
  }
  if (accepts.includes('Command')) {
    if (on === 'Changed') return { type: 'Command', name: 'Fader 1', value: source(xy ? 'value_x' : 'value') };
    if (on === 'Toggled') return { type: 'Command', name: 'Mute {x+1}', value: source('state') };
    return { type: 'Command', name: 'Play', value: on === 'Released' ? 0 : 1 };
  }
  if (accepts.includes('OscMessage')) {
    if (on === 'Changed') return { type: 'OscMessage', address: '/track/1/volume', args: [source(xy ? 'value_x' : 'value')] };
    if (on === 'Toggled') return { type: 'OscMessage', address: '/track/{x+1}/mute', args: [source('state')] };
    return { type: 'OscMessage', address: '/play', args: [on === 'Released' ? 0 : 1] };
  }
  const cells = widget.width * widget.height > 1 && !['Fader', 'Knob', 'XY', 'Button'].includes(widget.type);
  const note = cells ? source('cell', { offset: 36 }) : 60;
  switch (on) {
    case 'Pressed': return { type: 'NoteOn', note, velocity: source('velocity'), channel: 1 };
    case 'Released': return { type: 'NoteOff', note, velocity: 0, channel: 1 };
    case 'Changed': return { type: 'ControlChange', control: 1, value: source(xy ? 'value_x' : 'value'), channel: 1 };
    case 'Toggled': return { type: 'NoteOn', note: source('cell', { offset: 36 }), velocity: source('state'), channel: 1 };
    case 'NoteOn': return { type: 'NoteOn', note: source('note'), velocity: source('velocity'), channel: 1 };
    case 'NoteOff': return { type: 'NoteOff', note: source('note'), velocity: 0, channel: 1 };
    case 'Pressure': return { type: 'PolyPressure', note, pressure: source('pressure'), channel: 1 };
    case 'StepPlayed': return { type: 'NoteOn', note: source('note'), velocity: source('velocity'), channel: 1 };
    case 'StepEnded': return { type: 'NoteOff', note: source('note'), velocity: 0, channel: 1 };
    default: return { type: 'NoteOn', note: 60, velocity: 127, channel: 1 };
  }
}

// Names of the event values a layout message uses, placeholders included
export function messageSources(message) {
  const found = [];
  const visit = (value) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) found.push(value.source);
    else if (Array.isArray(value)) value.forEach(visit);
    else if (typeof value === 'string') for (const match of value.matchAll(/\{(\w+)/g)) found.push(match[1]);
  };
  for (const [key, value] of Object.entries(message || {})) if (key !== 'type') visit(value);
  return found;
}

// Sources a field can take: the event's values, or (receiving only) anything a message carries
export function sourceNames(on) {
  if (on) return state.catalog.events[on]?.sources || [];
  return [...new Set([...Object.values(state.catalog.events).flatMap((event) => event.sources), 'state', 'text'])];
}

// A field's editor: a constant or one of the event's values (with its range or offset)
function valueEditor(id, value, field, sources, commit) {
  const isSource = value && typeof value === 'object';
  const textual = field.kind === 'text' || field.kind === 'arg';
  const mode = el('select', {
    id, title: 'A constant, or a value from the event',
    onchange: (e) => commit(e.target.value === '' ? (field.range ? field.range[0] : (textual ? '' : 0)) : { source: e.target.value }),
  },
  el('option', { value: '', selected: !isSource }, 'constant'),
  sources.map((name) => el('option', { value: name, selected: isSource && value.source === name }, name)),
  // A source the event doesn't have (e.g. after changing the event)
  isSource && !sources.includes(value.source) ? el('option', { value: value.source, selected: true }, `${value.source} (not available)`) : null);
  const number = (key, placeholder, attrs = {}) => el('input', {
    type: 'number', class: 'small', value: value?.[key] ?? '', placeholder, title: key, ...attrs,
    onchange: (e) => {
      const next = { ...value };
      if (e.target.value === '') delete next[key];
      else next[key] = Number(e.target.value);
      commit(next);
    },
  });
  let detail;
  if (!isSource) {
    detail = el('input', {
      type: textual ? 'text' : 'number', class: textual ? '' : 'small', value: value ?? '',
      ...(field.range ? { min: field.range[0], max: field.range[1], step: 1 } : { step: 'any' }),
      onchange: (e) => {
        const text = e.target.value;
        // OSC arguments: numbers when they look like one
        commit(field.range ? parseInt(text || field.range[0], 10) : (textual && !/^-?\d*\.?\d+$/.test(text) ? text : Number(text)));
      },
    });
  } else if (INTEGER_SOURCES.has(value.source)) {
    detail = number('offset', '+0', { step: 1 });
  } else if (value.source === 'text') {
    detail = null;
  } else {
    detail = el('span', { class: 'range', title: 'The range 0.0-1.0 covers' },
      number('min', field.range ? String(field.range[0]) : '0'), '–', number('max', field.range ? String(field.range[1]) : '1'));
  }
  return el('div', { class: 'control value' }, mode, detail);
}

const COMMAND_KINDS = [
  ['button', 'Buttons'], ['fader', 'Faders'], ['relative', 'V-Pots and jog wheel (steps)'],
  ['display', 'Displays (received)'], ['meter', 'Meters (received)'],
];

// An output's commands for a picker: by kind, then numbered families as one per pad ('Mute {x+1}')
function commandChoices(info) {
  const commands = info?.commands || [];
  if (!commands.length) return [];
  const groups = COMMAND_KINDS.map(([kind, label]) => ({
    label, items: commands.filter((command) => command.kind === kind).map((command) => ({ value: command.name, kind })),
  }));
  const families = new Map();
  for (const command of commands) {
    const match = command.name.match(/^(.*\D) 1$/);
    if (match && commands.some((other) => other.name === `${match[1]} 2`)) families.set(`${match[1]} {x+1}`, command.kind);
  }
  groups.push({ label: 'One per pad column: {x+1} (use {y+1} or {cell+1} by typing)', items: [...families].map(([value, kind]) => ({ value, kind })) });
  return groups.filter((group) => group.items.length);
}

function addressChoices(info) {
  const addresses = info?.addresses || [];
  return addresses.length ? [{ label: info.model, items: addresses.map((value) => ({ value })) }] : [];
}

// Set a picked command (or address) and give the message a value that suits it
function pickName(widget, mapping, field, item) {
  change(() => {
    mapping.message[field] = item.value;
    if (mapping.message.type !== 'Command' || !item.kind) return;
    const xy = widget.type === 'XY';
    const wanted = { fader: xy ? 'value_x' : 'value', meter: 'value', relative: 'delta', display: 'text' }[item.kind];
    if (item.kind === 'display' || item.kind === 'meter') {
      // Only the DAW sends these
      delete mapping.on;
      mapping.feedback = true;
    }
    if (wanted) mapping.message.value = { source: wanted };
    else if (typeof mapping.message.value === 'object') mapping.message.value = mapping.on === 'Released' ? 0 : 1;
    // Sent on an event that has every value it uses ({x+1} needs x), else only received
    const needed = messageSources(mapping.message);
    if (mapping.on && !needed.every((name) => sourceNames(mapping.on).includes(name))) {
      const event = (state.catalog.widgets[widget.type]?.events || []).find((name) => needed.every((source) => sourceNames(name).includes(source)));
      if (event) mapping.on = event;
      else {
        delete mapping.on;
        mapping.feedback = true;
      }
    }
  });
}

// Browser key names → the keyboard output's ('KeyA' → 'a', 'ArrowUp' → 'up')
const KEY_CODES = {
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Enter: 'enter', NumpadEnter: 'enter',
  Space: 'space', Tab: 'tab', Escape: 'esc', Backspace: 'backspace', Delete: 'delete', CapsLock: 'caps_lock',
  Home: 'home', End: 'end', PageUp: 'page_up', PageDown: 'page_down',
  MediaPlayPause: 'media_play_pause', MediaTrackNext: 'media_next', MediaTrackPrevious: 'media_previous',
  AudioVolumeUp: 'media_volume_up', AudioVolumeDown: 'media_volume_down', AudioVolumeMute: 'media_volume_mute',
};
const MODIFIERS = { Control: 'ctrl', Shift: 'shift', Alt: 'alt', Meta: 'cmd' };

function keyName(event) {
  if (KEY_CODES[event.code]) return KEY_CODES[event.code];
  if (/^F\d+$/.test(event.code)) return event.code.toLowerCase();
  if (/^Key[A-Z]$/.test(event.code)) return event.code.slice(3).toLowerCase();
  if (/^Digit\d$/.test(event.code)) return event.code.slice(5);
  return event.key.length === 1 ? (event.key === '+' ? 'plus' : event.key.toLowerCase()) : null;
}

// Wait for a key combination; resolves with 'ctrl+shift+s' (or modifiers alone, released), or null on Escape
function recordKeys() {
  return new Promise((resolve) => {
    const held = [];
    const finish = (keys) => {
      window.removeEventListener('keydown', down, true);
      window.removeEventListener('keyup', up, true);
      resolve(keys);
    };
    const down = (event) => {
      event.preventDefault();
      event.stopPropagation();
      const modifier = MODIFIERS[event.key];
      if (modifier) {
        if (!held.includes(modifier)) held.push(modifier);
        return;
      }
      if (event.key === 'Escape' && !held.length) return finish(null);
      const key = keyName(event);
      if (key) finish([...held, key].join('+'));
    };
    const up = (event) => {
      event.preventDefault();
      event.stopPropagation();
      // Only modifiers pressed (e.g. Shift to hold)
      if (MODIFIERS[event.key] && held.length) finish(held.join('+'));
    };
    window.addEventListener('keydown', down, true);
    window.addEventListener('keyup', up, true);
  });
}

// A keys field: typed ('ctrl+shift+s', 'f{x+1}') or recorded by pressing them
function keysField(id, value, info, commit) {
  const input = el('input', {
    type: 'text', id, value: value ?? '', list: `${id}-names`, placeholder: 'ctrl+shift+s',
    title: 'Keys joined with +: ctrl, shift, alt, cmd, enter, f1-f20, up, media_play_pause... or single characters',
    onchange: (e) => commit(e.target.value.trim()),
  });
  const record = el('button', {
    id: `${id}-record`, title: 'Press the keys to use (Escape cancels)',
    onclick: async () => {
      record.textContent = 'Press keys…';
      record.classList.add('active');
      const keys = await recordKeys();
      record.classList.remove('active');
      record.textContent = 'Record';
      if (keys) commit(keys);
    },
  }, 'Record');
  return [
    el('label', { for: id }, 'keys'),
    el('div', { class: 'control' }, input, record,
      el('datalist', { id: `${id}-names` }, (info?.keys || []).map((name) => el('option', { value: name })))),
  ];
}

const SCANS = { track: 'tracks', plugin: 'plugins', parameter: 'parameters' };
const SCAN_HINTS = {
  track: 'A track of the DAW: Scan reads them from the Mackie Control display (7 characters at most)',
  plugin: 'A plug-in on the track: Scan opens the DAW\'s plug-in mode for the track',
  parameter: 'A parameter of the plug-in: Scan opens it and pages through its parameters',
};

// What an output scanned for PluginParameter's track, plugin or parameter (null: not scanned)
function scannedNames(output, name, message) {
  const scans = state.scans[output?.name];
  if (!scans) return null;
  if (name === 'track') return scans.tracks?.length ? scans.tracks : null;
  if (name === 'plugin') return scans.plugins?.[message.track] || null;
  return scans.parameters?.[`${message.track}/${message.plugin}`] || null;
}

async function scanDaw(output, what, message, button) {
  const index = outputsOf().indexOf(output);
  button.textContent = 'Scanning…';
  button.disabled = true;
  setStatus(what === 'tracks' ? 'Scanning the DAW\'s tracks…' : `Scanning ${what === 'plugins' ? `the plug-ins on ${message.track}` : `the parameters of ${message.plugin}`}…`, '');
  const result = await api('POST', '/api/scan', { output: index, what, track: message.track, plugin: message.plugin });
  if (!result.ok) {
    setStatus(result.error, 'error');
  } else {
    state.scans[output.name] = result.scanned;
    setStatus(result.names.length ? `Found ${result.names.length} ${what}` : `No ${what} found`, result.names.length ? 'ok' : 'error');
  }
  render();
}

// PluginParameter's track, plugin and parameter: picked from a scan of the DAW, or typed
function scanField(id, name, mapping, output, commit) {
  const message = mapping.message;
  if (output && !(output.name in state.scans)) {
    // What earlier scans found (the output keeps them while connected)
    state.scans[output.name] = null;
    api('POST', '/api/scan', { output: outputsOf().indexOf(output), what: 'known' }).then((result) => {
      if (result.ok && result.scanned) {
        state.scans[output.name] = result.scanned;
        render();
      }
    });
  }
  const value = message[name] ?? '';
  const names = scannedNames(output, name, message);
  const known = names?.includes(value);
  const input = el('input', {
    type: 'text', id, value, hidden: !!(names && (known || !value)), placeholder: { track: 'Track name', plugin: 'Plug-in name', parameter: 'Parameter name' }[name],
    title: SCAN_HINTS[name], onchange: (e) => commit(e.target.value.trim()),
  });
  const picker = names ? el('select', {
    id: `${id}-pick`, title: SCAN_HINTS[name],
    onchange: (e) => {
      if (e.target.value === '\u0000') {
        input.hidden = false;
        return input.focus();
      }
      commit(e.target.value);
    },
  },
  value && !known ? null : el('option', { value: '', selected: !value, disabled: true }, `Pick a ${name}`),
  names.map((item) => el('option', { value: item, selected: item === value }, item)),
  el('option', { value: '\u0000', selected: !!(value && !known) }, 'Type a name…')) : null;
  const missing = name === 'plugin' ? !message.track : name === 'parameter' ? !(message.track && message.plugin) : false;
  const scan = el('button', {
    id: `${id}-scan`, disabled: missing,
    title: missing ? `Pick the ${name === 'plugin' ? 'track' : 'track and plug-in'} first` : `${SCAN_HINTS[name].split(': ')[1]} (connect the output first)`,
    onclick: () => scanDaw(output, SCANS[name], message, scan),
  }, 'Scan');
  return [
    el('label', { for: names ? `${id}-pick` : id }, name),
    el('div', { class: 'control scan' }, picker, input, scan),
  ];
}

export function mappingCard(widget, mapping, index) {
  const events = state.catalog.widgets[widget.type]?.events || [];
  const output = outputsOf().find((candidate) => candidate.name === mapping.output);
  const info = outputInfo(output);
  const message = mapping.message || {};
  const schema = state.catalog.messages[message.type];
  const id = (name) => `mapping-${index}-${name}`;
  const edit = (mutate) => change(() => mutate(mapping));
  const sources = sourceNames(mapping.on);
  const setField = (name) => (value) => edit(() => {
    mapping.message[name] = value;
    // A track's volume follows a value, its pan steps or a value, mute/solo/record a state
    if (mapping.message.type === 'TrackParameter' && name === 'parameter') {
      const source = trackValueSource(value, info, sourceNames(mapping.on));
      if (source) mapping.message.value = { source };
    }
  });
  const fieldEditors = (schema?.fields || []).flatMap((field) => {
    if (field.kind === 'list') {
      // OSC arguments
      const args = message.args || [];
      return [
        el('label', {}, 'arguments'),
        el('div', { class: 'args' },
          args.map((arg, i) => el('div', { class: 'arg' },
            valueEditor(id(`arg${i}`), arg, { kind: 'arg' }, sources, (value) => edit(() => { mapping.message.args[i] = value; })),
            el('button', { class: 'link', title: 'Remove', onclick: () => edit(() => { mapping.message.args.splice(i, 1); }) }, '×'))),
          el('button', { class: 'link', onclick: () => edit(() => { mapping.message.args = [...args, { source: sources.includes('value') ? 'value' : sources[0] || 'value' }]; }) }, '+ argument')),
      ];
    }
    const value = field.name in message ? message[field.name] : field.default;
    if (field.kind === 'choice') {
      return [el('label', { for: id(field.name) }, field.name), el('div', { class: 'control' }, el('select', {
        id: id(field.name), onchange: (e) => setField(field.name)(e.target.value),
      }, field.choices.map((choice) => el('option', { value: choice, selected: choice === value }, choice))))];
    }
    if (field.kind === 'bool') {
      return [el('label', { for: id(field.name) }, field.name), el('div', { class: 'control' }, el('input', {
        type: 'checkbox', id: id(field.name), checked: !!value, onchange: (e) => setField(field.name)(e.target.checked),
      }))];
    }
    if (field.kind === 'keys') return keysField(id(field.name), value, info, setField(field.name));
    if (field.kind === 'scan') return scanField(id(field.name), field.name, mapping, output, setField(field.name));
    if (field.kind === 'text') {
      const groups = message.type === 'Command' ? commandChoices(info) : message.type === 'OscMessage' ? addressChoices(info) : [];
      const known = groups.some((group) => group.items.some((item) => item.value === value));
      const input = el('input', {
        type: 'text', id: id(field.name), value: value ?? '', hidden: !!(groups.length && known),
        title: 'Placeholders like {x+1} take a value from the event', onchange: (e) => setField(field.name)(e.target.value),
      });
      const picker = groups.length ? el('select', {
        id: id(`${field.name}-pick`), title: 'Pick one, or Custom to type a name with {x+1} placeholders',
        onchange: (e) => {
          if (e.target.value === '') {
            input.hidden = false;
            return input.focus();
          }
          const item = groups.flatMap((group) => group.items).find((candidate) => candidate.value === e.target.value);
          pickName(widget, mapping, field.name, item);
        },
      },
      groups.map((group) => el('optgroup', { label: group.label },
        group.items.map((item) => el('option', { value: item.value, selected: item.value === value }, item.value)))),
      el('option', { value: '', selected: !known }, 'Custom…')) : null;
      return [
        el('label', { for: id(groups.length ? `${field.name}-pick` : field.name) }, field.name),
        el('div', { class: 'control picker' }, picker, input),
      ];
    }
    return [el('label', { for: id(field.name) }, field.name), valueEditor(id(field.name), value, field, sources, setField(field.name))];
  });
  return el('div', { class: 'mapping' },
    el('div', { class: 'mapping-head' },
      el('select', {
        id: id('on'), title: 'The widget event that sends it; receive only: just feedback',
        onchange: (e) => edit(() => {
          if (e.target.value) {
            mapping.on = e.target.value;
            // A message using values the new event doesn't have becomes its default one
            const available = sourceNames(mapping.on);
            if (messageSources(mapping.message).some((name) => !available.includes(name))) {
              mapping.message = defaultMessage(widget, mapping.on, info);
            }
          } else {
            delete mapping.on;
            mapping.feedback = true;
          }
        }),
      },
      events.map((name) => el('option', { value: name, selected: name === mapping.on }, name)),
      el('option', { value: '', selected: !mapping.on }, 'receive only')),
      el('span', { class: 'arrow' }, '→'),
      el('select', {
        id: id('output'),
        onchange: (e) => edit(() => {
          mapping.output = e.target.value;
          const next = outputInfo(outputsOf().find((candidate) => candidate.name === mapping.output));
          // A message the new output can't send becomes its default one
          if (!next?.messages.includes(mapping.message?.type)) mapping.message = defaultMessage(widget, mapping.on, next);
        }),
      }, outputsOf().map((candidate) => el('option', { value: candidate.name, selected: candidate.name === mapping.output }, candidate.name))),
      el('button', {
        class: 'link remove', title: 'Remove this message',
        onclick: () => change((layout) => setMappings(layout, layout.mappings.filter((_, i) => i !== index))),
      }, '×')),
    el('div', { class: 'fields' },
      el('label', { for: id('type') }, 'message'),
      el('div', { class: info?.receives === false ? 'control' : 'control learnable' }, el('select', {
        id: id('type'),
        onchange: (e) => edit(() => {
          const type = e.target.value;
          const fields = state.catalog.messages[type].fields;
          // Keep the fields both types have
          const next = { type };
          for (const field of fields) if (field.name in mapping.message && field.kind !== 'list') next[field.name] = mapping.message[field.name];
          if (type === 'OscMessage') Object.assign(next, { address: mapping.message.address || '/', args: mapping.message.args || [] });
          // A knob or fader turns a plug-in parameter by its steps (Mackie Control), or sets it (REAPER)
          const value = info?.parameter_value || 'delta';
          if (type === 'PluginParameter' && sourceNames(mapping.on).includes(value)) next.value = { source: value };
          if (type === 'TrackParameter') {
            const source = trackValueSource(next.parameter || 'Volume', info, sourceNames(mapping.on));
            if (source) next.value = { source };
          }
          mapping.message = next;
        }),
      }, (info?.messages || Object.keys(state.catalog.messages)).map((type) => el('option', { value: type, selected: type === message.type }, type))),
      // What the DAW sends fills it in (channel, note, controller, address...)
      info?.receives === false || !output ? null : learnButton(id('message'), 'message', (event) => edit(() => {
        mapping.message = learnedMessage(mapping.message || {}, event._learn);
      }), mapping.output)),
      fieldEditors,
      // Outputs that send nothing back (the keyboard and mouse) have no feedback
      info?.receives === false ? null : [
        el('label', { for: id('feedback'), title: 'Matching messages from the output update the widget' }, 'feedback'),
        el('div', { class: 'control' }, el('input', {
          type: 'checkbox', id: id('feedback'), checked: !!mapping.feedback, disabled: !mapping.on,
          onchange: (e) => edit(() => { if (e.target.checked) mapping.feedback = true; else delete mapping.feedback; }),
        }))]),
  );
}
