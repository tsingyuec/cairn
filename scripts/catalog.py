"""知识目录的只读解析：README 是小节标题、编号和进度的唯一来源。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

GROUPS = {
    'B': ('基础知识/生物学', '生物学基础'),
    'M': ('基础知识/模型方法', '模型基础'),
    'P': ('专题知识/模型', '模型专题'),
    'D': ('专题知识/数据资源', '数据专题'),
}
METADATA = re.compile(r'编号：([BMPD]\d{2,}) · 类型：([^·\n]+) · 目录规模：(\d+) 个小节')
HEADING = re.compile(r'^(#{2,3}) (\d+(?:\.\d+)?) (.+)$')
LEAF = re.compile(r'^- (\d+\.\d+\.\d+) (.+?) <a id="([^"]+)"></a> \[(WAITING|PROCESSING|DONE|ABORT)\]$')
REFERENCE = re.compile(r'^- (\d+\.\d+\.\d+) (.+?) <a id="([^"]+)"></a> \[REUSE\]\(([^)]+)\)$')
ANCHOR = re.compile(r'<a\s+id="([^"]+)"\s*></a>')
LINK = re.compile(r'(!?)\[([^\]]*)\]\(\s*(<[^>]*>|(?:[^()\n]|\([^()\n]*\))*?)\s*\)')


def without_fences(text: str) -> str:
    """忽略反引号/波浪线围栏内的 Markdown 示例，保留行数。"""
    result = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence):
                fence = None
            result.append('')
        elif match:
            fence = match[1]
            result.append('')
        else:
            result.append(line)
    return '\n'.join(result)


def plain_title(title: str) -> str:
    title = LINK.sub(lambda m: m[2], title)
    return re.sub(r'<[^>]+>', '', title).replace('`', '').strip()


def directory_title(title: str) -> str:
    # “复用/关联”是链接注记，不参与物理目录名。
    title = plain_title(title.split('；', 1)[0])
    title = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '／', title)
    return title.rstrip('. ')[:120]


@dataclass
class Section:
    number: str
    title: str
    anchor: str
    status: str | None
    line: int
    raw: str
    parent_title: str
    learning_goal: str = ''
    kind: str = 'task'
    reuse_source: str = ''

    def relative_directory(self) -> Path:
        if self.kind == 'reference':
            raise ValueError('REUSE 小节没有独立正文目录，应直接链接通用原节')
        parent = self.number.rsplit('.', 1)[0]
        return Path(f'{parent}_{directory_title(self.parent_title)}') / f'{self.number}_{directory_title(self.title)}'


@dataclass
class Track:
    code: str
    title: str
    kind: str
    declared: int
    path: Path
    text: str
    sections: list[Section] = field(default_factory=list)
    headings: list[tuple[str, str]] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)

    @property
    def tasks(self) -> list[Section]:
        return [section for section in self.sections if section.kind == 'task']

    @property
    def references(self) -> list[Section]:
        return [section for section in self.sections if section.kind == 'reference']


def read_track(path: Path) -> Track | None:
    text = path.read_text(encoding='utf-8')
    match = METADATA.search(text)
    if not match:
        return None
    code, kind, count = match.groups()
    title = next((line[2:] for line in text.splitlines() if line.startswith('# ')), path.parent.name)
    track = Track(code, title, kind.strip(), int(count), path, text)
    parent_title = ''
    for line_no, line in enumerate(without_fences(text).splitlines(), 1):
        heading = HEADING.match(line)
        if heading:
            track.headings.append((heading[2], heading[3]))
            if heading[1] == '###':
                parent_title = heading[3]
        leaf = LEAF.match(line)
        reference = REFERENCE.match(line)
        if leaf or reference:
            match = leaf if leaf else reference
            number, name, anchor = match[1], match[2], match[3]
            status = leaf[4] if leaf else None
            track.sections.append(Section(number, name, anchor, status, line_no, line, parent_title,
                                          kind='task' if leaf else 'reference',
                                          reuse_source=reference[4] if reference else ''))
        elif line.startswith('  - 学习目标：') and track.sections:
            track.sections[-1].learning_goal = line.split('学习目标：', 1)[1]
    pre = re.search(r'\*\*前置知识\*\*：([^\n]+)', text)
    if pre:
        track.prerequisites = re.findall(r'\[([BMPD]\d{2,}) ', pre[1])
    return track


def section_materials(root: Path, directory: Path) -> list[Path]:
    """本节正文，或带目标覆盖说明的导读所引用的项目内既有正文。

    只检查材料存在性；目标是否真正覆盖必须由主会话验收。导读不能用
    README 互相引用凑成循环，也不能把外部网站或相邻项目当成已整理正文。
    """
    content = (root / 'content').resolve()
    if not directory.is_dir() or not directory.resolve().is_relative_to(content):
        return []
    found = []
    for path in sorted(directory.glob('*.md')):
        target = path.resolve()
        if path.name != 'README.md' and target.is_relative_to(content) and path.stat().st_size > 0:
            found.append(target)
    guide = directory / 'README.md'
    if guide.is_file():
        text = without_fences(guide.read_text(encoding='utf-8'))
        if '## 学习目标覆盖' in text:
            for bang, _, url in LINK.findall(text):
                url = url.strip().removeprefix('<').removesuffix('>')
                if bang or urlsplit(url).scheme or url.startswith('//'):
                    continue
                name = unquote(url.split('#', 1)[0])
                if not name:
                    continue
                target = (guide.parent / name).resolve()
                if (target.is_relative_to(content) and target.is_file()
                        and target.suffix == '.md' and target.name != 'README.md'
                        and re.match(r'^\d+\.\d+\.\d+_', target.parent.name)
                        and target.stat().st_size > 0):
                    found.append(target)
    return list(dict.fromkeys(found))


def read_tracks(root: Path) -> list[Track]:
    result = []
    for path in sorted((root / 'content').rglob('README.md')):
        track = read_track(path)
        if track:
            result.append(track)
    return sorted(result, key=lambda item: item.code)
