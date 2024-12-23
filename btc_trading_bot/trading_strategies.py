import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

class BaseStrategy:
    def __init__(self, initial_capital=1000, leverage=50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        self.entry_price = 0
        self.entry_time = None
        self.portfolio_value = initial_capital
        self.trades = []
        self.price_history = []
        self.volume_history = []
        self.maker_fee = 0.0002  # 0.02%
        self.taker_fee = 0.0005  # 0.05%
    
    def calculate_fees(self, position_size, is_maker=False):
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        return position_size * fee_rate
    
    def update_history(self, price, volume):
        self.price_history.append(price)
        self.volume_history.append(volume)
        # Keep last 100 data points for calculations
        if len(self.price_history) > 100:
            self.price_history.pop(0)
            self.volume_history.pop(0)

class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, initial_capital=1000, leverage=50):
        super().__init__(initial_capital, leverage)
        self.ema_short = 8
        self.ema_long = 21
        self.min_trend_strength = 0.5  # Minimum price movement %
        self.profit_target = 1.0  # 1%
        self.stop_loss = -0.5    # -0.5%
    
    def execute_trade(self, price, current_time, volume):
        self.update_history(price, volume)
        if len(self.price_history) < self.ema_long:
            return
        
        # Calculate EMAs
        prices = pd.Series(self.price_history)
        ema_short = prices.ewm(span=self.ema_short, adjust=False).mean().iloc[-1]
        ema_long = prices.ewm(span=self.ema_long, adjust=False).mean().iloc[-1]
        
        # Calculate trend strength
        price_change = (price - self.price_history[-2]) / self.price_history[-2] * 100
        
        # Entry logic
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            
            # Long entry
            if (ema_short > ema_long and 
                price_change > self.min_trend_strength and 
                volume > np.mean(self.volume_history)):
                self.position = 1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
            
            # Short entry
            elif (ema_short < ema_long and 
                  price_change < -self.min_trend_strength and 
                  volume > np.mean(self.volume_history)):
                self.position = -1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
        
        # Exit logic
        elif self.position != 0:
            current_pnl = ((price - self.entry_price) / self.entry_price * 100) * self.position
            
            if (current_pnl >= self.profit_target or 
                current_pnl <= self.stop_loss or 
                (self.position == 1 and ema_short < ema_long) or 
                (self.position == -1 and ema_short > ema_long)):
                
                exit_reason = (
                    "Profit Target" if current_pnl >= self.profit_target else
                    "Stop Loss" if current_pnl <= self.stop_loss else
                    "Trend Reversal"
                )
                
                # Calculate P&L
                position_size = self.trades[-1]['size']
                fees = self.calculate_fees(position_size, False)
                pnl = position_size * (current_pnl / 100) - fees
                
                # Update trade record
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': current_time,
                    'pnl': pnl,
                    'pnl_pct': current_pnl,
                    'exit_reason': exit_reason,
                    'fees': fees
                })
                
                # Update portfolio
                self.portfolio_value += pnl
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class MomentumStrategy(BaseStrategy):
    def __init__(self, initial_capital=1000, leverage=50):
        super().__init__(initial_capital, leverage)
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.profit_target = 0.8  # 0.8%
        self.stop_loss = -0.4    # -0.4%
    
    def calculate_rsi(self):
        if len(self.price_history) < self.rsi_period + 1:
            return 50  # Neutral RSI
        
        prices = pd.Series(self.price_history)
        deltas = prices.diff()
        gain = deltas.clip(lower=0)
        loss = -deltas.clip(upper=0)
        
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    
    def execute_trade(self, price, current_time, volume):
        self.update_history(price, volume)
        if len(self.price_history) < self.rsi_period + 1:
            return
        
        rsi = self.calculate_rsi()
        price_change = (price - self.price_history[-2]) / self.price_history[-2] * 100
        
        # Entry logic
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            
            # Long entry
            if rsi < self.rsi_oversold and price_change > 0:
                self.position = 1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
            
            # Short entry
            elif rsi > self.rsi_overbought and price_change < 0:
                self.position = -1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
        
        # Exit logic
        elif self.position != 0:
            current_pnl = ((price - self.entry_price) / self.entry_price * 100) * self.position
            
            if (current_pnl >= self.profit_target or 
                current_pnl <= self.stop_loss or 
                (self.position == 1 and rsi > self.rsi_overbought) or 
                (self.position == -1 and rsi < self.rsi_oversold)):
                
                exit_reason = (
                    "Profit Target" if current_pnl >= self.profit_target else
                    "Stop Loss" if current_pnl <= self.stop_loss else
                    "RSI Signal"
                )
                
                # Calculate P&L
                position_size = self.trades[-1]['size']
                fees = self.calculate_fees(position_size, False)
                pnl = position_size * (current_pnl / 100) - fees
                
                # Update trade record
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': current_time,
                    'pnl': pnl,
                    'pnl_pct': current_pnl,
                    'exit_reason': exit_reason,
                    'fees': fees
                })
                
                # Update portfolio
                self.portfolio_value += pnl
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class BreakoutStrategy(BaseStrategy):
    def __init__(self, initial_capital=1000, leverage=50):
        super().__init__(initial_capital, leverage)
        self.lookback = 20
        self.breakout_threshold = 0.3  # 0.3% price movement
        self.profit_target = 0.9  # 0.9%
        self.stop_loss = -0.4    # -0.4%
    
    def execute_trade(self, price, current_time, volume):
        self.update_history(price, volume)
        if len(self.price_history) < self.lookback:
            return
        
        # Calculate price range
        recent_prices = self.price_history[-self.lookback:]
        high = max(recent_prices)
        low = min(recent_prices)
        
        # Calculate volatility
        volatility = np.std(recent_prices) / np.mean(recent_prices) * 100
        
        # Entry logic
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            
            # Long entry - breakout above recent high
            if (price > high * (1 + self.breakout_threshold/100) and 
                volume > np.mean(self.volume_history) and
                volatility > 0.1):  # Minimum volatility threshold
                self.position = 1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
            
            # Short entry - breakdown below recent low
            elif (price < low * (1 - self.breakout_threshold/100) and 
                  volume > np.mean(self.volume_history) and
                  volatility > 0.1):
                self.position = -1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
        
        # Exit logic
        elif self.position != 0:
            current_pnl = ((price - self.entry_price) / self.entry_price * 100) * self.position
            
            if current_pnl >= self.profit_target or current_pnl <= self.stop_loss:
                exit_reason = (
                    "Profit Target" if current_pnl >= self.profit_target else
                    "Stop Loss"
                )
                
                # Calculate P&L
                position_size = self.trades[-1]['size']
                fees = self.calculate_fees(position_size, False)
                pnl = position_size * (current_pnl / 100) - fees
                
                # Update trade record
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': current_time,
                    'pnl': pnl,
                    'pnl_pct': current_pnl,
                    'exit_reason': exit_reason,
                    'fees': fees
                })
                
                # Update portfolio
                self.portfolio_value += pnl
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class VolumeStrategy(BaseStrategy):
    def __init__(self, initial_capital=1000, leverage=50):
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.leverage = leverage
        self.position = 0  # -1 for short, 0 for none, 1 for long
        self.entry_price = 0
        self.entry_time = None
        self.trades = []
        self.price_history = []
        self.volume_history = []
        self.volume_ma_period = 5
        self.price_ma_period = 3
        self.volume_threshold = 1.5  # Volume spike threshold
        self.profit_target = 0.15  # 0.15%
        self.stop_loss = -0.1    # -0.1%
        self.min_trades = 5      # Start trading quickly
        self.last_trade_time = None
        self.trade_cooldown = timedelta(seconds=6)  # Target 180 trades in 20 min
    
    def update_history(self, price, volume):
        self.price_history.append(price)
        self.volume_history.append(volume)
        
        # Keep last 20 data points
        if len(self.price_history) > 20:
            self.price_history.pop(0)
            self.volume_history.pop(0)
            
    def calculate_fees(self, position_size, is_entry=True):
        # Hyperliquid fees
        maker_fee = 0.0002  # 0.02%
        taker_fee = 0.0005  # 0.05%
        return position_size * taker_fee
    
    def execute_trade(self, price, current_time, volume):
        self.update_history(price, volume)
        if len(self.price_history) < max(self.volume_ma_period, self.price_ma_period, self.min_trades):
            return
        
        # Check if enough time has passed since last trade
        if self.last_trade_time and (current_time - self.last_trade_time) < self.trade_cooldown:
            return
        
        # Calculate moving averages
        volume_ma = np.mean(self.volume_history[-self.volume_ma_period:])
        price_ma = np.mean(self.price_history[-self.price_ma_period:])
        
        # Calculate volume spike
        volume_ratio = volume / volume_ma if volume_ma > 0 else 0
        
        # Entry logic
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            
            # Long entry
            if volume_ratio > self.volume_threshold and price > price_ma:
                self.position = 1
                self.entry_price = price
                self.entry_time = current_time
                self.last_trade_time = current_time
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
            
            # Short entry
            elif volume_ratio > self.volume_threshold and price < price_ma:
                self.position = -1
                self.entry_price = price
                self.entry_time = current_time
                self.last_trade_time = current_time
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
        
        # Exit logic
        elif self.position != 0:
            current_pnl = ((price - self.entry_price) / self.entry_price * 100) * self.position
            time_in_trade = current_time - self.entry_time
            
            if (current_pnl >= self.profit_target or 
                current_pnl <= self.stop_loss or
                time_in_trade > timedelta(seconds=30) or  # Force exit after 30 seconds
                (self.position == 1 and price < price_ma) or
                (self.position == -1 and price > price_ma)):
                
                exit_reason = (
                    "Profit Target" if current_pnl >= self.profit_target else
                    "Stop Loss" if current_pnl <= self.stop_loss else
                    "Time Limit" if time_in_trade > timedelta(seconds=30) else
                    "MA Cross"
                )
                
                # Calculate P&L
                position_size = self.trades[-1]['size']
                fees = self.calculate_fees(position_size, False)
                pnl = position_size * (current_pnl / 100) - fees
                
                # Update trade record
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': current_time,
                    'pnl': pnl,
                    'pnl_pct': current_pnl,
                    'exit_reason': exit_reason,
                    'fees': fees
                })
                
                # Update portfolio
                self.portfolio_value += pnl
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class ScalpingStrategy(BaseStrategy):
    def __init__(self, initial_capital=1000, leverage=50):
        super().__init__(initial_capital, leverage)
        self.price_ma_fast = 5
        self.price_ma_slow = 15
        self.min_spread = 0.1  # 0.1% minimum spread
        self.profit_target = 0.5  # 0.5%
        self.stop_loss = -0.2    # -0.2%
        self.max_hold_time = timedelta(minutes=5)  # Maximum trade duration
    
    def execute_trade(self, price, current_time, volume):
        self.update_history(price, volume)
        if len(self.price_history) < self.price_ma_slow:
            return
        
        # Calculate moving averages
        ma_fast = np.mean(self.price_history[-self.price_ma_fast:])
        ma_slow = np.mean(self.price_history[-self.price_ma_slow:])
        
        # Calculate spread
        spread = abs(ma_fast - ma_slow) / ma_slow * 100
        
        # Entry logic
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            
            # Long entry
            if (ma_fast > ma_slow and 
                spread > self.min_spread and 
                volume > np.mean(self.volume_history)):
                self.position = 1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
            
            # Short entry
            elif (ma_fast < ma_slow and 
                  spread > self.min_spread and 
                  volume > np.mean(self.volume_history)):
                self.position = -1
                self.entry_price = price
                self.entry_time = current_time
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
        
        # Exit logic
        elif self.position != 0:
            current_pnl = ((price - self.entry_price) / self.entry_price * 100) * self.position
            time_in_trade = current_time - self.entry_time
            
            if (current_pnl >= self.profit_target or 
                current_pnl <= self.stop_loss or 
                time_in_trade >= self.max_hold_time or
                (self.position == 1 and ma_fast < ma_slow) or 
                (self.position == -1 and ma_fast > ma_slow)):
                
                exit_reason = (
                    "Profit Target" if current_pnl >= self.profit_target else
                    "Stop Loss" if current_pnl <= self.stop_loss else
                    "Time Limit" if time_in_trade >= self.max_hold_time else
                    "MA Crossover"
                )
                
                # Calculate P&L
                position_size = self.trades[-1]['size']
                fees = self.calculate_fees(position_size, False)
                pnl = position_size * (current_pnl / 100) - fees
                
                # Update trade record
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': current_time,
                    'pnl': pnl,
                    'pnl_pct': current_pnl,
                    'exit_reason': exit_reason,
                    'fees': fees
                })
                
                # Update portfolio
                self.portfolio_value += pnl
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class AggressiveScalper(BaseStrategy):
    def __init__(self, initial_capital=1000, leverage=50):
        super().__init__(initial_capital, leverage)
        self.short_ma = 5
        self.long_ma = 10
        self.profit_target = 0.15  # Quick 0.15% target
        self.stop_loss = -0.1     # Tight -0.1% stop
        self.min_trades = 10      # Start trading quickly
        self.trades_per_min = 9   # Target 9 trades per minute (180/20)
        self.last_trade_time = None
        self.trade_cooldown = timedelta(seconds=6)  # 60/9 = ~6.67 seconds between trades
        
    def execute_trade(self, price, current_time, volume):
        self.update_history(price, volume)
        if len(self.price_history) < max(self.short_ma, self.long_ma, self.min_trades):
            return
            
        # Check if enough time has passed since last trade
        if self.last_trade_time and (current_time - self.last_trade_time) < self.trade_cooldown:
            return
            
        # Calculate EMAs
        short_ema = np.mean(self.price_history[-self.short_ma:])
        long_ema = np.mean(self.price_history[-self.long_ma:])
        
        # Entry logic
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            
            # Long entry
            if short_ema > long_ema:
                self.position = 1
                self.entry_price = price
                self.entry_time = current_time
                self.last_trade_time = current_time
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
            
            # Short entry    
            elif short_ema < long_ema:
                self.position = -1
                self.entry_price = price
                self.entry_time = current_time
                self.last_trade_time = current_time
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': price,
                    'entry_time': current_time,
                    'size': position_size
                })
                
        # Exit logic
        elif self.position != 0:
            current_pnl = ((price - self.entry_price) / self.entry_price * 100) * self.position
            time_in_trade = current_time - self.entry_time
            
            if (current_pnl >= self.profit_target or 
                current_pnl <= self.stop_loss or
                time_in_trade > timedelta(seconds=30) or  # Force exit after 30 seconds
                (self.position == 1 and short_ema < long_ema) or
                (self.position == -1 and short_ema > long_ema)):
                
                exit_reason = (
                    "Profit Target" if current_pnl >= self.profit_target else
                    "Stop Loss" if current_pnl <= self.stop_loss else
                    "Time Limit" if time_in_trade > timedelta(seconds=30) else
                    "EMA Cross"
                )
                
                # Calculate P&L
                position_size = self.trades[-1]['size']
                fees = self.calculate_fees(position_size, False)
                pnl = position_size * (current_pnl / 100) - fees
                
                # Update trade record
                self.trades[-1].update({
                    'exit_price': price,
                    'exit_time': current_time,
                    'pnl': pnl,
                    'pnl_pct': current_pnl,
                    'exit_reason': exit_reason,
                    'fees': fees
                })
                
                # Update portfolio
                self.portfolio_value += pnl
                self.position = 0
                self.entry_price = 0
                self.entry_time = None
