#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uurlijks Portfolio Rapport naar Discord - Compact"""

import sqlite3
import requests
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from config import config

DB_PATH = '/home/eddie/crypto-trading-bot/crypto_bot.db'


def get_market_data():
    """Haal actuele marktprijzen op van Bitvavo"""
    market_data = {}
    try:
        response = requests.get('https://api.bitvavo.com/v2/ticker/price', timeout=5)
        ticker_data = response.json()
        for item in ticker_data:
            market = item.get('market')
            price = item.get('price')
            if market and price:
                market_data[market] = {'price': float(price)}
    except Exception as e:
        print(f"Market data error: {e}")
    return market_data


def format_price(price):
    """Format prijs consistent"""
    if price >= 1000:
        return f"{price:,.2f}"
    elif price >= 1:
        return f"{price:.4f}"
    else:
        return f"{price:.8f}"


def get_coin_status(coin, market_price):
    """Bepaal coin status: hot, signal, of normal

    Returns:
        tuple: (status, trigger_price)
        status: 'hot' = trigger bereikt en trailing actief
                'signal' = buy/sell signal actief
                'normal' = geen actief signal
    """
    matrix = coin['matrix']
    gain = coin['gain']

    if coin['position'] == 'Y':  # In bezit - wil verkopen
        sell_trigger = matrix * (1 + gain)
        if market_price >= sell_trigger:
            return 'hot', sell_trigger
        else:
            return 'normal', sell_trigger
    else:  # Watching - wil kopen
        buy_trigger = matrix * (1 - gain)
        if market_price <= buy_trigger:
            return 'hot', buy_trigger
        else:
            return 'normal', buy_trigger


def send_discord_report():
    """Stuur compact portfolio rapport naar Discord"""
    webhook = config.DISCORD_WEBHOOK_REPORTS
    if not webhook:
        print("Discord REPORTS webhook niet geconfigureerd")
        return False

    # Database setup
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    # Haal alle coins op
    cursor.execute('''
        SELECT
            id, base_currency, quote_currency,
            current_price as matrix, position,
            temp_low, temp_high, gain, trail
        FROM coins
        ORDER BY base_currency, current_price DESC
    ''')
    coins = cursor.fetchall()

    # Haal transacties laatste uur op
    cursor.execute('''
        SELECT
            c.base_currency,
            t.transaction_type,
            COUNT(*) as count
        FROM transactions t
        JOIN coins c ON t.coin_id = c.id
        WHERE t.created_at >= datetime('now', '-1 hour')
        GROUP BY c.base_currency, t.transaction_type
    ''')
    transactions_last_hour = cursor.fetchall()

    db.close()

    # Verwerk transacties per crypto
    transactions_by_crypto = defaultdict(lambda: {'buy': 0, 'sell': 0})
    total_transactions = {'buy': 0, 'sell': 0}
    for tx in transactions_last_hour:
        crypto = tx['base_currency']
        tx_type = tx['transaction_type']
        count = tx['count']
        transactions_by_crypto[crypto][tx_type] = count
        total_transactions[tx_type] += count

    # Groepeer per crypto
    coins_by_crypto = defaultdict(list)
    for coin in coins:
        coin_dict = dict(coin)
        coins_by_crypto[coin['base_currency']].append(coin_dict)

    # Haal marktdata op
    market_data = get_market_data()

    # Verzamel statistieken
    total_bezit = 0
    total_watching = 0
    total_hot = 0
    crypto_summary = []

    for crypto in sorted(coins_by_crypto.keys()):
        crypto_coins = coins_by_crypto[crypto]
        market_pair = f"{crypto}-EUR"
        market_info = market_data.get(market_pair, {})
        market_price = market_info.get('price', 0)

        if not market_price:
            continue

        # Bereken status voor elke coin
        for coin in crypto_coins:
            status, trigger = get_coin_status(coin, market_price)
            coin['status'] = status
            coin['trigger_price'] = trigger
            coin['market_price'] = market_price
            coin['crypto'] = crypto

        # Tel statistieken
        hot_count = sum(1 for c in crypto_coins if c.get('status') == 'hot')
        bezit_count = sum(1 for c in crypto_coins if c['position'] == 'Y')
        watching_count = len(crypto_coins) - bezit_count

        total_bezit += bezit_count
        total_watching += watching_count
        total_hot += hot_count

        # Format marktprijs
        price_str = format_price(market_price)

        crypto_summary.append({
            'crypto': crypto,
            'price': price_str,
            'market_price': market_price,
            'hot': hot_count,
            'bezit': bezit_count,
            'watching': watching_count,
            'coins': crypto_coins
        })

    # Build Discord embed
    now = datetime.now()

    # Samenvatting text
    total_tx = total_transactions['buy'] + total_transactions['sell']
    summary = f"Totaal: {total_bezit + total_watching} coins\n"
    summary += f"In bezit: {total_bezit}\n"
    summary += f"Watching: {total_watching}\n"
    summary += f"Hot: {total_hot}\n"
    summary += f"Transacties laatste uur: {total_tx}"

    # Per crypto
    crypto_text = ""
    for c in crypto_summary:
        crypto = c['crypto']
        crypto_coins = c['coins']
        market_price = c['market_price']

        # Splits op position: [B] = bezit, [K] = wil kopen
        bezit_coins = [coin for coin in crypto_coins if coin['position'] == 'Y']
        koop_coins = [coin for coin in crypto_coins if coin['position'] == 'N']

        # Sorteer op matrix prijs (dichtstbij market_price eerst)
        bezit_coins.sort(key=lambda x: x['matrix'])
        koop_coins.sort(key=lambda x: x['matrix'], reverse=True)

        # Filter: hot/signal coins + max 3 normale
        def select_coins(coins_list):
            hot = [coin for coin in coins_list if coin.get('status') == 'hot']
            normal = [coin for coin in coins_list if coin.get('status') == 'normal'][:3]
            return hot + normal

        bezit_show = select_coins(bezit_coins)
        koop_show = select_coins(koop_coins)

        # Sorteer voor weergave
        bezit_show.sort(key=lambda x: x['matrix'])
        koop_show.sort(key=lambda x: x['matrix'], reverse=True)

        # BOVEN: [B] coins (in bezit, wil verkopen) - ALTIJD boven API prijs
        if bezit_show:
            crypto_text += "^ "
            formatted = []
            for coin in bezit_show:
                price_str = format_price(coin['matrix'])
                if coin.get('status') == 'hot':
                    formatted.append(f"[B!] {price_str}")
                else:
                    formatted.append(f"[B] {price_str}")
            crypto_text += " | ".join(formatted)
            crypto_text += "\n"

        # MIDDEN: Crypto info lijn met API prijs
        emoji = "!" if c['hot'] > 0 else "-"
        crypto_text += f"{emoji} {c['crypto']} {c['price']} | "
        crypto_text += f"Bezit:{c['bezit']} | Watch:{c['watching']}"
        if c['hot'] > 0:
            crypto_text += f" | HOT:{c['hot']}"
        crypto_text += "\n"

        # ONDER: [K] coins (wil kopen) - ALTIJD onder API prijs
        if koop_show:
            crypto_text += "v "
            formatted = []
            for coin in koop_show:
                price_str = format_price(coin['matrix'])
                if coin.get('status') == 'hot':
                    formatted.append(f"[K!] {price_str}")
                else:
                    formatted.append(f"[K] {price_str}")
            crypto_text += " | ".join(formatted)
            crypto_text += "\n"

        # Transacties laatste uur
        tx_data = transactions_by_crypto[crypto]
        tx_buy = tx_data['buy']
        tx_sell = tx_data['sell']
        if tx_buy > 0 or tx_sell > 0:
            crypto_text += f"Tx: {tx_buy} buy, {tx_sell} sell\n"
        crypto_text += "\n"

    # Health check
    import subprocess
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'crypto-trading-bot'],
            capture_output=True, text=True, timeout=5
        )
        bot_healthy = result.stdout.strip() == 'active'
        health_text = "Bot actief" if bot_healthy else "Bot probleem"
        health_color = 3066993 if bot_healthy else 15158332
    except:
        health_text = "Status onbekend"
        health_color = 15158332

    # Discord embed
    fields = [
        {
            "name": "Per Crypto",
            "value": crypto_text[:1024] if crypto_text else "Geen data",
            "inline": False
        }
    ]

    data = {
        "username": "Trading Bot",
        "embeds": [{
            "title": "Portfolio Overzicht",
            "description": summary,
            "color": health_color,
            "fields": fields,
            "timestamp": now.isoformat(),
            "footer": {
                "text": f"{health_text} | {now.strftime('%d-%m-%Y %H:%M')}"
            }
        }]
    }

    try:
        response = requests.post(webhook, json=data, timeout=10)
        response.raise_for_status()
        print(f"Portfolio rapport verzonden ({now.strftime('%H:%M')})")
        return True
    except Exception as e:
        print(f"Discord rapport gefaald: {e}")
        return False


if __name__ == '__main__':
    send_discord_report()
