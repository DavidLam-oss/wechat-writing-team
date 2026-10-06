import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("writer_packaging_archive", SCRIPTS / "archive.py")
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class PackagingFixes(unittest.TestCase):
    def test_markdown_examples_are_not_treated_as_missing_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self.setup_project(root, '```md\n![示例](missing.png)\n```\n`![示例](missing.png)`\n<!-- ![示例](missing.png) -->\n正文')
            self.assertEqual(self.publish(root, draft), 0)
            self.assertIn('![示例](missing.png)', (root / 'published/Test.md').read_text(encoding='utf-8'))

    def test_local_asset_outside_picture_folder_is_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self.setup_project(root, '![图](diagram.png)')
            (draft.parent / 'diagram.png').write_bytes(b'asset')
            self.assertEqual(self.publish(root, draft), 0)
            files = list((root / 'published/zpicture.assets').glob('import_*_diagram.png'))
            self.assertEqual(len(files), 1)
            self.assertIn(files[0].name, (root / 'published/Test.md').read_text(encoding='utf-8'))

    def setup_project(self, root, text):
        project = root / "articles/Project_Test"
        (project / "zpicture.assets").mkdir(parents=True)
        draft = project / "02_Draft.md"
        draft.write_text(text, encoding="utf-8")
        return draft

    def publish(self, root, draft, cover=""):
        with mock.patch.object(archive, "is_obsidian_reachable", return_value=False):
            return archive.process_archive({"source_file": str(draft), "workspace_root": str(root), "frontmatter": {"title": "Test", "cover": cover}})

    def test_dot_relative_missing_image_stops_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, "![图](./zpicture.assets/missing.png)")
            self.assertEqual(self.publish(root, draft), 1)
            self.assertFalse((root / "published/Test.md").exists())

    def test_explicit_missing_cover_stops_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, "body")
            self.assertEqual(self.publish(root, draft, "zpicture.assets/missing.jpg"), 1)
            self.assertFalse((root / "published/Test.md").exists())

    def test_encoded_local_image_is_preserved_and_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, '![图](./zpicture.assets/a%20b.png "title")')
            (draft.parent / "zpicture.assets/a b.png").write_bytes(b"asset")
            self.assertEqual(self.publish(root, draft), 0)
            self.assertTrue((root / "published/zpicture.assets/a b.png").is_file())

    def test_reference_style_missing_image_stops_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, "![图][pic]\n\n[pic]: ./zpicture.assets/missing.png")
            self.assertEqual(self.publish(root, draft), 1)

    def test_remote_image_and_cover_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, "![图](https://example.test/image.png)")
            self.assertEqual(self.publish(root, draft, "https://example.test/cover.jpg"), 0)
            content = (root / "published/Test.md").read_text(encoding="utf-8")
            self.assertIn("https://example.test/cover.jpg", content)

    def test_index_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, "body")
            with mock.patch.object(archive, "update_index", return_value=False):
                self.assertEqual(self.publish(root, draft), 1)

    def test_index_initialization_error_reports_partial_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); draft = self.setup_project(root, "body")
            with mock.patch.object(archive, "update_index", side_effect=PermissionError("locked")), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(self.publish(root, draft), 1)
            self.assertTrue((root / "published/Test.md").is_file())
            self.assertIn("Article and images saved", output.getvalue())

    def test_explicit_cli_workspace_has_priority_over_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);draft = self.setup_project(root, "body")
            with mock.patch.object(archive, "get_workspace_root", return_value=root) as resolve:
                archive.process_archive({"source_file": str(draft), "workspace_root": "other", "frontmatter": {"title": "Test"}}, explicit_workspace=str(root))
            self.assertEqual(resolve.call_args.kwargs["explicit"], str(root))
