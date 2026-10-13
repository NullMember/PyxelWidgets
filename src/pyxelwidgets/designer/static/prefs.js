// View preferences kept in this browser: folded sections, panel sizes, the drawer, per-file layer view sets

import { state, api } from './core.js';
import { render } from './board.js';

// Folded sections, panel sizes, the drawer; per layout file: collapsed, hidden and locked layers
export const prefs = (() => {
  try {
    return JSON.parse(localStorage.getItem('pyxelwidgets.designer') || '{}');
  } catch {
    return {};
  }
})();

export function savePrefs() {
  try {
    localStorage.setItem('pyxelwidgets.designer', JSON.stringify(prefs));
  } catch {
    // Private windows: preferences last for this page only
  }
}

function viewKey() {
  return state.file || '(unsaved)';
}

// Widget names in a per-file view set: 'collapsed', 'hidden' (in the designer only) or 'locked'
export function viewSet(kind) {
  return new Set(prefs.views?.[viewKey()]?.[kind] || []);
}

function setViewSet(kind, names) {
  prefs.views ||= {};
  prefs.views[viewKey()] ||= {};
  prefs.views[viewKey()][kind] = [...names];
  savePrefs();
  if (kind === 'hidden') sendHidden();
}

export function toggleView(kind, name) {
  const names = viewSet(kind);
  if (names.has(name)) names.delete(name);
  else names.add(name);
  setViewSet(kind, names);
  render();
}

// Keep view sets following renamed widgets
export function renameInViews(from, to) {
  for (const kind of ['collapsed', 'hidden', 'locked']) {
    const names = viewSet(kind);
    if (names.delete(from)) {
      names.add(to);
      setViewSet(kind, names);
    }
  }
}

// Widgets hidden in the designer only are hidden in the preview too
export function sendHidden() {
  api('POST', '/api/view', { hidden: [...viewSet('hidden')] });
}
