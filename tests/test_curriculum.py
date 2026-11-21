"""真实目录直接混排共性知识与专题扩展，不再使用阶段路线。"""
from pathlib import Path
from collections import defaultdict
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from catalog import read_tracks
from validate import reference_errors


class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracks = read_tracks(ROOT)
        cls.by_code = {track.code: track for track in cls.tracks}

    def test_all_tracks_use_one_numbered_curriculum(self):
        for track in self.tracks:
            with self.subTest(track=track.code):
                self.assertNotIn('## 学习路线', track.text)
                self.assertIsNone(re.search(r'^### 阶段 \d+', track.text, re.M))
                self.assertEqual([], reference_errors(track, self.tracks, ROOT))
                self.assertEqual(len(track.sections), len(track.tasks) + len(track.references))
                self.assertLess(len(track.sections), 100)

    def test_topics_interleave_foundations_with_owned_extensions(self):
        for code, track in self.by_code.items():
            if code[0] not in 'PD':
                continue
            groups = defaultdict(set)
            for section in track.sections:
                groups[section.number.rsplit('.', 1)[0]].add(section.kind)
            self.assertTrue(any(kinds == {'task', 'reference'} for kinds in groups.values()), code)

    def test_p09_statistics_chapter_contains_common_and_domain_content(self):
        track = self.by_code['P09']
        chapter = [s for s in track.sections if s.number.startswith('2.')]
        self.assertTrue(any(s.kind == 'reference' and '条件概率' in s.title for s in chapter))
        self.assertTrue(any(s.kind == 'reference' and '效应量' in s.title for s in chapter))
        self.assertTrue(any(s.kind == 'task' and s.title.startswith('扰动效应估计') for s in chapter))
        section = [s for s in chapter if s.number.startswith('2.2.')]
        self.assertEqual({'task', 'reference'}, {s.kind for s in section})
        self.assertTrue(any('GEARS' in s.title for s in track.tasks))
        self.assertTrue(any('chemCPA' in s.title for s in track.tasks))


if __name__ == '__main__':
    unittest.main()
