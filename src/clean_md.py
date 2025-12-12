import re
from typing import List, Dict, Any
from call_llm_api import chat_with_GLM

def read_file(path: str, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()

def write_file(path: str, text: str, encoding: str = "utf-8"):
    with open(path, "w", encoding=encoding) as f:
        f.write(text)

def convert_latex_to_md(text: str) -> str:
    pattern = r"\$\\left\(\s*\\mathbf\s*\{\s*([^}]*)\s*\}\s*\\right\)\$? "

    def repl(match):
        inner = match.group(1)  # 例如 "A 4 ."
        cleaned = inner.replace(" ", "")  # -> "A4."
        return f"# {cleaned}\n\n"

    return re.sub(pattern, repl, text)

def process_labels(text: str) -> str:
    labels = []

    labels += [f"A{i}." for i in range(1, 9)]   # A1.-A8.
    labels += [f"C{i}." for i in range(1, 9)]   # C1.-C8.
    labels += [f"G{i}." for i in range(1, 9)]   # G1.-G8.
    labels += [f"N{i}." for i in range(1, 8)]   # N1.-N7.

    counts = {}

    for label in labels:
        pattern_count = rf"\b{re.escape(label)}"
        matches = re.findall(pattern_count, text)
        counts[label] = len(matches)

    print("标签出现次数统计：")
    for label in labels:
        print(f"{label}: {counts[label]}")

    new_text = text
    for label in labels:
        if counts[label] <= 2 and counts[label] > 0:
            pattern_replace = rf"(?<!# )\b{re.escape(label)}\s{{0,2}}"
            replacement = f"# {label}\n\n"

            new_text = re.sub(pattern_replace, replacement, new_text)

    return new_text
def main(input_path="full.md", output_path="full_clean.md"):
    text = read_file(input_path)
    new_text = convert_latex_to_md(text)
    new_text = process_labels(new_text)
    write_file(output_path, new_text)
    print(f"处理完成：{input_path} → {output_path}")

if __name__ == "__main__":
    main()
