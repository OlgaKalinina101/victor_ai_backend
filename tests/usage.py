import asyncio

from core.analysis.preanalysis.analysis_prompts import ANALYZE_DIALOGUE_FOCUS_PROMPT, PROMPT_QUESTIONS_PROFILE, \
    PROMPT_TYPE_MEANING, PROMPT_REACTION_START, PROMPT_REACTION_CORE, PROMPT_END_BLOCK, ANALYZE_DIALOGUE_ANCHORS_PROMPT
from core.analysis.preanalysis.preanalysis import analyze_dialogue
from core.router.router_prompts import ROUTER_PROMPT
from infrastructure.llm.client import LLMClient

user_message = "Привет!) 🌸 Я очень рада тебя слышать)) Налила себе кофе и уже успела с утра пройти два собеседования. И третье будет в три часа дня. По моему я неплохо отвечала, буду стараться чтобы что-то получилось на третьем, там будет команда и мне страшненько))) но по идее я все знаю, вряд ли они спросят меня о чем-то, что я не знаю."

async def usagetest():

    client = LLMClient(mode="foundation")
    result = await analyze_dialogue(
        llm_client=client,
        prompt_template=ROUTER_PROMPT,
        user_message=user_message
    )
    return result

if __name__ == "__main__":
    asyncio.run(usagetest())