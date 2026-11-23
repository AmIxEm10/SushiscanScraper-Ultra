import os
import sys
import json
from flask import Flask, render_template, request, jsonify, Response

# Add src to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from scraper import Scraper, GENRES, ORDER_OPTIONS
from download_manager import DownloadManager

app = Flask(__name__, template_folder=os.path.join(current_dir, "templates"))

# Global scraper and download manager instances (allows up to 2 simultaneous manga downloads + queue)
scraper = Scraper()
dm = DownloadManager(scraper, max_concurrent=2)

# In-memory image cache for fast cover loading
IMAGE_CACHE = {}

@app.route("/")
def index():
    return render_template("index.html", genres=GENRES, order_options=ORDER_OPTIONS)

@app.route("/api/image_proxy")
def api_image_proxy():
    """
    Proxies cover images through the backend with valid Sushiscan Referer headers,
    bypassing hotlinking protection (403 Forbidden).
    """
    img_url = request.args.get("url", "").strip()
    if not img_url:
        return Response("URL manquante", status=400)

    # Check cache
    if img_url in IMAGE_CACHE:
        content, content_type = IMAGE_CACHE[img_url]
        return Response(content, mimetype=content_type, headers={"Cache-Control": "public, max-age=86400"})

    try:
        r = scraper.session.get(img_url, timeout=12)
        if r.status_code == 200 and len(r.content) > 100:
            content_type = r.headers.get("Content-Type", "image/jpeg")
            if len(IMAGE_CACHE) > 300:
                IMAGE_CACHE.pop(next(iter(IMAGE_CACHE)))
            IMAGE_CACHE[img_url] = (r.content, content_type)
            return Response(r.content, mimetype=content_type, headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        pass

    return Response("Image indisponible", status=502)

@app.route("/api/genres")
def api_genres():
    genre_list = [{"id": k, "name": v} for k, v in GENRES.items()]
    return jsonify(genre_list)

@app.route("/api/catalogue")
def api_catalogue():
    genre = request.args.get("genre")
    order = request.args.get("order", "popular")
    page = int(request.args.get("page", 1))
    letter = request.args.get("letter")
    items = scraper.get_catalogue(genre=genre, order=order, page=page, letter=letter)
    return jsonify({"items": items, "page": page})

@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    results = scraper.search(query)
    return jsonify(results)

@app.route("/api/surprise")
def api_surprise():
    try:
        manga = scraper.get_random_manga()
        return jsonify({"success": True, "manga": manga})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/manga/details")
def api_manga_details():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL manquante"}), 400
    try:
        details = scraper.get_manga_details(url)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.json or {}
    manga_title = data.get("manga_title")
    chapters = data.get("chapters", [])
    fmt = data.get("format", "pdf")
    output_dir = data.get("output_dir", "downloads")
    workers = int(data.get("workers", 6))

    if not manga_title or not chapters:
        return jsonify({"success": False, "error": "Paramètres manquants"}), 400

    task = dm.add_download(
        manga_title=manga_title,
        chapters=chapters,
        fmt=fmt,
        output_dir=output_dir,
        workers=workers
    )

    msg = "Téléchargement démarré en simultané !" if task.status == "downloading" else "Ajouté à la file d'attente !"
    return jsonify({"success": True, "task": task.to_dict(), "message": msg})

@app.route("/api/download/status")
def api_download_status():
    return jsonify(dm.get_status())

@app.route("/api/download/cancel", methods=["POST"])
def api_download_cancel():
    data = request.json or {}
    task_id = data.get("task_id")
    if task_id:
        dm.cancel_task(task_id)
        return jsonify({"success": True, "message": "Tâche annulée"})
    else:
        dm.cancel_all()
        return jsonify({"success": True, "message": "Tous les téléchargements ont été annulés"})

@app.route("/api/download/clear", methods=["POST"])
def api_download_clear():
    dm.clear_finished()
    return jsonify({"success": True, "message": "Historique nettoyé"})

@app.route("/api/select_folder", methods=["POST"])
def api_select_folder():
    """Opens a native Windows folder picker dialog."""
    try:
        import tkinter as tk
        import tkinter.filedialog as fd
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected_dir = fd.askdirectory(title="Choisir le dossier de téléchargement")
        root.destroy()
        if selected_dir:
            return jsonify({"folder": selected_dir})
        return jsonify({"folder": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
