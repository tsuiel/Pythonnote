# -*- coding: utf-8 -*-
"""
本地文档智能审查与摘要 Agent —— 进阶探索（Agent 化改造）
==========================================================
对应实验指导书「步骤 4：进阶探索与 Agent 化改造」。

三个进阶方向：
    1. 蒙特卡洛方法：对关键词权重的不确定性进行随机抽样与概率分布预测。
    2. 对接大模型 API：将 Top 关键词、词频与核心文本片段作为 Prompt，
       生成结构化审查意见/摘要（此处提供可插拔接口与本地模拟实现）。
    3. 自动化工作流：使用 watchdog 监控文件夹，新文档放入即自动触发分析。

注意：本模块不自动启动 watchdog 常驻进程，避免占用；可通过 --watch 显式开启。
"""

import os
import json
import random
import argparse
import statistics
from collections import Counter

import numpy as np

from analyze_documents import load_stopwords, load_user_dict, read_documents, segment_text, top_keywords, clean_text


# ---------- 方向 1：蒙特卡洛模拟 ----------
def monte_carlo_keyweight(word_freq, doc_text, n_simulations=10000, top_k=10):
    """
    用蒙特卡洛方法估计“关键词重要度”的不确定性分布。
    思路：把每个词在文档中的出现看作带噪声的抽样，重复 n_simulations 次，
    统计每个词进入 Top-K 的概率（置信度），作为补充上下文。
    """
    words = list(word_freq.keys())
    counts = np.array([word_freq[w] for w in words], dtype=float)
    total = counts.sum()
    probs = counts / total

    # 重复抽样：每次从多项式分布抽取一批词，重新统计排名
    topk_hits = Counter()
    tokens_per_sample = max(int(total), 100)
    for _ in range(n_simulations):
        sample = np.random.choice(len(words), size=tokens_per_sample, p=probs)
        sampled_counts = Counter(sample)
        ranked = sorted(sampled_counts, key=lambda i: sampled_counts[i], reverse=True)[:top_k]
        for i in ranked:
            topk_hits[words[i]] += 1

    result = [
        {"关键词": w, "进入TopK概率": round(hit / n_simulations, 3)}
        for w, hit in topk_hits.most_common(top_k)
    ]
    print("[蒙特卡洛] 关键词重要性概率分布（Top-K 置信度）：")
    for item in result:
        print(f"    {item['关键词']}: {item['进入TopK概率']:.1%}")
    return result


# ---------- 方向 2：对接大模型 API ----------
def build_review_prompt(filename, keywords, top_global, text_snippet):
    """把关键词、词频与核心文本片段组织成结构化 Prompt。"""
    prompt = f"""你是一名专业的文档审查助手。请根据以下信息，生成一份结构化的文档审查意见与摘要。

文档名称：{filename}
文档核心关键词：{', '.join(w for w, _ in keywords[:10])}
全局高频词：{', '.join(w for w, _ in top_global[:15])}
核心文本片段：
{text_snippet}

请按以下结构输出：
1. 一句话摘要
2. 三个核心主题
3. 潜在关注点或风险
4. 改进建议
"""
    return prompt


def call_llm_api(prompt, api_key=None, model="gpt-4o-mini"):
    """
    可插拔的大模型调用接口。
    - 若配置 api_key，可在此接入真实 API（示例以 OpenAI 兼容接口为例）。
    - 未配置时，使用本地模拟实现，保证实验在无网络/无密钥环境下也能跑通。
    """
    if api_key:
        try:
            from openai import OpenAI  # 需 pip install openai
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"[API 调用失败，回退本地模拟] {e}\n" + local_mock_review(prompt)
    return local_mock_review(prompt)


def local_mock_review(prompt):
    """本地模拟的结构化审查意见（演示用）。"""
    filename = prompt.split("文档名称：")[1].split("\n")[0].strip() if "文档名称：" in prompt else "文档"
    return f"""【{filename} 审查意见（本地模拟生成）】
1. 一句话摘要：本文档围绕核心主题展开，重点讨论了相关领域的关键技术与应用场景。
2. 三个核心主题：技术发展趋势、典型应用实践、面临的挑战与对策。
3. 潜在关注点：需关注数据隐私、算法公平性与技术落地的合规性。
4. 改进建议：建议补充量化数据与案例，进一步强化结论的可验证性。"""


# ---------- 方向 3：自动化工作流 ----------
def watch_folder(folder_path, interval=2):
    """使用 watchdog 监控文件夹，新文档放入即触发分析回调。"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("[错误] 未安装 watchdog，请先执行：pip install watchdog")
        return

    from analyze_documents import analyze_documents

    class DocHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory or not event.src_path.lower().endswith((".txt", ".md")):
                return
            print(f"[监控] 检测到新文档：{event.src_path}，触发自动分析...")
            analyze_documents(
                folder_path=folder_path,
                font_path="C:/Windows/Fonts/msyh.ttc",
                stopwords_file="./config/stopwords.txt",
                user_dict="./config/user_dict.txt",
                output_image="./output/watchdog_wordcloud.png",
            )

    observer = Observer()
    observer.schedule(DocHandler(), folder_path, recursive=False)
    observer.start()
    print(f"[监控] 开始监听文件夹：{folder_path}（按 Ctrl+C 停止）")
    try:
        import time
        while True:
            time.sleep(interval)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main():
    parser = argparse.ArgumentParser(description="Agent 化进阶探索")
    parser.add_argument("--folder", default="./docs", help="文档文件夹")
    parser.add_argument("--font", default="C:/Windows/Fonts/msyh.ttc")
    parser.add_argument("--stopwords", default="./config/stopwords.txt")
    parser.add_argument("--userdict", default="./config/user_dict.txt")
    parser.add_argument("--apikey", default=None, help="可选：大模型 API Key")
    parser.add_argument("--watch", action="store_true", help="开启文件夹监控工作流")
    args = parser.parse_args()

    if args.watch:
        watch_folder(args.folder)
        return

    load_user_dict(args.userdict)
    stopwords = load_stopwords(args.stopwords)
    docs = read_documents(args.folder)

    all_words = []
    for name, text in docs.items():
        all_words.extend(segment_text(text, stopwords))
    global_top = top_keywords(all_words, 50)
    word_freq = dict(global_top)

    print("\n" + "=" * 60)
    print("进阶方向 1 / 3：蒙特卡洛关键词权重不确定性分析")
    print("=" * 60)
    mc_result = monte_carlo_keyweight(word_freq, " ".join(docs.values()))

    print("\n" + "=" * 60)
    print("进阶方向 2 / 3：对接大模型 API 生成结构化审查意见")
    print("=" * 60)
    for name, text in list(docs.items())[:1]:
        kws = top_keywords(segment_text(text, stopwords), 10)
        prompt = build_review_prompt(name, kws, global_top, text[:300])
        print("[Prompt 预览]：", prompt[:120].replace("\n", " "), "...")
        review = call_llm_api(prompt, api_key=args.apikey)
        print(review)

    # 保存蒙特卡洛结果供报告引用
    with open("./output/monte_carlo_result.json", "w", encoding="utf-8") as f:
        json.dump(mc_result, f, ensure_ascii=False, indent=2)
    print("\n[信息] 蒙特卡洛结果已保存至 ./output/monte_carlo_result.json")
    print("[提示] 如需开启方向 3 文件夹自动监控，请加参数 --watch")


if __name__ == "__main__":
    main()
