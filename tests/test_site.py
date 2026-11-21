"""覆盖迁移特有的页面路径、引用锚点与多层目录装配。需站点依赖。"""
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('cairn_site_builder', Path(__file__).resolve().parents[1] / 'site/build_site.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class SiteTests(unittest.TestCase):
    def test_home_and_knowledge_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'content/基础知识/生物学/系列').mkdir(parents=True)
            (root / 'README.md').write_text('# 项目首页')
            (root / 'content/README.md').write_text('# 知识总目录')
            (root / 'content/基础知识/生物学/系列/README.md').write_text('# 系列')
            with patch.object(builder, 'ROOT', str(root)), patch.object(builder, 'CONTENT', str(root / 'content')):
                files, urls, present = builder.build_plan()
            self.assertEqual('index.md', files['README.md'])
            self.assertEqual('knowledge.md', files['content/README.md'])
            self.assertEqual(len(files), len(set(files.values())))
            nav = builder.build_nav(files)
            self.assertIn({'知识总目录': 'knowledge.md'}, nav)

    def test_nested_cross_track_reference_preserves_anchor(self):
        stats = {'rewritten': 0, 'unpublished': 0, 'missing': 0}
        source = 'content/专题知识/模型/新模型/README.md'
        target = 'content/基础知识/模型方法/图学习/README.md'
        docs = '专题知识/模型/新模型/index.md'
        urls = {source: docs, target: '基础知识/模型方法/图学习/index.md'}
        text = '[基础](../../../基础知识/模型方法/图学习/README.md#m03-3-1-2)'
        result = builder.rewrite_text(text, source, docs, urls, set(urls), stats)
        self.assertIn('#m03-3-1-2', result)
        self.assertIn('index.md#', result)
        self.assertEqual(1, stats['rewritten'])
        self.assertEqual(0, stats['missing'])

    def test_code_block_example_does_not_become_missing_link(self):
        stats = {'rewritten': 0, 'unpublished': 0, 'missing': 0}
        text = '```markdown\n[示例](not-real.md)\n```'
        self.assertEqual(text, builder.rewrite_text(text, 'README.md', 'index.md', {}, set(), stats))
        self.assertEqual(0, stats['missing'])

    def test_multi_blog_paths_are_not_flattened(self):
        files = {
            'README.md': 'index.md',
            'content/基础/系列/README.md': '基础/系列/index.md',
            'content/基础/系列/1.1_节/1.1.1_小节/文章一.md': '基础/系列/1.1_节/1.1.1_小节/文章一.md',
            'content/基础/系列/1.1_节/1.1.1_小节/文章二.md': '基础/系列/1.1_节/1.1.1_小节/文章二.md',
        }
        nav = str(builder.build_nav(files))
        self.assertIn('1.1_节', nav)
        self.assertIn('1.1.1_小节', nav)
        self.assertIn('文章一.md', nav)
        self.assertIn('文章二.md', nav)


if __name__ == '__main__':
    unittest.main()
