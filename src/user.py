import os
import sys
from tqdm import tqdm

from scraper import Scraper, GENRES, ORDER_OPTIONS
from utilities import parse_chapter_selection, sanitize_filename, DEFAULT_WEBSITE
from errors import NoResultsFound, ChapterDownloadError

class UserInterface:
    def __init__(self, website: str = DEFAULT_WEBSITE, out_folder: str = "downloads", fmt: str = "pdf", workers: int = 8) -> None:
        self.website = website
        self.out_folder = out_folder
        self.format = fmt
        self.scraper = Scraper(website=website, out_folder=out_folder, max_workers=workers)

    def print_banner(self) -> None:
        banner = r"""
  ==============================================================
    🍣 SushiscanScraper Ultra - Téléchargeur Rapide de Scans 🍣
  ==============================================================
        """
        print(banner)

    def select_manga(self, query: str) -> tuple[str, str]:
        """
        Searches and lets the user choose a manga.
        Returns (manga_title, manga_url).
        """
        print(f"\n🔍 Recherche de '{query}' sur {self.website}...")
        results = self.scraper.search(query)

        if not results:
            raise NoResultsFound(f"Aucun résultat trouvé pour '{query}'.")

        if len(results) == 1:
            print(f"👉 1 seul résultat trouvé : {results[0]['title']}")
            return results[0]["title"], results[0]["url"]

        print(f"\n📚 {len(results)} résultats trouvés :")
        for i, item in enumerate(results, start=1):
            latest_str = f" ({item['latest']})" if item.get('latest') else ""
            print(f"  [{i}] {item['title']}{latest_str}")

        while True:
            choice = input(f"\nChoisissez un numéro (1-{len(results)}) ou 'q' pour annuler : ").strip()
            if choice.lower() in ("q", "quit", "exit"):
                return "", ""
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(results):
                    selected = results[idx - 1]
                    return selected["title"], selected["url"]
            print("❌ Choix invalide, veuillez réessayer.")

    def select_chapters(self, chapters: list[dict]) -> list[dict]:
        """
        Displays chapter overview and lets user pick which chapters to download.
        """
        total = len(chapters)
        print(f"\n📖 {total} chapitres disponibles.")
        print(f"   Premier : [1] {chapters[0]['title']}")
        print(f"   Dernier : [{total}] {chapters[-1]['title']}")

        print("\nOptions de sélection :")
        print("  - 'all'          : Tout télécharger")
        print("  - 'latest'       : Le dernier chapitre uniquement")
        print("  - '1-10'         : Plage de chapitres (du 1 au 10)")
        print("  - '5-'           : Du chapitre 5 jusqu'à la fin")
        print("  - '1, 3, 5-8'    : Sélection personnalisée")

        while True:
            sel_str = input("\nEntrez votre sélection : ").strip()
            if not sel_str:
                continue
            indices = parse_chapter_selection(sel_str, total)
            if indices:
                selected_chapters = [chapters[i] for i in indices]
                print(f"\n✅ {len(selected_chapters)} chapitre(s) sélectionné(s).")
                return selected_chapters
            print("❌ Sélection invalide ou vide. Exemple: 'all', 'latest', ou '1-5'.")

    def download_chapter_workflow(self, manga_title: str, chapter_item: dict) -> None:
        """Downloads and saves a single chapter."""
        chap_title = chapter_item.get("title", "Chapitre")
        chap_url = chapter_item["url"]

        img_urls = self.scraper.get_chapter_images(chap_url)
        if not img_urls:
            print(f"  ⚠️ Aucune image trouvée pour {chap_title}")
            return

        imgs_data = self.scraper.download_chapter_images(img_urls)
        saved_info = self.scraper.save_chapter(
            images_data=imgs_data,
            manga_name=manga_title,
            chapter_title=chap_title,
            fmt=self.format
        )

    def browse_by_genre(self) -> tuple[str, str]:
        """Interactive genre browser."""
        genre_items = list(GENRES.items())
        print("\n📂 Choisissez une catégorie / genre :")
        for idx, (gid, gname) in enumerate(genre_items, start=1):
            print(f"  [{idx:2d}] {gname:<18}", end="\n" if idx % 3 == 0 else "")
        print()

        choice = input(f"\nNuméro du genre (1-{len(genre_items)}) : ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(genre_items)):
            return "", ""

        selected_id = genre_items[int(choice) - 1][0]
        selected_name = genre_items[int(choice) - 1][1]
        print(f"\n⏳ Récupération des mangas pour '{selected_name}'...")
        items = self.scraper.get_catalogue(genre=selected_id, order="popular", page=1)
        if not items:
            print(f"❌ Aucun manga trouvé pour ce genre.")
            return "", ""

        print(f"\n📚 Mangas dans la catégorie '{selected_name}' :")
        for i, item in enumerate(items[:20], start=1):
            latest_str = f" ({item['latest']})" if item.get('latest') else ""
            print(f"  [{i:2d}] {item['title']}{latest_str}")

        m_choice = input(f"\nChoisissez un manga (1-{min(len(items), 20)}) : ").strip()
        if m_choice.isdigit() and 1 <= int(m_choice) <= len(items):
            m = items[int(m_choice) - 1]
            return m["title"], m["url"]
        return "", ""

    def surprise_me(self) -> tuple[str, str]:
        """Picks a random manga and displays its details."""
        print("\n🎲 Recherche d'un manga surprise au hasard...")
        try:
            m = self.scraper.get_random_manga()
            print("\n" + "=" * 50)
            print(f"🎉 Manga Surprise : {m['title']}")
            print(f"🏷️ Genres : {', '.join(m['genres'])}")
            print(f"📖 Total chapitres : {len(m['chapters'])}")
            if m.get('synopsis'):
                print(f"📝 Synopsis : {m['synopsis'][:220]}...")
            print("=" * 50)
            return m["title"], m["url"]
        except Exception as e:
            print(f"❌ Erreur lors de la surprise : {e}")
            return "", ""

    def run_interactive(self) -> None:
        """Main interactive loop."""
        self.print_banner()

        # Ask output folder if default
        user_folder = input(f"Dossier de destination (Entrée pour '{self.out_folder}') : ").strip()
        if user_folder:
            self.out_folder = user_folder
            self.scraper.out_folder = user_folder

        # Ask format if not set
        fmt_choice = input(f"Format de sortie (pdf / cbz / images / both) [défaut: {self.format}] : ").strip().lower()
        if fmt_choice in ("pdf", "cbz", "images", "both"):
            self.format = fmt_choice

        while True:
            print("\n" + "-" * 50)
            print("Que souhaitez-vous faire ?")
            print("  [1] 🔍 Rechercher un manga par nom ou coller une URL")
            print("  [2] 📂 Parcourir par catégorie / genre (Action, Isekai, Romance...)")
            print("  [3] 🔤 Parcourir par ordre alphabétique (A-Z)")
            print("  [4] 🎲 Surprends-moi ! (Manga aléatoire)")
            print("  [5] 🖥️ Lancer l'interface graphique (GUI)")
            print("  [q] 🚪 Quitter")

            action = input("\nVotre choix [1-5 / q] : ").strip().lower()

            if action in ("q", "quit", "exit"):
                print("\n👋 Au revoir !")
                break

            manga_title = ""
            manga_url = ""

            if action == "5":
                print("\n🖥️ Lancement de l'interface graphique...")
                import subprocess
                subprocess.Popen([sys.executable, "gui.py"])
                print("L'interface graphique a été ouverte dans une nouvelle fenêtre.")
                continue

            elif action == "2":
                manga_title, manga_url = self.browse_by_genre()
                if not manga_url:
                    continue

            elif action == "3":
                letter = input("\nEntrez une lettre pour l'ordre alphabétique (A-Z ou Entrée pour tout) : ").strip().upper()
                print(f"\n⏳ Récupération des mangas pour la lettre '{letter or 'A-Z'}'...")
                items = self.scraper.get_catalogue(order="title", page=1, letter=letter if letter else None)
                if not items:
                    print("❌ Aucun manga trouvé.")
                    continue
                print(f"\n📚 Mangas trouvés (Page 1) :")
                for i, it in enumerate(items[:20], start=1):
                    print(f"  [{i:2d}] {it['title']}")
                c = input(f"\nChoisissez un manga (1-{min(len(items), 20)}) : ").strip()
                if c.isdigit() and 1 <= int(c) <= len(items):
                    m = items[int(c) - 1]
                    manga_title, manga_url = m["title"], m["url"]
                else:
                    continue

            elif action == "4":
                manga_title, manga_url = self.surprise_me()
                if not manga_url:
                    continue

            else:
                user_input = input("\nEntrez le nom d'un manga (ou une URL de chapitre/catalogue) :\n> ").strip()
                if not user_input:
                    continue

                # Case 1: Direct chapter URL
                if "chapitre" in user_input or "-chap-" in user_input or "-chapter-" in user_input:
                    manga_title = user_input.split("/")[-2].replace("-chapitre-", " Chapitre ").replace("-", " ").title()
                    print(f"\n🚀 Téléchargement direct du chapitre depuis l'URL...")
                    img_urls = self.scraper.get_chapter_images(user_input)
                    if not img_urls:
                        print("❌ Aucune image trouvée à cette URL.")
                        continue
                    print(f"  📥 Téléchargement de {len(img_urls)} pages...")
                    imgs_data = self.scraper.download_chapter_images(img_urls)
                    res_path = self.scraper.save_chapter(imgs_data, manga_title, "Chapitre", self.format)
                    print(f"  🎉 Sauvegardé avec succès dans : {res_path}")
                    continue

                if user_input.startswith("http://") or user_input.startswith("https://"):
                    manga_url = user_input
                    manga_title = user_input.rstrip("/").split("/")[-1].replace("-", " ").title()
                else:
                    manga_title, manga_url = self.select_manga(user_input)
                    if not manga_url:
                        continue

            # Fetch chapters & download
            try:
                print(f"\n⏳ Récupération de la liste des chapitres pour '{manga_title}'...")
                chapters = self.scraper.get_available_chapters(manga_url)
                if not chapters:
                    print(f"❌ Aucun chapitre trouvé pour ce manga.")
                    continue

                chosen = self.select_chapters(chapters)
                if not chosen:
                    continue

                print(f"\n🚀 Début du téléchargement ({len(chosen)} chapitres)...")
                with tqdm(total=len(chosen), desc="Progression globale", unit="chap") as pbar:
                    for chap in chosen:
                        pbar.set_postfix_str(chap["title"])
                        try:
                            self.download_chapter_workflow(manga_title, chap)
                        except Exception as err:
                            print(f"\n⚠️ Erreur sur {chap['title']}: {err}")
                        pbar.update(1)

                print(f"\n🎉 Terminé ! Tous les fichiers ont été enregistrés dans : {os.path.abspath(os.path.join(self.out_folder, sanitize_filename(manga_title)))}")
            except Exception as e:
                print(f"\n❌ Une erreur est survenue : {e}")
