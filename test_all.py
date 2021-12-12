from unittest.mock import Mock, patch
import pytest
from requests import Response
import json

from .lansforsakringar import Lansforsakringar, LansforsakringarBankIDLogin

MOCK_PERSONNUMMER = '201701012393'  # https://www.dataportal.se/sv/datasets/6_67959/testpersonnummer


def mock_response(data: str, status_code: int) -> Mock:
    mock_response = Mock(Response)
    mock_response.text = data
    mock_response.json.return_value = json.loads(data)
    mock_response.status_code = status_code
    return mock_response


def read_test_response_from_file(filename: str, status_code: int = 200) -> Mock:
    with open(f"test_data/{filename}", "r") as f:
        return mock_response(f.read(), status_code)


class TestLansforsakringarBankIDLogin:
    @patch('requests.Session.post')
    def test_get_token(self, mock_post) -> None:
        mock_post.return_value = read_test_response_from_file('start_token.json', 200)
        login_1 = LansforsakringarBankIDLogin(MOCK_PERSONNUMMER)
        token_1 = login_1.get_token()

        mock_post.assert_called_once_with(
            LansforsakringarBankIDLogin.BASE_URL + '/security/authentication/g2v2/g2/start',
            json={'userId': '', 'useQRCode': True},
        )

        assert isinstance(token_1, dict)
        assert token_1['autoStartToken'] == '70ada356-e9d8-4863-b8c7-d07057148c17'
        assert token_1['orderRef'] == '2385dd87-2eef-4f0e-82df-6bbe865c302e'

        mock_post.reset_mock()

        # cache is used
        token_1 = login_1.get_token()
        mock_post.assert_not_called()

        mock_post.reset_mock()

        # empty response
        mock_post.return_value = mock_response('{}', 200)
        login_2 = LansforsakringarBankIDLogin(MOCK_PERSONNUMMER)
        with pytest.raises(Exception):
            login_2.get_token()

        # incomplete response 1
        mock_post.return_value = mock_response('{"autoStartToken": "test1"}', 200)
        login_3 = LansforsakringarBankIDLogin(MOCK_PERSONNUMMER)
        with pytest.raises(Exception):
            login_3.get_token()

        # incomplete response 2
        mock_post.return_value = mock_response('{"orderRef": "test1"}', 200)
        login_4 = LansforsakringarBankIDLogin(MOCK_PERSONNUMMER)
        with pytest.raises(Exception):
            login_4.get_token()


class TestLansforsakringar:
    @patch('requests.Session.post')
    def test_get_accounts(self, mock_post) -> None:
        mock_post.return_value = read_test_response_from_file('getaccounts.txt', 200)

        lans = Lansforsakringar(MOCK_PERSONNUMMER)
        accounts = lans.get_accounts()
        mock_post.assert_called_once_with(
            Lansforsakringar.BASE_URL + '/im/json/overview/getaccounts',
            json={
                'customerId': MOCK_PERSONNUMMER,
                'responseControl': {
                    'filter': {
                        'includes': ['ALL']
                    }
                }
            },
            headers={'Content-type': 'application/json', 'Accept': 'application/json', 'CSRFToken': None}
        )
        assert isinstance(accounts, dict)
        # TODO: sometimes the account number is doubly string quoted
        assert list(accounts.keys()) == ["'50850045845'", '50850045846']

        account_1 = accounts["'50850045845'"]
        assert account_1["uncertainClaim"] is False
        assert account_1["creditAllowed"] is False
        assert account_1["name"] == "Privatkonto"
        assert account_1["currentBalance"] == 1234.32
        assert account_1["availableBalance"] == 1234.32
        assert account_1["type"] == "PRIMARY_ACCOUNT_OWNER"

        account_2 = accounts['50850045846']
        assert account_2["uncertainClaim"] is False
        assert account_2["creditAllowed"] is False
        assert account_2["name"] == "Sparkonto"
        assert account_2["currentBalance"] == 12345.33
        assert account_2["availableBalance"] == 12345.33
        assert account_2["type"] == "PRIMARY_ACCOUNT_OWNER"
