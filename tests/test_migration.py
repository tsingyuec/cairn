"""分阶段解析目录迁移；旧编号仍存在不代表教学范围仍相同。"""
from collections import Counter
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from catalog import read_tracks


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = ROOT / 'docs/目录审查'
        cls.first = json.loads((directory / '2026-11-20-小节迁移映射.json').read_text())
        cls.refinement = json.loads((directory / '2026-11-20-机制粒度复审.json').read_text())
        cls.second = {item['old_id']: item for item in cls.refinement['items']}
        cls.path_review = json.loads((directory / '2026-11-20-学习路径与补缺映射.json').read_text())
        cls.third = {item['old_id']: item for item in cls.path_review['items']}
        cls.integration = json.loads((directory / '2026-11-20-章节整合映射.json').read_text())
        cls.fourth = {item['old_id']: item['targets'][0] for item in cls.integration['items']}
        cls.supplements = [
            json.loads((directory / name).read_text()) for name in [
                '2026-11-21-基础脉络补缺映射.json',
                '2026-11-21-专题脉络补缺映射.json',
                '2026-11-21-专题脉络补缺修正.json',
                '2026-11-21-专题脉络补缺修正2.json',
                '2026-11-21-第二轮复审修复映射.json',
                '2026-11-21-第二轮复审目标修订.json',
                '2026-11-21-第二轮复审收尾映射.json',
                '2026-11-21-第二轮复审目标修订2.json',
                '2026-11-21-第二轮复审目标修订3.json',
                '2026-11-21-第二轮复审收尾映射2.json',
                '2026-11-21-第二轮复审收尾映射3.json',
            ]]
        cls.mappings = [{(item['code'], item['old_anchor']): item['new_anchor']
                         for item in ledger['items']} for ledger in cls.supplements]
        cls.tracks = {track.code: track for track in read_tracks(ROOT)}
        # 复用条目是课程内容，不是旧写作小节的迁移目标；任务映射只指向自有小节。
        cls.current = {(track.code, section.number): section
                       for track in cls.tracks.values() for section in track.tasks}
        # 复审允许把重复的自有任务改为 REUSE；旧任务仍应解析到同一个小节。
        cls.by_anchor = {(track.code, section.anchor): section
                         for track in cls.tracks.values() for section in track.sections}

    def through_path_review(self, target):
        # 每阶段只应用一次；拆分的首目标可能保留旧编号，不能递归直到编号不变。
        key = f"{target['code']}:{target['number']}"
        return self.third[key]['targets'] if key in self.third else [target]

    def integrated(self, target):
        return self.fourth[f"{target['code']}:{target['number']}"]

    def current_anchor(self, target):
        anchor = target['anchor']
        for mapping in self.mappings:
            anchor = mapping.get((target['code'], anchor), anchor)
        self.assertIn((target['code'], anchor), self.by_anchor, target)
        return anchor

    def goal(self, target):
        target = self.integrated(target)
        return self.by_anchor[(target['code'], self.current_anchor(target))].learning_goal

    def assert_current_target(self, target):
        target = self.integrated(target)
        anchor = self.current_anchor(target)
        section = self.by_anchor[(target['code'], anchor)]
        self.assertEqual(self.tracks[target['code']].path, ROOT / target['path'])
        return (target['code'], section.number)

    def test_all_old_tasks_resolve_through_the_full_mapping_chain(self):
        entries = self.first['items']
        self.assertEqual(638, self.first['old_total'])
        self.assertEqual(self.first['old_total'], len(entries))
        self.assertEqual(len(entries), len({item['old_id'] for item in entries}))
        intermediate, resolved = set(), set()
        for item in entries:
            self.assertTrue(item['rationale'])
            self.assertTrue(item['targets'], item['old_id'])
            for target in item['targets']:
                old_id = f"{target['code']}:{target['number']}"
                intermediate.add(old_id)
                self.assertIn(old_id, self.second, item['old_id'])
                refinement = self.second[old_id]
                self.assertEqual(target['anchor'], refinement['old_anchor'])
                self.assertEqual(target['path'], refinement['path'])
                for previous in refinement['targets']:
                    for current in self.through_path_review(previous):
                        resolved.add(self.assert_current_target(current))
        self.assertEqual(self.first['new_total'], len(intermediate))
        self.assertEqual(intermediate, set(self.second))
        additions = {self.assert_current_target(t)
                     for previous in self.refinement['additions'] for t in self.through_path_review(previous)}
        latest_additions = {self.assert_current_target(t) for t in self.path_review['additions']}
        self.assertTrue(resolved.isdisjoint(additions))
        self.assertTrue((resolved | additions).isdisjoint(latest_additions))
        self.assertEqual(self.path_review['new_total'], len(resolved | additions | latest_additions))

    def test_refinement_covers_every_previous_unit_without_duplicate_destinations(self):
        ledger = self.refinement
        self.assertEqual(531, ledger['old_total'])
        self.assertEqual(ledger['old_total'], len(ledger['items']))
        self.assertEqual(ledger['old_total'], len(self.second))
        destinations = []
        for item in ledger['items']:
            self.assertTrue(item['rationale'])
            self.assertTrue(item['targets'], item['old_id'])
            for target in item['targets']:
                destinations.append(self.assert_current_target(target))
        destinations.extend(self.assert_current_target(t) for t in ledger['additions'])
        self.assertEqual(ledger['new_total'], len(destinations))
        self.assertEqual(len(destinations), len(set(destinations)))
        # 后续可以新增内容，不能把这份历史快照当作未来总量上限。
        self.assertLessEqual(len(destinations), len(self.current))

    def test_chapter_integration_moves_every_task_once_and_adds_only_references(self):
        ledger = self.integration
        self.assertEqual(798, ledger['old_total'])
        self.assertEqual(799, ledger['owned_total'])
        self.assertEqual(798, len(self.fourth))
        destinations = {(t['code'], self.current_anchor(t)) for t in self.fourth.values()}
        # 之后允许新增或把 REUSE 改为自有任务；旧任务必须仍全部存在。
        self.assertLessEqual(destinations, set(self.by_anchor))
        self.assertLessEqual(ledger['owned_total'], len(self.current))
        for item in ledger['items']:
            self.assertEqual(1, len(item['targets']))
            target = item['targets'][0]
            self.assertIn((target['code'], self.current_anchor(target)), self.by_anchor)
        references = set()
        for r in ledger['references']:
            anchor = r['anchor']
            for mapping in self.mappings:
                anchor = mapping.get((r['code'], anchor), anchor)
            references.add((r['code'], anchor))
        actual = {(track.code, s.anchor) for track in self.tracks.values() for s in track.references}
        self.assertLessEqual(references, actual)
        self.assertLessEqual(ledger['reference_total'], len(actual))

    def test_learning_path_review_covers_previous_snapshot_and_all_new_targets(self):
        previous = [target for item in self.refinement['items'] for target in item['targets']]
        previous.extend(self.refinement['additions'])
        self.assertEqual({f"{t['code']}:{t['number']}" for t in previous}, set(self.path_review['old_ids']))
        self.assertEqual(len(previous), self.path_review['old_total'])
        resolved = [self.assert_current_target(t) for old in previous for t in self.through_path_review(old)]
        resolved.extend(self.assert_current_target(t) for t in self.path_review['additions'])
        self.assertEqual(self.path_review['new_total'], len(resolved))
        self.assertEqual(len(resolved), len(set(resolved)))
        for item in self.path_review['items']:
            for target in item['targets']:
                self.assertTrue(self.goal(target))
        for target in self.path_review['additions']:
            self.assertTrue(self.goal(target))

    def test_capacity_and_statistics_are_per_leaf_track(self):
        ledger = self.refinement
        previous = Counter(item['old_id'].split(':')[0] for item in ledger['items'])
        current = Counter(target['code'] for item in ledger['items'] for target in item['targets'])
        current.update(target['code'] for target in ledger['additions'])
        for track in ledger['tracks']:
            self.assertEqual(track['before'], previous[track['code']])
            self.assertEqual(track['after'], current[track['code']])
            self.assertGreater(track['after'], 0)
            self.assertLess(track['after'], 100)
        for prefix, stat in ledger['statistics'].items():
            self.assertEqual(stat['after'], sum(n for code, n in current.items() if code.startswith(prefix)))
        self.assertGreater(ledger['statistics']['B']['after'], 100)
        self.assertEqual(ledger['new_total'], sum(current.values()))

    def test_split_and_added_units_have_distinct_learning_goals(self):
        for item in self.refinement['items']:
            if item['action'] != 'split_and_expand':
                continue
            self.assertGreater(len(item['targets']), 1)
            goals = [self.goal(t) for t in item['targets']]
            self.assertTrue(all(goals), item['old_id'])
            self.assertEqual(len(goals), len(set(goals)), item['old_id'])
        for target in self.refinement['additions']:
            self.assertTrue(self.goal(target))


if __name__ == '__main__':
    unittest.main()
