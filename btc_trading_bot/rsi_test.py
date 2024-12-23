import websocket
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def calculate_rsi(prices, period=14):
    """Calculate RSI for a price series"""
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

class RSIStrategy:
    def __init__(self, initial_capital=1000, leverage=50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position = 0  # 0 = no position, 1 = long
        self.entry_price = 0
        self.entry_time = None
        self.portfolio_value = initial_capital
        self.trades = []
        self.prices = []
        self.rsi_period = 7  # Shorter period for faster signals
        self.rsi_oversold = 30  # Buy signal
        self.rsi_overbought = 70  # Sell signal
        self.min_profit_pct = 0.5  # Minimum profit target (0.5%)
        self.max_loss_pct = -1.0  # Maximum loss tolerance (-1%)

    def calculate_signals(self):
        if len(self.prices) < self.rsi_period + 1:
            return None
        
        rsi = calculate_rsi(np.array(self.prices), self.rsi_period)
        current_rsi = rsi[-1]
        
        logging.info(f"Current RSI: {current_rsi:.2f}")
        return current_rsi

    def execute_trade(self, current_price, current_time):
        # Add price to history
        self.prices.append(current_price)
        
        # Need enough price history to calculate RSI
        if len(self.prices) < self.rsi_period + 1:
            return
        
        current_rsi = self.calculate_signals()
        
        # If no position, look for buy signal
        if self.position == 0:
            if current_rsi < self.rsi_oversold:  # Oversold condition - Buy signal
                self.position = 1
                self.entry_price = current_price
                self.entry_time = current_time
                position_size = self.portfolio_value * self.leverage
                logging.info(f"RSI Oversold ({current_rsi:.2f}) - Opening LONG position at ${current_price:,.2f}")
                logging.info(f"Position size: ${position_size:,.2f} ({self.leverage}x leverage)")
                
                self.trades.append({
                    'type': 'LONG',
                    'entry_price': current_price,
                    'entry_time': current_time,
                    'entry_rsi': current_rsi,
                    'size': position_size
                })
        
        # If in position, look for sell signals
        elif self.position == 1:
            # Calculate current P&L
            current_pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
            
            # Sell conditions:
            # 1. RSI overbought
            # 2. Hit profit target
            # 3. Hit stop loss
            should_sell = (
                current_rsi > self.rsi_overbought or  # Overbought
                current_pnl_pct >= self.min_profit_pct or  # Hit profit target
                current_pnl_pct <= self.max_loss_pct  # Hit stop loss
            )
            
            if should_sell:
                exit_pnl = (current_price - self.entry_price) / self.entry_price * self.leverage
                self.portfolio_value *= (1 + exit_pnl)
                
                sell_reason = "RSI Overbought" if current_rsi > self.rsi_overbought else \
                            "Profit Target Hit" if current_pnl_pct >= self.min_profit_pct else \
                            "Stop Loss Hit"
                
                logging.info(f"{sell_reason} - Closing position at ${current_price:,.2f}")
                logging.info(f"Trade PnL: ${(self.portfolio_value - self.initial_capital):,.2f} ({exit_pnl*100:.2f}%)")
                
                self.trades[-1].update({
                    'exit_price': current_price,
                    'exit_time': current_time,
                    'exit_rsi': current_rsi,
                    'pnl': exit_pnl * self.initial_capital,
                    'exit_reason': sell_reason
                })
                
                self.position = 0
                self.entry_price = 0
                self.entry_time = None

class TestBot:
    def __init__(self):
        self.ws = None
        self.strategy = RSIStrategy()
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
            logging.info(f"\nStarting RSI Strategy Test Bot")
            logging.info(f"Initial capital: ${self.strategy.initial_capital:,.2f}")
            logging.info(f"Leverage: {self.strategy.leverage}x")
            logging.info(f"RSI Settings:")
            logging.info(f"  - Period: {self.strategy.rsi_period}")
            logging.info(f"  - Oversold (Buy): {self.strategy.rsi_oversold}")
            logging.info(f"  - Overbought (Sell): {self.strategy.rsi_overbought}")
            logging.info(f"Trade Settings:")
            logging.info(f"  - Min Profit Target: {self.strategy.min_profit_pct}%")
            logging.info(f"  - Max Loss Limit: {self.strategy.max_loss_pct}%\n")
            
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
            
            # Print final results
            logging.info("\nTest completed!")
            logging.info(f"Final portfolio value: ${self.strategy.portfolio_value:,.2f}")
            logging.info(f"Total return: {((self.strategy.portfolio_value / self.strategy.initial_capital - 1) * 100):.2f}%")
            logging.info(f"Number of trades: {len(self.strategy.trades)}")
            
            # Print detailed trade history
            if self.strategy.trades:
                logging.info("\nTrade History:")
                for i, trade in enumerate(self.strategy.trades, 1):
                    if 'exit_price' in trade:  # Only show completed trades
                        logging.info(f"\nTrade #{i}:")
                        logging.info(f"Entry: ${trade['entry_price']:,.2f} (RSI: {trade['entry_rsi']:.2f})")
                        logging.info(f"Exit: ${trade['exit_price']:,.2f} (RSI: {trade['exit_rsi']:.2f})")
                        logging.info(f"Reason: {trade['exit_reason']}")
                        logging.info(f"PnL: ${trade['pnl']:,.2f}")
            
        except Exception as e:
            logging.error(f"Error in test bot: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    bot = TestBot()
    bot.run(duration_minutes=20)  # Run for 20 minutes
