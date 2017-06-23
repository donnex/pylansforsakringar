# pylansforsakringar

A Python library for accessing bank data from Länsförsäkringars online bank. It uses both web scraping and an available JSON API that the browser uses.

## Usage

### Setup and login

```
from lansforsakringar import Lansforsarkingar
lf = Lansforsarkingar(PERSONAL_IDENTITY_NUMBER, PIN_CODE)
lf.login()
```

### View accounts overview

```
lf.get_accounts()

{u'12345678': {u'availableBalance': 10.25,
               u'currentBalance': 10.25,
               u'name': u'Privat',
               u'type': u'PRIMARY_ACCOUNT_OWNER'},
 u'87654321': {u'availableBalance': 2000.0,
               u'currentBalance': 2000.0,
               u'name': u'Privat spar',
               u'type': u'PRIMARY_ACCOUNT_OWNER'}}
```

### View transactions for account number

```
lf.get_account_transactions('12345678')

[{'amount': -10.0,
  'date': u'2017-06-22',
  'text': u'Example 1',
  'type': u'Betalning'},
 {'amount': -20.0,
  'date': u'2017-06-21',
  'text': u'Example 2',
  'type': u'Betalning'},
 {'amount': -30.0,
  'date': u'2017-06-20',
  'text': u'Example 3',
  'type': u'Betalning'}]
```
