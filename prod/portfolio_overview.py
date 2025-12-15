#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portfolio overzicht - Hot coins prioriteit met API-koers referentie"""

import sqlite3
import requests
import sys
from typing import Dict, List, Tuple
from collections import defaultdict

# Fix Windows console encoding voor emoji's
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

def get_market_data() -> Dict[str, Dict[str, float]]:
    """Haal actuele marktprijzen en orderbook data op van Bitvavo"""
    market_data = {}

    try:
        # Haal ticker prijzen op
        response = requests.get('https://api.bitvavo.com/v2/ticker/price', timeout=5)
        ticker_data = response.json()

        for item in ticker_data:
            market = item.get('market')
            price = item.get('price')
            if market and price:
                market_data[market] = {
                    'price': float(price),
                    'bid': None,
                    'ask': None
                }

        # Haal bid/ask prijzen op van ticker/24h (bevat meer info)
        response = requests.get('https://api.bitvavo.com/v2/ticker/24h', timeout=5)
        ticker_24h = response.json()

        for item in ticker_24h:
            market = item['market']
            if market in market_data:
                market_data[market]['bid'] = float(item.get('bid', 0)) if item.get('bid') else None
                market_data[market]['ask'] = float(item.get('ask', 0)) if item.get('ask') else None

    except Exception as e:
        print(f"⚠️  Error fetching market data: {e}")

    return market_data

def get_coin_temperature(coin: Dict, market_price: float) -> str:
    """
    Bepaal of een coin 'hot', 'warm' of 'cold' is

    Voor coins NIET in bezit (position == 'N'):
    - 'hot' (rood): buy_trigger is gepasseerd (market_price <= buy_trigger) → wacht op trail buy
    - 'warm' (oranje): API-koers tussen buy_trigger en matrix → koers komt dichterbij
    - 'cold': alle andere situaties

    Voor coins IN bezit (position == 'Y'):
    - 'hot' (rood): sell_trigger is gepasseerd (market_price >= sell_trigger) → wacht op trail sell
    - 'warm' (oranje): API-koers tussen matrix en sell_trigger → koers komt dichterbij
    - 'cold': alle andere situaties
    """
    matrix = coin['matrix']
    buy_trigger = matrix * (1 - coin['gain'])
    sell_trigger = matrix * (1 + coin['gain'])
    position = coin['position']

    if position == 'N':  # Niet in bezit
        if market_price <= buy_trigger:
            return 'hot'  # Trigger gepasseerd, wacht op trail buy
        elif buy_trigger < market_price < matrix:
            return 'warm'  # API tussen trigger en matrix
        else:
            return 'cold'
    else:  # In bezit (Y)
        if market_price >= sell_trigger:
            return 'hot'  # Trigger gepasseerd, wacht op trail sell
        elif matrix < market_price < sell_trigger:
            return 'warm'  # API tussen matrix en trigger
        else:
            return 'cold'

def filter_and_sort_coins(coins: List[Dict], market_price: float, max_non_hot: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """
    Sorteer coins in twee groepen: boven en onder market_price
    Selecteer coins die het DICHTST bij API-koers liggen
    Sorteer van laag naar hoog, zodat API-koers in het midden ligt

    BELANGRIJK: Bereken temperature EERST, dan sorteer op matrix positie
    """
    above_market = []  # Coins met matrix > market_price
    below_market = []  # Coins met matrix <= market_price

    # EERST: Bereken temperature voor ALLE coins
    for coin in coins:
        temperature = get_coin_temperature(coin, market_price)
        coin['temperature'] = temperature
        coin['is_hot'] = temperature == 'hot'

    # DAARNA: Sorteer op matrix positie t.o.v. market price
    for coin in coins:
        if coin['matrix'] > market_price:
            above_market.append(coin)
        else:
            below_market.append(coin)

    # Sorteer beide groepen ascending (laag naar hoog)
    above_market.sort(key=lambda c: c['matrix'])
    below_market.sort(key=lambda c: c['matrix'])

    # Filter: hot coins altijd + de dichtsbijzijnde niet-hot coins
    def filter_closest_to_api(coin_list: List[Dict], limit: int, is_above: bool) -> List[Dict]:
        hot_coins = [c for c in coin_list if c['is_hot']]
        non_hot_coins = [c for c in coin_list if not c['is_hot']]

        if is_above:
            # Boven API: pak de LAAGSTE (eerste na sortering) = dichtst bij API
            selected_non_hot = non_hot_coins[:limit]
        else:
            # Onder API: pak de HOOGSTE (laatste na sortering) = dichtst bij API
            selected_non_hot = non_hot_coins[-limit:] if len(non_hot_coins) > limit else non_hot_coins

        # Combineer en sorteer laag naar hoog
        combined = hot_coins + selected_non_hot
        combined.sort(key=lambda c: c['matrix'])
        return combined

    above_filtered = filter_closest_to_api(above_market, max_non_hot, is_above=True)
    below_filtered = filter_closest_to_api(below_market, max_non_hot, is_above=False)

    return above_filtered, below_filtered

def print_coin_row(coin: Dict):
    """Print een coin regel met kleuren - alleen relevante kolommen"""
    matrix = coin['matrix']
    buy_trigger = matrix * (1 - coin['gain'])
    sell_trigger = matrix * (1 + coin['gain'])
    trail_buy = coin['temp_low'] * (1 + coin['trail'])
    trail_sell = coin['temp_high'] * (1 - coin['trail'])

    # Temperatuur indicator
    if coin['temperature'] == 'hot':
        temp_icon = f"{RED}🔴{RESET}"  # Rood voor hot
    elif coin['temperature'] == 'warm':
        temp_icon = f"{YELLOW}🟠{RESET}"  # Oranje voor warm
    else:
        temp_icon = "⚪"  # Wit voor cold

    # Matrix kleur: Oranje voor warm/hot, normaal voor cold
    matrix_color = YELLOW if coin['temperature'] in ['warm', 'hot'] else RESET

    # Bereken gain en trail percentages
    gain_pct = f"{coin['gain']*100:.1f}%"
    trail_pct = f"{coin['trail']*100:.2f}%"

    if coin['position'] == 'Y':
        # IN BEZIT - toon alleen sell-gerelateerde info
        # Trigger kleur: Rood voor hot, normaal voor rest
        trigger_color = RED if coin['temperature'] == 'hot' else RESET

        print(f"{temp_icon} {coin['position']:<3} €{coin['transactie_bedrag']:>6.2f} {coin['id']:<4} {matrix_color}€{matrix:>10,.2f}{RESET} {gain_pct:>6} {'':>12} {trigger_color}€{sell_trigger:>10,.2f}{RESET} {'':>12} €{coin['temp_high']:>10,.2f} {trail_pct:>6} {'':>12} €{trail_sell:>10,.2f}")
    else:
        # WATCHING - toon alleen buy-gerelateerde info
        # Trigger kleur: Rood voor hot, normaal voor rest
        trigger_color = RED if coin['temperature'] == 'hot' else RESET

        print(f"{temp_icon} {coin['position']:<3} €{coin['transactie_bedrag']:>6.2f} {coin['id']:<4} {matrix_color}€{matrix:>10,.2f}{RESET} {gain_pct:>6} {trigger_color}€{buy_trigger:>10,.2f}{RESET} {'':>12} €{coin['temp_low']:>10,.2f} {'':>12} {trail_pct:>6} €{trail_buy:>10,.2f} {'':>12}")

# Database setup
db = sqlite3.connect('crypto_bot.db')
db.row_factory = sqlite3.Row
cursor = db.cursor()

# Haal alle coins op
cursor.execute('''
    SELECT
        c.id,
        c.base_currency,
        c.quote_currency,
        c.current_price as matrix,
        c.position,
        c.temp_low,
        c.temp_high,
        c.gain,
        c.trail,
        c.transactie_bedrag,
        c.last_buy_price,
        COALESCE(t.amount, 0) as amount
    FROM coins c
    LEFT JOIN (
        SELECT coin_id, amount
        FROM transactions
        WHERE transaction_type = 'buy'
        AND (coin_id, created_at) IN (
            SELECT coin_id, MAX(created_at)
            FROM transactions
            WHERE transaction_type = 'buy'
            GROUP BY coin_id
        )
    ) t ON c.id = t.coin_id
    ORDER BY c.base_currency, c.current_price DESC
''')

coins = cursor.fetchall()

# Groepeer coins per crypto
coins_by_crypto = defaultdict(list)
for coin in coins:
    coin_dict = dict(coin)
    coins_by_crypto[coin['base_currency']].append(coin_dict)

# Haal marktdata op
print('🔄 Ophalen actuele marktprijzen...')
market_data = get_market_data()

print('=' * 185)
print(f'{BOLD}PORTFOLIO OVERZICHT - Hot coins prioriteit met API-koers referentie{RESET}')
print('=' * 185)

total_bezit = 0
total_watching = 0
total_hot = 0

# Toon per crypto
for crypto in sorted(coins_by_crypto.keys()):
    crypto_coins = coins_by_crypto[crypto]
    market_pair = f"{crypto}-EUR"

    # Haal marktdata op
    market_info = market_data.get(market_pair, {})
    market_price = market_info.get('price', 0)
    bid_price = market_info.get('bid')
    ask_price = market_info.get('ask')

    if not market_price:
        print(f'\n{YELLOW}### {crypto} - ⚠️  Geen marktdata beschikbaar ###{RESET}')
        continue

    # Gebruik bid/ask als beschikbaar, anders market_price
    # BID voor watching (we willen kopen tegen bid)
    # ASK voor bezit (we willen verkopen tegen ask)
    # Voor display gebruiken we gemiddelde van bid/ask als beschikbaar
    if bid_price and ask_price:
        display_price = (bid_price + ask_price) / 2
    else:
        display_price = market_price

    # Filter en sorteer coins - gebruik display_price voor consistentie
    above_coins, below_coins = filter_and_sort_coins(crypto_coins, display_price)

    # Tel statistieken
    hot_count = sum(1 for c in crypto_coins if c.get('temperature') == 'hot')
    warm_count = sum(1 for c in crypto_coins if c.get('temperature') == 'warm')
    bezit_count = sum(1 for c in crypto_coins if c['position'] == 'Y')
    watching_count = len(crypto_coins) - bezit_count

    total_bezit += bezit_count
    total_watching += watching_count
    total_hot += hot_count

    # Print crypto header - gebruik display_price voor consistentie met temperature berekening
    print(f'\n{BOLD}{CYAN}### {crypto} - Markt: €{display_price:,.8f} | {RED}Hot: {hot_count}{CYAN} | {YELLOW}Warm: {warm_count}{CYAN} | Bezit: {bezit_count} | Watching: {watching_count} ###{RESET}')
    print(f"{'':3} {'Pos':<3} {'Bedrag':>8} {'ID':<4} {'Matrix':>11} {'Gain%':>6} {'Buy Trig':>11} {'Sell Trig':>11} {'temp_low':>11} {'temp_high':>11} {'Trail%':>6} {'Trail Buy':>11} {'Trail Sell':>11}")
    print('-' * 185)

    # Toon coins ONDER marktprijs (laag naar hoog, dichtst bij API)
    if below_coins:
        for coin in below_coins:
            print_coin_row(coin)

    # Toon API bid/ask koers (in het midden)
    if bid_price and ask_price:
        print(f"{YELLOW}{'':3} {'API':<3} {'BID':<4} €{bid_price:>10,.8f} {'':>11} {'':>11} {'':>11} {'':>11} {'':>11} {'':>11}{RESET}")
        print(f"{YELLOW}{'':3} {'API':<3} {'ASK':<4} €{ask_price:>10,.8f} {'':>11} {'':>11} {'':>11} {'':>11} {'':>11} {'':>11}{RESET}")
    else:
        print(f"{YELLOW}{'':3} {'API':<3} {'':<4} €{market_price:>10,.8f} {'':>11} {'':>11} {'':>11} {'':>11} {'':>11} {'':>11}{RESET}")

    # Toon coins BOVEN marktprijs (laag naar hoog, dichtst bij API)
    if above_coins:
        for coin in above_coins:
            print_coin_row(coin)

print('\n' + '=' * 185)
print(f'\n📊 {BOLD}SAMENVATTING:{RESET}')
print(f'   {RED}🔴 Hot coins{RESET} (trigger gepasseerd): {total_hot}')
print(f'   {YELLOW}🟠 Warm coins{RESET} (API tussen matrix en trigger): Zie overzicht')
print(f'   🔵 In bezit (Position Y): {total_bezit} coins')
print(f'   ⚪ Watching (Position N): {total_watching} coins')
print(f'   📦 Totaal: {total_bezit + total_watching} coins')
print('\n' + '=' * 185)

db.close()
