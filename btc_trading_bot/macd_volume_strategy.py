import numpy as np
from datetime import datetime, timedelta
import logging
import pandas as pd

class MACDVolumeStrategy:
    def __init__(self, initial_capital=500, leverage=1,
                 fast_period=12, slow_period=26, signal_period=9,
                 volume_ma_period=20, volume_threshold=2.0,
                 profit_target=0.01, stop_loss=-0.005,
                 trade_cooldown=20,
                 maker_fee=-0.0002, taker_fee=0.0005,
                 max_position_size_pct=0.1):  
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Fee structure
        self.maker_fee = maker_fee  # Negative fee for maker orders (rebate)
        self.taker_fee = taker_fee
        
        # Strategy parameters
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.volume_ma_period = volume_ma_period
        self.volume_threshold = volume_threshold
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.trade_cooldown = trade_cooldown
        self.limit_order_offset = 0.0001  # 0.01% offset for limit orders
        self.max_position_size_pct = max_position_size_pct
        
        # Risk management
        self.max_daily_loss = initial_capital * 0.02  # 2% max daily loss
        self.daily_loss = 0
        self.last_reset_day = datetime.now().date()
        
        # Data storage
        self.price_data = []
        self.volume_data = []
        self.macd = []
        self.signal = []
        self.volume_ma = []
        
        # Position tracking
        self.position = 0  # 1 for long, -1 for short, 0 for no position
        self.position_size = 0
        self.entry_price = 0
        self.limit_entry_price = 0
        self.highest_price = 0
        self.lowest_price = float('inf')
        self.last_trade_time = datetime.now()
        self.start_time = datetime.now()
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0
        self.total_fees = 0
        
    def has_position(self):
        """Check if we currently have an open position"""
        return self.position != 0
        
    def calculate_fees(self, position_size, is_maker=False):
        """Calculate trading fees for a position"""
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        fee_amount = position_size * abs(fee_rate)
        return fee_amount
        
    def calculate_position_size(self, price):
        """Calculate the position size based on current capital and leverage with risk management"""
        # Reset daily loss if it's a new day
        current_day = datetime.now().date()
        if current_day != self.last_reset_day:
            self.daily_loss = 0
            self.last_reset_day = current_day
            
        # Check if we've hit daily loss limit
        if self.daily_loss <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached. Skipping trade.")
            return 0
            
        max_position = self.current_capital * self.leverage
        target_position = max_position * self.max_position_size_pct
        return min(target_position / price, max_position / price)
        
    def enter_position(self, price, side="LONG"):
        """Enter a new position with a limit order"""
        if side == "LONG":
            # Place limit buy order slightly below market
            self.limit_entry_price = price * (1 - self.limit_order_offset)
        else:  # SHORT
            # Place limit sell order slightly above market
            self.limit_entry_price = price * (1 + self.limit_order_offset)
            
        self.position_size = self.calculate_position_size(self.limit_entry_price)
        position_value = self.position_size * self.limit_entry_price
        
        # Calculate entry fee (maker fee since using limit order)
        entry_fee = position_value * abs(self.maker_fee)
        
        print(f"Opening {side} position at {self.limit_entry_price} with size {self.position_size}, fee: {entry_fee}")
        
        self.position = 1 if side == "LONG" else -1
        self.entry_price = self.limit_entry_price
        self.highest_price = self.limit_entry_price
        self.lowest_price = self.limit_entry_price
        self.last_trade_time = datetime.now()

    def update(self, price, volume):
        """Update strategy with new price and volume data"""
        # Store price and volume data
        self.price_data.append(price)
        self.volume_data.append(volume)
        
        # Wait for enough data
        if len(self.price_data) < max(self.slow_period, self.volume_ma_period):
            return
        
        # Calculate MACD
        exp1 = pd.Series(self.price_data).ewm(span=self.fast_period, adjust=False).mean()
        exp2 = pd.Series(self.price_data).ewm(span=self.slow_period, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()
        
        self.macd = macd.tolist()
        self.signal = signal.tolist()
        
        # Calculate volume moving average
        volume_series = pd.Series(self.volume_data)
        self.volume_ma = volume_series.rolling(window=self.volume_ma_period).mean().tolist()
        
        # Log indicator values periodically
        if len(self.price_data) % 100 == 0:
            logging.info(f"\nIndicator Values:")
            logging.info(f"Price: {price:.2f}")
            logging.info(f"MACD: {self.macd[-1]:.4f}")
            logging.info(f"Signal: {self.signal[-1]:.4f}")
            logging.info(f"Volume: {volume:.4f}")
            logging.info(f"Volume MA: {self.volume_ma[-1]:.4f}")
        
        # Check if we have a position
        if self.position != 0:
            # Update highest and lowest prices
            self.highest_price = max(self.highest_price, price)
            self.lowest_price = min(self.lowest_price, price)
            
            # Check for exit conditions
            self._check_exit_conditions(price)
            return
            
        # Check entry conditions
        self._check_entry_conditions(price)
        
    def _check_entry_conditions(self, price):
        """Check for entry signals"""
        if len(self.price_data) < self.slow_period + self.signal_period:
            return
            
        # Check if enough time has passed since last trade
        if self.last_trade_time and (datetime.now() - self.last_trade_time).total_seconds() < self.trade_cooldown:
            return
            
        # Get latest indicator values
        current_macd = self.macd[-1]
        current_signal = self.signal[-1]
        current_volume = self.volume_data[-1]
        current_volume_ma = self.volume_ma[-1]
        
        # Calculate volume condition
        volume_condition = current_volume > current_volume_ma * self.volume_threshold
        
        # Log entry conditions check
        logging.info(f"\nChecking Entry Conditions:")
        logging.info(f"MACD vs Signal: {current_macd:.4f} vs {current_signal:.4f}")
        logging.info(f"Volume vs Threshold: {current_volume:.4f} vs {current_volume_ma * self.volume_threshold:.4f}")
        
        # Long signal
        if current_macd > current_signal and volume_condition:
            logging.info("Long signal triggered!")
            self.enter_position(price, side="LONG")
            
        # Short signal
        elif current_macd < current_signal and volume_condition:
            logging.info("Short signal triggered!")
            self.enter_position(price, side="SHORT")
            
    def _check_exit_conditions(self, price):
        """Check if we should exit the position"""
        # Calculate unrealized P&L
        price_change = (price - self.entry_price) / self.entry_price
        if self.position < 0:  # Short position
            price_change = -price_change
            
        pnl = price_change * self.leverage * 100
        
        # Check exit conditions
        hit_profit = pnl >= self.profit_target
        hit_stop = pnl <= self.stop_loss
        macd_cross = (self.position > 0 and self.macd[-1] < self.signal[-1]) or \
                    (self.position < 0 and self.macd[-1] > self.signal[-1])
                    
        if hit_profit or hit_stop or macd_cross:
            reason = 'Profit Target' if hit_profit else 'Stop Loss' if hit_stop else 'MACD Cross'
            self.close_position(price, reason)
            
    def close_position(self, price, reason):
        """Close the current position and calculate P&L"""
        if not self.has_position():
            return
            
        try:
            pnl = 0
            if self.position > 0:
                raw_pnl_pct = (price - self.entry_price) / self.entry_price
            else:  # SHORT
                raw_pnl_pct = (self.entry_price - price) / self.entry_price

            position_value = self.position_size * self.entry_price
            raw_pnl = position_value * raw_pnl_pct * self.leverage  # Added leverage multiplier
            total_fees = position_value * (abs(self.maker_fee) + abs(self.taker_fee))
            net_pnl = raw_pnl - total_fees
            
            # Update daily loss tracking
            self.daily_loss += net_pnl

            logging.info("\nTrade Closed:")
            logging.info(f"Side: {'LONG' if self.position > 0 else 'SHORT'}")
            logging.info(f"Entry Price: {self.entry_price:.2f}")
            logging.info(f"Exit Price: {price:.2f}")
            logging.info(f"Position Size: ${position_value:,.2f}")
            logging.info(f"Raw P&L %: {raw_pnl_pct:.2%}")
            logging.info(f"Leverage: {self.leverage}x")
            logging.info(f"Net P&L: ${net_pnl:,.2f}")
            logging.info(f"Daily Loss: ${self.daily_loss:,.2f}")
            logging.info(f"Exit Reason: {reason}\n")

            self.total_pnl += net_pnl
            self.total_fees += total_fees
            
            if net_pnl > 0:
                self.winning_trades += 1
            self.total_trades += 1
            
            # Reset position variables
            self.position = 0
            self.position_size = 0
            self.entry_price = 0
            self.highest_price = 0
            self.lowest_price = float('inf')
            
        except Exception as e:
            logging.error(f"Error closing position: {e}")
            # Force position reset in case of error
            self.position = 0
            self.position_size = 0

    def print_status(self, runtime_hours):
        """Print current trading status"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        print(f"\nStatus Update - MACD Volume Strategy - Runtime: {runtime_hours:.1f} hours")
        print(f"Portfolio Value: ${self.current_capital:,.2f}")
        print(f"Total Trades: {self.total_trades}")
        
        if self.total_trades > 0:
            print(f"Win Rate: {win_rate:.1f}%")
            print(f"Total PnL: ${self.total_pnl:,.2f}")
            print(f"Total Fees: ${self.total_fees:,.2f}")
