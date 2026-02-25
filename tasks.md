# Dev Talk - Task List

Track progress of each incremental task. Each task is a commit-worthy unit.

## Phase 1: Foundation

- [x] Task 1: Create initial_analysis.md, design.md, tasks.md
- [ ] Task 2: Project scaffold — pyproject.toml, .gitignore, folder structure, requirements
- [ ] Task 3: Config module — settings management with JSON persistence
- [ ] Task 4: Audio module — mic enumeration, recording, chunked capture

## Phase 2: Core STT

- [ ] Task 5: Transcriber abstraction — engine protocol, transcriber class
- [ ] Task 6: Local MLX Whisper engine — model download, transcription
- [ ] Task 7: Streaming transcription — chunked audio processing pipeline
- [ ] Task 8: Tests for audio, transcriber, and MLX engine

## Phase 3: macOS Integration

- [ ] Task 9: Text injection — CGEvent keyboard simulation + clipboard paste
- [ ] Task 10: Global hotkeys — push-to-talk and hands-free mode
- [ ] Task 11: Menubar app — rumps app with mic selection, settings menu
- [ ] Task 12: Recording overlay — floating indicator near dock
- [ ] Task 13: Tests for text injection, hotkeys, and app integration

## Phase 4: Remote Engine & Polish

- [ ] Task 14: OpenAI API engine — remote transcription with API key config
- [ ] Task 15: Engine switching — toggle between local and remote in settings
- [ ] Task 16: Tests for OpenAI engine and engine switching

## Phase 5: Packaging & Docs

- [ ] Task 17: py2app setup — standalone .app bundle build
- [ ] Task 18: README.md — installation, usage, screenshots, contributing
- [ ] Task 19: Final integration test and polish

---

## Progress Notes

_Updated as tasks are completed. Each task gets a commit on the `develop` branch._
