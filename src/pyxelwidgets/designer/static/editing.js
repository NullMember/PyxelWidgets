// Editing actions: adding (and dropping) widgets, duplicate, copy and paste, groups

import { DEFAULT_SIZE, state, $, el } from './core.js';
import { childrenOf, widgetAt, containerSize, absolute, allWidgets, uniqueName, isGroup, currentPage,
  hiddenBy, samePath, widgetSelection, topSelected, pathsOf, isDeviceTarget } from './model.js';
import { outputsOf, setMappings, removeOutput } from './mappings.js';
import { setLinks } from './links.js';
import { change, setStatus } from './history.js';
import { step, place, clamp, moveLimits } from './board.js';
import { select } from './properties.js';
import { insertSnippet } from './snippets.js';
import { setMode } from './files.js';

export function targetGroup() {
  // Path of the group new widgets go into, or null for the surface
  const selection = state.selection;
  if (selection?.kind !== 'widget') return null;
  const widget = widgetAt(selection.path);
  if (widget.type === 'Pages') {
    // Into the shown page when it's a group
    const page = widget.widgets?.[currentPage(widget)];
    return page && isGroup(page) ? [...selection.path, currentPage(widget)] : selection.path;
  }
  if (isGroup(widget)) return selection.path;
  return selection.path.length > 1 ? selection.path.slice(0, -1) : null;
}

// Adds a widget into ``group`` (a path, or null for the surface) at ``x``, ``y`` in it
export function addWidget(type, group = targetGroup(), x = 0, y = 0) {
  const [maxWidth, maxHeight] = group ? [widgetAt(group).width, widgetAt(group).height] : [state.layout.surface.width, state.layout.surface.height];
  // Containers fill the space; widgets of your own (parser.register) start at 2x2
  const [width, height] = DEFAULT_SIZE[type] || (state.catalog.widgets[type]?.container ? [maxWidth, maxHeight] : [2, 2]);
  const widget = { type, name: uniqueName(type), x, y, width: Math.min(width, maxWidth - x), height: Math.min(height, maxHeight - y), options: {} };
  if (state.catalog.widgets[type].container) widget.widgets = [];
  change((layout) => {
    const list = group ? widgetAt(group).widgets : layout.widgets;
    list.push(widget);
    state.selection = widgetSelection([[...(group || []), list.length - 1]]);
  });
}

// ---------------------------------------------------------------- dragging widgets onto the grid

// Where a dragged widget would go: the pad under the pointer is its top-left; inside the
// innermost group (or shown page) it fits in, else on the surface
function dropPlace(event, type, size = null) {
  const bounds = $('overlay').getBoundingClientRect();
  const pad = step();
  const { width: surfaceWidth, height: surfaceHeight } = state.layout.surface;
  const column = Math.floor((event.clientX - bounds.left) / pad);
  const row = Math.floor((event.clientY - bounds.top) / pad);
  if (column < 0 || row < 0 || column >= surfaceWidth || row >= surfaceHeight) return null;
  const [defaultWidth, defaultHeight] = size || DEFAULT_SIZE[type] || (state.catalog.widgets[type]?.container ? [surfaceWidth, surfaceHeight] : [2, 2]);
  const width = Math.min(defaultWidth, surfaceWidth), height = Math.min(defaultHeight, surfaceHeight);
  // Top-left at the pointer, moved back inside the surface
  const x = clamp(column, 0, surfaceWidth - width);
  const y = clamp(surfaceHeight - 1 - row - height + 1, 0, surfaceHeight - height);
  let group = null;
  for (const { widget, path } of allWidgets()) {
    if (!isGroup(widget) || widget.type === 'Pages' || hiddenBy(path).length || widget.options?.visible === false) continue;
    const [gx, gy] = absolute(path);
    if (x >= gx && y >= gy && x + width <= gx + widget.width && y + height <= gy + widget.height && (!group || path.length > group.length)) group = path;
  }
  const [gx, gy] = group ? absolute(group) : [0, 0];
  return { group, x: x - gx, y: y - gy, absolute: [x, y, width, height] };
}

export function clearGhost() {
  $('overlay').querySelector('.ghost')?.remove();
}

export function dragOver(event) {
  if (!state.dragType && !state.dragSnippet) return;
  const spot = dropPlace(event, state.dragType, state.dragSnippet?.size);
  if (!spot) return clearGhost();
  event.preventDefault();
  event.dataTransfer.dropEffect = 'copy';
  let ghost = $('overlay').querySelector('.ghost');
  if (!ghost) {
    ghost = el('div', { class: 'outline ghost' });
    $('overlay').append(ghost);
  }
  place(ghost, ...spot.absolute);
}

export function drop(event) {
  const snippet = state.dragSnippet;
  if (snippet) {
    clearGhost();
    state.dragSnippet = null;
    const spot = dropPlace(event, null, snippet.size);
    if (!spot) return;
    event.preventDefault();
    if (state.mode !== 'edit') setMode('edit');
    return insertSnippet(snippet, spot.group, spot.absolute.slice(0, 2));
  }
  const type = state.dragType || event.dataTransfer.getData('text/plain');
  clearGhost();
  state.dragType = null;
  if (!state.catalog.widgets[type]) return;
  const spot = dropPlace(event, type);
  if (!spot) return;
  event.preventDefault();
  if (state.mode !== 'edit') setMode('edit');
  addWidget(type, spot.group, spot.x, spot.y);
}

export function addDevice() {
  const type = $('device-type').value;
  change((layout) => {
    layout.devices.push({ type, x: 0, y: 0, options: {} });
    state.selection = { kind: 'device', index: layout.devices.length - 1 };
  });
}

export function removeSelection() {
  const selection = state.selection;
  if (!selection) return;
  if (selection.kind === 'output') return removeOutput(selection.index);
  change((layout) => {
    let bindings = layout.bindings || [];
    if (selection.kind === 'widget') {
      const widgets = topSelected().map(widgetAt);
      for (const widget of widgets) {
        const list = childrenOf(pathsOf([widget])[0]);
        list.splice(list.indexOf(widget), 1);
      }
      const names = new Set(allWidgets().map(({ widget }) => widget.name));
      bindings = bindings.filter((binding) => binding.widget === undefined || names.has(binding.widget));
      // Rules from device controls stay, unless they change a deleted widget
      const kept = (object) => object.widget === undefined || names.has(object.widget);
      setMappings(layout, (layout.mappings || []).filter(kept));
      setLinks(layout, (layout.links || []).filter((link) => kept(link) && (link.target === undefined || link.target === 'key' || isDeviceTarget(link.target) || names.has(link.target))));
    } else {
      // The device's bindings and the rules from its controls go; later devices move up
      const moved = (list) => list.filter((entry) => entry.device !== selection.index || entry.control === undefined)
        .map((entry) => (entry.device > selection.index ? { ...entry, device: entry.device - 1 } : entry));
      layout.devices.splice(selection.index, 1);
      bindings = moved(bindings);
      setMappings(layout, moved(layout.mappings || []));
      // So do links to its lights and screen
      const target = (link) => (!isDeviceTarget(link.target) ? link
        : link.target.device > selection.index ? { ...link, target: { ...link.target, device: link.target.device - 1 } } : link);
      setLinks(layout, moved(layout.links || []).filter((link) => !isDeviceTarget(link.target) || link.target.device !== selection.index).map(target));
    }
    if (bindings.length) layout.bindings = bindings;
    else delete layout.bindings;
    state.selection = null;
  });
}

export function reorder(path, direction) {
  const list = childrenOf(path);
  const index = path[path.length - 1];
  const target = index + direction;
  if (target < 0 || target >= list.length) return;
  change(() => {
    [list[index], list[target]] = [list[target], list[index]];
    state.selection = widgetSelection([[...path.slice(0, -1), target]]);
  });
}

// Copies of the selected widgets, each above its original, with their messages and links;
// the copies get selected
export function duplicate() {
  const originals = topSelected().map(widgetAt);
  if (!originals.length) return;
  const taken = new Set();
  const renames = new Map();
  const rename = (widget) => {
    const name = uniqueName(widget.type, taken);
    renames.set(widget.name, name);
    widget.name = name;
    taken.add(name);
    (widget.widgets || []).forEach(rename);
  };
  change((layout) => {
    const copies = originals.map((original) => {
      const copy = JSON.parse(JSON.stringify(original));
      rename(copy);
      const list = childrenOf(pathsOf([original])[0]);
      list.splice(list.indexOf(original) + 1, 0, copy);
      return copy;
    });
    copyBehaviour(layout, renames);
    state.selection = widgetSelection(pathsOf(copies));
  });
}

// Messages and links of renamed (copied) widgets, for the copies: links between copies stay between copies
function copyBehaviour(layout, renames, links = layout.links || [], mappings = layout.mappings || [], outputs = null) {
  const names = new Set(allWidgets().map(({ widget }) => widget.name));
  let dropped = 0;
  const newLinks = [];
  for (const link of links) {
    if (!renames.has(link.widget)) continue;
    const copy = { ...link, widget: renames.get(link.widget) };
    if (link.target !== undefined && link.target !== 'key' && !isDeviceTarget(link.target)) {
      if (renames.has(link.target)) copy.target = renames.get(link.target);
      else if (!names.has(link.target)) {
        dropped++;
        continue;
      }
    }
    newLinks.push(copy);
  }
  const known = new Set(outputsOf(layout).map((output) => output.name));
  const newMappings = [];
  for (const mapping of mappings) {
    if (!renames.has(mapping.widget)) continue;
    if (!known.has(mapping.output)) {
      dropped++;
      continue;
    }
    newMappings.push({ ...JSON.parse(JSON.stringify(mapping)), widget: renames.get(mapping.widget) });
  }
  setLinks(layout, [...(layout.links || []), ...newLinks]);
  setMappings(layout, [...(layout.mappings || []), ...newMappings]);
  return dropped;
}

// ---------------------------------------------------------------- copy and paste

const CLIPBOARD_KEY = 'pyxelwidgets.clipboard';

// The selected widgets with their messages and links, for pasting here or in another layout
export function copySelection(cut = false) {
  if (state.selection?.kind !== 'widget') return;
  const widgets = topSelected().map(widgetAt);
  const names = new Set();
  const collect = (widget) => {
    names.add(widget.name);
    (widget.widgets || []).forEach(collect);
  };
  widgets.forEach(collect);
  const clip = {
    format: 'pyxelwidgets.clipboard',
    widgets: widgets.map((widget) => ({ widget: JSON.parse(JSON.stringify(widget)), at: absolute(pathsOf([widget])[0]) })),
    links: (state.layout.links || []).filter((link) => names.has(link.widget)),
    mappings: (state.layout.mappings || []).filter((mapping) => names.has(mapping.widget)),
  };
  const text = JSON.stringify(clip);
  state.clipboard = clip;
  try {
    localStorage.setItem(CLIPBOARD_KEY, text);
  } catch {
    // This page only
  }
  navigator.clipboard?.writeText(text).catch(() => {});
  const count = `${widgets.length} widget${widgets.length > 1 ? 's' : ''}`;
  if (cut) removeSelection();
  setStatus(`${cut ? 'Cut' : 'Copied'} ${count}`, 'ok');
}

function readClipboard() {
  try {
    const stored = JSON.parse(localStorage.getItem(CLIPBOARD_KEY) || 'null');
    if (stored?.format === 'pyxelwidgets.clipboard') return stored;
  } catch {
    // Use this page's
  }
  return state.clipboard;
}

// Paste into the selected group (or next to the selected widget, or on the surface), on top,
// where they were; names stay unless taken
export function pasteWidgets(clip = readClipboard(), into = targetGroup()) {
  if (!clip?.widgets?.length) return setStatus('Nothing to paste: copy widgets first (Ctrl+C)', 'error');
  let dropped = 0;
  change((layout) => { dropped = placeClip(layout, clip, into); });
  const count = `${clip.widgets.length} widget${clip.widgets.length > 1 ? 's' : ''}`;
  setStatus(dropped ? `Pasted ${count}; ${dropped} message${dropped > 1 ? 's or links' : ' or link'} left out (their output or target isn't in this layout)` : `Pasted ${count}`, dropped ? '' : 'ok');
}

// Adds a clip's widgets (at their absolute places, kept inside ``into``) with their messages and links,
// inside a change; the new widgets get selected. Returns how many messages and links were left out.
export function placeClip(layout, clip, into) {
  const existing = new Set(allWidgets().map(({ widget }) => widget.name));
  const taken = new Set();
  const renames = new Map();
  const rename = (widget) => {
    const name = existing.has(widget.name) || taken.has(widget.name) ? uniqueName(widget.type, taken) : widget.name;
    renames.set(widget.name, name);
    widget.name = name;
    taken.add(name);
    (widget.widgets || []).forEach(rename);
  };
  const container = into ? widgetAt(into) : null;
  const list = container ? (container.widgets ||= []) : layout.widgets;
  const [ox, oy] = into ? absolute(into) : [0, 0];
  const [width, height] = container ? [container.width, container.height] : [layout.surface.width, layout.surface.height];
  const pasted = clip.widgets.map(({ widget, at }) => {
    const copy = JSON.parse(JSON.stringify(widget));
    rename(copy);
    copy.width = Math.min(copy.width, width);
    copy.height = Math.min(copy.height, height);
    copy.x = clamp(at[0] - ox, 0, width - copy.width);
    copy.y = clamp(at[1] - oy, 0, height - copy.height);
    list.push(copy);
    return copy;
  });
  const dropped = copyBehaviour(layout, renames, clip.links || [], clip.mappings || []);
  state.selection = widgetSelection(pathsOf(pasted));
  return dropped;
}

// Move the selected widgets into a new Group around them (they must share a parent)
export function groupSelection() {
  const paths = topSelected();
  const parent = paths[0].slice(0, -1);
  if (!paths.every((path) => samePath(path.slice(0, -1), parent))) {
    return setStatus('Only widgets in the same group can be grouped', 'error');
  }
  if (parent.length && widgetAt(parent).type === 'Pages') return setStatus('Add a page to group widgets on a Pages', 'error');
  const widgets = paths.map(widgetAt);
  const x0 = Math.min(...widgets.map((w) => w.x || 0)), y0 = Math.min(...widgets.map((w) => w.y || 0));
  const x1 = Math.max(...widgets.map((w) => (w.x || 0) + w.width)), y1 = Math.max(...widgets.map((w) => (w.y || 0) + w.height));
  change((layout) => {
    const list = parent.length ? widgetAt(parent).widgets : layout.widgets;
    const index = Math.min(...widgets.map((widget) => list.indexOf(widget)));
    // Keep their drawing order
    const ordered = list.filter((widget) => widgets.includes(widget));
    const group = {
      type: 'Group', name: uniqueName('Group'), x: x0, y: y0, width: x1 - x0, height: y1 - y0, options: {},
      widgets: ordered.map((widget) => ({ ...widget, x: (widget.x || 0) - x0, y: (widget.y || 0) - y0 })),
    };
    const rest = list.filter((widget) => !widgets.includes(widget));
    rest.splice(index, 0, group);
    list.splice(0, list.length, ...rest);
    state.selection = widgetSelection(pathsOf([group]));
  });
}

// Move the group's widgets out to its parent, where the group was
export function ungroup(path) {
  const group = widgetAt(path);
  change(() => {
    const list = childrenOf(path);
    const children = (group.widgets || []).map((widget) => ({ ...widget, x: (widget.x || 0) + (group.x || 0), y: (widget.y || 0) + (group.y || 0) }));
    list.splice(list.indexOf(group), 1, ...children);
    state.selection = widgetSelection(pathsOf(children));
  });
}

export function selectAll() {
  // The selected widget's siblings, or everything on the surface
  const scope = state.selection?.kind === 'widget' ? state.selection.path.slice(0, -1) : [];
  const list = scope.length ? widgetAt(scope).widgets : state.layout.widgets;
  select(widgetSelection(list.map((_, index) => [...scope, index]).filter((path) => !hiddenBy(path).length)));
}

export function nudge(dx, dy, resize) {
  const paths = topSelected();
  if (!paths.length) return;
  if (resize) {
    return change(() => paths.forEach((path) => {
      const widget = widgetAt(path);
      const [parentWidth, parentHeight] = containerSize(path);
      widget.width = clamp(widget.width + dx, 1, parentWidth - (widget.x || 0));
      widget.height = clamp(widget.height + dy, 1, parentHeight - (widget.y || 0));
    }));
  }
  // Together, as far as all of them can go
  const limits = moveLimits(paths);
  const [ox, oy] = [clamp(dx, ...limits.dx), clamp(dy, ...limits.dy)];
  if (!ox && !oy) return;
  const widgets = paths.map(widgetAt);
  change(() => widgets.forEach((widget) => Object.assign(widget, { x: (widget.x || 0) + ox, y: (widget.y || 0) + oy })));
}
