# Vosk Model Directory

Local STT models for the `vosk_local` engine. **Model binaries are not
committed to git** (they are 40-70 MB each); obtain them from the sources
below and drop the extracted folder here.

 Models currently supported by VERONIKA:

## English (default, required for `vosk_local`)
- `vosk-model-en-us-0.22/` (~68 MB)
- Source: copied from the Part 7 Android reference app:
  `..\..\jarvis\Playlist-main\Playlist-main\Part 7\app\src\main\assets\model-en-us\ `
  (TAMCL v1.0 attribution - see `docs/RESOURCE_INTEGRATION_MAP.md`)
- Alternatively download from https://alphacephei.com/vosk/models

## Hindi (optional, enables offline Hindi/Hinglish STT)
- `vosk-model-small-hi-0.22/` (~45 MB)
- Source: https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip

Install:
```
curl.exe -L -o vosk-model-small-hi-0.22.zip ^
  https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip
Expand-Archive vosk-model-small-hi-0.22.zip (then move the folder here)
```

## Layout requirements

Each model folder must contain an `am/` subdirectory (that is what
`voice.stt_vosk.resolve_model_for_language` uses to detect usable models).
Language detection: folder name prefixes
`vosk-model-en*` (English) / `vosk-model-small-hi*`, `vosk-model-hi*` (Hindi).

Cloud fallback for languages with no local model is controlled by the
settings toggle `voice.allow_cloud_fallback` (default: off - audio stays
local unless you explicitly allow it).
