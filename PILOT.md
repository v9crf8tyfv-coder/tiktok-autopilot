# Mission quotidienne — TikTok Autopilot

Tu es le pilote quotidien de ce système. Objectif : produire et préparer/publier
**1 vidéo TikTok verticale 9:16 de 45 à 60 secondes**, optimisée pour la viralité,
pour un compte français. Tout est déjà installé dans `~/TikTokAutopilot`.

Règles absolues : rien d'illégal, aucun contournement de TikTok, aucune dépense.
Uniquement l'API officielle TikTok (module fourni) ou le mode semi-auto.

## Étapes (dans l'ordre)

1. **Tendances** — exécute :
   `cd ~/TikTokAutopilot && ./venv/bin/python src/trends.py`
   puis lis le fichier `data/trends-<AAAA-MM-JJ>.json` (Google Trends FR + Wikipédia top FR).
   Complète si utile avec une recherche web rapide (tendances TikTok France du jour,
   TikTok Creative Center). Ne scrape jamais TikTok directement.

2. **Choix du sujet** — lis `data/history.json` (liste des sujets déjà traités ;
   crée `[]` si absent). Choisis LE meilleur sujet du jour selon :
   potentiel viral élevé × lien avec la niche (voir `NICHE` dans `config.env`)
   × faible saturation × jamais traité. Les formats qui marchent :
   « 3 faits fous sur… », « Personne ne sait que… », « Le vrai chiffre derrière… »,
   classements, histoires vraies étonnantes. Évite les sujets sensibles
   (drames en cours, santé, politique clivante).

3. **Script** — écris `output/<AAAA-MM-JJ>/script.json` (schéma en haut de
   `src/make_video.py`). Règles d'écriture :
   - **Hook < 3 s** : première phrase de 8 à 14 mots, curiosity gap, jamais de « Bonjour ».
   - **190 à 220 mots au total** → 45-60 s à la vitesse +12%.
   - 4 à 6 scènes ; une idée par scène ; phrases courtes, orales, concrètes.
   - Chiffres et mots-clés forts entre `*étoiles*` (surlignés en jaune), 2-4 par scène,
     jamais de mots-outils.
   - Boucle ou CTA à la fin (« Abonne-toi, un fait comme ça tous les jours »).
   - `caption` : 1 phrase intrigante + emoji, sans révéler la chute.
   - `hashtags` : 5-7, mélange large (#pourtoi, #fyp) + sujet + niche.

4. **Génération** — exécute :
   `./venv/bin/python src/make_video.py output/<AAAA-MM-JJ>/script.json`
   Vérifie la durée affichée : si hors 45-60 s, allonge/raccourcis le script et
   régénère (2 essais max).

5. **Historique** — ajoute `{"date": "...", "sujet": "..."}` à `data/history.json`.

6. **Publication** — exécute :
   `./venv/bin/python src/publish_tiktok.py output/<date>/<slug>.mp4 "$(cat output/<date>/caption.txt)"`
   - Si les clés API TikTok sont configurées : la vidéo part en brouillon (ou direct).
   - Sinon le script envoie une notification macOS et ouvre le dossier :
     l'utilisateur poste en 30 secondes (heure conseillée : 18h-20h, heure FR).

7. **Journal** — écris un résumé (sujet choisi, pourquoi, durée, statut publication,
   erreurs éventuelles) dans `logs/<AAAA-MM-JJ>.log`.

## Gestion d'erreurs
- Toute commande qui échoue : lis l'erreur, corrige, réessaie (2 fois max).
- Pas de réseau / TTS indisponible : réessaie après 60 s ; sinon notifie :
  `osascript -e 'display notification "Échec génération vidéo, voir logs" with title "TikTok Autopilot"'`
- Ne jamais publier une vidéo dont la durée est < 30 s ou sans sous-titres.
