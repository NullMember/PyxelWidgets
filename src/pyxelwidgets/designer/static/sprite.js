// The Sprite frame painter

import { SWATCHES, state, $, el } from './core.js';
import { change } from './history.js';
import { clamp } from './board.js';
import { setOption, renderProperties } from './properties.js';

// A Sprite's frames sized to the widget: rows from the top, each a list of colors or null.
// Stored frames of another size keep their bottom-left, like the Sprite does.
function spriteFrames(widget) {
  const frames = widget.options?.frames?.length ? widget.options.frames : [[]];
  return frames.map((rows) => Array.from({ length: widget.height }, (_, top) => {
    const row = rows[rows.length - widget.height + top] || [];
    return Array.from({ length: widget.width }, (_, x) => row[x] ?? null);
  }));
}

function setFrames(widget, frames) {
  const blank = frames.length === 1 && frames[0].every((row) => row.every((color) => color === null));
  setOption(widget, 'frames', blank ? undefined : frames);
}

export function spriteEditor(widget) {
  if (state.spriteFor !== widget.name) {
    state.spriteFor = widget.name;
    state.spriteFrame = 0;
  }
  const frames = spriteFrames(widget);
  const index = state.spriteFrame = clamp(state.spriteFrame, 0, frames.length - 1);
  const paint = state.paint;
  const edit = (mutate) => change(() => {
    const copy = spriteFrames(widget);
    mutate(copy);
    setFrames(widget, copy);
  });
  const showFrame = (i) => { state.spriteFrame = i; renderProperties(); };

  // A stroke paints cells as the pointer passes over them, then changes the layout once
  let stroke = null;
  const paintCell = (cell) => {
    if (!stroke || !cell?.classList.contains('cell')) return;
    const color = stroke.erase ? null : paint.color;
    stroke.frame[Number(cell.dataset.top)][Number(cell.dataset.x)] = color;
    cell.style.backgroundColor = color || '';
    cell.classList.toggle('empty', !color);
  };
  const size = clamp(Math.floor(266 / Math.max(widget.width, widget.height * 0.75)) - 2, 6, 28);
  const grid = el('div', {
    class: 'sprite-grid', id: 'sprite-grid', style: `grid-template-columns: repeat(${widget.width}, ${size}px)`,
    oncontextmenu: (e) => e.preventDefault(),
    onpointerdown: (e) => {
      e.preventDefault();
      grid.setPointerCapture(e.pointerId);
      stroke = { erase: paint.erase || e.button === 2, frame: frames[index].map((row) => [...row]) };
      paintCell(e.target);
    },
    // Captured: find the cell under the pointer
    onpointermove: (e) => paintCell(document.elementFromPoint(e.clientX, e.clientY)),
    onpointerup: () => {
      const done = stroke;
      stroke = null;
      if (done && JSON.stringify(done.frame) !== JSON.stringify(frames[index])) edit((copy) => { copy[index] = done.frame; });
    },
  }, frames[index].map((row, top) => row.map((color, x) => el('div', {
    class: `cell${color ? '' : ' empty'}`, dataset: { top, x },
    style: `width: ${size}px; height: ${size}px;${color ? ` background-color: ${color}` : ''}`,
  }))));

  const blankFrame = () => Array.from({ length: widget.height }, () => Array(widget.width).fill(null));
  const swatches = SWATCHES.filter((name) => state.catalog.colors[name]).map((name) => [name, state.catalog.colors[name]]);
  return [
    el('div', { class: 'frames' },
      frames.map((_, i) => el('button', { class: i === index ? 'active' : '', onclick: () => showFrame(i), title: `Paint frame ${i + 1}` }, String(i + 1))),
      el('button', { title: 'Add a blank frame after this one', onclick: () => { state.spriteFrame = index + 1; edit((copy) => copy.splice(index + 1, 0, blankFrame())); } }, '+')),
    el('div', { class: 'paint' },
      el('input', {
        type: 'color', value: paint.color, title: 'Paint color',
        onchange: (e) => { Object.assign(paint, { color: e.target.value, erase: false }); renderProperties(); },
      }),
      el('div', { class: 'swatches' }, swatches.map(([name, text]) => el('button', {
        class: `swatch${!paint.erase && paint.color === text ? ' active' : ''}`, title: name, style: `background-color: ${text}`,
        onclick: () => { Object.assign(paint, { color: text, erase: false }); renderProperties(); },
      }))),
      el('button', {
        class: paint.erase ? 'active' : '', title: 'Paint transparent cells (or drag with the right button)',
        onclick: () => { paint.erase = !paint.erase; renderProperties(); },
      }, 'Eraser')),
    grid,
    el('div', { class: 'actions' },
      el('button', { title: 'Paint the whole frame', onclick: () => edit((copy) => { copy[index] = copy[index].map((row) => row.map(() => (paint.erase ? null : paint.color))); }) }, 'Fill'),
      el('button', { title: 'Copy this frame after it', onclick: () => { state.spriteFrame = index + 1; edit((copy) => copy.splice(index + 1, 0, copy[index].map((row) => [...row]))); } }, 'Copy'),
      el('button', { title: 'Move earlier', disabled: index === 0, onclick: () => { state.spriteFrame = index - 1; edit((copy) => copy.splice(index - 1, 0, ...copy.splice(index, 1))); } }, '◀'),
      el('button', { title: 'Move later', disabled: index === frames.length - 1, onclick: () => { state.spriteFrame = index + 1; edit((copy) => copy.splice(index + 1, 0, ...copy.splice(index, 1))); } }, '▶'),
      el('button', {
        class: 'danger', title: frames.length > 1 ? 'Delete this frame' : 'Clear this frame',
        onclick: () => edit((copy) => (copy.length > 1 ? copy.splice(index, 1) : copy.splice(0, 1, blankFrame()))),
      }, frames.length > 1 ? 'Delete' : 'Clear')),
    el('p', { class: 'hint note' }, frames.length > 1
      ? 'Left-drag paints, right-drag erases. Set a rate to play the frames.'
      : 'Left-drag paints, right-drag erases. Add frames to animate it.'),
  ];
}
