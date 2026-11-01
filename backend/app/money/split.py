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


@dataclass
class ItemShare:
    """One person's part of one item."""

    item: str
    amount_paise: int
    shared_by: int  # how many people had the item
    half: bool  # whether this person had a half share


@dataclass
class PersonBreakdown:
    """How one person's total is made up."""

    items: list[ItemShare]
    charges_paise: int  # their part of tax and service charge, in proportion to what they had

    @property
    def total_paise(self) -> int:
        return sum(share.amount_paise for share in self.items) + self.charges_paise


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


def compute_breakdown(bill: Bill) -> dict[str, PersonBreakdown]:
    """Each person's part of every item they had, plus their part of the charges.

    Items are split by weight; tax and service charge are split in proportion
    to what each person had.
    """
    items_by_person: dict[str, list[ItemShare]] = {}
    for item in bill.items:
        for person, amount in allocate(item.amount_paise, item.weights).items():
            share = ItemShare(
                item=item.name,
                amount_paise=amount,
                shared_by=len(item.weights),
                half=item.weights[person] == HALF,
            )
            items_by_person.setdefault(person, []).append(share)

    subtotals = {
        person: sum(share.amount_paise for share in shares)
        for person, shares in items_by_person.items()
    }
    charges = allocate(bill.tax_paise + bill.service_charge_paise, subtotals)
    return {
        person: PersonBreakdown(items=shares, charges_paise=charges[person])
        for person, shares in items_by_person.items()
    }


def compute_shares(bill: Bill) -> dict[str, int]:
    """What each person owes in total, in paise. Taken from the breakdown, so the totals
    and the breakdown shown to users can never disagree."""
    return {person: part.total_paise for person, part in compute_breakdown(bill).items()}


def balances(owed: dict[str, int], paid: dict[str, int]) -> dict[str, int]:
    """Net position per person: positive means they are owed money, negative means they owe."""
    people = sorted(owed.keys() | paid.keys())  # sorted so results come out in the same order every run
    return {person: paid.get(person, 0) - owed.get(person, 0) for person in people}
