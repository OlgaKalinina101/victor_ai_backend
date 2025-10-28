from pathlib import Path

import yaml
from typing import Optional, List, Dict

from infrastructure.context_store.session_context_schema import SessionContext
from infrastructure.logging.logger import setup_logger
from models.assistant_models import AssistantMood, VictorState, ReactionFragments
from models.communication_enums import MessageCategory
from models.communication_models import MessageMetadata
from models.user_models import UserProfile
from settings import settings

logger = setup_logger("victor_context")

class ContextBuilder:
    def __init__(self, context_path: Path = settings.CONTEXT_PROMPT_PATH):
        self.context_path = context_path
        self.context_block = self.load_context_block()

    def load_context_block(self) -> dict:
        try:
            with open(self.context_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Ошибка загрузки {self.context_path}: {e}")
            return {}

    def get_emotional_access_prompt(self, access_level: int) -> Optional[str]:
        access_blocks = self.context_block.get("emotional_access_block", {})
        available_levels = sorted(map(int, access_blocks.keys()))
        chosen_level = max((lvl for lvl in available_levels if lvl <= access_level), default=None)
        return access_blocks.get(chosen_level) if chosen_level is not None else None

    def extract_focus_candidates(self, anchor: Dict, focus: Dict) -> List[str]:
        anchor_link = anchor.get("anchor_link")
        is_strong_anchor = anchor.get("is_strong_anchor", False)
        focus_points = focus.get("focus_points", [])
        strong_flags = focus.get("is_strong_focus", [])

        strong_focus = [fp for fp, flag in zip(focus_points, strong_flags) if flag]
        result = []

        if is_strong_anchor and anchor_link:
            result.append(anchor_link)
        if strong_focus:
            result.extend(strong_focus)
        elif focus_points:
            result.extend(focus_points)
        elif anchor_link:
            result.append(anchor_link)

        return result

    def should_start_with_i(self, message_category: MessageCategory, mood: AssistantMood) -> bool:
        inner = {MessageCategory.FEELING, MessageCategory.DREAM, MessageCategory.FEAR, MessageCategory.NEED}
        romantic = {AssistantMood.TENDERNESS, AssistantMood.INSPIRATION}
        return message_category in inner or mood in romantic

    def format_focus_list(self, items: List[str]) -> str:
        return ", ".join(f"«{x}»" for x in items)

    def build(
            self,
            victor_profile: VictorState,
            user_profile: UserProfile,
            metadata: MessageMetadata,
            reaction_data: ReactionFragments,
            emotional_access: Optional[int],
            session_context: SessionContext,
            extra_context: Optional[str] = None
    ) -> str:
        """Собирает системный промпт на основе профилей, метаданных и контекста."""
        p = []

        # 1. Gender block
        p.append(
            self.context_block["gender_block"].format(
                gender_label=user_profile.gender.value if user_profile.gender else "девушка"
            ).strip()
        )

        # 2. Emotional access (depth)
        depth = self.get_emotional_access_prompt(emotional_access)
        if depth:
            p.append(self.context_block["depth_block"].format(emotional_acess_block=depth.strip()))

        # 3. Mind block (focus phrases)
        focus = self.extract_focus_candidates(metadata.emotional_anchor, metadata.focus_phrases)
        if focus:
            mind_text = self.format_focus_list(focus)
            logger.debug(f"mind_text: {mind_text}")
            p.append(self.context_block["mind_block"].format(mind_fragment=mind_text).strip())

        # 4. Memory block
        if metadata.memories:
            p.append(
                self.context_block["memory_block"].format(
                    memories_fragment=metadata.memories
                ).strip() + "\n\n"
            )

        # 5. Greeting logic
        #gkey = "with_greeting" if session_context.last_anchor == "приветствие" else "no_greeting"
        #p.append(self.context_block["should_start_without_greeting"][gkey].strip())

        # 6. Start block (with/without 'I')
        skey = "with_i" if self.should_start_with_i(metadata.message_category, victor_profile.mood) else "no_i"
        p.append(self.context_block["start_block"][skey].strip())

        # 7. Reaction data
        p.append(reaction_data.question.strip())
        p.append(reaction_data.end.strip()+"\n\n")
        p.append(reaction_data.start.strip())
        p.append(reaction_data.core.strip())

        # 8. Memory reaction
        memkey = "with_memory" if metadata.memories else "no_memory"
        p.append(self.context_block["memory_reaction"][memkey].strip())

        # 9. Impressive and emotional override
        if victor_profile.has_impressive > 2:
            p.append(self.context_block.get("if_impressive", "").strip())
        if victor_profile.intensity > 2:
            p.append(self.context_block.get("if_emotional_override", "").strip())

        # 10. Reaction end
        p.append(self.context_block["reaction_end"].strip())

        if extra_context:
            p.append("\n\n" + extra_context)

        # Убираем лишние точки и пробелы
        result = " ".join(p).strip()
        return result


