import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "material_store.py"
SPEC = importlib.util.spec_from_file_location("wechat_material_store", SCRIPT)
material_store = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(material_store)


class MaterialStoreTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "articles").mkdir()
        (self.root / "knowledge").mkdir()

    def test_project_seed_requires_existing_project(self):
        with self.assertRaises(FileNotFoundError):
            material_store.store_material(
                self.root, "project-seed", "内容", project="不存在", topic="主题"
            )

    def test_project_seed_is_written_under_current_project(self):
        project = self.root / "articles" / "Project_测试"
        project.mkdir()
        target = material_store.store_material(
            self.root, "project-seed", "内容", project="测试", topic="主题"
        )
        self.assertEqual(target.parent, (project / "_source" / "Seeds").resolve())
        self.assertTrue(target.exists())

    def test_material_duplicate_is_rejected(self):
        first = material_store.store_material(self.root, "material", "相同内容", topic="A")
        self.assertTrue(first.exists())
        with self.assertRaises(FileExistsError):
            material_store.store_material(self.root, "material", "相同内容", topic="B")


if __name__ == "__main__":
    unittest.main()
