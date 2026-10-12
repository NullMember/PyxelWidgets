from pyxelwidgets.devices.virtual import Virtual
from pyxelwidgets.devices.midi import MIDI
from pyxelwidgets import (App, Button, ButtonGroup, Changed, Color, Colors, Fader, Group, Held, Keyboard, Knob,
                          NoteOff, NoteOn, Pages, Pressed, Released, Sequencer, StepPlayed, Surface)
import random

def random_color():
    return Color(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

controller = Virtual(9, 9)
controller.connect()

keyboard = MIDI()
keyboard.connect_virtual('Keyboard')

surface = Surface(9, 9)
surface.add_device(controller)
app = App(surface, bpm = 60)

# Pages share the 9x8 area under the top row, which selects them
pages = surface.add(Pages(0, 0, 9, 9, selector = Pages.Selector.Top, selector_color = Colors.Blue))
fader_page = pages.add(Group(0, 0, 9, 8))
knob_page = pages.add(Group(0, 0, 9, 8))
# The keyboard page has its own pages: the keyboard and its settings, switched with the red button
keyboard_pages = pages.add(Pages(0, 0, 9, 8, selector = Pages.Selector.Off))
keyboard_page = keyboard_pages.add(Group(0, 0, 9, 8))
keyboard_config_page = keyboard_pages.add(Group(0, 0, 9, 8))
sequencer_page = pages.add(Group(0, 0, 9, 8))

# Faders and knobs send control changes
for i in range(8):
    fader = fader_page.add(Fader(i, 0, 1, 8, active_color = random_color()))
    fader.on(Changed, lambda e, cc = 8 + i: keyboard.send_control_change(cc, int(e.value * 127.0)))
    knob = knob_page.add(Knob(0, 7 - i, 8, 1, type = Knob.Type.BoostCut, active_color = random_color()))
    knob.on(Changed, lambda e, cc = 16 + i: keyboard.send_control_change(cc, int(e.value * 127.0)))

# Keyboard, and a settings page opened with the red button
notes = keyboard_page.add(Keyboard(
    x = 0, y = 0, width = 8, height = 8,
    type = Keyboard.Type.DiatonicVertical,
    scale = Keyboard.Scale.Major,
    root = Keyboard.Root.C,
    fold = 4, octave = 4))
notes.on(NoteOn, lambda e: keyboard.send_note_on(e.note, int(e.velocity * 127.0)))
notes.on(NoteOff, lambda e: keyboard.send_note_off(e.note))
keyboard_page.add(Button(8, 0, 1, 1, inactive_color = Colors.Red)).on(Released, lambda e: keyboard_pages.next())

type_selector = keyboard_config_page.add(ButtonGroup(0, 7, len(Keyboard.Type), 1))
root_selector = keyboard_config_page.add(Keyboard(0, 5, 8, 2, type = Keyboard.Type.Keyboard))
octave_selector = keyboard_config_page.add(ButtonGroup(0, 4, 8, 1, inactive_color = Colors.PaleVioletRed))
scale_selector = keyboard_config_page.add(ButtonGroup(0, 0, 8, 2, inactive_color = Colors.SkyBlue))
keyboard_config_page.add(Button(8, 0, 1, 1, inactive_color = Colors.Red)).on(Released, lambda e: keyboard_pages.next())

@type_selector.on(Pressed)
def select_type(e):
    notes.type = Keyboard.Type(e.x)

@root_selector.on(NoteOn)
def select_root(e):
    notes.root = Keyboard.Root(e.note % 12)

@octave_selector.on(Pressed)
def select_octave(e):
    notes.octave = e.x

@scale_selector.on(Pressed)
def select_scale(e):
    index = e.x + (e.y * scale_selector.width)
    if index < len(Keyboard.Scale):
        notes.scale = Keyboard.Scale(index)

# 16 step sequencers playing drums on channel 2; the selected one is shown
sequencers = []
for i in range(16):
    sequencer = sequencer_page.add(Sequencer(0, 4, 8, 4, visible = i == 0))
    app.attach(sequencer)

    @sequencer.on(StepPlayed)
    def play(e, note = 36 + i):
        keyboard.send_note_on(note, 0, 1)
        if e.active:
            keyboard.send_note_on(note, 100 + random.randint(-10, 10), 1)

    sequencers.append(sequencer)

sample_selector = sequencer_page.add(ButtonGroup(0, 0, 4, 4, inactive_color = Color(255, 255, 0)))
length_selector = sequencer_page.add(ButtonGroup(4, 0, 1, 4, inactive_color = Color(255, 0, 255)))

@sample_selector.on(Pressed)
def select_sample(e):
    index = e.x + (e.y * 4)
    for i, sequencer in enumerate(sequencers):
        sequencer.visible = i == index
    keyboard.send_note_on(36 + index, 100, 1)
    keyboard.send_note_on(36 + index, 0, 1)

@sample_selector.on(Held)
def clear_sample(e):
    sequencers[e.x + (e.y * 4)].reset()

@length_selector.on(Pressed)
def select_length(e):
    for sequencer in sequencers:
        sequencer.steps = (e.y + 1) * 8

if __name__ == "__main__":
    # Runs until Ctrl+C or the grid window is closed
    app.transport.play()
    app.run()
    keyboard.close()
