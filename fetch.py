import pandas as pd
import requests
import sqlite3
import datetime

CSV_URL = 'https://www.provence-outillage.fr/csv/marketplace/mp.prices.csv'
DB_FILENAME = 'data.db'

# Scarica CSV
r = requests.get(CSV_URL)
r.encoding = 'cp1252'
with open('mp.prices.csv', 'w', encoding='cp1252') as f:
    f.write(r.text)

df = pd.read_csv('mp.prices.csv', sep=';', encoding='cp1252')

conn = sqlite3.connect(DB_FILENAME)

conn.execute('''
CREATE TABLE IF NOT EXISTS price_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT,
    qty INTEGER,
    platform TEXT,
    price REAL,
    discounted_price REAL,
    discount_start TEXT,
    discount_end TEXT,
    timestamp TEXT
)
''')

now = datetime.datetime.utcnow().isoformat()

for _, row in df.iterrows():
    sku = row.get('SKUs')
    qty = row.get('qty')
    if pd.isna(sku):
        continue
    for platform in ['AMZ_FR', 'Cdiscount', 'Cdiscount_FF', 'LeroyMerlin', 'LeroyMerlin_FF',
                     'Mano_FR', 'Mano_FR_FF', 'Mano_Pro', 'Mano_Pro_FF', 'Autres']:
        base_price = row.get(platform, None)
        promo_price = row.get(f'{platform}_PrixPromo', None)
        date_start = row.get(f'{platform}_DateDebut', None)
        date_end = row.get(f'{platform}_DateFin', None)

        if pd.isna(base_price) and pd.isna(promo_price):
            continue  # Nessun dato utile → salta

        conn.execute('''
        INSERT INTO price_records
        (sku, qty, platform, price, discounted_price, discount_start, discount_end, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(sku),
            int(qty),
            platform,
            float(base_price) if not pd.isna(base_price) else 0,
            float(promo_price) if not pd.isna(promo_price) else 0,
            str(date_start) if not pd.isna(date_start) else '',
            str(date_end) if not pd.isna(date_end) else '',
            now
        ))

conn.commit()
conn.close()
