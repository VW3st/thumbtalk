"""Hold-to-talk trigger. A quick press keeps the button's normal job (e.g. Back); holding it dictates.

Mouse buttons are caught with a low-level hook. The hook only queues the event and returns at once:
if a hook is slow, Windows lets the click through and may drop the hook. A quick click is then replayed
with SendInput, tagged so the hook lets our own replay pass.
"""
import ctypes, queue, threading, time

from .config import S
from . import engine

TRIGGERS = {
    "mouse_back": "Mouse Back button (side button)",
    "mouse_forward": "Mouse Forward button (side button)",
    "mouse_middle": "Middle mouse button (wheel click)",
    "right_ctrl": "Right Ctrl key",
}
SHORT = {"mouse_back": "mouse Back button", "mouse_forward": "mouse Forward button",
         "mouse_middle": "middle mouse button", "right_ctrl": "Right Ctrl key"}

WM_MDOWN, WM_MUP, WM_XDOWN, WM_XUP = 0x0207, 0x0208, 0x020B, 0x020C
XBUTTON = {"mouse_back": 1, "mouse_forward": 2}
MAGIC = 0x484F4C44  # tags clicks we replay ourselves
events = queue.Queue()
_mouse = None


def _mouse_filter(msg, data):
    trig = S["trigger"]
    if S["paused"] or data.dwExtraInfo == MAGIC:
        return True
    if trig in XBUTTON and msg in (WM_XDOWN, WM_XUP) and (data.mouseData >> 16) == XBUTTON[trig]:
        events.put((msg == WM_XDOWN, time.time()))
        _mouse.suppress_event()
    elif trig == "mouse_middle" and msg in (WM_MDOWN, WM_MUP):
        events.put((msg == WM_MDOWN, time.time()))
        _mouse.suppress_event()
    return True


class _MI(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class _IN(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MI), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def replay_click():
    trig = S["trigger"]
    if trig in XBUTTON:
        flags, data = (0x0080, 0x0100), XBUTTON[trig]
    elif trig == "mouse_middle":
        flags, data = (0x0020, 0x0040), 0
    else:
        return   # keyboard triggers are never blocked, so there is nothing to replay
    ev = (_IN * 2)()
    for i, fl in enumerate(flags):
        ev[i].type = 0
        ev[i].mi = _MI(0, 0, data, fl, 0, MAGIC)
    ctypes.windll.user32.SendInput(2, ev, ctypes.sizeof(_IN))


_key_down = False


def _on_key(down):
    def f(key):
        global _key_down
        from pynput.keyboard import Key
        if S["trigger"] != "right_ctrl" or S["paused"] or key != Key.ctrl_r:
            return
        if down and _key_down:
            return   # key auto-repeat
        _key_down = down
        events.put((down, time.time()))
    return f


def _loop():
    while True:
        down, t = events.get()
        if not down:
            continue
        try:
            down2, _ = events.get(timeout=S["hold_secs"])
            if not down2:
                replay_click()   # quick click: behave like a normal button
                continue
        except queue.Empty:
            pass
        engine.start(t)          # held: dictate until released
        while True:
            d, _ = events.get()
            if not d:
                engine.stop()
                break


def start():
    global _mouse
    from pynput import mouse, keyboard
    _mouse = mouse.Listener(win32_event_filter=_mouse_filter)
    _mouse.start()
    keyboard.Listener(on_press=_on_key(True), on_release=_on_key(False)).start()
    threading.Thread(target=_loop, daemon=True).start()
