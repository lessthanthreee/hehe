import logging
from datetime import datetime

def setup_logging():
    """Setup logging with both file and console output"""
    log_filename = f'trades_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create handlers
    file_handler = logging.FileHandler(log_filename)
    console_handler = logging.StreamHandler()
    
    # Create formatters and add it to handlers
    log_format = '%(message)s'
    file_handler.setFormatter(logging.Formatter(log_format))
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Add handlers to the logger
    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)
    
    # Set level
    logging.root.setLevel(logging.INFO)
    
    return log_filename

def log_trade_summary(trades, initial_capital, final_capital):
    """Log a human-readable trade summary"""
    if not trades:
        return
    
    total_pnl = final_capital - initial_capital
    total_return = (final_capital / initial_capital - 1) * 100
    
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
    break_even = [t for t in trades if t.get('pnl', 0) == 0]
    
    # Print Header
    logging.info("\n" + "="*50)
    logging.info("TRADING SESSION SUMMARY")
    logging.info("="*50)
    
    # Account Summary
    logging.info("\nACCOUNT SUMMARY:")
    logging.info(f"Initial Capital: ${initial_capital:,.2f}")
    logging.info(f"Final Capital:   ${final_capital:,.2f}")
    logging.info(f"Total P&L:       ${total_pnl:,.2f} ({total_return:.2f}%)")
    
    # Trade Statistics
    logging.info("\nTRADE STATISTICS:")
    logging.info(f"Total Trades:     {len(trades)}")
    logging.info(f"Winning Trades:   {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
    logging.info(f"Losing Trades:    {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
    logging.info(f"Break Even:       {len(break_even)}")
    
    # Calculate total fees
    total_fees = sum(t.get('total_fees', 0) for t in trades)
    avg_fee_impact = sum(t.get('fee_impact_pct', 0) for t in trades) / len(trades) if trades else 0
    
    logging.info(f"\nFEE ANALYSIS:")
    logging.info(f"Total Fees:      ${total_fees:,.2f}")
    logging.info(f"Avg Fee Impact:  {avg_fee_impact:.3f}% per trade")
    logging.info(f"Net P&L:         ${total_pnl:,.2f} (after fees)")
    
    if winning_trades:
        best_trade = max(trades, key=lambda x: x.get('pnl', 0))
        logging.info(f"\nBEST TRADE:")
        logging.info(f"Type:           {best_trade['type']}")
        logging.info(f"Entry:          ${best_trade['entry_price']:,.2f}")
        logging.info(f"Exit:           ${best_trade['exit_price']:,.2f}")
        logging.info(f"P&L:            ${best_trade['pnl']:,.2f} ({best_trade['pnl_pct']:.2f}%)")
        logging.info(f"Exit Reason:    {best_trade['exit_reason']}")
    
    if losing_trades:
        worst_trade = min(trades, key=lambda x: x.get('pnl', 0))
        logging.info(f"\nWORST TRADE:")
        logging.info(f"Type:           {worst_trade['type']}")
        logging.info(f"Entry:          ${worst_trade['entry_price']:,.2f}")
        logging.info(f"Exit:           ${worst_trade['exit_price']:,.2f}")
        logging.info(f"P&L:            ${worst_trade['pnl']:,.2f} ({worst_trade['pnl_pct']:.2f}%)")
        logging.info(f"Exit Reason:    {worst_trade['exit_reason']}")
    
    # Detailed Trade History
    logging.info("\n" + "="*50)
    logging.info("DETAILED TRADE HISTORY")
    logging.info("="*50)
    
    for i, trade in enumerate(trades, 1):
        if 'exit_price' in trade:  # Only show completed trades
            logging.info(f"\nTrade #{i}:")
            logging.info(f"Type:        {trade['type']}")
            logging.info(f"Entry:       ${trade['entry_price']:,.2f}")
            logging.info(f"Exit:        ${trade['exit_price']:,.2f}")
            logging.info(f"Raw P&L:     {trade.get('raw_pnl_pct', 0):.2f}%")
            logging.info(f"Fees:        ${trade.get('total_fees', 0):,.2f} ({trade.get('fee_impact_pct', 0):.3f}%)")
            logging.info(f"Net P&L:     ${trade['pnl']:,.2f} ({trade.get('actual_pnl_pct', 0):.2f}%)")
            logging.info(f"RSI:         {trade['entry_rsi']:.1f}")
            try:
                duration = trade['exit_time'] - trade['entry_time']
                logging.info(f"Duration:    {duration}")
            except:
                pass
    
    # Final Summary
    logging.info("\n" + "="*50)
    logging.info("FINAL RESULTS")
    logging.info("="*50)
    logging.info(f"Net P&L:         ${total_pnl:,.2f}")
    logging.info(f"Return:          {total_return:.2f}%")
    logging.info(f"Win Rate:        {len(winning_trades)/len(trades)*100:.1f}%")
    if winning_trades:
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
        logging.info(f"Average Win:     ${avg_win:,.2f}")
    if losing_trades:
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
        logging.info(f"Average Loss:    ${avg_loss:,.2f}")
    logging.info("="*50)
