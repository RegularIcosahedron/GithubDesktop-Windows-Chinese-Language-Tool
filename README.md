# GitHub Desktop 汉化工具（Windows 版）

> One-click Chinese localization for **GitHub Desktop on Windows**, powered by the
> 799-entry dictionary from [XiaOldMan/GithubDesktop-Chinese-Language-Tool](https://github.com/XiaOldMan/GithubDesktop-Chinese-Language-Tool) (MIT).

把 [XiaOldMan/GithubDesktop-Chinese-Language-Tool](https://github.com/XiaOldMan/GithubDesktop-Chinese-Language-Tool) 的 799 条人工校对词典，移植到 **Windows 版** GitHub Desktop 的一键汉化脚本。

> 上游项目只支持 macOS（`.app` + zsh）；本仓库是独立的 Windows 实现，复用其词典与指纹匹配思路，并额外处理了 Windows 版的助记符（`&Edit`）、句首大写（`Delete branch`）与 Windows 独有菜单项。

## 特点

- **一键汉化 / 一键还原**，自动探测安装目录和版本，永远作用于最新的 `app-*` 目录
- **写入前自动备份**，可随时恢复英文原版
- **语法校验**：两个文件都改完后先跑 `node --check`，失败则一个字节都不写
- **指纹定位**：按「字面量 + 上下文 ±56 字节」匹配，跨版本不依赖行号/偏移
- **归一化补翻**：把 Windows 的大小写、`&` 助记符、`…`/`...` 差异映射到同一译文
- **保护功能字符串**：进度阶段名（如 `Receiving objects`）保持英文，否则进度条会失去加权匹配
- **幂等**：重复执行结果一致；每次从备份的原版重新汉化

## 已测试版本

| 版本 | 状态 |
|---|---|
| Windows GitHub Desktop **3.6.10**（2026-11-06） | ✅ 实测通过 |
| 其他 3.6.x | ⚠️ 未逐版验证，指纹匹配通常向下兼容；建议先 `-DryRun` |

3.6.10 实测覆盖：

| 文件 | 词典条目 | 命中条目 | 精确替换 | 归一化补翻 | 最终未匹配 |
|---|---|---|---|---|---|
| `main.js`（菜单/原生对话框） | 126 | 52 | 49 | 60 | 4 |
| `renderer.js`（主界面） | 673 | 521 | 663 | 205 | 14 |

- 菜单栏 104 个菜单项中，89 项由词典直接覆盖，13 项由本仓库补充翻译；`Octicons`、`Arm64 banner` 两个开发者测试项保留英文。
- 主界面写入 6110 个汉字；少量新文案在上游词典之外，保持英文显示。

## 环境要求

- Windows 10 / 11
- 已安装 [GitHub Desktop](https://desktop.github.com/)（Squirrel 安装版，默认位置 `%LOCALAPPDATA%\GitHubDesktop`）
- Python 3.8+
- Node.js（用于 `node --check` 语法校验；缺失时会警告并跳过校验）

## 快速开始

方式一（最简单）：双击 `apply.bat`。

方式二（命令行）：

```powershell
# 在仓库目录内打开 PowerShell
powershell -ExecutionPolicy Bypass -File .\ghd-zh.ps1 -Action Apply
```

还原：双击 `restore.bat`，或执行 `.\ghd-zh.ps1 -Action Restore`。

完成后**完全退出** GitHub Desktop（托盘图标也要退出），再重新打开即可看到中文。

### 全部命令

| 命令 | 作用 |
|---|---|
| `.\ghd-zh.ps1 -Action Apply` | 汉化最新版本（自动备份） |
| `.\ghd-zh.ps1 -Action Restore` | 还原英文原版 |
| `.\ghd-zh.ps1 -Action Status` | 查看版本 / 备份 / 汉化状态 |
| `.\ghd-zh.ps1 -Action Apply -DryRun` | 只统计命中情况，不写文件 |
| `.\ghd-zh.ps1 -Action Apply -AppPath "C:\...\app-3.6.10\resources\app"` | 指定安装路径 |

也可以直接用 Python：

```powershell
python -I apply_windows.py --action apply
python -I apply_windows.py --action restore
python -I apply_windows.py --action status --app "C:\...\resources\app"
```

## 原理

GitHub Desktop 的界面文案内联在编译产物里：

- `resources\app\main.js` —— 主进程：应用菜单、原生对话框标题
- `resources\app\renderer.js` —— 渲染进程：React 界面文本

脚本对每个词条：

1. **精确匹配**：字面量存在时，用上游词典记录的上下文指纹（前后各 56 字节）定位出现位置；短词必须指纹命中，长句且唯一出现时才允许全局替换。
2. **归一化匹配**：去掉 `&`、把 `…` 视作 `...`、统一大小写后再次比对，命中词典的 Windows 变体；多词短语或 UI 属性上下文（`label:` / `title:` / `placeholder:` 等）才替换。
3. **Windows 补充词典**：13 条 Windows 独有菜单项。
4. **保护名单**：进度阶段标题与 git 原始输出逐字比较，始终跳过。
5. 两个文件全部改完后执行 `node --check`，通过才落盘。

数据目录：

- `%USERPROFILE%\.ghd-zh\backup\app-<版本>-windows\` —— 各版本英文原版备份

## 目录结构

```
.
├─ apply_windows.py     # 核心：探测 / 匹配 / 替换 / 备份 / 还原 / 状态
├─ ghd-zh.ps1           # PowerShell 一键入口
├─ dict.json            # 词典（来自上游，MIT）
├─ LICENSE
└─ README.md
```

## 常见问题

**官方更新后中文没了？**
更新会替换整个 `app-*` 目录。重新运行 `-Action Apply` 即可，备份按版本分目录，互不影响。

**菜单/界面还有英文？**
上游词典按 macOS 3.6.10 提取，Windows 新版可能新增文案。未命中的条目会安全跳过，保持英文，不影响使用。

**为什么进度条阶段名是英文？**
这些标题会与 git 原始输出（如 `Receiving objects`）做字符串比较，翻译会导致加权进度匹配失败，属于刻意保留。

**如何彻底恢复？**
`-Action Restore` 会把备份的原版 `main.js` / `renderer.js` 复制回去；也可手动从 `.ghd-zh\backup\` 取文件。

**会不会影响 GitHub Desktop 的更新和登录？**
不会。只改两个 JS 资源文件，不动安装包、签名、配置和账号数据。

## 许可与致谢

- 本项目代码：MIT
- `dict.json`：来自 [XiaOldMan/GithubDesktop-Chinese-Language-Tool](https://github.com/XiaOldMan/GithubDesktop-Chinese-Language-Tool)（MIT），未修改
- 指纹匹配算法与 JS 字符串分词思路参考上游 `apply.py` / `rebase.py`（MIT）

详见 [NOTICE.md](NOTICE.md)。
