import time
import threading
from collections import deque
from typing import Optional, Callable
from scraper import Scraper
from utilities import sanitize_filename

class DownloadManager:
    def __init__(self, scraper: Optional[Scraper] = None) -> None:
        self.scraper = scraper or Scraper()
        self.lock = threading.Lock()
        
        self.status = "idle"  # idle, running, finished, error, cancelled
        self.error_message = ""
        self.current_manga = ""
        self.current_chapter = ""
        self.chapter_current = 0
        self.chapter_total = 0
        self.page_current = 0
        self.page_total = 0
        
        self.total_bytes = 0
        self.speed_kbs = 0.0
        self.peak_speed_kbs = 0.0
        self.speed_history = deque([0.0] * 30, maxlen=30)
        
        self.logs = []
        self._cancel_flag = False
        self._thread: Optional[threading.Thread] = None

        # Telemetry tracking for speed calculation
        self._last_calc_time = time.time()
        self._bytes_in_window = 0

    def add_log(self, msg: str) -> None:
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            self.logs.append(f"[{timestamp}] {msg}")
            if len(self.logs) > 50:
                self.logs.pop(0)

    def record_bytes(self, count: int) -> None:
        with self.lock:
            self.total_bytes += count
            self._bytes_in_window += count

    def update_speed_tick(self) -> None:
        """Called periodically (e.g. every 500ms) to compute speed."""
        with self.lock:
            now = time.time()
            elapsed = now - self._last_calc_time
            if elapsed >= 0.4:
                kbytes = self._bytes_in_window / 1024.0
                speed = kbytes / elapsed
                self.speed_kbs = round(speed, 1) if self.status == "running" else 0.0
                if self.speed_kbs > self.peak_speed_kbs:
                    self.peak_speed_kbs = self.speed_kbs
                self.speed_history.append(self.speed_kbs)
                self._bytes_in_window = 0
                self._last_calc_time = now

    def get_status(self) -> dict:
        self.update_speed_tick()
        with self.lock:
            # If thread finished, make sure status is not running
            if self._thread and not self._thread.is_alive() and self.status == "running":
                self.status = "finished"

            return {
                "status": self.status,
                "error": self.error_message,
                "current_manga": self.current_manga,
                "current_chapter": self.current_chapter,
                "chapter_current": self.chapter_current,
                "chapter_total": self.chapter_total,
                "chapter_percent": round((self.chapter_current / self.chapter_total * 100), 1) if self.chapter_total else 0,
                "page_current": self.page_current,
                "page_total": self.page_total,
                "total_bytes": self.total_bytes,
                "speed_kbs": self.speed_kbs,
                "speed_mbs": round(self.speed_kbs / 1024.0, 2),
                "peak_speed_mbs": round(self.peak_speed_kbs / 1024.0, 2),
                "speed_history": list(self.speed_history),
                "logs": list(self.logs)
            }

    def start_download(
        self,
        manga_title: str,
        chapters: list[dict],
        fmt: str = "pdf",
        output_dir: str = "downloads",
        workers: int = 8
    ) -> bool:
        with self.lock:
            # Check if an actual download thread is alive
            if self._thread and self._thread.is_alive() and self.status == "running":
                return False

            self.status = "running"
            self.error_message = ""
            self.current_manga = manga_title
            self.chapter_current = 0
            self.chapter_total = len(chapters)
            self.page_current = 0
            self.page_total = 0
            self.total_bytes = 0
            self.speed_kbs = 0.0
            self.peak_speed_kbs = 0.0
            self._cancel_flag = False
            self._bytes_in_window = 0
            self._last_calc_time = time.time()
            self.scraper.out_folder = output_dir
            self.scraper.max_workers = workers

        self.add_log(f"🚀 Début du téléchargement de '{manga_title}' ({len(chapters)} chapitres, format: {fmt.upper()})")

        self._thread = threading.Thread(
            target=self._run_download,
            args=(manga_title, chapters, fmt),
            daemon=True
        )
        self._thread.start()
        return True

    def cancel(self) -> None:
        with self.lock:
            if self.status == "running":
                self._cancel_flag = True
                self.status = "cancelled"
                self.add_log("🛑 Téléchargement annulé par l'utilisateur.")

    def _run_download(self, manga_title: str, chapters: list[dict], fmt: str) -> None:
        try:
            for idx, chap in enumerate(chapters, 1):
                if self._cancel_flag:
                    break

                with self.lock:
                    self.chapter_current = idx - 1
                    self.current_chapter = chap.get("title", f"Chapitre {idx}")
                    self.page_current = 0
                    self.page_total = 0

                chap_title = chap.get("title", f"Chapitre {idx}")
                self.add_log(f"📖 Analyse de {chap_title}...")

                img_urls = self.scraper.get_chapter_images(chap["url"])
                if not img_urls:
                    self.add_log(f"⚠️ Aucune image trouvée pour {chap_title}, passage au suivant.")
                    with self.lock:
                        self.chapter_current = idx
                    continue

                with self.lock:
                    self.page_total = len(img_urls)

                self.add_log(f"📥 Téléchargement de {len(img_urls)} pages pour {chap_title}...")

                def progress_cb(byte_count: int):
                    self.record_bytes(byte_count)
                    with self.lock:
                        self.page_current = min(self.page_total, self.page_current + 1)

                images_data = self.scraper.download_chapter_images_with_cb(img_urls, progress_cb, lambda: self._cancel_flag)
                if self._cancel_flag:
                    break

                self.add_log(f"💾 Enregistrement de {chap_title} au format {fmt.upper()}...")
                saved_path = self.scraper.save_chapter(images_data, manga_title, chap_title, fmt)
                self.add_log(f"✅ {chap_title} sauvegardé !")

                with self.lock:
                    self.chapter_current = idx

            with self.lock:
                if not self._cancel_flag:
                    self.status = "finished"
                    self.speed_kbs = 0.0
                    self.add_log(f"🎉 Tous les chapitres de '{manga_title}' ont été téléchargés avec succès !")
        except Exception as e:
            with self.lock:
                self.status = "error"
                self.speed_kbs = 0.0
                self.error_message = str(e)
            self.add_log(f"❌ Erreur critique : {e}")
