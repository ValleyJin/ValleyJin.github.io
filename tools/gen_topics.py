#!/usr/bin/env python3
"""My Topics feed generator — OpenAlex → _data/topics.json.

Reads _data/topics_config.yml (editable via Decap CMS / by hand), queries
OpenAlex for recent, on-topic, peer-reviewed articles per topic, formats each
in APA style, and writes _data/topics.json for the Articles page to render.

Google Scholar has no API; OpenAlex is free, keyless, and structured — see
study/13 (and study/08 for the Scholar author feed).
"""
import json, re, sys, urllib.request, urllib.parse
from datetime import date, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "_data" / "topics_config.yml"
OUT = ROOT / "_data" / "topics.json"
ARCHIVE = ROOT / "_data" / "topics_new.json"   # 발견일(new)별 논문 누적
MAILTO = "jscho71@kaist.ac.kr"
API = "https://api.openalex.org/works"


def parse_topics(raw):
    """'라벨 | 검색어' 줄들을 [(label, query)] 로."""
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            label, query = [p.strip() for p in line.split("|", 1)]
        else:
            label = query = line
        out.append((label, query or label))
    return out


def apa_authors(authorships):
    """OpenAlex authorships → APA 저자 문자열 (최대 6명 후 et al.)."""
    names = []
    for a in authorships:
        disp = (a.get("author") or {}).get("display_name") or ""
        disp = disp.strip()
        if not disp:
            continue
        parts = disp.split()
        if len(parts) == 1:
            names.append(parts[0])
        else:
            family = parts[-1]
            initials = " ".join(p[0].upper() + "." for p in parts[:-1] if p)
            names.append(f"{family}, {initials}")
    if not names:
        return "Anon."
    if len(names) > 6:
        names = names[:6] + ["et al."]
    if len(names) == 1:
        return names[0]
    if names[-1] == "et al.":
        return ", ".join(names[:-1]) + ", et al."
    return ", ".join(names[:-1]) + ", & " + names[-1]


def fetch(query, concept, cutoff, n):
    filt = (f"default.search:{query},type:article,"
            f"from_publication_date:{cutoff},concepts.id:{concept},has_doi:true")
    q = {
        "filter": filt,
        "per_page": max(n * 2, 8),  # 여유분(중복 제거 후 n개 확보)
        "mailto": MAILTO,
        "select": "title,publication_year,authorships,primary_location,doi,cited_by_count,id",
    }
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": f"valleyjin-topics ({MAILTO})"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def clean_title(t):
    t = (t or "").strip()
    return re.sub(r"\s+", " ", t)


def main():
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    topics = parse_topics(cfg.get("topics", ""))
    concept = str(cfg.get("field_concept", "C41008148")).strip()
    years = int(cfg.get("years", 3))
    per_topic = int(cfg.get("per_topic", 4))
    cutoff = (date.today() - timedelta(days=365 * years)).isoformat()

    result = {"generated": date.today().isoformat(),
              "field": "Computer Science · AI & databases",
              "topics": []}

    for label, query in topics:
        block = {"topic": label, "query": query, "papers": []}
        try:
            data = fetch(query, concept, cutoff, per_topic)
        except Exception as e:  # 한 토픽 실패가 전체를 막지 않게
            print(f"! {label}: {e}", file=sys.stderr)
            result["topics"].append(block)
            continue
        block["count"] = data.get("meta", {}).get("count")
        seen = set()
        for w in data.get("results", []):
            title = clean_title(w.get("title"))
            key = title.lower()[:70]
            if not title or key in seen or len(title) < 8 or title.isdigit():
                continue
            src = (w.get("primary_location") or {}).get("source") or {}
            venue = (src.get("display_name") or "").strip()
            if not venue or venue.lower().startswith(("zenodo", "figshare", "ssrn")):
                continue
            seen.add(key)
            block["papers"].append({
                "title": title,
                "authors": apa_authors(w.get("authorships", [])),
                "year": w.get("publication_year"),
                "venue": venue,
                "url": w.get("doi") or w.get("id"),
                "cites": w.get("cited_by_count", 0),
            })
            if len(block["papers"]) >= per_topic:
                break
        result["topics"].append(block)
        print(f"  {label}: {len(block['papers'])} papers")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ wrote {OUT.relative_to(ROOT)} — {len(result['topics'])} topics")

    # ── 발견일(new)별 아카이브: 이전에 본 적 없는 논문만 '오늘' 버킷에 쌓는다 ──
    today = result["generated"]
    arch = {"days": []}
    if ARCHIVE.exists():
        try:
            arch = json.loads(ARCHIVE.read_text(encoding="utf-8")) or {"days": []}
        except Exception:
            arch = {"days": []}
    seen = {p["key"] for d in arch.get("days", []) for p in d.get("papers", []) if p.get("key")}
    new_today, seen_now = [], set()
    for grp in result["topics"]:
        for p in grp["papers"]:
            key = (p.get("url") or p["title"]).strip().lower()
            if not key or key in seen or key in seen_now:
                continue
            seen_now.add(key)
            new_today.append({**p, "topic": grp["topic"], "key": key})
    if new_today:
        entry = next((d for d in arch["days"] if d["date"] == today), None)
        if entry:
            have = {p["key"] for p in entry["papers"]}
            entry["papers"].extend(p for p in new_today if p["key"] not in have)
        else:
            arch["days"].append({"date": today, "papers": new_today})
    arch["days"].sort(key=lambda d: d["date"], reverse=True)
    arch["days"] = arch["days"][:120]      # 최근 ~120일 유지
    ARCHIVE.write_text(json.dumps(arch, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(d["papers"]) for d in arch["days"])
    print(f"✓ archive: {total} papers / {len(arch['days'])} days (+{len(new_today)} new today)")


if __name__ == "__main__":
    main()
