"""Deterministic bill-splitting maths. All money is integer paise (₹1 = 100 paise)."""

from dataclasses import dataclass

# Share weights: a half share costs half as much as a full share.
FULL = 2
HALF = 1


@dataclass
class Item:
    name: str
    amount_paise: int
    weights: dict[str, int]  # person -> FULL or HALF; people not listed didn't have it


@dataclass
class Bill:
    items: list[Item]
    tax_paise: int = 0
    service_charge_paise: int = 0


def allocate(total: int, weights: dict[str, int]) -> dict[str, int]:
    """Split `total` paise in proportion to `weights`, summing exactly to `total`.

    Each person first gets the rounded-down amount; the leftover paise go one each
    to the people with the largest remainders (ties broken by name, so it is repeatable).
    """
    weight_sum = sum(weights.values())
    shares = {person: total * w // weight_sum for person, w in weights.items()}
    leftover = total - sum(shares.values())
    by_remainder = sorted(weights, key=lambda p: (-(total * weights[p] % weight_sum), p))
    for person in by_remainder[:leftover]:
        shares[person] += 1
    return shares


def compute_shares(bill: Bill) -> dict[str, int]:
    """What each person owes in total, in paise.

    Items are split by weight; tax and service charge are split in proportion
    to what each person ate.
    """
    subtotals: dict[str, int] = {}
    for item in bill.items:
        for person, amount in allocate(item.amount_paise, item.weights).items():
            subtotals[person] = subtotals.get(person, 0) + amount

    charges = allocate(bill.tax_paise + bill.service_charge_paise, subtotals)
    return {person: subtotals[person] + charges[person] for person in subtotals}


def balances(owed: dict[str, int], paid: dict[str, int]) -> dict[str, int]:
    """Net position per person: positive means they are owed money, negative means they owe."""
    people = owed.keys() | paid.keys()
    return {person: paid.get(person, 0) - owed.get(person, 0) for person in people}
