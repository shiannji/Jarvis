"""
i18n.py — which language JARVIS hears, thinks out loud in, and speaks.

One setting, `JARVIS_LANGUAGE`:

    en      the default, and the original: a British butler, in English.
    zh-TW   Mandarin, written as it is in Taiwan (繁體中文).

It decides three things, and nothing else:

  * the language the browser's recogniser listens for (`speech_lang`),
    handed to the page in the `/ws/voice` config frame;
  * the language the brain replies in (`brain_directive`), one fixed
    paragraph appended to its launch prompt;
  * the handful of lines the server speaks in its own words — the greeting,
    "cancelled", "the work in X is done" — through `pick`.

Everything the brain reads stays English: tool results, the persona, the
handover. A model reads English instructions perfectly well and replies in
whatever language it is told to, so translating the inputs would buy nothing
and cost every test that pins them.

Read on every call rather than once at import, so a test — or a settings
change written to `os.environ` — takes effect without reloading anything.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

EN = "en"
ZH_TW = "zh-TW"
SUPPORTED = (EN, ZH_TW)

# Spellings people actually type into a .env for "Traditional Chinese".
# Anything else — including an empty or garbled value — is English, which is
# what JARVIS was before this setting existed.
_ZH_TW_ALIASES = frozenset({
    "zh-tw", "zh_tw", "zh", "zh-hant", "zh_hant", "zh-hant-tw", "tw",
    "cmn-hant-tw", "chinese", "中文", "繁體中文", "繁中", "國語",
})


def normalize(raw: str | None) -> str:
    """Any spelling of a supported language, as `en` or `zh-TW`."""
    return ZH_TW if (raw or "").strip().lower() in _ZH_TW_ALIASES else EN


def language() -> str:
    """`en` or `zh-TW`, from `JARVIS_LANGUAGE`."""
    return normalize(os.getenv("JARVIS_LANGUAGE"))


def is_zh() -> bool:
    return language() == ZH_TW


def pick(en: str, zh: str) -> str:
    """The line in the language JARVIS is speaking.

    Both are written at the call site, side by side, so the English that the
    tests pin stays exactly where it was and the translation sits next to the
    sentence it translates.
    """
    return zh if is_zh() else en


def speech_lang() -> str:
    """The BCP-47 tag the browser's SpeechRecognition listens with."""
    return "zh-TW" if is_zh() else "en-US"


# --- the brain -------------------------------------------------------------
#
# Appended to the launch prompt, which is trusted operator prose in every
# generation (see `brain.launch_prompt`), so it is a CONSTANT chosen by a
# lookup — no part of the setting's own value ever reaches the prompt — and
# it carries none of the characters that prompt is held free of: no angle
# bracket and no double quote.
_ZH_TW_DIRECTIVE = (
    "Language: the user speaks Mandarin. What reaches you is Chrome's "
    "Traditional Chinese (Taiwan) transcript of it, homophone slips included, "
    "so read it for what he meant: 賈維斯, 加維斯 or 嘉維斯 is you, and 克勞德 "
    "or cloud code is Claude Code. Reply only in spoken Traditional Chinese "
    "as people talk in Taiwan (繁體中文、台灣用語) — never Simplified "
    "characters and never whole English sentences, though names that are "
    "normally said in English stay as they are (Claude Code, Sonnet, Opus, "
    "GitHub, a project's own name). Use full-width punctuation (，。？！); "
    "the voice pauses on it. Every rule of your persona still holds: one or "
    "two short sentences, nothing that cannot be spoken aloud, nothing said "
    "before a tool, and where it says sir, say 先生. Tool results reach you "
    "in English; report them in Chinese, in your own words. Pass names to "
    "tools as he said them — the tools resolve near-misses. Where your "
    "persona gives him an English phrase to say, give him the Chinese words "
    "the server listens for instead: 重新開始 to start fresh, 再說一次 to "
    "hear your last reply again."
)

_DIRECTIVES = {ZH_TW: _ZH_TW_DIRECTIVE}


def brain_directive(lang: str) -> str:
    """The paragraph that makes the brain answer in `lang`, or "" for English.

    `lang` is a key, never text: an unknown value — including a hostile one —
    selects nothing.
    """
    return _DIRECTIVES.get(lang, "")


# --- speaking Chinese ------------------------------------------------------

_ZH_DIGITS = ("零", "一", "兩", "三", "四", "五", "六", "七", "八", "九")


def zh_count(n: int) -> str:
    """A small count the way it is said before a measure word: 一、兩、三…
    Ten and up stay digits, which every TTS reads correctly."""
    return _ZH_DIGITS[n] if 0 <= n < 10 else str(n)


def zh_join(items: list[str]) -> str:
    """'a', 'a 和 b', 'a、b 和 c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "、".join(items[:-1]) + f" 和 {items[-1]}"


_ZH_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def zh_clock(when: datetime) -> str:
    """'下午3點', '上午10點30分' — a time of day as it is said in Taiwan."""
    h, m = when.hour, when.minute
    if h < 5:
        part = "凌晨"
    elif h < 12:
        part = "上午"
    elif h < 13:
        part = "中午"
    elif h < 18:
        part = "下午"
    else:
        part = "晚上"
    hour12 = h % 12 or 12
    return f"{part}{hour12}點" + (f"{m}分" if m else "")


def zh_when(when: datetime, now: datetime) -> str:
    """A spoken moment that names the day when it is not today: '下午3點',
    '明天上午10點', '星期一上午10點', '9月8日星期一上午10點'."""
    clock = zh_clock(when)
    days = (when.date() - now.date()).days
    if days <= 0:
        return clock
    if days == 1:
        return f"明天{clock}"
    weekday = _ZH_WEEKDAYS[when.weekday()]
    if days < 7:
        return f"{weekday}{clock}"
    return f"{when.month}月{when.day}日{weekday}{clock}"


# --- hearing Chinese -------------------------------------------------------
#
# A spoken command is matched against the WHOLE utterance once the ways
# people pad one are taken off its ends: punctuation the recogniser added,
# a "JARVIS" said first, a polite 請 or a trailing 吧. Never a substring:
# 重新開始 is also how you ask for a run to be started again, and "幫我重新
# 開始那個 run" must reach the brain, not wipe its context.
_CJK_PUNCT_RE = re.compile(r"[\s　-〿＀-／：-＠［-｀｛-･"
                           r"!-/:-@\[-`{-~…—–·]+")
_ZH_ADDRESS = ("賈維斯", "加維斯", "嘉維斯", "佳維斯", "jarvis", "travis")
_ZH_LEADING = ("請你", "麻煩你", "麻煩", "請", "那就", "那", "好", "嗯", "呃", "欸", "喂")
# Never 了: 算了 ("forget it") and 好了 ("that's enough") are words in their
# own right, and stripping it would turn them into something else.
_ZH_TRAILING = ("好不好", "好嗎", "可以嗎", "一下", "吧", "啦", "喔", "哦", "啊", "呀", "嘛")


def zh_core(text: str) -> str:
    """The command at the heart of an utterance: no punctuation, no spaces,
    no address, no polite padding at either end. Lower-cased, so a Latin
    "JARVIS" the recogniser kept is padding too."""
    t = _CJK_PUNCT_RE.sub("", (text or "").lower())
    changed = True
    while changed and t:
        changed = False
        for word in _ZH_ADDRESS + _ZH_LEADING:
            if t.startswith(word) and len(t) > len(word):
                t = t[len(word):]
                changed = True
        for word in _ZH_ADDRESS + _ZH_TRAILING:
            if t.endswith(word) and len(t) > len(word):
                t = t[:-len(word)]
                changed = True
    return t
