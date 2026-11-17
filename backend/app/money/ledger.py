"""A group's running tab: what everyone paid and owes across many expenses, and what's been paid
back. All amounts are integer paise."""

from dataclasses import dataclass

from app.money.split import allocate


@dataclass
class Expense:
    paid: dict[str, int]  # who paid, and how much
    owed: dict[str, int]  # each person's share; adds up to the same total as `paid`
    id: str = ""  # only used to say which expenses a debt comes from


@dataclass
class Repayment:
    """Money paid back between two members, e.g. Arun paid Priya ₹500 to settle up."""

    sender: str
    receiver: str
    amount_paise: int
    id: str = ""


@dataclass
class DebtEntry:
    """One reason behind a debt: `ref` is an expense's or repayment's id. A positive amount adds
    to what the sender owes; a negative one takes it away (the receiver's part of something the
    sender paid, or money already paid back)."""

    ref: str
    amount_paise: int


@dataclass
class Debt:
    """What one member still owes another, with the expenses and repayments it comes from."""

    sender: str
    receiver: str
    amount_paise: int
    entries: list[DebtEntry]


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


def paid_by_person(members: list[str], expenses: list[Expense]) -> dict[str, int]:
    """What each member paid up front across all expenses, whoever it was for."""
    paid = dict.fromkeys(members, 0)
    for expense in expenses:
        for person, amount in expense.paid.items():
            paid[person] += amount
    return paid


def expense_debts(expense: Expense) -> dict[tuple[str, str], int]:
    """Who owes whom for one expense: (debtor, payer) -> paise.

    Each person owes their share to whoever paid. If several people paid, the share is split
    between the payers in proportion to what each paid. Your share of what you paid yourself
    is owed to nobody.
    """
    debts: dict[tuple[str, str], int] = {}
    for person, share in expense.owed.items():
        for payer, part in allocate(share, expense.paid).items():
            if payer != person and part:
                debts[(person, payer)] = debts.get((person, payer), 0) + part
    return debts


def pairwise_debts(expenses: list[Expense], repayments: list[Repayment]) -> list[Debt]:
    """Settling up pair by pair, the way Google Pay groups do.

    For every two members, add up what each owes the other across the expenses they shared,
    take off what's been paid back, and keep the difference. Unlike `settle()`, nobody is told
    to pay someone they never shared an expense with. It can mean a few more payments, but each
    one is easy to understand: "Arun pays you ₹264 for the dinner".
    """
    # Each pair is stored once, as (a, b) in name order: a positive total means a owes b.
    pairs: dict[tuple[str, str], list[DebtEntry]] = {}

    def add(debtor: str, creditor: str, ref: str, amount: int) -> None:
        first, second = sorted((debtor, creditor))
        sign = 1 if debtor == first else -1
        pairs.setdefault((first, second), []).append(DebtEntry(ref, sign * amount))

    for expense in expenses:
        for (debtor, payer), amount in expense_debts(expense).items():
            add(debtor, payer, expense.id, amount)
    for repayment in repayments:
        add(repayment.sender, repayment.receiver, repayment.id, -repayment.amount_paise)  # paid back

    debts = []
    for (first, second), entries in pairs.items():
        total = sum(entry.amount_paise for entry in entries)
        if total == 0:
            continue
        # Turn it round so the amounts read from the side of whoever owes.
        sender, receiver, sign = (first, second, 1) if total > 0 else (second, first, -1)
        flipped = [DebtEntry(entry.ref, sign * entry.amount_paise) for entry in entries]
        debts.append(Debt(sender, receiver, abs(total), flipped))
    return sorted(debts, key=lambda debt: (-debt.amount_paise, debt.sender, debt.receiver))
