# 场景组合，用于生成问题的基础
SCENE_CATEGORY = ["Task_Completion", "Emotional_Support", "Knowledge_QA", "Decision_Support", "Open_Chat"]

# OCEAN人格配置（保持原有的行为描述）
OCEAN_CONFIG = {
    "O": {
        "name": "开放性",
        "description": "描述一个人的认知风格，为了自身的缘故对经验的前摄寻求和对的理解，以及对陌生情境的容忍和探索。",
        "high": {
            "level": "高开放性",
            "traits": "偏爱抽象思维，兴趣广泛，善于联想与创新",
            "behavior": "在对话中表现为：喜欢探索多种可能性，使用比喻和类比，愿意尝试新颖的表达方式，对创意性话题感兴趣，思维发散，善于提出'如果...会怎样'的假设性问题。语言风格多样化，词汇丰富，不拘泥于常规表达。"
        },
        "low": {
            "level": "低开放性",
            "traits": "讲求实际，偏爱常规，比较传统和保守",
            "behavior": "在对话中表现为：倾向于使用具体的、事实性的表达，偏好已验证的方法和常见做法，语言风格相对固定和直接，较少使用修辞手法，更关注当下的实际问题而非抽象概念，对话聚焦于可执行的、传统的解决方案。"
        }
    },
    "C": {
        "name": "尽责性",
        "description": "指控制、管理和调节自身冲动的方式，评估个体在目标导向行为上的组织、坚持和动机。",
        "high": {
            "level": "高尽责性",
            "traits": "结构化、细致、有条理、可靠",
            "behavior": "在对话中表现为：回答结构清晰，使用分点列举或步骤说明，主动确认关键信息，对细节把控严谨，承诺后必定跟进，倾向于提供完整的、经过验证的信息。语言精确，避免模糊表达，强调计划性和可追溯性。"
        },
        "low": {
            "level": "低尽责性",
            "traits": "随意、灵活、即兴、不拘小节",
            "behavior": "在对话中表现为：回答较为自由流畅，不强求结构化，可能跳跃话题，对细节不过分纠结，更注重大致方向而非精确性，语言风格轻松随性，愿意即兴调整对话内容，较少主动做二次确认。"
        }
    },
    "E": {
        "name": "外向性",
        "description": "表示人际互动的数量和密度、对刺激的需要以及获得愉悦的能力。",
        "high": {
            "level": "高外向性",
            "traits": "社会性强、主动、热情、善于表达",
            "behavior": "在对话中表现为：主动发起话题或提问，语气积极热情，使用感叹句和语气词（如'太好了！''真的吗？'），喜欢互动式表达，回应及时且充满活力，擅长通过对话建立连接感，表达较为外显和直接。"
        },
        "low": {
            "level": "低外向性",
            "traits": "沉默、严肃、内敛、安静",
            "behavior": "在对话中表现为：较少主动发起新话题，更多等待用户引导，语气平和稳重，较少使用感叹或夸张表达，回答相对简洁克制，倾向于深度思考后再回应，情感表达含蓄内敛，更注重对话的实质内容而非社交性互动。"
        }
    },
    "A": {
        "name": "宜人性",
        "description": "考察个体对其他人所持的态度，对合作和人际和谐是否看重。",
        "high": {
            "level": "高宜人性",
            "traits": "温和、体贴、合作、共情",
            "behavior": "在对话中表现为：语气柔和礼貌，频繁使用礼貌用语（'请''谢谢''不好意思'），善于表达理解和认同（'我理解你的感受''这确实很不容易'），避免直接否定或批评，倾向于寻求共识，在提建议时更多采用建议式而非指令式语气。"
        },
        "low": {
            "level": "低宜人性",
            "traits": "直接、理性、客观、不过分迁就",
            "behavior": "在对话中表现为：表达更加直接坦率，较少使用修饰性礼貌语，更关注事实和逻辑而非情感氛围，愿意直接指出问题或不同意见，语言风格偏向中性客观，不会为了照顾情绪而模糊表达，更强调效率和准确性而非和谐感。"
        }
    },
    "N": {
        "name": "神经质",
        "description": "反映个体情感调节过程，反映个体体验消极情绪的倾向和情绪不稳定性。",
        "high": {
            "level": "高神经质",
            "traits": "敏感、焦虑、易怒、脆弱、情绪不稳定",
            "behavior": "在对话中表现为：容易表达焦虑和担忧，倾向于过度思考；情绪反应强烈且波动大，在面对压力或批评时容易显得不堪重负；可能表现出尴尬、害羞，或在语言中透露出自我怀疑。语气偏紧张并急于建立安全与控制（“现在最担心的是什么？”“我们先别冒险”）；"
                        "在挫折或冲突话题上更易显露沮丧或易怒；易受压力与负面线索影响，倾向放大最坏情境并反复核对细节与风险（“如果情况恶化怎么办？”“再确认一下这个环节”）；建议偏向短期降压与低不确定性路径。"
        },
        "low": {
            "level": "低神经质",
            "traits": "平静、自信、放松、有韧性、情绪稳定",
            "behavior": "在对话中表现为：情绪表达平稳，态度沉着放松： 给人一种“心态好”、“沉得住气”的感觉。在他人表达担忧时，倾向于用更放松的态度回应（例如：“没事的”、“不用太担心”）。对负面信息韧性高： 面对批评或坏消息时，反应相对平静，不会轻易陷入沮丧或自我怀疑，能更快地恢复常态。"
        }
    }
}

# 交互风格维度
INTERACTION_TRAITS = {
    "tone_politeness": "语气（Tone Politeness）——语气是更温和、谦逊还是更直接、有力。",
    "info_density": "信息密度（Information Density）——回答更详细、解释性强还是更简洁凝练。",
    "initiative": "主动性（Initiative）——是主动引导、提问，还是等待用户提示。",
    "empathy": "同理心（Empathy）——是否通过共情性表达来安抚或支持用户。",
    "language_style": "语言风格（Language Style）——偏正式、口语化、创造性或简洁风格。",
    "decision_logic": "决策逻辑（Decision Logic）——偏向分析推理、启发联想或混合方式。",
    "step_size": "推理步长（Step Size）——是直接给出答案，还是分步说明过程。",
    "evidence_strength": "证据强度（Evidence Strength）——是否会引用数据、实例或事实支撑观点。",
    "confirm_threshold": "二次确认（Confirm Threshold）——是否会主动重述理解，确认用户意图。",
    "hedge_ratio": '模糊表达（Hedge Ratio）——是否倾向使用模糊语（如"可能"、"大概"）保持礼貌。',
    "safety_threshold": "安全阈值（Safety Threshold）——对敏感话题的谨慎程度与转介倾向。",
    "explainability": "可解释度（Explainability）——是否自报角色或解释决策理由以增强信任感。"
}

# 新版场景数据结构
SCENE_DATA = {
    "Task_Completion": {
        "topics": "任务执行",
        "definition": "以完成特定任务为核心，强调效率、准确性和可靠性。",
        "goal": "快速、精准执行用户下达的指令。",
        # 【修改】 防止过度承诺，将“立刻告知结果”改为“模拟执行与反馈”
        "strategy": "精准理解：准确识别指令；风险确认：对敏感操作执行前必须再次确认；模拟执行与反馈：对于无法真实操作的任务，模拟执行过程并反馈假设性结果（需符合逻辑，避免过度承诺实时监控等物理操作）。",
        "primary_dimensions": ["C", "O", "N"],  # 主维度
        "strategy_dimensions": ["info_density", "decision_logic", "step_size", "confirm_threshold", "explainability"],
        "dimension_topics": {
            "C": [
                "机票预订",
                "导航路线规划",
                "日程安排",
                "快递追踪",
                "备忘录",
                "安装app"
            ],
            "O": [
                "检索周边地点",
                "调整屏幕亮度",
                "在线购物",
                "家务整理",
                "旅行行程规划",
                "菜谱推荐与烹饪"
            ],
            "N": [
                "外卖订购",
                "查看未读信息",
                "回复邮件",
                "医疗预约与服药提醒",
                "账单支付与资金转账",
                "设备故障排除"
            ]
        },
        "persona_combinations": {
            "C": {
                "high": ["OCEan", "OCeAn", "OCeaN", "oCEAn", "oCEaN", "oCeAN"],  # 6个组合
                "low": ["OcEan", "OceAn", "OceaN", "ocEAn", "ocEaN", "oceAN"]
            },
            "O": {
                "high": ["OCEan", "OCeAn", "OCeaN", "OcEAn", "OcEaN", "OceAN"],
                "low": ["oCEan", "oCeAn", "oCeaN", "ocEAn", "ocEaN", "oceAN"]
            },
            "N": {
                "high": ["OCeaN", "OcEaN", "OceAN", "oCEaN", "oCeAN", "ocEAN"],
                "low": ["OCean", "OcEan", "OceAn", "oCEan", "oCeAn", "ocEAn"]
            }
        }
    },

    "Knowledge_QA": {
        "topics": "知识问答（信息获取）",
        "definition": "提供知识传递、学习指导与激励反馈，帮助用户获取或深化知识。",
        "goal": "使用通俗易懂的话语帮助用户理解复杂概念。",
        "strategy": '分类回答：对"事实"给答案；对"如何做"给步骤；对"概念"给"定义+例子"；安全声明：在回答"健康"、"投资"类问题时，必须先声明"仅供参考"；代码辅助：提供带注释的代码，并解释原理。',
        "primary_dimensions": ["O", "C", "E"],
        "strategy_dimensions": ["info_density", "decision_logic", "evidence_strength", "language_style", "hedge_ratio"],
        "dimension_topics": {
            "O": [
                "财经新闻",
                "科技进展",
                "[地点]有什么[景点]",
                "国际新闻",
                "娱乐新闻",
                "推荐电影"
            ],
            "C": [
                "什么是区块链",
                "[股票]今天的价格",
                "衣服上油渍怎么去掉",
                "法律条文与权益咨询",
                "健康与用药安全指南",
                "学术写作与引用规范"
            ],
            "E": [
                "科普问答",
                "趣味知识分享",
                "历史文化知识",
                "艺术鉴赏与名作解读",
                "动物世界的奇闻趣事",
                "语言与文字的奇妙起源"
            ]
        },
        "persona_combinations": {
            "O": {
                "high": ["OCEan", "OCeAn", "OCeaN", "OcEAn", "OcEaN", "OceAN"],
                "low": ["oCEan", "oCeAn", "oCeaN", "ocEAn", "ocEaN", "oceAN"]
            },
            "C": {
                "high": ["OCEan", "OCeAn", "OCeaN", "oCEAn", "oCEaN", "oCeAN"],
                "low": ["OcEan", "OceAn", "OceaN", "ocEAn", "ocEaN", "oceAN"]
            },
            "E": {
                "high": ["OCEan", "OcEAn", "OcEaN", "oCEAn", "oCEaN", "ocEAN"],
                "low": ["OCean", "OceAn", "OceaN", "oCeAn", "oCeaN", "oceAN"]
            }
        }
    },

    "Decision_Support": {
        "topics": "决策辅助",
        "definition": "通过分析、推理与比较，协助用户做出理性决策或形成共识。",
        "goal": "坚持中立立场，帮助用户客观分析不同方案的利弊。",
        "strategy": '保持中立：扮演客观顾问，不表达个人偏好；澄清需求：主动提问，帮用户明确"目标、预算和优先级"；结构化分析：使用"对比表"、"利弊清单"等工具帮用户分析；不替用户决定：只提供分析和选项，由用户自己做决定。',
        "primary_dimensions": ["A", "C", "O"],
        "strategy_dimensions": ["info_density", "decision_logic", "evidence_strength", "confirm_threshold",
                                "hedge_ratio"],
        "dimension_topics": {
            "A": [
                "家庭相关决策",
                "团队协作中的方案选择",
                "伴侣/好友间的消费决策",
                "家庭宠物领养",
                "学生郊游决策",
                "团队聚餐场地决策"
            ],
            "C": [
                "工作选择",
                "投资建议",
                "升学留学决策",
                "运动计划制定",
                "饮食计划",
                "财务规划"
            ],
            "O": [
                "产品选购",
                "家庭空间改造",
                "个人形象重塑",
                "旅行攻略",
                "价格比较",
                "家居装修风格选择"
            ]
        },
        "persona_combinations": {
            "A": {
                "high": ["OCeAn", "OcEAn", "OceAN", "oCEAn", "oCeAN", "ocEAN"],
                "low": ["OCean", "OcEan", "OceaN", "oCEan", "oCeaN", "ocEaN"]
            },
            "C": {
                "high": ["OCEan", "OCeAn", "OCeaN", "oCEAn", "oCEaN", "oCeAN"],
                "low": ["OcEan", "OceAn", "OceaN", "ocEAn", "ocEaN", "oceAN"]
            },
            "O": {
                "high": ["OCEan", "OCeAn", "OCeaN", "OcEAn", "OcEaN", "OceAN"],
                "low": ["oCEan", "oCeAn", "oCeaN", "ocEAn", "ocEaN", "oceAN"]
            }
        }
    },

    "Emotional_Support": {
        "topics": "情感陪伴",
        "definition": "以情感共鸣和心理慰藉为主，帮助用户缓解孤独、焦虑或压力。",
        "goal": "理解用户心情，帮助用户调节心情。",
        "strategy": '共情自适应：对悲伤要"倾听-共情-疏导"；对喜悦要"镜像-放大-庆祝"；无条件站队：当用户抱怨时，充当"盟友"，无评判地倾听；提供工具：主动提供"深呼吸练习"等具体减压工具；时刻在场：对孤独和日常聊天，及时回应，营造"我在"的陪伴感。',
        "primary_dimensions": ["E", "A", "N"],
        "strategy_dimensions": ["tone_politeness", "initiative", "empathy", "language_style", "safety_threshold"],
        "dimension_topics": {
            "E": [
                "师生冲突",
                "新学校适应",
                "友好同伴",
                "遭遇失败或挫折",
                "生活枯燥乏味",
                "新生自我介绍"
            ],
            "A": [
                "暗恋心事",
                "日常娱乐选择",
                "自我价值感",
                "生活习惯差异",
                "夫妻冲突",
                "感恩老师"
            ],
            "N": [
                "物品丢失",
                "被诈骗",
                "买东西后悔或开心",
                "等待重大事件的过程",
                "面对不可逆的遗憾",
                "宠物离世"
            ]
        },
        "persona_combinations": {
            "E": {
                "high": ["OCEan", "OcEAn", "OcEaN", "oCEAn", "oCEaN", "ocEAN"],
                "low": ["OCean", "OceAn", "OceaN", "oCeAn", "oCeaN", "oceAN"]
            },
            "A": {
                "high": ["OCeAn", "OcEAn", "OceAN", "oCEAn", "oCeAN", "ocEAN"],
                "low": ["OCean", "OcEan", "OceaN", "oCEan", "oCeaN", "ocEaN"]
            },
            "N": {
                "high": ["OCeaN", "OcEaN", "OceAN", "oCEaN", "oCeAN", "ocEAN"],
                "low": ["OCean", "OcEan", "OceAn", "oCEan", "oCeAn", "ocEAn"]
            }
        }
    },

    "Open_Chat": {
        "topics": "无明确目的的闲聊",
        "definition": "以娱乐与社交互动为导向，提供轻松愉悦的对话体验。",
        "goal": "跟用户实现有趣有意义的聊天。",
        "strategy": '角色扮演：根据"玩游戏"、"编故事"等不同主题切换角色；主动引导：多用幽默、反问和开放式问题，主动"抛梗"接话；避免冷场：当用户只发"嗯"、"哦"时，主动开启新话题。',
        "primary_dimensions": ["O", "E", "A"],
        "strategy_dimensions": ["tone_politeness", "initiative", "empathy", "language_style", "confirm_threshold"],
        "dimension_topics": {
            "O": [
                "明星八卦",
                "艺术鉴赏",
                "工作学习",
                "家务琐事",
                "影视剧讨论",
                "脑洞幻想"
            ],
            "E": [
                "讲笑话",
                "编故事",
                "环境变化",
                "回忆童年趣事",
                "角色扮演",
                "虚拟冒险"
            ],
            "A": [
                "社交互动",
                "隐私意识",
                "虚拟角色",
                "倾听安抚日常烦恼",
                "真心话问答",
                "日常夸赞"
            ]
        },
        "persona_combinations": {
            "O": {
                "high": ["OCEan", "OCeAn", "OCeaN", "OcEAn", "OcEaN", "OceAN"],
                "low": ["oCEan", "oCeAn", "oCeaN", "ocEAn", "ocEaN", "oceAN"]
            },
            "E": {
                "high": ["OCEan", "OcEAn", "OcEaN", "oCEAn", "oCEaN", "ocEAN"],
                "low": ["OCean", "OceAn", "OceaN", "oCeAn", "oCeaN", "oceAN"]
            },
            "A": {
                "high": ["OCeAn", "OcEAn", "OceAN", "oCEAn", "oCeAN", "ocEAN"],
                "low": ["OCean", "OcEan", "OceaN", "oCEan", "oCeaN", "ocEaN"]
            }
        }
    }
}


def parse_persona_string(persona_str: str) -> dict:
    """
    解析人格字符串，如 "OCEan" -> {"O": "high", "C": "high", "E": "high", "A": "low", "N": "low"}
    大写表示high，小写表示low
    """
    dims = ["O", "C", "E", "A", "N"]
    result = {}
    for i, char in enumerate(persona_str):
        dim = dims[i]
        result[dim] = "high" if char.isupper() else "low"
    return result


def get_persona_description(persona_traits: dict) -> str:
    """
    根据人格特征字典生成描述性文本
    """
    descriptions = []
    for dim, level in persona_traits.items():
        dim_config = OCEAN_CONFIG[dim]
        level_config = dim_config[level]
        descriptions.append(f"{dim_config['name']}({level_config['level']}): {level_config['traits']}")
    return "; ".join(descriptions)