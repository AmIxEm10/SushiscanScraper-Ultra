import os
import re
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional
import requests
from bs4 import BeautifulSoup
import urllib3

from utilities import (
    sanitize_filename,
    save_images_as_pdf,
    save_images_as_cbz,
    save_raw_images,
    DEFAULT_WEBSITE,
)
from errors import InvalidStatusCode, NoResultsFound, ChapterDownloadError

# Suppress insecure SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GENRES = {
    "3": "Action",
    "12": "Aventure",
    "165": "Biographique",
    "13": "Comédie",
    "267": "Crossover",
    "4116": "Documentaire",
    "4": "Drame",
    "43": "Ecchi",
    "96": "Erotique",
    "5": "Fantastique",
    "32": "Fantasy",
    "2455": "Furyo",
    "3727": "Gekiga",
    "93": "Histoires courtes",
    "24": "Historique",
    "6": "Horreur",
    "639": "Isekai",
    "7": "Mature",
    "8": "Mystère",
    "764": "Nekketsu",
    "3251": "Polar",
    "20": "Psychologique",
    "26": "Romance",
    "16": "School-Life",
    "3443": "Science-Fantasy",
    "37": "Science-Fiction",
    "173": "Shôjo-aï",
    "599": "Shônen-aï",
    "28": "Slice of Life",
    "18": "Sport",
    "9": "Surnaturel",
    "79": "Thriller",
    "305": "Tournois",
    "10": "Tragique",
    "819": "Yonkoma"
}

ORDER_OPTIONS = {
    "popular": "Populaires",
    "title": "Alphabétique (A-Z)",
    "titlereverse": "Alphabétique (Z-A)",
    "latest": "Derniers ajouts",
    "update": "Mis à jour"
}

class Scraper:
    def __init__(self, website: str = DEFAULT_WEBSITE, out_folder: str = "downloads", max_workers: int = 8) -> None:
        self.website = website
        self.out_folder = out_folder
        self.max_workers = max_workers

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://{self.website}/",
        })
        self.session.verify = False

    def search(self, query: str) -> list[dict]:
        """
        Searches for a manga by its title on Sushiscan.
        Returns a list of dicts: [{'title': str, 'url': str, 'cover': str}]
        """
        encoded_query = query.strip().replace(" ", "+")
        url = f"https://{self.website}/?s={encoded_query}"
        
        try:
            resp = self.session.get(url, timeout=15)
        except requests.RequestException as e:
            raise InvalidStatusCode(f"Impossible de contacter https://{self.website} : {e}", "critical")

        if resp.status_code != 200:
            raise InvalidStatusCode(f"La recherche sur {url} a renvoyé le statut {resp.status_code}", "critical")

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for div in soup.find_all("div", {"class": "bsx"}):
            a = div.find("a")
            if a and a.get("href"):
                title = a.get("title") or a.get_text(strip=True)
                img = div.find("img")
                cover = img.get("src") if img else ""
                epxs = div.find("span", {"class": "epxs"}) or div.find("div", {"class": "epxs"})
                latest = epxs.get_text(strip=True) if epxs else ""
                results.append({
                    "title": title,
                    "url": a["href"],
                    "cover": cover,
                    "latest": latest
                })

        return results

    def get_catalogue(
        self,
        genre: Optional[str] = None,
        order: str = "popular",
        page: int = 1,
        letter: Optional[str] = None
    ) -> list[dict]:
        """
        Fetches manga catalog with category/genre, order, and pagination.
        """
        params = [f"page={page}", f"order={order}"]
        if genre and genre in GENRES:
            params.append(f"genre[]={genre}")
        elif genre:
            # find genre key by name (case-insensitive)
            for gid, gname in GENRES.items():
                if gname.lower() == genre.lower():
                    params.append(f"genre[]={gid}")
                    break

        if letter:
            params.append(f"title={letter.strip().upper()}")

        query_str = "&".join(params)
        url = f"https://{self.website}/catalogue/?{query_str}"

        try:
            resp = self.session.get(url, timeout=15)
        except requests.RequestException as e:
            raise InvalidStatusCode(f"Erreur d'accès au catalogue : {e}", "critical")

        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        for div in soup.find_all("div", {"class": "bsx"}):
            a = div.find("a")
            if not a or not a.get("href"):
                continue
            title = a.get("title") or a.get_text(strip=True)
            img = div.find("img")
            cover = img.get("src") if img else ""
            epxs = div.find("span", {"class": "epxs"}) or div.find("div", {"class": "epxs"})
            latest = epxs.get_text(strip=True) if epxs else ""
            items.append({
                "title": title,
                "url": a["href"],
                "cover": cover,
                "latest": latest
            })

        return items

    def get_random_manga(self) -> dict:
        """
        Fetches a random surprise manga from the catalog!
        """
        page = random.randint(1, 15)
        items = self.get_catalogue(order="popular", page=page)
        if not items:
            items = self.get_catalogue(order="popular", page=1)
        if not items:
            raise NoResultsFound("Impossible de récupérer un manga aléatoire.")

        chosen = random.choice(items)
        return self.get_manga_details(chosen["url"])

    def get_manga_details(self, manga_url: str) -> dict:
        """
        Retrieves full metadata and chapters for a manga.
        """
        try:
            resp = self.session.get(manga_url, timeout=15)
        except requests.RequestException as e:
            raise InvalidStatusCode(f"Erreur d'accès à {manga_url} : {e}")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_elt = soup.find("h1", {"class": "entry-title"})
        title = title_elt.get_text(strip=True) if title_elt else manga_url.rstrip("/").split("/")[-1].replace("-", " ").title()

        # Cover
        thumb = soup.find("div", {"class": "thumb"})
        img = thumb.find("img") if thumb else None
        cover = img.get("src") if img else ""

        # Synopsis
        synopsis_div = soup.find("div", {"itemprop": "description"}) or soup.find("div", {"class": "entry-content"})
        synopsis = synopsis_div.get_text(strip=True) if synopsis_div else ""

        # Genres
        genre_div = soup.find("div", {"class": "seriestugenre"})
        genres = [a.get_text(strip=True) for a in genre_div.find_all("a")] if genre_div else []

        # Chapters
        chapters = self.get_available_chapters(manga_url)

        return {
            "title": title,
            "url": manga_url,
            "cover": cover,
            "synopsis": synopsis,
            "genres": genres,
            "chapters": chapters
        }

    def get_available_chapters(self, manga_url: str) -> list[dict]:
        """
        Retrieves all available chapters from a manga's catalogue page.
        Returns a list ordered chronologically (oldest to newest):
        [{'title': str, 'url': str, 'index': int}]
        """
        try:
            resp = self.session.get(manga_url, timeout=15)
        except requests.RequestException as e:
            raise InvalidStatusCode(f"Erreur lors de l'accès à {manga_url} : {e}", "critical")

        if resp.status_code != 200:
            raise InvalidStatusCode(f"{manga_url} a retourné le code statut {resp.status_code}", "critical")

        soup = BeautifulSoup(resp.text, "html.parser")
        chapter_divs = soup.find_all("div", {"class": "eph-num"})
        
        raw_chapters = []
        for div in chapter_divs:
            a = div.find("a")
            if a and a.get("href"):
                title_span = a.find("span", {"class": "chapternum"})
                title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)
                raw_chapters.append({
                    "title": title,
                    "url": a["href"]
                })

        ordered = raw_chapters[::-1]
        for idx, chap in enumerate(ordered, start=1):
            chap["index"] = idx

        return ordered

    def get_chapter_images(self, chapter_url: str) -> list[str]:
        """
        Extracts all image URLs for a chapter page directly from HTML/JSON.
        """
        try:
            resp = self.session.get(chapter_url, timeout=15)
        except requests.RequestException as e:
            raise ChapterDownloadError(f"Erreur d'accès au chapitre {chapter_url} : {e}")

        if resp.status_code != 200:
            raise ChapterDownloadError(f"Le chapitre {chapter_url} a retourné le code {resp.status_code}")

        html = resp.text

        # 1. Primary: ts_reader.run JSON payload
        match = re.search(r"ts_reader\.run\(([\s\S]*?)\);", html)
        if match:
            try:
                data = json.loads(match.group(1))
                sources = data.get("sources", [])
                if sources and "images" in sources[0]:
                    images = sources[0]["images"]
                    cleaned = [self._clean_image_url(u) for u in images if u]
                    if cleaned:
                        return cleaned
            except Exception:
                pass

        # 2. Secondary: "images": [...] pattern
        match_arr = re.search(r'"images"\s*:\s*(\[[^\]]+\])', html)
        if match_arr:
            try:
                images = json.loads(match_arr.group(1))
                cleaned = [self._clean_image_url(u) for u in images if u]
                if cleaned:
                    return cleaned
            except Exception:
                pass

        # 3. Fallback: Parse readerarea DOM
        soup = BeautifulSoup(html, "html.parser")
        readerarea = soup.find("div", {"id": "readerarea"})
        if readerarea:
            images = []
            for img in readerarea.find_all("img"):
                src = img.get("data-src") or img.get("src") or img.get("data-lazy-src")
                if src and not any(src.lower().endswith(ext) for ext in [".svg", ".gif"]):
                    images.append(self._clean_image_url(src))
            if images:
                return images

        return []

    def _clean_image_url(self, url: str) -> str:
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        elif url.startswith("http://"):
            return "https://" + url[7:]
        return url

    def download_image_single(
        self,
        url: str,
        index: int,
        retries: int = 3,
        byte_cb: Optional[Callable[[int], None]] = None
    ) -> tuple[int, str, bytes]:
        filename = url.split("?")[0].split("/")[-1]
        for attempt in range(1, retries + 1):
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code == 200 and len(r.content) > 100:
                    if byte_cb:
                        byte_cb(len(r.content))
                    return (index, filename, r.content)
            except Exception:
                time.sleep(0.4 * attempt)
        raise ChapterDownloadError(f"Échec du téléchargement de l'image : {url}")

    def download_chapter_images(self, urls: list[str]) -> list[tuple[str, bytes]]:
        return self.download_chapter_images_with_cb(urls, None, None)

    def download_chapter_images_with_cb(
        self,
        urls: list[str],
        byte_cb: Optional[Callable[[int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> list[tuple[str, bytes]]:
        results: list[tuple[int, str, bytes]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(self.download_image_single, url, idx, 3, byte_cb): idx
                for idx, url in enumerate(urls)
            }
            for future in as_completed(future_to_idx):
                if cancel_check and cancel_check():
                    break
                res = future.result()
                results.append(res)

        results.sort(key=lambda x: x[0])
        return [(filename, raw_bytes) for _, filename, raw_bytes in results]

    def save_chapter(
        self,
        images_data: list[tuple[str, bytes]],
        manga_name: str,
        chapter_title: str,
        fmt: str = "pdf"
    ) -> str:
        safe_manga = sanitize_filename(manga_name)
        safe_chapter = sanitize_filename(chapter_title)

        manga_dir = os.path.join(self.out_folder, safe_manga)
        os.makedirs(manga_dir, exist_ok=True)

        created_files = []
        fmt_lower = fmt.lower()

        if fmt_lower in ("pdf", "both", "all"):
            pdf_path = os.path.join(manga_dir, f"{safe_chapter}.pdf")
            if save_images_as_pdf(images_data, pdf_path):
                created_files.append(pdf_path)

        if fmt_lower in ("cbz", "both", "all"):
            cbz_path = os.path.join(manga_dir, f"{safe_chapter}.cbz")
            if save_images_as_cbz(images_data, cbz_path):
                created_files.append(cbz_path)

        if fmt_lower in ("images", "img"):
            chapter_folder = os.path.join(manga_dir, safe_chapter)
            if save_raw_images(images_data, chapter_folder):
                created_files.append(chapter_folder)

        return ", ".join(created_files) if created_files else "Aucun fichier créé"
