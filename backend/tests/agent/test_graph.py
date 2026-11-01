from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent.extract import DINNER, LUNCH
from app.agent.graph import build_graph, new_split
from app.money.split import FULL

PEOPLE = ["arun", "priya", "ravi"]


def start(receipt_ids, thread_id="test"):
    """Start a split and run it until its first pause."""
    graph = build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(new_split(PEOPLE, "", receipt_ids), config)
    return graph, config


def paused_at(graph, config) -> dict:
    """What the graph is currently waiting for the user to answer."""
    return graph.get_state(config).interrupts[0].value


def answer(graph, config, value):
    graph.invoke(Command(resume=value), config)


def test_full_dinner_flow_pauses_three_times_then_settles():
    graph, config = start(["dinner"])

    # Pause 1: check the items
    question = paused_at(graph, config)
    assert question["step"] == "confirm_items"
    assert question["totals_match"] is True
    answer(graph, config, question["receipt"])

    # Pause 2: every item is shown for review; only the beer needs an answer
    question = paused_at(graph, config)
    assert question["step"] == "review_assignments"
    assert len(question["items"]) == 3
    assert [i["item"]["name"] for i in question["items"] if i["needs_answer"]] == ["Kingfisher x2"]
    answer(graph, config, {"changes": {"1": {"arun": FULL, "ravi": FULL}}})

    # Pause 3: who paid
    question = paused_at(graph, config)
    assert question["step"] == "payer"
    assert question["total_paise"] == 123200
    answer(graph, config, {"priya": 123200})

    final = graph.get_state(config).values
    assert final["shares"] == {"arun": 48400, "priya": 26400, "ravi": 48400}
    assert sorted((p["sender"], p["receiver"], p["amount_paise"]) for p in final["payments"]) == [
        ("arun", "priya", 48400),
        ("ravi", "priya", 48400),
    ]


def test_misread_receipt_is_retried_before_asking_the_user():
    graph, config = start(["blurry"])

    question = paused_at(graph, config)
    assert question["totals_match"] is True
    assert graph.get_state(config).values["attempts"] == 2


def test_unreadable_receipt_goes_to_the_user_after_two_retries():
    graph, config = start(["unreadable"])

    question = paused_at(graph, config)
    assert question["step"] == "confirm_items"
    assert question["totals_match"] is False
    assert graph.get_state(config).values["attempts"] == 3


def test_review_is_shown_even_when_nothing_is_unclear():
    graph, config = start(["lunch"])
    answer(graph, config, LUNCH)

    question = paused_at(graph, config)
    assert question["step"] == "review_assignments"
    assert not any(i["needs_answer"] for i in question["items"])

    answer(graph, config, {"changes": {}})  # "the suggestions are right"
    assert paused_at(graph, config)["step"] == "payer"


def test_user_can_remove_someone_from_an_item_the_agent_was_sure_about():
    graph, config = start(["dinner"])
    answer(graph, config, DINNER)

    # Priya skipped dessert; the beer was Arun and Ravi
    answer(
        graph,
        config,
        {"changes": {"1": {"arun": FULL, "ravi": FULL}, "2": {"arun": FULL, "ravi": FULL}}},
    )
    answer(graph, config, {"arun": 123200})

    shares = graph.get_state(config).values["shares"]
    # Priya now pays only for her third of the biryani, plus her part of the charges
    assert shares["priya"] == 22000
    assert sum(shares.values()) == 123200


def test_review_is_asked_again_while_an_item_has_nobody():
    graph, config = start(["dinner"])
    answer(graph, config, DINNER)

    answer(graph, config, {"changes": {}})  # skipped the beer question

    assert paused_at(graph, config)["step"] == "review_assignments"


def test_payer_is_asked_again_when_amounts_do_not_add_up():
    graph, config = start(["lunch"])
    answer(graph, config, LUNCH)
    answer(graph, config, {"changes": {}})

    answer(graph, config, {"arun": 100})

    assert paused_at(graph, config)["step"] == "payer"


def test_two_receipts_with_different_payers_are_settled_together():
    graph, config = start(["dinner", "lunch"])

    answer(graph, config, DINNER)
    answer(graph, config, {"changes": {"1": {"arun": FULL, "ravi": FULL}}})
    answer(graph, config, {"priya": 123200})
    answer(graph, config, LUNCH)
    answer(graph, config, {"changes": {}})
    answer(graph, config, {"arun": 47250})

    final = graph.get_state(config).values
    assert sum(final["shares"].values()) == 123200 + 47250
    assert sum(final["balances"].values()) == 0
    assert final["payments"]  # someone pays someone
    assert len(final["payments"]) <= len(PEOPLE) - 1


def test_split_resumes_from_a_new_graph_using_the_same_checkpointer():
    """Simulates closing the app and coming back later: same thread id, fresh graph."""
    checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "goa-trip"}}
    build_graph(checkpointer).invoke(new_split(PEOPLE, "", ["lunch"]), config)

    later = build_graph(checkpointer)

    assert paused_at(later, config)["step"] == "confirm_items"
    answer(later, config, LUNCH)
    assert paused_at(later, config)["step"] == "review_assignments"
