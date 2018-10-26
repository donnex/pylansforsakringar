import json
import logging
import os
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LansforsakringarError(Exception):
    pass


class Lansforsakringar(object):
    BASE_URL = 'https://secure246.lansforsakringar.se'
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) '
               'AppleWebKit/537.36 (KHTML, like Gecko) '
               'Chrome/59.0.3071.109 Safari/537.36'}

    def __init__(self, personal_identity_number, pin_code):
        if not personal_identity_number or not pin_code:
            raise LansforsakringarError('Missing personal identity number '
                                        '({}) or pin code ({})'.format(
                                            personal_identity_number,
                                            pin_code))

        self.personal_identity_number = personal_identity_number
        self.pin_code = pin_code

        self.accounts = {}

        self.token = None
        self.json_token = None
        self.last_req_body = None

        # Setup requests session
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _hidden_inputs_as_dict(self, elements):
        """Return all hidden inputs in elements list as a dict."""

        data = {}

        # Make sure elements is a list
        if not isinstance(elements, list):
            elements = [elements]

        for element in elements:
            for input in element.select('input[type=hidden]'):
                data[input.attrs['name']] = input.attrs.get('value', '')

        return data

    def _fix_balance(self, balance):
        """Fix the bank balance and return it as a float."""

        return float(balance.replace(',', '.').replace(' ', ''))

    def _parse_token(self, body):
        """Parse the token from body."""

        token_match = re.search('var\s*token\s*=[\s\']*(\d+)', body)
        return int(token_match.group(1))

    def _parse_json_token(self, body):
        """Parse the JSON token from body."""

        token_match = re.search('var\s*jsonToken\s*=[\s\']*([\w-]+)', body)
        return token_match.group(1)

    def _parse_tokens(self, body):
        """Parse and save tokens from body."""

        old_token = self.token
        old_json_token = self.json_token

        self.token = self._parse_token(body)
        self.json_token = self._parse_json_token(body)

        logger.debug('Token set to: %s (Old: %s)', self.token, old_token)
        logger.debug('JSON token set to: %s (Old: %s)', self.json_token,
                     old_json_token)

    def _parse_account_transactions(self, body):
        """Parse and return list of all account transactions."""

        transactions = []

        soup = BeautifulSoup(body, 'html.parser')
        for row in soup.select('.history.data-list-wrapper-inner tr'):
            transaction = {
                'date': row.select('td')[1].text,
                'type': row.select('td')[2].select('span')[0].text,
                'text': row.select('td')[2].select('div')[0].text,
                'amount': self._fix_balance(row.select('td')[3].text)
            }
            transactions.append(transaction)

        return transactions

    def login(self):
        """Login to the bank."""

        # Fetch and parse hidden inputs from login page
        # Use specific CA bundle to fix SSL verify problems if set as env.
        verify = True

        override_ca_bundle = os.getenv('OVERRIDE_CA_BUNDLE')
        if override_ca_bundle:
            verify = override_ca_bundle

        req = self.session.get(self.BASE_URL + '/im/login/privat',
                               verify=verify)

        # Get the login form
        soup = BeautifulSoup(req.content, 'html.parser')
        login_form = soup.select('#pPin_form')

        # Post login to current URL
        login_post_url = req.url

        # Build POST data with login settings and hidden inputs
        data = self._hidden_inputs_as_dict(login_form)
        data['pPin_inp'] = self.personal_identity_number
        data['pPinKod_inp'] = self.pin_code

        # Login request
        req = self.session.post(login_post_url, data=data)
        self.last_req_body = req.content

        self._parse_tokens(req.text)

        return True

    def get_accounts(self):
        """Fetch bank accounts by using json.

        This uses the same json api URL that the browser does when logged in.
        It also need to send the CSRFToken (JSON token) in order to work.
        """

        data = {
            'customerId': self.personal_identity_number,
            'responseControl': {
                'filter': {
                    'includes': ['ALL']
                }
            }
        }

        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json',
                   'CSRFToken': self.json_token}
        path = '/im/json/overview/getaccounts'
        req = self.session.post(
            self.BASE_URL + path,
            data=json.dumps(data),
            headers=headers)

        for account in req.json()['response']['accounts']:
            self.accounts[account['number']] = account
            del(self.accounts[account['number']]['number'])

        return self.accounts

    def get_account_transactions(self, account_number):
        """Fetch and return account transactions for account_number."""

        logger.debug('Fetching account transactions for account %s',
                     account_number)

        # Get javax.faces.ViewState from the last request
        last_req_hidden_inputs = self._hidden_inputs_as_dict(
            BeautifulSoup(self.last_req_body, 'html.parser'))

        data = {
            'dialog-overview_showAccount': 'Submit',
            'menuLinks_SUBMIT': 1,
            'menuLinks:_idcl': '',
            'menuLinks:_link_hidden_': '',
            'javax.faces.ViewState': last_req_hidden_inputs.get(
                'javax.faces.ViewState'),
            '_token': self.token,
            'productId': account_number
        }

        path = '/im/im/csw.jsf'
        req = self.session.post(self.BASE_URL + path, data=data)
        self.last_req_body = req.content

        logger.debug('Transaction request response code %s', req.status_code)

        self._parse_tokens(req.text)

        # Parse transactions
        transactions = self._parse_account_transactions(req.text)

        # Request was ok but but no transactions were found. Try to refetch.
        # Requests seems to loose the connections sometimes with the message
        # "Resetting dropped connection". This should work around that
        # problem.
        if req.status_code == requests.codes.ok and not transactions:
            transactions = self.get_account_transactions(account_number)

        return transactions
