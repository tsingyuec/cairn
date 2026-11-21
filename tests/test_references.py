from pathlib import Path
import json
import subprocess
import sys
import unittest

from test_catalog import FixtureTests, fixture
from catalog import read_tracks
from sections import change
from validate import validate

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/sections.py'


class ReferenceTests(FixtureTests):
    def setUp(self):
        super().setUp()
        self.root = self.root / 'mixed'
        self.root.mkdir()
        self.paths = fixture(self.root, [('B01', []), ('M01', [])], count=2)
        self.source = '../../../基础知识/模型方法/M01主题/README.md#m01-1-1-1'
        self.replace('- 1.1.1 小节1 <a id="b01-1-1-1"></a> [WAITING]',
                     self.reference_row('1.1.1', self.source))

    def reference_row(self, number, source):
        return (f'- {number} 共同概念 <a id="b01-{number.replace(".", "-")}"></a> [REUSE]({source})\n'
                '  - 学习目标：掌握共同定义和计算关系。')

    def test_reference_is_a_leaf_but_not_a_task_or_status(self):
        result = validate(self.root)
        self.assertEqual([], result.errors)
        self.assertEqual(4, result.sections)
        self.assertEqual(3, result.tasks)
        self.assertEqual(1, result.references)
        self.assertEqual({'WAITING': 3}, result.statuses)
        track = next(t for t in read_tracks(self.root) if t.code == 'B01')
        self.assertEqual(1, len(track.tasks))
        self.assertEqual(1, len(track.references))
        self.assertIsNone(track.references[0].status)
        self.assertEqual(self.source, track.references[0].reuse_source)
        with self.assertRaisesRegex(ValueError, '没有独立正文目录'):
            track.references[0].relative_directory()

    def test_all_progress_operations_reject_reference(self):
        path = self.paths['B01']
        before = path.read_text()
        for action in ['claim', 'finish', 'release', 'abort']:
            with self.assertRaisesRegex(ValueError, '没有独立进度'):
                change(self.root, 'B01', '1.1.1', action)
        self.assertEqual(before, path.read_text())

    def test_whole_course_and_chapter_are_not_reference_sources(self):
        self.replace(self.source, self.source.partition('#')[0] + '#m01-1')
        self.assertIn('不能引用整课或整章', self.errors())

    def test_external_source_is_rejected(self):
        self.replace(self.source, 'https://example.org/lesson')
        self.assertIn('项目内具体自有小节', self.errors())

    def test_learning_goal_is_required(self):
        self.replace('  - 学习目标：掌握共同定义和计算关系。\n', '')
        self.assertIn('缺少学习目标', self.errors())

    def test_duplicate_reuse_in_one_curriculum_is_rejected(self):
        self.replace('- 1.1.2 小节2 <a id="b01-1-1-2"></a> [WAITING]', self.reference_row('1.1.2', self.source))
        self.assertIn('重复 REUSE 同一小节', self.errors())

    def test_chained_reference_is_rejected(self):
        path = self.paths['M01']
        old = '- 1.1.1 小节1 <a id="m01-1-1-1"></a> [WAITING]'
        new = ('- 1.1.1 另一处复用 <a id="m01-1-1-1"></a> [REUSE](README.md#m01-1-1-2)\n'
               '  - 学习目标：阅读真正原节。')
        path.write_text(path.read_text().replace(old, new))
        self.assertIn('不得链式 REUSE', self.errors())

    def test_reference_source_must_be_foundation(self):
        root = self.root / 'pd'
        root.mkdir()
        paths = fixture(root, [('P01', []), ('D01', [])], count=2)
        path = paths['P01']
        path.write_text(path.read_text().replace(
            '- 1.1.1 小节1 <a id="p01-1-1-1"></a> [WAITING]',
            '- 1.1.1 数据资源概念 <a id="p01-1-1-1"></a> [REUSE](../../数据资源/D01主题/README.md#d01-1-1-1)\n'
            '  - 学习目标：说明数据资源概念。'))
        errors = '\n'.join(validate(root).errors)
        self.assertIn('REUSE 来源须在基础知识（B/M）中', errors)

    def test_reference_cannot_carry_a_progress_status(self):
        self.replace('[REUSE]', '[REUSE] [DONE]')
        self.assertIn('小节格式/状态非法', self.errors())

    def test_task_listing_skips_references_by_default(self):
        command = [sys.executable, str(SCRIPT), '--root', str(self.root), 'list', '--track', 'B01']
        tasks = json.loads(subprocess.check_output(command, text=True))
        self.assertEqual(['1.1.2'], [row['section'] for row in tasks])
        full = json.loads(subprocess.check_output(command + ['--include-references'], text=True))
        self.assertEqual(2, len(full))
        self.assertEqual('reference', full[0]['kind'])
        self.assertIsNone(full[0]['status'])
        self.assertIsNone(full[0]['content'])
        self.assertEqual(self.source, full[0]['source'])


if __name__ == '__main__':
    unittest.main()