import os
from dotenv import load_dotenv

# Proje kökündeki .env dosyasını yükle
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

class Config:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # FreeCAD macOS yolu
    FREECAD_PATH   = "/Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd"
    FREECAD_PYTHON = "/Applications/FreeCAD.app/Contents/Resources/bin/python"
    FREECAD_GUI    = "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"
    
    # Socket ayarları (Flask ↔ FreeCAD macro iletişimi)
    SOCKET_HOST = "127.0.0.1"
    SOCKET_PORT = 27182
    
    # Flask
    FLASK_HOST  = "127.0.0.1"
    FLASK_PORT  = 5000
    DEBUG       = False
    
    # FreeCAD çıktı dosyası (macro bu dizine yazar)
    OUTPUT_DIR  = os.path.expanduser(
        os.environ.get("OUTPUT_DIR", "~/freecad_text_to_3d_output")
    )
    CHAT_HISTORY_PATH = os.path.join(OUTPUT_DIR, "chat_history.json")
    EVENT_LOG_PATH = os.path.join(OUTPUT_DIR, "events.jsonl")
