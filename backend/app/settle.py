"""Turn everyone's balance into a short list of payments."""

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

    Each round, the person who owes the most pays the person who is owed the most.
    The payment is the smaller of the two amounts, so at least one of them is
    settled every round. That gives at most (people with a non-zero balance - 1)
    payments.

    Example:
        settle({"arun": 30000, "ravi": -30000})
        -> [Payment(sender="ravi", receiver="arun", amount_paise=30000)]
    """
    # Split people by sign. Amounts owed are stored as positive numbers.
    owes = {person: -balance for person, balance in balances.items() if balance < 0}
    owed = {person: balance for person, balance in balances.items() if balance > 0}

    payments = []
    while owes:
        sender = max(owes, key=owes.get)
        receiver = max(owed, key=owed.get)
        amount = min(owes[sender], owed[receiver])

        payments.append(Payment(sender=sender, receiver=receiver, amount_paise=amount))

        owes[sender] -= amount
        owed[receiver] -= amount
        if owes[sender] == 0:
            del owes[sender]
        if owed[receiver] == 0:
            del owed[receiver]

    return payments
