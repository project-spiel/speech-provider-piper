# Piper Speech Provider for Spiel

A [Spiel](https://project-spiel.org/) speech provider that uses [Piper](https://github.com/rhasspy/piper) neural TTS models for high-quality, offline speech synthesis.

## Overview

This provider integrates Piper's neural text-to-speech engine with the Spiel speech framework for GNOME. It exposes Piper voices over D-Bus using the [Speech Provider](https://github.com/project-spiel/libspeechprovider) interface, making them available to any Spiel client (such as [Orca](https://gitlab.gnome.org/GNOME/orca) screen reader).

### Features

- High-quality neural TTS with Piper ONNX models
- Supports multiple languages and voices simultaneously
- Adjustable speech rate, pitch, and volume
- Runs entirely offline — no network connection required after setup
- Integrates with Flatpak for easy voice installation via [Spiel Installer](https://github.com/project-spiel/spiel-installer)

## Installation

### Via Flatpak (recommended)

Voices are distributed as Flatpak extensions. Use the [Spiel Installer](https://github.com/project-spiel/spiel-installer) app to browse and install voices, or install manually:

```sh
# Add the Spiel Flatpak repository (see https://project-spiel.org/install.html)
# Then install a voice, e.g.:
flatpak install ai.piper.Speech.Provider.Voice.en_US-lessac-medium
```

### Building from source

**Dependencies:**

- Rust toolchain (stable)
- Meson (≥ 0.58)
- ONNX Runtime

```sh
meson setup build
meson compile -C build
```

To run without installing:

```sh
meson devenv -C build
./src/speech-provider-piper
```

### Build options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `offline` | boolean | `false` | Build using vendored/offline cargo dependencies |
| `voices_dir` | string | *(auto)* | Custom path to voice model directory |

## Adding custom voices

Piper voices consist of an ONNX model file and a JSON configuration file. To add a custom voice:

1. **Obtain or train a voice model.** See the [Piper documentation](https://github.com/rhasspy/piper#training) for training instructions, or download pre-trained voices from [Hugging Face](https://huggingface.co/rhasspy/piper-voices).

2. **Place the files** in the voices directory:
   ```
   <voices_dir>/<voice_name>/
   ├── <voice_name>.onnx        # The ONNX model
   └── <voice_name>.onnx.json   # Model configuration (sample rate, phoneme map, etc.)
   ```

3. **Restart the provider** — it will auto-detect new voices on startup.

When running via Flatpak, custom voices should be placed as Flatpak extensions. See `build-aux/generate_voice_manifests.py` for how voice Flatpak manifests are structured.

## Architecture

```
┌─────────────────┐     D-Bus      ┌──────────────────────┐
│  Spiel Client   │ ◄────────────► │  speech-provider-    │
│  (Orca, etc.)   │                │  piper               │
└─────────────────┘                │                      │
                                   │  ┌────────────────┐  │
                                   │  │ sonata-piper   │  │
                                   │  │ (ONNX Runtime) │  │
                                   │  └────────────────┘  │
                                   └──────────────────────┘
```

The provider registers on the session D-Bus as `ai.piper.Speech.Provider` and implements the `org.freedesktop.Speech.Provider` interface. Voice models are loaded via [sonata-piper](https://crates.io/crates/sonata-piper) which uses ONNX Runtime for inference.

## D-Bus interface

The provider exposes:

- **`Synthesize(fd, utterance, voice_id, pitch, rate, is_ssml)`** — Synthesizes speech and writes PCM audio to the given file descriptor.
- **`VoicesChanged`** signal — Emitted when voices are added or removed.

## License

GPL-3.0-or-later
