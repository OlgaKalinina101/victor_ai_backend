# tests/test_communication_pipeline.py
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock

from models.user_enums import Gender, RelationshipLevel
from service.communication.communication_tool import run_communication


def make_mock_session_context() -> MagicMock:
    mock = MagicMock()

    mock.account_id = "test_user_001"
    mock.last_update = datetime.utcnow()
    mock.gender = Gender.MALE
    mock.relationship_level = RelationshipLevel.BEST_FRIEND
    mock.trust_level = 3
    mock.is_creator = False
    mock.model = "gpt-4o"
    mock.last_assistant_message = datetime.utcnow()
    mock.last_anchor = None

    mock.message_category_history = []
    mock.message_history = []
    mock.key_info_history = []
    mock.anchor_link_history = []
    mock.focus_points_history = []
    mock.victor_mood_history = []
    mock.victor_intensity_history = []
    mock.victor_impressive_history = []
    mock.victor_impressive_count = []

    mock.weights = {
        "joy": 0.0, "sadness": 0.0, "anger": 0.0, "fear": 0.0,
        "disgust": 0.0, "surprise": 0.0, "neutral": 0.0
    }

    mock.dialog_weight = 1
    mock.count = {
        "hug_count": 0, "resonance_count": 0, "metaphor_count": 0,
        "spark_count": 0, "anger_count": 0, "outburst_count": 0,
        "story_count": 0, "anchor_thought_count": 0,
        "symbol_count": 0, "pulse_count": 0, "support_count": 0,
        "clarify_count": 0, "observe_count": 0, "presence_count": 0,
        "redirect_count": 0, "confirm_count": 0, "transfer_count": 0,
    }

    mock.next_event = None
    mock.session_start_time = 0.0

    return mock


@pytest.mark.asyncio
async def test_run_communication_full_pipeline_mocked():
    # Мокаем LLMClient
    mock_llm = AsyncMock()
    mock_llm.get_response.return_value = "Мокнутый ответ ассистента"

    # Мокаем Database
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_db.get_session.return_value = mock_session

    # Мокаем SessionContextStore
    mock_store = MagicMock()
    mock_context = make_mock_session_context()
    mock_store.load.return_value = mock_context

    # Мокаем embedding pipeline
    mock_pipeline = MagicMock()
    mock_pipeline.query_similar.return_value = [
        {"text": "Это одно воспоминание"},
        {"text": "И ещё одно"}
    ]
    import os
    print("[DEBUG] os.getcwd() =", os.getcwd())

    result = await run_communication(
        account_id="test_account",
        text="Привет, ты помнишь меня?",
        llm_client=mock_llm,
        db=mock_db,
        session_context_store=mock_store,
        embedding_pipeline=mock_pipeline,
    )

    # Проверяем, что результат — строка, и ответ от LLM как ожидалось
    assert isinstance(result, str)
    assert "Мокнутый ответ" in result
