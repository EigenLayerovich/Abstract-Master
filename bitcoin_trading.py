import pandas as pd
import numpy as np

def simulate_bitcoin_prices(days, initial_price=60000, mu=0.1, sigma=0.8):
    np.random.seed(42)  # For reproducibility
    dt = 1/365
    prices = [initial_price]
    for _ in range(1, days):
        # Geometric Brownian Motion
        drift = (mu - 0.5 * sigma**2) * dt
        shock = sigma * np.sqrt(dt) * np.random.normal()
        price = prices[-1] * np.exp(drift + shock)
        prices.append(price)

    dates = pd.date_range(start=pd.Timestamp.today() - pd.Timedelta(days=days-1), periods=days)
    df = pd.DataFrame({'Date': dates, 'Price': prices})
    return df

def run_trading_algo():
    # Simulate 60 days of data. To make sure we get MAs, we'll just output the 60 days
    df = simulate_bitcoin_prices(60)

    df['MA7'] = df['Price'].rolling(window=7).mean()
    df['MA30'] = df['Price'].rolling(window=30).mean()

    cash = 100000.0
    btc = 0.0

    print("Daily Ledger:")
    print(f"{'Date':<12} | {'Price':<10} | {'MA7':<10} | {'MA30':<10} | {'Action':<10} | {'Cash':<12} | {'BTC':<10} | {'Portfolio Value':<15}")
    print("-" * 105)

    for i in range(len(df)):
        price = df.loc[i, 'Price']
        ma7 = df.loc[i, 'MA7']
        ma30 = df.loc[i, 'MA30']
        date_str = df.loc[i, 'Date'].strftime('%Y-%m-%d')

        action = "HOLD"

        # Check for cross if we have valid MAs
        if i > 0 and not pd.isna(ma7) and not pd.isna(ma30) and not pd.isna(df.loc[i-1, 'MA7']) and not pd.isna(df.loc[i-1, 'MA30']):
            prev_ma7 = df.loc[i-1, 'MA7']
            prev_ma30 = df.loc[i-1, 'MA30']

            # Cross above (Golden Cross)
            if prev_ma7 <= prev_ma30 and ma7 > ma30:
                if cash > 0:
                    action = "BUY"
                    btc = cash / price
                    cash = 0.0
            # Cross below (Death Cross)
            elif prev_ma7 >= prev_ma30 and ma7 < ma30:
                if btc > 0:
                    action = "SELL"
                    cash = btc * price
                    btc = 0.0

        portfolio_value = cash + (btc * price)

        ma7_str = f"{ma7:.2f}" if not pd.isna(ma7) else "N/A"
        ma30_str = f"{ma30:.2f}" if not pd.isna(ma30) else "N/A"

        print(f"{date_str:<12} | ${price:<9.2f} | {ma7_str:<10} | {ma30_str:<10} | {action:<10} | ${cash:<11.2f} | {btc:<10.4f} | ${portfolio_value:<14.2f}")

    print("-" * 105)
    print("\nFinal Portfolio Performance:")
    print(f"Initial Portfolio Value: $100000.00")
    print(f"Final Portfolio Value:   ${portfolio_value:.2f}")

    roi = ((portfolio_value - 100000.0) / 100000.0) * 100
    print(f"Return on Investment:    {roi:.2f}%")

if __name__ == "__main__":
    run_trading_algo()
