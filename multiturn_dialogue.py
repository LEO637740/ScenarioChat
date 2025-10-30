# 一个额外的多轮对话实现，字面意义的使用两个llm互相询问。
# 按照官网api教程使用assistant携带上下文实现记忆力机制。

import os
import sys
import json
import argparse
import threading
import time
import re

from http import HTTPStatus
from tqdm import tqdm
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

import dashscope
from dashscope import Generation
from dashscope.api_entities.dashscope_response import Role  # 角色常量

from utils.prompt import promptChat
from utils.duplication_check import get_existing_data, get_existng_ids

prompt_chat = promptChat()
existing_ids = set()

MAX_WORKERS = 8  # 总线程数
MAX_API_CONC = 16  # API并发数
MAX_RETRY = 10
SEMAPHORE = threading.Semaphore(MAX_API_CONC)


# --------------------------------------------------------------------------------------
# 通用 LLM 调用封装
# --------------------------------------------------------------------------------------
def _extract_content(resp: Any) -> str:
    """
    从 DashScope 的响应对象中抽取 assistant 内容。
    同时兼容 prompt / messages 两种调用形态。
    """
    if resp.status_code != HTTPStatus.OK:
        raise RuntimeError(f"DashScope error {resp.status_code}: {resp.message}")

    out = resp.output

    # ① prompt 方式返回纯字符串
    if isinstance(out, str):
        return out.strip()

    # ② messages 方式 result_format='message'，返回 dict
    if isinstance(out, dict):
        try:
            return out["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            pass

    # ③ 其它意外格式 —— 退化为 str(out)
    return str(out).strip()


def call_llm(
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        enable_thinking: bool = False,
) -> str:
    """
    单轮调用 DashScope Generation API（同步，非流式）。
    :param model:  Generation.Models.<model_name>  或直接填字符串模型名
    :param messages: OpenAI Chat 格式的历史消息
    :return: assistant 回复文本
    """
    # Convert list of dicts to list of Message objects
    from dashscope.api_entities.dashscope_response import Message
    message_objs = [Message(role=m["role"], content=m["content"]) for m in messages]
    logger.debug(f"Calling model: {model}, messages count: {len(messages)}")
    for i in range(MAX_RETRY):
        try:
            with SEMAPHORE:
                # 调用 DashScope Generation API
                resp = dashscope.Generation.call(
                    model=model,
                    messages=message_objs,
                    result_format="message",  # 要求返回 OpenAI ChatMessage 结构
                    temperature=temperature,
                    stream=False,  # 需要流式可改 True
                    enable_thinking=enable_thinking,
                )
            if resp.status_code == HTTPStatus.OK:  # type: ignore
                logger.debug(f"调用成功: {model}, 消息数: {len(messages)}")
                break
        except Exception as e:
            logger.error(f"调用失败: {e}, 重试 {i + 1}/{MAX_RETRY}")
            time.sleep(1)
    return _extract_content(resp)  # type: ignore


def judge_should_continue(history: List[Dict[str, str]]) -> dict:
    """
    判断对话是否可以继续。
    :param history: 历史消息列表
    :return: dict with keys: should_continue, no_repetition, reason
    """
    # 生成判断 prompt
    judger_prompt = prompt_chat.generate_judger_prompt(history)

    # 调用 LLM 判断
    for i in range(MAX_RETRY):
        try:
            # 调用 DashScope Generation API
            response = call_llm(
                model=Generation.Models.qwen_turbo,
                messages=[{"role": Role.USER, "content": judger_prompt}],
                temperature=0.3,
                enable_thinking=False,
            )

            logger.debug(f"判断对话是否继续: {response}")
            response = re.sub(r"```json\n(.*?)\n```", r"\1", response, flags=re.DOTALL)
            response = json.loads(response)
            should_continue = bool(response["should_continue"])
            no_repetition = bool(response["no_repetition"])
            reason = response["reason"]
            return {"should_continue": should_continue, "no_repetition": no_repetition, "reason": reason}
        except Exception as e:
            logger.error(f"判断对话是否继续失败: {e}, 重试 {i + 1}/{MAX_RETRY}")
            time.sleep(1)

    # 如果所有重试都失败，返回默认值
    return {"should_continue": False, "no_repetition": True, "reason": "判断失败，默认终止对话"}


# --------------------------------------------------------------------------------------
# 多轮对话核心
# --------------------------------------------------------------------------------------
def run_multi_turn_dialog(
        turns: int,
        init_user_prompt: str,
        user_system_prompt: str,
        assistant_system_prompt: str,
        user_followup_prompt: str,
        assistant_followup_prompt: str,
        user_model: str = Generation.Models.qwen_turbo,
        assistant_model: str = Generation.Models.qwen_plus,
        temperature: float = 0.7,
        enable_thinking: bool = False,
) -> tuple:
    """
    让 user_model 和 assistant_model 进行多轮对话。
    一轮 = (user → assistant)。
    :return: (history, early_stop, length, stop_reason, no_repetition)
    """

    history: List[Dict[str, str]] = [{"role": Role.USER, "content": init_user_prompt}]

    user_system_prompt_msg: List[Dict[str, str]] = [{"role": Role.SYSTEM, "content": user_system_prompt}]
    assistant_system_prompt_msg: List[Dict[str, str]] = [{"role": Role.SYSTEM, "content": assistant_system_prompt}]
    user_followup_msg: List[Dict[str, str]] = [{"role": Role.SYSTEM, "content": user_followup_prompt}]
    assistant_followup_msg: List[Dict[str, str]] = [{"role": Role.SYSTEM, "content": assistant_followup_prompt}]

    # -------- 主循环 --------
    early_stop = False
    stop_reason = ""
    no_repetition = True

    for turn_idx in range(turns):
        logger.info(f"开始第 {turn_idx + 1}/{turns} 轮对话")

        # 助理回复
        try:
            assistant_reply = call_llm(
                assistant_model,
                messages=assistant_system_prompt_msg + history + assistant_followup_msg,
                temperature=temperature,
                enable_thinking=enable_thinking,
            )
            history.append({"role": Role.ASSISTANT, "content": assistant_reply})
            logger.debug(f"Assistant reply: {assistant_reply[:100]}...")
        except Exception as e:
            logger.error(f"助理回复失败: {e}")
            early_stop = True
            stop_reason = f"助理回复失败: {str(e)}"
            break

        # 模拟用户追问
        try:
            user_followup = call_llm(
                user_model,
                messages=user_system_prompt_msg + history + user_followup_msg,
                temperature=temperature,
                enable_thinking=enable_thinking,
            )
            history.append({"role": Role.USER, "content": user_followup})
            logger.debug(f"User followup: {user_followup[:100]}...")
        except Exception as e:
            logger.error(f"用户追问失败: {e}")
            early_stop = True
            stop_reason = f"用户追问失败: {str(e)}"
            break

        # 判断是否应该继续
        check_result = judge_should_continue(history)
        should_continue = check_result["should_continue"]
        no_repetition = check_result["no_repetition"]
        stop_reason = check_result["reason"]

        if not should_continue or not no_repetition:
            if not no_repetition:
                history.pop()  # 移除重复的用户提问
            early_stop = True
            logger.info(f"对话提前终止: {stop_reason}")
            break

    if not early_stop:
        stop_reason = "对话完成"

    return history, early_stop, len(history), stop_reason, no_repetition


def write_to_file(data: Dict, output_file: str = "dialogue.json"):
    """线程安全的增量写入"""
    lock = threading.Lock()
    try:
        with lock:
            # 读取现有数据
            existing = get_existing_data(output_file)

            # 追加新数据
            existing.append(data)

            # 写入文件
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入文件失败: {e}")


def generate_dialogue_for_entry(
        entry: dict,
        user_model: str,
        assistant_model: str,
        turns: int,
        temperature: float,
        enable_thinking: bool
) -> Optional[dict]:
    """为单个entry生成对话"""
    if entry["id"] in existing_ids:
        logger.info(f"跳过已存在的entry: {entry['id']}")
        return None

    config = entry["config"]
    topics = config["topics"]
    definition = config.get("definition", "")  # 新增：场景定义
    goal = config["goal"]
    strategy = config["strategy"]

    for idx, scene in enumerate(entry["scene"]):
        logger.info(f"处理entry {entry['id']} 的第 {idx + 1}/{len(entry['scene'])} 个场景")

        background = scene["background"]
        preference = scene["preference"]
        question = scene["question"]

        # 新增：获取策略调控说明
        strategy_adjustment = scene.get("strategy_adjustment", {})
        if strategy_adjustment:
            strategy_control = "策略调控说明：\n" + "\n".join(
                [f"- {k}: {v}" for k, v in strategy_adjustment.items()]
            )
        else:
            strategy_control = ""

        # 生成用户初始prompt（带核心问题约束）
        user_system_prompt = prompt_chat.generate_user_init_prompt(background, preference, question)
        user_followup_prompt = prompt_chat.generate_user_followup_prompt(question)

        # 生成助手初始prompt（带策略调控说明）
        assistant_system_prompt = prompt_chat.generate_assistant_init_prompt(
            topics, definition, goal, strategy, background, strategy_control
        )
        assistant_followup_prompt = prompt_chat.generate_assistant_followup_prompt()

        # 用户第一句话（直接提出核心问题）
        user_init_prompt = question

        try:
            result, early_stop, length, stop_reason, no_repetition = run_multi_turn_dialog(
                turns=turns,
                init_user_prompt=user_init_prompt,
                user_system_prompt=user_system_prompt,
                assistant_system_prompt=assistant_system_prompt,
                user_followup_prompt=user_followup_prompt,
                assistant_followup_prompt=assistant_followup_prompt,
                user_model=user_model,
                assistant_model=assistant_model,
                temperature=temperature,
                enable_thinking=enable_thinking,
            )

            scene["dialogue"] = result
            scene["early_stop"] = early_stop
            scene["length"] = length
            scene["stop_reason"] = stop_reason
            scene["no_repetition"] = no_repetition

            logger.info(f"场景 {idx + 1} 对话生成完成: {length} 轮, early_stop={early_stop}")

        except Exception as e:
            logger.error(f"生成对话失败: {e}")
            scene["dialogue"] = []
            scene["early_stop"] = True
            scene["length"] = 0
            scene["stop_reason"] = f"生成失败: {str(e)}"
            scene["no_repetition"] = False

    return entry


def run_concurrent_dialogue_generation(data_path: str, output_path: str, **kwargs):
    """并发生成对话"""
    global existing_ids
    existing_ids = get_existng_ids(output_file=output_path)

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
    except Exception as e:
        logger.error(f"读取数据文件失败: {e}")
        return

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(generate_dialogue_for_entry, entry, **kwargs): entry["id"]
            for entry in prompts if entry["id"] not in existing_ids
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="生成对话"):
            try:
                result = future.result()
                if result:
                    write_to_file(result, output_file=output_path)
                    results.append(result)
            except Exception as e:
                logger.error(f"生成失败: {e}")

    logger.info(f"对话生成完成，共生成 {len(results)} 个entry")


def main():
    parser = argparse.ArgumentParser(description="Qwen Multi-Agent Chat (DashScope)")
    parser.add_argument("--data", type=str, required=True, help="背景数据文件路径")
    parser.add_argument("--turns", type=int, default=9, help="对话轮数（user+assistant 为 1 轮）")
    parser.add_argument("--user_model", type=str, default="qwen-turbo", help="用户模型名")
    parser.add_argument("--assistant_model", type=str, default="qwen-plus", help="助理模型名")
    parser.add_argument("--test", action='store_true', help="是否为测试模式（仅运行一次对话）")
    parser.add_argument("--temperature", type=float, default=0.7, help="生成温度（0-2）")
    parser.add_argument("--enable_thinking", action='store_true', help="是否启用思考模式（模型可以进行思考）")
    args = parser.parse_args()

    # 允许字符串或 Generation.Models 枚举
    user_model = (
        getattr(Generation.Models, args.user_model)
        if hasattr(Generation.Models, args.user_model)
        else args.user_model
    )
    assistant_model = (
        getattr(Generation.Models, args.assistant_model)
        if hasattr(Generation.Models, args.assistant_model)
        else args.assistant_model
    )

    # 创建必要的目录
    if not os.path.exists("logs"):
        os.makedirs("logs")
    if not os.path.exists("results"):
        os.makedirs("results")
    os.makedirs("results/multiturn_dialogue", exist_ok=True)

    # 生成输出文件名
    output_path = f'''results/multiturn_dialogue/dialogue_{args.user_model}_{args.assistant_model}_{args.turns}turns_temperature{args.temperature}{"_thinking" if args.enable_thinking else ""}{"_test" if args.test else ""}_{time.strftime('%Y-%m-%d_%H-%M-%S')}.json'''

    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        f"logs/multiturn_dialogue_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )

    logger.info("=" * 60)
    logger.info("开始多轮对话生成")
    logger.info(f"数据文件: {args.data}")
    logger.info(f"用户模型: {user_model}")
    logger.info(f"助理模型: {assistant_model}")
    logger.info(f"对话轮数: {args.turns}")
    logger.info(f"温度: {args.temperature}")
    logger.info(f"启用思考模式: {args.enable_thinking}")
    logger.info(f"测试模式: {args.test}")
    logger.info(f"输出文件: {output_path}")
    logger.info("=" * 60)

    run_concurrent_dialogue_generation(
        data_path=args.data,
        output_path=output_path,
        user_model=user_model,
        assistant_model=assistant_model,
        turns=args.turns,
        temperature=args.temperature,
        enable_thinking=args.enable_thinking,
    )

    logger.info("=" * 60)
    logger.info("多轮对话生成完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    # 若未配置 API-KEY，脚本直接退出
    if not os.getenv("DASHSCOPE_API_KEY"):
        sys.exit("❌  请先设置环境变量 DASHSCOPE_API_KEY，再运行此脚本！")
    main()