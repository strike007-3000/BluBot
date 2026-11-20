"""Interactive credential checker: python scripts/check_tokens.py
Pick a platform, paste the secret (hidden), see whether it is accepted. Nothing is posted or stored."""
import os
import sys
from getpass import getpass

import requests

T = 15


def ask(label, env, secret=False):
    """Prompt; Enter keeps the env value if set. Secrets are hidden."""
    cur = os.getenv(env, "")
    hint = " [Enter = use $%s]" % env if cur else ""
    v = (getpass if secret else input)(f"{label}{hint}: ").strip()
    return v or cur


def bluesky():
    handle = ask("Bluesky handle (BSKY_HANDLE)", "BSKY_HANDLE")
    pw = ask("Bluesky app password (BSKY_APP_PASSWORD)", "BSKY_APP_PASSWORD", True)
    r = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                      json={"identifier": handle, "password": pw}, timeout=T)
    if r.ok:
        return True, f"logged in as {r.json().get('handle')}"
    return False, f"{r.status_code} {r.text[:200]}"


def mastodon():
    base = ask("Mastodon base URL (MASTODON_BASE_URL)", "MASTODON_BASE_URL").rstrip("/")
    tok = ask("Mastodon access token (MASTODON_ACCESS_TOKEN)", "MASTODON_ACCESS_TOKEN", True)
    if not base.startswith("https://"):
        return False, f"base URL must start with https:// (got {base!r})"
    h = {"Authorization": f"Bearer {tok}"}
    r = requests.get(f"{base}/api/v1/accounts/verify_credentials", headers=h, timeout=T)
    if not r.ok:
        return False, f"{r.status_code} {r.text[:200]}"
    msg = f"valid, account @{r.json().get('acct')}"
    s = requests.get(f"{base}/api/v1/apps/verify_credentials", headers=h, timeout=T)
    scopes = s.json().get("scopes") if s.ok else None
    if not scopes:
        return False, msg + " -> could not read token scopes, cannot confirm write:statuses"
    msg += f", scopes: {' '.join(scopes) if isinstance(scopes, list) else scopes}"
    if not any(x in ("write", "write:statuses") for x in scopes):
        return False, msg + " -> MISSING write:statuses, posting will fail"
    return True, msg


def threads():
    tok = ask("Threads access token (THREADS_ACCESS_TOKEN)", "THREADS_ACCESS_TOKEN", True)
    uid = ask("Threads user id (THREADS_USER_ID)", "THREADS_USER_ID")
    r = requests.get("https://graph.threads.net/v1.0/me",
                     params={"fields": "id,username", "access_token": tok}, timeout=T)
    if not r.ok:
        return False, f"{r.status_code} {r.text[:200]}"
    d = r.json()
    if uid and str(d.get("id")) != uid:
        return False, f"token is valid for id {d.get('id')} (@{d.get('username')}) but THREADS_USER_ID is {uid}"
    return True, f"valid, @{d.get('username')} (id {d.get('id')})"


def _get(url, tok, header="Authorization", prefix="Bearer ", **kw):
    r = requests.get(url, headers={header: prefix + tok}, timeout=T, **kw)
    return r, ("" if r.ok else f"{r.status_code} {r.text[:200]}")


def gemini():
    r, err = _get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
                  ask("Gemini key (GEMINI_KEY)", "GEMINI_KEY", True), "x-goog-api-key", "")
    return r.ok, err or "key accepted"


def nvidia():
    r, err = _get("https://integrate.api.nvidia.com/v1/models", ask("NVIDIA key (NVIDIA_KEY)", "NVIDIA_KEY", True))
    return r.ok, err or "key accepted"


def telegram():
    tok = ask("Telegram bot token (TELEGRAM_BOT_TOKEN)", "TELEGRAM_BOT_TOKEN", True)
    uid = ask("Telegram user id (TELEGRAM_USER_ID)", "TELEGRAM_USER_ID")
    r = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=T)
    if not r.ok:
        return False, f"{r.status_code} {r.text[:200]}"
    msg = f"bot @{r.json()['result'].get('username')}"
    c = requests.get(f"https://api.telegram.org/bot{tok}/getChat", params={"chat_id": uid}, timeout=T)
    if not c.ok:
        return False, msg + f" valid, but cannot reach user id {uid} (wrong id, or you never pressed Start on the bot)"
    return True, msg + f" valid, can reach user id {uid}"


def gist():
    tok = ask("GitHub gist token (GIST_TOKEN)", "GIST_TOKEN", True)
    gid = ask("Gist id (GIST_ID)", "GIST_ID")
    r, err = _get(f"https://api.github.com/gists/{gid}", tok)
    if not r.ok:
        return False, err
    # Prod PATCHes the gist, so prove write access: add a temp file, then delete it.
    url, h, f = f"https://api.github.com/gists/{gid}", {"Authorization": f"Bearer {tok}"}, "blubot_token_check.json"
    w = requests.patch(url, headers=h, json={"files": {f: {"content": "{}"}}}, timeout=T)
    if not w.ok:
        return False, f"readable but NOT writable: {w.status_code} {w.text[:200]}"
    requests.patch(url, headers=h, json={"files": {f: None}}, timeout=T)
    return True, f"gist readable and writable, owner {r.json().get('owner', {}).get('login')}"


def cloudflare():
    tok = ask("Cloudflare API token (CLOUDFLARE_API_TOKEN)", "CLOUDFLARE_API_TOKEN", True)
    acct = ask("Cloudflare account id (CLOUDFLARE_ACCOUNT_ID)", "CLOUDFLARE_ACCOUNT_ID")
    # Account-owned tokens verify here; user-owned tokens use /user/tokens/verify instead.
    r, err = _get(f"https://api.cloudflare.com/client/v4/accounts/{acct}/tokens/verify", tok)
    return r.ok, err or f"token status: {r.json().get('result', {}).get('status')}"


def huggingface():
    r, err = _get("https://huggingface.co/api/whoami-v2", ask("Hugging Face key (HUGGINGFACE_API_KEY)", "HUGGINGFACE_API_KEY", True))
    return r.ok, err or f"valid, user {r.json().get('name')}"


def repo_token():
    tok = ask("GitHub repo token (REPO_TOKEN)", "REPO_TOKEN", True)
    repo = input("Repo [strike007-3000/BluBot]: ").strip() or "strike007-3000/BluBot"
    r, err = _get(f"https://api.github.com/repos/{repo}", tok)
    if not r.ok:
        return False, err
    push = r.json().get("permissions", {}).get("push")
    return bool(push), f"repo readable, push access: {push}" + ("" if push else " -> cannot push/open PRs")


MENU = {
    "1": ("Bluesky", bluesky), "2": ("Threads", threads), "3": ("Mastodon", mastodon),
    "4": ("Gemini", gemini), "5": ("NVIDIA", nvidia), "6": ("Telegram", telegram),
    "7": ("Gist", gist), "8": ("Cloudflare", cloudflare), "9": ("Hugging Face", huggingface), "10": ("Repo token", repo_token),
}


if __name__ == "__main__":
    while True:
        print("\n" + "\n".join(f"{k}) {n}" for k, (n, _) in MENU.items()) + "\nq) quit")
        c = input("> ").strip().lower()
        if c in ("q", ""):
            sys.exit(0)
        if c not in MENU:
            continue
        name, fn = MENU[c]
        try:
            ok, msg = fn()
        except requests.RequestException as e:
            ok, msg = False, f"network error: {e.__class__.__name__}"
        print(f"{'✅' if ok else '❌'} {name}: {msg}")
