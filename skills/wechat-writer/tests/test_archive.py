#!/usr/bin/env python3
import importlib.util
import re
import shutil
import tempfile
import unittest
from contextlib import ExitStack
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
        (self.workspace / "articles").mkdir(parents=True, exist_ok=True)
        (self.workspace / "published").mkdir(parents=True, exist_ok=True)
        (self.workspace / "conductor" / "archive").mkdir(parents=True, exist_ok=True)

    def _create_project(self, project_name="Project_Test", draft_name="02_Draft.md"):
        project_dir = self.workspace / "articles" / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        source = project_dir / draft_name
        source.write_text("正文第一段\n\n正文第二段\n", encoding="utf-8")
        return project_dir, source

    def _run_archive(self, source_file, frontmatter, patch_move=None, patch_copytree=None):
        data = {"source_file": str(source_file), "frontmatter": frontmatter}
        patchers = [
            mock.patch.object(archive, "get_workspace_root", return_value=self.workspace),
            mock.patch.object(archive, "update_index", return_value=True),
            mock.patch.object(archive, "is_obsidian_reachable", return_value=False),
        ]
        if patch_move is not None:
            patchers.append(mock.patch.object(archive.shutil, "move", side_effect=patch_move))
        if patch_copytree is not None:
            patchers.append(mock.patch.object(archive.shutil, "copytree", side_effect=patch_copytree))

        with ExitStack() as stack:
            for p in patchers:
                stack.enter_context(p)
            archive.process_archive(data)

    @staticmethod
    def _extract_frontmatter_value(markdown_text, key):
        match = re.search(rf'^{key}:\s*"(.*)"$', markdown_text, re.MULTILINE)
        if not match:
            return None
        return match.group(1)

    def test_pick_cover_image_prioritizes_combined(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"main")
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")
        (img_dir / "cover-sidebar.jpg").write_bytes(b"sidebar")

        selected = archive.pick_cover_image(img_dir)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "cover-combined.jpg")

    def test_process_archive_auto_cover_uses_combined(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
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
            "zpicture.assets/cover-combined.jpg",
        )

    def test_process_archive_remaps_project_relative_cover(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "cover": "zpicture.assets/cover-combined.jpg",
            "tags": [],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "zpicture.assets/cover-combined.jpg",
        )

    def test_process_archive_keeps_explicit_cover_when_target_missing(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "cover": "zpicture.assets/cover-sidebar.jpg",
            "tags": [],
        }
        self._run_archive(source, fm)

        self.assertFalse((self.workspace / "published" / "Article.md").exists())

    def test_process_archive_keeps_explicit_cover(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"main")
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "cover": "https://example.test/custom/my-cover.jpg",
            "tags": [],
        }
        self._run_archive(source, fm)

        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "https://example.test/custom/my-cover.jpg",
        )

    def test_process_archive_leaves_cover_empty_when_no_valid_cover(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
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
        img_dir = source.parent / "zpicture.assets"
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
            "zpicture.assets/cover-main.jpg",
        )

    def test_process_archive_stops_when_img_copy_fails(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        def flaky_copytree(src, dst, *args, **kwargs):
            if Path(src).name == "zpicture.assets":
                raise OSError("simulated copy error")
            return shutil.copytree(src, dst, *args, **kwargs)

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm, patch_copytree=flaky_copytree)

        output_file = self.workspace / "published" / "Article.md"
        self.assertFalse(output_file.exists())
        # 复制失败不影响项目原图保留在 articles
        self.assertTrue((img_dir / "cover-combined.jpg").exists())

    def test_process_archive_does_not_publish_explicit_cover_when_copy_fails(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")

        def flaky_copytree(src, dst, *args, **kwargs):
            if Path(src).name == "zpicture.assets":
                raise OSError("simulated copy error")
            return shutil.copytree(src, dst, *args, **kwargs)

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "cover": "https://example.test/custom/my-cover.jpg",
            "tags": [],
        }
        self._run_archive(source, fm, patch_copytree=flaky_copytree)

        self.assertFalse((self.workspace / "published" / "Article.md").exists())

    def test_process_archive_escapes_frontmatter_values(self):
        _, source = self._create_project()
        title = 'Title "Q" \\ Path'
        excerpt = 'Say "Hi" in folder\\tmp'
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

    def test_process_archive_merges_into_existing_published_assets(self):
        """合并模式：published/zpicture.assets 已存在旧文章图时，新文章图片并图保留旧图，不产生 zpicture_prev_*"""
        old_img = self.workspace / "published" / "zpicture.assets"
        old_img.mkdir()
        (old_img / "旧文章_cover-main.jpg").write_bytes(b"old")

        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "新文章_cover-main.jpg").write_bytes(b"new")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm)

        pub_img = self.workspace / "published" / "zpicture.assets"
        # 新旧图像并存
        self.assertTrue((pub_img / "旧文章_cover-main.jpg").exists())
        self.assertTrue((pub_img / "新文章_cover-main.jpg").exists())
        # 不再产生 zpicture_prev_* 备份目录
        backups = list((self.workspace / "published").glob("zpicture_prev_*"))
        self.assertEqual(backups, [])

    def test_process_archive_auto_cover_uses_project_dir_not_published(self):
        """回归：封面从"项目目录"（仅含本文章图片）选择，不受 published 中其他文章封面干扰。"""
        # published/zpicture.assets 已存在其他文章的封面
        old_img = self.workspace / "published" / "zpicture.assets"
        old_img.mkdir()
        (old_img / "他文_cover-combined.jpg").write_bytes(b"other")

        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "本文_cover-combined.jpg").write_bytes(b"mine")

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
            "zpicture.assets/本文_cover-combined.jpg",
        )

    def test_process_archive_continues_when_merge_copy_fails(self):
        """合并复制失败：正文仍发布、封面留空，不中断归档（容错）。"""
        _, source = self._create_project()
        old_img = self.workspace / "published" / "zpicture.assets"
        old_img.mkdir()
        (old_img / "cover-main.jpg").write_bytes(b"old")

        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-main.jpg").write_bytes(b"new")

        real_copytree = shutil.copytree

        def flaky_copytree(src, dst, *args, **kwargs):
            if Path(src).name == "zpicture.assets":
                raise OSError("simulated merge copy error")
            return real_copytree(src, dst, *args, **kwargs)

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm, patch_copytree=flaky_copytree)

        output_file = self.workspace / "published" / "Article.md"
        self.assertFalse(output_file.exists())
        self.assertTrue((self.workspace / "published" / "zpicture.assets" / "cover-main.jpg").exists())

    def test_update_index_writes_workspace_conductor(self):
        """发布索引写入工作区 conductor/（而非技能 knowledge/），缺失时自动创建。"""
        index_path = self.workspace / "conductor" / "published_article_index.md"
        self.assertFalse(index_path.exists())
        archive.update_index("测试标题", "测试摘要", "test-slug", workspace_root=self.workspace)
        self.assertTrue(index_path.exists())
        content = index_path.read_text(encoding="utf-8")
        self.assertIn("[[测试标题]]", content)
        self.assertIn("测试摘要", content)

    def test_update_index_escapes_table_cells(self):
        archive.update_index("特殊标题", "第一行|第二行\n第三行", "slug", workspace_root=self.workspace)
        content = (self.workspace / "conductor" / "published_article_index.md").read_text(encoding="utf-8")
        self.assertIn("第一行\\|第二行 第三行", content)

    def test_update_index_inserts_new_month_as_markdown_lines(self):
        index = self.workspace / "conductor" / "published_article_index.md"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            "# 已发布文章索引\n\n## 2020-01\n\n| 标题 | 摘要 |\n| --- | --- |\n| [[旧]] | 旧摘要 |\n",
            encoding="utf-8",
        )
        archive.update_index("新标题", "新摘要", "slug", workspace_root=self.workspace)
        content = index.read_text(encoding="utf-8")
        self.assertIn("## ", content)
        self.assertIn("[[新标题]]", content)
        self.assertIn("## 2020-01", content)

    def test_process_archive_auto_cover_uses_prefixed_combined(self):
        """新命名 {prefix}_cover-combined.jpg：自动选中前缀封面，cover 路径含前缀。"""
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "职场破窗效应_cover-main.jpg").write_bytes(b"main")
        (img_dir / "职场破窗效应_cover-combined.jpg").write_bytes(b"combined")

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
            "zpicture.assets/职场破窗效应_cover-combined.jpg",
        )

    def test_process_archive_remaps_explicit_unprefixed_cover(self):
        _, source = self._create_project()
        img_dir = source.parent / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "职场破窗效应_cover-combined.jpg").write_bytes(b"combined")
        self._run_archive(source, {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
            "cover": "zpicture.assets/cover-combined.jpg",
        })
        output = (self.workspace / "published" / "Article.md").read_text(encoding="utf-8")
        self.assertEqual(
            self._extract_frontmatter_value(output, "cover"),
            "zpicture.assets/职场破窗效应_cover-combined.jpg",
        )

    def test_process_archive_keeps_project_and_copies_images(self):
        """项目目录与图片保留在 articles，published 生成发布副本，不再移动归档。"""
        project_dir, source = self._create_project()
        img_dir = project_dir / "zpicture.assets"
        img_dir.mkdir()
        (img_dir / "cover-combined.jpg").write_bytes(b"combined")
        (img_dir / "illustration-01.jpg").write_bytes(b"illu1")

        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm)

        # 项目保留在 articles，图片原图仍在
        self.assertTrue(project_dir.exists())
        self.assertTrue((img_dir / "cover-combined.jpg").exists())
        self.assertTrue((img_dir / "illustration-01.jpg").exists())

        # published 存发布副本
        pub_img = self.workspace / "published" / "zpicture.assets"
        self.assertTrue((pub_img / "cover-combined.jpg").exists())
        self.assertTrue((pub_img / "illustration-01.jpg").exists())

    def test_process_archive_does_not_create_conductor_archive(self):
        """不再产生 conductor/archive/YYYYMMDD_[Title]/ 归档目录。"""
        _, source = self._create_project()
        fm = {
            "title": "Article",
            "slug": "article",
            "excerpt": "summary",
            "tags": [],
        }
        self._run_archive(source, fm)

        archive_dir = self.workspace / "conductor" / "archive"
        entries = list(archive_dir.iterdir()) if archive_dir.exists() else []
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
