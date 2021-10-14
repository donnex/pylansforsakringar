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

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
ch = logging.StreamHandler()
logger.addHandler(ch)

requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.ERROR)
requests_log.propagate = True


class LansforsakringarError(Exception):
    pass


class LansforsakringarBankIDLogin:
    """
    Lansforsakringar does not support password based login anymore
    So we need to support BankID based login.
    This is not easy, as we need a human in the loop operating the app
    """
    BASE_URL = 'https://api.lansforsakringar.se'
    CLIENT_ID = 'LFAB-59IjjFXwGDTAB3K1uRHp9qAp'
    HEADERS = {
        'User-Agent': 'User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:93.0) Gecko/20100101 Firefox/93.0',
        'Authorization': f'Atmosphere atmosphere_app_id="LFAB-59IjjFXwGDTAB3K1uRHp9qAp"',
    }

    def __init__(self, personnummer):
        self.personnummer = personnummer
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        self.token = None

        verify = True
        override_ca_bundle = os.getenv('OVERRIDE_CA_BUNDLE')
        if override_ca_bundle:
            verify = override_ca_bundle

    def get_token(self):
        if self.token is None:
            url = self.BASE_URL + '/security/authentication/g2v2/g2/start'
            self.session.headers.update({
                'Content-Type': 'application/json;charset=UTF-8',
                'Accept': 'application/json'
            })
            req = self.session.post(url, json={"userId":"","useQRCode":True})
            self.token = json.loads(req.content)
            if self.token is None or len(self.token) != 2:
                raise Exception("No token fetched.")
        return self.token

    def get_qr_string(self):
        return f"bankid:///?autostarttoken={self.get_token()['autoStartToken']}"

    def get_intent(self):
        return f"intent:///?autostarttoken={self.get_token()['autoStartToken']}&redirect=null#Intent;scheme=bankid;package=com.bankid.bus;end"

    def get_qr_terminal(self):
        """
        Get Linux terminal printout of QR Code
        """
        bankidqr = pyqrcode.create(self.get_qr_string())
        return bankidqr.terminal()

    def wait_for_redirect(self) -> requests.cookies.RequestsCookieJar:
        url = self.BASE_URL + '/security/authentication/g2v2/g2/collect'
        data = {
            "clientId": self.CLIENT_ID,
            "isForCompany": False,
            "orderRef": self.get_token()['orderRef']
        }

        wait_ended = False
        cookie_jar = None
        step1 = False
        step2 = False
        while not wait_ended:
            req = self.session.post(url, json=data)
            resp = req.json()
            if resp["resultCode"] == "OUTSTANDING_TRANSACTION":
                if not step1:
                    step1 = True
                    print("Please scan this QR code.")
            elif resp["resultCode"] == "USER_SIGN":
                if not step2:
                    step2 = True
                    print("Please authenticate in the BankID app.")
            elif resp["resultCode"] == "COMPLETE":
                # This call sets a cookie on .lansforsakringar.se, so we just return the whole cookie jar
                print("Login successful.")
                wait_ended = True
                cookie_jar = req.cookies
            else:
                print(f"Unkown message: {resp}")
            time.sleep(2)
        return req.cookies

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

    def login(self, cookie_jar: requests.cookies.RequestsCookieJar, use_cache=False):
        """
        Login to the web bank
        cookie_jar: A CookieJar from the LansforsakringarBankIDLogin
        use_cache: Store token and cookies to disk. Beware that anyone with read access to those files can
        send requests as you
        """

        verify = True

        override_ca_bundle = os.getenv('OVERRIDE_CA_BUNDLE')
        if override_ca_bundle:
            verify = override_ca_bundle
        self.session.cookies = cookie_jar
        req = self.session.get(self.BASE_URL + '/im/login/privat', verify=verify)

        # TODO: cache cookie jar
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
