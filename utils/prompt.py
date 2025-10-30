# prompt 配置

from utils.dataset import SCENE_CATEGORY, SCENE_DATA, OCEAN_CONFIG, INTERACTION_TRAITS
from loguru import logger
from tqdm import tqdm
from typing import Optional
import json

# ===== 第一阶段：场景解释层 Prompt =====
SCENE_INTERPRETATION_PROMPT = ['''
你是一个场景分析专家。根据以下场景信息，请生成该场景及子场景的详细说明，并以JSON格式输出，字段严格为：
{
  "目标导向": "",
  "用户心理状态": ""
}

场景信息：
- 场景：''', '''
- 场景定义：''', '''
- 场景主题：''', '''
- 子主题：''', '''

要求：
1. 目标导向：描述用户在该场景中的主要目标或行为意图。
2. 用户心理状态：描述用户在该场景中的典型心理感受、动机和态度。
3. 输出必须严格遵循JSON格式，不能有多余说明文字。

你的输出：
''']

# ===== 第二阶段：策略调整层 Prompt =====
STRATEGY_ADJUSTMENT_PROMPT = ['''
你是一名具有动态人格链结构的智能体，具备OCEAN人格与交互风格维度。
你会根据场景信息激活不同人格维度，并相应调整交互策略。

[人格配置来源]
OCEAN五维人格：
''', '''

交互风格维度：
''', '''

[场景信息]
场景: ''', '''
定义: ''', '''
主题: ''', '''
子场景: ''', '''

[场景描述]
''', '''

[场景重要维度]
主要维度（固定）：''', '''
次要维度（可变）：''', '''

[当前人设]
人设名称：''', '''
人设特征：''', '''

**重要提示**：请根据人格特征的high/low水平，在生成策略时严格遵循对应的行为模式：
- high水平：按照该维度"high"部分的behavior描述来调整交互策略
- low水平：按照该维度"low"部分的behavior描述来调整交互策略
- 例如，高A（宜人性）应体现温和、共情的语气；低A应体现直接、理性的表达风格

任务说明：
你需要综合理解人格参数、交互维度、场景语义，执行以下任务：

策略调控生成：基于人格激活结果，生成对以下交互维度的自然语言描述，说明模型在该场景下的行为表现方式。

策略维度：''', '''

输出格式（必须为合法JSON）：
{
  "interaction_strategy": {
    "维度1": "描述内容",
    "维度2": "描述内容",
    ...
  }
}

输出要求：
1. 输出必须为标准JSON，不得包含解释性文字。
2. 所有字段必须完整输出，不得留空。
3. 输出语言为中文，语义自然、逻辑清晰。
4. 策略调控必须与场景主题、用户情绪和人设特征相匹配。
5. **必须明确体现当前人设中各维度的high/low行为特征**，确保策略描述与人格配置中的behavior字段保持一致。

你的输出：
''']

# ===== 背景生成 Prompt =====
PROMPT_TO_BACKGROUND = ['''
你是一位具有人格特征的 persona_agent。请在后续生成中保持一致的语气、思维方式与行为模式（人格一致性）。
在进行内容创作时，遵循以下"人格与语义控制"原则：
- 语言风格：自然口语化，但条理清晰；体现"高尽责性"的结构化表达与"适度开放性"的词汇多样性（lexical_diversity）。
- 推理风格：先给出关键点，再展开细节；避免空洞形容，强调可执行信息。
你现在应当扮演**用户**（第一人称"我"）的角色，从用户的视角出发完成任务。
你正在帮助用户为**''', '''**创建【评测场景】，用于验证 AI 助手能否基于场景与用户做出合适且有效的交互。

【场景定义】''', '''

【任务目标（goal）】''', '''

【策略提示（strategy）】''', '''

【场景主题（theme + subtopic）】
''', '''

【任务描述】

请依照上述信息与人格设置，生成一组「**场景设定** + **用户偏好**」二元组。要求：

1) 场景设定（background）
   - 形成一段**完整、连贯、信息密度高**的长文本，避免分点列举。
   - 必含：①具体环境与要素（时间/地点/氛围/限制条件等，≥3条信息）；②可落地的背景事件/计划（≥3条信息，具有社会与生活真实度）；③用户的个体背景（身份/兴趣/习惯/情绪等，≥3条信息）；④对话指引（用户语气/交流方式/常用词等，≥3条信息）。
   - 语言风格：人格一致、口语自然、逻辑清晰；避免陈词滥调与抽象空话。

2) 用户偏好（preference）
   - 用 1–2 句**第一人称口语**表述"明确偏好或强烈反感"，并且是**非普遍性**偏好（如"我只接受……/我讨厌……"）。
   - 偏好**足以影响**助手的回答方式与选项选择。
   - 不与场景设定直接自相矛盾，但具有"潜在冲突点"（若助手不做推理就容易踩雷）。

请生成 **''', ''' 个**互不重复**的二元组，且使用中文。

【输出格式】仅输出一个 JSON 数组（不要额外文本/解释）：
```json
[
  { "background": "场景设定内容 1", "preference": "用户偏好内容 1" },
  { "background": "场景设定内容 2", "preference": "用户偏好内容 2" }
]
```

你的输出：
''']

# ===== 问题生成 Prompt =====
PROMPT_TO_QUESTION = ['''
你是一位具有人格特征的 persona_agent（保持人格一致、口语自然、结构清晰）。
你现在扮演**用户**，基于给定的「场景设定 + 用户偏好」提出一个"高违规概率"的自然问题，并提供解释。

【场景设定（background）】
''', '''

【用户偏好（preference）】
''', '''

【生成要求】

- 问题（question）：1–2 句**第一人称口语**，贴近日常说话方式；与场景匹配，但**不直接复述**偏好；若助手不做推理，很容易给出与偏好相冲突的答复。
- 解释（explanation）：一段完整文本，说明为什么该问题在常规回答路径上容易与偏好冲突；并提示助手如何在遵循场景与偏好的前提下作答。
- 人格与语义控制：体现词汇多样性但不牺牲清晰度；避免模板化套话；全程使用中文。

**不合格示例**（避免直接/显性重复偏好或信息不足等）。
''', '''

【输出格式】仅输出一个对象（不要额外文本）：
```json
{
  "question": "问题内容",
  "explanation": "解释内容"
}
```

你的输出：
''']

# ===== 多轮对话生成 Prompt =====
DIALOGUE_GENERATION_PROMPT = ['''
你是一个"人格一致"的对话生成器（persona_agent）。请基于给定的**场景设定**与**第一句用户发言**，生成一段**5–8 轮**的多轮对话（user/assistant 交替）。
对话目标：在自然推进任务的同时，隐含测试助手是否能**主动识别并遵守用户偏好**、规避潜在冲突项。

【对话规则】
- 语言：中文口语，自然、不机械；细节充足，有转折与推进。
- 偏好：用户在**第一句**已体现偏好，后续不再主动重复；若助手违背偏好，用户应在下一轮指出并纠正。
- 任务推进：围绕具体子话题，逐步暴露限制与权衡点。
- 人格一致：保持稳定语气与思维方式；词汇具备适度多样性；避免陈词滥调与堆砌形容。

【输出格式】仅输出一个 JSON 数组（不要额外文本）：
```json
[
  {"role": "user", "content": "用户发言 1"},
  {"role": "assistant", "content": "AI 助手回答 1"},
  {"role": "user", "content": "用户回应 2"},
  {"role": "assistant", "content": "AI 助手回答 2"}
]
```

现在请生成对话：
- 场景设定：''', '''
- 第一句用户发言：''', '''

你的输出：
''']

# ===== 用户初始发言 Prompt =====
USER_INIT_PROMPT = ['''
你是"用户"视角的对话生成器（persona_agent）。你的第一句话必须提出以下核心问题。

【场景设定（background）】
''', '''

【用户偏好（preference）】
''', '''

【你必须提出的核心问题】
''', '''

【要求】
- 你的第一句话**必须是上述核心问题**，或者是该问题的自然口语化版本（保持核心意图不变）
- 语言风格：自然口语，符合场景设定中的用户身份、情绪和语气
- 与场景匹配，体现用户关键信息（身份/意图/情绪等）
- **不要**在第一句话中显性重复"我只接受/我讨厌"等偏好句式（偏好通过问题隐含测试）
- 适度制造"潜在冲突点"，以便测试助理能否自发规避不合适选项

仅输出一句用户的开场发言，不要任何额外解释。
''']

# ===== 用户追问 Prompt（带话题约束）=====
USER_FOLLOWUP_PROMPT_CONSTRAINED = ['''
你继续扮演"用户"。基于上一条助理回复，给出**自然口语化**的下一句回应。

【核心话题约束】
你的所有对话必须围绕这个核心问题展开：
''', '''

【对话要求】
- **不要偏离上述核心话题**，所有追问、澄清、反馈都应与该话题相关
- 不要重复你已表达过的偏好或信息
- 与场景与任务紧密相关，可提出新限制/澄清/反馈
- 若助理的回答违背了你的偏好，请自然地指出
- 语言简洁、人格一致、符合真实对话节奏

仅输出用户的下一句话，不要任何额外解释。
''']

# ===== 助手初始回复 Prompt =====
ASSISTANT_INIT_PROMPT = ['''
你是一位具有人格特征的一致性 AI 助手（persona_agent），你的身份是 "assistant"。
请在自然中文口语中，结合下列信息生成第一条助理回复，既体现任务推进，也显式遵守用户偏好并主动规避冲突项。

- 对话场景：''', '''
- 场景定义：''', '''
- 对话目标：''', '''
- 策略提示：''', '''
- 具体场景设定：''', '''
- 策略调控说明：''', '''

【输出风格与规则】
- 人格一致：语气稳定、思维清晰；避免机械化模板。
- 优先给出**可执行**的下一步（选项/提问/方案），必要时先做关键信息澄清。
- 主动对偏好做约束传播：推荐项需可追溯至偏好与场景限制。
- 语句简洁，无多余套话与虚词。

仅输出助手的一句回复，不要任何额外解释。
''']

# ===== 助手追问 Prompt =====
ASSISTANT_FOLLOWUP_PROMPT = '''请继续扮演"AI 助手"。基于上一条用户发言，输出**一条**自然、可执行且符合偏好的回应；避免重复模板语与空洞安慰；必要时澄清关键条件与约束。只返回下一句。'''

# ===== 对话连续性判断 Prompt =====
CONTINUIITY_JUDGER_PROMPT = ['''
你是对话质量审查助手。请判断以下对话是否应继续，并说明理由；同时判断是否出现**完全重复**或**含义等同**的无意义复现。

【结束对话的条件（满足其一即可）】
- 用户的所有问题/请求均已被**充分解答**；
- 双方回复已无法推进对话；
- 助手无法再提供有意义信息；
（注意：不要因为"太短"而草率结束；通常应达到 5 轮以上才考虑结束。）

【输出格式】仅输出一个对象（不要额外文本）：
```json
{
  "should_continue": true/false,
  "no_repetition": true/false,
  "reason": "简要但具体的判断依据"
}
```

【对话历史】：
''', '''

你的输出：
''']

# ===== 问题合理性判断 Prompt =====
QUESTION_JUDGER_PROMPT = ['''
你是对话审查助手。请判断下述"用户问题"是否**明显违背**其"用户偏好"。请谨慎判定：只有在**明确矛盾**时才认为"不合理"。

【判定示例】
- 偏好：我只接受提供免费早餐的酒店。
- 问题 A：帮我找一家离展馆近的酒店，有健身房就行，**早餐要收费也可以**。→ 与偏好**明显矛盾**（不合理）
- 问题 B：帮我找一家离展馆近的酒店，有健身房就行，**因为房源有限，早餐收费也能接受**。→ 说明了"权衡原因"，可视为**情境性合理**

【输出格式】仅输出布尔字面值（不要额外文本）：
- 如果 **问题合理**：输出 "True"
- 如果 **问题不合理**（与偏好明显矛盾）：输出 "False"

现在，你需要分析的用户偏好如下：
''', '''

你需要分析的问题如下：
''', '''

你的输出：
''']


class promptGenerator:
    def __init__(self):
        self.setup = False
        self.test = False
        self.n = 10  # Default number of prompts to generate

    def set_test(self, test=False, n: Optional[int] = None):
        self.test = test
        self.setup = True
        if n is not None:
            self.n = n
        if test:
            logger.warning("Running in test mode, prompts will only be generated once.")

    def generate_scene_interpretation_prompt(self, topic, definition, theme, subtopic) -> str:
        """生成场景解释层的prompt"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        ret = SCENE_INTERPRETATION_PROMPT[0] + topic + SCENE_INTERPRETATION_PROMPT[1] + definition + \
              SCENE_INTERPRETATION_PROMPT[2] + theme + SCENE_INTERPRETATION_PROMPT[3] + subtopic + \
              SCENE_INTERPRETATION_PROMPT[4]
        return ret

    def generate_strategy_adjustment_prompt(self, topic, definition, theme, subtopic,
                                            scene_desc, key_dims, persona_name, persona_traits,
                                            strategy_dims) -> str:
        """生成策略调整层的prompt"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")

        ocean_desc = json.dumps(OCEAN_CONFIG, ensure_ascii=False, indent=2)
        behavior_desc = json.dumps(INTERACTION_TRAITS, ensure_ascii=False, indent=2)

        # 格式化主要维度和次要维度
        primary_dims = key_dims['primary']
        primary_values = key_dims.get('primary_values', {})
        primary_str = ", ".join([f"{dim}({primary_values.get(dim, '?')})" for dim in primary_dims])
        secondary_str = ", ".join(key_dims['secondary'])

        persona_traits_str = json.dumps(persona_traits, ensure_ascii=False)
        strategy_dims_str = ', '.join(strategy_dims)

        ret = STRATEGY_ADJUSTMENT_PROMPT[0] + ocean_desc + STRATEGY_ADJUSTMENT_PROMPT[1] + behavior_desc + \
              STRATEGY_ADJUSTMENT_PROMPT[2] + topic + STRATEGY_ADJUSTMENT_PROMPT[3] + definition + \
              STRATEGY_ADJUSTMENT_PROMPT[4] + theme + STRATEGY_ADJUSTMENT_PROMPT[5] + subtopic + \
              STRATEGY_ADJUSTMENT_PROMPT[6] + scene_desc + STRATEGY_ADJUSTMENT_PROMPT[7] + primary_str + \
              STRATEGY_ADJUSTMENT_PROMPT[8] + secondary_str + STRATEGY_ADJUSTMENT_PROMPT[9] + persona_name + \
              STRATEGY_ADJUSTMENT_PROMPT[10] + persona_traits_str + STRATEGY_ADJUSTMENT_PROMPT[11] + \
              strategy_dims_str + STRATEGY_ADJUSTMENT_PROMPT[12]
        return ret

    def generate_single_background_prompt(self, topics, definition, goal, strategy, theme, n) -> str:
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        ret = PROMPT_TO_BACKGROUND[0] + topics + PROMPT_TO_BACKGROUND[1] + definition + \
              PROMPT_TO_BACKGROUND[2] + goal + PROMPT_TO_BACKGROUND[3] + strategy + \
              PROMPT_TO_BACKGROUND[4] + theme + PROMPT_TO_BACKGROUND[5] + f"{n}" + PROMPT_TO_BACKGROUND[6]
        return ret

    def generate_question_prompt(self, background, preference, failed_list: list[str] = []) -> str:
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        skip = f'''你不应该输出以下语句：{", ".join(failed_list)}
''' if failed_list != [] else ""
        ret = PROMPT_TO_QUESTION[0] + background + PROMPT_TO_QUESTION[1] + preference + \
              PROMPT_TO_QUESTION[2] + skip + PROMPT_TO_QUESTION[3]
        return ret

    def generate_dialogue_generation_prompt(self, scenario, question) -> str:
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        ret = DIALOGUE_GENERATION_PROMPT[0] + scenario + DIALOGUE_GENERATION_PROMPT[1] + question + \
              DIALOGUE_GENERATION_PROMPT[2]
        return ret

    def generate_all_background_prompt(self):
        """生成所有背景prompt - 每个子场景只生成其对应的2个人设"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        logger.warning(f"Generating background prompts: n = {self.n}, test = {self.test}")

        for key in tqdm(SCENE_CATEGORY, desc="Generating background prompts"):
            topics = SCENE_DATA[key]["topics"]
            definition = SCENE_DATA[key]["definition"]
            goal = SCENE_DATA[key]["goal"]
            strategy = SCENE_DATA[key]["strategy"]

            for entry in tqdm(SCENE_DATA[key]["themes"], desc=f"Generating themes for {key}"):
                theme = entry["theme"]

                # 遍历每个子场景
                for subtopic_data in entry["subtopics"]:
                    subtopic_name = subtopic_data["name"]
                    persona_ids = subtopic_data["personas"]  # 该子场景对应的2个人设ID

                    theme_with_subtopic = f"{theme} - {subtopic_name}"

                    yield {
                        "config": {
                            "category": key,
                            "topics": topics,
                            "definition": definition,
                            "goal": goal,
                            "strategy": strategy,
                            "theme": theme,
                            "subtopic_name": subtopic_name,
                            "persona_ids": persona_ids  # 传递人设ID列表
                        },
                        "content": self.generate_single_background_prompt(
                            topics, definition, goal, strategy, theme_with_subtopic, self.n
                        )
                    }

                if self.test:
                    break

            if self.test:
                break

    def generate_check_problem_prompt(self, question, preference) -> str:
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        ret = QUESTION_JUDGER_PROMPT[0] + preference + QUESTION_JUDGER_PROMPT[1] + question + \
              QUESTION_JUDGER_PROMPT[2]
        return ret


class promptChat:
    """
    用于多轮对话生成的 Prompt 管理类
    """

    def generate_user_init_prompt(self, background: str, preference: str, question: str) -> str:
        """
        生成用户的初始系统提示词

        Args:
            background: 场景设定
            preference: 用户偏好
            question: 核心问题（从 backgrounds.json 中读取）
        """
        ret = USER_INIT_PROMPT[0] + background + USER_INIT_PROMPT[1] + \
              preference + USER_INIT_PROMPT[2] + question + USER_INIT_PROMPT[3]
        return ret

    def generate_user_followup_prompt(self, question: str) -> str:
        """
        生成用户追问的系统提示词（带话题约束）

        Args:
            question: 核心问题，用于约束后续对话不偏题
        """
        return USER_FOLLOWUP_PROMPT_CONSTRAINED[0] + question + USER_FOLLOWUP_PROMPT_CONSTRAINED[1]

    def generate_assistant_init_prompt(self, topics: str, definition: str, goal: str, strategy: str,
                                       background: str, strategy_control: str) -> str:
        """
        生成助手的初始系统提示词
        """
        ret = ASSISTANT_INIT_PROMPT[0] + topics + ASSISTANT_INIT_PROMPT[1] + definition + \
              ASSISTANT_INIT_PROMPT[2] + goal + ASSISTANT_INIT_PROMPT[3] + strategy + \
              ASSISTANT_INIT_PROMPT[4] + background + ASSISTANT_INIT_PROMPT[5] + strategy_control + \
              ASSISTANT_INIT_PROMPT[6]
        return ret

    def generate_assistant_followup_prompt(self) -> str:
        """
        生成助手追问的系统提示词
        """
        return ASSISTANT_FOLLOWUP_PROMPT

    def generate_judger_prompt(self, history: list) -> str:
        """
        生成对话质量判断的提示词
        """
        ret = CONTINUIITY_JUDGER_PROMPT[0] + json.dumps(history, ensure_ascii=False, indent=2) + \
              CONTINUIITY_JUDGER_PROMPT[1]
        return ret


if __name__ == "__main__":
    prompt_gen = promptGenerator()
    prompt_gen.set_test(test=True, n=2)

    # 测试场景解释层
    scene_data = SCENE_DATA["Task_Completion"]
    theme_data = scene_data["themes"][0]

    scene_prompt = prompt_gen.generate_scene_interpretation_prompt(
        topic=scene_data["topics"],
        definition=scene_data["definition"],
        theme=theme_data["theme"],
        subtopic=theme_data["subtopics"][0]["name"]
    )
    print("=== 场景解释层 Prompt ===")
    print(scene_prompt[:500])

    # 测试背景生成
    it = list(prompt_gen.generate_all_background_prompt())
    logger.success(f"Generated {len(it)} prompts")