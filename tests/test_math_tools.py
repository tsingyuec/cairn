from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), '公式检查需要 Node.js')
class MathToolTests(unittest.TestCase):
    def run_check(self, script, path):
        return subprocess.run(['node', str(ROOT / 'scripts/check' / script), str(path)],
                              cwd=ROOT, capture_output=True, text=True)

    def test_source_readme_is_checked_and_bad_formula_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'README.md'
            path.write_text('# 示例\n\n$\\notARealCommand{x}$\n')
            result = self.run_check('check_md_math.mjs', path.parent)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('1 个文件', result.stdout)
            path.write_text('# 示例\n\n$x^2 + y^2$\n')
            result = self.run_check('check_md_math.mjs', path.parent)
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            self.assertIn('1 个公式', result.stdout)

    def test_rendered_formula_and_leftover_dollar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.html'
            path.write_text('<article><span class="arithmatex">\\(x^2\\)</span></article>')
            result = self.run_check('check_katex.mjs', path.parent)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('扫描 1 个页面', result.stdout)
            path.write_text('<article>not rendered: $x^2$</article>')
            result = self.run_check('check_katex.mjs', path.parent)
            self.assertNotEqual(0, result.returncode)


if __name__ == '__main__':
    unittest.main()
