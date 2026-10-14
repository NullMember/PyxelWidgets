// Shared state, constants and DOM helpers


export const DEFAULT_SIZE = {
  Button: [1, 1], ButtonGroup: [4, 1], ClipLauncher: [8, 4], DrumPads: [4, 4], Fader: [1, 8], Keyboard: [8, 4], Knob: [3, 3],
  Meter: [1, 8], Sequencer: [8, 4], Sprite: [2, 2], Text: [8, 5], Tracker: [4, 8], XY: [4, 4],
  PianoRoll: [8, 8], ChordPads: [8, 4], Arpeggiator: [8, 2], Euclidean: [8, 4], Automaton: [8, 8], TapTempo: [1, 1],
  Stepper: [4, 1], MeterBank: [8, 4], Presets: [8, 8],
};
// Colors offered for painting Sprite frames (any color can be picked too)
export const SWATCHES = ['White', 'Gray', 'Red', 'OrangeRed', 'Orange', 'Yellow', 'Lime', 'Green', 'Cyan', 'DodgerBlue', 'Blue', 'Purple', 'Magenta', 'HotPink'];

export const state = {
  catalog: null,
  // What outputs scanned in the DAW, by output name: {tracks, plugins: {track: [...]}, parameters: {'track/plugin': [...]}}
  scans: {},
  layout: null,
  file: null,
  saved: '',
  // null (surface) | {kind: 'widget', path: [i, j, ...], paths: [path, ...]} | {kind: 'device', index} | {kind: 'output', index}
  // `paths` are all selected widgets, `path` the last one picked (the one panels edit)
  selection: null,
  mode: 'edit',
  history: [],
  future: [],
  lastEvent: 0,
  playing: false,
  hardware: { devices: [], outputs: [] },
  // Options written as formulas that can't be computed now: {widget, option, error}
  formulas: [],
  dragType: null, // a palette widget type being dragged onto the grid
  zoom: 1, // pad size relative to the size that fits the window
  pan: { x: 0, y: 0 }, // the board moved from the middle of the stage, in pixels
  layerDrag: null, // paths of the layers being dragged in the Layers panel
  renaming: null, // the layer being renamed in place: {path, value}
  error: null,
  frameSize: [0, 0],
  spriteFrame: 0, // the Sprite frame being painted
  paint: { color: '#ffffff', erase: false },
  eventLog: [], // events from the preview, newest last
  eventsPaused: false,
  // The messages and links window: shown, every widget's or the selected ones', picked rules, Shift+click
  // start, search, whether keys go to it
  rules: { open: false, all: false, picked: [], anchor: null, query: '', focused: false },
  // Several picked rules edited as one: {kind, rep, others} (see spreadChange)
  broadcast: null,
  // A Learn button waiting for a control or a received message (learn.js): {id, kind, output, apply}
  learning: null,
  pages: {}, // the page each Pages container shows in the preview now, by name
};

export const $ = (id) => document.getElementById(id);

export function fill(node, ...children) {
  node.replaceChildren(...children.flat(Infinity).filter((child) => child != null));
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, '');
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child != null) node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export async function api(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  return { ok: response.ok, ...data };
}

// A widget drawn small (rows from the top of colors, null where transparent), or null
export function thumb(preview, box = 30) {
  if (!preview) return null;
  const rows = preview.length;
  const columns = preview[0].length;
  const cell = Math.max(3, Math.floor((box - (Math.max(rows, columns) - 1)) / Math.max(rows, columns)));
  return el('span', { class: 'thumb', style: `grid-template-columns: repeat(${columns}, ${cell}px); grid-auto-rows: ${cell}px` },
    preview.flat().map((color) => el('i', { style: `background: ${color || '#0c0d10'}` })));
}
