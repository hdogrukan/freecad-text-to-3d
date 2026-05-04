import ast
import re
from openai import OpenAI
from config import Config

SYSTEM_PROMPT = """
You are a FreeCAD 3D modeling expert. The user may describe models in Turkish
or English. Convert the request into complete FreeCAD Python API code.

RULES:
1. Every answer must contain exactly two parts:
   - A short explanation in the selected UI language.
   - A complete runnable FreeCAD Python script inside one ```python ... ``` block.
   - If the user asks a follow-up about the previous model, preserve the previous
     model geometry and return the FULL UPDATED script. Do not return only a patch,
     diff, or additional snippet.

2. The generated FreeCAD code must directly create 3D shapes. Do not use
   Sketcher or PartDesign unless explicitly required. Prefer the `Part` API,
   primitive solids, and boolean operations.

3. The FreeCAD code must follow this structure:
   ```python
   import FreeCAD, Part
   doc = FreeCAD.newDocument("Model")
   
   # ... model code here ...
   
   doc.recompute()
   ```

4. Use millimeters. If the user gives centimeters, multiply by 10.
5. If multiple objects are needed, add all of them to the same document.
6. The code runs in FreeCADCmd/headless mode. Do not use FreeCADGui,
   FreeCAD.Gui, activeDocument().activeView(), fitAll(),
   sendMsgToActiveView(), or GUI-only commands. The app opens the saved model
   in FreeCAD GUI after FreeCADCmd finishes.
7. Keep the code clean, commented where useful, and fully runnable.
8. Use FreeCAD APIs correctly:
   - Part.makeBox(l,w,h)
   - Part.makeCylinder(r,h)
   - Part.makeSphere(r)
   - Part.makeCone(r1,r2,h)
   - Booleans: shape.cut(other), shape.fuse(other)
   - doc.addObject("Part::Feature","Name").Shape = shape
   - Positioning: shape.translate(FreeCAD.Vector(x, y, z))
   - Rotation: shape.rotate(center, axis, angle)
   - Uniform scaling only: shape.scale(factor) or shape.scale(factor, center)
   - Never call shape.scale(x, y, z). FreeCAD 1.1.x rejects that signature.
     For non-uniform scaling, create a FreeCAD.Matrix(), set A11/A22/A33,
     then assign shape = shape.transformGeometry(matrix).

9. Python syntax must be valid:
   - Use 4-space indentation for for/if/try blocks.
   - Use ASCII variable names only.
   - Add every created visible shape to the document with doc.addObject.
   - End with doc.recompute().
   - The script must not stop at variable definitions or explanation-level code.
     It must contain at least one real `doc.addObject(...)` call.

10. Requested visual details must be clearly visible in FreeCAD:
   - When windows/glass are requested, add them as separate `Part::Feature`
     objects. Use object names containing `Window`, `Windshield`, or `Glass`.
   - Do not place windows, doors, headlights, handles, screws, or logos exactly
     coplanar with the body. Offset them outward by 0.3-1.0 mm or model them as
     thin panels to avoid z-fighting.
   - Do not only mention details in the explanation. They must be present in the
     code and added to the document.
   - Preserve the previous model's main geometry, then add the requested change
     as a clearly visible full updated model.

IMPORTANT: Start the code block with ```python and end it with ```.
Do not use any other code block.
Even if the user writes confirmation phrases like "do it", "apply it",
"uygula", "tamam", or "yap", regenerate the FULL UPDATED FreeCAD Python script
for the latest requested change. Never answer with explanation only.
"""

LANGUAGE_PROMPTS = {
    "tr": (
        "Write the short explanation in Turkish. The FreeCAD Python code must "
        "still use ASCII identifiers and follow all system rules."
    ),
    "en": (
        "Write the short explanation in English. Keep the FreeCAD Python code "
        "valid and follow all system rules."
    ),
}

GENERATION_MODE_PROMPTS = {
    "model_only": (
        "Generation mode: 3D model only. Create the FreeCAD 3D model and do not "
        "add TechDraw pages unless the user explicitly asks for technical drawings."
    ),
    "technical_drawing": (
        "Generation mode: 3D model plus technical drawing. Create the 3D model, "
        "then add a TechDraw page with front, top, right, and isometric views when "
        "possible. Use TechDraw APIs only, never FreeCADGui. Wrap TechDraw setup in "
        "try/except so the 3D model still succeeds if TechDraw is unavailable. Use "
        "Helvetica or Arial for annotations; do not request a missing font named Sans."
    ),
    "parametric_sketch": (
        "Generation mode: parametric sketch. For mechanical parts, prefer a "
        "parametric PartDesign Body with Sketcher constraints, pads, pockets, and "
        "named dimensions. Keep all key dimensions as variables at the top. If the "
        "requested object is decorative or better suited to Part primitives, still "
        "keep it parameterized and explain that a pure sketch is not appropriate."
    ),
}

class OpenAIBridge:
    def __init__(self, config: Config):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model  = config.OPENAI_MODEL
        self.max_completion_tokens = 8000

    def chat(
        self,
        history: list,
        user_message: str,
        language: str = "tr",
        generation_mode: str = "model_only",
        manual_context: dict | None = None,
    ) -> tuple[str, str]:
        """
        history: [{"role": "user"/"assistant", "content": "..."}]
        returns: (description_text, freecad_python_code)
        """
        language = self._normalize_language(language)
        generation_mode = self._normalize_generation_mode(generation_mode)
        messages = self._build_messages(history, language, generation_mode, manual_context)
        messages.append({"role": "user", "content": user_message})

        request_args = {
            "model": self.model,
            "messages": messages,
            self._token_limit_param(): self.max_completion_tokens,
        }
        self._set_temperature_if_supported(request_args, 0.3)

        full_text = self._complete(request_args)
        code = self._extract_code(full_text)
        if not self._is_complete_freecad_code(code):
            retry_messages = messages + [
                {"role": "assistant", "content": full_text},
                {
                    "role": "user",
                    "content": (
                        "Your previous answer did not include a complete runnable FreeCAD script. "
                        "Return the complete updated FreeCAD Python script now. It must include "
                        "doc.addObject(...) calls for the main model and every requested visible "
                        "detail, and it must end with doc.recompute(). Include exactly one "
                        "```python ... ``` block."
                    ),
                },
            ]
            retry_args = {**request_args, "messages": retry_messages}
            full_text = self._complete(retry_args)
            code = self._extract_code(full_text)
            if not self._is_complete_freecad_code(code):
                raise RuntimeError(
                    "The OpenAI response did not contain complete runnable FreeCAD code. "
                    "Please make the request more explicit or try again."
                )
        
        # Remove the code block from the explanation text.
        description = re.sub(r"```python.*?```", "", full_text, flags=re.DOTALL).strip()
        description = re.sub(r"```.*?```", "", description, flags=re.DOTALL).strip()
        
        return description, code

    def repair_code(
        self,
        history: list,
        user_message: str,
        failed_code: str,
        error_message: str,
        language: str = "tr",
        generation_mode: str = "model_only",
        manual_context: dict | None = None,
    ) -> tuple[str, str]:
        """Ask the model to repair code that failed in FreeCADCmd."""
        language = self._normalize_language(language)
        generation_mode = self._normalize_generation_mode(generation_mode)
        messages = self._build_messages(history, language, generation_mode, manual_context)
        messages.append({
            "role": "user",
            "content": (
                "The FreeCAD script generated for the latest user request failed when "
                "executed with FreeCADCmd on FreeCAD 1.1.1.\n\n"
                f"Latest user request:\n{user_message}\n\n"
                f"FreeCAD error:\n{error_message}\n\n"
                "Failed script:\n"
                "```python\n"
                f"{failed_code}\n"
                "```\n\n"
                "Return one complete corrected FreeCAD Python script. Preserve the "
                "requested model intent and any existing model context from the chat. "
                "Do not explain only. Do not return a patch. Include exactly one "
                "```python ... ``` block."
            ),
        })

        request_args = {
            "model": self.model,
            "messages": messages,
            self._token_limit_param(): self.max_completion_tokens,
        }
        self._set_temperature_if_supported(request_args, 0.2)

        full_text = self._complete(request_args)
        code = self._extract_code(full_text)
        if not self._is_complete_freecad_code(code):
            raise RuntimeError(
                "The OpenAI repair response did not contain complete runnable FreeCAD code."
            )

        description = re.sub(r"```python.*?```", "", full_text, flags=re.DOTALL).strip()
        description = re.sub(r"```.*?```", "", description, flags=re.DOTALL).strip()
        return description, code

    def _normalize_language(self, language: str) -> str:
        return language if language in LANGUAGE_PROMPTS else "tr"

    def _normalize_generation_mode(self, generation_mode: str) -> str:
        return generation_mode if generation_mode in GENERATION_MODE_PROMPTS else "model_only"

    def _build_messages(
        self,
        history: list,
        language: str,
        generation_mode: str = "model_only",
        manual_context: dict | None = None,
    ) -> list:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": LANGUAGE_PROMPTS[language]},
            {"role": "system", "content": GENERATION_MODE_PROMPTS[generation_mode]},
        ]
        if manual_context:
            messages.append({
                "role": "system",
                "content": self._manual_context_prompt(manual_context),
            })
        messages += history
        if history:
            messages.append({
                "role": "system",
                "content": (
                    "This conversation already contains a previous FreeCAD model. "
                    "Interpret the user's new request as a revision of the current "
                    "model unless they clearly ask for a new unrelated model. Preserve "
                    "the previous model's main geometry and return one complete, "
                    "runnable, fully updated Python script."
                ),
            })
        return messages

    def _manual_context_prompt(self, manual_context: dict) -> str:
        synced_path = manual_context.get("synced_model_path", "")
        objects = manual_context.get("objects", [])
        object_lines = []
        for obj in objects[:80]:
            bbox = obj.get("bound_box") or {}
            bbox_text = ""
            if bbox:
                bbox_text = (
                    f", bbox=({bbox.get('x_length')} x {bbox.get('y_length')} x "
                    f"{bbox.get('z_length')} mm)"
                )
            object_lines.append(
                f"- {obj.get('name')} / {obj.get('label')} / {obj.get('type_id')}{bbox_text}"
            )

        return (
            "The user synced an active FreeCAD document that may include manual edits. "
            "If the next user request refers to the current/existing drawing, use this "
            "context as the current model. You may open the synced FCStd file with "
            f"FreeCAD.openDocument({synced_path!r}) and modify named objects where "
            "reasonable. Preserve existing objects unless the user asks to delete or "
            "replace them. If an exact edit is impossible from the summary, make a "
            "best-effort visible change and keep object names clear.\n\n"
            f"Synced FCStd path: {synced_path}\n"
            "Objects:\n"
            + "\n".join(object_lines)
        )

    def _complete(self, request_args: dict) -> str:
        try:
            response = self.client.chat.completions.create(**request_args)
        except Exception as e:
            if "temperature" in request_args and self._is_unsupported_temperature_error(e):
                retry_args = dict(request_args)
                retry_args.pop("temperature", None)
                response = self.client.chat.completions.create(**retry_args)
            else:
                raise
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError(
                "The OpenAI response hit the token limit and the code was incomplete. "
                "Please split the request into smaller parts or increase the token limit."
            )
        return choice.message.content.strip()

    def _set_temperature_if_supported(self, request_args: dict, temperature: float) -> None:
        if not self._model_requires_default_temperature():
            request_args["temperature"] = temperature

    def _model_requires_default_temperature(self) -> bool:
        model = self.model.lower()
        return model.startswith(("gpt-5.5",))

    def _is_unsupported_temperature_error(self, error: Exception) -> bool:
        text = str(error).lower()
        return (
            "temperature" in text
            and (
                "unsupported_value" in text
                or "unsupported value" in text
                or "only the default" in text
                or "does not support" in text
            )
        )

    def _token_limit_param(self) -> str:
        model = self.model.lower()
        if model.startswith(("gpt-5", "o1", "o3", "o4")):
            return "max_completion_tokens"
        return "max_tokens"

    def _extract_code(self, text: str) -> str:
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```python\s*(.*)", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fallback: plain fenced block.
        match = re.search(r"```\s*(import FreeCAD.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _is_complete_freecad_code(self, code: str) -> bool:
        if not code:
            return False
        try:
            ast_tree = ast.parse(code)
        except SyntaxError:
            return False

        has_add_object = False
        has_recompute = False
        for node in ast.walk(ast_tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr == "addObject":
                    has_add_object = True
                if func.attr == "recompute":
                    has_recompute = True
        return has_add_object and has_recompute
