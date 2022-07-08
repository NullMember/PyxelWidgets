import enum

class Event(enum.Enum):
    Pressed = enum.auto()
    Released = enum.auto()
    Held = enum.auto()
    Touched = enum.auto()
    Changed = enum.auto()
    Increased = enum.auto()
    Decreased = enum.auto()
    Tick = enum.auto()
    Active = enum.auto()
    Page = enum.auto()
    Resized = enum.auto()
    Custom = enum.auto()