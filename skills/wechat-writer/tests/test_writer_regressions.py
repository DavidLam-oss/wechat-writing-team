import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def module(name):
    spec = importlib.util.spec_from_file_location("writer_review_" + name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


research = module("research")
memory = module("memory_store")
config = module("config_check")
archive = module("archive")
review = module("review_toolkit")
cleaner = module("cleaner")
material = module("material_store")


class WriterRegressionTest(unittest.TestCase):
    def test_missing_required_script_does_not_report_ready(self):
        with mock.patch.object(config, "check_scripts", return_value=["❌ scripts/archive.py 未找到"]), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(config.run_check(), 1)
        self.assertNotIn("环境就绪", output.getvalue())

    def test_first_index_keeps_heading_before_month(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive.update_index("first", "summary", "first", workspace_root=root)
            content = (root / "conductor/published_article_index.md").read_text(encoding="utf-8")
            self.assertTrue(content.startswith("# 已发布文章索引"))
            self.assertLess(content.index("> 运行数据"), content.index("## 20"))

    def test_review_write_failure_returns_nonzero_for_all_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "_temp_report.json"
            source.write_text("{}", encoding="utf-8")
            for mode in ("critique", "directive", "feedback"):
                with self.subTest(mode=mode), mock.patch("sys.argv", ["review_toolkit", "--mode", mode, str(source)]), mock.patch.object(Path, "write_text", side_effect=PermissionError("locked")):
                    self.assertEqual(review.main(), 1)

    def test_cleaner_missing_input_and_write_failure_return_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "clean.json"
            with mock.patch("sys.argv", ["cleaner", str(source)]):
                self.assertEqual(cleaner.main(), 1)
            source.write_text('{"cleaned_content":"body"}', encoding="utf-8")
            with mock.patch("sys.argv", ["cleaner", str(source)]), mock.patch.object(Path, "write_text", side_effect=PermissionError("locked")):
                self.assertEqual(cleaner.main(), 1)

    def test_duplicate_material_cli_has_friendly_failure(self):
        with mock.patch("sys.argv", ["material_store", "--workspace", ".", "--destination", "material", "--content", "body"]), mock.patch.object(material, "store_material", side_effect=FileExistsError("duplicate")), mock.patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(material.main(), 1)
            self.assertIn("Error:", output.getvalue())
            self.assertNotIn("Traceback", output.getvalue())

    def test_missing_workspace_shows_actionable_guidance(self):
        with mock.patch.object(config, "get_workspace_root", return_value=None), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            config.run_check()
        self.assertIn("请先选择文章工作区", output.getvalue())
        self.assertNotIn("按需替换", output.getvalue())

    def test_corrected_verdict_shows_the_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Research_Report.md"
            research.render_markdown({"data": {"fact_checks": [{"claim": "old", "verdict": "Verified (Corrected)",
                                        "truth": "corrected value", "source": "source"}]}}, path)
            self.assertIn("corrected value", path.read_text(encoding="utf-8"))

    def test_corrupt_memory_preserves_source_and_does_not_write(self):
        for contents in ("{broken", "{}", '["bad item"]'):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                pending = root / "conductor" / "pending_memory_suggestions.json"
                pending.parent.mkdir()
                pending.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    memory.apply_memory(root, "id", "accept")
                self.assertEqual(pending.read_text(encoding="utf-8"), contents)
                self.assertFalse((root / "knowledge" / "team_memory.md").exists())

    def test_personal_files_come_from_workspace(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(config, "get_workspace_root", return_value=Path(tmp)):
            knowledge = Path(tmp) / "knowledge"
            knowledge.mkdir()
            (knowledge / "team_memory.md").write_text("user data", encoding="utf-8")
            report = "\n".join(config.check_personal_files())
            self.assertIn("当前工作区团队记忆", report)
            self.assertNotIn("需要替换", report)

    def test_published_markdown_and_local_images_are_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "articles" / "Project_title"
            assets = project / "zpicture.assets"
            assets.mkdir(parents=True)
            source = project / "02_Draft.md"
            source.write_text("正文\n\n![插图](zpicture.assets/title_illustration-01.png)\n", encoding="utf-8")
            (assets / "title_illustration-01.png").write_bytes(b"director-validated-asset")
            (assets / "title_cover-combined.jpg").write_bytes(b"director-validated-cover")
            with mock.patch.object(archive, "is_obsidian_reachable", return_value=False):
                code = archive.process_archive({"source_file": str(source), "workspace_root": str(root),
                                               "frontmatter": {"title": "title", "excerpt": "summary"}})
            self.assertEqual(code, 0)
            final = root / "published" / "title.md"
            self.assertIn("zpicture.assets/title_illustration-01.png", final.read_text(encoding="utf-8"))
            self.assertTrue((final.parent / "zpicture.assets" / "title_illustration-01.png").exists())
            self.assertTrue((final.parent / "zpicture.assets" / "title_cover-combined.jpg").exists())
            self.assertTrue(source.exists())

    def test_missing_draft_does_not_create_empty_published_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = archive.process_archive({"source_file": str(root / "missing.md"), "workspace_root": str(root),
                                           "frontmatter": {"title": "missing"}})
            self.assertEqual(code, 2)
            self.assertFalse((root / "published" / "missing.md").exists())
