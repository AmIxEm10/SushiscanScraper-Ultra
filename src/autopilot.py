"""
AutoPilot — Mode Veille Automatique
====================================
Télécharge automatiquement l'intégralité du catalogue Sushiscan,
manga par manga, ordre alphabétique A→Z, puis recommence avec les
mangas non encore téléchargés. Tourne en arrière-plan.
"""
import threading
import time
import os
from typing import Optional

ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["#"]


class AutoPilotState:
    """Shared state object for AutoPilot (read by GUI, written by worker thread)."""

    def __init__(self):
        self.enabled = False
        self.paused = False
        self.current_letter = ""
        self.current_page = 1
        self.current_manga = ""
        self.letter_index = 0          # index in ALPHABET
        self.cycle = 1                 # how many full A-Z passes done
        self.downloaded_slugs: set = set()   # slugs already downloaded this run
        self.total_downloaded = 0
        self.total_queued = 0
        self.fmt = "pdf"
        self.output_dir = "downloads"
        self.status_msg = "En attente…"
        self.error_msg = ""

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "paused": self.paused,
            "current_letter": self.current_letter,
            "current_manga": self.current_manga,
            "cycle": self.cycle,
            "letter_index": self.letter_index,
            "alphabet_total": len(ALPHABET),
            "total_downloaded": self.total_downloaded,
            "total_queued": self.total_queued,
            "downloaded_slugs": len(self.downloaded_slugs),
            "status_msg": self.status_msg,
            "error_msg": self.error_msg,
            "fmt": self.fmt,
            "output_dir": self.output_dir,
        }


class AutoPilot:
    """
    Background thread that walks the Sushiscan catalogue A→Z and feeds the
    DownloadManager with whole-manga download tasks.

    - One manga at a time is submitted (queued); DownloadManager handles concurrency.
    - AutoPilot waits until the manga is fully done before submitting the next one,
      so the queue never grows out of control.
    - After Z, restarts from A skipping already-done slugs (new mangas only).
    - User can pause/resume/stop at any time.
    """

    def __init__(self, scraper, download_manager) -> None:
        self.scraper = scraper
        self.dm = download_manager
        self.state = AutoPilotState()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self, fmt: str = "pdf", output_dir: str = "downloads",
              resume_letter: str = "A") -> None:
        """Start the autopilot from a given letter."""
        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self.state.enabled = True
        self.state.paused = False
        self.state.fmt = fmt
        self.state.output_dir = output_dir
        self.state.error_msg = ""
        self.state.status_msg = "Démarrage…"

        # Find the starting letter index
        letter_upper = resume_letter.upper()
        if letter_upper in ALPHABET:
            self.state.letter_index = ALPHABET.index(letter_upper)
        else:
            self.state.letter_index = 0

        self._thread = threading.Thread(target=self._run, daemon=True, name="autopilot")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.state.enabled = False
        self.state.paused = False
        self.state.status_msg = "Arrêté par l'utilisateur."

    def pause(self) -> None:
        self.state.paused = True
        self.state.status_msg = "En pause…"

    def resume(self) -> None:
        self.state.paused = False
        self.state.status_msg = "Reprise…"

    def get_status(self) -> dict:
        return self.state.to_dict()

    # ------------------------------------------------------------------ #
    #  Internal worker                                                      #
    # ------------------------------------------------------------------ #

    def _run(self) -> None:
        try:
            self._walk_catalogue()
        except Exception as e:
            self.state.error_msg = str(e)
            self.state.status_msg = f"❌ Erreur fatale : {e}"
            self.dm.add_log(f"[AutoPilot] ❌ Erreur fatale : {e}")
        finally:
            self.state.enabled = False
            self.state.status_msg = "Terminé."

    def _walk_catalogue(self) -> None:
        """Main loop: iterate alphabet letters, page by page, manga by manga."""
        scraper = self.scraper

        while not self._stop_event.is_set():
            # --- Pick current letter ---
            letter = ALPHABET[self.state.letter_index]
            self.state.current_letter = letter
            self.state.current_page = 1

            self.dm.add_log(f"[AutoPilot] 🔤 Lettre {letter} — Cycle #{self.state.cycle}")
            self.state.status_msg = f"Scan lettre {letter} (cycle #{self.state.cycle})…"

            page = 1
            while not self._stop_event.is_set():
                # Pause check
                while self.state.paused and not self._stop_event.is_set():
                    time.sleep(1)

                self.state.current_page = page

                # Fetch a page of catalogue for this letter
                try:
                    items = scraper.get_catalogue(letter=letter, order="alphabet", page=page)
                except Exception as e:
                    self.dm.add_log(f"[AutoPilot] ⚠️ Erreur catalogue {letter} p{page}: {e}")
                    time.sleep(5)
                    break  # move to next letter

                if not items:
                    self.dm.add_log(f"[AutoPilot] ✅ Fin lettre {letter} (p{page} vide).")
                    break

                for item in items:
                    if self._stop_event.is_set():
                        return

                    while self.state.paused and not self._stop_event.is_set():
                        time.sleep(1)

                    slug = item.get("url", "")
                    title = item.get("title", slug)

                    # Skip already downloaded this run
                    if slug in self.state.downloaded_slugs:
                        self.dm.add_log(f"[AutoPilot] ⏭️ Déjà téléchargé, skip : {title}")
                        continue

                    # Skip if output folder already exists and contains files
                    manga_folder = os.path.join(
                        self.state.output_dir,
                        self._sanitize(title)
                    )
                    if os.path.isdir(manga_folder) and len(os.listdir(manga_folder)) > 0:
                        self.state.downloaded_slugs.add(slug)
                        self.dm.add_log(f"[AutoPilot] ⏭️ Dossier existant, skip : {title}")
                        continue

                    # Fetch manga details (chapters list)
                    self.state.current_manga = title
                    self.state.status_msg = f"{letter} · {title} — récupération des chapitres…"

                    try:
                        details = scraper.get_manga_details(slug)
                        chapters = details.get("chapters", [])
                    except Exception as e:
                        self.dm.add_log(f"[AutoPilot] ⚠️ Détails introuvables pour {title}: {e}")
                        continue

                    if not chapters:
                        self.dm.add_log(f"[AutoPilot] ⚠️ Aucun chapitre pour {title}, skip.")
                        continue

                    self.dm.add_log(
                        f"[AutoPilot] ➕ Ajout : {title} ({len(chapters)} chapitres, {self.state.fmt.upper()})"
                    )
                    self.state.total_queued += 1
                    self.state.status_msg = f"{letter} · {title} — {len(chapters)} chap en file…"

                    task = self.dm.add_download(
                        manga_title=title,
                        chapters=chapters,
                        fmt=self.state.fmt,
                        output_dir=self.state.output_dir,
                        workers=4  # lighter workers during autopilot
                    )

                    # Wait for this task to finish before moving on
                    self._wait_for_task(task)

                    if task.status == "completed":
                        self.state.downloaded_slugs.add(slug)
                        self.state.total_downloaded += 1
                        self.dm.add_log(f"[AutoPilot] 🎉 Fini : {title}")
                    elif task.status == "cancelled":
                        # User manually cancelled one — keep going with next
                        self.dm.add_log(f"[AutoPilot] ⏭️ Annulé manuellement, next…")
                    else:
                        # error — keep going
                        pass

                # Next page
                page += 1

            if self._stop_event.is_set():
                return

            # --- Move to next letter ---
            self.state.letter_index += 1
            if self.state.letter_index >= len(ALPHABET):
                # Full cycle complete — restart from A, new cycle
                self.state.letter_index = 0
                self.state.cycle += 1
                self.dm.add_log(
                    f"[AutoPilot] 🔄 Cycle #{self.state.cycle - 1} terminé ! "
                    f"{self.state.total_downloaded} mangas téléchargés. "
                    f"Redémarrage cycle #{self.state.cycle}…"
                )
                self.state.status_msg = f"Cycle #{self.state.cycle} en cours…"
                # Keep downloaded_slugs so we skip them in next cycle too
                # (only fresh mangas added to Sushiscan will be picked up)

    def _wait_for_task(self, task) -> None:
        """Block until the task leaves active/queued state."""
        while task.status in ("queued", "downloading"):
            if self._stop_event.is_set():
                task._cancel_flag = True
                return
            time.sleep(1)

    @staticmethod
    def _sanitize(name: str) -> str:
        keep = set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_()'")
        return "".join(c if c in keep else "_" for c in name).strip()
