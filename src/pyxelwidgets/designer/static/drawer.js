// The drawer under the grid: events, connections, Python, problems

import { state, $, fill, el } from './core.js';
import { prefs, savePrefs } from './prefs.js';
import { widgetAt, allWidgets, deviceInfo, widgetSelection, selectedPaths, isControlRule, ruleLabel, selectOwner, deviceControls } from './model.js';
import { outputsOf, outputInfo } from './mappings.js';
import { linkOptions, describeValue } from './links.js';
import { openRules } from './rules.js';
import { setStatus } from './history.js';
import { renderBoard, renderOverlay, clamp } from './board.js';
import { select, selectWidgetNamed, code, renderCode } from './properties.js';

const CLOCK_EVENTS = new Set(['StepPlayed', 'StepEnded', 'RowPlayed', 'ClipQueued', 'ClipStarted', 'ClipStopped', 'PageChanged', 'PageShown', 'ColumnChanged', 'RowChanged']);

export function drawerPrefs() {
  prefs.drawer ||= { open: true, tab: 'events', height: 230, filter: 'all', handlers: false, code: 'loader' };
  return prefs.drawer;
}

export function openDrawer(tab) {
  const drawer = drawerPrefs();
  drawer.open = true;
  if (tab) drawer.tab = tab;
  savePrefs();
  renderDrawer();
}

export function renderDrawer() {
  const drawer = drawerPrefs();
  $('drawer').classList.toggle('collapsed', !drawer.open);
  document.documentElement.style.setProperty('--drawer', `${drawer.height}px`);
  $('drawer-toggle').textContent = drawer.open ? '▾' : '▴';
  const problems = findProblems();
  const counts = { connections: connectionRows().length, problems: problems.length };
  for (const button of document.querySelectorAll('.tabs button')) {
    const tab = button.dataset.tab;
    button.classList.toggle('active', tab === drawer.tab && drawer.open);
    fill(button, button.dataset.label || (button.dataset.label = button.textContent),
      counts[tab] ? el('span', { class: 'count' }, counts[tab]) : null);
  }
  for (const panel of document.querySelectorAll('.drawer-body > [data-panel]')) panel.classList.toggle('shown', panel.dataset.panel === drawer.tab);
  if (drawer.tab === 'events') renderEvents();
  const tools = $('drawer-tools');
  if (drawer.tab === 'events') {
    fill(tools,
      el('select', {
        id: 'event-filter', title: 'Which events to show',
        onchange: (e) => { drawer.filter = e.target.value; savePrefs(); renderEvents(); },
      }, [['all', 'All events'], ['selected', 'Selected widget'], ['quiet', 'Without clock events'], ['debug', 'Only debug']].map(([value, label]) =>
        el('option', { value, selected: drawer.filter === value }, label))),
      el('button', {
        id: 'pause-events', class: state.eventsPaused ? 'active' : '', title: 'Pause the list (events are still kept)',
        onclick: () => { state.eventsPaused = !state.eventsPaused; renderDrawer(); renderEvents(); },
      }, state.eventsPaused ? 'Resume' : 'Pause'),
      el('button', { id: 'clear-events', class: 'link', onclick: () => { state.eventLog = []; renderEvents(); } }, 'clear'));
  } else if (drawer.tab === 'python') {
    fill(tools,
      el('div', { class: 'segmented', role: 'group', 'aria-label': 'Which code' },
        [['loader', 'Layout file', 'Load the layout file and run it'],
          ['standalone', 'Standalone', 'Build the same surface in code, without the layout file']].map(([value, label, title]) =>
          el('button', {
            id: `code-${value}`, class: (drawer.code || 'loader') === value ? 'active' : '', title,
            onclick: () => { drawer.code = value; savePrefs(); renderDrawer(); },
          }, label))),
      el('label', { title: 'Print each widget\'s main event' },
        el('input', { type: 'checkbox', id: 'code-handlers', checked: !!drawer.handlers, onchange: (e) => { drawer.handlers = e.target.checked; savePrefs(); renderCode(); } }),
        ' with handlers'),
      el('button', {
        id: 'copy-code', class: 'link',
        onclick: async () => {
          await navigator.clipboard?.writeText($('code').textContent);
          setStatus('Copied the Python snippet', 'ok');
        },
      }, 'copy'));
    renderCode();
  } else {
    tools.replaceChildren();
  }
  renderConnections();
  renderProblems(problems);
}

// Every link, message and binding: [kind, from, to, what, select]
function connectionRows() {
  const rows = [];
  (state.layout.links || []).forEach((link, index) => {
    const to = link.target || (link.action === 'debug' ? 'Debug log' : 'Transport');
    const what = link.action ? `${link.on} → ${link.action.replace(/^transport\./, '')}` : `${link.on} → ${(link.change || 'set').toLowerCase()} ${link.option}`;
    const value = describeValue(link);
    rows.push(['link', ruleLabel(link), to, value ? `${what} = ${value}` : what, () => openRules([{ kind: 'link', index }])]);
  });
  (state.layout.mappings || []).forEach((mapping, index) => {
    const message = mapping.message || {};
    const what = `${mapping.on || 'receive only'} → ${message.type}${message.name ? ` ${message.name}` : ''}${message.address ? ` ${message.address}` : ''}${mapping.feedback ? ' · feedback' : ''}`;
    rows.push(['message', ruleLabel(mapping), mapping.output, what, () => openRules([{ kind: 'mapping', index }])]);
  });
  for (const binding of state.layout.bindings || []) {
    const device = state.layout.devices[binding.device];
    const from = `${deviceInfo(device)?.model || device?.type} ${binding.control}`;
    rows.push(['binding', from, binding.widget || binding.action, binding.widget ? (binding.options?.takeover || '') : 'action', () => select({ kind: 'device', index: binding.device })]);
  }
  return rows;
}

function renderConnections() {
  const rows = connectionRows();
  fill($('connections'), rows.length
    ? el('table', {},
      el('tr', {}, ['', 'From', 'To', 'What'].map((head) => el('th', {}, head))),
      rows.map(([kind, from, to, what, go]) => el('tr', { class: 'connection', onclick: go, title: 'Select it' },
        el('td', { class: 'kind' }, kind), el('td', {}, from), el('td', {}, to), el('td', {}, what))))
    : el('p', { class: 'hint' }, 'No links, messages or bindings yet: add them on a widget, under Behaviour.'));
}

// Things that won't work as the layout is: [level ('error' or 'warning'), text, select]
// The event value a TrackParameter's parameter takes on an output (null: the event has none that fits)
export function trackValueSource(parameter, info, sources) {
  const wanted = parameter === 'Volume' ? ['value']
    : parameter === 'Pan' ? [info?.parameter_value || 'delta']
    : ['state', 'value'];
  return wanted.find((name) => sources.includes(name)) || null;
}

function findProblems() {
  const problems = [];
  if (state.error) problems.push(['error', state.error, null]);
  for (const mapping of state.layout.mappings || []) {
    const message = mapping.message || {};
    if (isControlRule(mapping) && !state.layout.devices[mapping.device]) continue;
    if (message.type === 'PluginParameter' && !(message.track && message.plugin && message.parameter)) {
      problems.push(['warning', `${ruleLabel(mapping)}: pick the track, plug-in and parameter it controls`, () => selectOwner(mapping)]);
    }
    if (message.type === 'TrackParameter' && !message.track) {
      problems.push(['warning', `${ruleLabel(mapping)}: pick the track it controls`, () => selectOwner(mapping)]);
    }
  }
  for (const formula of state.formulas) {
    problems.push(['warning', `${formula.widget}.${formula.option}: ${formula.error}`, () => selectWidgetNamed(formula.widget)]);
  }
  if (state.hardware.sync?.error) problems.push(['warning', `Sync to a DAW: ${state.hardware.sync.error}`, () => select(null)]);
  const names = new Map(allWidgets().map(({ widget, path }) => [widget.name, { widget, path }]));
  const outputs = new Set(outputsOf().map((output) => output.name));
  // Rules from device controls: the device is there and has the control
  const controlProblem = (object, what) => {
    const device = state.layout.devices[object.device];
    if (!device) return problems.push(['error', `A ${what} from a control of a missing device ${object.device + 1}`, null]);
    if (!deviceControls(device).some((control) => control.name === object.control)) {
      problems.push(['warning', `${ruleLabel(object)}: the device has no control "${object.control}" (on a Launchpad, side buttons are controls with side buttons off)`, () => selectOwner(object)]);
    }
    return false;
  };
  for (const link of state.layout.links || []) {
    if (isControlRule(link) ? controlProblem(link, 'link') : !names.has(link.widget)) {
      if (!isControlRule(link)) problems.push(['error', `A link from a missing widget "${link.widget}"`, null]);
    } else if (link.target && !names.has(link.target)) problems.push(['error', `${ruleLabel(link)}: links to a missing widget "${link.target}"`, () => selectOwner(link)]);
    else if (link.option && !linkOptions(names.get(link.target).widget).some((option) => option.name === link.option)) {
      problems.push(['error', `${ruleLabel(link)}: ${link.target} has no option "${link.option}"`, () => selectOwner(link)]);
    }
  }
  for (const mapping of state.layout.mappings || []) {
    if (isControlRule(mapping) && controlProblem(mapping, 'message')) continue;
    if (!outputs.has(mapping.output)) problems.push(['error', `${ruleLabel(mapping)}: sends to a missing output "${mapping.output}"`, () => selectOwner(mapping)]);
  }
  outputsOf().forEach((output, index) => {
    const info = outputInfo(output);
    if (info?.midi && !output.virtual && !output.input && !output.output) {
      problems.push(['warning', `Output ${output.name} has no port: give it a virtual port name, or input/output ports`, () => select({ kind: 'output', index })]);
    }
    if (info?.midi && output.virtual && (output.input || output.output)) {
      problems.push(['warning', `Output ${output.name} uses its virtual port "${output.virtual}" and ignores its input/output ports: clear one or the other`, () => select({ kind: 'output', index })]);
    }
    const status = state.hardware.outputs?.[index];
    if (status && !status.connected && status.error) problems.push(['warning', `Output ${output.name}: ${status.error}`, () => select({ kind: 'output', index })]);
    if (status?.warning) problems.push(['warning', `Output ${output.name}: ${status.warning}`, () => select({ kind: 'output', index })]);
  });
  state.layout.devices.forEach((device, index) => {
    const status = state.hardware.devices?.[index];
    if (status && !status.connected && status.error && !device.type.startsWith('virtual.')) {
      problems.push(['warning', `${deviceInfo(device)?.model || device.type}: ${status.error}`, () => select({ kind: 'device', index })]);
    }
  });
  const { width, height } = state.layout.surface;
  for (const { widget, path } of allWidgets()) {
    if (path.length === 1 && ((widget.x || 0) + widget.width > width || (widget.y || 0) + widget.height > height)) {
      problems.push(['warning', `${widget.name} reaches past the surface`, () => select(widgetSelection([path]))]);
    }
  }
  return problems;
}

function renderProblems(problems = findProblems()) {
  fill($('problem-list'), problems.length
    ? problems.map(([level, text, go]) => el('li', { class: level, onclick: go || null, title: go ? 'Show it' : null }, text))
    : el('li', { class: 'none' }, 'No problems found.'));
  const badge = $('problems');
  badge.hidden = !problems.length;
  badge.classList.toggle('error', problems.some(([level]) => level === 'error'));
  badge.textContent = `⚠ ${problems.length}`;
  badge.title = `${problems.length} problem${problems.length === 1 ? '' : 's'} in the layout`;
}

export function renderEvents() {
  if (state.eventsPaused) return;
  // Perform mode saves the work while the log isn't shown (opening it renders it)
  if (state.mode === 'perform' && !(drawerPrefs().open && drawerPrefs().tab === 'events')) return;
  const filter = drawerPrefs().filter;
  const selected = state.selection?.kind === 'widget' ? new Set(selectedPaths().map((path) => widgetAt(path)?.name)) : new Set();
  const shown = state.eventLog.filter((event) => filter === 'all'
    || (filter === 'quiet' && !CLOCK_EVENTS.has(event.event))
    || (filter === 'debug' && event.event === 'Debug')
    || (filter === 'selected' && selected.has(event.widget)));
  fill($('events'), shown.slice(-200).reverse().map((event) => {
    const debug = event.event === 'Debug';
    const fields = debug ? event.text : Object.entries(event)
      .filter(([key]) => !['id', 'widget', 'event'].includes(key) && !key.startsWith('_'))
      .map(([key, value]) => `${key}=${Array.isArray(value) ? `[${value}]` : value}`)
      .join(' ');
    return el('li', { class: debug ? 'debug' : null, title: `${event.widget} ${event.event} ${fields}` },
      el('b', {}, event.widget), ' ', el('span', { class: 'kind' }, event.event), ' ', fields);
  }));
}

export function bindDrawer() {
  for (const button of document.querySelectorAll('.tabs button')) {
    button.onclick = () => {
      const drawer = drawerPrefs();
      drawer.open = !(drawer.open && drawer.tab === button.dataset.tab);
      drawer.tab = button.dataset.tab;
      savePrefs();
      renderDrawer();
    };
  }
  $('drawer-toggle').onclick = () => {
    drawerPrefs().open = !drawerPrefs().open;
    savePrefs();
    renderDrawer();
  };
  // Drag the bar to make the drawer taller or shorter
  $('drawer').querySelector('.drawer-bar').addEventListener('pointerdown', (event) => {
    if (event.target.closest('button, select, input, label') || !drawerPrefs().open) return;
    const startY = event.clientY;
    const startHeight = drawerPrefs().height;
    const move = (e) => {
      drawerPrefs().height = clamp(startHeight - (e.clientY - startY), 80, Math.round(window.innerHeight * 0.7));
      document.documentElement.style.setProperty('--drawer', `${drawerPrefs().height}px`);
      renderBoard();
      renderOverlay();
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      savePrefs();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
}
