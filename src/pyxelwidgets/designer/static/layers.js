// The Layers tree: renaming, folding, drag and drop reordering

import { state, $, el } from './core.js';
import { viewSet, toggleView, renameInViews } from './prefs.js';
import { childrenOf, widgetAt, absolute, allWidgets, isGroup, currentPage, hiddenBy, samePath,
  widgetSelection, selectedPaths, isSelected, isInside, topSelected, toggleSelected, pathsOf } from './model.js';
import { change, setStatus } from './history.js';
import { render, clamp } from './board.js';
import { select, setOption } from './properties.js';
import { drop } from './editing.js';

const ICONS = {
  eye: '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="8" cy="8" r="2" fill="currentColor"/></svg>',
  eyeOff: '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 14L14 2" stroke="currentColor" stroke-width="1.6"/></svg>',
  lock: '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5" fill="currentColor"/><path d="M5 7V5a3 3 0 0 1 6 0v2" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
};

function icon(name) {
  const span = el('span', { class: 'svg' });
  span.innerHTML = ICONS[name];
  return span;
}

// Renames a widget and what refers to it (bindings, messages, links, view sets)
export function renameWidget(widget, name) {
  name = name.trim();
  if (name === widget.name) return render();
  if (!name || allWidgets().some((item) => item.widget !== widget && item.widget.name === name)) {
    setStatus(`Widget name "${name}" is empty or already used`, 'error');
    return render();
  }
  renameInViews(widget.name, name);
  change((layout) => {
    for (const binding of layout.bindings || []) if (binding.widget === widget.name) binding.widget = name;
    for (const mapping of layout.mappings || []) if (mapping.widget === widget.name) mapping.widget = name;
    for (const link of layout.links || []) {
      if (link.widget === widget.name) link.widget = name;
      if (link.target === widget.name) link.target = name;
    }
    widget.name = name;
  });
}

// Renaming in Layers: double-click a name, or F2 for the selected widget
export function startRename(path) {
  const widget = widgetAt(path);
  if (!widget) return;
  state.renaming = { path, value: widget.name, fresh: true };
  renderTree();
}

function finishRename(keep) {
  const renaming = state.renaming;
  if (!renaming) return;
  state.renaming = null;
  const widget = widgetAt(renaming.path);
  if (keep && widget) renameWidget(widget, renaming.value);
  else renderTree();
}

function renameInput() {
  const renaming = state.renaming;
  return el('input', {
    type: 'text', class: 'rename', value: renaming.value, 'aria-label': 'Widget name',
    oninput: (event) => {
      renaming.value = event.target.value;
      renaming.caret = [event.target.selectionStart, event.target.selectionEnd];
    },
    onkeydown: (event) => {
      event.stopPropagation();
      if (event.key === 'Enter') finishRename(true);
      if (event.key === 'Escape') finishRename(false);
    },
    onblur: (event) => { if (event.target.isConnected && state.renaming === renaming) finishRename(true); },
    onclick: (event) => event.stopPropagation(),
    ondblclick: (event) => event.stopPropagation(),
    onpointerdown: (event) => event.stopPropagation(),
  });
}

export function renderTree() {
  const collapsed = viewSet('collapsed');
  const hiddenHere = viewSet('hidden');
  const locked = viewSet('locked');
  const query = $('layer-search').value.trim().toLowerCase();
  const matches = (widget) => !query || widget.name.toLowerCase().includes(query) || widget.type.toLowerCase().includes(query)
    || (widget.widgets || []).some(matches);
  // Groups around the selection open up, without being remembered as open
  const open = new Set(selectedPaths().flatMap((path) => path.slice(0, -1).map((_, i) => widgetAt(path.slice(0, i + 1)).name)));
  const toggle = (kind, name, on, titles, icons) => el('button', {
    class: `toggle ${kind}${on ? ' on' : ''}`, title: on ? titles[1] : titles[0], 'aria-label': on ? titles[1] : titles[0],
    onclick: (event) => {
      event.stopPropagation();
      toggleView(kind, name);
    },
  }, icon(on ? icons[1] : icons[0]));
  const build = (list, prefix) => el('ul', {}, [...list.entries()].reverse().filter(([, widget]) => matches(widget)).map(([index, widget]) => {
    const path = [...prefix, index];
    const selected = isSelected(path);
    const children = widget.widgets?.length;
    const folded = children && collapsed.has(widget.name) && !query && !open.has(widget.name);
    const offPage = widget.type !== undefined && prefix.length && widgetAt(prefix).type === 'Pages' && index !== currentPage(widgetAt(prefix));
    const here = hiddenHere.has(widget.name);
    const renaming = state.renaming && samePath(state.renaming.path, path);
    return el('li', {},
      el('div', {
        class: `node${selected ? ' selected' : ''}${offPage ? ' off-page' : ''}${here ? ' hidden-here' : ''}`,
        title: offPage ? 'Another page: selecting it shows that page' : 'Drag to reorder, or onto a group to move it inside',
        draggable: renaming ? 'false' : 'true',
        dataset: { path: path.join('.') },
        ondragstart: (event) => {
          // Dragging a selected layer moves the whole selection
          state.layerDrag = isSelected(path) ? topSelected() : [path];
          event.dataTransfer.setData('text/plain', widget.name);
          event.dataTransfer.effectAllowed = 'move';
        },
        ondragend: () => { state.layerDrag = null; clearDropMarks(); },
        ondragover: (event) => layerDragOver(event, path),
        ondrop: (event) => layerDrop(event, path),
        onclick: (event) => {
          // From the layer clicked before (unless the selection changed elsewhere since), else the widget picked last
          const anchor = state.layerAnchor && state.layerAnchor.selection === state.selection ? state.layerAnchor.path : state.selection?.path;
          const remember = (from) => { state.layerAnchor = { path: from, selection: state.selection }; };
          if (event.shiftKey && anchor) {
            selectLayerRange(anchor, path);
            return remember(anchor);
          }
          if (event.shiftKey || event.ctrlKey || event.metaKey) {
            toggleSelected(path);
            return remember(path);
          }
          const hidden = hiddenBy(path);
          if (!hidden.length) {
            select(widgetSelection([path]));
            return remember(path);
          }
          // Show the page the widget is on
          change(() => {
            for (const [pagesPath, page] of hidden) setOption(widgetAt(pagesPath), 'page', page || undefined);
            state.selection = widgetSelection([path]);
          });
          remember(path);
        },
      },
        el('button', {
          class: `caret${children ? '' : ' none'}`, title: folded ? 'Show what is inside' : 'Fold', 'aria-label': folded ? 'Expand' : 'Collapse',
          onclick: (event) => {
            event.stopPropagation();
            if (children) toggleView('collapsed', widget.name);
          },
        }, folded ? '▸' : '▾'),
        renaming ? renameInput() : el('span', {
          class: 'name', title: 'Double-click to rename',
          ondblclick: (event) => {
            event.stopPropagation();
            startRename(path);
          },
        }, widget.name),
        el('span', { class: 'type' }, folded ? `${widget.type} · ${children}` : widget.type),
        toggle('hidden', widget.name, here, ['Hide in the designer (the layout keeps it)', 'Show in the designer'], ['eye', 'eyeOff']),
        toggle('locked', widget.name, locked.has(widget.name), ['Lock: no dragging it on the grid', 'Unlock'], ['lock', 'lock'])),
      children && !folded ? build(widget.widgets, path) : null);
  }));
  const tree = $('tree');
  tree.replaceChildren(...build(state.layout.widgets, []).children);
  if (!state.layout.widgets.length) tree.append(el('li', { class: 'hint' }, 'No widgets yet.'));
  else if (!tree.children.length) tree.append(el('li', { class: 'hint' }, `Nothing matches "${query}".`));
  const input = tree.querySelector('input.rename');
  if (input) {
    // Rebuilt while typing: keep the caret where it was
    input.focus();
    if (state.renaming.fresh) input.select();
    else if (state.renaming.caret) input.setSelectionRange(...state.renaming.caret);
    state.renaming.fresh = false;
  } else if (state.renaming) state.renaming = null; // its layer went away
}

// Shift+click in Layers: every layer shown between the one clicked before and this one
function selectLayerRange(from, to) {
  const shown = [...$('tree').querySelectorAll('.node')].map((node) => node.dataset.path.split('.').map(Number));
  const start = shown.findIndex((path) => samePath(path, from));
  const end = shown.findIndex((path) => samePath(path, to));
  if (start < 0 || end < 0) return toggleSelected(to);
  const range = shown.slice(Math.min(start, end), Math.max(start, end) + 1);
  select(widgetSelection(range, to));
}

// ---------------------------------------------------------------- reordering layers

function clearDropMarks() {
  for (const node of $('tree').querySelectorAll('.drop-above, .drop-below, .drop-into')) {
    node.classList.remove('drop-above', 'drop-below', 'drop-into');
  }
}

// The group a layer dropped into ``path`` goes in: a group, or the shown page of a Pages
function dropContainer(path) {
  const widget = widgetAt(path);
  if (widget.type === 'Pages') {
    const page = widget.widgets?.[currentPage(widget)];
    return page && isGroup(page) ? [...path, currentPage(widget)] : null;
  }
  return isGroup(widget) ? path : null;
}

// Where a drop on the layer at ``path`` puts the dragged ones: above or below it (the
// tree lists the topmost first), or into it when it's a group and the pointer is in the middle
function layerZone(event, path) {
  const dragged = state.layerDrag || [];
  // Not onto itself or inside itself
  if (dragged.some((from) => samePath(from, path) || isInside(path, from))) return null;
  const bounds = event.currentTarget.getBoundingClientRect();
  const at = (event.clientY - bounds.top) / bounds.height;
  const container = dropContainer(path);
  if (container && !dragged.some((from) => samePath(from, container) || isInside(container, from)) && at > 0.25 && at < 0.75) return 'into';
  return at < 0.5 ? 'above' : 'below';
}

function layerDragOver(event, path) {
  if (!state.layerDrag) return;
  const zone = layerZone(event, path);
  clearDropMarks();
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  event.dataTransfer.dropEffect = 'move';
  event.currentTarget.classList.add(`drop-${zone}`);
}

function layerDrop(event, path) {
  const paths = state.layerDrag;
  const zone = paths && layerZone(event, path);
  clearDropMarks();
  state.layerDrag = null;
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  moveLayers(paths, path, zone);
}

// Move the widgets at ``paths`` above or below the one at ``target``, or into it. They
// keep their place on the grid when they fit in the new group, else move inside it.
function moveLayers(paths, target, zone) {
  // In drawing order, so they stay in it
  const widgets = [...paths].sort(comparePaths).map(widgetAt);
  const placed = new Map(widgets.map((widget, i) => [widget, absolute(pathsOf([widget])[0])]));
  const anchor = widgetAt(target);
  const container = zone === 'into' ? widgetAt(dropContainer(target)) : null;
  change((layout) => {
    for (const widget of widgets) {
      const list = childrenOf(pathsOf([widget])[0]);
      list.splice(list.indexOf(widget), 1);
    }
    let parent, list, index;
    if (container) {
      parent = pathsOf([container])[0];
      container.widgets = container.widgets || [];
      list = container.widgets;
      // On top of what's in it
      index = list.length;
    } else {
      const at = pathsOf([anchor])[0];
      parent = at.slice(0, -1);
      list = childrenOf(at);
      index = list.indexOf(anchor) + (zone === 'above' ? 1 : 0);
    }
    const [ox, oy] = parent.length ? absolute(parent) : [0, 0];
    const [width, height] = parent.length ? [widgetAt(parent).width, widgetAt(parent).height] : [layout.surface.width, layout.surface.height];
    for (const widget of widgets) {
      const [ax, ay] = placed.get(widget);
      widget.width = Math.min(widget.width, width);
      widget.height = Math.min(widget.height, height);
      widget.x = clamp(ax - ox, 0, width - widget.width);
      widget.y = clamp(ay - oy, 0, height - widget.height);
    }
    list.splice(index, 0, ...widgets);
    state.selection = widgetSelection(pathsOf(widgets));
  });
}

function comparePaths(a, b) {
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] - b[i];
  return a.length - b.length;
}

// Dropped below the last layer: topmost on the surface
export function treeDragOver(event) {
  if (!state.layerDrag || event.target.closest('.node')) return;
  event.preventDefault();
  clearDropMarks();
}

export function treeDrop(event) {
  if (!state.layerDrag || event.target.closest('.node')) return;
  event.preventDefault();
  const paths = state.layerDrag;
  state.layerDrag = null;
  // Above the topmost surface widget that isn't being dragged
  const roots = state.layout.widgets.map((_, index) => index).reverse();
  const top = roots.find((index) => !paths.some((path) => samePath(path, [index])));
  if (top !== undefined) moveLayers(paths, [top], 'above');
}
