#!/usr/bin/env python3
"""workspace.py 共享解析模块回归测试。

覆盖方案中 T1-T6：
- T1 source_file 向上命中 articles+published 结构标记
- T2 explicit 显式指定优先；T2b explicit 不存在返回 None
- T3 无特征目录 + 无显式 -> None（绝不回退脚本位置推算）
- T4 cwd 处于工作区内 -> cwd 命中
- T5 环境变量 WECHAT_WORKSPACE
- T6 .obsidian 目录同样被识别为工作区根
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


WORKSPACE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "workspace.py"
SPEC = importlib.util.spec_from_file_location("wechat_workspace", WORKSPACE_PATH)
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


class WorkspaceResolveTest(unittest.TestCase):
    def _make_ws(self):
        """构造含 articles/+published/ 结构的工作区。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        wsroot = tmp / "WechatWrite"
        (wsroot / "articles").mkdir(parents=True)
        (wsroot / "published").mkdir()
        proj = wsroot / "articles" / "Project_测试"
        proj.mkdir()
        draft = proj / "02_Draft.md"
        draft.write_text("x", encoding="utf-8")
        return tmp, wsroot, proj, draft

    def test_t1_source_file_walks_up(self):
        """source_file 在项目内，向上命中工作区根。"""
        _, wsroot, _, draft = self._make_ws()
        root, method = workspace.resolve_workspace(source_file=str(draft))
        self.assertEqual(root, wsroot.resolve())
        self.assertEqual(method, "source")

    def test_t2_explicit_wins(self):
        """显式 explicit 优先于自动检测。"""
        tmp, wsroot, _, draft = self._make_ws()
        other = tmp / "other"
        other.mkdir()
        root, method = workspace.resolve_workspace(source_file=str(draft), explicit=str(other))
        self.assertEqual(root, other.resolve())
        self.assertEqual(method, "explicit")

    def test_t2b_explicit_missing_returns_none(self):
        """显式指定但目录不存在 -> (None, explicit)，交由调用方报错。"""
        tmp, _, _, _ = self._make_ws()
        root, method = workspace.resolve_workspace(explicit=str(tmp / "nope"))
        self.assertIsNone(root)
        self.assertEqual(method, "explicit")

    def test_t3_no_markers_returns_none(self):
        """无特征目录 + 无显式 -> None（绝不回退脚本位置推算）。"""
        tmp, _, _, _ = self._make_ws()
        root, method = workspace.resolve_workspace(cwd=tmp)
        self.assertIsNone(root)
        self.assertEqual(method, "none")

    def test_t4_cwd_inside_workspace(self):
        """cwd 处于工作区内 -> cwd 命中。"""
        tmp, wsroot, proj, _ = self._make_ws()
        root, method = workspace.resolve_workspace(cwd=str(proj))
        self.assertEqual(root, wsroot.resolve())
        self.assertEqual(method, "cwd")

    def test_t5_env_var(self):
        """环境变量 WECHAT_WORKSPACE 生效。"""
        tmp, wsroot, _, _ = self._make_ws()
        os.environ["WECHAT_WORKSPACE"] = str(wsroot)
        try:
            root, method = workspace.resolve_workspace(cwd=str(tmp))
            self.assertEqual(root, wsroot.resolve())
            self.assertEqual(method, "env")
        finally:
            del os.environ["WECHAT_WORKSPACE"]

    def test_t6_obsidian_vault_recognized(self):
        """.obsidian/ 目录同样被识别为工作区根。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        vault = tmp / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        f = vault / "a.md"
        f.write_text("x", encoding="utf-8")
        root, method = workspace.resolve_workspace(source_file=str(f))
        self.assertEqual(root, vault.resolve())
        self.assertEqual(method, "source")


if __name__ == "__main__":
    unittest.main()
