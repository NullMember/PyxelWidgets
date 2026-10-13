// The grid: rendering, zoom, widget outlines, dragging and the selection rectangle

import { state, $, el } from './core.js';
import { viewSet } from './prefs.js';
import { widgetAt, containerSize, absolute, allWidgets, deviceInfo, deviceSize, isGroup, hiddenBy, samePath,
  widgetSelection, selectedPaths, isSelected, topSelected, toggleSelected } from './model.js';
import { renderOutputs } from './mappings.js';
import { renderRules } from './rules.js';
import { renderDrawer } from './drawer.js';
import { change } from './history.js';
import { padDown, pressAt, padUp } from './preview.js';
import { showPadInfo, hidePadInfo } from './padinfo.js';
import { renderTree } from './layers.js';
import { renderDevices, select, renderProperties, renderCode, renderToolbar, renderDirty } from './properties.js';
import { renderWelcome } from './files.js';

export function render() {
  renderBoard();
  renderOverlay();
  renderTree();
  renderDevices();
  renderOutputs();
  renderProperties();
  renderCode();
  renderToolbar();
  renderDirty();
  renderDrawer();
  renderWelcome();
  renderRules();
}

export function step() {
  const style = getComputedStyle(document.documentElement);
  return parseFloat(style.getPropertyValue('--pad')) + parseFloat(style.getPropertyValue('--gap'));
}

export function renderBoard() {
  const { width, height } = state.layout.surface;
  const stage = $('stage');
  const gap = 4;
  // Pads as big as the stage allows (the board's frame and the stage's padding around them)
  const fit = (space, count) => (space - 80 - gap * (count - 1)) / count;
  const fitted = Math.max(16, Math.min(200, fit(stage.clientWidth, width), fit(stage.clientHeight - 40, height)));
  state.fitted = fitted;
  // In the browser's layout units (1/64 px), so pad positions add up exactly
  const pad = Math.round(clamp(fitted * state.zoom, 6, 320) * 64) / 64;
  document.documentElement.style.setProperty('--pad', `${pad}px`);
  document.documentElement.style.setProperty('--step', `${pad + gap}px`);
  zoomLabel();
  positionBoard();
  if (state.frameSize[0] === width && state.frameSize[1] === height) return;
  state.frameSize = [width, height];
  const pads = $('pads');
  pads.style.gridTemplateColumns = `repeat(${width}, var(--pad))`;
  pads.replaceChildren();
  for (let top = 0; top < height; top++) {
    for (let x = 0; x < width; x++) {
      pads.append(el('div', {
        class: 'pad', dataset: { x, y: height - 1 - top },
        onpointerdown: padDown, onpointerup: padUp, onpointercancel: padUp, onpointermove: showPadInfo, onpointerleave: hidePadInfo,
      }));
    }
  }
  positionBoard();
}

// The board in the middle of the stage (above the status line), moved by `state.pan`; at least
// a corner of it stays in view
function positionBoard() {
  const stage = $('stage'), board = $('board');
  const width = board.offsetWidth, height = board.offsetHeight;
  const room = [stage.clientWidth, stage.clientHeight - 40];
  const keep = 80;
  const pan = state.pan;
  const centre = [(room[0] - width) / 2, (room[1] - height) / 2];
  pan.x = clamp(pan.x, keep - width - centre[0], room[0] - keep - centre[0]);
  pan.y = clamp(pan.y, keep - height - centre[1], room[1] - keep - centre[1]);
  board.style.left = `${Math.round(centre[0] + pan.x)}px`;
  board.style.top = `${Math.round(centre[1] + pan.y)}px`;
}

export function panBy(dx, dy) {
  state.pan.x += dx;
  state.pan.y += dy;
  positionBoard();
}

// Zooming eases towards `target` a frame at a time; the pad under `anchor` (client x, y) stays put
export const zooming = { target: null, anchor: null, frame: null };

// The zoom it is going to
function zoomLabel() {
  const shown = zooming.target ?? state.zoom;
  $('zoom-fit').textContent = Math.abs(shown - 1) < 0.005 ? 'Fit' : `${Math.round(shown * 100)}%`;
}

export function setZoom(zoom, anchor = null) {
  zooming.target = clamp(zoom, 0.25, 8);
  zooming.centre = zoom === 1 && !anchor;
  zooming.anchor = anchor ? { x: anchor.clientX, y: anchor.clientY } : null;
  zoomLabel();
  if (zooming.frame === null) zooming.frame = requestAnimationFrame(zoomFrame);
}

function zoomFrame() {
  zooming.frame = null;
  const target = zooming.target;
  if (target === null) return;
  // A third of the way each frame, evenly on a log scale
  const next = Math.abs(Math.log(target / state.zoom)) < 0.004 ? target : state.zoom * (target / state.zoom) ** 0.35;
  if (zooming.centre) {
    // Fitting also brings the board back to the middle
    const left = next === target ? 0 : 0.65;
    state.pan.x *= left;
    state.pan.y *= left;
  }
  zoomNow(next, zooming.centre ? null : zooming.anchor);
  if (next === target && !(zooming.centre && (state.pan.x || state.pan.y))) zooming.target = null;
  else zooming.frame = requestAnimationFrame(zoomFrame);
  if (zooming.target === null) renderBoard();
}

// Zoom at once, keeping the point at `anchor` (else the stage's middle) over the same spot of the grid
function zoomNow(zoom, anchor = null) {
  const stage = $('stage');
  const bounds = stage.getBoundingClientRect();
  const point = anchor || { x: bounds.left + stage.clientWidth / 2, y: bounds.top + stage.clientHeight / 2 };
  const before = $('pads').getBoundingClientRect();
  const u = (point.x - before.left) / before.width, v = (point.y - before.top) / before.height;
  state.zoom = zoom;
  renderBoard();
  const after = $('pads').getBoundingClientRect();
  panBy(point.x - (after.left + u * after.width), point.y - (after.top + v * after.height));
}

// Outlines follow --step, so zooming doesn't redraw them
export function place(node, x, y, width, height) {
  const surfaceHeight = state.layout.surface.height;
  node.style.left = `calc(${x} * var(--step) - 2px)`;
  node.style.top = `calc(${surfaceHeight - y - height} * var(--step) - 2px)`;
  node.style.width = `calc(${width} * var(--step))`;
  node.style.height = `calc(${height} * var(--step))`;
}

// Links between widgets: the widgets `name` changes, and the ones changing it
function relations(name) {
  const links = state.layout.links || [];
  return {
    affects: new Set(links.filter((link) => link.widget === name && link.target && link.target !== name).map((link) => link.target)),
    affectedBy: new Set(links.filter((link) => link.target === name && link.widget !== name).map((link) => link.widget)),
  };
}

export function renderOverlay() {
  const overlay = $('overlay');
  overlay.replaceChildren();
  // Devices at the same place (e.g. a Launchpad mirrored in a browser) share one tag
  const places = new Map();
  state.layout.devices.forEach((device, index) => {
    const key = `${device.x || 0},${device.y || 0}`;
    if (!places.has(key)) places.set(key, []);
    places.get(key).push(index);
  });
  state.layout.devices.forEach((device, index) => {
    const [width, height] = deviceSize(device);
    const selected = state.selection?.kind === 'device' && state.selection.index === index;
    const together = places.get(`${device.x || 0},${device.y || 0}`);
    const tag = together[0] === index ? el('span', { class: 'tag' },
      together.map((other, i) => [
        i ? el('span', { class: 'mirror' }, '+') : null,
        el('span', {
          title: 'Drag to move the device on the surface',
          onpointerdown: (event) => startDeviceDrag(event, other),
        }, deviceInfo(state.layout.devices[other])?.model || state.layout.devices[other].type),
      ]),
      together.length > 1 ? el('span', { class: 'mirror', title: 'They show the same pads' }, '· mirrored') : null) : null;
    const outline = el('div', { class: `outline device${selected ? ' selected' : ''}`, dataset: { device: index } }, tag);
    place(outline, device.x || 0, device.y || 0, width, height);
    overlay.append(outline);
  });
  const paths = selectedPaths();
  const single = paths.length === 1;
  const related = single ? relations(widgetAt(paths[0]).name) : { affects: new Set(), affectedBy: new Set() };
  const hiddenHere = viewSet('hidden');
  const locked = viewSet('locked');
  for (const { widget, path } of allWidgets()) {
    const [x, y] = absolute(path);
    const selected = isSelected(path);
    // Widgets on other pages of a Pages aren't shown
    if (hiddenBy(path).length && !selected) continue;
    const hidden = widget.options?.visible === false;
    const classes = ['outline', 'widget'];
    if (isGroup(widget)) classes.push('group');
    if (selected) classes.push('selected');
    if (related.affects.has(widget.name)) classes.push('affects');
    if (related.affectedBy.has(widget.name)) classes.push('affected-by');
    if (locked.has(widget.name)) classes.push('locked');
    if (hiddenHere.has(widget.name) && !selected) classes.push('hidden-here');
    const role = related.affects.has(widget.name) ? ' · changed by the selection' : related.affectedBy.has(widget.name) ? ' · changes the selection' : '';
    const outline = el('div', {
      class: classes.join(' '),
      title: `${widget.name} (${widget.type})${role}`,
      dataset: { path: path.join('.') },
      onpointerdown: (event) => startDrag(event, path, 'move'),
    }, el('span', { class: 'tag' }, widget.name));
    if (hidden) outline.style.opacity = 0.35;
    if (selected && single) outline.append(el('div', { class: 'handle', onpointerdown: (event) => startDrag(event, path, 'resize') }));
    place(outline, x, y, widget.width, widget.height);
    overlay.append(outline);
  }
}

// Calls move(dx, dy) in pads while the pointer drags, then done(dx, dy)
function dragPads(event, move, done) {
  const start = [event.clientX, event.clientY];
  let delta = [0, 0];
  const onMove = (e) => {
    delta = [Math.round((e.clientX - start[0]) / step()), -Math.round((e.clientY - start[1]) / step())];
    move(...delta);
  };
  const onUp = () => {
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    done(...delta);
  };
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
}

export function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

// The furthest every widget of `paths` can move together while staying in its parent
export function moveLimits(paths) {
  const limits = { dx: [-Infinity, Infinity], dy: [-Infinity, Infinity] };
  for (const path of paths) {
    const widget = widgetAt(path);
    const [parentWidth, parentHeight] = containerSize(path);
    const x = widget.x || 0, y = widget.y || 0;
    limits.dx = [Math.max(limits.dx[0], -x), Math.min(limits.dx[1], parentWidth - widget.width - x)];
    limits.dy = [Math.max(limits.dy[0], -y), Math.min(limits.dy[1], parentHeight - widget.height - y)];
  }
  return limits;
}

function startDrag(event, path, kind) {
  if (event.altKey && state.mode === 'edit') return pressAt(event);
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.stopPropagation();
  event.preventDefault();
  if (event.shiftKey || event.ctrlKey || event.metaKey) return toggleSelected(path);
  if (!isSelected(path)) {
    state.selection = widgetSelection([path]);
    render();
  }
  if (kind === 'resize') {
    const widget = widgetAt(path);
    const [parentWidth, parentHeight] = containerSize(path);
    const x = widget.x || 0, y = widget.y || 0;
    const node = $('overlay').querySelector(`.outline.widget[data-path="${path.join('.')}"]`);
    const size = (dx, dy) => [clamp(widget.width + dx, 1, parentWidth - x), clamp(widget.height + dy, 1, parentHeight - y)];
    return dragPads(event,
      (dx, dy) => place(node, ...absolute(path), ...size(dx, dy)),
      (dx, dy) => {
        const [width, height] = size(dx, dy);
        if (width !== widget.width || height !== widget.height) change(() => Object.assign(widget, { width, height }));
      });
  }
  // Move every selected widget (a selected group carries its children)
  const paths = topSelected();
  const limits = moveLimits(paths);
  const nodes = paths.map((p) => [p, $('overlay').querySelector(`.outline.widget[data-path="${p.join('.')}"]`)]);
  const offset = (dx, dy) => [clamp(dx, ...limits.dx), clamp(dy, ...limits.dy)];
  dragPads(event,
    (dx, dy) => {
      const [ox, oy] = offset(dx, dy);
      for (const [p, node] of nodes) {
        const [x, y] = absolute(p);
        if (node) place(node, x + ox, y + oy, widgetAt(p).width, widgetAt(p).height);
      }
    },
    (dx, dy) => {
      const [ox, oy] = offset(dx, dy);
      if (!ox && !oy) return;
      const widgets = paths.map(widgetAt);
      change(() => widgets.forEach((widget) => Object.assign(widget, { x: (widget.x || 0) + ox, y: (widget.y || 0) + oy })));
    });
}

function startDeviceDrag(event, index) {
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.stopPropagation();
  event.preventDefault();
  if (!(state.selection?.kind === 'device' && state.selection.index === index)) select({ kind: 'device', index });
  const device = state.layout.devices[index];
  const [width, height] = deviceSize(device);
  const { width: surfaceWidth, height: surfaceHeight } = state.layout.surface;
  const x = device.x || 0, y = device.y || 0;
  // Inside the surface; one bigger than the surface can only shift over it
  const position = (dx, dy) => [
    clamp(x + dx, Math.min(0, surfaceWidth - width), Math.max(0, surfaceWidth - width)),
    clamp(y + dy, Math.min(0, surfaceHeight - height), Math.max(0, surfaceHeight - height)),
  ];
  const node = $('overlay').querySelector(`.outline.device[data-device="${index}"]`);
  dragPads(event,
    (dx, dy) => place(node, ...position(dx, dy), width, height),
    (dx, dy) => {
      const [nx, ny] = position(dx, dy);
      if (nx !== x || ny !== y) change(() => Object.assign(device, { x: nx, y: ny }));
    });
}

// Widgets inside a rectangle of pads (x0, y0 inclusive, x1, y1 exclusive): a group that
// doesn't fit offers its children instead
function widgetsIn(x0, y0, x1, y1) {
  const found = [];
  const visit = (list, prefix) => list.forEach((widget, index) => {
    const path = [...prefix, index];
    if (hiddenBy(path).length) return;
    const [x, y] = absolute(path);
    // Locked and hidden-here widgets aren't picked on the grid
    const skipped = viewSet('locked').has(widget.name) || viewSet('hidden').has(widget.name);
    if (!skipped && x >= x0 && y >= y0 && x + widget.width <= x1 && y + widget.height <= y1) found.push(path);
    else if (widget.widgets) visit(widget.widgets, path);
  });
  visit(state.layout.widgets, []);
  return found;
}

// Dragging on empty space draws a selection rectangle; a click there selects the surface
export function startMarquee(event) {
  if (state.mode !== 'edit' || event.button !== 0) return;
  event.preventDefault();
  const overlay = $('overlay');
  const bounds = overlay.getBoundingClientRect();
  const adding = event.shiftKey || event.ctrlKey || event.metaKey;
  const kept = adding ? selectedPaths() : [];
  const start = [event.clientX - bounds.left, event.clientY - bounds.top];
  const box = el('div', { class: 'marquee' });
  let moved = false;
  const move = (e) => {
    const end = [e.clientX - bounds.left, e.clientY - bounds.top];
    if (!moved && Math.hypot(end[0] - start[0], end[1] - start[1]) < 4) return;
    if (!moved) overlay.append(box);
    moved = true;
    const [left, right] = [Math.min(start[0], end[0]), Math.max(start[0], end[0])];
    const [top, bottom] = [Math.min(start[1], end[1]), Math.max(start[1], end[1])];
    Object.assign(box.style, { left: `${left}px`, top: `${top}px`, width: `${right - left}px`, height: `${bottom - top}px` });
    // Pads whose centre is inside
    const size = step();
    const centre = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--pad')) / 2;
    const first = (from) => Math.ceil((from - centre) / size), after = (to) => Math.floor((to - centre) / size) + 1;
    const height = state.layout.surface.height;
    const [x0, x1] = [first(left), after(right)];
    const rows = [first(top), after(bottom)];
    const found = x1 > x0 && rows[1] > rows[0] ? widgetsIn(x0, height - rows[1], x1, height - rows[0]) : [];
    for (const node of overlay.querySelectorAll('.outline.widget')) {
      const path = node.dataset.path.split('.').map(Number);
      node.classList.toggle('selected', [...kept, ...found].some((p) => samePath(p, path)));
    }
    box.dataset.found = JSON.stringify(found);
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    box.remove();
    if (!moved) {
      if (!adding) select(null);
      return;
    }
    const found = JSON.parse(box.dataset.found || '[]').filter((path) => !kept.some((p) => samePath(p, path)));
    select(widgetSelection([...kept, ...found]));
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}
