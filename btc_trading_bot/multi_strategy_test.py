import websocket
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from trade_logger import setup_logging, log_trade_summary
import threading

class BaseStrategy:
    def __init__(self, name, initial_capital=1000, leverage=50):
        self.name = name
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        self.entry_price = 0
        self.entry_time = None
        self.portfolio_value = initial_capital
        self.trades = []
        self.prices = []
        self.volumes = []
        
        # Fee structure (Hyperliquid)
        self.maker_fee = 0.0002  # 0.02%
        self.taker_fee = 0.0005  # 0.05%
        
    def calculate_fees(self, position_size, is_maker=False):
        """Calculate trading fees for a given position size"""
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        return position_size * fee_rate
        
    def calculate_total_cost(self, price, position_size, is_entry=True, is_maker=False):
        """Calculate total cost including fees for a trade"""
        fees = self.calculate_fees(position_size, is_maker)
        if is_entry:
            return position_size + fees
        else:
            return position_size - fees
        
    def calculate_ema(self, period):
        return pd.Series(self.prices).ewm(span=period, adjust=False).mean().values
        
    def calculate_macd(self):
        exp1 = pd.Series(self.prices).ewm(span=12, adjust=False).mean()
        exp2 = pd.Series(self.prices).ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd.values, signal.values
        
    def calculate_rsi(self, period=14):
        deltas = np.diff(self.prices)
        if len(deltas) < period:
            return np.array([50])  # Default neutral RSI
        gain = deltas.copy()
        loss = deltas.copy()
        gain[gain < 0] = 0
        loss[loss > 0] = 0
        avg_gain = np.concatenate(([0], pd.Series(gain).rolling(period).mean().values[period:]))
        avg_loss = np.concatenate(([0], pd.Series(np.abs(loss)).rolling(period).mean().values[period:]))
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
        
    def calculate_volume_ratio(self, period=20):
        if len(self.volumes) < period:
            return 1.0
        avg_volume = pd.Series(self.volumes).rolling(period).mean().iloc[-1]
        current_volume = self.volumes[-1]
        return current_volume / avg_volume if avg_volume > 0 else 1.0

class ConservativeRSIMACD(BaseStrategy):
    def __init__(self, initial_capital=1000):
        super().__init__("Conservative RSI+MACD", initial_capital)
        self.rsi_period = 14
        self.rsi_overbought = 75
        self.rsi_oversold = 25
        self.profit_target = 0.8  # 0.8%
        self.stop_loss = -0.15   # Tighter stop: -0.15%
        self.trailing_stop = 0.2  # Tighter trailing: 0.2%
        
    def execute_trade(self, price, volume, timestamp):
        self.prices.append(price)
        self.volumes.append(volume)
        
        if len(self.prices) < 26:
            return
            
        rsi = self.calculate_rsi(self.rsi_period)[-1]
        macd, signal = self.calculate_macd()
        ema_20 = self.calculate_ema(20)[-1]
        
        # Calculate momentum
        price_change = (price - self.prices[-2]) / self.prices[-2] * 100 if len(self.prices) > 1 else 0
        
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            entry_cost = self.calculate_total_cost(price, position_size, is_entry=True, is_maker=False)
            
            # Long entry - Multiple confirmations required
            long_signal = (
                rsi < self.rsi_oversold and  # Oversold
                macd[-1] > signal[-1] and    # MACD cross up
                price > ema_20 and           # Above EMA
                price_change > -0.1          # Not falling too fast
            )
            
            # Short entry - Multiple confirmations required
            short_signal = (
                rsi > self.rsi_overbought and  # Overbought
                macd[-1] < signal[-1] and      # MACD cross down
                price < ema_20 and             # Below EMA
                price_change < 0.1             # Not rising too fast
            )
            
            if long_signal:
                self.position = 1
                self.entry_price = price
                self.entry_time = timestamp
                self.highest_price = price
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_rsi': rsi,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size
                })
                
            elif short_signal:
                self.position = -1
                self.entry_price = price
                self.entry_time = timestamp
                self.lowest_price = price
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_rsi': rsi,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size
                })
                
        else:
            position_size = self.trades[-1]['position_size']
            exit_cost = self.calculate_total_cost(price, position_size, is_entry=False, is_maker=False)
            
            # Update trailing stops
            if self.position == 1:
                self.highest_price = max(self.highest_price, price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop/100)
            else:
                self.lowest_price = min(self.lowest_price, price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop/100)
            
            # Calculate P&L including fees
            entry_fees = self.trades[-1]['entry_fees']
            exit_fees = position_size * self.taker_fee
            total_fees = entry_fees + exit_fees
            
            # Calculate raw P&L
            raw_pnl_pct = ((price - self.entry_price) / self.entry_price * 100) * (1 if self.position == 1 else -1)
            
            # Adjust P&L for fees
            fee_impact_pct = (total_fees / position_size) * 100
            actual_pnl_pct = raw_pnl_pct - fee_impact_pct
            
            # Quick exit conditions
            quick_exit_long = (
                self.position == 1 and
                (macd[-1] < signal[-1] or  # MACD cross down
                price < ema_20 or           # Price below EMA
                price_change < -0.05)       # Quick price drop
            )
            
            quick_exit_short = (
                self.position == -1 and
                (macd[-1] > signal[-1] or  # MACD cross up
                price > ema_20 or           # Price above EMA
                price_change > 0.05)        # Quick price rise
            )
            
            # Exit conditions with trailing stop
            should_exit = (
                actual_pnl_pct >= self.profit_target or
                actual_pnl_pct <= self.stop_loss or
                (self.position == 1 and price <= trailing_stop) or
                (self.position == -1 and price >= trailing_stop) or
                quick_exit_long or
                quick_exit_short
            )
            
            if should_exit:
                actual_pnl = actual_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + actual_pnl)
                
                exit_reason = (
                    "Profit Target" if actual_pnl_pct >= self.profit_target else
                    "Stop Loss" if actual_pnl_pct <= self.stop_loss else
                    "Trailing Stop" if (self.position == 1 and price <= trailing_stop) or (self.position == -1 and price >= trailing_stop) else
                    "Quick Exit"
                )
                
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': timestamp,
                    'raw_pnl_pct': raw_pnl_pct,
                    'fee_impact_pct': fee_impact_pct,
                    'actual_pnl_pct': actual_pnl_pct,
                    'pnl': actual_pnl * self.initial_capital,
                    'exit_fees': exit_fees,
                    'total_fees': total_fees,
                    'exit_reason': exit_reason
                })
                
                self.position = 0

class AggressiveMACDVolume(BaseStrategy):
    def __init__(self, initial_capital=1000):
        super().__init__("Aggressive MACD+Volume", initial_capital)
        self.volume_threshold = 1.5  # 50% above average
        self.profit_target = 1.0    # 1.0%
        self.stop_loss = -0.15     # -0.15%
        self.trailing_stop = 0.25   # 0.25%
        
    def execute_trade(self, price, volume, timestamp):
        self.prices.append(price)
        self.volumes.append(volume)
        
        if len(self.prices) < 26:
            return
            
        macd, signal = self.calculate_macd()
        volume_ratio = self.calculate_volume_ratio()
        ema_20 = self.calculate_ema(20)[-1]
        
        # Calculate momentum
        price_change = (price - self.prices[-2]) / self.prices[-2] * 100 if len(self.prices) > 1 else 0
        
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            entry_cost = self.calculate_total_cost(price, position_size, is_entry=True, is_maker=False)
            
            # Strong volume confirmation
            volume_confirmed = volume_ratio > self.volume_threshold
            
            # Long entry - Volume + MACD + Momentum
            if macd[-1] > signal[-1] and volume_confirmed and price > ema_20 and price_change > 0:
                self.position = 1
                self.entry_price = price
                self.entry_time = timestamp
                self.highest_price = price
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size,
                    'volume_ratio': volume_ratio
                })
                
            # Short entry - Volume + MACD + Momentum
            elif macd[-1] < signal[-1] and volume_confirmed and price < ema_20 and price_change < 0:
                self.position = -1
                self.entry_price = price
                self.entry_time = timestamp
                self.lowest_price = price
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size,
                    'volume_ratio': volume_ratio
                })
                
        else:
            position_size = self.trades[-1]['position_size']
            exit_cost = self.calculate_total_cost(price, position_size, is_entry=False, is_maker=False)
            
            # Update trailing stops
            if self.position == 1:
                self.highest_price = max(self.highest_price, price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop/100)
            else:
                self.lowest_price = min(self.lowest_price, price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop/100)
            
            # Calculate P&L including fees
            entry_fees = self.trades[-1]['entry_fees']
            exit_fees = position_size * self.taker_fee
            total_fees = entry_fees + exit_fees
            
            # Calculate raw P&L
            raw_pnl_pct = ((price - self.entry_price) / self.entry_price * 100) * (1 if self.position == 1 else -1)
            
            # Adjust P&L for fees
            fee_impact_pct = (total_fees / position_size) * 100
            actual_pnl_pct = raw_pnl_pct - fee_impact_pct
            
            # Quick exit conditions
            quick_exit_long = (
                self.position == 1 and
                (macd[-1] < signal[-1] or price < ema_20 or price_change < -0.05)
            )
            
            quick_exit_short = (
                self.position == -1 and
                (macd[-1] > signal[-1] or price > ema_20 or price_change > 0.05)
            )
            
            # Exit conditions with trailing stop
            should_exit = (
                actual_pnl_pct >= self.profit_target or
                actual_pnl_pct <= self.stop_loss or
                (self.position == 1 and price <= trailing_stop) or
                (self.position == -1 and price >= trailing_stop) or
                quick_exit_long or
                quick_exit_short
            )
            
            if should_exit:
                actual_pnl = actual_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + actual_pnl)
                
                exit_reason = (
                    "Profit Target" if actual_pnl_pct >= self.profit_target else
                    "Stop Loss" if actual_pnl_pct <= self.stop_loss else
                    "Trailing Stop" if (self.position == 1 and price <= trailing_stop) or (self.position == -1 and price >= trailing_stop) else
                    "Quick Exit"
                )
                
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': timestamp,
                    'raw_pnl_pct': raw_pnl_pct,
                    'fee_impact_pct': fee_impact_pct,
                    'actual_pnl_pct': actual_pnl_pct,
                    'pnl': actual_pnl * self.initial_capital,
                    'exit_fees': exit_fees,
                    'total_fees': total_fees,
                    'exit_reason': exit_reason
                })
                
                self.position = 0

class PureRSI(BaseStrategy):
    def __init__(self, initial_capital=1000):
        super().__init__("Pure RSI", initial_capital)
        self.rsi_period = 7
        self.rsi_overbought = 80
        self.rsi_oversold = 20
        self.profit_target = 0.4    # 0.4%
        self.stop_loss = -0.12     # -0.12%
        self.trailing_stop = 0.2    # 0.2%
        
    def execute_trade(self, price, volume, timestamp):
        self.prices.append(price)
        self.volumes.append(volume)
        
        if len(self.prices) < self.rsi_period + 1:
            return
            
        rsi = self.calculate_rsi(self.rsi_period)[-1]
        ema_20 = self.calculate_ema(20)[-1]
        
        # Calculate momentum
        price_change = (price - self.prices[-2]) / self.prices[-2] * 100 if len(self.prices) > 1 else 0
        
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            entry_cost = self.calculate_total_cost(price, position_size, is_entry=True, is_maker=False)
            
            # Long entry - Extreme oversold + momentum
            if rsi < self.rsi_oversold and price_change > -0.05:
                self.position = 1
                self.entry_price = price
                self.entry_time = timestamp
                self.highest_price = price
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_rsi': rsi,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size
                })
                
            # Short entry - Extreme overbought + momentum
            elif rsi > self.rsi_overbought and price_change < 0.05:
                self.position = -1
                self.entry_price = price
                self.entry_time = timestamp
                self.lowest_price = price
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_rsi': rsi,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size
                })
                
        else:
            position_size = self.trades[-1]['position_size']
            exit_cost = self.calculate_total_cost(price, position_size, is_entry=False, is_maker=False)
            
            # Update trailing stops
            if self.position == 1:
                self.highest_price = max(self.highest_price, price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop/100)
            else:
                self.lowest_price = min(self.lowest_price, price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop/100)
            
            # Calculate P&L including fees
            entry_fees = self.trades[-1]['entry_fees']
            exit_fees = position_size * self.taker_fee
            total_fees = entry_fees + exit_fees
            
            # Calculate raw P&L
            raw_pnl_pct = ((price - self.entry_price) / self.entry_price * 100) * (1 if self.position == 1 else -1)
            
            # Adjust P&L for fees
            fee_impact_pct = (total_fees / position_size) * 100
            actual_pnl_pct = raw_pnl_pct - fee_impact_pct
            
            # Quick exit conditions
            quick_exit_long = (
                self.position == 1 and
                (rsi > 70 or price < ema_20 or price_change < -0.05)
            )
            
            quick_exit_short = (
                self.position == -1 and
                (rsi < 30 or price > ema_20 or price_change > 0.05)
            )
            
            # Exit conditions with trailing stop
            should_exit = (
                actual_pnl_pct >= self.profit_target or
                actual_pnl_pct <= self.stop_loss or
                (self.position == 1 and price <= trailing_stop) or
                (self.position == -1 and price >= trailing_stop) or
                quick_exit_long or
                quick_exit_short
            )
            
            if should_exit:
                actual_pnl = actual_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + actual_pnl)
                
                exit_reason = (
                    "Profit Target" if actual_pnl_pct >= self.profit_target else
                    "Stop Loss" if actual_pnl_pct <= self.stop_loss else
                    "Trailing Stop" if (self.position == 1 and price <= trailing_stop) or (self.position == -1 and price >= trailing_stop) else
                    "Quick Exit"
                )
                
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': timestamp,
                    'raw_pnl_pct': raw_pnl_pct,
                    'fee_impact_pct': fee_impact_pct,
                    'actual_pnl_pct': actual_pnl_pct,
                    'pnl': actual_pnl * self.initial_capital,
                    'exit_fees': exit_fees,
                    'total_fees': total_fees,
                    'exit_reason': exit_reason
                })
                
                self.position = 0

class EMACrossover(BaseStrategy):
    def __init__(self, initial_capital=1000):
        super().__init__("EMA Crossover", initial_capital)
        self.ema_fast = 8
        self.ema_slow = 21
        self.volume_threshold = 1.3
        self.profit_target = 0.5    # 0.5%
        self.stop_loss = -0.15     # -0.15%
        self.trailing_stop = 0.2    # 0.2%

    def execute_trade(self, price, volume, timestamp):
        self.prices.append(price)
        self.volumes.append(volume)

        if len(self.prices) < max(self.ema_fast, self.ema_slow) + 1:
            return

        ema_fast = self.calculate_ema(self.ema_fast)[-1]
        ema_slow = self.calculate_ema(self.ema_slow)[-1]
        volume_ratio = self.calculate_volume_ratio()

        # Calculate momentum
        price_change = (price - self.prices[-2]) / self.prices[-2] * 100 if len(self.prices) > 1 else 0

        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            entry_cost = self.calculate_total_cost(price, position_size, is_entry=True, is_maker=False)

            # Strong volume confirmation
            volume_confirmed = volume_ratio > self.volume_threshold

            # Long entry - EMA crossover + volume + momentum
            if ema_fast > ema_slow and volume_confirmed and price_change > 0:
                self.position = 1
                self.entry_price = price
                self.entry_time = timestamp
                self.highest_price = price
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size,
                    'volume_ratio': volume_ratio
                })

            # Short entry - EMA crossover + volume + momentum
            elif ema_fast < ema_slow and volume_confirmed and price_change < 0:
                self.position = -1
                self.entry_price = price
                self.entry_time = timestamp
                self.lowest_price = price
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size,
                    'volume_ratio': volume_ratio
                })

        else:
            position_size = self.trades[-1]['position_size']
            exit_cost = self.calculate_total_cost(price, position_size, is_entry=False, is_maker=False)

            # Update trailing stops
            if self.position == 1:
                self.highest_price = max(self.highest_price, price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop/100)
            else:
                self.lowest_price = min(self.lowest_price, price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop/100)

            # Calculate P&L including fees
            entry_fees = self.trades[-1]['entry_fees']
            exit_fees = position_size * self.taker_fee
            total_fees = entry_fees + exit_fees

            # Calculate raw P&L
            raw_pnl_pct = ((price - self.entry_price) / self.entry_price * 100) * (1 if self.position == 1 else -1)

            # Adjust P&L for fees
            fee_impact_pct = (total_fees / position_size) * 100
            actual_pnl_pct = raw_pnl_pct - fee_impact_pct

            # Quick exit conditions
            quick_exit_long = (
                self.position == 1 and
                (ema_fast < ema_slow or price_change < -0.05)
            )

            quick_exit_short = (
                self.position == -1 and
                (ema_fast > ema_slow or price_change > 0.05)
            )

            # Exit conditions with trailing stop
            should_exit = (
                actual_pnl_pct >= self.profit_target or
                actual_pnl_pct <= self.stop_loss or
                (self.position == 1 and price <= trailing_stop) or
                (self.position == -1 and price >= trailing_stop) or
                quick_exit_long or
                quick_exit_short
            )

            if should_exit:
                actual_pnl = actual_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + actual_pnl)

                exit_reason = (
                    "Profit Target" if actual_pnl_pct >= self.profit_target else
                    "Stop Loss" if actual_pnl_pct <= self.stop_loss else
                    "Trailing Stop" if (self.position == 1 and price <= trailing_stop) or (self.position == -1 and price >= trailing_stop) else
                    "Quick Exit"
                )

                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': timestamp,
                    'raw_pnl_pct': raw_pnl_pct,
                    'fee_impact_pct': fee_impact_pct,
                    'actual_pnl_pct': actual_pnl_pct,
                    'pnl': actual_pnl * self.initial_capital,
                    'exit_fees': exit_fees,
                    'total_fees': total_fees,
                    'exit_reason': exit_reason
                })

                self.position = 0

class CombinedStrategy(BaseStrategy):
    def __init__(self, initial_capital=1000):
        super().__init__("Combined Indicators", initial_capital)
        self.rsi_period = 14
        self.rsi_overbought = 75
        self.rsi_oversold = 25
        self.volume_threshold = 1.4
        self.profit_target = 0.6    # 0.6%
        self.stop_loss = -0.15     # -0.15%
        self.trailing_stop = 0.2    # 0.2%

    def execute_trade(self, price, volume, timestamp):
        self.prices.append(price)
        self.volumes.append(volume)

        if len(self.prices) < max(self.rsi_period, 26) + 1:
            return

        rsi = self.calculate_rsi(self.rsi_period)[-1]
        macd, signal = self.calculate_macd()
        ema_20 = self.calculate_ema(20)[-1]
        volume_ratio = self.calculate_volume_ratio()

        # Calculate momentum
        price_change = (price - self.prices[-2]) / self.prices[-2] * 100 if len(self.prices) > 1 else 0

        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            entry_cost = self.calculate_total_cost(price, position_size, is_entry=True, is_maker=False)

            # Strong volume confirmation
            volume_confirmed = volume_ratio > self.volume_threshold

            # Long entry - Multiple confirmations required
            long_signal = (
                rsi < self.rsi_oversold and  # Oversold
                macd[-1] > signal[-1] and    # MACD cross up
                price > ema_20 and           # Above EMA
                price_change > -0.1 and      # Not falling too fast
                volume_confirmed
            )

            # Short entry - Multiple confirmations required
            short_signal = (
                rsi > self.rsi_overbought and  # Overbought
                macd[-1] < signal[-1] and      # MACD cross down
                price < ema_20 and             # Below EMA
                price_change < 0.1 and         # Not rising too fast
                volume_confirmed
            )

            if long_signal:
                self.position = 1
                self.entry_price = price
                self.entry_time = timestamp
                self.highest_price = price
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_rsi': rsi,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size,
                    'volume_ratio': volume_ratio
                })

            elif short_signal:
                self.position = -1
                self.entry_price = price
                self.entry_time = timestamp
                self.lowest_price = price
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_rsi': rsi,
                    'position_size': position_size,
                    'entry_fees': entry_cost - position_size,
                    'volume_ratio': volume_ratio
                })

        else:
            position_size = self.trades[-1]['position_size']
            exit_cost = self.calculate_total_cost(price, position_size, is_entry=False, is_maker=False)

            # Update trailing stops
            if self.position == 1:
                self.highest_price = max(self.highest_price, price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop/100)
            else:
                self.lowest_price = min(self.lowest_price, price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop/100)

            # Calculate P&L including fees
            entry_fees = self.trades[-1]['entry_fees']
            exit_fees = position_size * self.taker_fee
            total_fees = entry_fees + exit_fees

            # Calculate raw P&L
            raw_pnl_pct = ((price - self.entry_price) / self.entry_price * 100) * (1 if self.position == 1 else -1)

            # Adjust P&L for fees
            fee_impact_pct = (total_fees / position_size) * 100
            actual_pnl_pct = raw_pnl_pct - fee_impact_pct

            # Quick exit conditions
            quick_exit_long = (
                self.position == 1 and
                (macd[-1] < signal[-1] or  # MACD cross down
                price < ema_20 or           # Price below EMA
                price_change < -0.05)       # Quick price drop
            )

            quick_exit_short = (
                self.position == -1 and
                (macd[-1] > signal[-1] or  # MACD cross up
                price > ema_20 or           # Price above EMA
                price_change > 0.05)        # Quick price rise
            )

            # Exit conditions with trailing stop
            should_exit = (
                actual_pnl_pct >= self.profit_target or
                actual_pnl_pct <= self.stop_loss or
                (self.position == 1 and price <= trailing_stop) or
                (self.position == -1 and price >= trailing_stop) or
                quick_exit_long or
                quick_exit_short
            )

            if should_exit:
                actual_pnl = actual_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + actual_pnl)

                exit_reason = (
                    "Profit Target" if actual_pnl_pct >= self.profit_target else
                    "Stop Loss" if actual_pnl_pct <= self.stop_loss else
                    "Trailing Stop" if (self.position == 1 and price <= trailing_stop) or (self.position == -1 and price >= trailing_stop) else
                    "Quick Exit"
                )

                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': timestamp,
                    'raw_pnl_pct': raw_pnl_pct,
                    'fee_impact_pct': fee_impact_pct,
                    'actual_pnl_pct': actual_pnl_pct,
                    'pnl': actual_pnl * self.initial_capital,
                    'exit_fees': exit_fees,
                    'total_fees': total_fees,
                    'exit_reason': exit_reason
                })

                self.position = 0

class MultiStrategyTester:
    def __init__(self):
        self.strategies = [
            ConservativeRSIMACD(),
            AggressiveMACDVolume(),
            PureRSI(),
            EMACrossover(),
            CombinedStrategy()
        ]
        self.ws = None
        self.running = True
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'data' in data and isinstance(data['data'], list):
                for trade in data['data']:
                    if isinstance(trade, dict) and 'time' in trade and 'px' in trade:
                        timestamp = datetime.fromtimestamp(int(trade['time'])/1000)
                        price = float(trade['px'])
                        volume = float(trade['sz'])
                        
                        # Execute all strategies
                        for strategy in self.strategies:
                            strategy.execute_trade(price, volume, timestamp)
                        
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.info("WebSocket connection closed")

    def on_open(self, ws):
        logging.info("WebSocket connection opened")
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": "BTC"
            }
        }
        ws.send(json.dumps(subscribe_msg))

    def run(self, duration_minutes=20):
        try:
            print("\nStarting Multi-Strategy Test")
            print("="*50)
            
            for strategy in self.strategies:
                print(f"\n{strategy.name}:")
                print(f"Initial capital: ${strategy.initial_capital:,.2f}")
                print(f"Leverage: {strategy.leverage}x")
            
            # Connect to WebSocket
            websocket.enableTrace(True)
            self.ws = websocket.WebSocketApp(
                'wss://api.hyperliquid.xyz/ws',
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # Start WebSocket connection in a separate thread
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Run for specified duration
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            
            while datetime.now() < end_time and self.running:
                time.sleep(5)  # Check every 5 seconds
                print("\nCurrent Results:")
                print("="*50)
                for strategy in self.strategies:
                    print(f"\n{strategy.name}:")
                    print(f"Current capital: ${strategy.portfolio_value:,.2f}")
                    print(f"P&L: ${strategy.portfolio_value - strategy.initial_capital:,.2f}")
                    if strategy.trades:
                        print(f"Active trades: {len(strategy.trades)}")
                        for trade in strategy.trades:
                            if 'exit_price' in trade:
                                print(f"Completed trade: {trade['type']} - P&L: ${trade['pnl']:,.2f}")
            
            self.ws.close()
            
            # Final results
            print("\n" + "="*50)
            print("FINAL RESULTS")
            print("="*50)
            
            for strategy in self.strategies:
                print(f"\n{strategy.name}:")
                print(f"Final capital: ${strategy.portfolio_value:,.2f}")
                print(f"Total P&L: ${strategy.portfolio_value - strategy.initial_capital:,.2f}")
                print(f"Total trades: {len(strategy.trades)}")
                
                winning_trades = [t for t in strategy.trades if t.get('pnl', 0) > 0]
                print(f"Win rate: {len(winning_trades)/len(strategy.trades)*100:.1f}%" if strategy.trades else "No trades")
                
                total_fees = sum(t.get('total_fees', 0) for t in strategy.trades)
                print(f"Total fees: ${total_fees:,.2f}")
            
        except Exception as e:
            print(f"Error in test bot: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    tester = MultiStrategyTester()
    tester.run(duration_minutes=20)  # Run for 20 minutes
