// Links (layout.links): widgets changing widgets, and their editors

import { state, $, el } from './core.js';
import { allWidgets } from './model.js';
import { INTEGER_SOURCES, sourceNames } from './mappings.js';
import { change } from './history.js';
import { optionControl } from './properties.js';

export function setLinks(layout, links) {
  if (links.length) layout.links = links;
  else delete layout.links;
}

export function widgetNamed(name) {
  return allWidgets().find(({ widget }) => widget.name === name)?.widget;
}

// The options of a widget a link can change: position, size and its options
export function linkOptions(widget) {
  return state.catalog.widgets[widget?.type]?.linkable || [];
}

// Set always; Add to numbers and choices; Toggle on/off options and choices
function linkChanges(kind) {
  return Object.entries(state.catalog.link.changes).filter(([, kinds]) => !kinds || kinds.includes(kind)).map(([name]) => name);
}

// What an option is in the layout (or by default)
function layoutValue(widget, option) {
  if (option.name === 'x' || option.name === 'y') return widget[option.name] || 0;
  if (option.name === 'width' || option.name === 'height') return widget[option.name] ?? 1;
  return widget.options && option.name in widget.options ? widget.options[option.name] : option.default;
}

// Event values a link to an option of `kind` can take
function linkSources(on, kind, change) {
  if (change !== 'Add' && !state.catalog.link.sources.includes(kind)) return [];
  return sourceNames(on).filter((name) => {
    if (name === 'text') return kind === 'str';
    // Colors cover a range: 0.0-1.0 values only
    if (kind === 'color' && change !== 'Add') return !INTEGER_SOURCES.has(name);
    return true;
  });
}

// A first change and value that suit the event and the option: a value from the event where one fits
export function defaultLinkValue(link) {
  const target = widgetNamed(link.target);
  const option = linkOptions(target).find((candidate) => candidate.name === link.option);
  for (const key of ['value', 'min', 'max', 'change']) delete link[key];
  if (!option) return;
  const sources = sourceNames(link.on);
  const level = ['value', 'state', 'velocity', 'pressure', 'active'].find((name) => sources.includes(name));
  switch (option.kind) {
    case 'bool': {
      // Follows a switch or a cell; presses toggle it
      const onOff = ['value', 'state'].find((name) => sources.includes(name));
      if (onOff) link.value = { source: onOff };
      else link.change = 'Toggle';
      return;
    }
    case 'enum':
      link.change = 'Toggle';
      return;
    case 'int': {
      // One per pad (e.g. a page per ButtonGroup cell), else one more each time
      const source = widgetNamed(link.widget);
      if (sources.includes('cell') && source && source.width * source.height > 1) link.value = { source: 'cell' };
      else {
        link.change = 'Add';
        link.value = 1;
      }
      return;
    }
    case 'float':
    case 'color':
      link.value = level ? { source: level } : layoutValue(target, option);
      return;
    case 'str':
      if (level) Object.assign(link, { value: { source: level }, min: 0, max: 100 });
      else link.value = layoutValue(target, option) ?? '';
      return;
    default:
      link.value = layoutValue(target, option);
  }
}

// The value a link sets or adds: a constant, or an event value with its range (or offset)
// "if <event value> <op> <constant> then <value> else <value>"
function conditionEditor(link, option, id, edit, change) {
  const condition = link.value;
  const sources = sourceNames(link.on).filter((name) => name !== 'text');
  const source = condition.if?.source;
  const choose = (key) => {
    const commit = (value) => edit(() => { link.value[key] = value; });
    if (change === 'Add' || option.action) {
      return el('input', {
        type: 'number', class: 'small', id: id(key), value: condition[key] ?? 0, step: option.kind === 'float' || option.action ? 'any' : 1,
        onchange: (e) => commit(Number(e.target.value)),
      });
    }
    return optionControl(option, condition[key], (value) => { if (value !== undefined) commit(value); }, id(key))[0];
  };
  return [
    el('div', { class: 'cond-row' },
      el('span', { class: 'word' }, 'if'),
      el('select', {
        id: id('if'), title: 'The event value to compare',
        onchange: (e) => edit(() => { link.value.if = { source: e.target.value }; }),
      }, sources.map((name) => el('option', { value: name, selected: name === source }, name)),
      source && !sources.includes(source) ? el('option', { value: source, selected: true }, `${source} (not available)`) : null),
      el('select', {
        id: id('op'), class: 'op',
        onchange: (e) => edit(() => { link.value.op = e.target.value; }),
      }, state.catalog.link.operators.map((op) => el('option', { value: op, selected: op === (condition.op || '==') }, op))),
      el('input', {
        type: 'text', class: 'small', id: id('to'), value: condition.to ?? 0,
        title: INTEGER_SOURCES.has(source) ? 'A whole number (cell 0 is the bottom-left pad)' : '0.0-1.0 values are compared as they are',
        onchange: (e) => edit(() => {
          const text = e.target.value.trim();
          link.value.to = /^-?\d*\.?\d+$/.test(text) ? Number(text) : text;
        }),
      })),
    el('div', { class: 'cond-row' }, el('span', { class: 'word' }, 'then'), choose('then')),
    el('div', { class: 'cond-row' }, el('span', { class: 'word' }, 'else'), choose('else')),
  ];
}

// "by <event value> pick from <values...>": the value's index (whole numbers) or place (0.0-1.0) in the list
function choiceEditor(link, option, id, edit, change) {
  const choice = link.value;
  const sources = sourceNames(link.on).filter((name) => name !== 'text');
  const by = choice.by?.source ?? choice.by;
  const entry = (index) => {
    const commit = (value) => edit(() => { link.value.choose[index] = value; });
    if (change === 'Add' || option.action) {
      return el('input', {
        type: 'number', class: 'small', id: id(`choose-${index}`), value: choice.choose[index] ?? 0, step: option.kind === 'float' || option.action ? 'any' : 1,
        onchange: (e) => commit(Number(e.target.value)),
      });
    }
    return optionControl(option, choice.choose[index], (value) => { if (value !== undefined) commit(value); }, id(`choose-${index}`))[0];
  };
  return [
    el('div', { class: 'cond-row' },
      el('span', { class: 'word' }, 'by'),
      el('select', {
        id: id('by'), title: 'The event value picking one: a whole number (x, cell...) is the place in the list from 0, a 0.0-1.0 value spreads over it',
        onchange: (e) => edit(() => { link.value.by = e.target.value; }),
      }, sources.map((name) => el('option', { value: name, selected: name === by }, name)),
      by && !sources.includes(by) ? el('option', { value: by, selected: true }, `${by} (not available)`) : null)),
    ...choice.choose.map((_, index) => el('div', { class: 'cond-row' },
      el('span', { class: 'word' }, String(index)), entry(index),
      choice.choose.length > 1 ? el('button', {
        class: 'small', title: 'Remove this one', onclick: () => edit(() => { link.value.choose.splice(index, 1); }),
      }, '−') : null)),
    el('div', { class: 'cond-row' }, el('span', { class: 'word' }), el('button', {
      class: 'small', id: id('choose-add'), title: 'Add a value to the list',
      onclick: () => edit(() => { link.value.choose.push(JSON.parse(JSON.stringify(choice.choose[choice.choose.length - 1]))); }),
    }, '+ value')),
  ];
}

// A link's value in words: "cell == 3 ? true : false", "{value}", "1"
export function describeValue(link) {
  const value = link.value;
  if (value && typeof value === 'object' && 'if' in value) return `${value.if.source} ${value.op || '=='} ${value.to} ? ${value.then} : ${value.else}`;
  if (value && typeof value === 'object' && 'choose' in value) return `[${value.choose.join(', ')}] by ${value.by?.source ?? value.by}`;
  if (value && typeof value === 'object') return `{${value.source}}`;
  return value === undefined ? '' : String(value);
}

function linkValueEditor(link, option, id, edit) {
  const change = link.change || 'Set';
  const sources = linkSources(link.on, option.kind, change);
  const isCondition = !!(link.value && typeof link.value === 'object' && 'if' in link.value);
  const isChoice = !!(link.value && typeof link.value === 'object' && 'choose' in link.value);
  const isSource = !isCondition && !isChoice && link.value && typeof link.value === 'object' && !Array.isArray(link.value);
  const constant = change === 'Add' ? 1 : option.action ? 0 : layoutValue(widgetNamed(link.target), option);
  const mode = el('select', {
    id: id('value'), title: 'A constant, a value from the event, a condition choosing between two values, or a list an event value picks from',
    onchange: (e) => edit(() => {
      delete link.min;
      delete link.max;
      if (e.target.value === '\u0000if') {
        // Compares an event value (a whole number one first: cell, x...) with a constant
        const all = sourceNames(link.on).filter((name) => name !== 'text');
        const first = all.includes('cell') ? 'cell' : all.find((name) => INTEGER_SOURCES.has(name)) || all[0];
        const onOff = option.kind === 'bool' && change === 'Set';
        link.value = { if: { source: first }, op: '==', to: 0, then: onOff ? true : constant, else: onOff ? false : (option.action ? 0 : option.default ?? constant) };
        return;
      }
      if (e.target.value === '\u0000choose') {
        // Picked by a whole number first (x: a row of pads), starting with two values
        const all = sourceNames(link.on).filter((name) => name !== 'text');
        const by = all.includes('x') ? 'x' : all.find((name) => INTEGER_SOURCES.has(name)) || all[0];
        const enumChoices = option.kind === 'enum' ? option.choices.slice(0, 2) : null;
        link.value = { choose: enumChoices || (option.kind === 'bool' ? [false, true] : [constant, constant]), by };
        return;
      }
      link.value = e.target.value === '' ? constant : { source: e.target.value };
      if (change === 'Set' && option.kind === 'str' && !INTEGER_SOURCES.has(e.target.value)) Object.assign(link, { min: 0, max: 100 });
    }),
  },
  el('option', { value: '', selected: !isSource && !isCondition && !isChoice }, 'constant'),
  el('option', { value: '\u0000if', selected: isCondition }, 'condition…'),
  el('option', { value: '\u0000choose', selected: isChoice }, 'list…'),
  sources.map((name) => el('option', { value: name, selected: isSource && link.value.source === name }, name)),
  isSource && !sources.includes(link.value.source) ? el('option', { value: link.value.source, selected: true }, `${link.value.source} (not available)`) : null);
  const number = (key, placeholder, attrs = {}) => el('input', {
    type: 'number', class: 'small', value: link[key] ?? '', placeholder, title: key, step: option.kind === 'float' ? 'any' : 1, ...attrs,
    onchange: (e) => edit(() => {
      if (e.target.value === '') delete link[key];
      else link[key] = Number(e.target.value);
    }),
  });
  let detail = null;
  if (isCondition) {
    return el('div', { class: 'control value condition' }, mode, conditionEditor(link, option, id, edit, change));
  }
  if (isChoice) {
    return el('div', { class: 'control value condition' }, mode, choiceEditor(link, option, id, edit, change));
  }
  if (!isSource) {
    if (change === 'Add') {
      detail = el('input', {
        type: 'number', class: 'small', value: link.value ?? 1, step: option.kind === 'float' ? 'any' : 1,
        title: option.kind === 'enum' ? 'Choices to move by' : 'Added each time',
        onchange: (e) => edit(() => { link.value = option.kind === 'float' ? Number(e.target.value) : parseInt(e.target.value || '0', 10); }),
      });
    } else {
      [detail] = optionControl(option, link.value, (value) => edit(() => { link.value = Number.isNaN(value) ? constant : value ?? constant; }), id('constant'));
    }
  } else if (INTEGER_SOURCES.has(link.value.source)) {
    detail = el('input', {
      type: 'number', class: 'small', value: link.value.offset ?? '', placeholder: '+0', step: 1, title: 'offset',
      onchange: (e) => edit(() => {
        if (e.target.value === '') delete link.value.offset;
        else link.value.offset = parseInt(e.target.value, 10);
      }),
    });
  } else if (change === 'Set' && link.value.source !== 'text') {
    // The range 0.0-1.0 covers
    const title = 'The range 0.0-1.0 covers';
    if (option.kind === 'color') {
      const bound = (key, fallback) => optionControl({ kind: 'color' }, link[key] ?? fallback, (value) => edit(() => { link[key] = value; }), id(key))[0];
      detail = el('span', { class: 'range', title }, bound('min', '#000000'), '–', bound('max', layoutValue(widgetNamed(link.target), option)));
    } else if (option.kind === 'enum') {
      const bound = (key, fallback) => el('select', {
        id: id(key), title: key,
        onchange: (e) => edit(() => { link[key] = e.target.value; }),
      }, option.choices.map((choice) => el('option', { value: choice, selected: choice === (link[key] ?? fallback) }, choice)));
      detail = el('span', { class: 'range', title }, bound('min', option.choices[0]), '–', bound('max', option.choices[option.choices.length - 1]));
    } else if (option.kind !== 'bool') {
      detail = el('span', { class: 'range', title }, number('min', '0'), '–', number('max', option.kind === 'int' && !option.action ? '127' : '1'));
    }
  }
  return el('div', { class: 'control value' }, mode, detail);
}

// Actions a link can call on a target: a widget's methods, or the transport's (target '')
function linkActions(target) {
  if (!target) return Object.fromEntries(Object.entries(state.catalog.link.actions).filter(([name]) => name !== 'debug'));
  return state.catalog.widgets[target.type]?.actions || {};
}

// An action's first value: the pad's cell or the event's step where there is one; a tempo from a fader
function defaultActionValue(link) {
  for (const key of ['value', 'min', 'max', 'change']) delete link[key];
  if (linkActions(widgetNamed(link.target))[link.action] === null) return;
  const sources = sourceNames(link.on);
  if (link.action === 'transport.tempo') {
    // A TapTempo's tempo as it is
    if (sources.includes('bpm')) link.value = { source: 'bpm' };
    else if (sources.includes('value')) Object.assign(link, { value: { source: 'value' }, min: 60, max: 180 });
    else link.value = 120;
    return;
  }
  if (link.action === 'transport.tempo_add') {
    link.value = 1;
    return;
  }
  // A value (0-1) for actions taking one, e.g. a fader setting a step's velocity
  if (linkActions(widgetNamed(link.target))[link.action] === 'float' && sources.includes('value')) {
    link.value = { source: 'value' };
    return;
  }
  const source = ['step', 'row', 'cell', 'note'].find((name) => sources.includes(name));
  link.value = source ? { source } : 0;
}

// A link writing to the debug log (the event log in the designer, printed when running)
function debugCard(widget, link, index, events) {
  const id = (name) => `link-${index}-${name}`;
  const edit = (mutate) => change(() => mutate(link));
  const sources = sourceNames(link.on);
  return el('div', { class: 'mapping link' },
    el('div', { class: 'mapping-head' },
      el('select', {
        id: id('on'), title: 'The event of this widget that writes',
        onchange: (e) => edit(() => { link.on = e.target.value; }),
      }, events.map((name) => el('option', { value: name, selected: name === link.on }, name))),
      el('span', { class: 'arrow' }, '→'),
      el('select', {
        id: id('target'), title: 'Where it goes',
        onchange: (e) => edit(() => {
          delete link.action;
          delete link.value;
          if (!e.target.value) {
            link.action = 'transport.toggle';
          } else {
            link.target = e.target.value;
            link.option = 'visible';
            defaultLinkValue(link);
          }
        }),
      },
      el('option', { value: '' }, 'Transport'),
      el('option', { value: '\u0000debug', selected: true }, 'Debug log'),
      allWidgets().map(({ widget: candidate }) => el('option', { value: candidate.name }, candidate === widget ? `${candidate.name} (itself)` : candidate.name))),
      el('button', {
        class: 'link remove', title: 'Remove this link',
        onclick: () => change((layout) => setLinks(layout, layout.links.filter((_, i) => i !== index))),
      }, '×')),
    el('div', { class: 'fields' },
      el('label', { for: id('value') }, 'text'),
      el('div', { class: 'control' }, el('input', {
        type: 'text', id: id('value'), value: link.value ?? '', placeholder: `${link.on} {all}`,
        title: `Placeholders take the event's values: ${sources.map((name) => `{${name}}`).join(' ')}; {all} is every value. Empty: the event and every value.`,
        onchange: (e) => edit(() => { if (e.target.value.trim()) link.value = e.target.value; else delete link.value; }),
      })),
      el('p', { class: 'hint', style: 'grid-column: 1 / -1' },
        `Shows in Events (filter: Only debug); printed when the layout runs. Values: ${sources.map((name) => `{${name}}`).join(' ')} {all}`)));
}

export function linkCard(widget, link, index) {
  const events = state.catalog.widgets[widget.type]?.events || [];
  if (link.action === 'debug') return debugCard(widget, link, index, events);
  const transport = !link.target;
  const target = transport ? null : widgetNamed(link.target);
  const options = transport ? [] : linkOptions(target);
  const actions = linkActions(target);
  const isAction = link.action !== undefined;
  const option = isAction
    ? (actions[link.action] ? { name: link.action, kind: actions[link.action], action: true } : null)
    : options.find((candidate) => candidate.name === link.option);
  const changeName = link.change || 'Set';
  const id = (name) => `link-${index}-${name}`;
  const edit = (mutate) => change(() => mutate(link));
  // Numbers added to are kept within limits
  const limits = !isAction && changeName === 'Add' && option && (option.kind === 'int' || option.kind === 'float');
  const actionLabel = (name) => name.replace(/^transport\./, '');
  const valueFields = () => {
    if (isAction) {
      if (!(link.action in actions)) return el('p', { class: 'hint' }, `${link.target || 'The transport'} has no action ${link.action}`);
      const label = { play: 'step', 'transport.tempo': 'bpm', 'transport.tempo_add': 'by' }[link.action] || 'with';
      return option ? [el('label', { for: id('value') }, label), linkValueEditor(link, option, id, edit)] : null;
    }
    if (!option) return el('p', { class: 'hint' }, `${link.target} has no option ${link.option}`);
    return [
      el('label', { for: id('change') }, 'change'),
      el('div', { class: 'control' }, el('select', {
        id: id('change'), title: 'Set it, add to it, or toggle it (on/off, next choice)',
        onchange: (e) => edit(() => {
          const next = e.target.value;
          for (const key of ['value', 'min', 'max', 'change']) delete link[key];
          if (next === 'Toggle') link.change = 'Toggle';
          else if (next === 'Add') Object.assign(link, { change: 'Add', value: 1 });
          else {
            defaultLinkValue(link);
            if (link.change) {
              // This option's default is another change: set a constant instead
              for (const key of ['value', 'min', 'max', 'change']) delete link[key];
              link.value = layoutValue(target, option);
            }
          }
        }),
      }, linkChanges(option.kind).map((name) => el('option', { value: name, selected: name === changeName }, name.toLowerCase())))),
      changeName !== 'Toggle' ? [el('label', { for: id('value') }, changeName === 'Add' ? 'by' : 'to'), linkValueEditor(link, option, id, edit)] : null,
      limits ? [
        el('label', { title: 'The lowest and highest it goes' }, 'limits'),
        el('div', { class: 'control value' }, el('span', { class: 'range' }, ...['min', 'max'].flatMap((key, i) => [i ? '–' : null, el('input', {
          type: 'number', class: 'small', id: id(key), value: link[key] ?? '', placeholder: 'none', title: key, step: option.kind === 'float' ? 'any' : 1,
          onchange: (e) => edit(() => {
            if (e.target.value === '') delete link[key];
            else link[key] = Number(e.target.value);
          }),
        })]))),
      ] : null,
    ];
  };
  return el('div', { class: 'mapping link' },
    el('div', { class: 'mapping-head' },
      el('select', {
        id: id('on'), title: 'The event of this widget that changes the option',
        onchange: (e) => edit(() => {
          link.on = e.target.value;
          const source = link.value?.source;
          if (source && !linkSources(link.on, option?.kind, changeName).includes(source)) {
            if (isAction) defaultActionValue(link);
            else defaultLinkValue(link);
          }
        }),
      }, events.map((name) => el('option', { value: name, selected: name === link.on }, name))),
      el('span', { class: 'arrow' }, '→'),
      el('select', {
        id: id('target'), title: 'The widget whose option changes, or the transport',
        onchange: (e) => edit(() => {
          for (const key of ['value', 'min', 'max', 'change']) delete link[key];
          if (!e.target.value || e.target.value === '\u0000debug') {
            // Transport actions and the debug log have no target
            delete link.target;
            delete link.option;
            link.action = e.target.value ? 'debug' : 'transport.toggle';
            return;
          }
          link.target = e.target.value;
          const next = widgetNamed(link.target);
          if (isAction && link.action in linkActions(next)) return defaultActionValue(link);
          delete link.action;
          if (!linkOptions(next).some((candidate) => candidate.name === link.option)) link.option = 'visible';
          defaultLinkValue(link);
        }),
      },
      el('option', { value: '', selected: transport }, 'Transport'),
      el('option', { value: '\u0000debug' }, 'Debug log'),
      allWidgets().map(({ widget: candidate }) => el('option', { value: candidate.name, selected: candidate.name === link.target },
        candidate === widget ? `${candidate.name} (itself)` : candidate.name))),
      el('button', {
        class: 'link remove', title: 'Remove this link',
        onclick: () => change((layout) => setLinks(layout, layout.links.filter((_, i) => i !== index))),
      }, '×')),
    el('div', { class: 'fields' },
      el('label', { for: id('option') }, isAction ? 'action' : 'option'),
      el('div', { class: 'control' }, el('select', {
        id: id('option'), title: 'An option to change, or an action to call',
        onchange: (e) => edit(() => {
          const [kind, name] = e.target.value.split(':');
          if (kind === 'action') {
            delete link.option;
            link.action = name;
            defaultActionValue(link);
          } else {
            delete link.action;
            link.option = name;
            defaultLinkValue(link);
          }
        }),
      },
      options.length ? el('optgroup', { label: 'Options' }, options.map((candidate) => el('option', {
        value: `option:${candidate.name}`, selected: !isAction && candidate.name === link.option,
      }, candidate.name.replace(/_/g, ' ')))) : null,
      Object.keys(actions).length ? el('optgroup', { label: 'Actions' }, Object.keys(actions).map((name) => el('option', {
        value: `action:${name}`, selected: isAction && name === link.action,
      }, actionLabel(name)))) : null)),
      valueFields()),
  );
}
