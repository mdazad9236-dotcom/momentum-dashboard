import yfinance as yf
from analysis import TechnicalAnalyzer


symbol = "TCS.NS"

print(f"\nDownloading data for {symbol}...")

data = yf.download(
    symbol,
    period="1y",
    interval="1d",
    auto_adjust=False,
    progress=False
)

if data.empty:
    raise RuntimeError("No market data received.")

# yfinance can sometimes return MultiIndex columns.
if hasattr(data.columns, "nlevels") and data.columns.nlevels > 1:
    data.columns = data.columns.get_level_values(0)

print(f"Rows received: {len(data)}")

analyzer = TechnicalAnalyzer(data)

result = analyzer.calculate()

print("\n" + "=" * 50)
print("X10 THINK — STAGE 1B TEST")
print("=" * 50)

for key, value in result.items():
    print(f"{key:20} : {value}")

print("=" * 50)

print("\nTEST PASSED")
