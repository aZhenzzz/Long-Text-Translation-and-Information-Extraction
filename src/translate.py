import re
from collections import OrderedDict
from tqdm import tqdm
from clean_md import read_file,write_file
from call_llm_api import chat_with_GLM

def is_formula(line: str) -> bool:
    return line.strip().startswith("$$") and line.strip().endswith("$$")

# TODO:剥除图例
def is_image(line: str) -> bool:
    return bool(re.match(r"!\[.*\]\(.*\)", line.strip()))

def is_number_heading(line: str) -> bool:
    return bool(re.match(r"#\s+[ACGN]\d+\.", line.strip()))

def split_paragraphs(md_text: str):
    paragraphs = md_text.split("\n\n")
    return [p.strip() for p in paragraphs if p.strip()]

def clean_text(text):
    text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)
    text = re.sub(r'\$.*?\$', '', text)
    text = re.sub(r'\\[a-zA-Z]+\s*', '', text)  
    text = re.sub(r'[*_`]', '', text)  
    text = re.sub(r'[\u3000\t\n\r\v ]+', ' ', text)
    punctuation_pattern = re.compile(
        r'[\uFF01\uFF02\uFF03\uFF04\uFF05\uFF06\uFF07\uFF08\uFF09\uFF0A\uFF0B\uFF0C\uFF0D\uFF0E\uFF0F\uFF10\uFF11\uFF12\uFF13\uFF14\uFF15\uFF16\uFF17\uFF18\uFF19\uFF1A\uFF1B\uFF1C\uFF1D\uFF1E\uFF20\uFF3B\uFF3C\uFF3D\uFF3E\uFF3F\uFF40\uFF5B\uFF5C\uFF5D\uFF5E\uFF60\uFF62\uFF63\uFF64\u2014\u2018\u2019\u201C\u201D\u2026\u2013\u3000\u3001\u3002\u3003\u3008\u3009\u300A\u300B\u300C\u300D\u300E\u300F\u3010\u3011\u3014\u3015\u3016\u3017\u3018\u3019\u301A\u301B\u301C\u301D\u301E\u301F\u203B\u2049\u2212\u2215\u0021\u0022\u0023\u0024\u0025\u0026\u0027\u0028\u0029\u002A\u002B\u002C\u002D\u002E\u002F\u003A\u003B\u003C\u003D\u003E\u003F\u0040\u005B\u005C\u005D\u005E\u005F\u0060\u007B\u007C\u007D\u007E-]+'
    )
    text = punctuation_pattern.sub('', text)
    text = re.sub(r'\s+', '', text.strip())
    # text = text.lower() 
    
    return text


# TODO:可以并发调用api加速数据处理速度
def main(input_path="full_clean.md", output_path="full_zh.md"):
    md_text = read_file(input_path)
    paragraphs = split_paragraphs(md_text)
    print(f"{input_path}文件共 {len(paragraphs)} 个段落")
    translation_cache = OrderedDict()
    output_paragraphs = []

    for p in tqdm(paragraphs, desc="Translating"):
        if is_formula(p) or is_image(p) or is_number_heading(p):
            output_paragraphs.append(p)
            continue
        cache_key = clean_text(p)
        if cache_key in translation_cache:
            output_paragraphs.append(translation_cache[cache_key])
            continue

        prompt = f"把下面的内容翻译成中文，保持原始格式且重点关注语义准确性,不要输出除翻译结果外的其他任何内容：\n\n{p}"
        try:
            translated = chat_with_GLM(prompt) 
            translated = translated.strip()
        except Exception as e:
            translated = f"Error:{e}\n原文为\n{p}\n"

        translation_cache[cache_key] = translated
        output_paragraphs.append(translated)

    write_file(output_path,"\n\n".join(output_paragraphs))

    print(f"翻译完成：{input_path} → {output_path}")
    print(f"已自动跳过重复段落,共翻译 {len(translation_cache)} 个段落")

if __name__ == "__main__":
    main()