from flask import Flask, render_template, jsonify
import concurrent.futures
import json
import logging
from datetime import datetime
import pandas as pd
from run_bot import HyperliquidAPI
from strategies import (
    RSIMACDStrategy,
    BollingerBandsStrategy,
    MovingAverageCrossStrategy,
    RegressionStrategy,
    VolumeWeightedStrategy
)

app = Flask(__name__)

# Setup logging with less verbose output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('strategy_test.log'),
        logging.StreamHandler()
    ]
)

def run_strategy(strategy_name, strategy_class, duration_hours=8, initial_capital=1000):
    """Run a single strategy and return its results"""
    try:
        strategy = strategy_class(initial_capital=initial_capital)
        api = HyperliquidAPI(strategy)
        api.run(duration_hours=duration_hours)
        
        return {
            'strategy': strategy_name,
            'metrics': strategy.performance_metrics,
            'trades': strategy.trades
        }
    except Exception as e:
        logging.error(f"Error running {strategy_name}: {e}")
        return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_test')
def start_test():
    strategies = {
        'RSI_MACD': RSIMACDStrategy,
        'Bollinger_Bands': BollingerBandsStrategy,
        'Moving_Average_Cross': MovingAverageCrossStrategy,
        'Regression': RegressionStrategy,
        'Volume_Weighted': VolumeWeightedStrategy
    }
    
    results = {}
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
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"strategy_comparison_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=4, default=str)
    
    return jsonify(results)

@app.route('/get_latest_results')
def get_latest_results():
    import glob
    import os
    
    # Get the most recent results file
    files = glob.glob("strategy_comparison_*.json")
    if not files:
        return jsonify({"error": "No results found"})
    
    latest_file = max(files, key=os.path.getctime)
    with open(latest_file, 'r') as f:
        results = json.load(f)
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
