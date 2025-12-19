Google News RSS Builder – PRO (FR/EN/DUAL) + Sentiment + Export CSV

Ce script est une petite application Python/Tkinter de veille boursière basée sur Google News RSS.
Il permet de construire une requête “pro”, récupérer les articles correspondants (en français, en anglais, ou les deux), puis trier, scorer (sentiment POS/NEG), filtrer, ouvrir les liens en un clic et exporter les résultats en CSV pour archivage ou alimentation d’un pipeline IA.

Pourquoi c’est utile
1) Veille boursière rapide et centralisée

Tu définis une requête (ex: AVGO OR Broadcom)

Tu récupères immédiatement une liste des news pertinentes

Tu peux scroller comme dans un terminal, sans pub, sans UI lourde

2) Zéro perte d’information FR/EN

Google News favorise souvent un “angle local” selon hl/gl/ceid.
Le mode FR+EN (dual feed) interroge deux éditions (France + US) puis fusionne les résultats, ce qui donne une couverture plus exhaustive.

3) Tri par fraîcheur + filtre POS/NEG

La plupart des flux RSS ne sont pas triés parfaitement, ou mélangent des éléments.
L’app :

parse les dates,

trie localement par fraîcheur,

attribue un score POS/NEG/NEU,

et permet d’afficher uniquement POS et/ou NEG.

4) Export CSV “prêt pour IA”

Le bouton SAVE CSV exporte un fichier contenant notamment :

date UTC / date locale

langue détectée

score + label POS/NEG/NEU

source

titre

URL brute (pas le [i])

la requête utilisée
Ce CSV peut ensuite servir à entraîner un modèle, nourrir un RAG, faire des stats, etc.

Fonctionnement général
1) Construction de la requête

L’interface permet de paramétrer :

Query / Symbol
Exemple : AVGO OR Broadcom OR "Broadcom Inc"

Récence (menu déroulant)
1d, 7d, 1m, 3m, 6m, 1y
→ injecté via l’opérateur Google News when:

After / Before (YYYY-MM-DD)
→ injecté via after: et before:

Source domain (optionnel)
→ injecté via site:example.com

Ensuite le script génère une URL du type :

https://news.google.com/rss/search?q=<...>&hl=...&gl=...&ceid=...

2) Mode langue (FR / EN / FR+EN)

Le sélecteur langue pilote les paramètres Google News :

FR : hl=fr gl=FR ceid=FR:fr

EN : hl=en gl=US ceid=US:en

FR+EN : appelle les deux flux, puis merge

En mode DUAL, tu récupères :

plus de sources US/UK

plus de news financières “techniques”

moins d’angles “localisés”

3) Récupération et parsing RSS

Requête HTTP avec un User-Agent “browser”

Parsing via feedparser

Extraction des champs :

title

link

source.title (quand disponible)

published/updated → converti en datetime timezone-aware

4) Déduplication + tri par fraîcheur

En mode FR+EN, un même article peut apparaître deux fois.
Le script dédoublonne via un hash SHA1 basé sur :

l’URL si disponible, sinon

le titre

Puis il trie par date décroissante (le plus récent d’abord).

5) Détection de langue automatique

Deux niveaux :

Heuristique rapide (par mots indicateurs : earnings, shares, résultats, prévisions, etc.)

Si installé : langdetect améliore la détection

6) Scoring sentiment (POS/NEG/NEU)

Le scoring est volontairement pragmatique pour un usage “veille trading” :

Lexiques pondérés (mots avec poids)

Expressions/bigrams (ex: cuts guidance, beats estimates, abaisse ses prévisions, etc.) avec poids plus forts

Les mots “finance-intent” donnent un petit bonus mais ne doivent pas à eux seuls faire basculer POS/NEG

Résultat :

score > 0 → POS

score < 0 → NEG

score = 0 → NEU

L’affichage colore :

vert foncé pour POS

rouge foncé pour NEG

gris pour NEU

7) UI de lecture et ouverture des liens

Chaque ligne affiche une information minimale et exploitable :

[YYYY-MM-DD HH:MM] [POS +4] [EN] Source – Title [i]

Le [i] est cliquable et ouvre l’URL dans le navigateur.

8) Export CSV (SAVE CSV)

Le bouton exporte tous les items (après tri/dédup) avec les champs :

dt_utc

dt_local

lang

label

score

source

title

url

query

Installation
pip install requests feedparser
# Optionnel (langue plus fiable)
pip install langdetect

Exemples de requêtes utiles

Ticker + nom :

AVGO OR Broadcom OR "Broadcom Inc"

Résultats / guidance :

(AVGO OR Broadcom) (earnings OR guidance OR forecast OR outlook)

Filtrer un média :

AVGO site:reuters.com

Limitations (assumées)

Le scoring est heuristique : il donne une tendance et sert au tri/filtrage, pas une vérité absolue.

Google News RSS reste dépendant du ranking Google et de la disponibilité des sources.
