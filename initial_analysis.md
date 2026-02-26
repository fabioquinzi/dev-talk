# Dev Talk - Initial Analysis

## Overview

Dev Talk is a macOS menubar application that replicates [Wispr Flow](https://wisprflow.ai/) functionality — voice-to-text that works in any text field, with push-to-talk and hands-free modes, a visual recording indicator, and microphone selection. Built for **English on Apple Silicon (M4)**.

---

## Speech-to-Text Engine Analysis

### Option A: MLX Whisper (LOCAL — SELECTED)

| Aspect | Details |
|---|---|
| **Model** | `whisper-large-v3-turbo` via `mlx-whisper` or `lightning-whisper-mlx` |
| **Parameters** | 809M |
| **Download size** | ~1.6 GB |
| **RAM usage** | ~2-4 GB (unified memory on Apple Silicon) |
| **Speed** | 10-27x real-time on M4 (10s audio in 0.37-1.2s) |
| **WER** | ~5-7% (English), comparable to cloud APIs |
| **Apple Silicon** | Native MLX framework — uses GPU/ANE natively, no CUDA needed |
| **Streaming** | Pseudo-streaming: process in 2-5s chunks as you speak |
| **Cost** | Free, forever |
| **Privacy** | 100% local, no data leaves your machine |

**Why this is the best local option:** MLX is Apple's own ML framework, purpose-built for Apple Silicon. `lightning-whisper-mlx` claims 10x faster than whisper.cpp and 4x faster than standard mlx-whisper. The `large-v3-turbo` model gives near-SOTA accuracy with only 809M params (vs 1.5B for full large-v3). On M4, this is extremely fast.

**Sources:**
- [lightning-whisper-mlx](https://github.com/mustafaaljadery/lightning-whisper-mlx)
- [mlx-whisper PyPI](https://pypi.org/project/mlx-whisper/)
- [Whisper large-v3-turbo - HuggingFace](https://huggingface.co/openai/whisper-large-v3-turbo)
- [Whisper M4 Benchmarks](https://dev.to/theinsyeds/whisper-speech-recognition-on-mac-m4-performance-analysis-and-benchmarks-2dlp)

### Option B: NVIDIA Canary-Qwen-2.5B (REJECTED)

| Aspect | Details |
|---|---|
| **Parameters** | 2.5B |
| **RAM usage** | ~8 GB VRAM (designed for NVIDIA GPUs) |
| **WER** | 5.63% (best on OpenASR leaderboard) |
| **Apple Silicon** | **Not natively supported** — requires NeMo toolkit + PyTorch. No MLX/CoreML port. |
| **Streaming** | Not designed for streaming; batch inference |

**Rejected because:** Best-in-class accuracy but requires NVIDIA GPU ecosystem. Would be slow and memory-hungry on Mac without native optimization.

**Sources:**
- [NVIDIA Canary-Qwen-2.5B - HuggingFace](https://huggingface.co/nvidia/canary-qwen-2.5b)
- [MarkTechPost Analysis](https://www.marktechpost.com/2025/07/17/nvidia-ai-releases-canary-qwen-2-5b-a-state-of-the-art-asr-llm-hybrid-model-with-sota-performance-on-openasr-leaderboard/)

### Option C: IBM Granite Speech 3.3 (REJECTED)

| Aspect | Details |
|---|---|
| **Variants** | 2B and 8B parameter versions |
| **RAM usage** | 2B: ~4-6 GB, 8B: ~16 GB |
| **Apple Silicon** | Could run via PyTorch MPS, but no MLX port. Not optimized. |

**Rejected because:** 8B is too heavy for a background utility; 2B has no Apple Silicon optimization. Multilingual focus is wasted since we only need English.

**Sources:**
- [IBM Granite Speech - HuggingFace](https://huggingface.co/ibm-granite/granite-speech-3.3-8b)
- [IBM Granite Docs](https://www.ibm.com/granite/docs/models/speech)

### Option D: OpenAI Whisper API (REMOTE — SELECTED as fallback)

| Aspect | Details |
|---|---|
| **Cost** | $0.006/min ($0.36/hr). GPT-4o-mini-transcribe: $0.003/min |
| **Quality** | Excellent, with diarization options |
| **Latency** | Network-dependent (~1-3s round-trip) |
| **Privacy** | Audio sent to OpenAI servers |
| **Streaming** | Supported via realtime API |

**Selected as configurable alternative** for users who prefer cloud accuracy or lower memory usage.

**Sources:**
- [OpenAI API Pricing](https://platform.openai.com/docs/pricing)
- [Whisper API Pricing Analysis](https://brasstranscripts.com/blog/openai-whisper-api-pricing-2025-self-hosted-vs-managed)

---

## Resource Requirements on M4 MacBook

| Resource | Impact |
|---|---|
| **Disk** | ~1.6 GB for model + ~100 MB for app |
| **RAM** | ~2-4 GB while running (from unified memory pool) |
| **CPU/GPU** | Brief spikes during transcription (~0.4-1.2s per chunk), idle otherwise |
| **Battery** | Minimal impact — only active during recording |
| **First launch** | ~2-5 min to download model (one-time) |

---

## Wispr Flow Feature Reference

Researched from [wisprflow.ai](https://wisprflow.ai/) and local app screenshots:

| Feature | Description | Dev Talk Scope |
|---|---|---|
| Push-to-talk | Hold key to record short speech | MVP |
| Hands-free mode | Toggle recording on/off | MVP |
| Microphone selection | Choose input device | MVP |
| Recording indicator | Visual feedback during recording | MVP |
| Text injection | Type into any focused field | MVP |
| Personal dictionary | Learn custom words | Future |
| Snippet library | Voice shortcuts for templates | Future |
| Tone adaptation | Context-aware formatting | Future |
| Multilingual | 100+ languages | Out of scope (English only) |
| AI auto-editing | Remove filler words, fix grammar | Future |

---

## Technology Decision Summary

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.12+ | Developer familiarity, ML ecosystem |
| macOS Integration | `rumps` + `PyObjC` | Menubar app, native APIs |
| STT (local) | `mlx-whisper` | Fastest on Apple Silicon |
| STT (remote) | OpenAI Whisper API | Reliable fallback |
| Audio | `sounddevice` | Mic selection, streaming |
| Hotkeys | `pynput` | Global keyboard shortcuts |
| Text injection | `PyObjC` (CGEvent) | Native keyboard simulation |
| Packaging | `py2app` | Standalone .app bundle |

---

## Comparison: Local vs API

| Factor | Local (MLX Whisper) | API (OpenAI) |
|---|---|---|
| **Cost** | Free | ~$6/1000 min |
| **Privacy** | Full | Audio sent to cloud |
| **Latency** | ~0.4-1.2s per chunk | ~1-3s per chunk |
| **Accuracy** | Excellent (5-7% WER) | Slightly better |
| **Memory** | 2-4 GB | ~200 MB |
| **Offline** | Yes | No |
| **Setup** | Auto model download (~1.6 GB) | Just API key |
