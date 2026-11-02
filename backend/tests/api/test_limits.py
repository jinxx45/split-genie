"""The per-visitor limit on starting splits."""

from app.api.limits import RateLimit


def test_uses_are_counted_per_key_within_the_window():
    limit = RateLimit(2, window_seconds=60)

    assert limit.allow("a", now=0) and limit.allow("a", now=10)
    assert not limit.allow("a", now=20)  # third use within a minute
    assert limit.allow("b", now=20)  # someone else is unaffected
    assert limit.allow("a", now=61)  # the first use has left the window
