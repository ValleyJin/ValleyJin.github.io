#!/usr/bin/env python3
"""My Topics feed generator — OpenAlex → _data/topics.json.

Reads _data/topics_config.yml (editable via Decap CMS / by hand), queries
OpenAlex for recent, on-topic, peer-reviewed articles per topic, formats each
in APA style, and writes _data/topics.json for the Articles page to render.

Google Scholar has no API; OpenAlex is free, keyless, and structured — see
study/13 (and study/08 for the Scholar author feed).
"""
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import date, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "_data" / "topics_config.yml"
OUT = ROOT / "_data" / "topics.json"
NEWEST = ROOT / "_data" / "newest.json"        # 최근 '발간'된 논문(발간일순, 달력용)
SCHOLARS = ROOT / "_data" / "scholars.json"    # 팔로우 학자별 최신 논문
VENUES = ROOT / "_data" / "venues.json"        # 토픽 학회/저널의 영향력지수·분야
MAILTO = "jscho71@kaist.ac.kr"
API = "https://api.openalex.org/works"
API_SOURCES = "https://api.openalex.org/sources"


def parse_topics(raw):
    """'라벨 | 검색어 | EM_URL' 줄들을 [(label, query, extra)] 로 (검색어·URL 선택)."""
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        label = parts[0]
        query = parts[1] if len(parts) > 1 and parts[1] else label
        extra = parts[2] if len(parts) > 2 else ""     # topics=EM URL, scholars=미사용
        out.append((label, query, extra))
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


def fetch(query, concept, cutoff, n, sort=None, field="default", until=None):
    if query.startswith("venue:"):
        # 학회/저널 지정: 해당 source의 논문만. has_doi는 빼야 한다(NeurIPS/ICML/ICLR 등 학회는 DOI가 없는 경우가 많음).
        parts = ["locations.source.id:" + query[6:].strip(), "type:article|proceedings-article"]
    else:
        parts = [f"{field}.search:{query}", "type:article", f"concepts.id:{concept}", "has_doi:true"]
    if cutoff:
        parts.append(f"from_publication_date:{cutoff}")      # cutoff=None → 전기간
    if until:
        parts.append(f"to_publication_date:{until}")         # 미래(예약) 발간일 제외
    filt = ",".join(parts)
    q = {
        "filter": filt,
        "per_page": max(n * 2, 8),  # 여유분(중복 제거 후 n개 확보)
        "mailto": MAILTO,
        "select": "title,publication_year,publication_date,authorships,primary_location,doi,cited_by_count,id,fwci,citation_normalized_percentile",
    }
    if sort:
        q["sort"] = sort
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": f"valleyjin-topics ({MAILTO})"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(1.5 * (attempt + 1))    # 429 백오프: 1.5, 3, 4.5, 6초
                continue
            raise


def fetch_s2(venue, cutoff, sort, n, until):
    """Semantic Scholar bulk search — venue(학회)로 논문 수집. OpenAlex가 DOI 없는 학회
    논문(NeurIPS/ICML/ICLR)을 못 잡는 한계를 보완. 결과를 OpenAlex 형식으로 변환해 호환."""
    q = {"venue": venue, "fields": "title,year,venue,authors,citationCount,externalIds,publicationDate"}
    if cutoff:
        q["year"] = cutoff[:4] + "-" + (until[:4] if until else "")
    if sort:
        q["sort"] = sort.replace("publication_date", "publicationDate").replace("cited_by_count", "citationCount")
    url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": f"valleyjin ({MAILTO})"})
    s2key = os.environ.get("S2_API_KEY")
    if s2key:
        req.add_header("x-api-key", s2key)
    raw = {}
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = json.load(r); break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(2 * (attempt + 1)); continue
            raise
    results = []
    for p in (raw.get("data") or [])[: max(n * 3, 12)]:
        ext = p.get("externalIds") or {}
        doi = ext.get("DOI"); arx = ext.get("ArXiv"); pid = p.get("paperId") or ""
        results.append({
            "title": p.get("title"),
            "publication_year": p.get("year"),
            "publication_date": p.get("publicationDate") or (f"{p.get('year')}-01-01" if p.get("year") else None),
            "authorships": [{"author": {"display_name": a.get("name")}} for a in (p.get("authors") or [])],
            "primary_location": {"source": {"display_name": p.get("venue")}},
            "doi": ("https://doi.org/" + doi) if doi else None,
            "id": ("https://arxiv.org/abs/" + arx) if arx else ("https://www.semanticscholar.org/paper/" + pid),
            "cited_by_count": p.get("citationCount") or 0,
        })
    return {"results": results, "meta": {"count": raw.get("total")}}


def _fetch(query, concept, cutoff, n, sort=None, field="default", until=None):
    """토픽 소스 분기: 's2:<venue>' 는 Semantic Scholar, 그 외는 OpenAlex."""
    if query.startswith("s2:"):
        return fetch_s2(query[3:].strip(), cutoff, sort, n, until)
    return fetch(query, concept, cutoff, n, sort=sort, field=field, until=until)


def fetch_scholar(user_id, key, n, sort=None):
    """Google Scholar 프로필의 최신 논문(SerpAPI). 저자 본인이 큐레이션 → 동명이인 없음."""
    params = {"engine": "google_scholar_author", "author_id": user_id.strip(),
              "api_key": key, "hl": "en", "num": min(max(n, 1), 100)}
    if sort:
        params["sort"] = sort   # "pubdate" = 최근순 (생략 시 cited by 인용순)
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def clean_title(t):
    t = (t or "").strip()
    return re.sub(r"\s+", " ", t)


SCIMAGO_URL = "https://www.scimagojr.com/journalrank.php?out=xls"   # 전체 저널 랭크 CSV(;구분)


def load_scimago():
    """SCImago 저널 랭크 → {정규화ISSN: {'q':'Q1','sjr':2.34}}. 저널 Q1~Q4 출처.
    한 번 내려받아 ISSN으로 매칭한다. 실패해도(네트워크 등) 빈 dict로 조용히 진행."""
    m = {}
    try:
        # SCImago는 봇 UA를 403으로 막는다 → 브라우저 UA + Referer로 요청
        req = urllib.request.Request(SCIMAGO_URL, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": "https://www.scimagojr.com/journalrank.php",
            "Accept": "text/csv,application/octet-stream,*/*",
        })
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"! SCImago 로드 실패(저널 분위 생략): {e}", file=sys.stderr)
        return m
    lines = raw.splitlines()
    if not lines:
        return m
    header = [h.strip().strip('"') for h in lines[0].split(";")]
    def _idx(name):
        for i, h in enumerate(header):
            if h.lower() == name.lower():
                return i
        return -1
    i_issn, i_q, i_sjr = _idx("Issn"), _idx("SJR Best Quartile"), _idx("SJR")
    if i_issn < 0 or i_q < 0:
        print("! SCImago 헤더 형식 예상과 다름 — 분위 생략", file=sys.stderr)
        return m
    for ln in lines[1:]:
        c = [x.strip().strip('"') for x in ln.split(";")]
        if len(c) <= max(i_issn, i_q, i_sjr):
            continue
        q = c[i_q].strip()
        if q not in ("Q1", "Q2", "Q3", "Q4"):
            continue
        sjr = None
        if i_sjr >= 0 and c[i_sjr]:
            try:
                sjr = round(float(c[i_sjr].replace(",", ".")), 2)   # xls는 소수점이 콤마
            except ValueError:
                sjr = None
        # 분야별 분위: Categories 컬럼이 ';'를 내부에 써서 열 분해가 불안정 → 'Name (Qn)' 패턴을 원본 줄에서 정규식 추출
        cats = [[n.strip(), "Q" + d] for n, d in re.findall(r"([A-Za-z][\w &,./'\-]+?)\s+\(Q([1-4])\)", ln)]
        entry = {"q": q, "sjr": sjr, "cats": cats}
        for iss in c[i_issn].replace(" ", "").split(","):
            k = iss.replace("-", "").upper()
            if k:
                m.setdefault(k, entry)
    print(f"· SCImago {len(m)} ISSN 로드", file=sys.stderr)
    return m


def quality(w, sci):
    """OpenAlex work → 품질지표: FWCI, 인용 백분위(Top 1/10%), 저널 분위(Q)·SJR."""
    out = {}
    fwci = w.get("fwci")
    if isinstance(fwci, (int, float)):
        out["fwci"] = round(float(fwci), 2)
    cnp = w.get("citation_normalized_percentile") or {}
    if cnp.get("is_in_top_1_percent"):
        out["pct"] = 1
    elif cnp.get("is_in_top_10_percent"):
        out["pct"] = 10
    src = (w.get("primary_location") or {}).get("source") or {}
    cand = []
    if src.get("issn_l"):
        cand.append(src["issn_l"])
    for i in (src.get("issn") or []):
        cand.append(i)
    for i in cand:
        k = str(i).replace("-", "").replace(" ", "").upper()
        if k in sci:
            out["q"] = sci[k]["q"]
            if sci[k].get("sjr") is not None:
                out["sjr"] = sci[k]["sjr"]
            break
    return out


# CS 학회는 OpenAlex 약칭 검색이 부정확 → 정식명으로 조회
CONF_FULLNAME = {
    "NeurIPS": "Neural Information Processing Systems",
    "ICML": "International Conference on Machine Learning",
    "ICLR": "International Conference on Learning Representations",
    "CVPR": "Computer Vision and Pattern Recognition",
}


def _oa_source_by_id(sid):
    try:
        with urllib.request.urlopen(f"{API_SOURCES}/{sid.strip()}?mailto={MAILTO}", timeout=30) as r:
            return json.load(r)
    except Exception:
        return None


def _oa_source_by_name(full):
    """학회 정식명으로 conference source 검색. 정식명 정확 일치 우선, 없으면 논문수 최다."""
    try:
        url = (API_SOURCES + "?search=" + urllib.parse.quote(full)
               + "&filter=type:conference&sort=works_count:desc&per_page=5&mailto=" + MAILTO)
        with urllib.request.urlopen(url, timeout=30) as r:
            res = (json.load(r).get("results") or [])
    except Exception:
        return None
    exact = [s for s in res if (s.get("display_name") or "").strip().lower() == full.lower()]
    lst = exact or res
    return lst[0] if lst else None


def _field_of(src):
    tp = (src.get("topics") or [])
    if not tp:
        return {}
    t = tp[0]
    return {"domain": (t.get("domain") or {}).get("display_name"),
            "field": (t.get("field") or {}).get("display_name"),
            "sub": (t.get("subfield") or {}).get("display_name")}


def build_venues(topics, sci):
    """토픽의 학회/저널별 영향력지수·분야 → venues.json. 저널은 SJR·Q(분야별)·IF·h,
    학회는 h-index·논문수·분야(OpenAlex)."""
    out = {}
    for label, query, link in topics:
        if query.startswith("venue:"):
            src = _oa_source_by_id(query[6:])
            if not src:
                continue
            ss = src.get("summary_stats") or {}
            f = _field_of(src)
            cand = []
            if src.get("issn_l"):
                cand.append(src["issn_l"])
            for i in (src.get("issn") or []):
                cand.append(i)
            sc = None
            for i in cand:
                k = str(i).replace("-", "").replace(" ", "").upper()
                if k in sci:
                    sc = sci[k]; break
            v = {"name": src.get("display_name"), "type": "journal", "link": link,
                 "h": ss.get("h_index"), "if2": round(ss.get("2yr_mean_citedness") or 0, 1),
                 "works": src.get("works_count"), "issn": src.get("issn_l"),
                 "domain": f.get("domain"), "field": f.get("field"), "sub": f.get("sub")}
            if sc:
                v["sjr"] = sc.get("sjr"); v["q"] = sc.get("q"); v["cats"] = sc.get("cats")
            out[label] = v
        elif query.startswith("s2:"):
            full = CONF_FULLNAME.get(label, query[3:].strip())
            src = _oa_source_by_name(full)
            v = {"name": full, "type": "conference", "link": link}
            if src:
                ss = src.get("summary_stats") or {}
                f = _field_of(src)
                v.update({"name": src.get("display_name") or full, "h": ss.get("h_index"),
                          "works": src.get("works_count"), "domain": f.get("domain"),
                          "field": f.get("field"), "sub": f.get("sub")})
            out[label] = v
        if label in out:
            print(f"  venue {label}: {out[label].get('type')} q={out[label].get('q')} h={out[label].get('h')}", file=sys.stderr)
    return out


def main():
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    topics = parse_topics(cfg.get("topics", ""))
    concept = str(cfg.get("field_concept", "C41008148")).strip()
    years = int(cfg.get("years", 3))
    per_topic = int(cfg.get("per_topic", 4))
    cutoff = (date.today() - timedelta(days=365 * years)).isoformat()
    # Newest(달력)용: OpenAlex는 최근 며칠에 논문이 몰려 있어 단순 최신순으로 뽑으면
    # 이번 달만 채워진다. 매 실행은 최근 N개월을 '달별'로 나눠 토픽별 상위 K편을 받고,
    # 결과를 기존 newest.json에 '병합(누적)'한다 → 8·9월은 계속 쌓여 남는다.
    # N=2(겹침): 색인 지연으로 다음 달에 뒤늦게 뜨는 전달 논문까지 이때 포착하려는 것.
    newest_months = int(cfg.get("newest_months", 2))          # 매 실행 새로 받을(겹칠) 최근 개월 수
    newest_per_month = int(cfg.get("newest_per_month", 15))    # 토픽 × 달마다 상위 몇 편
    scimago = load_scimago()                                   # 저널 Q1~Q4 · SJR (ISSN 매칭)

    # 토픽 학회/저널의 영향력지수·분야 → venues.json (칩 선택 시 표시)
    venues_meta = build_venues(topics, scimago)
    if venues_meta:
        VENUES.write_text(json.dumps({"generated": date.today().isoformat(), "venues": venues_meta},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ venues: {len(venues_meta)} venues", file=sys.stderr)

    result = {"generated": date.today().isoformat(),
              "field": "Computer Science · AI & databases",
              "topics": []}

    for label, query, _em in topics:
        block = {"topic": label, "query": query, "papers": []}
        try:
            data = _fetch(query, concept, cutoff, per_topic)
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

    # 모든 토픽 fetch가 실패(예: OpenAlex 429)해 전부 비면 기존 파일을 덮지 않는다.
    if not any(b["papers"] for b in result["topics"]) and OUT.exists():
        print("! 모든 토픽 fetch 실패(OpenAlex 오류 추정) — 기존 topics.json 유지", file=sys.stderr)
    else:
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ wrote {OUT.relative_to(ROOT)} — {len(result['topics'])} topics")

    # ── Newest: 팔로우 토픽에서 '최근 발간'된 논문(발간일순) → 달력용 ──
    today = result["generated"]
    from calendar import monthrange
    _t = date.today()

    # 기존 누적 파일을 먼저 읽는다(병합 + 전체갱신 판정에 사용)
    prev, prev_meta = [], {}
    if NEWEST.exists():
        try:
            prev_meta = json.loads(NEWEST.read_text(encoding="utf-8")) or {}
            prev = prev_meta.get("papers", []) or []
        except Exception:
            prev, prev_meta = [], {}

    # 전체 재fetch = 연 2회(1/1, 7/1 시작 반기). 그 반기에 아직 안 했으면 이번 실행에서 수행(놓침 방지).
    # 전체갱신 땐 누적된 전 기간(가장 이른 달 ~ 현재)을 다시 받아 오래된 논문 지표(FWCI·Q·인용)까지 갱신.
    newest_full_cap = int(cfg.get("newest_full_cap", 18))     # 전체갱신 시 거슬러 올라갈 최대 개월
    period_start = date(_t.year, 7 if _t.month >= 7 else 1, 1).isoformat()
    last_full = prev_meta.get("last_full")
    is_full = (not last_full) or (last_full < period_start)
    months = newest_months
    if is_full:
        _dts = [p.get("date", "") for p in prev if p.get("date")]
        if _dts:
            e = min(_dts)                                     # 누적 최이른 발간일 → 그 달부터 현재까지
            months = (_t.year - int(e[:4])) * 12 + (_t.month - int(e[5:7])) + 1
        months = max(newest_months, min(months, newest_full_cap))
        print(f"· 전체 재fetch(반기 {period_start}): 최근 {months}개월 갱신", file=sys.stderr)

    # 최근 months개월의 (시작일, 종료일) 윈도우 목록 — 현재 달부터 과거로
    windows, _wy, _wm = [], _t.year, _t.month
    for _ in range(max(1, months)):
        _start = date(_wy, _wm, 1)
        _end = date(_wy, _wm, monthrange(_wy, _wm)[1])
        if _end > _t:
            _end = _t                                        # 현재 달은 오늘까지
        windows.append((_start.isoformat(), _end.isoformat()))
        _wm -= 1
        if _wm == 0:
            _wm = 12; _wy -= 1

    newest_from = windows[-1][0]                             # 커버 윈도우의 가장 이른 시작일
    newest, seen_n = [], set()
    for label, query, _em in topics:
        for _wstart, _wend in windows:                       # 달마다 따로 받아 각 달을 보장
            try:
                data = _fetch(query, concept, _wstart, newest_per_month, sort="publication_date:desc", until=_wend)
            except Exception as e:
                print(f"! newest {label} {_wstart[:7]}: {e}", file=sys.stderr)
                continue
            kept = 0
            for w in data.get("results", []):
                pd = w.get("publication_date")
                title = clean_title(w.get("title"))
                key = (w.get("doi") or title).strip().lower()
                # s2/venue 소스가 날짜 필터를 무시하고 옛 논문을 섞어 보내는 경우 방어 → 윈도우 밖 제거
                if not pd or pd > today or pd < newest_from or not title or len(title) < 8 or key in seen_n:
                    continue                                 # pd 범위 밖 = 스킵
                src = (w.get("primary_location") or {}).get("source") or {}
                venue = (src.get("display_name") or "").strip()
                if not venue or venue.lower().startswith(("zenodo", "figshare", "ssrn")):
                    continue
                seen_n.add(key)
                _np = {
                    "date": pd, "title": title,
                    "authors": apa_authors(w.get("authorships", [])),
                    "year": w.get("publication_year"), "venue": venue,
                    "url": w.get("doi") or w.get("id"),
                    "cites": w.get("cited_by_count", 0), "topic": label,
                }
                _np.update(quality(w, scimago))   # FWCI·백분위·저널 분위(Q)·SJR
                newest.append(_np)
                kept += 1
                if kept >= newest_per_month:                 # 토픽×달마다 상위 K편만
                    break
    newest.sort(key=lambda p: p["date"], reverse=True)
    fresh = newest   # 이번 실행에서 새로 받은 최근 N개월치 (누적 병합 전)

    # ── Most cited: 토픽(키워드)별 '전기간' 누적 피인용 상위 (날짜 무관) ──
    mostcited = {}
    for label, query, _em in topics:
        arr, seen_m = [], set()
        try:
            # 관련도(정렬X)로 주제 논문을 넓게 → 그중 인용수 상위. (cited_by_count 정렬은
            # 관련도를 무시해 BLAST/ImageNet 같은 무관 초고인용을 끌어와서 안 씀)
            data = _fetch(query, concept, None, 30, field="title_and_abstract")
        except Exception as e:
            print(f"! mostcited {label}: {e}", file=sys.stderr)
            mostcited[label] = []
            continue
        qwords = [w for w in re.findall(r"[a-z0-9]{3,}", query.lower())]
        strict = []
        for w in data.get("results", []):
            title = clean_title(w.get("title"))
            key = (w.get("doi") or title).strip().lower()
            if not title or key in seen_m:
                continue
            src = (w.get("primary_location") or {}).get("source") or {}
            venue = (src.get("display_name") or "").strip()
            if not venue or venue.lower().startswith(("zenodo", "figshare", "ssrn")):
                continue
            seen_m.add(key)
            paper = {
                "title": title, "authors": apa_authors(w.get("authorships", [])),
                "year": w.get("publication_year"), "venue": venue,
                "url": w.get("doi") or w.get("id"), "cites": w.get("cited_by_count", 0),
                "topic": label,
            }
            paper.update(quality(w, scimago))   # FWCI·백분위·저널 분위(Q)·SJR
            arr.append(paper)
            tl = title.lower()
            if qwords and all(qw in tl for qw in qwords):   # 제목에 키워드 전부 포함 = 확실히 주제
                strict.append(paper)
        pick = strict if strict else arr                    # 제목에 키워드 든 게 있으면 그것만(정밀)
        pick.sort(key=lambda p: p["cites"], reverse=True)
        mostcited[label] = pick[:6]

    # 토픽별 OpenAlex 링크: 학회/저널이면 그 source의 works 페이지, 그 외는 검색어 검색
    oa_map = {}
    for _lab, _q, _e in topics:
        if _q.startswith("venue:"):
            oa_map[_lab] = "https://openalex.org/works?filter=primary_location.source.id:" + _q[6:].strip()
        elif _q.startswith("s2:"):
            oa_map[_lab] = "https://www.semanticscholar.org/search?q=" + urllib.parse.quote(_q[3:].strip()) + "&sort=pub-date"
        else:
            oa_map[_lab] = "https://openalex.org/works?filter=default.search:" + urllib.parse.quote(_q, safe="")

    # 누적 병합: 기존 newest.json(prev, 위에서 로드)에 이번에 받은 fresh를 병합해 '월별로 계속
    # 쌓이게' 한다. 색인 지연으로 다음 달에 뒤늦게 뜨는 전달 논문도 겹침 윈도우 덕에 추가된다.
    # 지난달 데이터는 절대 지우지 않는다. (전체갱신 반기엔 fresh가 전 기간이라 지표가 새로고침된다)
    def _nkey(p):
        return (p.get("url") or p.get("title") or "").strip().lower()
    merged = {}
    for p in prev:                       # 먼저 기존(누적) 논문을 넣고
        k = _nkey(p)
        if not k:
            continue
        p.setdefault("added", p.get("date"))   # 최초 관측일 백필: 기존분은 발간일로(신규 표시 안 함)
        merged[k] = p
    for p in fresh:                      # 새로 받은 것으로 덮어써 최신값(cites 등) 반영
        k = _nkey(p)
        if not k:
            continue
        # added = '우리가 처음 본 날'. 발간일이 지난달이어도 이번에 처음 색인됐으면 오늘이 된다
        # → 프런트에서 '방금 추가됨(NEW)'을 발간일과 무관하게 표시할 수 있다.
        p["added"] = merged[k]["added"] if k in merged else today
        merged[k] = p
    newest = sorted(merged.values(), key=lambda p: p.get("date", ""), reverse=True)[:2000]

    # 이번 fetch가 통째로 비고(API 오류) mostcited도 비면 기존 파일을 건드리지 않는다.
    if not fresh and not any(mostcited.values()) and NEWEST.exists():
        print("! fetch 비어있음(OpenAlex 오류 추정) — 기존 newest.json 유지", file=sys.stderr)
    else:
        NEWEST.write_text(json.dumps({
            "generated": today,
            "last_full": today if is_full else last_full,     # 마지막 전체 재fetch일(반기 판정용)
            "topics": [label for label, _q, _e in topics],   # 탭 순서(config 순)
            "venues": [label for label, _q, _e in topics if _q.startswith("venue:") or _q.startswith("s2:")],   # 학회/저널 토픽(구분선 아래 배치)
            "em": {label: em for label, _q, em in topics if em},   # 토픽별 Emergent Mind URL
            "oa": oa_map,                                            # 토픽별 OpenAlex 링크(학회=source, 그 외=검색어)
            "papers": newest,
            "mostcited": mostcited,                      # 키워드별 전기간 피인용 상위
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        ndays = len({p["date"] for p in newest})
        print(f"✓ newest: {len(newest)} papers over {ndays} publication days")

    # ── 팔로우 학자들의 최신 논문 → scholars.json (Google Scholar via SerpAPI) ──
    scholars_list = parse_topics(cfg.get("scholars", ""))   # "표시명 | scholar user id"
    serp_key = os.environ.get("SERPAPI_KEY")
    if not serp_key:
        print("· SERPAPI_KEY 없음 — scholars.json 유지(키 있는 Action에서 채워짐).", file=sys.stderr)
    else:
        per_scholar = int(cfg.get("per_scholar", 5))
        sresult = {"generated": today, "source": "Google Scholar", "scholars": []}
        def _mk(a):
            cb = a.get("cited_by") or {}
            return {"title": clean_title(a.get("title")),
                    "authors": (a.get("authors") or "").strip(),
                    "year": a.get("year") or "",
                    "venue": (a.get("publication") or "").strip(),
                    "url": a.get("link") or "",
                    "cites": cb.get("value") or 0}

        def _yr(v):
            try:
                return int(str(v)[:4])
            except Exception:
                return 0

        for name, uid, _ in scholars_list:
            blk = {"name": name, "id": uid, "papers": [], "recent": []}
            try:
                data = fetch_scholar(uid, serp_key, per_scholar)                   # cited by(인용순)
                data_r = fetch_scholar(uid, serp_key, per_scholar, sort="pubdate") # 최근순
            except Exception as e:
                print(f"! scholar {name}: {e}", file=sys.stderr)
                sresult["scholars"].append(blk)
                continue
            blk["photo"] = ((data.get("author") or {}).get("thumbnail") or "")     # SerpAPI 저자 사진(안정적 URL)
            blk["papers"] = [_mk(a) for a in (data.get("articles") or [])[:per_scholar]]
            blk["papers"].sort(key=lambda p: p.get("cites") or 0, reverse=True)     # 인용 많은 순 (Most cited)
            blk["recent"] = [_mk(a) for a in (data_r.get("articles") or [])[:per_scholar]]
            blk["recent"].sort(key=lambda p: _yr(p.get("year")), reverse=True)      # 최근 발간 순 (Recent)
            sresult["scholars"].append(blk)
            print(f"  scholar {name}: {len(blk['papers'])} cited, {len(blk['recent'])} recent")
        SCHOLARS.write_text(json.dumps(sresult, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ wrote {SCHOLARS.relative_to(ROOT)} — {len(sresult['scholars'])} scholars (Google Scholar)")


if __name__ == "__main__":
    main()
