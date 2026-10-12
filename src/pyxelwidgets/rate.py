"""
Musical lengths: note values such as ``'1/16'``, dotted ``'1/8.'``, triplet
``'1/8T'``, whole notes ``'1'`` or ``'2'``, and ``'beat'`` or ``'bar'`` of a
time signature. Used by the transport, widgets' ``rate`` and animations.
"""

import fractions
import re

__all__ = ['parse_rate', 'parse_signature', 'quarter_notes']

_RATE = re.compile(r'^\s*(\d+)\s*(?:/\s*(\d+))?\s*([.tT])?\s*$')

def parse_rate(rate, signature: tuple = (4, 4)) -> fractions.Fraction:
    """Length of ``rate`` in whole notes, e.g. ``'1/8.'`` → 3/16. Raises ValueError."""
    if isinstance(rate, (int, fractions.Fraction)) and not isinstance(rate, bool):
        length = fractions.Fraction(rate)
    elif rate == 'beat':
        length = fractions.Fraction(1, signature[1])
    elif rate == 'bar':
        length = fractions.Fraction(signature[0], signature[1])
    else:
        match = _RATE.match(rate) if isinstance(rate, str) else None
        if match is None:
            raise ValueError(f"expected a note value like '1/16', '1/8.', '1/8T', 'beat' or 'bar', got {rate!r}")
        numerator, denominator, modifier = match.groups()
        if denominator is not None and int(denominator) == 0:
            raise ValueError(f'rate {rate!r} divides by zero')
        length = fractions.Fraction(int(numerator), int(denominator or 1))
        if modifier == '.':
            length *= fractions.Fraction(3, 2)
        elif modifier in ('t', 'T'):
            length *= fractions.Fraction(2, 3)
    if length <= 0:
        raise ValueError(f'rate {rate!r} must be longer than zero')
    return length

def parse_signature(signature) -> tuple:
    """A time signature as (beats per bar, beat note value), e.g. ``[6, 8]`` → (6, 8). Raises ValueError."""
    try:
        beats, note = (int(value) for value in signature)
    except (TypeError, ValueError):
        raise ValueError(f'signature must be (beats, note value), got {signature!r}') from None
    if beats < 1 or note < 1:
        raise ValueError(f'signature must be positive, got {signature!r}')
    return (beats, note)

def quarter_notes(rate, signature: tuple = (4, 4)) -> float:
    """Length of ``rate`` in quarter notes (beats at x/4), e.g. ``'1/8'`` → 0.5."""
    return float(parse_rate(rate, signature) * 4)
