import time
import torch
from transformers import pipeline, AutoTokenizer
from typing import Dict, List

from infrastructure.logging.logger import setup_logger

logger = setup_logger("emotion_recognizer")


class EmotionRecognizer:
    """
    Класс-обёртка для детекции эмоций.
    Поддерживает мультиязычные модели.
    """

    _emotion_recognizer = None
    _tokenizer = None
    _current_model = None

    MODELS = {
        "ru": "seara/rubert-base-cased-russian-emotion-detection-cedr",  # лёгкая русскоязычная (~80МБ)
        "en": "j-hartmann/emotion-english-distilroberta-base"  # англ (~300МБ)
    }

    @classmethod
    def get_emotion_recognizer(cls, lang: str = "ru"):
        """
        Загружает пайплайн детекции эмоций и токенизатор для нужного языка.
        """
        start_time = time.time()
        model_name = cls.MODELS.get(lang, cls.MODELS["ru"])

        if cls._emotion_recognizer is None or cls._current_model != model_name:
            logger.info(f"Загрузка emotion recognizer [{lang}]...")
            cls._emotion_recognizer = pipeline(
                "text-classification",
                model=model_name,
                device=0 if torch.cuda.is_available() else -1,
                top_k=None
            )
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name)
            cls._current_model = model_name
            logger.info(
                f"Emotion recognizer [{lang}] загружен за {time.time() - start_time:.2f} секунд"
            )

        return cls._emotion_recognizer

    @classmethod
    def truncate_text(cls, text: str, lang: str = "ru", max_length: int = 512) -> str:
        """
        Универсальная обрезка текста для текущей модели.

        Args:
            text (str): Исходный текст.
            lang (str): "ru" или "en".
            max_length (int): Максимальное число токенов.

        Returns:
            str: Усечённый текст.
        """
        if cls._tokenizer is None or cls._current_model != cls.MODELS[lang]:
            cls._tokenizer = AutoTokenizer.from_pretrained(cls.MODELS[lang])

        tokens = cls._tokenizer.encode(
            text,
            truncation=True,
            max_length=max_length,
            return_tensors="pt"
        )
        return cls._tokenizer.decode(tokens[0], skip_special_tokens=True)

    @classmethod
    def predict(cls, text: str, lang: str = "ru") -> List[Dict[str, float]]:
        """
        Делает предсказание эмоций, автоматически обрезая текст.
        """
        recognizer = cls.get_emotion_recognizer(lang)
        clean_text = cls.truncate_text(text, lang)
        result = recognizer(clean_text)

        # Приводим к единому формату
        if isinstance(result, list) and isinstance(result[0], list):
            result = result[0]

        return [
            {"label": r["label"].lower(), "score": float(r["score"])}
            for r in result
        ]

