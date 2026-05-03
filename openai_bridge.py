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

class OpenAIBridge:
    def __init__(self, config: Config):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model  = config.OPENAI_MODEL
        self.max_completion_tokens = 8000

    def chat(self, history: list, user_message: str, language: str = "tr") -> tuple[str, str]:
        """
        history: [{"role": "user"/"assistant", "content": "..."}]
        returns: (description_text, freecad_python_code)
        """
        language = language if language in LANGUAGE_PROMPTS else "tr"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": LANGUAGE_PROMPTS[language]},
        ]
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
        messages.append({"role": "user", "content": user_message})

        request_args = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            self._token_limit_param(): self.max_completion_tokens,
        }

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

    def _complete(self, request_args: dict) -> str:
        response = self.client.chat.completions.create(**request_args)
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError(
                "The OpenAI response hit the token limit and the code was incomplete. "
                "Please split the request into smaller parts or increase the token limit."
            )
        return choice.message.content.strip()

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
