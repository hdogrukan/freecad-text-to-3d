"""
FreeCAD Bridge
- Launches FreeCAD as a subprocess
- Writes generated Python code to a temporary .py file
- Runs the file with FreeCADCmd
- Supports macOS and Windows FreeCAD paths by default
"""

import ast
import json
import shutil
import re
import subprocess
import os
import time
import zipfile
import xml.etree.ElementTree as ET
from config import Config
from app_logger import EventLogger

class FreeCADBridge:
    def __init__(self, config: Config):
        self.config      = config
        self.output_dir  = config.OUTPUT_DIR
        self.platform    = config.PLATFORM
        self.freecad_app = config.FREECAD_APP_PATH
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
        self._manual_context_path = os.path.join(self.output_dir, "active_freecad_context.json")
        self._manual_model_path = os.path.join(self.output_dir, "active_freecad_document.FCStd")
        self._last_sanitized_code = ""
        self.event_log = EventLogger(config.EVENT_LOG_PATH)

    def launch_freecad(self) -> tuple[bool, str]:
        """Launch the FreeCAD GUI."""
        try:
            if self.platform == "Darwin" and self.freecad_app and os.path.exists(self.freecad_app):
                command = ["open", "-a", "FreeCAD"]
                if os.path.abspath(self.freecad_app) != "/Applications/FreeCAD.app":
                    command = ["open", self.freecad_app]
                self.fc_process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(3)
                return True, "FreeCAD launched"

            if self.freecad_gui and os.path.exists(self.freecad_gui):
                self.fc_process = subprocess.Popen(
                    [self.freecad_gui],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(3)
                return True, "FreeCAD launched"

            return False, (
                "FreeCAD GUI not found. Configure FREECAD_GUI or install FreeCAD. "
                f"Current path: {self.freecad_gui or 'not resolved'}"
            )
        except Exception as e:
            return False, f"FreeCAD could not be launched: {e}"

    def run_code(self, python_code: str) -> tuple[bool, str]:
        """
        Run the given FreeCAD Python code.
        Writes code to a temporary .py file and executes it with FreeCADCmd.
        """
        if not python_code.strip():
            self.event_log.log("error", "freecad", "empty_code", "No code to run")
            return False, "No code to run"

        model_ok, model_msg = self._validate_generated_model_code(python_code)
        if not model_ok:
            self.event_log.log("error", "freecad", "invalid_model_code", model_msg)
            return False, model_msg

        self._latest_model_path = self._new_model_path()
        self.event_log.log(
            "info",
            "freecad",
            "run_code_start",
            "FreeCAD model run started",
            model_path=self._latest_model_path,
            code_lines=len(python_code.splitlines()),
        )

        # Save the script.
        script_path = os.path.join(self.output_dir, "current_model.py")
        
        # Sanitize once so the executed code can also be stored in chat history.
        sanitized_code = self._sanitize_code(python_code)
        self._last_sanitized_code = sanitized_code

        # Wrap user code for safer FreeCAD execution.
        safe_code = self._wrap_code(sanitized_code, sanitize=False)
        syntax_ok, syntax_msg = self._validate_python_syntax(safe_code)
        if not syntax_ok:
            return False, syntax_msg
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(safe_code)
        self.event_log.log("info", "freecad", "script_written", "Temporary FreeCAD script written", script_path=script_path)
        
        self._current_script = script_path

        # Run through FreeCADCmd; the saved model is then handed to the GUI bridge.
        success, msg = self._execute_via_freecadcmd(script_path)
        return success, msg

    def _wrap_code(self, user_code: str, sanitize: bool = True) -> str:
        """Wrap generated code in a safe try/except runner."""
        if sanitize:
            user_code = self._sanitize_code(user_code)
        return f"""# FreeCAD Text-to-3D - Auto-generated
import FreeCAD
import Part
import Sketcher
import math

try:
    # Close existing documents for a clean run.
    for name in list(FreeCAD.listDocuments().keys()):
        FreeCAD.closeDocument(name)
except:
    pass

try:
{self._indent(user_code, 4)}

    # Save the generated model.
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
        """Remove GUI-only or version-sensitive lines before FreeCADCmd execution."""
        blocked_fragments = (
            "FreeCADGui",
            "FreeCAD.Gui",
            "activeView()",
            "fitAll()",
            "sendMsgToActiveView",
            "Gui.updateGui",
        )
        has_techdraw = "TechDraw" in code
        safe_lines = []
        for line in code.splitlines():
            line = (
                line
                .replace('"Sans"', '"Helvetica"')
                .replace("'Sans'", "'Helvetica'")
                .replace("A4_Landscape_ISO7200TD.svg", "ISO/A4_Landscape_TD.svg")
                .replace("A4_Landscape_ISO7200.svg", "ISO/A4_Landscape_TD.svg")
            )
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
            template_match = re.match(
                r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\.Template\s*=\s*TechDraw\.getStandardTemplate\((.*?)\)\s*$',
                line,
            )
            if template_match:
                indent, template_name, requested_template = template_match.groups()
                safe_lines.extend(self._rewrite_techdraw_template_assignment(indent, template_name, requested_template))
                continue
            template_type_check_match = re.match(
                r'^(\s*)if\s+not\s+hasattr\(([A-Za-z_][A-Za-z0-9_]*),\s*[\'"]Proxy[\'"]\)\s+'
                r'or\s+not\s+isinstance\(\2\.Proxy,\s*TechDraw\.DrawSVGTemplate\):\s*$',
                line,
            )
            if template_type_check_match:
                indent, template_name = template_type_check_match.groups()
                safe_lines.append(f"{indent}if isinstance({template_name}, str):")
                continue
            rewritten_scale = self._rewrite_nonuniform_scale(line)
            if rewritten_scale:
                safe_lines.extend(rewritten_scale)
                continue
            recompute_match = re.match(r"^(\s*)doc\.recompute\(\)\s*$", line)
            if has_techdraw and recompute_match:
                safe_lines.extend(self._techdraw_page_cleanup(recompute_match.group(1)))
            safe_lines.append(line)
        return "\n".join(safe_lines)

    def _rewrite_techdraw_template_assignment(self, indent: str, template_name: str, requested_template: str) -> list[str]:
        """Resolve TechDraw templates defensively across FreeCAD 1.1.x builds."""
        return [
            f"{indent}__td_template_path = ''",
            f"{indent}for __td_template_candidate in ({requested_template}, 'ISO/A4_Landscape_TD.svg', 'A4_Landscape_TD.svg', 'ISO/A4_Landscape_blank.svg', 'A4_Landscape_blank.svg'):",
            f"{indent}    try:",
            f"{indent}        __td_template_path = TechDraw.getStandardTemplate(__td_template_candidate)",
            f"{indent}    except Exception:",
            f"{indent}        __td_template_path = ''",
            f"{indent}    if __td_template_path:",
            f"{indent}        break",
            f"{indent}if not __td_template_path:",
            f"{indent}    import os",
            f"{indent}    __td_template_path = os.path.join(FreeCAD.getResourceDir(), 'Mod', 'TechDraw', 'Templates', 'ISO', 'A4_Landscape_TD.svg')",
            f"{indent}{template_name}.Template = __td_template_path",
            f"{indent}if not getattr({template_name}, 'Template', ''):",
            f"{indent}    raise RuntimeError('TechDraw template could not be resolved')",
        ]

    def _techdraw_page_cleanup(self, indent: str) -> list[str]:
        """Remove orphan TechDraw pages before recompute to avoid Template-not-set errors."""
        return [
            f"{indent}for __td_obj in list(doc.Objects):",
            f"{indent}    try:",
            f"{indent}        if getattr(__td_obj, 'TypeId', '') == 'TechDraw::DrawPage' and not getattr(__td_obj, 'Template', None):",
            f"{indent}            doc.removeObject(__td_obj.Name)",
            f"{indent}    except Exception:",
            f"{indent}        pass",
        ]

    def _rewrite_nonuniform_scale(self, line: str):
        """Rewrite unsupported FreeCAD Shape.scale(x, y, z) calls."""
        match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\.scale\((.*)\)\s*(#.*)?$", line)
        if not match:
            return None

        indent, shape_name, args_text, trailing_comment = match.groups()
        args = self._split_top_level_args(args_text)
        if len(args) != 3:
            return None
        if any("=" in arg for arg in args):
            return None

        suffix = f"  {trailing_comment}" if trailing_comment else ""
        matrix_name = f"__scale_matrix_{len(args_text)}_{len(shape_name)}"
        return [
            f"{indent}{matrix_name} = FreeCAD.Matrix(){suffix}",
            f"{indent}{matrix_name}.A11 = {args[0]}",
            f"{indent}{matrix_name}.A22 = {args[1]}",
            f"{indent}{matrix_name}.A33 = {args[2]}",
            f"{indent}{shape_name} = {shape_name}.transformGeometry({matrix_name})",
        ]

    def _split_top_level_args(self, args_text: str) -> list[str]:
        args = []
        current = []
        depth = 0
        quote = None
        escape = False

        for char in args_text:
            if quote:
                current.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue

            if char in ("'", '"'):
                quote = char
                current.append(char)
                continue

            if char in "([{":
                depth += 1
                current.append(char)
                continue
            if char in ")]}":
                depth -= 1
                current.append(char)
                continue
            if char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                continue

            current.append(char)

        if current or args_text.strip():
            args.append("".join(current).strip())
        return args

    def _validate_python_syntax(self, code: str) -> tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            line = e.lineno or "?"
            detail = e.msg or "invalid Python syntax"
            return False, f"Generated Python code is invalid or incomplete (line {line}: {detail})"

    def _validate_generated_model_code(self, code: str) -> tuple[bool, str]:
        """Reject empty or incomplete model code that is still syntactically valid."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            line = e.lineno or "?"
            detail = e.msg or "invalid Python syntax"
            return False, f"Generated Python code is invalid or incomplete (line {line}: {detail})"

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
            return False, "Generated code is incomplete: no document object was added"
        if not has_recompute:
            return False, "Generated code is incomplete: doc.recompute() was not found"
        return True, ""

    def _execute_via_freecadcmd(self, script_path: str) -> tuple[bool, str]:
        """
        Run the script with FreeCADCmd on macOS.
        FreeCADCmd creates and saves the model; the GUI bridge opens it afterward.
        """
        freecadcmd = self.freecad_cmd
        freecad_gui = self.freecad_gui
        
        # First run FreeCADCmd to create and save the model.
        if os.path.exists(freecadcmd):
            try:
                self.event_log.log("info", "freecadcmd", "start", "Running FreeCADCmd", command=freecadcmd, script_path=script_path)
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
                    "FreeCADCmd finished",
                    returncode=result.returncode,
                    output_tail=output[-1200:],
                )
                
                if "MODEL_OK:" in output:
                    # Open the saved file in the FreeCAD GUI.
                    fcstd_path = self._latest_model_path
                    if os.path.exists(fcstd_path) and os.path.exists(freecad_gui):
                        shutil.copy2(fcstd_path, self._latest_alias_path)
                        model_summary = self._inspect_model_file(fcstd_path)
                        self.event_log.log(
                            "info",
                            "freecad",
                            "model_inspected",
                            "Saved model inspected",
                            model_path=fcstd_path,
                            object_count=model_summary.get("object_count", 0),
                            techdraw_page_count=len(model_summary.get("techdraw_pages", [])),
                            techdraw_pages=model_summary.get("techdraw_pages", []),
                        )
                        self.event_log.log(
                            "success",
                            "freecad",
                            "model_saved",
                            "Model file created",
                            model_path=fcstd_path,
                            latest_path=self._latest_alias_path,
                        )
                        gui_ok, gui_msg = self._open_model_in_gui(fcstd_path)
                        if not gui_ok:
                            return False, gui_msg
                        return True, self._model_success_message(model_summary)
                    return True, "Model updated and opened in FreeCAD"
                    
                elif "MODEL_ERROR:" in output:
                    err = self._extract_model_error(output)
                    self.event_log.log("error", "freecadcmd", "model_error", err)
                    return False, f"FreeCAD error: {err}"
                else:
                    # If the marker is missing but the command succeeded, keep a warning.
                    if result.returncode == 0:
                        self.event_log.log("warn", "freecadcmd", "missing_model_ok", "FreeCADCmd finished but MODEL_OK marker was not found")
                        return True, "Command completed"
                    return False, f"Unexpected output:\n{output[:500]}"
                    
            except subprocess.TimeoutExpired:
                self.event_log.log("error", "freecadcmd", "timeout", "FreeCAD timed out")
                return False, "FreeCAD timed out (30s)"
            except FileNotFoundError:
                self.event_log.log("error", "freecadcmd", "not_found", f"FreeCADCmd not found: {freecadcmd}")
                return False, f"FreeCADCmd not found: {freecadcmd}"
            except Exception as e:
                self.event_log.log("error", "freecadcmd", "exception", str(e))
                return False, str(e)
        
        # Fallback for older FreeCAD builds without FreeCADCmd.
        elif os.path.exists(freecad_gui):
            try:
                subprocess.Popen(
                    [freecad_gui, script_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True, "Script sent to FreeCAD GUI"
            except Exception as e:
                return False, str(e)
        else:
            return False, (
                "FreeCAD installation not found. Configure FREECAD_CMD/FREECAD_PATH "
                f"or FREECAD_GUI. Current FreeCADCmd path: {freecadcmd or 'not resolved'}"
            )

    def _extract_model_error(self, output: str) -> str:
        err = output.split("MODEL_ERROR:")[-1].split("\n")[0].strip()
        traceback_lines = re.findall(
            r'File ".*?", line (\d+), in <module>\n\s*(.+)',
            output,
        )
        if not traceback_lines:
            return err

        line_number, code_line = traceback_lines[-1]
        code_line = code_line.strip()
        if code_line:
            return f"{err} (line {line_number}: {code_line})"
        return f"{err} (line {line_number})"

    def _inspect_model_file(self, fcstd_path: str) -> dict:
        summary = {
            "object_count": 0,
            "techdraw_pages": [],
            "techdraw_views": [],
            "techdraw_templates": [],
        }
        try:
            with zipfile.ZipFile(fcstd_path) as archive:
                document_xml = archive.read("Document.xml")
            root = ET.fromstring(document_xml)
        except Exception as e:
            self.event_log.log("warn", "freecad", "model_inspect_failed", str(e), model_path=fcstd_path)
            return summary

        for obj in root.findall(".//Object"):
            object_type = obj.get("type") or ""
            object_name = obj.get("name") or ""
            if not object_type:
                continue
            summary["object_count"] += 1
            if object_type == "TechDraw::DrawPage":
                summary["techdraw_pages"].append(object_name)
            elif object_type.startswith("TechDraw::DrawView"):
                summary["techdraw_views"].append(object_name)
            elif object_type == "TechDraw::DrawSVGTemplate":
                summary["techdraw_templates"].append(object_name)
        return summary

    def _model_success_message(self, model_summary: dict) -> str:
        pages = model_summary.get("techdraw_pages", [])
        if pages:
            return "Model updated and opened in FreeCAD. TechDraw page: " + ", ".join(pages)
        if "TechDraw" in self._last_sanitized_code:
            return "Model updated and opened in FreeCAD, but no TechDraw page was saved."
        return "Model updated and opened in FreeCAD"

    def _open_model_in_gui(self, fcstd_path: str) -> tuple[bool, str]:
        """Send an open-model command to the GUI bridge; launch the bridge when needed."""
        command_id = f"{time.time():.6f}"
        self._write_gui_command(command_id, fcstd_path, action="open_model")
        self.event_log.log(
            "info",
            "freecad_gui",
            "command_written",
            "FreeCAD GUI command written",
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
                "Reusing existing FreeCAD GUI bridge",
                command_id=command_id,
            )

        ok, msg = self._wait_for_gui_command(command_id, timeout=20)
        if ok:
            return True, "Model updated in FreeCAD GUI"
        return False, msg

    def sync_active_document(self) -> tuple[bool, str, dict]:
        """Ask the GUI bridge to summarize and save-copy the active FreeCAD document."""
        if not os.path.exists(self.freecad_gui):
            return False, (
                "FreeCAD GUI not found. Configure FREECAD_GUI or install FreeCAD. "
                f"Current path: {self.freecad_gui or 'not resolved'}"
            ), {}

        stale_state = self._read_json_file(self._gui_state_path)
        if not self._gui_bridge_is_active() and not stale_state.get("last_document"):
            return False, "Open FreeCAD and open or create a document before syncing.", {}

        command_id = f"{time.time():.6f}"
        self._write_gui_command(
            command_id,
            self._latest_model_path,
            action="sync_active_document",
            context_path=self._manual_context_path,
            synced_model_path=self._manual_model_path,
        )
        self.event_log.log(
            "info",
            "freecad_gui",
            "sync_command_written",
            "FreeCAD active-document sync command written",
            command_id=command_id,
        )

        if not self._gui_bridge_is_active():
            self._launch_gui_bridge(self._latest_model_path)

        ok, msg = self._wait_for_gui_sync(command_id, timeout=20)
        context = self.get_manual_context()
        return ok, msg, context if ok else {}

    def _launch_gui_bridge(self, fcstd_path: str) -> None:
        gui_script = f'''# FreeCAD Text-to-3D - persistent GUI bridge script
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
        event("warn", "state_write_failed", "GUI bridge state could not be written", traceback=traceback.format_exc())

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
        elif any(key in name for key in ("body", "car", "govde")):
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

def object_summary(obj, gui_doc):
    data = {{
        "name": obj.Name,
        "label": getattr(obj, "Label", ""),
        "type_id": getattr(obj, "TypeId", ""),
    }}
    try:
        placement = obj.Placement
        data["placement"] = {{
            "base": [placement.Base.x, placement.Base.y, placement.Base.z],
            "axis": [placement.Rotation.Axis.x, placement.Rotation.Axis.y, placement.Rotation.Axis.z],
            "angle": placement.Rotation.Angle,
        }}
    except Exception:
        pass
    try:
        shape = getattr(obj, "Shape", None)
        if shape and not shape.isNull():
            bbox = shape.BoundBox
            data["shape_type"] = getattr(shape, "ShapeType", "")
            data["bound_box"] = {{
                "x_min": bbox.XMin,
                "y_min": bbox.YMin,
                "z_min": bbox.ZMin,
                "x_max": bbox.XMax,
                "y_max": bbox.YMax,
                "z_max": bbox.ZMax,
                "x_length": bbox.XLength,
                "y_length": bbox.YLength,
                "z_length": bbox.ZLength,
            }}
            data["volume"] = getattr(shape, "Volume", None)
            data["area"] = getattr(shape, "Area", None)
    except Exception:
        pass
    try:
        gui_obj = gui_doc.getObject(obj.Name)
        data["visible"] = bool(gui_obj.Visibility)
    except Exception:
        pass
    return data

try:
    from PySide import QtCore
except Exception:
    from PySide6 import QtCore

def open_model(command_id, model_path):
    log("COMMAND_RECEIVED:" + command_id + ":" + model_path)
    event("info", "command_received", "GUI model open command received", command_id=command_id, model_path=model_path)
    try:
        for name in list(FreeCAD.listDocuments().keys()):
            try:
                FreeCAD.closeDocument(name)
                event("info", "document_closed", "Open FreeCAD document closed", document=name)
            except Exception:
                event("warn", "document_close_failed", "FreeCAD document could not be closed", document=name, traceback=traceback.format_exc())

        doc = FreeCAD.openDocument(model_path)
        FreeCAD.setActiveDocument(doc.Name)
        gui_doc = FreeCADGui.getDocument(doc.Name)
        techdraw_pages = [
            obj.Name for obj in doc.Objects
            if getattr(obj, "TypeId", "") == "TechDraw::DrawPage"
        ]

        for obj in doc.Objects:
            try:
                gui_obj = gui_doc.getObject(obj.Name)
                gui_obj.Visibility = True
                style_object(obj, gui_obj)
            except Exception:
                pass

        doc.recompute()
        event("success", "document_opened", "Current model opened in FreeCAD GUI", command_id=command_id, document=doc.Name, model_path=model_path, object_count=len(doc.Objects), techdraw_pages=techdraw_pages)

        def complete_open():
            try:
                fit_view(gui_doc)
                update_state(status="ok", last_command_id=command_id, last_model_path=model_path, last_document=doc.Name, techdraw_pages=techdraw_pages, error="")
                event("success", "script_done", "FreeCAD GUI updated the model", command_id=command_id, document=doc.Name, model_path=model_path, techdraw_pages=techdraw_pages)
            except Exception:
                update_state(status="error", last_command_id=command_id, last_model_path=model_path, error=traceback.format_exc())

        QtCore.QTimer.singleShot(250, complete_open)
        QtCore.QTimer.singleShot(800, lambda: fit_view(gui_doc))
    except Exception:
        update_state(status="error", last_command_id=command_id, last_model_path=model_path, error=traceback.format_exc())
        event("error", "open_failed", "FreeCAD GUI could not open the model", command_id=command_id, model_path=model_path, traceback=traceback.format_exc())

def sync_active_document(command_id, context_path, synced_model_path):
    event("info", "sync_received", "Active FreeCAD document sync command received", command_id=command_id)
    try:
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("No active FreeCAD document is open")

        gui_doc = FreeCADGui.getDocument(doc.Name)
        doc.recompute()
        try:
            doc.saveCopy(synced_model_path)
        except Exception:
            doc.saveAs(synced_model_path)

        context = {{
            "document": doc.Name,
            "label": getattr(doc, "Label", ""),
            "synced_model_path": synced_model_path,
            "object_count": len(doc.Objects),
            "objects": [object_summary(obj, gui_doc) for obj in doc.Objects],
        }}
        write_json(context_path, context)
        update_state(
            status="ok",
            last_sync_command_id=command_id,
            manual_context_path=context_path,
            synced_model_path=synced_model_path,
            synced_document=doc.Name,
            error="",
        )
        event("success", "sync_done", "Active FreeCAD document synced", command_id=command_id, document=doc.Name, object_count=len(doc.Objects), context_path=context_path)
    except Exception:
        update_state(status="error", last_sync_command_id=command_id, error=traceback.format_exc())
        event("error", "sync_failed", "Active FreeCAD document could not be synced", command_id=command_id, traceback=traceback.format_exc())

def poll_commands():
    global last_seen_command_id
    command = read_command()
    try:
        if command and command.get("id") and command.get("id") != last_seen_command_id:
            last_seen_command_id = command.get("id")
            action = command.get("action", "open_model")
            if action == "sync_active_document":
                sync_active_document(command.get("id"), command.get("context_path"), command.get("synced_model_path"))
            else:
                open_model(command.get("id"), command.get("model_path"))
        else:
            update_state(bridge_status="idle")
    finally:
        QtCore.QTimer.singleShot(500, poll_commands)

log("GUI_BRIDGE_START")
event("success", "bridge_started", "FreeCAD GUI bridge started")
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
            "Starting FreeCAD GUI bridge",
            command=self.freecad_gui,
            script_path=self._latest_gui_script,
            model_path=fcstd_path,
        )

    def check_freecad_installed(self) -> bool:
        return bool(
            (self.freecad_cmd and os.path.exists(self.freecad_cmd))
            or (self.freecad_gui and os.path.exists(self.freecad_gui))
            or (self.freecad_app and os.path.exists(self.freecad_app))
        )
    
    def get_output_path(self) -> str:
        return self._latest_model_path

    def get_last_sanitized_code(self) -> str:
        return self._last_sanitized_code

    def get_manual_context(self) -> dict:
        context = self._read_json_file(self._manual_context_path)
        if not context:
            return {}
        model_path = context.get("synced_model_path")
        if model_path and not os.path.exists(model_path):
            return {}
        return context

    def _new_model_path(self) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        millis = int((time.time() % 1) * 1000)
        return os.path.join(self.output_dir, f"model_{stamp}_{millis:03d}.FCStd")

    def _write_gui_command(self, command_id: str, model_path: str, action: str = "open_model", **extra) -> None:
        data = {
            "id": command_id,
            "action": action,
            "model_path": model_path,
            "created_at": time.time(),
        }
        data.update(extra)
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
                        "FreeCAD GUI command applied",
                        command_id=command_id,
                        model_path=last_state.get("last_model_path"),
                    )
                    return True, "FreeCAD GUI updated"
                if last_state.get("status") == "error":
                    error = last_state.get("error") or "FreeCAD GUI command failed"
                    self.event_log.log("error", "freecad_gui", "command_failed", error, command_id=command_id)
                    return False, f"FreeCAD GUI could not be updated: {error[:300]}"
            time.sleep(0.25)

        self.event_log.log(
            "error",
            "freecad_gui",
            "command_timeout",
            "FreeCAD GUI command timed out",
            command_id=command_id,
            last_state=last_state,
        )
        return False, "FreeCAD GUI update could not be verified. Check the Logs section in the console."

    def _wait_for_gui_sync(self, command_id: str, timeout: int = 20) -> tuple[bool, str]:
        deadline = time.time() + timeout
        last_state = {}
        while time.time() < deadline:
            last_state = self._read_json_file(self._gui_state_path)
            if last_state.get("last_sync_command_id") == command_id:
                if last_state.get("status") == "ok" and not last_state.get("error"):
                    self.event_log.log(
                        "success",
                        "freecad_gui",
                        "sync_applied",
                        "Active FreeCAD document sync applied",
                        command_id=command_id,
                        context_path=last_state.get("manual_context_path"),
                    )
                    return True, "Active FreeCAD document synced"
                if last_state.get("status") == "error":
                    error = last_state.get("error") or "Active FreeCAD document sync failed"
                    self.event_log.log("error", "freecad_gui", "sync_failed", error, command_id=command_id)
                    return False, self._friendly_sync_error(error)
            time.sleep(0.25)

        self.event_log.log(
            "error",
            "freecad_gui",
            "sync_timeout",
            "Active FreeCAD document sync timed out",
            command_id=command_id,
            last_state=last_state,
        )
        return False, "Active FreeCAD document sync could not be verified. Check the Logs section."

    def _friendly_sync_error(self, error: str) -> str:
        if "No active FreeCAD document is open" in error:
            return "No active FreeCAD document is open. Open or create a model in FreeCAD, then click Sync Active FreeCAD again."
        return "Active FreeCAD document could not be synced. Check the Logs section for details."
