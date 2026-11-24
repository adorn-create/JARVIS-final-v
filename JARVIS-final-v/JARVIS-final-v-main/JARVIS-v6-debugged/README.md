# JARVIS-v6 — Local Windows Desktop Assistant

JARVIS can run conversational AI directly through an embedded GGUF model using llama-cpp-python, with Ollama retained as an optional fallback and vision provider. It also includes SQLite conversation history, optional Whisper voice input, and approval-gated Windows UI controls. Local GGUF inference does not require an Ollama process.

## Install
1. Install Python 3.11 or 3.12 and double-click `SETUP.bat`.
2. Choose `Y` when asked to install the optional local AI runtime (llama-cpp-python).
3. Download a compatible GGUF model into `models/` using the instructions below. Model weights are not bundled in Git.
4. Set `JARVIS_AI_PROVIDER=auto` in `.env` (the default): JARVIS prefers the local GGUF model and uses Ollama only if local inference is unavailable.
5. Ollama is optional for chat; install it only if you want the fallback or current screen-vision feature.
6. Choose `Y` to install optional voice/wake-word and desktop-control packages when prompted. Setup launches JARVIS; later use `LAUNCH.bat`.

If you skip the model pulls, run these commands manually:

```powershell
ollama run hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M
ollama pull qwen2.5vl:7b
```

The chat model is the Q4_K_M GGUF quantization of `huihui-ai/Qwen2.5-7B-Instruct-abliterated`; it is about 4.8 GB. `ollama run` opens an interactive prompt after downloading it; enter `/bye` to return to PowerShell. Setup's opt-in pull avoids opening that prompt.
The chat model runs through Ollama's local OpenAI-compatible API. The vision model is a separate local model because the chat model does not accept images.

## JARVIS-owned local conversational runtime

The current custom Naive Bayes intent classifier is not a language model. This upgrade adds a separate local conversational inference backend: llama.cpp loads a compact Qwen2.5-1.5B-Instruct GGUF model directly in the JARVIS Python process. The model is a pretrained base that JARVIS can specialize with its system prompt, approved memories, tools, and future curated fine-tuning; this repository does not claim to train a foundation model from scratch.

Install the optional runtime:

```powershell
.venv\\Scripts\\python.exe -m pip install -r requirements-local-ai.txt
```

Download the Q4_K_M model file from [Qwen2.5-1.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) and place it at `models/jarvis-qwen2.5-1.5b-instruct-q4_k_m.gguf`. If the repository's exact filename changes, update `JARVIS_LOCAL_MODEL_PATH` to match the downloaded file. The GGUF weights are a separate download (roughly 1 GB); they are not committed to Git.

Provider behavior:
- `auto`: prefer local GGUF when the file exists; otherwise use Ollama.
- `local`: try the local GGUF model; Ollama fallback is controlled by `JARVIS_OLLAMA_FALLBACK`.
- `ollama`: always use Ollama for chat.

The local backend reads the model's embedded chat template, supports the existing OpenAI-style tool-call response contract, keeps one model instance loaded, and exposes CPU threads, context size, and GPU layers as settings. CPU is the safe default. Set GPU layers only when your llama.cpp build and GPU support them. Screen vision still uses the existing Ollama vision route in this version; text chat, reasoning, memory, and tool orchestration can run without Ollama.

## Settings

Relevant `.env` settings:

```ini
JARVIS_AI_PROVIDER=auto
JARVIS_LOCAL_MODEL_PATH=models/jarvis-qwen2.5-1.5b-instruct-q4_k_m.gguf
JARVIS_LOCAL_CONTEXT=4096
JARVIS_LOCAL_THREADS=0
JARVIS_LOCAL_GPU_LAYERS=0
JARVIS_OLLAMA_FALLBACK=1
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M
OLLAMA_VISION_MODEL=qwen2.5vl:7b
OLLAMA_REQUEST_TIMEOUT=600
JARVIS_STT_MODEL=small.en
JARVIS_STT_DEVICE=cpu
JARVIS_STT_COMPUTE=int8
JARVIS_MAX_TOOL_ROUNDS=8
JARVIS_WAKE_THRESHOLD=0.5
JARVIS_AWARENESS_INTERVAL=8
```

`OLLAMA_BASE_URL` is restricted to localhost so prompts and screenshots are not sent to a remote endpoint. Increase `OLLAMA_REQUEST_TIMEOUT` between 30 and 1800 seconds if model inference is slow.

## Custom lightweight intelligence and PC awareness

JARVIS now includes a small, locally trained Naive Bayes intent model (`src/intent_engine.py`). It classifies common request categories using a bundled seed set and approved examples stored in the existing local SQLite database. It provides a weak routing hint to the assistant; it is not a general-purpose LLM and does not execute actions. Teach it with an explicit request such as “learn that ‘check my laptop resources’ is a system request”; JARVIS asks for approval before saving the example.

A lightweight background monitor (`src/awareness.py`) samples CPU, memory, and process starts locally. It reports high resource usage and newly observed processes in the HUD. Process names are observations, not malware verdicts. It does not capture screenshots, keystrokes, microphone audio, or camera frames, and it does not kill processes or remediate threats. Configure `JARVIS_AWARENESS_INTERVAL` (seconds; minimum 3, default 8) in `.env`.

The custom intent model is the first JARVIS-owned AI component. Complex open-ended reasoning and vision still use the existing optional local Ollama models.

## Features
- JARVIS-owned lightweight intent classifier with approval-gated local feedback learning
- Local GGUF conversational AI with resource-aware llama.cpp inference and optional Ollama fallback
- Bounded tool calling, planning, and progress updates
- Always-on, low-overhead local PC awareness for CPU, RAM, and newly started processes
- Multi-step planning, progress updates, and explicit error reporting
- SQLite conversation history and user-approved saved preferences/tasks
- Search for older conversation context and saved memory; ask JARVIS to forget a saved item
- System performance dashboard and animated HUD status
- Allowlisted app launch, read-only filename search, web search, and website opening
- Local screenshot analysis with `qwen2.5vl:7b`
- Optional Windows UI Automation: list visible windows and named controls, enter text in non-password fields, and click named buttons
- UI actions require per-action approval; text entry is verified and clicks are followed by screen inspection
- Optional push-to-talk Whisper speech recognition and offline `pyttsx3` speech
- Optional “Hey JARVIS” wake word, microphone-level display, and speech interruption
- Optional local face-count detection, enabled only by its HUD toggle and confirmation

## Privacy and safety
- With the local provider, chat prompts and saved memory are processed by the local GGUF model in the JARVIS process. If fallback is enabled and local inference fails, chat is sent to the local Ollama server. Screen images still use local Ollama vision in this version.
- Voice audio is transcribed locally; the transcript is sent to the local Ollama server. Wake detection runs locally and is off until you explicitly enable it.
- Face detection runs locally and is off until you explicitly enable it. While enabled, the camera stays active and the HUD shows its status and detected face count. JARVIS detects counts only: it does not identify people, save frames or biometric data, or provide access control. Turn it off with the HUD toggle or close JARVIS.
- Web search sends the search query to DuckDuckGo; opening websites connects to the selected site.
- JARVIS only saves preferences/tasks when you explicitly ask it to remember them, then asks for confirmation. `/clear` in console mode clears conversation history but preserves saved memory.
- JARVIS asks before each UI click or text entry. It will not type into password or credential-related fields. Review the exact text before approving.
- There is no arbitrary shell-execution tool. App launching is allowlisted and file search is read-only.
- Keep `.env` private. Existing OpenRouter settings in an older `.env` are ignored by this build.

## Troubleshooting
- If local chat is unavailable, confirm the GGUF file path in `.env` and install `requirements-local-ai.txt`. If using fallback, start Ollama with `ollama serve` and check `ollama list`.
- On Windows, llama-cpp-python may require a compatible prebuilt wheel or Microsoft C++ Build Tools. If its installation fails, JARVIS can continue using Ollama.
- If a model is missing, use the commands in Install. The Hugging Face model name must match `OLLAMA_MODEL`.
- If a Hugging Face pull fails with a `realm host` mismatch, update Ollama to the latest stable Windows release and retry. This is an Ollama registry redirect issue, not a JARVIS launcher issue ([Ollama issue #15661](https://github.com/ollama/ollama/issues/15661)).
- The first Whisper use downloads the selected speech model and may take a while.
- If optional voice packages fail on Python 3.14, install Python 3.12 and create a compatible environment.
- If setup reports that an existing virtual environment uses an unsupported Python version, rename `.venv` and rerun `SETUP.bat`; JARVIS requires Python 3.11 or 3.12.
- If an app does not expose accessible UI controls, JARVIS may be unable to inspect or operate it.


## Optional hand gesture recognition

Install the optional dependencies in the activated project environment:

```powershell
pip install -r requirements-gestures.txt
```

Launch JARVIS and press **GESTURES: OFF** to enable the camera after the confirmation prompt.
Recognition is local and displays labels only (OPEN PALM, FIST, PEACE, POINT, THUMBS UP,
NO HAND). Gestures do not execute computer actions or approve prompts. Turn it off
to release the camera. Hand recognition and face detection share the camera and are
not intended to run simultaneously.


## Local face unlock (optional)

Install face-unlock dependencies with `pip install -r requirements-face.txt`, then enroll using:

```powershell
.venv\Scripts\python.exe src\main.py --enroll-face
```

After enrollment, startup requires a local face match. Profile samples are stored in `%LOCALAPPDATA%\JARVIS\face_auth\face_samples.npz`. Delete that file to remove the enrollment. The feature uses OpenCV LBPH and is a convenience lock, not strong authentication; it can be spoofed by photos/video. Do not rely on it to protect sensitive data or replace Windows sign-in.

Gesture recognition dependencies can be installed with `pip install -r requirements-gestures.txt`.


## Local multi-user face unlock

Face unlock is an optional local convenience lock, not strong anti-spoof authentication. It uses OpenCV LBPH and can be fooled by photographs/video; do not use it as the only protection for sensitive data.

Install the face dependencies with `pip install -r requirements-face.txt`. Enroll the owner first using `python src/main.py --enroll-face` (camera enrollment window; press Q to cancel). After owner enrollment, every startup requires a recognized face. The owner can add a user with `python src/main.py --enroll-face Alice`; owner authentication is required before capture. List profiles with `python src/main.py --list-faces`; remove a non-owner profile with `python src/main.py --remove-face Alice` (owner authentication required). Profiles and face samples are stored locally under `%LOCALAPPDATA%\JARVIS\face_auth`.
