# BabelDOC 硬件翻译器 · 新电脑部署指南

## 前置要求

| 项目 | 说明 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| Python | 3.11（安装时务必勾选 **Add Python to PATH**） |
| WebView2 | Windows 11 自带；Windows 10 缺失时安装 [Evergreen Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |
| 网络 | 首次 `install.bat` 需联网下载依赖；已有 U 盘资源包时翻译可离线 |

---

## 方式一：U 盘整体拷贝（推荐，配置全部保留）

1. 把整个项目文件夹拷贝到新电脑任意位置，例如 `D:\Program Files\BabelDOC-Hardware-Translator`
2. 双击 **install.bat**（自动创建 venv、安装全部依赖，使用清华镜像加速）
3. 右键 **start_silent.vbs** → 发送到 → 桌面快捷方式
4. 双击桌面快捷方式即可启动（无黑框，纯桌面窗口）

> **好处**：`data/config.json`（含 API Key）与 `assets/`（模型 + 字体）会一起带过去，开箱即用。

---

## 方式二：git clone（干净环境）

```bat
git clone https://github.com/popqco/BabelDOC-Translator-WebUI.git BabelDOC-Hardware-Translator
cd BabelDOC-Hardware-Translator
install.bat
```

**首次启动后需手动补齐**：

1. 在界面里填入你的 API Key 并保存（`config.json` 被 .gitignore 排除，不会随仓库分发）
2. `assets/` 不在仓库内。首次翻译时 BabelDOC 会自动联网下载模型与字体（约 350 MB）；
   若希望完全离线，从旧电脑把 `assets/` 文件夹整体拷贝到项目根目录即可。

---

## 项目结构速览

```
BabelDOC-Hardware-Translator/
├── app.py                     # 桌面主入口（pywebview + 内置 Gradio）
├── core/
│   ├── config.py              # 便携配置 + Python 解释器自动探测
│   ├── task_manager.py        # 批量任务状态机（队列 / 停止 / 重试 / 历史）
│   └── translator_adapter.py  # BabelDOC 0.6.4 内核适配器
├── ui/view.py                 # Claude 风格 Gradio 界面
├── assets/
│   ├── models/                # DocLayout-YOLO ONNX（约 72 MB）
│   └── fonts/                 # CJK 字体包（约 272 MB）
├── tests/                     # 自动化测试套件
├── install.bat                # 一键环境初始化
├── start_silent.vbs           # 无黑框便携启动器（路径自适应）
└── requirements.txt           # Python 依赖清单
```

---

## 便携性说明

| 数据 | 是否随文件夹拷贝 | 是否随 git clone | 说明 |
|------|:-:|:-:|------|
| 源代码、测试、文档 | ✅ | ✅ | |
| `data/config.json` | ✅ | ❌（含 API Key，被 .gitignore 排除） | |
| `data/prompts.json` | ✅ | ❌ | 自定义提示词预设 |
| `data/tasks/history.json` | ✅ | ❌ | 本机任务历史（含绝对路径，程序会自动跳过失效项） |
| `assets/` | ✅ | ❌ | 模型与字体；克隆后首次翻译自动联网补齐 |

- **所有路径均运行时自动探测**，项目文件夹可放在任意盘符/目录。
- 启动器 `start_silent.vbs` 会依次尝试：项目内 `venv` → 项目内 `.venv` → 本机已有的共享 venv → PATH 上的 `pythonw.exe`。

---

## 常见问题

**Q：双击 start_silent.vbs 提示"未找到 Python 运行环境"**
A：先在项目目录下双击 install.bat 完成 venv 初始化。

**Q：翻译时报 "No module named babeldoc"**
A：依赖未装全。在项目目录执行：
```bat
venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Q：桌面窗口打不开 / 白屏**
A：确认系统已安装 WebView2 Runtime。Windows 10 用户可从微软官网下载 Evergreen 安装器。

**Q：换电脑后历史记录显示异常**
A：程序已内置失效路径检测，会在详情中标注"目录不存在"。相关条目不影响新任务。

**Q：如何升级 BabelDOC 内核**
A：修改 requirements.txt 中 `babeldoc==x.y.z` 后重新运行 install.bat；UI 和任务管理器与内核解耦，无需改界面代码。
