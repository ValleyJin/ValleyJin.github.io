#!/usr/bin/env python3
"""Google Scholar 알림 이메일 → _data/scholar_alerts.json.

Scholar는 공식 API가 없어 팔로우/인용/관련 논문 알림을 이메일로만 보낸다
(발신: scholaralerts-noreply@google.com). Gmail IMAP으로 그 메일을 읽어
논문 제목·링크·저자·스니펫을 파싱해 사이트(Following 탭)에서 보여준다.

환경변수(GitHub Secret):
  GMAIL_USER          = 알림을 받는 Gmail 주소
  GMAIL_APP_PASSWORD  = Gmail 앱 비밀번호(2단계 인증 후 발급, 16자리)
키가 없으면 아무것도 하지 않고(기존 파일 유지) 조용히 종료한다.
"""
import os, sys, re, json, html, imaplib, email, urllib.parse
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import date, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

OUT = Path(__file__).resolve().parent.parent / "_data" / "scholar_alerts.json"
SENDER = "scholaralerts-noreply@google.com"
MAX_MSGS = 25       # 최근 알림 메일 수
MAX_ITEMS = 40      # 표시 논문 상한


def _decode(s):
    if not s:
        return ""
    out = []
    for part, enc in decode_header(s):
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", "ignore"))
        else:
            out.append(part)
    return "".join(out)


def _html_of(msg):
    """멀티파트 메일에서 text/html 본문을 뽑는다."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                except Exception:
                    continue
        return ""
    if msg.get_content_type() == "text/html":
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "ignore")
    return ""


def _date(msg):
    """메일 Date 헤더 → KST 기준 YYYY-MM-DD. 실패 시 오늘(KST)."""
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).date().isoformat()
    except Exception:
        from datetime import datetime
        return datetime.now(KST).date().isoformat()


def _scholar(subject):
    """제목에서 학자명 추출. 'Joon Sung Park님의 자료가…' / 'Joon Sung Park - 새로운…'.
    'Min-Soo Kim'처럼 이름 안의 하이픈은 구분자로 오인 안 하도록 ' - '(공백 하이픈 공백)만 구분자로."""
    s = (subject or "").strip()
    m = re.match(r"^(.+?)(?:님(?:의)?|\s+[-–—]\s+)", s)
    return m.group(1).strip() if m else ""


def _kind(subject):
    s = (subject or "").lower()
    if "citation" in s or "cited by" in s or "인용" in s:
        return "Citation"
    if "related" in s or "관련" in s or "서지정보" in s:
        return "Related"
    return "New"


def _clean(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()


def _real_url(u):
    u = html.unescape(u or "")
    m = re.search(r"scholar_url\?url=([^&]+)", u)
    if m:
        return urllib.parse.unquote(m.group(1))
    return u


def parse_alert(html_body, kind):
    """Scholar 알림 HTML → [{title,url,authors,snippet,kind}]. h3 블록 단위."""
    items = []
    blocks = re.split(r"<h3", html_body)[1:]
    for b in blocks:
        b = "<h3" + b
        mt = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not mt:
            continue
        title = _clean(mt.group(2))
        if not title or len(title) < 6:
            continue
        url = _real_url(mt.group(1))
        ma = re.search(r"#006621[^>]*>(.*?)</", b, re.S)       # 저자·저널 줄(초록색)
        authors = _clean(ma.group(1)) if ma else ""
        ms = re.search(r'gse_alrt_sni[^>]*>(.*?)</div>', b, re.S)   # 스니펫
        snippet = _clean(ms.group(1)) if ms else ""
        items.append({"title": title, "url": url, "authors": authors,
                      "snippet": snippet, "kind": kind})
    return items


def main():
    user = os.environ.get("GMAIL_USER") or "scholararticleforwarding@gmail.com"
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        print("· GMAIL_USER/GMAIL_APP_PASSWORD 없음 — scholar_alerts.json 유지.", file=sys.stderr)
        return

    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(user, pw)
    M.select("INBOX")
    typ, data = M.search(None, '(FROM "%s")' % SENDER)
    ids = data[0].split()
    print("· INBOX Scholar 메일 %d통 (FROM %s)" % (len(ids), SENDER), file=sys.stderr)
    if not ids:
        # 발신 주소가 다를 수 있으니 'scholar' 포함 발신도 시도
        typ, data = M.search(None, '(FROM "scholar")')
        ids = data[0].split()
        print("· FROM scholar 재검색: %d통" % len(ids), file=sys.stderr)
        if not ids:
            M.logout()
            return

    seen, items = set(), []
    for num in reversed(ids[-MAX_MSGS:]):
        typ, msg_data = M.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        subject = _decode(msg.get("Subject"))
        kind = _kind(subject)
        sch = _scholar(subject)
        dt = _date(msg)
        html_body = _html_of(msg)
        got = parse_alert(html_body, kind)
        for it in got:
            it["scholar"] = sch
            it["date"] = dt
        print("  · [%s] html=%d h3=%d a=%d parsed=%d" % (
            subject[:45], len(html_body), html_body.count("<h3"), html_body.count("<a "), len(got)), file=sys.stderr)
        for it in got:
            key = (it["title"].lower()[:80])
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    M.logout()

    items = items[:MAX_ITEMS]

    # 수준 배지(Q·SJR·qcat·N/A) 부여 — 다른 논문 리스트와 표현 통일. venue는 authors의 "… - Venue, Year"에서 추출.
    try:
        import importlib.util
        _here = Path(__file__).resolve().parent
        _spec = importlib.util.spec_from_file_location("gt", str(_here / "gen_topics.py"))
        gt = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(gt)
        _sci, _core = gt.load_scimago(), gt.load_core()
        _vmeta = json.loads((_here.parent / "_data" / "venues.json").read_text(encoding="utf-8")).get("venues", {})
        _vidx = gt.build_vidx(_vmeta)
        def _venue(it):
            au = (it.get("authors") or "").replace("\xa0", " ")
            m = re.split(r"\s[-–—]\s", au)
            return m[-1].strip() if len(m) > 1 else ""
        for it in items:
            it.update(gt.badge(_venue(it), _sci, _core, None, _vidx, w=None))
    except Exception as e:
        print("! alert badge skipped: %s" % e, file=sys.stderr)

    OUT.write_text(json.dumps({"generated": date.today().isoformat(),
                               "source": "Google Scholar alerts (email)",
                               "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✓ wrote %s — %d alert items" % (OUT.name, len(items)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("scholar alerts fetch failed, keeping previous:", e, file=sys.stderr)
        sys.exit(0)
