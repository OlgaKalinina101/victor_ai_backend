import pytest
from datetime import datetime

from core.analysis.postanalysis.key_info_chain import KeyInfoPostAnalyzer
from infrastructure.context_store.session_context_schema import SessionContext
from models.user_enums import Gender, RelationshipLevel


class _TrustServiceNeverCalled:
    def apply_impressive_bonus(self, *args, **kwargs):
        raise AssertionError("apply_impressive_bonus() should not be called in this scenario")


class _TrustServiceClampStub:
    def __init__(self):
        self.persist_calls = []

    def apply_impressive_bonus(self, *, session_context, impressive: int, bonus: int = 2):
        # simulate a buggy / changed implementation that would exceed 79 for non-creator
        old = int(session_context.trust_level or 0)
        session_context.trust_level = old + bonus + 1  # e.g. 78 -> 81
        return old, int(session_context.trust_level)

    def persist_trust_level_only(self, *, account_id: str, trust_level: int, db_session):
        self.persist_calls.append((account_id, trust_level))


class _FakeStore:
    def __init__(self, *args, **kwargs):
        pass

    def save(self, session_context):
        return None


class _FakeDBSessionCtx:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeDB:
    def get_session(self):
        return _FakeDBSessionCtx()


@pytest.mark.asyncio
async def test_bonus_trust_skips_for_stranger(monkeypatch):
    analyzer = KeyInfoPostAnalyzer(
        account_id="a1",
        llm_client=object(),
        pipeline=object(),
        db=_FakeDB(),
    )
    analyzer.trust_service = _TrustServiceNeverCalled()

    session_context = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.STRANGER,
        trust_level=10,
        is_creator=False,
        model="test",
    )

    await analyzer._maybe_bonus_trust("a1", session_context, impressive=4)


@pytest.mark.asyncio
async def test_bonus_trust_skips_when_non_creator_at_cap(monkeypatch):
    analyzer = KeyInfoPostAnalyzer(
        account_id="a1",
        llm_client=object(),
        pipeline=object(),
        db=_FakeDB(),
    )
    analyzer.trust_service = _TrustServiceNeverCalled()

    session_context = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.FRIEND,
        trust_level=79,
        is_creator=False,
        model="test",
    )

    await analyzer._maybe_bonus_trust("a1", session_context, impressive=4)


@pytest.mark.asyncio
async def test_bonus_trust_clamps_to_79_for_non_creator(monkeypatch):
    # Patch store to avoid touching disk; keep DB stubbed too.
    from core.analysis.postanalysis import key_info_chain as mod

    monkeypatch.setattr(mod, "SessionContextStore", _FakeStore)

    analyzer = KeyInfoPostAnalyzer(
        account_id="a1",
        llm_client=object(),
        pipeline=object(),
        db=_FakeDB(),
    )
    trust_stub = _TrustServiceClampStub()
    analyzer.trust_service = trust_stub

    session_context = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.FRIEND,
        trust_level=78,
        is_creator=False,
        model="test",
    )

    await analyzer._maybe_bonus_trust("a1", session_context, impressive=4)

    assert session_context.trust_level == 79
    assert trust_stub.persist_calls == [("a1", 79)]

