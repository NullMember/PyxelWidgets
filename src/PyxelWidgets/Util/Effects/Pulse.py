from .Effect import Effect

class Pulse(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def step(self):
        super().step()
        if self._cycleCurrent < int(self._cycleTotal / 2):
            return 1.0
        else:
            return 0.0