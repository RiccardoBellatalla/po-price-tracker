from flask import Flask, render_template_string, request
import sqlite3
import pandas as pd
import plotly.graph_objs as go
import plotly.offline as pyo

DB_FILENAME = 'data.db'

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = sqlite3.connect(DB_FILENAME)
    skus = [row[0] for row in conn.execute(
        "SELECT DISTINCT sku FROM price_records WHERE sku != '' ORDER BY sku"
    ).fetchall()]
    selected_sku = request.form.get('sku')
    graph_html = None
    table_html = None

    if selected_sku:
        query = """
        SELECT timestamp, platform, price, discounted_price, discount_start, discount_end
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
            df['discount_start'] = pd.to_datetime(df['discount_start'], errors='coerce')
            df['discount_end'] = pd.to_datetime(df['discount_end'], errors='coerce')

            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            df['discounted_price'] = pd.to_numeric(df['discounted_price'], errors='coerce')

            fig = go.Figure()
            platforms = df['platform'].unique()
            all_y = []

            for platform in platforms:
                df_platform = df[df['platform'] == platform]

                df_price = df_platform[df_platform['price'] > 0]
                if not df_price.empty:
                    fig.add_trace(go.Scatter(
                        x=df_price['timestamp_dt'].tolist(),
                        y=df_price['price'].astype(float).tolist(),
                        mode='lines+markers',
                        name=f'{platform}',
                        customdata=list(zip(df_price['label'].tolist(), df_price['platform'].tolist())),
                        hovertemplate=(
                            "%{customdata[1]} : %{y} €<extra></extra><br>"
                            "%{customdata[0]}<br>"
                        )
                    ))
                    all_y.extend(df_price['price'].tolist())

                df_promo = df_platform[
                    (df_platform['discounted_price'] > 0) &
                    (df_platform['discount_start'].notnull()) &
                    (df_platform['discount_end'].notnull()) &
                    (df_platform['timestamp_dt'] >= df_platform['discount_start']) &
                    (df_platform['timestamp_dt'] <= df_platform['discount_end'])
                ]

                if not df_promo.empty:
                    fig.add_trace(go.Scatter(
                        x=df_promo['timestamp_dt'].tolist(),
                        y=df_promo['discounted_price'].astype(float).tolist(),
                        mode='lines+markers',
                        name=f'*Promo {platform}',
                        customdata=list(zip(df_promo['label'].tolist(), df_promo['platform'].tolist())),
                        hovertemplate=(
                            "PROMO %{customdata[1]} : %{y} €<extra></extra><br>"
                            "%{customdata[0]}<br>"
                        )
                    ))
                    all_y.extend(df_promo['discounted_price'].tolist())

            if all_y:
                ymax = max(all_y) * 1.1
            else:
                ymax = 1

            fig.update_layout(
                title=f'Evoluzione prezzi per SKU {selected_sku}',
                xaxis_title='Data',
                yaxis_title='Prezzo (€)',
                yaxis=dict(range=[0, ymax]),
                legend_title='Platform'
            )

            graph_html = pyo.plot(fig, include_plotlyjs=False, output_type='div')

            df_table = df[['label', 'platform', 'price', 'discounted_price', 'discount_start', 'discount_end']].copy()
            df_table.rename(columns={
                'label': 'Timestamp',
                'platform': 'Platform',
                'price': 'Price (€)',
                'discounted_price': 'Discounted Price (€)',
                'discount_start': 'Discount Start',
                'discount_end': 'Discount End'
            }, inplace=True)

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
    {% if graph_html %}
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        {{ graph_html | safe }}
        <h2>Dettaglio dati</h2>
        {{ table_html | safe }}
    {% endif %}
    '''
    return render_template_string(html, skus=skus, selected_sku=selected_sku, graph_html=graph_html, table_html=table_html)

if __name__ == '__main__':
    app.run(debug=True)
