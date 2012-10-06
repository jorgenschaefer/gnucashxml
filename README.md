# GNU Cash XML Library

`gnucashxml` is a [Python][] library to parse [GNU Cash][] XML files.
This allows writing reporting utilities that do not rely on the GNU
Cash libraries themselves, or require the main program to run at all.
Tested with GNU Cash 2.4.10.

The library supports extracting the account tree, including all
transactions and splits. It does not support scheduled transactions,
price tables, and likely none but the most basic commodities. In
particular, writing of XML files is not supported.

[python]: http://www.python.org/
[gnu cash]: http://www.gnucash.org/

## Usage

The interface is intended to allow quickly writing reports using
Python. It reuses as many Python data structures as possible. Whenever
dates or times are used, the standard library `datetime` is used. All
account and transaction balances are represented as the standard
`Decimal` type.

The three main concepts in GNU Cash are accounts, transactions, and
splits. A transaction consists of a number of splits that specify from
which account or to which account commodities are transferred by this
transaction. All splits within a transaction together are balanced.

The main classes provided by `gnucashxml` mirror these concepts. A
`Book` is the main class containing everything else. A `Commodity` is
what is stored in an account, for example, Euros or Dollars. An
`Account` is part of a tree structure and contains splits. `Splits`
again are part of `Transactions`.

These classes all have a `slots` member, which is a simple dictionary
for extra information. GNU Cash information such as "hidden" are
recorded here.

## Example

```Python
import gnucashxml

book = gnucashxml.from_filename("test.gnucash")

income_total = 0
expense_total = 0
for account, subaccounts, splits in book.walk():
    if account.actype == 'INCOME':
        income_total += sum(split.value for split in account.splits)
    elif account.actype == 'EXPENSE':
        expense_total += sum(split.value for split in account.splits)

print "Total income : {:9.2f}".format(income_total * -1)
print "Total expense: {:9.2f}".format(expense_total)
```

