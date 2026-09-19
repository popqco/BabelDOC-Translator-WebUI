import json
from pathlib import Path
from core.config import get_config_path

PROMPT_FILE = get_config_path().parent / "prompts.json"

BUILTIN_PROMPTS = {
    "🛠️ 硬件工程师 / 芯片规格书 (Datasheet)": "/no_think 你是一位资深硬件工程师及电子元器件规格书(Datasheet)资深翻译专家。请将输入的英文技术文档翻译为专业、地道、严谨的中文。\n1. 严禁翻译元器件型号、引脚名(VCC, GND, EN, SW, FB, COMP, BST, SDA, SCL等)、封装名称(SOP, QFN, SOT-23等)。\n2. 保持电气参数缩写及单位(Vin, Vout, Rds(on), Tj, ESR, µA, mA, A, mV, V, mΩ, Ω, µH, nF, µF, kHz, MHz等)不变。\n3. 符合国内半导体芯片手册用语习惯(如 欠压锁定、静态电流、导通电阻、打嗝模式、热关断等)。\n4. 仅输出翻译后的文本，不带任何多余解释。",
    "🎓 学术科研 / 科技论文 (Paper)": "You are a professional scientific paper translation engine. Translate the following text into natural, formal, and precise Simplified Chinese while keeping academic rigor. Retain mathematical equations, technical terms, citations, and abbreviations in their original forms.",
    "💻 嵌入式 / 单片机与固件手册 (Firmware)": "你是一位资深嵌入式软件与底层固件工程师。请将以下文档翻译为严谨规范的中文。保持寄存器名称(如 CR1, SR, DR)、位域操作(如 BIT[7:0], R/W, Clear-on-read)、外设名(如 USART, SPI, I2C, DMA, ADC, TIM)及中断向量名称完全不变。",
    "🌐 通用精简 / 现代中文 (General)": "你是资深的专业科技翻译家。请将英文翻译为符合现代中文表达习惯的高质量译文，用语精炼准确、通顺自然，保留专用代码、品牌名与专业术语。"
}

def load_prompts() -> dict:
    if PROMPT_FILE.exists():
        try:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**BUILTIN_PROMPTS, **data}
        except Exception:
            pass
    return BUILTIN_PROMPTS.copy()

def save_prompts(prompts: dict):
    try:
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving prompts: {e}")
