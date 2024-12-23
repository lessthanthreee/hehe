import websocket
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from macd_volume_strategy import MACDVolumeStrategy

# Configure logging
logging.basicConfig(
    filename='strategy_test.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TestBot:
    def __init__(self, config):
        self.strategy_name = config.pop('name')  # Remove name from config but save it
        self.initial_capital = config.get('initial_capital', 200)
        self.leverage = config.get('leverage', 50)
        self.strategy_config = {
            'initial_capital': self.initial_capital,
            'leverage': self.leverage,
            **config
        }
        self.strategy = MACDVolumeStrategy(**self.strategy_config)
        self.trades = []
        self.running = True
        self.ws = None
        self.trade_file = f"trades_{self.strategy_name}.json"
        self.start_time = datetime.now()
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data['channel'] == 'trades':
                for trade in data['data']:
                    price = float(trade['px'])
                    volume = float(trade['sz'])
                    self.strategy.update(price, volume)
                    
                    # Check for trade signals
                    if not self.strategy.has_position():
                        self.strategy._check_entry_conditions(price)
                        
                        # Record trade if position was opened
                        if self.strategy.has_position():
                            self.trades.append({
                                'entry_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                                'entry_price': self.strategy.entry_price,
                                'direction': 'LONG' if self.strategy.position > 0 else 'SHORT',
                                'size': self.strategy.position_size,
                                'entry_fee': self.strategy.calculate_fees(self.strategy.position_size, is_maker=True)
                            })
                    else:
                        self.strategy._check_exit_conditions(price)
                        
                        # Record trade if position was closed
                        if not self.strategy.has_position():
                            current_trade = self.trades[-1] if self.trades else None
                            if current_trade:
                                current_trade.update({
                                    'exit_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                                    'exit_price': price,
                                    'pnl': self.strategy.total_pnl,
                                    'total_fees': self.strategy.total_fees
                                })
                                
                                # Save trades to file
                                with open(self.trade_file, 'w') as f:
                                    json.dump(self.trades, f, indent=2)
                    
        except Exception as e:
            print(f"Error processing message: {e}")
                
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
        
    def run(self, duration_minutes=20):
        """Run the test bot for specified duration in minutes"""
        try:
            logging.info(f"\nStarting MACD Strategy Test Bot - Configuration: {self.strategy_name}")
            logging.info(f"Initial capital: ${self.initial_capital:,.2f}")
            logging.info(f"Leverage: {self.leverage}x")
            logging.info(f"Strategy Settings:")
            logging.info(f"  - MACD: ({self.strategy_config['fast_period']},{self.strategy_config['slow_period']},{self.strategy_config['signal_period']})")
            logging.info(f"  - Volume MA Period: {self.strategy_config['volume_ma_period']}")
            logging.info(f"  - Volume Threshold: {self.strategy_config['volume_threshold']}x")
            logging.info(f"Trade Settings:")
            logging.info(f"  - Profit Target: {self.strategy_config['profit_target']}%")
            logging.info(f"  - Stop Loss: {self.strategy_config['stop_loss']}%")
            logging.info(f"  - Trade Cooldown: {self.strategy_config['trade_cooldown']} seconds\n")
            
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
            
            test_duration = duration_minutes * 60  # Convert minutes to seconds
            start_time = time.time()
            
            while time.time() - start_time < test_duration and self.running:
                time.sleep(1)  # Check every second
                
                # Print status every minute
                elapsed_minutes = int((time.time() - start_time) / 60)
                if elapsed_minutes > 0 and elapsed_minutes % 1 == 0:
                    self.log_status()
                    logging.info(f"Time remaining: {duration_minutes - elapsed_minutes} minutes")
            
            self.ws.close()
            
            # Save trades to file
            with open(self.trade_file, 'w') as f:
                json.dump(self.trades, f, indent=2)
            
            # Print final results
            self.log_final_results()
            
        except Exception as e:
            logging.error(f"Error in test bot: {e}")
            if self.ws:
                self.ws.close()
                
    def log_status(self):
        """Log current trading status"""
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        
        print(f"\nStatus Update - {self.strategy_name} - Runtime: {hours:.1f} hours")
        print(f"Portfolio Value: ${self.strategy.current_capital:,.2f}")
        print(f"Total Trades: {len(self.trades)}")
        if self.trades:
            win_rate = (sum(1 for trade in self.trades if trade.get('pnl', 0) > 0) / len(self.trades)) * 100
            total_pnl = sum(trade.get('pnl', 0) for trade in self.trades)
            total_fees = sum(trade.get('total_fees', 0) for trade in self.trades)
            print(f"Win Rate: {win_rate:.1f}%")
            print(f"Total PnL: ${total_pnl:.2f}")
            print(f"Total Fees: ${total_fees:.2f}")
        
    def log_final_results(self):
        """Log final trading results"""
        runtime = datetime.now() - self.start_time
        hours = runtime.total_seconds() / 3600
        
        logging.info(f"\nTest completed! - {self.strategy_name}")
        logging.info(f"Runtime: {hours:.1f} hours")
        logging.info(f"Final portfolio value: ${self.strategy.current_capital:,.2f}")
        logging.info(f"Total return: {((self.strategy.current_capital / self.initial_capital - 1) * 100):.2f}%")
        logging.info(f"Number of trades: {len(self.trades)}")
        
        if self.trades:
            win_rate = (sum(1 for trade in self.trades if trade.get('pnl', 0) > 0) / len(self.trades)) * 100
            avg_trade = sum(trade.get('pnl', 0) for trade in self.trades) / len(self.trades)
            
            logging.info(f"Win Rate: {win_rate:.1f}%")
            logging.info(f"Average Trade PnL: ${avg_trade:,.2f}")
            logging.info(f"Total PnL: ${sum(trade.get('pnl', 0) for trade in self.trades):,.2f}")
            
            # Print last 5 trades
            logging.info("\nLast 5 Trades:")
            for trade in self.trades[-5:]:
                logging.info(f"Entry: ${trade['entry_price']:,.2f}")
                if 'exit_price' in trade:
                    logging.info(f"Exit: ${trade['exit_price']:,.2f}")
                    logging.info(f"PnL: ${trade['pnl']:,.2f}")
                    logging.info(f"Reason: {trade['exit_reason']}\n")

if __name__ == "__main__":
    # Strategy configuration
    config = {
        'name': 'conservative',
        'initial_capital': 5000,
        'leverage': 50,
        'fast_period': 24,
        'slow_period': 52,
        'signal_period': 18,
        'volume_ma_period': 20,
        'volume_threshold': 2.5,
        'profit_target': 0.005,  # 0.5% profit target
        'stop_loss': -0.002,    # 0.2% stop loss
        'trade_cooldown': 20,   # 20 seconds between trades
        'maker_fee': -0.0002,   # -0.02% maker fee (rebate)
        'taker_fee': 0.0005     # 0.05% taker fee
    }

    print("\nStarting 5-minute paper trading test...")
    print("Testing conservative strategy with detailed P&L logging")
    print(f"Initial capital: {config['initial_capital']}")
    print(f"Leverage: {config['leverage']}")
    print(f"Maker fee: {config['maker_fee']}")
    print(f"Taker fee: {config['taker_fee']}\n")

    bot = TestBot(config)
    bot.run()
    
    time.sleep(10)  # Give time for final status updates
    
    print("\nTest completed!")
    print("Check trade_logs directory for detailed results.")
