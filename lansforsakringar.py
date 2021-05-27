import json
import logging
import os
import re
import io
import base64
import requests
import time
from PIL import Image
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
            req = self.session.post(self.BASE_URL + url, data=f"{{DataValue: \"{self.personnummer}:false\" }}")
            data_resp = json.loads(req.content)
            self.token = data_resp["d"].split(',')
            if self.token is None or len(self.token) != 2:
                raise Exception("No token fetched.")
        return self.token

    def get_qr_bytes(self):
        url = '/lflogin/login.aspx/GetQRCode'
        token = self.get_token()[0]
        data = f"{{autostarttoken: \"{token}\"}}"
        req = self.session.post(self.BASE_URL + url, data=data)
        image_base = json.loads(req.content)["d"]
        image_byte = base64.b64decode(image_base)
        return image_byte

    def get_qr_string(self):
        return f"bankid:///?autostarttoken={self.get_token()[0]}"

    def get_intent(self):
        return f"intent:///?autostarttoken={self.get_token()[0]}&redirect=null#Intent;scheme=bankid;package=com.bankid.bus;end"

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
        data = f"{{DataValue: \"{token}\" }}"
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
            elif resp["d"] == "1;Legitimera dig i BankID-appen.":
                if not step2:
                    step2 = True
                    print("Legitimera dig i BankID-appen.")
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
                print(f"Unkown message: {resp['d']}")
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

        # Setup requests session
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _save_token_and_cookies(self) -> None:
        with open('lans_token.txt', 'w') as file:
            file.write(self.json_token)

        with open('lans_cookies.txt', 'w') as file:
            file.write(json.dumps(self.session.cookies.items()))

    def _load_token_and_cookies(self) -> None:
        try:
            with open('lans_token.txt', 'r') as file:
                token = file.read().replace('\n', '')
                self.json_token = token

            with open('lans_cookies.txt', 'r') as file:
                self.session.cookies.update(json.loads(file.read()))
        except FileNotFoundError:
            pass

    def check_token_and_cookies(self) -> bool:
        self._load_token_and_cookies()

        if self.get_accounts() is False:
            # request failed, unset data
            self.json_token = None
            self.session.cookies.clear()
            return False

        return True

    def _parse_json_token(self, body):
        """Parse the JSON token from body."""

        token_match = re.search('jsontoken=([\w-]+)', body)
        return token_match.group(1)

    def _parse_token(self, body, use_cache):
        """Parse and save tokens from body."""

        old_json_token = self.json_token

        self.json_token = self._parse_json_token(body)
        if use_cache:
            self._save_token_and_cookies()

        logger.debug(f'JSON token set to: {self.json_token} (Old: {old_json_token})')

    def _check_response(self, response) -> None:
        if "errors" in response.json().keys():
            raise Exception("Error in response {response}.")
        return

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
            print(f"Error: {e}, JSON: {decoded}")

    def login(self, url, use_cache=False):
        """
        Login to the web bank
        url: URL after a successful auth, e.g. the one from LansforsakringarBankIDLogin.wait_for_redirect()
        use_cache: Store token and cookies to disk. Beware that anyone with read access to those files can
        send requests as you
        """

        verify = True

        override_ca_bundle = os.getenv('OVERRIDE_CA_BUNDLE')
        if override_ca_bundle:
            verify = override_ca_bundle

        req = self.session.get(url, verify=verify)

        with open("login.txt", "w") as f:
            f.write(req.text)

        self._parse_token(req.text, use_cache)

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

        logger.debug(f'Transaction request response code {req.status_code}.')

        with open("getaccounts.txt", "w") as f:
            f.write(req.text)

        try:
            for account in req.json()['response']['accounts']:
                self.accounts[account['number']] = account
                del(self.accounts[account['number']]['number'])

            return self.accounts
        except json.decoder.JSONDecodeError:
            logger.error("JSON Decode error on get_accounts.")
            return False

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

            logger.debug(f'Transaction request response code {req.status_code}.')
            logger.debug(req.text)

            with open(f"getaccounttransactions_page{pageNumber}.txt", "w") as f:
                f.write(req.text)

            # Parse transactions
            decoded = req.json()

            moreExist = decoded["response"]["transactions"]["moreExist"]
            pageNumber += 1

            transactions += self._parse_account_transactions(decoded)
            logger.debug(transactions)

        return transactions
