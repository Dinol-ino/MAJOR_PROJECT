"""
Import Acts from a local clone of github.com/nyaayaIN/laws-of-india into data/acts_raw/.

    git clone --depth 1 https://github.com/nyaayaIN/laws-of-india <dir>
    python scripts/import_laws_of_india.py <dir> --acts "Indian Penal Code" "Contract Act" ...
    python scripts/import_laws_of_india.py <dir> --all
    python scripts/seed_tier1.py                       # then index

Writes one .txt per Act (sections as "Section N. Heading" lines, which the corpus pipeline
parses) and merges entries into manifest.yaml. Nothing is marked verified: the upstream text is
a community conversion (CC BY-NC-SA 4.0, non-commercial) and can lag amendments, so every entry
carries legal_status "unverified" until a human diffs it against the official India Code text.
"""
import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import yaml

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.ingestion.statutory_corpus import acts_dir  # noqa: E402

UPSTREAM = "https://github.com/nyaayaIN/laws-of-india"
LICENSE = "CC BY-NC-SA 4.0 (non-commercial)"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def xml_to_text(path: str):
    root = ET.parse(path).getroot()
    title = None
    year = None
    for el in root.iter():
        if _local(el.tag) == "shortTitle":
            title = _text(el)
            break
    m = re.search(r"(\d{4})\s*$", title or "")
    year = int(m.group(1)) if m else None
    out = []
    for el in root.iter():
        name = _local(el.tag)
        if name == "chapter":
            num = head = ""
            for c in el:
                if _local(c.tag) == "num":
                    num = _text(c)
                elif _local(c.tag) == "heading":
                    head = _text(c)
            out.append(f"\nCHAPTER {num} - {head}".rstrip(" -"))
        elif name == "section":
            num = head = ""
            body = []
            for c in el:
                cn = _local(c.tag)
                if cn == "num":
                    num = _text(c).rstrip(".")
                elif cn == "heading":
                    head = _text(c).rstrip("—-. ")
                else:
                    body.append(_text(c))
            if num:
                out.append(f"\nSection {num}. {head}\n" + "\n".join(b for b in body if b))
    return title, year, "\n".join(out).strip()


def md_to_text(path: str):
    raw = open(path, encoding="utf-8-sig").read()
    title = re.search(r"^#\s+(.+)$", raw, re.M)
    title = title.group(1).strip() if title else os.path.splitext(os.path.basename(path))[0]
    year = re.search(r"(\d{4})\s*$", title)
    text = re.sub(r"^###\s+(\d+[A-Z]{0,3})\.\s*", r"Section \1. ", raw, flags=re.M)
    text = re.sub(r"^##\s+(CHAPTER[^\n]*)", r"\1", text, flags=re.M)
    return title, int(year.group(1)) if year else None, text


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:100]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--acts", nargs="*", default=[], help="case-insensitive substrings of file names")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if not a.all and not a.acts:
        ap.error("give --acts <substrings> or --all")

    commit = subprocess.run(["git", "-C", a.repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = a.out or acts_dir()
    os.makedirs(out, exist_ok=True)
    mpath = os.path.join(out, "manifest.yaml")
    manifest = yaml.safe_load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}
    manifest = manifest or {}
    acts = manifest.setdefault("acts", {})

    files = []
    for sub in ("consolidated", "central-laws"):
        d = os.path.join(a.repo, sub)
        for root, _, names in os.walk(d):
            files += [os.path.join(root, n) for n in names if n.endswith((".xml", ".md"))]
    wanted = [f for f in files if a.all or any(s.lower() in os.path.basename(f).lower() for s in a.acts)]
    done, skipped = 0, []
    for f in sorted(wanted):
        try:
            title, year, text = xml_to_text(f) if f.endswith(".xml") else md_to_text(f)
        except ET.ParseError:
            skipped.append(os.path.basename(f)); continue
        if not title or len(text) < 200 or "Section " not in text:
            skipped.append(os.path.basename(f)); continue
        fname = slug(title.replace(",", " ")) + ".txt"
        open(os.path.join(out, fname), "w", encoding="utf-8").write(text)
        rel = os.path.relpath(f, a.repo).replace(os.sep, "/")
        entry = acts.setdefault(fname, {})
        entry.update({
            "title": title, "source_url": f"{UPSTREAM}/blob/{commit}/{rel}",
            "source_version": f"laws-of-india@{commit[:12]}; license {LICENSE}",
            "legal_status": "unverified",
        })
        if year:
            entry["year"] = year
        entry.pop("verified_at", None)
        done += 1
    yaml.safe_dump(manifest, open(mpath, "w", encoding="utf-8"), sort_keys=True, allow_unicode=True)
    print(f"imported {done} acts to {out}; skipped {len(skipped)} (no parseable sections)")


if __name__ == "__main__":
    main()
