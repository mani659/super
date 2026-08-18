import re
import pandas as pd
from datetime import datetime

html_path = 'c:/Users/ABRAR/Desktop/MT5Bot/Super/ReportHistory-474167713.html'

with open(html_path, 'r', encoding='utf-16') as f:
    html = f.read()

# Deals table starts with ">Deals</b>" and ends before ">Positions</b>" or ">Orders</b>"
idx_start = html.find('>Deals</b>')
idx_end = html.find('<h2>Open Positions</h2>')
if idx_end == -1:
    idx_end = len(html)

deals_html = html[idx_start:idx_end]

# Extract all rows in Deals table
rows = re.findall(r'<tr[^>]*>(.*?)</tr>', deals_html, re.DOTALL | re.IGNORECASE)

deals = []
for r in rows:
    cols = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL | re.IGNORECASE)
    cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
    if len(cols) >= 14:
        deals.append(cols)

# Expected columns: Time, Deal, Symbol, Type, Direction, Volume, Price, Order, Cost(hidden), Commission, Fee, Swap, Profit, Balance, Comment
# Length might be 15 if Comment is present, or 14 if Cost is missing.
df = pd.DataFrame(deals)
print("Deals dataframe shape:", df.shape)
if not df.empty:
    print(df.head())

# Let's save this as CSV to inspect easily
df.to_csv("c:/Users/ABRAR/Desktop/MT5Bot/Super/scratch/deals_extracted.csv", index=False)
