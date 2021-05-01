from .Effect import Effect

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def update(self):
        super().update()
        return self._cycleCurrent / self._cycleTotal