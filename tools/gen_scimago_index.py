#!/usr/bin/env python3
"""SCImago 전체 저널랭크 → 검색용 경량 인덱스(assets/data/scimago_search.json).
Metrics 2D 그래프의 '저널 검색'에서 로드된 데이터에 없는 신규 저널을 찾아 새 점을 생성할 때 사용.
OpenAlex 불필요 — SCImago CSV(브라우저 UA 우회)만 사용."""
import json, re, sys, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "scimago_search.json"
SCIMAGO_URL = "https://www.scimagojr.com/journalrank.php?out=xls"

_STOP = {"of", "and", "the", "in", "for", "on", "a", "an", "de", "&", "-"}


def acronym(title):
    """저널명 → 짧은 약칭(유의어 초성 대문자, 최대 5자). 실패 시 첫 단어."""
    words = [w for w in re.split(r"[\s/]+", title) if w]
    caps = [w for w in words if w[:1].isalpha() and w.lower() not in _STOP]
    ac = "".join(w[0].upper() for w in caps)[:6]
    if 2 <= len(ac) <= 6:
        return ac
    return (words[0][:8] if words else title[:8])


def main():
    req = urllib.request.Request(SCIMAGO_URL, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": "https://www.scimagojr.com/journalrank.php",
        "Accept": "text/csv,application/octet-stream,*/*",
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode("utf-8", "ignore")
    lines = raw.splitlines()
    header = [h.strip().strip('"') for h in lines[0].split(";")]

    def _idx(name):
        for i, h in enumerate(header):
            if h.lower() == name.lower():
                return i
        return -1

    def _idxp(sub):
        for i, h in enumerate(header):
            if sub.lower() in h.lower():
                return i
        return -1

    i_title, i_q, i_sjr = _idx("Title"), _idx("SJR Best Quartile"), _idx("SJR")
    i_type = _idx("Type")
    i_if2, i_docs = _idxp("citations / doc"), _idxp("docs. (3years")
    out = []
    for ln in lines[1:]:
        c = [x.strip().strip('"') for x in ln.split(";")]
        if len(c) <= max(i_title, i_q, i_sjr):
            continue
        q = c[i_q].strip()
        if q not in ("Q1", "Q2", "Q3", "Q4"):
            continue
        # 저널만(conference/book series 제외) — Type 컬럼이 있으면 journal만
        if i_type >= 0 and len(c) > i_type and c[i_type].strip().lower() not in ("journal", ""):
            continue
        title = c[i_title].strip()
        if not title:
            continue
        try:
            sjr = round(float(c[i_sjr].replace(",", ".")), 2) if (i_sjr >= 0 and c[i_sjr]) else None
        except ValueError:
            sjr = None
        if sjr is None:
            continue
        cats = [[n.strip(), "Q" + d] for n, d in re.findall(
            r"([A-Za-z][\w &,./'\-]*(?:\([^)]*\)[\w &,./'\-]*)*?)\s*\(Q([1-4])\)", ln)]
        try:
            if2 = round(float(c[i_if2].replace(",", ".")), 1) if (i_if2 >= 0 and len(c) > i_if2 and c[i_if2]) else None
        except ValueError:
            if2 = None
        try:
            works = int(c[i_docs].replace(",", "").replace(" ", "")) if (i_docs >= 0 and len(c) > i_docs and c[i_docs]) else None
        except ValueError:
            works = None
        rec = {"label": acronym(title), "name": title, "q": q, "sjr": sjr}
        if if2 is not None:
            rec["if2"] = if2
        if works is not None:
            rec["works"] = works
        if cats:
            rec["cat"] = cats[0][0]        # 대표 카테고리 1개만(용량 절약; 링크는 클라이언트에서 생성)
        out.append(rec)
    out.sort(key=lambda v: v["sjr"], reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"venues": out}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"· scimago_search.json {len(out)} journals, {OUT.stat().st_size//1024} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
