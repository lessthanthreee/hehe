import numpy as np
import pandas as pd
from datetime import datetime
import logging

class OrderBlockStrategy:
    def __init__(self, initial_capital=200, leverage=50,
                 lookback_period=30,
                 volume_threshold=1.5,  # Volume surge for order block
                 min_block_size=0.001,  # 0.1% minimum candle size
                 profit_target=0.003, stop_loss=-0.001,  # 0.3% profit, 0.1% stop
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.lookback_period = lookback_period
        self.volume_threshold = volume_threshold
        self.min_block_size = min_block_size
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.high_data = []
        self.low_data = []
        self.volume_data = []
        self.order_blocks = []  # [(price_high, price_low, volume, type)]
        
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
        self.max_daily_loss = initial_capital * 0.1
        self.daily_loss = 0
        self.last_reset_day = datetime.now().date()
        self.consecutive_losses = 0
        
    def identify_order_blocks(self):
        """Find potential order blocks based on volume and price action"""
        if len(self.price_data) < 3:
            return
            
        # Calculate average volume
        avg_volume = np.mean(self.volume_data[-20:])
        
        # Look for strong moves with high volume
        current_price = self.price_data[-1]
        prev_price = self.price_data[-2]
        prev_volume = self.volume_data[-2]
        
        # Calculate candle size
        candle_size = abs(current_price - prev_price) / prev_price
        
        # Check if it's a significant move with high volume
        if (candle_size > self.min_block_size and 
            prev_volume > (avg_volume * self.volume_threshold)):
            
            # Bullish order block (strong move up)
            if current_price > prev_price:
                block = (prev_price * 1.001, prev_price * 0.999, prev_volume, "BULL")
                self.order_blocks.append(block)
                logging.info(f"\nBullish Order Block found:")
                logging.info(f"Price range: {block[0]:.1f} - {block[1]:.1f}")
                logging.info(f"Volume: {prev_volume:.6f} ({prev_volume/avg_volume:.1f}x avg)")
                
            # Bearish order block (strong move down)
            else:
                block = (prev_price * 1.001, prev_price * 0.999, prev_volume, "BEAR")
                self.order_blocks.append(block)
                logging.info(f"\nBearish Order Block found:")
                logging.info(f"Price range: {block[0]:.1f} - {block[1]:.1f}")
                logging.info(f"Volume: {prev_volume:.6f} ({prev_volume/avg_volume:.1f}x avg)")
                
        # Keep only recent blocks
        if len(self.order_blocks) > 5:
            self.order_blocks.pop(0)
            
    def check_block_retest(self, price):
        """Check if price is retesting an order block"""
        if not self.order_blocks:
            return False, None
            
        for block in self.order_blocks:
            high, low, volume, block_type = block
            
            # Price retesting block level
            if low <= price <= high:
                # Calculate retest strength
                avg_volume = np.mean(self.volume_data[-20:])
                recent_volume = np.mean(self.volume_data[-3:])
                volume_surge = recent_volume > (avg_volume * 1.2)
                
                # Clean retest (lower volume than block)
                if recent_volume < (volume * 0.8) and volume_surge:
                    return True, block_type
                    
        return False, None
        
    def update(self, price, high, low, volume):
        """Update strategy with new data"""
        # Reset daily loss if new day
        current_date = datetime.now().date()
        if current_date > self.last_reset_day:
            self.daily_loss = 0
            self.last_reset_day = current_date
        
        # Store data
        self.price_data.append(price)
        self.high_data.append(high)
        self.low_data.append(low)
        self.volume_data.append(volume)
        
        # Keep data size manageable
        if len(self.price_data) > self.lookback_period:
            self.price_data.pop(0)
            self.high_data.pop(0)
            self.low_data.pop(0)
            self.volume_data.pop(0)
        
        # Look for new order blocks
        self.identify_order_blocks()
        
        # Check for exit conditions first
        if self.position != 0:
            self._check_exit_conditions(price)
            return
            
        # Skip if max daily loss reached
        if abs(self.daily_loss) >= self.max_daily_loss:
            logging.warning(f"Max daily loss reached: ${self.daily_loss:.2f}")
            return
            
        # Skip if too many consecutive losses
        if self.consecutive_losses >= 3:
            logging.warning(f"Too many consecutive losses: {self.consecutive_losses}")
            return
            
        # Check for entries
        self._check_entry_conditions(price)
        
    def _check_entry_conditions(self, price):
        """Check for entry signals"""
        # Check if price is retesting an order block
        retest, block_type = self.check_block_retest(price)
        if not retest:
            return
            
        # Enter long at bullish block
        if block_type == "BULL":
            logging.info("\nBullish Order Block retest!")
            logging.info(f"Current price: {price:.1f}")
            self.enter_position(price, "LONG")
            
        # Enter short at bearish block
        elif block_type == "BEAR":
            logging.info("\nBearish Order Block retest!")
            logging.info(f"Current price: {price:.1f}")
            self.enter_position(price, "SHORT")
            
    def _check_exit_conditions(self, price):
        """Check for exit conditions"""
        if not self.position:
            return
            
        price_change = (price - self.entry_price) / self.entry_price
        if self.position < 0:  # Short position
            price_change = -price_change
            
        # Take profit
        if price_change >= self.profit_target:
            self.close_position(price, "Take Profit")
            
        # Stop loss
        elif price_change <= self.stop_loss:
            self.close_position(price, "Stop Loss")
            
    def enter_position(self, price, side):
        """Enter a new position"""
        if self.position != 0:
            return
            
        try:
            # Calculate position size (20% of capital)
            position_value = self.current_capital * 0.2 * self.leverage
            position_size = position_value / price
            
            self.position = 1 if side == "LONG" else -1
            self.position_size = position_size
            self.entry_price = price
            self.last_trade_time = datetime.now()
            
            logging.info(f"\nEntering {side} position:")
            logging.info(f"Price: {price:.2f}")
            logging.info(f"Size: {position_size:.6f} BTC")
            logging.info(f"Leverage: {self.leverage}x")
            
        except Exception as e:
            logging.error(f"Error entering position: {e}")
            self.position = 0
            self.position_size = 0
            
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
            
            # Track consecutive losses
            if net_pnl > 0:
                self.winning_trades += 1
                self.consecutive_losses = 0
            else:
                self.consecutive_losses += 1
                
            logging.info(f"\nClosing position - {reason}:")
            logging.info(f"Entry: {self.entry_price:.2f}")
            logging.info(f"Exit: {price:.2f}")
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
