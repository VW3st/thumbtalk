"""On-screen panel, tray icon and settings window. All Tk work happens on the main thread (tick)."""
import ctypes, os, queue, subprocess, threading, time, webbrowser
import tkinter as tk
from tkinter import ttk

import numpy as np

from . import engine, shortcuts, trigger
from .config import APP, HOME_URL, VERSION, S, W, WORDS_F, save_settings, save_words
from .engine import st, ui, levels

BG, KEY, BORDER = "#1f1f23", "#010203", "#34343c"
TXT, DIM = "#ececf1", "#8b8b96"
COL = {"move": "#60a5fa", "saved": "#6ee7a8", "loading": "#f5c86b", "listening": "#f47284", "cleaning": "#f5c86b",
       "done": "#6ee7a8", "sent": "#6ee7a8", "undone": "#6ee7a8", "ready": "#60a5fa"}
WIDTH = 700
POSITIONS = {"top-left": "Top left", "top-center": "Top centre", "top-right": "Top right",
             "middle-left": "Left side", "middle-right": "Right side",
             "bottom-left": "Bottom left", "bottom-center": "Bottom centre", "bottom-right": "Bottom right"}
FONT, FONT_B, FONT_S = ("Segoe UI Variable Text", 12), ("Segoe UI Variable Display Semib", 11), ("Segoe UI Variable Text", 12, "italic")


def label(state):
    return {"move": "Drag me anywhere, let go to save", "saved": "Position saved",
            "loading": "Loading speech model… (the first start downloads it once)",
            "listening": "Listening", "cleaning": "Writing it up", "done": "Pasted", "sent": "Sent",
            "undone": "Removed the last dictation",
            "ready": f"Ready · hold the {trigger.SHORT[S['trigger']]} to talk"}.get(state, "")


root = cv = tray = None
view = {"state": "ready", "commit": "", "partial": "", "shown": False, "alpha": 0.0, "hide_at": 0.0, "t": 0.0,
        "moving": False, "drag": None, "xy": None}


# ---------------- panel ----------------
def no_activate(click_through=True):   # never steal focus; click-through unless being dragged
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20) | 0x08000000 | 0x80 | 0x80000
    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x20 if click_through else ex & ~0x20)


def work_area():   # screen minus the taskbar
    r = (ctypes.c_long * 4)()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, r, 0)
    return r[0], r[1], r[2], r[3]


def place(h):
    L, T, R, B = work_area()
    m, H = 24, h + 4
    if view["moving"] and view["xy"]:
        x, y = view["xy"]
    elif isinstance(S["pos"], list):
        x, y = S["pos"]
    else:
        v, hz = (S["pos"] if S["pos"] in POSITIONS else "bottom-center").split("-")
        x = {"left": L + m, "center": (L + R - WIDTH) // 2, "right": R - WIDTH - m}[hz]
        y = {"top": T + m, "middle": (T + B - H) // 2, "bottom": B - H - m}[v]
    x = max(L, min(int(x), R - WIDTH))
    y = max(T, min(int(y), B - H))
    root.geometry(f"{WIDTH}x{H}+{x}+{y}")


def drag_start(e):
    view["drag"] = (e.x_root - root.winfo_x(), e.y_root - root.winfo_y())


def drag_move(e):
    if view["drag"]:
        view["xy"] = (e.x_root - view["drag"][0], e.y_root - view["drag"][1])


def drag_end(e):
    if not view["moving"]:
        return
    S["pos"] = [root.winfo_x(), root.winfo_y()]
    save_settings()
    view.update(moving=False, drag=None, xy=None, state="saved", hide_at=time.time() + 1.5)
    no_activate(True)


def rrect(x1, y1, x2, y2, r, **kw):
    p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(p, smooth=True, **kw)


def draw():
    cv.delete("all")
    pad, col = 20, COL.get(view["state"], TXT)
    rec = view["state"] == "listening"
    body = view["commit"][-320:]
    tmp = [cv.create_text(pad, 0, text=body, font=FONT, width=WIDTH - 2 * pad, anchor="nw")] if body else []
    tmp += [cv.create_text(pad, 0, text=view["partial"][-220:], font=FONT_S, width=WIDTH - 2 * pad, anchor="nw")] if view["partial"] else []
    hs = [cv.bbox(t)[3] - cv.bbox(t)[1] for t in tmp]
    cv.delete("all")
    h = 58 + (sum(hs) + 6 * max(0, len(hs) - 1) + 14 if hs else 0)
    cv.config(height=h + 4)
    rrect(2, 2, WIDTH - 2, h, 16, fill=BG, outline=BORDER, width=1)
    cx, cy = pad + 14, 30
    lv = st["level"] if rec else 0
    if rec:
        cv.create_oval(cx - 14 - lv * 9, cy - 14 - lv * 9, cx + 14 + lv * 9, cy + 14 + lv * 9, outline=col, width=2)
    cv.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, fill=col, outline="")
    cv.create_rectangle(cx - 3, cy - 8, cx + 3, cy + 3, fill=BG, outline="")
    cv.create_arc(cx - 7, cy - 6, cx + 7, cy + 7, start=180, extent=180, style="arc", outline=BG, width=2)
    cv.create_line(cx, cy + 7, cx, cy + 10, fill=BG, width=2)
    cv.create_text(cx + 26, cy, text=label(view["state"]), font=FONT_B, fill=TXT, anchor="w")
    if rec:
        levels.append(st["level"])
        bx = WIDTH - pad - 32 * 6
        for i, l in enumerate(levels):
            bh = 2 + l * 22
            x = bx + i * 6
            cv.create_line(x, cy - bh / 2, x, cy + bh / 2, fill=col, width=3, capstyle="round")
    elif view["state"] in ("cleaning", "loading"):
        for i in range(3):
            a = (np.sin(view["t"] * 6 - i * 0.8) + 1) / 2
            x, r = WIDTH - pad - 40 + i * 16, 3 + a * 2
            cv.create_oval(x - r, cy - r, x + r, cy + r, fill=col, outline="")
    y = 58
    if body:
        t = cv.create_text(pad, y, text=body, font=FONT, fill=TXT, width=WIDTH - 2 * pad, anchor="nw")
        y = cv.bbox(t)[3] + 6
    if view["partial"]:
        cv.create_text(pad, y, text=view["partial"][-220:], font=FONT_S, fill=DIM, width=WIDTH - 2 * pad, anchor="nw")
    place(h)


def tick():
    view["t"] += 0.033
    try:
        while True:
            k, v = ui.get_nowait()
            if k == "begin":
                if view["moving"]:
                    view.update(moving=False, drag=None, xy=None)
                    no_activate(True)
                view.update(state="listening", commit="", partial="", hide_at=1e18, shown=True)
            elif k == "state":
                view["state"] = v
                view["hide_at"] = time.time() + (1.8 if v in ("done", "sent", "undone", "ready") else 1e9)
                view["shown"] = view["shown"] or v in ("ready", "loading")
            elif k == "partial":
                view["partial"] = v
            elif k == "commit":
                view["commit"] = (view["commit"] + " " + v).strip()
            elif k == "final":
                view.update(commit=v, partial="")
            elif k == "hide":
                view["hide_at"] = 0
            elif k == "preview" and not st["on"]:
                view.update(state="saved", shown=True, hide_at=time.time() + 2.0)
            elif k == "move" and not st["on"]:
                view.update(state="move", shown=True, moving=True, hide_at=1e18, commit="", partial="")
                if root.state() != "withdrawn":
                    no_activate(False)
            elif k == "settings":
                open_settings()
            elif k == "quit":
                root.destroy()
                return
    except queue.Empty:
        pass
    if time.time() > view["hide_at"] and not st["on"] and st["busy"] <= 0:
        view["shown"] = False
    view["alpha"] += ((0.97 if view["shown"] else 0.0) - view["alpha"]) * 0.35
    if view["alpha"] > 0.02:
        if root.state() == "withdrawn":
            root.deiconify()
            no_activate(not view["moving"])
        root.attributes("-alpha", view["alpha"])
        draw()
    elif root.state() != "withdrawn":
        root.withdraw()
    root.after(33, tick)


# ---------------- tray ----------------
def set_tray(state):
    try:
        tray.icon = shortcuts.icon_image("paused" if S["paused"] else state)
    except Exception:
        pass


def make_tray():
    import pystray

    def toggle_pause(icon, item):
        S["paused"] = not S["paused"]
        save_settings()
        set_tray("idle")

    return pystray.Icon(APP, shortcuts.icon_image(), f"{APP}: hold the {trigger.SHORT[S['trigger']]} to talk", menu=pystray.Menu(
        pystray.MenuItem(f"{APP} {VERSION}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings…", lambda i, it: ui.put(("settings", None)), default=True),
        pystray.MenuItem("Paused", toggle_pause, checked=lambda i: S["paused"]),
        pystray.MenuItem("Move the panel…", lambda i, it: ui.put(("move", None))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda i, it: (tray.stop(), ui.put(("quit", None))))))


# ---------------- settings window ----------------
_win = None


def open_settings():
    global _win
    if _win is not None and _win.winfo_exists():
        _win.deiconify()
        _win.lift()
        _win.focus_force()
        return
    from PIL import ImageTk
    w = _win = tk.Toplevel(root)
    w.title(f"{APP} settings")
    w.resizable(False, False)
    w._icon = ImageTk.PhotoImage(shortcuts.icon_image())
    w.iconphoto(False, w._icon)
    style = ttk.Style(w)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    f = ttk.Frame(w, padding=18)
    f.grid(sticky="nsew")
    f.columnconfigure(1, weight=1)
    row = [0]

    def add(text, widget, hint=None):
        ttk.Label(f, text=text).grid(row=row[0], column=0, sticky="nw", padx=(0, 14), pady=5)
        widget.grid(row=row[0], column=1, sticky="ew", pady=5)
        row[0] += 1
        if hint:
            ttk.Label(f, text=hint, foreground="#666").grid(row=row[0], column=1, sticky="w", pady=(0, 4))
            row[0] += 1

    def combo(options, current):
        keys, labels = list(options), list(options.values())
        v = tk.StringVar(value=options.get(current, labels[0]))
        cb = ttk.Combobox(f, textvariable=v, values=labels, state="readonly", width=52)
        return cb, lambda: keys[labels.index(v.get())]

    trig_cb, trig_get = combo(trigger.TRIGGERS, S["trigger"])
    add("Hold to talk", trig_cb, "A quick click still does the button's normal job.")
    hold = tk.DoubleVar(value=S["hold_secs"])
    hold_lbl = ttk.Label(f, text="")
    sc = ttk.Scale(f, from_=0.15, to=0.6, variable=hold,
                   command=lambda _=None: hold_lbl.config(text=f"{hold.get():.2f} s before it starts listening"))
    add("Hold time", sc)
    hold_lbl.grid(row=row[0], column=1, sticky="w")
    row[0] += 1
    hold_lbl.config(text=f"{hold.get():.2f} s before it starts listening")

    model_cb, model_get = combo(engine.MODELS, S["model"])
    add("Speech model", model_cb, f"Running on: {engine.device or 'loading…'}")
    lang_cb, lang_get = combo({"en": "English", "auto": "Detect automatically"}, S["language"])
    add("Language", lang_cb)
    om = engine.ollama_models()
    opts = {"off": "Off"} | {m: m for m in om}
    if S["cleanup_model"] not in opts:
        opts[S["cleanup_model"]] = S["cleanup_model"]
    ai_cb, ai_get = combo(opts, S["cleanup_model"])
    add("AI clean-up", ai_cb, "Local Ollama model that tidies grammar." if om else "Install Ollama to enable this (optional).")

    cmds = ttk.Frame(f)
    cv_send, cv_nl, cv_scr = (tk.BooleanVar(value=S[k]) for k in ("cmd_send", "cmd_newline", "cmd_scratch"))
    ttk.Checkbutton(cmds, text='"send it" at the end presses Enter', variable=cv_send).pack(anchor="w")
    ttk.Checkbutton(cmds, text='"new line" and "new paragraph"', variable=cv_nl).pack(anchor="w")
    ttk.Checkbutton(cmds, text='"scratch that" removes what you just said', variable=cv_scr).pack(anchor="w")
    add("Voice commands", cmds)

    pos_opts = dict(POSITIONS)
    if isinstance(S["pos"], list):
        pos_opts["custom"] = "Where I dragged it"
    pos_cb, pos_get = combo(pos_opts, "custom" if isinstance(S["pos"], list) else S["pos"])
    add("Panel position", pos_cb)
    ttk.Button(f, text="Drag it somewhere else…", command=lambda: (ui.put(("move", None)), w.destroy())).grid(
        row=row[0], column=1, sticky="w", pady=(0, 6))
    row[0] += 1

    start_v = tk.BooleanVar(value=shortcuts.startup_on())
    add("", ttk.Checkbutton(f, text="Start with Windows", variable=start_v))

    words = tk.Text(f, height=8, width=52, font=("Segoe UI", 10), wrap="word")
    words.insert("1.0", "\n".join(W.get("vocab", [])))
    add("My words", words, "One per line. Names, products and jargon it should spell exactly.")
    ttk.Button(f, text="Open the full word file (advanced fixes)…",
               command=lambda: subprocess.Popen(["notepad.exe", WORDS_F])).grid(row=row[0], column=1, sticky="w")
    row[0] += 1

    def save():
        reload = model_get() != S["model"] or lang_get() != S["language"]
        S.update(trigger=trig_get(), hold_secs=round(hold.get(), 2), model=model_get(), language=lang_get(),
                 cleanup_model=ai_get(), cmd_send=cv_send.get(), cmd_newline=cv_nl.get(), cmd_scratch=cv_scr.get())
        p = pos_get()
        if p != "custom":
            S["pos"] = p
        save_settings()
        W["vocab"] = [x.strip() for x in words.get("1.0", "end").splitlines() if x.strip()]
        save_words()
        shortcuts.set_startup(start_v.get())
        try:
            tray.title = f"{APP}: hold the {trigger.SHORT[S['trigger']]} to talk"
        except Exception:
            pass
        if reload:
            threading.Thread(target=engine.load_model, daemon=True).start()
        else:
            ui.put(("preview", None))
        w.destroy()

    btns = ttk.Frame(f)
    btns.grid(row=row[0], column=0, columnspan=2, sticky="ew", pady=(14, 0))
    credit = ttk.Label(btns, text=f"{APP} {VERSION}  ·  by AI Playgrounds", foreground="#888", cursor="hand2")
    credit.pack(side="left")
    credit.bind("<Button-1>", lambda e: webbrowser.open(HOME_URL))
    ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="right")
    ttk.Button(btns, text="Save", command=save).pack(side="right", padx=8)
    w.bind("<Escape>", lambda e: w.destroy())
    w.update_idletasks()
    w.geometry(f"+{(w.winfo_screenwidth() - w.winfo_width()) // 2}+{(w.winfo_screenheight() - w.winfo_height()) // 3}")
    w.lift()
    w.focus_force()


# ---------------- run ----------------
def run():
    global root, cv, tray
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", KEY)
    root.attributes("-alpha", 0.0)
    cv = tk.Canvas(root, width=WIDTH, height=120, bg=KEY, highlightthickness=0)
    cv.pack()
    cv.bind("<ButtonPress-1>", drag_start)
    cv.bind("<B1-Motion>", drag_move)
    cv.bind("<ButtonRelease-1>", drag_end)
    tray = make_tray()
    engine.hooks["tray"] = set_tray
    tray.run_detached()
    if S.get("first_run"):
        S["first_run"] = False
        save_settings()

        def hello():
            time.sleep(2)
            try:
                tray.notify(f"Hold your {trigger.SHORT[S['trigger']]}, talk, then let go. "
                            "Click the tray icon for settings.", f"{APP} is running")
            except Exception:
                pass
        threading.Thread(target=hello, daemon=True).start()
    view["shown"] = True
    tick()
    root.mainloop()
