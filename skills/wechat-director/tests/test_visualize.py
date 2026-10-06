#!/usr/bin/env python3
"""visualize.py 行为护栏（表征测试 / characterization tests）。

目的
----
visualize.py 约 1128 行，此前**没有任何自动化验证**。在按职责拆分它之前，
先用这套测试把「当前行为」钉死；拆分后再跑同一套测试，用来证明「行为未变」。

护栏的性质（很重要）
--------------------
这里的断言是从**当前实现的实测输出**固化的，不是从规范推导的。
它们不判断「这样写对不对」，只判断「有没有变」。因此：

    ⚠️ 拆分时不要修改任何断言值。
       断言变红 = 行为变了 = 必须先查清原因，而不是改期望值迁就代码。

拆分时唯一允许改的地方
----------------------
如果某个符号被搬到了子模块，在下面的 SYMBOL_HOME 里登记它搬去了哪即可，
断言一行都不用动。

跑法
----
    cd skills/wechat-director/tests
    python3 -m unittest test_visualize -v

（导入 visualize.py 时会打印 Pillow / tinify / COS 缺失的警告，属正常现象。）
"""
import base64
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
DIRECTOR = HERE.parent
VISUALIZE_PATH = DIRECTOR / "scripts" / "visualize.py"
FIXTURES = HERE / "fixtures"

SPEC = importlib.util.spec_from_file_location(
    "wechat_director_visualize", VISUALIZE_PATH)
visualize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(visualize)

# 拆分后各模块在 scripts/ 下；让 importlib 也能找到它们
if str(DIRECTOR / "scripts") not in sys.path:
    sys.path.insert(0, str(DIRECTOR / "scripts"))

# 拆分后：若某符号被搬到子模块，在这里登记 {"符号名": "模块名"}。
# 断言永远不动 —— 这是护栏的核心纪律。
SYMBOL_HOME = {
    "ASPECT_RATIOS": "director_core",
    "DIRECTOR_VERSION": "director_core",
    "get_workspace_root": "director_core",
    "load_api_config": "director_core",
    "sanitize_filename": "director_core",
    "clean_prompt": "director_core",
    "check_ip_requirement": "director_core",
    "calculate_hash": "director_core",
    "require_config": "director_core",
    "extract_context": "brief_parser",
    "parse_visual_brief": "brief_parser",
    "_extract_gpt_image2_result": "providers.gpt_image2",
}


def _sym(name):
    """解析符号：先看主模块，再查 SYMBOL_HOME 指定的落地模块。"""
    if hasattr(visualize, name):
        return getattr(visualize, name)
    home = SYMBOL_HOME.get(name)
    if home:
        return getattr(importlib.import_module(home), name)
    raise AttributeError(f"{name} 在主模块和 SYMBOL_HOME 里都找不到")


def _norm(obj):
    """把对象过一遍 JSON，消除 dict 键序 / tuple 等表示差异。"""
    return json.loads(json.dumps(obj, ensure_ascii=False, sort_keys=True))


class TestPureFunctions(unittest.TestCase):
    """纯函数：固定输入 → 实测输出。"""

    def test_sanitize_filename(self):
        f = _sym("sanitize_filename")
        self.assertEqual(f("A  B:C/D"), "A-BCD")          # 去非法字符 + 空格转连字符
        self.assertEqual(len(f("超长" * 30)), 50)          # 截断到 50

    def test_clean_prompt(self):
        f = _sym("clean_prompt")
        self.assertEqual(
            f("hello  world, aspect ratio 3:4 --ar 3:4"), "hello  world")
        self.assertIsNone(f("短"))                        # 少于 5 字 → None

    def test_check_ip_requirement(self):
        f = _sym("check_ip_requirement")
        self.assertTrue(f("(IP形象: 是)"))
        self.assertTrue(f("IP: Yes"))
        self.assertTrue(f("IP: Required"))
        self.assertFalse(f("(IP形象: 否)"))
        self.assertFalse(f("无标记"))

    def test_calculate_hash_is_stable(self):
        f = _sym("calculate_hash")
        self.assertEqual(f("p", 1, 2, "m", False), "51e534d3")
        self.assertEqual(f("p", 1, 2, "m", True), "fe6b9dd7")
        # use_ip 必须参与哈希，否则开关 IP 会命中缓存
        self.assertNotEqual(f("p", 1, 2, "m", False), f("p", 1, 2, "m", True))

    def test_extract_context(self):
        f = _sym("extract_context")
        self.assertEqual(f('> Context: "abc"'), "abc")
        self.assertEqual(f("> Context: abc"), "abc")
        self.assertIsNone(f("nope"))

    def test_extract_gpt_image2_result_shapes(self):
        f = _sym("_extract_gpt_image2_result")
        self.assertEqual(f({"data": [{"url": "http://x/1.png"}]}),
                         ("url", "http://x/1.png"))
        self.assertEqual(f({"data": [{"url": ["http://x/2.png"]}]}),
                         ("url", "http://x/2.png"))
        self.assertEqual(f({"data": [{"b64_json": "AAA"}]}), ("b64", "AAA"))
        self.assertEqual(f({"data": [{"task_id": "t-1"}]}), ("task", "t-1"))
        self.assertEqual(
            f({"data": [{"result": {"images": [{"url": "http://x/3.png"}]}}]}),
            ("url", "http://x/3.png"))
        self.assertEqual(f({"data": [{"image": "http://x/4.png"}]}),
                         ("url", "http://x/4.png"))
        with self.assertRaises(RuntimeError):
            f({"data": [{"nope": 1}]})

    def test_require_config(self):
        f = _sym("require_config")
        f({"a": 1}, "prov", ["a"])                       # 满足 → 不抛
        with self.assertRaises(RuntimeError):
            f({}, "prov", ["a"])                         # 空配置
        with self.assertRaises(RuntimeError):
            f({"a": 1}, "prov", ["a", "b"])              # 缺 key


class TestParseVisualBrief(unittest.TestCase):
    """解析器：对固定夹具做完整快照比对（拆分最易出错的环节）。"""

    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(
            (FIXTURES / "expected_parse.json").read_text(encoding="utf-8"))

    def _parse(self, case):
        return _sym("parse_visual_brief")(FIXTURES / case / "Storyboard.md")

    def test_fixtures_exist(self):
        for case in ("case_titled", "case_plain"):
            self.assertTrue((FIXTURES / case / "Storyboard.md").is_file(),
                            f"夹具缺失：{case}/Storyboard.md")

    def test_snapshot_matches(self):
        for case, exp in self.expected.items():
            with self.subTest(case=case):
                title, tasks = self._parse(case)
                self.assertEqual(title, exp["title"], f"{case}: title 变了")
                self.assertEqual(_norm(tasks), _norm(exp["tasks"]),
                                 f"{case}: 解析出的任务列表变了")

    def test_titled_case_keys(self):
        """把快照里最关键的结构单拎出来，红了能一眼看出是哪一项。"""
        exp = self.expected["case_titled"]
        self.assertEqual(len(exp["tasks"]), 8)            # 2 封面 + 6 插图
        self.assertEqual([t["type"] for t in exp["tasks"]],
                         ["cover-main", "cover-sidebar"] + ["illustration"] * 6)
        self.assertEqual([t["suffix"] for t in exp["tasks"]][-1],
                         "illustration-06")
        self.assertEqual([t["use_ip"] for t in exp["tasks"]],
                         [True, False, True, False, True, False, True, True])
        self.assertEqual(len([t for t in exp["tasks"] if t.get("context")]), 6)


class TestPipelineLogic(unittest.TestCase):
    """VisualPipeline 的纯逻辑（不碰网络 / 生图）。"""

    def _bare(self):
        cls = _sym("VisualPipeline")
        return cls.__new__(cls)                          # 绕过 __init__ 的可选依赖

    def test_resolve_providers(self):
        """auto 模式的优先级顺序：gpt-image2 先于 gemini。"""
        p = self._bare()
        p.config = {"gpt-image2": {"api_key": "x"}, "gemini": {"api_key": "y"}}
        self.assertEqual(p._resolve_providers("auto"), ["gpt-image2", "gemini"])
        self.assertEqual(p._resolve_providers("gemini"), ["gemini"])
        p.config = {"gemini": {"api_key": "y"}}
        self.assertEqual(p._resolve_providers("auto"), ["gemini"])
        p.config = {}
        self.assertEqual(p._resolve_providers("auto"), [])

    def test_resolve_providers_treats_empty_dict_as_absent(self):
        """⚠️ 真实边界：键存在、但值是空 dict 时，会被当作「未配置」。

        实现用的是 `if self.config.get("gpt-image2")`，而空 dict 是 falsy。
        这是现状行为，拆成模块后必须保持一致（不是 bug，但很容易被改错）。
        """
        p = self._bare()
        p.config = {"gpt-image2": {}, "gemini": {}}
        self.assertEqual(p._resolve_providers("auto"), [])

    def test_manifest_roundtrip(self):
        p = self._bare()
        with tempfile.TemporaryDirectory() as d:
            p.output_dir = Path(d)
            p.manifest_path = Path(d) / "manifest.json"
            self.assertEqual(p._load_manifest(), {})
            p.manifest = {"k": 1}
            p._save_manifest()
            self.assertEqual(p._load_manifest(), {"k": 1})


class TestModuleContract(unittest.TestCase):
    """模块级契约：常量与路径解析。"""

    def test_aspect_ratios(self):
        self.assertEqual(_norm(_sym("ASPECT_RATIOS")), {
            "cover-main": {"width": 1504, "height": 640, "suffix": "cover-main"},
            "cover-sidebar": {"width": 1024, "height": 1024,
                              "suffix": "cover-sidebar"},
            "illustration": {"width": 768, "height": 1024,
                             "suffix": "illustration"},
            "quote": {"width": 768, "height": 1024, "suffix": "quote"},
        })

    def test_director_version(self):
        self.assertEqual(_sym("DIRECTOR_VERSION"), "2.5.0")

    def test_workspace_root_resolves_by_structure_markers(self):
        """2026-10-06 **有意变更**：不再「按脚本位置向上推算仓库根」。

        改为与 `workspace.py` 同一套解析：显式 > 环境变量 > 结构标记。
        技能被安装到托管目录（~/.claude/skills、~/.codex/skills）或运行在
        Windows 上时，按脚本位置推算的深度必然错误；结构标记才是可靠判据。
        这里用显式指定验证「含 articles/ + published/ 的目录被认作工作区根」。
        """
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d) / "workspace"
            (ws / "articles").mkdir(parents=True)
            (ws / "published").mkdir(parents=True)
            root = _sym("get_workspace_root")(explicit=str(ws))
            self.assertIsNotNone(root)
            self.assertEqual(Path(root).resolve(), ws.resolve())


class TestCLI(unittest.TestCase):
    """CLI 契约：拆分后 `python3 visualize.py` 必须照旧可用。"""

    def test_help(self):
        r = subprocess.run([sys.executable, str(VISUALIZE_PATH), "--help"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        for token in ("--brief", "--draft", "--output-dir", "--force",
                      "--upload-only", "--provider", "--gemini-web-login"):
            self.assertIn(token, r.stdout, f"--help 里少了 {token}")
        for choice in ("auto", "gemini-web", "gemini", "gpt-image2"):
            self.assertIn(choice, r.stdout, f"--provider 少了 {choice}")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(VISUALIZE_PATH), *args],
            capture_output=True, text=True, timeout=180)

    def test_missing_brief_exits_with_usage_code(self):
        """缺 --brief → 退出码 2（用法错误，与 argparse 约定一致）。

        ⚠️ 2026-10-05 **有意变更**：原实现是裸 `main()`，所有错误分支退出码
        恒为 0（实测打印了错误提示却仍返回 0），Agent 侧靠退出码判断成败会
        误判为成功。现约定：0 = 全部产出成功；1 = 运行期失败；2 = 用法错误。
        """
        r = self._run()
        self.assertIn("--brief is required", r.stderr)
        self.assertEqual(
            r.returncode, 2,
            "退出码与约定不符 —— 约定见 visualize.py 模块 docstring")

    def test_missing_brief_file_exits_nonzero(self):
        """--brief 给了但文件不存在 → 运行期失败（1）。"""
        r = self._run("--brief", "/nonexistent/Storyboard.md")
        self.assertIn("File not found", r.stderr)
        self.assertEqual(r.returncode, 1)

    def test_unknown_provider_rejected_by_argparse(self):
        """非法 --provider 由 argparse 拦下（2），不会走到生图逻辑。"""
        r = self._run("--provider", "bogus", "--brief", "x")
        self.assertEqual(r.returncode, 2)

    def test_brief_without_tasks_exits_nonzero(self):
        """没有任何插图任务 = 什么都没产出 → 按失败处理（1）。"""
        with tempfile.TemporaryDirectory() as d:
            brief = Path(d) / "Storyboard.md"
            brief.write_text("# 空白分镜\n\n没有插图。\n", encoding="utf-8")
            r = self._run("--brief", str(brief))
        self.assertEqual(r.returncode, 1)
        self.assertIn("No tasks found", r.stderr)

    def test_generation_failure_exits_nonzero(self):
        """端到端证明「有任务没产出 → 非 0」，**不需要任何 stub**。

        手法：用 `--provider gemini-web` 制造一次真实失败 —— 该渠道依赖
        `vendor/baoyu-danger-gemini-web` 与 `bun`，通常不在本机，
        submit_task_gemini_web 会抛 FileNotFoundError。
        若本机确实装齐了，则跳过（那时它会真的尝试生图，不该在单测里跑）。
        """
        vendor = DIRECTOR / "vendor" / "baoyu-danger-gemini-web"
        if vendor.exists() and shutil.which("bun"):
            self.skipTest("本机已装 gemini-web vendor，该用例会真的生图")

        with tempfile.TemporaryDirectory() as d:
            # 用真实夹具的副本，避免污染仓库（output_dir 会落在临时目录）
            brief = Path(d) / "Storyboard.md"
            brief.write_text(
                (FIXTURES / "case_titled" / "Storyboard.md").read_text(
                    encoding="utf-8"),
                encoding="utf-8")
            r = self._run("--brief", str(brief), "--provider", "gemini-web")

        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("failed task", r.stdout)
        self.assertIn("生成失败", r.stdout)


class TestGenerateOrchestration(unittest.TestCase):
    """`generate()` 的编排逻辑 —— 假替身只拦在 **provider 函数** 这一层。

    边界约定（2026-10-05 与 David 确认）
    ------------------------------------
    只替换 `submit_task_gemini` / `submit_task_gpt_image2` /
    `submit_task_gemini_web` 三个函数，**其余全部走真实代码**：
    真实临时目录、真实 manifest 读写、真实文件命名与比例处理。

    因此本类**测不到**：真实 HTTP 细节、COS 上传与 tinify 压缩的分支
    （那两层需要更深的桩，本次明确不做）。

    补这一段的原因：此前 `generate()` 覆盖率是 0，正是这个缺口放过了
    拆分引入的 IP 参考图静默回归。
    """

    TASK_ILL = {
        "type": "illustration", "suffix": "illustration-01",
        "width": 768, "height": 1024,
        "prompt": "a test prompt", "use_ip": False, "context": "ctx-1",
    }
    TASK_COVER = {
        "type": "cover-main", "suffix": "cover-main",
        "width": 1504, "height": 640,
        "prompt": "a test prompt", "use_ip": False, "context": None,
    }

    def _pipeline(self, config, d):
        cls = _sym("VisualPipeline")
        return cls(config, Path(d))

    def test_gemini_success_writes_file_and_records_no_failure(self):
        """gemini 契约：返回 b64 字符串，由调用方解码落盘。"""
        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline({"gemini": {"api_key": "x"}}, d)
            fake = lambda *a, **k: base64.b64encode(b"GEMINI-BYTES").decode()
            with mock.patch.object(visualize, "submit_task_gemini", fake):
                url, path = p.generate(self.TASK_ILL, "T", provider="gemini")
            self.assertIsNone(url)          # 未启用 COS → 无 URL 属正常，不算失败
            self.assertEqual(path.read_bytes(), b"GEMINI-BYTES")
            self.assertEqual(p.failures, {})

    def test_gpt_image2_success_writes_bytes_directly(self):
        """gpt-image2 契约：直接返回 bytes。"""
        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline({"gpt-image2": {"api_key": "x"}}, d)
            fake = lambda *a, **k: b"GPT-BYTES"
            with mock.patch.object(visualize, "submit_task_gpt_image2", fake):
                url, path = p.generate(self.TASK_ILL, "T", provider="gpt-image2")
            self.assertEqual(path.read_bytes(), b"GPT-BYTES")
            self.assertEqual(p.failures, {})

    def test_gemini_web_writes_to_output_path_itself(self):
        """gemini-web 契约**不同**：自己写 output_path、返回 None。

        这条是防"契约被统一"的护栏 —— 若有人把它改成"返回 bytes"，
        这里会红，从而避免出现一个静默不落盘的渠道。
        """
        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline({"gemini_web": {"model": "m"}}, d)

            def fake(api_config, prompt, output_path, use_ip=False):
                Path(output_path).write_bytes(b"WEB-BYTES")
                return None

            with mock.patch.object(visualize, "submit_task_gemini_web", fake):
                url, path = p.generate(self.TASK_ILL, "T", provider="gemini-web")
            self.assertEqual(path.read_bytes(), b"WEB-BYTES")
            self.assertEqual(p.failures, {})

    def test_falls_back_to_second_provider(self):
        """auto 模式下第一个渠道抛错 → 自动回退到第二个，且不记失败。"""
        cfg = {"gpt-image2": {"api_key": "x"}, "gemini": {"api_key": "y"}}
        calls = []

        def boom(*a, **k):
            calls.append("gpt-image2")
            raise RuntimeError("provider down")

        def ok(*a, **k):
            calls.append("gemini")
            return base64.b64encode(b"FALLBACK").decode()

        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline(cfg, d)
            with mock.patch.object(visualize, "submit_task_gpt_image2", boom), \
                 mock.patch.object(visualize, "submit_task_gemini", ok):
                url, path = p.generate(self.TASK_ILL, "T", provider="auto")
            self.assertEqual(calls, ["gpt-image2", "gemini"])
            self.assertEqual(path.read_bytes(), b"FALLBACK")
            self.assertEqual(p.failures, {})

    def test_all_providers_failing_records_failure(self):
        """全部渠道失败 → 记账（这正是 main() 用来决定退出码的依据）。"""
        cfg = {"gpt-image2": {"api_key": "x"}, "gemini": {"api_key": "y"}}

        def boom(*a, **k):
            raise RuntimeError("all down")

        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline(cfg, d)
            with mock.patch.object(visualize, "submit_task_gpt_image2", boom), \
                 mock.patch.object(visualize, "submit_task_gemini", boom):
                url, path = p.generate(self.TASK_ILL, "T", provider="auto")
            self.assertIsNone(url)
            self.assertFalse(path.exists())
            self.assertIn("illustration-01", p.failures)
            self.assertIn("生成失败", p.failures["illustration-01"])

    def test_cover_is_not_failed_merely_for_having_no_url(self):
        """封面从不上传 COS —— 未启用 COS 时不得因「没有 URL」被记为失败。"""
        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline({"gemini": {"api_key": "x"}}, d)
            fake = lambda *a, **k: base64.b64encode(b"COVER").decode()
            with mock.patch.object(visualize, "submit_task_gemini", fake):
                url, path = p.generate(self.TASK_COVER, "T", provider="gemini")
            self.assertIsNone(url)
            self.assertTrue(path.exists())
            self.assertEqual(p.failures, {})

    def test_second_run_hits_local_cache_and_skips_provider(self):
        """同一任务第二次调用应命中本地缓存，不再打 provider。"""
        calls = []

        def ok(*a, **k):
            calls.append(1)
            return base64.b64encode(b"CACHED").decode()

        with tempfile.TemporaryDirectory() as d:
            p = self._pipeline({"gemini": {"api_key": "x"}}, d)
            with mock.patch.object(visualize, "submit_task_gemini", ok):
                p.generate(self.TASK_ILL, "T", provider="gemini")
                p.generate(self.TASK_ILL, "T", provider="gemini")
        self.assertEqual(len(calls), 1, "第二次应命中缓存，provider 不该被再次调用")


class TestIPAssetsPath(unittest.TestCase):
    """IP 参考图路径 —— 钉住 2026-10-05 拆分引入的静默回归。

    背景：拆分前脚本住在 scripts/ 下，`Path(__file__).parent.parent / "assets"`
    正好指向 `wechat-director/assets/`。搬进 `scripts/providers/` 后 __file__
    多了一层，同一个表达式变成 `scripts/assets/`（不存在）——于是 use_ip=True
    时只打一条 warning、**静默不注入**参考图，连报错都没有。

    旧护栏 18 个断言全绿却漏掉了它，因为没有一条覆盖 provider 分支。
    """

    def test_assets_dir_resolves_to_existing_reference(self):
        from director_core import ASSETS_DIR
        ref = ASSETS_DIR / "IP_Reference.png"
        self.assertTrue(
            ref.exists(),
            f"IP 参考图不存在：{ref} —— ASSETS_DIR 的 __file__ 深度可能又算错了")
        self.assertGreater(
            ref.stat().st_size, 0, f"IP 参考图是空文件：{ref}")

    def test_providers_do_not_recompute_assets_from_dunder_file(self):
        """providers/ 下不得自行用 __file__ 推算 assets —— 必须用 ASSETS_DIR。"""
        offenders = []
        for p in sorted((DIRECTOR / "scripts" / "providers").glob("*.py")):
            for i, line in enumerate(
                    p.read_text(encoding="utf-8").splitlines(), 1):
                if "__file__" in line and "assets" in line:
                    offenders.append(f"{p.name}:{i}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "providers/ 里又出现了自行推算 assets 路径的代码，"
            "应从 director_core 导入 ASSETS_DIR：\n  " + "\n  ".join(offenders))

    def test_all_injection_sites_share_one_constant(self):
        """三处 IP 注入点必须共用同一个常量，否则深度最容易各自算错。"""
        scripts = DIRECTOR / "scripts"
        files = sorted((scripts / "providers").glob("*.py")) + [
            scripts / "visualize.py"]
        total = 0
        for p in files:
            text = p.read_text(encoding="utf-8")
            total += text.count('ASSETS_DIR / "IP_Reference.png"')
            if "IP_Reference.png" in text:
                self.assertIn(
                    "ASSETS_DIR", text,
                    f"{p.name} 引用了 IP_Reference.png 却没走 ASSETS_DIR")
        self.assertEqual(
            total, 3, f"预期 3 处注入点统一走 ASSETS_DIR，实际 {total} 处")


if __name__ == "__main__":
    unittest.main(verbosity=2)
