import types

import pytest


@pytest.mark.asyncio
async def test_emotion_recognizer_switch_lang_cleans_up(monkeypatch):
    """
    Проверяем, что при смене языка EmotionRecognizer чистит старую модель (и дергает empty_cache на CUDA).
    Тест без скачивания реальных моделей: monkeypatch pipeline/AutoTokenizer/torch.cuda.
    """
    from infrastructure.embeddings import emotion_recognizer as mod

    # Reset state to avoid interference from other tests/imports.
    mod.EmotionRecognizer.cleanup()

    created = {"pipelines": [], "tokenizers": []}

    def fake_pipeline(task, model, device, top_k=None):
        created["pipelines"].append((task, model, device, top_k))
        return f"pipe:{model}"

    class FakeTokenizer:
        def __init__(self, model_name):
            self.model_name = model_name
            created["tokenizers"].append(model_name)

        def encode(self, text, truncation=True, max_length=512, **kwargs):
            # Crucial: must NOT create torch tensors
            assert "return_tensors" not in kwargs
            return [1, 2, 3]

        def decode(self, tokens, skip_special_tokens=True):
            return "decoded"

    fake_autotok = types.SimpleNamespace(
        from_pretrained=lambda model_name: FakeTokenizer(model_name)
    )

    empty_cache_calls = []

    monkeypatch.setattr(mod, "pipeline", fake_pipeline)
    monkeypatch.setattr(mod, "AutoTokenizer", fake_autotok)
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(mod.torch.cuda, "empty_cache", lambda: empty_cache_calls.append(1))

    # Load RU
    r1 = mod.EmotionRecognizer.get_emotion_recognizer("ru")
    assert r1 == f"pipe:{mod.EmotionRecognizer.MODELS['ru']}"
    assert mod.EmotionRecognizer._current_model == mod.EmotionRecognizer.MODELS["ru"]

    # Switch to EN -> must cleanup and empty_cache
    r2 = mod.EmotionRecognizer.get_emotion_recognizer("en")
    assert r2 == f"pipe:{mod.EmotionRecognizer.MODELS['en']}"
    assert mod.EmotionRecognizer._current_model == mod.EmotionRecognizer.MODELS["en"]
    assert len(empty_cache_calls) == 1

    # Same EN again -> no extra cleanup
    _ = mod.EmotionRecognizer.get_emotion_recognizer("en")
    assert len(empty_cache_calls) == 1


def test_emotion_recognizer_truncate_text_does_not_create_tensors(monkeypatch):
    from infrastructure.embeddings import emotion_recognizer as mod

    mod.EmotionRecognizer.cleanup()

    class FakeTokenizer:
        def encode(self, text, truncation=True, max_length=512, **kwargs):
            assert "return_tensors" not in kwargs
            return [1, 2, 3]

        def decode(self, tokens, skip_special_tokens=True):
            return "decoded"

    fake_autotok = types.SimpleNamespace(from_pretrained=lambda model_name: FakeTokenizer())
    monkeypatch.setattr(mod, "AutoTokenizer", fake_autotok)

    out = mod.EmotionRecognizer.truncate_text("hello", lang="ru", max_length=10)
    assert out == "decoded"

