# -*- coding: utf-8 -*-
"""
本地文档智能审查与摘要 Agent —— 核心分析模块
================================================
对应实验指导书「步骤 3：核心代码实现与本地验证」。

功能：
    1. 批量读取文件夹中的 .txt / .md 文档
    2. 加载自定义词典与停用词表，使用 jieba 精确模式分词
    3. 过滤停用词与单字符，统计词频
    4. 生成 Top 50 高频词云（PNG）并展示
    5. 输出包含各文件核心关键词的汇总报告（CSV + TXT）

作者：实验作者
日期：2026-11-17
"""

import os
import re
import csv
import argparse
from collections import Counter

import jieba
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# matplotlib 中文字体显示（避免图表中文显示为方框）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


# 默认基础停用词（当未提供停用词文件时使用）
DEFAULT_STOPWORDS = {
    "的", "了", "和", "在", "是", "我", "你", "他",
    "我们", "他们", "为", "以", "等", "并", "对", "与",
}


def load_stopwords(stopwords_file):
    """加载停用词表；文件不存在时回退到默认基础停用词。"""
    stopwords = set()
    if stopwords_file and os.path.exists(stopwords_file):
        with open(stopwords_file, "r", encoding="utf-8") as f:
            stopwords = {line.strip() for line in f if line.strip()}
        print(f"[信息] 已加载停用词表：{stopwords_file}（{len(stopwords)} 个词）")
    else:
        stopwords = set(DEFAULT_STOPWORDS)
        print("[警告] 未找到停用词表，使用默认基础停用词。")
    return stopwords


def load_user_dict(user_dict):
    """加载自定义专业词典，提升特定领域分词准确率。"""
    if user_dict and os.path.exists(user_dict):
        jieba.load_userdict(user_dict)
        print(f"[信息] 已加载自定义词典：{user_dict}")
    else:
        print("[警告] 未找到自定义词典，使用 jieba 默认词典。")


def read_documents(folder_path):
    """遍历目录，批量读取所有 .txt 与 .md 文件，返回 {文件名: 文本}。"""
    docs = {}
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"文件夹不存在：{folder_path}")

    for filename in sorted(os.listdir(folder_path)):
        if filename.lower().endswith((".txt", ".md")):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    docs[filename] = f.read()
                print(f"[成功] 读取文件：{filename}")
            except UnicodeDecodeError:
                # 尝试兼容 GBK 编码的中文文本
                try:
                    with open(file_path, "r", encoding="gbk") as f:
                        docs[filename] = f.read()
                    print(f"[成功] 读取文件（GBK 编码）：{filename}")
                except Exception as e:
                    print(f"[错误] 处理文件 {filename} 时发生编码错误：{e}")
            except Exception as e:
                print(f"[错误] 处理文件 {filename} 时发生错误：{e}")
    return docs


def clean_text(text):
    """文本清洗：去除 Markdown 标记、URL、多余空白，仅保留中文与英文字母数字。"""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)   # 标题 # 号
    text = re.sub(r"\*\*|__|`|>", "", text)                        # 加粗/引用标记
    text = re.sub(r"https?://\S+", "", text)                       # URL
    text = re.sub(r"\s+", " ", text)                               # 合并空白
    return text.strip()


def segment_text(text, stopwords):
    """文本清洗 -> jieba 精确模式分词 -> 过滤停用词与单字符/纯标点。"""
    text = clean_text(text)
    words = jieba.lcut(text)
    # 仅保留长度>1 且含中文/字母数字的词，排除 ## 等纯标点
    return [w for w in words
            if len(w) > 1 and w not in stopwords and re.search(r"[\u4e00-\u9fa5A-Za-z0-9]", w)]


def top_keywords(words, top_n=50):
    """统计词频并返回 Top N 高频词。"""
    return Counter(words).most_common(top_n)


def generate_wordcloud(word_freq, font_path, output_image, width=1000, height=800):
    """根据词频字典生成词云并保存为 PNG，同时用 matplotlib 展示。"""
    wc = WordCloud(
        font_path=font_path,
        width=width,
        height=height,
        background_color="white",
        max_words=50,
        collocations=False,  # 避免词语重复组合
        color_func=None,
    )
    wc.generate_from_frequencies(dict(word_freq))

    # 保存图片
    wc.to_file(output_image)
    print(f"[信息] 词云已保存至：{output_image}")

    # 本地展示
    plt.figure(figsize=(10, 8))
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.title("本地文档高频词云分析", fontsize=16)
    plt.tight_layout()
    plt.show()
    return wc


def write_summary_report(doc_keywords, global_top, output_csv, output_txt):
    """输出汇总报告：各文件核心关键词 + 全局 Top 词。"""
    # CSV 报告
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["文件名", "排名", "关键词", "词频"])
        for filename, kws in doc_keywords.items():
            for rank, (word, count) in enumerate(kws, start=1):
                writer.writerow([filename, rank, word, count])

    # TXT 报告
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("本地文档智能审查与摘要 —— 关键词汇总报告\n")
        f.write("=" * 50 + "\n\n")
        f.write("一、各文件核心关键词（Top 10）\n")
        f.write("-" * 50 + "\n")
        for filename, kws in doc_keywords.items():
            f.write(f"\n【{filename}】\n")
            f.write("、".join(f"{w}({c})" for w, c in kws[:10]))
            f.write("\n")
        f.write("\n二、全局高频词（Top 50）\n")
        f.write("-" * 50 + "\n")
        f.write("、".join(f"{w}({c})" for w, c in global_top))
        f.write("\n")

    print(f"[信息] 汇总报告已保存至：{output_csv} 和 {output_txt}")


def analyze_documents(folder_path, font_path, stopwords_file=None, user_dict=None,
                      output_image="document_wordcloud.png", top_n=50):
    """主流程：批量读取 -> 分词 -> 统计 -> 词云 -> 汇总报告。"""
    print("=" * 60)
    print("本地文档智能审查与摘要 Agent —— 开始分析")
    print("=" * 60)

    # 1. 加载词典
    load_user_dict(user_dict)
    stopwords = load_stopwords(stopwords_file)

    # 2. 批量读取与分词
    docs = read_documents(folder_path)
    if not docs:
        print("[错误] 未读取到任何有效文档，请检查文件夹路径。")
        return

    all_words = []
    doc_keywords = {}
    for filename, text in docs.items():
        words = segment_text(text, stopwords)
        all_words.extend(words)
        doc_keywords[filename] = top_keywords(words, top_n=10)
        print(f"[分词] {filename}：提取 {len(words)} 个有效词，"
              f"核心词 {doc_keywords[filename][:5]}")

    if not all_words:
        print("[错误] 未提取到有效词汇，请检查文件内容或停用词表。")
        return

    # 3. 统计全局词频
    global_top = top_keywords(all_words, top_n)
    print(f"[信息] 全局 Top {top_n} 高频词：{global_top}")

    # 4. 生成词云
    generate_wordcloud(global_top, font_path, output_image)

    # 5. 汇总报告
    out_dir = os.path.dirname(output_image) or "."
    write_summary_report(
        doc_keywords, global_top,
        os.path.join(out_dir, "summary_report.csv"),
        os.path.join(out_dir, "summary_report.txt"),
    )

    print("=" * 60)
    print("分析完成！")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="本地文档智能审查与摘要 Agent")
    parser.add_argument("--docs", default="./docs", help="文档文件夹路径")
    parser.add_argument("--font", default="C:/Windows/Fonts/msyh.ttc", help="中文字体路径")
    parser.add_argument("--stopwords", default="./config/stopwords.txt", help="停用词表路径")
    parser.add_argument("--userdict", default="./config/user_dict.txt", help="自定义词典路径")
    parser.add_argument("--output", default="./output/document_wordcloud.png", help="词云输出路径")
    args = parser.parse_args()

    analyze_documents(
        folder_path=args.docs,
        font_path=args.font,
        stopwords_file=args.stopwords,
        user_dict=args.userdict,
        output_image=args.output,
    )


if __name__ == "__main__":
    main()
