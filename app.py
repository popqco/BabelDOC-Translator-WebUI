import os
import sys
import json
from pathlib import Path
import gradio as gr
from gradio_pdf import PDF
import subprocess

CONFIG_PATH = Path.home() / ".config" / "PDFMathTranslate" / "babeldoc_claude_config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_PROMPTS = {
    "🛠️ 硬件工程师 / 芯片规格书 (Datasheet)": "/no_think 你是一位资深硬件工程师及电子元器件规格书(Datasheet)资深翻译专家。请将输入的英文技术文档翻译为专业、地道、严谨的中文。\n1. 严禁翻译元器件型号、引脚名(VCC, GND, EN, SW, FB, COMP, BST, SDA, SCL等)、封装名称(SOP, QFN, SOT-23等)。\n2. 保持电气参数缩写及单位(Vin, Vout, Rds(on), Tj, ESR, µA, mA, A, mV, V, mΩ, Ω, µH, nF, µF, kHz, MHz等)不变。\n3. 符合国内半导体芯片手册用语习惯(如 欠压锁定、静态电流、导通电阻、打嗝模式、热关断等)。\n4. 仅输出翻译后的文本，不带任何多余解释。",
    "🎓 学术科研 / 科技论文 (Paper)": "You are a professional scientific paper translation engine. Translate the following text into natural, formal, and precise Simplified Chinese while keeping academic rigor. Retain mathematical equations, technical terms, citations, and abbreviations in their original forms.",
    "💻 嵌入式 / 单片机与固件手册 (Firmware)": "你是一位资深嵌入式软件与底层固件工程师。请将以下文档翻译为严谨规范的中文。保持寄存器名称(如 CR1, SR, DR)、位域操作(如 BIT[7:0], R/W, Clear-on-read)、外设名(如 USART, SPI, I2C, DMA, ADC, TIM)及中断向量名称完全不变。",
    "🌐 通用精简 / 现代中文 (General)": "你是资深的专业科技翻译家。请将英文翻译为符合现代中文表达习惯的高质量译文，用语精炼准确、通顺自然，保留专用代码、品牌名与专业术语。"
}

LANG_MAP = {
    "英语 (English)": "en",
    "简体中文 (Simplified Chinese)": "zh",
    "繁体中文 (Traditional Chinese)": "zh-tw",
    "日语 (Japanese)": "ja",
    "韩语 (Korean)": "ko",
    "德语 (German)": "de",
    "法语 (French)": "fr",
    "俄语 (Russian)": "ru",
    "西班牙语 (Spanish)": "es"
}

LANG_REV_MAP = {v: k for k, v in LANG_MAP.items()}

DEFAULT_CONFIG = {
    "base_url": "https://moyuu.cc/v1",
    "api_key": "***REMOVED***",
    "model": "gemini-3.1-flash-lite-preview",
    "lang_in": "en",
    "lang_out": "zh",
    "qps": "4",
    "translate_table_text": True,
    "current_prompt_title": "🛠️ 硬件工程师 / 芯片规格书 (Datasheet)",
    "prompts": DEFAULT_PROMPTS
}

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = {**DEFAULT_CONFIG, **data}
                if "prompts" not in cfg or not cfg["prompts"]:
                    cfg["prompts"] = DEFAULT_PROMPTS
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

current_cfg = load_config()

# Claude 风格极简温润定制主题 CSS
CLAUDE_CUSTOM_CSS = """
:root {
    --claude-bg: #FAF9F5;
    --claude-surface: #FFFFFF;
    --claude-border: #E5E4DE;
    --claude-text: #2D2B28;
    --claude-text-muted: #736E65;
    --claude-accent: #DA7756;
    --claude-accent-hover: #C86747;
    --claude-accent-soft: #FBF0EB;
}

body, .gradio-container {
    background-color: var(--claude-bg) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    color: var(--claude-text) !important;
}

.gr-panel, .gr-box, .gr-compact {
    background-color: var(--claude-surface) !important;
    border: 1px solid var(--claude-border) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
}

.gr-accordion {
    background-color: var(--claude-surface) !important;
    border: 1px solid var(--claude-border) !important;
    border-radius: 10px !important;
    margin-bottom: 12px !important;
}

.gr-button-primary {
    background: linear-gradient(135deg, #DA7756 0%, #C86747 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    box-shadow: 0 2px 4px rgba(218, 119, 86, 0.25) !important;
    transition: all 0.2s ease !important;
}

.gr-button-primary:hover {
    background: linear-gradient(135deg, #C86747 0%, #B85B3D 100%) !important;
    box-shadow: 0 4px 8px rgba(218, 119, 86, 0.35) !important;
    transform: translateY(-1px);
}

.gr-button-secondary {
    background-color: #F4F3ED !important;
    color: var(--claude-text) !important;
    border: 1px solid var(--claude-border) !important;
    border-radius: 8px !important;
}

.gr-button-secondary:hover {
    background-color: #EAE8DF !important;
}

input, textarea, select {
    border-radius: 8px !important;
    border: 1px solid var(--claude-border) !important;
}

input:focus, textarea:focus {
    border-color: var(--claude-accent) !important;
    box-shadow: 0 0 0 2px var(--claude-accent-soft) !important;
}
"""

def on_prompt_select(selected_title, user_prompts):
    return user_prompts.get(selected_title, "")

def on_save_prompt(current_title, current_text, user_prompts):
    if not current_title.strip():
        gr.Warning("预设名称不能为空！")
        return gr.update(), user_prompts
    new_prompts = dict(user_prompts)
    new_prompts[current_title.strip()] = current_text.strip()
    
    cfg = load_config()
    cfg["prompts"] = new_prompts
    cfg["current_prompt_title"] = current_title.strip()
    save_config(cfg)
    
    gr.Info(f"已保存模板预设：{current_title.strip()}")
    choices = list(new_prompts.keys())
    return gr.update(choices=choices, value=current_title.strip()), new_prompts

def on_delete_prompt(selected_title, user_prompts):
    if len(user_prompts) <= 1:
        gr.Warning("至少需要保留一个提示词模板！")
        return gr.update(), gr.update(), user_prompts
    new_prompts = dict(user_prompts)
    if selected_title in new_prompts:
        del new_prompts[selected_title]
    new_default = list(new_prompts.keys())[0]
    
    cfg = load_config()
    cfg["prompts"] = new_prompts
    cfg["current_prompt_title"] = new_default
    save_config(cfg)
    
    gr.Info(f"已删除预设：{selected_title}")
    return gr.update(choices=list(new_prompts.keys()), value=new_default), new_prompts[new_default], new_prompts

def run_translation(
    file_obj,
    base_url,
    api_key,
    model,
    lang_in_name,
    lang_out_name,
    qps,
    translate_table,
    system_prompt,
    user_prompts,
    selected_prompt_title,
    progress=gr.Progress()
):
    if not file_obj:
        raise gr.Error("请先上传需要翻译的 PDF 文件！")
    
    lang_in = LANG_MAP.get(lang_in_name, "en")
    lang_out = LANG_MAP.get(lang_out_name, "zh")
    
    cfg_to_save = {
        "base_url": base_url.strip(),
        "api_key": api_key.strip(),
        "model": model.strip(),
        "lang_in": lang_in,
        "lang_out": lang_out,
        "qps": str(qps),
        "translate_table_text": bool(translate_table),
        "current_prompt_title": selected_prompt_title,
        "prompts": user_prompts
    }
    save_config(cfg_to_save)
    
    input_pdf = Path(file_obj)
    output_dir = Path(r"D:\Program Files\PDFMathTranslate\pdf2zh_files")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        sys.executable,
        "-m", "babeldoc.main",
        "--files", str(input_pdf),
        "--output", str(output_dir),
        "--lang-in", lang_in,
        "--lang-out", lang_out,
        "--qps", str(qps),
        "--openai",
        "--openai-base-url", base_url.strip(),
        "--openai-api-key", api_key.strip(),
        "--openai-model", model.strip(),
    ]
    
    if translate_table:
        cmd.append("--translate-table-text")
    if system_prompt.strip():
        cmd.extend(["--custom-system-prompt", system_prompt.strip()])
        
    progress(0.1, desc="BabelDOC 0.6.4 正在解析版面及提取文本与表格...")
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1
    )
    
    for line in iter(proc.stdout.readline, ''):
        line = line.strip()
        if line:
            print("[BabelDOC 0.6.4]:", line)
            if "%" in line:
                progress(0.6, desc=f"翻译处理中: {line[:55]}")
                
    proc.stdout.close()
    return_code = proc.wait()
    
    if return_code != 0:
        raise gr.Error("BabelDOC 翻译处理遇到错误，请查看控制台日志。")
        
    stem = input_pdf.stem
    dual_candidate = output_dir / f"{stem}.{lang_out}.dual.pdf"
    
    if not dual_candidate.exists():
        duals = list(output_dir.glob(f"{stem}*.dual.pdf"))
        if not duals:
            duals = list(output_dir.glob("*.dual.pdf"))
        if duals:
            duals.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            dual_candidate = duals[0]
            
    progress(1.0, desc="翻译排版完成！")
    return str(dual_candidate), str(dual_candidate)

with gr.Blocks(title="BabelDOC - 科技文档翻译器", css=CLAUDE_CUSTOM_CSS) as demo:
    prompt_state = gr.State(current_cfg.get("prompts", DEFAULT_PROMPTS))
    
    with gr.Row():
        gr.Markdown(
            """
            # 📜 BabelDOC 文档翻译
            沉浸式翻译同款 **BabelDOC 0.6.4** 最新内核 · 硬件规格书/学术论文级排版 · 支持完整表格翻译与私有模型配置
            """
        )
    
    with gr.Row():
        with gr.Column(scale=5):
            file_input = gr.File(
                label="📁 上传 PDF 文档 (Datasheet / 学术论文)",
                file_types=[".pdf"],
                height=140
            )
            
            with gr.Accordion("🔑 API 与模型连接配置 (自动保存)", open=True):
                base_url = gr.Textbox(
                    label="OpenAI 兼容 Base URL",
                    placeholder="https://api.deepseek.com/v1 或中转接口",
                    value=current_cfg["base_url"]
                )
                with gr.Row():
                    api_key = gr.Textbox(
                        label="API Key",
                        type="password",
                        placeholder="sk-...",
                        value=current_cfg["api_key"],
                        scale=3
                    )
                    model = gr.Textbox(
                        label="Model 代号",
                        placeholder="deepseek-chat / gpt-4o-mini 等",
                        value=current_cfg["model"],
                        scale=2
                    )
                
            with gr.Accordion("🌐 语言与排版参数", open=True):
                with gr.Row():
                    lang_in_dd = gr.Dropdown(
                        label="源语言 (Translate From)",
                        choices=list(LANG_MAP.keys()),
                        value=LANG_REV_MAP.get(current_cfg.get("lang_in", "en"), "英语 (English)"),
                        scale=2
                    )
                    lang_out_dd = gr.Dropdown(
                        label="目标语言 (Translate To)",
                        choices=list(LANG_MAP.keys()),
                        value=LANG_REV_MAP.get(current_cfg.get("lang_out", "zh"), "简体中文 (Simplified Chinese)"),
                        scale=2
                    )
                    qps = gr.Textbox(
                        label="并发线程数 (QPS)",
                        value=current_cfg.get("qps", "4"),
                        scale=1
                    )
                translate_table = gr.Checkbox(
                    label="开启表格内容翻译 (--translate-table-text)",
                    value=current_cfg.get("translate_table_text", True),
                    info="规格书必开：开启后将完整解析并翻译电气特性参数表、引脚说明表。"
                )

            with gr.Accordion("🎯 提示词预设库 (Prompt Management)", open=True):
                prompt_keys = list(prompt_state.value.keys())
                saved_key = current_cfg.get("current_prompt_title", prompt_keys[0])
                if saved_key not in prompt_keys:
                    saved_key = prompt_keys[0]
                    
                with gr.Row():
                    prompt_selector = gr.Dropdown(
                        label="选择已保存的场景模板",
                        choices=prompt_keys,
                        value=saved_key,
                        scale=3
                    )
                    del_prompt_btn = gr.Button("🗑️ 删除该模板", variant="secondary", scale=1)
                
                prompt_name_input = gr.Textbox(
                    label="当前模板名称 (修改此处可保存为新模板)",
                    value=saved_key
                )
                system_prompt = gr.Textbox(
                    label="系统提示词指令 (System Prompt)",
                    lines=6,
                    value=prompt_state.value[saved_key]
                )
                save_prompt_btn = gr.Button("💾 保存 / 更新此提示词模板", variant="secondary")

            trans_btn = gr.Button("✨ 开始高质量排版翻译 (生成双语对照 PDF)", variant="primary", size="lg")
            
        with gr.Column(scale=5):
            gr.Markdown("### 📖 双语对照翻译预览与成果")
            output_file = gr.File(label="📥 下载翻译后的双语 PDF")
            output_preview = PDF(label="在线文档阅读器", height=780)
            
    # 事件绑定
    prompt_selector.change(
        fn=lambda k, p: (k, p.get(k, "")),
        inputs=[prompt_selector, prompt_state],
        outputs=[prompt_name_input, system_prompt]
    )
    
    save_prompt_btn.click(
        fn=on_save_prompt,
        inputs=[prompt_name_input, system_prompt, prompt_state],
        outputs=[prompt_selector, prompt_state]
    )
    
    del_prompt_btn.click(
        fn=on_delete_prompt,
        inputs=[prompt_selector, prompt_state],
        outputs=[prompt_selector, system_prompt, prompt_state]
    ).then(
        fn=lambda sel: sel,
        inputs=[prompt_selector],
        outputs=[prompt_name_input]
    )

    trans_btn.click(
        run_translation,
        inputs=[
            file_input,
            base_url,
            api_key,
            model,
            lang_in_dd,
            lang_out_dd,
            qps,
            translate_table,
            system_prompt,
            prompt_state,
            prompt_name_input
        ],
        outputs=[output_file, output_preview]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, inbrowser=True)