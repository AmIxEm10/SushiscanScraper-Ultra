#!/usr/bin/env python3
import os
import sys
import time
import threading
import webbrowser

# Add src to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from gui_server import app

def start_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

def main():
    print("=" * 60)
    print("   🍣 SushiscanScraper Ultra - Démarrage de l'interface...")
    print("=" * 60)

    # Start Flask in daemon thread
    server_thread = threading.Thread(target=start_flask, daemon=True)
    server_thread.start()

    time.sleep(1.0)
    url = "http://127.0.0.1:5000"

    # Try native desktop window via pywebview
    use_webview = True
    try:
        import webview
        print("🖥️ Lancement de la fenêtre application native...")
        webview.create_window(
            title="🍣 SushiscanScraper Ultra",
            url=url,
            width=1280,
            height=850,
            min_size=(950, 650)
        )
        webview.start()
    except Exception as e:
        print(f"ℹ️ Ouverture dans le navigateur par défaut ({e})...")
        webbrowser.open(url)
        print(f"✨ Interface active sur : {url}")
        print("Appuyez sur Ctrl+C dans ce terminal pour quitter.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArrêt de l'application.")

if __name__ == "__main__":
    main()
