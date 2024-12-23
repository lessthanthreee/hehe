import concurrent.futures
import json
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from run_bot import HyperliquidAPI
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
        logging.FileHandler('strategy_test.log'),
        logging.StreamHandler()
    ]
)

def calculate_sharpe_ratio(returns):
    """Calculate the Sharpe ratio of the strategy"""
    if len(returns) < 2:
        return 0
    return np.mean(returns) / np.std(returns) * np.sqrt(365 * 24)  # Annualized for hourly data

def run_strategy(strategy_name, strategy_class):
    """Run a single strategy and return its results"""
    try:
        logging.info(f"Starting {strategy_name} strategy test")
        strategy = strategy_class()
        api = HyperliquidAPI(strategy)
        
        # Run for 20 minutes for quick testing
        logging.info(f"Running {strategy_name} for 20 minutes...")
        api.run(duration_hours=1/3)  # 20 minutes = 1/3 hour
        
        # Calculate additional metrics
        returns = []
        prev_value = strategy.initial_capital
        for trade in strategy.trades:
            if 'portfolio_value' in trade:
                returns.append((trade['portfolio_value'] - prev_value) / prev_value)
                prev_value = trade['portfolio_value']
        
        sharpe = calculate_sharpe_ratio(returns)
        avg_trade_duration = 0
        if len(strategy.trades) > 1:
            durations = []
            for i in range(1, len(strategy.trades)):
                entry_time = datetime.fromisoformat(strategy.trades[i-1]['timestamp'])
                exit_time = datetime.fromisoformat(strategy.trades[i]['timestamp'])
                duration = (exit_time - entry_time).total_seconds() / 60  # in minutes
                durations.append(duration)
            avg_trade_duration = sum(durations) / len(durations)
        
        strategy.performance_metrics.update({
            'sharpe_ratio': sharpe,
            'avg_trade_duration_mins': avg_trade_duration,
            'profit_factor': (
                abs(sum(r for r in returns if r > 0)) / 
                abs(sum(r for r in returns if r < 0)) if any(r < 0 for r in returns) else float('inf')
            )
        })
        
        logging.info(f"{strategy_name} completed with {len(strategy.trades)} trades")
        if len(strategy.trades) > 0:
            logging.info(f"Performance: ROI={strategy.performance_metrics['roi']:.2f}%, "
                        f"Win Rate={strategy.performance_metrics['win_rate']:.2f}%, "
                        f"Sharpe={sharpe:.2f}")
        else:
            logging.warning(f"{strategy_name} did not execute any trades")
        
        return {
            'strategy': strategy_name,
            'metrics': strategy.performance_metrics,
            'trades': strategy.trades
        }
    except Exception as e:
        logging.error(f"Error running {strategy_name}: {e}")
        return None

def compare_strategies():
    """Run all strategies in parallel and compare results"""
    strategies = {
        'RSI_MACD': RSIMACDStrategy,
        'Bollinger_Bands': BollingerBandsStrategy,
        'Moving_Average_Cross': MovingAverageCrossStrategy,
        'Momentum': MomentumStrategy,
        'VWAP': VWAPStrategy,
        'Scalping': ScalpingStrategy
    }
    
    results = {}
    
    # Run strategies in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(strategies)) as executor:
        future_to_strategy = {
            executor.submit(run_strategy, name, strategy_class): name
            for name, strategy_class in strategies.items()
        }
        
        for future in concurrent.futures.as_completed(future_to_strategy):
            strategy_name = future_to_strategy[future]
            try:
                result = future.result()
                if result:
                    results[strategy_name] = result
            except Exception as e:
                logging.error(f"Strategy {strategy_name} generated an exception: {e}")
    
    return results

def print_comparison(results):
    """Print formatted comparison of strategy results"""
    print("\nStrategy Performance Comparison:")
    print("=" * 120)
    
    # Create DataFrame for easy comparison
    comparison_data = []
    for strategy_name, result in results.items():
        metrics = result['metrics']
        comparison_data.append({
            'Strategy': strategy_name,
            'Total PnL': f"${metrics['total_pnl']:.2f}",
            'ROI': f"{metrics['roi']:.2f}%",
            'Win Rate': f"{metrics['win_rate']:.2f}%",
            'Sharpe': f"{metrics.get('sharpe_ratio', 0):.2f}",
            'Profit Factor': f"{metrics.get('profit_factor', 0):.2f}",
            'Avg Duration': f"{metrics.get('avg_trade_duration_mins', 0):.1f}m",
            'Total Trades': metrics['total_trades'],
            'Max DD': f"{metrics['max_drawdown']:.2f}%"
        })
    
    df = pd.DataFrame(comparison_data)
    print(df.to_string(index=False))
    
    # Find best strategy by multiple metrics
    best_roi = max(results.items(), key=lambda x: x[1]['metrics']['roi'])[0]
    best_sharpe = max(results.items(), key=lambda x: x[1]['metrics'].get('sharpe_ratio', 0))[0]
    best_profit_factor = max(results.items(), key=lambda x: x[1]['metrics'].get('profit_factor', 0))[0]
    
    print(f"\nBest ROI Strategy: {best_roi}")
    print(f"Best Sharpe Ratio Strategy: {best_sharpe}")
    print(f"Best Profit Factor Strategy: {best_profit_factor}")
    
    # Recommend overall best strategy
    scores = {}
    for name, result in results.items():
        metrics = result['metrics']
        score = (
            metrics['roi'] / 100 +  # Normalized ROI
            metrics.get('sharpe_ratio', 0) +  # Sharpe ratio
            min(metrics.get('profit_factor', 0), 3) / 3 +  # Capped profit factor
            min(metrics['win_rate'], 70) / 70 -  # Capped win rate
            metrics['max_drawdown'] / 100  # Drawdown penalty
        )
        scores[name] = score
    
    best_overall = max(scores.items(), key=lambda x: x[1])[0]
    print(f"\nRecommended Strategy: {best_overall}")
    
    return best_overall

def save_results(results):
    """Save detailed results to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save complete results
    with open(f"strategy_comparison_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=4, default=str)
    
    # Save summary CSV
    summary_data = []
    for strategy_name, result in results.items():
        metrics = result['metrics']
        summary_data.append({
            'Strategy': strategy_name,
            'Total_PnL': metrics['total_pnl'],
            'ROI': metrics['roi'],
            'Win_Rate': metrics['win_rate'],
            'Sharpe_Ratio': metrics.get('sharpe_ratio', 0),
            'Profit_Factor': metrics.get('profit_factor', 0),
            'Avg_Trade_Duration': metrics.get('avg_trade_duration_mins', 0),
            'Total_Trades': metrics['total_trades'],
            'Max_Drawdown': metrics['max_drawdown']
        })
    
    pd.DataFrame(summary_data).to_csv(f"strategy_summary_{timestamp}.csv", index=False)
    
    logging.info(f"Results saved to strategy_comparison_{timestamp}.json and strategy_summary_{timestamp}.csv")

if __name__ == "__main__":
    print("Starting strategy comparison test...")
    print("This will run all strategies in parallel for 20 minutes each")
    print("Results will be saved to files and displayed here")
    
    results = compare_strategies()
    best_strategy = print_comparison(results)
    save_results(results)
    
    print("\nTest completed! Check strategy_test.log for detailed logs")
    print("You can now run the best performing strategy continuously using:")
    print(f"python run_bot.py --strategy {best_strategy}")
