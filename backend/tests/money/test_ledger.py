from app.money.ledger import (
    Expense,
    Repayment,
    group_balances,
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
