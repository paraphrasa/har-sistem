from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

from ocr import proses_nota
from sheets import tulis as sheets_tulis

import pathlib
BASE_DIR = pathlib.Path(__file__).parent.resolve()
PUBLIC_DIR = BASE_DIR / "public"

app = Flask(__name__, static_folder=str(PUBLIC_DIR), static_url_path="")
CORS(app)

# ── Static frontend ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(PUBLIC_DIR), "index.html")

# ── OCR endpoint ─────────────────────────────────────────────────────────────

@app.route("/api/ocr", methods=["POST"])
def ocr():
    """
    Terima foto nota (multipart/form-data, field: 'foto'),
    kembalikan JSON hasil ekstraksi Claude.
    """
    if "foto" not in request.files:
        return jsonify({"error": "Field 'foto' tidak ditemukan"}), 400

    foto = request.files["foto"]
    if foto.filename == "":
        return jsonify({"error": "Tidak ada file yang dipilih"}), 400

    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if foto.mimetype not in allowed:
        return jsonify({"error": f"Format tidak didukung: {foto.mimetype}"}), 400

    image_bytes = foto.read()
    media_type  = foto.mimetype

    result = proses_nota(image_bytes, media_type)
    return jsonify(result)

# ── Confirm endpoint ─────────────────────────────────────────────────────────

@app.route("/api/confirm", methods=["POST"])
def confirm():
    """
    Terima data nota yang sudah dikonfirmasi user.
    Untuk sekarang: log dan return ok.
    Nanti: tulis ke Google Sheets.
    """
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "error": "No data"}), 400

    print(f"[CONFIRM] {data.get('nama')} | {data.get('tanggal')} | {len(data.get('items', []))} items")
    result = sheets_tulis(data)
    if result["status"] == "ok":
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "error": result["error"]}), 500

# ── Health check ─────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "HAR OCR System"})

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
