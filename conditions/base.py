# conditions/base.py

class Condition:
    def evaluate(self, current_data, historical_data=None, context=None):
        raise NotImplementedError("Subclasses should implement this!")
