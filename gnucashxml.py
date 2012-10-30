# gnucashxml.py --- Parse GNU Cash XML files

# Copyright (C) 2012 Jorgen Schaefer <forcer@forcix.cx>

# Author: Jorgen Schaefer <forcer@forcix.cx>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import decimal
import gzip

from dateutil.parser import parse as parse_date
from xml.etree import ElementTree

__version__ = "1.0"

class Book(object):
    """
    A book is the main container for GNU Cash data.

    It doesn't really do anything at all by itself, except to have
    a reference to the accounts, transactions, and commodities.
    """
    def __init__(self, guid, transactions=None, root_account=None,
                 commodities=None, slots=None):
        self.guid = guid
        self.transactions = transactions or []
        self.root_account = root_account
        self.commodities = commodities or []
        self.slots = slots or {}

    def __repr__(self):
        return "<Book {}>".format(self.guid)

    def walk(self):
        return self.root_account.walk()

    def find_account(self, name):
        for account, children, splits in self.walk():
            if account.name == name:
                return account


class Commodity(object):
    """
    A commodity is something that's stored in GNU Cash accounts.

    Consists of a name (or id) and a space (namespace).
    """
    def __init__(self, name, space=None):
        self.name = name
        self.space = space

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Commodity {}:{}>".format(self.space, self.name)


class Account(object):
    """
    An account is part of a tree structure of accounts and contains splits.
    """
    def __init__(self, name, guid, actype, parent=None,
                 commodity=None, commodity_scu=None,
                 description=None, slots=None):
        self.name = name
        self.guid = guid
        self.actype = actype
        self.description = description
        self.parent = parent
        self.children = []
        self.commodity = commodity
        self.commodity_scu = commodity_scu
        self.splits = []
        self.slots = slots or {}

    def __repr__(self):
        return "<Account {}>".format(self.guid)

    def walk(self):
        """
        Generate splits in this account tree by walking the tree.

        For each account, it yields a 3-tuple (account, subaccounts, splits).

        You can modify the list of subaccounts, but should not modify
        the list of splits.
        """
        accounts = [self]
        while accounts:
            acc, accounts = accounts[0], accounts[1:]
            children = list(acc.children)
            yield (acc, children, acc.splits)
            accounts.extend(children)

    def get_all_splits(self):
        split_list = []
        for account, children, splits in self.walk():
            split_list.extend(splits)
        return sorted(split_list)


class Transaction(object):
    """
    A transaction is a balanced group of splits.
    """

    def __init__(self, guid=None, currency=None,
                 date=None, date_entered=None,
                 description=None, splits=None,
                 slots=None):
        self.guid = guid
        self.currency = currency
        self.date = date
        self.date_entered = date_entered
        self.description = description
        self.splits = splits or []
        self.slots = slots or {}

    def __repr__(self):
        return u"<Transaction {}>".format(self.guid)

    def __lt__(self, other):
        # For sorted() only
        if isinstance(other, Transaction):
            return self.date < other.date
        else:
            False


class Split(object):
    """
    A split is one entry in a transaction.
    """

    def __init__(self, guid=None, memo=None,
                 reconciled_state=None, reconcile_date=None, value=None,
                 quantity=None, account=None, transaction=None,
                 slots=None):
        self.guid = guid
        self.reconciled_state = reconciled_state
        self.reconcile_date = reconcile_date
        self.value = value
        self.quantity = quantity
        self.account = account
        self.transaction = transaction
        self.memo = memo
        self.slots = slots

    def __repr__(self):
        return "<Split {}>".format(self.guid)

    def __lt__(self, other):
        # For sorted() only
        if isinstance(other, Split):
            return self.transaction < other.transaction
        else:
            False



##################################################################
# XML file parsing

def from_filename(filename):
    """Parse a GNU Cash file and return a Book object."""
    return parse(gzip.open(filename, "rb"))


# Implemented:
# - gnc:book
#
# Not implemented:
# - gnc:count-data
#   - This seems to be primarily for integrity checks?
def parse(fobj):
    """Parse GNU Cash XML data from a file object and return a Book object."""
    tree = ElementTree.parse(fobj)
    root = tree.getroot()
    if root.tag != 'gnc-v2':
        raise ValueError("File stream was not a valid GNU Cash v2 XML file")
    return _book_from_tree(root.find("{http://www.gnucash.org/XML/gnc}book"))


# Implemented:
# - book:id
# - book:slots
# - gnc:commodity
# - gnc:account
# - gnc:transaction
#
# Not implemented:
# - gnc:schedxaction
# - gnc:template-transactions
# - gnc:count-data
#   - This seems to be primarily for integrity checks?
def _book_from_tree(tree):
    guid = tree.find('{http://www.gnucash.org/XML/book}id').text

    commodities = []
    commoditydict = {}
    for child in tree.findall('{http://www.gnucash.org/XML/gnc}commodity'):
        comm = _commodity_from_tree(child)
        commodities.append(comm)
        commoditydict[(comm.space, comm.name)] = comm

    root_account = None
    accountdict = {}
    parentdict = {}
    for child in tree.findall('{http://www.gnucash.org/XML/gnc}account'):
        parent_guid, acc = _account_from_tree(child, commoditydict)
        if acc.actype == 'ROOT':
            root_account = acc
        accountdict[acc.guid] = acc
        parentdict[acc.guid] = parent_guid
    for acc in accountdict.values():
        if acc.parent is None and acc.actype != 'ROOT':
            parent = accountdict[parentdict[acc.guid]]
            acc.parent = parent
            parent.children.append(acc)

    transactions = []
    for child in tree.findall('{http://www.gnucash.org/XML/gnc}'
                              'transaction'):
        transactions.append(_transaction_from_tree(child,
                                                   accountdict,
                                                   commoditydict))

    slots = _slots_from_tree(
        tree.find('{http://www.gnucash.org/XML/book}slots'))
    return Book(guid=guid,
                transactions=transactions,
                root_account=root_account,
                commodities=commodities,
                slots=slots)


# Implemented:
# - cmdty:id
# - cmdty:space
#
# Not implemented:
# - cmdty:get_quotes => unknown, empty, optional
# - cmdty:quote_tz => unknown, empty, optional
# - cmdty:source => text, optional, e.g. "currency"
# - cmdty:name => optional, e.g. "template"
# - cmdty:xcode => optional, e.g. "template"
# - cmdty:fraction => optional, e.g. "1"
def _commodity_from_tree(tree):
    name = tree.find('{http://www.gnucash.org/XML/cmdty}id').text
    space = tree.find('{http://www.gnucash.org/XML/cmdty}space').text
    return Commodity(name=name, space=space)


# Implemented:
# - act:name
# - act:id
# - act:type
# - act:description
# - act:commodity
# - act:commodity-scu
# - act:parent
# - act:slots
def _account_from_tree(tree, commoditydict):
    act = '{http://www.gnucash.org/XML/act}'
    cmdty = '{http://www.gnucash.org/XML/cmdty}'

    name = tree.find(act + 'name').text
    guid = tree.find(act + 'id').text
    actype = tree.find(act + 'type').text
    description = tree.find(act + "description")
    if description is not None:
        description = description.text
    slots = _slots_from_tree(tree.find(act + 'slots'))
    if actype == 'ROOT':
        parent_guid = None
        commodity = None
        commodity_scu = None
    else:
        parent_guid = tree.find(act + 'parent').text
        commodity_space = tree.find(act + 'commodity/' +
                                    cmdty + 'space').text
        commodity_name = tree.find(act + 'commodity/' +
                                   cmdty + 'id').text
        commodity_scu = tree.find(act + 'commodity-scu').text
        commodity = commoditydict[(commodity_space, commodity_name)]
    return parent_guid, Account(name=name,
                                description=description,
                                guid=guid,
                                actype=actype,
                                commodity=commodity,
                                commodity_scu=commodity_scu,
                                slots=slots)

# Implemented:
# - trn:id
# - trn:currency
# - trn:date-posted
# - trn:date-entered
# - trn:description
# - trn:splits / trn:split
# - trn:slots
def _transaction_from_tree(tree, accountdict, commoditydict):
    trn = '{http://www.gnucash.org/XML/trn}'
    cmdty = '{http://www.gnucash.org/XML/cmdty}'
    ts = '{http://www.gnucash.org/XML/ts}'
    split = '{http://www.gnucash.org/XML/split}'

    guid = tree.find(trn + "id").text
    currency_space = tree.find(trn + "currency/" +
                               cmdty + "space").text
    currency_name = tree.find(trn + "currency/" +
                               cmdty + "id").text
    currency = commoditydict[(currency_space, currency_name)]
    date = parse_date(tree.find(trn + "date-posted/" +
                                       ts + "date").text)
    date_entered = parse_date(tree.find(trn + "date-entered/" +
                                        ts + "date").text)
    description = tree.find(trn + "description").text
    slots = _slots_from_tree(tree.find(trn + "slots"))
    transaction = Transaction(guid=guid,
                              currency=currency,
                              date=date,
                              date_entered=date_entered,
                              description=description,
                              slots=slots)

    for subtree in tree.findall(trn + "splits/" + trn + "split"):
        split = _split_from_tree(subtree, accountdict, transaction)
        transaction.splits.append(split)

    return transaction


# Implemented:
# - split:id
# - split:memo
# - split:reconciled-state
# - split:reconcile-date
# - split:value
# - split:quantity
# - split:account
# - split:slots
def _split_from_tree(tree, accountdict, transaction):
    split = '{http://www.gnucash.org/XML/split}'
    ts = "{http://www.gnucash.org/XML/ts}"

    guid = tree.find(split + "id").text
    memo = tree.find(split + "memo")
    if memo is not None:
        memo = memo.text
    reconciled_state = tree.find(split + "reconciled-state").text
    reconcile_date = tree.find(split + "reconcile-date/" + ts + "date")
    if reconcile_date is not None:
        reconcile_date = parse_date(reconcile_date.text)
    value = _parse_number(tree.find(split + "value").text)
    quantity = _parse_number(tree.find(split + "quantity").text)
    account_guid = tree.find(split + "account").text
    account = accountdict[account_guid]
    slots = _slots_from_tree(tree.find(split + "slots"))
    split = Split(guid=guid,
                  memo=memo,
                  reconciled_state=reconciled_state,
                  reconcile_date=reconcile_date,
                  value=value,
                  quantity=quantity,
                  account=account,
                  transaction=transaction,
                  slots=slots)
    account.splits.append(split)
    return split


# Implemented:
# - slot
# - slot:key
# - slot:value
# - ts:date
# - gdate
def _slots_from_tree(tree):
    if tree is None:
        return {}
    slot = "{http://www.gnucash.org/XML/slot}"
    ts = "{http://www.gnucash.org/XML/ts}"
    slots = {}
    for elt in tree.findall("slot"):
        key = elt.find(slot + "key").text
        value = elt.find(slot + "value")
        type_ = value.get('type', 'string')
        if type_ == 'integer':
            slots[key] = long(value.text)
        elif type_ == 'numeric':
            slots[key] = _parse_number(value.text)
        elif type_ in ('string', 'guid'):
            slots[key] = value.text
        elif type_ == 'gdate':
            slots[key] = parse_date(value.find("gdate").text)
        elif type_ == 'timespec':
            slots[key] = parse_date(value.find(ts + "date").text)
        elif type_ == 'frame':
            slots[key] = _slots_from_tree(value)
        else:
            raise RuntimeError("Unknown slot type {}".format(type_))
    return slots

def _parse_number(numstring):
    num, denum = numstring.split("/")
    return decimal.Decimal(num) / decimal.Decimal(denum)
