#!/usr/bin/env python3
"""Collecte quotidienne des tendances (sources gratuites et légales, sans clé API).

Sources :
  - Google Trends (flux RSS officiel, geo=FR)
  - Reddit (endpoints JSON publics : r/all + subreddits de la niche)

Sortie : data/trends-YYYY-MM-DD.json
"""
import datetime
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) TrendResearch/1.0"}

NICHE_SUBREDDITS = os.environ.get(
    "TREND_SUBREDDITS", "rapfr,france,musique,hiphopheads"
).split(",")


def google_trends_fr():
    """Tendances de recherche du jour en France (RSS officiel Google Trends)."""
    url = "https://trends.google.com/trending/rss?geo=FR"
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"ht": "https://trends.google.com/trending/rss"}
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            traffic = item.findtext("ht:approx_traffic", "", ns).strip()
            news = [
                n.findtext("ht:news_item_title", "", ns).strip()
                for n in item.findall("ht:news_item", ns)
            ][:2]
            if title:
                out.append({"sujet": title, "volume": traffic, "contexte": news})
    except Exception as e:
        out.append({"erreur": "google_trends: %s" % e})
    return out


def wikipedia_top_fr(limit=25):
    """Articles Wikipédia FR les plus vus hier (API Wikimédia officielle, sans clé)."""
    d = datetime.date.today() - datetime.timedelta(days=1)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
           "fr.wikipedia/all-access/%04d/%02d/%02d" % (d.year, d.month, d.day))
    skip = ("Spécial:", "Wikipédia:", "Portail:", "Aide:", "Cookie", "Page_d'accueil")
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        for art in r.json()["items"][0]["articles"]:
            name = art["article"]
            if any(s in name for s in skip):
                continue
            out.append({"article": name.replace("_", " "), "vues": art["views"]})
            if len(out) >= limit:
                break
    except Exception as e:
        out.append({"erreur": "wikipedia: %s" % e})
    return out


def reddit_top(subreddit, limit=10, period="day"):
    url = "https://www.reddit.com/r/%s/top.json?t=%s&limit=%d" % (subreddit, period, limit)
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        for child in r.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            title = d.get("title", "")
            # On ignore les posts purement méta ou NSFW
            if d.get("over_18") or not title:
                continue
            out.append({
                "titre": re.sub(r"\s+", " ", title)[:200],
                "score": d.get("score", 0),
                "commentaires": d.get("num_comments", 0),
                "subreddit": subreddit,
            })
    except Exception as e:
        out.append({"erreur": "reddit/%s: %s" % (subreddit, e)})
    return out


def main():
    today = datetime.date.today().isoformat()
    result = {
        "date": today,
        "google_trends_fr": google_trends_fr(),
        "wikipedia_top_fr": wikipedia_top_fr(),
        "reddit": {},
    }
    # Reddit bloque parfois les requêtes anonymes : purement optionnel
    for sub in NICHE_SUBREDDITS:
        sub = sub.strip()
        if sub:
            posts = reddit_top(sub, limit=8)
            if posts and "erreur" not in posts[0]:
                result["reddit"][sub] = posts

    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "trends-%s.json" % today)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
