"""
Test sell strategies: eur, crypto, split

Tests the _calculate_sell_params method to ensure correct behavior for each strategy.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from unittest.mock import MagicMock, patch


class MockCoin:
    """Mock Coin class for testing _calculate_sell_params"""

    def __init__(self, transactie_bedrag, last_buy_price, proceeds_strategy, proceeds_crypto_ratio=0.5):
        self.transactie_bedrag = transactie_bedrag
        self.last_buy_price = last_buy_price
        self.proceeds_strategy = proceeds_strategy
        self.proceeds_crypto_ratio = proceeds_crypto_ratio
        self.analysis_pair = 'ETH-EUR'

    def _calculate_sell_params(self, current_price: float) -> dict:
        """
        Calculate sell parameters based on proceeds_strategy.
        """
        # Fallback if no last_buy_price available
        if self.last_buy_price <= 0:
            return {
                'use_amount': False,
                'amountQuote': self.transactie_bedrag,
                'expected_eur': self.transactie_bedrag,
                'crypto_owned': 0,
                'strategy': self.proceeds_strategy
            }

        # Calculate how much crypto we own
        crypto_owned = self.transactie_bedrag / self.last_buy_price

        # Calculate expected profit at current price
        current_value = crypto_owned * current_price
        profit = current_value - self.transactie_bedrag

        if self.proceeds_strategy == 'crypto':
            # Sell ALL crypto
            return {
                'use_amount': True,
                'amount': round(crypto_owned, 8),
                'expected_eur': current_value,
                'crypto_owned': crypto_owned,
                'profit': profit,
                'strategy': 'crypto'
            }

        elif self.proceeds_strategy == 'split':
            # Sell transactie_bedrag + (profit * ratio)
            if profit > 0:
                sell_eur = self.transactie_bedrag + (profit * self.proceeds_crypto_ratio)
                leftover_value = profit * (1 - self.proceeds_crypto_ratio)
            else:
                sell_eur = self.transactie_bedrag
                leftover_value = 0

            return {
                'use_amount': False,
                'amountQuote': round(sell_eur, 2),
                'expected_eur': sell_eur,
                'crypto_owned': crypto_owned,
                'profit': profit,
                'leftover_value': leftover_value,
                'strategy': 'split'
            }

        else:  # 'eur' or unknown
            return {
                'use_amount': False,
                'amountQuote': self.transactie_bedrag,
                'expected_eur': self.transactie_bedrag,
                'crypto_owned': crypto_owned,
                'profit': profit,
                'leftover_value': profit if profit > 0 else 0,
                'strategy': 'eur'
            }


class TestSellStrategies(unittest.TestCase):
    """Test sell strategy calculations"""

    def setUp(self):
        """Common test scenario:
        - Bought EUR 10 worth of ETH at EUR 2,500
        - Crypto owned: 10 / 2500 = 0.004 ETH
        - Current price: EUR 2,630 (5.2% gain)
        - Current value: 0.004 * 2630 = EUR 10.52
        - Profit: EUR 0.52
        """
        self.transactie_bedrag = 10.0
        self.last_buy_price = 2500.0
        self.current_price = 2630.0
        self.crypto_owned = 10.0 / 2500.0  # 0.004 ETH
        self.current_value = self.crypto_owned * self.current_price  # 10.52 EUR
        self.profit = self.current_value - self.transactie_bedrag  # 0.52 EUR

    def test_eur_strategy(self):
        """
        EUR Strategy: Sell only transactie_bedrag EUR worth
        - Sell: amountQuote = 10 EUR
        - Crypto sold: 10 / 2630 = 0.0038 ETH
        - Leftover: 0.004 - 0.0038 = 0.0002 ETH (profit as crypto)
        """
        coin = MockCoin(
            transactie_bedrag=self.transactie_bedrag,
            last_buy_price=self.last_buy_price,
            proceeds_strategy='eur'
        )

        params = coin._calculate_sell_params(self.current_price)

        print("\n=== EUR STRATEGY ===")
        print(f"Input: bedrag={self.transactie_bedrag}, buy_price={self.last_buy_price}, sell_price={self.current_price}")
        print(f"Crypto owned: {self.crypto_owned:.8f} ETH")
        print(f"Current value: EUR {self.current_value:.2f}")
        print(f"Profit: EUR {self.profit:.2f}")
        print(f"Output: {params}")

        # Assertions
        self.assertEqual(params['strategy'], 'eur')
        self.assertFalse(params['use_amount'])  # Use amountQuote, not amount
        self.assertEqual(params['amountQuote'], self.transactie_bedrag)  # Sell EUR 10 worth
        self.assertEqual(params['expected_eur'], self.transactie_bedrag)
        self.assertAlmostEqual(params['profit'], self.profit, places=2)

        # Verify leftover calculation
        crypto_sold = params['amountQuote'] / self.current_price
        leftover_crypto = self.crypto_owned - crypto_sold
        leftover_value = leftover_crypto * self.current_price

        print(f"\nVerification:")
        print(f"  Crypto sold: {crypto_sold:.8f} ETH")
        print(f"  Leftover crypto: {leftover_crypto:.8f} ETH")
        print(f"  Leftover value: EUR {leftover_value:.2f}")

        self.assertGreater(leftover_crypto, 0)  # Should have leftover
        self.assertAlmostEqual(leftover_value, self.profit, places=2)

    def test_crypto_strategy(self):
        """
        CRYPTO Strategy: Sell ALL crypto
        - Sell: amount = 0.004 ETH (all)
        - EUR received: 0.004 * 2630 = 10.52 EUR
        - Leftover: 0 ETH
        """
        coin = MockCoin(
            transactie_bedrag=self.transactie_bedrag,
            last_buy_price=self.last_buy_price,
            proceeds_strategy='crypto'
        )

        params = coin._calculate_sell_params(self.current_price)

        print("\n=== CRYPTO STRATEGY ===")
        print(f"Input: bedrag={self.transactie_bedrag}, buy_price={self.last_buy_price}, sell_price={self.current_price}")
        print(f"Crypto owned: {self.crypto_owned:.8f} ETH")
        print(f"Current value: EUR {self.current_value:.2f}")
        print(f"Output: {params}")

        # Assertions
        self.assertEqual(params['strategy'], 'crypto')
        self.assertTrue(params['use_amount'])  # Use amount, not amountQuote
        self.assertAlmostEqual(params['amount'], self.crypto_owned, places=8)  # Sell all crypto
        self.assertAlmostEqual(params['expected_eur'], self.current_value, places=2)  # Full value
        self.assertAlmostEqual(params['profit'], self.profit, places=2)

        # Verify no leftover
        leftover_crypto = self.crypto_owned - params['amount']
        print(f"\nVerification:")
        print(f"  Crypto sold: {params['amount']:.8f} ETH (ALL)")
        print(f"  EUR received: EUR {params['expected_eur']:.2f}")
        print(f"  Leftover crypto: {leftover_crypto:.8f} ETH")

        self.assertAlmostEqual(leftover_crypto, 0, places=8)  # No leftover

    def test_split_strategy_50_percent(self):
        """
        SPLIT Strategy (50% ratio): Sell transactie_bedrag + (profit * 0.5)
        - Profit: EUR 0.52
        - Sell: amountQuote = 10 + (0.52 * 0.5) = 10.26 EUR
        - Leftover value: 0.52 * 0.5 = 0.26 EUR as crypto
        """
        coin = MockCoin(
            transactie_bedrag=self.transactie_bedrag,
            last_buy_price=self.last_buy_price,
            proceeds_strategy='split',
            proceeds_crypto_ratio=0.5
        )

        params = coin._calculate_sell_params(self.current_price)

        expected_sell = self.transactie_bedrag + (self.profit * 0.5)  # 10.26
        expected_leftover = self.profit * 0.5  # 0.26

        print("\n=== SPLIT STRATEGY (50%) ===")
        print(f"Input: bedrag={self.transactie_bedrag}, buy_price={self.last_buy_price}, sell_price={self.current_price}")
        print(f"Crypto owned: {self.crypto_owned:.8f} ETH")
        print(f"Profit: EUR {self.profit:.2f}")
        print(f"Ratio: 0.5")
        print(f"Expected sell: EUR {expected_sell:.2f}")
        print(f"Expected leftover: EUR {expected_leftover:.2f}")
        print(f"Output: {params}")

        # Assertions
        self.assertEqual(params['strategy'], 'split')
        self.assertFalse(params['use_amount'])  # Use amountQuote
        self.assertAlmostEqual(params['amountQuote'], expected_sell, places=2)
        self.assertAlmostEqual(params['leftover_value'], expected_leftover, places=2)

        # Verify leftover
        crypto_sold = params['amountQuote'] / self.current_price
        leftover_crypto = self.crypto_owned - crypto_sold
        leftover_value = leftover_crypto * self.current_price

        print(f"\nVerification:")
        print(f"  Crypto sold: {crypto_sold:.8f} ETH")
        print(f"  Leftover crypto: {leftover_crypto:.8f} ETH")
        print(f"  Leftover value: EUR {leftover_value:.2f}")

        self.assertAlmostEqual(leftover_value, expected_leftover, places=1)

    def test_split_strategy_75_percent(self):
        """
        SPLIT Strategy (75% ratio): More profit reinvested
        - Profit: EUR 0.52
        - Sell: amountQuote = 10 + (0.52 * 0.75) = 10.39 EUR
        - Leftover value: 0.52 * 0.25 = 0.13 EUR as crypto
        """
        coin = MockCoin(
            transactie_bedrag=self.transactie_bedrag,
            last_buy_price=self.last_buy_price,
            proceeds_strategy='split',
            proceeds_crypto_ratio=0.75
        )

        params = coin._calculate_sell_params(self.current_price)

        expected_sell = self.transactie_bedrag + (self.profit * 0.75)  # 10.39
        expected_leftover = self.profit * 0.25  # 0.13

        print("\n=== SPLIT STRATEGY (75%) ===")
        print(f"Ratio: 0.75")
        print(f"Expected sell: EUR {expected_sell:.2f}")
        print(f"Expected leftover: EUR {expected_leftover:.2f}")
        print(f"Output: {params}")

        self.assertAlmostEqual(params['amountQuote'], expected_sell, places=2)
        self.assertAlmostEqual(params['leftover_value'], expected_leftover, places=2)

    def test_no_last_buy_price_fallback(self):
        """Test fallback when last_buy_price is not available"""
        coin = MockCoin(
            transactie_bedrag=self.transactie_bedrag,
            last_buy_price=0,  # No buy price
            proceeds_strategy='crypto'
        )

        params = coin._calculate_sell_params(self.current_price)

        print("\n=== NO LAST_BUY_PRICE FALLBACK ===")
        print(f"Output: {params}")

        # Should fallback to amountQuote
        self.assertFalse(params['use_amount'])
        self.assertEqual(params['amountQuote'], self.transactie_bedrag)

    def test_loss_scenario(self):
        """Test split strategy when there's a loss"""
        loss_price = 2400.0  # Price dropped

        coin = MockCoin(
            transactie_bedrag=self.transactie_bedrag,
            last_buy_price=self.last_buy_price,
            proceeds_strategy='split',
            proceeds_crypto_ratio=0.5
        )

        params = coin._calculate_sell_params(loss_price)

        current_value = self.crypto_owned * loss_price
        loss = current_value - self.transactie_bedrag

        print("\n=== LOSS SCENARIO ===")
        print(f"Buy price: EUR {self.last_buy_price}")
        print(f"Sell price: EUR {loss_price}")
        print(f"Current value: EUR {current_value:.2f}")
        print(f"Loss: EUR {loss:.2f}")
        print(f"Output: {params}")

        # On loss, should just sell transactie_bedrag
        self.assertFalse(params['use_amount'])
        self.assertEqual(params['amountQuote'], self.transactie_bedrag)
        self.assertEqual(params['leftover_value'], 0)  # No leftover on loss


class TestSellStrategiesComparison(unittest.TestCase):
    """Compare all strategies side by side"""

    def test_comparison_table(self):
        """Print comparison table for all strategies"""
        transactie_bedrag = 10.0
        last_buy_price = 2500.0
        current_price = 2630.0

        crypto_owned = transactie_bedrag / last_buy_price
        current_value = crypto_owned * current_price
        profit = current_value - transactie_bedrag

        print("\n" + "="*80)
        print("SELL STRATEGIES COMPARISON")
        print("="*80)
        print(f"Setup: EUR {transactie_bedrag} @ EUR {last_buy_price} -> 0.004 ETH")
        print(f"Current price: EUR {current_price}")
        print(f"Current value: EUR {current_value:.2f}")
        print(f"Profit: EUR {profit:.2f} ({profit/transactie_bedrag*100:.1f}%)")
        print("-"*80)

        strategies = [
            ('eur', 0.5),
            ('crypto', 0.5),
            ('split', 0.5),
            ('split', 0.75),
        ]

        print(f"{'Strategy':<15} {'Sell Type':<12} {'Sell Amount':<15} {'EUR Recv':<12} {'Leftover':<12}")
        print("-"*80)

        for strategy, ratio in strategies:
            coin = MockCoin(transactie_bedrag, last_buy_price, strategy, ratio)
            params = coin._calculate_sell_params(current_price)

            if params['use_amount']:
                sell_type = 'amount'
                sell_amount = f"{params['amount']:.8f} ETH"
            else:
                sell_type = 'amountQuote'
                sell_amount = f"EUR {params['amountQuote']:.2f}"

            eur_recv = params['expected_eur']
            leftover = params.get('leftover_value', params.get('profit', 0))
            if strategy == 'crypto':
                leftover = 0

            label = f"{strategy}" if strategy != 'split' else f"split({int(ratio*100)}%)"
            print(f"{label:<15} {sell_type:<12} {sell_amount:<15} EUR {eur_recv:<8.2f} EUR {leftover:<8.2f}")

        print("="*80)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
