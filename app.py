from flask import Flask, render_template_string, request
import sqlite3
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd

DB_FILENAME = 'data.db'

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = sqlite3.connect(DB_FILENAME)
    skus = [row[0] for row in conn.execute("SELECT DISTINCT sku FROM price_records WHERE sku != '' ORDER BY sku").fetchall()]
    selected_sku = request.form.get('sku')
    img_data = None

    if selected_sku:
        query = """
        SELECT timestamp, platform, price, discounted_price, qty
        FROM price_records
        WHERE sku = ?
        ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(selected_sku,))
        conn.close()

        if not df.empty:
            fig, ax1 = plt.subplots(figsize=(10, 6))

            platforms = df['platform'].unique()
            for platform in platforms:
                subset = df[df['platform'] == platform]
                ax1.plot(pd.to_datetime(subset['timestamp']), subset['price'], marker='o', label=f'{platform} price')
                ax1.plot(pd.to_datetime(subset['timestamp']), subset['discounted_price'], marker='x', linestyle='--', label=f'{platform} promo')

            ax1.set_xlabel('Data')
            ax1.set_ylabel('Prezzo (€)')
            ax1.legend(loc='upper left')
            ax1.set_title(f'Evoluzione prezzi e qty per SKU {selected_sku}')
            fig.autofmt_xdate()

            # Secondo asse Y per qty
            ax2 = ax1.twinx()
            qty_df = df.groupby('timestamp')['qty'].mean()  # media qty su tutte le piattaforme
            ax2.plot(pd.to_datetime(qty_df.index), qty_df.values, color='grey', linestyle=':', marker='s', label='qty')
            ax2.set_ylabel('Quantità disponibile')

            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()
        else:
            img_data = None
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
        <input type="submit" value="Mostra grafico">
    </form>
    {% if img_data %}
        <img src="data:image/png;base64,{{ img_data }}">
    {% endif %}
    '''
    return render_template_string(html, skus=skus, selected_sku=selected_sku, img_data=img_data)

if __name__ == '__main__':
    app.run(debug=True)