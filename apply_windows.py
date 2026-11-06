#!/usr/bin/env python3
"""GitHub Desktop 汉化工具（Windows 移植版）

把 XiaOldMan/GithubDesktop-Chinese-Language-Tool 的翻译词典应用到
Windows 版 GitHub Desktop 的 main.js / renderer.js。

用法：
  python -I apply_windows.py --action apply     # 汉化（自动探测最新版本）
  python -I apply_windows.py --action restore   # 还原英文原版
  python -I apply_windows.py --action status    # 查看状态
  python -I apply_windows.py --action apply --app "C:\\...\\app-3.6.10\\resources\\app"
  python -I apply_windows.py --action apply --dry-run   # 只统计不改文件

安全措施：
  * 写入前备份原版到 ~/.ghd-zh/backup/app-<版本>-windows/
  * 两个文件都在内存中改完后先跑 node --check，失败则不写盘
  * 进度阶段标题保持英文（它们要和 git 原始输出逐字匹配）
"""

import argparse
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REG_PRECEDERS = set("=([,:!&|?{;<>+-*%^~")
UI_PROP = re.compile(
    r'(?:label|title|description|buttonText|placeholder|aria-label|ariaLabel|'
    r'text|message|header|subtitle|children|summary|tooltip|okButtonText|'
    r'caption|prompt|detail|name|alt)\s*:\s*$')

# 这些字符串会被 `n.title === t.title` 与 git 原始输出比对（进度条权重表），
# 翻译后匹配失败会导致进度条退化，因此始终保留英文。
PROTECTED_TITLES = {
    "Checking out files",
    "remote: Compressing objects",
    "Receiving objects",
    "Resolving deltas",
    "Compressing objects",
    "Writing objects",
    "remote: Resolving deltas",
}

# Windows 独有（或措辞不同）的菜单项补充翻译。
EXTRA_MENU = {
    "&Options\u2026": "\u9009\u9879\u2026",
    "E&xit": "\u9000\u51fa",
    "&Changes": "\u66f4\u6539",
    "&History": "\u5386\u53f2",
    "Repository &list": "\u4ed3\u5e93\u5217\u8868",
    "&Branches list": "\u5206\u652f\u5217\u8868",
    "Wor&ktrees list": "\u5de5\u4f5c\u6811\u5217\u8868",
    "Show in E&xplorer": "\u5728\u8d44\u6e90\u7ba1\u7406\u5668\u4e2d\u663e\u793a",
    "S&how logs in Explorer": "\u5728\u8d44\u6e90\u7ba1\u7406\u5668\u4e2d\u663e\u793a\u65e5\u5fd7",
    "Command Line Tool": "\u547d\u4ee4\u884c\u5de5\u5177",
    "Install": "\u5b89\u88c5",
    "Uninstall": "\u5378\u8f7d",
    "&Help": "\u5e2e\u52a9",
}

VERSION_RE = re.compile(r'^app-(\d+)\.(\d+)\.(\d+)$')


def has_han(s):
    return any(0x4e00 <= ord(c) <= 0x9fff for c in s)


def norm(s):
    s = s.replace('&', '').replace('\u2026', '...').lower()
    return re.sub(r'\s+', ' ', s).strip()


PROTECTED = {norm(s) for s in PROTECTED_TITLES}


def extract_strings(src):
    """Tokenizer: yield (literal_with_quotes, start, end) for simple JS strings."""
    out = []
    i, n = 0, len(src)
    prev = ''
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i)
            i = n if j < 0 else j + 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i)
            i = n if j < 0 else j + 2
            continue
        if c == '/' and prev in REG_PRECEDERS:
            j = i + 1
            inclass = False
            while j < n:
                ch = src[j]
                if ch == '\\':
                    j += 2
                    continue
                if ch == '\n':
                    break
                if ch == '[':
                    inclass = True
                elif ch == ']':
                    inclass = False
                elif ch == '/' and not inclass:
                    break
                j += 1
            i = j + 1
            prev = '/'
            continue
        if c in ('"', "'", '`'):
            q = c
            j = i + 1
            while j < n:
                ch = src[j]
                if ch == '\\':
                    j += 2
                    continue
                if ch == q or ch == '\n':
                    break
                j += 1
            if j < n and src[j] == q:
                out.append((src[i:j + 1], i, j + 1))
                i = j + 1
                prev = q
                continue
            i += 1
            prev = c
            continue
        if not c.isspace():
            prev = c
        i += 1
    return out


def is_codeish(lit):
    inner = lit[1:-1]
    if not inner:
        return True
    if any(t in inner for t in ('://', '.js', '.css', '.png', '.svg', '.json', '.git')):
        return True
    if re.match(r'^[a-z0-9_\-:.]+$', inner) and ' ' not in inner:
        return True
    if inner.startswith('#') or inner.startswith('.'):
        return True
    return False


def apply_exact(src, mappings):
    """上游算法：上下文指纹匹配，长句唯一出现兜底。"""
    out = src
    stat = dict(total=len(mappings), present=0, replaced=0, fp=0, uniq=0, miss=0)
    for en, m in mappings.items():
        if norm(en[1:-1]) in PROTECTED:
            continue
        if en not in out:
            continue
        stat['present'] += 1
        occ, i = [], 0
        while True:
            i = out.find(en, i)
            if i < 0:
                break
            occ.append(i)
            i += len(en)
        hits = []
        for oq in occ:
            cl = out[max(0, oq - 56):oq]
            cr = out[oq + len(en):oq + len(en) + 56]
            for fp in m['occ']:
                if fp['l'] == cl or fp['r'] == cr:
                    hits.append(oq)
                    break
                if (len(fp['l']) >= 24 and cl.endswith(fp['l'][-24:])) or \
                   (len(fp['r']) >= 24 and cr[:24] == fp['r'][:24]):
                    hits.append(oq)
                    break
        if hits:
            for oq in sorted(set(hits), reverse=True):
                out = out[:oq] + m['zh'] + out[oq + len(en):]
            stat['fp'] += 1
            stat['replaced'] += len(set(hits))
        elif len(en) >= 16 and len(occ) == 1:
            out = out.replace(en, m['zh'])
            stat['uniq'] += 1
            stat['replaced'] += 1
        else:
            stat['miss'] += 1
    return out, stat


def zh_inner(zh):
    if len(zh) >= 2 and zh[0] == zh[-1] and zh[0] in '"\'`':
        return zh[1:-1]
    return zh


def build_lookup(d, fname):
    lookup, conflicts = {}, 0
    for en, v in d[fname].items():
        inner = en[1:-1]
        z = zh_inner(v['zh'])
        if not has_han(z):
            continue
        key = norm(inner)
        if key in lookup and lookup[key] != z:
            conflicts += 1
            continue
        lookup.setdefault(key, z)
    return lookup, conflicts


def apply_variants(src, lookup, stats):
    """把大小写 / 助记符 / 省略号不同的 Windows 写法映射到同一译文。"""
    spans = extract_strings(src)
    replacements = []
    for lit, s, e in spans:
        inner = lit[1:-1]
        if not inner or has_han(inner) or is_codeish(lit) or norm(inner) in PROTECTED:
            continue
        z = lookup.get(norm(inner))
        if not z or z == inner or not has_han(z):
            continue
        if '${' in inner:
            if set(re.findall(r'\$\{[^}]*\}', inner)) != set(re.findall(r'\$\{[^}]*\}', z)):
                continue
        keyed = bool(UI_PROP.search(src[max(0, s - 48):s]))
        multiword = ' ' in inner and re.match(r'^[&A-Z0-9]', inner)
        if keyed or multiword:
            replacements.append((s, e, lit[0] + z + lit[0]))
    for s, e, repl in sorted(replacements, key=lambda r: r[0], reverse=True):
        src = src[:s] + repl + src[e:]
    stats['variants'] = len(replacements)
    stats['variant_unique'] = len({r[2] for r in replacements})
    return src


def apply_extra_menu(src, stats):
    for lit, z in EXTRA_MENU.items():
        needle = '"' + lit + '"'
        if needle in src:
            src = src.replace(needle, '"' + z + '"')
    stats['extra_menu'] = len(EXTRA_MENU)
    return src


def node_check(src, fname):
    node = shutil.which('node')
    if not node:
        print('  [警告] 未找到 node，跳过语法校验（建议安装 Node.js 后再汉化）')
        return True
    tmp = os.path.join(tempfile.gettempdir(), 'ghdzh-check-' + fname)
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(src)
    try:
        r = subprocess.run([node, '--check', tmp], capture_output=True, text=True)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    if r.returncode != 0:
        print('  [失败] %s 语法校验未通过: %s' % (fname, r.stderr[:300]))
        return False
    return True


def resolve_app(app_arg):
    """返回 (app资源目录, 版本目录名, 版本号)。"""
    candidates = []
    if app_arg:
        p = os.path.abspath(app_arg)
        for cand in (p, os.path.join(p, 'resources', 'app')):
            if os.path.isfile(os.path.join(cand, 'main.js')):
                candidates.append(cand)
        if not candidates:
            raise SystemExit('指定的路径里找不到 main.js: %s' % app_arg)
    else:
        root = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'GitHubDesktop')
        for p in glob.glob(os.path.join(root, 'app-*')):
            m = VERSION_RE.match(os.path.basename(p))
            res = os.path.join(p, 'resources', 'app')
            if m and os.path.isfile(os.path.join(res, 'main.js')) \
                    and os.path.isfile(os.path.join(res, 'renderer.js')):
                candidates.append((tuple(int(x) for x in m.groups()), res))
        if not candidates:
            raise SystemExit('未能在 %s 下找到 GitHub Desktop，请用 --app 指定' % root)
        candidates.sort(key=lambda c: c[0])
        candidates = [candidates[-1][1]]
    res = candidates[0]
    ver_dir = os.path.basename(os.path.dirname(os.path.dirname(res)))
    ver = ver_dir[4:] if ver_dir.startswith('app-') else ver_dir
    return res, ver_dir, ver


def backup_dir(ver_dir):
    return os.path.join(os.path.expanduser('~'), '.ghd-zh', 'backup', ver_dir + '-windows')


def cmd_status(app_arg):
    res, ver_dir, ver = resolve_app(app_arg)
    bdir = backup_dir(ver_dir)
    print('安装目录: %s' % res)
    print('版本: %s' % ver)
    for fname in ('main.js', 'renderer.js'):
        cur = io.open(os.path.join(res, fname), encoding='utf-8').read()
        han = sum(1 for c in cur if 0x4e00 <= ord(c) <= 0x9fff)
        state = '已汉化' if han > 0 else '英文原版'
        print('  %-12s %8d 字节, 汉字 %5d -> %s' % (fname, len(cur.encode('utf-8')), han, state))
    if os.path.isdir(bdir):
        print('备份: %s' % bdir)
    else:
        print('备份: 无（首次 apply 时自动创建）')


def cmd_restore(app_arg):
    res, ver_dir, ver = resolve_app(app_arg)
    bdir = backup_dir(ver_dir)
    if not os.path.isdir(bdir):
        raise SystemExit('没有找到 %s 的备份: %s' % (ver, bdir))
    for fname in ('main.js', 'renderer.js'):
        bak = os.path.join(bdir, fname)
        if not os.path.isfile(bak):
            raise SystemExit('备份缺少 %s' % fname)
        shutil.copy2(bak, os.path.join(res, fname))
        print('已还原: %s' % os.path.join(res, fname))
    print('完成。请重启 GitHub Desktop 生效。')


def cmd_apply(app_arg, dict_path, dry):
    res, ver_dir, ver = resolve_app(app_arg)
    if not os.path.isfile(dict_path):
        raise SystemExit('词典不存在: %s' % dict_path)
    d = json.load(io.open(dict_path, encoding='utf-8'))
    if 'main.js' not in d or 'renderer.js' not in d:
        raise SystemExit('词典格式不对: 需要 main.js / renderer.js 两个键')
    print('安装目录: %s' % res)
    print('版本: %s' % ver)
    print('词典: %s (%d + %d 条)' % (dict_path, len(d['main.js']), len(d['renderer.js'])))

    # 幂等：若已有备份，永远以备份的英文原版为基线重新汉化，
    # 避免在已汉化文件上反复叠加替换。
    bdir = backup_dir(ver_dir)
    use_backup = all(os.path.isfile(os.path.join(bdir, f))
                     for f in ('main.js', 'renderer.js'))
    if use_backup:
        print('基线: 备份原版 (%s)' % bdir)

    outputs, report = {}, {}
    for fname in ('main.js', 'renderer.js'):
        path = os.path.join(res, fname)
        source_path = os.path.join(bdir, fname) if use_backup else path
        src = io.open(source_path, encoding='utf-8').read()
        out, stat = apply_exact(src, d[fname])
        lookup, conflicts = build_lookup(d, fname)
        out = apply_variants(out, lookup, stat)
        if fname == 'main.js':
            out = apply_extra_menu(out, stat)
        if not node_check(out, fname):
            print('已中止，未修改任何文件。')
            return 1
        outputs[fname] = out
        stat['orig_len'] = len(src.encode('utf-8'))
        stat['new_len'] = len(out.encode('utf-8'))
        stat['conflicts'] = conflicts
        report[fname] = stat

    for fname, st in report.items():
        print('%-12s 词典 %d 条, 存在 %d, 精确替换 %d (指纹 %d / 唯一 %d), '
              '归一化补翻 %d, 未匹配 %d' % (
                  fname, st['total'], st['present'], st['replaced'],
                  st['fp'], st['uniq'], st['variants'], st['miss']))

    if dry:
        print('dry-run：未写入任何文件。')
        return 0

    os.makedirs(bdir, exist_ok=True)
    for fname, out in outputs.items():
        src_path = os.path.join(res, fname)
        bak = os.path.join(bdir, fname)
        if not os.path.isfile(bak):
            shutil.copy2(src_path, bak)
        with io.open(src_path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(out)
        print('已写入: %s' % src_path)
    print('备份: %s' % bdir)
    print('完成。请完全退出并重新启动 GitHub Desktop 生效。')
    return 0


def main():
    ap = argparse.ArgumentParser(description='GitHub Desktop Windows 汉化工具')
    ap.add_argument('--action', choices=['apply', 'restore', 'status'], default='apply')
    ap.add_argument('--app', help='GitHub Desktop 安装目录（默认自动探测最新版本）')
    ap.add_argument('--dict', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dict.json'),
                    help='词典路径（默认脚本同目录 dict.json）')
    ap.add_argument('--dry-run', action='store_true', help='只统计，不写文件')
    args = ap.parse_args()

    if args.action == 'status':
        return cmd_status(args.app)
    if args.action == 'restore':
        return cmd_restore(args.app)
    return cmd_apply(args.app, args.dict, args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
