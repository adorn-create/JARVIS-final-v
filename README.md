# JARVIS-v6 — Local Windows Desktop Assistant

JARVIS uses Ollama for local chat and screen analysis, SQLite conversation history, optional Whisper voice input, and approval-gated Windows UI controls. Prompts and screenshots are sent only to the local Ollama server configured on loopback.

## Install
1. Install the latest Ollama for Windows from [ollama.com/download](https://ollama.com/download). Use Ollama 0.7.0 or newer for the vision model.
2. Double-click `SETUP.bat`.
3. Setup offers separate opt-in pulls for the chat and vision models. Both require several GB of disk space; the vision model is about 6 GB.
4. Choose `Y` to install optional voice/wake-word and desktop-control packages when prompted.
5. Choose `Y` at the optional face-detection prompt to install OpenCV.
6. Setup launches JARVIS. Later, use `LAUNCH.bat`.

If you skip the model pulls, run these commands manually:

```powershell
ollama run hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M
ollama pull qwen2.5vl:7b
```

The chat model is the Q4_K_M GGUF quantization of `huihui-ai/Qwen2.5-7B-Instruct-abliterated`; it is about 4.8 GB. `ollama run` opens an interactive prompt after downloading it; enter `/bye` to return to PowerShell. Setup's opt-in pull avoids opening that prompt.
The chat model runs through Ollama's local OpenAI-compatible API. The vision model is a separate local model because the chat model does not accept images.

## Settings

Relevant `.env` settings:

```ini
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

## 16 GB RAM, CPU-only JARVIS model profile

The target profile for a Windows PC with about 16 GB system RAM and no dedicated VRAM is **Qwen3-4B, quantized to GGUF Q4_K_M**, running through the in-process `llama-cpp-python` backend. Qwen3-4B is an Apache-2.0 model family; JARVIS-specific behavior will be created by fine-tuning our own adapter/model and packaging the resulting weights separately. The base model is not itself our original model. See [Qwen3-4B on Hugging Face](https://huggingface.co/Qwen/Qwen3-4B).

Suggested initial settings:

```ini
JARVIS_LLM_BACKEND=llama_cpp
JARVIS_GGUF_MODEL=models/jarvis-4b-q4_k_m.gguf
JARVIS_CONTEXT_LENGTH=3072
JARVIS_CPU_THREADS=4
JARVIS_GPU_LAYERS=0
JARVIS_MAX_TOKENS=768
```

Use a 4-bit quantized GGUF for inference. Keep context at 3072 initially and leave several GB of RAM for Windows, the HUD, voice, memory, and other applications. If the PC starts paging or becoming unresponsive, lower context to 2048 or use a smaller 1.7B Q4 model. CPU speed depends heavily on processor generation, memory bandwidth, and cooling; no fixed tokens-per-second figure is guaranteed. The model is loaded lazily on the first chat request. `JARVIS_LLM_BACKEND=auto` uses the GGUF file when the configured path exists, otherwise it falls back to Ollama for compatibility. Set it to `llama_cpp` to require the direct local backend and fail clearly instead of silently using Ollama.

Install the optional runtime in the project virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-llm.txt
```

On Windows, `llama-cpp-python` may need a compatible prebuilt CPU wheel or a C++ build toolchain. The model file is not included in Git; place it under `models\` and keep large model files out of source control.

### How we make it our own

A machine with 16 GB RAM and no VRAM is suitable for **running** a compact quantized model, but it is not a practical setup for training a multi-billion-parameter language model from scratch. CPU-only LoRA fine-tuning is possible in principle but typically very slow and memory-constrained. The plan is to create and curate a JARVIS-owned instruction/conversation dataset, fine-tune a Qwen3-4B base with LoRA/QLoRA on a temporary GPU training machine, merge/export the resulting adapter to GGUF, and run that JARVIS-specific model locally on this PC. Training hardware can be rented or borrowed; the final inference machine does not need a GPU. We will keep the training dataset, adapter, model card, evaluation prompts, and export recipe in the project so the model remains reproducible.

Do not train on passwords, private conversations, or raw camera/microphone recordings. Use curated examples and explicit user-approved feedback. The existing intent classifier remains a lightweight router; it is not the conversational model.

## Features
- JARVIS-owned lightweight intent classifier with approval-gated local feedback learning
- Local chat with the configured Ollama model and bounded tool calling
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
- Chat prompts, saved memory, window information, and screen images are processed by the local Ollama server. Model files are downloaded from Ollama when you opt in to setup pulls.
- Voice audio is transcribed locally; the transcript is sent to the local Ollama server. Wake detection runs locally and is off until you explicitly enable it.
- Face detection runs locally and is off until you explicitly enable it. While enabled, the camera stays active and the HUD shows its status and detected face count. JARVIS detects counts only: it does not identify people, save frames or biometric data, or provide access control. Turn it off with the HUD toggle or close JARVIS.
- Web search sends the search query to DuckDuckGo; opening websites connects to the selected site.
- JARVIS only saves preferences/tasks when you explicitly ask it to remember them, then asks for confirmation. `/clear` in console mode clears conversation history but preserves saved memory.
- JARVIS asks before each UI click or text entry. It will not type into password or credential-related fields. Review the exact text before approving.
- There is no arbitrary shell-execution tool. App launching is allowlisted and file search is read-only.
- Keep `.env` private. Existing OpenRouter settings in an older `.env` are ignored by this build.

## Troubleshooting
- If JARVIS cannot connect, start the Ollama Windows app or run `ollama serve`, then check `ollama list`.
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

## Windows-native defensive security engine

JARVIS includes an optional, lightweight security assessment module in src/security_engine.py. It uses the Python standard library plus the existing project dependencies; it does not load another AI model.

Available JARVIS commands:
- **Windows security posture:** read-only Microsoft Defender and Windows Firewall status via PowerShell.
- **Private-host service check:** a TCP connect-only check for one literal private, loopback, or link-local IPv4 address. Hostnames, CIDR ranges, public IPs, and arbitrary ports are rejected. Only the built-in conservative port allowlist is accepted, with a maximum of 16 ports per run.
- **Local web-header check:** inspect common security headers on a localhost/private-IP lab endpoint using an HTTP HEAD request only.
- **CVE intelligence:** query the public NIST NVD API by keyword. A CVE match is an investigation lead, not proof that a particular machine is vulnerable.
- **Safe lab demonstration:** an in-memory path-traversal validation lesson. It does not touch the network or read/write files.

Network checks and lab demonstrations require the JARVIS per-action approval prompt. The private-host scanner sends no exploit payloads, does not attempt authentication, does not brute-force, and does not execute code on the target. Controlled exploit demonstrations in this release are deliberately limited to harmless local simulations; no real exploit runner is included. Use an isolated VM snapshot for any future hands-on exploit research, and keep it disconnected from production networks.

Run the unit tests with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
