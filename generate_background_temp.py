# 这里是全流程生成过程，背景 -> 问题 -> 对话流水线

from utils.prompt import promptGenerator  # 用于生成提示词的类
from utils.duplication_check import generate_data_identifier, get_existing_data, get_existng_ids  # 去重函数，加载函数

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional
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
import uuid
import argparse

# ===== 配置区 =====
API_KEY = os.getenv("DASHSCOPE_API_KEY")
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

MAX_WORKERS = 8  # 总线程数
MAX_API_CONC = 16  # API并发数
MAX_RETRY = 200
SEMAPHORE = threading.Semaphore(MAX_API_CONC)
output_file = "backgrounds_num=20.json"

model, thinking = "qwen-turbo", False  # 不启用思维模式
generator = promptGenerator()  # 实例化一个提示词生成器
existing_ids = set()  # 初始化一个空集合，用于记录唯一id

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


# 构建消息内容：将系统prompt和用户prompt组装好给模型
def build_messages(user_prompt: str, system_prompt: str = "") -> list[dict]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ] if system_prompt else [
        {"role": "user", "content": user_prompt}
    ]


# 向阿里api发起请求并返回模型回答
def call_deepseek(messages: list[dict]) -> str:
    logger.debug(f"Calling model: {model}, with messages: {messages}")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "enable_thinking": thinking
    }
    with SEMAPHORE:  # 锁定信号量，防止超并发
        resp = requests.post(API_URL, headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def check_question_validity(question: str, preference: str) -> bool:
    """检查问题是否符合要求"""
    question_prompt = generator.generate_check_problem_prompt(question, preference)
    messages = build_messages(user_prompt=question_prompt)
    for _ in range(MAX_RETRY):
        try:
            response = call_deepseek(messages)  # true / false
            if response.lower() not in ["true", "false"]:
                raise ValueError("API返回的有效性检查结果不是布尔值")
            elif response.lower() == "true":
                return True
            else:
                logger.warning(f"问题无效: {question}")
                return False
        except Exception as e:
            logger.error(f"检查问题有效性失败: {e}")
            return False

    raise RuntimeError("检查问题有效性失败，已重试多次，但仍未成功")
    return False


def generate_questions_for_entry(entry: dict) -> Optional[dict]:
    """为单个entry生成问题和对话"""
    failed_topics = []
    for i in range(MAX_RETRY):
        try:
            question_prompt = generator.generate_question_prompt(
                background=entry["background"],
                preference=entry["preference"],
                failed_list=failed_topics
            )
            res = call_deepseek(build_messages(user_prompt=question_prompt))
            res = re.sub(r"```json\n(.*?)\n```", r"\1", res, flags=re.DOTALL)
            res = json.loads(res)
            entry["question"] = res["question"]
            entry["explanation"] = res["explanation"]

            # if not check_question_validity(entry["question"], entry["preference"]):
            #     logger.warning(f"生成的问题无效，跳过: {entry['question'], entry['preference']}")
            #     failed_topics.append(entry["question"])
            #     if len(failed_topics) >= 5:
            #         logger.error("连续生成5个无效问题，就这样吧")
            #         return entry
            #     continue
            return entry
        except requests.RequestException as e:
            if e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁，等待重试...")
                time.sleep(random.uniform(5, 10))
            else:
                logger.error(f"API请求失败: {e}")
                time.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.warning(f"生成问题失败: {e}")
            time.sleep(random.uniform(1, 3))
    return None


def generate_scene_with_questions(prompt: dict) -> Optional[dict]:
    """生成场景及其所有问题"""
    config, content = prompt["config"], prompt["content"]
    scene = None
    hash_id = generate_data_identifier(prompt, sort_keys=True, ensure_ascii=False, indent=2)
    if hash_id in existing_ids:
        logger.info(f"跳过已存在的ID: {hash_id}")
        return None
    # 生成场景
    for _ in range(MAX_RETRY):
        try:
            res = call_deepseek(build_messages(user_prompt=content))
            res = re.sub(r"```json\n(.*?)\n```", r"\1", res, flags=re.DOTALL)
            scene = json.loads(res)

            if not isinstance(scene, list):
                raise ValueError("场景响应不是列表")

            # 验证每个entry格式
            for entry in scene:
                if not isinstance(entry, dict) or "background" not in entry or "preference" not in entry:
                    raise ValueError(f"无效entry格式: {entry}")

            break

        except requests.RequestException as e:
            if e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁，等待重试...")
                time.sleep(random.uniform(5, 10))
            else:
                logger.error(f"API请求失败: {e}")
                time.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.warning(f"生成场景失败: {e}")
            time.sleep(random.uniform(1, 5))

    if not scene:
        return None

    # 并发生成问题
    with ThreadPoolExecutor(max_workers=min(4, MAX_WORKERS // 2)) as executor:
        futures = {executor.submit(generate_questions_for_entry, entry): entry for entry in scene}

        for future in as_completed(futures):
            entry = futures[future]
            try:
                result = future.result()
                if not result:
                    logger.error(f"为entry生成问题失败: {entry}")
            except Exception as e:
                logger.error(f"生成问题异常: {e}")

    return {
        "id": hash_id,
        "config": config,
        "scene": scene
    }


def generate_dialogue(scenario: str, question: str) -> list[dict]:
    """生成对话"""
    dialogue_prompt = generator.generate_dialogue_generation_prompt(scenario, question)
    for _ in range(MAX_RETRY):
        try:
            res = call_deepseek(build_messages(user_prompt=dialogue_prompt))
            res = re.sub(r"```json\n(.*?)\n```", r"\1", res, flags=re.DOTALL)
            dialogue = json.loads(res)
            if isinstance(dialogue, list) and all(
                    isinstance(d, dict) and "role" in d and "content" in d for d in dialogue):
                return dialogue
            else:
                raise ValueError("对话格式不正确")
        except requests.RequestException as e:
            if e.response and e.response.status_code == 429:
                logger.warning("API请求过于频繁，等待重试...")
                time.sleep(random.uniform(5, 10))
            else:
                logger.error(f"API请求失败: {e}")
                time.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.warning(f"生成对话失败: {e}")
            time.sleep(random.uniform(1, 5))
    raise RuntimeError("生成对话失败，已重试多次，但仍未成功")


def generate_background():
    """主生成函数"""
    prompts = list(generator.generate_all_background_prompt())
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(generate_scene_with_questions, prompt): prompt for prompt in prompts}

        for future in tqdm(as_completed(futures), total=len(futures), desc="生成场景"):
            prompt = futures[future]
            try:
                result = future.result()
                if result:
                    write_to_file(result)
                    results.append(result)
            except Exception as e:
                logger.error(f"处理prompt失败 '{prompt}': {e}")

    return results


def write_to_file(data: Dict):
    """线程安全的增量写入"""
    lock = threading.Lock()
    try:
        with lock:
            # 读取现有数据
            existing = get_existing_data(output_file=output_file)
            existing.append(data)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入文件失败: {e}")


def main():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        f"logs/generate_background_{time.strftime('%Y-%m-%d@%H:%M:%S')}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )
    parser = argparse.ArgumentParser(description="生成背景数据")
    parser.add_argument("--num", type=int, default=20, help="生成的背景数量")
    parser.add_argument("--test", action="store_true", help="测试模式，仅生成一次")
    parser.add_argument("--output", type=str, default="backgrounds_num=20.json", help="输出文件路径")
    parser.add_argument("--model", type=str, default="qwen-turbo", help="使用的模型名称")
    parser.add_argument("--thinking", action="store_true", help="启用思考模式")
    args = parser.parse_args()
    global model, thinking
    test, model, thinking, num = args.test, args.model, args.thinking, args.num

    if not os.path.exists("results"):
        os.makedirs("results")
    os.makedirs("results/background", exist_ok=True)
    global output_file
    output_file = '''results/background/background_''' + \
                  f'''{model}{"_thinking" if thinking else ""}{"_test" if test else ""}.json'''

    global generator
    generator.set_test(test=test, n=num)

    logger.info(f"测试模式: {test}, 使用模型: {model}, 思考模式: {thinking}, 输出文件: {output_file}")
    logger.info("开始生成背景数据...")

    global existing_ids
    existing_ids = get_existng_ids(output_file=output_file)

    generate_background()


if __name__ == "__main__":
    main()