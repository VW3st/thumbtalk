"""End-to-end check with a synthetic recording: Windows text-to-speech -> engine -> what would be typed.
python tests/pipeline_check.py   (loads the real speech model; no microphone or typing happens)"""
import os, subprocess, sys, tempfile, threading, time, wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np  # noqa: E402
from thumbtalk import engine  # noqa: E402
from thumbtalk.config import S  # noqa: E402

SAY = ("Please check the Supabase table. Scratch that. Check the GitHub logs instead. New line. "
       "And make sure the MCP server is connected to Claude Code. Send it.")
wav = os.path.join(tempfile.gettempdir(), "thumbtalk_check.wav")
ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
      "$f=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono);"
      f"$s.SetOutputToWaveFile('{wav}',$f); $s.Speak('{SAY}'); $s.Dispose()")
subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)

typed = []
engine.paste = lambda t: typed.append(("paste", t))
engine.press = lambda k, n=1: typed.append(("key", k, n))
S.update(cleanup_model="off", cmd_send=True, cmd_newline=True, cmd_scratch=True, paused=False)

engine.load_model()
threading.Thread(target=engine.worker, daemon=True).start()
w = wave.open(wav)
a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
a = np.concatenate([a, np.zeros(16000, np.float32)])   # a second of silence: must not become "Thank you."
t0 = time.time()
engine.start()
for i in range(0, len(a) - engine.BLOCK, engine.BLOCK):   # feed in real time like a microphone
    engine.audio_cb(a[i:i + engine.BLOCK].reshape(-1, 1), engine.BLOCK, None, None)
    time.sleep(0.03)
t1 = time.time()
engine.stop()
while engine.st["busy"] > 0:
    time.sleep(0.05)
print(f"device {engine.device} | audio {len(a) / 16000:.1f}s | text ready {time.time() - t1:.2f}s after release")
for x in typed:
    print(repr(x))
expected = "Check the GitHub logs instead.\nAnd make sure the MCP server is connected to Claude Code."
ok = typed and typed[0][0] == "paste" and typed[0][1] == expected and typed[-1] == ("key", "enter", 1)
print("PASS" if ok else f"CHECK MANUALLY (expected {expected!r})")
