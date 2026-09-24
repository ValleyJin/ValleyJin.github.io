#!/usr/bin/env python3
"""키페이퍼 → 유관 논문 크롤 + 인용(cited-by) 알림.

재사용 절차: _data/pinned_papers.json 의 topics.<토픽> 에
    { "key": ["<대표 arXiv id>"], "em": "<Emergent Mind 토픽 URL(선택)>" }
을 넣으면 이 스크립트가
  (1) 유관 논문 = em 페이지에 큐레이션된 arXiv 논문(있으면), 없으면 key 논문의 참고문헌,
  (2) 인용 알림 = key 논문을 인용한 논문(cited-by, 새로 뜬 것)
을 만들어 _data/keypapers.json 으로 저장한다. 인용 논문의 최초 관측일(first_seen)을 보존해
사이트에서 'NEW'(며칠간)를 낸다.

엔진(견고성 우선):
  · arXiv id 목록 → Emergent Mind 페이지 정적 HTML 파싱(urllib)
  · 논문 메타데이터(제목·저자·연도) → arXiv Atom API (권위·완전·배치)
  · 피인용수(cites) → OpenAlex (arXiv DOI, best-effort)
  · 인용한 논문(cited-by) → Semantic Scholar citations (best-effort, 백오프)
표준 라이브러리만 사용. 선택적 환경변수:
  S2_API_KEY   = Semantic Scholar API key (없어도 동작; 무인증 레이트리밋만)
  OPENALEX_KEY = OpenAlex 예산 키 (없어도 동작)
"""
import os, sys, json, time, re, xml.etree.ElementTree as ET
import urllib.request, urllib.error, urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "_data" / "pinned_papers.json"
OUT = ROOT / "_data" / "keypapers.json"
TODAY = date.today().isoformat()
MAILTO = "jscho71@kaist.ac.kr"
S2 = "https://api.semanticscholar.org/graph/v1"
S2_KEY = os.environ.get("S2_API_KEY", "").strip()
OPENALEX_KEY = os.environ.get("OPENALEX_KEY", "").strip()

RELATED_MAX = 12     # 유관 논문 최대
CITING_MAX = 40      # 인용 알림 목록 최대
ATOM = "{http://www.w3.org/2005/Atom}"


def _fetch(url, headers=None, tries=4):
    hdr = {"User-Agent": "valleyjin-keypapers/1.0 (mailto:%s)" % MAILTO}
    if headers:
        hdr.update(headers)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=45) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(6 + i * 8, 40))
                continue
            return None
        except Exception:
            time.sleep(2 + i * 2)
    return None


# ── 1) Emergent Mind 페이지 → 유관 arXiv id ──────────────────────────
def em_arxiv_ids(em_url):
    html = _fetch(em_url, headers={"User-Agent": "Mozilla/5.0"})
    if not html:
        print(f"  ! em fetch 실패 {em_url}", file=sys.stderr)
        return []
    seen, out = set(), []
    for i in re.findall(r"/papers/(\d{4}\.\d{4,5})", html):
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ── 2) arXiv Atom API → 메타데이터(제목·저자·연도) ───────────────────
def _apa(authors):
    names = []
    for full in authors[:3]:
        p = full.split()
        names.append((p[0][0] + " " + p[-1]) if len(p) >= 2 else full)
    s = ", ".join(names)
    if len(authors) > 3:
        s += ", et al."
    return s


def arxiv_meta(ids):
    """arXiv id 리스트 → {id: {title, authors, year, url}} (배치)."""
    meta = {}
    ids = list(dict.fromkeys(ids))
    for k in range(0, len(ids), 40):                 # 배치 40개씩
        chunk = ids[k:k + 40]
        url = "https://export.arxiv.org/api/query?id_list=" + ",".join(chunk) + "&max_results=" + str(len(chunk))
        xml = _fetch(url)
        if not xml:
            continue
        try:
            root = ET.fromstring(xml)
        except Exception:
            continue
        for e in root.findall(ATOM + "entry"):
            idu = (e.findtext(ATOM + "id") or "")
            m = re.search(r"/abs/(\d{4}\.\d{4,5})", idu)
            if not m:
                continue
            aid = m.group(1)
            title = " ".join((e.findtext(ATOM + "title") or "").split())
            auth = [ (a.findtext(ATOM + "name") or "").strip() for a in e.findall(ATOM + "author") ]
            auth = [a for a in auth if a]
            pub = (e.findtext(ATOM + "published") or "")
            year = int(pub[:4]) if pub[:4].isdigit() else None
            meta[aid] = {"title": title, "authors": _apa(auth), "year": year,
                         "url": "https://arxiv.org/abs/" + aid, "venue": "arXiv"}
        time.sleep(1)
    return meta


# ── 3) OpenAlex → 피인용수(best-effort) ──────────────────────────────
def _oa(url):
    url += ("&" if "?" in url else "?") + "mailto=" + MAILTO
    if OPENALEX_KEY:
        url += "&api_key=" + urllib.parse.quote(OPENALEX_KEY)
    return url


def oa_cites(ids):
    """{arxiv_id: (cited_by_count, openalex_work_id)} — DOI 배치 조회."""
    out = {}
    ids = list(dict.fromkeys(ids))
    for k in range(0, len(ids), 40):
        chunk = ids[k:k + 40]
        dois = "|".join("10.48550/arxiv." + i for i in chunk)
        url = _oa("https://api.openalex.org/works?filter=doi:" + dois +
                  "&per-page=50&select=title,doi,ids,cited_by_count")
        txt = _fetch(url)
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        for w in data.get("results", []):
            doi = (w.get("doi") or "").lower()
            m = re.search(r"arxiv\.(\d{4}\.\d{4,5})", doi)
            if m:
                out[m.group(1)] = (w.get("cited_by_count") or 0, w.get("id"))
        time.sleep(0.5)
    return out


# ── 4) Semantic Scholar → 이 논문을 인용한 논문(cited-by 알림) ────────
def _s2(url):
    hdr = {"x-api-key": S2_KEY} if S2_KEY else None
    return _fetch(url, headers=hdr)


def s2_citations(arxiv):
    f = "title,authors,year,externalIds,citationCount,venue,publicationDate"
    txt = _s2(f"{S2}/paper/arXiv:{arxiv}/citations?fields={f}&limit=200")
    if not txt:
        return []
    try:
        rows = (json.loads(txt) or {}).get("data", [])
    except Exception:
        return []
    out = []
    for row in rows:
        cp = row.get("citingPaper") or {}
        if not cp.get("title"):
            continue
        ext = cp.get("externalIds") or {}
        arx = ext.get("ArXiv"); doi = ext.get("DOI")
        if arx:
            url = "https://arxiv.org/abs/" + arx
        elif doi:
            url = "https://doi.org/" + doi
        else:
            url = "https://www.semanticscholar.org/paper/" + (cp.get("paperId") or "")
        auth = [ (a.get("name") or "").strip() for a in (cp.get("authors") or []) ]
        out.append({
            "title": cp["title"].strip(), "authors": _apa([a for a in auth if a]),
            "year": cp.get("year"), "venue": (cp.get("venue") or "arXiv").strip() or "arXiv",
            "url": url, "cites": cp.get("citationCount") or 0,
            "pubdate": cp.get("publicationDate") or "",
        })
    return out


def _obj(aid, meta, cites_map, topic, key=False):
    m = meta.get(aid) or {"title": "", "authors": "", "year": None,
                          "url": "https://arxiv.org/abs/" + aid, "venue": "arXiv"}
    o = dict(m); o["topic"] = topic; o["arxiv"] = aid
    o["cites"] = (cites_map.get(aid) or (0,))[0]
    if key:
        o["key"] = True
    return o


def main():
    cfg = json.loads(CFG.read_text(encoding="utf-8")) if CFG.exists() else {}
    topics = (cfg.get("topics") or {})
    if not topics:
        print("no key papers configured", file=sys.stderr)
        return

    prev = {}
    if OUT.exists():
        try:
            prev = (json.loads(OUT.read_text(encoding="utf-8")) or {}).get("topics", {})
        except Exception:
            prev = {}

    result = {"generated": TODAY, "source": "arXiv + OpenAlex + Semantic Scholar", "topics": {}}
    any_ok = False

    for topic, spec in topics.items():
        keys = spec.get("key") or []
        if isinstance(keys, str):
            keys = [keys]
        keys = [str(k).strip() for k in keys if str(k).strip()]
        # em: 문자열 또는 리스트(여러 Emergent Mind 페이지). 순서 유지 dedup.
        em_urls = spec.get("em") or []
        if isinstance(em_urls, str):
            em_urls = [em_urls]
        em_all = []
        for u in em_urls:
            u = str(u).strip()
            if u:
                em_all += em_arxiv_ids(u)
        em_all = list(dict.fromkeys(em_all))
        if not keys and em_all:
            keys = [em_all[0]]                        # 키 미지정 → em 첫 논문을 대표로
        key_set = set(keys)
        em_ids = [i for i in em_all if i not in key_set][:RELATED_MAX]
        if not keys:
            continue
        print(f"· {topic}: key {len(keys)} · em 유관 {len(em_ids)}")

        all_ids = keys + em_ids
        meta = arxiv_meta(all_ids)
        cites = oa_cites(all_ids)
        if meta:
            any_ok = True

        key_objs = [_obj(k, meta, cites, topic, key=True) for k in keys]
        related = [_obj(i, meta, cites, topic) for i in em_ids]     # em 순서(큐레이션 흐름) 유지

        # em 유관이 없으면 참고문헌으로 폴백은 생략(키페이퍼만이라도 정확히 뜨게) — em URL 권장

        # 인용 알림: 이전 first_seen 보존
        prev_seen = {c["url"]: (c.get("first_seen") or TODAY)
                     for c in (prev.get(topic, {}) or {}).get("citing", []) if c.get("url")}
        citing = {}
        for arx in keys:
            for c in s2_citations(arx):
                if c["url"] in citing:
                    continue
                c["cited_key"] = (meta.get(arx, {}).get("title") or arx)[:60]
                c["first_seen"] = prev_seen.get(c["url"], TODAY)
                citing[c["url"]] = c
            time.sleep(1)

        key_urls = {k["url"] for k in key_objs}
        cite_list = [c for c in citing.values() if c["url"] not in key_urls]
        cite_list.sort(key=lambda p: (p.get("pubdate") or "", p.get("cites") or 0), reverse=True)

        result["topics"][topic] = {
            "key": key_objs,
            "related": related[:RELATED_MAX],
            "citing": cite_list[:CITING_MAX],
            "n_citing": len(cite_list),
        }
        print(f"  → related {len(related)} · citing {len(cite_list)}")

    if not any_ok and prev:
        print("! 모든 키페이퍼 조회 실패 — 기존 keypapers.json 유지", file=sys.stderr)
        return
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ wrote {OUT.relative_to(ROOT)} — {len(result['topics'])} topic(s)")


if __name__ == "__main__":
    main()
