import numpy as np
import pandas as pd
from datetime import datetime
import logging

class SupportResistanceStrategy:
    def __init__(self, initial_capital=200, leverage=20,
                 lookback_period=100, num_touches=3,
                 breakout_threshold=0.0015,  # 0.15% breakout confirmation
                 profit_target=0.008, stop_loss=-0.004,  # 0.8% profit, 0.4% stop loss
                 trade_cooldown=60,
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.lookback_period = lookback_period
        self.num_touches = num_touches
        self.breakout_threshold = breakout_threshold
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.trade_cooldown = trade_cooldown
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.high_data = []
        self.low_data = []
        self.support_levels = []
        self.resistance_levels = []
        
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
        self.max_daily_loss = initial_capital * 0.05  # 5% max daily loss
        self.daily_loss = 0
        self.last_reset_day = datetime.now().date()
        
    def find_support_resistance(self):
        """Find support and resistance levels"""
        if len(self.price_data) < self.lookback_period:
            return
            
        # Convert to pandas for easier calculation
        highs = pd.Series(self.high_data[-self.lookback_period:])
        lows = pd.Series(self.low_data[-self.lookback_period:])
        
        # Find local minima and maxima
        resistance_levels = []
        support_levels = []
        
        for i in range(2, len(highs)-2):
            # Resistance levels
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance_levels.append(highs[i])
                
            # Support levels
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support_levels.append(lows[i])
        
        # Group close levels together
        self.resistance_levels = self.group_levels(resistance_levels)
        self.support_levels = self.group_levels(support_levels)
        
    def group_levels(self, levels, threshold=0.002):
        """Group price levels that are close together"""
        if not levels:
            return []
            
        levels = sorted(levels)
        grouped = []
        current_group = [levels[0]]
        
        for level in levels[1:]:
            if (level - current_group[-1]) / current_group[-1] <= threshold:
                current_group.append(level)
            else:
                grouped.append(sum(current_group) / len(current_group))
                current_group = [level]
                
        grouped.append(sum(current_group) / len(current_group))
        return grouped
        
    def calculate_position_size(self, price):
        """Calculate position size with risk management"""
        if self.daily_loss <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached. No new trades.")
            return 0
            
        # Use 30% of available capital per trade
        position_value = self.current_capital * 0.3 * self.leverage
        return position_value / price
        
    def update(self, price, high, low):
        """Update strategy with new price data"""
        self.price_data.append(price)
        self.high_data.append(high)
        self.low_data.append(low)
        
        # Wait for enough data
        if len(self.price_data) < self.lookback_period:
            return
            
        # Update support and resistance levels
        self.find_support_resistance()
        
        # Log levels periodically
        if len(self.price_data) % 50 == 0:
            logging.info(f"\nPrice: {price:.2f}")
            logging.info(f"Support levels: {[f'{x:.2f}' for x in self.support_levels]}")
            logging.info(f"Resistance levels: {[f'{x:.2f}' for x in self.resistance_levels]}")
        
        # Check position management
        if self.position != 0:
            self._check_exit_conditions(price)
        else:
            self._check_entry_conditions(price)
            
    def _check_entry_conditions(self, price):
        """Check for entry signals"""
        if not self.support_levels or not self.resistance_levels:
            return
            
        # Check trade cooldown
        if (datetime.now() - self.last_trade_time).total_seconds() < self.trade_cooldown:
            return
            
        # Find closest levels
        closest_support = min(self.support_levels, key=lambda x: abs(x - price))
        closest_resistance = min(self.resistance_levels, key=lambda x: abs(x - price))
        
        # Calculate breakout conditions
        support_breakout = (price < closest_support * (1 - self.breakout_threshold))
        resistance_breakout = (price > closest_resistance * (1 + self.breakout_threshold))
        
        # Volume confirmation (could add volume analysis here)
        
        if resistance_breakout:
            self.enter_position(price, "LONG")
        elif support_breakout:
            self.enter_position(price, "SHORT")
            
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
        
        logging.info(f"\nEntering {side} position:")
        logging.info(f"Price: {price:.2f}")
        logging.info(f"Size: {self.position_size:.4f}")
        logging.info(f"Value: ${position_value:.2f}")
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
        
        # Level reversal conditions
        if self.position > 0:
            level_reversal = any(price < level for level in self.support_levels)
        else:
            level_reversal = any(price > level for level in self.resistance_levels)
        
        if hit_profit or hit_stop or level_reversal:
            reason = 'Profit Target' if hit_profit else 'Stop Loss' if hit_stop else 'Level Reversal'
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
                
            logging.info(f"\nClosing position - {reason}:")
            logging.info(f"Entry Price: {self.entry_price:.2f}")
            logging.info(f"Exit Price: {price:.2f}")
            logging.info(f"Position Size: {self.position_size:.6f} BTC")
            logging.info(f"Leverage: {self.leverage}x")
            logging.info(f"P&L: ${net_pnl:.2f}")
            logging.info(f"Fees: ${total_fees:.2f}")
            logging.info(f"New Capital: ${self.current_capital:.2f}")
            
            # Reset position
            self.position = 0
            self.position_size = 0
            self.entry_price = 0
            
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
