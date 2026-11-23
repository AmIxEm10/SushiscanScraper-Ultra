import time
import uuid
import threading
from collections import deque
from typing import Optional, Callable
from scraper import Scraper
from utilities import sanitize_filename

class DownloadTask:
    def __init__(
        self,
        task_id: str,
        manga_title: str,
        chapters: list[dict],
        fmt: str = "pdf",
        output_dir: str = "downloads",
        workers: int = 6
    ) -> None:
        self.id = task_id
        self.manga_title = manga_title
        self.chapters = chapters
        self.fmt = fmt
        self.output_dir = output_dir
        self.workers = workers
        
        self.status = "queued"  # queued, downloading, completed, error, cancelled
        self.error_message = ""
        self.chapter_current = 0
        self.chapter_total = len(chapters)
        self.current_chapter = ""
        self.page_current = 0
        self.page_total = 0
        self.bytes_downloaded = 0
        self._cancel_flag = False

    def to_dict(self) -> dict:
        pct = round((self.chapter_current / self.chapter_total * 100), 1) if self.chapter_total else 0
        return {
            "id": self.id,
            "manga_title": self.manga_title,
            "status": self.status,
            "error": self.error_message,
            "current_chapter": self.current_chapter,
            "chapter_current": self.chapter_current,
            "chapter_total": self.chapter_total,
            "percent": pct,
            "page_current": self.page_current,
            "page_total": self.page_total,
            "format": self.fmt
        }

class DownloadManager:
    def __init__(self, scraper: Optional[Scraper] = None, max_concurrent: int = 2) -> None:
        self.scraper = scraper or Scraper()
        self.max_concurrent = max_concurrent
        self.lock = threading.Lock()
        
        self.tasks: list[DownloadTask] = []
        self.total_bytes = 0
        self.speed_kbs = 0.0
        self.peak_speed_kbs = 0.0
        self.speed_history = deque([0.0] * 30, maxlen=30)
        
        self.logs = []
        self._last_calc_time = time.time()
        self._bytes_in_window = 0

        # Start background scheduler
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def add_log(self, msg: str) -> None:
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            self.logs.append(f"[{timestamp}] {msg}")
            if len(self.logs) > 60:
                self.logs.pop(0)

    def record_bytes(self, count: int) -> None:
        with self.lock:
            self.total_bytes += count
            self._bytes_in_window += count

    def update_speed_tick(self) -> None:
        with self.lock:
            now = time.time()
            elapsed = now - self._last_calc_time
            if elapsed >= 0.4:
                kbytes = self._bytes_in_window / 1024.0
                speed = kbytes / elapsed
                active = any(t.status == "downloading" for t in self.tasks)
                self.speed_kbs = round(speed, 1) if active else 0.0
                if self.speed_kbs > self.peak_speed_kbs:
                    self.peak_speed_kbs = self.speed_kbs
                self.speed_history.append(self.speed_kbs)
                self._bytes_in_window = 0
                self._last_calc_time = now

    def add_download(
        self,
        manga_title: str,
        chapters: list[dict],
        fmt: str = "pdf",
        output_dir: str = "downloads",
        workers: int = 6
    ) -> DownloadTask:
        task_id = str(uuid.uuid4())[:8]
        task = DownloadTask(
            task_id=task_id,
            manga_title=manga_title,
            chapters=chapters,
            fmt=fmt,
            output_dir=output_dir,
            workers=workers
        )
        with self.lock:
            self.tasks.append(task)
        
        active_count = sum(1 for t in self.tasks if t.status == "downloading")
        if active_count < self.max_concurrent:
            self.add_log(f"🚀 Ajouté et démarrage immédiat : '{manga_title}' ({len(chapters)} chapitres)")
        else:
            self.add_log(f"⏳ Ajouté à la file d'attente : '{manga_title}' ({len(chapters)} chapitres)")
        return task

    def cancel_task(self, task_id: str) -> bool:
        with self.lock:
            for t in self.tasks:
                if t.id == task_id:
                    t._cancel_flag = True
                    t.status = "cancelled"
                    self.add_log(f"🛑 Annulé : '{t.manga_title}'")
                    return True
        return False

    def cancel_all(self) -> None:
        with self.lock:
            for t in self.tasks:
                if t.status in ("queued", "downloading"):
                    t._cancel_flag = True
                    t.status = "cancelled"
            self.add_log("🛑 Tous les téléchargements ont été annulés.")

    def clear_finished(self) -> None:
        with self.lock:
            self.tasks = [t for t in self.tasks if t.status in ("queued", "downloading")]

    def get_status(self) -> dict:
        self.update_speed_tick()
        with self.lock:
            active_tasks = [t.to_dict() for t in self.tasks if t.status == "downloading"]
            queued_tasks = [t.to_dict() for t in self.tasks if t.status == "queued"]
            completed_tasks = [t.to_dict() for t in self.tasks if t.status in ("completed", "finished")]
            all_tasks = [t.to_dict() for t in self.tasks]

            overall_status = "downloading" if active_tasks else ("queued" if queued_tasks else "idle")

            return {
                "status": overall_status,
                "active_count": len(active_tasks),
                "queued_count": len(queued_tasks),
                "speed_kbs": self.speed_kbs,
                "speed_mbs": round(self.speed_kbs / 1024.0, 2),
                "peak_speed_mbs": round(self.peak_speed_kbs / 1024.0, 2),
                "total_bytes": self.total_bytes,
                "speed_history": list(self.speed_history),
                "tasks": all_tasks,
                "logs": list(self.logs)
            }

    def _scheduler_loop(self) -> None:
        """Continuously checks the queue and spawns workers up to max_concurrent."""
        while True:
            time.sleep(0.3)
            with self.lock:
                active_count = sum(1 for t in self.tasks if t.status == "downloading")
                if active_count >= self.max_concurrent:
                    continue

                # Find next queued task
                next_task = None
                for t in self.tasks:
                    if t.status == "queued" and not t._cancel_flag:
                        next_task = t
                        break

                if next_task:
                    next_task.status = "downloading"
                    th = threading.Thread(target=self._run_task, args=(next_task,), daemon=True)
                    th.start()

    def _run_task(self, task: DownloadTask) -> None:
        try:
            self.add_log(f"⚡ Démarrage du téléchargement de '{task.manga_title}' ({len(task.chapters)} chapitres)...")
            # Create a separate Scraper instance per task for thread isolation
            task_scraper = Scraper(
                website=self.scraper.website,
                out_folder=task.output_dir,
                max_workers=task.workers
            )

            for idx, chap in enumerate(task.chapters, 1):
                if task._cancel_flag:
                    break

                with self.lock:
                    task.chapter_current = idx - 1
                    task.current_chapter = chap.get("title", f"Chapitre {idx}")
                    task.page_current = 0
                    task.page_total = 0

                chap_title = chap.get("title", f"Chapitre {idx}")

                img_urls = task_scraper.get_chapter_images(chap["url"])
                if not img_urls:
                    self.add_log(f"⚠️ {task.manga_title} : Aucune image trouvée pour {chap_title}.")
                    with self.lock:
                        task.chapter_current = idx
                    continue

                with self.lock:
                    task.page_total = len(img_urls)

                def progress_cb(byte_count: int):
                    self.record_bytes(byte_count)
                    with self.lock:
                        task.bytes_downloaded += byte_count
                        task.page_current = min(task.page_total, task.page_current + 1)

                images_data = task_scraper.download_chapter_images_with_cb(
                    img_urls,
                    progress_cb,
                    lambda: task._cancel_flag
                )
                if task._cancel_flag:
                    break

                task_scraper.save_chapter(images_data, task.manga_title, chap_title, task.fmt)
                with self.lock:
                    task.chapter_current = idx

            with self.lock:
                if not task._cancel_flag:
                    task.status = "completed"
                    self.add_log(f"🎉 Terminé : '{task.manga_title}' ({len(task.chapters)} chapitres en {task.fmt.upper()}) !")
        except Exception as e:
            with self.lock:
                task.status = "error"
                task.error_message = str(e)
            self.add_log(f"❌ Erreur sur '{task.manga_title}' : {e}")
