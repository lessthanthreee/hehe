import websocket
import json
import time
import numpy as np
import pandas as pd
import threading
from datetime import datetime, timedelta
import logging
from trade_logger import setup_logging, log_trade_summary

# Setup logging
log_file = setup_logging()

def calculate_ema(prices, period):
    """Calculate EMA for a price series"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().values

def calculate_macd(prices):
    """Calculate MACD (12,26,9)"""
    exp1 = pd.Series(prices).ewm(span=12, adjust=False).mean()
    exp2 = pd.Series(prices).ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.values, signal.values

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    deltas = np.diff(prices)
    if len(deltas) < period:
        return np.array([50])  # Default neutral RSI
    gain = deltas.copy()
    loss = deltas.copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0
    avg_gain = np.concatenate(([0], pd.Series(gain).rolling(period).mean().values[period:]))
    avg_loss = np.concatenate(([0], pd.Series(np.abs(loss)).rolling(period).mean().values[period:]))
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

class OptimizedStrategy:
    def __init__(self, initial_capital=1000, leverage=50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        self.entry_price = 0
        self.entry_time = None
        self.portfolio_value = initial_capital
        self.trades = []
        self.prices = []
        self.volumes = []
        self.highest_price = 0
        self.lowest_price = float('inf')
        
        # Strategy Parameters
        self.ema_fast = 8
        self.ema_slow = 21
        self.rsi_period = 7
        self.rsi_overbought = 80  # More conservative
        self.rsi_oversold = 20    # More conservative
        self.min_profit_pct = 0.5  # Smaller targets for quicker profits
        self.max_loss_pct = -0.15  # Tighter stop loss
        self.trailing_stop_pct = 0.2  # Tighter trailing stop
        
        # Fee structure (Hyperliquid)
        self.maker_fee = 0.0002  # 0.02%
        self.taker_fee = 0.0005  # 0.05%
        
    def calculate_fees(self, position_size, is_maker=False):
        """Calculate trading fees for a given position size"""
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        return position_size * fee_rate
        
    def calculate_total_cost(self, price, position_size, is_entry=True, is_maker=False):
        """Calculate total cost including fees for a trade"""
        fees = self.calculate_fees(position_size, is_maker)
        if is_entry:
            return position_size + fees
        else:
            return position_size - fees

    def calculate_signals(self):
        if len(self.prices) < 26:  # Need enough data for all indicators
            return None, None, None, None, None, None
        
        # Calculate indicators
        macd, signal = calculate_macd(self.prices)
        ema_fast = calculate_ema(self.prices, self.ema_fast)
        ema_slow = calculate_ema(self.prices, self.ema_slow)
        rsi = calculate_rsi(np.array(self.prices), self.rsi_period)
        
        # Calculate price momentum
        price_change = (self.prices[-1] - self.prices[-2]) / self.prices[-2] * 100
        
        # Current values
        current_price = self.prices[-1]
        current_macd = macd[-1]
        current_signal = signal[-1]
        current_ema_fast = ema_fast[-1]
        current_ema_slow = ema_slow[-1]
        current_rsi = rsi[-1]
        
        logging.info(f"Price: ${current_price:,.2f}, RSI: {current_rsi:.1f}, MACD: {current_macd:.4f}, Momentum: {price_change:.2f}%")
        
        return current_price, current_macd, current_signal, current_rsi, (current_ema_fast > current_ema_slow), price_change

    def execute_trade(self, current_price, current_time, volume=None):
        # Add price to history
        self.prices.append(current_price)
        if volume:
            self.volumes.append(volume)
        
        # Need enough price history
        if len(self.prices) < 26:
            return
        
        # Calculate signals
        price, macd, signal, rsi, trend_up, momentum = self.calculate_signals()
        
        # If no position, look for entry signals
        if self.position == 0:
            position_size = self.portfolio_value * self.leverage
            entry_cost = self.calculate_total_cost(price, position_size, is_entry=True, is_maker=False)
            
            # LONG signal conditions (all must be true):
            # 1. RSI oversold
            # 2. MACD crossing up
            # 3. Fast EMA > Slow EMA
            # 4. Price not falling too fast
            long_signal = (
                rsi < self.rsi_oversold and
                macd > signal and
                trend_up and
                momentum > -0.1  # Not falling too fast
            )
            
            # SHORT signal conditions (all must be true):
            # 1. RSI overbought
            # 2. MACD crossing down
            # 3. Fast EMA < Slow EMA
            # 4. Price not rising too fast
            short_signal = (
                rsi > self.rsi_overbought and
                macd < signal and
                not trend_up and
                momentum < 0.1  # Not rising too fast
            )
            
            if long_signal:
                self.position = 1
                self.entry_price = current_price
                self.entry_time = current_time
                self.highest_price = current_price
                
                logging.info(f"\nLONG Entry - Price: ${current_price:,.2f}, RSI: {rsi:.1f}")
                logging.info(f"Position size: ${position_size:,.2f} ({self.leverage}x leverage)")
                
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': current_price,
                    'entry_time': current_time,
                    'entry_rsi': rsi,
                    'size': position_size,
                    'entry_fees': entry_cost - position_size
                })
                
            elif short_signal:
                self.position = -1
                self.entry_price = current_price
                self.entry_time = current_time
                self.lowest_price = current_price
                
                logging.info(f"\nSHORT Entry - Price: ${current_price:,.2f}, RSI: {rsi:.1f}")
                logging.info(f"Position size: ${position_size:,.2f} ({self.leverage}x leverage)")
                
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': current_price,
                    'entry_time': current_time,
                    'entry_rsi': rsi,
                    'size': position_size,
                    'entry_fees': entry_cost - position_size
                })
        
        # If in position, look for exit signals
        elif self.position != 0:
            position_size = self.trades[-1]['size']
            exit_cost = self.calculate_total_cost(price, position_size, is_entry=False, is_maker=False)
            
            # Update price extremes for trailing stop
            if self.position == 1:  # Long position
                self.highest_price = max(self.highest_price, current_price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop_pct/100)
            else:  # Short position
                self.lowest_price = min(self.lowest_price, current_price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop_pct/100)
            
            # Calculate P&L including fees
            entry_fees = self.trades[-1]['entry_fees']
            exit_fees = position_size * self.taker_fee
            total_fees = entry_fees + exit_fees
            
            # Calculate raw P&L
            raw_pnl_pct = ((current_price - self.entry_price) / self.entry_price * 100) * (1 if self.position == 1 else -1)
            
            # Adjust P&L for fees
            fee_impact_pct = (total_fees / position_size) * 100
            actual_pnl_pct = raw_pnl_pct - fee_impact_pct
            
            # Quick exit conditions
            quick_exit_long = (
                self.position == 1 and
                (macd < signal or  # MACD cross down
                momentum < -0.05)  # Quick price drop
            )
            
            quick_exit_short = (
                self.position == -1 and
                (macd > signal or  # MACD cross up
                momentum > 0.05)   # Quick price rise
            )
            
            # Exit conditions with trailing stop
            should_exit = (
                actual_pnl_pct >= self.min_profit_pct or  # Hit profit target
                actual_pnl_pct <= self.max_loss_pct or  # Hit stop loss
                (self.position == 1 and current_price <= trailing_stop) or  # Long trailing stop
                (self.position == -1 and current_price >= trailing_stop) or  # Short trailing stop
                quick_exit_long or
                quick_exit_short
            )
            
            if should_exit:
                actual_pnl = actual_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + actual_pnl)
                
                exit_reason = (
                    "Profit Target" if actual_pnl_pct >= self.min_profit_pct else
                    "Stop Loss" if actual_pnl_pct <= self.max_loss_pct else
                    "Trailing Stop" if (self.position == 1 and current_price <= trailing_stop) or 
                                     (self.position == -1 and current_price >= trailing_stop) else
                    "Quick Exit"
                )
                
                trade_type = "LONG" if self.position == 1 else "SHORT"
                logging.info(f"\nClosing {trade_type} - {exit_reason}")
                logging.info(f"Exit Price: ${current_price:,.2f}")
                logging.info(f"P&L: ${(actual_pnl * self.initial_capital):,.2f} ({actual_pnl_pct:.1f}%)")
                
                self.trades[-1].update({
                    'exit_price': current_price,
                    'exit_time': current_time,
                    'exit_rsi': rsi,
                    'pnl': actual_pnl * self.initial_capital,
                    'pnl_pct': actual_pnl_pct,
                    'exit_reason': exit_reason,
                    'total_fees': total_fees
                })
                
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class TestBot:
    def __init__(self):
        self.ws = None
        self.strategy = OptimizedStrategy()
        self.last_price = None
        self.running = True
    
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'p' in data and 'E' in data:  # Binance trade event
                current_time = datetime.fromtimestamp(int(data['E'])/1000)
                current_price = float(data['p'])
                volume = float(data['q'])
                self.last_price = current_price
                
                # Execute strategy
                self.strategy.execute_trade(current_price, current_time, volume)
                
        except Exception as e:
            logging.error(f"Error processing message: {e}")
    
    def on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        logging.info("WebSocket connection closed")
        self.running = False
    
    def on_open(self, ws):
        logging.info("WebSocket connection opened")
        # Binance WebSocket auto-subscribes to the stream in the URL
        pass
    
    def run(self, duration_minutes=20):
        """Run the test bot for specified duration"""
        try:
            # Setup logging
            log_file = setup_logging()
            
            print(f"\nStarting Optimized Strategy Test Bot")
            print("="*50)
            print(f"Initial capital: ${self.strategy.initial_capital:,.2f}")
            print(f"Leverage: {self.strategy.leverage}x")
            print(f"Strategy Settings:")
            print(f"  - RSI (Period: {self.strategy.rsi_period}, Oversold: {self.strategy.rsi_oversold}, Overbought: {self.strategy.rsi_overbought})")
            print(f"  - EMAs: {self.strategy.ema_fast}/{self.strategy.ema_slow}")
            print(f"Trade Settings:")
            print(f"  - Min Profit Target: {self.strategy.min_profit_pct}%")
            print(f"  - Max Loss Limit: {self.strategy.max_loss_pct}%")
            print(f"  - Trailing Stop: {self.strategy.trailing_stop_pct}%\n")
            
            # Connect to WebSocket
            websocket.enableTrace(True)
            self.ws = websocket.WebSocketApp(
                'wss://stream.binance.com:9443/ws/btcusdt@trade',
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # Start WebSocket connection in a separate thread
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Run for specified duration
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            
            while datetime.now() < end_time and self.running:
                time.sleep(5)  # Check every 5 seconds
                if self.strategy.trades:
                    print("\nCurrent Results:")
                    print("="*50)
                    print(f"Current capital: ${self.strategy.portfolio_value:,.2f}")
                    print(f"P&L: ${self.strategy.portfolio_value - self.strategy.initial_capital:,.2f}")
                    completed_trades = [t for t in self.strategy.trades if 'exit_price' in t]
                    if completed_trades:
                        print(f"Completed trades: {len(completed_trades)}")
                        print(f"Last trade P&L: ${completed_trades[-1]['pnl']:,.2f}")
            
            self.ws.close()
            
            # Log final trade summary
            log_trade_summary(
                self.strategy.trades,
                self.strategy.initial_capital,
                self.strategy.portfolio_value
            )
            
        except Exception as e:
            logging.error(f"Error in test bot: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    bot = TestBot()
    bot.run(duration_minutes=20)  # Run for 20 minutes
