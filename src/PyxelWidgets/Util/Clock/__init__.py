from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from threading import Thread
import time

class Target:

    _count = 0

    def __init__(self, target: Callable, wrap = 1, delay = 0, **kwargs) -> None:
        self._name = kwargs.get('name', f'Target_{Target._count}')
        self._target = target
        self._wrap = wrap
        self._delay = delay
        self._active = True
        self._lock = False
        self._tick = 0
        Target._count += 1
    
    @property
    def name(self) -> str:
        return self._name

    @property
    def wrap(self) -> int:
        return self._wrap
    
    @wrap.setter
    def wrap(self, value: int) -> None:
        self._wrap = value if value >= 0 else 0
    
    @property
    def delay(self) -> int:
        return self._delay
    
    @delay.setter
    def delay(self, value: int) -> None:
        self._delay = value

    @property
    def active(self) -> bool:
        return self._active
    
    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
    
    @property
    def tick(self) -> int:
        return self._tick

    @tick.setter
    def tick(self, value: int) -> None:
        if not self._lock:
            self._lock = True
            self._tick = value
            if (self._tick + self._delay) % self._wrap == 0:
                self._target(self._tick)
            self._lock = False

    def step(self) -> None:
        if not self._lock:
            self._lock = True
            self._tick += 1
            if (self._tick + self._delay) % self._wrap == 0:
                self._target(self._tick)
            self._lock = False
    
    def set(self, tick: int) -> None:
        self.tick = tick

class Clock(Thread):

    _count = 0

    def __init__(self, bpm: float = 60, ppq: float = 24) -> None:
        super().__init__(name = f'Clock_{Clock._count}')
        self._pool = ThreadPoolExecutor(thread_name_prefix = f'Clock_{self._count}_Target')
        self._bpm: float = bpm
        self._ppq: float = ppq
        self._delay: float = 60.0 / (bpm * ppq)
        self._tick: int = 0
        self._currentTime: float = 0
        self._targets = {}
        self._running = True
        self._pause = False
        self._terminate = False
        Clock._count += 1
    
    def __del__(self):
        self.terminate()

    @property
    def bpm(self) -> float:
        return self._bpm
    
    @bpm.setter
    def bpm(self, value: float) -> None:
        self._bpm = value
        self._delay = 60.0 / (self._bpm * self._ppq)
    
    @property
    def ppq(self) -> float:
        return self._ppq
    
    @ppq.setter
    def ppq(self, value: float) -> None:
        self._ppq = value
        self._delay = 60.0 / (self._bpm * self._ppq)
    
    @property
    def delay(self) -> float:
        return self._delay

    @delay.setter
    def delay(self, value: float) -> None:
        self._delay = value

    @property
    def tick(self) -> int:
        return self._tick
    
    @property
    def names(self) -> list:
        return list(self._targets)
    
    @property
    def values(self) -> list:
        return list(self._targets.values())

    @property
    def targets(self) -> dict:
        return self._targets
    
    @property
    def state(self) -> str:
        if self._terminate:
            return "terminated"
        elif not self._running:
            return "stopped"
        elif self._pause:
            return "paused"
        else:
            return "running"

    def addTarget(self, target: Target) -> None:
        self._targets[target.name] = target
    
    def addTargets(self, targets: dict) -> None:
        for target in targets:
            self._targets[target.name] = target
    
    def removeTarget(self, name: str) -> Target:
        if name in self._targets:
            return self._targets.pop(name)
    
    def getTarget(self, name: str) -> Target:
        if name in self._targets:
            return self._targets[name]

    def run(self):
        while not self._terminate:
            self._currentTime = time.time()
            self.step()
            delay = self._delay - (time.time() - self._currentTime)
            time.sleep(0.0 if delay < 0.0 else delay)
    
    def step(self):
        if self._running:
            for target in self.values:
                if target.active:
                    self._pool.submit(target.set, self._tick)
            if not self._pause:
                self._tick += 1
    
    def pause(self):
        self._pause = True
    
    def resume(self):
        self._pause = False
        self._running = True
    
    def reset(self):
        self._tick = 0
    
    def stop(self):
        self._running = False
    
    def terminate(self):
        self._terminate = True