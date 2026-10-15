// The device check: for owners of a device the author can't test. Test patterns on the device and
// questions about them, pads pressed and controls moved, then a report file to share with the developers

import { state, $, el, fill, api, downloadText } from './core.js';
import { deviceControls, deviceInfo } from './model.js';
import { setStatus } from './history.js';

const STEPS = [
  { key: 'intro', pattern: 'off' },
  { key: 'corners', pattern: 'corners' },
  { key: 'pads', pattern: 'pads' },
  { key: 'colors', pattern: 'colors' },
  { key: 'controls', pattern: 'off' },
  { key: 'report', pattern: 'off' },
];
const COLORS = ['red', 'green', 'blue', 'yellow', 'white', 'cyan', 'magenta', 'orange'];

export async function openCheck(index) {
  if (!state.hardware.devices[index]?.connected) return setStatus('Connect the device first (its Connect button)', 'error');
  const reply = await api('POST', '/api/check', { index, pattern: 'off' });
  if (!reply.ok) return setStatus(reply.error, 'error');
  state.check = { index, step: 0, answers: {}, status: reply.check, timer: setInterval(refresh, 250) };
  renderCheck();
}

async function closeCheck() {
  if (!state.check) return;
  clearInterval(state.check.timer);
  state.check = null;
  $('check')?.remove();
  await api('POST', '/api/check', { pattern: null });
}

async function refresh() {
  if (!state.check) return;
  const { check } = await api('GET', '/api/check');
  if (!state.check) return;
  if (!check?.type) {
    // Disconnected or removed meanwhile
    setStatus('The device check ended: the device is gone', 'error');
    return closeCheck();
  }
  const before = JSON.stringify([state.check.status?.pressed, state.check.status?.controls, state.check.status?.raw?.length]);
  state.check.status = check;
  if (before !== JSON.stringify([check.pressed, check.controls, check.raw?.length])) renderCheck();
}

async function go(step) {
  const check = state.check;
  check.step = step;
  const reply = await api('POST', '/api/check', { index: check.index, pattern: STEPS[step].pattern });
  if (reply.ok) check.status = reply.check;
  renderCheck();
}

function answer(key, value) {
  state.check.answers[key] = { ...state.check.answers[key], answer: value };
  if (value === 'yes') go(state.check.step + 1);
  else renderCheck();
}

function question(key, text, choices = [['yes', 'Yes'], ['no', 'No']]) {
  const given = state.check.answers[key] || {};
  return [
    el('p', {}, text),
    el('div', { class: 'answers' }, choices.map(([value, label]) => el('button', {
      class: given.answer === value ? 'active' : '', dataset: { answer: value }, onclick: () => answer(key, value),
    }, label))),
    given.answer && given.answer !== 'yes' ? [
      el('label', { for: `check-note-${key}` }, 'What do you see? (it goes in the report)'),
      el('textarea', {
        id: `check-note-${key}`, rows: 3, value: given.note || '',
        oninput: (e) => { state.check.answers[key] = { ...state.check.answers[key], note: e.target.value }; },
      }, given.note || ''),
    ] : null,
  ];
}

function body(status, device) {
  const { width, height } = status;
  switch (STEPS[state.check.step].key) {
    case 'intro': return [
      el('p', {}, `This checks that PyxelWidgets drives your ${status.model} right: its lights, pads and controls. It takes a few minutes.`),
      el('p', { class: 'hint' }, 'Your answers and what the device sends go into a report file you can share with the developers, e.g. in an issue on GitHub. Nothing is sent anywhere by itself. While checking, the device shows test patterns instead of your widgets.'),
    ];
    case 'corners': return question('corners', `Look at the device: is the bottom-left pad red, the top-left one green and the top-right one blue (the others dark)?`);
    case 'pads': {
      const [first, second] = status.pressed;
      const expected = [[0, 0], [width - 1, height - 1]];
      const line = (place, want, label) => el('li', { class: !place ? '' : place[0] === want[0] && place[1] === want[1] ? 'ok' : 'wrong' },
        `${label}: ${place ? `x ${place[0]}, y ${place[1]}` : 'not yet'} (should be x ${want[0]}, y ${want[1]})`);
      return [
        el('p', {}, 'Press the bottom-left pad, then the top-right one. Pads you press light up white while held; then try a few others.'),
        el('ul', { class: 'check-list', id: 'check-pads' }, line(first, expected[0], 'First press'), line(second, expected[1], 'Second press')),
        el('p', { class: 'hint' }, `${status.pressed.length} press${status.pressed.length === 1 ? '' : 'es'} so far.`),
      ];
    }
    case 'colors': return question('colors', `The rows from the bottom should be ${COLORS.slice(0, height).join(', ')}${height > COLORS.length ? ', then again' : ''}. Are they?`,
      [['yes', 'Yes'], ['close', 'Close (other shades)'], ['no', 'No']]);
    case 'controls': {
      const controls = deviceControls(device);
      const seen = status.controls || {};
      return [
        el('p', {}, controls.length ? 'Move every knob, fader and encoder, and press every button. Each one ticks when PyxelWidgets understands it.' : 'This device has no controls besides its pads.'),
        controls.length ? el('ul', { class: 'check-list controls', id: 'check-controls' }, controls.map((control) => el('li', { class: seen[control.name] ? 'ok' : '' },
          `${control.name} (${control.kind})${seen[control.name] ? ` · ${seen[control.name].last}` : ''}`))) : null,
        el('p', { class: 'hint' }, `${Object.keys(seen).length} of ${controls.length} understood · ${status.raw.length} MIDI messages received`),
      ];
    }
    default: {
      const report = buildReport();
      return [
        el('p', {}, 'Thank you! Download the report and share it with the developers (attach it to an issue), or copy it.'),
        el('ul', { class: 'check-list' }, report.summary.map(([ok, text]) => el('li', { class: ok ? 'ok' : 'wrong' }, text))),
        el('div', { class: 'answers' },
          el('button', { class: 'primary', id: 'check-download', onclick: () => download(report) }, 'Download report'),
          el('button', { id: 'check-copy', onclick: () => navigator.clipboard?.writeText(JSON.stringify(report.data, null, 2)).then(() => setStatus('Report copied', 'ok')) }, 'Copy')),
      ];
    }
  }
}

// The report: what was asked and answered, what the device reported, and the raw MIDI it sent
export function buildReport() {
  const { status, answers } = state.check;
  const device = state.layout.devices[state.check.index];
  const controls = deviceControls(device);
  const [first, second] = status.pressed;
  const padsOk = !!first && !!second && first[0] === 0 && first[1] === 0 && second[0] === status.width - 1 && second[1] === status.height - 1;
  const missing = controls.filter((control) => !status.controls[control.name]).map((control) => control.name);
  const summary = [
    [answers.corners?.answer === 'yes', `Corners: ${answers.corners?.answer || 'not answered'}`],
    [padsOk, `Pads: ${first ? `first press x ${first[0]}, y ${first[1]}` : 'none'}${second ? `, second x ${second[0]}, y ${second[1]}` : ''}`],
    [answers.colors?.answer === 'yes', `Colors: ${answers.colors?.answer || 'not answered'}`],
    [!missing.length, missing.length ? `Controls not understood: ${missing.join(', ')}` : 'Every control understood'],
  ];
  const data = {
    format: 'pyxelwidgets.device-check', version: 1,
    device: { type: device.type, driver: status.type, model: status.model, options: device.options || {}, ports: status.ports, size: [status.width, status.height] },
    system: status.system,
    corners: answers.corners || null,
    pads: { pressed: status.pressed, expected: [[0, 0], [status.width - 1, status.height - 1]], ok: padsOk },
    colors: { ...(answers.colors || {}), rows: COLORS },
    controls: { understood: status.controls, missing },
    // [seconds since the check started, bytes]
    midi: status.raw,
  };
  return { data, summary };
}

function download(report) {
  downloadText(`device-check-${report.data.device.type.replace(/\W+/g, '-')}.json`, JSON.stringify(report.data, null, 2) + '\n');
}

export function renderCheck() {
  const check = state.check;
  let box = $('check');
  if (!check) return box?.remove();
  if (!box) {
    box = el('div', { id: 'check', class: 'start-window check-window', role: 'dialog', 'aria-label': 'Device check' });
    document.body.append(box);
  }
  const device = state.layout.devices[check.index];
  const status = check.status;
  const last = check.step === STEPS.length - 1;
  fill(box,
    el('div', { class: 'start-head' }, el('h3', {}, `Check ${status.model || deviceInfo(device)?.model || device.type}`),
      el('button', { class: 'link', id: 'check-close', title: 'Stop checking', onclick: closeCheck }, '✕')),
    el('ol', { class: 'check-steps' }, STEPS.slice(1).map((step, i) => el('li', { class: i + 1 === check.step ? 'current' : i + 1 < check.step ? 'done' : '' }, step.key))),
    el('section', { id: `check-${STEPS[check.step].key}` }, body(status, device)),
    el('div', { class: 'buttons' },
      check.step > 0 ? el('button', { id: 'check-back', onclick: () => go(check.step - 1) }, 'Back') : null,
      last ? el('button', { class: 'primary', id: 'check-done', onclick: closeCheck }, 'Done')
        : el('button', { class: 'primary', id: 'check-next', onclick: () => go(check.step + 1) }, check.step === 0 ? 'Start' : 'Next')));
}
