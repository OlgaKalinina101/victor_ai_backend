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