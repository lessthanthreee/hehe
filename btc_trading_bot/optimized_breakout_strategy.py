import numpy as np
import pandas as pd
from datetime import datetime
import logging

class OptimizedBreakoutStrategy:
    def __init__(self, initial_capital=200, leverage=50,
                 lookback_period=20,  # Super short lookback
                 num_touches=1,  # Single touch
                 breakout_threshold=0.0003,  # 0.03% breakout
                 profit_target=0.003, stop_loss=-0.0008,  # 0.3% profit, 0.08% stop loss
                 momentum_period=14,
                 trade_cooldown=0,
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
        self.momentum_period = momentum_period
        self.trade_cooldown = trade_cooldown
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.high_data = []
        self.low_data = []
        self.volume_data = []
        self.support_levels = []
        self.resistance_levels = []
        self.level_touches = {}
        self.rsi_values = []
        self.ema_fast = []  # 8 EMA
        self.ema_slow = []  # 21 EMA
        
        # Position tracking
        self.position = 0
        self.position_size = 0
        self.entry_price = 0
        self.last_trade_time = datetime.now()
        self.consecutive_losses = 0
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0
        self.total_fees = 0
        self.start_time = datetime.now()
        
        # Risk management
        self.max_daily_loss = initial_capital * 0.15  # 15% max daily loss
        self.daily_loss = 0
        self.last_reset_day = datetime.now().date()
        
    def find_support_resistance(self):
        """Find support and resistance levels with volume confirmation"""
        if len(self.price_data) < self.lookback_period:
            return
            
        # Convert to pandas for easier calculation
        highs = pd.Series(self.high_data[-self.lookback_period:])
        lows = pd.Series(self.low_data[-self.lookback_period:])
        volumes = pd.Series(self.volume_data[-self.lookback_period:])
        
        # Find local minima and maxima with volume confirmation
        resistance_levels = []
        support_levels = []
        
        for i in range(2, len(highs)-2):
            # Volume confirmation (current volume > average)
            vol_confirm = volumes[i] > volumes[i-5:i+5].mean()
            
            # Resistance levels
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2] and vol_confirm:
                resistance_levels.append(highs[i])
                
            # Support levels
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2] and vol_confirm:
                support_levels.append(lows[i])
        
        # Group close levels together
        self.resistance_levels = self.group_levels(resistance_levels)
        self.support_levels = self.group_levels(support_levels)
        
        # Update level touches
        current_price = self.price_data[-1]
        self.update_level_touches(current_price)
        
    def update_level_touches(self, price):
        """Update the number of times price touches each level"""
        touch_threshold = 0.001  # 0.1% distance considered a touch
        
        # Update resistance touches
        for level in self.resistance_levels:
            level_key = f"R_{level:.0f}"
            if abs(price - level) / level < touch_threshold:
                self.level_touches[level_key] = self.level_touches.get(level_key, 0) + 1
                
        # Update support touches
        for level in self.support_levels:
            level_key = f"S_{level:.0f}"
            if abs(price - level) / level < touch_threshold:
                self.level_touches[level_key] = self.level_touches.get(level_key, 0) + 1
        
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
                # Use volume-weighted average for level
                grouped.append(sum(current_group) / len(current_group))
                current_group = [level]
                
        grouped.append(sum(current_group) / len(current_group))
        return grouped
        
    def calculate_position_size(self, price):
        """Calculate position size with risk management"""
        if self.daily_loss <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached. No new trades.")
            return 0
            
        # Scale position size based on level strength but more conservative with 50x
        base_size = 0.2  # Reduced to 20% of capital for higher leverage
        level_multiplier = min(1.3, 1 + (self.current_level_touches * 0.1))  # Max 30% increase
        position_value = self.current_capital * base_size * level_multiplier * self.leverage
        return position_value / price
        
    def calculate_rsi(self):
        """Calculate RSI indicator"""
        if len(self.price_data) < self.momentum_period + 1:
            return 50  # Default to neutral
            
        prices = pd.Series(self.price_data)
        deltas = prices.diff()
        
        gain = (deltas.where(deltas > 0, 0)).rolling(window=self.momentum_period).mean()
        loss = (-deltas.where(deltas < 0, 0)).rolling(window=self.momentum_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]

    def calculate_ema(self):
        """Calculate EMA indicators"""
        if len(self.price_data) < 21:
            return 0, 0
            
        prices = pd.Series(self.price_data)
        self.ema_fast = prices.ewm(span=8, adjust=False).mean()
        self.ema_slow = prices.ewm(span=21, adjust=False).mean()
        
        return self.ema_fast.iloc[-1], self.ema_slow.iloc[-1]
        
    def update(self, price, high, low, volume):
        """Update strategy with new price data"""
        self.price_data.append(price)
        self.high_data.append(high)
        self.low_data.append(low)
        self.volume_data.append(volume)
        
        # Reset daily loss if it's a new day
        current_day = datetime.now().date()
        if current_day != self.last_reset_day:
            self.daily_loss = 0
            self.last_reset_day = current_day
        
        # Wait for enough data
        if len(self.price_data) < self.lookback_period:
            return
            
        # Update support and resistance levels
        self.find_support_resistance()
        
        # Log levels periodically
        if len(self.price_data) % 100 == 0:
            logging.info(f"\nPrice: {price:.2f}")
            logging.info(f"Support levels: {[f'{x:.2f}' for x in self.support_levels]}")
            logging.info(f"Resistance levels: {[f'{x:.2f}' for x in self.resistance_levels]}")
            logging.info(f"Level touches: {dict(sorted(self.level_touches.items()))}")
        
        # Check position management
        if self.position != 0:
            self._check_exit_conditions(price)
        else:
            self._check_entry_conditions(price, volume)
            
    def _check_entry_conditions(self, price, volume):
        """Check for entry signals with improved confirmation"""
        # Volume confirmation - even lower to 1.05x
        avg_volume = np.mean(self.volume_data[-20:])
        volume_surge = volume > (avg_volume * 1.05)
        
        if not volume_surge:
            return
            
        # Calculate indicators
        rsi = self.calculate_rsi()
        ema_fast, ema_slow = self.calculate_ema()
        
        # Find closest levels
        closest_support = min(self.support_levels, key=lambda x: abs(x - price)) if self.support_levels else None
        closest_resistance = min(self.resistance_levels, key=lambda x: abs(x - price)) if self.resistance_levels else None
        
        if not closest_support or not closest_resistance:
            return
            
        # Check level strength
        support_touches = self.level_touches.get(f"S_{closest_support:.0f}", 0)
        resistance_touches = self.level_touches.get(f"R_{closest_resistance:.0f}", 0)
        
        # Calculate breakout conditions
        support_breakout = (price < closest_support * (1 - self.breakout_threshold))
        resistance_breakout = (price > closest_resistance * (1 + self.breakout_threshold))
        
        # Store touches for position sizing
        self.current_level_touches = max(support_touches, resistance_touches)
        
        # Check consecutive losses
        if self.consecutive_losses >= 3:
            logging.warning(f"Skipping trade due to {self.consecutive_losses} consecutive losses")
            return
            
        # Enter with momentum and trend confirmation
        if resistance_breakout and resistance_touches >= self.num_touches and rsi > 50 and ema_fast > ema_slow:
            logging.info(f"\nResistance breakout detected!")
            logging.info(f"Level: {closest_resistance:.2f}")
            logging.info(f"Touches: {resistance_touches}")
            logging.info(f"Volume surge: {volume/avg_volume:.1f}x")
            logging.info(f"RSI: {rsi:.1f}")
            logging.info(f"EMAs: Fast={ema_fast:.1f}, Slow={ema_slow:.1f}")
            self.enter_position(price, "LONG")
            
        elif support_breakout and support_touches >= self.num_touches and rsi < 50 and ema_fast < ema_slow:
            logging.info(f"\nSupport breakout detected!")
            logging.info(f"Level: {closest_support:.2f}")
            logging.info(f"Touches: {support_touches}")
            logging.info(f"Volume surge: {volume/avg_volume:.1f}x")
            logging.info(f"RSI: {rsi:.1f}")
            logging.info(f"EMAs: Fast={ema_fast:.1f}, Slow={ema_slow:.1f}")
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
            
            # Track consecutive losses
            if net_pnl > 0:
                self.winning_trades += 1
                self.consecutive_losses = 0
            else:
                self.consecutive_losses += 1
                
            logging.info(f"\nClosing position - {reason}:")
            logging.info(f"Entry Price: {self.entry_price:.2f}")
            logging.info(f"Exit Price: {price:.2f}")
            logging.info(f"Position Size: {self.position_size:.6f} BTC")
            logging.info(f"Leverage: {self.leverage}x")
            logging.info(f"P&L: ${net_pnl:.2f}")
            logging.info(f"Fees: ${total_fees:.2f}")
            logging.info(f"New Capital: ${self.current_capital:.2f}")
            logging.info(f"Consecutive Losses: {self.consecutive_losses}")
            
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
