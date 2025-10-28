from infrastructure.embeddings.embedding_manager import EmbeddingManager
from infrastructure.embeddings.emotion_recognizer import EmotionRecognizer
from infrastructure.logging.logger import setup_logger

logger = setup_logger("preload_models")

def preload_models():
    logger.info("🔁 Предзагрузка моделей...")

    # Предзагрузка эмбеддинговой модели
    embedder = EmbeddingManager.get_embedding_model()

    # Предзагрузка эмоций для русского языка (или нужного тебе)
    recognizer = EmotionRecognizer.get_emotion_recognizer("ru")

    logger.info("✅ Все модели загружены")