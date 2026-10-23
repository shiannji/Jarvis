"""The free voice: a sentence with no Fish audio is spoken by the page.

The upstream answer to "no audio for this sentence" was a `text` frame — shown,
not said, and counted as heard the instant it was sent. With a browser voice
behind it the sentence is now a `speak` frame that the page says aloud and
acks when it FINISHES, exactly like an audio chunk. Everything that hangs off
that ack — echo rejection, barge-in, a read-back's cancel window — has to
work the same in both voices, and that is what these check.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_speech import Harness

pytestmark = pytest.mark.asyncio


class NoAudio(Harness):
    """A Harness whose synthesizer never has audio — no Fish key."""

    async def synth(self, text):
        self.synth_calls.append(text)
        await asyncio.sleep(0.01)
        return None

    def speaks(self):
        return [(m["utt"], m["idx"], m["text"]) for m in self.msgs if m["type"] == "speak"]


async def _ack_speech(h, rounds=20):
    for _ in range(rounds):
        await asyncio.sleep(0.03)
        for m in list(h.msgs):
            if m["type"] == "speak" and not m.get("_acked"):
                m["_acked"] = True
                await h.sched.played(m["utt"], m["idx"])


async def test_no_audio_and_a_browser_voice_means_the_page_speaks_it():
    h = NoAudio(browser_voice=lambda: True)
    await h.sched.start()
    try:
        utt = await h.sched.say("Good evening, sir. All systems nominal.")
        await asyncio.sleep(0.15)
        assert [t for _, _, t in h.speaks()] == ["Good evening, sir.", "All systems nominal."][:len(h.speaks())]
        assert "text" not in h.types(), "spoken, not merely shown"
        assert not utt.done, "nothing is heard until the page says it has finished"
        await _ack_speech(h)
        assert await h.sched.wait_for(utt, timeout=2)
        assert [t for _, _, t in h.speaks()] == ["Good evening, sir.", "All systems nominal."]
    finally:
        await h.sched.stop()


async def test_without_a_browser_voice_it_is_text_as_before():
    """`JARVIS_TTS=fish`: Fish Audio or nothing, the original behaviour."""
    h = NoAudio()
    await h.sched.start()
    try:
        utt = await h.sched.say("Good evening, sir.")
        await asyncio.sleep(0.15)
        assert "speak" not in h.types()
        assert {"type": "text", "text": "Good evening, sir."} in h.msgs
        assert await h.sched.wait_for(utt, timeout=1)
    finally:
        await h.sched.stop()


async def test_the_page_is_handed_the_prepared_text():
    """It is read aloud, so it gets what TTS would have got: no markdown."""
    h = NoAudio(browser_voice=lambda: True,
                prepare=lambda s: s.replace("**", ""))
    await h.sched.start()
    try:
        await h.sched.say("It is **done**, sir.")
        await asyncio.sleep(0.15)
        assert [t for _, _, t in h.speaks()] == ["It is done, sir."]
    finally:
        await h.sched.stop()


async def test_a_sentence_fish_could_not_voice_falls_back_to_the_page():
    """`auto` with a key: one failed request does not mean silence."""
    h = Harness(browser_voice=lambda: True)
    h.fail_texts.add("Second one.")
    await h.sched.start()
    try:
        await h.sched.say("First one. Second one. Third one.")
        for _ in range(20):
            await asyncio.sleep(0.03)
            for m in list(h.msgs):
                if m["type"] in ("audio", "speak") and not m.get("_acked"):
                    m["_acked"] = True
                    await h.sched.played(m["utt"], m["idx"])
        frames = [(m["type"], m["text"]) for m in h.msgs if m["type"] in ("audio", "speak", "text")]
        assert frames == [("audio", "First one."), ("speak", "Second one."), ("audio", "Third one.")]
    finally:
        await h.sched.stop()


async def test_his_browser_voice_is_rejected_as_echo_while_it_plays():
    h = NoAudio(browser_voice=lambda: True)
    await h.sched.start()
    try:
        await h.sched.say("The work in chitauri is done, sir.")
        await asyncio.sleep(0.15)
        assert h.speaks()
        assert h.sched.classify("the work in chitauri is done") == "echo"
    finally:
        await h.sched.stop()


async def test_a_barge_in_stops_the_page_too():
    h = NoAudio(browser_voice=lambda: True)
    await h.sched.start()
    try:
        await h.sched.say("One sentence. Another sentence. And a third for luck.")
        await asyncio.sleep(0.15)
        await h.sched.user_final("actually wait a moment")
        assert "stop" in h.types()
    finally:
        await h.sched.stop()


async def test_the_page_speaking_is_not_a_voice_failure():
    """Three sentences with no Fish audio used to warn 'my voice is failing'.
    With the page speaking them, nothing is failing."""
    h = NoAudio(browser_voice=lambda: True)
    await h.sched.start()
    try:
        await h.sched.say("One. Two. Three. Four.")
        await _ack_speech(h, rounds=30)
        assert not any(m["type"] == "text" for m in h.msgs), h.msgs
    finally:
        await h.sched.stop()


async def test_say_that_again_speaks_the_same_words_again():
    h = NoAudio(browser_voice=lambda: True)
    await h.sched.start()
    try:
        utt = await h.sched.say("Good evening, sir.")
        await _ack_speech(h)
        assert await h.sched.wait_for(utt, timeout=2)
        assert await h.sched.replay_last()
        await _ack_speech(h)
        assert [t for _, _, t in h.speaks()] == ["Good evening, sir.", "Good evening, sir."]
    finally:
        await h.sched.stop()
