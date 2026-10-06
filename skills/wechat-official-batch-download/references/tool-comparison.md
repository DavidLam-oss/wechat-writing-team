# Tool Comparison

## Summary

`wechat-article-exporter` and its public site `down.mptext.top` are valuable, but their best place in the workflow is the first layer: finding accounts, syncing article lists, and exporting official article URLs.

They should not be treated as a guaranteed final body downloader.

## Public References

- Project: `https://github.com/wechat-article/wechat-article-exporter`
- Tool site: `https://down.mptext.top/`
- Dashboard: `https://down.mptext.top/dashboard/`
- Docs: `https://docs.mptext.top/`

## Layered Workflow

```text
link pool:
  down.mptext.top / wechat-article-exporter / backend export / user file

body download:
  local script / MCP downloader / browser-assisted single-page capture

acceptance:
  raw HTML / preserved Markdown / images / metadata / fidelity check

analysis:
  topic mining / account study / writing patterns / report
```

## Comparison Table

| Dimension | down.mptext.top / exporter | MCP or local downloader | Browser single-page reader | Mirror sources |
| --- | --- | --- | --- | --- |
| Best role | Account search, list sync, link export | Batch body download | Single-article troubleshooting | Missing/deleted fallback |
| Input | Account name, URL, dashboard data | Real article URLs | One article URL or open tab | Mirror/index URL |
| Needs login | Usually yes for dashboard | Usually no, once links are known | Maybe, depending on page | Usually no |
| Link-pool ability | Strong | Weak | Weak | Partial |
| Body fidelity control | Variable | Strong if locally verified | Strong for single page | Variable |
| Best use | Get full historical link list | Build standard corpus | Debug one article | Supplement only |

## Recommended Decisions

- To get all historical links: prefer `down.mptext.top/dashboard/` or private `wechat-article-exporter`.
- If dashboard body fetch fails: export Excel/JSON and use a local downloader.
- For one blocked article: use a browser-assisted reader before mirror fallback.
- For official corpus claims: use only real `mp.weixin.qq.com/s/...` links.

## Security Boundary

Do not store or share:

- cookies
- auth keys
- `X-Auth-Key`
- API keys
- tokens
- browser storage
- dashboard session data

