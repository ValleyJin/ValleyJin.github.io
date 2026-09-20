/**
 * Decap CMS <-> GitHub OAuth proxy (Cloudflare Worker).
 * Lets valleyjin.github.io/admin log in and commit posts, no server to run.
 * Secrets: GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
 */
export default {
  async fetch(req, env) {
    const u = new URL(req.url);

    // 1) Decap opens /auth -> bounce to GitHub's consent screen
    if (u.pathname === "/auth") {
      const a = new URL("https://github.com/login/oauth/authorize");
      a.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
      a.searchParams.set("redirect_uri", u.origin + "/callback");
      a.searchParams.set("scope", u.searchParams.get("scope") || "repo");
      a.searchParams.set("state", crypto.randomUUID());
      return Response.redirect(a.toString(), 302);
    }

    // 2) GitHub redirects back to /callback?code=... -> exchange for a token
    if (u.pathname === "/callback") {
      const code = u.searchParams.get("code");
      if (!code) return new Response("Missing code", { status: 400 });
      const data = await fetch("https://github.com/login/oauth/access_token", {
        method: "POST",
        headers: { "content-type": "application/json", "accept": "application/json" },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code: code,
          redirect_uri: u.origin + "/callback"
        })
      }).then(function (r) { return r.json(); });

      if (!data.access_token) {
        const detail = JSON.stringify(data).replace(/</g, "&lt;");
        return new Response(
          "<!doctype html><body><h3>GitHub token exchange failed</h3><pre>" + detail + "</pre></body>",
          { headers: { "content-type": "text/html" } }
        );
      }

      const message = "authorization:github:success:" +
        JSON.stringify({ token: data.access_token, provider: "github" });
      // Decap handshake: announce until the CMS replies, then post the token
      // back to the CMS origin. Guard on the exact echo so stray messages can't
      // consume the handshake.
      const script =
        "(function(){var sent=false;" +
        "function receive(e){if(sent)return;if(e.data!=='authorizing:github')return;sent=true;" +
        "window.opener.postMessage(" + JSON.stringify(message) + ",e.origin);" +
        "document.body.textContent='Done. You can close this window.';}" +
        "window.addEventListener('message',receive,false);var n=0;" +
        "var t=setInterval(function(){if(sent||n++>40){clearInterval(t);return;}" +
        "if(window.opener){window.opener.postMessage('authorizing:github','*');}},250);})();";
      const tagOpen = "<scr" + "ipt>";
      const tagClose = "</scr" + "ipt>";
      const page = "<!doctype html><body>Logging in..." + tagOpen + script + tagClose + "</body>";
      return new Response(page, { headers: { "content-type": "text/html" } });
    }

    return new Response("OAuth proxy running", { status: 200 });
  }
};
