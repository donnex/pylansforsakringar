from unittest.mock import Mock, patch
from requests import Response
import json

from .lansforsakringar import Lansforsakringar

MOCK_PERSONNUMMER = '201701012393'  # https://www.dataportal.se/sv/datasets/6_67959/testpersonnummer


def load_test_response(filename):
    with open(f"test_data/{filename}", "r") as f:
        data = f.read()
        mock_response = Mock(Response)
        mock_response.text = data
        mock_response.json.return_value = json.loads(data)
        return mock_response


class TestLansforsakringar:
    @patch('requests.Session.post')
    def test_get_accounts(self, mock_post):
        mock_post.return_value = load_test_response('getaccounts.txt')

        lans = Lansforsakringar(MOCK_PERSONNUMMER)
        accounts = lans.get_accounts()
        mock_post.assert_called_once_with(
            Lansforsakringar.BASE_URL + '/im/json/overview/getaccounts',
            data=json.dumps({
                'customerId': MOCK_PERSONNUMMER,
                'responseControl': {
                    'filter': {
                        'includes': ['ALL']
                    }
                }
            }),
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
