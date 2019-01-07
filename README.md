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

## Pin certificate authority
Sometimes, the Comodo certificate is no accepted, probably because it is not in the certifi package yet. If you want to provide your own CA bundle, download the certificate for the web interface in your browser and store it. In this example, it is called `secure246lansforsakringarse.crt`.

Furthermore, download the intermediate certificate and the final certificate from Comodo:
* https://support.comodo.com/index.php?/Knowledgebase/Article/View/968/108/intermediate-ca-2-comodo-rsa-organization-validation-secure-server-ca-sha-2
* https://support.comodo.com/index.php?/Knowledgebase/Article/View/969/108/root-comodo-rsa-certification-authority-sha-2

Put them all together in a file
```
cat secure246lansforsakringarse.crt comodorsaorganizationvalidationsecureserverca.crt comodorsacertificationauthority.crt > comodo.ca-bundle
```

and then set the environment variable OVERRIDE_CA_BUNDLE to the path of the `comodo.ca-bundle` file:
```
$ export OVERRIDE_CA_BUNDLE=comodo.ca-bundle
$ python
```
