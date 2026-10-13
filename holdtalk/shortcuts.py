"""Start menu, desktop and start-with-Windows shortcuts, plus the app icon."""
import os, subprocess, sys

from .config import APP, DIR

_PROGRAMS = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
START_MENU = os.path.join(_PROGRAMS, APP + ".lnk")
STARTUP = os.path.join(_PROGRAMS, "Startup", APP + ".lnk")
ICON = os.path.join(DIR, "holdtalk.ico")


def desktop_path():
    try:   # handles a Desktop redirected to OneDrive
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                             capture_output=True, text=True, creationflags=0x08000000).stdout.strip()
        if out:
            return os.path.join(out, APP + ".lnk")
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop", APP + ".lnk")


def icon_image(state="idle"):
    from PIL import Image, ImageDraw
    c = {"idle": (96, 165, 250), "rec": (244, 114, 132), "paused": (140, 140, 150)}[state]
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((2, 2, 62, 62), fill=(32, 32, 36, 255))
    d.rounded_rectangle((24, 12, 40, 38), radius=8, fill=c)
    d.arc((17, 22, 47, 46), 0, 180, fill=c, width=4)
    d.line((32, 46, 32, 52), fill=c, width=4)
    d.line((24, 52, 40, 52), fill=c, width=4)
    return im


def _pythonw():
    d = os.path.dirname(sys.executable)
    p = os.path.join(d, "pythonw.exe")
    return p if os.path.exists(p) else sys.executable


def make(path):
    if not os.path.exists(ICON):
        icon_image().resize((256, 256)).save(ICON, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    q = lambda s: s.replace("'", "''")
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(path)}');"
          f"$s.TargetPath='{q(_pythonw())}';$s.Arguments='-m holdtalk';$s.WorkingDirectory='{q(DIR)}';"
          f"$s.IconLocation='{q(ICON)}';$s.Description='Hold a button, talk, let go';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000, check=False)


def startup_on():
    return os.path.exists(STARTUP)


def set_startup(on):
    if on and not startup_on():
        make(STARTUP)
    elif not on and startup_on():
        os.remove(STARTUP)


def setup():
    for p in (START_MENU, desktop_path(), STARTUP):
        make(p)


def remove_all():
    for p in (START_MENU, desktop_path(), STARTUP):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
