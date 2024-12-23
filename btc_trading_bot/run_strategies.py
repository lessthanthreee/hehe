from multi_strategy_manager import StrategyManager
from macd_volume_strategy import MACDVolumeStrategy

def main():
    # Create MACD + Volume strategy
    strategy = MACDVolumeStrategy(
        initial_capital=5000,  # Use all capital
        leverage=50           # Max leverage
    )
    
    # Create strategy manager
    manager = StrategyManager(
        strategies=[strategy],
        total_capital=5000,
        max_drawdown=-300    # Still keep safety
    )
    
    # Run strategy
    manager.run(duration_minutes=20)

if __name__ == "__main__":
    main()
