"""Turn everyone's balance into a short list of payments. This one is yours to write."""

from dataclasses import dataclass


@dataclass
class Payment:
    sender: str
    receiver: str
    amount_paise: int


def settle(balances: dict[str, int]) -> list[Payment]:
    """Return payments that bring every balance to zero.

    `balances` comes from `split.balances()`: positive means the person is owed
    money, negative means they owe. The balances always add up to zero.

    Example:
        settle({"arun": 30000, "ravi": -30000})
        -> [Payment(sender="ravi", receiver="arun", amount_paise=30000)]

    Rules (checked by tests/test_settle.py):
        - After the payments, everyone is at zero.
        - Every amount is positive.
        - At most (number of people with a non-zero balance - 1) payments.
        - People already at zero never appear.

    TODO: implement this. Run `uv run pytest tests/test_settle.py` until it passes.
    """
    raise NotImplementedError("settle() is yours to write — see the hints in this file")


# ---------------------------------------------------------------------------
# HINTS — read one at a time, only if you get stuck.
#
# Hint 1 (the idea):
#   Split people into two groups: those who owe (negative) and those who are owed
#   (positive). Repeatedly take the person who owes the MOST and the person who is
#   owed the MOST. The smaller of the two amounts is paid. At least one of them is
#   now at zero, so drop them. Repeat until nobody is left.
#
# Hint 2 (Python you'll need, with the TypeScript equivalent):
#   Filter a dict into a new dict:
#       owes = {p: -b for p, b in balances.items() if b < 0}
#       // TS: Object.fromEntries(Object.entries(balances).filter(([, b]) => b < 0).map(([p, b]) => [p, -b]))
#   Find the key with the largest value:
#       top = max(owes, key=owes.get)
#       // TS: Object.keys(owes).reduce((a, b) => owes[a] > owes[b] ? a : b)
#   Loop while a dict is not empty:     while owes:            // TS: while (Object.keys(owes).length)
#   Smaller of two numbers:             min(x, y)              // TS: Math.min(x, y)
#   Remove a key:                       del owes[top]          // TS: delete owes[top]
#   Add to a list:                      payments.append(...)   // TS: payments.push(...)
#   Build a Payment:                    Payment(sender="ravi", receiver="arun", amount_paise=30000)
#
# Hint 3 (structure):
#   payments = []
#   owes = ...
#   owed = ...
#   while owes:
#       sender = ...
#       receiver = ...
#       amount = ...
#       append the payment, subtract `amount` from both, delete whoever hit zero
#   return payments
# ---------------------------------------------------------------------------
