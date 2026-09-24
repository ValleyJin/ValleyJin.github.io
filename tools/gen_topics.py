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
    """SCImago 저널 랭크 → {'issn':{정규화ISSN:{q,sjr,cats}}, 'title':{저널명소문자:{...}}}.
    ISSN 매칭(논문 카드·venue)과 제목 매칭(Google Scholar 논문의 venue 텍스트)을 모두 지원.
    실패해도(네트워크 등) 빈 맵으로 조용히 진행."""
    m, tmap = {}, {}
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
        return {"issn": m, "title": tmap}
    lines = raw.splitlines()
    if not lines:
        return {"issn": m, "title": tmap}
    header = [h.strip().strip('"') for h in lines[0].split(";")]
    def _idx(name):
        for i, h in enumerate(header):
            if h.lower() == name.lower():
                return i
        return -1
    i_issn, i_q, i_sjr, i_title = _idx("Issn"), _idx("SJR Best Quartile"), _idx("SJR"), _idx("Title")
    if i_issn < 0 or i_q < 0:
        print("! SCImago 헤더 형식 예상과 다름 — 분위 생략", file=sys.stderr)
        return {"issn": m, "title": tmap}
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
        # 카테고리명에 내부 괄호가 있을 수 있다(예: "Physics and Astronomy (miscellaneous) (Q2)")
        cats = [[n.strip(), "Q" + d] for n, d in re.findall(r"([A-Za-z][\w &,./'\-]*(?:\([^)]*\)[\w &,./'\-]*)*?)\s*\(Q([1-4])\)", ln)]
        entry = {"q": q, "sjr": sjr, "cats": cats}
        for iss in c[i_issn].replace(" ", "").split(","):
            k = iss.replace("-", "").upper()
            if k:
                m.setdefault(k, entry)
        if i_title >= 0 and c[i_title]:
            tmap.setdefault(_norm_title(c[i_title]), entry)      # 정규화 제목 → entry
    print(f"· SCImago {len(m)} ISSN / {len(tmap)} title 로드", file=sys.stderr)
    return {"issn": m, "title": tmap}


def _qcat(e):
    """분위(Q)는 분야 상대순위 → 그 Q를 준 카테고리명(같은 Q 여럿이면 첫 번째)."""
    q = (e or {}).get("q")
    for c in (e or {}).get("cats") or []:
        if c[1] == q:
            return c[0]
    return None


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
    issn = (sci or {}).get("issn", {})
    cand = []
    if src.get("issn_l"):
        cand.append(src["issn_l"])
    for i in (src.get("issn") or []):
        cand.append(i)
    for i in cand:
        k = str(i).replace("-", "").replace(" ", "").upper()
        if k in issn:
            out["q"] = issn[k]["q"]
            if issn[k].get("sjr") is not None:
                out["sjr"] = issn[k]["sjr"]
            qc = _qcat(issn[k])
            if qc:
                out["qcat"] = qc
            break
    return out


def _journal_name(pub):
    """Google Scholar publication 텍스트에서 저널명만 추출.
    'International Journal of Modern Physics C 38 (03), 2750027, 2027' → 'International Journal of Modern Physics C'."""
    s = (pub or "").split(",")[0].strip()          # 첫 쉼표 앞 = 저널명 + 볼륨
    s = re.sub(r"\s*\(\d+[^)]*\)\s*$", "", s)       # 끝의 (03) 제거
    s = re.sub(r"\s+\d[\d\s–-]*$", "", s)           # 끝의 볼륨 번호 제거
    return s.strip()


def _norm_title(s):
    s = (s or "").strip().lower()
    s = s.replace("®", "").replace("™", "").replace("©", "")     # 상표기호 제거
    s = s.replace("–", "-").replace("—", "-")                    # 엔/엠 대시 → 하이픈
    s = s.replace(" & ", " and ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip("… .").strip()                               # Scholar가 자른 끝 ellipsis 제거


def _title_cands(nm):
    """저널명 후보들: 원문 + 괄호 안(정식명) + 괄호 밖(약칭).
    'EPL (Europhysics Letters)' → ['epl (europhysics letters)', 'europhysics letters', 'epl']."""
    cands = [nm]
    m = re.search(r"\(([^)]+)\)", nm)
    if m:
        cands.append(_norm_title(m.group(1)))                        # 괄호 안
        cands.append(_norm_title(re.sub(r"\s*\([^)]*\)\s*", " ", nm)))  # 괄호 제거
    out, seen = [], set()
    for c in cands:
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out


def scholar_q(pub, sci):
    """Scholar 논문 venue 텍스트 → 저널 분위(Q)·SJR (SCImago 제목 매칭).
    괄호 약칭/정식명 후보를 모두 시도하고, 정확 일치 실패 시 접두 매칭
    (예: 'Proceedings of the National Academy of Sciences' ↔ SCImago '…of the United States of America')."""
    tmap = (sci or {}).get("title", {})
    if not tmap:
        return {}
    for nm in _title_cands(_norm_title(_journal_name(pub))):
        e = tmap.get(nm)
        if not e and len(nm) >= 16:             # 접두 폴백(너무 짧은 이름은 오매칭 방지)
            for t, v in tmap.items():
                if t.startswith(nm) or nm.startswith(t):
                    e = v
                    break
        if e:
            out = {"q": e["q"]}
            if e.get("sjr") is not None:
                out["sjr"] = e["sjr"]
            qc = _qcat(e)
            if qc:
                out["qcat"] = qc
            return out
    return {}


CORE_URL = "http://portal.core.edu.au/conf-ranks/?search=&by=all&source=all&sort=arank&do=Export"


def load_core():
    """CORE 학회 랭킹 → {'acr':{약칭:등급}, 'title':{제목:등급}}. 학회는 Q1~Q4 대신 A*/A/B/C.
    같은 학회의 여러 CORE 판(연도) 중 최신을 채택. 실패 시 빈 맵."""
    import csv, io
    acr, ttl, ay, ty = {}, {}, {}, {}
    try:
        req = urllib.request.Request(CORE_URL, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
        raw = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"! CORE 로드 실패(학회 등급 생략): {e}", file=sys.stderr)
        return {"acr": acr, "title": ttl}
    for r in csv.reader(io.StringIO(raw)):
        if len(r) < 5:
            continue
        title, a, source, rank = r[1].strip(), r[2].strip(), r[3], r[4].strip()
        if rank not in ("A*", "A", "B", "C"):
            continue
        mo = re.search(r"(\d{4})", source or "")
        yr = int(mo.group(1)) if mo else 0
        ak = a.lower()
        if ak and ay.get(ak, -1) < yr:
            ay[ak] = yr; acr[ak] = rank
        tk = re.sub(r"\s+", " ", re.sub(r"\s*\(.*?\)\s*", " ", title)).strip().lower()
        if tk and ty.get(tk, -1) < yr:
            ty[tk] = yr; ttl[tk] = rank
    print(f"· CORE {len(acr)} acronym / {len(ttl)} title 로드", file=sys.stderr)
    return {"acr": acr, "title": ttl}


def _norm_conf(s):
    s = re.sub(r"\s*\(.*?\)\s*", " ", s or "").strip().lower()
    s = re.sub(r"^(proceedings of (the )?|the )", "", s)
    return re.sub(r"\s+", " ", s).strip()


# 정식 철자명이 표기마다 다른 대형 학회 → 약칭(고유 핵심구). 잘못된 등급 방지 위해
# 'systems'까지 포함한 정밀 구문만(ICONIP 'neural information processing'과 구분).
CONF_PHRASE = {
    "neural information processing systems": "neurips",
    "international conference on machine learning": "icml",
    "international conference on learning representations": "iclr",
    "computer vision and pattern recognition": "cvpr",
    "empirical methods in natural language processing": "emnlp",
    "association for computational linguistics": "acl",
    "knowledge discovery and data mining": "kdd",
    "conference on human factors in computing systems": "chi",
}


def _conf_key(venue):
    """venue → 학회 핵심 명칭. 'Proceedings of the', 'Adjunct', 연도, 서수(36th Annual) 제거.
    Scholar가 끝을 '…'로 자른 경우도 그대로 둬 접두 매칭에 쓴다."""
    s = _norm_title(_journal_name(venue))
    for _ in range(3):
        s = re.sub(r"^(adjunct\s+|proceedings of the\s+|proceedings of\s+|the\s+|\d{4}\s+|\d+(?:st|nd|rd|th)(?:\s+annual)?\s+)", "", s)
    return s.strip()


def conf_rank(venue, core, topic=None):
    """학회 논문 → CORE 등급(A*/A/B/C). 약칭 → 정확명 → (잘림 대응)접두 매칭 → 대형학회 핵심구.
    오매칭(틀린 등급) 방지를 최우선으로 보수적으로 매칭한다."""
    if not core:
        return {}
    acr, ttl = core.get("acr", {}), core.get("title", {})
    for key in (topic, venue):
        if key and key.strip().lower() in acr:
            return {"crank": acr[key.strip().lower()]}
    key = _conf_key(venue)
    if not key:
        return {}
    if key in ttl:
        return {"crank": ttl[key]}
    # 접두 매칭: Scholar가 끝을 자른 경우(‘…User Interface Software and …’)도 CORE 정식명의
    # 접두이면 인정. 양방향 접두 + 최장 매칭으로 유사명 오매칭을 피한다(양쪽 20자 이상).
    best = None
    if len(key) >= 20:
        for t, rank in ttl.items():
            if len(t) >= 20 and (t.startswith(key) or key.startswith(t)):
                if best is None or len(t) > len(best[0]):
                    best = (t, rank)
    if best:
        return {"crank": best[1]}
    # 대형 학회: 표기가 달라도(‘Conference on Neural Information Processing Systems’) 고유 핵심구로 인정.
    # Scholar가 끝을 자른 경우도 위해 구문 앞 30자 부분매칭 허용(구문이 충분히 길어 오매칭 방지).
    for phrase, acro in CONF_PHRASE.items():
        if acro in acr and (phrase in key or phrase[:30] in key):
            return {"crank": acr[acro]}
    return {}


# 등급이 원래 없는 매체 = 의도적 N/A(preprint·워크숍·초록·학위·기관/리포지토리). 이걸 'N/A'로,
# 정상 저널/학회 모양인데 미매칭인 것은 blank로 남겨 '진짜 누락'을 눈에 띄게 한다.
_NA_PAT = re.compile(
    r"(arxiv|preprint|biorxiv|medrxiv|working paper|\bworkshop\b|extended abstract|"
    r"\bthesis\b|dissertation|technical report|\btech report\b|digital commons|knowledge commons|"
    r"\bssrn\b|zenodo|figshare|researchgate|osf\.io|\bhal-\d|\buniversity\b|\binstitute\b|"
    r"\bproquest\b|repository|habilitation)", re.I)


def na_venue(venue):
    """등급이 원래 존재하지 않는 매체인가(의도적 N/A). venue가 없으면(워킹페이퍼) True."""
    v = (venue or "").strip()
    if not v:
        return True
    return bool(_NA_PAT.search(v))


def build_vidx(vmeta):
    """내 토픽 venues(venues.json)를 정규화 제목→배지 인덱스로. 논문 배지 매칭의
    마지막 폴백 — 이미 해결된 내 학회지/저널은 절대 blank로 안 남게."""
    idx = {}
    for lab, v in (vmeta or {}).items():
        b = {}
        if v.get("type") == "journal" and v.get("q"):
            b = {"q": v["q"]}
            if v.get("sjr") is not None:
                b["sjr"] = v["sjr"]
            qc = _qcat({"q": v["q"], "cats": v.get("cats")})
            if qc:
                b["qcat"] = qc
        elif v.get("type") == "conference" and v.get("crank"):
            b = {"crank": v["crank"]}
        if not b:
            continue
        for nm in _title_cands(_norm_title(v.get("name", ""))):
            idx.setdefault(nm, b)
        idx.setdefault(_norm_title(lab), b)   # 라벨(예: 'NeurIPS')도 키로
    return idx


def badge(venue, sci, core, label=None, vidx=None, w=None):
    """논문 1편의 수준 배지(q·sjr·crank·nr)를 결정 — 모든 경로 공통.
    ① quality(ISSN, w 있을 때) ② scholar_q(제목) ③ conf_rank(CORE)
    ④ 내 토픽 venues 조회 ⑤ 그래도 없으면 nr='na'(blank 금지)."""
    out = {}
    if w is not None:
        out.update(quality(w, sci))            # fwci·pct + ISSN 저널 분위
    if "q" not in out:
        out.update(scholar_q(venue, sci))      # 제목 기반 저널 분위(ISSN 없는 S2 소스 등)
    if "q" not in out:
        cr = conf_rank(venue, core, label)
        if cr:
            out.update(cr)
    if "q" not in out and "crank" not in out and vidx:
        for nm in _title_cands(_norm_title(_journal_name(venue))):
            if nm in vidx:
                out.update(vidx[nm]); break
    if "q" not in out and "crank" not in out:
        out["nr"] = "na"                        # 매칭 실패 → N/A (blank 없이 항상 분류)
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


# 내 토픽 venue의 큐레이션 분야(칩 그루핑용). OpenAlex 자동분류는 의도와 어긋남
# (예: TFSC는 자동으로 'Strategy'지만 실제론 미래학 대표지).
_VENUE_GROUP = {
    "NeurIPS": "인공지능", "ICML": "인공지능", "ICLR": "인공지능", "CVPR": "인공지능",
    "Futures": "미래학", "TFSC": "미래학", "FFS": "미래학", "JFS": "미래학", "EJFR": "미래학",
    "TASM": "경영전략", "SMJ": "경영전략", "LRP": "경영전략", "AMJ": "경영전략", "SO": "경영전략",
    "TAR": "회계학", "JAE": "회계학", "JAR": "회계학", "CAR": "회계학", "RAST": "회계학",
}


def _venue_group(label, v):
    """칩 그루핑 분야. 큐레이션 우선, 없으면 OpenAlex field로 추정."""
    if label in _VENUE_GROUP:
        return _VENUE_GROUP[label]
    if v.get("type") == "conference" or v.get("field") == "Computer Science":
        return "인공지능"
    if v.get("sub") == "Accounting":
        return "회계학"
    if v.get("field") == "Decision Sciences":
        return "미래학"
    if v.get("field") == "Business, Management and Accounting":
        return "경영전략"
    return v.get("field") or "기타"


def build_venues(topics, sci, core=None):
    """토픽의 학회/저널별 영향력지수·분야 → venues.json. 저널은 SJR·Q(분야별)·IF·h,
    학회는 h-index·논문수·분야(OpenAlex) + CORE 등급(A*/A/B/C)."""
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
            _issn = (sci or {}).get("issn", {})
            for i in cand:
                k = str(i).replace("-", "").replace(" ", "").upper()
                if k in _issn:
                    sc = _issn[k]; break
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
                          "i10": ss.get("i10_index"),
                          "works": src.get("works_count"), "domain": f.get("domain"),
                          "field": f.get("field"), "sub": f.get("sub")})
            v.update(conf_rank(v.get("name"), core, label))   # CORE 등급(A*/A/B/C)
            out[label] = v
        if label in out:
            out[label]["group"] = _venue_group(label, out[label])   # 칩 그루핑 분야
            print(f"  venue {label}: {out[label].get('type')} q={out[label].get('q')} grp={out[label].get('group')}", file=sys.stderr)
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
    core = load_core()                                         # 학회 A*/A/B/C (CORE)

    # 토픽 학회/저널의 영향력지수·분야 → venues.json (칩 선택 시 표시)
    venues_meta = build_venues(topics, scimago, core)
    if venues_meta:
        VENUES.write_text(json.dumps({"generated": date.today().isoformat(), "venues": venues_meta},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ venues: {len(venues_meta)} venues", file=sys.stderr)
    vidx = build_vidx(venues_meta)    # 내 토픽 venues → 배지 폴백 인덱스

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
            _tp = {
                "title": title,
                "authors": apa_authors(w.get("authorships", [])),
                "year": w.get("publication_year"),
                "venue": venue,
                "url": w.get("doi") or w.get("id"),
                "cites": w.get("cited_by_count", 0),
            }
            _tp.update(badge(venue, scimago, core, label, vidx, w=w))   # 수준 배지
            block["papers"].append(_tp)
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
                _np.update(badge(venue, scimago, core, label, vidx, w=w))   # 수준 배지(q·crank·nr, 폴백 포함)
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
            paper.update(badge(venue, scimago, core, label, vidx, w=w))   # 수준 배지(q·crank·nr, 폴백 포함)
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
            pub = (a.get("publication") or "").strip()
            p = {"title": clean_title(a.get("title")),
                 "authors": (a.get("authors") or "").strip(),
                 "year": a.get("year") or "",
                 "venue": pub,
                 "url": a.get("link") or "",
                 "cites": cb.get("value") or 0}
            p.update(badge(pub, scimago, core, None, vidx))   # 수준 배지(q·crank·nr, 폴백 포함)
            return p

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
