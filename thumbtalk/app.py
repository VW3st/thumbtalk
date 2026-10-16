"""Entry point.  thumbtalk            run the app
                thumbtalk --setup    create Start menu, desktop and start-with-Windows shortcuts
                thumbtalk --remove   remove those shortcuts (before `uv tool uninstall thumbtalk`)"""
import ctypes, sys, threading

from .config import APP, LOG_F


def _msg(text, icon=0x40):
    ctypes.windll.user32.MessageBoxW(None, text, APP, icon)


def main():
    from . import shortcuts
    if "--setup" in sys.argv:
        shortcuts.setup()
        return
    if "--remove" in sys.argv:
        shortcuts.remove_all()
        return

    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\thumbtalk_single_instance")  # noqa: F841
    if ctypes.windll.kernel32.GetLastError() == 183:
        _msg(f"{APP} is already running. Look for the microphone icon next to the clock.")
        return
    if sys.stdout is None or "pythonw" in sys.executable.lower():   # no console: log to a file instead
        sys.stdout = sys.stderr = open(LOG_F, "a", encoding="utf-8", buffering=1)

    import faulthandler
    faulthandler.enable(sys.stderr)
    # Import every library here, on one thread, before any other thread starts. Importing native modules
    # (PyAV, CTranslate2, onnxruntime, Tk, pynput) from two threads at once crashes with an access violation.
    from . import engine  # sets up the CUDA DLL path first
    import ctranslate2, faster_whisper, faster_whisper.vad, huggingface_hub, onnxruntime  # noqa: F401,E401
    from huggingface_hub import snapshot_download  # noqa: F401  (lazy import inside the hub otherwise)
    import pyperclip, pystray, sounddevice, tkinter  # noqa: F401,E401
    from pynput import keyboard, mouse  # noqa: F401
    from PIL import ImageTk  # noqa: F401
    from . import gui, trigger
    try:
        engine.open_mic()
    except Exception as e:
        engine.log("microphone:", repr(e))
        _msg("No microphone could be opened.\n\nCheck one is plugged in, and that Windows Settings > Privacy & security > "
             "Microphone > \"Let desktop apps access your microphone\" is on.", 0x30)
        return
    threading.Thread(target=engine.worker, daemon=True).start()
    threading.Thread(target=engine.load_model, daemon=True).start()
    if engine.S["cleanup_model"] != "off":
        threading.Thread(target=engine.cleanup, args=("warm up the clean up model now please thank you",), daemon=True).start()
    trigger.start()
    gui.run()


if __name__ == "__main__":
    main()
