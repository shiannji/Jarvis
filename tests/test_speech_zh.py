"""The mouth and the ear, in Mandarin.

The scheduler was written for English, and one line of it would have made
Mandarin unusable outright: `_tokens` kept only `[a-z0-9']`, so every Chinese
transcript tokenized to nothing — and `classify` calls a transcript with no
tokens an echo. Every word the user said would have been dropped as JARVIS
hearing himself. These pin the Mandarin behaviour against the real scheduler.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_speech import Harness, _split_all


# --- splitting --------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("好的，先生。我已經打開瀏覽器了！接下來要做什麼？",
     ["好的，先生。", "我已經打開瀏覽器了！", "接下來要做什麼？"]),
    ("「完成了。」他說。", ["「完成了。」", "他說。"]),
    ("真的嗎？！是的。", ["真的嗎？！", "是的。"]),
    ("好的!我來處理.接著呢", ["好的!", "我來處理.", "接著呢"]),     # ASCII marks, no spaces
    ("版本 3.5 已經上線。", ["版本 3.5 已經上線。"]),
    ("hammer 和 chitauri 都完成了。Good.", ["hammer 和 chitauri 都完成了。", "Good."]),
])
def test_mandarin_sentences_split_where_they_end(text, expected):
    assert _split_all(text) == expected


def test_the_first_chunk_goes_out_early_in_mandarin_too():
    """Forty Latin letters is two or three seconds of speech; forty Han
    characters is nine. The early cut is weighted so it means the same thing
    in both: here it lands on the semicolon, a pause a listener expects."""
    from speech import SentenceSplitter
    s = SentenceSplitter()
    out = s.feed("先生，三個專案目前都在進行中；hammer 正在等你確認權限，其餘兩個還在跑")
    assert out == ["先生，三個專案目前都在進行中；"]


def test_english_splits_exactly_as_it_did():
    assert _split_all("Good evening, sir. All systems nominal.") == \
        ["Good evening, sir.", "All systems nominal."]


# --- tokens -------------------------------------------------------------------

def test_a_han_character_is_a_token():
    from speech import _tokens
    assert _tokens("先生，hammer 在等您。") == ["先", "生", "hammer", "在", "等", "您"]
    assert _tokens("I'm fine, sir.") == ["i'm", "fine", "sir"]


# --- the ear ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_mandarin_sentence_is_speech_not_echo():
    """The regression this file exists for."""
    h = Harness()
    assert h.sched.classify("幫我看一下哪些對話在等我") == "speech"


@pytest.mark.asyncio
async def test_his_own_mandarin_coming_back_is_echo():
    h = Harness()
    await h.sched.start()
    try:
        await h.sched.say("先生，有兩個對話在等您。")
        await asyncio.sleep(0.15)
        assert h.audio(), h.msgs
        # The recogniser hears him through the speaker, punctuation gone and
        # one homophone slipped (您 -> 你).
        assert h.sched.classify("先生有兩個對話在等你") == "echo"
        # ...while something new from the user is still heard.
        assert h.sched.classify("幫我打開 hammer 的終端機") == "speech"
    finally:
        await h.sched.stop()


@pytest.mark.parametrize("heard", [
    "再說一次", "請再說一次", "可以再說一次嗎", "你剛剛說什麼", "蛤", "什麼",
    "賈維斯再講一遍", "重複一次吧",
])
def test_say_that_again_in_mandarin(heard):
    h = Harness()
    assert h.sched.classify(heard) == "replay"


@pytest.mark.parametrize("heard", [
    "你說什麼意思", "再說一次那個指令的名字", "什麼時候會好", "重複執行那個 run",
])
def test_a_real_question_is_not_a_replay(heard):
    h = Harness()
    assert h.sched.classify(heard) == "speech"


@pytest.mark.parametrize("word", ["等一下", "等等", "取消", "不要", "算了", "停"])
@pytest.mark.asyncio
async def test_a_mandarin_cancel_word_cancels_in_the_window(word):
    h = Harness()
    h.sched._cancel_window_open = True
    assert h.sched.classify(word) == "cancel"


def test_english_cancel_words_still_work():
    h = Harness()
    h.sched._cancel_window_open = True
    assert h.sched.classify("hold on") == "cancel"
    assert h.sched.classify("stop") == "cancel"


@pytest.mark.asyncio
async def test_a_mandarin_interruption_cuts_him_off():
    h = Harness()
    await h.sched.start()
    try:
        await h.sched.say("先生，三個專案都在跑，hammer 正在建置，其餘的還在測試。")
        await asyncio.sleep(0.15)
        assert h.audio()
        await h.sched.user_interim("等一下")
        assert "stop" in h.types(), h.types()
    finally:
        await h.sched.stop()


@pytest.mark.asyncio
async def test_his_own_word_does_not_cut_him_off():
    """等 is in what he is saying; an interim of it alone is him, not the user."""
    h = Harness()
    await h.sched.start()
    try:
        await h.sched.say("先生，hammer 在等您確認權限。")
        await asyncio.sleep(0.15)
        await h.sched.user_interim("等")
        assert "stop" not in h.types(), h.types()
    finally:
        await h.sched.stop()


# --- what he says in his own words -----------------------------------------

@pytest.mark.asyncio
async def test_the_resume_bridge_is_said_in_mandarin(monkeypatch):
    monkeypatch.setenv("JARVIS_LANGUAGE", "zh-TW")
    from speech import Priority, ZH_BRIDGES
    h = Harness()
    await h.sched.start()
    try:
        await h.sched.say("第一句話在這裡。第二句話在這裡。第三句話在這裡。")
        await asyncio.sleep(0.1)
        await h.sched.say("緊急：hammer 需要你。", Priority.URGENT, immediate=True)
        await h.ack_all(rounds=30)
        spoken = [text for _, _, text in h.audio()]
        assert any(t in ZH_BRIDGES for t in spoken), spoken
    finally:
        await h.sched.stop()


@pytest.mark.asyncio
async def test_unread_news_opens_in_mandarin(monkeypatch):
    monkeypatch.setenv("JARVIS_LANGUAGE", "zh-TW")
    from speech import ZH_UNREAD_PREFIX
    h = Harness()
    h.sched._unread.append("hammer 需要你。")
    await h.sched.start()
    try:
        await asyncio.sleep(0.3)
        spoken = " ".join(text for _, _, text in h.audio())
        assert spoken.startswith(ZH_UNREAD_PREFIX), spoken
    finally:
        await h.sched.stop()
