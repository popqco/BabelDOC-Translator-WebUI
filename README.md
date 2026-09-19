# 📜 BabelDOC 芯片规格书 / 科技文档高质量双语翻译器 WebUI

[![CI](https://github.com/popqco/BabelDOC-Translator-WebUI/actions/workflows/ci.yml/badge.svg)](https://github.com/popqco/BabelDOC-Translator-WebUI/actions/workflows/ci.yml)

> 基于 **BabelDOC 0.6.4** 最新内核打造，针对 **硬件工程师 Assistant、元器件 Datasheet、芯片手册与学术论文** 深度优化的本地双语对照排版翻译工具。当前版本 **v1.1.0**（[更新内容](https://github.com/popqco/BabelDOC-Translator-WebUI/releases/tag/v1.1.0)）。

---

## ✨ 核心亮点

1. **沉浸式翻译同款质量（BabelDOC 0.6.4 官方内核）**：
   - 原生开启 `--translate-table-text` 表格文本翻译：完整解析并翻译元器件规格书的 **电气特性表（Electrical Characteristics）** 与 **引脚定义表（Pin Description）**。
   - 彻底解决旧版开源软件公式占位符泄露（如 `{v1}`、`{v2}` 乱码）与字体重叠挤压问题。
   - 严谨保护物理量单位（$\Omega$, $\text{m}\Omega$, $\mu\text{A}$, $\text{V}$, $\text{kHz}$ 等）及元器件型号与封装。
2. **翻译质量守护（v1.1.0）**：
   - 每份产物自动校验是否包含目标语言译文；内核因 API 限流/失败而**静默输出原文回退**时，会自动重试一次并在仍失败时明确标红报错（附内核错误详情），绝不再把"英文回退版"当作成功交付。
3. **断点续翻（v1.1.0）**：
   - 批次启动即持久化进度；程序意外退出（崩溃/断电/误关窗口）后，重启即可在历史记录中看到"中断"批次，**一键重试失败文件**（自动继承原批次的语言、提示词与输出设置）。
4. **Claude 风格温润视觉设计**：
   - 采用 Claude 标志性的温润米白底色（`#FAF9F5`）、暖灰柔和边框与陶土红金牌主色调，界面舒适护眼，完整适配深色模式。
5. **多场景提示词预设库（Prompt Management）**：
   - 内置 **硬件工程师 / 芯片规格书**、**嵌入式与单片机固件手册**、**学术科研论文**、**通用现代翻译** 等多套黄金模板。
   - 支持自由新增、修改、保存与删除自定义场景模板，并持久化保存在本地。
6. **全自动状态记忆（v1.1.0 起真实生效）**：
   - API Base URL、API Key、Model 代号、语言选择及高级配置，填过一次即永久自动记住（输入完成即保存，无需额外点击）。

---

## 🛠️ 在另一台电脑上的部署指南（极简保姆级）

### 前置环境
1. **安装 Python 3.10 ~ 3.13（推荐 3.11）**：
   - 前往 [Python 官网](https://www.python.org/downloads/) 下载安装包（BabelDOC 0.6.4 不支持 3.14+）。
   - **安装时务必勾选最下方的 `Add python.exe to PATH`**（将 Python 添加到系统环境变量）。

### 部署与一键启动（Windows）
1. **获取项目代码**：
   - 打开命令行终端运行：
     ```bash
     git clone https://github.com/popqco/BabelDOC-Translator-WebUI.git BabelDOC-Hardware-Translator
     cd BabelDOC-Hardware-Translator
     ```
   - 或者直接在 GitHub 页面点击绿色的 **`Code -> Download ZIP`**，解压到你电脑的任意文件夹。

2. **初始化环境**：
   - 双击 **`install.bat`**！脚本会自动挑选兼容的 Python 版本、创建独立虚拟环境（venv）并安装全部依赖（优先使用完全锁定的 `requirements.lock`，清华镜像加速、失败自动回退官方源）。

3. **一键启动**：
   - 双击 **`start_silent.vbs`**（无黑框桌面窗口）或 **`run.bat`**（带控制台，便于排障）。
   - 启动后自动弹出原生桌面窗口（WebView2），无需手动开浏览器；端口随机分配，设置 `BABELDOC_PORT` 环境变量可固定。

---

## ⚙️ 使用说明

1. **填写 API**：
   - 在左侧面板填入你的 OpenAI 兼容 Base URL（如 DeepSeek 官方、中转平台、本地 Ollama 等）、API Key 和 Model 代号。输入完成移开焦点即自动保存。
2. **选择语言与场景模板**：
   - 源语言与目标语言直接下拉选择；
   - 提示词预设库默认已勾选“🛠️ 硬件工程师 / 芯片规格书 (Datasheet)”。
3. **开始翻译**：
   - 拖入你要翻译的 PDF，点击 **“✨ 开始高质量排版翻译”**，稍等片刻即可在右侧预览并一键下载双语对照 PDF！
4. **批量与中断恢复**：
   - 支持多次拖拽排队、翻译中动态追加；批次进度实时落盘。
   - 若某文件翻译失败（如 API 异常），批次完成后点击 **“🔄 重试本批失败文件”** 即可带最新配置重跑，历史中的失败批次在重启软件后依然可重试。

---

## 🧑‍💻 开发者

```bash
pip install -r requirements.lock   # 或 requirements.txt（宽松约束）
pip install pytest ruff pymupdf    # 开发工具
pytest                             # 运行测试（运行时状态自动隔离到临时目录）
ruff check .                       # 代码检查
```

每次推送到 GitHub 会自动触发 **CI**（`ruff` 代码检查 + `pytest` 测试），结果见仓库的 **Actions** 页面。

---

## 📜 开源协议与致谢
- 本项目基于 [funstory-ai/BabelDOC](https://github.com/funstory-ai/BabelDOC) 开源文档排版与翻译引擎开发。
- 本项目自身以 [MIT License](LICENSE) 开源；`assets/fonts/` 内字体遵循各自上游许可（SIL OFL / Apache 2.0 等）。
