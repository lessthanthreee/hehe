import requests
import pandas as pd
import numpy as np
import websocket
import json
import threading
from queue import Queue
from datetime import datetime, timedelta
import time

# Hyperliquid API URLs
WS_URL = 'wss://api.hyperliquid.xyz/ws'
API_URL = 'https://api.hyperliquid.xyz/info'

class TradingStrategy:
    def __init__(self, leverage=50, initial_capital=1000):
        self.leverage = leverage
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.position = 0
        self.entry_price = 0
        self.trades = []
        self.base_stop_loss_pct = 0.005  # Base stop loss at 0.5%
        self.base_take_profit_pct = 0.01  # Base take profit at 1%
        self.atr_period = 14  # Period for ATR calculation
        
    def calculate_rsi(self, data, periods=7):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    def calculate_indicators(self, df):
        # RSI
        df['RSI'] = self.calculate_rsi(df['close'])
        
        # Moving Averages
        df['SMA_50'] = df['close'].rolling(window=10).mean()
        df['SMA_200'] = df['close'].rolling(window=20).mean()
        
        # Bollinger Bands
        df['BB_Middle'] = df['close'].rolling(window=20).mean()
        df['BB_Std'] = df['close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * 2)
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Volume-weighted indicators
        df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / df['Volume_SMA']
        
        # ATR for dynamic stop loss/take profit
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(window=self.atr_period).mean()
        
        # Trend Strength
        df['ADX'] = self.calculate_adx(df)
        
        return df
        
    def calculate_adx(self, df, period=14):
        # Calculate +DM and -DM
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        plus_dm = pd.Series(0.0, index=df.index)
        minus_dm = pd.Series(0.0, index=df.index)
        
        plus_dm[high_diff > low_diff] = high_diff[high_diff > low_diff]
        plus_dm[high_diff <= 0] = 0.0
        minus_dm[low_diff > high_diff] = low_diff[low_diff > high_diff]
        minus_dm[low_diff <= 0] = 0.0
        
        # Calculate TR
        tr = pd.DataFrame(index=df.index)
        tr['HL'] = df['high'] - df['low']
        tr['HC'] = abs(df['high'] - df['close'].shift(1))
        tr['LC'] = abs(df['low'] - df['close'].shift(1))
        tr['TR'] = tr.max(axis=1)
        
        # Calculate smoothed averages
        tr_smooth = tr['TR'].rolling(window=period).mean()
        plus_dm_smooth = plus_dm.rolling(window=period).mean()
        minus_dm_smooth = minus_dm.rolling(window=period).mean()
        
        # Calculate +DI and -DI
        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)
        
        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
        
    def generate_signals(self, df):
        df['Signal'] = 0
        
        # Dynamic stop loss and take profit based on ATR
        df['Dynamic_SL'] = df['ATR'] * 1.5  # 1.5x ATR for stop loss
        df['Dynamic_TP'] = df['ATR'] * 3.0  # 3x ATR for take profit
        
        # Entry conditions for LONG position
        long_conditions = (
            (df['RSI'] < 30) &  # Oversold
            (df['MACD'] > df['MACD_Signal']) &  # MACD crossover
            (df['close'] < df['BB_Lower']) &  # Price below lower BB
            (df['SMA_50'] > df['SMA_200']) &  # Golden cross
            (df['Volume_Ratio'] > 1.2) &  # Above average volume
            (df['close'] < df['VWAP']) &  # Price below VWAP
            (df['ADX'] > 25)  # Strong trend
        )
        
        # Entry conditions for SHORT position
        short_conditions = (
            (df['RSI'] > 70) &  # Overbought
            (df['MACD'] < df['MACD_Signal']) &  # MACD crossover
            (df['close'] > df['BB_Upper']) &  # Price above upper BB
            (df['SMA_50'] < df['SMA_200']) &  # Death cross
            (df['Volume_Ratio'] > 1.2) &  # Above average volume
            (df['close'] > df['VWAP']) &  # Price above VWAP
            (df['ADX'] > 25)  # Strong trend
        )
        
        df.loc[long_conditions, 'Signal'] = 1
        df.loc[short_conditions, 'Signal'] = -1
        
        return df
        
    def execute_trade(self, current_price, signal, dynamic_sl, dynamic_tp):
        if signal != 0 and self.position == 0:  # Open new position
            position_size = self.portfolio_value * self.leverage
            self.position = position_size * signal  # Positive for long, negative for short
            self.entry_price = current_price
            
            # Calculate dynamic stop loss and take profit levels
            if signal > 0:  # Long position
                self.stop_loss = self.entry_price * (1 - max(self.base_stop_loss_pct, dynamic_sl/current_price))
                self.take_profit = self.entry_price * (1 + max(self.base_take_profit_pct, dynamic_tp/current_price))
            else:  # Short position
                self.stop_loss = self.entry_price * (1 + max(self.base_stop_loss_pct, dynamic_sl/current_price))
                self.take_profit = self.entry_price * (1 - max(self.base_take_profit_pct, dynamic_tp/current_price))
                
            trade_type = "LONG" if signal > 0 else "SHORT"
            self.trades.append(f"{trade_type} entry at ${current_price:,.2f}")
            
        elif self.position != 0:  # Check for exit conditions
            pnl = 0
            exit_reason = ""
            
            # Calculate current PnL
            price_change = (current_price - self.entry_price) / self.entry_price
            unrealized_pnl = self.position * price_change
            
            # Check stop loss and take profit
            if self.position > 0:  # Long position
                if current_price <= self.stop_loss:
                    exit_reason = "Stop Loss"
                    pnl = unrealized_pnl
                elif current_price >= self.take_profit:
                    exit_reason = "Take Profit"
                    pnl = unrealized_pnl
            else:  # Short position
                if current_price >= self.stop_loss:
                    exit_reason = "Stop Loss"
                    pnl = unrealized_pnl
                elif current_price <= self.take_profit:
                    exit_reason = "Take Profit"
                    pnl = unrealized_pnl
            
            # Exit position if stop loss or take profit hit
            if exit_reason:
                self.portfolio_value += pnl
                self.trades.append(f"Exit at ${current_price:,.2f} ({exit_reason}) - PnL: ${pnl:,.2f}")
                self.position = 0
                
        return self.portfolio_value - self.initial_capital

class HyperliquidAPI:
    def __init__(self):
        self.data_queue = Queue()
        self.ws = None
        self.trades = []
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'data' in data and isinstance(data['data'], list):
                for trade in data['data']:
                    if isinstance(trade, dict) and 'time' in trade and 'px' in trade:
                        self.trades.append({
                            'timestamp': int(trade['time']),
                            'price': float(trade['px']),
                        })
        except Exception as e:
            print(f"Error processing message: {e}")

    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket connection closed")

    def on_open(self, ws):
        print("WebSocket connection opened")
        subscribe_msg = {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": "BTC"
            }
        }
        ws.send(json.dumps(subscribe_msg))

    def connect_websocket(self):
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            WS_URL,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
    def fetch_historical_data(self):
        try:
            market_info = requests.post(API_URL, json={"type": "metaAndAssetCtxs"})
            print("Market info received:", market_info.status_code)
            
            print("Connecting to WebSocket...")
            self.connect_websocket()
            
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            print("Collecting trade data (this will take 2 minutes)...")
            time.sleep(120)  # 2 minutes of data collection
            
            self.ws.close()
            
            if not self.trades:
                print("No trades collected")
                return None
                
            df = pd.DataFrame(self.trades)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            ohlc = df.set_index('timestamp').price.resample('1min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }).dropna()
            
            volume = df.set_index('timestamp').price.resample('1min').count().dropna()
            
            candles = pd.concat([ohlc, volume.rename('volume')], axis=1)
            
            print("\nSample of collected data:")
            print(candles.head())
            return candles
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

def main():
    print("Initializing Hyperliquid API...")
    api = HyperliquidAPI()
    
    print("Fetching historical BTC data...")
    df = api.fetch_historical_data()
    
    if df is not None and not df.empty:
        print(f"\nRetrieved {len(df)} candles")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        
        strategy = TradingStrategy(leverage=50, initial_capital=1000)
        
        # Calculate indicators
        print("\nCalculating technical indicators...")
        df = strategy.calculate_indicators(df)
        
        # Generate trading signals
        print("Generating trading signals...")
        df = strategy.generate_signals(df)
        
        # Execute trades
        print("Executing trades...")
        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            signal = df['Signal'].iloc[i]
            dynamic_sl = df['Dynamic_SL'].iloc[i]
            dynamic_tp = df['Dynamic_TP'].iloc[i]
            pnl = strategy.execute_trade(current_price, signal, dynamic_sl, dynamic_tp)
        
        print("\nTrading Results:")
        print("================")
        print(f"Initial Capital: ${strategy.initial_capital:,.2f}")
        print(f"Final Portfolio Value: ${strategy.portfolio_value:,.2f}")
        print(f"Total PnL: ${pnl:,.2f}")
        print(f"ROI: {((strategy.portfolio_value / strategy.initial_capital) - 1) * 100:.2f}%")
        
        print("\nTrade History:")
        for trade in strategy.trades:
            print(trade)
    else:
        print("Failed to fetch historical data")

if __name__ == '__main__':
    main()
