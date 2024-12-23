import websocket
import json
import time
import logging
from datetime import datetime
import threading
from rsi_bollinger_strategy import RSIBollingerStrategy
from support_resistance_strategy import SupportResistanceStrategy
from volume_profile_strategy import VolumeProfileStrategy
from mega_trend_strategy import MegaTrendStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MultiStrategyTester:
    def __init__(self):
        # Initialize strategies with different risk profiles
        self.strategies = {
            'Mega-Trend': MegaTrendStrategy(
                initial_capital=200,
                leverage=50,  # High leverage for strong trends
                profit_target=0.015,  # 1.5% profit target
                stop_loss=-0.005,  # 0.5% stop loss
                trade_cooldown=3600  # 1 hour cooldown
            ),
            'Scalping': RSIBollingerStrategy(
                initial_capital=200,
                leverage=20,
                rsi_period=7,  # Faster RSI
                bollinger_period=20,
                profit_target=0.004,  # 0.4% profit target
                stop_loss=-0.002,  # 0.2% stop loss
                trade_cooldown=30  # 30 second cooldown
            ),
            'Breakout': SupportResistanceStrategy(
                initial_capital=200,
                leverage=30,
                lookback_period=100,
                profit_target=0.01,  # 1% profit target
                stop_loss=-0.004,  # 0.4% stop loss
                trade_cooldown=300  # 5 minute cooldown
            ),
            'Volume-Flow': VolumeProfileStrategy(
                initial_capital=200,
                leverage=25,
                volume_period=30,
                profit_target=0.008,  # 0.8% profit target
                stop_loss=-0.003,  # 0.3% stop loss
                trade_cooldown=120  # 2 minute cooldown
            )
        }
        
        self.running = True
        self.ws = None
        self.start_time = datetime.now()
        self.trade_count = 0
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data['channel'] == 'trades':
                for trade in data['data']:
                    price = float(trade['px'])
                    volume = float(trade['sz'])
                    
                    # Update all strategies
                    self.strategies['Mega-Trend'].update(price, volume)
                    self.strategies['Scalping'].update(price)
                    self.strategies['Breakout'].update(price, price, price)
                    self.strategies['Volume-Flow'].update(price, volume)
                    
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
        total_pnl = 0
        total_trades = 0
        
        logging.info("\n=== Strategy Performance ===")
        for name, strategy in self.strategies.items():
            metrics = strategy.get_metrics()
            total_pnl += metrics['total_pnl']
            total_trades += metrics['total_trades']
            
            logging.info(f"\n{name} Strategy:")
            logging.info(f"Total Trades: {metrics['total_trades']}")
            logging.info(f"Win Rate: {metrics['win_rate']:.1f}%")
            logging.info(f"Total PnL: ${metrics['total_pnl']:.2f}")
            logging.info(f"Total Fees: ${metrics['total_fees']:.2f}")
            logging.info(f"Current Capital: ${metrics['current_capital']:.2f}")
            
        logging.info(f"\nOverall Performance:")
        logging.info(f"Total PnL: ${total_pnl:.2f}")
        logging.info(f"Total Trades: {total_trades}")
            
    def run(self, duration_minutes=30):
        """Run all strategies for specified duration"""
        try:
            logging.info("\nStarting Multi-Strategy Test")
            logging.info(f"Initial Capital per Strategy: $200")
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
    tester = MultiStrategyTester()
    tester.run(duration_minutes=30)
