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

# Rest of the code from bidirectional_test.py...
[Previous code here, ending with:]

    def run(self, duration_minutes=20):
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
