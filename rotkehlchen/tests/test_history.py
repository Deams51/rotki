import os

import pytest

from rotkehlchen.constants.assets import A_ETH
from rotkehlchen.fval import FVal
from rotkehlchen.history import (
    ASSETMOVEMENTS_HISTORYFILE,
    ETHEREUM_TX_LOGFILE,
    LOANS_HISTORYFILE,
    TRADES_HISTORYFILE,
    limit_trade_list_to_period,
)
from rotkehlchen.order_formatting import Trade
from rotkehlchen.tests.utils.history import TEST_END_TS, mock_history_processing_and_exchanges
from rotkehlchen.typing import TradeType


@pytest.mark.parametrize('use_clean_caching_directory', [True])
def test_history_creation(
        rotkehlchen_server_with_exchanges,
        accountant,
        trades_historian_with_exchanges,
):
    """This is a big test that contacts all exchange mocks and returns mocked
    trades and other data from exchanges in order to create the accounting history
    for a specific period and see that rotkehlchen handles the creation of that
    history correctly"""
    server = rotkehlchen_server_with_exchanges
    rotki = server.rotkehlchen
    rotki.accountant = accountant
    rotki.trades_historian = trades_historian_with_exchanges
    rotki.kraken.random_trade_data = False
    rotki.kraken.random_ledgers_data = False
    (
        accountant_patch,
        polo_patch,
        binance_patch,
        bittrex_patch,
    ) = mock_history_processing_and_exchanges(rotki)
    with accountant_patch, polo_patch, binance_patch, bittrex_patch:
        response = server.process_trade_history(start_ts='0', end_ts=str(TEST_END_TS))
    # The history processing is completely mocked away and omitted in this test.
    # because it is only for the history creation not its processing.
    # For history processing tests look at test_accounting.py and
    # test_accounting_events.py
    assert response['message'] == ''
    assert response['result'] == {}

    # And now make sure that warnings have also been generated for the query of
    # the unsupported/unknown assets
    warnings = rotki.msg_aggregator.consume_warnings()
    assert len(warnings) == 16
    assert 'kraken trade with unprocessable pair IDONTEXISTZEUR' in warnings[0]
    assert 'kraken trade with unknown asset IDONTEXISTTOO' in warnings[1]
    assert 'kraken trade with unprocessable pair %$#%$#%$#%$#%$#%' in warnings[2]
    assert 'unknown kraken asset IDONTEXIST. Ignoring its deposit/withdrawals query' in warnings[3]
    msg = 'unknown kraken asset IDONTEXISTEITHER. Ignoring its deposit/withdrawals query'
    assert msg in warnings[4]
    assert 'poloniex trade with unknown asset NOEXISTINGASSET' in warnings[5]
    assert 'poloniex trade with unsupported asset BALLS' in warnings[6]
    assert 'poloniex loan with unsupported asset BDC' in warnings[7]
    assert 'poloniex loan with unknown asset NOTEXISTINGASSET' in warnings[8]
    assert 'withdrawal of unknown poloniex asset IDONTEXIST' in warnings[9]
    assert 'withdrawal of unsupported poloniex asset DIS' in warnings[10]
    assert 'deposit of unknown poloniex asset IDONTEXIST' in warnings[11]
    assert 'deposit of unsupported poloniex asset EBT' in warnings[12]
    assert 'bittrex trade with unsupported asset PTON' in warnings[13]
    assert 'bittrex trade with unknown asset IDONTEXIST' in warnings[14]
    assert 'bittrex trade with unprocessable pair %$#%$#%#$%' in warnings[15]


@pytest.mark.parametrize('use_clean_caching_directory', [True])
def test_history_creation_corrupt_trades_cache(
        rotkehlchen_server_with_exchanges,
        accountant,
        trades_historian_with_exchanges,
        accounting_data_dir,
):
    """
    Tests for corrupt trade cache.

    Test that if cache is used and data are corrupt we revert to omitting
    cache and contacting the exchanges
    """

    # Create the "broken" trades cache. Must have broken cache for all registered exchanges too
    historyfile_path = os.path.join(accounting_data_dir, TRADES_HISTORYFILE)
    with open(historyfile_path, 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[{{"unknown_trade_key": "random_trade_value"}}]}}',
        )
    with open(os.path.join(accounting_data_dir, 'poloniex_trades.json'), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'{{"BTC_SJX": [{{"unknown_trade_key": "random_trade_value"}}]}}}}',
        )
    with open(os.path.join(accounting_data_dir, 'kraken_trades.json'), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[{{"unknown_trade_key": "random_trade_value"}}]}}',
        )
    with open(os.path.join(accounting_data_dir, 'binance_trades.json'), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[{{"unknown_trade_key": "random_trade_value"}}]}}',
        )
    with open(os.path.join(accounting_data_dir, 'bittrex_trades.json'), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[{{"unknown_trade_key": "random_trade_value"}}]}}',
        )
    with open(os.path.join(accounting_data_dir, LOANS_HISTORYFILE), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[{{"unknown_trade_key": "random_trade_value"}}]}}',
        )
    with open(os.path.join(accounting_data_dir, ASSETMOVEMENTS_HISTORYFILE), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[]}}',
        )
    with open(os.path.join(accounting_data_dir, ETHEREUM_TX_LOGFILE), 'w') as f:
        f.write(
            f'{{"start_time":0, "end_time": {TEST_END_TS}, "data": '
            f'[]}}',
        )

    server = rotkehlchen_server_with_exchanges
    rotki = server.rotkehlchen
    rotki.accountant = accountant
    rotki.trades_historian = trades_historian_with_exchanges
    rotki.kraken.random_trade_data = False
    rotki.kraken.random_ledgers_data = False
    (
        accountant_patch,
        polo_patch,
        binance_patch,
        bittrex_patch,
    ) = mock_history_processing_and_exchanges(rotki)
    with accountant_patch, polo_patch, binance_patch, bittrex_patch:
        response = server.process_trade_history(start_ts='0', end_ts=str(TEST_END_TS))
    # The history processing is completely mocked away and omitted in this test.
    # because it is only for the history creation not its processing.
    # For history processing tests look at test_accounting.py and
    # test_accounting_events.py
    assert response['message'] == ''
    assert response['result'] == {}

    # And now make sure that warnings/errors number did not change
    warnings = rotki.msg_aggregator.consume_warnings()
    assert len(warnings) == 16
    errors = rotki.msg_aggregator.consume_errors()
    assert len(errors) == 0


def test_limit_trade_list_to_period():
    trade1 = Trade(
        timestamp=1459427707,
        location='kraken',
        pair='ETH_BTC',
        trade_type=TradeType.BUY,
        amount=FVal(1),
        rate=FVal(1),
        fee=FVal('0.1'),
        fee_currency=A_ETH,
    )
    trade2 = Trade(
        timestamp=1469427707,
        location='poloniex',
        pair='ETH_BTC',
        trade_type=TradeType.BUY,
        amount=FVal(1),
        rate=FVal(1),
        fee=FVal('0.1'),
        fee_currency=A_ETH,
    )
    trade3 = Trade(
        timestamp=1479427707,
        location='poloniex',
        pair='ETH_BTC',
        trade_type=TradeType.BUY,
        amount=FVal(1),
        rate=FVal(1),
        fee=FVal('0.1'),
        fee_currency=A_ETH,
    )

    full_list = [trade1, trade2, trade3]
    assert limit_trade_list_to_period(full_list, 1459427706, 1479427708) == full_list
    assert limit_trade_list_to_period(full_list, 1459427707, 1479427708) == full_list
    assert limit_trade_list_to_period(full_list, 1459427707, 1479427707) == full_list

    expected = [trade2, trade3]
    assert limit_trade_list_to_period(full_list, 1459427708, 1479427707) == expected
    expected = [trade2]
    assert limit_trade_list_to_period(full_list, 1459427708, 1479427706) == expected
    assert limit_trade_list_to_period(full_list, 0, 10) == []
    assert limit_trade_list_to_period(full_list, 1479427708, 1479427719) == []
    assert limit_trade_list_to_period([trade1], 1459427707, 1459427707) == [trade1]
    assert limit_trade_list_to_period([trade2], 1469427707, 1469427707) == [trade2]
    assert limit_trade_list_to_period([trade3], 1479427707, 1479427707) == [trade3]
    assert limit_trade_list_to_period(full_list, 1459427707, 1459427707) == [trade1]
    assert limit_trade_list_to_period(full_list, 1469427707, 1469427707) == [trade2]
    assert limit_trade_list_to_period(full_list, 1479427707, 1479427707) == [trade3]