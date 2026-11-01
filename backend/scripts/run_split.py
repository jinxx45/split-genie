"""Run a whole split in the terminal with Gemini, answering each pause yourself.

From the backend folder:
    uv run python -m scripts.run_split ~/Downloads/bill.jpg --people "Arun,Priya,Ravi" --note "Ravi doesn't drink"
Several photos make a multi-receipt split:
    uv run python -m scripts.run_split day1.jpg day2.jpg --people "Arun,Priya,Ravi"
"""

import argparse
import shutil
import sys
import uuid
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent import llm
from app.agent.graph import build_graph, new_split
from app.agent.receipt import format_rupees, to_paise
from app.config import settings
from app.money.split import FULL, HALF
from app.observability import configure_logging, enable_langsmith_if_configured


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a full split in the terminal.")
    parser.add_argument("photos", type=Path, nargs="+")
    parser.add_argument("--people", required=True, help="Comma-separated names, e.g. Arun,Priya,Ravi")
    parser.add_argument("--note", default="", help="e.g. \"Ravi doesn't drink\"")
    args = parser.parse_args()

    if not settings.gemini_api_key:
        sys.exit("No GEMINI_API_KEY found. Add it to backend/.env first.")
    configure_logging()
    if enable_langsmith_if_configured():
        print("LangSmith tracing is on: see the split-genie project at smith.langchain.com")

    people = [name.strip() for name in args.people.split(",") if name.strip()]
    receipt_ids = [save_photo(photo.expanduser()) for photo in args.photos]

    graph = build_graph(
        InMemorySaver(), llm.read_receipt, llm.suggest_assignments, llm.correct_assignments
    )
    config = {"configurable": {"thread_id": f"terminal-{uuid.uuid4().hex[:8]}"}}
    graph.invoke(new_split(people, args.note, receipt_ids), config)

    while True:
        state = graph.get_state(config)
        if not state.interrupts:
            break
        question = state.interrupts[0].value
        graph.invoke(Command(resume=ask(question, people)), config)

    print("\nDone. Payments:")
    for payment in graph.get_state(config).values["payments"]:
        print(f"  {payment['sender']} → {payment['receiver']}  {format_rupees(payment['amount_paise'])}")


def save_photo(photo: Path) -> str:
    """Copy the photo into the uploads folder under a fresh id, the way the app will."""
    if not photo.is_file():
        sys.exit(f"No such file: {photo}")
    settings.uploads_dir.mkdir(exist_ok=True)
    receipt_id = f"{uuid.uuid4().hex}{photo.suffix.lower()}"
    shutil.copy(photo, settings.uploads_dir / receipt_id)
    return receipt_id


# --- One function per kind of pause. Each returns the answer the graph expects. ---


def ask(question: dict, people: list[str]):
    step = question["step"]
    if step == "confirm_items":
        return ask_confirm(question)
    if step == "review_assignments":
        return ask_review(question, people)
    if step == "payer":
        return ask_payer(question, people)
    if step == "approve":
        return ask_approval(question)
    sys.exit(f"Unknown step: {step}")


def ask_confirm(question: dict) -> dict:
    receipt = question["receipt"]
    print("\n── Check the items ──")
    for index, item in enumerate(receipt["items"]):
        print(f"  {index}. {item['name']:<32} {format_rupees(item['amount_paise']):>11}  {item['category']}")
    print(f"  Tax and adjustments {format_rupees(receipt['tax_paise']):>24}")
    print(f"  Service charge      {format_rupees(receipt['service_charge_paise']):>24}")
    if not question["totals_match"]:
        print("  ⚠ These don't add up to the printed total. (Fixing items comes with the app screens.)")
    input("Press Enter to continue ")
    return receipt


def ask_review(question: dict, people: list[str]) -> dict:
    print("\n── Who had what ──")
    for entry in question["items"]:
        who = llm.describe_people(entry["suggested"]) or "❓"
        flag = "  ← please answer" if entry["needs_answer"] else ""
        print(f"  {entry['index']}. {entry['item']['name']:<32} {who:<30} {entry['reason']}{flag}")

    changes: dict[str, dict[str, int]] = {}
    for entry in question["items"]:
        if entry["needs_answer"]:
            changes[str(entry["index"])] = read_people(f"Who had {entry['item']['name']}? ", people)

    print("To change another item, type its number. Press Enter when everything is right.")
    while choice := input("Item number: ").strip():
        if not choice.isdigit() or int(choice) >= len(question["items"]):
            print("  That isn't an item number.")
            continue
        changes[choice] = read_people("Who had it? ", people)
    return {"changes": changes}


def ask_payer(question: dict, people: list[str]) -> dict:
    total = question["total_paise"]
    print(f"\n── Who paid {format_rupees(total)}? ──")
    print("  One name if one person paid, or name=amount for each payer, e.g. Arun=1000,Priya=232")
    while True:
        answer = input("Paid by: ").strip()
        try:
            return parse_payers(answer, people, total)
        except ValueError as problem:
            print(f"  {problem}")


def ask_approval(question: dict) -> dict:
    print("\n── Final split ──")
    for person, amount in question["shares"].items():
        print(f"  {person:<16} owes in total {format_rupees(amount):>11}")
    for payment in question["payments"]:
        print(f"  {payment['sender']} → {payment['receiver']}  {format_rupees(payment['amount_paise'])}")
    if question["error"]:
        print(f"  ⚠ {question['error']}")
    answer = input("Type y to approve, or say what's wrong: ").strip()
    if answer.lower() in ("y", "yes"):
        return {"approved": True}
    return {"approved": False, "note": answer}  # the graph checks the note itself


# --- Reading names and amounts typed by the user ---


def read_people(prompt: str, people: list[str]) -> dict[str, int]:
    """'Arun, Priya*' -> {"Arun": FULL, "Priya": HALF}. A * marks a half share."""
    print(f"  Names separated by commas; add * for a half share. People: {', '.join(people)}")
    while True:
        answer = input(prompt).strip()
        try:
            return parse_people(answer, people)
        except ValueError as problem:
            print(f"  {problem}")


def parse_people(answer: str, people: list[str]) -> dict[str, int]:
    by_lowercase = {person.lower(): person for person in people}
    weights = {}
    for part in answer.split(","):
        name = part.strip()
        weight = HALF if name.endswith("*") else FULL
        person = by_lowercase.get(name.rstrip("*").strip().lower())
        if person is None:
            raise ValueError(f"Unknown name: {name or '(empty)'}")
        weights[person] = weight
    return weights


def parse_payers(answer: str, people: list[str], total: int) -> dict[str, int]:
    by_lowercase = {person.lower(): person for person in people}
    if "=" not in answer:
        person = by_lowercase.get(answer.lower())
        if person is None:
            raise ValueError(f"Unknown name: {answer or '(empty)'}")
        return {person: total}

    paid = {}
    for part in answer.split(","):
        name, _, amount = part.partition("=")
        person = by_lowercase.get(name.strip().lower())
        if person is None:
            raise ValueError(f"Unknown name: {name.strip() or '(empty)'}")
        paid[person] = to_paise(amount)
    if sum(paid.values()) != total:
        raise ValueError(f"That adds up to {format_rupees(sum(paid.values()))}, not {format_rupees(total)}.")
    return paid


if __name__ == "__main__":
    main()
