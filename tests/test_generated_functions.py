"""Synthetic checks for codegen repartitioning and ambiguous-function rejection."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from generated_functions import locate_functions


class GeneratedFunctionLocations(unittest.TestCase):
    def test_repartitioning_and_shared_unit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / 'ben10_recomp.97.cpp'
            second = root / 'ben10_recomp.3.cpp'
            first.write_text('DEFINE_REX_FUNC(sub_A) {\n}\nDEFINE_REX_FUNC(sub_B) {\n}\n')
            second.write_text('DEFINE_REX_FUNC(sub_C) {\n}\n')
            expected = {'sub_A': first, 'sub_B': first, 'sub_C': second}
            self.assertEqual(locate_functions(root, expected), expected)
            moved = root / 'ben10_recomp.200.cpp'
            first.rename(moved)
            expected.update(sub_A=moved, sub_B=moved)
            self.assertEqual(locate_functions(root, expected), expected)

    def test_missing_function_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'found 0'):
                locate_functions(directory, ['sub_missing'])

    def test_duplicate_function_rejected(self):
        for same_file in (True, False):
            with self.subTest(same_file=same_file), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                definition = 'DEFINE_REX_FUNC(sub_A) {\n}\n'
                (root / 'one.cpp').write_text(definition * (2 if same_file else 1))
                if not same_file:
                    (root / 'two.cpp').write_text(definition)
                with self.assertRaisesRegex(RuntimeError, 'found 2'):
                    locate_functions(root, ['sub_A'])


if __name__ == '__main__':
    unittest.main()
