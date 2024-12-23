import websocket
import json
import time
import numpy as np
import pandas as pd
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
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum()/period
    down = -seed[seed < 0].sum()/period
    rs = up/down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100./(1. + rs)

    for i in range(period, len(prices)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up/down
        rsi[i] = 100. - 100./(1. + rs)

    return rsi

class BidirectionalStrategy:
    def __init__(self, initial_capital=1000, leverage=50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        self.entry_price = 0
        self.entry_time = None
        self.portfolio_value = initial_capital
        self.trades = []
        self.prices = []
        self.highest_price = 0
        self.lowest_price = float('inf')
        
        # Strategy Parameters
        self.ema_fast = 8
        self.ema_slow = 21
        self.rsi_period = 7
        self.rsi_overbought = 75
        self.rsi_oversold = 25
        self.min_profit_pct = 1.0  # 1% (50% with leverage)
        self.max_loss_pct = -0.2  # -0.2% (-10% with leverage)
        self.trailing_stop_pct = 0.5  # 0.5% trailing stop

    def calculate_signals(self):
        if len(self.prices) < 26:  # Need enough data for all indicators
            return None, None, None, None, None
        
        # Calculate indicators
        macd, signal = calculate_macd(self.prices)
        ema_fast = calculate_ema(self.prices, self.ema_fast)
        ema_slow = calculate_ema(self.prices, self.ema_slow)
        rsi = calculate_rsi(np.array(self.prices), self.rsi_period)
        
        # Current values
        current_price = self.prices[-1]
        current_macd = macd[-1]
        current_signal = signal[-1]
        current_ema_fast = ema_fast[-1]
        current_ema_slow = ema_slow[-1]
        current_rsi = rsi[-1]
        
        logging.info(f"Price: ${current_price:,.2f}, RSI: {current_rsi:.1f}, MACD: {current_macd:.4f}")
        
        return current_price, current_macd, current_signal, current_rsi, (current_ema_fast > current_ema_slow)

    def execute_trade(self, current_price, current_time):
        # Add price to history
        self.prices.append(current_price)
        
        # Need enough price history
        if len(self.prices) < 26:
            return
        
        # Calculate signals
        price, macd, signal, rsi, trend_up = self.calculate_signals()
        
        # If no position, look for entry signals
        if self.position == 0:
            # LONG signal conditions (all must be true):
            # 1. RSI oversold
            # 2. MACD crossing up
            # 3. Fast EMA > Slow EMA
            long_signal = (
                rsi < self.rsi_oversold and
                macd > signal and
                trend_up
            )
            
            # SHORT signal conditions (all must be true):
            # 1. RSI overbought
            # 2. MACD crossing down
            # 3. Fast EMA < Slow EMA
            short_signal = (
                rsi > self.rsi_overbought and
                macd < signal and
                not trend_up
            )
            
            if long_signal:
                self.position = 1
                self.entry_price = current_price
                self.entry_time = current_time
                self.highest_price = current_price
                position_size = self.portfolio_value * self.leverage
                
                logging.info(f"\nLONG Entry - Price: ${current_price:,.2f}, RSI: {rsi:.1f}")
                logging.info(f"Position size: ${position_size:,.2f} ({self.leverage}x leverage)")
                
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': current_price,
                    'entry_time': current_time,
                    'entry_rsi': rsi,
                    'size': position_size
                })
                
            elif short_signal:
                self.position = -1
                self.entry_price = current_price
                self.entry_time = current_time
                self.lowest_price = current_price
                position_size = self.portfolio_value * self.leverage
                
                logging.info(f"\nSHORT Entry - Price: ${current_price:,.2f}, RSI: {rsi:.1f}")
                logging.info(f"Position size: ${position_size:,.2f} ({self.leverage}x leverage)")
                
                self.trades.append({
                    'type': 'SHORT',
                    'entry_price': current_price,
                    'entry_time': current_time,
                    'entry_rsi': rsi,
                    'size': position_size
                })
        
        # If in position, look for exit signals
        elif self.position != 0:
            # Update price extremes for trailing stop
            if self.position == 1:  # Long position
                self.highest_price = max(self.highest_price, current_price)
                trailing_stop = self.highest_price * (1 - self.trailing_stop_pct/100)
            else:  # Short position
                self.lowest_price = min(self.lowest_price, current_price)
                trailing_stop = self.lowest_price * (1 + self.trailing_stop_pct/100)
            
            # Calculate current P&L
            if self.position == 1:
                current_pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
                stop_hit = current_price <= trailing_stop
            else:
                current_pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
                stop_hit = current_price >= trailing_stop
            
            # Exit conditions
            should_exit = (
                (self.position == 1 and macd < signal and rsi > 70) or  # Long exit
                (self.position == -1 and macd > signal and rsi < 30) or  # Short exit
                current_pnl_pct >= self.min_profit_pct or  # Hit profit target
                current_pnl_pct <= self.max_loss_pct or  # Hit stop loss
                stop_hit  # Hit trailing stop
            )
            
            if should_exit:
                exit_pnl = current_pnl_pct * self.leverage / 100
                self.portfolio_value *= (1 + exit_pnl)
                
                exit_reason = "Signal Reversal" if (
                    (self.position == 1 and macd < signal) or
                    (self.position == -1 and macd > signal)
                ) else (
                    "Profit Target" if current_pnl_pct >= self.min_profit_pct else
                    "Stop Loss" if current_pnl_pct <= self.max_loss_pct else
                    "Trailing Stop"
                )
                
                trade_type = "LONG" if self.position == 1 else "SHORT"
                logging.info(f"\nClosing {trade_type} - {exit_reason}")
                logging.info(f"Exit Price: ${current_price:,.2f}")
                logging.info(f"P&L: ${(exit_pnl * self.initial_capital):,.2f} ({current_pnl_pct:.1f}%)")
                
                self.trades[-1].update({
                    'exit_price': current_price,
                    'exit_time': current_time,
                    'exit_rsi': rsi,
                    'pnl': exit_pnl * self.initial_capital,
                    'pnl_pct': current_pnl_pct,
                    'exit_reason': exit_reason
                })
                
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class TestBot:
    def __init__(self):
        self.ws = None
        self.strategy = BidirectionalStrategy()
        self.last_price = None
        self.running = True
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'data' in data and isinstance(data['data'], list):
                for trade in data['data']:
                    if isinstance(trade, dict) and 'time' in trade and 'px' in trade:
                        current_time = datetime.fromtimestamp(int(trade['time'])/1000)
                        current_price = float(trade['px'])
                        self.last_price = current_price
                        
                        # Execute strategy
                        self.strategy.execute_trade(current_price, current_time)
                        
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.info("WebSocket connection closed")

    def on_open(self, ws):
        logging.info("WebSocket connection opened")
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": "BTC"
            }
        }
        ws.send(json.dumps(subscribe_msg))

    def run(self, duration_minutes=20):
        """Run the test bot for specified duration"""
        try:
            logging.info(f"\nStarting Bidirectional Strategy Test Bot")
            logging.info(f"Initial capital: ${self.strategy.initial_capital:,.2f}")
            logging.info(f"Leverage: {self.strategy.leverage}x")
            logging.info(f"Strategy Settings:")
            logging.info(f"  - RSI (Period: {self.strategy.rsi_period}, Oversold: {self.strategy.rsi_oversold}, Overbought: {self.strategy.rsi_overbought})")
            logging.info(f"  - EMAs: {self.strategy.ema_fast}/{self.strategy.ema_slow}")
            logging.info(f"Trade Settings:")
            logging.info(f"  - Min Profit Target: {self.strategy.min_profit_pct}%")
            logging.info(f"  - Max Loss Limit: {self.strategy.max_loss_pct}%")
            logging.info(f"  - Trailing Stop: {self.strategy.trailing_stop_pct}%\n")
            
            # Connect to WebSocket
            websocket.enableTrace(True)
            self.ws = websocket.WebSocketApp(
                'wss://api.hyperliquid.xyz/ws',
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # Start WebSocket connection in a separate thread
            import threading
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Run for specified duration
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            
            while datetime.now() < end_time and self.running:
                time.sleep(1)
            
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
