from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ledgerpilot.domain.enums import BreakSeverity, BreakStatus, BreakType
from ledgerpilot.domain.models import Break, MatchLeg
from ledgerpilot.store.db import create_all, session_scope
from ledgerpilot.store.repositories import AuditRepository, BreakRepository, JournalRepository


@pytest.fixture(autouse=True)
def setup_db() -> None:
    create_all()


def test_decide_approve(client: object) -> None:
    leg = MatchLeg(record_type="gateway_txn", record_id="rec_1", amount_minor=1000)
    brk = Break(
        break_id="brk_approve_1",
        break_type=BreakType.FEE_VARIANCE,
        severity=BreakSeverity.MEDIUM,
        status=BreakStatus.OPEN,
        amount_at_risk_minor=50,
        currency="USD",
        legs=[leg],
        detected_by="test",
        detected_at=datetime.now(UTC),
        summary="Fee variance test",
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    resp = client.post(
        "/breaks/brk_approve_1/decision",
        json={"action": "approve", "note": "Approved by controller", "assignee": "alice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["break_id"] == "brk_approve_1"
    assert data["status"] == "resolved_manual"
    assert data["assignee"] == "alice"
    assert "journal_entry" in data

    # Verify DB persistence
    with session_scope() as session:
        stored = BreakRepository(session).get("brk_approve_1")
        assert stored is not None
        assert stored.status == BreakStatus.RESOLVED_MANUAL

        journals = JournalRepository(session).by_break("brk_approve_1")
        assert len(journals) == 1

        events, count = AuditRepository(session).list(subject_id="brk_approve_1")
        assert count >= 1
        assert events[0].event_type == "human_approved"


def test_decide_reject(client: object) -> None:
    brk = Break(
        break_id="brk_reject_1",
        break_type=BreakType.SHORT_PAYMENT,
        severity=BreakSeverity.LOW,
        status=BreakStatus.OPEN,
        amount_at_risk_minor=200,
        currency="USD",
        legs=[],
        detected_by="test",
        detected_at=datetime.now(UTC),
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    resp = client.post(
        "/breaks/brk_reject_1/decision",
        json={"action": "reject", "note": "Invalid break"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert "journal_entry" not in data

    with session_scope() as session:
        journals = JournalRepository(session).by_break("brk_reject_1")
        assert len(journals) == 0

        events, count = AuditRepository(session).list(subject_id="brk_reject_1")
        assert count >= 1
        assert events[0].event_type == "human_rejected"


def test_decide_write_off(client: object) -> None:
    leg = MatchLeg(record_type="gateway_txn", record_id="rec_2", amount_minor=1000)
    brk = Break(
        break_id="brk_writeoff_1",
        break_type=BreakType.FEE_VARIANCE,
        severity=BreakSeverity.LOW,
        status=BreakStatus.PENDING_APPROVAL,
        amount_at_risk_minor=50,
        currency="USD",
        legs=[leg],
        detected_by="test",
        detected_at=datetime.now(UTC),
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    resp = client.post(
        "/breaks/brk_writeoff_1/decision",
        json={"action": "write_off", "note": "Immaterial write off", "assignee": "bob"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "written_off"
    assert "journal_entry" in data

    with session_scope() as session:
        stored = BreakRepository(session).get("brk_writeoff_1")
        assert stored is not None
        assert stored.status == BreakStatus.WRITTEN_OFF


def test_decide_escalate(client: object) -> None:
    brk = Break(
        break_id="brk_escalate_1",
        break_type=BreakType.CHARGEBACK,
        severity=BreakSeverity.HIGH,
        status=BreakStatus.OPEN,
        amount_at_risk_minor=5000,
        currency="USD",
        legs=[],
        detected_by="test",
        detected_at=datetime.now(UTC),
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    resp = client.post(
        "/breaks/brk_escalate_1/decision",
        json={"action": "escalate", "note": "Escalating to fraud team"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "escalated"
    assert "journal_entry" not in data

    with session_scope() as session:
        journals = JournalRepository(session).by_break("brk_escalate_1")
        assert len(journals) == 0


def test_decide_reassign(client: object) -> None:
    brk = Break(
        break_id="brk_reassign_1",
        break_type=BreakType.TIMING_DIFFERENCE,
        severity=BreakSeverity.INFO,
        status=BreakStatus.OPEN,
        amount_at_risk_minor=300,
        currency="USD",
        legs=[],
        detected_by="test",
        detected_at=datetime.now(UTC),
        assignee="alice",
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    resp = client.post(
        "/breaks/brk_reassign_1/decision",
        json={"action": "reassign", "assignee": "charlie"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "open"
    assert data["assignee"] == "charlie"
    assert "journal_entry" not in data


def test_decide_comment(client: object) -> None:
    brk = Break(
        break_id="brk_comment_1",
        break_type=BreakType.FEE_VARIANCE,
        severity=BreakSeverity.LOW,
        status=BreakStatus.INVESTIGATING,
        amount_at_risk_minor=150,
        currency="USD",
        legs=[],
        detected_by="test",
        detected_at=datetime.now(UTC),
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    resp = client.post(
        "/breaks/brk_comment_1/decision",
        json={"action": "comment", "note": "Need more statement files"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "investigating"
    assert data["note"] == "Need more statement files"
    assert "journal_entry" not in data


def test_decide_unknown_break_404(client: object) -> None:
    resp = client.post(
        "/breaks/non_existent_id/decision",
        json={"action": "approve"},
    )
    assert resp.status_code == 404


def test_decide_duplicate_decision_409(client: object) -> None:
    leg = MatchLeg(record_type="gateway_txn", record_id="rec_dup", amount_minor=1000)
    brk = Break(
        break_id="brk_dup_1",
        break_type=BreakType.FEE_VARIANCE,
        severity=BreakSeverity.MEDIUM,
        status=BreakStatus.OPEN,
        amount_at_risk_minor=50,
        currency="USD",
        legs=[leg],
        detected_by="test",
        detected_at=datetime.now(UTC),
    )
    with session_scope() as session:
        BreakRepository(session).upsert(brk)

    # First decision succeeds
    resp1 = client.post(
        "/breaks/brk_dup_1/decision",
        json={"action": "approve"},
    )
    assert resp1.status_code == 200

    # Second decision fails with 409 Conflict
    resp2 = client.post(
        "/breaks/brk_dup_1/decision",
        json={"action": "reject"},
    )
    assert resp2.status_code == 409
