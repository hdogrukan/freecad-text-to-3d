# FreeCAD Text-to-3D

[Türkçe README](README.tr.md)

A local web application that creates FreeCAD 3D models from natural-language prompts using OpenAI, Flask, and FreeCADCmd.

The project supports macOS and Windows. Default FreeCAD discovery checks the usual install locations:

```text
macOS:   /Applications/FreeCAD.app
Windows: C:\Program Files\FreeCAD*\bin\FreeCADCmd.exe
```

## Features

- 3D model generation from Turkish or English natural-language prompts
- OpenAI-powered FreeCAD Python API code generation
- Local Flask web UI
- Language selector: `TR` and `EN`
- Frontend OpenAI API key and model settings
- Generation modes:
  - `3D`: 3D model only
  - `3D + Drawing`: 3D model plus a TechDraw page when possible
  - `Sketch`: parametric sketch / PartDesign-oriented generation
- Continue a chat to revise the previous model while preserving context
- Persistent local chat history
- Reopen previous chats from the sidebar
- `.FCStd` model generation through FreeCADCmd
- Timestamped model files plus a `latest.FCStd` alias
- FreeCAD GUI bridge for opening, refreshing, centering, and basic styling
- Sync manual changes made directly in FreeCAD back into the app context
- Automatic code validation and up to 2 repair attempts when generated code fails
- FreeCADCmd sanitization for GUI-only calls and FreeCAD 1.1.x compatibility issues
- TechDraw template and font sanitization for FreeCAD 1.1.x
- Event log panel for API, OpenAI, FreeCADCmd, and FreeCAD GUI steps

## Architecture

```text
Browser UI
    <-> Flask API
Flask backend
    <-> OpenAI API
OpenAI model
    -> FreeCAD Python code
Flask backend
    <-> FreeCADCmd
FreeCADCmd
    -> .FCStd model file
FreeCAD GUI bridge
    -> opens, refreshes, and syncs the model in FreeCAD GUI
```

## Requirements

- macOS or Windows
- Python 3.10+
- FreeCAD
- OpenAI API key
- Internet connection

For custom FreeCAD installations, set `FREECAD_HOME`, `FREECAD_CMD`, `FREECAD_GUI`, or `FREECAD_PYTHON` in `.env` or your shell.

## FreeCAD Compatibility

This project has been validated on macOS with FreeCAD `1.1.1`. Windows support is wired for the standard FreeCAD layout under `C:\Program Files\FreeCAD...\bin`.

The local test installation reports:

```text
CFBundleVersion: 1.1.1
FreeCADCmd log: FreeCAD 1.1.1, Libs: 1.1.1R20260414
```

Older or newer FreeCAD versions may work, but the default paths, TechDraw template handling, and GUI bridge behavior are designed around FreeCAD `1.1.x`.

## Installation

### 1. Prepare The Repository

```bash
git clone https://github.com/hdogrukan/freecad-text-to-3d.git
cd freecad-text-to-3d
```

If you downloaded a ZIP, extract it and open the project folder in your terminal.

### 2. Install FreeCAD

Download FreeCAD from the official website:

```text
https://www.freecad.org/downloads.php
```

On macOS, move `FreeCAD.app` into the `Applications` folder. Verify the path:

```bash
ls /Applications/FreeCAD.app
```

On Windows, install FreeCAD into the default `Program Files` location, then verify that one of these files exists:

```text
C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe
C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe
```

### 3. Configure Your OpenAI API Key

For temporary use, export the key in your terminal:

```bash
export OPENAI_API_KEY="sk-..."
```

For persistent local configuration, create a `.env` file:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OUTPUT_DIR=~/freecad_text_to_3d_output
```

Do not commit `.env`. It is ignored by [.gitignore](.gitignore).

## Running

### macOS Quick Start

```bash
chmod +x start.sh
./start.sh
```

`start.sh` handles:

- Python check
- FreeCAD existence and version check
- `venv` creation
- Python dependency installation
- Output directory creation
- Flask app startup

### Windows Quick Start

Open PowerShell in the project folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start.ps1
```

`start.ps1` checks Python, detects FreeCAD from `Program Files` or environment variables, creates `venv`, installs dependencies, and starts the app.

The app runs at:

```text
http://127.0.0.1:5000
```

### Manual Start On macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

If the virtual environment already exists:

```bash
source venv/bin/activate
python app.py
```

### Manual Start On Windows

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## Usage

1. Start the Flask app.
2. Open `http://127.0.0.1:5000` in your browser.
3. Select `TR` or `EN` from the top bar.
4. If needed, enter your OpenAI API key and model in the `Settings` panel.
5. Select a generation mode: `3D`, `3D + Drawing`, or `Sketch`.
6. Type your model request in the chat box.
7. The app asks OpenAI for FreeCAD Python code, validates it, runs it through FreeCADCmd, and opens the result in FreeCAD GUI.
8. Continue in the same chat to revise the current model.
9. If you manually edit the model in FreeCAD, click `Sync Active FreeCAD` before requesting another revision.
10. Reopen previous local chats from the sidebar.
11. Use `Clear History` to delete local chat history.
12. Use `Console > Logs` to inspect API, OpenAI, FreeCADCmd, and FreeCAD GUI events.

Example prompts:

```text
An open rectangular box sized 10x10x5 cm
A hollow cylinder with 5 cm diameter, 10 cm height, and 2 mm wall thickness
A cone with 2 cm top diameter, 4 cm bottom diameter, and 8 cm height
Draw a car
Make the car convertible
Add technical drawing views from the front, top, and right
Create a parametric mounting plate with holes
```

## Generation Modes

### 3D

The default mode. It creates a direct 3D model using FreeCAD `Part` API primitives, solids, and boolean operations. It does not add a TechDraw page unless explicitly requested.

### 3D + Drawing

Creates the 3D model and adds a TechDraw page when possible. The target views are front, top, right, and isometric. TechDraw setup is wrapped defensively so the 3D model can still succeed if drawing generation fails.

For FreeCAD `1.1.x`, the app prefers the available `ISO/A4_Landscape_TD.svg` TechDraw template and avoids the missing `Sans` font by using `Helvetica` for generated drawing annotations.

### Sketch

For mechanical parts, this mode prefers a parametric PartDesign Body, Sketcher constraints, pad/pocket operations, and named dimension variables at the top of the script. For decorative or freeform models, it may still use parameterized Part primitives.

## Automatic Repair And Code Safety

The app extracts a single `python` code block from the OpenAI response and checks whether it is a runnable FreeCAD script.

Basic validation:

- Python syntax check
- At least one `doc.addObject(...)` call
- A `doc.recompute()` call
- Rejection of missing or incomplete FreeCAD code

If FreeCADCmd fails, the app sends the same context, the error message, and the failed code back to OpenAI for automatic repair. The default maximum repair attempts is `2`.

For FreeCADCmd compatibility, some generated lines are removed or rewritten:

- GUI-only calls such as `FreeCADGui`, `activeView()`, and `fitAll()` are removed
- Sketch support and map mode assignments are rewritten into safer forms
- FreeCAD 1.1.x-incompatible `shape.scale(x, y, z)` calls are converted to matrix-based non-uniform scaling
- Missing TechDraw template names such as `A4_Landscape_ISO7200TD.svg` are rewritten to `ISO/A4_Landscape_TD.svg`
- Missing `Sans` font references are rewritten to `Helvetica`
- Orphan TechDraw pages without a template are removed before `doc.recompute()` to avoid `Template not set for Page`

## OpenAI Settings And API Key Safety

OpenAI settings can be provided in two ways:

- Global default through `.env` or environment variables
- Per-browser-session override through the web UI `Settings` panel

API keys entered in the UI are handled as follows:

- They are not written to browser `localStorage` or `sessionStorage`.
- They are not returned in API responses.
- They are not written to event logs.
- They are not stored as plaintext in Flask server-side session files; the session stores only a random settings ID.
- They are kept in the running Flask process memory and disappear when the app restarts or when the 8-hour session TTL expires.
- The `Clear` button removes the in-memory OpenAI settings for the current session and falls back to `.env` defaults.

This security model is intended for local use. Do not expose the app to other machines; keep the default `127.0.0.1` host setting.

## Active FreeCAD Sync

The `Sync Active FreeCAD` button asks the FreeCAD GUI bridge to read the currently active document and save it into the app context.

Sync outputs:

- Active document copy: `active_freecad_document.FCStd`
- Object summary: `active_freecad_context.json`
- Object names, labels, types, visibility, and bounding boxes

The next chat request can use this synced document as the current model context. This is useful when you manually change a model in FreeCAD and want the AI to continue from that version.

## Output Files

Default output directory:

```text
~/freecad_text_to_3d_output
```

Important files:

| File | Description |
|---|---|
| `latest.FCStd` | Alias for the latest successful model |
| `model_*.FCStd` | Timestamped model outputs |
| `current_model.py` | Last wrapped FreeCAD Python script |
| `chat_history.json` | Local chat history |
| `events.jsonl` | API, OpenAI, FreeCADCmd, and GUI event logs |
| `open_latest_in_gui.py` | FreeCAD GUI bridge script |
| `open_latest_in_gui.log` | GUI bridge log file |
| `gui_command.json` | Flask -> GUI bridge command file |
| `gui_state.json` | GUI bridge status and heartbeat file |
| `active_freecad_context.json` | Synced active FreeCAD document summary |
| `active_freecad_document.FCStd` | Synced active FreeCAD document copy |

## Configuration

Main settings live in [config.py](config.py).

| Setting | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | `.env` or environment variable | OpenAI API key |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | Model used for code generation |
| `FREECAD_HOME` / `FREECAD_APP_DIR` / `FREECAD_ROOT` | auto-detected | FreeCAD install root |
| `FREECAD_CMD` / `FREECAD_PATH` | auto-detected | FreeCADCmd executable path |
| `FREECAD_PYTHON` | auto-detected | FreeCAD Python path |
| `FREECAD_GUI` | auto-detected | FreeCAD GUI executable path |
| `FLASK_HOST` | `127.0.0.1` | Flask host |
| `FLASK_PORT` | `5000` | Flask port |
| `DEBUG` | `False` | Flask debug mode |
| `OUTPUT_DIR` | `~/freecad_text_to_3d_output` | Local output, logs, and chat history directory |
| `CHAT_HISTORY_PATH` | `OUTPUT_DIR/chat_history.json` | Chat history file |
| `EVENT_LOG_PATH` | `OUTPUT_DIR/events.jsonl` | Event log file |

Common `.env` settings:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OUTPUT_DIR=~/freecad_text_to_3d_output
```

Optional FreeCAD overrides:

```env
# macOS
FREECAD_APP_DIR=/Applications/FreeCAD.app

# Windows
FREECAD_HOME='C:\Program Files\FreeCAD 1.1'
FREECAD_CMD='C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe'
FREECAD_GUI='C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe'
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Web UI |
| `/api/chat` | `POST` | Processes a message, generates OpenAI code, and runs the model through FreeCADCmd |
| `/api/new` | `POST` | Creates a new chat |
| `/api/chats` | `GET` | Returns the local chat list |
| `/api/chats/<chat_id>` | `GET` | Returns one chat detail |
| `/api/chats/clear` | `POST` | Clears local chat history |
| `/api/status` | `GET` | Returns FreeCAD, model, OpenAI settings status, and output directory info |
| `/api/logs` | `GET` | Returns recent event logs |
| `/api/launch` | `POST` | Launches FreeCAD GUI |
| `/api/freecad/sync` | `POST` | Syncs the active FreeCAD document into app context |
| `/api/settings/openai` | `GET` | Returns current OpenAI model and API key status; never returns the key value |
| `/api/settings/openai` | `POST` | Saves OpenAI API key and model for the current session |
| `/api/settings/openai` | `DELETE` | Clears OpenAI settings for the current session |

Example `/api/chat` request body:

```json
{
  "message": "Create a 10x10x5 cm open-top box",
  "language": "en",
  "chat_id": "optional-chat-id",
  "generation_mode": "model_only"
}
```

Valid `generation_mode` values:

```text
model_only
technical_drawing
parametric_sketch
```

## Project Structure

```text
freecad_text_to_3d/
├── app.py
├── app_logger.py
├── chat_store.py
├── config.py
├── freecad_bridge.py
├── openai_bridge.py
├── requirements.txt
├── start.sh
├── start.ps1
├── templates/
│   └── index.html
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── README.tr.md
```

File roles:

- [app.py](app.py): Flask app and API endpoints
- [openai_bridge.py](openai_bridge.py): OpenAI message construction, code extraction, generation mode prompts, and automatic repair
- [freecad_bridge.py](freecad_bridge.py): FreeCADCmd execution, code wrapping/sanitization, GUI bridge, and active document sync
- [chat_store.py](chat_store.py): Local chat history read/write
- [app_logger.py](app_logger.py): JSONL event logs
- [config.py](config.py): Environment variables, FreeCAD paths, and output directory settings
- [templates/index.html](templates/index.html): Web UI
- [start.sh](start.sh): macOS quick setup and launch script
- [start.ps1](start.ps1): Windows quick setup and launch script

## Troubleshooting

### `ModuleNotFoundError: No module named 'flask'`

Activate the virtual environment and install dependencies on macOS:

```bash
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

On Windows:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

### `OPENAI_API_KEY` Is Missing

Create `.env`, export the variable, or enter it from the UI `Settings` panel:

```bash
export OPENAI_API_KEY="sk-..."
```

### FreeCAD Is Not Found

On macOS, make sure FreeCAD exists at:

```text
/Applications/FreeCAD.app
```

On Windows, make sure FreeCAD is installed under `Program Files`, for example:

```text
C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe
```

If FreeCAD is installed elsewhere, set one or more of these in `.env`:

```env
FREECAD_HOME=/path/to/freecad
FREECAD_CMD=/path/to/FreeCADCmd
FREECAD_GUI=/path/to/FreeCAD
```

Use Windows-style paths on Windows, for example:

```env
FREECAD_HOME='C:\Program Files\FreeCAD 1.1'
FREECAD_CMD='C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe'
FREECAD_GUI='C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe'
```

### Port 5000 Is In Use

Change `FLASK_PORT` in [config.py](config.py):

```python
FLASK_PORT = 5001
```

### FreeCAD GUI Does Not Refresh

Click `Console > Logs` in the web UI. Also inspect:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/open_latest_in_gui.log
~/freecad_text_to_3d_output/gui_state.json
```

If an old GUI bridge is still running, close all FreeCAD windows and restart the Flask app.

### TechDraw Reports `Template not set for Page`

This usually means generated code created a `TechDraw::DrawPage` but failed to assign a valid `DrawSVGTemplate`. FreeCAD then keeps a template-less page and reports:

```text
<Exception> Template not set for Page
```

The app now sanitizes generated TechDraw code for FreeCAD `1.1.x` by resolving `ISO/A4_Landscape_TD.svg` and removing orphan pages before recompute. If an older generated model already contains a bad page, delete that page in FreeCAD or regenerate the model in `3D + Drawing` mode.

### FreeCAD Reports Missing `Sans` Font

FreeCAD/Qt may log:

```text
Replace uses of missing font family "Sans" with one that exists
```

Generated code is sanitized to use `Helvetica` instead of `Sans`. Existing files generated before this fix may still contain the warning until regenerated.

### Active FreeCAD Sync Fails

Open or create a document in FreeCAD GUI first. Then click `Sync Active FreeCAD` again.

Useful log files:

```text
~/freecad_text_to_3d_output/events.jsonl
~/freecad_text_to_3d_output/gui_state.json
~/freecad_text_to_3d_output/active_freecad_context.json
```

### OpenAI Returned Incomplete Or Invalid Code

The app rejects incomplete code and tries automatic repair for some FreeCAD errors. If the issue persists, make the request more explicit or split it into smaller steps. For complex technical drawing or parametric sketch requests, first generate the main model, then request details as revisions.

## Development

Local development:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Pre-PR or pre-release checklist:

- The app starts with `python app.py`
- API keys, `.env`, logs, and generated `.FCStd` files are not committed
- README or docs are updated when behavior changes
- FreeCAD-related changes are tested with FreeCAD when possible
- The UI remains usable on desktop and mobile widths

Good contribution areas:

- Improve FreeCAD model generation prompts
- Make model revision workflows more reliable
- Improve technical drawing and parametric sketch quality
- Improve FreeCAD GUI refresh, centering, and visibility behavior
- Broaden Windows installer detection and add Linux FreeCAD path support
- Add tests for chat history, code extraction, sanitization, and FreeCAD execution
- Add screenshots, demo GIFs, or sample generated models

## Before Publishing Publicly

- Do not commit `.env`.
- Do not commit `venv/` or `.venv/`.
- Do not commit `__pycache__/`.
- Do not commit generated `.FCStd` files.
- Do not paste your OpenAI API key into README, source code, issues, commits, or logs.
- If your API key was exposed in logs, rotate it in the OpenAI dashboard.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
