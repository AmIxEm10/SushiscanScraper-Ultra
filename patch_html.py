"""Patch index.html to add AutoPilot button, modal, CSS and JS."""
import re

HTML_PATH = r"C:\Users\maxim\.gemini\antigravity\scratch\SushiscanScraper\src\templates\index.html"

with open(HTML_PATH, encoding="utf-8") as f:
    content = f.read()

# ── 1. Add "Veille Auto" button in header ─────────────────────────────────
old_header_btn = '</button>\n    </div>\n  </header>'
new_header_btn = '''</button>
      <button class="btn btn-autopilot" id="btnAutopilot" onclick="openAutopilotModal()" title="Mode Veille : télécharge tout le catalogue automatiquement A-Z">
        🤖 Veille Auto
        <span id="badgeAutopilot" style="display:none; background:#10b981; color:#000; font-size:0.7rem; padding:0.1rem 0.4rem; border-radius:999px; font-weight:800;">ON</span>
      </button>
    </div>
  </header>'''

# Only replace the first occurrence (the header close)
content = content.replace(old_header_btn, new_header_btn, 1)

# ── 2. Add CSS for autopilot button (after .btn-surprise rule) ────────────
autopilot_css = """
    .btn-autopilot {
      background: linear-gradient(135deg, #064e3b, #065f46);
      color: #34d399;
      border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .btn-autopilot:hover { background: linear-gradient(135deg, #065f46, #047857); }
    .btn-autopilot.active { background: linear-gradient(135deg, #10b981, #059669); color: #000; box-shadow: 0 0 16px rgba(16,185,129,0.5); }

    /* AutoPilot Modal */
    .ap-modal-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 1rem;
      max-width: 560px;
      width: 95%;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .ap-alphabet-track {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
    }
    .ap-letter-pill {
      width: 2rem;
      height: 2rem;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 0.35rem;
      font-size: 0.75rem;
      font-weight: 800;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text-muted);
      transition: all 0.2s;
    }
    .ap-letter-pill.done { background: rgba(16,185,129,0.25); color: #34d399; border-color: #10b981; }
    .ap-letter-pill.active { background: var(--primary); color: #000; border-color: var(--primary); animation: pulse-glow 1s infinite; }
    .ap-letter-pill.pending { opacity: 0.4; }
    .ap-stat-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem; }
    .ap-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.6rem 0.8rem; text-align: center; }
    .ap-stat-val { font-size: 1.3rem; font-weight: 800; color: var(--primary); }
    .ap-stat-lbl { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.1rem; }
    .ap-status-bar { background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.6rem 0.8rem; font-size: 0.8rem; color: var(--text-muted); min-height: 2.2rem; display: flex; align-items: center; gap: 0.5rem; }
"""
# Insert before closing </style>
content = content.replace("  </style>", autopilot_css + "  </style>", 1)

# ── 3. Add AutoPilot modal (before the Toast notification) ────────────────
autopilot_modal = """
  <!-- AutoPilot Modal -->
  <div class="modal-overlay" id="autopilotModal">
    <div class="ap-modal-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3 style="font-size:1.1rem; font-weight:800; background:linear-gradient(135deg,#10b981,#06b6d4); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
          🤖 Mode Veille Automatique
        </h3>
        <button class="close-btn" onclick="closeModal('autopilotModal')">×</button>
      </div>

      <p style="font-size:0.8rem; color:var(--text-muted); line-height:1.5;">
        Le mode Veille télécharge <strong>automatiquement tous les mangas du catalogue</strong>, lettre par lettre
        (A → Z), puis recommence avec les nouveaux titres. Il skippe les mangas déjà téléchargés.
      </p>

      <!-- Letter progress track -->
      <div>
        <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:0.4rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;">Progression alphabétique :</div>
        <div class="ap-alphabet-track" id="apAlphabetTrack"></div>
      </div>

      <!-- Stats -->
      <div class="ap-stat-row">
        <div class="ap-stat">
          <div class="ap-stat-val" id="apStatDownloaded">0</div>
          <div class="ap-stat-lbl">Téléchargés</div>
        </div>
        <div class="ap-stat">
          <div class="ap-stat-val" id="apStatQueued">0</div>
          <div class="ap-stat-lbl">En file</div>
        </div>
        <div class="ap-stat">
          <div class="ap-stat-val" id="apStatCycle" style="color:var(--accent);">1</div>
          <div class="ap-stat-lbl">Cycle</div>
        </div>
      </div>

      <!-- Status message -->
      <div class="ap-status-bar" id="apStatusBar">
        <span>⏸ AutoPilot inactif. Configurez et démarrez.</span>
      </div>

      <!-- Settings (shown only when stopped) -->
      <div id="apSettings" style="display:flex; flex-direction:column; gap:0.6rem;">
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.6rem;">
          <div>
            <label style="font-size:0.72rem; color:var(--text-muted); display:block; margin-bottom:0.25rem;">Format :</label>
            <select id="apFormat" style="width:100%; background:var(--surface); border:1px solid var(--border); border-radius:0.4rem; padding:0.4rem 0.6rem; color:var(--text); font-size:0.85rem;">
              <option value="pdf">📄 PDF</option>
              <option value="cbz">📦 CBZ</option>
              <option value="images">🖼️ Images brutes</option>
            </select>
          </div>
          <div>
            <label style="font-size:0.72rem; color:var(--text-muted); display:block; margin-bottom:0.25rem;">Démarrer à la lettre :</label>
            <select id="apStartLetter" style="width:100%; background:var(--surface); border:1px solid var(--border); border-radius:0.4rem; padding:0.4rem 0.6rem; color:var(--text); font-size:0.85rem;">
              <option value="A">A (début)</option>
            </select>
          </div>
        </div>
        <div>
          <label style="font-size:0.72rem; color:var(--text-muted); display:block; margin-bottom:0.25rem;">Dossier de destination :</label>
          <div style="display:flex; gap:0.4rem;">
            <input type="text" id="apOutputDir" value="downloads" style="flex:1; background:var(--surface); border:1px solid var(--border); border-radius:0.4rem; padding:0.4rem 0.6rem; color:var(--text); font-size:0.85rem;">
            <button class="btn" style="background:var(--surface); border:1px solid var(--border);" onclick="pickFolderAp()">📁</button>
          </div>
        </div>
      </div>

      <!-- Action buttons -->
      <div style="display:flex; gap:0.6rem; justify-content:flex-end; flex-wrap:wrap;">
        <button class="btn" style="background:var(--surface); border:1px solid var(--border);" onclick="closeModal('autopilotModal')">Fermer</button>
        <button class="btn" id="apBtnPause" style="display:none; background:rgba(245,158,11,0.2); color:var(--warning); border:1px solid var(--warning);" onclick="autopilotPause()">⏸ Pause</button>
        <button class="btn" id="apBtnStop" style="display:none; background:var(--danger); color:#fff;" onclick="autopilotStop()">🛑 Arrêter</button>
        <button class="btn" id="apBtnStart" style="background:linear-gradient(135deg,#10b981,#059669); color:#fff; font-weight:800;" onclick="autopilotStart()">▶ Démarrer la Veille</button>
      </div>
    </div>
  </div>

"""
content = content.replace("  <!-- Toast Notification -->", autopilot_modal + "  <!-- Toast Notification -->", 1)

# ── 4. Add AutoPilot JavaScript (before closing </script>) ────────────────
autopilot_js = """
    // ═══════════════════════════════════════════════════════
    //  AUTO-PILOT  (Mode Veille Automatique)
    // ═══════════════════════════════════════════════════════
    let apPollInterval = null;
    let apAlphabet = [];

    function openAutopilotModal() {
      openModal('autopilotModal');
      refreshAutopilotStatus();
      if (!apPollInterval) apPollInterval = setInterval(refreshAutopilotStatus, 1500);
    }

    async function refreshAutopilotStatus() {
      try {
        const res = await fetch('/api/autopilot/status');
        const d = await res.json();

        // Store alphabet once
        if (d.alphabet && d.alphabet.length && !apAlphabet.length) {
          apAlphabet = d.alphabet;
          buildAlphabetTrack(apAlphabet);
          populateLetterSelect(apAlphabet);
        }

        // Update letter pills
        apAlphabet.forEach((letter, i) => {
          const pill = document.getElementById('apPill_' + letter);
          if (!pill) return;
          pill.className = 'ap-letter-pill';
          if (!d.enabled) {
            pill.classList.add('pending');
          } else if (i < d.letter_index) {
            pill.classList.add('done');
          } else if (i === d.letter_index) {
            pill.classList.add('active');
          } else {
            pill.classList.add('pending');
          }
        });

        // Stats
        document.getElementById('apStatDownloaded').innerText = d.total_downloaded || 0;
        document.getElementById('apStatQueued').innerText = d.total_queued || 0;
        document.getElementById('apStatCycle').innerText = d.cycle || 1;

        // Status bar
        const bar = document.getElementById('apStatusBar');
        if (d.enabled && !d.paused) {
          bar.innerHTML = `<span class="pulse-dot"></span> <strong>${d.current_letter}</strong> · ${escHtml(d.current_manga || 'Scan en cours…')} · ${escHtml(d.status_msg)}`;
        } else if (d.paused) {
          bar.innerHTML = `⏸ <strong>En pause</strong> — ${escHtml(d.status_msg)}`;
        } else {
          bar.innerHTML = `⏸ ${escHtml(d.status_msg || 'AutoPilot inactif. Configurez et démarrez.')}`;
        }

        // Header badge
        const badgeAp = document.getElementById('badgeAutopilot');
        badgeAp.style.display = d.enabled ? 'inline-block' : 'none';
        badgeAp.innerText = d.paused ? 'PAUSE' : 'ON';

        // Button visibility
        const headerBtn = document.getElementById('btnAutopilot');
        if (d.enabled) headerBtn.classList.add('active');
        else headerBtn.classList.remove('active');

        document.getElementById('apBtnStart').style.display = d.enabled ? 'none' : 'inline-flex';
        document.getElementById('apBtnStop').style.display = d.enabled ? 'inline-flex' : 'none';
        document.getElementById('apBtnPause').style.display = d.enabled ? 'inline-flex' : 'none';
        document.getElementById('apBtnPause').innerText = d.paused ? '▶ Reprendre' : '⏸ Pause';
        document.getElementById('apSettings').style.display = d.enabled ? 'none' : 'flex';
      } catch(e) { console.error('AutoPilot status error:', e); }
    }

    function buildAlphabetTrack(alphabet) {
      const track = document.getElementById('apAlphabetTrack');
      track.innerHTML = alphabet.map(l =>
        `<div class="ap-letter-pill pending" id="apPill_${l}">${l}</div>`
      ).join('');
    }

    function populateLetterSelect(alphabet) {
      const sel = document.getElementById('apStartLetter');
      sel.innerHTML = alphabet.map(l =>
        `<option value="${l}">${l}${l==='A' ? ' (début)' : ''}</option>`
      ).join('');
    }

    async function autopilotStart() {
      const fmt = document.getElementById('apFormat').value;
      const outputDir = document.getElementById('apOutputDir').value || 'downloads';
      const letter = document.getElementById('apStartLetter').value;
      const res = await fetch('/api/autopilot/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ format: fmt, output_dir: outputDir, letter: letter })
      });
      const d = await res.json();
      showToast(d.message || (d.success ? '🤖 Veille démarrée !' : '❌ Erreur'));
      refreshAutopilotStatus();
      openDownloadDrawer();
    }

    async function autopilotStop() {
      await fetch('/api/autopilot/stop', { method: 'POST' });
      showToast('🛑 Veille arrêtée.');
      clearInterval(apPollInterval);
      apPollInterval = null;
      refreshAutopilotStatus();
    }

    async function autopilotPause() {
      const res = await fetch('/api/autopilot/pause', { method: 'POST' });
      const d = await res.json();
      showToast(d.message);
      refreshAutopilotStatus();
    }

    async function pickFolderAp() {
      const res = await fetch('/api/select_folder', { method: 'POST' });
      const d = await res.json();
      if (d.folder) document.getElementById('apOutputDir').value = d.folder;
    }

    function escHtml(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

"""
content = content.replace("    // Initial load", autopilot_js + "    // Initial load", 1)

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch appliqué avec succès !")
print(f"Taille finale : {len(content)} octets")
