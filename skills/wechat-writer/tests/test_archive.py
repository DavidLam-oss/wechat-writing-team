#!/usr/bin/env python3
import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ARCHIVE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "archive.py"
SPEC = importlib.util.spec_from_file_location("wechat_writer_archive", ARCHIVE_PATH)
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


class ArchiveScriptTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "To-be-used").mkdir(parents=True, exist_ok=True)
        (self.workspace / "published").mkdir(parents=True, exist_ok=True)
        (self.workspace / "conductor" / "archive").mkdir(parents=True, exist_ok=True)

    def _create_project(self, project_name="Project_Test", draft_name="02_Draft.md"):
        project_dir = self.workspace / "To-be-used" / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        source = project_dir / draft_name
        source.write_text("正文第一段\n\n正文第二段\n", encoding="utf-8")
        return project_dir, source

    def _run_archive(self, source_file, frontmatter, patch_move=None):
        data = {"source_file": str(source_file), "frontmatter": frontmatter}
        patchers = [
            mock.patch.object(archive, "get_workspace_root", return_value=self.workspace),
            mock.patch.object(archive, "update_index", return_value=None),
        ]
        if patch_move is not None:
            patchers.append(mock.patch.object(archive.shutil, "move", side_effect=patch_move))

        with patchers[0], patchers[1]:
            if len(patchers) == 3:
                with patchers[2]:
                    archive.process_archive(data)
            else:
                archive.process_archive(data)

    @staticmethod
    def _extract_frontmatter_value(markdown_text, key):
        match = re.search(rf'^{key}:\s*"(.*)"$', markdown_text, re.MULTILINE)
        if not match:
            return None
        return match.group(1)

    def test_pick_cover_image_prioritizes_combined(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"main")
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")
        (img_dir / "cover-sidebar.jpg").write_bytes(b"sidebar")

        selected = archive.pick_cover_image(img_dir)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "cover-combined.jpg")

    def test_process_archive_auto_cover_uses_combined(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"main")
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")
        (img_dir / "cover-sidebar.jpg").write_bytes(b"sidebar")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": ["t1"],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "workspace/published/img/cover-combined.jpg",
        )

    def test_process_archive_keeps_explicit_cover(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"main")
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "cover": "published/custom/my-cover.jpg",
            "tags": [],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "workspace/published/custom/my-cover.jpg",
        )

    def test_process_archive_leaves_cover_empty_when_no_valid_cover(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-sidebar.jpg").write_bytes(b"sidebar")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(self._extract_frontmatter_value(output, "cover"), "")

    def test_process_archive_falls_back_to_cover_main(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"main")
        (img_dir / "cover-sidebar.jpg").write_bytes(b"sidebar")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "workspace/published/img/cover-main.jpg",
        )

    def test_process_archive_continues_when_img_move_fails(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        real_move = shutil.move

        def flaky_move(src, dst, *args, **kwargs):
            if Path(src).name == "img":
                raise OSError("simulated move error")
            return real_move(src, dst, *args, **kwargs)

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm, patch_move=flaky_move)

        output_file = self.workspace / "published" / "Article.md"
        self.assertTrue(output_file.exists())
        output = output_file.read_text(encoding="utf-8")
        self.assertEqual(self._extract_frontmatter_value(output, "cover"), "")

    def test_process_archive_keeps_explicit_cover_when_move_fails(self):
        _, source = self._create_project()
        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        real_move = shutil.move

        def flaky_move(src, dst, *args, **kwargs):
            if Path(src).name == "img":
                raise OSError("simulated move error")
            return real_move(src, dst, *args, **kwargs)

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "cover": "published/custom/my-cover.jpg",
            "tags": [],
        }
        self._run_archive(source, fm, patch_move=flaky_move)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "workspace/published/custom/my-cover.jpg",
        )

    def test_process_archive_escapes_frontmatter_values(self):
        _, source = self._create_project()
        title = 'Title "Q" \\ Path'
        excerpt = 'Say "Hi" in C:\\tmp'
        slug = 'slug-"quoted"-\\'

        fm = {
            "title": title,
            "slug": slug,
            "excerpt": excerpt,
            "tags": [],
        }
        self._run_archive(source, fm)

        safe_title = archive.sanitize_filename(title)
        output = (self.workspace / "published" / f"{safe_title}.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "title"),
            archive.yaml_escape(title),
        )
        self.assertEqual(
            self._extract_frontmatter_value(output, "slug"),
            archive.yaml_escape(slug),
        )
        self.assertEqual(
            self._extract_frontmatter_value(output, "excerpt"),
            archive.yaml_escape(excerpt),
        )

    def test_process_archive_does_not_clamp_excerpt(self):
        _, source = self._create_project()
        long_excerpt = "a" * 140

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": long_excerpt,
            "tags": [],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        excerpt = self._extract_frontmatter_value(output, "excerpt")
        self.assertEqual(len(excerpt), 140)
        self.assertEqual(excerpt, "a" * 140)

    def test_process_archive_warns_when_excerpt_exceeds_120(self):
        _, source = self._create_project()
        long_excerpt = "a" * 140
        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": long_excerpt,
            "tags": [],
        }

        with mock.patch("builtins.print") as mock_print:
            self._run_archive(source, fm)

        warning = "⚠️ Excerpt length is 140 (>120). Please shorten it in Stage 3."
        self.assertTrue(
            any(args and args[0] == warning for args, _ in mock_print.call_args_list)
        )

    def test_process_archive_replaces_published_img_with_backup(self):
        _, source = self._create_project()
        old_img = self.workspace / "published" / "img"
        old_img.mkdir()
        (old_img / "cover-main.jpg").write_bytes(b"old")

        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"new")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm)

        new_cover = self.workspace / "published" / "img" / "cover-main.jpg"
        self.assertTrue(new_cover.exists())

        backups = list((self.workspace / "published").glob("img_prev_*"))
        self.assertTrue(backups)
        self.assertTrue((backups[0] / "cover-main.jpg").exists())

    def test_process_archive_continues_when_backup_move_fails(self):
        _, source = self._create_project()
        old_img = self.workspace / "published" / "img"
        old_img.mkdir()
        (old_img / "cover-main.jpg").write_bytes(b"old")

        img_dir = source.parent / "img"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"new")

        real_move = shutil.move

        def flaky_move(src, dst, *args, **kwargs):
            src_path = Path(src)
            if src_path.name == "img" and src_path.parent.name == "published":
                raise OSError("simulated backup move error")
            return real_move(src, dst, *args, **kwargs)

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm, patch_move=flaky_move)

        output_file = self.workspace / "published" / "Article.md"
        self.assertTrue(output_file.exists())
        output = output_file.read_text(encoding="utf-8")
        self.assertEqual(self._extract_frontmatter_value(output, "cover"), "")
        self.assertTrue((self.workspace / "published" / "img" / "cover-main.jpg").exists())


if __name__ == "__main__":
    unittest.main()
