from flask import Flask, render_template, request
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
from datetime import datetime
import json
import os

app = Flask(__name__)

def calculate_position_size(balance, max_loss_percent, entry_price, stop_price, direction):
    """Рассчитывает размер позиции на основе максимального убытка"""
    if direction == 'long':
        price_diff = entry_price - stop_price
    else:  # short
        price_diff = stop_price - entry_price
    
    max_loss_amount = balance * (max_loss_percent / 100)
    position_size = max_loss_amount / (price_diff / entry_price)
    return position_size

def calculate_trailing_stop(entry_price, stop_price, take_price, current_price, 
                          trailing_activation, trailing_distance, direction):
    """Рассчитывает трейлинг-стоп"""
    if direction == 'long':
        stop_diff = entry_price - stop_price
        activation_price = entry_price + (stop_diff * trailing_activation)
        
        if current_price >= activation_price:
            new_stop = current_price - (stop_diff * trailing_distance)
            return max(new_stop, stop_price)
    else:  # short
        stop_diff = stop_price - entry_price
        activation_price = entry_price - (stop_diff * trailing_activation)
        
        if current_price <= activation_price:
            new_stop = current_price + (stop_diff * trailing_distance)
            return min(new_stop, stop_price)
    
    return stop_price

def calculate_deal_result(row, params):
    """Рассчитывает результат одной сделки"""
    entry_price = row['entry_price']
    stop_price = row['stop_price']
    take_price = row['take_price']
    direction = row['direction']
    current_price = row['current_price']
    best_price = row['best_price']
    status = row['status']
    
    # Рассчитываем размер позиции
    position_size = calculate_position_size(
        params['initial_balance'],
        params['max_loss_percent'],
        entry_price,
        stop_price,
        direction
    )
    
    # Рассчитываем проценты движения цены
    if direction == 'long':
        stop_percent = (entry_price - stop_price) / entry_price * 100
        take_percent = (take_price - entry_price) / entry_price * 100
    else:  # short
        stop_percent = (stop_price - entry_price) / entry_price * 100
        take_percent = (entry_price - take_price) / entry_price * 100
    
    # Рассчитываем трейлинг-стоп
    trailing_stop = calculate_trailing_stop(
        entry_price, stop_price, take_price, best_price,
        params['trailing_activation'], params['trailing_distance'], direction
    )
    
    # Определяем точку выхода
    if direction == 'long':
        if status == 'win':
            exit_price = take_price
        elif best_price >= (entry_price + (entry_price - stop_price) * params['trailing_activation']):
            exit_price = trailing_stop
        else:
            exit_price = stop_price
    else:  # short
        if status == 'win':
            exit_price = take_price
        elif best_price <= (entry_price - (stop_price - entry_price) * params['trailing_activation']):
            exit_price = trailing_stop
        else:
            exit_price = stop_price
    
    # Рассчитываем прибыль/убыток
    if direction == 'long':
        profit = (exit_price - entry_price) / entry_price * position_size
    else:
        profit = (entry_price - exit_price) / entry_price * position_size
    
    # Вычитаем комиссии
    profit = profit - (position_size * (params['entry_commission'] + params['exit_commission']) / 100)
    
    return profit, position_size, stop_percent, take_percent

def calculate_equity_curve(df, params):
    """Рассчитывает кривую капитала"""
    balance = params['initial_balance']
    equity_curve = [balance]
    dates = [df.iloc[0]['datetime']]
    deals = []
    
    for _, row in df.iterrows():
        profit, position_size, stop_percent, take_percent = calculate_deal_result(row, params)
        balance += profit
        
        deals.append({
            'datetime': row['datetime'],
            'pair': row['pair'],
            'direction': row['direction'],
            'entry_price': row['entry_price'],
            'stop_price': row['stop_price'],
            'take_price': row['take_price'],
            'best_price': row['best_price'],
            'position_size': round(position_size, 2),
            'stop_percent': round(stop_percent, 2),
            'take_percent': round(take_percent, 2),
            'result': 'win' if profit > 0 else 'loss',
            'profit': round(profit, 2),
            'balance': round(balance, 2)
        })
        
        equity_curve.append(balance)
        dates.append(row['datetime'])
    
    return dates, equity_curve, deals

def calculate_statistics(df, params):
    """Рассчитывает общую статистику по сделкам"""
    stats = {}
    
    # Базовая статистика
    stats['total_deals'] = len(df)
    stats['win_deals'] = len(df[df['status'] == 'win'])
    stats['loss_deals'] = len(df[df['status'] == 'loss'])
    stats['win_percent'] = round(stats['win_deals'] / stats['total_deals'] * 100, 2) if stats['total_deals'] > 0 else 0
    stats['loss_percent'] = round(stats['loss_deals'] / stats['total_deals'] * 100, 2) if stats['total_deals'] > 0 else 0
    
    # Прибыль/убыток
    profits = []
    for _, row in df.iterrows():
        profit, _, _, _ = calculate_deal_result(row, params)
        profits.append(profit)
    
    stats['avg_profit'] = round(sum(profits) / len(profits), 2) if profits else 0
    stats['max_profit'] = round(max(profits), 2) if profits else 0
    stats['max_loss'] = round(min(profits), 2) if profits else 0
    
    # Финансовые показатели
    stats['initial_balance'] = params['initial_balance']
    stats['final_balance'] = params['initial_balance'] + sum(profits)
    stats['total_profit'] = round(sum(profits), 2)
    stats['roi'] = round((stats['final_balance'] / stats['initial_balance'] - 1) * 100, 2)
    
    # Максимальная просадка
    balance = params['initial_balance']
    max_balance = balance
    max_drawdown = 0
    for profit in profits:
        balance += profit
        if balance > max_balance:
            max_balance = balance
        drawdown = (max_balance - balance) / max_balance * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    stats['max_drawdown'] = round(max_drawdown, 2)
    
    # Направления сделок
    long_deals = df[df['direction'] == 'long']
    short_deals = df[df['direction'] == 'short']
    
    stats['long_deals'] = len(long_deals)
    stats['short_deals'] = len(short_deals)
    
    long_wins = len(long_deals[long_deals['status'] == 'win'])
    short_wins = len(short_deals[short_deals['status'] == 'win'])
    
    stats['long_win_percent'] = round(long_wins / stats['long_deals'] * 100, 2) if stats['long_deals'] > 0 else 0
    stats['short_win_percent'] = round(short_wins / stats['short_deals'] * 100, 2) if stats['short_deals'] > 0 else 0
    
    return stats

def calculate_pair_statistics(df, params):
    """Рассчитывает статистику по торговым парам"""
    pair_stats = []
    for pair in df['pair'].unique():
        pair_df = df[df['pair'] == pair]
        
        stats = {
            'pair': pair,
            'total_deals': len(pair_df),
            'win_deals': len(pair_df[pair_df['status'] == 'win']),
            'loss_deals': len(pair_df[pair_df['status'] == 'loss'])
        }
        
        stats['win_percent'] = round(stats['win_deals'] / stats['total_deals'] * 100, 2) if stats['total_deals'] > 0 else 0
        
        profits = []
        for _, row in pair_df.iterrows():
            profit, _, _, _ = calculate_deal_result(row, params)
            profits.append(profit)
        
        stats['avg_profit'] = round(sum(profits) / len(profits), 2) if profits else 0
        stats['total_profit'] = round(sum(profits), 2)
        
        pair_stats.append(stats)
    
    return sorted(pair_stats, key=lambda x: x['total_profit'], reverse=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    # Параметры по умолчанию
    params = {
        'database': 'deals_1h.sqlite',
        'initial_balance': 1000,
        'max_loss_percent': 1.0,
        'trailing_activation': 0.5,
        'trailing_distance': 0.3,
        'entry_commission': 0.1,
        'exit_commission': 0.1
    }
    
    # Получаем номер страницы
    page = int(request.args.get('page', 1))
    per_page = 100
    
    if request.method == 'POST':
        params = {
            'database': request.form.get('database', 'deals_1h.sqlite'),
            'initial_balance': 1000,
            'max_loss_percent': float(request.form.get('max_loss_percent', 1.0)),
            'trailing_activation': float(request.form.get('trailing_activation', 0.5)),
            'trailing_distance': float(request.form.get('trailing_distance', 0.3)),
            'entry_commission': float(request.form.get('entry_commission', 0.1)),
            'exit_commission': float(request.form.get('exit_commission', 0.1))
        }
    
    # Загружаем данные из выбранной базы
    try:
        db_path = os.path.join('..', params['database'])
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM deals ORDER BY datetime", conn)
        conn.close()
        
        # Рассчитываем кривую капитала и результаты сделок
        dates, equity_curve, deals = calculate_equity_curve(df, params)
        
        # Рассчитываем статистику
        stats = calculate_statistics(df, params)
        pair_stats = calculate_pair_statistics(df, params)
        
        # Пагинация сделок
        total_pages = (len(deals) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_deals = deals[start_idx:end_idx]
        
        # Создаем график
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=equity_curve,
            mode='lines',
            name='Баланс'
        ))
        
        fig.update_layout(
            title='Кривая капитала',
            xaxis_title='Дата',
            yaxis_title='Баланс (USDT)',
            showlegend=True
        )
        
        graph_json = json.dumps(fig.to_dict())
        
        return render_template('index.html', 
                             graph_json=graph_json,
                             params=params,
                             deals=paginated_deals,
                             stats=stats,
                             pair_stats=pair_stats,
                             page=page,
                             total_pages=total_pages)
    except Exception as e:
        return f"Ошибка при загрузке данных: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 