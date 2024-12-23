import websocket
import json
import time
import logging
from datetime import datetime
import threading
from rsi_bollinger_strategy import RSIBollingerStrategy
from support_resistance_strategy import SupportResistanceStrategy
from volume_profile_strategy import VolumeProfileStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class StrategyTester:
    def __init__(self):
        # Initialize strategies
        self.strategies = {
            'RSI-Bollinger': RSIBollingerStrategy(
                initial_capital=200,
                leverage=20,
                rsi_period=9,
                bollinger_period=20,
                profit_target=0.005,
                stop_loss=-0.003
            ),
            'Support-Resistance': SupportResistanceStrategy(
                initial_capital=200,
                leverage=20,
                lookback_period=100,
                profit_target=0.008,
                stop_loss=-0.004
            ),
            'Volume-Profile': VolumeProfileStrategy(
                initial_capital=200,
                leverage=20,
                volume_period=30,
                profit_target=0.006,
                stop_loss=-0.003
            )
        }
        
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
                    
                    # Update RSI-Bollinger strategy
                    self.strategies['RSI-Bollinger'].update(price)
                    
                    # Update Support-Resistance strategy
                    self.strategies['Support-Resistance'].update(price, price, price)
                    
                    # Update Volume-Profile strategy
                    self.strategies['Volume-Profile'].update(price, volume)
                    
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
        """Print performance metrics for all strategies"""
        logging.info("\n=== Strategy Performance ===")
        for name, strategy in self.strategies.items():
            metrics = strategy.get_metrics()
            logging.info(f"\n{name} Strategy:")
            logging.info(f"Total Trades: {metrics['total_trades']}")
            logging.info(f"Win Rate: {metrics['win_rate']:.1f}%")
            logging.info(f"Total PnL: ${metrics['total_pnl']:.2f}")
            logging.info(f"Total Fees: ${metrics['total_fees']:.2f}")
            logging.info(f"Current Capital: ${metrics['current_capital']:.2f}")
            
    def run(self, duration_minutes=20):
        """Run all strategies for specified duration"""
        try:
            logging.info("\nStarting Strategy Test")
            logging.info(f"Initial Capital: $200")
            logging.info(f"Test Duration: {duration_minutes} minutes")
            logging.info("\nStrategy Configurations:")
            
            for name, strategy in self.strategies.items():
                logging.info(f"\n{name}:")
                logging.info(f"Leverage: {strategy.leverage}x")
                logging.info(f"Profit Target: {strategy.profit_target*100:.1f}%")
                logging.info(f"Stop Loss: {strategy.stop_loss*100:.1f}%")
            
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
                
                # Print status every minute
                elapsed_minutes = int((time.time() - start_time) / 60)
                if elapsed_minutes > 0 and elapsed_minutes % 1 == 0:
                    self.print_status()
                    logging.info(f"\nTime remaining: {duration_minutes - elapsed_minutes} minutes")
            
            self.ws.close()
            
            # Print final results
            logging.info("\n=== Final Results ===")
            self.print_status()
            
        except Exception as e:
            logging.error(f"Error in strategy tester: {e}")
            if self.ws:
                self.ws.close()

if __name__ == "__main__":
    tester = StrategyTester()
    tester.run(duration_minutes=20)
