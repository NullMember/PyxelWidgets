from .Effect import Effect

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def step(self):
        super().step()
        return self._cycleCurrent / self._cycleTotal