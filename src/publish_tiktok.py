#!/usr/bin/env python3
"""Publication TikTok via l'API OFFICIELLE Content Posting (open.tiktokapis.com).

Aucun contournement : uniquement l'API développeur officielle de TikTok.

Modes :
  --auth              première connexion OAuth (affiche l'URL à ouvrir, colle le code)
  <video> <caption>   publie la vidéo (ou la met en brouillon selon TIKTOK_MODE)

Prérequis (gratuits) — voir README section "Publication automatique" :
  1. Créer une app sur https://developers.tiktok.com (gratuit)
  2. Activer le produit "Content Posting API" + scope video.publish
  3. Renseigner TIKTOK_CLIENT_KEY et TIKTOK_CLIENT_SECRET dans config.env

Sans clés : repli légal → notification macOS + dossier ouvert, tu postes en 30s
(et tu peux ajouter un son en tendance dans l'app, ce que l'API ne permet pas).
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "data", "tiktok_token.json")
API = "https://open.tiktokapis.com/v2"
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI",
    "https://v9crf8tyfv-coder.github.io/tiktok-autopilot/callback.html",
)


def load_env():
    env = {}
    path = os.path.join(ROOT, "config.env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("TIKTOK_")})
    return env


def notify(title, message):
    if sys.platform != "darwin":
        return  # pas de notification macOS en cloud (Linux)
    subprocess.run(["osascript", "-e",
                    'display notification "%s" with title "%s" sound name "Glass"'
                    % (message.replace('"', "'"), title.replace('"', "'"))])


def fallback(video, caption):
    print("Pas de clés API TikTok : mode semi-automatique.")
    print("Vidéo prête : %s" % video)
    print("Légende : %s" % caption[:120])
    notify("TikTok Autopilot", "Vidéo du jour prête à poster ! 🎬")
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", video])
    return 0


# ------------------------------------------------------------- OAuth

def auth_url(env):
    key = env.get("TIKTOK_CLIENT_KEY")
    return ("https://www.tiktok.com/v2/auth/authorize/?client_key=%s"
            "&scope=video.publish,video.upload&response_type=code&redirect_uri=%s&state=autopilot"
            % (key, urllib.parse.quote(REDIRECT_URI, safe="")))


def auth_flow(env):
    key = env.get("TIKTOK_CLIENT_KEY")
    secret = env.get("TIKTOK_CLIENT_SECRET")
    if not (key and secret):
        print("Renseigne d'abord TIKTOK_CLIENT_KEY et TIKTOK_CLIENT_SECRET dans config.env")
        return 1
    print("1) Ouvre cette URL, connecte-toi avec TON compte et autorise :\n\n%s\n" % auth_url(env))
    print("2) Tu seras redirigé vers une URL localhost (page d'erreur = NORMAL).")
    code = input("3) Colle ici le code (paramètre code=... de l'URL) : ").strip()
    return exchange_code(env, code)


def exchange_code(env, code):
    """Échange le code d'autorisation contre un jeton (utilisable non-interactif)."""
    key = env.get("TIKTOK_CLIENT_KEY")
    secret = env.get("TIKTOK_CLIENT_SECRET")
    code = urllib.parse.unquote(code).split("code=")[-1].split("&")[0].split("*")[0]
    r = requests.post(API + "/oauth/token/", data={
        "client_key": key, "client_secret": secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    tok = r.json()
    if "access_token" not in tok:
        print("Échec : %s" % tok)
        return 1
    tok["obtained_at"] = int(time.time())
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    json.dump(tok, open(TOKEN_FILE, "w"))
    print("✅ Connecté ! Jeton enregistré.")
    print("REFRESH_TOKEN=%s" % tok.get("refresh_token", ""))
    return 0


def get_access_token(env):
    if not os.path.exists(TOKEN_FILE):
        # Cloud (GitHub Actions) : amorçage depuis le secret TIKTOK_REFRESH_TOKEN
        rt = env.get("TIKTOK_REFRESH_TOKEN")
        if not rt:
            return None
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        json.dump({"refresh_token": rt, "obtained_at": 0, "expires_in": 0},
                  open(TOKEN_FILE, "w"))
    tok = json.load(open(TOKEN_FILE))
    age = time.time() - tok.get("obtained_at", 0)
    if age > tok.get("expires_in", 86400) - 600:  # rafraîchir avant expiration
        r = requests.post(API + "/oauth/token/", data={
            "client_key": env["TIKTOK_CLIENT_KEY"],
            "client_secret": env["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        new = r.json()
        if "access_token" not in new:
            print("Rafraîchissement du jeton impossible : %s" % new)
            return None
        new["obtained_at"] = int(time.time())
        json.dump(new, open(TOKEN_FILE, "w"))
        tok = new
    return tok["access_token"]


# ------------------------------------------------------------- Publication

def publish(env, video, caption):
    token = get_access_token(env)
    if token is None:
        return fallback(video, caption)
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    size = os.path.getsize(video)
    mode = env.get("TIKTOK_MODE", "DRAFT").upper()  # DRAFT (brouillon dans l'app) ou DIRECT

    if mode == "DIRECT":
        endpoint, body = "/post/publish/video/init/", {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": env.get("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE"),
                "disable_duet": False, "disable_comment": False, "disable_stitch": False,
            },
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": size, "total_chunk_count": 1},
        }
    else:  # brouillon : la vidéo arrive dans la boîte de réception TikTok, tu valides dans l'app
        endpoint, body = "/post/publish/inbox/video/init/", {
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": size, "total_chunk_count": 1},
        }

    r = requests.post(API + endpoint, headers=headers, json=body, timeout=30)
    data = r.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        print("Erreur init publication : %s" % data)
        return fallback(video, caption)

    upload_url = data["data"]["upload_url"]
    publish_id = data["data"]["publish_id"]
    with open(video, "rb") as f:
        content = f.read()
    up = requests.put(upload_url, data=content, headers={
        "Content-Type": "video/mp4",
        "Content-Range": "bytes 0-%d/%d" % (size - 1, size),
    }, timeout=600)
    if up.status_code not in (200, 201):
        print("Erreur upload : %s %s" % (up.status_code, up.text[:300]))
        return fallback(video, caption)

    # suivi du statut
    for _ in range(30):
        time.sleep(5)
        st = requests.post(API + "/post/publish/status/fetch/", headers=headers,
                           json={"publish_id": publish_id}, timeout=30).json()
        status = st.get("data", {}).get("status", "?")
        print("statut: %s" % status)
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            notify("TikTok Autopilot", "Vidéo envoyée sur TikTok ✅ (%s)" % status)
            print("✅ Publié (%s). En mode brouillon : ouvre TikTok > notifications pour valider.")
            return 0
        if status == "FAILED":
            print("Échec : %s" % st)
            return fallback(video, caption)
    print("Statut indéterminé, vérifie l'app TikTok.")
    return 0


def main():
    env = load_env()
    if len(sys.argv) > 1 and sys.argv[1] == "--auth":
        return auth_flow(env)
    if len(sys.argv) > 1 and sys.argv[1] == "--url":
        print(auth_url(env))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "--exchange":
        return exchange_code(env, sys.argv[2])
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    video, caption = sys.argv[1], sys.argv[2]
    if not (env.get("TIKTOK_CLIENT_KEY") and os.path.exists(TOKEN_FILE)):
        return fallback(video, caption)
    return publish(env, video, caption)


if __name__ == "__main__":
    sys.exit(main())
