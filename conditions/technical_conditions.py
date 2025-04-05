# conditions/technical_conditions.py

from .base import Condition


class MovingAverageCondition(Condition):
    def __init__(self, window, direction='above'):
        self.window = window
        self.direction = direction.lower()

    def evaluate(self, current_data, historical_data=None, context=None):
        if historical_data is None or len(historical_data) < self.window:
            return False
        # Calculate moving average on the 'Price' column
        ma = historical_data['Price'].tail(self.window).mean()
        current_price = current_data['Price']
        return current_price > ma if self.direction == 'above' else current_price < ma


class StopLossCondition(Condition):
    def __init__(self,
                 account_stop_loss_pct: float = None,
                 strategy_stop_loss_pct: float = None,
                 underlying_move_stop_pct: float = None,
                 absolute_stop_loss: float = None):
        """
        Parameters (all are optional):
          - account_stop_loss_pct: Fraction of entry capital lost (e.g., 0.02 for 2%).
          - strategy_stop_loss_pct: Percentage move adverse relative to entry underlying price.
          - underlying_move_stop_pct: Another measure of underlying adverse move.
          - absolute_stop_loss: Fixed rupee loss threshold.
        """
        self.account_stop_loss_pct = account_stop_loss_pct
        self.strategy_stop_loss_pct = strategy_stop_loss_pct
        self.underlying_move_stop_pct = underlying_move_stop_pct
        self.absolute_stop_loss = absolute_stop_loss

    def evaluate(self, current_data, historical_data=None, context=None):
        """
        Evaluates whether any stop loss condition is triggered.
        Expects context to include:
          - "entry_underlying_price": underlying price at entry.
          - "entry_capital": capital at trade entry.
          - "option_data_series": list of option data DataFrames for each leg.
          - "entry_option_prices": list of entry option prices for each leg.
          - "legs": list of leg objects (with attributes 'action' and 'quantity').
          - "contract_multiplier": multiplier for each contract.
          - current_data['Price'] is the current underlying price.
        """
        if context is None:
            return False

        entry_underlying = context.get("entry_underlying_price")
        current_underlying = current_data.get("Price")
        entry_capital = context.get("current_capital")
        option_data_series = context.get("option_data_series", [])
        entry_option_prices = context.get("entry_option_prices", [])
        legs = context.get("legs", [])
        contract_multiplier = context.get("contract_multiplier", 50)

        # Compute estimated current profit from options for the entire trade
        total_profit = 0
        from new_backtest.utils.helpers import get_nearest_option_price
        for idx, leg in enumerate(legs):
            option_df = option_data_series[idx]
            current_option_price = get_nearest_option_price(option_df, current_data.name)
            entry_option_price = entry_option_prices[idx]
            lots = leg.quantity
            if leg.action.lower() == "buy":
                profit = (current_option_price - entry_option_price) * contract_multiplier * lots
            else:
                profit = (entry_option_price - current_option_price) * contract_multiplier * lots
            total_profit += profit

        # Determine overall strategy direction (simple majority: if more BUY than SELL, assume long)
        buy_count = sum(1 for leg in legs if leg.action.lower() == "buy")
        sell_count = sum(1 for leg in legs if leg.action.lower() == "sell")
        long_strategy = buy_count >= sell_count

        stop_triggered = False

        # Strategy-level stop loss: if underlying moves adversely by a percentage of the entry price.
        if self.strategy_stop_loss_pct is not None and entry_underlying is not None and current_underlying is not None:
            if long_strategy:
                if (entry_underlying - current_underlying) / entry_underlying >= self.strategy_stop_loss_pct:
                    stop_triggered = True
            else:
                if (current_underlying - entry_underlying) / entry_underlying >= self.strategy_stop_loss_pct:
                    stop_triggered = True

        # Underlying move stop loss: similar check (can be tuned differently)
        if self.underlying_move_stop_pct is not None and entry_underlying is not None and current_underlying is not None:
            if long_strategy:
                if (entry_underlying - current_underlying) / entry_underlying >= self.underlying_move_stop_pct:
                    stop_triggered = True
            else:
                if (current_underlying - entry_underlying) / entry_underlying >= self.underlying_move_stop_pct:
                    stop_triggered = True

        # Absolute loss stop: if total estimated profit is below negative threshold.
        if self.absolute_stop_loss is not None:
            if total_profit <= -self.absolute_stop_loss:
                stop_triggered = True

        # Account-level stop loss: if loss exceeds a percentage of entry capital.
        if self.account_stop_loss_pct is not None and entry_capital is not None:
            if total_profit <= - (self.account_stop_loss_pct * entry_capital):
                stop_triggered = True

        return stop_triggered


class VIXCondition(Condition):
    def __init__(self, threshold, direction='above'):
        self.threshold = threshold
        self.direction = direction.lower()

    def evaluate(self, current_data, historical_data=None, context=None):
        vix = current_data.get('VIX', None)
        if vix is None:
            return False
        return vix > self.threshold if self.direction == 'above' else vix < self.threshold

class TakeProfitCondition(Condition):
    def __init__(self, take_profit_pct=None, take_profit_abs=None):
        self.take_profit_pct = take_profit_pct
        self.take_profit_abs = take_profit_abs

    def evaluate(self, current_data, historical_data=None, context=None):
        entry_price = context.get('entry_price')
        current_price = current_data['Price']
        if entry_price is None:
            return False
        if self.take_profit_pct is not None:
            return (current_price - entry_price) / entry_price >= self.take_profit_pct
        elif self.take_profit_abs is not None:
            return current_price >= entry_price + self.take_profit_abs
        return False

class TrailingStoplossCondition(Condition):
    def __init__(self, trailing_stoploss_pct):
        self.trailing_stoploss_pct = trailing_stoploss_pct
        self.max_price = None

    def evaluate(self, current_data, historical_data=None, context=None):
        current_price = current_data['Price']
        if self.max_price is None:
            # Initialize max price as entry price
            self.max_price = context.get('entry_price', current_price)
        else:
            # Update max price if current price exceeds it
            if current_price > self.max_price:
                self.max_price = current_price
        # Check if current price has dropped by trailing_stoploss_pct from the maximum
        return (current_price - self.max_price) / self.max_price <= -self.trailing_stoploss_pct

