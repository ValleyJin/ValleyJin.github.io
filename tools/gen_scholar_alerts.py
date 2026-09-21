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
from datetime import date
from pathlib import Path

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


def _kind(subject):
    s = (subject or "").lower()
    if "citations" in s or "cited by" in s:
        return "Citation"
    if "related" in s:
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
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        print("· GMAIL_USER/GMAIL_APP_PASSWORD 없음 — scholar_alerts.json 유지.", file=sys.stderr)
        return

    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(user, pw)
    M.select("INBOX")
    typ, data = M.search(None, '(FROM "%s")' % SENDER)
    ids = data[0].split()
    if not ids:
        print("· Scholar 알림 메일 없음.", file=sys.stderr)
        M.logout()
        return

    seen, items = set(), []
    for num in reversed(ids[-MAX_MSGS:]):
        typ, msg_data = M.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        subject = _decode(msg.get("Subject"))
        kind = _kind(subject)
        for it in parse_alert(_html_of(msg), kind):
            key = (it["title"].lower()[:80])
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    M.logout()

    items = items[:MAX_ITEMS]
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
