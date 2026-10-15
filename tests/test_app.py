import threading
import time

import pytest

from pyxelwidgets import App, ButtonGroup, Frame, Sequencer, StepPlayed, Surface, Transport
from pyxelwidgets.devices import Device


class FakeDevice(Device):
    def send_pixel(self, x, y, pixel):
        pass


@pytest.fixture
def thread_errors():
    errors = []
    previous = threading.excepthook
    threading.excepthook = lambda args: errors.append(args.exc_value)
    yield errors
    threading.excepthook = previous


def make_app(fps = 200, **kwargs):
    controller = FakeDevice(width = 8, height = 8)
    controller.connect()
    surface = Surface(8, 8)
    surface.add_device(controller, 0, 0)
    return App(surface, fps = fps, **kwargs), surface, controller


def run_in_thread(app):
    thread = threading.Thread(target = app.run)
    thread.start()
    return thread


def test_stop_ends_run_and_closes_controllers():
    app, surface, controller = make_app()
    frames = []
    @surface.on(Frame)
    def on_frame(e):
        frames.append(e.frame)
        if len(frames) == 5:
            app.stop()
    app.run()
    assert len(frames) == 5
    assert controller.terminated
    assert not app.transport.playing


def test_closing_a_controller_ends_run():
    app, surface, controller = make_app()
    surface.on(Frame, lambda e: controller.close() if e.frame == 2 else None)
    app.run()
    assert controller.terminated


def test_keyboard_interrupt_closes_cleanly():
    app, surface, controller = make_app()
    def interrupt(e):
        raise KeyboardInterrupt
    surface.on(Frame, interrupt)
    app.run()
    assert controller.terminated


def test_frame_rate():
    app, surface, controller = make_app(fps = 50)
    thread = run_in_thread(app)
    time.sleep(0.5)
    app.stop()
    thread.join()
    assert 15 <= surface.frame_counter <= 30


def test_input_waits_for_render_lock():
    app, surface, controller = make_app()
    group = surface.add(ButtonGroup(0, 0, 8, 1, mode = ButtonGroup.Mode.Multi))
    pressed = threading.Event()
    with app.lock:
        thread = threading.Thread(target = lambda: (controller.set_button(3, 0, 1.0), pressed.set()))
        thread.start()
        assert not pressed.wait(0.1)
        assert not group.state[3, 0]
    assert pressed.wait(1)
    assert group.state[3, 0]
    thread.join()
    controller.close()


def test_transport_subscribers_run_under_lock(thread_errors):
    lock = threading.RLock()
    transport = Transport(lock = lock)
    called = threading.Event()
    transport.every('1/16', lambda count: called.set())
    with lock:
        transport.play()
        assert not called.wait(0.1)
    assert called.wait(1)
    transport.close()
    assert thread_errors == []


def test_transport_close_while_playing(thread_errors):
    transport = Transport(600, ppq = 96)
    transport.every('1/64', lambda count: None)
    transport.play()
    thread = transport._thread
    time.sleep(0.05)
    transport.close()
    assert not thread.is_alive() and not transport.playing
    assert thread_errors == []


def test_app_close_stops_transport():
    app, surface, controller = make_app()
    app.transport.play()
    thread = app.transport._thread
    app.close()
    assert not thread.is_alive()


def test_sequencer_on_app_transport_with_concurrent_input(thread_errors):
    app, surface, controller = make_app(bpm = 600)
    sequencer = surface.add(Sequencer(0, 0, 8, 2))
    app.transport.every(sequencer.rate, sequencer.play)
    app.transport.play()
    ticks = []
    sequencer.on(StepPlayed, lambda e: ticks.append(e.step))
    thread = run_in_thread(app)
    # Hammer the grid from another thread while the clock and renderer run
    for i in range(400):
        controller.set_button(i % 8, (i // 8) % 2, 1.0)
        controller.set_button(i % 8, (i // 8) % 2, 0.0)
    time.sleep(0.3)
    app.stop()
    thread.join()
    assert len(ticks) > 5
    assert thread_errors == []


def test_transport_and_app_reject_unknown_arguments():
    with pytest.raises(TypeError):
        Transport(tempo = 90)
    with pytest.raises(TypeError):
        App(Surface(1, 1), tempo = 90)
    app = App(Surface(1, 1), bpm = 90, signature = (6, 8))
    assert app.transport.bpm == 90 and app.transport.signature == (6, 8)
    assert app.transport.lock is app.lock


def test_input_is_drawn_at_once():
    # A frame every 2 s: without drawing on input the press would wait 1.8 s
    app, surface, controller = make_app(fps = 0.5, check_interval = None)
    group = surface.add(ButtonGroup(0, 0, 8, 8))
    shown = []
    controller.send_pixel = lambda x, y, pixel: shown.append((time.perf_counter(), x, y))
    thread = run_in_thread(app)
    time.sleep(0.2)
    shown.clear()
    pressed = time.perf_counter()
    controller.set_button(3, 4, 1.0)
    deadline = time.monotonic() + 1.0
    while not any(pad == (3, 4) for _, *pad in shown) and time.monotonic() < deadline:
        time.sleep(0.005)
    app.stop()
    thread.join(timeout = 2.0)
    [when] = [when for when, *pad in shown if pad == [3, 4]][:1]
    assert when - pressed < 0.1
    assert not thread.is_alive()
