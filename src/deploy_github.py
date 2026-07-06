#!/usr/bin/env python3
"""Déploie tout le projet sur GitHub : crée le dépôt privé, pousse le code,
range les secrets/variables chiffrés pour GitHub Actions.

Usage : venv/bin/python src/deploy_github.py <GITHUB_TOKEN> [nom-repo]
"""
import base64
import json
import os
import subprocess
import sys

import requests
from nacl import encoding, public

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"


def load_env():
    env = {}
    p = os.path.join(ROOT, "config.env")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def gh(method, path, token, **kw):
    return requests.request(method, API + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }, timeout=30, **kw)


def encrypt(pub_key_b64, secret_value):
    pk = public.PublicKey(pub_key_b64.encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(secret_value.encode())
    return base64.b64encode(sealed).decode()


def main():
    if len(sys.argv) < 2:
        print("Usage: deploy_github.py <GITHUB_TOKEN> [repo]")
        return 1
    token = sys.argv[1].strip()
    repo = sys.argv[2] if len(sys.argv) > 2 else "tiktok-autopilot"
    env = load_env()

    me = gh("GET", "/user", token).json()
    owner = me.get("login")
    if not owner:
        print("Token invalide : %s" % me)
        return 1
    print("Compte GitHub : %s" % owner)

    # 1) créer le dépôt privé (ignore si déjà présent)
    r = gh("POST", "/user/repos", token, json={
        "name": repo, "private": True, "auto_init": False,
        "description": "TikTok Autopilot — vidéos quotidiennes automatiques",
    })
    if r.status_code == 201:
        print("Dépôt créé : %s/%s" % (owner, repo))
    elif r.status_code == 422:
        print("Dépôt déjà existant, on continue.")
    else:
        print("Création dépôt : %s %s" % (r.status_code, r.text[:200]))

    # 2) pousser le code (token seulement dans l'URL de push, pas stocké en remote)
    push_url = "https://%s:%s@github.com/%s/%s.git" % (owner, token, owner, repo)
    subprocess.run(["git", "-C", ROOT, "branch", "-M", "main"], check=False)
    subprocess.run(["git", "-C", ROOT, "remote", "remove", "origin"], check=False)
    subprocess.run(["git", "-C", ROOT, "remote", "add", "origin",
                    "https://github.com/%s/%s.git" % (owner, repo)], check=False)
    p = subprocess.run(["git", "-C", ROOT, "push", push_url, "main", "--force"],
                       capture_output=True, text=True)
    print("push:", (p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else "ok")

    # 3) secrets chiffrés
    pk = gh("GET", "/repos/%s/%s/actions/secrets/public-key" % (owner, repo), token).json()
    token_file = os.path.join(ROOT, "data", "tiktok_token.json")
    refresh = ""
    if os.path.exists(token_file):
        refresh = json.load(open(token_file)).get("refresh_token", "")

    secrets = {
        "MISTRAL_API_KEY": env.get("MISTRAL_API_KEY", ""),
        "GROQ_API_KEY": env.get("GROQ_API_KEY", ""),
        "TIKTOK_CLIENT_KEY": env.get("TIKTOK_CLIENT_KEY", ""),
        "TIKTOK_CLIENT_SECRET": env.get("TIKTOK_CLIENT_SECRET", ""),
        "TIKTOK_REFRESH_TOKEN": refresh,
    }
    for name, val in secrets.items():
        if not val:
            print("  (secret %s vide, ignoré pour l'instant)" % name)
            continue
        r = gh("PUT", "/repos/%s/%s/actions/secrets/%s" % (owner, repo, name), token,
               json={"encrypted_value": encrypt(pk["key"], val), "key_id": pk["key_id"]})
        print("  secret %s : %s" % (name, "OK" if r.status_code in (201, 204) else r.text[:120]))

    # 4) variables (non secrètes)
    for name, val in {"NICHE": env.get("NICHE", ""),
                      "TIKTOK_MODE": env.get("TIKTOK_MODE", "DRAFT")}.items():
        gh("DELETE", "/repos/%s/%s/actions/variables/%s" % (owner, repo, name), token)
        r = gh("POST", "/repos/%s/%s/actions/variables" % (owner, repo), token,
               json={"name": name, "value": val})
        print("  variable %s : %s" % (name, "OK" if r.status_code in (201, 204) else r.text[:120]))

    print("\n✅ Déploiement terminé : https://github.com/%s/%s" % (owner, repo))
    print("   Onglet Actions → workflow « TikTok Autopilot quotidien ».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
