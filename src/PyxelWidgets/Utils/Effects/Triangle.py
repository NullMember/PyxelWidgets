from . import Effect, EffectDirection

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Triangle_{Triangle._count}')
        super().__init__(**kwargs)
        Triangle._count += 1
    
    def step(self):
        super().step()
        self.value = self._cycleCurrent / self.length
        return self.value