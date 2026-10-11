from concurrent.futures import ThreadPoolExecutor
import enum
from typing import Callable
from threading import Lock, Thread, current_thread
import time

class Target:

    _count = 0

    def __init__(self, target: Callable, wrap = 1, delay = 0, **kwargs) -> None:
        self.name = kwargs.get('name', f'Target_{Target._count}')
        self.wrap = wrap
        self.delay = delay
        self.target = target
        self.active = True
        self.lock = Lock()
        self._tick = 0
        Target._count += 1
    
    @property
    def tick(self) -> int:
        return self._tick

    @tick.setter
    def tick(self, value: int) -> None:
        # Skip this tick if the previous call is still running
        if self.lock.acquire(blocking = False):
            try:
                self._tick = value
                if (self._tick + self.delay) % self.wrap == 0:
                    self.target(self._tick)
            finally:
                self.lock.release()

    def step(self) -> None:
        self.tick = self._tick + 1
    
    def set(self, tick: int):
        self.tick = tick

class Clock(Thread):

    _count = 0

    class State(enum.Enum):
        Running = enum.auto()
        Paused = enum.auto()
        Stopped = enum.auto()
        Terminated = enum.auto()

    def __init__(self, bpm: float = 60, ppq: float = 24, lock = None) -> None:
        super().__init__(name = f'Clock_{Clock._count}')
        self._pool = ThreadPoolExecutor(thread_name_prefix = f'Clock_{self._count}_Target')
        self._bpm: float = bpm
        self._ppq: float = ppq
        self.delay: float = 60.0 / (bpm * ppq)
        self.tick: int = 0
        self.current_time: float = 0
        self.targets = {}
        self.futures = {}
        self.running = True
        self._pause = False
        self._terminate = False
        # Held while calling each target, e.g. an App's lock shared with rendering
        self.lock = lock
        Clock._count += 1

    @property
    def bpm(self) -> float:
        return self._bpm
    
    @bpm.setter
    def bpm(self, value: float) -> None:
        self._bpm = value
        self.delay = 60.0 / (self._bpm * self._ppq)
    
    @property
    def ppq(self) -> float:
        return self._ppq
    
    @ppq.setter
    def ppq(self, value: float) -> None:
        self._ppq = value
        self.delay = 60.0 / (self._bpm * self._ppq)
    
    @property
    def state(self) -> State:
        if self._terminate:
            return Clock.State.Terminated
        elif not self.running:
            return Clock.State.Stopped
        elif self._pause:
            return Clock.State.Paused
        else:
            return Clock.State.Running

    def add_target(self, target: Target) -> None:
        self.targets[target.name] = target
    
    def add_targets(self, targets: dict) -> None:
        for target in targets:
            self.targets[target.name] = target
    
    def remove_target(self, name: str) -> Target:
        if name in self.targets:
            return self.targets.pop(name)
    
    def get_target(self, name: str) -> Target:
        if name in self.targets:
            return self.targets[name]

    def run(self):
        # Schedule ticks against an absolute timeline so sleep overshoot doesn't drift the tempo
        next_tick = time.perf_counter()
        while not self._terminate:
            self.current_time = time.time()
            self._step()
            next_tick += self.delay
            delay = next_tick - time.perf_counter()
            if delay > 0.0:
                time.sleep(delay)
            elif delay < -self.delay:
                # Fell more than a tick behind (e.g. suspended); resync instead of bursting
                next_tick = time.perf_counter()
    
    def step(self):
        for target in list(self.targets.values()):
            if target.active:
                self._pool.submit(self._call, target, self.tick)
        if not self._pause:
            self.tick += 1

    def _call(self, target: Target, tick: int) -> None:
        if self.lock is None:
            target.set(tick)
        else:
            with self.lock:
                target.set(tick)
    
    def _step(self):
        if self.running:
            self.step()
    
    def pause(self):
        self._pause = True
    
    def resume(self):
        self._pause = False
        self.running = True
    
    def reset(self):
        self.tick = 0
    
    def stop(self):
        self.running = False
        self.reset()
    
    def terminate(self):
        self._terminate = True
        # Let the tick loop exit before shutting the pool, or its next submit raises
        if self.is_alive() and current_thread() is not self:
            self.join()
        self._pool.shutdown(wait = True, cancel_futures = True)