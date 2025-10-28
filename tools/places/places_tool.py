from datetime import datetime
import yaml
from tools.places.google_places_utils import get_nearby_restaurants
from infrastructure.logging.logger import setup_logger
from tools.places.osm_maps_utils import get_nearby_restaurants_osm

logger = setup_logger("places_tool")


class PlacesContextBuilder:
    def __init__(self, prompt_path: str = "tools/places/places_prompt.yaml"):
        self.prompt_path = prompt_path
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("places_prompt", "")
        except Exception as e:
            logger.error(f"Ошибка загрузки {self.prompt_path}: {e}")
            return ""

    def _build_places_context(self, places: list[dict]) -> str:
        context_parts = []
        for idx, place in enumerate(places, start=1):
            name = place.get('name', 'Неизвестное место')
            rating = place.get('rating', '–')
            url = place.get('map_url', '')

            # Markdown-ссылка с переносами строк
            part = f"[{idx}] [{name}]({url}) (рейтинг {rating})"
            context_parts.append(part)

        # Разделяем каждый блок переносом строки
        return "\n".join(context_parts)

    def build(self, latitude: float, longitude: float) -> str:
        try:
            places = get_nearby_restaurants_osm(latitude, longitude)
        except Exception as e:
            logger.error(f"Ошибка получения ресторанов: {e}")
            places = ""

        formatted_time = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

        return self.prompt_template.format(
            places_context=places,
            local_time=formatted_time
        )

