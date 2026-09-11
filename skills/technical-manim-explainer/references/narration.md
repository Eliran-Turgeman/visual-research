# Narration: audition, reuse, recover

Load after the silent picture explains the mechanism. Provider choice is
explicit; a credential being present is not permission to synthesize speech.
See the [root render workflow](../../../README.md#render-a-managed-episode)
for draft and production commands.

## Before a full synthesis

1. Write short semantic blocks alongside the visual beats. Remove filler and
   prose already communicated by labels.
2. Keep a small glossary of display spelling, intended spoken form, and
   audition result. For example, decide whether `DDTree` is spoken "D D tree,"
   `KV` is "kay vee," and a symbol should be read by name or explained in
   words. These are candidates to audition, not guaranteed pronunciations.
3. With paid use authorized, synthesize and listen to a brief representative
   clip using the **same provider, model, voice, and delivery** as the final.
   Include names, acronyms, equations, and transitions likely to be difficult.
4. Correct the spoken script without falsifying the displayed terminology.
   Confirm provider/model support before using phonemes, SSML, style, or
   instruction controls; support in another endpoint does not imply support
   through this integration.
5. Freeze the chosen delivery, then synthesize the remaining blocks. Budget
   animation using actual tracker durations, not the silent word-count estimate.

OpenRouter's repository default voice is `microsoft/mai-voice-2` /
`en-US-Harper:MAI-Voice-2`, with speed `0.96`. This is a reproducible house
choice, not a measured claim that it is best for every audience. Keep speed
near its auditioned value and use supported style controls sparingly. Provider
availability and capabilities can change; record the configuration actually
used rather than silently substituting another voice.

## Provider controls

| Provider | Explicit selection and configuration |
|---|---|
| Silent | `MANIM_TTS_PROVIDER=none`; no service or credentials; approximate pacing |
| OpenRouter | `openrouter`, `OPENROUTER_API_KEY`; model/voice/speed controls below |
| gTTS | `gtts`; requires network access, no API key; useful for explicit speech drafts |
| OpenAI | `openai`, `OPENAI_API_KEY`; managed `OPENAI_TTS_MODEL` defaults to `tts-1-hd`, `OPENAI_TTS_VOICE` to `alloy`, `OPENAI_TTS_SPEED` to `1` |
| Azure | `azure`, `AZURE_SUBSCRIPTION_KEY`, `AZURE_SERVICE_REGION`; managed default voice `en-US-AriaNeural`, speed `1` |

Install the appropriate existing voiceover extra as documented in the
[README](../../../README.md#installation). Scenes use `manim-voiceover`; model
and voice support depends on the installed service and provider. In particular,
the upstream OpenAI API's newer instruction and voice capabilities do not
automatically become options in `OpenAIService`. Managed provider settings can
be supplied explicitly through `--model`, `--voice`, `--speed`, `--style`, and
`--style-degree` where supported; unsupported combinations fail rather than
being ignored. OpenAI transcription is disabled in the managed path, avoiding
an implicit Whisper download. This workflow requires no
unexplained dependency or product upgrade.

OpenRouter controls:

| Environment variable | Meaning |
|---|---|
| `OPENROUTER_TTS_MODEL` | Default `microsoft/mai-voice-2` |
| `OPENROUTER_TTS_VOICE` | Default `en-US-Harper:MAI-Voice-2` |
| `OPENROUTER_TTS_SPEED` | Default `0.96`; supported integration range `0.5`–`2.0` |
| `OPENROUTER_TTS_STYLE` | Optional Azure-provider style; use only if supported by the selected route |
| `OPENROUTER_TTS_STYLE_DEGREE` | Optional style strength; requires a style |
| `OPENROUTER_TTS_TIMEOUT` | Default `60` seconds; finite positive SDK network-operation/inactivity timeout |
| `OPENROUTER_TTS_MAX_RETRIES` | Default `2` retries after the initial attempt; nonnegative integer |

`OpenRouterSpeechService(request_timeout=..., max_retries=...)` overrides those
environment settings explicitly. `cache_lock_timeout=300` is a finite positive
constructor-only setting in seconds, not an environment variable or CLI flag.
The OpenAI-compatible SDK alone performs request retries; there is no outer
application retry loop. The timeout is **not a whole-render deadline**, and
timeouts/retries do not guarantee that the provider avoided duplicate execution
or charges. The integration requests MP3; it does not automatically switch
providers after failure. Timeout, retry, and lock settings do not alter speech
cache identity.

```powershell
$env:OPENROUTER_TTS_TIMEOUT = "60"
$env:OPENROUTER_TTS_MAX_RETRIES = "2"
```

Provider `speed` is distinct from inherited local `global_speed`
postprocessing. Changing `global_speed` from `1` still requires SoX; this
workflow does not install it or promise provider-side expressive controls.

Keep credentials in the process or configured credential store, never in scene
source, narration JSON, review evidence, screenshots, or manifests. Record only
an allowlist of non-secret settings.

## Cache reuse and recovery

Managed rendering separates a **persistent provider cache** from **run-specific
audio snapshots**. Cache-root precedence is:

1. `--cache-dir CACHE_ROOT` (`-CacheDir` in the DDTree convenience wrapper).
2. `MANIM_TTS_CACHE_ROOT`.
3. The repository/worktree's `media\voiceovers` directory.

The effective cache is always `CACHE_ROOT\PROVIDER`, for example
`media\voiceovers\openrouter`. It is independent of the run ID and output/media
directory. Providers do not share a metadata JSON file. Default roots are
worktree-local; supply the same explicit root to reuse valid speech across
worktrees.

```powershell
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer `
  --profile production --provider openrouter --cache-dir media\voiceovers `
  --output-dir media\runs --run-id minimal-cached-production-01
```

This example requires configured credentials and authorization for any missing
speech; a cache setting is not a promise that the run makes no paid requests.
Repeat with a fresh run ID and the same cache/configuration to reuse valid
unchanged clips. Preserve audio **and** its provider metadata; copying
filenames without the matching configuration
does not establish a valid cache hit. An unchanged text/configuration can be
reused; changing pronunciation, model, voice, speed, or style may require new
speech and a new timing review.

For scene implementations, `MANIM_TTS_CACHE_DIR` is the resolved provider cache
passed to speech services; `MANIM_VOICEOVER_DIR` is the unique run's `audio`
directory, **not** the reusable cache. `NarratedScene.add_sound` snapshots
consumed bytes by SHA-256 before Manim reads them. Later corruption or mutation
of the shared cache cannot alter those retained snapshots.

`manifest.cache` records provider/path. Optional
`timeline.blocks[].audio` and `manifest.artifacts.audio` are **lists** of
actual `{path, sha256}` references, not one path object or fabricated empty
measurements. References identify files inside the run's `audio` directory;
the renderer checks their location and hashes. Retain those snapshots with the
run even if the shared cache is subsequently repaired or removed. Managed
external-gTTS also uses the shared synthesis cache, but keeps its track manifest
and copied audio in the run and already embeds the speech in the video.

OpenRouter validates complete MP3 decoding, byte size, and SHA-256 fingerprints
before reuse. Valid unchanged assets cause no new provider request. Missing or
corrupt assets are regenerated; a completed deterministic orphan audio file can
repair an interrupted metadata publication without resynthesis. Audio and JSON
publication are individually atomic, **not** a single multi-file transaction.
Malformed cache JSON is quarantined as `cache.corrupt-<uuid>.json`, preserving
recoverable complete records; duplicate matching records are repaired without
discarding unrelated entries.

The persistent `.openrouter-cache.lock` serializes cooperating OpenRouter
writers. Do not delete the lock file to force progress while another process
may hold it. Other upstream speech services do not honor this lock; use
separate **worker cache roots** (`--cache-dir` or `MANIM_TTS_CACHE_ROOT`) for
concurrent legacy-provider work that does not cooperate with the lock.
Provider subdirectories isolate different providers, not concurrent writers
using the same legacy service. No new cache
management CLI is required: the normal service call validates/reuses/recovers
the assets. Missing credentials and provider/auth/quota/stream failures remain
visible rather than silently producing an accepted fallback.

For the full DDTree episode, follow its [narration instructions](../../../examples/ddtree_full/README.md#reproducible-speech-assets)
and distinguish standalone legacy assets from the managed provider cache.
Avoid regenerating all narration merely to repair one visual collision.

On failure:

1. Keep the valid cache and failed-run evidence; do not start by deleting the
   whole media directory.
2. Read the error and distinguish missing credentials, unsupported delivery,
   network/provider failure, cache contention, and corrupt audio.
3. Resolve the underlying cause; wait for an active cache writer rather than
   removing its lock. Regenerate only missing or invalid segments through the
   normal speech service after paid use is authorized.
4. Check recovered audio duration and pronunciation, rerender affected timing,
   and perform the complete audiovisual review on the resulting production
   artifact. An old review does not approve new audio or a new video hash.

Do not assume OpenRouter-specific cache/retry behavior applies to the other
`manim-voiceover` services. Local audio reuse is not an API prompt-cache discount
or a Batch API pricing claim.

## Disclosure and final listening

For OpenAI TTS, give end users a clear disclosure such as **"Narration uses an
AI-generated voice."** Include it in the delivered video's description or
another clearly visible accompanying notice. This is required by the
[OpenAI TTS guide](https://developers.openai.com/api/docs/guides/text-to-speech);
do not imply the voice is a human narrator. A similar disclosure is sensible
for other synthetic providers, subject to their own requirements.

Listen to the complete final artifact. Verify terms, natural pauses, volume,
cutoffs, drift, and that narration describes the currently visible state.
Audio-stream detection proves only that a stream exists, not that it is
intelligible, correctly pronounced, synchronized, or pedagogically useful.
