import websocket
import json
import time
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SimpleTestStrategy:
    def __init__(self, initial_capital=1000, leverage=50):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        self.entry_price = 0
        self.entry_time = None
        self.portfolio_value = initial_capital
        self.trades = []

    def execute_trade(self, current_price, current_time):
        # If no position, enter long
        if self.position == 0:
            self.position = 1
            self.entry_price = current_price
            self.entry_time = current_time
            position_size = self.portfolio_value * self.leverage
            logging.info(f"Opening LONG position at ${current_price:,.2f}")
            logging.info(f"Position size: ${position_size:,.2f} ({self.leverage}x leverage)")
            
            self.trades.append({
                'type': 'LONG',
                'entry_price': current_price,
                'entry_time': current_time,
                'size': position_size
            })
            
        # If in position for 5 minutes or more, close it
        elif self.position == 1 and (current_time - self.entry_time).total_seconds() >= 300:  # 5 minutes
            exit_pnl = (current_price - self.entry_price) / self.entry_price * self.leverage
            self.portfolio_value *= (1 + exit_pnl)
            
            logging.info(f"Closing position at ${current_price:,.2f}")
            logging.info(f"Trade PnL: ${(self.portfolio_value - self.initial_capital):,.2f} ({exit_pnl*100:.2f}%)")
            
            self.trades[-1].update({
                'exit_price': current_price,
                'exit_time': current_time,
                'pnl': exit_pnl * self.initial_capital
            })
            
            self.position = 0
            self.entry_price = 0
            self.entry_time = None

class TestBot:
    def __init__(self):
        self.ws = None
        self.strategy = SimpleTestStrategy()
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

    def run(self, duration_minutes=10):
        """Run the test bot for specified duration"""
        try:
            logging.info(f"Starting test bot for {duration_minutes} minutes")
            logging.info(f"Initial capital: ${self.strategy.initial_capital:,.2f}")
            logging.info(f"Leverage: {self.strategy.leverage}x")
            
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
                time.sleep(1)  # Check every second
                
            self.ws.close()
            
            # Print final results
            logging.info("\nTest completed!")
            logging.info(f"Final portfolio value: ${self.strategy.portfolio_value:,.2f}")
            logging.info(f"Total return: {((self.strategy.portfolio_value / self.strategy.initial_capital - 1) * 100):.2f}%")
            logging.info(f"Number of trades: {len(self.strategy.trades)}")
            
        except Exception as e:
            logging.error(f"Error in test bot: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    bot = TestBot()
    bot.run(duration_minutes=10)  # Run for 10 minutes
