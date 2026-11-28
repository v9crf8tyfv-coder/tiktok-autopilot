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
import re
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
        "model": "openai/gpt-oss-120b",
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


def _extract_json(text):
    """Récupère le bloc JSON même si le modèle l'entoure de ``` ou de texte."""
    if not text:
        return text
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.I | re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    return t[i:j + 1] if i != -1 and j != -1 and j > i else t


def _call_one(p, key, model, prompt, temperature, max_tokens):
    if p["kind"] == "openai":
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # les modèles "gpt-oss" (raisonnement) refusent le JSON strict → on parse à la main
        if "gpt-oss" in model or "reasoning" in model:
            payload["reasoning_effort"] = "low"
        else:
            payload["response_format"] = {"type": "json_object"}
        r = requests.post(
            p["url"],
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json=payload, timeout=90,
        )
        if r.status_code != 200:
            raise LLMUnavailable("%s HTTP %s: %s" % (p["name"], r.status_code, r.text[:200]))
        try:
            return _extract_json(r.json()["choices"][0]["message"]["content"])
        except (KeyError, IndexError):
            raise LLMUnavailable("réponse %s inattendue" % p["name"])

    # Gemini
    r = requests.post(
        p["url"] % model, params={"key": key},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
                                   "responseMimeType": "application/json"}},
        timeout=90,
    )
    if r.status_code != 200:
        raise LLMUnavailable("gemini HTTP %s: %s" % (r.status_code, r.text[:200]))
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMUnavailable("réponse gemini inattendue")


def generate(prompt, env=None, temperature=0.9, max_tokens=2048):
    """Essaie chaque fournisseur ayant une clé, dans l'ordre ; renvoie le 1er qui répond.

    Résilient : si un fournisseur tombe (offre gratuite supprimée, quota…), on passe au suivant.
    """
    env = env or os.environ
    errors = []
    tried = False
    for p in PROVIDERS:
        key = env.get(p["key_env"])
        if not key:
            continue
        tried = True
        try:
            return _call_one(p, key, env.get(p["model_env"], p["model"]),
                             prompt, temperature, max_tokens)
        except LLMUnavailable as e:
            errors.append(str(e))
            continue
    if not tried:
        raise LLMUnavailable("aucune clé IA (GROQ_API_KEY / MISTRAL_API_KEY / GEMINI_API_KEY)")
    raise LLMUnavailable("tous les fournisseurs ont échoué: " + " | ".join(errors))
