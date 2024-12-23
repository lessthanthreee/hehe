import websocket
import json
import threading
import time
from datetime import datetime
import logging

from volume_surge_strategy import VolumeSurgeStrategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VolumeSurgeTester:
    def __init__(self):
        self.strategy = VolumeSurgeStrategy(
            initial_capital=200,
            leverage=50,
            volume_threshold=1.3,  # 1.3x volume surge
            min_price_move=0.0002,  # 0.02% min move
            profit_target=0.002,  # 0.2% profit
            stop_loss=-0.0008  # 0.08% stop
        )
        self.running = True
        self.ws = None
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            if data["channel"] == "trades":
                for trade in data["data"]:
                    if trade["coin"] == "BTC":
                        price = float(trade["px"])
                        volume = float(trade["sz"])
                        self.strategy.update(price, volume)
                        
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        logging.error(f"WebSocket error: {error}")
        
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logging.info("WebSocket connection closed")
        
    def on_open(self, ws):
        """Handle WebSocket connection open"""
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coins": ["BTC"]
            }
        }
        ws.send(json.dumps(subscribe_msg))
        
    def print_status(self):
        """Print strategy performance metrics"""
        elapsed_hours = (datetime.now() - self.strategy.start_time).total_seconds() / 3600
        
        logging.info("\n=== Strategy Performance ===")
        logging.info(f"Total Trades: {self.strategy.total_trades}")
        
        win_rate = (self.strategy.winning_trades / self.strategy.total_trades * 100) if self.strategy.total_trades > 0 else 0
        logging.info(f"Win Rate: {win_rate:.1f}%")
        
        logging.info(f"Total PnL: ${self.strategy.total_pnl:.2f}")
        logging.info(f"Total Fees: ${self.strategy.total_fees:.2f}")
        logging.info(f"Current Capital: ${self.strategy.current_capital:.2f}")
        
        logging.info("\nHourly Stats:")
        hourly_pnl = self.strategy.total_pnl / elapsed_hours if elapsed_hours > 0 else 0
        hourly_trades = self.strategy.total_trades / elapsed_hours if elapsed_hours > 0 else 0
        logging.info(f"PnL per Hour: ${hourly_pnl:.2f}")
        logging.info(f"Trades per Hour: {hourly_trades:.1f}")
        
    def run(self, duration_hours=4):
        """Run strategy for specified duration"""
        try:
            logging.info("\nStarting Volume Surge Test")
            logging.info(f"Initial Capital: $200")
            logging.info(f"Test Duration: {duration_hours} hours")
            logging.info("\nStrategy Configuration:")
            logging.info(f"Leverage: {self.strategy.leverage}x")
            logging.info(f"Volume Threshold: {self.strategy.volume_threshold}x")
            logging.info(f"Min Price Move: {self.strategy.min_price_move*100:.3f}%")
            logging.info(f"Profit Target: {self.strategy.profit_target*100:.2f}%")
            logging.info(f"Stop Loss: {self.strategy.stop_loss*100:.2f}%")
            
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
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Run for specified duration
            test_duration = duration_hours * 3600
            start_time = time.time()
            
            while time.time() - start_time < test_duration and self.running:
                time.sleep(1)
                
                # Print status every 15 minutes
                elapsed_minutes = int((time.time() - start_time) / 60)
                if elapsed_minutes > 0 and elapsed_minutes % 15 == 0:
                    self.print_status()
                    hours_remaining = (test_duration - (time.time() - start_time)) / 3600
                    logging.info(f"\nTime remaining: {hours_remaining:.1f} hours")
            
            self.ws.close()
            
            # Print final results
            logging.info("\n=== Final Results ===")
            self.print_status()
            
        except Exception as e:
            logging.error(f"Error in strategy tester: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    tester = VolumeSurgeTester()
    tester.run(duration_hours=4)
