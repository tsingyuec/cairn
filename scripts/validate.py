#!/usr/bin/env python3
"""校验知识目录、状态和项目内链接。只依赖 Python 标准库，不联网。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from catalog import ANCHOR, GROUPS, HEADING, LEAF, LINK, plain_title, read_tracks, section_materials, without_fences


# 标题用知识主题，学习问题放在目标中。这里只识别显式问句/指令，语义仍须人工审查。
QUESTION_TITLE = re.compile(r'如何|怎样|为什么|为何|什么|是否|有何|怎么|哪些|何种|哪里|哪种|哪个|哪类|谁|何时|何处|从何|何以|究竟|[？?]')
INSTRUCTION_TITLE = re.compile(r'^(?:读懂|学会|理解|掌握|认识一下|探索一下)')


def title_needs_revision(title: str) -> bool:
    core = plain_title(title.split('；', 1)[0])
    return not core or bool(QUESTION_TITLE.search(core) or INSTRUCTION_TITLE.search(core))


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    tracks: int = 0
    sections: int = 0
    tasks: int = 0
    references: int = 0
    links: int = 0
    statuses: Counter = field(default_factory=Counter)


def reference_errors(track, tracks, root: Path) -> list[str]:
    """REUSE 属于正常目录，来源必须是唯一、可定位的 B/M 自有小节。"""
    errors = []
    foundation = (root / 'content/基础知识').resolve()
    targets = {(item.path.resolve(), section.anchor): section
               for item in tracks for section in item.sections}
    seen = set()
    for section in track.sections:
        if section.kind == 'task':
            continue
        if section.status is not None:
            errors.append(f'{section.number} REUSE 条目不应有进度状态')
        if not section.learning_goal:
            errors.append(f'{section.number} REUSE 条目缺少学习目标')
        url = section.reuse_source.strip().removeprefix('<').removesuffix('>')
        if urlsplit(url).scheme or url.startswith('//'):
            errors.append(f'{section.number} REUSE 来源须是项目内具体自有小节')
            continue
        name, _, anchor = url.partition('#')
        path = (track.path.parent / unquote(name)).resolve() if name else track.path.resolve()
        key = (path, unquote(anchor))
        source = targets.get(key)
        if not source:
            errors.append(f'{section.number} REUSE 来源须精确到有效小节，不能引用整课或整章：{url}')
        elif foundation not in path.parents:
            errors.append(f'{section.number} REUSE 来源须在基础知识（B/M）中：{url}')
        elif source.kind != 'task':
            errors.append(f'{section.number} 不得链式 REUSE 另一个 REUSE 条目，应直接指向自有原节')
        if key in seen:
            errors.append(f'{section.number} 在本脉络重复 REUSE 同一小节')
        seen.add(key)
    return errors


def validate(root: Path) -> Result:
    root = root.resolve()
    result = Result()
    tracks = read_tracks(root)
    by_code = {}

    def error(path, message):
        result.errors.append(f'{path.relative_to(root)}: {message}')

    if not tracks:
        result.errors.append('content/: 没有找到知识脉络')
    for track in tracks:
        path = track.path
        result.tracks += 1
        result.sections += len(track.sections)
        result.tasks += len(track.tasks)
        result.references += len(track.references)
        result.statuses.update(item.status for item in track.tasks)
        if track.code in by_code:
            error(path, f'重复编号 {track.code}')
        by_code[track.code] = track
        group, kind = GROUPS[track.code[0]]
        if path.parent.parent != root / 'content' / group or track.kind != kind:
            error(path, f'{track.code} 的分类应为 {group} / {kind}')
        if track.title != path.parent.name:
            error(path, '主题标题与目录名不一致')
        if not 0 < len(track.sections) < 100:
            error(path, '每条叶子脉络须有 1–99 个小节；分类和全项目汇总不受此限')
        if len(track.sections) != track.declared:
            error(path, f'目录规模声明 {track.declared}，实际 {len(track.sections)}')
        for label in ['**知识主线**：', '**范围与边界**：', '**前置知识**：', '## 目录', '## 学习出口', '## 原始资料与延伸阅读', '## 导航']:
            if label not in track.text:
                error(path, f'缺少 {label}')
        for message in reference_errors(track, tracks, root):
            error(path, message)
        clean = without_fences(track.text)
        if re.search(r'^## 学习路线|^### 阶段 \d+', clean, re.M):
            error(path, '通用与专题内容应整合进章、节、小节，不再设置独立学习路线或阶段表')
        anchors = ANCHOR.findall(clean)
        if len(anchors) != len(set(anchors)):
            error(path, '存在重复显式锚点')
        counters = [0, 0, 0]
        leaves_by_line = {item.line: item for item in track.sections}
        children = Counter()
        for no, line in enumerate(clean.splitlines(), 1):
            heading = HEADING.match(line)
            leaf = leaves_by_line.get(no)
            if heading:
                depth = len(heading[1]) - 2
                number = heading[2]
                node_title = heading[3]
            elif leaf:
                depth, number = 2, leaf.number
                node_title = leaf.title
            else:
                if re.match(r'^(?:- |#### )\d+\.\d+\.\d+', line):
                    error(path, f'第 {no} 行的小节格式/状态非法，须为带锚点和行尾状态的列表行')
                continue
            if title_needs_revision(node_title):
                error(path, f'第 {no} 行目录标题须直接列明知识主题与关键知识点，问句或学习指令应放入学习目标')
            counters[depth] += 1
            for i in range(depth + 1, 3):
                counters[i] = 0
            expected = '.'.join(map(str, counters[:depth + 1]))
            if expected != number or 0 in counters[:depth + 1]:
                error(path, f'第 {no} 行编号 {number}，预期 {expected}')
            anchor = f'{track.code.lower()}-{number.replace(".", "-")}'
            if anchor not in anchors or (leaf and leaf.anchor != anchor):
                error(path, f'缺少或错误的稳定锚点 {anchor}')
            if '.' in number:
                children[number.rsplit('.', 1)[0]] += 1
        for number, _ in track.headings:
            if children[number] == 0:
                error(path, f'{number} 没有子节点')
        for item in track.sections:
            if item.kind == 'reference':
                continue
            directory = path.parent / item.relative_directory()
            blogs = section_materials(root, directory)
            if item.status == 'DONE' and not blogs:
                error(path, f'{item.number} 为 DONE，但没有正文或合格导读引用')
            if item.status == 'WAITING' and blogs:
                error(path, f'{item.number} 仍为 WAITING，但已有正文，请核对验收状态')
        index = path.parent.parent / 'README.md'
        if index.is_file():
            expected_link = f']({path.parent.name}/README.md)（{len(track.sections)} 小节）'
            if expected_link not in index.read_text(encoding='utf-8'):
                error(index, f'{track.code} 的分类链接或小节数未同步')

    # content 下的结构目录都应可导航；assets 不是内容结构目录。
    directories = [root / 'content', *(p for p in (root / 'content').rglob('*') if p.is_dir())]
    track_roots = [t.path.parent for t in tracks]
    for directory in directories:
        if 'assets' in directory.parts or any(part.startswith('.') for part in directory.relative_to(root).parts):
            continue
        if any(parent in directory.parents for parent in track_roots):
            continue  # 正文的节/小节目录由脉络 README 索引，不强求另建 README。
        if not (directory / 'README.md').is_file():
            error(directory, '缺少分类或脉络 README 导航')

    active, visited = set(), set()
    def visit(code):
        if code in active:
            result.errors.append(f'前置依赖环：{code}')
            return
        if code in visited:
            return
        active.add(code)
        for prerequisite in by_code[code].prerequisites:
            if prerequisite not in by_code:
                error(by_code[code].path, f'未知前置脉络 {prerequisite}')
            else:
                visit(prerequisite)
        active.remove(code)
        visited.add(code)
    for code in by_code:
        visit(code)

    # 检查所有手写 Markdown；不检查构建产物、依赖发行包和中间材料。
    pages = []
    for path in root.rglob('*.md'):
        rel = path.relative_to(root)
        if any(part in {'.git', '.venv', 'build', '_work', 'vendor', 'node_modules', '__pycache__'} for part in rel.parts):
            continue
        pages.append(path)
    for path in pages:
        clean = without_fences(path.read_text(encoding='utf-8'))
        for _, _, url in LINK.findall(clean):
            url = url.strip().removeprefix('<').removesuffix('>')
            if urlsplit(url).scheme or url.startswith('//'):
                continue
            result.links += 1
            name, _, fragment = url.partition('#')
            target = (path.parent / unquote(name)).resolve() if name else path
            if not target.is_relative_to(root):
                error(path, f'项目内链接越出项目：{url}')
                continue
            if not target.is_file():
                error(path, f'死链：{url}')
                continue
            if fragment and target.suffix == '.md':
                target_text = without_fences(target.read_text(encoding='utf-8'))
                if unquote(fragment) not in ANCHOR.findall(target_text):
                    error(path, f'找不到显式锚点：{url}')
        for no, line in enumerate(clean.splitlines(), 1):
            if line.rstrip() != line:
                error(path, f'第 {no} 行尾部空白')

    # 导航中的规模声明统一校验，不把统计变成另一套手工元数据。
    for path in [root / 'README.md', root / 'content/README.md']:
        if not path.is_file():
            result.errors.append(f'缺少项目入口 {path}')
            continue
        text = path.read_text(encoding='utf-8')
        if not re.search(fr'{result.tracks} 条知识脉络[、，]{result.sections} 个(?:三级)?小节', text):
            error(path, f'总规模未同步，应为 {result.tracks} 条知识脉络、{result.sections} 个小节')
    for prefix, (group, _) in GROUPS.items():
        matching = [t for t in tracks if t.code.startswith(prefix)]
        total = sum(len(t.sections) for t in matching)
        path = root / 'content' / group / 'README.md'
        if path.is_file():
            text = path.read_text(encoding='utf-8')
            if f'{len(matching)} 条脉络、{total} 个小节' not in text:
                error(path, '分类统计未同步')
            upper = path.parent.parent / 'README.md'
            if upper.is_file() and f'{len(matching)} 条脉络、{total} 个小节' not in upper.read_text(encoding='utf-8'):
                error(upper, f'{group} 的统计未同步')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = validate(args.root)
    if result.errors:
        for error in result.errors:
            print(f'ERROR: {error}')
        print(f'FAIL: {len(result.errors)} 个问题')
        return 1
    print(f'PASS: {result.tracks} 条脉络 / {result.sections} 个小节 / {result.links} 个项目内链接')
    print(f'自有任务：{result.tasks}；REUSE：{result.references}（无独立进度）')
    print('状态：' + ', '.join(f'{key}={value}' for key, value in sorted(result.statuses.items())))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
