import json
import logging
import os
import re
import sys
import io
import base64
import requests
import time
from PIL import Image
from bs4 import BeautifulSoup
import pyqrcode

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
ch = logging.StreamHandler()
logger.addHandler(ch)


class LansforsakringarError(Exception):
    pass


class LansforsakringarBankIDLogin:
    """
    Lansforsakringar does not support password based login anymore
    So we need to support BankID based login.
    This is not easy, as we need a human in the loop operating the app
    """
    BASE_URL = 'https://secure127.lansforsakringar.se'
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.109 Safari/537.36'}

    def __init__(self, personnummer):
        self.personnummer = personnummer
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        self.token = None

        verify = True
        override_ca_bundle = os.getenv('OVERRIDE_CA_BUNDLE')
        if override_ca_bundle:
            verify = override_ca_bundle

        # load initial cookies, seem to be needed
        self.first_req = self.session.get('https://secure246.lansforsakringar.se/im/privat/login', verify=verify)
        cookie_obj = requests.cookies.create_cookie(domain='secure127.lansforsakringar.se',name='mech',value='pMBankID')
        self.session.cookies.set_cookie(cookie_obj)

    def get_token(self):
        if self.token is None:
            url = '/lflogin/login.aspx/startBankIdClient'
            self.session.headers.update({'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
            req = self.session.post(self.BASE_URL + url, data="{{DataValue: \"{}:false\" }}".format(self.personnummer))
            data_resp = json.loads(req.content)
            self.token = data_resp["d"].split(',')
            if self.token is None or len(self.token) != 2:
                raise Exception("No token fetched.")
        return self.token

    def get_qr_bytes(self):
        url = '/lflogin/login.aspx/GetQRCode'
        token = self.get_token()[0]
        data = "{{autostarttoken: \"{}\"}}".format(token)
        req = self.session.post(self.BASE_URL + url, data=data)
        image_base = json.loads(req.content)["d"]
        image_byte = base64.b64decode(image_base)
        return image_byte

    def get_qr_string(self):
        return "bankid:///?autostarttoken={}".format(self.get_token()[0])

    def get_qr_terminal(self):
        """
        Get Linux terminal printout of QR Code
        """
        bankidqr = pyqrcode.create(self.get_qr_string())
        return bankidqr.terminal()

    def get_qr_as_image(self):
        image = Image.open(io.BytesIO(self.get_qr_bytes()))
        return image

    def save_qr_as_file(self, filename):
        with open(filename, 'wb') as file:
            file.write(self.get_qr_bytes())

    def wait_for_redirect(self):
        url = '/lflogin/login.aspx/BankIdCollect'
        token = self.get_token()[1]
        data = "{{DataValue: \"{}\" }}".format(token)
        self.session.headers.update({'Referer': self.first_req.url})

        wait_ended = False
        redirect = None
        step1 = False
        step2 = False
        while not wait_ended:
            req = self.session.post(self.BASE_URL + url, data=data)
            resp = json.loads(req.content)
            if resp["d"] == "1;Starta BankID-appen på din mobil eller surfplatta och tryck på QR-ikonen.":
                if not step1:
                    step1 = True
                    print("Starta BankID-appen på din mobil eller surfplatta och tryck på QR-ikonen.")
            elif resp["d"] == "1;Skriv in din säkerhetskod för Mobilt bankID på 6-8 tecken och tryck på legitimera eller avbryt.":
                if not step2:
                    step2 = True
                    print("Skriv in din säkerhetskod för Mobilt bankID på 6-8 tecken och tryck på legitimera eller avbryt.")
            elif step1 and step2 and "{url}" in resp["d"]:
                redirect = resp["d"].replace("0;{url}", "")
                wait_ended = True
            elif resp["d"] == "0;Åtgärden avbruten. Försök igen":
                print("An error occured. Try again in a few minutes.")
                return
            elif resp["d"] == "0;MobilBidInvalidParameters":
                print("An error occured. Try again in a few minutes.")
                return
            else:
                print("Unkown message: {}".format(resp["d"]))
            time.sleep(2)
        return redirect

class Lansforsakringar:
    BASE_URL = 'https://secure246.lansforsakringar.se'
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) '
               'AppleWebKit/537.36 (KHTML, like Gecko) '
               'Chrome/59.0.3071.109 Safari/537.36'}

    def __init__(self, personal_identity_number):
        self.personal_identity_number = personal_identity_number
        self.accounts = {}

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

    def _parse_json_token(self, body):
        """Parse the JSON token from body."""

        token_match = re.search('jsontoken=([\w-]+)', body)
        return token_match.group(1)

    def _parse_token(self, body):
        """Parse and save tokens from body."""

        old_json_token = self.json_token

        self.json_token = self._parse_json_token(body)

        logger.debug('JSON token set to: %s (Old: %s)', self.json_token,
                     old_json_token)

    def _parse_account_transactions(self, decoded):
        """Parse and return list of all account transactions."""

        transactions = []

        try:
            if "historicalTransactions" in decoded["response"]["transactions"]:
                for row in decoded["response"]["transactions"]["historicalTransactions"]:
                    transaction = {
                        'bookKeepingDate': row["bookKeepingDate"],
                        'transactionDate': row["transactionDate"],
                        'type': row["transactionType"],
                        'text': row["transactionText"],
                        'amount': row["amount"],
                        'comment': row["comment"]
                    }
                    transactions.append(transaction)
            if "upcomingTransactions" in decoded["response"]["transactions"]:
                for row in decoded["response"]["transactions"]["upcomingTransactions"]:
                    transaction = {
                        'transactionDate': row["transactionDate"],
                        'type': row["transactionType"],
                        'text': row["transactionText"],
                        'amount': row["amount"],
                        'comment': row["comment"]
                    }
                    transactions.append(transaction)
            return transactions
        except KeyError as e:
            print("Error: {}, JSON: {}".format(e, decoded))

    def login(self, url):
        """
        Login to the web bank
        url: URL after a successfull auth, e.g. the one from LansforsakringarBankIDLogin.wait_for_redirect()
        """

        verify = True

        override_ca_bundle = os.getenv('OVERRIDE_CA_BUNDLE')
        if override_ca_bundle:
            verify = override_ca_bundle

        req = self.session.get(url, verify=verify)
        self.last_req_body = req.content

        self._parse_token(req.text)

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

    def get_account_transactions(self, account_number, from_date=None, to_date=None):
        """Fetch and return account transactions for account_number."""
        if from_date is not None:
            from_date_str = from_date.strftime('%Y-%m-%d')
        else:
            from_date_str = ""
        if to_date is not None:
            to_date_str = to_date.strftime('%Y-%m-%d')
        else:
            to_date_str = ""
        pageNumber = 0
        moreExist = True
        transactions = []

        while moreExist:
            data = {
                'accountNumber': account_number,
                "currentPageNumber": pageNumber,
                "searchCriterion": {
                    "fromDate": from_date_str,
                    "toDate": to_date_str,
                    "fromAmount": "",
                    "toAmount": ""
                }
            }
            logger.debug(data)

            headers = {'Content-type': 'application/json',
                       'Accept': 'application/json',
                       'CSRFToken': self.json_token}
            path = '/im/json/account/getaccounttransactions'
            req = self.session.post(
                self.BASE_URL + path,
                data=json.dumps(data),
                headers=headers)

            logger.debug('Transaction request response code %s', req.status_code)

            # self._parse_token(req.text)
            logger.debug(req.text)

            # Parse transactions
            decoded = json.loads(req.text)

            moreExist = decoded["response"]["transactions"]["moreExist"]
            pageNumber += 1

            transactions += self._parse_account_transactions(decoded)
            logger.debug(transactions)

        # Request was ok but but no transactions were found. Try to refetch.
        # Requests seems to loose the connections sometimes with the message
        # "Resetting dropped connection". This should work around that
        # problem.
        #if req.status_code == requests.codes.ok and not transactions:
        #    transactions = self.get_account_transactions(account_number)

        return transactions
