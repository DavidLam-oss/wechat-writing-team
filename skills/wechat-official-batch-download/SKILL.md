---
name: wechat-official-batch-download
description: Use this skill when the user wants to batch download, archive, verify, or build a corpus from WeChat Official Account articles, or needs to fetch articles as writing references. Especially when using mp.weixin.qq.com links, down.mptext.top/dashboard, wechat-article-exporter, exported Excel/JSON link pools, or a local downloader/MCP. It teaches the agent to acquire official article URLs first, preserve raw HTML/Markdown/images/metadata, verify counts and fidelity, and avoid storing cookies, auth keys, or login secrets.
version: 1.2.1
---

# WeChat Official Batch Download

Use this skill for WeChat Official Account article batch download, corpus building, and download verification.

The default goal is not just "download some pages". The goal is a traceable corpus:

```text
real mp.weixin.qq.com/s/... links
-> raw HTML + preserved Markdown + images + metadata
-> count/fidelity verification
-> valid article inventory + report
```

## When To Use

- User asks to batch download WeChat Official Account articles.
- User provides many `mp.weixin.qq.com/s/...` links or a link-pool file.
- User wants all/latest articles from one account.
- User mentions `down.mptext.top`, `wechat-article-exporter`, dashboard export, Excel/JSON address list, or WeChat corpus.
- User asks whether a downloaded corpus is complete, official, readable, or faithful.

## Route First

Classify the request. **Default is `reference`** — you do NOT need to say which mode unless you want corpus mode.

- `reference` (default): one or more article URLs downloaded as writing references. Lightweight, no local images, no corpus. Files go to project `_source/`.
- `single`: one user-provided article URL, downloaded as corpus (with images, HTML, metadata).
- `recent`: latest N articles, default 10 if no count is provided.
- `all`: all backend/export-visible articles for a target account.
- `link-pool`: user already has Excel/JSON/TXT links.
- `verify`: check an existing corpus.
- `fallback`: official link pool unavailable or site downloader failed.

The agent classifies like this:
- User says "下载这篇文章" / "帮我拉一下" / "参考一下" / "放到 source 里" → **reference** (default)
- User says "做个语料库" / "全部下载" / "要验收" / "包括图片" → **corpus mode** (single / all / link-pool)

## Non-Negotiable Rules

1. Official corpus work starts with real `https://mp.weixin.qq.com/s/...` URLs.
2. Do not claim "all articles" without a counted official URL pool or a user-verified export.
3. Treat `down.mptext.top/dashboard/` and `wechat-article-exporter` primarily as link-pool/export tools, not guaranteed final body downloaders.
4. If a website's body download fails, keep the exported links and switch to local download.
5. Never store or print cookies, `auth-key`, `X-Auth-Key`, API keys, tokens, browser storage, or login secrets.
6. Do not treat mirrors/search snippets as official source material unless clearly labeled as fallback.
7. Do not claim exact text fidelity unless raw visible article text and preserved Markdown were compared after whitespace normalization.

## Preferred Workflow

1. Establish the official URL pool.
   - Best: fixed/logged-in WeChat backend or user-exported official address list.
   - Good fallback: `down.mptext.top/dashboard/` or private `wechat-article-exporter` export.
   - Acceptable input: user-provided Excel/JSON/TXT containing real article URLs.

2. Normalize the link pool.
   - Keep only real `mp.weixin.qq.com/s/...` article links.
   - Deduplicate.
   - Save `links.json` with count, source route, and timestamp.

3. Download articles.
   - Use the local downloader available in the user's environment.
   - If an MCP downloader is available, call `initialize`, `tools/list`, and smoke-test 3 links before batch work.
   - If using scripts, preserve raw HTML first, then derive Markdown and metadata from the raw source.

4. Produce mandatory artifacts for every successful article.
   - `html_raw/*.html`
   - `articles_preserved/*.md`
   - `images/<article>/...`
   - `meta/*.json`

5. Verify the corpus.
   - URL count vs attempted count.
   - raw HTML count.
   - preserved Markdown count.
   - valid body count.
   - image count and missing-image count.
   - fidelity warnings.
   - failed URLs and retry/fallback notes.

6. Report clearly.
   - Give output directory and counts.
   - Separate official source, fallback source, failures, and warnings.
   - Do not paste full article text into chat.

## Reference Route (写作参考模式)

Use this route when the user needs articles **as writing references**, not as a permanent corpus.

### Output rules

- Each article becomes one standalone Markdown file.
- **Images keep original WeChat CDN links** — do not download to local.
- No HTML/JSON/metadata artifacts.
- No acceptance report.

### Project directory

If no project directory exists yet, the agent creates it:

```text
To-be-used/Project_[Title]/
└── _source/
    ├── Refer_[ArticleTitle1].md
    ├── Refer_[ArticleTitle2].md
    └── ...
```

- Project title: derived from article topic or user-provided intent.
- If a project already exists, reuse it and add files under its `_source/`.
- Filename: `Refer_` + article title (sanitized).
- One `.md` per article, never merged into one file.
- Frontmatter includes source URL and fetch date.

### Image handling

```markdown
<!-- Keep original WeChat image links, do not download -->
![](https://mmbiz.qpic.cn/...)
```

No local image download, no image folder, no cleanup needed after reference use.

### Lifecycle

1. User provides one or more article URLs.
2. Agent fetches each article, converts to Markdown.
3. Each `.md` saved to `_source/Refer_[Title].md`.
4. When the project is archived, reference files archive with it.
5. No separate cleanup needed.

## Tool Adaptation

This skill does not assume one fixed workstation. Use the best available local equivalent:

- **Local Python Scripts**:
  - `scripts/downloader.py`: Multi-threaded downloader. Uses a **direct connection by default** with a high-fidelity Chrome UA to bypass the hotlinking block; the CF Worker proxy pool is opt-in via `--proxy`. With no proxy available (pool file missing or empty) it also falls back to a direct request, and if every proxy attempt fails it retries once directly instead of aborting the batch. Supports request throttling (`--delay`) and authentication (`--cookie`).
  - `scripts/exporters/md_exporter.py`: Exporter converting raw HTML to preserved Markdown.
  - `scripts/exporters/html_exporter.py`: Exporter normalizing HTML into clean, offline-friendly single files via `no-referrer` metadata injection and protocol-relative stylesheet link corrections (`https:` prefixing).
- local Python/Node downloader
- existing WeChat article export script
- MCP downloader with tools such as `single_article_download` or `batch_download_articles`
- browser-assisted capture for single article troubleshooting

If no downloader exists, create a small local script only after the link pool is known and after checking legal/compliance boundaries.

## Read References As Needed

- For operational detail, read `references/batch-download-sop.md`.
- For the website/tool comparison, read `references/tool-comparison.md`.
- For a portable handoff summary to show a human, read `references/portable-usage.md`.

## Changelog

- **v1.2.1 (2026-10-07)**: Fixed the `--proxy` toggle, which was a no-op: `Downloader.__init__` rebuilt a `ProxyManager` whenever it was passed `None`, so the pool was loaded even without the flag and the documented "direct by default" behaviour never took effect. Now `None` really means direct, and when the pool is used but every attempt fails the downloader retries once directly instead of aborting the batch.
- **v1.2.0 (2026-06-27)**: Disabled CF Worker proxy pool by default. Reconfigured downloader to prioritize direct HTTPS requests using browser User-Agent. Added `--proxy` toggle, `--delay` throttling, and `--cookie` authorization parameters.
- **v1.1.0 (2026-06-27)**: Added local Python proxy pool downloader and Markdown/HTML exporters. Kept images and stylesheets on WeChat CDN and injected `no-referrer` meta to bypass hotlinking block, ensuring clean single-file structures.
- **v1.0.0**: Initial release of the batch download skill specification.

