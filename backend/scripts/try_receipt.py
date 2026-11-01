"""Try Gemini on a real bill photo.

From the backend folder:
    uv run python -m scripts.try_receipt ~/Desktop/bill.jpg
    uv run python -m scripts.try_receipt ~/Desktop/bill.jpg --people "Arun,Priya,Ravi" --note "Ravi doesn't drink"
"""

import argparse
import sys
from pathlib import Path

from app.agent import llm
from app.agent.receipt import format_rupees, receipt_total, totals_match
from app.config import settings
from app.money.split import FULL
from app.observability import enable_langsmith_if_configured


def main() -> None:
    parser = argparse.ArgumentParser(description="Read a bill photo with Gemini.")
    parser.add_argument("photo", type=Path)
    parser.add_argument("--people", help="Comma-separated names, e.g. Arun,Priya,Ravi")
    parser.add_argument("--note", default="", help="e.g. \"Ravi doesn't drink\"")
    args = parser.parse_args()

    if not settings.gemini_api_key:
        sys.exit("No GEMINI_API_KEY found. Add it to backend/.env first.")
    if enable_langsmith_if_configured():
        print("LangSmith tracing is on: see the split-genie project at smith.langchain.com")

    photo = args.photo.expanduser().resolve()
    settings.uploads_dir = photo.parent  # read the photo from wherever it is

    receipt = llm.read_receipt(photo.name, feedback=None)

    print(f"\nPlace: {receipt['place'] or '(not printed)'}")
    print("\nItems")
    for index, item in enumerate(receipt["items"]):
        print(f"  {index}. {item['name']:<30} {format_rupees(item['amount_paise']):>12}  {item['category']}")
    print(f"  {'Tax and adjustments':<33} {format_rupees(receipt['tax_paise']):>12}")
    print(f"  {'Service charge':<33} {format_rupees(receipt['service_charge_paise']):>12}")
    print(f"\n  Adds up to:    {format_rupees(receipt_total(receipt))}")
    print(f"  Printed total: {format_rupees(receipt['printed_total_paise'])}")
    print("  Totals match ✅" if totals_match(receipt) else "  Totals don't match ❌ (the app would retry)")

    if args.people and args.note:
        people = [name.strip() for name in args.people.split(",")]
        suggestions = llm.suggest_assignments(people, args.note, receipt["items"])
        print("\nWho had what")
        for item, suggestion in zip(receipt["items"], suggestions):
            who = ", ".join(
                name if weight == FULL else f"{name} (half)"
                for name, weight in suggestion["weights"].items()
            )
            print(f"  {item['name']:<30} {who or '❓ ask the user':<35} {suggestion['reason']}")


if __name__ == "__main__":
    main()
