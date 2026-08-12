"""Text-content commands: pulling clean paragraphs out of any source, and ranking/comparing
those paragraphs by embedding. Grouped under one `kb text` parent since they're two halves of
the same pipeline (`kb text extract SOURCE | kb text semsearch rank QUERY`) and are reached for
together often enough that a shared parent is worth the one extra word. Both are DB-free (no
`args.session` use, same shape as pager.py) so this stays usable from any harness and could be
extracted to its own package later without carrying kb-specific dependencies along with it.

    kb text extract SOURCE                # print paragraphs to stdout, one per line
    kb text extract SOURCE --cache        # also write to ~/.cache/kb-webscan/<sha256(source)>.txt
    kb text extract SOURCE --show N       # print paragraph N verbatim from the cache (no re-fetch)
    kb text extract -                     # read plain text from stdin, split into paragraphs

    kb text semsearch rank QUERY [FILE]   # rank stdin/FILE's lines by relevance to QUERY
    kb text semsearch compare A B         # cosine similarity between two texts/files/- (stdin)

    kb text extract https://example.com/article | kb text semsearch rank "query"

SOURCE may be an http(s):// URL, a local file path (.pdf/.html/.htm/.txt or extensionless --
sniffed by content), or - for stdin."""

import argparse
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "kb-webscan"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


# -- extract --------------------------------------------------------------


def _cache_path(source: str) -> Path:
    digest = hashlib.sha256(source.encode()).hexdigest()
    return CACHE_DIR / f"{digest}.txt"


def _fetch_url_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data: bytes = resp.read()
        return data


def _clean_block_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs_from_dom(content_html: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content_html, "lxml")
    # Block-level elements are the real paragraph boundaries -- walking the parsed DOM
    # (not regex-splitting the markup) is what actually lines up with how the HTML is
    # structured, including nested tags a regex split silently ignores.
    block_tags = ("p", "div", "li", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6")
    paragraphs = []
    for el in soup.find_all(block_tags):
        if el.find(block_tags):
            continue  # skip containers whose own text is already captured by their children
        text = _clean_block_text(el.get_text(" "))
        if len(text) > 20:
            paragraphs.append(text)
    return paragraphs


def _paragraphs_from_html(html: str) -> list[str]:
    from bs4 import BeautifulSoup

    # MediaWiki's own content container is a more reliable main-content boundary than
    # readability's generic heuristic, which on a thin wiki page (little prose, one code
    # block) can pick the wrong element entirely -- prefer the known-CMS selector when present.
    soup = BeautifulSoup(html, "lxml")
    mw_content = soup.find(id="mw-content-text")
    if mw_content is not None:
        return _paragraphs_from_dom(str(mw_content))

    from readability import Document

    doc = Document(html)
    return _paragraphs_from_dom(doc.summary())


def _paragraphs_from_pdf(data: bytes) -> list[str]:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    paragraphs = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for block in re.split(r"\n\s*\n", text):
            cleaned = _clean_block_text(block)
            if len(cleaned) > 20:
                paragraphs.append(cleaned)
    return paragraphs


def _paragraphs_from_plain_text(text: str) -> list[str]:
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        cleaned = _clean_block_text(block)
        if len(cleaned) > 20:
            paragraphs.append(cleaned)
    return paragraphs


def _sniff_kind(data: bytes) -> str:
    if data[:5] == b"%PDF-":
        return "pdf"
    lowered = data[:2048].lstrip().lower()
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html") or b"<body" in lowered:
        return "html"
    return "text"


def _load_source(source: str) -> bytes:
    if source == "-":
        return sys.stdin.buffer.read()
    if source.startswith("http://") or source.startswith("https://"):
        return _fetch_url_bytes(source)
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"not found: {source}")
    return path.read_bytes()


def extract_paragraphs(source: str) -> list[str]:
    """The one entry point for turning any supported source into stable, ordered paragraphs --
    same function `kb text extract` and any future in-process caller (e.g. kb_cli/archivebox.py's
    `kb ab fetch`) both call, so there is exactly one place that owns source-kind detection."""
    data = _load_source(source)
    if source.endswith(".pdf"):
        kind = "pdf"
    elif source.endswith((".html", ".htm")):
        kind = "html"
    elif source.endswith(".txt") or source == "-":
        kind = "text"
    else:
        kind = _sniff_kind(data)

    if kind == "pdf":
        return _paragraphs_from_pdf(data)
    if kind == "html":
        return _paragraphs_from_html(data.decode("utf-8", errors="replace"))
    return _paragraphs_from_plain_text(data.decode("utf-8", errors="replace"))


def cmd_extract(args: argparse.Namespace) -> None:
    if args.show is not None:
        path = _cache_path(args.source)
        if not path.exists():
            print(f"not cached -- run `kb text extract {args.source} --cache` first", file=sys.stderr)
            sys.exit(1)
        paragraphs = path.read_text().splitlines()
        if args.show < 0 or args.show >= len(paragraphs):
            print(f"paragraph {args.show} out of range (0..{len(paragraphs) - 1})", file=sys.stderr)
            sys.exit(1)
        print(paragraphs[args.show])
        return

    try:
        paragraphs = extract_paragraphs(args.source)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if args.cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(args.source).write_text("\n".join(paragraphs))
        print(f"cached: {_cache_path(args.source)} ({len(paragraphs)} paragraphs)", file=sys.stderr)

    try:
        for para in paragraphs:
            print(para)
    except BrokenPipeError:
        sys.stderr.close()


# -- semsearch --------------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def _read_lines(source: str) -> list[str]:
    if source == "-":
        text = sys.stdin.read()
    else:
        text = Path(source).read_text()
    return [line for line in text.splitlines() if line.strip()]


def _read_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text()


def cmd_semsearch_rank(args: argparse.Namespace) -> None:
    from embed import embed

    lines = _read_lines(args.file)
    query_vec = embed(args.query)
    scored = [(1 - _cosine(query_vec, embed(line)), i, line) for i, line in enumerate(lines)]
    scored.sort(key=lambda x: x[0])
    for dist, i, line in scored[: args.top]:
        snippet = line[:150] + ("..." if len(line) > 150 else "")
        print(f"[{i}] (dist={dist:.3f}) {snippet}")


def cmd_semsearch_compare(args: argparse.Namespace) -> None:
    from embed import embed

    text_a = _read_text(args.a)
    text_b = _read_text(args.b)
    similarity = _cosine(embed(text_a), embed(text_b))
    print(f"{similarity:.4f}")


# -- wiring --------------------------------------------------------------


def add_subparser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("text", help="Extract clean paragraphs from any source, rank/compare by embedding")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="Pull clean text paragraphs from a URL, PDF, HTML file, or plain text")
    p_extract.add_argument("source", help="URL, file path, or - for stdin")
    p_extract.add_argument("--cache", action="store_true", help="Write paragraphs to the source's cache file")
    p_extract.add_argument("--show", type=int, metavar="N", help="Print cached paragraph N verbatim, no re-fetch")
    p_extract.set_defaults(func=cmd_extract)

    p_semsearch = sub.add_parser("semsearch", help="Rank or compare paragraphs by embedding")
    semsearch_sub = p_semsearch.add_subparsers(dest="semsearch_cmd", required=True)

    p_rank = semsearch_sub.add_parser("rank", help="Rank stdin/FILE lines by relevance to a query")
    p_rank.add_argument("query", help="Text to rank paragraphs against")
    p_rank.add_argument("file", nargs="?", default="-", help="File to read paragraphs from (default: stdin)")
    p_rank.add_argument("--top", type=int, default=5, help="Number of top-ranked paragraphs to print (default: 5)")
    p_rank.set_defaults(func=cmd_semsearch_rank)

    p_compare = semsearch_sub.add_parser("compare", help="Cosine similarity between two texts")
    p_compare.add_argument("a", help="File path or - for stdin")
    p_compare.add_argument("b", help="File path or - for stdin")
    p_compare.set_defaults(func=cmd_semsearch_compare)
