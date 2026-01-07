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

from logging import Logger
from typing import Optional, Tuple

def extract_usage_info(logger: Logger, response: dict) -> Optional[Tuple[int, int]]:
    """Хелпер для подсчета токенов"""
    try:
        logger.info(f"response: {response}")
        usage_data = response.get("usage")
        if not usage_data:
            return None

        # Ключи зависят от API — у OpenAI это prompt_tokens и completion_tokens
        input_tokens = usage_data.get("input_tokens") or usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("output_tokens") or usage_data.get("completion_tokens", 0)

        return input_tokens, output_tokens
    except Exception as e:
        logger.warning(f"[extract_usage_info] Ошибка: {e}")
        return None
