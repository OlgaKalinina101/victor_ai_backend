import io
from datetime import datetime

import pytest

from infrastructure.context_store.session_context_schema import SessionContext
from models.user_enums import Gender, RelationshipLevel
from models.user_models import UserProfile


class _DummyLogger:
    def info(self, *args, **kwargs):
        return None


class _DummySelf:
    logger = _DummyLogger()


class _EnumLike:
    def __init__(self, value):
        self.value = value


class _MetadataStub:
    def __init__(self):
        self.mood = _EnumLike("ok")
        self.mood_level = _EnumLike("low")
        self.message_category = _EnumLike("chat")
        self.dialog_weight = 1
        self.emotional_anchor = None
        self.focus_phrases = None
        self.memories = None
        self.text = "hello"


class _VictorStub:
    def __init__(self):
        self.mood = _EnumLike("neutral")
        self.intensity = 0.1
        self.has_impressive = 1


class _OpenNoClose:
    """Context manager wrapper that doesn't close the underlying buffer."""

    def __init__(self, buf: io.StringIO):
        self.buf = buf

    def __enter__(self):
        return self.buf

    def __exit__(self, exc_type, exc, tb):
        # do not close
        return False


@pytest.mark.asyncio
async def test_debug_dataset_not_written_for_non_creator(monkeypatch):
    from core.chain.communication import CommunicationPipeline

    opened = {"called": False}
    makedirs = {"called": False}

    def _fake_open(*args, **kwargs):
        opened["called"] = True
        return io.StringIO()

    def _fake_makedirs(*args, **kwargs):
        makedirs["called"] = True
        return None

    monkeypatch.setattr("builtins.open", _fake_open)
    monkeypatch.setattr("os.makedirs", _fake_makedirs)

    user_profile = UserProfile(
        account_id="a1",
        gender=Gender.OTHER,
        relationship=RelationshipLevel.FRIEND,
        trust_level=50,
        model="test",
    )
    session_context = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.FRIEND,
        trust_level=50,
        is_creator=False,
        model="test",
    )

    await CommunicationPipeline._maybe_save_debug(
        _DummySelf(),
        user_profile,
        _MetadataStub(),
        ["user: hi", "assistant: hey"],
        _VictorStub(),
        1,
        "sys",
        "ctx",
        "resp",
        session_context=session_context,
    )

    assert opened["called"] is False
    assert makedirs["called"] is False


@pytest.mark.asyncio
async def test_debug_dataset_written_for_creator(monkeypatch):
    from core.chain.communication import CommunicationPipeline

    sink = io.StringIO()
    makedirs = {"called": False}

    def _fake_open(*args, **kwargs):
        return _OpenNoClose(sink)

    def _fake_makedirs(*args, **kwargs):
        makedirs["called"] = True
        return None

    monkeypatch.setattr("builtins.open", _fake_open)
    monkeypatch.setattr("os.makedirs", _fake_makedirs)

    user_profile = UserProfile(
        account_id="a1",
        gender=Gender.OTHER,
        relationship=RelationshipLevel.FRIEND,
        trust_level=50,
        model="test",
    )
    session_context = SessionContext(
        account_id="a1",
        last_update=datetime.utcnow(),
        gender=Gender.OTHER,
        relationship_level=RelationshipLevel.FRIEND,
        trust_level=50,
        is_creator=True,
        model="test",
    )

    await CommunicationPipeline._maybe_save_debug(
        _DummySelf(),
        user_profile,
        _MetadataStub(),
        ["user: hi", "assistant: hey"],
        _VictorStub(),
        1,
        "sys",
        "ctx",
        "resp",
        session_context=session_context,
    )

    assert makedirs["called"] is True
    assert sink.getvalue().strip() != ""

