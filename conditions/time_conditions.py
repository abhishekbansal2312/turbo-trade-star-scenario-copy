# conditions/time_conditions.py

from datetime import datetime
from .base import Condition


class EntryTimeCondition(Condition):
    def __init__(self, target_time):
        self.target_time = datetime.strptime(target_time, "%H:%M").time()

    def evaluate(self, current_data, historical_data=None, context=None):
        return current_data.name.time() == self.target_time


class EntryDateCondition(Condition):
    def __init__(self, day_name):
        self.day_name = day_name.lower()

    def evaluate(self, current_data, historical_data=None, context=None):
        return current_data.name.strftime('%A').lower() == self.day_name