"""
FreeCAD Bridge
- FreeCAD uygulamasını subprocess olarak başlatır
- Üretilen Python kodunu bir .py dosyasına yazar
- FreeCADCmd ile bu dosyayı çalıştırır
- macOS /Applications/FreeCAD.app destekli
"""

import ast
import json
import shutil
import re
import subprocess
import os
import time
from config import Config
from app_logger import EventLogger

# FreeCAD Python scriptinin başına eklenecek init kodu
FREECAD_INIT = """
import sys
sys.path.insert(0, "/Applications/FreeCAD.app/Contents/Resources/lib/python3.x/site-packages")
"""

class FreeCADBridge:
    def __init__(self, config: Config):
        self.config      = config
        self.output_dir  = config.OUTPUT_DIR
        self.freecad_cmd = config.FREECAD_PATH
        self.freecad_gui = config.FREECAD_GUI
        self.fc_process  = None
        
        os.makedirs(self.output_dir, exist_ok=True)
        self._current_script = None
        self._latest_alias_path = os.path.join(self.output_dir, "latest.FCStd")
        self._latest_model_path = self._latest_alias_path
        self._latest_gui_script = os.path.join(self.output_dir, "open_latest_in_gui.py")
        self._latest_gui_log = os.path.join(self.output_dir, "open_latest_in_gui.log")
        self._gui_command_path = os.path.join(self.output_dir, "gui_command.json")
        self._gui_state_path = os.path.join(self.output_dir, "gui_state.json")
        self.event_log = EventLogger(config.EVENT_LOG_PATH)

    def launch_freecad(self) -> tuple[bool, str]:
        """FreeCAD GUI'yi başlat"""
        # macOS
        app_path = "/Applications/FreeCAD.app"
        
        if os.path.exists(app_path):
            try:
                self.fc_process = subprocess.Popen(
                    ["open", "-a", "FreeCAD"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(3)  # FreeCAD'in açılması için bekle
                return True, "FreeCAD başlatıldı"
            except Exception as e:
                return False, f"FreeCAD başlatılamadı: {e}"
        else:
            return False, f"FreeCAD bulunamadı: {app_path}"

    def run_code(self, python_code: str) -> tuple[bool, str]:
        """
        Verilen FreeCAD Python kodunu çalıştır.
        Kodu temp .py dosyasına yazar, FreeCADCmd ile çalıştırır.
        """
        if not python_code.strip():
            self.event_log.log("error", "freecad", "empty_code", "Çalıştırılacak kod yok")
            return False, "Çalıştırılacak kod yok"

        model_ok, model_msg = self._validate_generated_model_code(python_code)
        if not model_ok:
            self.event_log.log("error", "freecad", "invalid_model_code", model_msg)
            return False, model_msg

        self._latest_model_path = self._new_model_path()
        self.event_log.log(
            "info",
            "freecad",
            "run_code_start",
            "FreeCAD model çalıştırma başladı",
            model_path=self._latest_model_path,
            code_lines=len(python_code.splitlines()),
        )

        # Scripti kaydet
        script_path = os.path.join(self.output_dir, "current_model.py")
        
        # FreeCAD için güvenli wrapper
        safe_code = self._wrap_code(python_code)
        syntax_ok, syntax_msg = self._validate_python_syntax(safe_code)
        if not syntax_ok:
            return False, syntax_msg
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(safe_code)
        self.event_log.log("info", "freecad", "script_written", "Geçici FreeCAD script yazıldı", script_path=script_path)
        
        self._current_script = script_path

        # FreeCADCmd ile çalıştır (headless değil, GUI FreeCAD'e gönder)
        # macOS'ta en güvenilir yöntem: osascript ile FreeCAD'e AppleScript
        success, msg = self._execute_via_freecadcmd(script_path)
        return success, msg

    def _wrap_code(self, user_code: str) -> str:
        """Kullanıcı kodunu güvenli bir try/except sarmalayıcıya al"""
        user_code = self._sanitize_code(user_code)
        return f"""# FreeCAD Text-to-3D - Otomatik üretildi
import FreeCAD
import Part
import Sketcher
import math

try:
    # Mevcut belgeleri kapat (temiz başlangıç)
    for name in list(FreeCAD.listDocuments().keys()):
        FreeCAD.closeDocument(name)
except:
    pass

try:
{self._indent(user_code, 4)}

    # Kaydet
    out_path = {self._latest_model_path!r}
    if FreeCAD.ActiveDocument:
        FreeCAD.ActiveDocument.saveAs(out_path)
        print("MODEL_OK:" + out_path)

except Exception as e:
    print("MODEL_ERROR:" + str(e))
    import traceback
    traceback.print_exc()
"""

    def _indent(self, code: str, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line for line in code.splitlines())

    def _sanitize_code(self, code: str) -> str:
        """FreeCADCmd'de çalışmayan veya sürüme hassas satırları kaldır."""
        blocked_fragments = (
            "FreeCADGui",
            "FreeCAD.Gui",
            "activeView()",
            "fitAll()",
            "sendMsgToActiveView",
            "Gui.updateGui",
        )
        safe_lines = []
        for line in code.splitlines():
            if any(fragment in line for fragment in blocked_fragments):
                safe_lines.append("# GUI-only line removed for FreeCADCmd compatibility")
                continue
            support_match = re.match(
                r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\.Support\s*=\s*'
                r'\(doc\.getObject\("([^"]+)"\),\s*\[""\]\)',
                line,
            )
            if support_match:
                indent, sketch_name, plane_name = support_match.groups()
                safe_lines.extend([
                    f'{indent}plane = doc.getObject("{plane_name}")',
                    f'{indent}if hasattr({sketch_name}, "AttachmentSupport"):',
                    f'{indent}    {sketch_name}.AttachmentSupport = [(plane, "")]',
                    f'{indent}elif hasattr({sketch_name}, "Support"):',
                    f'{indent}    {sketch_name}.Support = (plane, [""])',
                ])
                continue
            generic_support_match = re.match(
                r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\.Support\s*=\s*(.+)$',
                line,
            )
            if generic_support_match:
                indent, sketch_name, value = generic_support_match.groups()
                safe_lines.extend([
                    f'{indent}if hasattr({sketch_name}, "Support"):',
                    f'{indent}    {sketch_name}.Support = {value}',
                ])
                continue
            map_mode_match = re.match(
                r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\.MapMode\s*=\s*(".*?"|\'.*?\')',
                line,
            )
            if map_mode_match:
                indent, sketch_name, map_mode = map_mode_match.groups()
                safe_lines.extend([
                    f'{indent}if hasattr({sketch_name}, "MapMode"):',
                    f'{indent}    {sketch_name}.MapMode = {map_mode}',
                ])
                continue
            safe_lines.append(line)
        return "\n".join(safe_lines)

    def _validate_python_syntax(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            line = e.lineno or "?"
            detail = e.msg or "geçersiz Python sözdizimi"
            return False, f"Üretilen Python kodu hatalı veya yarım geldi (satır {line}: {detail})"

    def _validate_generated_model_code(self, code: str) -> tuple[bool, str]:
        """Boş/yarım ama sözdizimsel olarak geçerli model kodlarını engelle."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            line = e.lineno or "?"
            detail = e.msg or "geçersiz Python sözdizimi"
            return False, f"Üretilen Python kodu hatalı veya yarım geldi (satır {line}: {detail})"

        has_add_object = False
        has_recompute = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "addObject":
                has_add_object = True
            elif node.func.attr == "recompute":
                has_recompute = True

        if not has_add_object:
            return False, "Üretilen kod yarım geldi: modele eklenecek obje bulunamadı"
        if not has_recompute:
            return False, "Üretilen kod yarım geldi: doc.recompute() bulunamadı"
        return True, ""

    def _execute_via_freecadcmd(self, script_path: str) -> tuple[bool, str]:
        """
        macOS'ta FreeCADCmd ile scripti çalıştır.
        FreeCADCmd = headless mod, model oluşturur ve kaydeder.
        Sonra FreeCAD GUI ile açılmış dosyayı gösterir.
        """
        freecadcmd = self.freecad_cmd
        freecad_gui = self.freecad_gui
        
        # Önce FreeCADCmd ile çalıştır (model oluştur + kaydet)
        if os.path.exists(freecadcmd):
            try:
                self.event_log.log("info", "freecadcmd", "start", "FreeCADCmd çalıştırılıyor", command=freecadcmd, script_path=script_path)
                result = subprocess.run(
                    [freecadcmd, script_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                output = result.stdout + result.stderr
                self.event_log.log(
                    "info" if result.returncode == 0 else "error",
                    "freecadcmd",
                    "finished",
                    "FreeCADCmd tamamlandı",
                    returncode=result.returncode,
                    output_tail=output[-1200:],
                )
                
                if "MODEL_OK:" in output:
                    # Kaydedilen dosyayı FreeCAD GUI'de aç
                    fcstd_path = self._latest_model_path
                    if os.path.exists(fcstd_path) and os.path.exists(freecad_gui):
                        shutil.copy2(fcstd_path, self._latest_alias_path)
                        self.event_log.log(
                            "success",
                            "freecad",
                            "model_saved",
                            "Model dosyası oluşturuldu",
                            model_path=fcstd_path,
                            latest_path=self._latest_alias_path,
                        )
                        gui_ok, gui_msg = self._open_model_in_gui(fcstd_path)
                        if not gui_ok:
                            return False, gui_msg
                    return True, "Model güncellendi ve FreeCAD'de açıldı"
                    
                elif "MODEL_ERROR:" in output:
                    err = output.split("MODEL_ERROR:")[-1].split("\n")[0]
                    self.event_log.log("error", "freecadcmd", "model_error", err)
                    return False, f"FreeCAD hata: {err}"
                else:
                    # Çıktıda belirteç yoksa genel başarı say
                    if result.returncode == 0:
                        self.event_log.log("warn", "freecadcmd", "missing_model_ok", "FreeCADCmd bitti ama MODEL_OK belirteci bulunamadı")
                        return True, "Komut tamamlandı"
                    return False, f"Beklenmeyen çıktı:\n{output[:500]}"
                    
            except subprocess.TimeoutExpired:
                self.event_log.log("error", "freecadcmd", "timeout", "FreeCAD zaman aşımına uğradı")
                return False, "FreeCAD zaman aşımına uğradı (30s)"
            except FileNotFoundError:
                self.event_log.log("error", "freecadcmd", "not_found", f"FreeCADCmd bulunamadı: {freecadcmd}")
                return False, f"FreeCADCmd bulunamadı: {freecadcmd}"
            except Exception as e:
                self.event_log.log("error", "freecadcmd", "exception", str(e))
                return False, str(e)
        
        # FreeCADCmd yoksa doğrudan GUI ile scripti çalıştır (eski FreeCAD sürümleri)
        elif os.path.exists(freecad_gui):
            try:
                subprocess.Popen(
                    [freecad_gui, script_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True, "Script FreeCAD GUI'ye gönderildi"
            except Exception as e:
                return False, str(e)
        else:
            return False, "FreeCAD kurulumu bulunamadı. /Applications/FreeCAD.app kontrol edin."

    def _open_model_in_gui(self, fcstd_path: str) -> tuple[bool, str]:
        """Açık FreeCAD GUI bridge'e model açma komutu gönder; yoksa bridge'i başlat."""
        command_id = f"{time.time():.6f}"
        self._write_gui_command(command_id, fcstd_path)
        self.event_log.log(
            "info",
            "freecad_gui",
            "command_written",
            "FreeCAD GUI komutu yazıldı",
            command_id=command_id,
            model_path=fcstd_path,
        )

        if not self._gui_bridge_is_active():
            self._launch_gui_bridge(fcstd_path)
        else:
            self.event_log.log(
                "info",
                "freecad_gui",
                "bridge_reuse",
                "Mevcut FreeCAD GUI bridge kullanılacak",
                command_id=command_id,
            )

        ok, msg = self._wait_for_gui_command(command_id, timeout=20)
        if ok:
            return True, "Model FreeCAD GUI'de güncellendi"
        return False, msg

    def _launch_gui_bridge(self, fcstd_path: str) -> None:
        gui_script = f'''# FreeCAD Text-to-3D - kalıcı GUI bridge scripti
import FreeCAD
import FreeCADGui
import json
import os
import time
import traceback
from datetime import datetime, timezone

log_path = {self._latest_gui_log!r}
event_log_path = {self.config.EVENT_LOG_PATH!r}
command_path = {self._gui_command_path!r}
state_path = {self._gui_state_path!r}
last_seen_command_id = None
started_at = time.time()

def log(message):
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(str(message) + "\\n")
    except Exception:
        pass

def event(level, name, message, **data):
    try:
        record = {{
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "source": "freecad_gui",
            "event": name,
            "message": message,
            "data": data,
        }}
        with open(event_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\\n")
    except Exception:
        pass

def write_json(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True)
    os.replace(tmp_path, path)

def update_state(**data):
    state = {{}}
    try:
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                state.update(existing)
    except Exception:
        pass
    state.update({{
        "bridge_active": True,
        "heartbeat_at": time.time(),
        "started_at": started_at,
    }})
    state.update(data)
    try:
        write_json(state_path, state)
    except Exception:
        event("warn", "state_write_failed", "GUI bridge state yazılamadı", traceback=traceback.format_exc())

def read_command():
    try:
        with open(command_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def style_object(obj, gui_obj):
    name = (obj.Name + " " + getattr(obj, "Label", "")).lower()
    try:
        if any(key in name for key in ("window", "windshield", "glass", "cam", "pencere")):
            gui_obj.ShapeColor = (0.25, 0.68, 1.0)
            gui_obj.Transparency = 35
        elif any(key in name for key in ("wheel", "tire", "tyre", "lastik", "teker")):
            gui_obj.ShapeColor = (0.03, 0.03, 0.035)
            gui_obj.Transparency = 0
        elif any(key in name for key in ("light", "headlamp", "far")):
            gui_obj.ShapeColor = (1.0, 0.82, 0.18)
            gui_obj.Transparency = 0
        elif any(key in name for key in ("body", "car", "gövde", "govde")):
            gui_obj.ShapeColor = (0.86, 0.12, 0.10)
            gui_obj.Transparency = 0
    except Exception:
        pass

def fit_view(gui_doc):
    try:
        view = gui_doc.ActiveView
        view.viewAxometric()
        view.fitAll()
    except Exception:
        pass

try:
    from PySide import QtCore
except Exception:
    from PySide6 import QtCore

def open_model(command_id, model_path):
    log("COMMAND_RECEIVED:" + command_id + ":" + model_path)
    event("info", "command_received", "GUI model açma komutu alındı", command_id=command_id, model_path=model_path)
    try:
        for name in list(FreeCAD.listDocuments().keys()):
            try:
                FreeCAD.closeDocument(name)
                event("info", "document_closed", "Açık FreeCAD dokümanı kapatıldı", document=name)
            except Exception:
                event("warn", "document_close_failed", "FreeCAD dokümanı kapatılamadı", document=name, traceback=traceback.format_exc())

        doc = FreeCAD.openDocument(model_path)
        FreeCAD.setActiveDocument(doc.Name)
        gui_doc = FreeCADGui.getDocument(doc.Name)

        for obj in doc.Objects:
            try:
                gui_obj = gui_doc.getObject(obj.Name)
                gui_obj.Visibility = True
                style_object(obj, gui_obj)
            except Exception:
                pass

        doc.recompute()
        event("success", "document_opened", "Güncel model FreeCAD GUI'de açıldı", command_id=command_id, document=doc.Name, model_path=model_path, object_count=len(doc.Objects))

        def complete_open():
            try:
                fit_view(gui_doc)
                update_state(status="ok", last_command_id=command_id, last_model_path=model_path, last_document=doc.Name, error="")
                event("success", "script_done", "FreeCAD GUI modeli güncelledi", command_id=command_id, document=doc.Name, model_path=model_path)
            except Exception:
                update_state(status="error", last_command_id=command_id, last_model_path=model_path, error=traceback.format_exc())

        QtCore.QTimer.singleShot(250, complete_open)
        QtCore.QTimer.singleShot(800, lambda: fit_view(gui_doc))
    except Exception:
        update_state(status="error", last_command_id=command_id, last_model_path=model_path, error=traceback.format_exc())
        event("error", "open_failed", "FreeCAD GUI modeli açamadı", command_id=command_id, model_path=model_path, traceback=traceback.format_exc())

def poll_commands():
    global last_seen_command_id
    command = read_command()
    try:
        if command and command.get("id") and command.get("id") != last_seen_command_id:
            last_seen_command_id = command.get("id")
            open_model(command.get("id"), command.get("model_path"))
        else:
            update_state(bridge_status="idle")
    finally:
        QtCore.QTimer.singleShot(500, poll_commands)

log("GUI_BRIDGE_START")
event("success", "bridge_started", "FreeCAD GUI bridge başladı")
update_state(status="ready", last_command_id="", error="")
QtCore.QTimer.singleShot(0, poll_commands)
'''
        with open(self._latest_gui_script, "w", encoding="utf-8") as f:
            f.write(gui_script)

        with open(self._latest_gui_log, "w", encoding="utf-8") as f:
            f.write("GUI bridge launch requested\\n")

        subprocess.Popen(
            [self.freecad_gui, self._latest_gui_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.event_log.log(
            "info",
            "freecad_gui",
            "launch",
            "FreeCAD GUI bridge başlatılıyor",
            command=self.freecad_gui,
            script_path=self._latest_gui_script,
            model_path=fcstd_path,
        )

    def check_freecad_installed(self) -> bool:
        return os.path.exists("/Applications/FreeCAD.app")
    
    def get_output_path(self) -> str:
        return self._latest_model_path

    def _new_model_path(self) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        millis = int((time.time() % 1) * 1000)
        return os.path.join(self.output_dir, f"model_{stamp}_{millis:03d}.FCStd")

    def _write_gui_command(self, command_id: str, model_path: str) -> None:
        data = {
            "id": command_id,
            "model_path": model_path,
            "created_at": time.time(),
        }
        tmp_path = self._gui_command_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True)
        os.replace(tmp_path, self._gui_command_path)

    def _read_json_file(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _gui_bridge_is_active(self) -> bool:
        state = self._read_json_file(self._gui_state_path)
        heartbeat = float(state.get("heartbeat_at") or 0)
        return bool(state.get("bridge_active")) and (time.time() - heartbeat) < 3

    def _wait_for_gui_command(self, command_id: str, timeout: int = 20) -> tuple[bool, str]:
        deadline = time.time() + timeout
        last_state = {}
        while time.time() < deadline:
            last_state = self._read_json_file(self._gui_state_path)
            if last_state.get("last_command_id") == command_id:
                status = last_state.get("status")
                if status == "ok" or (status in ("idle", None) and not last_state.get("error")):
                    self.event_log.log(
                        "success",
                        "freecad_gui",
                        "command_applied",
                        "FreeCAD GUI komutu uyguladı",
                        command_id=command_id,
                        model_path=last_state.get("last_model_path"),
                    )
                    return True, "FreeCAD GUI güncellendi"
                if last_state.get("status") == "error":
                    error = last_state.get("error") or "FreeCAD GUI komutu hata verdi"
                    self.event_log.log("error", "freecad_gui", "command_failed", error, command_id=command_id)
                    return False, f"FreeCAD GUI güncellenemedi: {error[:300]}"
            time.sleep(0.25)

        self.event_log.log(
            "error",
            "freecad_gui",
            "command_timeout",
            "FreeCAD GUI komutu zaman aşımına uğradı",
            command_id=command_id,
            last_state=last_state,
        )
        return False, "FreeCAD GUI güncellemesi doğrulanamadı. Konsoldaki Loglar bölümünü kontrol edin."
