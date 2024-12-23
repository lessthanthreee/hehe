from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from datetime import datetime
import json
import logging

class BaseStrategy(ABC):
    def __init__(self, leverage=50, initial_capital=1000):
        self.leverage = leverage
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.position = 0
        self.entry_price = 0
        self.trades = []
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.04
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'max_drawdown': 0,
            'win_rate': 0,
            'roi': 0
        }
        
    @abstractmethod
    def calculate_indicators(self, df):
        pass
        
    @abstractmethod
    def generate_signals(self, df):
        pass
        
    def update_performance_metrics(self, pnl):
        self.performance_metrics['total_trades'] += 1
        self.performance_metrics['total_pnl'] += pnl
        
        if pnl > 0:
            self.performance_metrics['winning_trades'] += 1
        else:
            self.performance_metrics['losing_trades'] += 1
            
        self.performance_metrics['win_rate'] = (
            self.performance_metrics['winning_trades'] / 
            self.performance_metrics['total_trades'] * 100 if self.performance_metrics['total_trades'] > 0 else 0
        )
        
        self.performance_metrics['roi'] = (
            (self.portfolio_value / self.initial_capital - 1) * 100
        )
        
        # Calculate max drawdown
        peak = self.initial_capital
        for trade in self.trades:
            if isinstance(trade, dict) and 'portfolio_value' in trade:
                current = trade['portfolio_value']
                drawdown = (peak - current) / peak * 100
                self.performance_metrics['max_drawdown'] = max(
                    self.performance_metrics['max_drawdown'],
                    drawdown
                )
                if current > peak:
                    peak = current
                    
    def execute_trade(self, current_price, signal):
        if signal != 0 and self.position == 0:  # Open new position
            position_size = self.portfolio_value * self.leverage
            self.position = position_size * signal
            self.entry_price = current_price
            
            if signal > 0:  # Long position
                self.stop_loss = self.entry_price * (1 - self.stop_loss_pct)
                self.take_profit = self.entry_price * (1 + self.take_profit_pct)
            else:  # Short position
                self.stop_loss = self.entry_price * (1 + self.stop_loss_pct)
                self.take_profit = self.entry_price * (1 - self.take_profit_pct)
                
            trade_type = "LONG" if signal > 0 else "SHORT"
            trade_info = {
                'type': trade_type,
                'entry_price': current_price,
                'size': abs(self.position),
                'timestamp': datetime.now().isoformat(),
                'portfolio_value': self.portfolio_value
            }
            self.trades.append(trade_info)
            logging.info(f"Opened {trade_type} position at ${current_price:,.2f}")
            
        elif self.position != 0:  # Check for exit conditions
            pnl = 0
            exit_reason = ""
            
            price_change = (current_price - self.entry_price) / self.entry_price
            unrealized_pnl = self.position * price_change
            
            if self.position > 0:  # Long position
                if current_price <= self.stop_loss:
                    exit_reason = "Stop Loss"
                    pnl = unrealized_pnl
                elif current_price >= self.take_profit:
                    exit_reason = "Take Profit"
                    pnl = unrealized_pnl
            else:  # Short position
                if current_price >= self.stop_loss:
                    exit_reason = "Stop Loss"
                    pnl = unrealized_pnl
                elif current_price <= self.take_profit:
                    exit_reason = "Take Profit"
                    pnl = unrealized_pnl
            
            if exit_reason:
                self.portfolio_value += pnl
                trade_info = {
                    'exit_price': current_price,
                    'exit_reason': exit_reason,
                    'pnl': pnl,
                    'timestamp': datetime.now().isoformat(),
                    'portfolio_value': self.portfolio_value
                }
                self.trades[-1].update(trade_info)
                self.update_performance_metrics(pnl)
                logging.info(f"Closed position at ${current_price:,.2f} ({exit_reason}) - PnL: ${pnl:,.2f}")
                self.position = 0
                
        return self.portfolio_value - self.initial_capital

class RSIMACDStrategy(BaseStrategy):
    def calculate_rsi(self, data, periods=7):  
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    def calculate_indicators(self, df):
        # RSI
        df['RSI'] = self.calculate_rsi(df['close'])
        
        # MACD with faster settings
        exp1 = df['close'].ewm(span=8, adjust=False).mean()  
        exp2 = df['close'].ewm(span=17, adjust=False).mean()  
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Volume filter
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / df['Volume_SMA']
        
        return df
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Entry conditions with volume confirmation (loosened)
        long_conditions = (
            (df['RSI'] < 35) &  
            (df['MACD'] > df['MACD_Signal']) &  
            (df['Volume_Ratio'] > 1.1)  
        )
        
        short_conditions = (
            (df['RSI'] > 65) &  
            (df['MACD'] < df['MACD_Signal']) &  
            (df['Volume_Ratio'] > 1.1)  
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, leverage=50, initial_capital=1000):
        super().__init__(leverage, initial_capital)
        self.stop_loss_pct = 0.01  
        self.take_profit_pct = 0.02  
        
    def calculate_indicators(self, df):
        # Bollinger Bands with narrower bands
        df['BB_Middle'] = df['close'].rolling(window=20).mean()
        df['BB_Std'] = df['close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * 2.0)  
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * 2.0)
        
        # RSI for confirmation
        df['RSI'] = RSIMACDStrategy.calculate_rsi(self, df['close'], periods=14)
        
        return df
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Entry conditions with RSI confirmation (loosened)
        long_conditions = (
            (df['close'] < df['BB_Lower']) &  
            (df['RSI'] < 35)  
        )
        
        short_conditions = (
            (df['close'] > df['BB_Upper']) &  
            (df['RSI'] > 65)  
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df

class MovingAverageCrossStrategy(BaseStrategy):
    def __init__(self, leverage=50, initial_capital=1000):
        super().__init__(leverage, initial_capital)
        self.stop_loss_pct = 0.015  
        self.take_profit_pct = 0.03  
        
    def calculate_indicators(self, df):
        # Multiple Moving Averages (faster)
        df['EMA_5'] = df['close'].ewm(span=5, adjust=False).mean()  
        df['SMA_15'] = df['close'].rolling(window=15).mean()  
        df['SMA_30'] = df['close'].rolling(window=30).mean()  
        
        # Trend strength
        df['Trend'] = np.where(
            (df['EMA_5'] > df['SMA_15']) & (df['SMA_15'] > df['SMA_30']),
            1,
            np.where(
                (df['EMA_5'] < df['SMA_15']) & (df['SMA_15'] < df['SMA_30']),
                -1,
                0
            )
        )
        
        return df
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Entry conditions (simplified)
        long_conditions = (
            (df['EMA_5'] > df['SMA_15']) &  
            (df['close'] > df['SMA_15'])  
        )
        
        short_conditions = (
            (df['EMA_5'] < df['SMA_15']) &  
            (df['close'] < df['SMA_15'])  
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df

class MomentumStrategy(BaseStrategy):
    def __init__(self, leverage=50, initial_capital=1000):
        super().__init__(leverage, initial_capital)
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.04
        
    def calculate_indicators(self, df):
        # Rate of Change (faster)
        df['ROC'] = df['close'].pct_change(periods=5) * 100
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()
        
        # Momentum
        df['Momentum'] = df['close'] - df['close'].shift(5)
        
        return df
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Entry conditions (loosened)
        long_conditions = (
            (df['ROC'] > 1.0) &  
            (df['Momentum'] > 0) &  
            (df['ATR'] > df['ATR'].rolling(window=20).mean() * 0.8)  
        )
        
        short_conditions = (
            (df['ROC'] < -1.0) &  
            (df['Momentum'] < 0) &  
            (df['ATR'] > df['ATR'].rolling(window=20).mean() * 0.8)  
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df

class VWAPStrategy(BaseStrategy):
    def __init__(self, leverage=50, initial_capital=1000):
        super().__init__(leverage, initial_capital)
        self.stop_loss_pct = 0.008  
        self.take_profit_pct = 0.015  
        
    def calculate_indicators(self, df):
        # VWAP
        df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        # VWAP Bands (narrower)
        df['VWAP_Std'] = df['close'].rolling(window=20).std()
        df['VWAP_Upper'] = df['VWAP'] + (df['VWAP_Std'] * 0.8)  
        df['VWAP_Lower'] = df['VWAP'] - (df['VWAP_Std'] * 0.8)
        
        # Volume Profile
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / df['Volume_SMA']
        
        return df
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Entry conditions (loosened)
        long_conditions = (
            (df['close'] < df['VWAP_Lower']) &  
            (df['Volume_Ratio'] > 1.1) &  
            (df['close'].diff() > 0)  
        )
        
        short_conditions = (
            (df['close'] > df['VWAP_Upper']) &  
            (df['Volume_Ratio'] > 1.1) &  
            (df['close'].diff() < 0)  
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df

class ScalpingStrategy(BaseStrategy):
    def __init__(self, leverage=50, initial_capital=1000):
        super().__init__(leverage, initial_capital)
        self.stop_loss_pct = 0.005  
        self.take_profit_pct = 0.01  
        
    def calculate_indicators(self, df):
        # Short-term EMAs (even faster)
        df['EMA_2'] = df['close'].ewm(span=2, adjust=False).mean()  
        df['EMA_4'] = df['close'].ewm(span=4, adjust=False).mean()
        df['EMA_6'] = df['close'].ewm(span=6, adjust=False).mean()
        
        # RSI with very short period
        df['RSI'] = RSIMACDStrategy.calculate_rsi(self, df['close'], periods=3)  
        
        # Price action
        df['Higher_High'] = df['high'] > df['high'].shift(1)
        df['Lower_Low'] = df['low'] < df['low'].shift(1)
        
        return df
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Entry conditions for quick scalps (loosened)
        long_conditions = (
            (df['EMA_2'] > df['EMA_4']) &  
            (df['RSI'] < 40) &  
            (df['Higher_High'])  
        )
        
        short_conditions = (
            (df['EMA_2'] < df['EMA_4']) &  
            (df['RSI'] > 60) &  
            (df['Lower_Low'])  
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df
