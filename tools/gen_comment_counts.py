#!/usr/bin/env python3
"""giscus(GitHub Discussions)의 글별 댓글 수를 집계 → _data/comment_counts.json.
giscus는 data-mapping=pathname 이라 각 Discussion의 title = 글의 pathname(post.url).
GitHub GraphQL은 인증이 필요하므로 GitHub Actions의 GITHUB_TOKEN으로 빌드 시 실행."""
import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_data" / "comment_counts.json"
OWNER, NAME = "ValleyJin", "ValleyJin.github.io"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

QUERY = """
query($owner:String!,$name:String!,$cursor:String){
  repository(owner:$owner,name:$name){
    discussions(first:100, after:$cursor){
      nodes{ title comments{ totalCount } }
      pageInfo{ hasNextPage endCursor }
    }
  }
}
"""


def gql(cursor=None):
    body = json.dumps({"query": QUERY, "variables": {"owner": OWNER, "name": NAME, "cursor": cursor}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, method="POST", headers={
        "Authorization": "bearer " + TOKEN,
        "User-Agent": "valleyjin-comment-counts",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def main():
    if not TOKEN:
        print("! GITHUB_TOKEN 없음 — 스킵(기존 파일 유지)", file=sys.stderr)
        return
    counts, cursor = {}, None
    try:
        while True:
            d = gql(cursor)
            if "errors" in d:
                print("! GraphQL 오류:", d["errors"], file=sys.stderr); return
            disc = d["data"]["repository"]["discussions"]
            for n in disc["nodes"]:
                title = (n.get("title") or "").strip()
                c = (n.get("comments") or {}).get("totalCount", 0)
                if title:
                    counts[title] = c            # title = pathname (giscus pathname 매핑)
            if disc["pageInfo"]["hasNextPage"]:
                cursor = disc["pageInfo"]["endCursor"]
            else:
                break
    except Exception as e:
        print(f"! Discussions 집계 실패: {e}", file=sys.stderr)
        return
    OUT.write_text(json.dumps(counts, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"· comment_counts.json {len(counts)} discussions", file=sys.stderr)


if __name__ == "__main__":
    main()
