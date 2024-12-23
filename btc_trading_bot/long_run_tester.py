import websocket
import json
import time
import logging
from datetime import datetime
import threading
from optimized_breakout_strategy import OptimizedBreakoutStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class LongRunTester:
    def __init__(self):
        self.strategy = OptimizedBreakoutStrategy(
            initial_capital=200,
            leverage=50,
            lookback_period=20,  # 20 candle lookback
            num_touches=1,  # Single touch
            breakout_threshold=0.0003,  # 0.03% breakout
            profit_target=0.003,  # 0.3% profit
            stop_loss=-0.0008,  # 0.08% stop loss
            momentum_period=14,  # RSI period
            trade_cooldown=0
        )
        
        self.running = True
        self.ws = None
        self.start_time = datetime.now()
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data['channel'] == 'trades':
                for trade in data['data']:
                    price = float(trade['px'])
                    volume = float(trade['sz'])
                    
                    # Update strategy with OHLCV data
                    self.strategy.update(price, price, price, volume)
                    
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            
    def on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")
        
    def on_close(self, ws, close_status_code, close_msg):
        logging.info("WebSocket connection closed")
        self.running = False
        
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
        
    def print_status(self):
        """Print performance metrics"""
        metrics = self.strategy.get_metrics()
        
        logging.info("\n=== Strategy Performance ===")
        logging.info(f"Total Trades: {metrics['total_trades']}")
        logging.info(f"Win Rate: {metrics['win_rate']:.1f}%")
        logging.info(f"Total PnL: ${metrics['total_pnl']:.2f}")
        logging.info(f"Total Fees: ${metrics['total_fees']:.2f}")
        logging.info(f"Current Capital: ${metrics['current_capital']:.2f}")
        
        # Calculate hourly stats
        hours_elapsed = (datetime.now() - self.start_time).total_seconds() / 3600
        if hours_elapsed > 0:
            hourly_pnl = metrics['total_pnl'] / hours_elapsed
            hourly_trades = metrics['total_trades'] / hours_elapsed
            logging.info(f"\nHourly Stats:")
            logging.info(f"PnL per Hour: ${hourly_pnl:.2f}")
            logging.info(f"Trades per Hour: {hourly_trades:.1f}")
            
    def run(self, duration_minutes=20):
        """Run strategy for specified duration"""
        try:
            logging.info("\nStarting Short Run Test")
            logging.info(f"Initial Capital: $200")
            logging.info(f"Test Duration: {duration_minutes} minutes")
            logging.info("\nStrategy Configuration:")
            logging.info(f"Leverage: {self.strategy.leverage}x")
            logging.info(f"Profit Target: {self.strategy.profit_target*100:.1f}%")
            logging.info(f"Stop Loss: {self.strategy.stop_loss*100:.1f}%")
            logging.info(f"Level Touches Required: {self.strategy.num_touches}")
            logging.info(f"Breakout Threshold: {self.strategy.breakout_threshold*100:.2f}%")
            
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
            test_duration = duration_minutes * 60
            start_time = time.time()
            
            while time.time() - start_time < test_duration and self.running:
                time.sleep(1)
                
                # Print status every 5 minutes
                elapsed_minutes = int((time.time() - start_time) / 60)
                if elapsed_minutes > 0 and elapsed_minutes % 5 == 0:
                    self.print_status()
                    minutes_remaining = duration_minutes - elapsed_minutes
                    logging.info(f"\nTime remaining: {minutes_remaining} minutes")
            
            self.ws.close()
            
            # Print final results
            logging.info("\n=== Final Results ===")
            self.print_status()
            
        except Exception as e:
            logging.error(f"Error in strategy tester: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    tester = LongRunTester()
    tester.run(duration_minutes=20)
