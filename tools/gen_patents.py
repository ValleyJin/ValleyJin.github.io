#!/usr/bin/env python3
"""KIPRIS 오픈API로 발명자(조진삼)의 한국 등록특허 수 → _data/patents.json.

특허는 Scholar/OpenAlex에 없어 KIPRIS(한국특허정보원) API로 발명자명 검색해 집계한다.
환경변수(GitHub Secret): KIPRIS_KEY = KIPRIS 서비스키. PATENT_INVENTOR = 발명자명(기본 조진삼).
키가 없으면 아무것도 하지 않고 기존 파일을 유지한다.
"""
import os, sys, json, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_data" / "patents.json"
KEY = os.environ.get("KIPRIS_KEY")
INVENTOR = (os.environ.get("PATENT_INVENTOR") or "조진삼").strip()
BASE = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/getAdvancedSearch"


def main():
    if not KEY:
        print("· KIPRIS_KEY 없음 — patents.json 유지.", file=sys.stderr)
        return
    q = {"inventor": INVENTOR, "patent": "true", "utility": "false",
         "numOfRows": 1, "pageNo": 1, "ServiceKey": KEY}
    url = BASE + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=60) as r:
        xml = r.read().decode("utf-8", "ignore")
    root = ET.fromstring(xml)
    tc = root.find(".//count/totalCount")
    if tc is None:
        tc = root.find(".//totalCount")
    count = int(tc.text) if (tc is not None and tc.text and tc.text.strip().isdigit()) else None
    print(f"· KIPRIS inventor={INVENTOR} totalCount={count}", file=sys.stderr)
    if count is None:
        print("· 파싱 실패 — 응답 일부:", xml[:400].replace("\n", " "), file=sys.stderr)
        return
    OUT.write_text(json.dumps({"count": count, "inventor": INVENTOR, "source": "KIPRIS"},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ wrote patents.json — {count}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("patents fetch failed, keeping previous:", e, file=sys.stderr)
        sys.exit(0)
