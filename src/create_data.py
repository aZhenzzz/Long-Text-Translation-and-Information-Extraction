import os
import re
import json
import base64
import mimetypes
import time
from typing import List, Dict, Any, Optional
from clean_md import read_file
from call_llm_api import chat_with_GLM

def extract_solution_section(text: str) -> str:
    marker = "# 解决方案"
    idx = text.rfind(marker)
    if idx == -1:
        raise ValueError("未找到 '# 解决方案' 段落")
    return text[idx:]

def iter_problem_blocks(solution_text: str):
    pattern = re.compile(r'(?m)^#\s*([ACGN]\d+)\.')
    matches = list(pattern.finditer(solution_text))
    if not matches:
        raise ValueError("未在解决方案部分找到任何题号如 # A1.等")

    for i, m in enumerate(matches):
        prob_id = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(solution_text)
        block = solution_text[start:end].strip()
        yield prob_id, block

def split_problem_block_by_llm(
    block: str,
    retry: int = 3, 
    model: str = "glm-4.5",
    max_token: int = 8192,
    temperature: float = 0.3
):
    prompt = f"""
请严格按照以下规则解析题目块文本，并返回**标准JSON字符串**（不要输出任何额外内容）：
1. 输出JSON结构要求（键名不可修改）：
{{
    "problem_text": "题目主体（包含所有题目内容，也包括国家信息（一般格式为(XX国家)））",
    "final_answer": "最终答案（出现在以"答案："开头的段落，若无该段落答案设为null）",
    "solutions": ["解法1内容", "解法2内容", ...]  // 整个题目块文本除去题目主题和最终答案的剩余所有内容 。可能会包含多个解法（如解法1.，解法二等表示），你需要将该题所有解法分割到列表中。
}}
2. 格式约束：
   - 必须返回可直接解析的JSON字符串，禁止添加注释、说明文字；
   - "final_answer" 无答案时必须为null（不是"None"字符串）；
   - "solutions" 无解法则为空数组[]；
   - 不要改变原文本的内容与格式，只需将他们段落按以上输出规则分类。
3. 示例输出（仅参考结构，需适配实际内容）：
{{
    "problem_text": "在△ABC中，AB=AC，∠A=60°，求BC的长度。(中国)",
    "final_answer": "答案：AB",
    "solutions": ["解法1：∵ AB=AC，∠A=60° ∴ △ABC是等边三角形，故BC=AB。", "解法二：用余弦定理可证BC=AB。"]
}}

需要解析的题目块文本：
{block}
    """

    for attempt in range(retry + 1):
        try:
            response = chat_with_GLM(
                prompt=prompt.strip(),
                model=model,
                max_token=max_token,
                temperature=temperature
            )
            response = response.strip()
            if not response:
                raise ValueError("LLM返回空内容")

            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                raise ValueError(f"未提取到有效JSON，原始返回：{response[:500]}")
            json_str = json_match.group()

            try:
                result = json.loads(json_str)
            except Exception as e:
                raise ValueError(f"JSON解析失败：{str(e)}，JSON字符串：{json_str[:500]}")

            required_keys = ["problem_text", "final_answer", "solutions"]
            for key in required_keys:
                if key not in result:
                    raise ValueError(f"JSON缺少必要字段：{key}，当前字段：{list(result.keys())}")

            problem_text = result["problem_text"].strip()
            final_answer = result["final_answer"] if result["final_answer"] is not None else None
            solutions = [s.strip() for s in result["solutions"] if isinstance(s, str) and s.strip()]

            return problem_text, solutions, final_answer

        except Exception as e:
            if attempt < retry:
                print(f"第{attempt+1}次解析失败，错误：{e}\n1秒后重试... 错误：{str(e)[:200]}")
                time.sleep(1)
            else:
                print(f"重试{retry}次后失败，将block作为problem返回")

    return block, [], None

def split_problem_block(block: str):
    lines = block.splitlines()
    if not lines:
        raise ValueError("空的题目块")

    content_lines = lines[1:]

    country_idx = None
    for i, line in enumerate(content_lines):
        if re.match(r'^\(.+?\)\s*$', line.strip()):
            country_idx = i
            break
    if country_idx is None:
        print("未找到国家行 '(xxx)'，块内容,正在调用大模型解析block...\n")
        return block, [], None
        # return split_problem_block_by_llm(block)


    problem_lines = content_lines[: country_idx + 1]
    rest_lines = content_lines[country_idx + 1 :]

    final_answer: Optional[str] = None
    ans_idx = None
    for i, line in enumerate(rest_lines):
        m = re.match(r'^答案[:：]\s*(.*)$', line.strip())
        if m:
            final_answer = m.group(1).strip() or None
            ans_idx = i
            break

    if ans_idx is not None:
        rest_lines = rest_lines[ans_idx + 1 :]

    solutions_block = "\n".join(rest_lines).strip()
    solutions = split_solutions(solutions_block)

    problem_text = "\n".join(problem_lines).strip()

    return problem_text, solutions, final_answer


def split_solutions(text: str) -> List[str]:

    text = text.strip()
    if not text:
        return []

    pattern = re.compile(r'(?m)^解法\s*[0-9一二三四五六七八九十]+[\.．：:。xS]?')
    matches = list(pattern.finditer(text))

    if not matches:
        return [text]

    solutions = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        part = text[start:end].strip()
        if part:
            solutions.append(part)

    return solutions

def embed_images(md_text: str, md_path: str) -> str:
    IMAGE_PATTERN = re.compile(r'!\[\]\((images/[^\)]+)\)')

    base_dir = os.path.dirname(os.path.abspath(md_path))

    def repl(match):
        rel_path = match.group(1)
        abs_path = os.path.join(base_dir, rel_path)
        try:
            with open(abs_path, "rb") as img_f:
                data = img_f.read()
        except FileNotFoundError:
            print(f"[WARN] 图片文件不存在：{abs_path}，保留原始路径。")
            return match.group(0)

        b64 = base64.b64encode(data).decode("ascii")
        mime, _ = mimetypes.guess_type(rel_path)
        if mime is None:
            mime = "image/png"
        return f"![](data:{mime};base64,{b64})"

    return IMAGE_PATTERN.sub(repl, md_text)


def build_json(md_path: str = "full_cn.md") -> List[Dict[str, Any]]:
    raw = read_file(md_path)
    sol_text = extract_solution_section(raw)
    results: List[Dict[str, Any]] = []
    found_ids: List[str] = []
    for prob_id, block in iter_problem_blocks(sol_text):
        print("处理",prob_id)
        found_ids.append(prob_id)

        problem, solutions, final_answer = split_problem_block(block)

        problem_b64 = embed_images(problem, md_path)
        solutions_b64 = [embed_images(s, md_path) for s in solutions]
        final_answer_b64 = embed_images(final_answer, md_path) if final_answer else None

        entry = {
            "id": prob_id,
            "problem": problem_b64,
            "solutions": solutions_b64,
            "final_answer": final_answer_b64, 
        }

        results.append(entry)


    return results

def save_json(data: List[Dict[str, Any]], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"处理完成：data → {path}")


if __name__ == "__main__":
    data = build_json()
    save_json(data, "full_zh.json")
