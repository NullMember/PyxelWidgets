// The live preview: polling frames and events, pressing pads

import { state, $, api } from './core.js';
import { renderOutputs } from './mappings.js';
import { renderDrawer, renderEvents } from './drawer.js';
import { widgetNamed } from './links.js';
import { change, flushSync, setStatus } from './history.js';
import { startMarquee } from './board.js';
import { renderDevices, syncStatus, renderToolbar } from './properties.js';

export async function poll() {
  try {
    const frame = await api('GET', `/api/frame?since=${state.lastEvent}`);
    paint(frame);
    addEvents(frame.events);
    if (frame.playing !== state.playing || frame.synced !== state.synced) {
      state.playing = frame.playing;
      state.synced = !!frame.synced;
      renderToolbar();
    }
    state.bpm = frame.bpm;
    if ($('sync-status')) $('sync-status').textContent = syncStatus();
    $('position').textContent = frame.position ? `bar ${frame.position}` : '';
    if (JSON.stringify(frame.hardware) !== JSON.stringify(state.hardware)) {
      state.hardware = frame.hardware;
      renderToolbar();
      renderDevices();
      renderOutputs();
      renderDrawer();
    }
  } catch {
    setStatus('Lost connection to the designer server', 'error');
  }
  setTimeout(poll, document.hidden ? 500 : 80);
}

function paint(frame) {
  if (frame.width !== state.frameSize[0] || frame.height !== state.frameSize[1]) return;
  const pads = $('pads').children;
  frame.pixels.forEach((row, top) => row.forEach((color, x) => {
    const pad = pads[top * frame.width + x];
    if (pad && pad.dataset.color !== color) {
      pad.dataset.color = color;
      pad.style.backgroundColor = color;
    }
  }));
}

function addEvents(events) {
  if (!events.length) return;
  const stored = new Map();
  for (const event of events) {
    state.lastEvent = Math.max(state.lastEvent, event.id);
    if (event.presets) {
      stored.set(event.widget, event.presets);
      delete event.presets;
    }
    state.eventLog.push(event);
  }
  if (stored.size) keepPresets(stored);
  if (state.eventLog.length > 500) state.eventLog.splice(0, state.eventLog.length - 500);
  renderEvents();
}

// Presets groups (with save on) stored something: it goes in the layout, so saving keeps it
function keepPresets(stored) {
  change((layout) => {
    for (const [name, presets] of stored) {
      const widget = widgetNamed(name);
      if (widget) widget.options = { ...widget.options, presets };
    }
  });
}

// Input goes in order, and after any pending layout change: rebuilding the preview resets widget state
let inputs = Promise.resolve();
function sendInput(x, y, velocity) {
  inputs = inputs.then(flushSync).then(() => api('POST', '/api/input', { x, y, velocity })).catch(() => {});
}

export const held = new Map();
export function padDown(event) {
  if (state.mode !== 'try' && !event.altKey) return startMarquee(event);
  pressAt(event);
}

// Press the pad under the pointer (Try mode, or Alt + click while editing) until it's released
export function pressAt(event) {
  const pad = document.elementsFromPoint(event.clientX, event.clientY).find((node) => node.classList?.contains('pad'));
  if (!pad) return;
  event.preventDefault();
  event.stopPropagation();
  const x = Number(pad.dataset.x), y = Number(pad.dataset.y);
  held.set(event.pointerId, [x, y]);
  const up = (e) => {
    if (e.pointerId !== event.pointerId) return;
    window.removeEventListener('pointerup', up);
    window.removeEventListener('pointercancel', up);
    padUp(e);
  };
  window.addEventListener('pointerup', up);
  window.addEventListener('pointercancel', up);
  sendInput(x, y, 1.0);
}

export function padUp(event) {
  const pad = held.get(event.pointerId);
  if (!pad) return;
  held.delete(event.pointerId);
  sendInput(pad[0], pad[1], 0.0);
}
