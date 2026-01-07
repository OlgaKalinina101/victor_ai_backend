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

"""Репозиторий для кеша подписей к POI."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from infrastructure.logging.logger import setup_logger
from tools.maps.models import POICaption

logger = setup_logger("place_caption_repository")


class PlaceCaptionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_lookup(
        self,
        account_id: str,
        osm_element_id: int,
        osm_element_type: str,
        tags_hash: str,
    ) -> Optional[POICaption]:
        return (
            self.session.query(POICaption)
            .filter(
                POICaption.account_id == account_id,
                POICaption.osm_element_id == osm_element_id,
                POICaption.osm_element_type == osm_element_type,
                POICaption.tags_hash == tags_hash,
            )
            .order_by(POICaption.created_at.desc())
            .first()
        )

    def create(
        self,
        account_id: str,
        osm_element_id: int,
        osm_element_type: str,
        poi_name: Optional[str],
        tags: Dict[str, Any],
        tags_hash: str,
        caption: str,
    ) -> POICaption:
        row = POICaption(
            account_id=account_id,
            osm_element_id=osm_element_id,
            osm_element_type=osm_element_type,
            poi_name=poi_name,
            tags=tags,
            tags_hash=tags_hash,
            caption=caption,
        )
        self.session.add(row)
        self.session.flush()
        return row


