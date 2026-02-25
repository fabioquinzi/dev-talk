# Dev Talk - Task List

Track progress of each incremental task. Each task is a commit-worthy unit.

## Phase 1: Foundation

- [x] Task 1: Create initial_analysis.md, design.md, tasks.md
- [x] Task 2: Project scaffold — pyproject.toml, .gitignore, folder structure, requirements
- [x] Task 3: Config module — settings management with JSON persistence
- [x] Task 4: Audio module — mic enumeration, recording, chunked capture

## Phase 2: Core STT

- [x] Task 5: Transcriber abstraction — engine protocol, transcriber class
- [x] Task 6: Local MLX Whisper engine — model download, transcription
- [x] Task 7: Streaming transcription — integrated into audio + transcriber modules
- [x] Task 8: Tests for audio, transcriber, and MLX engine

## Phase 3: macOS Integration

- [x] Task 9: Text injection — CGEvent keyboard simulation + clipboard paste
- [x] Task 10: Global hotkeys — push-to-talk and hands-free mode
- [x] Task 11: Menubar app — rumps app with mic selection, settings menu
- [x] Task 12: Recording overlay — floating indicator near dock
- [x] Task 13: Tests for text injection, hotkeys, overlay, and app integration

## Phase 4: Remote Engine & Polish

- [x] Task 14: OpenAI API engine — remote transcription with API key config
- [x] Task 15: Engine switching — toggle between local and remote in settings
- [x] Task 16: Tests for OpenAI engine and engine switching

## Phase 5: Packaging & Docs

- [x] Task 17: py2app setup — standalone .app bundle build
- [x] Task 18: README.md — installation, usage, configuration, development guide
- [ ] Task 19: Final integration testing and user acceptance

---

## Progress Notes

All 18 tasks completed across 12 commits on the `develop` branch.
107 tests passing across 8 test files.

### Commits (develop branch)
1. Add project analysis, architecture design, and task tracking docs
2. Add project scaffold with pyproject.toml, package structure, and dev tooling
3. Add config module with JSON persistence and full test coverage
4. Add audio capture module with mic enumeration and chunked streaming
5. Add transcriber abstraction with engine protocol and streaming support
6. Add MLX Whisper local engine with lazy loading and Apple Silicon detection
7. Add text injection with clipboard paste and CGEvent keyboard simulation
8. Add global hotkey manager with push-to-talk and hands-free modes
9. Add floating recording overlay with pill UI near dock
10. Add menubar app wiring audio, transcriber, hotkeys, overlay, and text injection
11. Add OpenAI Whisper API engine with runtime engine switching
12. Add py2app packaging, comprehensive README, and final task updates
