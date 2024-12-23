import numpy as np
import pandas as pd
from datetime import datetime
import logging

class MomentumDivergenceStrategy:
    def __init__(self, initial_capital=200, leverage=50,
                 rsi_period=14,
                 ema_fast=8, ema_slow=21,
                 profit_target=0.004, stop_loss=-0.0015,  # 0.4% profit, 0.15% stop
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.rsi_period = rsi_period
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.volume_data = []
        self.rsi_values = []
        self.ema_fast_values = []
        self.ema_slow_values = []
        self.rsi_peaks = []
        self.price_peaks = []
        self.support_resistance = []
        
        # Position tracking
        self.position = 0  # 1 for long, -1 for short, 0 for none
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
        
    def calculate_rsi(self):
        """Calculate RSI and detect divergences"""
        if len(self.price_data) < self.rsi_period + 1:
            return 50, False, None
            
        prices = pd.Series(self.price_data)
        deltas = prices.diff()
        
        gain = (deltas.where(deltas > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-deltas.where(deltas < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # Store RSI peaks and price peaks for divergence
        if len(rsi) > 2:
            if rsi.iloc[-2] > rsi.iloc[-1] and rsi.iloc[-2] > rsi.iloc[-3]:
                self.rsi_peaks.append(rsi.iloc[-2])
                self.price_peaks.append(prices.iloc[-2])
                
            # Keep only last 5 peaks
            if len(self.rsi_peaks) > 5:
                self.rsi_peaks.pop(0)
                self.price_peaks.pop(0)
        
        # Check for divergence
        divergence = False
        divergence_type = None
        if len(self.rsi_peaks) >= 2:
            # Bearish divergence: Higher highs in price, lower highs in RSI
            if self.price_peaks[-1] > self.price_peaks[-2] and self.rsi_peaks[-1] < self.rsi_peaks[-2]:
                divergence = True
                divergence_type = "BEARISH"
                
            # Bullish divergence: Lower lows in price, higher lows in RSI
            elif self.price_peaks[-1] < self.price_peaks[-2] and self.rsi_peaks[-1] > self.rsi_peaks[-2]:
                divergence = True
                divergence_type = "BULLISH"
        
        return current_rsi, divergence, divergence_type
        
    def calculate_emas(self):
        """Calculate EMAs for trend confirmation"""
        if len(self.price_data) < self.ema_slow:
            return 0, 0
            
        prices = pd.Series(self.price_data)
        ema_fast = prices.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.ema_slow, adjust=False).mean()
        
        return ema_fast.iloc[-1], ema_slow.iloc[-1]
        
    def find_support_resistance(self):
        """Find recent support/resistance levels"""
        if len(self.price_data) < 50:
            return []
            
        prices = pd.Series(self.price_data[-50:])
        peaks = []
        
        for i in range(1, len(prices)-1):
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                peaks.append((i, prices[i], "R"))
            elif prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                peaks.append((i, prices[i], "S"))
                
        # Keep only significant levels (with multiple touches)
        levels = []
        for _, price, level_type in peaks:
            price_range = price * 0.001  # 0.1% range
            touches = sum(1 for p in self.price_data if abs(p - price) < price_range)
            if touches >= 2:
                levels.append((price, level_type))
                
        return levels
        
    def check_volume_confirmation(self):
        """Check for volume surge confirmation"""
        if len(self.volume_data) < 20:
            return False
            
        recent_volume = np.mean(self.volume_data[-3:])
        avg_volume = np.mean(self.volume_data[-20:])
        
        return recent_volume > (avg_volume * 1.2)
        
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
        
        # Update indicators
        rsi, divergence, divergence_type = self.calculate_rsi()
        ema_fast, ema_slow = self.calculate_emas()
        self.support_resistance = self.find_support_resistance()
        
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
            
        # Check entry conditions
        self._check_entry_conditions(price, rsi, divergence, divergence_type, ema_fast, ema_slow)
        
    def _check_entry_conditions(self, price, rsi, divergence, divergence_type, ema_fast, ema_slow):
        """Check for entry signals"""
        # Need volume confirmation
        if not self.check_volume_confirmation():
            return
            
        # Check if price is near support/resistance
        near_level = False
        level_type = None
        for level_price, l_type in self.support_resistance:
            if abs(price - level_price) < (price * 0.001):  # Within 0.1%
                near_level = True
                level_type = l_type
                break
                
        if not near_level:
            return
            
        # Enter long
        if (divergence_type == "BULLISH" and 
            level_type == "S" and 
            rsi < 40 and 
            ema_fast > ema_slow):
            
            logging.info("\nBullish setup detected!")
            logging.info(f"RSI: {rsi:.1f}")
            logging.info(f"EMAs: Fast={ema_fast:.1f}, Slow={ema_slow:.1f}")
            logging.info(f"Support level: {price:.1f}")
            self.enter_position(price, "LONG")
            
        # Enter short
        elif (divergence_type == "BEARISH" and 
              level_type == "R" and 
              rsi > 60 and 
              ema_fast < ema_slow):
              
            logging.info("\nBearish setup detected!")
            logging.info(f"RSI: {rsi:.1f}")
            logging.info(f"EMAs: Fast={ema_fast:.1f}, Slow={ema_slow:.1f}")
            logging.info(f"Resistance level: {price:.1f}")
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
