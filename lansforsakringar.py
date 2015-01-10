import re

import requests
from bs4 import BeautifulSoup
from slugify import slugify


class Lansforsarkingar(object):
    def __init__(self, personal_number, pin_code):
        self.base_url = 'https://secure246.lansforsakringar.se'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/39.0.2171.95 Safari/537.36'}

        self.personal_number = personal_number
        self.pin_code = pin_code

        self.accounts = {}
        self.saving_accounts = {}
        self.founds = {}
        self.isk_founds = {}

        # Setup requests session
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _hidden_inputs_as_dict(self, soup):
        """Return all hidden inputs in a soup as a dict"""

        data = {}
        for input in soup.select('form input[type=hidden]'):
            data[input.attrs['name']] = input.attrs.get('value', '')

        return data

    def _fix_balance(self, balance):
        """Fix the bank balance and return it as a float"""

        return float(balance.replace(',', '.').replace(' ', ''))

    def _bank_name_key(self, name):
        """Return a key from account name"""

        return slugify(name).lower().replace('-', '_')

    def _parse_token(self, body):
        """Parse the token from body"""

        token_match = re.search('token\s*=[\s\']*(\d+)', body)
        return int(token_match.group(1))

    def _fetch_bank_form_page(self, id):
        """Fetch a bank form page, return the soup"""

        # Build POST data with hidden inputs from bank overview page
        hidden_inputs = self._hidden_inputs_as_dict(self.bank_overview_soup)
        data = {}
        data['bankOverviewForm_SUBMIT'] = 1
        data['newUc'] = 'true'
        data['bankOverviewForm:_idcl'] = id
        data['bankOverviewForm:_link_hidden_'] = ''
        data['javax.faces.ViewState'] = hidden_inputs['javax.faces.ViewState']
        data['_token'] = self.next_token

        # Request the ISK founds page to get the menu and build next POST
        path = '/im/im/bank.jsf'
        req = self.session.post(self.base_url + path, data=data)
        soup = BeautifulSoup(req.content)

        self.next_token = self._parse_token(req.text)

        return soup

    def login(self):
        """Login to the bank"""

        # Fetch and parse hidden inputs from login page
        req = self.session.get(self.base_url + '/im/login/privat')

        soup = BeautifulSoup(req.content)

        # Post login to current URL
        login_post_url = req.url

        # Build POST data with login settings and hidden inputs
        data = self._hidden_inputs_as_dict(soup)
        data['selMechanism'] = 'PIN-kod'
        data['btnLogIn.x'] = 0
        data['btnLogIn.y'] = 0
        data['inputPersonalNumber'] = self.personal_number
        data['inputPinCode'] = self.pin_code

        # Login request
        req = self.session.post(login_post_url, data=data)

        self.next_token = self._parse_token(req.text)

    def fetch_bank_overview(self):
        """Fetch bank overview page"""

        # Fetch bank overview
        path = '/im/im/bank.jsf?newUc=true&_token={}'.format(self.next_token)
        req = self.session.get(self.base_url + path)
        soup = BeautifulSoup(req.content)

        self.next_token = self._parse_token(req.text)

        self.bank_overview_soup = soup

        # Accounts
        for tr in soup.select('#bankOverviewForm:commonAccountDataTable '
                              'tbody tr'):
            name = tr.select('td')[0].text
            balance = self._fix_balance(tr.select('td')[2].text)

            key = self._bank_name_key(name)
            id = tr.select('a')[0].attrs['id']

            self.accounts[key] = {'name': name, 'balance': balance, 'id': id}

        # Saving accounts
        for tr in soup.select('#bankOverviewForm:savingAccountDataTable '
                              'tbody tr'):
            name = tr.select('td')[0].text
            balance = self._fix_balance(tr.select('td')[2].text)

            key = self._bank_name_key(name)
            id = tr.select('a')[0].attrs['id']

            self.saving_accounts[key] = {'name': name, 'balance': balance,
                                         'id': id}

        # Founds
        for tr in soup.select('#bankOverviewForm:fundsDataTable tbody tr'):
            name = tr.select('td')[0].text
            balance = self._fix_balance(tr.select('td')[2].text)

            key = self._bank_name_key(name)
            id = tr.select('a')[0].attrs['id']

            self.founds[key] = {'name': name, 'balance': balance, 'id': id}

        # ISK founds
        for tr in soup.select('#bankOverviewForm:iskDataTable tbody tr'):
            name = tr.select('td')[0].text
            balance = self._fix_balance(tr.select('td')[2].text)

            key = self._bank_name_key(name)
            id = tr.select('a')[0].attrs['id']

            self.isk_founds[key] = {'name': name, 'balance': balance, 'id': id}

        return True

    def fetch_account_details(self, id):
        """Fetch and return account details"""

        # Fetch the bank page
        soup = self._fetch_bank_form_page(id)

        actions = []

        # Parse actions from table
        table = soup.select('#viewAccountListTransactionsForm:'
                            'transactionsDataTable')[0]
        for tr in table.select('tbody tr'):
            date = tr.select('td')[1].text
            description = tr.select('td')[2].text
            amount = self._fix_balance(tr.select('td')[3].text)
            new_balance = self._fix_balance(tr.select('td')[4].text)

            actions.append({'date': date, 'description': description,
                            'amount': amount, 'new_balance': new_balance})

        return actions

    def fetch_founds_detail(self, id):
        """Fetch and return founds detail"""

        # Fetch the bank page
        soup = self._fetch_bank_form_page(id)

        founds = {}

        # Parse founds
        table = soup.select('#mutualFundList:MutualFundList')[0]
        for tr in table.select('tbody tr'):
            name = tr.select('td a')[0].text
            balance = self._fix_balance(tr.select('td')[3].text)
            acquisition_value = self._fix_balance(tr.select('td')[4].text)

            key = self._bank_name_key(name)

            founds[key] = {'name': name, 'balance': balance,
                           'acquisition_value': acquisition_value}

        # Total
        tr_total = table.select('tfoot tr')[0]
        name = 'Totalt'
        balance = self._fix_balance(tr_total.select('td')[3].text)
        acquisition_value = self._fix_balance(tr_total.select('td')[4].text)
        key = 'totalt'
        founds[key] = {'name': name, 'balance': balance,
                       'acquisition_value': acquisition_value}

        return founds

    def fetch_isk_founds_detail(self, id):
        """Fetch and return ISK founds detail"""

        # Fetch the bank page
        soup = self._fetch_bank_form_page(id)

        # Build requst for the ISK founds page
        hidden_inputs = self._hidden_inputs_as_dict(soup)
        data = {}
        data['sideMenuForm_SUBMIT'] = 1
        data['sideMenuForm:_link_hidden_'] = ''
        data['sideMenuForm:_idcl'] = 'sideMenuForm_sidemenu_item0_item2'
        data['javax.faces.ViewState'] = hidden_inputs['javax.faces.ViewState']
        data['_token'] = self.next_token

        # Request the ISK founds detail page
        path = ('/im/jsp/investmentsavingsaccount/view/'
                'viewInvestmentSavingsAccountOverview.jsf')
        req = self.session.post(self.base_url + path, data=data)
        soup = BeautifulSoup(req.content)

        self.next_token = self._parse_token(req.text)

        return self.parse_isk_founds(soup)

    def parse_isk_founds(self, soup):
        """Parse ISK founds details from soup"""

        isk_founds = {}

        # Founds
        table = soup.select('#viewInvestmentSavingsFundHoldingsForm:'
                            'fundDataTable')[0]
        for tr in table.select('tbody tr'):
            name = tr.select('td span')[0].text
            balance = self._fix_balance(tr.select('td')[3].text)
            acquisition_value = self._fix_balance(tr.select('td')[4].text)

            key = self._bank_name_key(name)

            isk_founds[key] = {'name': name, 'balance': balance,
                               'acquisition_value': acquisition_value}

        # Total
        tr_total = table.select('tfoot tr')[0]
        name = 'Totalt'
        balance = self._fix_balance(tr_total.select('td')[3].text)
        acquisition_value = self._fix_balance(tr_total.select('td')[4].text)
        key = 'totalt'
        isk_founds[key] = {'name': name, 'balance': balance,
                           'acquisition_value': acquisition_value}

        return isk_founds
