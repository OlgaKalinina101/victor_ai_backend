from dataclasses import dataclass

from models.user_enums import Gender, RelationshipLevel


@dataclass
class UserProfile:
    """Профиль пользователя."""
    account_id: str | None = None
    gender: Gender = Gender.OTHER
    relationship: RelationshipLevel = RelationshipLevel.STRANGER
    trust_level: int = 0
    model: str = "gpt-4o"

