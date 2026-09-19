# BabelDOC 硬件翻译器 · 新电脑部署指南

## 前置要求

| 项目 | 说明 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| Python | 3.10 ~ 3.13（推荐 3.11；BabelDOC 0.6.4 不支持 3.14+。安装时务必勾选 **Add Python to PATH**） |
| WebView2 | Windows 11 自带；Windows 10 缺失时安装 [Evergreen Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |
| 网络 | 首次 `install.bat` 需联网下载依赖；`assets/` 已随仓库分发，翻译过程完全离线 |

---

## 方式一：U 盘整体拷贝（推荐，配置全部保留）

1. 把整个项目文件夹拷贝到新电脑任意位置，例如 `D:\Program Files\BabelDOC-Hardware-Translator`
2. 双击 **install.bat**（自动创建 venv、安装全部依赖，使用清华镜像加速、失败自动回退官方源）
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

1. 在界面里填入你的 API Key 并保存（`data/` 整目录被 .gitignore 排除，不会随仓库分发）
2. `assets/`（模型 + 字体，约 344 MB）**已随仓库提交**，clone 后即可完全离线翻译；若仓库体积太大，也可从旧电脑仅拷贝 `assets/` 文件夹

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
│   ├── models/                # DocLayout-YOLO ONNX（约 72 MB，已随仓库分发）
│   └── fonts/                 # CJK 字体包（约 272 MB，已随仓库分发）
├── tests/                     # 自动化测试套件（运行时状态自动隔离）
├── packaging/                 # Inno Setup 安装包脚本
├── docs/adr/                  # 架构决策记录
├── install.bat                # 一键环境初始化
├── start_silent.vbs           # 无黑框便携启动器（路径自适应）
├── requirements.txt           # Python 直接依赖（宽松约束）
└── requirements.lock          # 完全锁定的依赖版本（可复现安装，install.bat 优先使用）
```

---

## 便携性说明

| 数据 | 是否随文件夹拷贝 | 是否随 git clone | 说明 |
|------|:-:|:-:|------|
| 源代码、测试、文档、`assets/` | ✅ | ✅ | 模型与字体已随仓库提交，克隆即可离线翻译 |
| `data/config.json` | ✅ | ❌（含 API Key，被 .gitignore 排除） | |
| `data/prompts.json` | ✅ | ❌ | 自定义提示词预设 |
| `data/tasks/history.json` | ✅ | ❌ | 本机任务历史（含绝对路径，程序会自动跳过失效项） |

- **所有路径均运行时自动探测**，项目文件夹可放在任意盘符/目录。
- 启动器 `start_silent.vbs` 只使用项目内 `venv` 或 `.venv`；两者都不存在时弹出提示引导先运行 `install.bat`（不再回退到系统 Python，保证依赖版本一致）。
- 跨电脑迁移后，历史记录里失效的输出路径会被自动标注；批次若在运行中被中断，重启后会以"中断"状态出现在历史中，可一键重试失败文件。

---

## 常见问题

**Q：双击 start_silent.vbs 提示"未找到 Python 运行环境"**
A：先在项目目录下双击 install.bat 完成 venv 初始化。

**Q：翻译时报 "No module named babeldoc"**
A：依赖未装全。在项目目录执行：
```bat
venv\Scripts\python.exe -m pip install -r requirements.lock -i https://pypi.tuna.tsinghua.edu.cn/simple
```
（若无 requirements.lock 则使用 requirements.txt）

**Q：桌面窗口打不开 / 白屏**
A：确认系统已安装 WebView2 Runtime。Windows 10 用户可从微软官网下载 Evergreen 安装器。

**Q：换电脑后历史记录显示异常**
A：程序已内置失效路径检测，会在详情中标注"目录不存在"。相关条目不影响新任务。

**Q：如何升级 BabelDOC 内核**
A：修改 requirements.txt 中 `babeldoc==x.y.z` 后重新运行 install.bat；UI 和任务管理器与内核解耦，无需改界面代码。

**Q：想固定 Web 服务端口（排障/防火墙放行）**
A：启动前设置环境变量 `set BABELDOC_PORT=7860` 即可；默认由系统自动分配随机空闲端口。
