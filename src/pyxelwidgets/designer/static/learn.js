// Learn buttons: the next control moved on a connected device fills a binding; the next message an
// output receives (from the DAW) fills a message, keeping the event values it sends

import { state, el } from './core.js';
import { outputsOf } from './mappings.js';
import { setStatus } from './history.js';
import { render } from './board.js';

// A button waiting for a control ('control') or for a message from `output` ('message'); `apply(event)`
// gets the log entry: a control event ({_device, control, ...}) or a received message ({_learn, ...})
export function learnButton(id, kind, apply, output = null) {
  const active = state.learning?.id === id;
  return el('button', {
    id: `${id}-learn`, class: active ? 'learn active' : 'learn',
    title: kind === 'control' ? 'Move a knob, fader or button on a connected device to pick it' : 'Send a message from the DAW (move or press something there) to fill this one in',
    onclick: () => (active ? stopLearning() : startLearning({ id, kind, output, apply })),
  }, active ? 'Cancel' : 'Learn');
}

function startLearning(learning) {
  if (learning.kind === 'control' && !state.hardware.devices.some((device) => device?.connected)) {
    return setStatus('Connect a device to learn its controls (Connections, or the device list)', 'error');
  }
  if (learning.kind === 'message') {
    const index = outputsOf().findIndex((output) => output.name === learning.output);
    if (!state.hardware.outputs[index]?.connected) return setStatus(`Connect ${learning.output} to learn from what it receives`, 'error');
  }
  state.learning = learning;
  setStatus(learning.kind === 'control' ? 'Move a knob, fader or button on a connected device… (Escape cancels)'
    : `Move or press something in the DAW: the next message ${learning.output} receives fills this one in… (Escape cancels)`);
  render();
}

export function stopLearning() {
  if (!state.learning) return;
  state.learning = null;
  setStatus(state.error || '', state.error ? 'error' : '');
  render();
}

// New preview events: the first one a waiting Learn button takes
export function learnFrom(events) {
  const learning = state.learning;
  if (!learning) return;
  const event = events.find((entry) => (learning.kind === 'control' ? entry._device !== undefined : entry._learn && entry.widget === learning.output));
  if (!event) return;
  state.learning = null;
  learning.apply(event);
  setStatus(`Learned ${learning.kind === 'control' ? event.control : event.event.replace('← ', '')}`, 'ok');
}

// The field carrying the value of each message type (where a learned message keeps the event's value)
const VALUE_FIELDS = {
  NoteOn: 'velocity', NoteOff: 'velocity', ControlChange: 'value', PitchBend: 'value', PolyPressure: 'pressure',
  ChannelPressure: 'pressure', ProgramChange: 'program', Command: 'value', TrackParameter: 'value', PluginParameter: 'value',
};

const isSource = (value) => value && typeof value === 'object' && 'source' in value;

// `current` filled in from `received` (layout JSON): the received message's constants (channel, note,
// controller, address, command name...), with the event values `current` sends kept where they fit
export function learnedMessage(current, received) {
  const same = current.type === received.type;
  const values = [...Object.values(current), ...(current.args || [])].filter(isSource);
  const main = values[0];
  if (received.type === 'OscMessage') {
    const args = (received.args || []).map((arg, i) => {
      const old = same ? current.args?.[i] : undefined;
      if (isSource(old)) return old;
      return typeof arg === 'number' && main && i === 0 ? main : arg;
    });
    return { type: 'OscMessage', address: received.address, args };
  }
  const next = { type: received.type };
  const fields = state.catalog.messages[received.type]?.fields || [];
  for (const field of fields) {
    if (!(field.name in received)) continue;
    const old = current[field.name];
    if (isSource(old) && (same || field.name === VALUE_FIELDS[received.type])) next[field.name] = old;
    else if (field.name === VALUE_FIELDS[received.type] && main) next[field.name] = main;
    else next[field.name] = received[field.name];
  }
  return next;
}
