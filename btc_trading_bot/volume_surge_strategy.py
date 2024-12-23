import numpy as np
from datetime import datetime
import logging

class VolumeSurgeStrategy:
    def __init__(self, initial_capital=200, leverage=50,
                 volume_threshold=2.0,  # Volume must be 2x average
                 min_price_move=0.0005,  # 0.05% minimum move
                 profit_target=0.002, stop_loss=-0.0008,  # 0.2% profit, 0.08% stop
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.volume_threshold = volume_threshold
        self.min_price_move = min_price_move
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.volume_data = []
        self.recent_surges = []  # Track recent volume surges
        
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
        self.max_daily_loss = initial_capital * 0.1  # 10% max daily loss
        self.daily_loss = 0
        self.last_reset_day = datetime.now().date()
        self.consecutive_losses = 0
        
    def detect_volume_surge(self, volume):
        """Detect if current volume is a surge"""
        if len(self.volume_data) < 20:
            return False, 0
            
        # Calculate average volume (excluding current)
        avg_volume = np.mean(self.volume_data[-20:-1])
        volume_ratio = volume / avg_volume
        
        return volume_ratio >= self.volume_threshold, volume_ratio
        
    def detect_price_direction(self):
        """Detect price direction after volume surge"""
        if len(self.price_data) < 3:
            return "NONE", 0
            
        # Calculate recent price change
        price_change = (self.price_data[-1] - self.price_data[-2]) / self.price_data[-2]
        
        # Check if move is significant
        if abs(price_change) < self.min_price_move:
            return "NONE", price_change
            
        return "UP" if price_change > 0 else "DOWN", price_change
        
    def update(self, price, volume):
        """Update strategy with new data"""
        # Reset daily loss if new day
        current_date = datetime.now().date()
        if current_date > self.last_reset_day:
            self.daily_loss = 0
            self.last_reset_day = current_date
        
        # Store data
        self.price_data.append(price)
        self.volume_data.append(volume)
        
        # Keep data size manageable
        if len(self.price_data) > 100:
            self.price_data.pop(0)
            self.volume_data.pop(0)
        
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
        self._check_entry_conditions(price, volume)
        
    def _check_entry_conditions(self, price, volume):
        """Check for entry signals"""
        # Detect volume surge
        is_surge, volume_ratio = self.detect_volume_surge(volume)
        if not is_surge:
            return
            
        # Get price direction
        direction, price_change = self.detect_price_direction()
        if direction == "NONE":
            return
            
        # Store surge for tracking
        self.recent_surges.append({
            'price': price,
            'volume_ratio': volume_ratio,
            'direction': direction,
            'price_change': price_change
        })
        
        # Keep only recent surges
        if len(self.recent_surges) > 5:
            self.recent_surges.pop(0)
            
        # Enter long on up surge
        if direction == "UP":
            logging.info("\nBullish Volume Surge detected!")
            logging.info(f"Volume: {volume_ratio:.1f}x average")
            logging.info(f"Price change: {price_change*100:.3f}%")
            self.enter_position(price, "LONG")
            
        # Enter short on down surge
        elif direction == "DOWN":
            logging.info("\nBearish Volume Surge detected!")
            logging.info(f"Volume: {volume_ratio:.1f}x average")
            logging.info(f"Price change: {price_change*100:.3f}%")
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
