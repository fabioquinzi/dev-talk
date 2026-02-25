"""Main menubar application.

Wires together audio capture, transcription, hotkeys, text injection,
and the recording overlay into a rumps-based macOS menubar app.
"""

from __future__ import annotations

import logging
import threading

import numpy as np
import rumps

from dev_talk import __version__
from dev_talk.audio import AudioManager
from dev_talk.config import Config
from dev_talk.engines.local_mlx import MLXWhisperEngine
from dev_talk.engines.remote_openai import OpenAIWhisperEngine
from dev_talk.hotkeys import HotkeyManager
from dev_talk.overlay import RecordingOverlay
from dev_talk.text_input import inject_text
from dev_talk.transcriber import Transcriber

logger = logging.getLogger(__name__)

# Menubar icons (using emoji as simple icons; can be replaced with actual icon files)
ICON_IDLE = "🎙️"
ICON_RECORDING = "🔴"


class DevTalkApp(rumps.App):
    """macOS menubar speech-to-text application."""

    def __init__(self) -> None:
        super().__init__(name="Dev Talk", title=ICON_IDLE, quit_button=None)

        self._config = Config.load()
        self._audio = AudioManager(device_id=self._config.mic_device_id)
        self._overlay = RecordingOverlay()
        self._hands_free_active = False
        self._recording_thread: threading.Thread | None = None

        # Set up transcription engine
        self._engine = self._create_engine()
        self._transcriber = Transcriber(engine=self._engine, language=self._config.language)

        # Set up hotkeys
        self._hotkeys = HotkeyManager(
            push_to_talk_key=self._config.push_to_talk_key,
            hands_free_keys=self._config.hands_free_keys,
            on_push_to_talk_start=self._on_ptt_start,
            on_push_to_talk_stop=self._on_ptt_stop,
            on_hands_free_toggle=self._on_hands_free_toggle,
        )

        # Build menu
        self._build_menu()

    def _build_menu(self) -> None:
        """Build the menubar dropdown menu."""
        self.menu.clear()

        # Status
        status = rumps.MenuItem(f"Dev Talk v{__version__}", callback=None)
        status.set_callback(None)
        self.menu.add(status)
        self.menu.add(rumps.separator)

        # Engine selection submenu
        engine_menu = rumps.MenuItem("Engine")
        local_prefix = "✓ " if self._config.engine == "local" else "  "
        engine_menu.add(rumps.MenuItem(
            f"{local_prefix}Local (MLX Whisper)",
            callback=lambda _: self._switch_engine("local"),
        ))
        openai_prefix = "✓ " if self._config.engine == "openai" else "  "
        engine_menu.add(rumps.MenuItem(
            f"{openai_prefix}OpenAI API",
            callback=lambda _: self._switch_engine("openai"),
        ))
        self.menu.add(engine_menu)

        # Streaming mode toggle
        mode_label = "Streaming" if self._config.streaming_mode else "Full Recording"
        mode_item = rumps.MenuItem(f"Mode: {mode_label}", callback=self._toggle_streaming_mode)
        self.menu.add(mode_item)

        self.menu.add(rumps.separator)

        # Microphone selection submenu
        mic_menu = rumps.MenuItem("Microphone")
        try:
            devices = AudioManager.list_devices()
            for dev in devices:
                prefix = "✓ " if dev.device_id == self._config.mic_device_id else "  "
                if dev.is_default and self._config.mic_device_id is None:
                    prefix = "✓ "
                item = rumps.MenuItem(
                    f"{prefix}{dev.name}",
                    callback=lambda sender, d=dev: self._select_mic(d.device_id, d.name),
                )
                mic_menu.add(item)
        except Exception as e:
            mic_menu.add(rumps.MenuItem(f"Error: {e}"))
        self.menu.add(mic_menu)

        self.menu.add(rumps.separator)

        # Hotkey info
        ptt_label = f"Push-to-talk: {self._config.push_to_talk_key}"
        self.menu.add(rumps.MenuItem(ptt_label, callback=None))
        hf_label = f"Hands-free: {'+'.join(self._config.hands_free_keys)}"
        self.menu.add(rumps.MenuItem(hf_label, callback=None))

        self.menu.add(rumps.separator)

        # Setup & Diagnostics submenu
        diag_menu = rumps.MenuItem("Setup & Diagnostics")
        diag_menu.add(rumps.MenuItem("Check Permissions", callback=self._check_permissions))
        diag_menu.add(rumps.MenuItem("Test Microphone", callback=self._test_microphone))
        diag_menu.add(rumps.MenuItem("Test Hotkey (fn)", callback=self._test_hotkey))
        diag_menu.add(rumps.separator)
        diag_menu.add(rumps.MenuItem("Permission Guide", callback=self._show_permission_guide))
        self.menu.add(diag_menu)

        self.menu.add(rumps.separator)

        # Quit
        self.menu.add(rumps.MenuItem("Quit Dev Talk", callback=self._quit))

    def _create_engine(self):
        """Create the appropriate STT engine based on config."""
        if self._config.engine == "openai" and self._config.openai_api_key:
            return OpenAIWhisperEngine(
                api_key=self._config.openai_api_key,
                model=self._config.openai_model,
            )
        return MLXWhisperEngine(model=self._config.model)

    def _switch_engine(self, engine_type: str) -> None:
        """Switch between local and OpenAI engines."""
        if engine_type == "openai" and not self._config.openai_api_key:
            rumps.notification(
                "Dev Talk",
                "API Key Required",
                "Set your OpenAI API key in ~/.config/dev-talk/config.json",
            )
            return

        self._config.update(engine=engine_type)
        self._engine = self._create_engine()
        self._transcriber.engine = self._engine
        self._build_menu()
        logger.info("Engine switched to: %s", self._transcriber.engine_name)

    def _select_mic(self, device_id: int, device_name: str) -> None:
        """Handle microphone selection."""
        self._config.update(mic_device_id=device_id, mic_device_name=device_name)
        self._audio.device_id = device_id
        self._build_menu()
        logger.info("Microphone changed to: %s (id=%d)", device_name, device_id)

    def _toggle_streaming_mode(self, sender: rumps.MenuItem) -> None:
        """Toggle between streaming and full-recording transcription."""
        self._config.update(streaming_mode=not self._config.streaming_mode)
        self._build_menu()
        mode = "streaming" if self._config.streaming_mode else "full recording"
        logger.info("Transcription mode changed to: %s", mode)

    def _on_ptt_start(self) -> None:
        """Push-to-talk key pressed — start recording."""
        if self._audio.is_recording:
            return
        self._start_recording()

    def _on_ptt_stop(self) -> None:
        """Push-to-talk key released — stop and transcribe."""
        if not self._audio.is_recording:
            return
        if self._config.streaming_mode:
            # Streaming mode: stop recording (stream_chunks generator will exit)
            self._stop_recording_and_transcribe()
        else:
            self._stop_recording_and_transcribe()

    def _on_hands_free_toggle(self) -> None:
        """Hands-free combo pressed — toggle recording."""
        if self._hands_free_active:
            self._hands_free_active = False
            self._stop_recording_and_transcribe()
        else:
            self._hands_free_active = True
            self._start_recording()

    def _start_recording(self) -> None:
        """Start audio capture and update UI."""
        self._audio.start_recording()
        self.title = ICON_RECORDING
        self._overlay.show_recording()
        logger.info("Recording started")

        if self._config.streaming_mode:
            self._recording_thread = threading.Thread(
                target=self._stream_transcribe, daemon=True
            )
            self._recording_thread.start()

    def _stop_recording_and_transcribe(self) -> None:
        """Stop recording and transcribe the audio."""
        if self._config.streaming_mode:
            # Just stop recording — the streaming thread will handle the rest
            audio = self._audio.stop_recording()
            self.title = ICON_IDLE
            self._overlay.hide()
            logger.info("Recording stopped (streaming mode)")
        else:
            audio = self._audio.stop_recording()
            self._overlay.show_transcribing()
            logger.info("Recording stopped, transcribing %d samples", audio.size)

            # Transcribe in background thread
            thread = threading.Thread(
                target=self._transcribe_full, args=(audio,), daemon=True
            )
            thread.start()

    def _transcribe_full(self, audio: np.ndarray) -> None:
        """Transcribe full audio buffer and inject text (runs in background thread)."""
        try:
            text = self._transcriber.transcribe_full(audio)
            if text:
                inject_text(text, method=self._config.injection_method)
                logger.info("Injected text: %s", text[:100])
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            rumps.notification("Dev Talk", "Transcription Error", str(e))
        finally:
            self.title = ICON_IDLE
            self._overlay.hide()

    def _stream_transcribe(self) -> None:
        """Transcribe audio chunks as they arrive (runs in background thread)."""
        try:
            chunks = self._audio.stream_chunks(
                chunk_duration_s=self._config.chunk_duration_s
            )
            for text in self._transcriber.transcribe_streaming(chunks):
                if text:
                    # Add space before each chunk to separate words
                    inject_text(text + " ", method=self._config.injection_method)
                    logger.debug("Streamed text: %s", text[:100])
        except Exception as e:
            logger.error("Streaming transcription failed: %s", e)
        finally:
            self.title = ICON_IDLE
            self._overlay.hide()

    def _check_permissions(self, sender: rumps.MenuItem) -> None:
        """Run all permission checks and show results."""
        from dev_talk.diagnostics import check_all_permissions, format_results, get_host_app

        host = get_host_app()
        results = check_all_permissions()
        message = format_results(results, host)
        rumps.alert(title="Permission Check", message=message)

    def _test_microphone(self, sender: rumps.MenuItem) -> None:
        """Test microphone recording."""
        from dev_talk.diagnostics import test_microphone_recording

        def _run():
            result = test_microphone_recording(device_id=self._config.mic_device_id)
            rumps.alert(title="Microphone Test", message=result.message)

        threading.Thread(target=_run, daemon=True).start()

    def _test_hotkey(self, sender: rumps.MenuItem) -> None:
        """Interactive fn key test."""
        from dev_talk.diagnostics import test_fn_key_detection

        # Pause main hotkeys during test to avoid side effects
        self._hotkeys.stop()

        event, handle = test_fn_key_detection()
        rumps.alert(
            title="Test Hotkey",
            message="Press and release the fn (globe) key, then click OK.",
        )
        handle.stop()

        if event.is_set():
            rumps.alert(title="Hotkey Test", message="fn key detected! Hotkeys are working.")
        else:
            rumps.alert(
                title="Hotkey Test",
                message=(
                    "fn key was NOT detected.\n\n"
                    "Possible causes:\n"
                    "- Accessibility permission not granted\n"
                    "- Permission granted to wrong app\n"
                    "- fn key behavior changed in System Settings > Keyboard"
                ),
            )

        # Resume main hotkeys
        self._hotkeys.start()

    def _show_permission_guide(self, sender: rumps.MenuItem) -> None:
        """Show permission setup guide."""
        from dev_talk.diagnostics import get_host_app

        host = get_host_app()
        rumps.alert(
            title="Permission Guide",
            message=(
                f"Dev Talk is running inside: {host}\n"
                f"Permissions must be granted to {host}.\n\n"
                "System Settings > Privacy & Security:\n\n"
                "1. Accessibility\n"
                f"   Add {host}\n"
                "   (Required for hotkeys + text injection)\n\n"
                "2. Microphone\n"
                f"   Add {host}\n"
                "   (Required for recording)\n\n"
                "After granting permissions, restart Dev Talk.\n\n"
                "Tip: Build as a .app (python setup.py py2app) to get\n"
                "Dev Talk as its own entry in the permission lists."
            ),
        )

    def _quit(self, sender: rumps.MenuItem) -> None:
        """Clean shutdown."""
        logger.info("Shutting down Dev Talk")
        self._hotkeys.stop()
        self._overlay.cleanup()
        if self._audio.is_recording:
            self._audio.stop_recording()
        rumps.quit_application()

    def run(self, **kwargs) -> None:
        """Start the app with hotkey listener."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
        logger.info("Starting Dev Talk v%s", __version__)
        self._hotkeys.start()
        super().run(**kwargs)
