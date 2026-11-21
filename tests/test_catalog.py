from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from catalog import GROUPS, read_tracks
from sections import change
from validate import validate


def fixture(root, specs=None, count=1):
    specs = specs or [('B01', [])]
    paths = {}
    for code, prerequisites in specs:
        group, kind = GROUPS[code[0]]
        title = f'{code}主题'
        path = root / 'content' / group / title / 'README.md'
        path.parent.mkdir(parents=True)
        pre = '无硬性前置。'
        if prerequisites:
            pre = '、'.join(f'[{key} 主题](../../../{GROUPS[key[0]][0]}/{key}主题/README.md#{key.lower()}-1-1-1)' for key in prerequisites)
        body = f'''# {title}

编号：{code} · 类型：{kind} · 目录规模：{count} 个小节（三级叶子节点，少于 100）。

**知识主线**：科学问题。
**范围与边界**：目录。
**前置知识**：{pre}

## 目录

<a id="{code.lower()}-1"></a>
## 1 第一章

<a id="{code.lower()}-1-1"></a>
### 1.1 第一节

'''
        for i in range(1, count + 1):
            body += f'- 1.1.{i} 小节{i} <a id="{code.lower()}-1-1-{i}"></a> [WAITING]\n'
        body += '\n## 学习出口\n\n无。\n\n## 原始资料与延伸阅读\n\n无。\n\n## 导航\n\n[分类](../README.md)\n'
        path.write_text(body)
        paths[code] = path
    total = len(specs) * count
    for path in [root / 'README.md', root / 'content/README.md']:
        path.write_text(f'# 项目\n\n{len(specs)} 条知识脉络、{total} 个小节。\n')
    for prefix, (group, _) in GROUPS.items():
        matching = [code for code, _ in specs if code.startswith(prefix)]
        stat = f'{len(matching)} 条脉络、{len(matching) * count} 个小节'
        directory = root / 'content' / group
        directory.mkdir(parents=True, exist_ok=True)
        text = '# 分类\n\n' + stat + '\n\n'
        for code in matching:
            text += f'- [{code} {code}主题]({code}主题/README.md)（{count} 小节）\n'
        (directory / 'README.md').write_text(text)
        upper = directory.parent / 'README.md'
        with upper.open('a') as output:
            output.write(stat + '\n\n')
    return paths


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def errors(self):
        return '\n'.join(validate(self.root).errors)

    def replace(self, old, new):
        path = self.paths['B01']
        path.write_text(path.read_text().replace(old, new))


class CatalogTests(FixtureTests):
    def test_valid(self):
        result = validate(self.root)
        self.assertEqual([], result.errors)
        self.assertEqual(1, result.sections)
        self.assertEqual({'WAITING': 1}, result.statuses)

    def test_question_style_title_is_rejected(self):
        self.replace('1.1.1 小节1', '1.1.1 文档解析如何恢复阅读顺序和跨页结构')
        self.assertIn('标题须直接列明知识主题', self.errors())

    def test_instruction_style_title_is_rejected(self):
        self.replace('1.1.1 小节1', '1.1.1 读懂预测结果')
        self.assertIn('标题须直接列明知识主题', self.errors())

    def test_question_is_allowed_in_goal_not_title(self):
        self.replace('1.1.1 小节1', '1.1.1 文档结构解析：版面分析、阅读顺序与跨页分块')
        self.replace('[WAITING]', '[WAITING]\n  - 学习目标：文档解析如何恢复阅读顺序和跨页结构？')
        self.assertEqual([], validate(self.root).errors)

    def test_chapter_title_uses_same_naming_rule(self):
        self.replace('## 1 第一章', '## 1 结构证据从哪里来')
        self.assertIn('标题须直接列明知识主题', self.errors())

    def test_reference_label_does_not_change_topic_title(self):
        self.replace('1.1.1 小节1', '1.1.1 文档结构解析；复用 [如何阅读](README.md#b01-1-1-1)')
        self.assertEqual([], validate(self.root).errors)

    def test_separate_learning_route_is_rejected(self):
        self.replace('## 目录', '## 学习路线\n\n### 阶段 1 · 额外路线\n\n## 目录')
        self.assertIn('不再设置独立学习路线', self.errors())

    def test_missing_link(self):
        self.replace('无硬性前置。', '[缺失](missing.md)')
        self.assertIn('死链', self.errors())

    def test_missing_fragment(self):
        self.replace('无硬性前置。', '[引用](README.md#b01-no-such-anchor)')
        self.assertIn('找不到显式锚点', self.errors())

    def test_external_sibling_is_not_dependency(self):
        target = self.root.parent / (self.root.name + '-outside.md')
        target.write_text('outside')
        self.addCleanup(target.unlink)
        self.replace('无硬性前置。', f'[依赖](../../../../../{target.name})')
        self.assertIn('越出项目', self.errors())

    def test_invalid_status(self):
        self.replace('[WAITING]', '[PENDING]')
        self.assertIn('小节格式/状态非法', self.errors())

    def test_declared_count(self):
        self.replace('目录规模：1', '目录规模：2')
        self.assertIn('实际 1', self.errors())

    def test_anchor(self):
        self.replace('id="b01-1-1-1"', 'id="other"')
        self.assertIn('稳定锚点', self.errors())

    def test_done_requires_blog(self):
        self.replace('[WAITING]', '[DONE]')
        self.assertIn('为 DONE', self.errors())

    def test_duplicate_id(self):
        old = self.paths['B01']
        new = old.parent.parent / '重复' / 'README.md'
        new.parent.mkdir()
        new.write_text(old.read_text())
        self.assertIn('重复编号', self.errors())

    def test_cycle(self):
        root = self.root / 'cycle'
        root.mkdir()
        fixture(root, [('B01', ['M01']), ('M01', ['B01'])])
        self.assertTrue(any('依赖环' in item for item in validate(root).errors))

    def test_limit(self):
        root = self.root / 'large'
        root.mkdir()
        fixture(root, count=100)
        self.assertTrue(any('1–99' in item for item in validate(root).errors))

    def test_capacity_applies_per_leaf_track_not_to_category_total(self):
        root = self.root / 'independent-capacity'
        root.mkdir()
        fixture(root, [('B01', []), ('B02', [])], count=60)
        result = validate(root)
        self.assertEqual([], result.errors)
        self.assertEqual(120, result.sections)
        self.assertEqual(2, result.tracks)

    def test_learning_goal_is_exposed_to_task_planning(self):
        self.replace('[WAITING]', '[WAITING]\n  - 学习目标：从同一示例解释输入与输出。')
        track = read_tracks(self.root)[0]
        self.assertEqual('从同一示例解释输入与输出。', track.sections[0].learning_goal)
        self.assertEqual([], validate(self.root).errors)

    def test_code_examples_are_not_links(self):
        with self.paths['B01'].open('a') as output:
            output.write('\n~~~markdown\n[示例](does-not-exist.md)\n~~~\n')
        self.assertEqual([], validate(self.root).errors)


class StateTests(FixtureTests):
    def test_claim_changes_only_one_line_and_cannot_reclaim(self):
        path = self.paths['B01']
        before = path.read_text()
        result = change(self.root, 'B01', '1.1.1', 'claim')
        self.assertEqual('PROCESSING', result['status'])
        self.assertEqual(before.replace('[WAITING]', '[PROCESSING]'), path.read_text())
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'claim')
        change(self.root, 'B01', '1.1.1', 'release')
        self.assertEqual(before, path.read_text())

    def test_cannot_finish_empty_or_release_existing_blog(self):
        change(self.root, 'B01', '1.1.1', 'claim')
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'finish')
        track = read_tracks(self.root)[0]
        directory = track.path.parent / track.sections[0].relative_directory()
        directory.mkdir(parents=True)
        (directory / '正文.md').write_text('# 正文\n\n一手来源和必要证据。\n')
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'release')
        change(self.root, 'B01', '1.1.1', 'finish')
        self.assertEqual([], validate(self.root).errors)

    def test_can_finish_with_coverage_guide_to_existing_article(self):
        change(self.root, 'B01', '1.1.1', 'claim')
        track = read_tracks(self.root)[0]
        directory = track.path.parent / track.sections[0].relative_directory()
        directory.mkdir(parents=True)
        existing = directory.parent / '9.9.9_既有内容' / '规范博客.md'
        existing.parent.mkdir()
        existing.write_text('# 已整理的独立博客\n\n这里是对应目标的实际解释。\n')
        (directory / 'README.md').write_text(
            '# 本节导读\n\n## 学习目标覆盖\n\n- 本节目标由既有博客的例子解释。\n\n'
            '[既有正文](../9.9.9_既有内容/规范博客.md)\n')
        self.assertEqual('DONE', change(self.root, 'B01', '1.1.1', 'finish')['status'])
        self.assertEqual([], validate(self.root).errors)

    def test_cannot_finish_with_placeholder_or_readme_reference(self):
        change(self.root, 'B01', '1.1.1', 'claim')
        track = read_tracks(self.root)[0]
        directory = track.path.parent / track.sections[0].relative_directory()
        directory.mkdir(parents=True)
        (directory / 'README.md').write_text(
            '# 仅有目录引用\n\n## 学习目标覆盖\n\n[上级目录](../../README.md)\n')
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'finish')
        (directory / 'README.md').write_text(
            '# 仅有外部材料\n\n## 学习目标覆盖\n\n[外站](https://example.org/article.md)\n')
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'finish')

    def test_cannot_finish_with_cyclic_guides(self):
        change(self.root, 'B01', '1.1.1', 'claim')
        track = read_tracks(self.root)[0]
        directory = track.path.parent / track.sections[0].relative_directory()
        directory.mkdir(parents=True)
        other = directory.parent / '9.9.9_另一导读'
        other.mkdir()
        (directory / 'README.md').write_text(
            '## 学习目标覆盖\n\n[另一导读](../9.9.9_另一导读/README.md)\n')
        (other / 'README.md').write_text(
            f'## 学习目标覆盖\n\n[循环导读](../{directory.name}/README.md)\n')
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'finish')

    def test_two_claimers_only_one_wins(self):
        def attempt(_):
            try:
                change(self.root, 'B01', '1.1.1', 'claim')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(1, sum(pool.map(attempt, range(2))))

    def test_abort_only_from_processing(self):
        with self.assertRaises(ValueError):
            change(self.root, 'B01', '1.1.1', 'abort')
        change(self.root, 'B01', '1.1.1', 'claim')
        self.assertEqual('ABORT', change(self.root, 'B01', '1.1.1', 'abort')['status'])


if __name__ == '__main__':
    unittest.main()
