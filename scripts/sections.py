#!/usr/bin/env python3
"""列出小节任务；以比较旧状态的方式精确修改一行，不重写目录结构。"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from catalog import read_tracks, section_materials

TRANSITIONS = {
    'claim': ('WAITING', 'PROCESSING'),
    'finish': ('PROCESSING', 'DONE'),
    'release': ('PROCESSING', 'WAITING'),
    'abort': ('PROCESSING', 'ABORT'),
}


def locate(root: Path, code: str, number: str):
    tracks = [item for item in read_tracks(root) if item.code == code]
    if len(tracks) != 1:
        raise ValueError(f'脉络 {code} 不存在或编号不唯一')
    track = tracks[0]
    sections = [item for item in track.sections if item.number == number]
    if len(sections) != 1:
        raise ValueError(f'小节 {number} 不存在或编号不唯一')
    return track, sections[0]


def change(root: Path, code: str, number: str, action: str) -> dict:
    root = root.resolve()
    if action not in TRANSITIONS:
        raise ValueError(f'未知操作 {action}')
    # 锁文件只互斥这次精确修改，不存进度。不同小节正文可独立写，README 由主会话统一更新。
    lock_dir = root / '_work/.locks'
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_name = hashlib.sha256(code.encode()).hexdigest() + '.lock'
    with (lock_dir / lock_name).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        track, section = locate(root, code, number)
        if section.kind == 'reference':
            raise ValueError(f'{code} §{number} 是 REUSE 小节，没有独立进度；请使用其链接的通用原节')
        before, after = TRANSITIONS[action]
        if section.status != before:
            raise ValueError(f'{code} §{number} 当前为 {section.status}，操作 {action} 要求 {before}')
        directory = track.path.parent / section.relative_directory()
        blogs = section_materials(root, directory)
        if action == 'finish' and not blogs:
            raise ValueError(f'未找到正文或合格导读引用，不能标记 DONE：{directory}')
        if action in {'release', 'abort'} and blogs:
            raise ValueError('已有正文，先验收或人工核对；不把产物静默退回待处理或终止')
        old = section.raw
        new = old.removesuffix(f'[{before}]') + f'[{after}]'
        lines = track.text.splitlines(keepends=True)
        if lines[section.line - 1].rstrip('\r\n') != old:
            raise ValueError('目录行已变化，请重读后再操作')
        ending = lines[section.line - 1][len(old):]
        lines[section.line - 1] = new + ending
        # 只替换匹配的小节行，其他内容逐字保留。
        track.path.write_text(''.join(lines), encoding='utf-8')
        reread, confirmed = locate(root, code, number)
        if confirmed.raw != new:
            raise ValueError('写入后重读不一致，停止操作并检查并发写入')
        work = root / '_work' / track.path.parent.relative_to(root / 'content') / directory.name
        return {'track': code, 'section': number, 'status': confirmed.status,
                'readme': str(track.path.relative_to(root)),
                'content': str(directory.relative_to(root)), 'work': str(work.relative_to(root))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest='action', required=True)
    listing = sub.add_parser('list', help='只读列出任务及正文落位路径')
    listing.add_argument('--track')
    listing.add_argument('--include-references', action='store_true', help='同时查看课程中的 REUSE 条目；不将其作为任务')
    listing.add_argument('--status', choices=['WAITING', 'PROCESSING', 'DONE', 'ABORT'])
    for action in TRANSITIONS:
        command = sub.add_parser(action)
        command.add_argument('--track', required=True)
        command.add_argument('--section', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'list':
            rows = []
            for track in read_tracks(args.root):
                if args.track and track.code != args.track:
                    continue
                for section in track.sections:
                    if section.kind == 'reference' and not args.include_references:
                        continue
                    if args.status and section.status != args.status:
                        continue
                    rows.append({'track': track.code, 'section': section.number,
                                 'title': section.title, 'learning_goal': section.learning_goal,
                                                                  'kind': section.kind, 'status': section.status,
                                 'source': section.reuse_source if section.kind == 'reference' else None,
                                 'content': None if section.kind == 'reference' else str((track.path.parent / section.relative_directory()).relative_to(args.root.resolve()))})
            if args.track and not any(t.code == args.track for t in read_tracks(args.root)):
                raise ValueError(f'未知脉络 {args.track}')
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(change(args.root, args.track, args.section, args.action), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
