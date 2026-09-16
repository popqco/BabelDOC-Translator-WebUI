# 📜 BabelDOC 芯片规格书 / 科技文档高质量双语翻译器 WebUI

> 基于 **BabelDOC 0.6.4** 最新内核打造，针对 **硬件工程师 Assistant、元器件 Datasheet、芯片手册与学术论文** 深度优化的本地双语对照排版翻译工具。

---

## ✨ 核心亮点

1. **沉浸式翻译同款质量（BabelDOC 0.6.4 官方内核）**：
   - 原生开启 `--translate-table-text` 表格文本翻译：完整解析并翻译元器件规格书的 **电气特性表（Electrical Characteristics）** 与 **引脚定义表（Pin Description）**。
   - 彻底解决旧版开源软件公式占位符泄露（如 `{v1}`、`{v2}` 乱码）与字体重叠挤压问题。
   - 严谨保护物理量单位（$\Omega$, $\text{m}\Omega$, $\mu\text{A}$, $\text{V}$, $\text{kHz}$ 等）及元器件型号与封装。
2. **Claude 风格温润视觉设计**：
   - 采用 Claude 标志性的温润米白底色（`#FAF9F5`）、暖灰柔和边框与陶土红金牌主色调，界面舒适护眼。
3. **多场景提示词预设库（Prompt Management）**：
   - 内置 **硬件工程师 / 芯片规格书**、**嵌入式与单片机固件手册**、**学术科研论文**、**通用现代翻译** 等多套黄金模板。
   - 支持自由新增、修改、保存与删除自定义场景模板，并持久化保存在本地。
4. **全自动状态记忆**：
   - API Base URL、API Key、Model 代号、语言选择及高级配置，填过一次即可永久自动记住。

---

## 🛠️ 在另一台电脑上的部署指南（极简保姆级）

### 前置环境
1. **安装 Python 3.10 或 3.11**：
   - 前往 [Python 官网](https://www.python.org/downloads/) 下载安装包。
   - **安装时务必勾选最下方的 `Add python.exe to PATH`**（将 Python 添加到系统环境变量）。

### 部署与一键启动（Windows）
1. **获取项目代码**：
   - 打开命令行终端运行：
     ```bash
     git clone https://github.com/popqco/BabelDOC-Hardware-Translator.git
     cd BabelDOC-Hardware-Translator
     ```
   - 或者直接在 GitHub 页面点击绿色的 **`Code -> Download ZIP`**，解压到你电脑的任意文件夹。

2. **一键运行**：
   - 直接双击文件夹内的 **`run.bat`**！
   - 脚本会自动检测环境、创建独立虚拟环境（venv）、安装所有所需依赖并拉起网页。
   - 启动成功后在浏览器中打开：👉 **`http://localhost:7860`**

---

## ⚙️ 使用说明

1. **填写 API**：
   - 在左侧面板填入你的 OpenAI 兼容 Base URL（如 DeepSeek 官方、中转平台、本地 Ollama 等）、API Key 和 Model 代号。
2. **选择语言与场景模板**：
   - 源语言与目标语言直接下拉选择；
   - 提示词预设库默认已勾选“🛠️ 硬件工程师 / 芯片规格书 (Datasheet)”。
3. **开始翻译**：
   - 拖入你要翻译的 PDF，点击 **“✨ 开始高质量排版翻译”**，稍等片刻即可在右侧预览并一键下载双语对照 PDF！

---

## 📜 开源协议与致谢
- 本项目基于 [funstory-ai/BabelDOC](https://github.com/funstory-ai/BabelDOC) 开源文档排版与翻译引擎开发。
