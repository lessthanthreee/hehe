import numpy as np
import pandas as pd
from datetime import datetime
import logging

class RSIBollingerStrategy:
    def __init__(self, initial_capital=200, leverage=20,
                 rsi_period=9, bollinger_period=20, bollinger_std=2.0,
                 rsi_oversold=30, rsi_overbought=70,
                 profit_target=0.005, stop_loss=-0.003,  # 0.5% profit, 0.3% stop loss
                 trade_cooldown=30,
                 maker_fee=-0.0002, taker_fee=0.0005):
        
        # Account settings
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.leverage = leverage
        
        # Strategy parameters
        self.rsi_period = rsi_period
        self.bollinger_period = bollinger_period
        self.bollinger_std = bollinger_std
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.trade_cooldown = trade_cooldown
        
        # Fee structure
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        # Data storage
        self.price_data = []
        self.rsi_values = []
        self.upper_band = []
        self.lower_band = []
        self.sma = []
        
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
        
    def calculate_rsi(self):
        """Calculate RSI values"""
        prices = pd.Series(self.price_data)
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    def calculate_bollinger_bands(self):
        """Calculate Bollinger Bands"""
        prices = pd.Series(self.price_data)
        self.sma = prices.rolling(window=self.bollinger_period).mean()
        std = prices.rolling(window=self.bollinger_period).std()
        self.upper_band = self.sma + (std * self.bollinger_std)
        self.lower_band = self.sma - (std * self.bollinger_std)
        
    def calculate_position_size(self, price):
        """Calculate position size with risk management"""
        if self.daily_loss <= -self.max_daily_loss:
            logging.warning("Daily loss limit reached. No new trades.")
            return 0
            
        # Use 20% of available capital per trade
        position_value = self.current_capital * 0.2 * self.leverage
        return position_value / price
        
    def update(self, price):
        """Update strategy with new price data"""
        self.price_data.append(price)
        
        # Wait for enough data
        if len(self.price_data) < max(self.rsi_period, self.bollinger_period):
            return
            
        # Calculate indicators
        self.rsi_values = self.calculate_rsi()
        self.calculate_bollinger_bands()
        
        # Log indicator values periodically
        if len(self.price_data) % 50 == 0:
            logging.info(f"\nPrice: {price:.2f}")
            logging.info(f"RSI: {self.rsi_values.iloc[-1]:.2f}")
            logging.info(f"BB Upper: {self.upper_band.iloc[-1]:.2f}")
            logging.info(f"BB Lower: {self.lower_band.iloc[-1]:.2f}")
        
        # Check position management
        if self.position != 0:
            self._check_exit_conditions(price)
        else:
            self._check_entry_conditions(price)
            
    def _check_entry_conditions(self, price):
        """Check for entry signals"""
        if not self.rsi_values.iloc[-1] or not self.upper_band.iloc[-1]:
            return
            
        # Check trade cooldown
        if (datetime.now() - self.last_trade_time).total_seconds() < self.trade_cooldown:
            return
            
        rsi = self.rsi_values.iloc[-1]
        upper_band = self.upper_band.iloc[-1]
        lower_band = self.lower_band.iloc[-1]
        
        # Long signal: RSI oversold + price below lower band
        if rsi < self.rsi_oversold and price < lower_band:
            self.enter_position(price, "LONG")
            
        # Short signal: RSI overbought + price above upper band
        elif rsi > self.rsi_overbought and price > upper_band:
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
        
        # RSI reversal conditions
        rsi = self.rsi_values.iloc[-1]
        rsi_reversal = (self.position > 0 and rsi > self.rsi_overbought) or \
                      (self.position < 0 and rsi < self.rsi_oversold)
        
        if hit_profit or hit_stop or rsi_reversal:
            reason = 'Profit Target' if hit_profit else 'Stop Loss' if hit_stop else 'RSI Reversal'
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
