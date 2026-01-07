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

from typing import Optional, Dict, Any, Literal

from pydantic import BaseModel, Field

from models.user_enums import Gender


class WebDemoResolveRequest(BaseModel):
    demo_key: str


class WebDemoResolveResponse(BaseModel):
    status: Literal["ok", "needs_registration"]
    message: Optional[str] = None

    # ok:
    access_token: Optional[str] = None
    token_type: str = "bearer"
    account_id: Optional[str] = None
    initial_state: Optional[Dict[str, Any]] = None

    # needs_registration:
    required_fields: Optional[list[str]] = None
    gender_options: Optional[list[str]] = None


class WebDemoRegisterRequest(BaseModel):
    demo_key: str
    account_id: str = Field(..., min_length=2, max_length=64)
    gender: Gender  # принимает "мужчина"/"девушка"/"другое"


class WebDemoLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_id: str
    initial_state: Dict[str, Any]


