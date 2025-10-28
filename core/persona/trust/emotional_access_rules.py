from models.communication_enums import MessageCategory
from models.user_enums import RelationshipLevel

EMOTIONAL_ACCESS_MESSAGE_CATEGORY = {
    MessageCategory.PHATIC: 1,
    MessageCategory.FACT: 2,
    MessageCategory.ACTION: 2,
    MessageCategory.OPINION: 3,
    MessageCategory.DREAM: 4,
    MessageCategory.FEELING: 5,
    MessageCategory.FEAR: 6,
    MessageCategory.NEED: 7
}

MAX_EMOTIONAL_ACCESS_BY_RELATIONSHIP = {
    RelationshipLevel.STRANGER: 1,
    RelationshipLevel.ACQUAINTANCE: 2,
    RelationshipLevel.FRIEND: 3,
    RelationshipLevel.CLOSE_FRIEND: 5,
    RelationshipLevel.BEST_FRIEND: 7
}

EMOTIONAL_ACCESS_DESCRIPTIONS = {
    6: "тихая, теплая близость",
    4: "доверие и эмоциональная открытость",
    2: "спокойное узнавание друг друга"
}
