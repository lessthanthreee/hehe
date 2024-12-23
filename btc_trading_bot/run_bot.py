import websocket
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
from queue import Queue
import logging
import schedule
from strategies import (
    RSIMACDStrategy,
    BollingerBandsStrategy,
    MovingAverageCrossStrategy,
    MomentumStrategy,
    VWAPStrategy,
    ScalpingStrategy
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

class HyperliquidAPI:
    def __init__(self, strategy):
        self.data_queue = Queue()
        self.ws = None
        self.trades = []
        self.strategy = strategy
        self.running = True
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'data' in data and isinstance(data['data'], list):
                for trade in data['data']:
                    if isinstance(trade, dict) and 'time' in trade and 'px' in trade:
                        self.trades.append({
                            'timestamp': int(trade['time']),
                            'price': float(trade['px']),
                            'volume': float(trade.get('sz', 0))
                        })
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

    def process_trades(self):
        """Convert trade data to OHLCV candles and execute strategy"""
        if not self.trades:
            return
            
        df = pd.DataFrame(self.trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Create 5-minute candles
        ohlc = df.set_index('timestamp').price.resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        volume = df.set_index('timestamp').volume.resample('5min').sum().dropna()
        
        candles = pd.concat([ohlc, volume.rename('volume')], axis=1)
        
        if len(candles) > 0:
            # Calculate indicators and generate signals
            candles = self.strategy.calculate_indicators(candles)
            candles = self.strategy.generate_signals(candles)
            
            # Get latest data for logging
            latest = candles.iloc[-1]
            
            # Execute trades based on the latest signal
            current_price = latest['close']
            signal = latest['Signal']
            
            # Log detailed market conditions
            conditions = {
                'price': current_price,
                'signal': signal
            }
            
            # Add strategy-specific indicators to log
            for col in candles.columns:
                if col not in ['open', 'high', 'low', 'close', 'volume', 'Signal']:
                    conditions[col] = latest[col]
            
            logging.info(f"Market Conditions: {json.dumps(conditions, indent=2)}")
            
            if signal != 0:
                logging.info(f"Signal generated: {'LONG' if signal > 0 else 'SHORT'} at ${current_price:,.2f}")
            
            pnl = self.strategy.execute_trade(current_price, signal)
            
            # Log strategy performance
            metrics = self.strategy.performance_metrics
            if pnl != 0:
                logging.info(f"Trade executed - PnL: ${pnl:.2f}, ROI: {metrics['roi']:.2f}%, Win Rate: {metrics['win_rate']:.2f}%")
            
            # Log strategy performance
            metrics = self.strategy.performance_metrics
            logging.info(f"Strategy Update - PnL: ${pnl:.2f}, ROI: {metrics['roi']:.2f}%, Win Rate: {metrics['win_rate']:.2f}%")

    def run(self, duration_hours=8):
        """Run the trading bot for specified duration"""
        try:
            logging.info(f"Starting trading session for {duration_hours} hours")
            
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
            end_time = datetime.now() + timedelta(hours=duration_hours)
            
            while datetime.now() < end_time and self.running:
                self.process_trades()
                time.sleep(60)  # Process data every minute
                
            self.ws.close()
            
            # Save trade history
            self.save_results()
            
        except Exception as e:
            logging.error(f"Error in trading session: {e}")
            if self.ws:
                self.ws.close()
                
    def save_results(self):
        """Save trading results and performance metrics"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save trade history
        trades_df = pd.DataFrame(self.strategy.trades)
        trades_df.to_csv(f"trades_{timestamp}.csv", index=False)
        
        # Save performance metrics
        metrics = self.strategy.performance_metrics
        with open(f"metrics_{timestamp}.json", "w") as f:
            json.dump(metrics, f, indent=4)
            
        logging.info(f"Results saved: trades_{timestamp}.csv and metrics_{timestamp}.json")

def run_daily_session(strategy_name):
    """Run a daily trading session with the specified strategy"""
    strategies = {
        'RSI_MACD': RSIMACDStrategy(),
        'Bollinger_Bands': BollingerBandsStrategy(),
        'Moving_Average_Cross': MovingAverageCrossStrategy(),
        'Momentum': MomentumStrategy(),
        'VWAP': VWAPStrategy(),
        'Scalping': ScalpingStrategy()
    }
    
    if strategy_name not in strategies:
        logging.error(f"Invalid strategy name: {strategy_name}")
        return
        
    strategy = strategies[strategy_name]
    api = HyperliquidAPI(strategy)
    api.run(duration_hours=8)

def schedule_daily_sessions(strategy_name):
    """Schedule daily trading sessions"""
    # Run sessions every day at specific times
    schedule.every().day.at("09:30").do(run_daily_session, strategy_name)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python run_bot.py <strategy_name>")
        print("Available strategies: RSI_MACD, Bollinger_Bands, Moving_Average_Cross, Momentum, VWAP, Scalping")
        sys.exit(1)
        
    strategy_name = sys.argv[1]
    schedule_daily_sessions(strategy_name)
