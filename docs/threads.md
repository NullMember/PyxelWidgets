# Threads

PyxelWidgets handles input the moment it arrives, on the thread it arrives
on. One lock keeps those threads from stepping on each other and on
rendering. This page says what runs where and the few rules that follow.

## What runs where

| Thread | Runs | Holds the lock while |
|---|---|---|
| Main (`app.run()`) | rendering every frame (`surface.update()`), binding glides, device checks once a second | rendering; each device check |
| MIDI input (one per open port, from rtmidi) | `decode`, then pad and control events, the widgets' input handling, their events and everything subscribed to them (mappings, links, your handlers) | handling the input |
| Transport (while playing) | `every()` subscribers: Sequencers, Trackers and ClipLaunchers on the transport, your subscriptions | each tick |
| A widget's own clock (`clock = Clock.Own`) | that widget's `tick` | each tick |
| WebGrid (one per open browser) | touches from that browser, as pad events | handling the input |
| Outputs (MIDI ports, OSC server) | messages from other software: `MessageReceived`, mapping feedback | updating the widget |

The lock is `app.lock`, the same object as `surface.lock` and
`app.transport.lock`. It is an `RLock`: a thread holding it can take it again.

The on-screen `Virtual` device is the exception: Tk only works on the
thread that created it. Create it and run the App on the main thread; its
clicks are handled while it shows a frame.

## Rule 1: hold the lock when you touch widgets from your own thread

Everything PyxelWidgets starts already holds the lock when it calls you.
Your own threads don't. A MIDI port of your own, a network client, a timer:

```python
import rtmidi

def on_message(message, _):
    status, control, value = message[0]
    with app.lock:
        surface['volume'].value = value / 127

midi_in = rtmidi.MidiIn()
midi_in.open_port(0)
midi_in.set_callback(on_message)
```

Without the lock a frame could render half-changed widgets. Two threads
could also change the same widget at once.

## Rule 2: keep handlers short

Event handlers, transport subscribers and link actions run while the lock is
held. While one runs, nothing renders and no other input is handled.

- Don't sleep or wait for slow things (network, files, user input) in a
  handler. Hand the work to a thread or a `queue.Queue` and return.
- Don't wait for a thread that needs the lock: it can't get it until you
  return. For instance `transport.close()` waits for the transport thread,
  so from a pad handler it stalls for up to a second. Use `transport.stop()`
  there; it doesn't wait. The designer starts and stops its transport on a
  short-lived thread for this reason.
- Errors in transport subscribers are printed, not raised, so one broken
  subscriber doesn't stop the music.

## Rule 3: events happen where they're caused

`widget.on(Changed, handler)` calls `handler` on the thread that changed
the widget. That can be the MIDI thread for a press, the transport thread
for a played step, or the main thread when your code calls `set_value`.
Handlers shouldn't assume a particular thread.

Changing a widget from code (`fader.value = 0.5`, `widget.configure(...)`)
doesn't emit events, so there are no surprise callbacks. The exception is a
Pages' `page`, which emits PageChanged. Calling the input
methods (`press`, `set_value`) does, as if a person had done it.

## Rule 4: one App loop

`app.run()` blocks and renders until `app.stop()`, Ctrl+C or a device
closing. To run your own loop instead, call `app.step()` once a frame, plus
`surface.check_devices()` now and then if devices may be unplugged.
`app.close()` stops the transport and the widgets' own clocks first, then
closes the devices and outputs, outside the lock.

## In the designer

The designer server adds:

- one thread per browser request;
- a render thread for connected hardware (30 frames a second);
- a thread checking for unplugged and plugged-in hardware.

They take the preview's lock and then the surface lock, always in that
order. The event log has its own small lock, because widgets emit events
from device and transport threads that already hold the surface lock.
