from flask import Flask, render_template_string, request
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd
import numpy as np

DB_FILENAME = 'data.db'

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = sqlite3.connect(DB_FILENAME)
    skus = [row[0] for row in conn.execute("SELECT DISTINCT sku FROM price_records WHERE sku != '' ORDER BY sku").fetchall()]
    selected_sku = request.form.get('sku')
    img_data = None
    table_html = None

    if selected_sku:
        query = """
        SELECT timestamp, platform, price, discounted_price
        FROM price_records
        WHERE sku = ?
        ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(selected_sku,))
        conn.close()

        if not df.empty:
            df['timestamp_dt'] = pd.to_datetime(df['timestamp'])
            df['halfday'] = df['timestamp_dt'].apply(lambda x: 'HD1' if x.hour < 12 else 'HD2')
            df['label'] = df['halfday'] + '-' + df['timestamp_dt'].dt.strftime('%d/%m/%y')

            # Creiamo una mappa label → index per jitter
            unique_labels = df['label'].unique()
            label_to_x = {label: idx for idx, label in enumerate(unique_labels)}

            fig, ax1 = plt.subplots(figsize=(12, 6))
            platforms = df['platform'].unique()

            jitter_width = 0.1  # Offset orizzontale massimo
            for i, platform in enumerate(platforms):
                subset = df[df['platform'] == platform]

                # Filtra price > 0
                subset_price = subset[subset['price'] > 0]
                if not subset_price.empty:
                    x_vals_price = [label_to_x[label] + (i - len(platforms)/2) * jitter_width / len(platforms) for label in subset_price['label']]
                    ax1.plot(x_vals_price, subset_price['price'], marker='o', linestyle='-', alpha=0.8, label=f'{platform} price')

                # Filtra discounted_price > 0
                subset_promo = subset[subset['discounted_price'] > 0]
                if not subset_promo.empty:
                    x_vals_promo = [label_to_x[label] + (i - len(platforms)/2) * jitter_width / len(platforms) for label in subset_promo['label']]
                    ax1.plot(x_vals_promo, subset_promo['discounted_price'], marker='x', linestyle='--', alpha=0.8, label=f'{platform} promo')

            ax1.set_xticks(range(len(unique_labels)))
            ax1.set_xticklabels(unique_labels, rotation=45, ha='right')
            ax1.set_xlabel('Half-day')
            ax1.set_ylabel('Prezzo (€)')
            ax1.legend(loc='upper left')
            ax1.set_title(f'Evoluzione prezzi per SKU {selected_sku}')

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()

            # Prepara tabella HTML
            df_table = df[['label', 'platform', 'price', 'discounted_price']].copy()
            df_table.rename(columns={
                'label': 'Timestamp',
                'platform': 'Platform',
                'price': 'Price (€)',
                'discounted_price': 'Discounted Price (€)'
            }, inplace=True)

            # Styling manuale CSS
            table_html = df_table.to_html(index=False, border=1, classes='dataframe', justify='left')

            style = '''
            <style>
                table.dataframe { border-collapse: collapse; width: 100%; }
                table.dataframe th { text-align: left; border: 1px solid black; padding: 4px; }
                table.dataframe td { text-align: left; border: 1px solid black; padding: 4px; }
                table.dataframe td:nth-child(3),
                table.dataframe td:nth-child(4) { text-align: right; }
            </style>
            '''

            table_html = style + table_html

    else:
        conn.close()

    html = '''
    <h1>Price Tracker</h1>
    <form method="post">
        <label for="sku">Seleziona SKU:</label>
        <select name="sku">
            {% for s in skus %}
                <option value="{{ s }}" {% if s == selected_sku %}selected{% endif %}>{{ s }}</option>
            {% endfor %}
        </select>
        <input type="submit" value="Mostra grafico e tabella">
    </form>
    {% if img_data %}
        <img src="data:image/png;base64,{{ img_data }}">
        <h2>Dettaglio dati</h2>
        {{ table_html | safe }}
    {% endif %}
    '''
    return render_template_string(html, skus=skus, selected_sku=selected_sku, img_data=img_data, table_html=table_html)

if __name__ == '__main__':
    app.run(debug=True)
