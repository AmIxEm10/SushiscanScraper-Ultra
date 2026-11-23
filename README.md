# 🍣 SushiscanScraper Ultra (v2.0 PRO)

Un téléchargeur et explorateur complet, ultra-rapide et moderne pour **Sushiscan** (`sushiscan.net` et `sushiscan.fr`), équipé d'une **interface graphique (GUI) interactive**, d'un **moniteur avec graphique de vitesse en temps réel**, du **filtrage par catégories**, de la **recherche A-Z**, et du mode **"Surprends-moi !"**.

---

## ✨ Fonctionnalités Principales

### 🖥️ 1. Interface Graphique Moderne (GUI)
- Fenêtre d'application de bureau native (accélérée matériellement via WebView2 / Edge) avec repli automatique sur votre navigateur par défaut.
- **Barre de recherche instantanée** : trouvez n'importe quel manga en quelques millisecondes.
- **Cartes de mangas avec couvertures HD** et badge du dernier chapitre sorti.
- **Fiche détaillée du manga** : synopsis complet, genres, statut, et liste cochable de tous les chapitres.
- **Sélecteur de dossier natif** : bouton *Parcourir* pour choisir où enregistrer vos mangas.

### 📈 2. Graphique de Débit & Moniteur en Temps Réel
- **Oscilloscope / Graphique en direct** (Canvas HTML5) : courbe fluide du débit de téléchargement (en MB/s ou KB/s).
- Affichage de la **vitesse actuelle**, du **pic de vitesse**, et du total des données reçues.
- Double barre de progression : progression globale des chapitres et progression des pages en cours.
- Journal d'événements (*logs*) en temps réel avec possibilité d'annulation instantanée.

### 🎲 3. Mode "Surprends-moi !" (Découverte Aléatoire)
- Envie de lire quelque chose de nouveau sans savoir quoi chercher ?
- Cliquez sur **"🎲 Surprends-moi !"** (ou tapez `--surprise`) : le scraper explore le catalogue, sélectionne une pépite au hasard, affiche sa couverture, son synopsis et ses chapitres, prêt à être téléchargé en 1 clic !

### 📂 4. Filtre par Catégories / Genres
- Explorez parmi plus de **35 catégories** : *Action, Aventure, Isekai, Comédie, Drame, Romance, Fantastique, Seinen, Shônen, Mystère, Horreur, Slice of Life...*

### 🔤 5. Ordre Alphabétique (A-Z) & Tris
- Barre alphabétique rapide : filtrez les mangas par lettre (`A`, `B`, `C` ... `Z`, `#`).
- Tris disponibles : *Plus Populaires, Alphabétique (A-Z), Alphabétique (Z-A), Derniers ajouts, Dernières mises à jour*.

### ⚡ 6. Moteur Ultra-Rapide
- Téléchargement multi-threadé (toutes les pages d'un chapitre en parallèle).
- Formats au choix : **PDF** (haute définition avec gestion de transparence), **CBZ** (archive liseuse), **Images** (dossier brut), ou **Both** (les deux).

---

## 🚀 Démarrage Rapide

### Option A : Interface Graphique (Recommandé)
- Double-cliquez simplement sur **`run_gui.bat`** (ou tapez `python gui.py` ou `python sushiscan.py --gui`).

### Option B : Terminal Interactif
- Double-cliquez sur **`run.bat`** (ou tapez `python sushiscan.py`).
- Un menu vous propose :
  - `[1]` Recherche par nom ou URL
  - `[2]` Parcourir par catégorie (genres)
  - `[3]` Parcourir par ordre alphabétique (A-Z)
  - `[4]` 🎲 Surprends-moi ! (Manga aléatoire)
  - `[5]` 🖥️ Lancer la GUI

### Option C : Ligne de Commande (CLI)
```bash
# Lancer l'interface graphique
python sushiscan.py --gui

# Découvrir un manga surprise et télécharger son dernier chapitre en CBZ
python sushiscan.py --surprise -c latest -f cbz

# Télécharger les chapitres 1 à 5 de One Piece en PDF
python sushiscan.py -s "One Piece" -c 1-5 -f pdf

# Explorer les mangas de la catégorie "Isekai"
python sushiscan.py --genre "Isekai" -c 1-3

# Télécharger tous les mangas par ordre alphabétique
python sushiscan.py --order title
```

---

## 📦 Dépendances Installées
Toutes les dépendances requises sont listées dans `requirements.txt` :
- `requests`, `beautifulsoup4`, `lxml`
- `Pillow`, `tqdm`, `urllib3`
- `flask`, `pywebview`

---

## ⚖️ Responsabilité
Ce script est destiné à un usage personnel et d'archivage. Merci de respecter les droits d'auteur et de soutenir les éditeurs et plateformes officielles (Manga Plus, Crunchyroll, etc.).
