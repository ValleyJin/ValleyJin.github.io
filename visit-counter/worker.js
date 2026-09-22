/**
 * valleyjin-visit-counter — 정적 사이트(GitHub Pages)용 방문 카운터.
 * Cloudflare Workers + KV. 쿠키 없음, 개인정보 수집 없음(총 방문 수만 센다).
 *
 * 엔드포인트
 *   GET /hit    → 카운트 +1 후 { count } 반환 (세션당 1회는 클라이언트가 제어)
 *   GET /count  → 증가 없이 현재 { count } 반환
 *
 * KV 바인딩: COUNTER (wrangler.toml 참고)
 */
const ALLOW = "https://valleyjin.github.io";

function cors(extra = {}) {
  return {
    "Access-Control-Allow-Origin": ALLOW,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Cache-Control": "no-store",
    ...extra,
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: cors() });

    const KEY = "total";
    if (url.pathname === "/hit") {
      const n = (parseInt((await env.COUNTER.get(KEY)) || "0", 10) || 0) + 1;
      await env.COUNTER.put(KEY, String(n));
      return json({ count: n });
    }
    if (url.pathname === "/count") {
      const n = parseInt((await env.COUNTER.get(KEY)) || "0", 10) || 0;
      return json({ count: n });
    }
    return new Response("valleyjin-visit-counter", { headers: cors() });

    function json(obj) {
      return new Response(JSON.stringify(obj), {
        headers: cors({ "content-type": "application/json" }),
      });
    }
  },
};
