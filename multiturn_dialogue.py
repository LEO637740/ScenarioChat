# 多轮对话实现，使用两个LLM互相询问

import os
import sys
import json
import argparse
import threading
import time
import re

from http import HTTPStatus
from tqdm import tqdm
from typing import List, Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

import dashscope
from dashscope import Generation
from dashscope.api_entities.dashscope_response import Role

from utils.prompt import promptChat
# 【修复】 修正拼写错误
from utils.duplication_check import get_existing_data, get_existing_ids
# 【修复】 导入 OCEAN_CONFIG 以便验证
from utils.dataset import OCEAN_CONFIG

prompt_chat = promptChat()
existing_ids: Set[str] = set()

MAX_WORKERS = 8
MAX_API_CONC = 16
MAX_RETRY = 10
RETRY_DELAY = 1
SEMAPHORE = threading.Semaphore(MAX_API_CONC)
WRITE_LOCK = threading.Lock()  # ✅ 添加这一行


def _extract_content(resp: Any) -> str:
    """从DashScope的响应对象中抽取assistant内容"""
    if resp.status_code != HTTPStatus.OK:
        raise RuntimeError(f"DashScope error {resp.status_code}: {resp.message}")

    out = resp.output

    # prompt方式返回纯字符串
    if isinstance(out, str):
        return out.strip()

    # messages方式返回dict
    if isinstance(out, dict):
        try:
            return out["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            pass

    # 其它格式退化为str(out)
    return str(out).strip()


def call_llm(
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        enable_thinking: bool = False,
) -> str:
    """单轮调用DashScope Generation API（同步，非流式）"""
    from dashscope.api_entities.dashscope_response import Message
    message_objs = [Message(role=m["role"], content=m["content"]) for m in messages]
    logger.debug(f"Calling model: {model}, messages count: {len(messages)}")

    for i in range(MAX_RETRY):
        try:
            with SEMAPHORE:
                resp = dashscope.Generation.call(
                    model=model,
                    messages=message_objs,
                    result_format="message",
                    temperature=temperature,
                    stream=False,
                    enable_thinking=enable_thinking,
                )
            if resp.status_code == HTTPStatus.OK:
                logger.debug(f"调用成功: {model}, 消息数: {len(messages)}")
                return _extract_content(resp)
        except Exception as e:
            logger.error(f"调用失败: {e}, 重试 {i + 1}/{MAX_RETRY}")
            time.sleep(RETRY_DELAY)

    raise RuntimeError(f"API调用失败，已重试{MAX_RETRY}次")


def judge_should_continue(history: List[Dict[str, str]]) -> dict:
    """判断对话是否可以继续"""
    judger_prompt = prompt_chat.generate_judger_prompt(history)

    for i in range(MAX_RETRY):
        try:
            response = call_llm(
                model=Generation.Models.qwen_turbo,
                messages=[{"role": Role.USER, "content": judger_prompt}],
                temperature=0.3,
                enable_thinking=False,
            )

            logger.debug(f"判断对话是否继续: {response}")
            response = re.sub(r"```json\n(.*?)\n```", r"\1", response, flags=re.DOTALL)
            response = json.loads(response)

            return {
                "should_continue": bool(response["should_continue"]),
                "no_repetition": bool(response["no_repetition"]),
                "reason": response["reason"]
            }
        except Exception as e:
            logger.error(f"判断对话是否继续失败: {e}, 重试 {i + 1}/{MAX_RETRY}")
            time.sleep(RETRY_DELAY)

    # 如果所有重试都失败，返回默认值
    return {
        "should_continue": False,
        "no_repetition": True,
        "reason": "判断失败，默认终止对话"
    }


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
    """让user_model和assistant_model进行多轮对话"""
    history: List[Dict[str, str]] = [{"role": Role.USER, "content": init_user_prompt}]

    user_system_prompt_msg = [{"role": Role.SYSTEM, "content": user_system_prompt}]
    assistant_system_prompt_msg = [{"role": Role.SYSTEM, "content": assistant_system_prompt}]
    user_followup_msg = [{"role": Role.SYSTEM, "content": user_followup_prompt}]
    assistant_followup_msg = [{"role": Role.SYSTEM, "content": assistant_followup_prompt}]

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
    global WRITE_LOCK
    try:
        with WRITE_LOCK:
            existing = get_existing_data(output_file)
            existing.append(data)

            # 先写入临时文件
            temp_file = output_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            # 原子性替换
            import os
            os.replace(temp_file, output_file)

            logger.debug(f"成功写入数据,当前总数: {len(existing)}")
    except Exception as e:
        logger.error(f"写入文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def generate_dialogue_for_entry(
        entry: dict,
        user_model: str,
        assistant_model: str,
        turns: int,
        temperature: float,
        enable_thinking: bool,
        output_file: str
) -> Optional[dict]:
    """为单个entry生成对话"""
    if entry["id"] in existing_ids:
        logger.info(f"跳过已存在的entry: {entry['id']}")
        return None

    # --- 【修复】 增加安全访问 ---
    config = entry.get("config", {})
    if not config:
        logger.error(f"Entry {entry.get('id', '???')} 缺少 'config' 块. 跳过.")
        return None

    topics = config.get("topics", "未知话题")
    definition = config.get("definition", "")
    goal = config.get("goal", "未知目标")
    strategy = config.get("strategy", "未知策略")
    # --- 安全访问结束 ---

    for idx, scene in enumerate(entry["scene"]):
        logger.info(f"处理entry {entry['id']} 的第 {idx + 1}/{len(entry['scene'])} 个场景")

        background = scene["background"]
        preference = scene["preference"]
        question = scene["question"]

        primary_dim = scene.get("primary_dim") or config.get("primary_dim", "C")
        primary_level = scene.get("primary_level") or config.get("primary_level", "high")

        # --- 【修复】 增加关键的数据验证 (这会捕获 'o' 错误) ---
        if primary_dim not in OCEAN_CONFIG:
            logger.error(f"无效的 primary_dim: '{primary_dim}' (在 entry {entry['id']}). "
                         f"数据文件可能已过时或损坏。跳过此场景。")
            scene["dialogue"] = []
            scene["early_stop"] = True
            scene["length"] = 0
            scene["stop_reason"] = f"无效的 primary_dim: {primary_dim} (数据文件与 dataset.py 不匹配)"
            scene["no_repetition"] = False
            continue  # 跳到下一个 scene

        if primary_level not in OCEAN_CONFIG[primary_dim]:
            logger.error(f"无效的 primary_level: '{primary_level}' (用于 dim '{primary_dim}' "
                         f"in entry {entry['id']}). 数据文件可能已过时或损坏。跳过此场景。")
            scene["dialogue"] = []
            scene["early_stop"] = True
            scene["length"] = 0
            scene["stop_reason"] = (f"无效的 primary_level: {primary_level} for dim {primary_dim} "
                                    f"(数据文件与 dataset.py 不匹配)")
            scene["no_repetition"] = False
            continue  # 跳到下一个 scene
        # --- 验证结束 ---

        logger.debug(f"主维度信息: dim={primary_dim}, level={primary_level}")

        # 获取策略调控说明
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

        try:
            assistant_system_prompt = prompt_chat.generate_assistant_init_prompt(
                topics, definition, goal, strategy, background, strategy_control,
                primary_dim, primary_level
            )
            assistant_followup_prompt = prompt_chat.generate_assistant_followup_prompt(
                primary_dim, primary_level
            )
        except Exception as e:
            # 理论上不应再发生KeyError，因为上面已经验证过了
            logger.error(f"生成助手prompt失败 (非预期的错误): {e}")
            logger.error(f"主维度信息: primary_dim={primary_dim}, primary_level={primary_level}")
            scene["dialogue"] = []
            scene["early_stop"] = True
            scene["length"] = 0
            scene["stop_reason"] = f"生成prompt失败: {str(e)}"
            scene["no_repetition"] = False
            continue

        # 用户第一句话（直接提出核心问题）
        user_init_prompt = question

        # ===== 【修改】 增加质量重试循环 =====
        max_generation_attempts = 3  # 最多尝试3次
        min_dialogue_length = 10  # 最小对话长度

        for attempt in range(max_generation_attempts):
            logger.info(f"处理 entry {entry['id']} 场景 {idx + 1}, 尝试 {attempt + 1}/{max_generation_attempts}")

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

                # --- 质量检查 ---
                if length < min_dialogue_length:
                    logger.warning(f"对话太短 (length={length}), 不符合质量标准 (< {min_dialogue_length}).")

                    if attempt == max_generation_attempts - 1:
                        # 这是最后一次尝试
                        logger.error(f"已达最大尝试次数. 记录为失败 (长度 {length}).")
                        scene["dialogue"] = result
                        scene["early_stop"] = True
                        scene["length"] = length
                        scene[
                            "stop_reason"] = f"质量不合格: {max_generation_attempts} 次尝试后长度仍 < {min_dialogue_length} (last length={length})"
                        scene["no_repetition"] = no_repetition
                    else:
                        # 还有重试机会
                        logger.info("准备重试...")
                        time.sleep(RETRY_DELAY)  # 等待一小会
                        continue  # 进入下一次循环 (attempt + 1)

                # --- 质量合格 ---
                else:
                    scene["dialogue"] = result
                    scene["early_stop"] = early_stop
                    scene["length"] = length
                    scene["stop_reason"] = stop_reason
                    scene["no_repetition"] = no_repetition
                    logger.info(f"场景 {idx + 1} 对话生成完成: {length} 轮, early_stop={early_stop}")
                    break  # 成功，退出重试循环

            except Exception as e:
                logger.error(f"生成对话失败 (尝试 {attempt + 1}): {e}")
                scene["dialogue"] = []
                scene["early_stop"] = True
                scene["length"] = 0
                scene["stop_reason"] = f"生成失败: {str(e)}"
                scene["no_repetition"] = False
                break  # 发生异常，退出重试循环
        # ===== 【修改】 质量重试循环结束 =====

    # 写入文件（立即保存）
    write_to_file(entry, output_file)
    return entry


def run_concurrent_dialogue_generation(
        data_path: str,
        output_path: str,
        user_model: str,
        assistant_model: str,
        turns: int,
        temperature: float,
        enable_thinking: bool
):
    """并发生成对话"""
    global existing_ids
    existing_ids = get_existing_ids(output_file=output_path)  # <-- 【修复】 修正拼写

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
    except Exception as e:
        logger.error(f"读取数据文件失败: {e}")
        return

    logger.info(f"共读取 {len(prompts)} 个entry，其中 {len(existing_ids)} 个已存在")

    # ✅ 数据验证：检查必要字段
    valid_prompts = []
    for entry in prompts:
        if entry["id"] in existing_ids:
            continue

        # 检查数据完整性
        if "scene" not in entry or not entry["scene"]:
            logger.warning(f"跳过无效entry: {entry.get('id', 'unknown')} - 缺少scene字段")
            continue

        # 检查每个scene是否有必要字段
        valid = True
        for scene in entry["scene"]:
            if not all(k in scene for k in ["background", "preference", "question"]):
                logger.warning(f"跳过无效entry: {entry['id']} - scene缺少必要字段")
                valid = False
                break

        if valid:
            valid_prompts.append(entry)

    logger.info(f"经过验证，共 {len(valid_prompts)} 个有效entry需要处理")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                generate_dialogue_for_entry,
                entry,
                user_model,
                assistant_model,
                turns,
                temperature,
                enable_thinking,
                output_path
            ): entry["id"]
            for entry in valid_prompts
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="生成对话"):
            try:
                result = future.result()
                if result:
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
    parser.add_argument("--test", action='store_true', help="是否为测试模式")
    parser.add_argument("--temperature", type=float, default=0.7, help="生成温度（0-2）")
    parser.add_argument("--enable_thinking", action='store_true', help="是否启用思考模式")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")
    args = parser.parse_args()

    # 模型名称处理
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
    output_path = f'results/multiturn_dialogue/dialogue_{args.user_model}_{args.assistant_model}_{args.turns}turns_temperature{args.temperature}{"_thinking" if args.enable_thinking else ""}{"_test" if args.test else ""}_{time.strftime("%Y-%m-%d_%H-%M-%S")}.json'

    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)
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
    if not os.getenv("DASHSCOPE_API_KEY"):
        sys.exit("❌  请先设置环境变量 DASHSCOPE_API_KEY，再运行此脚本！")
    main()