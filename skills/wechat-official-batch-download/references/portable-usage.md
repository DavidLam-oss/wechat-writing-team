# Portable Usage Guide

This guide explains how an agent should use the `wechat-official-batch-download` skill on any workstation.

## What This Skill Does

It helps an agent build a reusable corpus from WeChat Official Account articles by separating four layers:

1. Official URL pool acquisition
2. Body download and artifact preservation
3. Fidelity/count verification
4. Analysis or reporting

The most important habit is to get real article URLs first:

```text
https://mp.weixin.qq.com/s/...
```

## Human Setup

If the agent cannot find all article links directly, ask the human to use one of these routes:

- log in to `https://down.mptext.top/dashboard/`
- search or sync the target Official Account
- export Excel/JSON/address list
- provide that exported file to the agent

The agent must not ask the human to paste cookies, auth keys, browser storage, or login secrets.

## Agent Setup

The agent should check what download tools are available locally:

- an existing Python/Node WeChat downloader
- an MCP server with article download tools
- a browser automation lane for single-page capture
- simple HTTP fetch for public pages where allowed

If the local environment has no downloader, start with a small proof-of-concept on 3 URLs before running a batch.

## Optional: Dedicated Proxies

The bundled `scripts/downloader.py` uses a direct HTTPS connection by default and only touches the proxy pool when `--proxy` is passed. The pool lives in `scripts/proxy_pool.txt` (shared/public workers only).

To prioritise your own dedicated proxies, add them to `proxy_pool.txt` and declare their hostnames so the manager prefers them:

```bash
export DWT_PRIVATE_PROXY_HOSTS="proxy-a.example.com,proxy-b.example.com"
```

Hosts listed here are substring-matched and tried before the shared pool.

## Expected Output Layout

Use this shape unless the user specifies another output root:

```text
wechat-corpus/
  links.json
  html_raw/
  articles_preserved/
  images/
  meta/
  download-report.json
  fidelity-check.json
  valid-md.json
  download-acceptance.md
```

## Acceptance Checklist

Report these fields:

- source route
- official URL count
- attempted count
- success count
- raw HTML count
- preserved Markdown count
- valid body count
- image count
- missing image count
- failed URLs
- fidelity warning count
- output directory

## Failure Handling

If a dashboard or website can export links but fails to download bodies, keep the links and switch to local download.

If an article is blocked or unavailable, mark it failed with the visible reason. Do not silently replace it with mirror content.

