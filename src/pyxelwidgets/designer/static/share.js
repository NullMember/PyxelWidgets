// Share: opening the designer to other computers on the network (e.g. to edit a
// phone's or a Pi's layouts from a bigger screen). The addresses carry a key.

import { state, $, el, fill, api } from './core.js';
import { newDialog } from './files.js';
import { setStatus } from './history.js';

export async function loadSharing() {
  const reply = await api('GET', '/api/share');
  if (reply.ok) state.sharing = reply;
  renderShareButton();
}

function renderShareButton() {
  const button = $('share');
  const shared = state.sharing?.shared;
  button.classList.toggle('on', !!shared);
  button.textContent = shared ? 'Shared' : 'Share';
  button.title = shared ? 'Other computers on the network can open this designer' : 'Open this designer to other computers on the network';
}

export function showShare() {
  const dialog = newDialog();
  dialog.id = 'share-dialog';
  const render = () => {
    const sharing = state.sharing || {};
    const toggle = async (event) => {
      event.target.disabled = true;
      const reply = await api('POST', '/api/share', { shared: !sharing.shared });
      if (reply.ok) state.sharing = { ...reply, local: sharing.local };
      else setStatus(reply.error || 'Sharing failed', 'error');
      renderShareButton();
      render();
    };
    fill(dialog,
      el('h3', {}, 'Share on the network'),
      el('p', { class: 'hint' }, sharing.shared
        ? 'Other computers and phones on this network can open the designer at:'
        : 'Only this computer can open the designer. Sharing lets you edit from another computer or a tablet on the same network.'),
      sharing.shared ? el('div', { class: 'share-urls' }, (sharing.urls || []).map((url) =>
        el('div', { class: 'share-url' },
          el('code', { id: 'share-url' }, url),
          el('button', { onclick: () => navigator.clipboard?.writeText(url).then(() => setStatus('Address copied', 'ok')) }, 'Copy')))) : null,
      el('p', { class: 'hint warning' }, 'Anyone who has the address (it carries a key) can edit layouts and open and save files on this computer. Share only on networks you trust.'),
      sharing.fixed ? el('p', { class: 'hint' }, 'It was started to listen on the network (--host), so it stays shared until it stops.') : null,
      sharing.local === false ? el('p', { class: 'hint' }, 'You are using it from another computer: only the computer running it can change this.') : null,
      el('div', { class: 'buttons' },
        el('button', { onclick: () => dialog.close() }, 'Close'),
        sharing.fixed || sharing.local === false ? null
          : el('button', { class: sharing.shared ? '' : 'primary', id: 'share-toggle', onclick: toggle }, sharing.shared ? 'Stop sharing' : 'Share')));
  };
  render();
  dialog.showModal();
  loadSharing().then(() => dialog.open && render());
}
