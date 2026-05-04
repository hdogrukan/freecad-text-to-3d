"""
Flask Backend
- /            -> Main chat UI
- /api/chat    -> Send message to OpenAI, generate FreeCAD code, and run it
- /api/new     -> Create a new chat
- /api/status  -> FreeCAD connection/status details
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

# Store Flask sessions server-side.
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

# Check whether FreeCAD is installed.
FREECAD_AVAILABLE = fc_bridge.check_freecad_installed()
MAX_FREECAD_REPAIR_ATTEMPTS = 2
GENERATION_MODES = {"model_only", "technical_drawing", "parametric_sketch"}


def is_repairable_model_error(message: str) -> bool:
    repairable_prefixes = (
        "FreeCAD error:",
        "Generated Python code is invalid",
        "Generated code is incomplete",
    )
    return any(message.startswith(prefix) for prefix in repairable_prefixes)


def repair_note(language: str, attempts: int) -> str:
    if language == "tr":
        return f"İlk FreeCAD çalıştırması hata verdi; kod otomatik düzeltildi ve {attempts}. denemede başarıyla çalıştırıldı."
    return f"The first FreeCAD run failed; the code was automatically repaired and succeeded on attempt {attempts}."


def normalize_generation_mode(mode: str) -> str:
    return mode if mode in GENERATION_MODES else "model_only"

# API -------------------------------------------------------------------------

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
    generation_mode = normalize_generation_mode(data.get("generation_mode", "model_only"))
    chat_id = data.get("chat_id")
    manual_context = fc_bridge.get_manual_context()
    event_log.log(
        "info",
        "api",
        "chat_request",
        "Chat request received",
        chat_id=chat_id,
        language=language,
        generation_mode=generation_mode,
        manual_context=bool(manual_context),
        message_preview=message[:120],
    )

    if not message:
        error = "Message cannot be empty"
        event_log.log("warn", "api", "empty_message", error, chat_id=chat_id)
        return jsonify({"error": error}), 400

    history = chat_store.to_openai_history(chat_id)
    event_log.log("info", "chat_store", "history_loaded", "Chat history loaded", chat_id=chat_id, history_items=len(history))

    # 1. Get a response from OpenAI.
    try:
        description, python_code = ai_bridge.chat(
            history,
            message,
            language=language,
            generation_mode=generation_mode,
            manual_context=manual_context,
        )
        event_log.log(
            "success",
            "openai",
            "completion",
            "OpenAI response received",
            chat_id=chat_id,
            code_lines=len((python_code or "").splitlines()),
            description_preview=description[:180],
        )
    except Exception as e:
        prefix = "OpenAI error"
        event_log.log("error", "openai", "completion_failed", str(e), chat_id=chat_id)
        return jsonify({"error": f"{prefix}: {str(e)}"}), 500

    if not python_code:
        python_code = chat_store.latest_python_code(chat_id)
        if python_code:
            description = "No new code block was returned, so the latest generated model code was applied again."
            event_log.log("warn", "api", "fallback_latest_code", "No new code was returned; applying the latest code again", chat_id=chat_id)

    # 2. Run FreeCAD code when available.
    fc_result = {"success": False, "message": "No code found"}
    if python_code:
        success, msg = fc_bridge.run_code(python_code)
        fc_result = {"success": success, "message": msg}
        sanitized_code = fc_bridge.get_last_sanitized_code()
        if sanitized_code:
            python_code = sanitized_code

        repair_attempts = 0
        while (
            not fc_result.get("success")
            and is_repairable_model_error(fc_result.get("message", ""))
            and repair_attempts < MAX_FREECAD_REPAIR_ATTEMPTS
        ):
            repair_attempts += 1
            event_log.log(
                "warn",
                "openai",
                "repair_attempt",
                "FreeCAD run failed; requesting repaired code",
                chat_id=chat_id,
                attempt=repair_attempts,
                error=fc_result.get("message", ""),
            )
            try:
                repaired_description, repaired_code = ai_bridge.repair_code(
                    history,
                    message,
                    python_code,
                    fc_result.get("message", ""),
                    language=language,
                    generation_mode=generation_mode,
                    manual_context=manual_context,
                )
            except Exception as e:
                event_log.log(
                    "error",
                    "openai",
                    "repair_failed",
                    str(e),
                    chat_id=chat_id,
                    attempt=repair_attempts,
                )
                break

            description = repaired_description
            python_code = repaired_code
            success, msg = fc_bridge.run_code(python_code)
            fc_result = {
                "success": success,
                "message": msg,
                "repair_attempts": repair_attempts,
            }
            sanitized_code = fc_bridge.get_last_sanitized_code()
            if sanitized_code:
                python_code = sanitized_code
            event_log.log(
                "success" if success else "error",
                "freecad",
                "repair_run_result",
                msg,
                chat_id=chat_id,
                attempt=repair_attempts,
            )

            if success:
                description = f"{description}\n\n{repair_note(language, repair_attempts)}"
                break

        if repair_attempts and "repair_attempts" not in fc_result:
            fc_result["repair_attempts"] = repair_attempts
    event_log.log(
        "success" if fc_result.get("success") else "error",
        "freecad",
        "run_result",
        fc_result.get("message", ""),
        chat_id=chat_id,
    )

    # 3. Persist chat history to disk.
    chat = chat_store.add_turn(chat_id, message, description, python_code, fc_result)
    event_log.log("info", "chat_store", "turn_saved", "Chat turn saved to disk", chat_id=chat["id"], turn_count=len(chat.get("turns", [])))

    return jsonify({
        "chat_id":       chat["id"],
        "chat_title":    chat.get("title"),
        "description":   description,
        "python_code":   python_code,
        "freecad_result": fc_result,
        "generation_mode": generation_mode,
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
        return jsonify({"error": "Chat not found"}), 404
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
    """Launch the FreeCAD GUI."""
    success, msg = fc_bridge.launch_freecad()
    return jsonify({"success": success, "message": msg})


@app.route("/api/freecad/sync", methods=["POST"])
def api_sync_active_freecad():
    """Sync the active FreeCAD GUI document into app context."""
    success, msg, context = fc_bridge.sync_active_document()
    status = 200 if success else 409
    return jsonify({
        "success": success,
        "message": msg,
        "context": context,
    }), status


# Startup ---------------------------------------------------------------------

if __name__ == "__main__":
    import webbrowser, time

    print("\n" + "═" * 55)
    print("  FreeCAD Text-to-3D")
    print("  http://127.0.0.1:5000")
    print("═" * 55)
    
    if not FREECAD_AVAILABLE:
        print("  !  FreeCAD not found: /Applications/FreeCAD.app")
        print("  -> Download it from https://www.freecad.org")
    else:
        print("  ✓  FreeCAD detected")
    
    print("  OpenAI Model:", config.OPENAI_MODEL)
    print("═" * 55 + "\n")

    # Open the browser after a short delay.
    def open_browser():
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:5000")
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.DEBUG
    )
