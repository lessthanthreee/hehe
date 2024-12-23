import json
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob

def analyze_trades_json(trades_file):
    """Analyze trades from JSON file"""
    print(f"\nAnalyzing trades from {trades_file}")
    
    with open(trades_file, 'r') as f:
        trades = json.load(f)
    
    if not trades:
        print(f"No trades found in {trades_file}")
        return
        
    # Convert to DataFrame
    df = pd.DataFrame(trades)
    df['entry_time'] = pd.to_datetime(df['entry_time'], format='mixed')
    df['exit_time'] = pd.to_datetime(df['exit_time'], format='mixed')
    df['duration'] = df['exit_time'] - df['entry_time']
    
    # Calculate statistics
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    losing_trades = len(df[df['pnl'] <= 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_profit = df[df['pnl'] > 0]['pnl'].sum()
    total_loss = df[df['pnl'] <= 0]['pnl'].sum()
    net_pnl = total_profit + total_loss
    
    total_fees = df['total_fees'].sum() if 'total_fees' in df.columns else 0
    avg_fees_per_trade = total_fees / total_trades if total_trades > 0 else 0
    
    avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['pnl'] <= 0]['pnl'].mean() if losing_trades > 0 else 0
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
    
    avg_duration = df['duration'].mean()
    trades_per_hour = total_trades / (df['duration'].sum().total_seconds() / 3600) if total_trades > 0 else 0
    
    # Print results
    print(f"\nTrade Analysis for {os.path.basename(trades_file)}")
    print("=" * 50)
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades}")
    print(f"Losing Trades: {losing_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"\nTotal Profit: {total_profit:,.2f}%")
    print(f"Total Loss: {total_loss:,.2f}%")
    print(f"Net P&L: {net_pnl:,.2f}%")
    print(f"\nTotal Fees: ${total_fees:,.2f}")
    print(f"Average Fees per Trade: ${avg_fees_per_trade:.2f}")
    print(f"\nAverage Win: {avg_win:,.2f}%")
    print(f"Average Loss: {avg_loss:,.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Average Trade Duration: {avg_duration}")
    print(f"Trades per Hour: {trades_per_hour:.2f}")
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # Cumulative P&L
    plt.subplot(2, 2, 1)
    df['cumulative_pnl'] = df['pnl'].cumsum()
    plt.plot(df['entry_time'], df['cumulative_pnl'])
    plt.title('Cumulative P&L')
    plt.xlabel('Time')
    plt.ylabel('Profit/Loss (%)')
    plt.xticks(rotation=45)
    
    # P&L Distribution
    plt.subplot(2, 2, 2)
    sns.histplot(data=df['pnl'], bins=30)
    plt.title('P&L Distribution')
    plt.xlabel('Profit/Loss (%)')
    plt.ylabel('Frequency')
    
    # Win Rate Over Time
    plt.subplot(2, 2, 3)
    df['win'] = df['pnl'] > 0
    df['win_rate'] = df['win'].rolling(window=20, min_periods=1).mean()
    plt.plot(df['entry_time'], df['win_rate'])
    plt.title('Win Rate (20-trade MA)')
    plt.xlabel('Time')
    plt.ylabel('Win Rate')
    plt.xticks(rotation=45)
    
    # Trade Duration Distribution
    plt.subplot(2, 2, 4)
    sns.histplot(data=df['duration'].dt.total_seconds() / 60, bins=30)
    plt.title('Trade Duration Distribution')
    plt.xlabel('Duration (minutes)')
    plt.ylabel('Frequency')
    
    plt.tight_layout()
    plt.savefig(f"analysis_{os.path.basename(trades_file).split('.')[0]}.png")
    plt.close()

def analyze_strategy_comparison(comparison_file):
    """Analyze strategy comparison results"""
    print(f"\nAnalyzing strategy comparison from {comparison_file}")
    
    with open(comparison_file, 'r') as f:
        data = json.load(f)
    
    results = []
    for strategy_name, strategy_data in data.items():
        metrics = strategy_data['metrics']
        results.append({
            'Strategy': strategy_name,
            'Total Trades': metrics['total_trades'],
            'Win Rate': metrics['win_rate'],
            'Total PnL': metrics['total_pnl'],
            'ROI': metrics['roi'],
            'Sharpe Ratio': metrics['sharpe_ratio'],
            'Profit Factor': metrics['profit_factor'],
            'Max Drawdown': metrics['max_drawdown'],
            'Avg Duration (mins)': metrics['avg_trade_duration_mins']
        })
    
    df = pd.DataFrame(results)
    
    # Print results
    print("\nStrategy Performance Summary")
    print("=" * 50)
    print(df.to_string(index=False))
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # ROI Comparison
    plt.subplot(2, 2, 1)
    plt.bar(df['Strategy'], df['ROI'])
    plt.title('Return on Investment by Strategy')
    plt.xlabel('Strategy')
    plt.ylabel('ROI (%)')
    plt.xticks(rotation=45)
    
    # Win Rate Comparison
    plt.subplot(2, 2, 2)
    plt.bar(df['Strategy'], df['Win Rate'])
    plt.title('Win Rate by Strategy')
    plt.xlabel('Strategy')
    plt.ylabel('Win Rate (%)')
    plt.xticks(rotation=45)
    
    # Profit Factor Comparison
    plt.subplot(2, 2, 3)
    profit_factors = df['Profit Factor'].replace([float('inf')], 0)  # Replace inf with 0 for visualization
    plt.bar(df['Strategy'], profit_factors)
    plt.title('Profit Factor by Strategy')
    plt.xlabel('Strategy')
    plt.ylabel('Profit Factor')
    plt.xticks(rotation=45)
    
    # Max Drawdown Comparison
    plt.subplot(2, 2, 4)
    plt.bar(df['Strategy'], df['Max Drawdown'])
    plt.title('Maximum Drawdown by Strategy')
    plt.xlabel('Strategy')
    plt.ylabel('Max Drawdown (%)')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(f"analysis_{os.path.basename(comparison_file).split('.')[0]}.png")
    plt.close()

if __name__ == "__main__":
    # Analyze trade files for each strategy
    strategy_files = ['trades_aggressive.json', 'trades_moderate.json', 'trades_conservative.json']
    for trades_file in strategy_files:
        if os.path.exists(trades_file):
            analyze_trades_json(trades_file)
        else:
            print(f"No trades file found for {trades_file}")

    # Analyze strategy comparison
    comparison_files = glob.glob('strategy_comparison_*.json')
    if comparison_files:
        latest_comparison = max(comparison_files, key=os.path.getmtime)
        analyze_strategy_comparison(latest_comparison)
    else:
        print("No strategy comparison files found")
