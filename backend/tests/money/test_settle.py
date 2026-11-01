from app.money.settle import Payment, settle


def apply(payments: list[Payment], balances: dict[str, int]) -> dict[str, int]:
    """Replay the payments and return what's left for each person."""
    left = dict(balances)
    for payment in payments:
        left[payment.sender] += payment.amount_paise
        left[payment.receiver] -= payment.amount_paise
    return left


def test_one_person_pays_another():
    assert settle({"arun": 30000, "ravi": -30000}) == [
        Payment(sender="ravi", receiver="arun", amount_paise=30000)
    ]


def test_nobody_pays_when_everyone_is_square():
    assert settle({"arun": 0, "ravi": 0}) == []


def test_two_people_pay_the_one_who_paid_the_bill():
    payments = settle({"priya": 48600, "arun": -24300, "ravi": -24300})

    assert sorted((p.sender, p.receiver, p.amount_paise) for p in payments) == [
        ("arun", "priya", 24300),
        ("ravi", "priya", 24300),
    ]


def test_everyone_ends_at_zero_with_few_payments():
    balances = {
        "arun": 52000,
        "priya": 18000,
        "ravi": -30000,
        "meena": -25000,
        "kavin": -15000,
        "divya": 0,
    }

    payments = settle(balances)

    assert all(amount == 0 for amount in apply(payments, balances).values())
    assert all(p.amount_paise > 0 for p in payments)
    assert len(payments) <= 4  # 5 people with a non-zero balance -> at most 4 payments
    assert all("divya" not in (p.sender, p.receiver) for p in payments)
