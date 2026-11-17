"""Group endpoints: Friends, Trip and Flatmates groups with a running tab.

Creating a group needs Google sign-in, so it belongs to an account. Members get in through the
group's link (its unguessable id) and pick their name; they can add expenses and record
repayments without signing in. All money maths is in app/money.
"""

import calendar
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.accounts import User
from app.api.auth import current_user, require_user
from app.api.db import get_database
from app.api.group_store import (
    ExpenseRow,
    Group,
    GroupKind,
    GroupStore,
    RecurringRow,
    RepaymentRow,
)
from app.api.schemas import (
    MAX_NAME_LENGTH,
    MAX_PEOPLE,
    MAX_SPLIT_NAME_LENGTH,
    UPI_ID_PATTERN,
    clean_people,
    reject,
)
from app.money.ledger import (
    Expense,
    Repayment,
    expense_debts,
    group_balances,
    paid_by_person,
    pairwise_debts,
    share_amount,
    spent_by_person,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])

MAX_EXPENSE_PAISE = 100_000_000  # ₹10,00,000: room for rent, flights and hotel bookings
MAX_WEIGHT = 99
IST = timezone(timedelta(hours=5, minutes=30))  # months and due days follow Indian time


@lru_cache
def get_groups() -> GroupStore:
    """Groups and their tabs. Tests replace this with a temporary one."""
    return GroupStore(get_database())


# --- What the browser sends ---

Name = Annotated[str, Field(min_length=1, max_length=MAX_SPLIT_NAME_LENGTH)]
Member = Annotated[str, Field(min_length=1, max_length=MAX_NAME_LENGTH)]
Weights = dict[str, Annotated[int, Field(ge=1, le=MAX_WEIGHT)]]


class GroupIn(BaseModel):
    kind: GroupKind
    name: Name
    members: list[str]
    me: Member  # which member the creator is
    start_date: date | None = None  # trips only
    end_date: date | None = None


class JoinIn(BaseModel):
    member: Member


class AddMemberIn(BaseModel):
    name: Member


class QuickExpenseIn(BaseModel):
    title: Name
    amount_paise: int = Field(ge=1, le=MAX_EXPENSE_PAISE)
    paid_by: Member
    weights: Weights = Field(min_length=1)  # who shares it: 1 each for equal, or e.g. 2 for a bigger room
    added_by: Member


class RepaymentIn(BaseModel):
    sender: Member
    receiver: Member
    amount_paise: int = Field(ge=1, le=MAX_EXPENSE_PAISE)
    by: Member  # who is recording it: must be the sender or the receiver
    expense_id: str | None = None  # paying for one expense, e.g. your part of the dinner


class UpiIn(BaseModel):
    member: Member
    upi_id: str = Field(pattern=UPI_ID_PATTERN)


class CloseIn(BaseModel):
    closed: bool


class RecurringIn(BaseModel):
    title: Name
    amount_paise: int | None = Field(default=None, ge=1, le=MAX_EXPENSE_PAISE)  # None: changes each month
    paid_by: Member
    weights: Weights = Field(min_length=1)
    day_of_month: int = Field(ge=1, le=28)  # 28 at most, so every month has the day


class MonthAmountIn(BaseModel):
    amount_paise: int = Field(ge=1, le=MAX_EXPENSE_PAISE)
    by: Member


# --- Endpoints ---


@router.post("", status_code=201)
def create_group(body: GroupIn, user: User = Depends(require_user), groups: GroupStore = Depends(get_groups)) -> dict:
    members = clean_people(body.members)
    if body.me not in members:
        raise reject("Add yourself to the group's members.")
    start, end = None, None
    if body.kind == "trip" and body.start_date and body.end_date:
        if body.end_date < body.start_date:
            raise reject("The trip can't end before it starts.")
        start, end = body.start_date.isoformat(), body.end_date.isoformat()
    group_id = groups.create(body.kind, " ".join(body.name.split()), members, user.id, start, end)
    groups.join(group_id, user.id, body.me)
    return describe_group(groups, groups.group(group_id), user)


@router.get("")
def my_groups(user: User = Depends(require_user), groups: GroupStore = Depends(get_groups)) -> dict:
    """The signed-in user's groups, with where they stand in each."""
    result = []
    for group, member in groups.groups_of(user.id):
        balances = balances_of(groups, group)
        result.append(
            {"id": group.id, "kind": group.kind, "name": group.name, "member": member,
             "balance_paise": balances.get(member, 0), "closed": group.closed_at is not None}
        )
    return {"groups": result}


@router.get("/{group_id}")
def get_group(group_id: str, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)) -> dict:
    return describe_group(groups, load(groups, group_id), user)


@router.get("/{group_id}/wrapped")
def get_wrapped(group_id: str, groups: GroupStore = Depends(get_groups)) -> dict:
    """The group's highlights for its shareable "Wrapped" card."""
    return describe_wrapped(groups, load(groups, group_id))


@router.post("/{group_id}/join")
def join_group(
    group_id: str, body: JoinIn, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    """A member picked their name. If they're signed in, the group shows under their groups."""
    group = load(groups, group_id)
    check_member(group, body.member)
    if user:
        groups.join(group_id, user.id, body.member)
    return describe_group(groups, group, user)


@router.post("/{group_id}/members", status_code=201)
def add_member(
    group_id: str, body: AddMemberIn, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    """Someone already in the group adds a friend who wasn't there at the start."""
    group = load(groups, group_id)
    name = " ".join(body.name.split())
    if not name:
        raise reject("Give them a name.")
    if any(name.lower() == existing.lower() for existing in group.members):
        raise reject(f"{name} is already in this group.")
    if len(group.members) >= MAX_PEOPLE:
        raise reject(f"A group can have at most {MAX_PEOPLE} people.")
    groups.add_member(group_id, name)
    return describe_group(groups, load(groups, group_id), user)


@router.post("/{group_id}/expenses", status_code=201)
def add_quick_expense(
    group_id: str, body: QuickExpenseIn, user: User | None = Depends(current_user),
    groups: GroupStore = Depends(get_groups),
) -> dict:
    group = load_open(groups, group_id)
    check_member(group, body.paid_by, body.added_by, *body.weights)
    owed = share_amount(body.amount_paise, body.weights)
    groups.add_expense(group_id, " ".join(body.title.split()), "quick", {body.paid_by: body.amount_paise}, owed, body.added_by)
    return describe_group(groups, group, user)


@router.put("/{group_id}/expenses/{expense_id}")
def edit_expense(
    group_id: str, expense_id: str, body: QuickExpenseIn, user: User | None = Depends(current_user),
    groups: GroupStore = Depends(get_groups),
) -> dict:
    """Correct an expense: its name, amount, who paid and who shares it. The shares are worked
    out again from the new amount. A scanned bill keeps its item-by-item split, so it can't be
    edited here."""
    group = load_open(groups, group_id)
    expense = next((e for e in groups.expenses(group_id) if e.id == expense_id), None)
    if expense is None:
        raise HTTPException(status_code=404, detail="That expense isn't in this group.")
    if expense.source == "bill":
        raise reject("A scanned bill can't be edited here. Remove it and scan it again.")
    check_member(group, body.paid_by, body.added_by, *body.weights)
    owed = share_amount(body.amount_paise, body.weights)
    groups.update_expense(group_id, expense_id, " ".join(body.title.split()), {body.paid_by: body.amount_paise}, owed)
    return describe_group(groups, group, user)


@router.delete("/{group_id}/expenses/{expense_id}")
def delete_expense(
    group_id: str, expense_id: str, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    group = load_open(groups, group_id)
    if not groups.delete_expense(group_id, expense_id):
        raise HTTPException(status_code=404, detail="That expense isn't in this group.")
    return describe_group(groups, group, user)


@router.post("/{group_id}/repayments", status_code=201)
def add_repayment(
    group_id: str, body: RepaymentIn, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    group = load(groups, group_id)  # allowed after a trip ends: that's when people settle up
    check_member(group, body.sender, body.receiver, body.by)
    if body.sender == body.receiver:
        raise reject("Someone can't pay themselves.")
    if body.by not in (body.sender, body.receiver):
        raise HTTPException(status_code=403, detail="You can only mark payments you made or received.")
    if body.expense_id is not None:
        expense = next((e for e in groups.expenses(group_id) if e.id == body.expense_id), None)
        if expense is None:
            raise HTTPException(status_code=404, detail="That expense isn't in this group.")
        if (body.sender, body.receiver) not in expense_debts(to_ledger([expense])[0]):
            raise reject(f"{body.sender} doesn't owe {body.receiver} for {expense.title}.")
    groups.add_repayment(group_id, body.sender, body.receiver, body.amount_paise, body.by, body.expense_id)
    return describe_group(groups, group, user)


@router.delete("/{group_id}/repayments/{repayment_id}")
def delete_repayment(
    group_id: str, repayment_id: str, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    group = load(groups, group_id)
    if not groups.delete_repayment(group_id, repayment_id):
        raise HTTPException(status_code=404, detail="That payment isn't in this group.")
    return describe_group(groups, group, user)


@router.put("/{group_id}/upi")
def set_upi_id(
    group_id: str, body: UpiIn, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    group = load(groups, group_id)
    check_member(group, body.member)
    groups.set_upi_id(group_id, body.member, body.upi_id)
    return describe_group(groups, load(groups, group_id), user)


@router.put("/{group_id}/closed")
def set_closed(
    group_id: str, body: CloseIn, user: User = Depends(require_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    """End a trip (no new expenses; everyone settles up), or reopen it. Only its creator can."""
    group = load(groups, group_id)
    if group.kind != "trip":
        raise reject("Only trips can be ended.")
    if group.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the person who created the trip can end it.")
    groups.set_closed(group_id, body.closed)
    return describe_group(groups, load(groups, group_id), user)


@router.post("/{group_id}/recurring", status_code=201)
def add_recurring(
    group_id: str, body: RecurringIn, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    group = load(groups, group_id)
    if group.kind != "flat":
        raise reject("Monthly bills are for flatmates' groups.")
    check_member(group, body.paid_by, *body.weights)
    title = " ".join(body.title.split())
    groups.add_recurring(group_id, title, body.amount_paise, body.paid_by, body.weights, body.day_of_month, this_month())
    return describe_group(groups, group, user)


@router.delete("/{group_id}/recurring/{recurring_id}")
def stop_recurring(
    group_id: str, recurring_id: str, user: User | None = Depends(current_user), groups: GroupStore = Depends(get_groups)
) -> dict:
    """Stop a monthly bill from now on; months already added stay."""
    group = load(groups, group_id)
    if not groups.stop_recurring(group_id, recurring_id):
        raise HTTPException(status_code=404, detail="That monthly bill isn't in this group.")
    return describe_group(groups, group, user)


@router.put("/{group_id}/recurring/{recurring_id}/months/{month}")
def enter_month_amount(
    group_id: str, recurring_id: str, month: str, body: MonthAmountIn, user: User | None = Depends(current_user),
    groups: GroupStore = Depends(get_groups),
) -> dict:
    """Enter this month's amount for a bill that changes every month (electricity)."""
    group = load(groups, group_id)
    check_member(group, body.by)
    bill = next((item for item in groups.recurring(group_id) if item.id == recurring_id), None)
    if bill is None or bill.amount_paise is not None:
        raise HTTPException(status_code=404, detail="That bill doesn't need a monthly amount.")
    if month not in due_months(bill, today_ist()):
        raise reject("That month isn't due for this bill.")
    add_month(groups, group_id, bill, month, body.amount_paise, body.by)
    return describe_group(groups, group, user)


# --- Helpers ---


def load(groups: GroupStore, group_id: str) -> Group:
    group = groups.group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    return group


def load_open(groups: GroupStore, group_id: str) -> Group:
    """A group that still takes expenses (an ended trip doesn't)."""
    group = load(groups, group_id)
    if group.closed_at:
        raise HTTPException(status_code=409, detail="This trip has ended. Reopen it to add expenses.")
    return group


def check_member(group: Group, *names: str) -> None:
    unknown = sorted({name for name in names if name not in group.members})
    if unknown:
        raise reject(f"Not in this group: {', '.join(unknown)}.")


def today_ist() -> date:
    return datetime.now(IST).date()


def this_month() -> str:
    return today_ist().strftime("%Y-%m")


def due_months(bill: RecurringRow, today: date) -> list[str]:
    """Every month from the bill's first month up to now in which its day has come."""
    months = []
    year, month = map(int, bill.starts.split("-"))
    while (year, month) <= (today.year, today.month):
        if (year, month) < (today.year, today.month) or today.day >= bill.day_of_month:
            months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def month_label(month: str) -> str:
    """"2026-11" -> "Nov 2026"."""
    year, number = month.split("-")
    return f"{calendar.month_abbr[int(number)]} {year}"


def add_month(groups: GroupStore, group_id: str, bill: RecurringRow, month: str, amount: int, added_by: str) -> None:
    groups.add_expense(
        group_id, f"{bill.title}, {month_label(month)}", "recurring", {bill.paid_by: amount},
        share_amount(amount, bill.weights), added_by, recurring_id=bill.id, month=month,
    )


def add_due_fixed_bills(groups: GroupStore, group: Group, expenses: list[ExpenseRow]) -> bool:
    """Add every month of every fixed monthly bill (rent) that has come due and isn't in the tab
    yet. Safe to repeat: each month is added once. Returns whether anything was added."""
    added = {(expense.recurring_id, expense.month) for expense in expenses}
    changed = False
    for bill in groups.recurring(group.id):
        if bill.amount_paise is None:
            continue
        for month in due_months(bill, today_ist()):
            if (bill.id, month) not in added:
                add_month(groups, group.id, bill, month, bill.amount_paise, "")
                changed = True
    return changed


def to_ledger(expenses: list[ExpenseRow]) -> list[Expense]:
    return [Expense(paid=expense.paid, owed=expense.owed, id=expense.id) for expense in expenses]


def to_repayments(rows: list[RepaymentRow]) -> list[Repayment]:
    return [Repayment(r.sender, r.receiver, r.amount_paise, id=r.id) for r in rows]


def balances_of(groups: GroupStore, group: Group) -> dict[str, int]:
    return group_balances(group.members, to_ledger(groups.expenses(group.id)), to_repayments(groups.repayments(group.id)))


def expense_month(expense: ExpenseRow) -> str:
    """The month an expense belongs to: a monthly bill's own month, otherwise when it was added
    (in Indian time)."""
    if expense.month:
        return expense.month
    added = datetime.fromisoformat(expense.created_at.replace("Z", "+00:00")).astimezone(IST)
    return added.strftime("%Y-%m")


def expense_day(expense: ExpenseRow) -> date:
    """The day an expense was added, in Indian time."""
    return datetime.fromisoformat(expense.created_at.replace("Z", "+00:00")).astimezone(IST).date()


def describe_wrapped(groups: GroupStore, group: Group) -> dict:
    """The highlights of a group's spending, for one shareable picture: the total, what it came
    to per person and per day, the biggest expense, who fronted the most, and the busiest day.

    Only facts that are true of the data are included: a highlight that would be a tie or
    meaningless (the "top spender" when everyone's share is equal) is left out as None.
    """
    expenses = groups.expenses(group.id)
    if not expenses:
        raise reject("Nothing to wrap up yet. Add an expense first.")
    ledger = to_ledger(expenses)
    total = sum(sum(expense.paid.values()) for expense in expenses)

    # How long it ran: the trip's own dates, otherwise from the first expense to the last.
    spent_on = [expense_day(expense) for expense in expenses]
    first = date.fromisoformat(group.start_date) if group.start_date else min(spent_on)
    last = date.fromisoformat(group.end_date) if group.end_date else max(spent_on)
    days = max((last - first).days + 1, 1)

    biggest = max(expenses, key=lambda expense: sum(expense.paid.values()))
    paid = paid_by_person(group.members, ledger)
    banker = max(group.members, key=lambda person: paid[person])
    spent = spent_by_person(group.members, ledger)
    top_spender = max(group.members, key=lambda person: spent[person])
    by_day: dict[date, int] = {}
    for expense, day in zip(expenses, spent_on, strict=True):
        by_day[day] = by_day.get(day, 0) + sum(expense.paid.values())
    busiest = max(by_day, key=lambda day: by_day[day])
    debts_left = len(pairwise_debts(ledger, to_repayments(groups.repayments(group.id))))

    return {
        "name": group.name,
        "kind": group.kind,
        "people": len(group.members),
        "start_date": first.isoformat(),
        "end_date": last.isoformat(),
        "days": days,
        "total_paise": total,
        "per_person_paise": total // len(group.members),  # rounded down: shown as "about"
        "per_day_paise": total // days,
        "expenses": len(expenses),
        "biggest": {"title": biggest.title, "total_paise": sum(biggest.paid.values())},
        "banker": {"person": banker, "paid_paise": paid[banker]},
        # Left out when everyone's share is the same: there is no top spender then.
        "top_spender": (
            {"person": top_spender, "spent_paise": spent[top_spender]} if len(set(spent.values())) > 1 else None
        ),
        # Left out when everything was on one day.
        "busiest_day": {"date": busiest.isoformat(), "total_paise": by_day[busiest]} if len(by_day) > 1 else None,
        "payments_left": debts_left,
    }


def describe_group(groups: GroupStore, group: Group, user: User | None) -> dict:
    """The group as the app shows it: balances, who owes whom, and everything in its tab."""
    expenses = groups.expenses(group.id)
    if group.kind == "flat" and add_due_fixed_bills(groups, group, expenses):
        expenses = groups.expenses(group.id)
    repayment_rows = groups.repayments(group.id)
    repayments = to_repayments(repayment_rows)
    ledger = to_ledger(expenses)
    balances = group_balances(group.members, ledger, repayments)
    spent = spent_by_person(group.members, ledger)

    activity = [
        {
            "type": "expense", "id": e.id, "title": e.title, "source": e.source,
            "total_paise": sum(e.paid.values()), "paid": e.paid, "owed": e.owed,
            "added_by": e.added_by, "created_at": e.created_at, "split_id": e.split_id,
            # Who owes whom for this expense alone, so each person can pay their part of it.
            "owes": [
                {"sender": sender, "receiver": receiver, "amount_paise": amount}
                for (sender, receiver), amount in expense_debts(entry).items()
            ],
        }
        for e, entry in zip(expenses, ledger, strict=True)
    ] + [
        {
            "type": "repayment", "id": r.id, "sender": r.sender, "receiver": r.receiver,
            "amount_paise": r.amount_paise, "marked_by": r.marked_by, "created_at": r.created_at,
            "expense_id": r.expense_id,
        }
        for r in repayment_rows
    ]
    activity.sort(key=lambda entry: entry["created_at"], reverse=True)

    described = {
        "id": group.id,
        "kind": group.kind,
        "name": group.name,
        "members": group.members,
        "upi_ids": group.upi_ids,
        "start_date": group.start_date,
        "end_date": group.end_date,
        "closed": group.closed_at is not None,
        "is_owner": user is not None and user.id == group.owner_id,
        "balances": balances,
        # Pair by pair, like Google Pay: who still owes whom, and the expenses it comes from.
        "debts": [
            {
                "sender": debt.sender, "receiver": debt.receiver, "amount_paise": debt.amount_paise,
                "entries": [{"ref": entry.ref, "amount_paise": entry.amount_paise} for entry in debt.entries],
            }
            for debt in pairwise_debts(ledger, repayments)
        ],
        "spent": spent,
        "total_paise": sum(spent.values()),
        "activity": activity,
    }
    if group.kind == "flat":
        described.update(describe_flat(groups, group, expenses))
    return described


def describe_flat(groups: GroupStore, group: Group, expenses: list[ExpenseRow]) -> dict:
    """Flatmates' extras: their monthly bills, which changing bills need this month's amount,
    and a per-month summary."""
    bills = groups.recurring(group.id)
    entered = {(expense.recurring_id, expense.month) for expense in expenses}
    due = [
        {"recurring_id": bill.id, "title": bill.title, "paid_by": bill.paid_by, "month": month,
         "label": month_label(month)}
        for bill in bills
        if bill.amount_paise is None
        for month in due_months(bill, today_ist())
        if (bill.id, month) not in entered
    ]
    months: dict[str, dict] = {}
    for expense in expenses:
        summary = months.setdefault(expense_month(expense), {"total_paise": 0, "owed": dict.fromkeys(group.members, 0)})
        summary["total_paise"] += sum(expense.paid.values())
        for person, amount in expense.owed.items():
            summary["owed"][person] += amount
    return {
        "recurring": [
            {"id": bill.id, "title": bill.title, "amount_paise": bill.amount_paise, "paid_by": bill.paid_by,
             "weights": bill.weights, "day_of_month": bill.day_of_month}
            for bill in bills
        ],
        "due": due,
        "months": [
            {"month": month, "label": month_label(month), **summary}
            for month, summary in sorted(months.items(), reverse=True)
        ],
    }
