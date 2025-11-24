# 这里是全流程生成过程,背景 -> 场景解释 -> 策略调整 -> 问题 -> 对话流水线

from utils.prompt import promptGenerator
from utils.dataset import SCENE_DATA, parse_persona_string, get_persona_description
from utils.duplication_check import generate_data_identifier, get_existing_data, get_existing_ids

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Set
from tqdm import tqdm
from loguru import logger
import requests
import random
import os
import time
import argparse
import json
import re
import sys
import threading
from collections import deque

# ===== 配置区 =====
API_KEY = os.getenv("DASHSCOPE_API_KEY")
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

MAX_WORKERS = 8
MAX_API_CONC = 16
MAX_RETRY = 200
RETRY_DELAY_MIN = 1
RETRY_DELAY_MAX = 3
RATE_LIMIT_DELAY_MIN = 5
RATE_LIMIT_DELAY_MAX = 10

# ✅ 批量写入配置
BATCH_WRITE_SIZE = 50  # 每50个结果批量写入一次
WRITE_INTERVAL = 300  # 或每5分钟强制写入一次

SEMAPHORE = threading.Semaphore(MAX_API_CONC)
WRITE_LOCK = threading.Lock()
output_file = "backgrounds_demo.json"

model, thinking = "qwen-turbo", False
generator = promptGenerator()
existing_ids: Set[str] = set()

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


def build_messages(user_prompt: str, system_prompt: str = "") -> list[dict]:
    """构建消息内容"""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ] if system_prompt else [
        {"role": "user", "content": user_prompt}
    ]


def call_deepseek(messages: list[dict]) -> str:
    """向API发起请求并返回模型回答"""
    logger.debug(f"Calling model: {model}, with messages count: {len(messages)}")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "enable_thinking": thinking
    }
    with SEMAPHORE:
        resp = requests.post(API_URL, headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def clean_json_response(response: str) -> str:
    """清理API返回的JSON格式,处理各种可能的格式问题"""
    response = re.sub(r"```json\s*", "", response, flags=re.IGNORECASE)
    response = re.sub(r"```\s*$", "", response, flags=re.MULTILINE)
    response = re.sub(r"^```\s*", "", response, flags=re.MULTILINE)

    start_idx = response.find('{')
    end_idx = response.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        response = response[start_idx:end_idx + 1]

    return response.strip()


def safe_parse_json(response: str, context: str = "") -> Optional[dict]:
    """安全解析JSON,提供详细的错误信息"""
    try:
        cleaned = clean_json_response(response)
        logger.debug(f"[{context}] 清理后的响应: {cleaned[:200]}...")
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[{context}] JSON解析失败: {e}")
        logger.error(f"[{context}] 原始响应: {response[:500]}")
        logger.error(f"[{context}] 清理后响应: {cleaned[:500]}")
        return None


def check_question_validity(question: str, preference: str) -> bool:
    """检查问题是否符合要求"""
    question_prompt = generator.generate_check_problem_prompt(question, preference)
    messages = build_messages(user_prompt=question_prompt)

    for retry_idx in range(MAX_RETRY):
        try:
            response = call_deepseek(messages)
            response = response.strip().lower()

            if "true" in response:
                return True
            elif "false" in response:
                logger.warning(f"问题无效: {question[:50]}...")
                return False
            else:
                raise ValueError(f"API返回的有效性检查结果不是布尔值: {response}")

        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁,等待重试...")
                time.sleep(random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX))
            else:
                logger.error(f"API请求失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
                time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))
        except Exception as e:
            logger.error(f"检查问题有效性失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
            time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))

    logger.error("检查问题有效性失败,已重试多次")
    return False


def generate_scene_interpretation(category: str, subtopic: str) -> Optional[Dict[str, str]]:
    """生成场景解释(第一阶段)"""
    scene_data = SCENE_DATA[category]
    prompt = generator.generate_scene_interpretation_prompt(
        topic=scene_data["topics"],
        definition=scene_data["definition"],
        subtopic=subtopic
    )

    for retry_idx in range(MAX_RETRY):
        try:
            res = call_deepseek(build_messages(user_prompt=prompt))
            interpretation = safe_parse_json(res, context="场景解释")

            if not interpretation:
                raise ValueError("JSON解析失败")
            if not isinstance(interpretation, dict):
                raise ValueError("场景解释响应不是字典")
            if "目标导向" not in interpretation or "用户心理状态" not in interpretation:
                raise ValueError(f"场景解释缺少必要字段,当前字段: {list(interpretation.keys())}")

            logger.info(f"✓ 场景解释生成成功: {subtopic}")
            return interpretation

        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁,等待重试...")
                time.sleep(random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX))
            else:
                logger.error(f"API请求失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
                time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))
        except Exception as e:
            logger.warning(f"生成场景解释失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
            time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX * 2))

    logger.error(f"✗ 场景解释生成失败,已重试{MAX_RETRY}次: {subtopic}")
    return None


def generate_strategy_adjustment(
        category: str,
        subtopic: str,
        scene_desc: str,
        primary_dim: str,
        primary_level: str,
        persona_traits: dict
) -> Optional[Dict]:
    """生成策略调整(第二阶段)"""
    scene_data = SCENE_DATA[category]
    prompt = generator.generate_strategy_adjustment_prompt(
        topic=scene_data["topics"],
        definition=scene_data["definition"],
        subtopic=subtopic,
        scene_desc=scene_desc,
        strategy=scene_data["strategy"],
        primary_dim=primary_dim,
        primary_level=primary_level,
        persona_traits=persona_traits,
        strategy_dims=scene_data["strategy_dimensions"]
    )

    for retry_idx in range(MAX_RETRY):
        try:
            res = call_deepseek(build_messages(user_prompt=prompt))
            strategy = safe_parse_json(res, context="策略调整")

            if not strategy:
                raise ValueError("JSON解析失败")

            required_fields = ["conflict_analysis", "strategy_mode", "interaction_strategy"]
            if not all(field in strategy for field in required_fields):
                raise ValueError(f"策略调整响应缺少必要字段,当前字段: {list(strategy.keys())}")

            logger.info(f"✓ 策略调整生成成功: {subtopic}")
            logger.debug(f"冲突分析: {strategy['conflict_analysis']}")
            logger.debug(f"策略模式: {strategy['strategy_mode']}")

            return strategy

        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁,等待重试...")
                time.sleep(random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX))
            else:
                logger.error(f"API请求失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
                time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))
        except Exception as e:
            logger.warning(f"生成策略调整失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
            time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX * 2))

    logger.error(f"✗ 策略调整生成失败,已重试{MAX_RETRY}次: {subtopic}")
    return None


def generate_questions_for_entry(entry: dict) -> Optional[dict]:
    """为单个entry生成问题"""
    failed_topics = []
    max_question_attempts = 5

    for attempt_idx in range(max_question_attempts):
        for retry_idx in range(MAX_RETRY):
            try:
                question_prompt = generator.generate_question_prompt(
                    background=entry["background"],
                    preference=entry["preference"],
                    failed_list=failed_topics
                )
                res = call_deepseek(build_messages(user_prompt=question_prompt))
                parsed = safe_parse_json(res, context="问题生成")

                if not parsed:
                    raise ValueError("JSON解析失败")
                if not isinstance(parsed, dict) or "question" not in parsed or "explanation" not in parsed:
                    raise ValueError(f"返回格式不正确,当前字段: {list(parsed.keys()) if parsed else 'None'}")

                question = parsed["question"]
                explanation = parsed["explanation"]

                if check_question_validity(question, entry["preference"]):
                    entry["question"] = question
                    entry["explanation"] = explanation
                    logger.info(f"✓ 问题生成成功: {question[:50]}...")
                    return entry
                else:
                    failed_topics.append(question)
                    logger.warning(f"问题无效,重新生成 (尝试 {attempt_idx + 1}/{max_question_attempts})")
                    break

            except requests.RequestException as e:
                if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                    logger.warning("API请求过于频繁,等待重试...")
                    time.sleep(random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX))
                else:
                    logger.error(f"API请求失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
                    time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))
            except Exception as e:
                logger.warning(f"生成问题失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
                time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))

    logger.error(f"✗ 问题生成失败,已尝试{max_question_attempts}次")
    return None


def generate_scene_with_questions(prompt: dict) -> Optional[dict]:
    """生成场景及其所有问题(包括场景解释和策略调整)"""
    config, content = prompt["config"], prompt["content"]
    category = config["category"]
    subtopic = config["subtopic"]
    primary_dim = config["primary_dim"]
    primary_level = config["primary_level"]
    persona_str = config["persona_str"]

    persona_traits = parse_persona_string(persona_str)
    instance_id = config.get("instance_id", 0)

    task_id = f"{category}_{subtopic}_{persona_str}_{instance_id}"

    hash_id = generate_data_identifier(config, sort_keys=True, ensure_ascii=False, indent=2)
    if hash_id in existing_ids:
        logger.info(f"⊘ 跳过已存在的ID: {hash_id[:16]}... ({task_id})")
        return None

    logger.info(f"▶ 开始任务: {task_id}")

    # 第一阶段:生成场景解释
    scene_interpretation = generate_scene_interpretation(category, subtopic)
    if not scene_interpretation:
        logger.error(f"✗ 场景解释生成失败: {task_id}")
        return None

    scene_desc = f"目标导向:{scene_interpretation['目标导向']};用户心理状态:{scene_interpretation['用户心理状态']}"

    # 第二阶段:生成策略调整
    strategy_adjustment = generate_strategy_adjustment(
        category, subtopic, scene_desc, primary_dim, primary_level, persona_traits
    )
    if not strategy_adjustment:
        logger.error(f"✗ 策略调整生成失败: {task_id}")
        return None

    # 第三阶段:生成场景背景
    scene_entry = None
    for retry_idx in range(MAX_RETRY):
        try:
            res = call_deepseek(build_messages(user_prompt=content))
            scene_entry = safe_parse_json(res, context="场景背景")

            if not scene_entry:
                raise ValueError("JSON解析失败")
            if not isinstance(scene_entry, dict) or "background" not in scene_entry or "preference" not in scene_entry:
                raise ValueError(f"无效entry格式,当前字段: {list(scene_entry.keys()) if scene_entry else 'None'}")

            logger.info(f"✓ 场景背景生成成功: {task_id}")
            break

        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁,等待重试...")
                time.sleep(random.uniform(RATE_LIMIT_DELAY_MIN, RATE_LIMIT_DELAY_MAX))
            else:
                logger.error(f"API请求失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
                time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX))
        except Exception as e:
            logger.warning(f"生成场景失败 (尝试 {retry_idx + 1}/{MAX_RETRY}): {e}")
            time.sleep(random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX * 2))

    if not scene_entry:
        logger.error(f"✗ 场景背景生成失败,已重试{MAX_RETRY}次: {task_id}")
        return None

    # 第四阶段:添加人格信息并生成问题
    scene_entry["persona_str"] = persona_str
    scene_entry["primary_dim"] = primary_dim
    scene_entry["primary_level"] = primary_level
    scene_entry["conflict_analysis"] = strategy_adjustment.get("conflict_analysis", "")
    scene_entry["strategy_mode"] = strategy_adjustment.get("strategy_mode", "fusion")
    scene_entry["conflict_degree"] = strategy_adjustment.get("conflict_degree", "none")
    scene_entry["strategy_adjustment"] = strategy_adjustment.get("interaction_strategy", {})

    result = generate_questions_for_entry(scene_entry)
    if not result:
        logger.error(f"✗ 问题生成失败: {task_id}")
        return None

    logger.success(f"✓ 任务成功: {task_id}")

    return {
        "id": hash_id,
        "config": config,
        "scene_interpretation": scene_interpretation,
        "scene": [result]
    }


def batch_write_to_file(data_list: list):
    """✅ 批量写入文件 - 更高效"""
    global WRITE_LOCK

    if not data_list:
        return

    try:
        with WRITE_LOCK:
            existing = get_existing_data(output_file=output_file)
            existing.extend(data_list)  # 批量添加

            temp_file = output_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            os.replace(temp_file, output_file)
            logger.info(f"✅ 批量写入 {len(data_list)} 条数据,当前总数: {len(existing)}")
    except Exception as e:
        logger.error(f"✗ 批量写入文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def generate_background():
    """主生成函数 - 批量写入版"""

    all_prompts = list(generator.generate_all_background_prompt())
    prompt_queue = deque(all_prompts)
    total_tasks = len(all_prompts)

    if not total_tasks:
        logger.warning("没有需要生成的prompt。")
        return []

    logger.info(f"📋 总目标:生成 {total_tasks} 个场景")

    results = []
    completed_count = 0
    retry_count = {}
    max_retries_per_task = 3

    # ✅ 批量写入相关变量
    pending_writes = []  # 待写入的缓冲区
    last_write_time = time.time()

    pbar = tqdm(total=total_tasks, desc="生成场景", unit="个")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        active_futures = {}

        while prompt_queue or active_futures:

            # 填满工作线程
            while prompt_queue and len(active_futures) < MAX_WORKERS:
                prompt = prompt_queue.popleft()

                config = prompt["config"]
                prompt_id = f"{config['category']}_{config['subtopic']}_{config['persona_str']}_{config.get('instance_id', 0)}"

                if prompt_id not in retry_count:
                    retry_count[prompt_id] = 0

                future = executor.submit(generate_scene_with_questions, prompt)
                active_futures[future] = (prompt, prompt_id)

            if not active_futures:
                break

            try:
                completed_iterator = as_completed(active_futures, timeout=2.0)
                future = next(completed_iterator)
                prompt, prompt_id = active_futures[future]
            except (StopIteration, Exception):
                # ✅ 检查是否需要定期写入
                current_time = time.time()
                if pending_writes and (current_time - last_write_time > WRITE_INTERVAL):
                    batch_write_to_file(pending_writes)
                    pending_writes = []
                    last_write_time = current_time
                continue

            try:
                result = future.result()
                config = prompt.get("config", {})

                if result:
                    # ✅ 成功:添加到待写入缓冲区
                    results.append(result)
                    pending_writes.append(result)
                    completed_count += 1
                    pbar.update(1)
                    pbar.set_postfix({
                        "完成": f"{completed_count}/{total_tasks}",
                        "缓冲": len(pending_writes),
                        "队列": len(prompt_queue)
                    })

                    # ✅ 达到批量大小,立即写入
                    if len(pending_writes) >= BATCH_WRITE_SIZE:
                        batch_write_to_file(pending_writes)
                        pending_writes = []
                        last_write_time = time.time()

                else:
                    # 失败:重试逻辑
                    retry_count[prompt_id] += 1

                    if retry_count[prompt_id] < max_retries_per_task:
                        logger.warning(f"⚠️ 任务失败,第 {retry_count[prompt_id]} 次重试: {prompt_id}")
                        prompt_queue.append(prompt)
                    else:
                        logger.error(f"❌ 任务失败超过{max_retries_per_task}次,放弃: {prompt_id}")
                        completed_count += 1
                        pbar.update(1)

            except Exception as e:
                config = prompt.get("config", {})
                retry_count[prompt_id] = retry_count.get(prompt_id, 0) + 1

                if retry_count[prompt_id] < max_retries_per_task:
                    logger.error(f"❌ 任务异常,第 {retry_count[prompt_id]} 次重试: {prompt_id}: {e}")
                    prompt_queue.append(prompt)
                else:
                    logger.error(f"❌ 任务异常超过{max_retries_per_task}次,放弃: {prompt_id}: {e}")
                    completed_count += 1
                    pbar.update(1)

            del active_futures[future]

    # ✅ 写入剩余的数据
    if pending_writes:
        logger.info(f"📝 写入剩余的 {len(pending_writes)} 条数据...")
        batch_write_to_file(pending_writes)

    pbar.close()

    logger.success(f"✅ 生成完成, 共成功生成 {len(results)}/{total_tasks} 个场景")

    if len(results) < total_tasks:
        logger.warning(f"⚠️ 注意:期望生成 {total_tasks} 个,实际成功 {len(results)} 个")
        failed_count = total_tasks - len(results)
        logger.warning(f"⚠️ 失败或放弃的任务数: {failed_count}")

        failed_tasks = [k for k, v in retry_count.items() if v >= max_retries_per_task]
        if failed_tasks:
            logger.warning(f"⚠️ 以下任务失败:")
            for task in failed_tasks[:10]:
                logger.warning(f"   - {task}")
            if len(failed_tasks) > 10:
                logger.warning(f"   ... 还有 {len(failed_tasks) - 10} 个失败任务")

    return results


def main():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    parser = argparse.ArgumentParser(description="生成背景数据")
    parser.add_argument("--num", type=int, default=8, help="每个人格组合生成的背景数量")
    parser.add_argument("--test", action="store_true", help="测试模式,仅生成一次")
    parser.add_argument("--model", type=str, default="qwen-turbo", help="使用的模型名称")
    parser.add_argument("--thinking", action="store_true", help="启用思考模式")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")
    args = parser.parse_args()

    global model, thinking, generator, output_file, existing_ids

    num_from_args = args.num

    num = num_from_args

    test, model, thinking = args.test, args.model, args.thinking

    if not os.path.exists("results"):
        os.makedirs("results")
    os.makedirs("results/background", exist_ok=True)

    output_file = 'results/background/backgrounds.json'

    generator.set_test(test=test, n=num)

    logger.remove()
    logger.add(sys.stderr, level=args.log_level)
    logger.add(
        f"logs/generate_background_{time.strftime('%Y-%m-%d@%H:%M:%S')}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )

    logger.info("=" * 60)
    logger.info(f"🚀 开始生成背景数据")
    logger.info(f"测试模式: {test}")
    logger.info(f"使用模型: {model}")
    logger.info(f"思考模式: {thinking}")
    logger.info(f"每个组合生成: {num} 条 (总目标: {1080 * num})")
    logger.info(f"批量写入大小: {BATCH_WRITE_SIZE}")
    logger.info(f"输出文件: {output_file}")
    logger.info(f"日志级别: {args.log_level}")
    logger.info("=" * 60)

    existing_ids = get_existing_ids(output_file=output_file)
    logger.info(f"📊 已存在 {len(existing_ids)} 个数据,将跳过已生成的ID")

    results = generate_background()

    # 最终统计
    expected_total = 1080 * num
    actual_in_file = len(get_existing_data(output_file))

    logger.info("=" * 60)
    logger.info(f"📊 最终统计:")
    logger.info(f"  期望生成: {expected_total} 个")
    logger.info(f"  函数返回: {len(results)} 个")
    logger.info(f"  文件中实际: {actual_in_file} 个")

    # 计算行数估算
    estimated_lines = actual_in_file * 40  # 每个场景约40行
    logger.info(f"  预计文件行数: ~{estimated_lines:,} 行")

    if actual_in_file < expected_total:
        missing = expected_total - actual_in_file
        logger.warning(f"⚠️ 文件中数据不完整,缺少 {missing} 个 ({missing / expected_total * 100:.1f}%)")
        logger.info("💡 建议:")
        logger.info("  1. 检查日志中的错误信息")
        logger.info("  2. 重新运行程序(会自动跳过已生成的数据)")
        logger.info("  3. 检查API配额和网络连接")
        logger.info("  4. 考虑增加重试次数或调整并发数")
    else:
        logger.success("✅ 数据生成完整!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()