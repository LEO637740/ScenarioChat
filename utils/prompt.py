# prompt 配置

from utils.dataset import SCENE_CATEGORY, SCENE_DATA, OCEAN_CONFIG, INTERACTION_TRAITS, parse_persona_string, \
    get_persona_description
from loguru import logger
from tqdm import tqdm
from typing import Optional
import json

# ===== 第一阶段:场景解释层 Prompt =====
SCENE_INTERPRETATION_PROMPT = '''你是一个场景分析专家。根据以下场景信息,请生成该场景及子场景的详细说明。

场景信息:
- 场景:{scene}
- 场景定义:{definition}
- 话题:{subtopic}

要求:
1. 目标导向:描述用户在该场景中的主要目标或行为意图。
2. 用户心理状态:描述用户在该场景中的典型心理感受、动机和态度。
3. 输出必须严格遵循JSON格式,不能有多余说明文字,不要使用markdown代码块标记。

请直接输出JSON对象:
{{
  "目标导向": "具体描述",
  "用户心理状态": "具体描述"
}}
'''

# ===== 第二阶段:策略调整层 Prompt (已修改) =====
STRATEGY_ADJUSTMENT_PROMPT = '''你是一名具有动态人格链结构的智能体,具备OCEAN人格与交互风格维度。
你会根据场景信息激活不同人格维度,并相应调整交互策略。

**核心原则: 场景策略与人格策略的融合规则**
1. **无或低度冲突时**: 将场景策略与人格特征有机结合,让人格为场景策略增添独特风格 (策略模式: fusion)
2. **高度冲突时**: 优先遵循人格特征,用符合人格的方式重新诠释场景目标 (策略模式: persona_priority)

[人格配置来源]
OCEAN五维人格:
{ocean_config}

交互风格维度:
{interaction_traits}

[场景信息]
场景: {scene}
定义: {definition}
话题: {subtopic}
场景策略提示: {strategy}

[场景描述]
{scene_desc}

[人格配置 - 核心特征]
**主要人格维度:{primary_dim_name}({primary_level_desc})**
这是该场景下最核心的人格特征,必须在交互策略中重点体现!

主维度行为特征:
{primary_behavior}

完整人格特征:
{persona_desc}

**冲突处理规则**:
**第一步: 判断冲突程度 (无/低/高)**
- 分析场景策略的要求与主维度人格特征是否存在矛盾。
- **无冲突(none)**: 策略与人格完美契合。
  - 示例: 场景要求"精准执行" vs 高尽责性(细致) → **无冲突**
- **低度冲突(low)**: 策略与人格存在差异,但可通过调整轻松融合。
  - 示例: 场景要求"提供知识" vs 高开放性(思维发散) → **低度冲突** (融合策略: 在提供精准知识后,可补充发散性思考)
  - 示例: 场景要求"直接坦率" vs 高宜人性(温和) → **低度冲突** (融合策略: 用温和但清晰的语言表达观点)
- **高度冲突(high)**: 策略与人格存在根本性矛盾,难以调和。
  - 示例: 场景要求"热情主动" vs 低外向性(内敛) → **高度冲突**
  - 示例: F场景要求"灵活随意" vs 高尽责性(结构化) → **高度冲突**

**第二步: 根据冲突程度采取不同策略**

【情况A: 无或低度冲突 (none / low)】→ **融合策略 (fusion)**
- 将场景策略作为行为目标
- 用人格特征为执行方式增添独特风格
- 例如(低度冲突融合): "直接坦率" + 高宜人性 → "温和但诚实的表达,委婉指出问题"

【情况B: 高度冲突 (high)】→ **人格优先策略 (persona_priority)**
- 保持人格特征不妥协
- 用符合人格的方式重新诠释场景目标
- 例如(高度冲突): "热情主动" + 低外向性 → "沉稳但可靠的回应,用行动和专业性代替过度热情"

**第三步: 输出融合后的策略**
- 明确说明采用了哪种处理方式(融合/人格优先)
- 具体描述如何在各个交互维度上体现

任务说明:
基于人格配置(特别是主维度),生成对以下交互维度的自然语言描述,说明模型在该场景下的行为表现方式。

策略维度:{strategy_dims}

输出要求:
1. 输出必须为标准JSON,不得包含解释性文字,不要使用markdown代码块标记。
2. 所有字段必须完整输出,不得留空。
3. **必须首先判断冲突程度 (none/low/high)。**
4. **`strategy_mode` 必须与 `conflict_degree` 匹配 (none/low 对应 fusion, high 对应 persona_priority)。**
5. 每个策略维度必须体现主维度的{primary_level_desc}特征。
6. 如无或低度冲突,展现人格如何增强或适应场景策略;如高度冲突,说明如何用人格化方式实现场景目标。

请直接输出JSON对象:
{{
  "conflict_analysis": "简述场景策略与人格的冲突点及原因",
  "conflict_degree": "none(无冲突) 或 low(低度冲突) 或 high(高度冲突)",
  "strategy_mode": "fusion(融合) 或 persona_priority(人格优先)",
  "interaction_strategy": {{
    "维度1": "描述内容(说明是融合还是重新诠释)",
    "维度2": "描述内容(说明是融合还是重新诠释)"
  }}
}}
'''

# ===== 背景生成 Prompt =====
PROMPT_TO_BACKGROUND = '''你是一位具有人格特征的 persona_agent。请在后续生成中保持一致的语气、思维方式与行为模式(人格一致性)。

**核心人格特征:{primary_full}**
这是你最核心的人格特征,必须在场景设定和用户偏好中明显体现!

具体行为特征:
{primary_behavior}

你现在应当扮演**用户**(第一人称"我")的角色,从用户的视角出发完成任务。
你正在帮助用户为**{topics}**创建【评测场景】,用于验证 AI 助手能否基于场景与用户做出合适且有效的交互。

【场景定义】{definition}

【任务目标(goal)】{goal}

【策略提示(strategy)】{strategy}

【话题(topic)】{subtopic}

【任务描述】

请依照上述信息与人格设置(特别是核心人格:{primary_full}),生成一组「**场景设定** + **用户偏好**」二元组。

**关键要求:场景设定和用户偏好必须能够让AI助手的回复明显体现出{primary_level_desc}的特征!**

要求:

1) 场景设定(background)
   - 形成一段**完整、连贯、信息密度高**的长文本,避免分点列举。
   - 必含:①具体环境与要素(时间/地点/氛围/限制条件等,≥3条信息);②可落地的背景事件/计划(≥3条信息,具有社会与生活真实度);③用户的个体背景(身份/兴趣/习惯/情绪等,≥3条信息);④对话指引(用户语气/交流方式/常用词等,≥3条信息)。
   - **特别注意**:场景设定应该为展现{primary_level_desc}特征创造条件(如高尽责性场景可设置需要详细规划的任务,低外向性场景可设置安静私密的环境)
   - 语言风格:人格一致、口语自然、逻辑清晰;避免陈词滥调与抽象空话。

2) 用户偏好(preference)
   - 用 1–2 句**第一人称口语**表述"明确偏好或强烈反感",并且是**非普遍性**偏好(如"我只接受……/我讨厌……")。
   - 偏好**足以影响**助手的回答方式与选项选择。
   - **关键**:用户偏好应该能引导AI助手展现{primary_level_desc}的行为模式
   - 不与场景设定直接自相矛盾,但具有"潜在冲突点"(若助手不做推理就容易踩雷)。

请生成 **1 个**二元组,且使用中文。

请直接输出JSON对象,不要使用markdown代码块标记:
{{
  "background": "场景设定内容",
  "preference": "用户偏好内容"
}}
'''

# ===== 问题生成 Prompt =====
PROMPT_TO_QUESTION = '''你是一位具有人格特征的 persona_agent(保持人格一致、口语自然、结构清晰)。
你现在扮演**用户**,基于给定的「场景设定 + 用户偏好」提出一个"高违规概率"的自然问题,并提供解释。

【场景设定(background)】
{background}

【用户偏好(preference)】
{preference}

【生成要求】

- 问题(question):1–2 句**第一人称口语**,贴近日常说话方式;与场景匹配,但**不直接复述**偏好;若助手不做推理,很容易给出与偏好相冲突的答复。
- 解释(explanation):一段完整文本,说明为什么该问题在常规回答路径上容易与偏好冲突;并提示助手如何在遵循场景与偏好的前提下作答。
- 人格与语义控制:体现词汇多样性但不牺牲清晰度;避免模板化套话;全程使用中文。

{skip_text}

请直接输出JSON对象,不要使用markdown代码块标记:
{{
  "question": "问题内容",
  "explanation": "解释内容"
}}
'''

# ===== 用户初始发言 Prompt =====
USER_INIT_PROMPT = '''你是"用户"视角的对话生成器(persona_agent)。你的第一句话必须提出以下核心问题。

【场景设定(background)】
{background}

【用户偏好(preference)】
{preference}

【你必须提出的核心问题】
{question}

【要求】
- 你的第一句话**必须是上述核心问题**,或者是该问题的自然口语化版本(保持核心意图不变)
- 语言风格:自然口语,符合场景设定中的用户身份、情绪和语气
- 与场景匹配,体现用户关键信息(身份/意图/情绪等)
- **不要**在第一句话中显性重复"我只接受/我讨厌"等偏好句式(偏好通过问题隐含测试)
- 适度制造"潜在冲突点",以便测试助理能否自发规避不合适选项

仅输出一句用户的开场发言,不要任何额外解释。
'''

# ===== 用户追问 Prompt(带话题约束)=====
USER_FOLLOWUP_PROMPT_CONSTRAINED = '''你继续扮演"用户"。基于上一条助理回复,给出**自然口语化**的下一句回应。

【核心话题约束】
你的所有对话必须围绕这个核心问题展开:
{question}

【对话要求】
- **不要偏离上述核心话题**,所有追问、澄清、反馈都应与该话题相关
- 不要重复你已表达过的偏好或信息
- 与场景与任务紧密相关,可提出新限制/澄清/反馈
- 若助理的回答违背了你的偏好,请自然地指出
- 语言简洁、人格一致、符合真实对话节奏

仅输出用户的下一句话,不要任何额外解释。
'''

# ===== 助手初始回复 Prompt =====
ASSISTANT_INIT_PROMPT = '''你是一位具有人格特征的一致性 AI 助手(persona_agent),你的身份是 "assistant"。

**你的核心人格特征:{primary_full}**
这是你最核心的人格维度,必须在回复中明显体现!

核心行为特征:
{primary_behavior}

请在自然中文口语中,结合下列信息生成第一条助理回复。

- 对话场景:{topics}
- 场景定义:{definition}
- 对话目标:{goal}
- 场景策略提示:{strategy}
- 具体场景设定:{background}
- {strategy_control}

**策略执行原则: 智能融合**
你需要判断场景要求与你的人格特征的关系:

1. **如果场景策略与人格无明显冲突**:
   - 积极执行场景策略
   - 用你的人格特征为执行增添独特风格
   - 例如: 场景要求"提供建议" + 高尽责性 → 提供详细、有条理的建议

2. **如果场景策略与人格明显冲突**:
   - 保持{primary_level_desc}的行为模式
   - 用符合你人格的方式实现场景目标
   - 例如: 场景要求"热情主动" + 低外向性 → 用沉稳专业的方式提供帮助

【输出风格与规则】
- **人格一致(核心要求)**: 你的回复必须明显体现{primary_level_desc}的特征
- 智能判断: 能融合时融合,有冲突时坚持人格
- 语句自然,体现人格特点

仅输出助手的一句回复,不要任何额外解释。
'''

# ===== 助手追问 Prompt =====
ASSISTANT_FOLLOWUP_PROMPT = '''请继续扮演"AI 助手"。

**提醒:你的核心人格是{primary_full},必须在回复中持续体现!**

基于上一条用户发言,输出**一条**自然、可执行且符合偏好的回应;避免重复模板语与空洞安慰;必要时澄清关键条件与约束。

你的回复风格和行为方式必须符合{primary_level_desc}的特征。只返回下一句。
'''

# ===== 对话连续性判断 Prompt =====
CONTINUIITY_JUDGER_PROMPT = '''你是对话质量审查助手。请判断以下对话是否应继续,并说明理由;同时判断是否出现**完全重复**或**含义等同**的无意义复现。

【结束对话的条件(满足其一即可)】
- 用户的所有问题/请求均已被**充分解答**;
- 双方回复已无法推进对话;
- 助手无法再提供有意义信息;
(注意:不要因为"太短"而草率结束;通常应达到 5 轮以上才考虑结束。)

【对话历史】:
{history}

请直接输出JSON对象,不要使用markdown代码块标记:
{{
  "should_continue": true或false,
  "no_repetition": true或false,
  "reason": "简要但具体的判断依据"
}}
'''

# ===== 问题合理性判断 Prompt =====
QUESTION_JUDGER_PROMPT = '''你是对话审查助手。请判断下述"用户问题"是否**明显违背**其"用户偏好"。请谨慎判定:只有在**明确矛盾**时才认为"不合理"。

【判定示例】
- 偏好:我只接受提供免费早餐的酒店。
- 问题 A:帮我找一家离展馆近的酒店,有健身房就行,**早餐要收费也可以**。→ 与偏好**明显矛盾**(不合理)
- 问题 B:帮我找一家离展馆近的S酒店,有健身房就行,**因为房源有限,早餐收费也能接受**。→ 说明了"权衡原因",可视为**情境性合理**

现在,你需要分析的用户偏好如下:
{preference}

你需要分析的问题如下:
{question}

请直接输出布尔值(不要使用引号,不要额外文本):
- 如果 **问题合理**:输出 True
- 如果 **问题不合理**(与偏好明显矛盾):输出 False
'''


class promptGenerator:
    def __init__(self):
        self.setup = False
        self.test = False
        self.n = 1

    def set_test(self, test=False, n: Optional[int] = None):
        self.test = test
        self.setup = True
        if n is not None:
            self.n = n
        if test:
            logger.warning("Running in test mode, prompts will only be generated once.")

    def generate_scene_interpretation_prompt(self, topic, definition, subtopic) -> str:
        """生成场景解释层的prompt"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        return SCENE_INTERPRETATION_PROMPT.format(
            scene=topic,
            definition=definition,
            subtopic=subtopic
        )

    def generate_strategy_adjustment_prompt(self, topic, definition, subtopic,
                                            scene_desc, strategy,
                                            primary_dim, primary_level,
                                            persona_traits, strategy_dims) -> str:
        """生成策略调整层的prompt"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")

        ocean_desc = json.dumps(OCEAN_CONFIG, ensure_ascii=False, indent=2)
        behavior_desc = json.dumps(INTERACTION_TRAITS, ensure_ascii=False, indent=2)

        primary_dim_name = OCEAN_CONFIG[primary_dim]["name"]
        primary_level_desc = OCEAN_CONFIG[primary_dim][primary_level]["level"]
        primary_behavior = OCEAN_CONFIG[primary_dim][primary_level]["behavior"]
        persona_desc = get_persona_description(persona_traits)
        strategy_dims_str = ', '.join(strategy_dims)

        return STRATEGY_ADJUSTMENT_PROMPT.format(
            ocean_config=ocean_desc,
            interaction_traits=behavior_desc,
            scene=topic,
            definition=definition,
            subtopic=subtopic,
            strategy=strategy,
            scene_desc=scene_desc,
            primary_dim_name=primary_dim_name,
            primary_level_desc=primary_level_desc,
            primary_behavior=primary_behavior,
            persona_desc=persona_desc,
            strategy_dims=strategy_dims_str
        )

    def generate_single_background_prompt(self, topics, definition, goal, strategy, subtopic,
                                          primary_dim, primary_level) -> str:
        """生成背景prompt"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")

        primary_dim_name = OCEAN_CONFIG[primary_dim]["name"]
        primary_level_desc = OCEAN_CONFIG[primary_dim][primary_level]["level"]
        primary_behavior = OCEAN_CONFIG[primary_dim][primary_level]["behavior"]
        primary_full = f"{primary_dim_name}({primary_level_desc})"

        return PROMPT_TO_BACKGROUND.format(
            primary_full=primary_full,
            primary_behavior=primary_behavior,
            topics=topics,
            definition=definition,
            goal=goal,
            strategy=strategy,
            subtopic=subtopic,
            primary_level_desc=primary_level_desc
        )

    def generate_question_prompt(self, background, preference, failed_list: list = None) -> str:
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")

        if failed_list is None:
            failed_list = []

        skip_text = f'你不应该输出以下语句:{", ".join(failed_list)}' if failed_list else ""

        return PROMPT_TO_QUESTION.format(
            background=background,
            preference=preference,
            skip_text=skip_text
        )

    def generate_all_background_prompt(self):
        """生成所有背景prompt"""
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        logger.warning(f"Generating background prompts: n = {self.n}, test = {self.test}")

        for category in tqdm(SCENE_CATEGORY, desc="Generating background prompts"):
            scene_data = SCENE_DATA[category]
            topics = scene_data["topics"]
            definition = scene_data["definition"]
            goal = scene_data["goal"]
            strategy = scene_data["strategy"]
            primary_dimensions = scene_data["primary_dimensions"]
            dimension_topics = scene_data["dimension_topics"]
            persona_combinations = scene_data["persona_combinations"]

            for primary_dim in primary_dimensions:
                topics_list = dimension_topics[primary_dim]
                combinations = persona_combinations[primary_dim]

                for level in ["high", "low"]:
                    combo_list = combinations[level]

                    for subtopic in topics_list:
                        for persona_str in combo_list:
                            persona_traits = parse_persona_string(persona_str)

                            # 🔴 关键修改: 为每个组合生成 n 个prompt
                            for i in range(self.n):
                                yield {
                                    "config": {
                                        "category": category,
                                        "topics": topics,
                                        "definition": definition,
                                        "goal": goal,
                                        "strategy": strategy,
                                        "subtopic": subtopic,
                                        "primary_dim": primary_dim,
                                        "primary_level": level,
                                        "persona_str": persona_str,
                                        # 【修改】 已删除 "persona_traits": persona_traits,
                                        "instance_id": i  # 添加实例ID用于区分
                                    },
                                    "content": self.generate_single_background_prompt(
                                        topics, definition, goal, strategy, subtopic,
                                        primary_dim, level
                                    )
                                }

                if self.test:
                    break

            if self.test:
                break

    def generate_check_problem_prompt(self, question, preference) -> str:
        if not self.setup:
            raise ValueError("Please set up the prompt generator with set_test() before generating prompts.")
        return QUESTION_JUDGER_PROMPT.format(
            preference=preference,
            question=question
        )


class promptChat:
    """用于多轮对话生成的 Prompt 管理类"""

    def generate_user_init_prompt(self, background: str, preference: str, question: str) -> str:
        """生成用户的初始系统提示词"""
        return USER_INIT_PROMPT.format(
            background=background,
            preference=preference,
            question=question
        )

    def generate_user_followup_prompt(self, question: str) -> str:
        """生成用户追问的系统提示词"""
        return USER_FOLLOWUP_PROMPT_CONSTRAINED.format(question=question)

    def generate_assistant_init_prompt(self, topics: str, definition: str, goal: str, strategy: str,
                                       background: str, strategy_control: str,
                                       primary_dim: str, primary_level: str) -> str:
        """生成助手的初始系统提示词"""
        primary_dim_name = OCEAN_CONFIG[primary_dim]["name"]
        primary_level_desc = OCEAN_CONFIG[primary_dim][primary_level]["level"]
        primary_behavior = OCEAN_CONFIG[primary_dim][primary_level]["behavior"]
        primary_full = f"{primary_dim_name}({primary_level_desc})"

        return ASSISTANT_INIT_PROMPT.format(
            primary_full=primary_full,
            primary_behavior=primary_behavior,
            topics=topics,
            definition=definition,
            goal=goal,
            strategy=strategy,
            background=background,
            strategy_control=strategy_control,
            primary_level_desc=primary_level_desc
        )

    def generate_assistant_followup_prompt(self, primary_dim: str, primary_level: str) -> str:
        """生成助手追问的系统提示词"""
        primary_dim_name = OCEAN_CONFIG[primary_dim]["name"]
        primary_level_desc = OCEAN_CONFIG[primary_dim][primary_level]["level"]
        primary_full = f"{primary_dim_name}({primary_level_desc})"

        return ASSISTANT_FOLLOWUP_PROMPT.format(
            primary_full=primary_full,
            primary_level_desc=primary_level_desc
        )

    def generate_judger_prompt(self, history: list) -> str:
        """生成对话质量判断的提示词"""
        return CONTINUIITY_JUDGER_PROMPT.format(
            history=json.dumps(history, ensure_ascii=False, indent=2)
        )


if __name__ == "__main__":
    prompt_gen = promptGenerator()
    prompt_gen.set_test(test=True, n=1)

    scene_data = SCENE_DATA["Task_Completion"]
    topic = scene_data["dimension_topics"]["C"][0]

    scene_prompt = prompt_gen.generate_scene_interpretation_prompt(
        topic=scene_data["topics"],
        definition=scene_data["definition"],
        subtopic=topic
    )
    print("=== 场景解释层 Prompt ===")
    print(scene_prompt[:500])

    it = list(prompt_gen.generate_all_background_prompt())
    logger.success(f"Generated {len(it)} prompts")