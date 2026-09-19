# Enabling the /admin writing form (one-time, ~10 min)

The site and the editor at `https://valleyjin.github.io/admin/` are already built.
GitHub Pages is static, so the only thing login needs is a tiny OAuth proxy. You deploy it
once (free) and never touch it again.

## Step 1 — Create a GitHub OAuth App
1. https://github.com/settings/developers → **New OAuth App**
2. Application name: `ValleyJin CMS`
3. Homepage URL: `https://valleyjin.github.io`
4. Authorization callback URL: `https://valleyjin-cms-auth.<your>.workers.dev/callback`
   (you'll get the exact Worker URL in Step 2 — come back and paste it)
5. Save. Note the **Client ID** and generate a **Client Secret**.

## Step 2 — Deploy the OAuth proxy (Cloudflare Worker, free)
The Worker code is in `tools/cms-oauth-worker.js`.

```bash
npm i -g wrangler
wrangler login
# from the repo root:
wrangler deploy tools/cms-oauth-worker.js --name valleyjin-cms-auth --compatibility-date 2024-11-01
wrangler secret put GITHUB_CLIENT_SECRET   # paste the client secret
wrangler deploy tools/cms-oauth-worker.js --name valleyjin-cms-auth \
  --var GITHUB_CLIENT_ID:<your-client-id>
```
This prints a URL like `https://valleyjin-cms-auth.<your>.workers.dev`.

## Step 3 — Wire it up
1. Put the real Worker URL into `admin/config.yml` → `backend.base_url`.
2. Put `.../callback` into the OAuth App's callback URL (Step 1.4).
3. Commit. Open `https://valleyjin.github.io/admin/`, click **Login with GitHub**,
   write a post, hit **Publish**. It commits to `_posts/` and the site rebuilds in ~1 min.

That's it — after this you write daily from the browser (phone included), no terminal.

---

### Alternative with zero Cloudflare
If you'd rather not run a Worker, host the same site on **Netlify** (free) and switch
`admin/config.yml` to `backend: { name: git-gateway }` + enable Netlify Identity. The
trade-off is the site moves off the `valleyjin.github.io` domain. The Worker path above
keeps your github.io URL.
