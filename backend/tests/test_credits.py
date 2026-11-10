from __future__ import annotations

import pytest

from app.billing.credits import CreditService, InsufficientCredits


def test_grant_reserve_settle_and_idempotency(tmp_path) -> None:
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("t1", 100, "seed")
    assert credits.balance("t1") == 100

    reservation = credits.reserve("t1", 30, "job", "j1")
    assert credits.balance("t1") == 70
    assert credits.reserve("t1", 30, "job", "j1") == reservation
    assert credits.balance("t1") == 70

    difference = credits.settle_ref("t1", "job", "j1", actual_amount=20)
    assert difference == 10
    assert credits.balance("t1") == 80
    assert credits.refund_ref("t1", "job", "j1") == 0


def test_refund_returns_reserved_credits(tmp_path) -> None:
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("t1", 50, "seed")
    credits.reserve("t1", 30, "pipeline", "p1")
    assert credits.balance("t1") == 20
    assert credits.refund_ref("t1", "pipeline", "p1") == 30
    assert credits.balance("t1") == 50
    assert credits.refund_ref("t1", "pipeline", "p1") == 0


def test_insufficient_credits(tmp_path) -> None:
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("t1", 10, "seed")
    with pytest.raises(InsufficientCredits):
        credits.reserve("t1", 20, "job", "j1")
    assert credits.balance("t1") == 10
