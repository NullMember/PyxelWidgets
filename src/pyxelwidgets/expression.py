"""
Expressions: small formulas in braces that options, links and messages
compute from other widgets' options and from event values::

    {roll.steps - roll.width}                 # options of the widget named roll
    {value * 8}                               # an event value (links, messages)
    {min(x, 3) + 1}
    {'on' if state else 'off'}
    Step {roll.column + 1} of {roll.steps}    # a text: each part filled in

``Expression`` is one formula (with or without its braces), ``Template`` a
text with formulas in it (``{{`` and ``}}`` are braces). Both take ``names``:
what names other than event values stand for (widgets by name, ``self``,
``transport``), and ``evaluate(values)`` with the event's values, which come
first. Event values are as the event has them: ``velocity``/``value`` 0.0-1.0,
``x``/``cell``/``step`` whole numbers.

Allowed: numbers, text in quotes, true/false, names, ``name.option`` (an
option or property, never a method or a name starting with ``_``; choices
read as their name, ``roll.follow == 'Page'``), ``+ - * / // % **``,
comparisons, ``and``/``or``/``not``, ``a if test else b`` and the
``FUNCTIONS``. Python's ``eval`` is not used: nothing else runs.

``skip`` is a result meaning "do nothing this time": a link with it changes
nothing (an action isn't called), a message with it isn't sent and an
option's formula leaves the option as it is::

    {note if pages.page == 3 else skip}       # only on page 4
    {velocity * 127 if velocity > 0 else skip}

A template with a part that is ``skip`` is ``skip`` as a whole.
"""

import ast
import enum
import math
import operator
import re

__all__ = ['Expression', 'Template', 'ExpressionError', 'FUNCTIONS', 'SKIP', 'parse', 'is_expression']

class ExpressionError(ValueError):
    """An expression that doesn't parse, or can't be computed (an unknown name, a division by zero...)."""

def _clamp(value, low, high):
    return min(max(value, low), high)

#: Functions expressions can call
FUNCTIONS = {'min': min, 'max': max, 'abs': abs, 'round': round, 'int': int, 'float': float, 'str': str, 'bool': bool,
             'floor': math.floor, 'ceil': math.ceil, 'clamp': _clamp}

class _Skip:
    """The ``skip`` result (``SKIP``): whatever computed it does nothing this time."""

    #: What message.py looks for (it imports nothing)
    skips = True

    def __repr__(self) -> str:
        return 'SKIP'

    def __reduce__(self):
        return 'SKIP'

#: The result meaning "do nothing this time" (``skip`` in expressions)
SKIP = _Skip()

_CONSTANTS = {'skip': SKIP, 'true': True, 'false': False, 'True': True, 'False': False, 'none': None, 'None': None, 'pi': math.pi}

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}
_COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
            ast.Gt: operator.gt, ast.GtE: operator.ge}
_ALLOWED = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.Attribute, ast.BinOp, ast.UnaryOp, ast.BoolOp,
            ast.And, ast.Or, ast.Compare, ast.IfExp, ast.Call, *_BINARY, *_UNARY, *_COMPARE)

# Results too big to make by accident ('x' * 10 ** 9)
_LONGEST = 10000

def _unbrace(text: str) -> str:
    text = text.strip()
    if text.startswith('{') and text.endswith('}') and '{' not in text[1:-1] and '}' not in text[1:-1]:
        return text[1:-1].strip()
    return text

def is_expression(value) -> bool:
    """Whether ``value`` is text holding just one ``{formula}``."""
    return isinstance(value, str) and value.strip().startswith('{') and _unbrace(value) != value.strip() and not value.strip().startswith('{{')

class Expression:
    """
    One formula, e.g. ``Expression('roll.steps - roll.width', {'roll': roll})``.
    Raises ExpressionError if it doesn't parse or uses what isn't allowed.
    """

    def __init__(self, text: str, names: dict | None = None) -> None:
        self.text = _unbrace(text)
        self.names = dict(names or {})
        if not self.text:
            raise ExpressionError('an empty expression')
        try:
            tree = ast.parse(self.text, mode = 'eval')
        except SyntaxError as error:
            raise ExpressionError(f'{{{self.text}}} is not an expression: {error.msg}') from None
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED):
                raise ExpressionError(f'{{{self.text}}}: {type(node).__name__} is not allowed')
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords):
                raise ExpressionError(f'{{{self.text}}}: only {", ".join(FUNCTIONS)} can be called (without keywords)')
            if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
                raise ExpressionError(f'{{{self.text}}}: {node.attr!r} is private')
        self._tree = tree.body
        calls = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self._used = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and id(node) not in calls]

    @property
    def free(self) -> list:
        """The names it uses that aren't ``names`` or constants: event values it needs."""
        return [name for name in dict.fromkeys(self._used) if name not in self.names and name not in _CONSTANTS]

    @property
    def bound(self) -> list:
        """The ``names`` it uses."""
        return [name for name in dict.fromkeys(self._used) if name in self.names]

    def references(self) -> list:
        """``(name, option)`` for each ``name.option`` it reads (option None for a bare name)."""
        found = []
        for node in ast.walk(self._tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                found.append((node.value.id, node.attr))
        return found

    def evaluate(self, values: dict | None = None):
        """The result, with event ``values`` (looked up before ``names``)."""
        try:
            result = self._evaluate(self._tree, values or {})
        except ExpressionError:
            raise
        except ZeroDivisionError:
            raise ExpressionError(f'{{{self.text}}}: division by zero') from None
        except (TypeError, ValueError, OverflowError, AttributeError) as error:
            raise ExpressionError(f'{{{self.text}}}: {error}') from None
        if isinstance(result, str) and len(result) > _LONGEST:
            raise ExpressionError(f'{{{self.text}}}: the text is too long')
        return result

    def _evaluate(self, node, values: dict):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in values:
                return values[node.id]
            if node.id in self.names:
                return self.names[node.id]
            if node.id in _CONSTANTS:
                return _CONSTANTS[node.id]
            known = [*values, *self.names]
            raise ExpressionError(f'{{{self.text}}}: unknown name {node.id!r}' + (f' (names: {", ".join(known)})' if known else ''))
        if isinstance(node, ast.Attribute):
            owner = self._evaluate(node.value, values)
            what = node.value.id if isinstance(node.value, ast.Name) else 'it'
            try:
                value = getattr(owner, node.attr)
            except AttributeError:
                raise ExpressionError(f'{{{self.text}}}: {what} has no {node.attr!r}') from None
            if callable(value) and not isinstance(value, enum.Enum):
                raise ExpressionError(f'{{{self.text}}}: {what}.{node.attr} is a method, not an option')
            return value.name if isinstance(value, enum.Enum) else value
        if isinstance(node, ast.BinOp):
            left, right = self._evaluate(node.left, values), self._evaluate(node.right, values)
            if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > 100:
                raise ExpressionError(f'{{{self.text}}}: the power is too big')
            if isinstance(node.op, ast.Mult) and isinstance(left, str) != isinstance(right, str) \
                    and len(left if isinstance(left, str) else right) * abs(int(right if isinstance(left, str) else left)) > _LONGEST:
                raise ExpressionError(f'{{{self.text}}}: the text is too long')
            if isinstance(node.op, ast.Add) and isinstance(left, str) != isinstance(right, str):
                # 'Step ' + 3
                left, right = _text(left), _text(right)
            return _BINARY[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp):
            return _UNARY[type(node.op)](self._evaluate(node.operand, values))
        if isinstance(node, ast.BoolOp):
            result = None
            for operand in node.values:
                result = self._evaluate(operand, values)
                if isinstance(node.op, ast.And) != bool(result):
                    return result
            return result
        if isinstance(node, ast.Compare):
            left = self._evaluate(node.left, values)
            for op, operand in zip(node.ops, node.comparators):
                right = self._evaluate(operand, values)
                if not _compare(op, left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self._evaluate(node.body if self._evaluate(node.test, values) else node.orelse, values)
        if isinstance(node, ast.Call):
            return FUNCTIONS[node.func.id](*(self._evaluate(argument, values) for argument in node.args))
        raise ExpressionError(f'{{{self.text}}}: {type(node).__name__} is not allowed')

    def __str__(self) -> str:
        return f'{{{self.text}}}'

    def __repr__(self) -> str:
        return f'Expression({self.text!r})'

    def __eq__(self, other) -> bool:
        return isinstance(other, Expression) and (self.text, self.names) == (other.text, other.names)

    def __hash__(self) -> int:
        return hash(self.text)

def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def _compare(op, left, right) -> bool:
    if isinstance(op, (ast.Eq, ast.NotEq)) and _number(left) and _number(right) and float in (type(left), type(right)):
        # 0.1 + 0.2 equals 0.3
        return (abs(left - right) < 1e-6) == isinstance(op, ast.Eq)
    return bool(_COMPARE[type(op)](left, right))

def _text(value) -> str:
    """How a result shows in text: floats to three decimals, whole ones without."""
    if isinstance(value, float):
        value = round(value, 3)
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, bool):
        return 'on' if value else 'off'
    return str(value)

_PART = re.compile(r'\{\{|\}\}|\{([^{}]*)\}')

class Template:
    """
    A text with ``{formula}`` parts, e.g. ``Template('Step {roll.column + 1}', {'roll': roll})``;
    ``{{`` and ``}}`` are braces.
    """

    def __init__(self, text: str, names: dict | None = None) -> None:
        self.text = text
        self.names = dict(names or {})
        self.parts = []
        last = 0
        for match in _PART.finditer(text):
            self.parts.append(text[last:match.start()])
            if match.group(0) in ('{{', '}}'):
                self.parts.append(match.group(0)[0])
            else:
                self.parts.append(Expression(match.group(1), self.names))
            last = match.end()
        self.parts.append(text[last:])

    @property
    def expressions(self) -> list:
        return [part for part in self.parts if isinstance(part, Expression)]

    @property
    def free(self) -> list:
        return list(dict.fromkeys(name for part in self.expressions for name in part.free))

    @property
    def bound(self) -> list:
        return list(dict.fromkeys(name for part in self.expressions for name in part.bound))

    def references(self) -> list:
        return [reference for part in self.expressions for reference in part.references()]

    def evaluate(self, values: dict | None = None, *, keep_unknown: bool = False, show = _text) -> str:
        """The text filled in (SKIP if a part is); with ``keep_unknown`` a part that can't be computed stays as written."""
        text = []
        for part in self.parts:
            if not isinstance(part, Expression):
                text.append(part)
                continue
            try:
                result = part.evaluate(values)
                if result is SKIP:
                    return SKIP
                text.append(show(result))
            except ExpressionError:
                if not keep_unknown:
                    raise
                text.append(str(part))
        return ''.join(text)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f'Template({self.text!r})'

    def __eq__(self, other) -> bool:
        return isinstance(other, Template) and (self.text, self.names) == (other.text, other.names)

    def __hash__(self) -> int:
        return hash(self.text)

def parse(text, names: dict | None = None):
    """An Expression for text that is one ``{formula}``, a Template for text with formulas in it, else None."""
    if not isinstance(text, str) or '{' not in text:
        return None
    if is_expression(text):
        return Expression(text, names)
    template = Template(text, names)
    return template if template.expressions else None
