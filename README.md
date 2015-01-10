# About
A Python library for accessing bank data by parsing Länsförsäkringars online bank.

# Usage
## Setup and login
    lf = Lansforsarkingar(PERSONAL_IDENTITY_NUMBER, PIN_CODE)
    lf.login()
    lf.fetch_bank_overview()

## View accounts overview
    lf.accounts

    ipdb> pprint(lf.accounts)
    {u'konto_1': {'balance': 1865.0,
                     'id': u'ID',
                     'name': u'Konto 1'},
     u'konto_2': {'balance': 2000.0,
                 'id': u'ID',
                 'name': u'Konto 2'}}

## View saving accounts overview
    lf.saving_accounts

    ipdb> pprint(lf.saving_accounts)
    {u'spar_1': {'balance': 2000.0,
                          'id': u'ID',
                          'name': u'Spar 1'},
     u'spar_2': {'balance': 3000.0,
                      'id': u'ID',
                      'name': u'Spar 2'}}

## Fetch account details
    lf.fetch_account_details(id)

    ipdb> pprint(lf.fetch_account_details(lf.accounts['konto_1']['id']))
    [{'amount': -55.0,
      'date': u'2015-01-07',
      'description': u'DESCRIPTION',
      'new_balance': 1865.0},
     {'amount': -135.0,
      'date': u'2015-01-06',
      'description': u'DESCRIPTION',
      'new_balance': 2000.0},
      ...

## View founds overview
    lf.founds

    ipdb> pprint(lf.founds)
    {u'fonder': {'balance': 4900.0,
                 'id': u'ID',
                 'name': u'Fonder'}}

## Fetch founds detail
    lf.fetch_founds_detail(id)

    ipdb> pprint(lf.fetch_founds_detail(lf.founds['fonder']['id']))
    {u'fond_1': {'acquisition_value': 2000.0,
                       'balance': 2200.0,
                       'name': u'Fond 1'},
     u'fond_2': {'acquisition_value': 2500.0,
                       'balance': 2700.0,
                       'name': u'Fond 2'},
     'totalt': {'acquisition_value': 4500.0,
                'balance': 4900.0,
                'name': 'Totalt'}}

## View ISK founds overview
    lf.isk_founds

    ipdb> pprint(lf.isk_founds)
    {u'isk_1': {'balance': 4000.0,
                         'id': u'ID',
                         'name': u'ISK 1'},
     u'isk_2': {'balance': 5000.0,
                     'id': u'ID',
                     'name': u'ISK 2'}}

## Fetch ISK founds detail
    lf.fetch_isk_founds_detail(ID)

    ipdb> pprint(lf.fetch_isk_founds_detail(lf.isk_founds['isk_1']['id']))
    {u'isk_fond_1': {'acquisition_value': 3800.0,
                       'balance': 4000.0,
                       'name': u'ISK Fond 1'},
     u'isk_fond_2': {'acquisition_value': 4800.0,
                       'balance': 5000.0,
                       'name': u'ISK Fond 2'},
     'totalt': {'acquisition_value': 8600.0, 'balance': 9000.0, 'name': 'Totalt'}}
