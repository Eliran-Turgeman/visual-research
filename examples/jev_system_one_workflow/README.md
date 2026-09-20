# Jev: judgment inside software

This theory-first episode establishes the System One mental model before using
a support ticket:

1. generation versus evaluation;
2. Jev's focused, non-agent role;
3. the typed state/question/result contract;
4. atomic questions and Choice, Score, and Noul;
5. independent parallel evaluation over shared state;
6. probability, confidence, and aggregate calibration;
7. application-owned control flow and side effects;
8. one complete customer-support routing example.

All numerical distributions, confidence values, calibration bins, and policy
thresholds are illustrative. The episode makes no speed, cost, benchmark, or
production-accuracy claim.

## Silent managed draft

```powershell
.\scripts\render.ps1 examples\jev_system_one_workflow\scene.py `
  JevSystemOneWorkflow --profile draft --provider none `
  --output-dir media\runs --run-id jev-system-one-theory-draft-01
```

The managed run writes `manifest.json`, `timeline.json`, and `video.mp4` under
`media\runs\<run-id>\`. Extract review frames and contact sheets with:

```powershell
.\.venv\Scripts\python.exe scripts\extract_narration_frames.py `
  media\runs\<run-id>\video.mp4 media\runs\<run-id>\timeline.json `
  media\runs\<run-id>\review-frames
```

No paid narration provider is required. Direct Manim renders use
`media\review\jev_system_one_workflow\timeline.json`.

## Narrated production

```powershell
.\scripts\render.ps1 examples\jev_system_one_workflow\scene.py `
  JevSystemOneWorkflow --profile production --provider openrouter `
  --output-dir media\runs --run-id jev-system-one-theory-production-01
```

The production render uses OpenRouter `microsoft/mai-voice-2` with the Harper
voice. The reviewed artifact is:

`media\runs\jev-system-one-theory-production-01\video.mp4`
