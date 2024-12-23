import numpy as np
import pandas as pd
from datetime import datetime
import logging
from collections import defaultdict

class VolumeProfileStrategy:
    def __init__(self, initial_capital=200, leverage=20,
                 volume_period=30, price_levels=50,
                 volume_threshold=2.0,
                 profit_target=0.006, stop_loss=-0.003,  # 0.6% profit, 0.3% stop loss
                 trade_cooldown=45,
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.volume_period = volume_period
        self.price_levels = price_levels
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
        self.volume_profile = defaultdict(float)
        self.poc_price = None  # Point of Control price
        self.value_area = []  # 70% of volume range
        
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
        
    def update_volume_profile(self):
        """Update volume profile analysis"""
        if len(self.price_data) < self.volume_period:
            return
            
        # Get recent price and volume data
        recent_prices = np.array(self.price_data[-self.volume_period:])
        recent_volumes = np.array(self.volume_data[-self.volume_period:])
        
        # Create price levels
        price_range = recent_prices.max() - recent_prices.min()
        level_height = price_range / self.price_levels
        
        # Reset volume profile
        self.volume_profile.clear()
        
        # Build volume profile
        for price, volume in zip(recent_prices, recent_volumes):
            level = int((price - recent_prices.min()) / level_height)
            self.volume_profile[level] += volume
            
        # Find Point of Control (price level with highest volume)
        max_volume_level = max(self.volume_profile.items(), key=lambda x: x[1])[0]
        self.poc_price = recent_prices.min() + (max_volume_level * level_height)
        
        # Calculate Value Area (70% of total volume)
        total_volume = sum(self.volume_profile.values())
        target_volume = total_volume * 0.7
        current_volume = 0
        levels = sorted(self.volume_profile.items(), key=lambda x: x[1], reverse=True)
        
        value_area_levels = []
        for level, volume in levels:
            current_volume += volume
            value_area_levels.append(level)
            if current_volume >= target_volume:
                break
                
        # Convert levels to prices
        min_level = min(value_area_levels)
        max_level = max(value_area_levels)
        self.value_area = [
            recent_prices.min() + (min_level * level_height),
            recent_prices.min() + (max_level * level_height)
        ]
        
    def calculate_position_size(self, price):
        """Calculate position size with risk management"""
        if self.daily_loss <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached. No new trades.")
            return 0
            
        # Use 25% of available capital per trade
        position_value = self.current_capital * 0.25 * self.leverage
        return position_value / price
        
    def update(self, price, volume):
        """Update strategy with new price and volume data"""
        self.price_data.append(price)
        self.volume_data.append(volume)
        
        # Wait for enough data
        if len(self.price_data) < self.volume_period:
            return
            
        # Update volume profile
        self.update_volume_profile()
        
        # Log profile data periodically
        if len(self.price_data) % 50 == 0:
            logging.info(f"\nPrice: {price:.2f}")
            logging.info(f"POC: {self.poc_price:.2f}")
            logging.info(f"Value Area: [{self.value_area[0]:.2f}, {self.value_area[1]:.2f}]")
            logging.info(f"Current Volume: {volume:.4f}")
        
        # Check position management
        if self.position != 0:
            self._check_exit_conditions(price)
        else:
            self._check_entry_conditions(price)
            
    def _check_entry_conditions(self, price):
        """Check for entry signals"""
        if not self.poc_price or not self.value_area:
            return
            
        # Check trade cooldown
        if (datetime.now() - self.last_trade_time).total_seconds() < self.trade_cooldown:
            return
            
        # Calculate volume conditions
        current_volume = self.volume_data[-1]
        avg_volume = np.mean(self.volume_data[-self.volume_period:])
        volume_surge = current_volume > (avg_volume * self.volume_threshold)
        
        # Price relative to value area
        above_value_area = price > self.value_area[1]
        below_value_area = price < self.value_area[0]
        
        # Entry conditions
        if volume_surge:
            if above_value_area:
                self.enter_position(price, "LONG")
            elif below_value_area:
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
        
        # Value area reversal
        if self.position > 0:
            value_area_reversal = price < self.value_area[0]
        else:
            value_area_reversal = price > self.value_area[1]
        
        if hit_profit or hit_stop or value_area_reversal:
            reason = 'Profit Target' if hit_profit else 'Stop Loss' if hit_stop else 'Value Area Reversal'
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
