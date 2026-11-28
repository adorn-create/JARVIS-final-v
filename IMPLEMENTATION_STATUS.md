# JARVIS implementation and verification status

This file distinguishes code present in the repository from capabilities that have been demonstrated on real hardware. A feature is not marked verified merely because a module or tool definition exists.

## Current repository baseline

| Area | Present in source | Automated coverage | Real-device validation |
|---|---|---|---|
| Local chat | Ollama and optional llama.cpp router | Client/agent tests | Model/template and memory profile not measured on every PC |
| Face authentication | Local multi-user LBPH enrollment/authentication | Limited module/controller tests | Camera, lighting, spoof resistance not certified |
| Voice | Whisper input, offline TTS, wake-word listener | Partial | Microphone/speaker matrix still required |
| HUD | Tkinter animated dashboard | Limited | Windows DPI/scaling and long-run performance pending |
| PC awareness | CPU/RAM/process-start monitor | Limited | Resource overhead benchmark pending |
| Android | Multi-device ADB, allowlisted launch, approved wireless reconnect | Not yet comprehensive | Multiple physical phones pending |
| MORPHEUS | Defender/firewall posture, bounded private-host checks, TLS, CVE metadata, read-only file hash/signature triage, process-path review alerts | Security-engine and triage tests | Defender event correlation, malware samples, and lab integration pending |
| E.V. | On-demand camera/audio/wearable/feed/data tools; observations can be passed to F.R.I.D.A.Y. fusion | Unit tests for selected helpers | Real sensor/feed adapters pending |
| F.R.I.D.A.Y. | Advisory movement, safety, diagnostics, navigation and conservative multi-source observation fusion | Unit tests for selected helpers | Continuous sensor fusion and real-world validation pending |
| ULTRON | Planning, review proposals, local saved-plan history, manual step tracking, simulation, resilience checks | Unit tests for selected helpers | Physical robotics/distributed nodes not implemented |

## Explicitly not delivered by this repository

- A newly trained multi-billion-parameter foundation model or GPT-6-equivalent local model.
- A validated 2 GB total-process or total-system memory guarantee.
- Production-grade EDR, kernel-level monitoring, malware sandboxing, automatic ransomware containment, or a validated malware classifier. Current MORPHEUS triage is read-only and heuristic; it is not an antivirus replacement.
- Face anti-spoofing / liveness detection suitable for protecting sensitive accounts.
- General-purpose Android UI automation, lock-screen interaction, or automated ADB RSA approval.
- Automatic wearable discovery, universal sensor fusion, or certified emergency detection. E.V. and F.R.I.D.A.Y. tools are currently opt-in and advisory. A new fusion helper correlates already-collected camera-motion, acoustic-level and user-reported signals, but does not continuously infer or certify emergencies.
- Real robotics, physical fleet actuation, self-replication, or unattended source-code rewriting. ULTRON can save and track advisory plans locally, but execution remains manual and approval-controlled.
- Verified cross-platform desktop automation.

## MORPHEUS read-only triage added on the upgrade branch

- `security_triage_file`: hashes one user-selected local file, inspects its header/extension, Windows download-zone marker, and Authenticode signature where available. It never executes, uploads, modifies, deletes, or quarantines the file.
- `security_defender_scan_file`: invokes a Microsoft Defender custom scan only after explicit approval. Defender may quarantine/remove a detection according to its existing policy; JARVIS does not alter that policy.
- `security_process_snapshot`: reports process images in common user-writable locations as review leads only.
- The low-overhead awareness loop now emits a rate-limited review alert when a newly observed process image launches from common user-writable locations. This is not a malware verdict and does not stop the process.

## Resource target

The 2 GB objective applies to JARVIS application overhead excluding the separately loaded LLM. It is a measurement target, not a current verified result. Optional Whisper, MediaPipe, OpenCV, camera capture, and the LLM can materially increase peak memory. Keep optional modules lazy-loaded and measure idle, voice, face, gestures, vision, and chat separately.

## Verification commands

Run from the repository root in the supported Python 3.11/3.12 virtual environment:

```powershell
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Physical acceptance testing is still required for camera, microphone, speakers, ADB USB/RSA approval, wireless reconnect, and actual local-model inference.
