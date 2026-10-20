#!/usr/bin/env python3
"""
Build _data/publications.yml for the CRUMBS website.

Sources, in order of trust:
  1. The CV .bib files in _pubsrc/cv/ (copied there by `make publish`)
  2. DBLP (adds papers missing from the CV, plus DOI/arXiv links)
  3. _data/paper_links.yml (hand-written: code links, PDF fixes, tag changes, hiding)

Run locally from the repo root:  python _scripts/build_publications.py
"""
import difflib
import glob
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import bibtexparser
import yaml
from pylatexenc.latex2text import LatexNodes2Text

# ------------------------------------------------------------------ settings
DBLP_PID = "186/9675"
CV_BIB_DIR = "_pubsrc/cv"
OVERRIDES = "_data/paper_links.yml"
MEMBERS_DIR = "_members"
OUTPUT = "_data/publications.yml"
ALWAYS_BOLD = ["Francesco Leofante"]

# Which CV file gets which tag. Set a tag to None to keep that file off the website.
CV_FILES = {
    "biblio_books.bib": "Book",
    "biblio_journals.bib": "Journal",
    "biblio_conferences.bib": "Conference",
    "biblio_ws.bib": "Workshop",
    "biblio_thesis.bib": "Thesis",
}

# If a paper appears several times (e.g. arXiv + conference), the lowest rank is shown.
RANK = {"Book": 0, "Journal": 1, "Conference": 2, "Book chapter": 3,
        "Workshop": 3, "Thesis": 4, "Pre-print": 5}

SIMILARITY = 0.92  # how similar two titles must be to count as the same paper

# ------------------------------------------------------------------- helpers
_L2T = LatexNodes2Text()


def clean(s):
    """LaTeX -> plain text with single spaces."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", _L2T.latex_to_text(s)).strip()


def ascii_fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", ascii_fold(t).lower())


def slug(t):
    s = re.sub(r"[^a-z0-9]+", "-", ascii_fold(t).lower()).strip("-")
    return s[:80].rstrip("-")


def name_key(name):
    """'Francesco Leofante' and 'F. Leofante' both become 'f leofante'."""
    parts = re.sub(r"[^a-z ]", " ", ascii_fold(name).lower()).split()
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else f"{parts[0][0]} {parts[-1]}"


def year_int(y):
    m = re.search(r"\d{4}", str(y))
    return int(m.group()) if m else 0


def same_paper(a, b):
    return difflib.SequenceMatcher(None, norm_title(a), norm_title(b)).ratio() >= SIMILARITY


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={
        "User-Agent": "CRUMBS-website-bot/1.0 (+https://the-crumbs-lab.github.io)",
        "Accept": "application/xml, text/xml, */*",
    })
    return urllib.request.urlopen(req, timeout=timeout)


# ------------------------------------------------------------------- sources
def read_cv():
    entries = []
    for fname, tag in CV_FILES.items():
        path = os.path.join(CV_BIB_DIR, fname)
        if tag is None or not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            db = bibtexparser.load(f)
        for e in db.entries:
            authors = [clean(a) for a in re.split(r"\s+and\s+", e.get("author", "")) if a.strip()]
            et_al = bool(authors) and authors[-1].lower() == "others"
            if et_al:
                authors = authors[:-1]
            venue = e.get("journal") or e.get("booktitle") or e.get("school") or e.get("publisher") or ""
            doi = e.get("doi")
            entries.append({
                "source": "cv", "tag": tag,
                "title": clean(e.get("title", "")).rstrip("."),
                "authors": authors, "et_al": et_al,
                "venue": clean(venue), "year": clean(e.get("year", "")),
                "pdf": e.get("pdf"), "code": e.get("code"),
                "url": e.get("url") or (f"https://doi.org/{doi}" if doi else None),
                "doi": doi, "arxiv": None,
            })
    return entries


DBLP_TAGS = {"article": "Journal", "inproceedings": "Conference", "book": "Book",
             "incollection": "Book chapter", "phdthesis": "Thesis"}
ARXIV_RE = re.compile(r"arxiv(?:\.org/abs/|\.)(\d{4}\.\d{4,5})", re.I)


DBLP_MIRRORS = ["https://dblp.org", "https://dblp.uni-trier.de", "https://dblp.dagstuhl.de"]


def parse_dblp(body):
    root = ET.fromstring(body)
    entries = []
    for rec in root.findall("r"):
        e = rec[0]
        informal = "informal" in (e.get("publtype") or "") or e.findtext("journal") == "CoRR"
        tag = "Pre-print" if informal else DBLP_TAGS.get(e.tag)
        if tag is None:
            continue  # e.g. edited proceedings
        ees = ["".join(x.itertext()).strip() for x in e.findall("ee")]
        arxiv_ids = [m.group(1) for u in ees for m in [ARXIV_RE.search(u)] if m]
        arxiv = f"https://arxiv.org/abs/{arxiv_ids[0]}" if arxiv_ids else None
        doi = next((u.split("doi.org/", 1)[1] for u in ees
                    if "doi.org/" in u and "arxiv" not in u.lower()), None)
        title_el = e.find("title")
        title = "".join(title_el.itertext()).strip().rstrip(".") if title_el is not None else ""
        venue = "arXiv" if informal else (e.findtext("journal") or e.findtext("booktitle")
                                          or e.findtext("publisher") or e.findtext("school") or "")
        entries.append({
            "source": "dblp", "tag": tag, "title": title,
            "authors": [re.sub(r"\s+\d{4}$", "", "".join(a.itertext()).strip())
                        for a in e.findall("author")],
            "et_al": False, "venue": venue, "year": e.findtext("year", ""),
            "pdf": None, "code": None,
            "url": f"https://doi.org/{doi}" if doi else (arxiv or (ees[0] if ees else None)),
            "doi": doi, "arxiv": arxiv,
        })
    return entries


def read_dblp():
    """Try each DBLP mirror a few times; raise with details if all fail."""
    errors = []
    for base in DBLP_MIRRORS:
        url = f"{base}/pid/{DBLP_PID}.xml"
        for attempt in range(1, 4):
            try:
                with fetch(url) as r:
                    status, body = r.status, r.read()
                if b"<dblpperson" not in body[:3000]:
                    raise ValueError(f"HTTP {status}, response starts with {body[:80]!r}")
                return parse_dblp(body)
            except Exception as err:
                errors.append(f"{url} (attempt {attempt}): {err}")
                time.sleep(5 * attempt)
    raise RuntimeError(" | ".join(errors[-3:]))


def s2_pdf(doi, title):
    """Ask Semantic Scholar for a free PDF. Returns a URL or None."""
    base = "https://api.semanticscholar.org/graph/v1/paper/"
    fields = "fields=title,openAccessPdf,externalIds"
    url = (f"{base}DOI:{urllib.parse.quote(doi)}?{fields}" if doi
           else f"{base}search/match?query={urllib.parse.quote(title)}&{fields}")
    try:
        with fetch(url, timeout=30) as r:
            data = json.load(r)
        if "data" in data:
            data = data["data"][0] if data["data"] else {}
        if not doi and not same_paper(data.get("title", ""), title):
            return None
        ext = data.get("externalIds") or {}
        if ext.get("ArXiv"):
            return f"https://arxiv.org/pdf/{ext['ArXiv']}"
        return (data.get("openAccessPdf") or {}).get("url") or None
    except Exception:
        return None
    finally:
        time.sleep(1.1)  # stay within the free rate limit


def member_keys():
    keys = {name_key(n) for n in ALWAYS_BOLD}
    for path in glob.glob(os.path.join(MEMBERS_DIR, "*.md")):
        with open(path, encoding="utf-8") as f:
            m = re.match(r"---\s*\n(.*?)\n---", f.read(), re.S)
        if m:
            fm = yaml.safe_load(m.group(1)) or {}
            name = fm.get("name") or fm.get("title")
            if name:
                keys.add(name_key(str(name)))
    return keys


# ---------------------------------------------------------------------- main
def main():
    cv = read_cv()
    try:
        dblp = read_dblp()
    except Exception as err:
        if os.path.exists(OUTPUT):
            print(f"::warning::Could not read DBLP, keeping the current list. Details: {err}")
            sys.exit(0)
        print(f"::warning::Could not read DBLP, building from the CV only. Details: {err}")
        dblp = []
        
    overrides = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as f:
            overrides = yaml.safe_load(f) or {}
    members = member_keys()

    # Each CV entry is its own paper (the CV is curated, so never merge two CV entries).
    groups = [[e] for e in cv]
    # DBLP entries join the matching paper, preferring one with the same tag.
    for e in dblp:
        matches = [g for g in groups if any(same_paper(e["title"], x["title"]) for x in g)]
        if not matches:
            groups.append([e])
        else:
            g = next((g for g in matches if any(x["tag"] == e["tag"] for x in g)), matches[0])
            g.append(e)

    pubs, used_ids = [], set()
    for g in groups:
        best = min(g, key=lambda x: (RANK[x["tag"]], x["source"] != "cv"))
        ov = next((overrides[s] for s in {slug(x["title"]) for x in g} if s in overrides), None) or {}
        if ov.get("hide"):
            continue

        pdf = (best["pdf"] or next((x["pdf"] for x in g if x["pdf"]), None)
               or next((x["arxiv"].replace("/abs/", "/pdf/") for x in g if x["arxiv"]), None))
        doi = best["doi"] or next((x["doi"] for x in g if x["doi"]), None)
        url = best["url"] or (f"https://doi.org/{doi}" if doi else None)
        if not pdf and not ov.get("pdf"):
            pdf = s2_pdf(doi, best["title"])
        code = best["code"] or next((x["code"] for x in g if x["code"]), None)

        pid = slug(best["title"])
        if pid in used_ids:
            pid = f"{pid}-{slug(best['tag'])}"
        used_ids.add(pid)

        pub = {
            "id": pid, "tag": best["tag"], "title": best["title"],
            "authors": [{"name": a, "member": name_key(a) in members} for a in best["authors"]],
            "et_al": best["et_al"], "venue": best["venue"], "year": best["year"],
            "pdf": pdf, "url": url if url != pdf else None, "code": code,
        }
        pub.update({k: v for k, v in ov.items() if k != "hide"})
        pubs.append(pub)

    pubs.sort(key=lambda p: (-year_int(p["year"]), RANK.get(p["tag"], 9), p["title"].lower()))
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("# GENERATED FILE - do not edit by hand. See README.md (Publications).\n")
        yaml.safe_dump(pubs, f, allow_unicode=True, sort_keys=False, width=1000)
    print(f"Wrote {len(pubs)} publications to {OUTPUT}")


if __name__ == "__main__":
    main()