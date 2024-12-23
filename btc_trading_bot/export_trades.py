import pandas as pd
import json
from datetime import datetime

# Read the trade history
with open('last_trades.json', 'r') as f:
    trades = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(trades)

# Calculate additional metrics
df['profit_pct'] = (df['exit_price'] - df['entry_price']) / df['entry_price'] * 100
df['trade_duration'] = pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])
df['trade_duration_mins'] = df['trade_duration'].dt.total_seconds() / 60

# Reorder and select columns
columns = [
    'entry_time', 'exit_time',
    'entry_price', 'exit_price',
    'pnl', 'profit_pct',
    'trade_duration_mins',
    'exit_reason',
    'size'
]

# Format the DataFrame
df_export = df[columns].copy()
df_export['entry_time'] = pd.to_datetime(df_export['entry_time'])
df_export['exit_time'] = pd.to_datetime(df_export['exit_time'])
df_export['pnl'] = df_export['pnl'].round(2)
df_export['profit_pct'] = df_export['profit_pct'].round(2)
df_export['trade_duration_mins'] = df_export['trade_duration_mins'].round(2)

# Add summary row
summary = pd.DataFrame({
    'entry_time': ['SUMMARY'],
    'exit_time': [''],
    'entry_price': [df_export['entry_price'].mean()],
    'exit_price': [df_export['exit_price'].mean()],
    'pnl': [df_export['pnl'].sum()],
    'profit_pct': [df_export['profit_pct'].mean()],
    'trade_duration_mins': [df_export['trade_duration_mins'].mean()],
    'exit_reason': [''],
    'size': [df_export['size'].mean()]
})

df_export = pd.concat([df_export, summary])

# Export to Excel with formatting
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
filename = f'trade_history_{timestamp}.xlsx'

with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
    df_export.to_excel(writer, sheet_name='Trade History', index=False)
    
    # Get workbook and worksheet objects
    workbook = writer.book
    worksheet = writer.sheets['Trade History']
    
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D3D3D3',
        'border': 1
    })
    
    profit_format = workbook.add_format({
        'num_format': '$#,##0.00',
        'bg_color': '#C6EFCE',
        'font_color': '#006100'
    })
    
    loss_format = workbook.add_format({
        'num_format': '$#,##0.00',
        'bg_color': '#FFC7CE',
        'font_color': '#9C0006'
    })
    
    percent_format = workbook.add_format({'num_format': '0.00%'})
    currency_format = workbook.add_format({'num_format': '$#,##0.00'})
    
    # Apply formats
    worksheet.set_row(0, None, header_format)
    worksheet.set_column('A:B', 20)  # Time columns
    worksheet.set_column('C:D', 12, currency_format)  # Price columns
    worksheet.set_column('E:E', 12)  # PnL column
    worksheet.set_column('F:F', 10, percent_format)  # Profit % column
    worksheet.set_column('G:G', 15)  # Duration column
    worksheet.set_column('H:H', 20)  # Reason column
    worksheet.set_column('I:I', 15, currency_format)  # Size column
    
    # Apply conditional formatting to PnL column
    for row in range(1, len(df_export) + 1):
        worksheet.write_formula(
            row, 4,
            f'=IF(E{row+1}>0,E{row+1},E{row+1})',
            profit_format if df_export.iloc[row-1]['pnl'] > 0 else loss_format,
            df_export.iloc[row-1]['pnl']
        )

print(f"Trade history exported to {filename}")

# Print summary statistics
print("\nTrade Summary:")
print(f"Total Trades: {len(df_export)-1}")  # -1 for summary row
print(f"Total PnL: ${df_export['pnl'].sum():.2f}")
print(f"Win Rate: {(df_export['pnl'] > 0).mean()*100:.1f}%")
print(f"Average Trade Duration: {df_export['trade_duration_mins'].mean():.1f} minutes")
