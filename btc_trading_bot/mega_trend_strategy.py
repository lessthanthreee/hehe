import numpy as np
import pandas as pd
from datetime import datetime
import logging

class MegaTrendStrategy:
    def __init__(self, initial_capital=200, leverage=50,  # High leverage for strong trends
                 ema_fast=8, ema_medium=21, ema_slow=55,
                 volume_ma_period=30, volume_threshold=3.0,
                 profit_target=0.015, stop_loss=-0.005,  # 1.5% profit, 0.5% stop loss
                 trade_cooldown=3600,  # 1 hour cooldown
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.ema_fast = ema_fast
        self.ema_medium = ema_medium
        self.ema_slow = ema_slow
        self.volume_ma_period = volume_ma_period
        self.volume_threshold = volume_threshold
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.trade_cooldown = trade_cooldown
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.volume_data = []
        self.ema_fast_values = []
        self.ema_medium_values = []
        self.ema_slow_values = []
        self.volume_ma = []
        
        # Trend strength indicators
        self.trend_strength = 0  # 0 to 100
        self.consecutive_signals = 0
        
        # Position tracking
        self.position = 0
        self.position_size = 0
        self.entry_price = 0
        self.last_trade_time = datetime.now()
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0
        self.total_fees = 0
        self.start_time = datetime.now()
        
        # Risk management
        self.max_daily_loss = initial_capital * 0.10  # 10% max daily loss (aggressive)
        self.daily_loss = 0
        self.last_reset_day = datetime.now().date()
        
    def calculate_emas(self):
        """Calculate EMAs"""
        prices = pd.Series(self.price_data)
        self.ema_fast_values = prices.ewm(span=self.ema_fast, adjust=False).mean()
        self.ema_medium_values = prices.ewm(span=self.ema_medium, adjust=False).mean()
        self.ema_slow_values = prices.ewm(span=self.ema_slow, adjust=False).mean()
        
    def calculate_trend_strength(self):
        """Calculate trend strength (0-100)"""
        if len(self.price_data) < self.ema_slow:
            return 0
            
        # EMA alignment score (50%)
        ema_aligned = (self.ema_fast_values.iloc[-1] > self.ema_medium_values.iloc[-1] > self.ema_slow_values.iloc[-1])
        ema_score = 50 if ema_aligned else 0
        
        # Volume strength score (30%)
        volume_ratio = self.volume_data[-1] / np.mean(self.volume_data[-self.volume_ma_period:])
        volume_score = min(30, volume_ratio * 10)
        
        # Price momentum score (20%)
        price_change = (self.price_data[-1] / self.price_data[-20] - 1) * 100
        momentum_score = min(20, max(0, price_change * 4))
        
        self.trend_strength = ema_score + volume_score + momentum_score
        return self.trend_strength
        
    def calculate_position_size(self, price):
        """Calculate position size with risk management"""
        if self.daily_loss <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached. No new trades.")
            return 0
            
        # Scale position size with trend strength
        base_size = 0.4  # Base size 40% of capital
        trend_multiplier = self.trend_strength / 100  # 0 to 1
        position_value = self.current_capital * base_size * trend_multiplier * self.leverage
        return position_value / price
        
    def update(self, price, volume):
        """Update strategy with new price and volume data"""
        self.price_data.append(price)
        self.volume_data.append(volume)
        
        # Wait for enough data
        if len(self.price_data) < self.ema_slow:
            return
            
        # Update indicators
        self.calculate_emas()
        self.calculate_trend_strength()
        
        # Log indicator values periodically
        if len(self.price_data) % 100 == 0:
            logging.info(f"\nMega Trend Indicators:")
            logging.info(f"Price: {price:.2f}")
            logging.info(f"Trend Strength: {self.trend_strength:.1f}")
            logging.info(f"Fast EMA: {self.ema_fast_values.iloc[-1]:.2f}")
            logging.info(f"Medium EMA: {self.ema_medium_values.iloc[-1]:.2f}")
            logging.info(f"Slow EMA: {self.ema_slow_values.iloc[-1]:.2f}")
        
        # Check position management
        if self.position != 0:
            self._check_exit_conditions(price)
        else:
            self._check_entry_conditions(price)
            
    def _check_entry_conditions(self, price):
        """Check for mega trend entry signals"""
        if (datetime.now() - self.last_trade_time).total_seconds() < self.trade_cooldown:
            return
            
        # Only enter if trend strength is very high
        if self.trend_strength < 80:  # Need very strong trend
            return
            
        # Check EMA alignment
        if (self.ema_fast_values.iloc[-1] > self.ema_medium_values.iloc[-1] > 
            self.ema_slow_values.iloc[-1]):
            self.consecutive_signals += 1
            
            # Need multiple consecutive signals
            if self.consecutive_signals >= 3:
                logging.info(f"\nMega Trend Detected!")
                logging.info(f"Trend Strength: {self.trend_strength:.1f}")
                self.enter_position(price, "LONG")
        else:
            self.consecutive_signals = 0
            
    def enter_position(self, price, side):
        """Enter a new position"""
        self.position_size = self.calculate_position_size(price)
        if self.position_size == 0:
            return
            
        self.position = 1 if side == "LONG" else -1
        self.entry_price = price
        self.last_trade_time = datetime.now()
        
        position_value = self.position_size * price
        entry_fee = position_value * abs(self.maker_fee)
        
        logging.info(f"\nEntering {side} Mega Trend position:")
        logging.info(f"Price: {price:.2f}")
        logging.info(f"Size: {self.position_size:.6f} BTC")
        logging.info(f"Value: ${position_value:.2f}")
        logging.info(f"Leverage: {self.leverage}x")
        logging.info(f"Fee: ${entry_fee:.2f}")
        
    def _check_exit_conditions(self, price):
        """Check exit conditions"""
        if not self.position:
            return
            
        # Calculate unrealized P&L
        price_change = (price - self.entry_price) / self.entry_price
        if self.position < 0:
            price_change = -price_change
            
        pnl = price_change * self.leverage
        
        # Exit conditions
        hit_profit = pnl >= self.profit_target
        hit_stop = pnl <= self.stop_loss
        
        # Trend reversal
        trend_reversal = self.trend_strength < 50 or \
                        self.ema_fast_values.iloc[-1] < self.ema_medium_values.iloc[-1]
        
        if hit_profit or hit_stop or trend_reversal:
            reason = 'Profit Target' if hit_profit else 'Stop Loss' if hit_stop else 'Trend Reversal'
            self.close_position(price, reason)
            
    def close_position(self, price, reason):
        """Close the current position"""
        if not self.position:
            return
            
        try:
            # Calculate P&L
            price_change = (price - self.entry_price) / self.entry_price
            if self.position < 0:
                price_change = -price_change
                
            position_value = self.position_size * self.entry_price
            raw_pnl = position_value * price_change * self.leverage
            total_fees = position_value * (abs(self.maker_fee) + abs(self.taker_fee))
            net_pnl = raw_pnl - total_fees
            
            # Update capital and daily loss tracking
            self.current_capital += net_pnl
            self.daily_loss += net_pnl
            
            # Update performance metrics
            self.total_pnl += net_pnl
            self.total_fees += total_fees
            self.total_trades += 1
            if net_pnl > 0:
                self.winning_trades += 1
                
            logging.info(f"\nClosing Mega Trend position - {reason}:")
            logging.info(f"Entry Price: {self.entry_price:.2f}")
            logging.info(f"Exit Price: {price:.2f}")
            logging.info(f"Position Size: {self.position_size:.6f} BTC")
            logging.info(f"Leverage: {self.leverage}x")
            logging.info(f"P&L: ${net_pnl:.2f}")
            logging.info(f"Fees: ${total_fees:.2f}")
            logging.info(f"New Capital: ${self.current_capital:.2f}")
            
            # Reset position and signals
            self.position = 0
            self.position_size = 0
            self.entry_price = 0
            self.consecutive_signals = 0
            
        except Exception as e:
            logging.error(f"Error closing position: {e}")
            self.position = 0
            self.position_size = 0
            
    def get_metrics(self):
        """Get current performance metrics"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        return {
            'total_trades': self.total_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'total_fees': self.total_fees,
            'current_capital': self.current_capital
        }
