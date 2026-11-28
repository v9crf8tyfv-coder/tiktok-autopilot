#!/usr/bin/env python3
"""Publication AUTOMATIQUE sur YouTube Shorts via l'API officielle (légal, gratuit).

Modes :
  --auth              première connexion OAuth (ouvre le navigateur, 1 seule fois)
  --exchange <url>    variante : colle l'URL localhost de redirection pour finir l'auth
  <video> <caption>   upload la vidéo en Short public sur ta chaîne

Prérequis gratuits (voir README) :
  1. Projet Google Cloud + API "YouTube Data API v3" activée
  2. Identifiants OAuth "Desktop app" → YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET (config.env / secrets)
  3. T'ajouter en "Test user" sur l'écran de consentement OAuth

Quota gratuit : 10 000 unités/jour, un upload = ~1600 → ~6 vidéos/jour gratuites. On en fait 3.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "data", "youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
REDIRECT = "http://localhost:8766/"


def load_env():
    env = dict(os.environ)
    p = os.path.join(ROOT, "config.env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def client_config(env):
    return {"installed": {
        "client_id": env.get("YOUTUBE_CLIENT_ID", ""),
        "client_secret": env.get("YOUTUBE_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT],
    }}


def auth_flow(env):
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not (env.get("YOUTUBE_CLIENT_ID") and env.get("YOUTUBE_CLIENT_SECRET")):
        print("Renseigne YOUTUBE_CLIENT_ID et YOUTUBE_CLIENT_SECRET dans config.env d'abord.")
        return 1
    flow = InstalledAppFlow.from_client_config(client_config(env), SCOPES)
    # ouvre le navigateur et récupère le code automatiquement (1 clic "Autoriser")
    creds = flow.run_local_server(port=8766, prompt="consent", open_browser=True)
    _save(creds)
    print("\n✅ Chaîne YouTube connectée ! Jeton enregistré.")
    return 0


def print_auth_url(env):
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(client_config(env), SCOPES, redirect_uri=REDIRECT)
    url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print(url)
    return 0


def exchange(env, url_or_code):
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(client_config(env), SCOPES, redirect_uri=REDIRECT)
    flow.fetch_token(authorization_response=url_or_code) if url_or_code.startswith("http") \
        else flow.fetch_token(code=url_or_code)
    _save(flow.credentials)
    print("✅ Connecté. Jeton enregistré.")
    return 0


def _save(creds):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    json.dump({
        "refresh_token": creds.refresh_token,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
    }, open(TOKEN_FILE, "w"))


def _credentials(env):
    from google.oauth2.credentials import Credentials
    rt = env.get("YOUTUBE_REFRESH_TOKEN")
    cid = env.get("YOUTUBE_CLIENT_ID")
    cs = env.get("YOUTUBE_CLIENT_SECRET")
    if (not rt) and os.path.exists(TOKEN_FILE):
        tok = json.load(open(TOKEN_FILE))
        rt = tok.get("refresh_token"); cid = cid or tok.get("client_id"); cs = cs or tok.get("client_secret")
    if not (rt and cid and cs):
        return None
    return Credentials(None, refresh_token=rt, client_id=cid, client_secret=cs,
                       token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)


def _title_desc(caption):
    lines = [l for l in caption.split("\n") if l.strip()]
    title = (lines[0] if lines else "Short du jour")[:95]
    tags = [l for l in lines if l.strip().startswith("#")]
    desc = caption + "\n\n#Shorts"
    hashtags = [re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", h) for l in tags for h in l.split()][:12]
    if "#shorts" not in title.lower():
        title = (title + " #Shorts")[:100]
    return title, desc, hashtags


def upload(env, video, caption):
    creds = _credentials(env)
    if creds is None:
        print("YouTube non connecté (lance --auth). Upload ignoré.")
        return 0
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    title, desc, tags = _title_desc(caption)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {"title": title, "description": desc, "tags": tags, "categoryId": "24"},
        "status": {"privacyStatus": env.get("YOUTUBE_PRIVACY", "public"),
                   "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp.get("id")
    print("✅ Publié sur YouTube Shorts : https://youtube.com/shorts/%s" % vid)
    return 0


def main():
    env = load_env()
    a = sys.argv[1:]
    if a and a[0] == "--auth":
        return auth_flow(env)
    if a and a[0] == "--url":
        return print_auth_url(env)
    if len(a) >= 2 and a[0] == "--exchange":
        return exchange(env, a[1])
    if len(a) < 2:
        print(__doc__)
        return 1
    return upload(env, a[0], a[1])


if __name__ == "__main__":
    sys.exit(main())
