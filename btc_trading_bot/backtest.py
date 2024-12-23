import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from strategies import (
    RSIMACDStrategy,
    BollingerBandsStrategy,
    MovingAverageCrossStrategy,
    RegressionStrategy,
    VolumeWeightedStrategy
)

def backtest_strategy(strategy, data):
    """Run backtest for a single strategy"""
    df = strategy.calculate_indicators(data.copy())
    df = strategy.generate_signals(df)
    
    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        signal = df['Signal'].iloc[i]
        strategy.execute_trade(current_price, signal)
        
    return strategy.performance_metrics, strategy.trades

def compare_strategies(data):
    """Compare performance of all strategies"""
    strategies = {
        'RSI_MACD': RSIMACDStrategy(),
        'Bollinger_Bands': BollingerBandsStrategy(),
        'Moving_Average_Cross': MovingAverageCrossStrategy(),
        'Regression': RegressionStrategy(),
        'Volume_Weighted': VolumeWeightedStrategy()
    }
    
    results = {}
    for name, strategy in strategies.items():
        metrics, trades = backtest_strategy(strategy, data)
        results[name] = {
            'metrics': metrics,
            'trades': trades
        }
        
    return results

def print_results(results):
    """Print formatted results of strategy comparison"""
    print("\nStrategy Comparison Results:")
    print("=" * 80)
    
    metrics_to_show = [
        'total_trades',
        'winning_trades',
        'losing_trades',
        'total_pnl',
        'max_drawdown',
        'win_rate',
        'roi'
    ]
    
    # Create comparison table
    rows = []
    for strategy_name, result in results.items():
        metrics = result['metrics']
        row = [strategy_name]
        for metric in metrics_to_show:
            value = metrics[metric]
            if metric in ['win_rate', 'roi', 'max_drawdown']:
                row.append(f"{value:.2f}%")
            elif metric in ['total_pnl']:
                row.append(f"${value:.2f}")
            else:
                row.append(str(value))
        rows.append(row)
    
    # Print table header
    header = ['Strategy'] + [m.replace('_', ' ').title() for m in metrics_to_show]
    print("| " + " | ".join(f"{h:<15}" for h in header) + " |")
    print("|" + "|".join("-" * 16 for _ in range(len(header))) + "|")
    
    # Print table rows
    for row in rows:
        print("| " + " | ".join(f"{str(cell):<15}" for cell in row) + " |")
    
    # Find best strategy
    best_strategy = max(results.items(), key=lambda x: x[1]['metrics']['roi'])[0]
    print("\nBest Performing Strategy:", best_strategy)
    
    return best_strategy

if __name__ == "__main__":
    # Load historical data
    data = pd.read_csv("historical_data.csv")
    results = compare_strategies(data)
    best_strategy = print_results(results)
    
    # Save detailed results
    with open("backtest_results.json", "w") as f:
        json.dump(results, f, indent=4, default=str)
