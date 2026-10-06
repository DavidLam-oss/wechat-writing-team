# Batch Download SOP

## Purpose

Build reusable WeChat Official Account corpora from real article links with preserved outputs and verification.

Verified chain:

```text
real mp.weixin.qq.com links
-> raw HTML + preserved Markdown + images
-> fidelity check
-> valid Markdown inventory
-> statistics/report
```

## Trigger

Use this SOP when the user asks for:

- batch download of WeChat Official Account articles
- corpus creation from a navigation page or link pool
- all/latest articles for a target account
- verification of an existing corpus
- use of exported Excel/JSON/article address lists

## Route Vocabulary

- `single`: one user-provided article URL
- `recent`: latest 10 articles by default, or another count if given
- `all`: all account articles visible through the available backend/export source
- `link-pool`: user-provided Excel/JSON/TXT links
- `verify`: check existing output

## Official URL Pool Requirement

An official corpus requires a complete pool of real WeChat article URLs:

```text
https://mp.weixin.qq.com/s/...
```

Source priority:

1. logged-in/fixed browser backend or official backend list
2. `down.mptext.top/dashboard/` or private `wechat-article-exporter` export
3. user-provided JSON/Excel/address list
4. mirror or search sources only as labeled fallback

Do not claim official completeness without a counted official URL pool or a user-verified export.

## down.mptext.top Placement

Treat `down.mptext.top/dashboard/` and `wechat-article-exporter` as preferred official URL-pool acquisition tools.

Correct role:

```text
dashboard or private exporter
-> search/sync Official Account
-> export Excel/JSON/address list
-> extract real mp.weixin.qq.com/s/... links
-> local download and verification
```

Rules:

1. If the user can log in to the dashboard, prefer an exported Excel/JSON/address list when no full URL pool exists.
2. If the site's own batch body download fails, do not loop on the public site.
3. Keep the exported URL list and switch to local download.
4. Do not write `X-Auth-Key`, cookies, `auth-key`, dashboard secrets, or captured credentials into files or chat.

## Mandatory Outputs

Every successful article should produce:

- raw source HTML: `html_raw/*.html`
- preserved Markdown: `articles_preserved/*.md`
- local images: `images/<article>/...`
- article metadata: `meta/*.json`

Workflow-level files:

- `links.json`
- `download-report.json`
- `fidelity-check.json`
- `valid-md.json`
- `download-acceptance.md`

Optional transformed outputs may include readable Markdown, classified Markdown, merged Markdown, PDF, Word, or PPT exports. These must not replace preserved Markdown.

## Fidelity Rule

Default fidelity means:

- HTML preserves the raw fetched source.
- Markdown preserves visible article body text.
- Image references are local and kept in reading order when available.

Validation:

1. Extract visible text from raw HTML.
2. Extract visible text from preserved Markdown.
3. Normalize whitespace.
4. Require exact equality for `fidelity_status: ok`.
5. If not exact, mark `fidelity_warning`.

## MCP Preflight

If an MCP downloader is available:

1. Call `initialize`.
2. Call `tools/list`.
3. Confirm downloader tools exist.
4. Read the link file and verify count.
5. Smoke test 3 links before batch work.
6. Only then run the full batch.

## Final Report

The final answer should include:

- route
- output directory
- link count
- success/failure count
- raw HTML count
- preserved Markdown count
- valid body count
- image missing count
- fidelity warning count
- final report path

