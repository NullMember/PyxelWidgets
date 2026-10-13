// The messages and links window

import { state, $, fill, el } from './core.js';
import { prefs, savePrefs } from './prefs.js';
import { widgetAt, allWidgets, widgetSelection, selectedPaths } from './model.js';
import { outputsOf, outputInfo, setMappings, defaultEvent, defaultMessage, messageSources, sourceNames,
  mappingCard } from './mappings.js';
import { setLinks, widgetNamed, defaultLinkValue, describeValue, linkCard } from './links.js';
import { change, setStatus } from './history.js';
import { render, clamp } from './board.js';
import { duplicate } from './editing.js';

// A floating window listing the messages (layout.mappings) and links of the selected widgets, or
// of every widget. Rules are picked as {kind: 'mapping' | 'link', index}; several picked ones of
// one kind are edited together: a change to the first is made to the others (`spreadChange`).

const RULES_CLIPBOARD = 'pyxelwidgets.rules';

function ruleKey(rule) {
  return `${rule.kind}:${rule.index}`;
}

function ruleObject(rule) {
  return (rule.kind === 'mapping' ? state.layout.mappings : state.layout.links)?.[rule.index];
}

// The selected widgets in layout order
function selectedWidgets() {
  const picked = new Set(selectedPaths().map((path) => widgetAt(path)));
  return allWidgets().map((item) => item.widget).filter((widget) => picked.has(widget));
}

// Widgets whose rules show: the selected ones, or all of them
function ruleWidgets() {
  return state.rules.all ? allWidgets().map((item) => item.widget) : selectedWidgets();
}

function fieldText(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    if ('if' in value) return `(${value.if?.source} ${value.op || '=='} ${value.to} ? ${value.then} : ${value.else})`;
    if ('choose' in value) return `([${value.choose.join(', ')}] by ${value.by?.source ?? value.by})`;
    return `{${value.source}${value.offset ? `${value.offset > 0 ? '+' : ''}${value.offset}` : ''}}`;
  }
  if (Array.isArray(value)) return value.map(fieldText).join(' ');
  return String(value);
}

// A message in a few words: "ControlChange control 1 · value {value} · channel 1"
function messageText(message = {}) {
  switch (message.type) {
    case 'Command': return `${message.name ?? 'Play'} = ${fieldText(message.value ?? 1)}`;
    case 'OscMessage': return `${message.address ?? '/'} ${fieldText(message.args || [])}`.trim();
    case 'PluginParameter': return `${message.track || '?'} / ${message.plugin || '?'} / ${message.parameter || '?'}`;
    case 'TrackParameter': return `${message.track || '?'} · ${message.parameter || 'Volume'}`;
    default: return Object.entries(message).filter(([key]) => key !== 'type').map(([key, value]) => `${key} ${fieldText(value)}`).join(' · ');
  }
}

// [when, to, what] of a rule
export function ruleText(rule, object = ruleObject(rule)) {
  if (rule.kind === 'mapping') {
    return [object.on || 'receive only', object.output, `${object.message?.type || '?'} ${messageText(object.message)}`];
  }
  if (object.action === 'debug') return [object.on, 'Debug log', `"${object.value ?? `${object.on} {all}`}"`];
  const what = object.action ? object.action.replace(/^transport\./, '') : `${(object.change || 'set').toLowerCase()} ${object.option}`;
  const value = describeValue(object);
  return [object.on, object.target || 'Transport', value ? `${what} ${object.change === 'Add' ? 'by' : object.action ? '' : '='} ${value}`.replace(/  +/g, ' ') : what];
}

// The rows the window lists: [{rule, widget, text}], by widget, messages before links
function ruleRows() {
  const query = state.rules.query.trim().toLowerCase();
  const rows = [];
  for (const widget of ruleWidgets()) {
    const add = (kind, list) => list.forEach((object, index) => {
      if (object.widget !== widget.name) return;
      const rule = { kind, index };
      const text = ruleText(rule, object);
      if (query && ![widget.name, ...text].some((part) => String(part).toLowerCase().includes(query))) return;
      rows.push({ rule, widget, text });
    });
    add('mapping', state.layout.mappings || []);
    add('link', state.layout.links || []);
  }
  return rows;
}

function pickedRules() {
  const shown = new Set(ruleRows().map((row) => ruleKey(row.rule)));
  return state.rules.picked.filter((rule) => shown.has(ruleKey(rule)) && ruleObject(rule));
}

function isPicked(rule) {
  return state.rules.picked.some((picked) => ruleKey(picked) === ruleKey(rule));
}

// Click: this one; Shift+click: the rows from the one clicked before; Ctrl/Cmd+click or the box: one more or less
function pickRule(rule, event = {}) {
  const rules = state.rules;
  const rows = ruleRows().map((row) => row.rule);
  if (event.shiftKey && rules.anchor) {
    const keys = rows.map(ruleKey);
    const [a, b] = [keys.indexOf(ruleKey(rules.anchor)), keys.indexOf(ruleKey(rule))];
    if (a >= 0 && b >= 0) {
      rules.picked = rows.slice(Math.min(a, b), Math.max(a, b) + 1);
      return renderRules();
    }
  }
  rules.anchor = rule;
  if (event.ctrlKey || event.metaKey || event.toggle) {
    rules.picked = isPicked(rule) ? rules.picked.filter((picked) => ruleKey(picked) !== ruleKey(rule)) : [...pickedRules(), rule];
  } else {
    rules.picked = [rule];
  }
  renderRules();
}

export function openRules(picked = null) {
  state.rules.open = true;
  if (picked) {
    state.rules.picked = picked;
    state.rules.anchor = picked[picked.length - 1] || null;
    // Shown even when the widget isn't selected
    const widgets = new Set(picked.map((rule) => ruleObject(rule)?.widget));
    if (!state.rules.all && !ruleWidgets().some((widget) => widgets.has(widget.name))) {
      const paths = allWidgets().filter(({ widget }) => widgets.has(widget.name)).map(({ path }) => path);
      if (paths.length) state.selection = widgetSelection(paths);
    }
  }
  state.rules.focused = true;
  render();
}

export function closeRules() {
  state.rules.open = false;
  state.rules.focused = false;
  state.broadcast = null;
  renderRules();
}

// ---- several rules changed as one

// Paths of the values that differ between two rules: a message's fields, a link's value...
// (event values, conditions and lists count as one value)
function leafPaths(a, b, path = [], found = []) {
  const leaf = (value) => value === null || typeof value !== 'object' || Array.isArray(value) || 'source' in value || 'if' in value || 'choose' in value;
  if (a !== undefined && b !== undefined && !leaf(a) && !leaf(b)) {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) leafPaths(a[key], b[key], [...path, key], found);
  } else if (JSON.stringify(a) !== JSON.stringify(b)) {
    found.push(path);
  }
  return found;
}

function getPath(object, path) {
  return path.reduce((value, key) => value?.[key], object);
}

function setPath(object, path, value) {
  let parent = object;
  for (const key of path.slice(0, -1)) {
    if (parent[key] === null || typeof parent[key] !== 'object') parent[key] = {};
    parent = parent[key];
  }
  const last = path[path.length - 1];
  if (value === undefined) delete parent[last];
  else parent[last] = JSON.parse(JSON.stringify(value));
}

// Make the change `rep` went through (from `before`) to `others` too, where it fits them: an
// event their widget has, a field their message type has, a value for the same option
export function spreadChange(kind, before, rep, others) {
  const order = (path) => (path[1] === 'type' ? 0 : ['target', 'option', 'action', 'output'].includes(path[0]) ? 1 : 2);
  const paths = leafPaths(before, rep).filter((path) => path[0] !== 'widget').sort((a, b) => order(a) - order(b));
  if (!paths.length) return;
  for (const other of others) {
    const events = state.catalog.widgets[widgetNamed(other.widget)?.type]?.events || [];
    for (const path of paths) {
      const value = getPath(rep, path);
      if (path[0] === 'on' && value !== undefined && !events.includes(value)) continue;
      if (kind === 'mapping' && path[0] === 'message' && path[1] !== 'type') {
        const fields = state.catalog.messages[other.message?.type]?.fields || [];
        if (!fields.some((field) => field.name === path[1])) continue;
      }
      if (kind === 'link' && ['value', 'min', 'max', 'change'].includes(path[0])
        && (other.option !== rep.option || other.action !== rep.action)) continue;
      setPath(other, path, value);
    }
    if (kind === 'mapping') {
      // Fields another message type had
      const fields = state.catalog.messages[other.message?.type]?.fields;
      if (fields) for (const key of Object.keys(other.message)) if (key !== 'type' && !fields.some((field) => field.name === key)) delete other.message[key];
      if (!other.on) other.feedback = true;
    }
  }
}

// Marks the editors of values that differ between the picked rules
function markMixed(card, kind, index, rep, others) {
  const prefix = `${kind}-${index}-`;
  const ids = new Set();
  for (const other of others) {
    for (const path of leafPaths(rep, other)) {
      if (path[0] === 'widget') continue;
      if (kind === 'mapping') ids.add(path[0] === 'message' ? (path[1] === 'type' ? 'type' : path[1] === 'args' ? 'arg0' : path[1]) : path[0]);
      else ids.add(path[0] === 'action' ? 'option' : path[0]);
    }
  }
  for (const id of ids) {
    const node = card.querySelector(`#${CSS.escape(prefix + id)}-pick`) || card.querySelector(`#${CSS.escape(prefix + id)}`);
    if (!node) continue;
    const target = node.closest('.control') || node;
    target.classList.add('mixed');
    target.title = 'Differs between the picked ones: each keeps its own until this is changed';
  }
}

// ---- adding, copying, pasting

// New messages for a widget (notes come with their note-offs)
function newMappings(widget) {
  const output = outputsOf()[0];
  const info = outputInfo(output);
  // Macro buttons: a momentary button fires a shortcut on presses (it changes on releases too)
  const momentary = widget.type === 'Button' && (widget.options?.mode || 'Button') !== 'Switch';
  const on = momentary && info?.messages.includes('Hotkey') ? 'Pressed' : defaultEvent(widget);
  const rules = [{ widget: widget.name, on, output: output.name, message: defaultMessage(widget, on, info) }];
  // A Sequencer's notes end with their gates, other widgets' with their NoteOff
  const ends = { StepPlayed: 'StepEnded', NoteOn: 'NoteOff' }[on];
  const events = state.catalog.widgets[widget.type]?.events || [];
  if (ends && events.includes(ends) && rules[0].message.type === 'NoteOn' && info?.messages.includes('NoteOff')) {
    rules.push({ widget: widget.name, on: ends, output: output.name, message: defaultMessage(widget, ends, info) });
  }
  return rules;
}

function newLink(widget) {
  // A momentary button acts on presses (it changes on releases too)
  const momentary = widget.type === 'Button' && (widget.options?.mode || 'Button') !== 'Switch';
  const on = momentary ? 'Pressed' : defaultEvent(widget);
  // Another widget if there is one
  const target = allWidgets().map((item) => item.widget).find((candidate) => candidate !== widget) || widget;
  const link = { widget: widget.name, on, target: target.name, option: 'visible' };
  defaultLinkValue(link);
  return link;
}

// Add rules made by `make(widget)` (one or a list) to each widget, and pick them
function addRules(kind, widgets, make) {
  if (!widgets.length) return;
  const added = [];
  change((layout) => {
    const list = kind === 'mapping' ? (layout.mappings ||= []) : (layout.links ||= []);
    for (const widget of widgets) {
      for (const rule of [make(widget)].flat()) {
        list.push(rule);
        added.push({ kind, index: list.length - 1 });
      }
    }
    state.rules.picked = added;
    state.rules.anchor = added[added.length - 1];
  });
  openRules();
}

function copyRules(cut = false) {
  const picked = pickedRules();
  if (!picked.length) return;
  const clip = {
    format: RULES_CLIPBOARD,
    mappings: picked.filter((rule) => rule.kind === 'mapping').map(ruleObject),
    links: picked.filter((rule) => rule.kind === 'link').map(ruleObject),
  };
  const text = JSON.stringify(clip);
  state.ruleClipboard = clip;
  try {
    localStorage.setItem(RULES_CLIPBOARD, text);
  } catch {
    // This page only
  }
  navigator.clipboard?.writeText(text).catch(() => {});
  if (cut) deleteRules();
  setStatus(`${cut ? 'Cut' : 'Copied'} ${picked.length} message${picked.length > 1 ? 's and links' : ' or link'}`, 'ok');
}

function readRuleClipboard() {
  try {
    const stored = JSON.parse(localStorage.getItem(RULES_CLIPBOARD) || 'null');
    if (stored?.format === RULES_CLIPBOARD) return stored;
  } catch {
    // Use this page's
  }
  return state.ruleClipboard;
}

// A copied rule for `widget`: null when it can't be (no such output or target, no event it needs)
function adaptRule(kind, rule, widget) {
  const copy = { ...JSON.parse(JSON.stringify(rule)), widget: widget.name };
  const events = state.catalog.widgets[widget.type]?.events || [];
  const needs = kind === 'mapping' ? messageSources(copy.message)
    : [copy.value?.source, copy.value?.if?.source, copy.value?.by?.source ?? copy.value?.by].filter(Boolean);
  if (kind === 'mapping' && !outputsOf().some((output) => output.name === copy.output)) return null;
  if (kind === 'link' && copy.target !== undefined) {
    // A link changing its own widget changes the new one
    if (copy.target === rule.widget) copy.target = widget.name;
    else if (!widgetNamed(copy.target)) return null;
  }
  if (copy.on && !events.includes(copy.on)) {
    const fits = events.find((name) => needs.every((source) => sourceNames(name).includes(source)));
    if (!fits) return null;
    copy.on = events.includes(defaultEvent(widget)) && needs.every((source) => sourceNames(defaultEvent(widget)).includes(source)) ? defaultEvent(widget) : fits;
  }
  return copy;
}

// Paste onto every selected widget (or, with none selected, the widgets they came from)
function pasteRules(clip = readRuleClipboard(), widgets = selectedWidgets()) {
  const rules = [...(clip?.mappings || []).map((rule) => ['mapping', rule]), ...(clip?.links || []).map((rule) => ['link', rule])];
  if (!rules.length) return setStatus('Nothing to paste: copy messages or links first (Ctrl+C in this window)', 'error');
  let pasted = 0, dropped = 0;
  const added = [];
  change((layout) => {
    for (const [kind, rule] of rules) {
      const targets = widgets.length ? widgets : [widgetNamed(rule.widget)].filter(Boolean);
      if (!targets.length) dropped++;
      for (const widget of targets) {
        const copy = adaptRule(kind, rule, widget);
        if (!copy) {
          dropped++;
          continue;
        }
        const list = kind === 'mapping' ? (layout.mappings ||= []) : (layout.links ||= []);
        list.push(copy);
        added.push({ kind, index: list.length - 1 });
        pasted++;
      }
    }
    state.rules.picked = added;
    state.rules.anchor = added[added.length - 1] || null;
  });
  const count = `${pasted} message${pasted === 1 ? ' or link' : 's and links'}`;
  setStatus(dropped ? `Pasted ${count}; ${dropped} left out (their output, target or event isn't there)` : `Pasted ${count}`, dropped ? '' : 'ok');
}

function duplicateRules() {
  const picked = pickedRules();
  if (!picked.length) return;
  const added = [];
  change((layout) => {
    for (const rule of picked) {
      const list = rule.kind === 'mapping' ? layout.mappings : layout.links;
      list.push(JSON.parse(JSON.stringify(list[rule.index])));
      added.push({ kind: rule.kind, index: list.length - 1 });
    }
    state.rules.picked = added;
    state.rules.anchor = added[added.length - 1];
  });
}

function deleteRules() {
  const picked = pickedRules();
  if (!picked.length) return;
  const gone = new Set(picked.map(ruleKey));
  change((layout) => {
    setMappings(layout, (layout.mappings || []).filter((_, index) => !gone.has(`mapping:${index}`)));
    setLinks(layout, (layout.links || []).filter((_, index) => !gone.has(`link:${index}`)));
    state.rules.picked = [];
  });
}

// Keys while the window has the focus (not in a field): true when handled
export function rulesKey(event) {
  const mod = event.ctrlKey || event.metaKey;
  const key = event.key.toLowerCase();
  const actions = {
    c: () => copyRules(), x: () => copyRules(true), v: () => pasteRules(), d: () => duplicateRules(),
    a: () => { state.rules.picked = ruleRows().map((row) => row.rule); renderRules(); },
  };
  if (mod && actions[key] && !(key === 'c' && window.getSelection()?.toString())) {
    event.preventDefault();
    actions[key]();
    return true;
  }
  if (mod) return false;
  if (key === 'delete' || key === 'backspace') {
    event.preventDefault();
    deleteRules();
    return true;
  }
  if (key === 'escape') {
    closeRules();
    return true;
  }
  return false;
}

// ---- the window

export function buildRules() {
  const window_ = $('rules');
  const head = window_.querySelector('.window-head');
  // Dragged by its title bar; where it is and its size are remembered
  head.addEventListener('pointerdown', (event) => {
    if (event.target.closest('button, input, select') || event.button !== 0) return;
    event.preventDefault();
    const start = { x: event.clientX, y: event.clientY, left: window_.offsetLeft, top: window_.offsetTop };
    const move = (e) => {
      window_.style.left = `${clamp(start.left + e.clientX - start.x, 0, innerWidth - 80)}px`;
      window_.style.top = `${clamp(start.top + e.clientY - start.y, 0, innerHeight - 40)}px`;
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      saveRulesPlace();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  new ResizeObserver(() => { if (!window_.hidden) saveRulesPlace(); }).observe(window_);
  $('rules-close').onclick = closeRules;
  $('rules-selected').onclick = () => { state.rules.all = false; renderRules(); };
  $('rules-all').onclick = () => { state.rules.all = true; renderRules(); };
  $('rules-search').addEventListener('input', (e) => { state.rules.query = e.target.value; renderRules(); });
  $('rules-add-message').onclick = () => addRules('mapping', selectedWidgets(), newMappings);
  $('rules-add-link').onclick = () => addRules('link', selectedWidgets(), newLink);
  $('rules-copy').onclick = () => copyRules();
  $('rules-cut').onclick = () => copyRules(true);
  $('rules-paste').onclick = () => pasteRules();
  $('rules-duplicate').onclick = duplicateRules;
  $('rules-delete').onclick = deleteRules;
  $('rules-all-rows').onclick = () => { state.rules.picked = ruleRows().map((row) => row.rule); renderRules(); };
  // Which part of the page keys go to; changes spread to several picked rules only from their editor
  document.addEventListener('pointerdown', (event) => {
    state.rules.focused = state.rules.open && !!event.target.closest('#rules');
    if (!event.target.closest('.rule-editor.multi')) state.broadcast = null;
  }, true);
  document.addEventListener('focusin', (event) => {
    if (!event.target.closest('.rule-editor.multi')) state.broadcast = null;
  }, true);
}

function saveRulesPlace() {
  const window_ = $('rules');
  prefs.rulesWindow = { left: window_.offsetLeft, top: window_.offsetTop, width: window_.offsetWidth, height: window_.offsetHeight };
  savePrefs();
}

function placeRules() {
  const window_ = $('rules');
  const stage = $('stage').getBoundingClientRect();
  const place = prefs.rulesWindow || {
    width: Math.min(820, Math.max(480, stage.width - 32)), height: Math.min(560, Math.max(360, stage.height - 32)),
    left: stage.left + 16, top: stage.top + 16,
  };
  const width = Math.min(place.width, innerWidth - 16), height = Math.min(place.height, innerHeight - 16);
  Object.assign(window_.style, {
    width: `${width}px`, height: `${height}px`,
    left: `${clamp(place.left, 0, Math.max(0, innerWidth - width))}px`, top: `${clamp(place.top, 0, Math.max(0, innerHeight - height))}px`,
  });
}

export function renderRules() {
  const window_ = $('rules');
  const open = state.rules.open;
  if (window_.hidden === open) {
    window_.hidden = !open;
    if (open) placeRules();
  }
  if (!open) return;
  const rules = state.rules;
  const widgets = ruleWidgets();
  const selected = selectedWidgets();
  const rows = ruleRows();
  rules.picked = pickedRules();
  const picked = rules.picked;
  $('rules-title').textContent = rules.all ? 'All widgets'
    : widgets.length === 1 ? widgets[0].name : widgets.length ? `${widgets.length} widgets` : 'No widget selected';
  $('rules-selected').classList.toggle('active', !rules.all);
  $('rules-all').classList.toggle('active', rules.all);
  const each = selected.length > 1 ? ' to each selected widget' : '';
  $('rules-add-message').disabled = !selected.length || !outputsOf().length;
  $('rules-add-message').title = !outputsOf().length ? 'Add an output first (Outputs, on the left)' : selected.length ? `Send an event${each} to an output` : 'Select a widget first';
  $('rules-add-link').disabled = !selected.length;
  $('rules-add-link').title = selected.length ? `Change an option of a widget on an event${each}` : 'Select a widget first';
  for (const id of ['rules-copy', 'rules-cut', 'rules-duplicate', 'rules-delete']) $(id).disabled = !picked.length;
  const clip = readRuleClipboard();
  const clipped = (clip?.mappings?.length || 0) + (clip?.links?.length || 0);
  $('rules-paste').disabled = !clipped;
  $('rules-paste').title = clipped ? `Paste ${clipped}${selected.length ? (selected.length > 1 ? ` onto each of the ${selected.length} selected widgets` : ` onto ${selected[0].name}`) : ' onto the widgets they came from'} (Ctrl/Cmd+V)` : 'Copy messages or links first (Ctrl/Cmd+C)';
  $('rules-all-rows').disabled = !rows.length;
  // The list, by widget
  const list = $('rules-list');
  const items = [];
  let last = null;
  for (const row of rows) {
    if (row.widget !== last && widgets.length > 1) {
      const own = rows.filter((other) => other.widget === row.widget).map((other) => other.rule);
      items.push(el('li', {
        class: 'rule-widget', title: 'Pick all of its messages and links',
        onclick: () => { rules.picked = own; rules.anchor = own[own.length - 1]; renderRules(); },
      }, row.widget.name, el('span', { class: 'type' }, row.widget.type)));
    }
    last = row.widget;
    const [when, to, what] = row.text;
    const object = ruleObject(row.rule);
    items.push(el('li', {
      class: `rule-row${isPicked(row.rule) ? ' picked' : ''}`, dataset: { rule: ruleKey(row.rule) },
      onclick: (event) => pickRule(row.rule, event),
    },
      el('input', {
        type: 'checkbox', checked: isPicked(row.rule), 'aria-label': 'Pick',
        onclick: (event) => { event.stopPropagation(); pickRule(row.rule, { toggle: true }); },
      }),
      el('span', { class: `rule-kind ${row.rule.kind}` }, row.rule.kind === 'mapping' ? 'msg' : 'link'),
      el('span', { class: 'rule-text' },
        el('span', { class: 'rule-line' }, el('b', {}, when), ' → ', to, row.rule.kind === 'mapping' && object.feedback ? el('span', { class: 'feedback', title: 'Feedback: the output updates the widget' }, ' ⇄') : null),
        el('span', { class: 'rule-what', title: what }, what))));
  }
  if (!rows.length) {
    items.push(el('li', { class: 'hint' }, rules.query ? `Nothing matches "${rules.query}".`
      : !widgets.length ? 'Select widgets on the grid or in Layers, or show All widgets.'
        : 'No messages or links yet: add one above.'));
  }
  list.replaceChildren(...items);
  fill($('rules-editor'), ruleEditor(picked));
}

function ruleEditor(picked) {
  if (!picked.length) {
    return el('p', { class: 'hint' }, 'Pick a message or link to edit it. Shift+click picks a range, Ctrl/Cmd+click one more: '
      + 'changes are then made to all of them. Ctrl/Cmd+C and V copy and paste them onto the selected widgets.');
  }
  const kinds = new Set(picked.map((rule) => rule.kind));
  if (kinds.size > 1) {
    return el('p', { class: 'hint' }, `${picked.length} picked. Messages and links are edited apart: pick only messages or only links to change them together. Copy, cut, duplicate and delete work on all of them.`);
  }
  const [first] = picked;
  const rep = ruleObject(first);
  const widget = widgetNamed(rep.widget);
  if (!widget) return el('p', { class: 'hint' }, `${rep.widget} isn't in the layout.`);
  const card = first.kind === 'mapping' ? mappingCard(widget, rep, first.index) : linkCard(widget, rep, first.index);
  if (picked.length === 1) {
    return el('div', { class: 'rule-editor' }, el('p', { class: 'rule-for' }, widget.name, el('span', { class: 'type' }, widget.type)), card);
  }
  const others = picked.slice(1).map(ruleObject);
  markMixed(card, first.kind, first.index, rep, others);
  const names = [...new Set([rep, ...others].map((object) => object.widget))];
  const editor = el('div', { class: 'rule-editor multi' },
    el('p', { class: 'rule-for' }, `${picked.length} ${first.kind === 'mapping' ? 'messages' : 'links'} of ${names.length > 3 ? `${names.length} widgets` : names.join(', ')}`),
    el('p', { class: 'hint note' }, 'A change here is made to all of them. Dashed fields differ: each keeps its own value until you change it.'),
    card);
  // Changes made in this editor spread to the other picked rules (see change())
  const arm = () => {
    const now = pickedRules();
    if (now.length > 1 && now[0].kind === first.kind) state.broadcast = { kind: first.kind, rep: ruleObject(now[0]), others: now.slice(1).map(ruleObject) };
  };
  for (const type of ['pointerdown', 'focusin', 'keydown', 'change']) editor.addEventListener(type, arm, true);
  return editor;
}

// The Behaviour group's list: a line per message and link, opening the window
export function ruleSummary(widgets) {
  const names = new Set(widgets.map((widget) => widget.name));
  const rows = [];
  (state.layout.mappings || []).forEach((object, index) => { if (names.has(object.widget)) rows.push({ kind: 'mapping', index }); });
  (state.layout.links || []).forEach((object, index) => { if (names.has(object.widget)) rows.push({ kind: 'link', index }); });
  const single = widgets.length === 1;
  return [
    el('h4', {}, 'Messages and links'),
    outputsOf().length ? null : el('p', { class: 'hint' }, 'Add an output (a MIDI port, OSC, Mackie Control or HUI) to send events to other software.'),
    rows.length ? el('ul', { class: 'rule-summary' }, rows.slice(0, 10).map((rule) => {
      const [when, to, what] = ruleText(rule);
      return el('li', { onclick: () => openRules([rule]), title: 'Edit it' },
        el('span', { class: `rule-kind ${rule.kind}` }, rule.kind === 'mapping' ? 'msg' : 'link'),
        el('span', { class: 'rule-text' },
          el('span', { class: 'rule-line' }, single ? null : `${ruleObject(rule).widget}: `, el('b', {}, when), ' → ', to),
          el('span', { class: 'rule-what' }, what)));
    }), rows.length > 10 ? el('li', { class: 'more', onclick: () => openRules(rows), title: 'Edit them' }, `and ${rows.length - 10} more…`) : null)
      : el('p', { class: 'hint' }, 'Send events to outputs (messages), or change other widgets\' options when this one is used (links): show a group, switch a page, move a keyboard\'s octave, dim a color…'),
    el('div', { class: 'actions' },
      outputsOf().length ? el('button', { onclick: () => addRules('mapping', widgets, newMappings), title: single ? 'Send an event of this widget to an output' : 'Add one to each' }, single ? 'Add message' : 'Add message to each') : null,
      el('button', { onclick: () => addRules('link', widgets, newLink), title: single ? 'Change an option of a widget on an event of this one' : 'Add one to each' }, single ? 'Add link' : 'Add link to each'),
      el('button', { onclick: () => openRules(rows), title: 'Edit, copy and paste them in a window (M)' }, rows.length ? 'Edit…' : 'Open editor')),
  ];
}
