// Bluetooth MIDI devices: scan, connect, disconnect (pyxelwidgets.devices.bluetooth). Once
// connected, a device's ports are listed like any other MIDI port; remembered devices
// connect again when the designer starts and when they come back in range.

import { $, el, fill, api } from './core.js';
import { newDialog } from './files.js';
import { setStatus } from './history.js';

export async function showBluetooth() {
  const dialog = newDialog();
  dialog.id = 'bluetooth-dialog';
  let status = await api('GET', '/api/bluetooth');
  let found = null;
  let busy = null;
  let error = null;

  const act = async (label, body) => {
    busy = label;
    error = null;
    render();
    const reply = await api('POST', '/api/bluetooth', body);
    busy = null;
    if (!reply.ok) error = reply.error;
    status = reply;
    if (reply.found) found = reply.found;
    if (reply.ok && body.action === 'connect') setStatus(`Connected ${reply.name}: its ports are listed with the MIDI ports`, 'ok');
    if (reply.ok && body.action === 'pair') {
      setStatus('Paired', 'ok');
      if (found) found = found.map((device) => device.address === body.address ? { ...device, paired: true } : device);
    }
    render();
  };

  // Android says whether a device is paired: one that encrypts MIDI stays silent until it is
  const pair = (device) => device.paired === false
    ? el('button', { disabled: !!busy, title: 'For devices that ask for pairing: accept the request on this device',
      onclick: () => act(`Pairing with ${device.name}: accept the request on this device`, { action: 'pair', address: device.address }) }, 'Pair')
    : null;
  const row = (device, ...buttons) => el('div', { class: 'bluetooth-device' },
    el('div', {}, el('b', {}, device.name), el('small', {}, ` ${device.address}${device.rssi !== undefined ? ` · signal ${device.rssi} dBm` : ''}${device.paired ? ' · paired' : ''}`),
      device.error ? el('div', { class: 'hint warning' }, device.error) : null),
    el('div', { class: 'bluetooth-buttons' }, buttons));

  function render() {
    const connected = new Set((status.connected || []).map((device) => device.address));
    const remembered = new Set((status.remembered || []).map((device) => device.address));
    fill(dialog,
      el('h3', {}, 'Bluetooth MIDI devices'),
      !status.available || status.problem && !busy ? el('p', { class: 'hint' }, status.problem) : null,
      error ? el('p', { class: 'hint warning', id: 'bluetooth-error' }, error) : null,
      (status.connected || []).length ? [el('h4', {}, 'Connected'), status.connected.map((device) =>
        row(device, pair(device), el('button', { disabled: !!busy, onclick: () => act('Disconnecting', { action: 'disconnect', address: device.address }) }, 'Disconnect')))] : null,
      (status.remembered || []).length ? [el('h4', {}, 'Connected again when found'), status.remembered.map((device) =>
        row(device,
          el('button', { disabled: !!busy, onclick: () => act(`Connecting ${device.name}`, { action: 'connect', address: device.address }) }, 'Connect'),
          el('button', { disabled: !!busy, onclick: () => act('Forgetting', { action: 'disconnect', address: device.address }) }, 'Forget')))] : null,
      found ? [el('h4', {}, 'Found'), found.filter((device) => !connected.has(device.address) && !remembered.has(device.address)).length
        ? found.filter((device) => !connected.has(device.address) && !remembered.has(device.address)).map((device) =>
          row(device, pair(device), el('button', { class: 'primary', disabled: !!busy, onclick: () => act(`Connecting ${device.name}`, { action: 'connect', address: device.address }) }, 'Connect')))
        : el('p', { class: 'hint' }, 'No other devices advertising MIDI. Is it on, and not connected to something else?')] : null,
      busy ? el('p', { class: 'hint', id: 'bluetooth-busy' }, `${busy}…`) : null,
      [...(found || []), ...(status.connected || [])].some((device) => device.paired === false)
        ? el('p', { class: 'hint' }, 'A device that asks for pairing stays silent until it\'s paired: press Pair and accept the request.') : null,
      el('div', { class: 'buttons' },
        el('button', { onclick: () => dialog.close() }, 'Close'),
        status.available ? el('button', { class: 'primary', id: 'bluetooth-scan', disabled: !!busy, onclick: () => act('Scanning', { action: 'scan', seconds: 4 }) }, found ? 'Scan again' : 'Scan') : null));
  }

  render();
  dialog.showModal();
}
