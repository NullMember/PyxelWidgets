from . import Effect, EffectDirection

class Pulse(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Pulse_{Pulse._count}')
        super().__init__(**kwargs)
        Pulse._count += 1
    
    def step(self):
        super().step()
        if self._cycleCurrent < int(self.length / 2):
            self.value = 1.0
        else:
            self.value = 0.0
        return self.value