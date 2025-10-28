from dataclasses import field, dataclass
from typing import Dict, Any


@dataclass
class AnalysisResult:
    """Результаты анализа сообщения.
    Хранит данные анализа для формирования MessageMetadata и DialogContext.
    """
    mood_data: Dict[str, Any] = field(default_factory=dict) # "mood" будет Mood
    focus_result: Dict[str, str] = field(default_factory=dict)
    anchor_result: Dict[str, Any] = field(default_factory=dict)
    type_result: Dict[str, str] = field(default_factory=dict)
    reaction_start_result: Dict[str, str] = field(default_factory=dict)
    reaction_core_result: Dict[str, str] = field(default_factory=dict)
    question_result: Dict[str, str] = field(default_factory=dict)
    end_result: Dict[str, str] = field(default_factory=dict)
    memories_result: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def empty() -> "AnalysisResult":
        return AnalysisResult()