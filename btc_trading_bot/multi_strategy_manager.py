from datetime import datetime, timedelta
from hyperliquid_client import HyperliquidClient
import time

class StrategyManager:
    def __init__(self, strategies, total_capital, max_drawdown):
        self.strategies = strategies
        self.total_capital = total_capital
        self.max_drawdown = max_drawdown
        self.start_time = None
        self.client = None
        
    def run(self, duration_minutes):
        print("\nStarting Multi-Strategy Manager")
        print("=" * 50)
        print(f"Total Capital: ${self.total_capital:,.2f}")
        print(f"Capital per Strategy: ${self.total_capital/len(self.strategies):,.2f}")
        print(f"Max Drawdown Limit: ${self.max_drawdown:,.2f}")
        print(f"Number of Strategies: {len(self.strategies)}")
        
        print("\nStrategy Settings:\n")
        for i, strategy in enumerate(self.strategies, 1):
            print(f"Strategy #{i}:")
            print(f"  - Type: {strategy.__class__.__name__}")
            print(f"  - Initial Capital: ${strategy.portfolio_value:,.2f}\n")
        
        # Connect to Hyperliquid
        self.client = HyperliquidClient()
        self.client.connect()
        
        # Add callback for each strategy
        for strategy in self.strategies:
            self.client.add_trade_callback(strategy.execute_trade)
            
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(minutes=duration_minutes)
        
        try:
            while datetime.now() < end_time:
                # Print results every minute
                if datetime.now().second == 0:
                    self.print_results()
                    
                # Check max drawdown
                total_pnl = sum(s.portfolio_value - s.initial_capital for s in self.strategies)
                if total_pnl <= self.max_drawdown:
                    print(f"\nMax drawdown (${self.max_drawdown:,.2f}) reached. Stopping all strategies.")
                    break
                    
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping strategies...")
        finally:
            self.client.close()
            self.print_final_results()
            
    def print_results(self):
        print("\nCurrent Results:")
        print("=" * 50)
        
        total_pnl = sum(s.portfolio_value - s.initial_capital for s in self.strategies)
        print(f"\nTotal P&L: ${total_pnl:,.2f}")
        
        for i, strategy in enumerate(self.strategies, 1):
            pnl = strategy.portfolio_value - strategy.initial_capital
            completed_trades = len([t for t in strategy.trades if 'exit_price' in t])
            
            print(f"\nStrategy #{i}:")
            print(f"P&L: ${pnl:,.2f}")
            print(f"Completed Trades: {completed_trades}")
            
            if completed_trades > 0:
                last_trade = next(t for t in reversed(strategy.trades) if 'exit_price' in t)
                print(f"Last Trade P&L: ${last_trade['pnl']:,.2f}")
                
    def print_final_results(self):
        print("\nFinal Results:")
        print("=" * 50)
        
        for i, strategy in enumerate(self.strategies, 1):
            print(f"\nStrategy #{i} Summary:")
            completed_trades = [t for t in strategy.trades if 'exit_price' in t]
            if completed_trades:
                total_pnl = sum(t['pnl'] for t in completed_trades)
                win_trades = len([t for t in completed_trades if t['pnl'] > 0])
                print(f"Total P&L: ${total_pnl:,.2f}")
                print(f"Total Trades: {len(completed_trades)}")
                print(f"Win Rate: {win_trades/len(completed_trades)*100:.1f}%")
                print(f"Average P&L per Trade: ${total_pnl/len(completed_trades):,.2f}")
                print("\nTrade Breakdown:")
                print(f"Profit Target Hits: {len([t for t in completed_trades if t.get('exit_reason')=='Profit Target'])}")
                print(f"Stop Losses: {len([t for t in completed_trades if t.get('exit_reason')=='Stop Loss'])}")
                print(f"Time Limits: {len([t for t in completed_trades if t.get('exit_reason')=='Time Limit'])}")
                print(f"EMA Crosses: {len([t for t in completed_trades if t.get('exit_reason')=='EMA Cross'])}")
