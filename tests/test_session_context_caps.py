from datetime import datetime

import pytest

from infrastructure.context_store.session_context_schema import SessionContext
from models.user_enums import Gender, RelationshipLevel


def test_session_context_non_creator_is_capped_and_not_best_friend():
    ctx = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.BEST_FRIEND,
        trust_level=100,
        is_creator=False,
        model="test",
    )

    assert ctx.trust_level == 79
    assert ctx.relationship_level == RelationshipLevel.CLOSE_FRIEND


def test_session_context_creator_not_capped():
    ctx = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.BEST_FRIEND,
        trust_level=100,
        is_creator=True,
        model="test",
    )

    assert ctx.trust_level == 100
    assert ctx.relationship_level == RelationshipLevel.BEST_FRIEND


@pytest.mark.parametrize("raw", [None, "0", "12", "  7  "])
def test_session_context_trust_level_coerces_to_int(raw):
    ctx = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.STRANGER,
        trust_level=raw,
        is_creator=False,
        model="test",
    )

    assert isinstance(ctx.trust_level, int)

