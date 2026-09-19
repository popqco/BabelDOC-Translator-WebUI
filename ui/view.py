import os
import subprocess
from pathlib import Path
import gradio as gr
from gradio_pdf import PDF

from core.config import load_app_config, save_app_config, get_default_output_dir
from core.prompt_manager import load_prompts, save_prompts
from core.task_manager import TaskManager

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
    --claude-success: #2E7D32;
    --claude-danger: #C62828;
}

/* 夜间模式颜色变量 (Claude Dark Charcoal & Terracotta 配色) */
.dark, :root .dark, [data-theme="dark"] {
    --claude-bg: #1E1E1E !important;
    --claude-surface: #2A2A28 !important;
    --claude-border: #3E3D39 !important;
    --claude-text: #ECEBE8 !important;
    --claude-text-muted: #A8A59E !important;
    --claude-accent: #E07A5F !important;
    --claude-accent-hover: #EC896E !important;
    --claude-accent-soft: #382C27 !important;
    --claude-success: #7BC67E !important;
    --claude-danger: #F2A2A2 !important;
}

body, .gradio-container {
    background-color: var(--claude-bg) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;
    color: var(--claude-text) !important;
}

.dark body, .dark .gradio-container, [data-theme="dark"] .gradio-container {
    background-color: var(--claude-bg) !important;
    color: var(--claude-text) !important;
}

.gr-panel, .gr-box, .gr-compact {
    background-color: var(--claude-surface) !important;
    border: 1px solid var(--claude-border) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
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

/* 夜间模式按钮适配 */
.dark .gr-button-secondary, [data-theme="dark"] .gr-button-secondary {
    background-color: #33322E !important;
    color: var(--claude-text) !important;
    border: 1px solid var(--claude-border) !important;
}

.dark .gr-button-secondary:hover, [data-theme="dark"] .gr-button-secondary:hover {
    background-color: #3F3E39 !important;
}

/* 统一输入框与文本域的夜间及日间模式样式 */
input, textarea, select {
    border-radius: 8px !important;
    border: 1px solid var(--claude-border) !important;
    background-color: var(--claude-surface) !important;
    color: var(--claude-text) !important;
}

/* 彻底解决 Textbox 在夜间模式下外部容器或输入框变白的突兀问题 */
.dark input, .dark textarea, .dark select,
[data-theme="dark"] input, [data-theme="dark"] textarea, [data-theme="dark"] select,
.dark .block, [data-theme="dark"] .block,
.dark [data-testid="textbox"], [data-theme="dark"] [data-testid="textbox"] {
    background-color: #242422 !important;
    color: #ECEBE8 !important;
    border-color: #3E3D39 !important;
}

.dark label.container, [data-theme="dark"] label.container {
    background-color: #242422 !important;
}

/* 解决 Gradio Textbox 组件中内部 input 被默认变量覆盖而发白的问题 */
.dark input[data-testid="textbox"],
[data-theme="dark"] input[data-testid="textbox"],
.dark textarea[data-testid="textbox"],
[data-theme="dark"] textarea[data-testid="textbox"] {
    background-color: #1E1E1C !important;
    color: #ECEBE8 !important;
    border: 1px solid #3E3D39 !important;
}

input:focus, textarea:focus,
.dark input:focus, .dark textarea:focus,
[data-theme="dark"] input:focus, [data-theme="dark"] textarea:focus {
    border-color: var(--claude-accent) !important;
    box-shadow: 0 0 0 2px var(--claude-accent-soft) !important;
}

/* 标题与 Markdown 文本在明暗模式下的对比度增强 */
h1, h2, h3, h4, h5, h6, .markdown h1, .markdown h2, .markdown h3 {
    color: var(--claude-text) !important;
}

.dark h1, .dark h2, .dark h3, .dark h4, .dark p, .dark span,
[data-theme="dark"] h1, [data-theme="dark"] h2, [data-theme="dark"] h3, [data-theme="dark"] p {
    color: var(--claude-text) !important;
}

/* 日志框样式 */
.log-box textarea {
    font-family: Consolas, "Courier New", monospace !important;
    font-size: 12px !important;
    line-height: 1.4 !important;
    background-color: #F8F7F2 !important;
    color: #3C3836 !important;
}

.dark .log-box textarea, [data-theme="dark"] .log-box textarea {
    background-color: #191918 !important;
    color: #D4D2CD !important;
    border: 1px solid var(--claude-border) !important;
}

/* 拖拽上传框适配 */
.file-upload-box {
    min-height: 145px !important;
}
.file-upload-box .upload-container, 
.file-upload-box [data-testid="file-upload"],
.file-upload-box .drop-zone {
    min-height: 135px !important;
    padding: 8px !important;
}
.file-upload-box .wrap {
    min-height: 95px !important;
    padding-top: 2px !important;
    padding-bottom: 6px !important;
    justify-content: center !important;
}
.file-upload-box .icon-wrap {
    margin-bottom: 4px !important;
    width: 24px !important;
}
.file-upload-box .file-preview {
    pointer-events: auto !important;
}

.dark .file-upload-box, [data-theme="dark"] .file-upload-box {
    background-color: var(--claude-surface) !important;
    border: 1px dashed var(--claude-border) !important;
}
.dark .file-upload-box .wrap, [data-theme="dark"] .file-upload-box .wrap {
    color: var(--claude-text) !important;
}

.status-pill {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    display: inline-block;
}
"""

def open_folder(folder_path: str):
    if folder_path and os.path.exists(folder_path):
        subprocess.Popen(["explorer.exe", os.path.normpath(folder_path)])
    else:
        gr.Warning("输出文件夹尚未生成或不存在。")

def pick_folder_dialog(current_val: str):
    """弹出原生 Windows 文件夹选择框"""
    try:
        import webview
        if webview.windows:
            win = webview.windows[0]
            chosen = win.create_file_dialog(dialog_type=webview.FOLDER_DIALOG, directory=current_val)
            if chosen and len(chosen) > 0:
                selected_dir = chosen[0]
                save_app_config({"output_dir": selected_dir})
                return selected_dir
        else:
            gr.Warning("未检测到桌面窗口环境，无法打开系统目录选择框。")
    except Exception as e:
        print(f"Native folder dialog fallback: {e}")
    return current_val

def create_ui():
    cfg = load_app_config()
    prompts = load_prompts()
    tm = TaskManager()

    def format_pending_display():
        with tm.lock:
            if not tm.pending_queue:
                return "（当前队列为空，请拖入或点击添加 PDF）"
            lines = [f"**待翻译清单 ({len(tm.pending_queue)} 个文件)**："]
            for i, item in enumerate(tm.pending_queue, start=1):
                lines.append(f"{i}. 📄 **{item['name']}**")
            return "\n".join(lines)

    with gr.Blocks(title="BabelDOC 科技文档翻译器", css=CLAUDE_CUSTOM_CSS) as demo:
        prompt_state = gr.State(prompts)
        selected_batch_id = gr.State("")

        with gr.Row():
            gr.Markdown(
                """
                # 📜 BabelDOC 科技文档/芯片规格书批量翻译器
                **BabelDOC 0.6.4** 官方内核 · 可选生成仅译文/双语对照 · 动态任务队列追加与取消 · 原生桌面交付
                """
            )

        with gr.Row():
            # ================= 左侧控制面板 =================
            with gr.Column(scale=5):
                # 上传区域：支持拖入与选择，拖入后立即按 hash 排重入队
                file_input = gr.File(
                    label="📁 拖入或选择 PDF 文档 (支持多次追加拖拽)",
                    file_types=[".pdf"],
                    file_count="multiple",
                    height=140,
                    elem_classes=["file-upload-box"]
                )

                with gr.Row():
                    remove_last_btn = gr.Button("➖ 移除最后一项", variant="secondary", size="sm")
                    clear_btn = gr.Button("🗑️ 清空待翻译列表", variant="secondary", size="sm")

                pending_display = gr.Markdown(value=format_pending_display())

                # 输出格式与交付控制 (立即持久化记忆)
                with gr.Accordion("⚙️ 输出文件与交付方式设置 (自动记忆)", open=True):
                    with gr.Row():
                        out_mono_cb = gr.Checkbox(
                            label="仅译文版 PDF (.mono.pdf)",
                            value=cfg.get("output_mono", False),
                            info="格式保留，纯译文排版"
                        )
                        out_dual_cb = gr.Checkbox(
                            label="双语对照版 PDF (.dual.pdf)",
                            value=cfg.get("output_dual", True),
                            info="原文与译文逐段并排对照"
                        )
                    with gr.Row():
                        gen_zip_cb = gr.Checkbox(
                            label="📦 自动打包为 ZIP 交付包",
                            value=cfg.get("generate_zip", False),
                            info="将本批次成功生成的 PDF 压缩打包"
                        )
                        zip_mode_dd = gr.Dropdown(
                            label="ZIP 交付策略",
                            choices=["保留独立 PDF + ZIP (both)", "仅保留 ZIP (zip_only)"],
                            value="保留独立 PDF + ZIP (both)" if cfg.get("zip_delivery_mode", "both") == "both" else "仅保留 ZIP (zip_only)",
                            interactive=cfg.get("generate_zip", False),
                            scale=2
                        )

                    with gr.Row():
                        output_dir_box = gr.Textbox(
                            label="成果保存根目录",
                            value=cfg.get("output_dir", get_default_output_dir()),
                            interactive=True,
                            scale=4
                        )
                        browse_dir_btn = gr.Button("📂 浏览选择...", variant="secondary", scale=1)

                with gr.Accordion("🔑 API 与模型连接配置 (自动保存)", open=False):
                    base_url = gr.Textbox(label="OpenAI 兼容 Base URL", value=cfg.get("base_url", "https://moyuu.cc/v1"))
                    with gr.Row():
                        api_key = gr.Textbox(label="API Key", type="password", value=cfg.get("api_key", ""), scale=3)
                        model = gr.Textbox(label="Model 代号", value=cfg.get("model", "gemini-3.1-flash-lite-preview"), scale=2)

                with gr.Accordion("🌐 语言与排版参数", open=False):
                    with gr.Row():
                        lang_in_dd = gr.Dropdown(
                            label="源语言",
                            choices=list(LANG_MAP.keys()),
                            value=LANG_REV_MAP.get(cfg.get("lang_in", "en"), "英语 (English)"),
                            scale=2
                        )
                        lang_out_dd = gr.Dropdown(
                            label="目标语言",
                            choices=list(LANG_MAP.keys()),
                            value=LANG_REV_MAP.get(cfg.get("lang_out", "zh"), "简体中文 (Simplified Chinese)"),
                            scale=2
                        )
                        qps = gr.Textbox(label="并发线程数 (QPS)", value=cfg.get("qps", "4"), scale=1)
                    translate_table = gr.Checkbox(
                        label="开启表格内容翻译 (--translate-table-text)",
                        value=cfg.get("translate_table_text", True),
                        info="规格书必开：解析并翻译电气特性与引脚表。"
                    )

                with gr.Accordion("🎯 提示词预设库 (Prompt Management)", open=False):
                    prompt_keys = list(prompts.keys())
                    current_key = cfg.get("current_prompt_title", prompt_keys[0])
                    if current_key not in prompt_keys:
                        current_key = prompt_keys[0]

                    with gr.Row():
                        prompt_selector = gr.Dropdown(label="选择场景模板", choices=prompt_keys, value=current_key, scale=3)
                        del_prompt_btn = gr.Button("🗑️ 删除模板", variant="secondary", scale=1)

                    prompt_name_input = gr.Textbox(label="当前模板名称", value=current_key)
                    system_prompt = gr.Textbox(label="系统提示词指令", lines=5, value=prompts[current_key])
                    save_prompt_btn = gr.Button("💾 保存 / 更新此提示词模板", variant="secondary")

                # 任务主操作区
                with gr.Row():
                    start_trans_btn = gr.Button("✨ 开始排版翻译", variant="primary", scale=3, size="lg")
                    stop_after_btn = gr.Button("⏸️ 完成当前后停止", variant="secondary", scale=2)
                    cancel_now_btn = gr.Button("⏹️ 立即取消整批", variant="secondary", scale=2)

                with gr.Accordion("📜 运行与内核日志 (实时增量滚动)", open=False):
                    log_output = gr.Textbox(
                        label="Log Stream",
                        lines=9,
                        interactive=False,
                        elem_classes=["log-box"],
                        value="就绪。\n"
                    )

            # ================= 右侧成果与任务管理 =================
            with gr.Column(scale=5):
                gr.Markdown("### 📖 翻译成果预览与任务历史")

                # 批次状态与快速操作
                with gr.Row():
                    open_curr_folder_btn = gr.Button("📁 一键打开成果文件夹", variant="primary", scale=2)
                    repack_zip_btn = gr.Button("📦 补打/重新打包 ZIP", variant="secondary", scale=2)

                batch_summary_md = gr.Markdown("当前尚无正在运行或完成的批次。")

                with gr.Row():
                    pdf_result_selector = gr.Dropdown(allow_custom_value=True, 
                        label="📑 选择已完成的文件版本 (按文档归组，点击即预览)",
                        choices=[],
                        value="",
                        interactive=True,
                        visible=False,
                        scale=4
                    )
                    retry_failed_btn = gr.Button("🔄 重试本批失败文件", variant="secondary", visible=False, scale=2)

                with gr.Row(visible=False) as download_row:
                    batch_zip_file = gr.File(label="📦 ZIP 交付包", interactive=False)
                    single_pdf_file = gr.File(label="📄 当前选中的 PDF", interactive=False)

                # PDF 阅读器
                output_preview = PDF(label="桌面内置 PDF 阅读器", height=660)

                with gr.Accordion("📋 历史任务批次记录", open=False):
                    history_dropdown = gr.Dropdown(label="选择历史批次", choices=[], allow_custom_value=True)
                    history_detail_md = gr.Markdown("无历史记录")
                    open_hist_folder_btn = gr.Button("📂 打开该历史批次目录", variant="secondary", size="sm")

        # 每秒刷新定时器，用于实时驱动日志与任务进度展示
        timer = gr.Timer(1.0)

        # ================= 事件绑定 =================
        # 输出配置即时自动保存
        def on_output_cfg_change(mono_v, dual_v, zip_v, zip_m, out_d):
            if not mono_v and not dual_v:
                gr.Warning("注意：仅译文(mono)与双语对照(dual)不能同时关闭，已为您自动重置为双语对照！")
                dual_v = True
            mode_val = "both" if "both" in zip_m else "zip_only"
            save_app_config({
                "output_mono": bool(mono_v),
                "output_dual": bool(dual_v),
                "generate_zip": bool(zip_v),
                "zip_delivery_mode": mode_val,
                "output_dir": out_d.strip()
            })
            return mono_v, dual_v, gr.update(interactive=bool(zip_v))

        # 复选框/下拉用 change 即时保存；输出目录为文本框，
        # 改用 blur（失焦）保存，避免每敲一个字符就写一次磁盘
        for comp in [out_mono_cb, out_dual_cb, gen_zip_cb, zip_mode_dd]:
            comp.change(
                fn=on_output_cfg_change,
                inputs=[out_mono_cb, out_dual_cb, gen_zip_cb, zip_mode_dd, output_dir_box],
                outputs=[out_mono_cb, out_dual_cb, zip_mode_dd]
            )
        output_dir_box.blur(
            fn=on_output_cfg_change,
            inputs=[out_mono_cb, out_dual_cb, gen_zip_cb, zip_mode_dd, output_dir_box],
            outputs=[out_mono_cb, out_dual_cb, zip_mode_dd]
        )

        browse_dir_btn.click(
            fn=pick_folder_dialog,
            inputs=[output_dir_box],
            outputs=[output_dir_box]
        )

        # 待翻译文件拖拽追加
        def on_files_uploaded(incoming_files):
            if not incoming_files:
                return format_pending_display(), None
            paths = [f.name if hasattr(f, 'name') else str(f) for f in incoming_files]
            # 运行状态快照（避免绕过锁直接读取共享状态）
            with tm.lock:
                running = bool(tm.active_batch and tm.active_batch.status == "running")
            # 若当前有任务正在运行，则动态追加到活动批次；否则加入待办
            if running:
                added, msg = tm.append_to_active_batch(paths)
                gr.Info(msg)
            else:
                added, _ = tm.add_to_pending(paths)
                gr.Info(f"已添加 {added} 个文档至待翻译列表")
            return format_pending_display(), None

        file_input.upload(
            fn=on_files_uploaded,
            inputs=[file_input],
            outputs=[pending_display, file_input]
        )

        def on_remove_last():
            with tm.lock:
                idx = len(tm.pending_queue) - 1
                empty = idx < 0
            if empty:
                gr.Warning("待翻译列表已为空，没有可移除的文件。")
            else:
                tm.remove_from_pending(idx)
            return format_pending_display()

        remove_last_btn.click(
            fn=on_remove_last,
            inputs=None,
            outputs=[pending_display]
        )

        clear_btn.click(
            fn=lambda: (tm.clear_pending(), format_pending_display())[1],
            inputs=None,
            outputs=[pending_display]
        )

        # 提示词管理
        prompt_selector.change(
            fn=lambda k, p: (k, p.get(k, "")),
            inputs=[prompt_selector, prompt_state],
            outputs=[prompt_name_input, system_prompt]
        )

        def on_save_prompt_handler(title, text, cur_prompts):
            if not title.strip():
                gr.Warning("模板名称不能为空！")
                return gr.update(), cur_prompts
            new_p = dict(cur_prompts)
            new_p[title.strip()] = text.strip()
            save_prompts(new_p)
            save_app_config({"current_prompt_title": title.strip()})
            gr.Info(f"已保存场景模板: {title.strip()}")
            return gr.update(choices=list(new_p.keys()), value=title.strip()), new_p

        save_prompt_btn.click(
            fn=on_save_prompt_handler,
            inputs=[prompt_name_input, system_prompt, prompt_state],
            outputs=[prompt_selector, prompt_state]
        )

        def on_delete_prompt_handler(selected_t, cur_prompts):
            if len(cur_prompts) <= 1:
                gr.Warning("至少保留一个模板！")
                return gr.update(), gr.update(), cur_prompts
            new_p = dict(cur_prompts)
            if selected_t in new_p:
                del new_p[selected_t]
            new_first = list(new_p.keys())[0]
            save_prompts(new_p)
            gr.Info(f"已删除模板: {selected_t}")
            return gr.update(choices=list(new_p.keys()), value=new_first), new_p[new_first], new_p

        del_prompt_btn.click(
            fn=on_delete_prompt_handler,
            inputs=[prompt_selector, prompt_state],
            outputs=[prompt_selector, system_prompt, prompt_state]
        ).then(
            fn=lambda sel: sel,
            inputs=[prompt_selector],
            outputs=[prompt_name_input]
        )

        # 开始翻译
        def on_start_translation(mono_v, dual_v, zip_v, zip_m, out_d, b_url, key, mdl, l_in, l_out, qps_v, tbl_v, prompt_t, prompt_title):
            if not tm.pending_queue:
                raise gr.Error("待翻译清单为空，请先拖入或添加 PDF 文档！")
            if not mono_v and not dual_v:
                raise gr.Error("至少需要勾选一种 PDF 输出（仅译文 或 双语对照）！")

            # QPS 必须为正数，否则直接传给内核会导致启动失败
            try:
                qps_num = float(str(qps_v).strip())
                if qps_num <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise gr.Error("并发线程数 (QPS) 必须为大于 0 的数字！") from None

            zip_m_str = "both" if "both" in zip_m else "zip_only"
            # 保存当前所有配置
            save_app_config({
                "base_url": b_url.strip(),
                "api_key": key.strip(),
                "model": mdl.strip(),
                "lang_in": LANG_MAP.get(l_in, "en"),
                "lang_out": LANG_MAP.get(l_out, "zh"),
                "qps": str(qps_v),
                "translate_table_text": bool(tbl_v),
                "current_prompt_title": (prompt_title or "").strip(),
                "output_mono": bool(mono_v),
                "output_dual": bool(dual_v),
                "generate_zip": bool(zip_v),
                "zip_delivery_mode": zip_m_str,
                "output_dir": out_d.strip()
            })

            opts = {
                "base_url": b_url.strip(),
                "api_key": key.strip(),
                "model": mdl.strip(),
                "lang_in": LANG_MAP.get(l_in, "en"),
                "lang_out": LANG_MAP.get(l_out, "zh"),
                "qps": str(qps_v),
                "translate_table_text": bool(tbl_v),
                "system_prompt": prompt_t.strip(),
                "current_prompt_title": (prompt_title or "").strip(),
                "output_mono": bool(mono_v),
                "output_dual": bool(dual_v),
                "generate_zip": bool(zip_v),
                "zip_delivery_mode": zip_m_str,
                "output_dir": out_d.strip()
            }

            ok, msg = tm.start_batch(opts)
            if not ok:
                raise gr.Error(f"启动失败：{msg}")
            gr.Info(f"已成功启动批量排版翻译任务（{msg}）！")
            return format_pending_display()

        start_trans_btn.click(
            fn=on_start_translation,
            inputs=[
                out_mono_cb, out_dual_cb, gen_zip_cb, zip_mode_dd, output_dir_box,
                base_url, api_key, model, lang_in_dd, lang_out_dd, qps, translate_table, system_prompt,
                prompt_selector
            ],
            outputs=[pending_display]
        )

        # 停止控制（给出明确受理反馈）
        def on_stop_after():
            if tm.request_stop("stop_after_current"):
                gr.Info("已请求【完成当前文档后停止】，后续排队文档将取消。")
            else:
                gr.Warning("当前没有正在运行的批次。")

        def on_cancel_now():
            if tm.request_stop("cancel_immediately"):
                gr.Info("已请求【立即取消整批任务】，正在终止翻译进程。")
            else:
                gr.Warning("当前没有正在运行的批次。")

        stop_after_btn.click(fn=on_stop_after, inputs=None, outputs=None)
        cancel_now_btn.click(fn=on_cancel_now, inputs=None, outputs=None)

        # 打开所在文件夹
        def on_open_curr_folder():
            with tm.lock:
                out_dir = tm.active_batch.output_dir if tm.active_batch else None
            open_folder(out_dir or cfg.get("output_dir"))

        open_curr_folder_btn.click(fn=on_open_curr_folder, inputs=None, outputs=None)

        # 补打/重新打包 ZIP
        def on_repack_zip():
            with tm.lock:
                batch_id = tm.active_batch.batch_id if tm.active_batch else None
            if not batch_id:
                gr.Warning("当前无活动批次。")
                return None
            ok, res = tm.pack_existing_batch_zip(batch_id, delete_standalone_pdfs=False)
            if ok:
                gr.Info(f"成功打包 ZIP: {Path(res).name}")
                return res
            else:
                gr.Warning(res)
                return None

        repack_zip_btn.click(
            fn=on_repack_zip,
            inputs=None,
            outputs=[batch_zip_file]
        )

        # 切换成果预览：下拉选项改为 (展示名, 真实路径) 二元组，
        # 直接按路径精确匹配，不再用文件名子串猜测
        def on_switch_result(selected_path):
            if not selected_path:
                return None, None
            if Path(selected_path).exists():
                return selected_path, selected_path
            gr.Warning("所选文件已不存在（可能已被移动或清理）。")
            return None, None

        pdf_result_selector.change(
            fn=on_switch_result,
            inputs=[pdf_result_selector],
            outputs=[single_pdf_file, output_preview]
        )

        # 重试失败文件
        def on_retry_failed_click(b_url, key, mdl):
            with tm.lock:
                batch_id = tm.active_batch.batch_id if tm.active_batch else None
            if not batch_id:
                gr.Warning("当前无活动批次！")
                return
            conn = {"base_url": b_url.strip(), "api_key": key.strip(), "model": mdl.strip()}
            ok, msg = tm.retry_failed_tasks(batch_id, conn)
            if ok:
                gr.Info(f"重试已启动！{msg}")
            else:
                gr.Warning(msg)

        retry_failed_btn.click(
            fn=on_retry_failed_click,
            inputs=[base_url, api_key, model],
            outputs=None
        )

        # 历史记录切换
        def on_history_select(selected_b_id):
            if not selected_b_id:
                return "请选择历史批次", gr.update()
            target = None
            for r in tm.history_records:
                if r["batch_id"] == selected_b_id:
                    target = r
                    break
            if not target:
                return "未找到记录", gr.update()

            md = [
                f"### 批次: {target['batch_id']}",
                f"- **状态**: {target['status']} ({target['summary_message']})",
                f"- **创建时间**: {target['created_at']}",
                f"- **成果目录**: `{target['output_dir']}`",
                f"- **ZIP 包**: `{Path(target['zip_path']).name if target.get('zip_path') else '无'}`",
                "\n**包含文档**："
            ]
            for t in target["tasks"]:
                ico = "✓" if t["status"] == "success" else ("✗" if t["status"] == "failed" else "⏸")
                err = f" ({t['error_message']})" if t.get("error_message") else ""
                md.append(f"- {ico} **{t['filename']}**: `{t['status']}`{err}")
            return "\n".join(md), selected_b_id

        history_dropdown.change(
            fn=on_history_select,
            inputs=[history_dropdown],
            outputs=[history_detail_md, selected_batch_id]
        )

        open_hist_folder_btn.click(
            fn=lambda b_id: [open_folder(r["output_dir"]) for r in tm.history_records if r["batch_id"] == b_id],
            inputs=[selected_batch_id],
            outputs=None
        )

        # 定时轮询更新（实时增量日志、任务进度状态卡与产物下拉）
        # 上一次交付给 gr.File 的 ZIP 路径：仅在变化时才更新组件，
        # 避免每秒对大压缩包做一次重新拷贝/哈希
        last_zip_state = gr.State(None)
        # 上一次各组件的渲染签名：内容未变化时返回 gr.update() 跳过整卡重渲染，
        # 否则状态卡会每秒闪烁一次
        last_render_state = gr.State(None)

        def on_timer_tick(current_choice, prev_zip, prev_render):
            prev_render = prev_render or {}
            # 锁内只取轻量快照，文件系统探测与拼接放在锁外，
            # 避免每秒轮询与翻译工作线程互相阻塞
            with tm.lock:
                logs_tail = list(tm.logs)[-150:]
                if not tm.active_batch:
                    hist_ids = [r["batch_id"] for r in tm.history_records]
                    if prev_render.get("phase") == "empty":
                        return (
                            "".join(logs_tail) if logs_tail else "等待任务启动...\n",
                            gr.update(), gr.update(), gr.update(), gr.update(),
                            gr.update(), gr.update(), None, prev_render
                        )
                    empty_render = {"phase": "empty"}
                    return (
                        "".join(logs_tail) if logs_tail else "等待任务启动...\n",
                        "当前尚无正在运行或完成的批次。",
                        gr.update(choices=[], visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(value=None) if prev_zip else gr.update(),
                        gr.update(choices=hist_ids),
                        None,
                        empty_render
                    )
                b = tm.active_batch
                snapshot = {
                    "batch_id": b.batch_id,
                    "status": b.status,
                    "output_dir": b.output_dir,
                    "zip_path": b.zip_path,
                    "tasks": [(t.status, t.filename, t.mono_output, t.dual_output) for t in b.tasks],
                }
                hist_ids = [r["batch_id"] for r in tm.history_records]

            log_txt = "".join(logs_tail) if logs_tail else "等待任务启动...\n"

            statuses = [t[0] for t in snapshot["tasks"]]
            total_cnt = len(statuses)
            succ_cnt = statuses.count("success")
            fail_cnt = statuses.count("failed")
            canc_cnt = statuses.count("cancelled")
            proc_cnt = statuses.count("processing")

            # 全部使用主题 CSS 变量：暗色模式下自动适配配色并保证可读性
            status_color = ("var(--claude-accent)" if snapshot["status"] == "running"
                            else "var(--claude-success)" if snapshot["status"] == "completed"
                            else "var(--claude-danger)")
            summary_html = f"""
            <div style='background: var(--claude-surface); border: 1px solid var(--claude-border); color: var(--claude-text); border-radius: 8px; padding: 10px; margin-bottom: 8px;'>
                <b>批次编号:</b> {snapshot['batch_id']} | <span style='color: {status_color}; font-weight: bold;'>{snapshot['status'].upper()}</span><br/>
                <b>进度概览:</b> 共 {total_cnt} 篇 (完成 <span style='color:var(--claude-success);'>{succ_cnt}</span> / 处理中 {proc_cnt} / 失败 <span style='color:var(--claude-danger);'>{fail_cnt}</span> / 取消 {canc_cnt})<br/>
                <b>输出路径:</b> <small>{snapshot['output_dir']}</small>
            </div>
            """

            # 提取所有可预览的成果项：(展示名, 真实路径) 二元组，
            # 下拉的 value 即真实路径，消费端按路径精确匹配
            choices = []
            for _, fname, mono_p, dual_p in snapshot["tasks"]:
                if mono_p and Path(mono_p).exists():
                    choices.append((f"📄 {fname} [仅译文 mono]", mono_p))
                if dual_p and Path(dual_p).exists():
                    choices.append((f"📄 {fname} [双语对照 dual]", dual_p))

            choice_values = [v for _, v in choices]
            new_choice = current_choice if current_choice in choice_values else (choice_values[0] if choice_values else "")
            has_results = len(choices) > 0
            has_failures = (fail_cnt + canc_cnt) > 0 and snapshot["status"] != "running"

            zp = snapshot["zip_path"]
            zip_ok = bool(zp and Path(zp).exists())
            if zip_ok:
                zip_out = zp if zp != prev_zip else gr.update()
                new_zip_state = zp
            else:
                zip_out = gr.update(value=None) if prev_zip else gr.update()
                new_zip_state = None

            # 各组件渲染签名：与上一秒一致则返回 gr.update()（跳过 DOM 更新，消除闪烁）
            render = {
                "phase": "batch",
                "summary": summary_html,
                "choices": (tuple(choice_values), new_choice, has_results),
                "retry": has_failures,
                "row": (has_results or zip_ok),
                "hist": tuple(hist_ids),
            }
            out_summary = summary_html if render["summary"] != prev_render.get("summary") else gr.update()
            out_choices = (gr.update(choices=choices, value=new_choice, visible=has_results)
                           if render["choices"] != prev_render.get("choices") else gr.update())
            out_retry = (gr.update(visible=has_failures)
                         if render["retry"] != prev_render.get("retry") else gr.update())
            out_row = (gr.update(visible=render["row"])
                       if render["row"] != prev_render.get("row") else gr.update())
            out_hist = (gr.update(choices=hist_ids)
                        if render["hist"] != prev_render.get("hist") else gr.update())

            return (
                log_txt,
                out_summary,
                out_choices,
                out_retry,
                out_row,
                zip_out,
                out_hist,
                new_zip_state,
                render
            )

        timer.tick(
            fn=on_timer_tick,
            inputs=[pdf_result_selector, last_zip_state, last_render_state],
            outputs=[
                log_output,
                batch_summary_md,
                pdf_result_selector,
                retry_failed_btn,
                download_row,
                batch_zip_file,
                history_dropdown,
                last_zip_state,
                last_render_state
            ]
        )

    return demo
