#!/usr/bin/env python3
"""Cerveau IA — multi-fournisseurs GRATUITS (dispo en Belgique/UE).

Détection automatique selon la clé présente (config.env en local, secret GitHub en cloud) :
  - MISTRAL_API_KEY  -> Mistral 🇫🇷  (https://console.mistral.ai — offre gratuite)
  - GROQ_API_KEY     -> Groq ⚡      (https://console.groq.com — offre gratuite)
  - GEMINI_API_KEY   -> Google Gemini (si un jour dispo)

Mistral et Groq utilisent l'API "chat completions" compatible OpenAI.
Sans aucune clé : generate() lève LLMUnavailable → l'appelant bascule sur le gabarit local.
"""
import json
import os

import requests


class LLMUnavailable(Exception):
    pass


PROVIDERS = [
    {
        "key_env": "MISTRAL_API_KEY",
        "name": "mistral",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model_env": "MISTRAL_MODEL",
        "model": "mistral-small-latest",
        "kind": "openai",
    },
    {
        "key_env": "GROQ_API_KEY",
        "name": "groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model_env": "GROQ_MODEL",
        "model": "llama-3.3-70b-versatile",
        "kind": "openai",
    },
    {
        "key_env": "GEMINI_API_KEY",
        "name": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent",
        "model_env": "GEMINI_MODEL",
        "model": "gemini-2.0-flash",
        "kind": "gemini",
    },
]


def active_provider(env=None):
    env = env or os.environ
    for p in PROVIDERS:
        if env.get(p["key_env"]):
            return p
    return None


def have_key(env=None):
    return active_provider(env) is not None


def generate(prompt, env=None, temperature=0.9, max_tokens=2048):
    env = env or os.environ
    p = active_provider(env)
    if not p:
        raise LLMUnavailable("aucune clé IA (MISTRAL_API_KEY / GROQ_API_KEY / GEMINI_API_KEY)")
    key = env.get(p["key_env"])
    model = env.get(p["model_env"], p["model"])

    if p["kind"] == "openai":
        r = requests.post(
            p["url"],
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        if r.status_code != 200:
            raise LLMUnavailable("%s HTTP %s: %s" % (p["name"], r.status_code, r.text[:300]))
        try:
            return r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise LLMUnavailable("réponse %s inattendue" % p["name"])

    # Gemini
    r = requests.post(
        p["url"] % model,
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        },
        timeout=90,
    )
    if r.status_code != 200:
        raise LLMUnavailable("gemini HTTP %s: %s" % (r.status_code, r.text[:300]))
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMUnavailable("réponse gemini inattendue: %s" % json.dumps(r.json())[:200])
