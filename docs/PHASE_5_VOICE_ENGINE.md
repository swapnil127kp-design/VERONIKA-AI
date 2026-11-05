# PHASE 5: VOICE ENGINE — IMPLEMENTATION LOG

**Date Started:** 2026-11-05  
**Status:** 🔄 IN PROGRESS  
**Owner:** Swapnil Kumar  
**Priority:** HIGHEST

---

## OBJECTIVES

Transform VERONIKA from a text-based AI assistant into a **fully voice-enabled conversational AI** with:

1. ✅ Complete microphone recording pipeline
2. 🔄 Local Vosk STT integration (privacy-friendly)
3. 🔄 Privacy-gated cloud STT option
4. 🔄 Speech interruption (barge-in)
5. 🔄 Hindi/Hinglish support evaluation
6. 🔄 Wake word keyring integration fix
7. 🔄 Visible mic status + emergency stop control

---

## COMPLETED WORK

### 1. Microphone Recording Pipeline ✅

**File:** `voice/microphone.py` (237 LOC)

**Implemented Features:**
- ✅ Background threaded recording
- ✅ Start/stop/cancel controls
- ✅ WAV export with proper headers
- ✅ RMS level callback for UI metering
- ✅ Device enumeration
- ✅ Explicit user-controlled lifecycle (no silent activation)
- ✅ Pure-Python RMS calculation (Python 3.13 compatible)
- ✅ Proper resource cleanup

**API:**
```python
mic = MicrophoneManager()

# List devices
devices = mic.list_input_devices()

# Start recording with live level meter
mic.start_recording(on_level=lambda level: print(f"Level: {level}"))

# Stop and get WAV bytes
wav_data = mic.stop_recording()

# Convenience: record for fixed duration
wav_data = mic.record_seconds(5.0)
```

**Format:** 16 kHz mono 16-bit PCM (Vosk-compatible)

### 2. Vosk STT Module Created ✅

**File:** `voice/stt_vosk.py`

**Status:** Stub created, needs implementation

---

## IN PROGRESS

### 3. Vosk STT Integration 🔄

**Vosk Model Location (Part 7):**
```
C:\Users\Swapnil\OneDrive\Desktop\claude code\jarvis\
  Playlist-main\Playlist-main\Part 7\app\src\main\assets\model-en-us\
```

**Required Files:**
- `am/final.mdl` (~16 MB) — acoustic model
- `graph/Gr.fst` (~24 MB) — grammar FST
- `graph/HCLr.fst` (~22 MB) — HCLG FST
- `ivector/` — ivector extractor
- `conf/` — configuration files

**Target Location:**
```
VERONIKA\voice\models\vosk-model-en-us-0.22\
```

**Implementation Plan:**
1. Copy Vosk model from Part 7 to VERONIKA
2. Add `vosk` to requirements.txt
3. Implement `VoskSTT` class in `stt_vosk.py`
4. Add model loader with caching
5. Integrate with speech_recognition.py
6. Add Hindi/Hinglish evaluation

---

## PENDING

### 4. Speech Recognition Orchestrator 🔄

**File:** `voice/speech_recognition.py`

**Needs:**
- Integration of Vosk local STT
- Privacy toggle for cloud STT
- Fallback chain: Vosk → Cloud (if enabled)
- Language detection/selection
- Confidence scoring

### 5. Speech Interruption (Barge-in) 🔄

**Requirements:**
- Monitor RMS level during TTS playback
- Detect speech onset
- Cancel TTS immediately
- Start listening
- Process interruption

**Integration Points:**
- `microphone.py` on_level callback ✅ (ready)
- `text_to_speech.py` cancellation ✅ (already has cancel())
- Main window interrupt handler (needs implementation)

### 6. Wake Word Fix 🔄

**File:** `voice/wake_word.py`

**Current Issue:** Line 59 — keyring key never written

**Fix Required:**
- Implement key storage in keyring
- Add Settings UI for wake word configuration
- Test Porcupine demo keyword
- Document custom keyword setup

### 7. Hindi/Hinglish Support 🔄

**Vosk Models Available:**
- `vosk-model-small-en-us-0.15` (Part 7 has this)
- `vosk-model-small-hi-0.22` (need to download)
- `vosk-model-small-hi-en-0.1` (Hinglish, need to download)

**Evaluation Plan:**
1. Test English model with Hinglish input
2. Download Hindi model if needed
3. Test code-mixing scenarios
4. Measure accuracy
5. Implement model switching

### 8. UI Integration 🔄

**Main Window Updates Needed:**
- Microphone button (push-to-talk)
- Live level meter
- Recording indicator
- Emergency stop button
- Voice status display
- STT engine selector

**Settings Window Updates Needed:**
- Voice input tab
- STT engine selection (Vosk/Cloud)
- Privacy toggle
- Microphone device selector
- Language selection
- Wake word configuration

---

## TECHNICAL DECISIONS

### Why Vosk?

1. ✅ **Privacy:** 100% offline, no data leaves PC
2. ✅ **No API costs:** Free forever
3. ✅ **Low latency:** ~100-300ms
4. ✅ **Model available:** Part 7 includes complete US-English model
5. ✅ **Multi-language:** Hindi/Hinglish models exist
6. ✅ **Python support:** Official `vosk` pip package
7. ✅ **Proven:** Used in production Android apps

### Why Keep Cloud STT?

1. Privacy-gated fallback for better accuracy
2. Support for languages without Vosk models
3. Owner's choice: privacy vs accuracy
4. Useful when model not available

---

## TESTING PLAN

### Unit Tests

**New test file:** `tests/test_voice_recording.py`

Test cases:
- ✅ Microphone device enumeration
- ✅ Recording start/stop lifecycle
- ✅ WAV format correctness
- ✅ RMS level calculation
- ⬜ Vosk STT accuracy
- ⬜ Language detection
- ⬜ Interruption detection

### Integration Tests

**New test file:** `tests/test_voice_integration.py`

Test cases:
- ⬜ Record → Vosk → Text pipeline
- ⬜ Record → Cloud → Text fallback
- ⬜ TTS → Interrupt → STT flow
- ⬜ Wake word → Listen → Respond cycle
- ⬜ Privacy mode enforcement

### Manual Testing

- ⬜ Push-to-talk conversation
- ⬜ Hindi/Hinglish recognition
- ⬜ Microphone device switching
- ⬜ Emergency stop during recording
- ⬜ Background noise handling
- ⬜ Long utterance handling

---

## DEPENDENCIES

### Already Installed ✅
- `SpeechRecognition>=3.10.0`
- `PyAudio>=0.2.14`
- `pyttsx3>=2.90`
- `edge-tts>=6.1.0`
- `pydub>=0.25.1`
- `numpy>=1.26.0`

### To Add
```txt
vosk>=0.3.45
```

### Optional
```txt
# Hindi/Hinglish support requires downloading models:
# https://alphacephei.com/vosk/models
# - vosk-model-small-hi-0.22 (~30 MB)
# - vosk-model-small-hi-en-0.1 (~120 MB, code-mixing)
```

---

## IMPLEMENTATION TIMELINE

### Day 1 (Today - 2026-11-05) 🔄
- ✅ Microphone recording pipeline
- ✅ Create stt_vosk.py stub
- 🔄 Copy Vosk model from Part 7
- 🔄 Implement VoskSTT class
- 🔄 Add vosk to requirements.txt
- 🔄 Test basic recognition

### Day 2 (2026-11-06)
- 🔄 Integrate Vosk with speech_recognition.py
- 🔄 Add privacy toggle
- 🔄 Implement barge-in detection
- 🔄 Add unit tests
- 🔄 Fix wake word keyring

### Day 3 (2026-11-07)
- 🔄 UI integration (mic button, meter, status)
- 🔄 Settings UI updates
- 🔄 Hindi/Hinglish evaluation
- 🔄 Integration tests
- 🔄 End-to-end testing

### Day 4 (2026-11-08)
- 🔄 Bug fixes
- 🔄 Performance tuning
- 🔄 Documentation
- 🔄 Phase 5 completion report

---

## KNOWN ISSUES & RISKS

### Issue #1: PyAudio Installation
**Impact:** Windows users may need MSVC Build Tools
**Status:** PyAudio already in requirements.txt
**Mitigation:** Provide binary wheels or installation guide

### Issue #2: Vosk Model Size
**Impact:** ~71 MB model adds to repo size
**Status:** Not in repo yet
**Mitigation:** 
- Option A: Include in repo (acceptable for desktop app)
- Option B: Download on first run (complicates setup)
- **Decision:** Include in repo for better UX

### Issue #3: Hindi Model Accuracy
**Impact:** Unknown performance on Hinglish code-mixing
**Status:** Needs evaluation
**Mitigation:** Test with Part 7's English model first, evaluate Hindi separately

### Issue #4: Wake Word Keyring
**Impact:** Porcupine key not stored
**Status:** Known bug (ROADMAP.md:59)
**Mitigation:** Fix in Day 2

---

## SUCCESS CRITERIA

Phase 5 is **COMPLETE** when:

1. ✅ Owner can record voice via microphone button
2. ✅ Vosk STT converts speech to text (English)
3. ✅ Privacy toggle works (local/cloud selection)
4. ✅ Barge-in detection implemented
5. ✅ Hindi/Hinglish evaluated and documented
6. ✅ Wake word keyring bug fixed
7. ✅ UI shows mic status and level
8. ✅ Emergency stop works
9. ✅ All tests passing (280 baseline + new voice tests)
10. ✅ Voice conversation works end-to-end:
    - User presses mic button
    - VERONIKA listens (visible indicator)
    - Vosk converts speech to text
    - AI processes request
    - VERONIKA speaks response
    - User can interrupt

---

## NEXT ACTIONS

**Immediate (Next 1 Hour):**
1. Copy Vosk model from Part 7
2. Add `vosk` to requirements.txt
3. Implement VoskSTT class
4. Test basic "hello world" recognition

**Today (Remaining):**
5. Integrate with speech_recognition.py
6. Add privacy toggle
7. Create basic UI integration
8. Write unit tests

**Tomorrow:**
9. Polish UI
10. Add barge-in
11. Fix wake word
12. Evaluate Hindi

---

**Phase 5 Lead:** Kiro AI Development Team  
**Last Updated:** 2026-11-05 07:14 UTC  
**Status:** Microphone pipeline complete ✅ | Vosk integration in progress 🔄
