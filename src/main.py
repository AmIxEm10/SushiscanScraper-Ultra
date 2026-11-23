import os
import sys
import argparse

# Add src folder to sys.path if invoked from elsewhere
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from user import UserInterface
from utilities import parse_chapter_selection
from scraper import GENRES, ORDER_OPTIONS
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(
        description="🍣 SushiscanScraper Ultra - Téléchargeur ultra-rapide de mangas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation :
  Interface Graphique (GUI) :
    python sushiscan.py --gui

  Mode interactif :
    python sushiscan.py

  Surprise Aléatoire :
    python sushiscan.py --surprise -c latest -f pdf

  Filtrer par catégorie / genre :
    python sushiscan.py --genre Action -c 1-5

  Ligne de commande directe :
    python sushiscan.py -s "One Piece" -c 1-5 -f pdf
    python sushiscan.py -s "Solo Leveling" -c latest -f cbz
    python sushiscan.py -u "https://sushiscan.net/catalogue/one-piece/" -c all
        """
    )
    parser.add_argument("--gui", action="store_true", help="Lancer l'interface graphique (GUI)")
    parser.add_argument("-s", "--search", type=str, help="Nom du manga à rechercher")
    parser.add_argument("-u", "--url", type=str, help="URL directe du manga ou du chapitre")
    parser.add_argument("--genre", type=str, help="Nom ou ID de la catégorie / genre")
    parser.add_argument("--order", type=str, default="popular", choices=["popular", "title", "titlereverse", "latest", "update"], help="Ordre de tri")
    parser.add_argument("--surprise", action="store_true", help="Sélectionner un manga surprise au hasard")
    parser.add_argument("-c", "--chapters", type=str, default="latest", help="Chapitres à télécharger ('all', 'latest', '1-10', '1,3,5') [défaut: latest]")
    parser.add_argument("-o", "--output", type=str, default="downloads", help="Dossier de destination [défaut: downloads]")
    parser.add_argument("-f", "--format", type=str, default="pdf", choices=["pdf", "cbz", "images", "both"], help="Format de sortie [défaut: pdf]")
    parser.add_argument("-w", "--workers", type=int, default=8, help="Nombre de téléchargements simultanés [défaut: 8]")
    parser.add_argument("--website", type=str, default="sushiscan.net", help="Domaine cible [défaut: sushiscan.net]")

    args = parser.parse_args()

    # Launch GUI if requested
    if args.gui:
        import subprocess
        gui_path = os.path.join(os.path.dirname(current_dir), "gui.py")
        subprocess.run([sys.executable, gui_path])
        return

    ui = UserInterface(
        website=args.website,
        out_folder=args.output,
        fmt=args.format,
        workers=args.workers
    )

    # Surprise mode
    if args.surprise:
        ui.print_banner()
        manga_title, manga_url = ui.surprise_me()
        if not manga_url:
            sys.exit(1)
        args.url = manga_url

    # Genre mode
    elif args.genre:
        ui.print_banner()
        items = ui.scraper.get_catalogue(genre=args.genre, order=args.order, page=1)
        if not items:
            print(f"❌ Aucun manga trouvé pour le genre '{args.genre}'.")
            sys.exit(1)
        print(f"📚 {len(items)} mangas trouvés dans '{args.genre}' :")
        for i, it in enumerate(items[:15], start=1):
            print(f"  [{i}] {it['title']}")
        choice = input(f"\nChoisissez un numéro (1-{min(len(items), 15)}) : ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            target = items[int(choice) - 1]
            args.url = target["url"]
            args.search = None
        else:
            sys.exit(0)

    # If no search or URL is specified, run interactive mode
    elif not args.search and not args.url:
        ui.run_interactive()
        return

    # Non-interactive CLI mode
    ui.print_banner()

    if args.url:
        target = args.url
        # Direct chapter URL
        if "chapitre" in target or "-chap-" in target or "-chapter-" in target:
            print(f"🚀 Téléchargement direct du chapitre : {target}")
            img_urls = ui.scraper.get_chapter_images(target)
            if not img_urls:
                print("❌ Aucune image trouvée.")
                sys.exit(1)
            print(f"📥 Téléchargement de {len(img_urls)} images...")
            imgs_data = ui.scraper.download_chapter_images(img_urls)
            manga_name = target.split("/")[-2].replace("-chapitre-", " Chapitre ").replace("-", " ").title()
            res = ui.scraper.save_chapter(imgs_data, manga_name, "Chapitre", ui.format)
            print(f"🎉 Enregistré dans : {res}")
            return

        manga_url = target
        manga_title = target.rstrip("/").split("/")[-1].replace("-", " ").title()
    else:
        results = ui.scraper.search(args.search)
        if not results:
            print(f"❌ Aucun résultat trouvé pour '{args.search}'.")
            sys.exit(1)
        manga_title = results[0]["title"]
        manga_url = results[0]["url"]
        print(f"👉 Manga sélectionné : {manga_title} ({manga_url})")

    print(f"⏳ Récupération de la liste des chapitres...")
    chapters = ui.scraper.get_available_chapters(manga_url)
    if not chapters:
        print("❌ Aucun chapitre trouvé.")
        sys.exit(1)

    indices = parse_chapter_selection(args.chapters, len(chapters))
    if not indices:
        print(f"❌ Sélection de chapitres invalide : '{args.chapters}'.")
        sys.exit(1)

    selected = [chapters[i] for i in indices]
    print(f"🚀 Téléchargement de {len(selected)} chapitre(s) au format {ui.format.upper()}...")

    with tqdm(total=len(selected), desc="Progression", unit="chap") as pbar:
        for chap in selected:
            pbar.set_postfix_str(chap["title"])
            try:
                ui.download_chapter_workflow(manga_title, chap)
            except Exception as e:
                print(f"\n⚠️ Erreur sur {chap['title']}: {e}")
            pbar.update(1)

    print(f"\n🎉 Terminé ! Dossier de sortie : {os.path.abspath(os.path.join(ui.out_folder, manga_title))}")

if __name__ == "__main__":
    main()
