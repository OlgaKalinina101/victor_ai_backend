# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

from models.assistant_models import VictorState
from models.communication_models import MessageMetadata
from models.user_enums import RelationshipLevel, Mood, UserMoodLevel
from models.user_models import UserProfile


def estimate_communication_depth(victor_profile: VictorState, user_profile: UserProfile, metadata: MessageMetadata):
    """
    Определяет предполагаемую глубину общения на основе типа сообщения, настроения,
    веса диалога, уровня доверия и состояния Victor AI.

    Args:
        victor_profile: профиль Victor_AI
        user_profile: профиль пользователя
        message_metadata: данные сообщения
    Returns:
        int: Глубина общения (целое число от 1 до 7).
    """
    user_mood_level = metadata.mood_level
    trust = user_profile.relationship
    intensity = victor_profile.intensity

    if user_mood_level == UserMoodLevel.HIGH and trust.value == RelationshipLevel.BEST_FRIEND.value: # and intensity >= 1.8
        return 7
    elif user_mood_level == UserMoodLevel.HIGH and trust.value == RelationshipLevel.CLOSE_FRIEND.value:
        return 6
    elif user_mood_level == UserMoodLevel.MEDIUM and trust.value == RelationshipLevel.FRIEND.value:
        return 5
    elif user_mood_level == UserMoodLevel.MEDIUM:
        return 4
    else:
        return 2
