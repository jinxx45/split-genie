from app.money.ledger import (
    Debt,
    DebtEntry,
    Expense,
    Repayment,
    expense_debts,
    group_balances,
    pairwise_debts,
    share_amount,
    spent_by_person,
)
from app.money.settle import Payment, settle

MEMBERS = ["Arun", "Priya", "Ravi"]


def test_shares_are_equal_or_weighted_and_add_up_exactly():
    assert share_amount(100000, {"Arun": 1, "Priya": 1, "Ravi": 1}) == {"Arun": 33334, "Priya": 33333, "Ravi": 33333}
    assert share_amount(3000000, {"Arun": 2, "Priya": 1, "Ravi": 1}) == {"Arun": 1500000, "Priya": 750000, "Ravi": 750000}


def test_balances_add_paid_and_subtract_shares():
    dinner = Expense(paid={"Priya": 90000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000})
    cab = Expense(paid={"Arun": 30000}, owed={"Arun": 10000, "Priya": 10000, "Ravi": 10000})

    balances = group_balances(MEMBERS, [dinner, cab], [])

    assert balances == {"Arun": -10000, "Priya": 50000, "Ravi": -40000}
    assert sum(balances.values()) == 0


def test_repayments_move_balances_towards_zero():
    dinner = Expense(paid={"Priya": 90000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000})

    balances = group_balances(MEMBERS, [dinner], [Repayment("Arun", "Priya", 30000)])

    assert balances == {"Arun": 0, "Priya": 30000, "Ravi": -30000}


def test_settling_the_balances_clears_everyone():
    dinner = Expense(paid={"Priya": 90000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000})
    cab = Expense(paid={"Arun": 30000}, owed={"Arun": 10000, "Priya": 10000, "Ravi": 10000})

    payments = settle(group_balances(MEMBERS, [dinner, cab], []))

    assert sorted(payments, key=lambda p: p.sender) == [Payment("Arun", "Priya", 10000), Payment("Ravi", "Priya", 40000)]


def test_spent_is_each_persons_own_share_whoever_paid():
    dinner = Expense(paid={"Priya": 90000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000})
    cab = Expense(paid={"Arun": 30000}, owed={"Arun": 20000, "Ravi": 10000})

    assert spent_by_person(MEMBERS, [dinner, cab]) == {"Arun": 50000, "Priya": 30000, "Ravi": 40000}


# --- Pairwise settling (Google Pay style) ---


def owed(debts: list[Debt]) -> list[tuple[str, str, int]]:
    return [(debt.sender, debt.receiver, debt.amount_paise) for debt in debts]


def test_each_pair_settles_on_its_own_instead_of_being_rerouted():
    # Pragadeesh paid dinner with Sushanth; Arun paid a cab for Pragadeesh. Pragadeesh is even
    # overall, so the fewest-payments method skips him: "Sushanth pays Arun". Pair by pair,
    # Sushanth pays Pragadeesh for the dinner and Pragadeesh pays Arun for the cab.
    dinner = Expense(paid={"Pragadeesh": 60000}, owed={"Pragadeesh": 30000, "Sushanth": 30000}, id="dinner")
    cab = Expense(paid={"Arun": 30000}, owed={"Pragadeesh": 30000}, id="cab")
    members = ["Arun", "Pragadeesh", "Sushanth"]

    assert settle(group_balances(members, [dinner, cab], [])) == [Payment("Sushanth", "Arun", 30000)]
    assert owed(pairwise_debts([dinner, cab], [])) == [
        ("Pragadeesh", "Arun", 30000),
        ("Sushanth", "Pragadeesh", 30000),
    ]


def test_debts_between_two_people_are_netted():
    dinner = Expense(paid={"Priya": 90000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000}, id="dinner")
    cab = Expense(paid={"Arun": 30000}, owed={"Arun": 10000, "Priya": 10000, "Ravi": 10000}, id="cab")

    [ravi_priya, arun_priya, ravi_arun] = pairwise_debts([dinner, cab], [])  # biggest first

    # Arun owes Priya 300 for dinner, Priya owes Arun 100 for the cab: Arun pays 200.
    assert arun_priya == Debt("Arun", "Priya", 20000, [DebtEntry("dinner", 30000), DebtEntry("cab", -10000)])
    assert owed([ravi_priya, ravi_arun]) == [("Ravi", "Priya", 30000), ("Ravi", "Arun", 10000)]


def test_pairwise_debts_match_everyones_balance():
    dinner = Expense(paid={"Priya": 90000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000}, id="dinner")
    cab = Expense(paid={"Arun": 30000}, owed={"Arun": 10000, "Priya": 10000, "Ravi": 10000}, id="cab")
    back = Repayment("Ravi", "Priya", 5000, id="back")

    net = dict.fromkeys(MEMBERS, 0)
    for debt in pairwise_debts([dinner, cab], [back]):
        net[debt.sender] -= debt.amount_paise
        net[debt.receiver] += debt.amount_paise

    assert net == group_balances(MEMBERS, [dinner, cab], [back])


def test_repayments_reduce_a_debt_and_paying_too_much_turns_it_round():
    dinner = Expense(paid={"Priya": 60000}, owed={"Arun": 30000, "Priya": 30000}, id="dinner")

    assert pairwise_debts([dinner], [Repayment("Arun", "Priya", 30000, id="r1")]) == []
    [debt] = pairwise_debts([dinner], [Repayment("Arun", "Priya", 40000, id="r1")])
    assert (debt.sender, debt.receiver, debt.amount_paise) == ("Priya", "Arun", 10000)
    assert debt.entries == [DebtEntry("dinner", -30000), DebtEntry("r1", 40000)]


def test_with_two_payers_a_share_is_owed_to_both_in_proportion():
    # Priya paid 600 and Arun 300 of a 900 bill shared by three.
    bill = Expense(paid={"Priya": 60000, "Arun": 30000}, owed={"Arun": 30000, "Priya": 30000, "Ravi": 30000})

    assert expense_debts(bill) == {("Arun", "Priya"): 20000, ("Priya", "Arun"): 10000, ("Ravi", "Priya"): 20000,
                                   ("Ravi", "Arun"): 10000}
    assert owed(pairwise_debts([bill], [])) == [("Ravi", "Priya", 20000), ("Arun", "Priya", 10000), ("Ravi", "Arun", 10000)]
