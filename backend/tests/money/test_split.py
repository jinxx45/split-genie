from app.money.split import FULL, HALF, Bill, Item, allocate, balances, compute_shares


def test_allocate_splits_evenly_when_possible():
    assert allocate(300, {"arun": FULL, "priya": FULL, "ravi": FULL}) == {
        "arun": 100,
        "priya": 100,
        "ravi": 100,
    }


def test_allocate_hands_out_leftover_paise_so_total_is_exact():
    # ₹1.00 between three people: 34 + 33 + 33, never 33.33 each
    shares = allocate(100, {"arun": FULL, "priya": FULL, "ravi": FULL})

    assert sum(shares.values()) == 100
    assert sorted(shares.values()) == [33, 33, 34]


def test_allocate_half_share_pays_half():
    # Four full shares and one half share: the half pays 1/9 of the item
    shares = allocate(
        90000,
        {"arun": FULL, "priya": HALF, "ravi": FULL, "meena": FULL, "kavin": FULL},
    )

    assert shares["priya"] == 10000
    assert shares["arun"] == 20000


def test_compute_shares_only_charges_people_who_had_the_item():
    bill = Bill(
        items=[
            Item("Biryani", 60000, {"arun": FULL, "ravi": FULL}),
            Item("Kingfisher", 40000, {"arun": FULL}),
        ]
    )

    assert compute_shares(bill) == {"arun": 70000, "ravi": 30000}


def test_compute_shares_splits_tax_in_proportion_to_what_people_ate():
    bill = Bill(
        items=[
            Item("Biryani", 60000, {"arun": FULL, "ravi": FULL}),
            Item("Kingfisher", 40000, {"arun": FULL}),
        ],
        tax_paise=5000,
        service_charge_paise=5000,
    )

    # Arun ate 70% of the food, so he pays 70% of the ₹100 charges
    assert compute_shares(bill) == {"arun": 77000, "ravi": 33000}


def test_compute_shares_always_sums_to_the_bill_total():
    bill = Bill(
        items=[
            Item("Paneer Tikka", 33333, {"a": FULL, "b": FULL, "c": HALF}),
            Item("Naan", 9999, {"a": FULL, "b": FULL, "c": FULL}),
            Item("Gulab Jamun", 12001, {"b": FULL, "c": FULL}),
        ],
        tax_paise=2777,
        service_charge_paise=5555,
    )

    total = 33333 + 9999 + 12001 + 2777 + 5555
    assert sum(compute_shares(bill).values()) == total


def test_balances_positive_means_owed_money():
    owed = {"arun": 70000, "ravi": 30000}
    paid = {"arun": 100000}

    assert balances(owed, paid) == {"arun": 30000, "ravi": -30000}
