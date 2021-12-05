from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from threading import Thread
import time

class Target:

    _count = 0

    def __init__(self, target: Callable, wrap = 1, delay = 0, **kwargs) -> None:
        self.name = kwargs.get('name', f'Target_{Target._count}')
        self.target = target
        self.wrap = wrap
        self.delay = delay
        self.active = True
        self.lock = False
        self._tick = 0
        Target._count += 1
    
    @property
    def tick(self) -> int:
        return self._tick

    @tick.setter
    def tick(self, value: int) -> None:
        if not self.lock:
            self.lock = True
            self._tick = value
            if (self._tick + self.delay) % self.wrap == 0:
                self.target(self._tick)
            self.lock = False

    def step(self) -> None:
        if not self.lock:
            self.lock = True
            self._tick += 1
            if (self._tick + self.delay) % self.wrap == 0:
                self.target(self._tick)
            self.lock = False
    
    def set(self, tick: int):
        self.tick = tick

class Clock(Thread):

    _count = 0

    def __init__(self, bpm: float = 60, ppq: float = 24) -> None:
        super().__init__(name = f'Clock_{Clock._count}')
        self._pool = ThreadPoolExecutor(thread_name_prefix = f'Clock_{self._count}_Target')
        self._bpm: float = bpm
        self._ppq: float = ppq
        self.delay: float = 60.0 / (bpm * ppq)
        self.tick: int = 0
        self.currentTime: float = 0
        self.targets = {}
        self.futures = {}
        self.running = True
        self._pause = False
        self._terminate = False
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
    def state(self) -> str:
        if self._terminate:
            return "terminated"
        elif not self.running:
            return "stopped"
        elif self._pause:
            return "paused"
        else:
            return "running"

    def addTarget(self, target: Target) -> None:
        self.targets[target.name] = target
    
    def addTargets(self, targets: dict) -> None:
        for target in targets:
            self.targets[target.name] = target
    
    def removeTarget(self, name: str) -> Target:
        if name in self.targets:
            return self.targets.pop(name)
    
    def getTarget(self, name: str) -> Target:
        if name in self.targets:
            return self.targets[name]

    def run(self):
        while not self._terminate:
            self.currentTime = time.time()
            self._step()
            delay = self.delay - (time.time() - self.currentTime)
            time.sleep(0.0 if delay < 0.0 else delay)
    
    def step(self):
        for target in self.targets.values():
            if target.active:
                self._pool.submit(target.set, self.tick)
        if not self._pause:
            self.tick += 1
    
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
        self._pool.shutdown(wait = True)