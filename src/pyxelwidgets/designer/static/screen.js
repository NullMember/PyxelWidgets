// Playing on this screen: the layout's Web Grid device is a touch page of pads (pyxelwidgets.devices.web).
// In the Android app or the desktop window it opens in place of the designer (with a way back), in a
// browser in a new tab.

import { state, $, el, fill, appWindow } from './core.js';
import { change, flushSync } from './history.js';

const WEB_GRID = 'web.WebGrid';

export function renderPlayHere() {
  const box = $('play-here');
  if (!box) return;
  const index = state.layout.devices.findIndex((device) => device.type === WEB_GRID);
  const status = index >= 0 ? state.hardware?.devices?.[index] : null;
  fill(box, index < 0
    ? [el('button', { id: 'play-here-add', onclick: addGrid }, 'Add a touch grid'),
      el('span', { class: 'hint' }, 'A Web Grid device: this screen (or a phone or tablet) becomes pads for the layout.')]
    : [el('button', { class: 'primary', id: 'play-here-open', disabled: !status?.url, onclick: () => openGrid(status.url) }, 'Play on this screen'),
      status?.url ? null : el('span', { class: 'hint' }, 'Connect the Web Grid device first (Devices).')]);
}

function addGrid() {
  const { width, height } = state.layout.surface;
  change((layout) => {
    layout.devices.push({ type: WEB_GRID, x: 0, y: 0, options: { columns: width, rows: height } });
  });
}

// The grid's page on the designer's own host name (the grid listens on every address by default)
export async function openGrid(url) {
  const page = `${location.protocol}//${location.hostname}:${new URL(url).port}/`;
  if (!appWindow()) return window.open(page, '_blank');
  await flushSync();
  state.leaving = true;
  location.href = `${page}?back=${encodeURIComponent(`${location.origin}/?mode=perform`)}`;
}
