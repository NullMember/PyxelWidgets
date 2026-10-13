// The device list and the properties panel: option editors, animation, the toolbar

import { state, $, fill, el, api } from './core.js';
import { prefs, savePrefs } from './prefs.js';
import { widgetAt, containerSize, allWidgets, deviceInfo, bindingFields, transportControls, deviceSize,
  isGroup, currentPage, addPage, widgetSelection } from './model.js';
import { outputsOf, renderOutputs, outputProperties } from './mappings.js';
import { describeValue } from './links.js';
import { ruleSummary } from './rules.js';
import { drawerPrefs } from './drawer.js';
import { change, flushSync, setStatus } from './history.js';
import { render } from './board.js';
import { renameWidget } from './layers.js';
import { spriteEditor } from './sprite.js';
import { targetGroup, removeSelection, reorder, duplicate, groupSelection, ungroup } from './editing.js';

export function renderDevices() {
  const list = $('devices');
  list.replaceChildren(...state.layout.devices.map((device, index) => {
    const selected = state.selection?.kind === 'device' && state.selection.index === index;
    return el('li', { class: selected ? 'selected' : '', onclick: () => select({ kind: 'device', index }) },
      el('span', { class: 'swatch-device' }),
      el('span', { class: 'label' },
        el('span', { class: 'name' }, deviceInfo(device)?.model || device.type),
        el('span', { class: 'type' }, `at ${device.x || 0}, ${device.y || 0}`),
        // A browser grid: where to open it
        state.hardware.devices?.[index]?.url ? el('a', {
          class: 'type url', href: state.hardware.devices[index].url, target: '_blank', title: 'Open it in a browser on this network',
          onclick: (e) => e.stopPropagation(),
        }, state.hardware.devices[index].url) : null),
      hardwareDot(index),
      connectButton('devices', index));
  }));
  if (!state.layout.devices.length) list.append(el('li', { class: 'hint' }, 'Preview only. Add the hardware the layout runs on.'));
}

export function hardwareDot(index, list = 'devices') {
  const status = state.hardware[list]?.[index];
  if (!status) return el('span', { class: 'dot', title: 'Connecting…' });
  if (!status.connected && !status.error) return el('span', { class: 'dot idle', title: 'Not connected' });
  return el('span', {
    class: `dot ${status.connected ? 'on' : 'off'}`,
    title: status.connected ? (list === 'devices' ? 'Connected: mirrors the preview, pads work the widgets' : 'Connected: sends and receives messages') : status.error,
  });
}

// Connects or disconnects a layout device or output (an on-screen device can't be)
export function connectButton(kind, index) {
  const entry = (kind === 'devices' ? state.layout.devices : outputsOf())[index];
  if (entry?.type?.startsWith('virtual.')) return null;
  const connected = !!state.hardware[kind]?.[index]?.connected;
  return el('button', {
    class: `connect${connected ? ' on' : ''}`,
    title: connected ? 'Disconnect' : (state.hardware[kind]?.[index]?.error || 'Connect'),
    onclick: (event) => {
      event.stopPropagation();
      setConnected(kind, index, !connected);
    },
  }, connected ? 'Disconnect' : 'Connect');
}

async function setConnected(kind, index, connected) {
  // The server connects what's in the layout it has
  await flushSync();
  const reply = await api('POST', '/api/connect', { kind, index, connected });
  if (!reply.ok) return setStatus(reply.error, 'error');
  state.hardware = { devices: reply.devices, outputs: reply.outputs };
  renderDevices();
  renderOutputs();
  const status = state.hardware[kind][index];
  if (connected && !status?.connected) setStatus(`Couldn't connect: ${status?.error}`, 'error');
}

export function select(selection) {
  state.selection = selection;
  render();
}

export function setOption(target, name, value) {
  target.options = target.options || {};
  if (value === undefined) delete target.options[name];
  else target.options[name] = value;
}

// A labelled editor for one option from the catalog schema. `prefix` keeps element ids
// apart; `apply(value)` replaces setting the option on `target` (e.g. on several widgets).
export function optionField(target, option, prefix = 'option', apply = null) {
  if (option.kind === 'frames') return [];
  const options = target.options || {};
  const set = option.name in options;
  const value = set ? options[option.name] : option.default;
  const commit = (newValue) => change(() => (apply ? apply(newValue) : setOption(target, option.name, newValue)));
  const id = `${prefix}-${option.name}`;
  const [control, suggestions] = optionControl(option, value, commit, id);
  return [
    el('label', { for: id, class: set ? 'changed' : '', title: option.name }, option.name.replace(/_/g, ' ')),
    el('div', { class: 'control' }, control, suggestions,
      el('button', { class: 'link reset', title: `Reset to ${JSON.stringify(option.default)}`, onclick: () => commit(undefined) }, 'reset')),
  ];
}

// The input for one option kind (and a datalist of suggestions for rates), with element id `id`
export function optionControl(option, value, commit, id) {
  let control, suggestions;
  switch (option.kind) {
    case 'enum':
      control = el('select', { onchange: (e) => commit(e.target.value) },
        option.choices.map((choice) => el('option', { value: choice, selected: choice === value }, choice)));
      break;
    case 'bool':
      control = el('input', { type: 'checkbox', checked: !!value, onchange: (e) => commit(e.target.checked) });
      break;
    case 'int':
    case 'float':
      control = el('input', {
        type: 'number', step: option.kind === 'int' ? 1 : 0.01, value: value ?? '', placeholder: value == null ? 'auto' : null,
        onchange: (e) => commit(e.target.value === '' ? undefined : (option.kind === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value))),
      });
      break;
    case 'color': {
      const text = value || '#000000';
      const rgb = text.slice(0, 7);
      const alpha = text.length === 9 ? parseInt(text.slice(7), 16) : 255;
      const picker = el('input', { type: 'color', value: rgb, title: 'Color' });
      const slider = el('input', { type: 'range', min: 0, max: 255, value: alpha, title: 'Opacity', 'aria-label': 'Opacity' });
      const shown = el('span', { class: 'alpha', title: 'Opacity' }, `${Math.round(alpha / 2.55)}%`);
      const update = () => commit(picker.value + (Number(slider.value) === 255 ? '' : Number(slider.value).toString(16).padStart(2, '0')));
      picker.addEventListener('change', update);
      slider.addEventListener('input', () => { shown.textContent = `${Math.round(slider.value / 2.55)}%`; });
      slider.addEventListener('change', update);
      control = el('div', { class: 'color' }, picker, slider, shown);
      break;
    }
    case 'point': {
      const point = value || [0, 0];
      const axis = (i) => el('input', {
        type: 'number', step: 0.01, value: point[i],
        onchange: (e) => commit(point.map((v, j) => (j === i ? parseFloat(e.target.value) : v))),
      });
      control = el('div', { class: 'control' }, axis(0), axis(1));
      break;
    }
    case 'rate': {
      // Any note value is accepted; the list only suggests common ones. Some also take seconds.
      const parse = (text) => (option.seconds && /^\d*\.?\d+$/.test(text) ? Number(text) : text || undefined);
      control = el('input', {
        type: 'text', value: value ?? '', list: `${id}-rates`,
        placeholder: value == null ? 'off' : null,
        title: option.seconds ? 'A note value (1/8, bar…) or seconds (0.5)' : 'A note value (1/16, 1/8., beat, bar…)',
        onchange: (e) => commit(parse(e.target.value.trim())),
      });
      suggestions = el('datalist', { id: `${id}-rates` }, option.choices.map((choice) => el('option', { value: choice })));
      break;
    }
    default:
      control = el('input', { type: 'text', value: value ?? '', onchange: (e) => commit(e.target.value) });
  }
  control.id = id;
  return [control, suggestions];
}

// The animation of one or more widgets (several only show one they share)
function animationFields(widgets) {
  const entries = widgets.map((widget) => widget.animation);
  const same = entries.every((entry) => JSON.stringify(entry) === JSON.stringify(entries[0]));
  const type = same ? (entries[0]?.type ?? '') : null;
  const info = type ? state.catalog.animations[type] : null;
  const select = el('select', {
    id: 'animation-type',
    onchange: (e) => change(() => widgets.forEach((widget) => {
      if (e.target.value) widget.animation = { type: e.target.value, options: {} };
      else delete widget.animation;
    })),
  },
  type === null ? el('option', { value: 'mixed', selected: true, disabled: true }, 'mixed') : null,
  el('option', { value: '', selected: type === '' }, 'None'),
  Object.keys(state.catalog.animations).map((name) => el('option', { value: name, selected: name === type }, name)));
  return [
    el('div', { class: 'fields' },
      el('label', { for: 'animation-type', title: 'Changes how the widget looks over time; note values follow the transport' }, 'type'),
      el('div', { class: 'control' }, select),
      info ? info.options.flatMap((option) => optionField(entries[0], option, 'animation',
        widgets.length > 1 ? (value) => widgets.forEach((widget) => setOption(widget.animation, option.name, value)) : null)) : null),
    info ? el('p', { class: 'hint note' }, info.doc.replace(/``/g, '')) : null,
  ];
}

// Several widgets: their shared options and animation, and what can be done to all
function multiProperties(panel, paths) {
  const widgets = paths.map(widgetAt);
  const types = [...new Set(widgets.map((widget) => widget.type))];
  const optionsOf = (type) => state.catalog.widgets[type]?.options || [];
  const shared = optionsOf(types[0]).filter((option) => option.kind !== 'frames'
    && types.every((type) => optionsOf(type).some((other) => other.name === option.name && other.kind === option.kind)));
  // Shows a value when every widget has it
  const common = { options: {} };
  for (const option of shared) {
    const values = widgets.map((widget) => widget.options?.[option.name]);
    if (values[0] !== undefined && values.every((value) => JSON.stringify(value) === JSON.stringify(values[0]))) common.options[option.name] = values[0];
  }
  fill(panel,
    el('div', { class: 'props-head' },
      el('h3', {}, `${widgets.length} widgets`),
      el('div', { class: 'actions' },
        el('button', { onclick: () => duplicate(), title: 'Duplicate (Ctrl+D)' }, 'Duplicate'),
        el('button', { onclick: () => groupSelection(), title: 'Put them in a new Group (Ctrl+G)' }, 'Group'),
        el('button', { class: 'danger', onclick: () => removeSelection(), title: 'Delete (Del)' }, 'Delete'))),
    el('p', { class: 'doc' }, widgets.map((widget) => widget.name).join(', ')),
    shared.length ? [
      el('h4', {}, types.length > 1 ? 'Shared options' : 'Options'),
      el('div', { class: 'fields' }, shared.flatMap((option) => optionField(common, option, 'option',
        (value) => widgets.forEach((widget) => setOption(widget, option.name, value))))),
    ] : null,
    group('behaviour', 'Behaviour', ruleSummary(widgets)),
    group('animation', 'Animation', animationFields(widgets)),
    el('p', { class: 'hint note' }, 'Drag one or use the arrow keys to move them together. Shift+click adds or removes a widget; drag on empty pads to select an area; Shift+click in Layers selects a range.'),
  );
}

function numberInput(label, value, onchange, attrs = {}) {
  return el('label', {}, label, el('input', { type: 'number', value, step: 1, ...attrs, onchange: (e) => onchange(parseInt(e.target.value, 10)) }));
}

// Options most layouts leave alone: shown under "More options"
// Mackie Control's plug-in mode buttons too
export const ADVANCED = new Set(['visible', 'propagation', 'interactive', 'held_time', 'double_press_time',
  'plugin_button', 'channel_button', 'next_page', 'previous_page']);

// A collapsible group of the properties panel; open or closed is remembered in this browser
export function group(key, title, children, { count = null, open = true } = {}) {
  prefs.groups ||= {};
  const details = el('details', { class: 'group', dataset: { group: key } },
    el('summary', {}, title, count ? el('span', { class: 'count' }, count) : null),
    children);
  details.open = prefs.groups[key] ?? open;
  details.addEventListener('toggle', () => {
    prefs.groups[key] = details.open;
    savePrefs();
  });
  return details;
}

// Option fields, the rarely changed ones folded away (open when one of them is set)
export function optionFields(target, options, prefix = 'option') {
  const main = options.filter((option) => !ADVANCED.has(option.name));
  const more = options.filter((option) => ADVANCED.has(option.name));
  const changed = more.some((option) => option.name in (target.options || {}));
  return [
    main.flatMap((option) => optionField(target, option, prefix)),
    more.length ? el('details', { class: 'more', open: changed },
      el('summary', {}, `More options (${more.map((option) => option.name.replace(/_/g, ' ')).join(', ')})`),
      el('div', { class: 'fields' }, more.flatMap((option) => optionField(target, option, prefix)))) : null,
  ];
}

// What changes a widget from elsewhere: links of other widgets, device controls, outputs' feedback
function controlledBy(widget) {
  const items = [];
  for (const link of state.layout.links || []) {
    if (link.target !== widget.name || link.widget === widget.name) continue;
    const what = link.action ? `${link.on} → ${link.action}` : `${link.on} → ${(link.change || 'set').toLowerCase()} ${link.option}`;
    const value = describeValue(link);
    items.push({ from: link.widget, what: value ? `${what} = ${value}` : what, go: () => selectWidgetNamed(link.widget) });
  }
  for (const binding of state.layout.bindings || []) {
    if (binding.widget !== widget.name) continue;
    const device = state.layout.devices[binding.device];
    items.push({ from: deviceInfo(device)?.model || device?.type || 'device', what: `control ${binding.control}`, go: () => select({ kind: 'device', index: binding.device }) });
  }
  for (const mapping of state.layout.mappings || []) {
    if (mapping.widget !== widget.name || !mapping.feedback) continue;
    const index = outputsOf().findIndex((output) => output.name === mapping.output);
    items.push({ from: mapping.output, what: `feedback: ${mapping.message?.type}${mapping.message?.name ? ` ${mapping.message.name}` : ''}`, go: () => select({ kind: 'output', index }) });
  }
  return items;
}

export function selectWidgetNamed(name) {
  const found = allWidgets().find(({ widget }) => widget.name === name);
  if (found) select(widgetSelection([found.path]));
}

export function renderProperties() {
  const panel = $('properties');
  const selection = state.selection;
  if (selection?.kind === 'widget' && selection.paths.length > 1) return multiProperties(panel, selection.paths);
  if (selection?.kind === 'widget') {
    const path = selection.path;
    const widget = widgetAt(path);
    const info = state.catalog.widgets[widget.type];
    const [parentWidth, parentHeight] = containerSize(path);
    const setGeometry = (key) => (value) => {
      if (Number.isNaN(value)) return render();
      // Keep the widget inside its parent, like dragging does
      const x = widget.x || 0, y = widget.y || 0;
      const limits = {
        x: [0, parentWidth - widget.width], y: [0, parentHeight - widget.height],
        width: [1, parentWidth - x], height: [1, parentHeight - y],
      }[key];
      value = Math.max(limits[0], Math.min(limits[1], value));
      if (value === (widget[key] ?? 0)) return render();
      change(() => { widget[key] = value; });
    };
    const incoming = controlledBy(widget);
    const behaviour = (state.layout.mappings || []).filter((mapping) => mapping.widget === widget.name).length
      + (state.layout.links || []).filter((link) => link.widget === widget.name).length + incoming.length;
    fill(panel,
      el('div', { class: 'props-head' },
        el('h3', { title: widget.name }, widget.type),
        el('div', { class: 'actions' },
          el('button', { onclick: () => reorder(path, 1), title: 'Raise: draw above the next widget', 'aria-label': 'Raise' }, '▲'),
          el('button', { onclick: () => reorder(path, -1), title: 'Lower: draw below the previous widget', 'aria-label': 'Lower' }, '▼'),
          el('button', { onclick: () => duplicate(), title: 'Duplicate (Ctrl+D)' }, 'Duplicate'),
          el('button', { class: 'danger', onclick: () => removeSelection(), title: 'Delete (Del)' }, 'Delete'))),
      el('p', { class: 'doc' }, (info?.doc || '').replace(/``/g, '')),
      group('properties', 'Properties', [
      el('div', { class: 'quad' },
        numberInput('x', widget.x || 0, setGeometry('x'), { min: 0, max: parentWidth - 1 }),
        numberInput('y', widget.y || 0, setGeometry('y'), { min: 0, max: parentHeight - 1 }),
        numberInput('width', widget.width, setGeometry('width'), { min: 1 }),
        numberInput('height', widget.height, setGeometry('height'), { min: 1 })),
      el('div', { class: 'fields' },
        el('label', { for: 'widget-name' }, 'name'),
        el('div', { class: 'control' }, el('input', {
          type: 'text', id: 'widget-name', value: widget.name,
          onchange: (e) => renameWidget(widget, e.target.value),
        })),
        optionFields(widget, (info?.options || []).filter((option) => !ADVANCED.has(option.name))),
        info?.bindable ? bindingFields(widget) : null),
      optionFields(widget, (info?.options || []).filter((option) => ADVANCED.has(option.name))),
      widget.type === 'Group' ? el('div', { class: 'actions' }, el('button', { onclick: () => ungroup(path), title: 'Move its widgets out (Ctrl+Shift+G)' }, 'Ungroup')) : null,
      widget.type === 'Pages' ? [
        el('p', { class: 'hint' }, `Page ${currentPage(widget) + 1} of ${widget.widgets?.length || 0} shown. Widgets added from the palette go on it; select a widget in Layers to show its page.`),
        el('div', { class: 'actions' }, el('button', { onclick: () => addPage(path) }, 'Add page')),
      ] : isGroup(widget) ? el('p', { class: 'hint' }, 'Widgets added from the palette go inside this group.') : null,
      ]),
      widget.type === 'Sprite' ? group('frames', 'Frames', spriteEditor(widget)) : null,
      group('behaviour', 'Behaviour', [
        el('h4', {}, 'Changed by'),
        incoming.length
          ? el('ul', { class: 'controlled' }, incoming.map((item) => el('li', { onclick: item.go, title: 'Select it' },
            el('span', { class: 'from' }, item.from), el('span', { class: 'what' }, item.what))))
          : el('p', { class: 'hint' }, 'Nothing changes this widget: links of other widgets, device controls and output feedback show up here.'),
        ruleSummary([widget]),
      ], { count: behaviour || null }),
      group('animation', 'Animation', animationFields([widget]), { count: widget.animation ? widget.animation.type : null }),
    );
    return;
  }
  if (selection?.kind === 'output') return outputProperties(panel, selection.index);
  if (selection?.kind === 'device') {
    const device = state.layout.devices[selection.index];
    const info = deviceInfo(device);
    const [width, height] = deviceSize(device);
    const port = (key, label) => [
      el('label', { for: `device-${key}` }, label),
      el('div', { class: 'control' }, el('input', {
        type: 'text', id: `device-${key}`, value: device[key] || '', placeholder: 'find by name',
        onchange: (e) => change(() => { if (e.target.value) device[key] = e.target.value; else delete device[key]; }),
      })),
    ];
    fill(panel,
      el('h3', {}, info?.model || device.type),
      el('p', { class: 'doc' }, `${device.type} · ${width}×${height} pads${info?.ports?.length ? ` · ports matching ${info.ports.join(', ')}` : ''}`),
      el('div', { class: 'quad' },
        numberInput('x', device.x || 0, (v) => change(() => { device.x = v; })),
        numberInput('y', device.y || 0, (v) => change(() => { device.y = v; })),
        el('label', {}, 'width', el('input', { type: 'number', value: width, disabled: true })),
        el('label', {}, 'height', el('input', { type: 'number', value: height, disabled: true }))),
      el('div', { class: 'fields' },
        info?.ports?.length ? [port('input', 'input port'), port('output', 'output port')] : null,
        optionFields(device, (info?.options || []).filter((option) => !ADVANCED.has(option.name)))),
      optionFields(device, (info?.options || []).filter((option) => ADVANCED.has(option.name))),
      info?.controls?.length ? el('p', { class: 'hint' }, `Controls: ${info.controls.map((c) => c.name).join(', ')}`) : null,
      el('div', { class: 'actions' }, el('button', { class: 'danger', onclick: () => removeSelection() }, 'Remove device')),
    );
    return;
  }
  const { surface } = state.layout;
  const transport = state.layout.transport || {};
  const signature = transport.signature || [4, 4];
  fill(panel,
    el('h3', {}, 'Surface'),
    el('p', { class: 'doc' }, 'The grid widgets are placed on. Devices show parts of it.'),
    el('div', { class: 'quad' },
      numberInput('width', surface.width, (v) => v > 0 && change(() => { surface.width = v; }), { min: 1 }),
      numberInput('height', surface.height, (v) => v > 0 && change(() => { surface.height = v; }), { min: 1 }),
      numberInput('bpm', transport.bpm ?? 120, (v) => v > 0 && change((l) => { l.transport = { ...transport, bpm: v }; }), { min: 1 }),
      el('label', {}, 'time sig.', el('input', {
        type: 'text', value: signature.join('/'), title: 'Beats per bar / beat note value, e.g. 6/8',
        onchange: (e) => {
          const match = e.target.value.match(/^\s*(\d+)\s*\/\s*(\d+)\s*$/);
          if (match && +match[1] > 0 && +match[2] > 0) change((l) => { l.transport = { ...transport, signature: [+match[1], +match[2]] }; });
          else render();
        },
      }))),
    el('p', { class: 'hint' }, 'Select a widget to edit it; Shift+click or drag on empty pads to select several. Drag a device by its name. In Try mode, click pads to press them; hold for a Held event.'),
    syncFields(),
    el('h4', {}, 'Transport controls'),
    transportControls(),
  );
}

// The transport following a DAW's MIDI clock (transport.sync): a virtual port or an input port
function syncFields() {
  const transport = state.layout.transport || {};
  const sync = transport.sync || null;
  const kind = sync ? ('virtual' in sync ? 'virtual' : 'input') : 'off';
  const setSync = (value) => change((layout) => {
    const next = { ...(layout.transport || {}) };
    if (value) next.sync = value;
    else delete next.sync;
    layout.transport = next;
  });
  if (kind === 'input' && !state.ports) {
    state.ports = { inputs: [], outputs: [] };
    api('GET', '/api/ports').then((ports) => { state.ports = ports; if (!state.selection) renderProperties(); });
  }
  return el('div', { class: 'sync' },
    el('h4', {}, 'Sync to a DAW'),
    el('div', { class: 'row' },
      el('select', {
        id: 'sync-kind', 'aria-label': 'Sync',
        onchange: (e) => setSync(e.target.value === 'off' ? null
          : e.target.value === 'virtual' ? { virtual: 'PyxelWidgets Clock' } : { input: state.ports?.inputs?.[0] || 'IAC Driver Bus 1' }),
      }, [['off', 'Off: its own tempo'], ['virtual', 'Virtual port'], ['input', 'MIDI input port']].map(([value, label]) =>
        el('option', { value, selected: kind === value }, label))),
      kind === 'off' ? null : el('input', {
        id: 'sync-port', type: 'text', value: sync[kind], 'aria-label': 'Port name', list: kind === 'input' ? 'sync-ports' : null,
        title: kind === 'virtual' ? 'The name of the port the DAW sends its clock to' : 'The MIDI input the DAW\'s clock comes in through',
        onchange: (e) => { const name = e.target.value.trim(); if (name) setSync({ [kind]: name }); else render(); },
      })),
    kind === 'input' ? el('datalist', { id: 'sync-ports' }, (state.ports?.inputs || []).map((name) => el('option', { value: name }))) : null,
    kind === 'off' ? null : el('p', { id: 'sync-status', class: 'hint sync-status' }, syncStatus()),
    el('p', { class: 'hint' }, kind === 'off'
      ? 'Follow a DAW\'s MIDI clock: its tempo, play, stop and position. Sequencers and Trackers then play with the DAW.'
      : kind === 'virtual'
        ? 'In the DAW, send MIDI clock (and song position) to this port, then play from the DAW. The tempo above is used until the clock arrives.'
        : 'Route the DAW\'s MIDI clock to this input (on macOS the IAC Driver, on Windows loopMIDI), then play from the DAW.'));
}

export function syncStatus() {
  const status = state.hardware.sync;
  if (!status) return '';
  if (!status.connected) return status.error || 'Not connected';
  if (!state.playing) return `Connected${state.bpm ? ` · ${state.bpm} bpm` : ''} · waiting for the DAW to play`;
  return `Following the DAW · ${state.bpm} bpm`;
}

// The Python tab's code comes from the server (pyxelwidgets.codegen): both versions for the layout as it is
export const code = { key: null, data: null, timer: null };

export function renderCode() {
  const drawer = drawerPrefs();
  if (!drawer.open || drawer.tab !== 'python') return;
  const file = state.file ? state.file.split(/[\\/]/).pop() : 'layout.json';
  const key = JSON.stringify([state.layout, file, !!drawer.handlers]);
  const show = () => {
    const data = code.data;
    if (!data) return;
    $('code').textContent = data.ok ? data[drawer.code === 'standalone' ? 'standalone' : 'loader'] : `# The layout has a problem, so there's no code for it:\n# ${data.error}`;
  };
  if (key === code.key) {
    show();
    return;
  }
  code.key = key;
  clearTimeout(code.timer);
  code.timer = setTimeout(async () => {
    const data = await api('POST', '/api/python', { layout: state.layout, file, handlers: !!drawer.handlers });
    if (code.key !== key) return;
    code.data = data;
    show();
  }, 150);
}

export function renderToolbar() {
  $('mode-edit').classList.toggle('active', state.mode === 'edit');
  $('mode-try').classList.toggle('active', state.mode === 'try');
  document.body.classList.toggle('try', state.mode === 'try');
  $('undo').disabled = !state.history.length;
  $('redo').disabled = !state.future.length;
  $('save').title = state.file ? `Save to ${state.file} (Ctrl+S)` : 'Save: choose where to keep it (Ctrl+S)';
  const play = $('play');
  play.textContent = state.playing ? '■ Stop' : '▶ Play';
  play.classList.toggle('on', state.playing);
  // Following a DAW: it plays and stops
  play.disabled = !!state.synced;
  play.title = state.synced ? 'The DAW plays and stops it (Sync on the Surface panel)' : 'Play the transport so Sequencers and Trackers play (Space)';
  if (!state.playing) $('position').textContent = '';
  $('palette-hint').textContent = targetGroup() ? `into ${widgetAt(targetGroup()).name}` : '';
  $('device-count').textContent = state.layout.devices.length || '';
  $('output-count').textContent = outputsOf().length || '';
  const wheel = $('wheel-mode');
  wheel.textContent = prefs.wheel === 'scroll' ? 'Wheel scrolls' : 'Wheel zooms';
  wheel.title = prefs.wheel === 'scroll'
    ? 'The mouse wheel scrolls the grid; Ctrl/Cmd + wheel and pinches zoom. Click: the wheel zooms'
    : 'The mouse wheel zooms around the pointer (Shift + wheel, two-finger scrolls and dragging around the grid move it). Click: the wheel scrolls';
}

export function renderDirty() {
  const dirty = JSON.stringify(state.layout) !== state.saved;
  $('file').classList.toggle('dirty', dirty);
  $('file').textContent = state.file ? state.file.split(/[\\/]/).pop() : 'Unsaved layout';
  $('file').title = state.file || '';
  document.title = `${dirty ? '• ' : ''}PyxelWidgets Designer`;
}
