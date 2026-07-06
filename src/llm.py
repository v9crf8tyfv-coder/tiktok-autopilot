#!/usr/bin/env python3
"""Petit client pour l'API Google Gemini (offre gratuite, sans carte bancaire).

Clé à créer sur https://aistudio.google.com/apikey puis :
  - en local : GEMINI_API_KEY dans config.env
  - en cloud : secret GitHub GEMINI_API_KEY

Si aucune clé n'est fournie, generate() lève LLMUnavailable et l'appelant
bascule sur un gabarit local (aucune dépendance, mais moins créatif).
"""
import json
import os

import requests

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"


class LLMUnavailable(Exception):
    pass


def have_key(env=None):
    env = env or os.environ
    return bool(env.get("GEMINI_API_KEY"))


def generate(prompt, env=None, temperature=0.9, max_tokens=2048):
    env = env or os.environ
    key = env.get("GEMINI_API_KEY")
    if not key:
        raise LLMUnavailable("GEMINI_API_KEY manquant")
    r = requests.post(
        ENDPOINT % MODEL,
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise LLMUnavailable("Gemini HTTP %s: %s" % (r.status_code, r.text[:300]))
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMUnavailable("Réponse Gemini inattendue: %s" % json.dumps(data)[:300])
