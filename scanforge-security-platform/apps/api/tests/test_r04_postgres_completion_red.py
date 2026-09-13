"""R04 red tests. Run only with R04_POSTGRES_URL against an isolated PostgreSQL database.

These assertions intentionally describe the policy contract and currently fail because
the service has no immutable attempt receipt or shared cancellation terminal transaction.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("R04_POSTGRES_URL"), reason="set R04_POSTGRES_URL to a disposable PostgreSQL database"
)


def test_changed_valid_replay_is_conflict_and_does_not_mutate():
    pytest.fail("R04 red: completion service currently reconstructs replay and accepts no immutable evidence digest")


def test_failure_after_evidence_writes_rolls_back_receipt_and_rows():
    pytest.fail("R04 red: no API-owned completion receipt exists to assert atomic evidence commit")


def test_completion_and_cancellation_have_one_postgresql_terminal_winner():
    pytest.fail("R04 red: cancellation service does not acquire the same Scan transaction lock as completion")
