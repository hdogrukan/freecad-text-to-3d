import os
import glob
import platform
import shutil
from dotenv import load_dotenv

# Load the .env file from the project root.
PROJECT_ROOT = os.path.dirname(__file__)
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))


def _expand_path(value: str) -> str:
    if not value:
        return ""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(value)))


def _first_existing(paths: list[str]) -> str:
    for path in paths:
        expanded = _expand_path(path)
        if expanded and os.path.exists(expanded):
            return expanded
    return ""


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _default_windows_freecad_home() -> str:
    roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    candidates = []
    for root in roots:
        if root:
            candidates.extend(glob.glob(os.path.join(root, "FreeCAD*")))
    candidates = sorted(set(candidates), reverse=True)
    return _first_existing(
        path for path in candidates
        if os.path.exists(os.path.join(path, "bin", "FreeCADCmd.exe"))
        or os.path.exists(os.path.join(path, "bin", "FreeCAD.exe"))
    )


def _resolve_freecad_paths() -> dict:
    system = platform.system()
    app_dir = _expand_path(
        os.environ.get("FREECAD_APP_DIR")
        or os.environ.get("FREECAD_HOME")
        or os.environ.get("FREECAD_ROOT")
        or ""
    )

    if not app_dir:
        if system == "Darwin":
            app_dir = "/Applications/FreeCAD.app"
        elif system == "Windows":
            app_dir = _default_windows_freecad_home()

    if system == "Darwin":
        default_cmd = os.path.join(app_dir, "Contents", "Resources", "bin", "FreeCADCmd") if app_dir else ""
        default_python = os.path.join(app_dir, "Contents", "Resources", "bin", "python") if app_dir else ""
        default_gui = os.path.join(app_dir, "Contents", "MacOS", "FreeCAD") if app_dir else ""
    elif system == "Windows":
        default_cmd = os.path.join(app_dir, "bin", "FreeCADCmd.exe") if app_dir else ""
        default_python = os.path.join(app_dir, "bin", "python.exe") if app_dir else ""
        default_gui = os.path.join(app_dir, "bin", "FreeCAD.exe") if app_dir else ""
    else:
        default_cmd = shutil.which("FreeCADCmd") or shutil.which("freecadcmd") or ""
        default_python = shutil.which("python3") or shutil.which("python") or ""
        default_gui = shutil.which("FreeCAD") or shutil.which("freecad") or ""

    freecad_cmd = _first_existing([
        os.environ.get("FREECAD_CMD", ""),
        os.environ.get("FREECAD_PATH", ""),
        default_cmd,
        shutil.which("FreeCADCmd.exe") or "",
        shutil.which("FreeCADCmd") or "",
        shutil.which("freecadcmd") or "",
    ])
    freecad_gui = _first_existing([
        os.environ.get("FREECAD_GUI", ""),
        default_gui,
        shutil.which("FreeCAD.exe") or "",
        shutil.which("FreeCAD") or "",
        shutil.which("freecad") or "",
    ])
    freecad_python = _first_existing([
        os.environ.get("FREECAD_PYTHON", ""),
        default_python,
    ])

    if not app_dir and freecad_cmd:
        bin_dir = os.path.dirname(freecad_cmd)
        app_dir = os.path.dirname(bin_dir)

    return {
        "platform": system,
        "app_path": app_dir,
        "cmd_path": freecad_cmd or _expand_path(os.environ.get("FREECAD_PATH", "")) or default_cmd,
        "python_path": freecad_python or default_python,
        "gui_path": freecad_gui or default_gui,
    }


FREECAD_PATHS = _resolve_freecad_paths()

class Config:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # FreeCAD paths. Environment overrides:
    # FREECAD_APP_DIR/FREECAD_HOME/FREECAD_ROOT, FREECAD_CMD/FREECAD_PATH,
    # FREECAD_GUI, FREECAD_PYTHON.
    PLATFORM      = FREECAD_PATHS["platform"]
    FREECAD_APP_PATH = FREECAD_PATHS["app_path"]
    FREECAD_PATH   = FREECAD_PATHS["cmd_path"]
    FREECAD_PYTHON = FREECAD_PATHS["python_path"]
    FREECAD_GUI    = FREECAD_PATHS["gui_path"]
    
    # Socket settings (Flask <-> FreeCAD macro communication)
    SOCKET_HOST = "127.0.0.1"
    SOCKET_PORT = 27182
    FREECAD_CMD_TIMEOUT_SECONDS = _int_env("FREECAD_CMD_TIMEOUT_SECONDS", 120, 10, 600)
    
    # Flask
    FLASK_HOST  = "127.0.0.1"
    FLASK_PORT  = 5000
    DEBUG       = False
    
    # FreeCAD output directory
    OUTPUT_DIR  = _expand_path(os.environ.get("OUTPUT_DIR", "~/freecad_text_to_3d_output"))
    CHAT_HISTORY_PATH = os.path.join(OUTPUT_DIR, "chat_history.json")
    EVENT_LOG_PATH = os.path.join(OUTPUT_DIR, "events.jsonl")
