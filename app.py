"""
Flask Backend
- /          → Ana sayfa (chat UI)
- /api/chat  → OpenAI'ye mesaj gönder, FreeCAD kodu üret ve çalıştır
- /api/new   → Chat geçmişini sıfırla
- /api/status → FreeCAD bağlantı durumu
"""

import os
import threading
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session

from config import Config
from openai_bridge import OpenAIBridge
from freecad_bridge import FreeCADBridge
from chat_store import ChatStore
from app_logger import EventLogger

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Session sunucu taraflı (in-memory) sakla
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "/tmp/freecad_sessions"
app.config["SESSION_PERMANENT"] = False
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
Session(app)

config     = Config()
ai_bridge  = OpenAIBridge(config)
fc_bridge  = FreeCADBridge(config)
chat_store = ChatStore(config.CHAT_HISTORY_PATH)
event_log  = EventLogger(config.EVENT_LOG_PATH)

# FreeCAD kurulu mu kontrol et
FREECAD_AVAILABLE = fc_bridge.check_freecad_installed()

# ─── API ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        freecad_ok=FREECAD_AVAILABLE,
        model=config.OPENAI_MODEL,
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True)
    message = data.get("message", "").strip()
    language = data.get("language", "tr")
    chat_id = data.get("chat_id")
    event_log.log(
        "info",
        "api",
        "chat_request",
        "Chat isteği alındı",
        chat_id=chat_id,
        language=language,
        message_preview=message[:120],
    )

    if not message:
        error = "Message cannot be empty" if language == "en" else "Mesaj boş olamaz"
        event_log.log("warn", "api", "empty_message", error, chat_id=chat_id)
        return jsonify({"error": error}), 400

    history = chat_store.to_openai_history(chat_id)
    event_log.log("info", "chat_store", "history_loaded", "Chat geçmişi yüklendi", chat_id=chat_id, history_items=len(history))

    # 1. OpenAI'dan yanıt al
    try:
        description, python_code = ai_bridge.chat(history, message, language=language)
        event_log.log(
            "success",
            "openai",
            "completion",
            "OpenAI yanıtı alındı",
            chat_id=chat_id,
            code_lines=len((python_code or "").splitlines()),
            description_preview=description[:180],
        )
    except Exception as e:
        prefix = "OpenAI error" if language == "en" else "OpenAI hatası"
        event_log.log("error", "openai", "completion_failed", str(e), chat_id=chat_id)
        return jsonify({"error": f"{prefix}: {str(e)}"}), 500

    if not python_code:
        python_code = chat_store.latest_python_code(chat_id)
        if python_code:
            description = (
                "No new code block was returned, so the latest generated model code was applied again."
                if language == "en"
                else "Yeni kod bloğu gelmediği için son üretilen model kodu tekrar uygulandı."
            )
            event_log.log("warn", "api", "fallback_latest_code", "Yeni kod gelmedi, son kod tekrar uygulanacak", chat_id=chat_id)

    # 2. FreeCAD kodu varsa çalıştır
    fc_result = {"success": False, "message": "Kod bulunamadı"}
    if python_code:
        success, msg = fc_bridge.run_code(python_code)
        fc_result = {"success": success, "message": msg}
    event_log.log(
        "success" if fc_result.get("success") else "error",
        "freecad",
        "run_result",
        fc_result.get("message", ""),
        chat_id=chat_id,
    )

    # 3. Chat geçmişini diske kaydet
    chat = chat_store.add_turn(chat_id, message, description, python_code, fc_result)
    event_log.log("info", "chat_store", "turn_saved", "Chat turn diske kaydedildi", chat_id=chat["id"], turn_count=len(chat.get("turns", [])))

    return jsonify({
        "chat_id":       chat["id"],
        "chat_title":    chat.get("title"),
        "description":   description,
        "python_code":   python_code,
        "freecad_result": fc_result,
        "history_count": len(chat.get("turns", [])),
    })


@app.route("/api/new", methods=["POST"])
def api_new_chat():
    chat = chat_store.create_chat()
    return jsonify({"ok": True, "chat": chat})


@app.route("/api/chats", methods=["GET"])
def api_chats():
    return jsonify({"chats": chat_store.list_chats()})


@app.route("/api/chats/<chat_id>", methods=["GET"])
def api_chat_detail(chat_id):
    chat = chat_store.get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat bulunamadı"}), 404
    return jsonify({"chat": chat})


@app.route("/api/chats/clear", methods=["POST"])
def api_clear_chats():
    chat_store.clear()
    return jsonify({"ok": True})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "freecad_installed": FREECAD_AVAILABLE,
        "freecad_path":      "/Applications/FreeCAD.app",
        "model":             config.OPENAI_MODEL,
        "output_dir":        config.OUTPUT_DIR,
        "event_log_path":    config.EVENT_LOG_PATH,
        "gui_log_path":      os.path.join(config.OUTPUT_DIR, "open_latest_in_gui.log"),
    })


@app.route("/api/logs", methods=["GET"])
def api_logs():
    try:
        limit = int(request.args.get("limit", 120))
    except ValueError:
        limit = 120
    return jsonify({"events": event_log.tail(limit)})


@app.route("/api/launch", methods=["POST"])
def api_launch():
    """FreeCAD GUI'yi başlat"""
    success, msg = fc_bridge.launch_freecad()
    return jsonify({"success": success, "message": msg})


# ─── Başlat ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser, time

    print("\n" + "═" * 55)
    print("  FreeCAD Text-to-3D")
    print("  http://127.0.0.1:5000")
    print("═" * 55)
    
    if not FREECAD_AVAILABLE:
        print("  ⚠  FreeCAD bulunamadı: /Applications/FreeCAD.app")
        print("  → https://www.freecad.org adresinden indirin")
    else:
        print("  ✓  FreeCAD tespit edildi")
    
    print("  OpenAI Model:", config.OPENAI_MODEL)
    print("═" * 55 + "\n")

    # Tarayıcıyı 1 saniye sonra aç
    def open_browser():
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:5000")
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.DEBUG
    )
