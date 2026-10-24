// Snippets: ready-made pieces with their links and messages

import { state, $, el, api, thumb } from './core.js';
import { prefs, savePrefs } from './prefs.js';
import { widgetAt, absolute, topSelected, pathsOf } from './model.js';
import { outputsOf, uniqueOutputName } from './mappings.js';
import { change, setStatus } from './history.js';
import { targetGroup, clearGhost, placeClip } from './editing.js';
import { ask } from './files.js';

// Adds a snippet (widgets with their links, messages and outputs) into ``into`` with its bottom-left
// at ``at`` (absolute; default the group's corner). Its messages go to an output of the same type
// when the layout has one, else its output is added.
export function insertSnippet(snippet, into = targetGroup(), at = null) {
  let dropped = 0;
  const [width, height] = into ? [widgetAt(into).width, widgetAt(into).height] : [state.layout.surface.width, state.layout.surface.height];
  change((layout) => {
    const outputs = new Map();
    for (const output of snippet.outputs || []) {
      const same = outputsOf(layout).find((other) => other.type === output.type);
      if (same) {
        outputs.set(output.name, same.name);
        continue;
      }
      const name = uniqueOutputName(output.name);
      layout.outputs = [...outputsOf(layout), { ...JSON.parse(JSON.stringify(output)), name }];
      outputs.set(output.name, name);
    }
    const [ox, oy] = at || (into ? absolute(into) : [0, 0]);
    dropped = placeClip(layout, {
      widgets: snippet.widgets.map((widget) => ({ widget, at: [ox + (widget.x || 0), oy + (widget.y || 0)] })),
      links: snippet.links || [],
      mappings: (snippet.mappings || []).map((mapping) => ({ ...mapping, output: outputs.get(mapping.output) ?? mapping.output })),
    }, into);
  });
  const [w, h] = snippet.size;
  const notes = [];
  if (w > width || h > height) notes.push(`it is ${w}x${h}, larger than the ${width}x${height} it went into`);
  if (dropped) notes.push(`${dropped} link${dropped > 1 ? 's' : ''} left out`);
  setStatus(`Added ${snippet.title}${notes.length ? `: ${notes.join('; ')}` : ''}`, notes.length ? '' : 'ok');
}

// Widgets or Snippets in the palette section; remembered in this browser
export function showPaletteTab(tab) {
  prefs.paletteTab = tab;
  savePrefs();
  $('tab-widgets').classList.toggle('active', tab === 'widgets');
  $('tab-snippets').classList.toggle('active', tab === 'snippets');
  $('palette').hidden = tab !== 'widgets';
  $('snippet-pane').hidden = tab !== 'snippets';
}

export async function loadSnippets() {
  const reply = await api('GET', '/api/snippets');
  state.snippets = reply.snippets || [];
  renderSnippets();
}

function snippetSize(entry) {
  return `${entry.size[0]}x${entry.size[1]}`;
}

export function renderSnippets() {
  const list = state.snippets || [];
  const sizes = [...new Set(list.map(snippetSize))].sort((a, b) => {
    const [aw, ah] = a.split('x').map(Number), [bw, bh] = b.split('x').map(Number);
    return bw * bh - aw * ah || bw - aw;
  });
  const chosen = sizes.includes(prefs.snippetSize) ? prefs.snippetSize : '';
  const filter = $('snippet-size');
  filter.replaceChildren(el('option', { value: '' }, 'All sizes'),
    ...sizes.map((size) => el('option', { value: size, selected: size === chosen }, size)));
  filter.value = chosen;
  const shown = list.filter((entry) => !chosen || snippetSize(entry) === chosen);
  const categories = new Map();
  for (const entry of shown) {
    if (!categories.has(entry.category)) categories.set(entry.category, []);
    categories.get(entry.category).push(entry);
  }
  $('snippets').replaceChildren(...[...categories].flatMap(([category, entries]) => [
    el('h4', {}, category),
    ...entries.map((entry) => el('button', {
      class: 'snippet', dataset: { snippet: entry.id }, draggable: 'true',
      title: `${entry.title} (${snippetSize(entry)}): ${entry.doc}\nClick to add, or drag onto the grid.`,
      onclick: () => insertSnippet(entry.snippet),
      ondragstart: (event) => {
        state.dragSnippet = entry.snippet;
        document.body.classList.add('dragging');
        event.dataTransfer.setData('text/plain', `snippet:${entry.id}`);
        event.dataTransfer.effectAllowed = 'copy';
      },
      ondragend: () => { state.dragSnippet = null; document.body.classList.remove('dragging'); clearGhost(); },
    },
      thumb(entry.preview, 48) || el('span', { class: 'glyph' }, snippetSize(entry)),
      el('span', { class: 'label' }, entry.title),
      el('span', { class: 'size' }, snippetSize(entry)),
      entry.builtin ? null : el('span', {
        class: 'delete', role: 'button', title: 'Delete this snippet',
        onclick: (event) => { event.stopPropagation(); deleteSnippet(entry); },
      }, '×'))),
  ]));
  if (!shown.length) $('snippets').append(el('p', { class: 'hint' }, 'No snippets of this size yet: select widgets and save them as one.'));
}

// The selected widgets, their links and messages (and the outputs those use) as a snippet
function selectionSnippet(title, doc, category) {
  const widgets = topSelected().map(widgetAt);
  const places = widgets.map((widget) => absolute(pathsOf([widget])[0]));
  const x0 = Math.min(...places.map(([x]) => x)), y0 = Math.min(...places.map(([, y]) => y));
  const x1 = Math.max(...widgets.map((widget, i) => places[i][0] + widget.width));
  const y1 = Math.max(...widgets.map((widget, i) => places[i][1] + widget.height));
  const names = new Set();
  const collect = (widget) => {
    names.add(widget.name);
    (widget.widgets || []).forEach(collect);
  };
  widgets.forEach(collect);
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const mappings = (state.layout.mappings || []).filter((mapping) => names.has(mapping.widget));
  const used = new Set(mappings.map((mapping) => mapping.output));
  const snippet = {
    format: 'pyxelwidgets.snippet', title, doc, category, size: [x1 - x0, y1 - y0],
    widgets: widgets.map((widget, i) => ({ ...copy(widget), x: places[i][0] - x0, y: places[i][1] - y0 })),
  };
  // Links between the widgets, and to the transport
  const links = (state.layout.links || []).filter((link) => names.has(link.widget) && (link.target === undefined || link.target === 'key' || names.has(link.target)));
  if (links.length) snippet.links = copy(links);
  if (mappings.length) {
    snippet.mappings = copy(mappings);
    snippet.outputs = copy(outputsOf().filter((output) => used.has(output.name)));
  }
  return snippet;
}

export async function saveSnippet() {
  if (state.selection?.kind !== 'widget') return setStatus('Select the widgets to keep as a snippet first', 'error');
  const first = widgetAt(topSelected()[0]);
  const answer = await ask({
    title: 'Save as a snippet',
    text: 'The selected widgets with their links and messages, to add to any layout from the Snippets section.',
    fields: [
      { name: 'title', label: 'name', value: topSelected().length === 1 ? first.name : '', placeholder: 'My drum kit' },
      { name: 'doc', label: 'description', placeholder: 'What it does' },
      { name: 'category', label: 'category', value: 'My snippets' },
    ],
    ok: 'Save',
  });
  if (!answer) return;
  if (!answer.title) return setStatus('A snippet needs a name', 'error');
  const reply = await api('POST', '/api/snippets', { snippet: selectionSnippet(answer.title, answer.doc, answer.category || 'My snippets') });
  if (!reply.ok) return setStatus(reply.error, 'error');
  state.snippets = reply.snippets;
  renderSnippets();
  setStatus(`Saved the snippet ${answer.title}`, 'ok');
}

async function deleteSnippet(entry) {
  if (!(await ask({ title: `Delete the snippet ${entry.title}?`, text: 'It goes from every layout\'s Snippets section (layouts using it keep their widgets).', ok: 'Delete' }))) return;
  const reply = await api('POST', '/api/snippets', { delete: entry.id });
  if (!reply.ok) return setStatus(reply.error, 'error');
  state.snippets = reply.snippets;
  renderSnippets();
}
