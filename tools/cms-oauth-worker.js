/**
 * Decap CMS ↔ GitHub OAuth proxy — single Cloudflare Worker.
 * Lets the /admin editor log in and commit posts, with no server to run.
 *
 * Deploy: see SETUP-CMS.md. Set these Worker secrets/vars:
 *   GITHUB_CLIENT_ID      (plain var)
 *   GITHUB_CLIENT_SECRET  (secret)
 */
const GH_AUTHORIZE = "https://github.com/login/oauth/authorize";
const GH_TOKEN = "https://github.com/login/oauth/access_token";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const redirectUri = `${url.origin}/callback`;

    // 1) Decap opens /auth → bounce to GitHub's consent screen
    if (url.pathname === "/auth") {
      const state = crypto.randomUUID();
      const auth = new URL(GH_AUTHORIZE);
      auth.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
      auth.searchParams.set("redirect_uri", redirectUri);
      auth.searchParams.set("scope", url.searchParams.get("scope") || "repo");
      auth.searchParams.set("state", state);
      return Response.redirect(auth.toString(), 302);
    }

    // 2) GitHub redirects back to /callback?code=... → exchange for a token
    if (url.pathname === "/callback") {
      const code = url.searchParams.get("code");
      if (!code) return new Response("Missing code", { status: 400 });

      const res = await fetch(GH_TOKEN, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
          redirect_uri: redirectUri,
        }),
      });
      const data = await res.json();
      const ok = !!data.access_token;
      const payload = ok
        ? { token: data.access_token, provider: "github" }
        : { error: data.error || "no_token" };

      // Hand the token back to the CMS window via postMessage
      const body = `<!doctype html><html><body><script>
        (function(){
          function send(){
            window.opener && window.opener.postMessage(
              'authorization:github:${ok ? "success" : "error"}:${JSON.stringify(payload)}',
              '*');
          }
          window.addEventListener('message', send, false);
          send();
          setTimeout(function(){ window.close(); }, 800);
        })();
      </script>${ok ? "Logged in — you can close this window." : "Login failed."}</body></html>`;
      return new Response(body, { headers: { "Content-Type": "text/html" } });
    }

    return new Response("ValleyJin CMS OAuth proxy", { status: 200 });
  },
};
