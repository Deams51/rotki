from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
import requests

from rotkehlchen.tests.utils.api import (
    api_url_for,
    assert_error_response,
    assert_ok_async_response,
    assert_proper_response,
    assert_simple_ok_response,
    wait_for_async_task,
)
from rotkehlchen.tests.utils.exchanges import (
    assert_binance_balances_result,
    assert_poloniex_balances_result,
    patch_binance_balances_query,
    patch_poloniex_balances_query,
)
from rotkehlchen.tests.utils.history import (
    assert_binance_trades_result,
    assert_poloniex_trades_result,
    mock_history_processing_and_exchanges,
)

API_KEYPAIR_VALIDATION_PATCH = patch(
    'rotkehlchen.exchanges.kraken.Kraken.validate_api_key',
    return_value=(True, ''),
)


def test_setup_exchange(rotkehlchen_api_server):
    """Test that setting up an exchange via the api works"""
    # Check that no exchanges are registered
    response = requests.get(api_url_for(rotkehlchen_api_server, "exchangesresource"))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    assert json_data['result'] == []

    # First test that if api key validation fails we get an error
    data = {'name': 'kraken', 'api_key': 'ddddd', 'api_secret': 'fffffff'}
    response = requests.put(api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Provided API Key or secret is in invalid Format',
        status_code=HTTPStatus.CONFLICT,
    )

    # Mock the api pair validation and make sure that the exchange is setup
    data = {'name': 'kraken', 'api_key': 'ddddd', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_simple_ok_response(response)

    # and check that kraken is now registered
    response = requests.get(api_url_for(rotkehlchen_api_server, "exchangesresource"))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    assert json_data['result'] == ['kraken']

    # Check that we get an error if we try to re-setup an already setup exchange
    data = {'name': 'kraken', 'api_key': 'ddddd', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Exchange kraken is already registered',
        status_code=HTTPStatus.CONFLICT,
    )


def test_setup_exchange_errors(rotkehlchen_api_server):
    """Test errors and edge cases of setup_exchange endpoint"""

    # Provide unsupported exchange name
    data = {'name': 'superexchange', 'api_key': 'ddddd', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Exchange superexchange is not supported',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # Provide invalid type exchange name
    data = {'name': 3434, 'api_key': 'ddddd', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Exchange name should be a string',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # Omit exchange name
    data = {'api_key': 'ddddd', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Missing data for required field',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # Provide invalid type for api key
    data = {'name': 'kraken', 'api_key': True, 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Given API Key should be a string',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # Omit api key
    data = {'name': 'kraken', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Missing data for required field',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # Provide invalid type for api secret
    data = {'name': 'kraken', 'api_key': 'ddddd', 'api_secret': 234.1}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Given API Secret should be a string',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # Omit api secret
    data = {'name': 'kraken', 'api_key': 'ddddd'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_error_response(
        response=response,
        contained_in_msg='Missing data for required field',
        status_code=HTTPStatus.BAD_REQUEST,
    )


def test_remove_exchange(rotkehlchen_api_server):
    """Test that removing a setup exchange via the api works"""
    # Setup kraken exchange
    data = {'name': 'kraken', 'api_key': 'ddddd', 'api_secret': 'fffffff'}
    with API_KEYPAIR_VALIDATION_PATCH:
        response = requests.put(
            api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data,
        )
    assert_simple_ok_response(response)

    # and check that kraken is now registered
    response = requests.get(api_url_for(rotkehlchen_api_server, "exchangesresource"))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    assert json_data['result'] == ['kraken']

    # Now remove the registered kraken exchange
    data = {'name': 'kraken'}
    response = requests.delete(api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data)
    assert_simple_ok_response(response)
    # and check that it's not registered anymore
    response = requests.get(api_url_for(rotkehlchen_api_server, "exchangesresource"))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    assert json_data['result'] == []

    # now try to remove a non-registered exchange
    data = {'name': 'binance'}
    response = requests.delete(api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Exchange binance is not registered',
        status_code=HTTPStatus.CONFLICT,
    )


def test_remove_exchange_errors(rotkehlchen_api_server):
    """Errors and edge cases when using the remove exchange endpoint"""
    # remove unsupported exchange
    data = {'name': 'wowexchange'}
    response = requests.delete(api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Exchange wowexchange is not supported',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # invalid type for exchange name
    data = {'name': 5533}
    response = requests.delete(api_url_for(rotkehlchen_api_server, "exchangesresource"), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Exchange name should be a string',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # omit exchange name at removal
    response = requests.delete(api_url_for(rotkehlchen_api_server, "exchangesresource"))
    assert_error_response(
        response=response,
        contained_in_msg='Missing data for required field',
        status_code=HTTPStatus.BAD_REQUEST,
    )


@pytest.mark.parametrize('added_exchanges', [('binance', 'poloniex')])
def test_exchange_query_balances(rotkehlchen_api_server_with_exchanges):
    """Test that using the exchange balances query endpoint works fine"""

    # query balances of one specific exchange
    server = rotkehlchen_api_server_with_exchanges
    binance = server.rest_api.rotkehlchen.exchange_manager.connected_exchanges['binance']

    binance_patch = patch_binance_balances_query(binance)
    with binance_patch:
        response = requests.get(api_url_for(
            server,
            "named_exchanges_balances_resource",
            name='binance',
        ))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    result = json_data['result']
    assert_binance_balances_result(json_data['result'])

    # query balances of all setup exchanges
    poloniex = server.rest_api.rotkehlchen.exchange_manager.connected_exchanges['poloniex']

    poloniex_patch = patch_poloniex_balances_query(poloniex)
    with binance_patch, poloniex_patch:
        response = requests.get(api_url_for(server, "exchangebalancesresource"))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    result = json_data['result']
    assert_binance_balances_result(result['binance'])
    assert_poloniex_balances_result(result['poloniex'])


@pytest.mark.parametrize('added_exchanges', [('binance', 'poloniex')])
def test_exchange_query_balances_async(rotkehlchen_api_server_with_exchanges):
    """Test that using the exchange balances query endpoint works fine for async calls"""
    # async query balances of one specific exchange
    server = rotkehlchen_api_server_with_exchanges
    binance = server.rest_api.rotkehlchen.exchange_manager.connected_exchanges['binance']

    binance_patch = patch_binance_balances_query(binance)
    with binance_patch:
        response = requests.get(api_url_for(
            server,
            "named_exchanges_balances_resource",
            name='binance',
        ), json={'async_query': True})
        task_id = assert_ok_async_response(response)
        outcome = wait_for_async_task(server, task_id)
    assert_binance_balances_result(outcome['result'])

    # async query balances of all setup exchanges
    poloniex = server.rest_api.rotkehlchen.exchange_manager.connected_exchanges['poloniex']

    poloniex_patch = patch_poloniex_balances_query(poloniex)
    with binance_patch, poloniex_patch:
        response = requests.get(
            api_url_for(server, "exchangebalancesresource"),
            json={'async_query': True},
        )
        task_id = assert_ok_async_response(response)
        outcome = wait_for_async_task(server, task_id)
    result = outcome['result']
    assert_binance_balances_result(result['binance'])
    assert_poloniex_balances_result(result['poloniex'])


@pytest.mark.parametrize('added_exchanges', [('binance', 'poloniex')])
def test_exchange_query_balances_errors(rotkehlchen_api_server_with_exchanges):
    """Test errors and edge cases of the exchange balances query endpoint"""
    server = rotkehlchen_api_server_with_exchanges
    # Invalid exchange
    response = requests.get(api_url_for(
        server,
        "named_exchanges_balances_resource",
        name='dasdsad',
    ))
    assert_error_response(
        response=response,
        contained_in_msg='Exchange dasdsad is not supported',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # not registered exchange
    response = requests.get(api_url_for(
        server,
        "named_exchanges_balances_resource",
        name='kraken',
    ))
    assert_error_response(
        response=response,
        contained_in_msg='Could not query balances for kraken since it is not registered',
        status_code=HTTPStatus.CONFLICT,
    )


@pytest.mark.parametrize('added_exchanges', [('binance', 'poloniex')])
def test_exchange_query_trades(rotkehlchen_api_server_with_exchanges):
    """Test that using the exchange trades query endpoint works fine"""
    server = rotkehlchen_api_server_with_exchanges
    setup = mock_history_processing_and_exchanges(server.rest_api.rotkehlchen)
    # query trades of one specific exchange
    with setup.binance_patch:
        response = requests.get(api_url_for(
            server,
            "named_exchanges_trades_resource",
            name='binance',
        ))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    assert_binance_trades_result(json_data['result'])

    # query trades of all exchanges
    with setup.binance_patch, setup.polo_patch:
        response = requests.get(api_url_for(server, "exchangetradesresource"))
    assert_proper_response(response)
    json_data = response.json()
    assert json_data['message'] == ''
    assert len(json_data['result']) == 2, 'only two exchanges should be registered'
    assert_binance_trades_result(json_data['result']['binance'])
    assert_poloniex_trades_result(json_data['result']['poloniex'])

    def assert_okay(response):
        """Helper function for DRY checking below assertions"""
        assert_proper_response(response)
        json_data = response.json()
        assert json_data['message'] == ''
        assert len(json_data['result']) == 2, 'only two exchanges should be registered'
        assert_binance_trades_result(json_data['result']['binance'])
        assert_poloniex_trades_result(json_data['result']['poloniex'], trades_to_check=(0,))

    # and now query them in a specific time range excluding two of poloniex's trades
    data = {'from_timestamp': 1499865548, 'to_timestamp': 1539713118}
    with setup.binance_patch, setup.polo_patch:
        response = requests.get(api_url_for(server, "exchangetradesresource"), json=data)
    assert_okay(response)
    # do the same but with query args. This serves as test of from/to timestamp with query args
    with setup.binance_patch, setup.polo_patch:
        response = requests.get(
            api_url_for(server, "exchangetradesresource") + '?' + urlencode(data))
    assert_okay(response)


@pytest.mark.parametrize('added_exchanges', [('binance', 'poloniex')])
def test_exchange_query_trades_async(rotkehlchen_api_server_with_exchanges):
    """Test that using the exchange trades query endpoint works fine when called asynchronously"""
    server = rotkehlchen_api_server_with_exchanges
    setup = mock_history_processing_and_exchanges(server.rest_api.rotkehlchen)
    # async query trades of one specific exchange
    with setup.binance_patch:
        response = requests.get(api_url_for(
            server,
            "named_exchanges_trades_resource",
            name='binance',
        ), json={'async_query': True})
    task_id = assert_ok_async_response(response)
    outcome = wait_for_async_task(rotkehlchen_api_server_with_exchanges, task_id)
    assert_binance_trades_result(outcome['result'])

    def assert_okay(response):
        """Helper function for DRY checking below assertions"""
        task_id = assert_ok_async_response(response)
        outcome = wait_for_async_task(rotkehlchen_api_server_with_exchanges, task_id)
        assert_binance_trades_result(outcome['result']['binance'])
        assert_poloniex_trades_result(outcome['result']['poloniex'], trades_to_check=(0,))

    # query trades of all exchanges and in a specific range asynchronously
    data = {'from_timestamp': 1499865548, 'to_timestamp': 1539713118, 'async_query': True}
    with setup.binance_patch, setup.polo_patch:
        response = requests.get(api_url_for(server, "exchangetradesresource"), json=data)
    assert_okay(response)
    # do the same but with query args. This serves as test of async query with query args
    with setup.binance_patch, setup.polo_patch:
        response = requests.get(
            api_url_for(server, "exchangetradesresource") + '?' + urlencode(data),
        )
    assert_okay(response)


@pytest.mark.parametrize('added_exchanges', [('binance', 'poloniex')])
def test_exchange_query_trades_errors(rotkehlchen_api_server_with_exchanges):
    """Test errors and edge case of the exchange trades query endpoint"""
    server = rotkehlchen_api_server_with_exchanges
    # invalid exchange
    response = requests.get(api_url_for(
        server,
        "named_exchanges_trades_resource",
        name='boomshakalaka',
    ))
    assert_error_response(
        response=response,
        contained_in_msg='Exchange boomshakalaka is not supported',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # not registered exchange
    response = requests.get(api_url_for(
        server,
        "named_exchanges_trades_resource",
        name='bitmex',
    ))
    assert_error_response(
        response=response,
        contained_in_msg='Could not query trades for bitmex since it is not registered',
        status_code=HTTPStatus.CONFLICT,
    )

    data = {'from_timestamp': 0, 'to_timestamp': 1573409648}
    # TODO: move this into own test
    # from_timestamp being out of range (general test for timestamps field validation)

    data = {'from_timestamp': -1, 'to_timestamp': 1573409648}
    response = requests.get(api_url_for(
        server,
        "named_exchanges_trades_resource",
        name='binance',
    ), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Timestamps can not have negative values',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # from_timestamp not being a valid timestamp type
    data = {'from_timestamp': 'dasd', 'to_timestamp': 1573409648}
    response = requests.get(api_url_for(
        server,
        "named_exchanges_trades_resource",
        name='binance',
    ), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Failed to deserialize a timestamp entry from string dasd',
        status_code=HTTPStatus.BAD_REQUEST,
    )

    # to_timestamp not being a valid timestamp type
    data = {'from_timestamp': 1, 'to_timestamp': 'dasd'}
    response = requests.get(api_url_for(
        server,
        "named_exchanges_trades_resource",
        name='binance',
    ), json=data)
    assert_error_response(
        response=response,
        contained_in_msg='Failed to deserialize a timestamp entry from string dasd',
        status_code=HTTPStatus.BAD_REQUEST,
    )