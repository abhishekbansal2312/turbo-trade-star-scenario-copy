# strategies/strategy.py

class OptionLeg:
    """
    Represents one leg of an options trade.
    """

    def __init__(self, option_type, action, strike_selection: dict, quantity=1):
        self.option_type = option_type.lower()
        self.action = action.lower()  # "buy" or "sell"
        self.strike_selection = strike_selection  # dict with method and value
        self.quantity = quantity
        # Computed at trade entry
        self.computed_strike = None


class OptionStrategy:
    """
    Encapsulates an option strategy with multiple entry/exit conditions and option legs.
    """

    def __init__(self, name):
        self.name = name
        self.entry_conditions = []
        self.exit_conditions = []
        self.option_legs = []

    def add_entry_condition(self, condition):
        self.entry_conditions.append(condition)

    def add_exit_condition(self, condition):
        self.exit_conditions.append(condition)

    def add_option_leg(self, leg: OptionLeg):
        self.option_legs.append(leg)
