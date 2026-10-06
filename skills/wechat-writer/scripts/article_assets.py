"""Resolve article file references and plan portable copies; no image-quality rules."""

import hashlib
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

DESTINATION = r'(?:<([^>\n]+)>|((?:\\.|[^()\s]|\([^()\n]*\))+))'
INLINE_IMAGE = re.compile(r'!\[[^\]\n]*\]\(\s*' + DESTINATION + r'(?:\s+(?:"[^"\n]*"|\'[^\'\n]*\'|\([^\n)]*\)))?\s*\)')
DEFINITION = re.compile(r'^\s*\[([^\]\n]+)\]:\s*' + DESTINATION, re.MULTILINE)


def is_remote(reference):
    return reference.startswith("//") or urlsplit(reference).scheme.lower() in {"http", "https", "data"}


def image_links(content):
    """Yield destination spans for inline, reference, Obsidian and HTML images."""
    # Code samples are article text, not files that the article must deliver.
    masked = []
    fence = None
    for line in content.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)', line)
        hidden = fence is not None or marker is not None
        if marker:
            run, tail = marker.groups()
            if fence is None:
                fence = (run[0], len(run))
            elif run[0] == fence[0] and len(run) >= fence[1] and not tail.strip():
                fence = None
        masked.append(re.sub(r'[^\r\n]', ' ', line) if hidden else line)
    content = ''.join(masked)
    content = re.sub(r'<!--.*?-->', lambda m: re.sub(r'[^\r\n]', ' ', m[0]), content, flags=re.DOTALL)
    content = re.sub(r'(`+)(?!`)(.*?)(?<!`)\1(?!`)', lambda m: re.sub(r'[^\r\n]', ' ', m[0]), content, flags=re.DOTALL)
    links = []
    for match in INLINE_IMAGE.finditer(content):
        group = 1 if match.group(1) is not None else 2
        links.append((*match.span(group), match.group(group)))
    labels = set()
    for match in re.finditer(r'!\[([^\]\n]+)\](?:\[([^\]\n]*)\])?(?!\()', content):
        label = match.group(2) or match.group(1)
        labels.add(" ".join(label.casefold().split()))
    for match in DEFINITION.finditer(content):
        if " ".join(match.group(1).casefold().split()) in labels:
            group = 2 if match.group(2) is not None else 3
            links.append((*match.span(group), match.group(group)))
    for match in re.finditer(r'!\[\[([^\]|\n]+)(?:\|[^\]\n]*)?\]\]', content):
        links.append((*match.span(1), match.group(1)))
    for match in re.finditer(r'<img\b[^>]*\bsrc\s*=\s*(["\'])(.*?)\1', content, re.IGNORECASE):
        links.append((*match.span(2), match.group(2)))
    return sorted(set(links))


def plan_asset(reference, project, allow_legacy_cover=False):
    """Return (source, destination) or None for remote URLs; reject missing/local escapes."""
    reference = reference.strip().strip("<>")
    if is_remote(reference):
        return None
    # Markdown escapes differ from Windows separator backslashes.
    reference = re.sub(r'\\([() ])', r'\1', reference).replace("\\", "/")
    parsed = urlsplit(reference)
    if parsed.scheme or reference.startswith("/"):
        raise ValueError("Local article images must use relative paths")
    relative = unquote(parsed.path)
    project = Path(project).resolve()
    source = (project / relative).resolve()
    if not source.is_relative_to(project):
        raise ValueError("Local article image is outside the current project")
    if not source.is_file() and allow_legacy_cover:
        folder = project / "zpicture.assets"
        candidates = [path for path in folder.glob(f"*_{Path(relative).name}") if path.is_file()]
        if len(candidates) == 1:
            source = candidates[0].resolve()
    if not source.is_file() or not source.is_relative_to(project):
        raise FileNotFoundError(f"Article image does not exist: {reference}")
    source_relative = source.relative_to(project)
    if source_relative.parts[0] == "zpicture.assets":
        destination = source_relative.as_posix()
    else:
        identity = f"{project.name}/{source_relative.as_posix()}"
        tag = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        destination = f"zpicture.assets/import_{tag}_{source.name}"
    return source, destination


def prepare_markdown(content, project):
    plans = {}
    replacements = []
    for start, end, reference in image_links(content):
        plan = plan_asset(reference, project)
        if plan is None:
            continue
        source, destination = plan
        plans[destination] = source
        replacements.append((start, end, quote(destination, safe="/-._~")))
    for start, end, destination in reversed(replacements):
        content = content[:start] + destination + content[end:]
    return content, plans


def verify_published(content, published, cover=""):
    for _, _, reference in image_links(content):
        plan_asset(reference, published)
    if cover:
        plan_asset(cover, published)
