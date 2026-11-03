"""A group's running tab: what everyone paid and owes across many expenses, and what's been paid
back. All amounts are integer paise."""

from dataclasses import dataclass

from app.money.split import allocate


@dataclass
class Expense:
    paid: dict[str, int]  # who paid, and how much
    owed: dict[str, int]  # each person's share; adds up to the same total as `paid`


@dataclass
class Repayment:
    """Money paid back between two members, e.g. Arun paid Priya ₹500 to settle up."""

    sender: str
    receiver: str
    amount_paise: int


def share_amount(total_paise: int, weights: dict[str, int]) -> dict[str, int]:
    """Split one amount between people by weight: equal weights for an equal split, or e.g.
    {"Arun": 2, "Priya": 1} for a bigger room. The shares always add up to exactly the total."""
    return allocate(total_paise, weights)


def group_balances(members: list[str], expenses: list[Expense], repayments: list[Repayment]) -> dict[str, int]:
    """Each member's position: positive means they get money back, negative means they owe.

    Paying for something raises your balance; your share of it lowers it. Paying someone back
    raises your balance and lowers theirs. The balances always add up to zero.
    """
    balance = dict.fromkeys(members, 0)
    for expense in expenses:
        for person, amount in expense.paid.items():
            balance[person] += amount
        for person, amount in expense.owed.items():
            balance[person] -= amount
    for repayment in repayments:
        balance[repayment.sender] += repayment.amount_paise
        balance[repayment.receiver] -= repayment.amount_paise
    return balance


def spent_by_person(members: list[str], expenses: list[Expense]) -> dict[str, int]:
    """What each member's own shares add up to: their real cost, e.g. "the trip cost you ₹6,820",
    whoever happened to pay."""
    spent = dict.fromkeys(members, 0)
    for expense in expenses:
        for person, amount in expense.owed.items():
            spent[person] += amount
    return spent
