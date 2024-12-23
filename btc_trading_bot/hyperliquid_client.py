import websocket
import json
import threading
import time
from datetime import datetime

class HyperliquidClient:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.trades = []
        self.callbacks = []
        
    def connect(self):
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            "wss://api.hyperliquid.xyz/ws",
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait for connection
        while not self.connected:
            time.sleep(0.1)
            
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'data' in data and isinstance(data['data'], list):
                for trade in data['data']:
                    if isinstance(trade, dict) and 'time' in trade and 'px' in trade and 'sz' in trade:
                        current_time = datetime.fromtimestamp(int(trade['time'])/1000)
                        price = float(trade['px'])
                        size = float(trade['sz'])
                        for callback in self.callbacks:
                            callback(price, current_time, size)
        except Exception as e:
            print(f"Error processing message: {e}")
                
    def _on_error(self, ws, error):
        print(f"Error: {error}")
        
    def _on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")
        self.connected = False
        
    def _on_open(self, ws):
        print("Opened connection")
        self.connected = True
        
        # Use working format from before
        subscribe_message = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": "BTC"
            }
        }
        ws.send(json.dumps(subscribe_message))
        
    def add_trade_callback(self, callback):
        self.callbacks.append(callback)
        
    def close(self):
        if self.ws:
            self.ws.close()
