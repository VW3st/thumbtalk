"""Text clean-up and voice command tests (no microphone or model needed).  python -m pytest tests  or  python tests/test_text.py"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from thumbtalk import engine  # noqa: E402
from thumbtalk.config import S  # noqa: E402

S.update(cmd_send=True, cmd_newline=True, cmd_scratch=True)


def cmd(t):
    return engine.apply_commands(t)


def test_fillers():
    assert engine.fix("Um… come out wrong. uh... and so on, um, right") == "Come out wrong. And so on, right"


def test_send_it():
    assert cmd("Check the logs, send it.") == ("Check the logs.", {"send": True, "undo_last": False})
    assert cmd("Is it done? Send it")[0] == "Is it done?"
    assert cmd("Did you send it to him") == ("Did you send it to him", {"send": False, "undo_last": False})


def test_scratch_that():
    assert cmd("I want the blue one. Scratch that. I want the red one.")[0] == "I want the red one."
    assert cmd("First point. The blue one, scratch that, the red one.")[0] == "First point. The red one."
    t, a = cmd("Scratch that.")
    assert t == "" and a["undo_last"]
    t, a = cmd("Scratch that. Check the logs instead.")
    assert t == "Check the logs instead." and a["undo_last"]


def test_new_line():
    assert cmd("Hi Sam, new line. Thanks for the update.")[0] == "Hi Sam,\nThanks for the update."
    assert cmd("Point one. New paragraph. point two.")[0] == "Point one.\n\nPoint two."


def test_commands_can_be_switched_off():
    S.update(cmd_send=False, cmd_newline=False, cmd_scratch=False)
    try:
        assert cmd("Scratch that. New line. Send it.")[0] == "Scratch that. New line. Send it."
    finally:
        S.update(cmd_send=True, cmd_newline=True, cmd_scratch=True)



def test_stray_letters():
    t, _ = cmd("I don't really understand how this works. A new paragraph and let's see.")
    assert t == "I don't really understand how this works.\n\nAnd let's see.", repr(t)
    t, _ = cmd("Hi, how are you there, and a new line what can we do here?")
    assert t == "Hi, how are you there,\nWhat can we do here?", repr(t)
    t, _ = cmd("We'll go with plan A.")
    assert t == "We'll go with plan A.", repr(t)
    t, _ = cmd("It works. E")
    assert t == "It works.", repr(t)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
