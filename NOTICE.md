# Attribution / 第三方来源说明

## XiaOldMan/GithubDesktop-Chinese-Language-Tool

- URL: https://github.com/XiaOldMan/GithubDesktop-Chinese-Language-Tool
- License: MIT（据其 README）
- 使用内容：
  - `dict.json` —— 799 条翻译词典，原样使用，未修改
  - 上下文指纹匹配算法（`apply.py`）的思路
  - JS 字符串分词逻辑（`rebase.py` 中的 `extract_strings`）的思路与结构

## 本仓库新增内容（MIT）

- `apply_windows.py`：Windows 路径探测、版本选择、备份/还原/状态、大小写与助记符归一化匹配、Windows 菜单补充词典、进度阶段保护名单
- `ghd-zh.ps1`：PowerShell 入口
- README 与打包

## GitHub Desktop

- URL: https://github.com/desktop/desktop
- 本项目仅修改本地安装目录中的 `main.js` / `renderer.js` 文本，不分发 GitHub Desktop 的任何二进制文件。
