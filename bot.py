

import asyncio
import contextvars
import html
import io
import json
import logging
import os
import random
import re
import time
import sqlite3
import traceback
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

from telegram import (
    Bot,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    Chat,
    ChatMemberAdministrator,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Message,
    Update,
    User,
)
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    TypeHandler,
)

# =============================================================================
# LANGUAGE PACK (inlined from lang.py)
# =============================================================================
from typing import Dict, List, Tuple  # noqa: E402  (used by inlined lang tables)

# ----------------------------------------------------------------------
# Languages shown in the /settings -> Lang menu (matches Miss Rose UI).
# ----------------------------------------------------------------------
LANGUAGES: List[Tuple[str, str]] = [
    ("en", "🇬🇧 English"),
    ("it", "🇮🇹 Italiano"),
    ("es", "🇪🇸 Español"),
    ("pt", "🇵🇹 Português"),
    ("de", "🇩🇪 Deutsch"),
    ("fr", "🇫🇷 Français"),
    ("ro", "🇷🇴 Română"),
    ("nl", "🇳🇱 Nederlands"),
    ("tr", "🇹🇷 Türkçe"),
    ("zh", "🇨🇳 简体中文"),
    ("zt", "🇹🇼 繁體中文"),
    ("uk", "🇺🇦 Українська"),
    ("ru", "🇷🇺 Русский"),
    ("kk", "🇰🇿 Қазақ"),
    ("id", "🇮🇩 Indonesia"),
    ("uz", "🇺🇿 O'zbekcha"),
    ("uz_cy", "🇺🇿 Ўзбекча"),
    ("az", "🇦🇿 Azərbaycanca"),
    ("ms", "🇲🇾 Melayu"),
    ("so", "🇸🇴 Soomaali"),
    ("sq", "🇦🇱 Shqipe"),
    ("sr", "🇷🇸 Srpski"),
    ("am", "🇪🇹 Amharic"),
    ("el", "🇬🇷 Ελληνικά"),
    ("ar", "🇸🇦 العربية"),
    ("ko", "🇰🇷 한국어"),
    ("fa", "🇮🇷 پارسی"),
    ("ku", "☀️ کوردی"),
    ("hi", "🇮🇳 हिन्दी"),
    ("si", "🇱🇰 සිංහල"),
    ("bn", "🇧🇩 বাংলা"),
    ("ur", "🇵🇰 اُردُو"),
    ("he", "🇮🇱 עברית"),
]


# All 32 supported locales. The runtime checks this set before walking the
# AUTO_TRANSLATE table; missing-key lookups fall back silently to English.
TRANSLATED_LOCALES = frozenset({
    "en", "hi", "bn", "ur", "ar", "es", "fr", "de", "ru", "zh",
    "pt", "id", "tr", "it", "ro", "nl", "zt", "uk", "kk", "uz",
    "uz_cy", "az", "ms", "so", "sq", "sr", "am", "el", "ko",
    "fa", "ku", "si", "he",
})


# ----------------------------------------------------------------------
# Keyed templates -- preserves the original behaviour of ``_t(lang, key)``.
# Add new keys here in the "en" block first; other languages fall back to
# the English template when their key is missing.
# ----------------------------------------------------------------------
I18N: Dict[str, Dict[str, str]] = {
    "en": {
        "warned": "{user} received warning {count}/{limit}.",
        "warn_reset": "Warns for {user} reset to 0.",
        "warn_limit": "{user} reached warning limit {limit}. What to do?",
        "warns_none": "{user} has no warns.",
        "muted": "{user} has been 🔇 muted.",
        "unmuted": "{user} is no longer 🔇 muted.",
        "banned": "{user} has been 🚫 banned.",
        "unbanned": "{user} has been unbanned.",
        "kicked": "{user} has been kicked.",
        "no_target": "Reply to a user, or pass an @username / user-id.",
        "not_admin": "❌ Admins only.",
        "bot_no_perm": "❌ I don't have the right permission to do this.",
        "self_target": "❌ You can't use this on yourself.",
        "admin_target": "❌ I can't act against another admin.",
        "owner_target": "❌ I can't act against the chat owner.",
        "cant_self": "❌ You can't use this on yourself.",
        "cant_admin": "❌ I can't act against another admin.",
        "action_failed": "❌ Failed: {error}",
        "reason_label": "Reason: {reason}",
        "fed_only_owner": "❌ Only the federation owner can do this.",
        "fed_not_found": "❌ Federation not found.",
        "fed_created": "✅ Federation '{name}' created with id `{fid}`.",
        "fed_joined": "✅ This chat joined federation `{fid}`.",
        "fed_left": "✅ This chat left the federation.",
        "fed_banned": "✅ {user} fed-banned across {n} chats. Reason: {reason}",
        "fed_unbanned": "✅ {user} removed from federation ban list.",
        "note_saved": "✅ Note `{name}` saved.",
        "note_cleared": "✅ Note `{name}` cleared.",
        "note_missing": "❌ I don't have a note named `{name}`.",
        "notes_empty": "No notes in this chat.",
        "filter_saved": "✅ Filter `{kw}` saved.",
        "filter_cleared": "✅ Filter `{kw}` cleared.",
        "filters_empty": "No filters configured here.",
        "lock_set": "🔒 Locked `{type}`.",
        "unlock_set": "🔓 Unlocked `{type}`.",
        "lock_unknown": "❌ Unknown lock type. Try /locktypes.",
        "bl_added": "✅ Added to blacklist: {word}",
        "bl_removed": "✅ Removed from blacklist: {word}",
        "bl_empty": "Blacklist is empty.",
        "disabled_set": "Command `{cmd}` disabled.",
        "enabled_set": "Command `{cmd}` enabled.",
        "afk_on": "{user} is now AFK. Reason: {reason}",
        "afk_back": "{user} is back. Was AFK for {dur}.",
        "afk_mentioned": "{user} is AFK ({dur}). Reason: {reason}",
        "connect_ok": "✅ Connected to {title}.",
        "connect_off": "Disconnected.",
        "connect_none": "Not connected to any chat.",
        "gban_ok": "✅ Globally banned {user}.",
        "ungban_ok": "✅ Removed {user} from the global ban list.",
        "welcome_default": "Welcome {mention} to {groupname}!",
        "goodbye_default": "Goodbye {mention}!",
        "captcha_prompt": "👋 Welcome {mention}! Solve: {a} + {b} = ?",
        "captcha_wrong": "❌ Wrong! Try again.",
        "captcha_correct": "✅ Correct! Welcome {mention}!",
        "captcha_timeout": "⏰ {mention} did not solve the captcha and was removed.",
        "settings_admin_only": "Only administrators can use /settings.",
        "where_open": "Where do you want to open the settings menu?",
        "open_here": "👥 Open here",
        "open_private": "👤 Open in Private Chat",
        "settings_closed": "Settings closed.",
        "lang_changed": "Done — I will now speak English here.",
        "user_lang_changed": "✅ Your language is now {lang}. All my messages will appear in this language.",
        "rules_updated": "✅ Rules updated.",
        "rules_cleared": "✅ Rules cleared.",
        "no_rules": "No rules set.",
        "perms_title": "🕹 Permissions\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Permissions saved for {user}.",
        "perm_text": "Text messages",
        "perm_photo": "Photo",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Voice",
        "perm_file": "File",
        "perm_roundvideo": "Round Video",
        "perm_polls": "Polls",
        "perm_links": "Enable link previews",
        "perm_tag": "Edit own tag",
        "perm_save_btn": "Save ✓",
        "cancelled": "❌ Cancelled.",
        "done": "✅ Done.",
        "error": "❌ Error: {msg}",
        "admins_only": "❌ Admins only.",
        "reply_required": "❌ Reply to a message first.",
        "user_not_found": "❌ User not found.",
        "invalid_args": "❌ Invalid arguments.",
    },
    "hi": {
        "warned": "{user} ko warning di gayi ({count}/{limit}).",
        "warn_reset": "{user} ki warnings 0 kar di gayi.",
        "warn_limit": "{user} warning limit {limit} tak pahunch gaya. Kya karna hai?",
        "warns_none": "{user} ki koi warning nahi hai.",
        "muted": "{user} ko 🔇 mute kar diya.",
        "unmuted": "{user} ab 🔇 mute nahi hai.",
        "banned": "{user} ko 🚫 ban kar diya.",
        "unbanned": "{user} ka ban hata diya.",
        "kicked": "{user} ko kick kar diya.",
        "no_target": "Kisi user ko reply karo, ya @username / user-id do.",
        "not_admin": "❌ Sirf admins ke liye.",
        "bot_no_perm": "❌ Mujhe yeh kaam karne ki permission nahi hai.",
        "self_target": "❌ Khud par yeh action nahi le sakte.",
        "admin_target": "❌ Doosre admin par action nahi le sakta.",
        "owner_target": "❌ Chat owner par action nahi le sakta.",
        "cant_self": "❌ Khud par yeh action nahi le sakte.",
        "cant_admin": "❌ Doosre admin par action nahi le sakta.",
        "action_failed": "❌ Asafal: {error}",
        "reason_label": "Wajah: {reason}",
        "fed_only_owner": "❌ Sirf federation owner yeh kar sakta hai.",
        "fed_not_found": "❌ Federation nahi mili.",
        "fed_created": "✅ Federation '{name}' ban gayi. ID `{fid}`.",
        "fed_joined": "✅ Yeh chat federation `{fid}` me shaamil ho gayi.",
        "fed_left": "✅ Yeh chat federation se nikal gayi.",
        "fed_banned": "✅ {user} ko {n} chats me fed-ban kiya. Wajah: {reason}",
        "fed_unbanned": "✅ {user} ko federation ban-list se hata diya.",
        "note_saved": "✅ Note `{name}` save ho gaya.",
        "note_cleared": "✅ Note `{name}` hata diya.",
        "note_missing": "❌ `{name}` naam ka koi note nahi hai.",
        "notes_empty": "Is chat me koi note nahi hai.",
        "filter_saved": "✅ Filter `{kw}` save ho gaya.",
        "filter_cleared": "✅ Filter `{kw}` hata diya.",
        "filters_empty": "Yahaan koi filter nahi hai.",
        "lock_set": "🔒 `{type}` lock kar diya.",
        "unlock_set": "🔓 `{type}` unlock kar diya.",
        "lock_unknown": "❌ Lock type pata nahi. /locktypes try karo.",
        "bl_added": "✅ Blacklist me jod diya: {word}",
        "bl_removed": "✅ Blacklist se hata diya: {word}",
        "bl_empty": "Blacklist khaali hai.",
        "disabled_set": "Command `{cmd}` band kar di.",
        "enabled_set": "Command `{cmd}` chalu kar di.",
        "afk_on": "{user} ab AFK hai. Wajah: {reason}",
        "afk_back": "{user} wapas aa gaya. AFK time: {dur}.",
        "afk_mentioned": "{user} AFK hai ({dur}). Wajah: {reason}",
        "connect_ok": "✅ {title} se connect ho gaya.",
        "connect_off": "Disconnect ho gaya.",
        "connect_none": "Kisi chat se connect nahi hai.",
        "gban_ok": "✅ {user} ko global-ban kar diya.",
        "ungban_ok": "✅ {user} ko global ban-list se hata diya.",
        "welcome_default": "{mention} ka {groupname} me swagat hai!",
        "goodbye_default": "Alvida {mention}!",
        "captcha_prompt": "👋 Swagat {mention}! Solve karo: {a} + {b} = ?",
        "captcha_wrong": "❌ Galat! Phir se try karo.",
        "captcha_correct": "✅ Sahi! Swagat {mention}!",
        "captcha_timeout": "⏰ {mention} ne captcha solve nahi kiya, isiliye nikaal diya.",
        "settings_admin_only": "Sirf admins /settings use kar sakte hain.",
        "where_open": "Settings menu kahaan kholna hai?",
        "open_here": "👥 Yahin kholo",
        "open_private": "👤 Private Chat me kholo",
        "settings_closed": "Settings band kar diye.",
        "lang_changed": "Theek hai — ab main yahaan Hindi me baat karunga.",
        "user_lang_changed": "✅ Aapki language ab {lang} hai. Saare messages isi me aayenge.",
        "rules_updated": "✅ Rules update ho gaye.",
        "rules_cleared": "✅ Rules saaf kar diye.",
        "no_rules": "Koi rules set nahi hain.",
        "perms_title": "🕹 Permissions\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} ki permissions save ho gayi.",
        "perm_text": "Text messages",
        "perm_photo": "Photo",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Voice",
        "perm_file": "File",
        "perm_roundvideo": "Round Video",
        "perm_polls": "Polls",
        "perm_links": "Link preview chalu",
        "perm_tag": "Apna tag edit karo",
        "perm_save_btn": "Save ✓",
        "cancelled": "❌ Cancel kar diya.",
        "done": "✅ Done.",
        "error": "❌ Error: {msg}",
        "admins_only": "❌ Sirf admins ke liye.",
        "reply_required": "❌ Pehle kisi message ko reply karo.",
        "user_not_found": "❌ User nahi mila.",
        "invalid_args": "❌ Galat arguments.",
    },
    "bn": {
        "warned": "{user} সতর্ক করা হয়েছে। ({count}/{limit})",
        "warn_reset": "{user}-এর সতর্কতা ০ করা হয়েছে।",
        "warn_limit": "{user} সতর্কতার সীমা {limit}-এ পৌঁছেছে। কী করব?",
        "warns_none": "{user}-এর কোনো সতর্কতা নেই।",
        "muted": "{user} 🔇 মিউট করা হয়েছে।",
        "unmuted": "{user} আর 🔇 মিউট নয়।",
        "banned": "{user} 🚫 ব্যান করা হয়েছে।",
        "unbanned": "{user} আনব্যান করা হয়েছে।",
        "kicked": "{user} কিক করা হয়েছে।",
        "no_target": "ইউজারকে রিপ্লাই করুন, অথবা @username / user-id দিন।",
        "not_admin": "❌ শুধু অ্যাডমিনদের জন্য।",
        "bot_no_perm": "❌ এই কাজের অনুমতি আমার নেই।",
        "self_target": "❌ নিজের উপর প্রয়োগ করা যাবে না।",
        "admin_target": "❌ অন্য অ্যাডমিনের বিরুদ্ধে এটি করা যাবে না।",
        "owner_target": "❌ চ্যাট-ওনারের বিরুদ্ধে এটি করা যাবে না।",
        "cant_self": "❌ নিজের উপর প্রয়োগ করা যাবে না।",
        "cant_admin": "❌ অন্য অ্যাডমিনের বিরুদ্ধে এটি করা যাবে না।",
        "action_failed": "❌ ব্যর্থ: {error}",
        "reason_label": "কারণ: {reason}",
        "fed_only_owner": "❌ শুধু ফেডারেশন ওনার এটি করতে পারবেন।",
        "fed_not_found": "❌ ফেডারেশন পাওয়া যায়নি।",
        "fed_created": "✅ ফেডারেশন '{name}' তৈরি হয়েছে। আইডি `{fid}`।",
        "fed_joined": "✅ এই চ্যাট ফেডারেশন `{fid}`-এ যুক্ত হলো।",
        "fed_left": "✅ এই চ্যাট ফেডারেশন থেকে বের হলো।",
        "fed_banned": "✅ {user} {n}টি চ্যাটে ফেড-ব্যান হয়েছে। কারণ: {reason}",
        "fed_unbanned": "✅ {user} ফেডারেশন ব্যান-লিস্ট থেকে সরানো হলো।",
        "note_saved": "✅ নোট `{name}` সংরক্ষিত।",
        "note_cleared": "✅ নোট `{name}` মুছে ফেলা হলো।",
        "note_missing": "❌ `{name}` নামে কোনো নোট নেই।",
        "notes_empty": "এই চ্যাটে কোনো নোট নেই।",
        "filter_saved": "✅ ফিল্টার `{kw}` সংরক্ষিত।",
        "filter_cleared": "✅ ফিল্টার `{kw}` মুছে ফেলা হলো।",
        "filters_empty": "কোনো ফিল্টার নেই।",
        "lock_set": "🔒 `{type}` লক করা হলো।",
        "unlock_set": "🔓 `{type}` আনলক হলো।",
        "lock_unknown": "❌ অজানা লক টাইপ। /locktypes দেখুন।",
        "bl_added": "✅ ব্ল্যাকলিস্টে যোগ: {word}",
        "bl_removed": "✅ ব্ল্যাকলিস্ট থেকে সরানো: {word}",
        "bl_empty": "ব্ল্যাকলিস্ট খালি।",
        "disabled_set": "কমান্ড `{cmd}` বন্ধ করা হলো।",
        "enabled_set": "কমান্ড `{cmd}` চালু করা হলো।",
        "afk_on": "{user} এখন AFK। কারণ: {reason}",
        "afk_back": "{user} ফিরে এসেছে। AFK ছিল {dur}।",
        "afk_mentioned": "{user} AFK ({dur})। কারণ: {reason}",
        "connect_ok": "✅ {title}-এর সাথে সংযুক্ত।",
        "connect_off": "সংযোগ বিচ্ছিন্ন।",
        "connect_none": "কোনো চ্যাটের সাথে সংযুক্ত নয়।",
        "gban_ok": "✅ {user} গ্লোবাল-ব্যান হলো।",
        "ungban_ok": "✅ {user} গ্লোবাল ব্যান-লিস্ট থেকে সরানো হলো।",
        "welcome_default": "{groupname}-এ {mention}-কে স্বাগতম!",
        "goodbye_default": "বিদায় {mention}!",
        "captcha_prompt": "👋 স্বাগতম {mention}! সমাধান করুন: {a} + {b} = ?",
        "captcha_wrong": "❌ ভুল! আবার চেষ্টা করুন।",
        "captcha_correct": "✅ সঠিক! স্বাগতম {mention}!",
        "captcha_timeout": "⏰ {mention} ক্যাপচা সমাধান না করায় সরানো হলো।",
        "settings_admin_only": "শুধু অ্যাডমিনরা /settings ব্যবহার করতে পারবেন।",
        "where_open": "সেটিংস মেনু কোথায় খুলবেন?",
        "open_here": "👥 এখানেই খুলুন",
        "open_private": "👤 ব্যক্তিগত চ্যাটে খুলুন",
        "settings_closed": "সেটিংস বন্ধ।",
        "lang_changed": "বেশ, এবার বাংলায়ই কথা হোক!",
        "user_lang_changed": "✅ আপনার ভাষা এখন {lang}। সব বার্তা এই ভাষায় আসবে।",
        "rules_updated": "✅ নিয়ম আপডেট হলো।",
        "rules_cleared": "✅ নিয়ম মোছা হলো।",
        "no_rules": "কোনো নিয়ম সেট নেই।",
        "perms_title": "🕹 অনুমতি\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user}-এর অনুমতি সংরক্ষিত।",
        "perm_text": "টেক্সট মেসেজ",
        "perm_photo": "ছবি",
        "perm_video": "ভিডিও",
        "perm_sticker": "স্টিকার/GIF",
        "perm_audio": "অডিও",
        "perm_voice": "ভয়েস",
        "perm_file": "ফাইল",
        "perm_roundvideo": "রাউন্ড ভিডিও",
        "perm_polls": "পোল",
        "perm_links": "লিঙ্ক প্রিভিউ চালু",
        "perm_tag": "নিজের ট্যাগ এডিট",
        "perm_save_btn": "সংরক্ষণ ✓",
        "cancelled": "❌ বাতিল।",
        "done": "✅ সম্পন্ন।",
        "error": "❌ ত্রুটি: {msg}",
        "admins_only": "❌ শুধু অ্যাডমিনদের জন্য।",
        "reply_required": "❌ আগে একটি বার্তায় রিপ্লাই দিন।",
        "user_not_found": "❌ ইউজার পাওয়া যায়নি।",
        "invalid_args": "❌ ভুল আর্গুমেন্ট।",
    },
    "ur": {
        "warned": "{user} کو تنبیہ دی گئی ({count}/{limit})۔",
        "warn_reset": "{user} کی وارننگز ۰ کر دی گئیں۔",
        "warn_limit": "{user} وارننگ حد {limit} پر پہنچ گیا۔ کیا کریں؟",
        "warns_none": "{user} کی کوئی وارننگ نہیں۔",
        "muted": "{user} 🔇 میوٹ کر دیا گیا۔",
        "unmuted": "{user} اب 🔇 میوٹ نہیں۔",
        "banned": "{user} پر 🚫 پابندی لگا دی گئی۔",
        "unbanned": "{user} سے پابندی ہٹا دی گئی۔",
        "kicked": "{user} کو نکال دیا گیا۔",
        "no_target": "صارف کو ریپلائی کریں، یا @username / user-id بھیجیں۔",
        "not_admin": "❌ صرف ایڈمنز کے لیے۔",
        "bot_no_perm": "❌ یہ کام کرنے کی اجازت میرے پاس نہیں۔",
        "self_target": "❌ خود پر استعمال نہیں ہو سکتا۔",
        "admin_target": "❌ کسی اور ایڈمن پر یہ کارروائی نہیں۔",
        "owner_target": "❌ چیٹ اونر پر یہ کارروائی نہیں۔",
        "cant_self": "❌ خود پر استعمال نہیں ہو سکتا۔",
        "cant_admin": "❌ کسی اور ایڈمن پر یہ کارروائی نہیں۔",
        "action_failed": "❌ ناکام: {error}",
        "reason_label": "وجہ: {reason}",
        "fed_only_owner": "❌ صرف فیڈریشن اونر یہ کر سکتا ہے۔",
        "fed_not_found": "❌ فیڈریشن نہیں ملی۔",
        "fed_created": "✅ فیڈریشن '{name}' بنا دی گئی۔ آئی ڈی `{fid}`۔",
        "fed_joined": "✅ یہ چیٹ فیڈریشن `{fid}` میں شامل۔",
        "fed_left": "✅ یہ چیٹ فیڈریشن سے نکل گئی۔",
        "fed_banned": "✅ {user} {n} چیٹس میں فیڈ-بین ہوا۔ وجہ: {reason}",
        "fed_unbanned": "✅ {user} فیڈریشن بین-لسٹ سے ہٹا دیا گیا۔",
        "note_saved": "✅ نوٹ `{name}` محفوظ۔",
        "note_cleared": "✅ نوٹ `{name}` ہٹا دیا۔",
        "note_missing": "❌ `{name}` نام کا کوئی نوٹ نہیں۔",
        "notes_empty": "اس چیٹ میں کوئی نوٹ نہیں۔",
        "filter_saved": "✅ فلٹر `{kw}` محفوظ۔",
        "filter_cleared": "✅ فلٹر `{kw}` ہٹا دیا۔",
        "filters_empty": "یہاں کوئی فلٹر نہیں۔",
        "lock_set": "🔒 `{type}` لاک کر دیا۔",
        "unlock_set": "🔓 `{type}` اَن-لاک کر دیا۔",
        "lock_unknown": "❌ نامعلوم لاک قسم۔ /locktypes دیکھیں۔",
        "bl_added": "✅ بلیک لسٹ میں شامل: {word}",
        "bl_removed": "✅ بلیک لسٹ سے نکال دیا: {word}",
        "bl_empty": "بلیک لسٹ خالی ہے۔",
        "disabled_set": "کمانڈ `{cmd}` بند کر دی۔",
        "enabled_set": "کمانڈ `{cmd}` چالو کر دی۔",
        "afk_on": "{user} اب AFK ہے۔ وجہ: {reason}",
        "afk_back": "{user} واپس آ گیا۔ AFK وقت: {dur}۔",
        "afk_mentioned": "{user} AFK ہے ({dur})۔ وجہ: {reason}",
        "connect_ok": "✅ {title} سے کنیکٹ ہو گیا۔",
        "connect_off": "ڈسکنیکٹ ہو گیا۔",
        "connect_none": "کسی چیٹ سے کنیکٹ نہیں۔",
        "gban_ok": "✅ {user} گلوبل-بین ہوا۔",
        "ungban_ok": "✅ {user} گلوبل بین-لسٹ سے ہٹا دیا۔",
        "welcome_default": "{groupname} میں {mention} کا خوش آمدید!",
        "goodbye_default": "الوداع {mention}!",
        "captcha_prompt": "👋 خوش آمدید {mention}! حل کریں: {a} + {b} = ?",
        "captcha_wrong": "❌ غلط! دوبارہ کوشش کریں۔",
        "captcha_correct": "✅ درست! خوش آمدید {mention}!",
        "captcha_timeout": "⏰ {mention} نے کیپچا حل نہیں کیا، نکال دیا۔",
        "settings_admin_only": "صرف ایڈمن /settings استعمال کر سکتے ہیں۔",
        "where_open": "سیٹنگز مینو کہاں کھولنا ہے؟",
        "open_here": "👥 یہیں کھولیں",
        "open_private": "👤 پرائیویٹ چیٹ میں کھولیں",
        "settings_closed": "سیٹنگز بند۔",
        "lang_changed": "ٹھیک ہے — اب میں یہاں اردو میں بات کروں گا۔",
        "user_lang_changed": "✅ آپ کی زبان اب {lang} ہے۔ میرے سب پیغامات اسی میں آئیں گے۔",
        "rules_updated": "✅ قواعد اپ ڈیٹ ہو گئے۔",
        "rules_cleared": "✅ قواعد صاف کر دیے۔",
        "no_rules": "کوئی قاعدہ سیٹ نہیں۔",
        "perms_title": "🕹 اجازتیں\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} کی اجازتیں محفوظ۔",
        "perm_text": "ٹیکسٹ پیغامات",
        "perm_photo": "تصویر",
        "perm_video": "ویڈیو",
        "perm_sticker": "اسٹکر/GIF",
        "perm_audio": "آڈیو",
        "perm_voice": "وائس",
        "perm_file": "فائل",
        "perm_roundvideo": "راؤنڈ ویڈیو",
        "perm_polls": "پولز",
        "perm_links": "لنک پری ویو چالو",
        "perm_tag": "اپنا ٹیگ ایڈٹ کریں",
        "perm_save_btn": "محفوظ کریں ✓",
        "cancelled": "❌ منسوخ۔",
        "done": "✅ ہو گیا۔",
        "error": "❌ ایرر: {msg}",
        "admins_only": "❌ صرف ایڈمنز کے لیے۔",
        "reply_required": "❌ پہلے کسی پیغام کا ریپلائی دیں۔",
        "user_not_found": "❌ صارف نہیں ملا۔",
        "invalid_args": "❌ غلط آرگیومنٹس۔",
    },
    "ar": {
        "warned": "{user} تلقى تحذيرًا ({count}/{limit}).",
        "warn_reset": "تمت إعادة تحذيرات {user} إلى 0.",
        "warn_limit": "{user} وصل إلى حد التحذيرات {limit}. ماذا نفعل؟",
        "warns_none": "{user} ليس عليه تحذيرات.",
        "muted": "{user} تم كتمه 🔇.",
        "unmuted": "{user} لم يعد مكتومًا 🔇.",
        "banned": "{user} تم حظره 🚫.",
        "unbanned": "{user} تم رفع الحظر عنه.",
        "kicked": "{user} تم طرده.",
        "no_target": "ردّ على مستخدم أو أرسل @username / user-id.",
        "not_admin": "❌ للمشرفين فقط.",
        "bot_no_perm": "❌ لا أملك صلاحية لذلك.",
        "self_target": "❌ لا يمكنك استخدام هذا على نفسك.",
        "admin_target": "❌ لا يمكنني التصرف ضد مشرف آخر.",
        "owner_target": "❌ لا يمكنني التصرف ضد مالك المحادثة.",
        "cant_self": "❌ لا يمكنك استخدام هذا على نفسك.",
        "cant_admin": "❌ لا يمكنني التصرف ضد مشرف آخر.",
        "action_failed": "❌ فشل: {error}",
        "reason_label": "السبب: {reason}",
        "fed_only_owner": "❌ مالك الفيدرالية فقط يمكنه فعل ذلك.",
        "fed_not_found": "❌ الفيدرالية غير موجودة.",
        "fed_created": "✅ تم إنشاء الفيدرالية '{name}' بالمعرف `{fid}`.",
        "fed_joined": "✅ انضمت هذه المحادثة إلى الفيدرالية `{fid}`.",
        "fed_left": "✅ غادرت هذه المحادثة الفيدرالية.",
        "fed_banned": "✅ تم حظر {user} في {n} محادثات. السبب: {reason}",
        "fed_unbanned": "✅ تم إزالة {user} من قائمة حظر الفيدرالية.",
        "note_saved": "✅ تم حفظ الملاحظة `{name}`.",
        "note_cleared": "✅ تم مسح الملاحظة `{name}`.",
        "note_missing": "❌ لا توجد ملاحظة باسم `{name}`.",
        "notes_empty": "لا توجد ملاحظات في هذه المحادثة.",
        "filter_saved": "✅ تم حفظ الفلتر `{kw}`.",
        "filter_cleared": "✅ تم مسح الفلتر `{kw}`.",
        "filters_empty": "لا توجد فلاتر هنا.",
        "lock_set": "🔒 تم قفل `{type}`.",
        "unlock_set": "🔓 تم فتح قفل `{type}`.",
        "lock_unknown": "❌ نوع قفل غير معروف. جرّب /locktypes.",
        "bl_added": "✅ أُضيف إلى القائمة السوداء: {word}",
        "bl_removed": "✅ أُزيل من القائمة السوداء: {word}",
        "bl_empty": "القائمة السوداء فارغة.",
        "disabled_set": "تم تعطيل الأمر `{cmd}`.",
        "enabled_set": "تم تفعيل الأمر `{cmd}`.",
        "afk_on": "{user} غائب الآن (AFK). السبب: {reason}",
        "afk_back": "{user} عاد. كان غائبًا لمدة {dur}.",
        "afk_mentioned": "{user} غائب ({dur}). السبب: {reason}",
        "connect_ok": "✅ تم الاتصال بـ {title}.",
        "connect_off": "تم قطع الاتصال.",
        "connect_none": "غير متصل بأي محادثة.",
        "gban_ok": "✅ تم حظر {user} عالميًا.",
        "ungban_ok": "✅ تم إزالة {user} من قائمة الحظر العالمية.",
        "welcome_default": "أهلًا بك {mention} في {groupname}!",
        "goodbye_default": "وداعًا {mention}!",
        "captcha_prompt": "👋 أهلًا {mention}! حلّ: {a} + {b} = ?",
        "captcha_wrong": "❌ خطأ! حاول مجددًا.",
        "captcha_correct": "✅ صحيح! أهلًا {mention}!",
        "captcha_timeout": "⏰ {mention} لم يحلّ الكابتشا وتمت إزالته.",
        "settings_admin_only": "يمكن للمشرفين فقط استخدام /settings.",
        "where_open": "أين تريد فتح قائمة الإعدادات؟",
        "open_here": "👥 افتح هنا",
        "open_private": "👤 افتح في الخاص",
        "settings_closed": "تم إغلاق الإعدادات.",
        "lang_changed": "تم — سأتحدث بالعربية هنا الآن.",
        "user_lang_changed": "✅ لغتك الآن {lang}. ستظهر جميع رسائلي بهذه اللغة.",
        "rules_updated": "✅ تم تحديث القواعد.",
        "rules_cleared": "✅ تم مسح القواعد.",
        "no_rules": "لا توجد قواعد.",
        "perms_title": "🕹 الصلاحيات\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ تم حفظ صلاحيات {user}.",
        "perm_text": "الرسائل النصية",
        "perm_photo": "الصور",
        "perm_video": "الفيديو",
        "perm_sticker": "ملصق/GIF",
        "perm_audio": "الصوت",
        "perm_voice": "الرسائل الصوتية",
        "perm_file": "الملف",
        "perm_roundvideo": "فيديو دائري",
        "perm_polls": "الاستطلاعات",
        "perm_links": "تفعيل معاينة الروابط",
        "perm_tag": "تعديل الوسم الخاص",
        "perm_save_btn": "حفظ ✓",
        "cancelled": "❌ تم الإلغاء.",
        "done": "✅ تم.",
        "error": "❌ خطأ: {msg}",
        "admins_only": "❌ للمشرفين فقط.",
        "reply_required": "❌ ردّ على رسالة أولًا.",
        "user_not_found": "❌ المستخدم غير موجود.",
        "invalid_args": "❌ معطيات غير صالحة.",
    },
    "es": {
        "warned": "{user} ha recibido aviso {count}/{limit}.",
        "warn_reset": "Avisos de {user} reiniciados a 0.",
        "warn_limit": "{user} alcanzó el límite de avisos {limit}. ¿Qué hacemos?",
        "warns_none": "{user} no tiene avisos.",
        "muted": "{user} ha sido 🔇 silenciado.",
        "unmuted": "{user} ya no está 🔇 silenciado.",
        "banned": "{user} ha sido 🚫 baneado.",
        "unbanned": "{user} ha sido desbaneado.",
        "kicked": "{user} ha sido expulsado.",
        "no_target": "Responde a un usuario o pasa @username / user-id.",
        "not_admin": "❌ Solo administradores.",
        "bot_no_perm": "❌ No tengo permiso para esto.",
        "self_target": "❌ No puedes usar esto contigo mismo.",
        "admin_target": "❌ No puedo actuar contra otro administrador.",
        "owner_target": "❌ No puedo actuar contra el propietario del chat.",
        "cant_self": "❌ No puedes hacerlo contigo mismo.",
        "cant_admin": "❌ No puedo actuar contra otro administrador.",
        "action_failed": "❌ Falló: {error}",
        "reason_label": "Motivo: {reason}",
        "fed_only_owner": "❌ Solo el dueño de la federación puede hacer esto.",
        "fed_not_found": "❌ Federación no encontrada.",
        "fed_created": "✅ Federación '{name}' creada con id `{fid}`.",
        "fed_joined": "✅ Este chat se unió a la federación `{fid}`.",
        "fed_left": "✅ Este chat salió de la federación.",
        "fed_banned": "✅ {user} fed-baneado en {n} chats. Motivo: {reason}",
        "fed_unbanned": "✅ {user} eliminado de la lista de baneo federada.",
        "note_saved": "✅ Nota `{name}` guardada.",
        "note_cleared": "✅ Nota `{name}` eliminada.",
        "note_missing": "❌ No tengo ninguna nota llamada `{name}`.",
        "notes_empty": "No hay notas en este chat.",
        "filter_saved": "✅ Filtro `{kw}` guardado.",
        "filter_cleared": "✅ Filtro `{kw}` eliminado.",
        "filters_empty": "No hay filtros configurados.",
        "lock_set": "🔒 Bloqueado `{type}`.",
        "unlock_set": "🔓 Desbloqueado `{type}`.",
        "lock_unknown": "❌ Tipo de bloqueo desconocido. Prueba /locktypes.",
        "bl_added": "✅ Añadido a la lista negra: {word}",
        "bl_removed": "✅ Eliminado de la lista negra: {word}",
        "bl_empty": "La lista negra está vacía.",
        "disabled_set": "Comando `{cmd}` desactivado.",
        "enabled_set": "Comando `{cmd}` activado.",
        "afk_on": "{user} está AFK. Motivo: {reason}",
        "afk_back": "{user} ha vuelto. Estuvo AFK durante {dur}.",
        "afk_mentioned": "{user} está AFK ({dur}). Motivo: {reason}",
        "connect_ok": "✅ Conectado a {title}.",
        "connect_off": "Desconectado.",
        "connect_none": "No conectado a ningún chat.",
        "gban_ok": "✅ {user} baneado globalmente.",
        "ungban_ok": "✅ {user} eliminado de la lista de baneo global.",
        "welcome_default": "¡Bienvenido {mention} a {groupname}!",
        "goodbye_default": "¡Adiós {mention}!",
        "captcha_prompt": "👋 ¡Bienvenido {mention}! Resuelve: {a} + {b} = ?",
        "captcha_wrong": "❌ ¡Incorrecto! Inténtalo de nuevo.",
        "captcha_correct": "✅ ¡Correcto! ¡Bienvenido {mention}!",
        "captcha_timeout": "⏰ {mention} no resolvió el captcha y fue eliminado.",
        "settings_admin_only": "Solo los administradores pueden usar /settings.",
        "where_open": "¿Dónde quieres abrir el menú de ajustes?",
        "open_here": "👥 Abrir aquí",
        "open_private": "👤 Abrir en chat privado",
        "settings_closed": "Ajustes cerrados.",
        "lang_changed": "Listo — ahora hablaré en español aquí.",
        "user_lang_changed": "✅ Tu idioma ahora es {lang}. Todos mis mensajes aparecerán en este idioma.",
        "rules_updated": "✅ Reglas actualizadas.",
        "rules_cleared": "✅ Reglas borradas.",
        "no_rules": "No hay reglas configuradas.",
        "perms_title": "🕹 Permisos\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Permisos guardados para {user}.",
        "perm_text": "Mensajes de texto",
        "perm_photo": "Foto",
        "perm_video": "Vídeo",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Voz",
        "perm_file": "Archivo",
        "perm_roundvideo": "Vídeo redondo",
        "perm_polls": "Encuestas",
        "perm_links": "Activar vista previa de enlaces",
        "perm_tag": "Editar etiqueta propia",
        "perm_save_btn": "Guardar ✓",
        "cancelled": "❌ Cancelado.",
        "done": "✅ Hecho.",
        "error": "❌ Error: {msg}",
        "admins_only": "❌ Solo administradores.",
        "reply_required": "❌ Responde a un mensaje primero.",
        "user_not_found": "❌ Usuario no encontrado.",
        "invalid_args": "❌ Argumentos inválidos.",
    },
    "fr": {
        "warned": "{user} a reçu l'avertissement {count}/{limit}.",
        "warn_reset": "Avertissements de {user} remis à 0.",
        "warn_limit": "{user} a atteint la limite d'avertissements {limit}. Que faire ?",
        "warns_none": "{user} n'a aucun avertissement.",
        "muted": "{user} a été 🔇 mis en sourdine.",
        "unmuted": "{user} n'est plus 🔇 en sourdine.",
        "banned": "{user} a été 🚫 banni.",
        "unbanned": "{user} a été débanni.",
        "kicked": "{user} a été expulsé.",
        "no_target": "Réponds à un utilisateur ou passe @username / user-id.",
        "not_admin": "❌ Réservé aux administrateurs.",
        "bot_no_perm": "❌ Je n'ai pas la permission.",
        "self_target": "❌ Tu ne peux pas faire ça sur toi-même.",
        "admin_target": "❌ Je ne peux pas agir contre un autre admin.",
        "owner_target": "❌ Je ne peux pas agir contre le propriétaire du chat.",
        "cant_self": "❌ Tu ne peux pas faire ça sur toi-même.",
        "cant_admin": "❌ Je ne peux pas agir contre un autre admin.",
        "action_failed": "❌ Échec : {error}",
        "reason_label": "Raison : {reason}",
        "fed_only_owner": "❌ Seul le propriétaire de la fédération peut faire ça.",
        "fed_not_found": "❌ Fédération introuvable.",
        "fed_created": "✅ Fédération '{name}' créée avec l'id `{fid}`.",
        "fed_joined": "✅ Ce chat a rejoint la fédération `{fid}`.",
        "fed_left": "✅ Ce chat a quitté la fédération.",
        "fed_banned": "✅ {user} fed-banni dans {n} chats. Raison : {reason}",
        "fed_unbanned": "✅ {user} retiré de la liste de bans fédérée.",
        "note_saved": "✅ Note `{name}` enregistrée.",
        "note_cleared": "✅ Note `{name}` supprimée.",
        "note_missing": "❌ Aucune note nommée `{name}`.",
        "notes_empty": "Aucune note dans ce chat.",
        "filter_saved": "✅ Filtre `{kw}` enregistré.",
        "filter_cleared": "✅ Filtre `{kw}` supprimé.",
        "filters_empty": "Aucun filtre configuré.",
        "lock_set": "🔒 `{type}` verrouillé.",
        "unlock_set": "🔓 `{type}` déverrouillé.",
        "lock_unknown": "❌ Type de verrou inconnu. Essaie /locktypes.",
        "bl_added": "✅ Ajouté à la liste noire : {word}",
        "bl_removed": "✅ Retiré de la liste noire : {word}",
        "bl_empty": "La liste noire est vide.",
        "disabled_set": "Commande `{cmd}` désactivée.",
        "enabled_set": "Commande `{cmd}` activée.",
        "afk_on": "{user} est maintenant AFK. Raison : {reason}",
        "afk_back": "{user} est de retour. AFK pendant {dur}.",
        "afk_mentioned": "{user} est AFK ({dur}). Raison : {reason}",
        "connect_ok": "✅ Connecté à {title}.",
        "connect_off": "Déconnecté.",
        "connect_none": "Connecté à aucun chat.",
        "gban_ok": "✅ {user} banni globalement.",
        "ungban_ok": "✅ {user} retiré de la liste des bans globaux.",
        "welcome_default": "Bienvenue {mention} sur {groupname} !",
        "goodbye_default": "Au revoir {mention} !",
        "captcha_prompt": "👋 Bienvenue {mention} ! Résous : {a} + {b} = ?",
        "captcha_wrong": "❌ Faux ! Réessaie.",
        "captcha_correct": "✅ Correct ! Bienvenue {mention} !",
        "captcha_timeout": "⏰ {mention} n'a pas résolu le captcha et a été retiré.",
        "settings_admin_only": "Seuls les administrateurs peuvent utiliser /settings.",
        "where_open": "Où veux-tu ouvrir le menu des paramètres ?",
        "open_here": "👥 Ouvrir ici",
        "open_private": "👤 Ouvrir en privé",
        "settings_closed": "Paramètres fermés.",
        "lang_changed": "C'est fait — je parlerai maintenant en français ici.",
        "user_lang_changed": "✅ Ta langue est maintenant {lang}. Tous mes messages apparaîtront dans cette langue.",
        "rules_updated": "✅ Règles mises à jour.",
        "rules_cleared": "✅ Règles effacées.",
        "no_rules": "Aucune règle définie.",
        "perms_title": "🕹 Permissions\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Permissions enregistrées pour {user}.",
        "perm_text": "Messages texte",
        "perm_photo": "Photo",
        "perm_video": "Vidéo",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Voix",
        "perm_file": "Fichier",
        "perm_roundvideo": "Vidéo ronde",
        "perm_polls": "Sondages",
        "perm_links": "Activer l'aperçu des liens",
        "perm_tag": "Modifier son tag",
        "perm_save_btn": "Enregistrer ✓",
        "cancelled": "❌ Annulé.",
        "done": "✅ Fait.",
        "error": "❌ Erreur : {msg}",
        "admins_only": "❌ Réservé aux administrateurs.",
        "reply_required": "❌ Réponds d'abord à un message.",
        "user_not_found": "❌ Utilisateur introuvable.",
        "invalid_args": "❌ Arguments invalides.",
    },
    "de": {
        "warned": "{user} hat Verwarnung {count}/{limit} erhalten.",
        "warn_reset": "Verwarnungen für {user} auf 0 zurückgesetzt.",
        "warn_limit": "{user} hat das Verwarnungslimit {limit} erreicht. Was tun?",
        "warns_none": "{user} hat keine Verwarnungen.",
        "muted": "{user} wurde 🔇 stummgeschaltet.",
        "unmuted": "{user} ist nicht mehr 🔇 stummgeschaltet.",
        "banned": "{user} wurde 🚫 gebannt.",
        "unbanned": "{user} wurde entbannt.",
        "kicked": "{user} wurde gekickt.",
        "no_target": "Antworte einem Nutzer oder übergib @username / user-id.",
        "not_admin": "❌ Nur für Admins.",
        "bot_no_perm": "❌ Ich habe nicht die Berechtigung dafür.",
        "self_target": "❌ Das geht nicht gegen dich selbst.",
        "admin_target": "❌ Ich kann nicht gegen einen anderen Admin vorgehen.",
        "owner_target": "❌ Ich kann nicht gegen den Chat-Besitzer vorgehen.",
        "cant_self": "❌ Das geht nicht gegen dich selbst.",
        "cant_admin": "❌ Ich kann nicht gegen einen anderen Admin vorgehen.",
        "action_failed": "❌ Fehlgeschlagen: {error}",
        "reason_label": "Grund: {reason}",
        "fed_only_owner": "❌ Nur der Föderationsinhaber kann das tun.",
        "fed_not_found": "❌ Föderation nicht gefunden.",
        "fed_created": "✅ Föderation '{name}' mit ID `{fid}` erstellt.",
        "fed_joined": "✅ Dieser Chat ist der Föderation `{fid}` beigetreten.",
        "fed_left": "✅ Dieser Chat hat die Föderation verlassen.",
        "fed_banned": "✅ {user} in {n} Chats fed-banned. Grund: {reason}",
        "fed_unbanned": "✅ {user} von der Föderations-Bannliste entfernt.",
        "note_saved": "✅ Notiz `{name}` gespeichert.",
        "note_cleared": "✅ Notiz `{name}` gelöscht.",
        "note_missing": "❌ Keine Notiz mit dem Namen `{name}`.",
        "notes_empty": "Keine Notizen in diesem Chat.",
        "filter_saved": "✅ Filter `{kw}` gespeichert.",
        "filter_cleared": "✅ Filter `{kw}` gelöscht.",
        "filters_empty": "Keine Filter konfiguriert.",
        "lock_set": "🔒 `{type}` gesperrt.",
        "unlock_set": "🔓 `{type}` entsperrt.",
        "lock_unknown": "❌ Unbekannter Sperrtyp. Versuche /locktypes.",
        "bl_added": "✅ Zur Blacklist hinzugefügt: {word}",
        "bl_removed": "✅ Aus der Blacklist entfernt: {word}",
        "bl_empty": "Die Blacklist ist leer.",
        "disabled_set": "Befehl `{cmd}` deaktiviert.",
        "enabled_set": "Befehl `{cmd}` aktiviert.",
        "afk_on": "{user} ist jetzt AFK. Grund: {reason}",
        "afk_back": "{user} ist zurück. War {dur} AFK.",
        "afk_mentioned": "{user} ist AFK ({dur}). Grund: {reason}",
        "connect_ok": "✅ Mit {title} verbunden.",
        "connect_off": "Verbindung getrennt.",
        "connect_none": "Mit keinem Chat verbunden.",
        "gban_ok": "✅ {user} global gebannt.",
        "ungban_ok": "✅ {user} von der globalen Bannliste entfernt.",
        "welcome_default": "Willkommen {mention} in {groupname}!",
        "goodbye_default": "Tschüss {mention}!",
        "captcha_prompt": "👋 Willkommen {mention}! Löse: {a} + {b} = ?",
        "captcha_wrong": "❌ Falsch! Versuche es nochmal.",
        "captcha_correct": "✅ Richtig! Willkommen {mention}!",
        "captcha_timeout": "⏰ {mention} hat das Captcha nicht gelöst und wurde entfernt.",
        "settings_admin_only": "Nur Administratoren können /settings verwenden.",
        "where_open": "Wo soll das Einstellungsmenü geöffnet werden?",
        "open_here": "👥 Hier öffnen",
        "open_private": "👤 Im privaten Chat öffnen",
        "settings_closed": "Einstellungen geschlossen.",
        "lang_changed": "Fertig — ich werde hier jetzt Deutsch sprechen.",
        "user_lang_changed": "✅ Deine Sprache ist jetzt {lang}. Alle meine Nachrichten erscheinen in dieser Sprache.",
        "rules_updated": "✅ Regeln aktualisiert.",
        "rules_cleared": "✅ Regeln gelöscht.",
        "no_rules": "Keine Regeln gesetzt.",
        "perms_title": "🕹 Berechtigungen\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Berechtigungen für {user} gespeichert.",
        "perm_text": "Textnachrichten",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Sprachnachricht",
        "perm_file": "Datei",
        "perm_roundvideo": "Rundvideo",
        "perm_polls": "Umfragen",
        "perm_links": "Linkvorschau aktivieren",
        "perm_tag": "Eigenes Tag bearbeiten",
        "perm_save_btn": "Speichern ✓",
        "cancelled": "❌ Abgebrochen.",
        "done": "✅ Erledigt.",
        "error": "❌ Fehler: {msg}",
        "admins_only": "❌ Nur für Admins.",
        "reply_required": "❌ Antworte zuerst auf eine Nachricht.",
        "user_not_found": "❌ Nutzer nicht gefunden.",
        "invalid_args": "❌ Ungültige Argumente.",
    },
    "ru": {
        "warned": "{user} получил предупреждение {count}/{limit}.",
        "warn_reset": "Предупреждения {user} сброшены до 0.",
        "warn_limit": "{user} достиг лимита предупреждений {limit}. Что делать?",
        "warns_none": "У {user} нет предупреждений.",
        "muted": "{user} получил 🔇 mute.",
        "unmuted": "{user} больше не 🔇 в mute.",
        "banned": "{user} забанен 🚫.",
        "unbanned": "{user} разбанен.",
        "kicked": "{user} удалён из чата.",
        "no_target": "Ответь пользователю или укажи @username / user-id.",
        "not_admin": "❌ Только для администраторов.",
        "bot_no_perm": "❌ У меня нет нужных прав.",
        "self_target": "❌ К себе это применить нельзя.",
        "admin_target": "❌ Не могу действовать против другого админа.",
        "owner_target": "❌ Не могу действовать против владельца чата.",
        "cant_self": "❌ К себе это применить нельзя.",
        "cant_admin": "❌ Не могу действовать против другого админа.",
        "action_failed": "❌ Ошибка: {error}",
        "reason_label": "Причина: {reason}",
        "fed_only_owner": "❌ Только владелец федерации может это сделать.",
        "fed_not_found": "❌ Федерация не найдена.",
        "fed_created": "✅ Федерация '{name}' создана, id `{fid}`.",
        "fed_joined": "✅ Этот чат присоединился к федерации `{fid}`.",
        "fed_left": "✅ Этот чат покинул федерацию.",
        "fed_banned": "✅ {user} забанен в {n} чатах федерации. Причина: {reason}",
        "fed_unbanned": "✅ {user} удалён из бан-листа федерации.",
        "note_saved": "✅ Заметка `{name}` сохранена.",
        "note_cleared": "✅ Заметка `{name}` удалена.",
        "note_missing": "❌ Заметки `{name}` нет.",
        "notes_empty": "В этом чате нет заметок.",
        "filter_saved": "✅ Фильтр `{kw}` сохранён.",
        "filter_cleared": "✅ Фильтр `{kw}` удалён.",
        "filters_empty": "Здесь нет фильтров.",
        "lock_set": "🔒 `{type}` заблокирован.",
        "unlock_set": "🔓 `{type}` разблокирован.",
        "lock_unknown": "❌ Неизвестный тип блокировки. Попробуй /locktypes.",
        "bl_added": "✅ Добавлено в чёрный список: {word}",
        "bl_removed": "✅ Удалено из чёрного списка: {word}",
        "bl_empty": "Чёрный список пуст.",
        "disabled_set": "Команда `{cmd}` отключена.",
        "enabled_set": "Команда `{cmd}` включена.",
        "afk_on": "{user} теперь AFK. Причина: {reason}",
        "afk_back": "{user} вернулся. Был AFK {dur}.",
        "afk_mentioned": "{user} AFK ({dur}). Причина: {reason}",
        "connect_ok": "✅ Подключено к {title}.",
        "connect_off": "Отключено.",
        "connect_none": "Не подключено ни к одному чату.",
        "gban_ok": "✅ {user} забанен глобально.",
        "ungban_ok": "✅ {user} удалён из глобального бан-листа.",
        "welcome_default": "Добро пожаловать, {mention}, в {groupname}!",
        "goodbye_default": "Пока, {mention}!",
        "captcha_prompt": "👋 Добро пожаловать, {mention}! Реши: {a} + {b} = ?",
        "captcha_wrong": "❌ Неверно! Попробуй снова.",
        "captcha_correct": "✅ Верно! Добро пожаловать, {mention}!",
        "captcha_timeout": "⏰ {mention} не решил капчу и был удалён.",
        "settings_admin_only": "Только администраторы могут использовать /settings.",
        "where_open": "Где открыть меню настроек?",
        "open_here": "👥 Открыть здесь",
        "open_private": "👤 Открыть в личке",
        "settings_closed": "Настройки закрыты.",
        "lang_changed": "Готово — теперь я буду говорить по-русски здесь.",
        "user_lang_changed": "✅ Твой язык теперь {lang}. Все мои сообщения будут на этом языке.",
        "rules_updated": "✅ Правила обновлены.",
        "rules_cleared": "✅ Правила удалены.",
        "no_rules": "Правила не заданы.",
        "perms_title": "🕹 Права\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Права для {user} сохранены.",
        "perm_text": "Текстовые сообщения",
        "perm_photo": "Фото",
        "perm_video": "Видео",
        "perm_sticker": "Стикер/GIF",
        "perm_audio": "Аудио",
        "perm_voice": "Голосовое",
        "perm_file": "Файл",
        "perm_roundvideo": "Кружок",
        "perm_polls": "Опросы",
        "perm_links": "Включить превью ссылок",
        "perm_tag": "Изменить свой тег",
        "perm_save_btn": "Сохранить ✓",
        "cancelled": "❌ Отменено.",
        "done": "✅ Готово.",
        "error": "❌ Ошибка: {msg}",
        "admins_only": "❌ Только для администраторов.",
        "reply_required": "❌ Сначала ответь на сообщение.",
        "user_not_found": "❌ Пользователь не найден.",
        "invalid_args": "❌ Неверные аргументы.",
    },
    "zh": {
        "warned": "{user} 收到警告 {count}/{limit}。",
        "warn_reset": "{user} 的警告已清零。",
        "warn_limit": "{user} 已达警告上限 {limit}。如何处置？",
        "warns_none": "{user} 没有任何警告。",
        "muted": "{user} 已被 🔇 禁言。",
        "unmuted": "{user} 已解除 🔇 禁言。",
        "banned": "{user} 已被 🚫 封禁。",
        "unbanned": "{user} 已解除封禁。",
        "kicked": "{user} 已被踢出。",
        "no_target": "请回复某用户或提供 @username / 用户 ID。",
        "not_admin": "❌ 仅限管理员。",
        "bot_no_perm": "❌ 我没有相应的权限。",
        "self_target": "❌ 不能对自己使用。",
        "admin_target": "❌ 不能对其他管理员执行此操作。",
        "owner_target": "❌ 不能对群主执行此操作。",
        "cant_self": "❌ 不能对自己使用。",
        "cant_admin": "❌ 不能对其他管理员执行此操作。",
        "action_failed": "❌ 失败：{error}",
        "reason_label": "原因：{reason}",
        "fed_only_owner": "❌ 仅联邦所有者可以执行此操作。",
        "fed_not_found": "❌ 未找到联邦。",
        "fed_created": "✅ 联邦 '{name}' 已创建，ID `{fid}`。",
        "fed_joined": "✅ 此聊天已加入联邦 `{fid}`。",
        "fed_left": "✅ 此聊天已退出联邦。",
        "fed_banned": "✅ {user} 在 {n} 个聊天中被联邦封禁。原因：{reason}",
        "fed_unbanned": "✅ {user} 已从联邦封禁列表移除。",
        "note_saved": "✅ 笔记 `{name}` 已保存。",
        "note_cleared": "✅ 笔记 `{name}` 已删除。",
        "note_missing": "❌ 没有名为 `{name}` 的笔记。",
        "notes_empty": "此聊天没有笔记。",
        "filter_saved": "✅ 过滤器 `{kw}` 已保存。",
        "filter_cleared": "✅ 过滤器 `{kw}` 已删除。",
        "filters_empty": "此处未配置过滤器。",
        "lock_set": "🔒 已锁定 `{type}`。",
        "unlock_set": "🔓 已解锁 `{type}`。",
        "lock_unknown": "❌ 未知的锁定类型。试试 /locktypes。",
        "bl_added": "✅ 已加入黑名单：{word}",
        "bl_removed": "✅ 已从黑名单移除：{word}",
        "bl_empty": "黑名单为空。",
        "disabled_set": "已禁用命令 `{cmd}`。",
        "enabled_set": "已启用命令 `{cmd}`。",
        "afk_on": "{user} 现已 AFK。原因：{reason}",
        "afk_back": "{user} 已回来。AFK 时长 {dur}。",
        "afk_mentioned": "{user} 正在 AFK ({dur})。原因：{reason}",
        "connect_ok": "✅ 已连接到 {title}。",
        "connect_off": "已断开连接。",
        "connect_none": "未连接到任何聊天。",
        "gban_ok": "✅ 已全局封禁 {user}。",
        "ungban_ok": "✅ 已将 {user} 从全局封禁列表移除。",
        "welcome_default": "欢迎 {mention} 加入 {groupname}！",
        "goodbye_default": "再见 {mention}！",
        "captcha_prompt": "👋 欢迎 {mention}！请回答：{a} + {b} = ?",
        "captcha_wrong": "❌ 错误！请重试。",
        "captcha_correct": "✅ 正确！欢迎 {mention}！",
        "captcha_timeout": "⏰ {mention} 未通过验证已被移除。",
        "settings_admin_only": "只有管理员可以使用 /settings。",
        "where_open": "在哪里打开设置菜单？",
        "open_here": "👥 在此打开",
        "open_private": "👤 在私聊中打开",
        "settings_closed": "设置已关闭。",
        "lang_changed": "好的 — 我现在会在这里说中文。",
        "user_lang_changed": "✅ 你的语言已设为 {lang}。我所有的消息都会用这种语言显示。",
        "rules_updated": "✅ 规则已更新。",
        "rules_cleared": "✅ 规则已清除。",
        "no_rules": "未设置规则。",
        "perms_title": "🕹 权限\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} 的权限已保存。",
        "perm_text": "文本消息",
        "perm_photo": "图片",
        "perm_video": "视频",
        "perm_sticker": "贴纸/GIF",
        "perm_audio": "音频",
        "perm_voice": "语音",
        "perm_file": "文件",
        "perm_roundvideo": "圆视频",
        "perm_polls": "投票",
        "perm_links": "启用链接预览",
        "perm_tag": "编辑自己标签",
        "perm_save_btn": "保存 ✓",
        "cancelled": "❌ 已取消。",
        "done": "✅ 完成。",
        "error": "❌ 错误：{msg}",
        "admins_only": "❌ 仅限管理员。",
        "reply_required": "❌ 请先回复一条消息。",
        "user_not_found": "❌ 找不到该用户。",
        "invalid_args": "❌ 无效参数。",
    },
    "zt": {
        "warned": "{user} 收到警告 {count}/{limit}。",
        "warn_reset": "{user} 的警告已清零。",
        "warn_limit": "{user} 已達警告上限 {limit}。如何處置？",
        "warns_none": "{user} 沒有任何警告。",
        "muted": "{user} 已被 🔇 禁言。",
        "unmuted": "{user} 已解除 🔇 禁言。",
        "banned": "{user} 已被 🚫 封禁。",
        "unbanned": "{user} 已解除封禁。",
        "kicked": "{user} 已被踢出。",
        "no_target": "請回覆某用戶或提供 @username / 使用者 ID。",
        "not_admin": "❌ 僅限管理員。",
        "bot_no_perm": "❌ 我沒有相應的權限。",
        "self_target": "❌ 不能對自己使用。",
        "admin_target": "❌ 不能對其他管理員執行此操作。",
        "owner_target": "❌ 不能對群主執行此操作。",
        "cant_self": "❌ 不能對自己使用。",
        "cant_admin": "❌ 不能對其他管理員執行此操作。",
        "action_failed": "❌ 失敗：{error}",
        "reason_label": "原因：{reason}",
        "fed_only_owner": "❌ 僅聯邦所有者可以執行此操作。",
        "fed_not_found": "❌ 找不到聯邦。",
        "fed_created": "✅ 聯邦 '{name}' 已建立，ID `{fid}`。",
        "fed_joined": "✅ 此聊天已加入聯邦 `{fid}`。",
        "fed_left": "✅ 此聊天已退出聯邦。",
        "fed_banned": "✅ {user} 在 {n} 個聊天中被聯邦封禁。原因：{reason}",
        "fed_unbanned": "✅ {user} 已從聯邦封禁列表移除。",
        "note_saved": "✅ 筆記 `{name}` 已儲存。",
        "note_cleared": "✅ 筆記 `{name}` 已刪除。",
        "note_missing": "❌ 沒有名為 `{name}` 的筆記。",
        "notes_empty": "此聊天沒有筆記。",
        "filter_saved": "✅ 過濾器 `{kw}` 已儲存。",
        "filter_cleared": "✅ 過濾器 `{kw}` 已刪除。",
        "filters_empty": "此處未設定過濾器。",
        "lock_set": "🔒 已鎖定 `{type}`。",
        "unlock_set": "🔓 已解鎖 `{type}`。",
        "lock_unknown": "❌ 未知的鎖定類型。試試 /locktypes。",
        "bl_added": "✅ 已加入黑名單：{word}",
        "bl_removed": "✅ 已從黑名單移除：{word}",
        "bl_empty": "黑名單為空。",
        "disabled_set": "已停用指令 `{cmd}`。",
        "enabled_set": "已啟用指令 `{cmd}`。",
        "afk_on": "{user} 現已 AFK。原因：{reason}",
        "afk_back": "{user} 已回來。AFK 時長 {dur}。",
        "afk_mentioned": "{user} 正在 AFK ({dur})。原因：{reason}",
        "connect_ok": "✅ 已連線到 {title}。",
        "connect_off": "已斷開連線。",
        "connect_none": "未連線到任何聊天。",
        "gban_ok": "✅ 已全域封禁 {user}。",
        "ungban_ok": "✅ 已將 {user} 從全域封禁列表移除。",
        "welcome_default": "歡迎 {mention} 加入 {groupname}！",
        "goodbye_default": "再見 {mention}！",
        "captcha_prompt": "👋 歡迎 {mention}！請回答：{a} + {b} = ?",
        "captcha_wrong": "❌ 錯誤！請重試。",
        "captcha_correct": "✅ 正確！歡迎 {mention}！",
        "captcha_timeout": "⏰ {mention} 未通過驗證已被移除。",
        "settings_admin_only": "只有管理員可以使用 /settings。",
        "where_open": "在哪裡打開設定選單？",
        "open_here": "👥 在此打開",
        "open_private": "👤 在私聊中打開",
        "settings_closed": "設定已關閉。",
        "lang_changed": "好的 — 我現在會在這裡說繁體中文。",
        "user_lang_changed": "✅ 您的語言已設為 {lang}。所有訊息將以此語言顯示。",
        "rules_updated": "✅ 規則已更新。",
        "rules_cleared": "✅ 規則已清除。",
        "no_rules": "未設定規則。",
        "perms_title": "🕹 權限\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} 的權限已儲存。",
        "perm_text": "文字訊息",
        "perm_photo": "圖片",
        "perm_video": "影片",
        "perm_sticker": "貼圖/GIF",
        "perm_audio": "音訊",
        "perm_voice": "語音",
        "perm_file": "檔案",
        "perm_roundvideo": "圓形影片",
        "perm_polls": "投票",
        "perm_links": "啟用連結預覽",
        "perm_tag": "編輯自己的標籤",
        "perm_save_btn": "儲存 ✓",
        "cancelled": "❌ 已取消。",
        "done": "✅ 完成。",
        "error": "❌ 錯誤：{msg}",
        "admins_only": "❌ 僅限管理員。",
        "reply_required": "❌ 請先回覆一則訊息。",
        "user_not_found": "❌ 找不到該使用者。",
        "invalid_args": "❌ 無效參數。",
    },
    "pt": {
        "warned": "{user} recebeu aviso {count}/{limit}.",
        "warn_reset": "Avisos de {user} reiniciados para 0.",
        "warn_limit": "{user} atingiu o limite de avisos {limit}. O que fazer?",
        "warns_none": "{user} não tem avisos.",
        "muted": "{user} foi 🔇 silenciado.",
        "unmuted": "{user} já não está 🔇 silenciado.",
        "banned": "{user} foi 🚫 banido.",
        "unbanned": "{user} foi desbanido.",
        "kicked": "{user} foi expulso.",
        "no_target": "Responda a um utilizador ou passe @username / user-id.",
        "not_admin": "❌ Apenas administradores.",
        "bot_no_perm": "❌ Não tenho permissão para isto.",
        "self_target": "❌ Não podes fazer isso a ti próprio.",
        "admin_target": "❌ Não posso agir contra outro admin.",
        "owner_target": "❌ Não posso agir contra o dono do chat.",
        "cant_self": "❌ Não podes fazer isso a ti próprio.",
        "cant_admin": "❌ Não posso agir contra outro admin.",
        "action_failed": "❌ Falhou: {error}",
        "reason_label": "Motivo: {reason}",
        "fed_only_owner": "❌ Apenas o dono da federação pode fazer isto.",
        "fed_not_found": "❌ Federação não encontrada.",
        "fed_created": "✅ Federação '{name}' criada com id `{fid}`.",
        "fed_joined": "✅ Este chat juntou-se à federação `{fid}`.",
        "fed_left": "✅ Este chat saiu da federação.",
        "fed_banned": "✅ {user} fed-banido em {n} chats. Motivo: {reason}",
        "fed_unbanned": "✅ {user} removido da lista de banimentos da federação.",
        "note_saved": "✅ Nota `{name}` guardada.",
        "note_cleared": "✅ Nota `{name}` removida.",
        "note_missing": "❌ Não tenho nenhuma nota chamada `{name}`.",
        "notes_empty": "Sem notas neste chat.",
        "filter_saved": "✅ Filtro `{kw}` guardado.",
        "filter_cleared": "✅ Filtro `{kw}` removido.",
        "filters_empty": "Sem filtros configurados.",
        "lock_set": "🔒 `{type}` bloqueado.",
        "unlock_set": "🔓 `{type}` desbloqueado.",
        "lock_unknown": "❌ Tipo de bloqueio desconhecido. Tenta /locktypes.",
        "bl_added": "✅ Adicionado à lista negra: {word}",
        "bl_removed": "✅ Removido da lista negra: {word}",
        "bl_empty": "Lista negra vazia.",
        "disabled_set": "Comando `{cmd}` desativado.",
        "enabled_set": "Comando `{cmd}` ativado.",
        "afk_on": "{user} está AFK. Motivo: {reason}",
        "afk_back": "{user} voltou. Esteve AFK durante {dur}.",
        "afk_mentioned": "{user} está AFK ({dur}). Motivo: {reason}",
        "connect_ok": "✅ Ligado a {title}.",
        "connect_off": "Desligado.",
        "connect_none": "Não ligado a nenhum chat.",
        "gban_ok": "✅ {user} banido globalmente.",
        "ungban_ok": "✅ {user} removido da lista de banimentos globais.",
        "welcome_default": "Bem-vindo {mention} a {groupname}!",
        "goodbye_default": "Adeus {mention}!",
        "captcha_prompt": "👋 Bem-vindo {mention}! Resolve: {a} + {b} = ?",
        "captcha_wrong": "❌ Errado! Tenta de novo.",
        "captcha_correct": "✅ Correto! Bem-vindo {mention}!",
        "captcha_timeout": "⏰ {mention} não resolveu o captcha e foi removido.",
        "settings_admin_only": "Apenas administradores podem usar /settings.",
        "where_open": "Onde queres abrir o menu de definições?",
        "open_here": "👥 Abrir aqui",
        "open_private": "👤 Abrir em chat privado",
        "settings_closed": "Definições fechadas.",
        "lang_changed": "Pronto — agora vou falar em português aqui.",
        "user_lang_changed": "✅ A tua língua é agora {lang}. Todas as minhas mensagens aparecerão neste idioma.",
        "rules_updated": "✅ Regras atualizadas.",
        "rules_cleared": "✅ Regras apagadas.",
        "no_rules": "Sem regras definidas.",
        "perms_title": "🕹 Permissões\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Permissões guardadas para {user}.",
        "perm_text": "Mensagens de texto",
        "perm_photo": "Foto",
        "perm_video": "Vídeo",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Áudio",
        "perm_voice": "Voz",
        "perm_file": "Ficheiro",
        "perm_roundvideo": "Vídeo redondo",
        "perm_polls": "Sondagens",
        "perm_links": "Ativar pré-visualização de links",
        "perm_tag": "Editar a própria tag",
        "perm_save_btn": "Guardar ✓",
        "cancelled": "❌ Cancelado.",
        "done": "✅ Pronto.",
        "error": "❌ Erro: {msg}",
        "admins_only": "❌ Apenas administradores.",
        "reply_required": "❌ Responde primeiro a uma mensagem.",
        "user_not_found": "❌ Utilizador não encontrado.",
        "invalid_args": "❌ Argumentos inválidos.",
    },
    "id": {
        "warned": "{user} mendapat peringatan {count}/{limit}.",
        "warn_reset": "Peringatan {user} direset ke 0.",
        "warn_limit": "{user} mencapai batas peringatan {limit}. Apa yang harus dilakukan?",
        "warns_none": "{user} tidak punya peringatan.",
        "muted": "{user} telah 🔇 dibisukan.",
        "unmuted": "{user} tidak lagi 🔇 dibisukan.",
        "banned": "{user} telah 🚫 dibanned.",
        "unbanned": "{user} telah dibuka banned-nya.",
        "kicked": "{user} telah dikeluarkan.",
        "no_target": "Balas user atau berikan @username / user-id.",
        "not_admin": "❌ Hanya admin.",
        "bot_no_perm": "❌ Saya tidak punya izin.",
        "self_target": "❌ Tidak bisa pada diri sendiri.",
        "admin_target": "❌ Tidak bisa pada admin lain.",
        "owner_target": "❌ Tidak bisa pada pemilik chat.",
        "cant_self": "❌ Tidak bisa pada diri sendiri.",
        "cant_admin": "❌ Tidak bisa pada admin lain.",
        "action_failed": "❌ Gagal: {error}",
        "reason_label": "Alasan: {reason}",
        "fed_only_owner": "❌ Hanya pemilik federasi yang bisa melakukan ini.",
        "fed_not_found": "❌ Federasi tidak ditemukan.",
        "fed_created": "✅ Federasi '{name}' dibuat dengan id `{fid}`.",
        "fed_joined": "✅ Chat ini bergabung ke federasi `{fid}`.",
        "fed_left": "✅ Chat ini keluar dari federasi.",
        "fed_banned": "✅ {user} di-fedban di {n} chat. Alasan: {reason}",
        "fed_unbanned": "✅ {user} dihapus dari daftar fedban.",
        "note_saved": "✅ Catatan `{name}` tersimpan.",
        "note_cleared": "✅ Catatan `{name}` dihapus.",
        "note_missing": "❌ Tidak ada catatan bernama `{name}`.",
        "notes_empty": "Tidak ada catatan di chat ini.",
        "filter_saved": "✅ Filter `{kw}` tersimpan.",
        "filter_cleared": "✅ Filter `{kw}` dihapus.",
        "filters_empty": "Tidak ada filter di sini.",
        "lock_set": "🔒 `{type}` dikunci.",
        "unlock_set": "🔓 `{type}` dibuka.",
        "lock_unknown": "❌ Tipe lock tidak dikenal. Coba /locktypes.",
        "bl_added": "✅ Ditambahkan ke daftar hitam: {word}",
        "bl_removed": "✅ Dihapus dari daftar hitam: {word}",
        "bl_empty": "Daftar hitam kosong.",
        "disabled_set": "Perintah `{cmd}` dinonaktifkan.",
        "enabled_set": "Perintah `{cmd}` diaktifkan.",
        "afk_on": "{user} sekarang AFK. Alasan: {reason}",
        "afk_back": "{user} sudah kembali. Sempat AFK {dur}.",
        "afk_mentioned": "{user} sedang AFK ({dur}). Alasan: {reason}",
        "connect_ok": "✅ Terhubung ke {title}.",
        "connect_off": "Terputus.",
        "connect_none": "Tidak terhubung ke chat manapun.",
        "gban_ok": "✅ {user} di-banned secara global.",
        "ungban_ok": "✅ {user} dihapus dari daftar banned global.",
        "welcome_default": "Selamat datang {mention} di {groupname}!",
        "goodbye_default": "Selamat tinggal {mention}!",
        "captcha_prompt": "👋 Selamat datang {mention}! Selesaikan: {a} + {b} = ?",
        "captcha_wrong": "❌ Salah! Coba lagi.",
        "captcha_correct": "✅ Benar! Selamat datang {mention}!",
        "captcha_timeout": "⏰ {mention} tidak menyelesaikan captcha dan dikeluarkan.",
        "settings_admin_only": "Hanya admin yang dapat menggunakan /settings.",
        "where_open": "Di mana mau membuka menu pengaturan?",
        "open_here": "👥 Buka di sini",
        "open_private": "👤 Buka di chat pribadi",
        "settings_closed": "Pengaturan ditutup.",
        "lang_changed": "Beres — sekarang saya akan berbicara bahasa Indonesia di sini.",
        "user_lang_changed": "✅ Bahasamu sekarang {lang}. Semua pesanku akan tampil dalam bahasa ini.",
        "rules_updated": "✅ Aturan diperbarui.",
        "rules_cleared": "✅ Aturan dihapus.",
        "no_rules": "Belum ada aturan.",
        "perms_title": "🕹 Izin\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Izin untuk {user} tersimpan.",
        "perm_text": "Pesan teks",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Stiker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Voice",
        "perm_file": "File",
        "perm_roundvideo": "Video bulat",
        "perm_polls": "Polling",
        "perm_links": "Aktifkan pratinjau tautan",
        "perm_tag": "Edit tag sendiri",
        "perm_save_btn": "Simpan ✓",
        "cancelled": "❌ Dibatalkan.",
        "done": "✅ Selesai.",
        "error": "❌ Error: {msg}",
        "admins_only": "❌ Hanya admin.",
        "reply_required": "❌ Balas pesan dulu.",
        "user_not_found": "❌ Pengguna tidak ditemukan.",
        "invalid_args": "❌ Argumen tidak valid.",
    },
    "tr": {
        "warned": "{user} {count}/{limit} uyarı aldı.",
        "warn_reset": "{user} kullanıcısının uyarıları sıfırlandı.",
        "warn_limit": "{user} uyarı sınırı {limit}'e ulaştı. Ne yapalım?",
        "warns_none": "{user} hiç uyarı almamış.",
        "muted": "{user} 🔇 sessize alındı.",
        "unmuted": "{user} artık 🔇 sessizde değil.",
        "banned": "{user} 🚫 yasaklandı.",
        "unbanned": "{user} yasağı kaldırıldı.",
        "kicked": "{user} atıldı.",
        "no_target": "Bir kullanıcıya cevap ver veya @kullanici / id geç.",
        "not_admin": "❌ Sadece yöneticiler.",
        "bot_no_perm": "❌ Bunun için iznim yok.",
        "self_target": "❌ Bunu kendine yapamazsın.",
        "admin_target": "❌ Başka bir yöneticiye karşı yapamam.",
        "owner_target": "❌ Sohbet sahibine karşı yapamam.",
        "cant_self": "❌ Bunu kendine yapamazsın.",
        "cant_admin": "❌ Başka bir yöneticiye karşı yapamam.",
        "action_failed": "❌ Başarısız: {error}",
        "reason_label": "Sebep: {reason}",
        "fed_only_owner": "❌ Bunu yalnızca federasyon sahibi yapabilir.",
        "fed_not_found": "❌ Federasyon bulunamadı.",
        "fed_created": "✅ '{name}' federasyonu oluşturuldu. ID `{fid}`.",
        "fed_joined": "✅ Bu sohbet `{fid}` federasyonuna katıldı.",
        "fed_left": "✅ Bu sohbet federasyondan ayrıldı.",
        "fed_banned": "✅ {user} {n} sohbette fed-banlandı. Sebep: {reason}",
        "fed_unbanned": "✅ {user} federasyon ban listesinden çıkarıldı.",
        "note_saved": "✅ Not `{name}` kaydedildi.",
        "note_cleared": "✅ Not `{name}` silindi.",
        "note_missing": "❌ `{name}` adında bir not yok.",
        "notes_empty": "Bu sohbette not yok.",
        "filter_saved": "✅ Filtre `{kw}` kaydedildi.",
        "filter_cleared": "✅ Filtre `{kw}` silindi.",
        "filters_empty": "Burada filtre yok.",
        "lock_set": "🔒 `{type}` kilitlendi.",
        "unlock_set": "🔓 `{type}` kilidi açıldı.",
        "lock_unknown": "❌ Bilinmeyen kilit türü. /locktypes deneyin.",
        "bl_added": "✅ Kara listeye eklendi: {word}",
        "bl_removed": "✅ Kara listeden çıkarıldı: {word}",
        "bl_empty": "Kara liste boş.",
        "disabled_set": "`{cmd}` komutu devre dışı.",
        "enabled_set": "`{cmd}` komutu aktif.",
        "afk_on": "{user} artık AFK. Sebep: {reason}",
        "afk_back": "{user} döndü. {dur} boyunca AFK idi.",
        "afk_mentioned": "{user} AFK ({dur}). Sebep: {reason}",
        "connect_ok": "✅ {title} sohbetine bağlandı.",
        "connect_off": "Bağlantı kesildi.",
        "connect_none": "Hiçbir sohbete bağlı değil.",
        "gban_ok": "✅ {user} küresel olarak yasaklandı.",
        "ungban_ok": "✅ {user} küresel ban listesinden çıkarıldı.",
        "welcome_default": "Hoş geldin {mention}, {groupname} grubuna!",
        "goodbye_default": "Güle güle {mention}!",
        "captcha_prompt": "👋 Hoş geldin {mention}! Çöz: {a} + {b} = ?",
        "captcha_wrong": "❌ Yanlış! Tekrar dene.",
        "captcha_correct": "✅ Doğru! Hoş geldin {mention}!",
        "captcha_timeout": "⏰ {mention} captcha'yı çözemedi ve atıldı.",
        "settings_admin_only": "Yalnızca yöneticiler /settings komutunu kullanabilir.",
        "where_open": "Ayarlar menüsünü nerede açmak istiyorsun?",
        "open_here": "👥 Burada aç",
        "open_private": "👤 Özel sohbette aç",
        "settings_closed": "Ayarlar kapatıldı.",
        "lang_changed": "Tamam — burada artık Türkçe konuşacağım.",
        "user_lang_changed": "✅ Dilin artık {lang}. Tüm mesajlarım bu dilde görünecek.",
        "rules_updated": "✅ Kurallar güncellendi.",
        "rules_cleared": "✅ Kurallar temizlendi.",
        "no_rules": "Tanımlı kural yok.",
        "perms_title": "🕹 İzinler\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} için izinler kaydedildi.",
        "perm_text": "Metin mesajları",
        "perm_photo": "Fotoğraf",
        "perm_video": "Video",
        "perm_sticker": "Çıkartma/GIF",
        "perm_audio": "Ses dosyası",
        "perm_voice": "Sesli mesaj",
        "perm_file": "Dosya",
        "perm_roundvideo": "Yuvarlak video",
        "perm_polls": "Anketler",
        "perm_links": "Bağlantı önizlemeleri",
        "perm_tag": "Kendi etiketini düzenle",
        "perm_save_btn": "Kaydet ✓",
        "cancelled": "❌ İptal edildi.",
        "done": "✅ Tamam.",
        "error": "❌ Hata: {msg}",
        "admins_only": "❌ Sadece yöneticiler.",
        "reply_required": "❌ Önce bir mesaja cevap ver.",
        "user_not_found": "❌ Kullanıcı bulunamadı.",
        "invalid_args": "❌ Geçersiz argümanlar.",
    },
    "it": {
        "warned": "{user} ha ricevuto l'avviso {count}/{limit}.",
        "warn_reset": "Avvisi di {user} azzerati.",
        "warn_limit": "{user} ha raggiunto il limite di avvisi {limit}. Che si fa?",
        "warns_none": "{user} non ha avvisi.",
        "muted": "{user} è stato 🔇 silenziato.",
        "unmuted": "{user} non è più 🔇 silenziato.",
        "banned": "{user} è stato 🚫 bannato.",
        "unbanned": "{user} è stato sbannato.",
        "kicked": "{user} è stato espulso.",
        "no_target": "Rispondi a un utente o passa @username / id.",
        "not_admin": "❌ Solo amministratori.",
        "bot_no_perm": "❌ Non ho il permesso.",
        "self_target": "❌ Non puoi farlo su te stesso.",
        "admin_target": "❌ Non posso agire contro un altro admin.",
        "owner_target": "❌ Non posso agire contro il proprietario della chat.",
        "cant_self": "❌ Non puoi farlo su te stesso.",
        "cant_admin": "❌ Non posso agire contro un altro admin.",
        "action_failed": "❌ Errore: {error}",
        "reason_label": "Motivo: {reason}",
        "fed_only_owner": "❌ Solo il proprietario della federazione può farlo.",
        "fed_not_found": "❌ Federazione non trovata.",
        "fed_created": "✅ Federazione '{name}' creata con id `{fid}`.",
        "fed_joined": "✅ Questa chat è entrata nella federazione `{fid}`.",
        "fed_left": "✅ Questa chat ha lasciato la federazione.",
        "fed_banned": "✅ {user} fed-bannato in {n} chat. Motivo: {reason}",
        "fed_unbanned": "✅ {user} rimosso dalla lista bannati della federazione.",
        "note_saved": "✅ Nota `{name}` salvata.",
        "note_cleared": "✅ Nota `{name}` cancellata.",
        "note_missing": "❌ Non ho una nota chiamata `{name}`.",
        "notes_empty": "Nessuna nota in questa chat.",
        "filter_saved": "✅ Filtro `{kw}` salvato.",
        "filter_cleared": "✅ Filtro `{kw}` cancellato.",
        "filters_empty": "Nessun filtro configurato.",
        "lock_set": "🔒 `{type}` bloccato.",
        "unlock_set": "🔓 `{type}` sbloccato.",
        "lock_unknown": "❌ Tipo di blocco sconosciuto. Prova /locktypes.",
        "bl_added": "✅ Aggiunto alla lista nera: {word}",
        "bl_removed": "✅ Rimosso dalla lista nera: {word}",
        "bl_empty": "La lista nera è vuota.",
        "disabled_set": "Comando `{cmd}` disattivato.",
        "enabled_set": "Comando `{cmd}` attivato.",
        "afk_on": "{user} è ora AFK. Motivo: {reason}",
        "afk_back": "{user} è tornato. È stato AFK per {dur}.",
        "afk_mentioned": "{user} è AFK ({dur}). Motivo: {reason}",
        "connect_ok": "✅ Connesso a {title}.",
        "connect_off": "Disconnesso.",
        "connect_none": "Nessuna chat connessa.",
        "gban_ok": "✅ {user} bannato globalmente.",
        "ungban_ok": "✅ {user} rimosso dalla lista ban globale.",
        "welcome_default": "Benvenuto {mention} in {groupname}!",
        "goodbye_default": "Addio {mention}!",
        "captcha_prompt": "👋 Benvenuto {mention}! Risolvi: {a} + {b} = ?",
        "captcha_wrong": "❌ Sbagliato! Riprova.",
        "captcha_correct": "✅ Corretto! Benvenuto {mention}!",
        "captcha_timeout": "⏰ {mention} non ha risolto il captcha ed è stato rimosso.",
        "settings_admin_only": "Solo gli amministratori possono usare /settings.",
        "where_open": "Dove vuoi aprire il menu impostazioni?",
        "open_here": "👥 Apri qui",
        "open_private": "👤 Apri in chat privata",
        "settings_closed": "Impostazioni chiuse.",
        "lang_changed": "Fatto — ora parlerò in italiano qui.",
        "user_lang_changed": "✅ La tua lingua è ora {lang}. Tutti i miei messaggi saranno in questa lingua.",
        "rules_updated": "✅ Regole aggiornate.",
        "rules_cleared": "✅ Regole cancellate.",
        "no_rules": "Nessuna regola impostata.",
        "perms_title": "🕹 Permessi\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Permessi salvati per {user}.",
        "perm_text": "Messaggi di testo",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Voce",
        "perm_file": "File",
        "perm_roundvideo": "Videomessaggio",
        "perm_polls": "Sondaggi",
        "perm_links": "Abilita anteprime link",
        "perm_tag": "Modifica il proprio tag",
        "perm_save_btn": "Salva ✓",
        "cancelled": "❌ Annullato.",
        "done": "✅ Fatto.",
        "error": "❌ Errore: {msg}",
        "admins_only": "❌ Solo amministratori.",
        "reply_required": "❌ Rispondi prima a un messaggio.",
        "user_not_found": "❌ Utente non trovato.",
        "invalid_args": "❌ Argomenti non validi.",
    },
    "ro": {
        "warned": "{user} a primit avertismentul {count}/{limit}.",
        "warn_reset": "Avertismentele lui {user} resetate la 0.",
        "warn_limit": "{user} a atins limita de avertismente {limit}. Ce facem?",
        "warns_none": "{user} nu are avertismente.",
        "muted": "{user} a fost 🔇 silențiat.",
        "unmuted": "{user} nu mai este 🔇 silențiat.",
        "banned": "{user} a fost 🚫 banat.",
        "unbanned": "{user} a fost debanat.",
        "kicked": "{user} a fost dat afară.",
        "no_target": "Răspunde unui utilizator sau dă @username / id.",
        "not_admin": "❌ Doar administratorii.",
        "bot_no_perm": "❌ Nu am permisiunea.",
        "self_target": "❌ Nu poți face asta cu tine.",
        "admin_target": "❌ Nu pot acționa împotriva altui admin.",
        "owner_target": "❌ Nu pot acționa împotriva proprietarului chatului.",
        "cant_self": "❌ Nu poți face asta cu tine.",
        "cant_admin": "❌ Nu pot acționa împotriva altui admin.",
        "action_failed": "❌ Eșec: {error}",
        "reason_label": "Motiv: {reason}",
        "fed_only_owner": "❌ Doar proprietarul federației poate face asta.",
        "fed_not_found": "❌ Federația nu a fost găsită.",
        "fed_created": "✅ Federația '{name}' a fost creată cu id-ul `{fid}`.",
        "fed_joined": "✅ Acest chat s-a alăturat federației `{fid}`.",
        "fed_left": "✅ Acest chat a părăsit federația.",
        "fed_banned": "✅ {user} fed-banat în {n} chaturi. Motiv: {reason}",
        "fed_unbanned": "✅ {user} eliminat din lista federației.",
        "note_saved": "✅ Notița `{name}` salvată.",
        "note_cleared": "✅ Notița `{name}` ștearsă.",
        "note_missing": "❌ Nu am o notiță numită `{name}`.",
        "notes_empty": "Nicio notiță în acest chat.",
        "filter_saved": "✅ Filtrul `{kw}` salvat.",
        "filter_cleared": "✅ Filtrul `{kw}` șters.",
        "filters_empty": "Nu sunt filtre configurate.",
        "lock_set": "🔒 `{type}` blocat.",
        "unlock_set": "🔓 `{type}` deblocat.",
        "lock_unknown": "❌ Tip de blocaj necunoscut. Încearcă /locktypes.",
        "bl_added": "✅ Adăugat la lista neagră: {word}",
        "bl_removed": "✅ Eliminat din lista neagră: {word}",
        "bl_empty": "Lista neagră este goală.",
        "disabled_set": "Comanda `{cmd}` dezactivată.",
        "enabled_set": "Comanda `{cmd}` activată.",
        "afk_on": "{user} este acum AFK. Motiv: {reason}",
        "afk_back": "{user} s-a întors. A fost AFK {dur}.",
        "afk_mentioned": "{user} este AFK ({dur}). Motiv: {reason}",
        "connect_ok": "✅ Conectat la {title}.",
        "connect_off": "Deconectat.",
        "connect_none": "Neconectat la niciun chat.",
        "gban_ok": "✅ {user} banat global.",
        "ungban_ok": "✅ {user} eliminat din lista de ban global.",
        "welcome_default": "Bun venit {mention} în {groupname}!",
        "goodbye_default": "La revedere {mention}!",
        "captcha_prompt": "👋 Bun venit {mention}! Rezolvă: {a} + {b} = ?",
        "captcha_wrong": "❌ Greșit! Mai încearcă.",
        "captcha_correct": "✅ Corect! Bun venit {mention}!",
        "captcha_timeout": "⏰ {mention} nu a rezolvat captcha și a fost dat afară.",
        "settings_admin_only": "Doar administratorii pot folosi /settings.",
        "where_open": "Unde vrei să deschizi meniul setări?",
        "open_here": "👥 Deschide aici",
        "open_private": "👤 Deschide în privat",
        "settings_closed": "Setări închise.",
        "lang_changed": "Gata — acum voi vorbi în română aici.",
        "user_lang_changed": "✅ Limba ta este acum {lang}. Toate mesajele mele vor apărea în această limbă.",
        "rules_updated": "✅ Reguli actualizate.",
        "rules_cleared": "✅ Reguli șterse.",
        "no_rules": "Nicio regulă setată.",
        "perms_title": "🕹 Permisiuni\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Permisiuni salvate pentru {user}.",
        "perm_text": "Mesaje text",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Vocal",
        "perm_file": "Fișier",
        "perm_roundvideo": "Video rotund",
        "perm_polls": "Sondaje",
        "perm_links": "Activează previzualizarea linkurilor",
        "perm_tag": "Editează propria etichetă",
        "perm_save_btn": "Salvează ✓",
        "cancelled": "❌ Anulat.",
        "done": "✅ Gata.",
        "error": "❌ Eroare: {msg}",
        "admins_only": "❌ Doar administratori.",
        "reply_required": "❌ Răspunde mai întâi unui mesaj.",
        "user_not_found": "❌ Utilizator negăsit.",
        "invalid_args": "❌ Argumente invalide.",
    },
    "nl": {
        "warned": "{user} kreeg waarschuwing {count}/{limit}.",
        "warn_reset": "Waarschuwingen van {user} teruggezet naar 0.",
        "warn_limit": "{user} heeft de waarschuwingslimiet {limit} bereikt. Wat te doen?",
        "warns_none": "{user} heeft geen waarschuwingen.",
        "muted": "{user} is 🔇 gedempt.",
        "unmuted": "{user} is niet langer 🔇 gedempt.",
        "banned": "{user} is 🚫 verbannen.",
        "unbanned": "{user} is ontbannen.",
        "kicked": "{user} is uit de chat gezet.",
        "no_target": "Reageer op een gebruiker of geef @username / id.",
        "not_admin": "❌ Alleen voor admins.",
        "bot_no_perm": "❌ Ik heb hier geen rechten voor.",
        "self_target": "❌ Dat kan niet op jezelf.",
        "admin_target": "❌ Ik kan niet tegen een andere beheerder optreden.",
        "owner_target": "❌ Ik kan niet tegen de chat-eigenaar optreden.",
        "cant_self": "❌ Dat kan niet op jezelf.",
        "cant_admin": "❌ Ik kan niet tegen een andere admin optreden.",
        "action_failed": "❌ Mislukt: {error}",
        "reason_label": "Reden: {reason}",
        "fed_only_owner": "❌ Alleen de federatie-eigenaar kan dit doen.",
        "fed_not_found": "❌ Federatie niet gevonden.",
        "fed_created": "✅ Federatie '{name}' aangemaakt met id `{fid}`.",
        "fed_joined": "✅ Deze chat is lid geworden van federatie `{fid}`.",
        "fed_left": "✅ Deze chat heeft de federatie verlaten.",
        "fed_banned": "✅ {user} fed-banned in {n} chats. Reden: {reason}",
        "fed_unbanned": "✅ {user} verwijderd uit de federatie banlijst.",
        "note_saved": "✅ Notitie `{name}` opgeslagen.",
        "note_cleared": "✅ Notitie `{name}` verwijderd.",
        "note_missing": "❌ Geen notitie met de naam `{name}`.",
        "notes_empty": "Geen notities in deze chat.",
        "filter_saved": "✅ Filter `{kw}` opgeslagen.",
        "filter_cleared": "✅ Filter `{kw}` verwijderd.",
        "filters_empty": "Geen filters ingesteld.",
        "lock_set": "🔒 `{type}` vergrendeld.",
        "unlock_set": "🔓 `{type}` ontgrendeld.",
        "lock_unknown": "❌ Onbekend sloottype. Probeer /locktypes.",
        "bl_added": "✅ Toegevoegd aan de zwarte lijst: {word}",
        "bl_removed": "✅ Verwijderd uit de zwarte lijst: {word}",
        "bl_empty": "Zwarte lijst is leeg.",
        "disabled_set": "Commando `{cmd}` uitgeschakeld.",
        "enabled_set": "Commando `{cmd}` ingeschakeld.",
        "afk_on": "{user} is nu AFK. Reden: {reason}",
        "afk_back": "{user} is terug. Was AFK voor {dur}.",
        "afk_mentioned": "{user} is AFK ({dur}). Reden: {reason}",
        "connect_ok": "✅ Verbonden met {title}.",
        "connect_off": "Verbinding verbroken.",
        "connect_none": "Met geen chat verbonden.",
        "gban_ok": "✅ {user} globaal verbannen.",
        "ungban_ok": "✅ {user} verwijderd uit de globale banlijst.",
        "welcome_default": "Welkom {mention} bij {groupname}!",
        "goodbye_default": "Tot ziens {mention}!",
        "captcha_prompt": "👋 Welkom {mention}! Los op: {a} + {b} = ?",
        "captcha_wrong": "❌ Fout! Probeer opnieuw.",
        "captcha_correct": "✅ Goed! Welkom {mention}!",
        "captcha_timeout": "⏰ {mention} heeft de captcha niet opgelost en is verwijderd.",
        "settings_admin_only": "Alleen beheerders kunnen /settings gebruiken.",
        "where_open": "Waar wil je het instellingenmenu openen?",
        "open_here": "👥 Hier openen",
        "open_private": "👤 In privéchat openen",
        "settings_closed": "Instellingen gesloten.",
        "lang_changed": "Klaar — ik spreek hier nu Nederlands.",
        "user_lang_changed": "✅ Je taal is nu {lang}. Al mijn berichten verschijnen in deze taal.",
        "rules_updated": "✅ Regels bijgewerkt.",
        "rules_cleared": "✅ Regels gewist.",
        "no_rules": "Geen regels ingesteld.",
        "perms_title": "🕹 Rechten\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Rechten opgeslagen voor {user}.",
        "perm_text": "Tekstberichten",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Spraak",
        "perm_file": "Bestand",
        "perm_roundvideo": "Rondvideo",
        "perm_polls": "Polls",
        "perm_links": "Linkvoorbeelden inschakelen",
        "perm_tag": "Eigen tag bewerken",
        "perm_save_btn": "Opslaan ✓",
        "cancelled": "❌ Geannuleerd.",
        "done": "✅ Klaar.",
        "error": "❌ Fout: {msg}",
        "admins_only": "❌ Alleen voor beheerders.",
        "reply_required": "❌ Reageer eerst op een bericht.",
        "user_not_found": "❌ Gebruiker niet gevonden.",
        "invalid_args": "❌ Ongeldige argumenten.",
    },
    "uk": {
        "warned": "{user} отримав попередження {count}/{limit}.",
        "warn_reset": "Попередження для {user} скинуто до 0.",
        "warn_limit": "{user} досяг ліміту попереджень {limit}. Що робити?",
        "warns_none": "У {user} немає попереджень.",
        "muted": "{user} отримав 🔇 mute.",
        "unmuted": "{user} більше не в 🔇 mute.",
        "banned": "{user} забанений 🚫.",
        "unbanned": "{user} розбанений.",
        "kicked": "{user} вилучений з чату.",
        "no_target": "Дай відповідь користувачу або вкажи @username / id.",
        "not_admin": "❌ Лише для адміністраторів.",
        "bot_no_perm": "❌ У мене немає потрібних прав.",
        "self_target": "❌ До себе застосувати не можна.",
        "admin_target": "❌ Не можу діяти проти іншого адміна.",
        "owner_target": "❌ Не можу діяти проти власника чату.",
        "cant_self": "❌ До себе застосувати не можна.",
        "cant_admin": "❌ Не можу діяти проти іншого адміна.",
        "action_failed": "❌ Помилка: {error}",
        "reason_label": "Причина: {reason}",
        "fed_only_owner": "❌ Лише власник федерації може це зробити.",
        "fed_not_found": "❌ Федерацію не знайдено.",
        "fed_created": "✅ Федерацію '{name}' створено, id `{fid}`.",
        "fed_joined": "✅ Цей чат приєднався до федерації `{fid}`.",
        "fed_left": "✅ Цей чат покинув федерацію.",
        "fed_banned": "✅ {user} забанено у {n} чатах федерації. Причина: {reason}",
        "fed_unbanned": "✅ {user} вилучено зі списку банів федерації.",
        "note_saved": "✅ Нотатку `{name}` збережено.",
        "note_cleared": "✅ Нотатку `{name}` видалено.",
        "note_missing": "❌ Немає нотатки з назвою `{name}`.",
        "notes_empty": "У цьому чаті немає нотаток.",
        "filter_saved": "✅ Фільтр `{kw}` збережено.",
        "filter_cleared": "✅ Фільтр `{kw}` видалено.",
        "filters_empty": "Тут не налаштовано фільтрів.",
        "lock_set": "🔒 `{type}` заблоковано.",
        "unlock_set": "🔓 `{type}` розблоковано.",
        "lock_unknown": "❌ Невідомий тип блокування. Спробуй /locktypes.",
        "bl_added": "✅ Додано до чорного списку: {word}",
        "bl_removed": "✅ Прибрано з чорного списку: {word}",
        "bl_empty": "Чорний список порожній.",
        "disabled_set": "Команду `{cmd}` вимкнено.",
        "enabled_set": "Команду `{cmd}` увімкнено.",
        "afk_on": "{user} тепер AFK. Причина: {reason}",
        "afk_back": "{user} повернувся. Був AFK {dur}.",
        "afk_mentioned": "{user} AFK ({dur}). Причина: {reason}",
        "connect_ok": "✅ Підключено до {title}.",
        "connect_off": "Відключено.",
        "connect_none": "Не під'єднано до жодного чату.",
        "gban_ok": "✅ {user} забанено глобально.",
        "ungban_ok": "✅ {user} вилучено з глобального бан-списку.",
        "welcome_default": "Ласкаво просимо {mention} до {groupname}!",
        "goodbye_default": "До побачення, {mention}!",
        "captcha_prompt": "👋 Вітаємо {mention}! Розв'яжи: {a} + {b} = ?",
        "captcha_wrong": "❌ Неправильно! Спробуй ще.",
        "captcha_correct": "✅ Правильно! Вітаємо {mention}!",
        "captcha_timeout": "⏰ {mention} не розв'язав капчу і був вилучений.",
        "settings_admin_only": "Лише адміністратори можуть використовувати /settings.",
        "where_open": "Де відкрити меню налаштувань?",
        "open_here": "👥 Відкрити тут",
        "open_private": "👤 Відкрити в приватному чаті",
        "settings_closed": "Налаштування закрито.",
        "lang_changed": "Готово — тепер я говоритиму українською тут.",
        "user_lang_changed": "✅ Твоя мова — {lang}. Усі мої повідомлення будуть цією мовою.",
        "rules_updated": "✅ Правила оновлено.",
        "rules_cleared": "✅ Правила очищено.",
        "no_rules": "Правил не задано.",
        "perms_title": "🕹 Права\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Права для {user} збережено.",
        "perm_text": "Текстові повідомлення",
        "perm_photo": "Фото",
        "perm_video": "Відео",
        "perm_sticker": "Стікер/GIF",
        "perm_audio": "Аудіо",
        "perm_voice": "Голосове",
        "perm_file": "Файл",
        "perm_roundvideo": "Кругле відео",
        "perm_polls": "Опитування",
        "perm_links": "Увімкнути попередній перегляд посилань",
        "perm_tag": "Редагувати власний тег",
        "perm_save_btn": "Зберегти ✓",
        "cancelled": "❌ Скасовано.",
        "done": "✅ Готово.",
        "error": "❌ Помилка: {msg}",
        "admins_only": "❌ Лише для адміністраторів.",
        "reply_required": "❌ Спочатку відповідай на повідомлення.",
        "user_not_found": "❌ Користувача не знайдено.",
        "invalid_args": "❌ Неправильні аргументи.",
    },
    "fa": {
        "warned": "{user} اخطار {count}/{limit} گرفت.",
        "warn_reset": "اخطارهای {user} به ۰ بازنشانی شد.",
        "warn_limit": "{user} به سقف اخطار {limit} رسید. چه کار کنیم؟",
        "warns_none": "{user} هیچ اخطاری ندارد.",
        "muted": "{user} 🔇 ساکت شد.",
        "unmuted": "{user} دیگر 🔇 ساکت نیست.",
        "banned": "{user} 🚫 مسدود شد.",
        "unbanned": "{user} رفع مسدودیت شد.",
        "kicked": "{user} اخراج شد.",
        "no_target": "به یک کاربر پاسخ دهید یا @username / user-id بدهید.",
        "not_admin": "❌ فقط برای ادمین‌ها.",
        "bot_no_perm": "❌ من اجازهٔ این کار را ندارم.",
        "self_target": "❌ روی خودت قابل استفاده نیست.",
        "admin_target": "❌ نمی‌توانم علیه ادمین دیگر اقدام کنم.",
        "owner_target": "❌ نمی‌توانم علیه مالک گفتگو اقدام کنم.",
        "cant_self": "❌ روی خودت قابل استفاده نیست.",
        "cant_admin": "❌ نمی‌توانم علیه ادمین دیگر اقدام کنم.",
        "action_failed": "❌ ناموفق: {error}",
        "reason_label": "دلیل: {reason}",
        "fed_only_owner": "❌ فقط مالک فدراسیون می‌تواند این کار را انجام دهد.",
        "fed_not_found": "❌ فدراسیون پیدا نشد.",
        "fed_created": "✅ فدراسیون '{name}' با شناسهٔ `{fid}` ساخته شد.",
        "fed_joined": "✅ این گفتگو به فدراسیون `{fid}` پیوست.",
        "fed_left": "✅ این گفتگو از فدراسیون خارج شد.",
        "fed_banned": "✅ {user} در {n} گفتگو فد-بن شد. دلیل: {reason}",
        "fed_unbanned": "✅ {user} از لیست بن فدراسیون حذف شد.",
        "note_saved": "✅ یادداشت `{name}` ذخیره شد.",
        "note_cleared": "✅ یادداشت `{name}` حذف شد.",
        "note_missing": "❌ یادداشتی به نام `{name}` ندارم.",
        "notes_empty": "در این گفتگو یادداشتی نیست.",
        "filter_saved": "✅ فیلتر `{kw}` ذخیره شد.",
        "filter_cleared": "✅ فیلتر `{kw}` حذف شد.",
        "filters_empty": "هیچ فیلتری اینجا تنظیم نشده.",
        "lock_set": "🔒 `{type}` قفل شد.",
        "unlock_set": "🔓 `{type}` باز شد.",
        "lock_unknown": "❌ نوع قفل ناشناخته. /locktypes را امتحان کنید.",
        "bl_added": "✅ به فهرست سیاه افزوده شد: {word}",
        "bl_removed": "✅ از فهرست سیاه حذف شد: {word}",
        "bl_empty": "فهرست سیاه خالی است.",
        "disabled_set": "دستور `{cmd}` غیرفعال شد.",
        "enabled_set": "دستور `{cmd}` فعال شد.",
        "afk_on": "{user} اکنون AFK است. دلیل: {reason}",
        "afk_back": "{user} برگشت. به مدت {dur} AFK بود.",
        "afk_mentioned": "{user} AFK است ({dur}). دلیل: {reason}",
        "connect_ok": "✅ به {title} متصل شد.",
        "connect_off": "قطع شد.",
        "connect_none": "به هیچ چتی متصل نیست.",
        "gban_ok": "✅ {user} به‌صورت سراسری مسدود شد.",
        "ungban_ok": "✅ {user} از فهرست مسدودیت سراسری حذف شد.",
        "welcome_default": "خوش آمدی {mention} به {groupname}!",
        "goodbye_default": "بدرود {mention}!",
        "captcha_prompt": "👋 خوش آمدی {mention}! حل کن: {a} + {b} = ?",
        "captcha_wrong": "❌ نادرست! دوباره تلاش کن.",
        "captcha_correct": "✅ درست! خوش آمدی {mention}!",
        "captcha_timeout": "⏰ {mention} کپچا را حل نکرد و حذف شد.",
        "settings_admin_only": "فقط مدیران می‌توانند از /settings استفاده کنند.",
        "where_open": "منوی تنظیمات را کجا باز کنیم؟",
        "open_here": "👥 همین‌جا باز کن",
        "open_private": "👤 در پیام خصوصی باز کن",
        "settings_closed": "تنظیمات بسته شد.",
        "lang_changed": "انجام شد — اکنون اینجا به فارسی صحبت می‌کنم.",
        "user_lang_changed": "✅ زبان شما اکنون {lang} است. همهٔ پیام‌ها به این زبان نمایش داده می‌شوند.",
        "rules_updated": "✅ قوانین به‌روز شد.",
        "rules_cleared": "✅ قوانین پاک شد.",
        "no_rules": "هیچ قانونی تنظیم نشده.",
        "perms_title": "🕹 مجوزها\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ مجوزهای {user} ذخیره شد.",
        "perm_text": "پیام متنی",
        "perm_photo": "عکس",
        "perm_video": "ویدیو",
        "perm_sticker": "استیکر/GIF",
        "perm_audio": "صدا",
        "perm_voice": "ویس",
        "perm_file": "فایل",
        "perm_roundvideo": "ویدیوی گرد",
        "perm_polls": "نظرسنجی",
        "perm_links": "فعال‌سازی پیش‌نمایش لینک",
        "perm_tag": "ویرایش تگ خود",
        "perm_save_btn": "ذخیره ✓",
        "cancelled": "❌ لغو شد.",
        "done": "✅ انجام شد.",
        "error": "❌ خطا: {msg}",
        "admins_only": "❌ فقط برای ادمین‌ها.",
        "reply_required": "❌ ابتدا به یک پیام پاسخ بده.",
        "user_not_found": "❌ کاربر پیدا نشد.",
        "invalid_args": "❌ آرگومان‌های نامعتبر.",
    },
    "he": {
        "warned": "{user} קיבל אזהרה {count}/{limit}.",
        "warn_reset": "האזהרות של {user} אופסו ל-0.",
        "warn_limit": "{user} הגיע לגבול האזהרות {limit}. מה עושים?",
        "warns_none": "ל-{user} אין אזהרות.",
        "muted": "{user} 🔇 הושתק.",
        "unmuted": "{user} כבר לא 🔇 מושתק.",
        "banned": "{user} 🚫 הורחק.",
        "unbanned": "{user} שוחרר מהחסימה.",
        "kicked": "{user} הוסר מהקבוצה.",
        "no_target": "השב למשתמש או העבר @username / user-id.",
        "not_admin": "❌ רק למנהלים.",
        "bot_no_perm": "❌ אין לי הרשאה לכך.",
        "self_target": "❌ לא ניתן להשתמש בזה על עצמך.",
        "admin_target": "❌ לא ניתן לפעול נגד מנהל אחר.",
        "owner_target": "❌ לא ניתן לפעול נגד בעלי הצ'אט.",
        "cant_self": "❌ לא ניתן להשתמש בזה על עצמך.",
        "cant_admin": "❌ לא ניתן לפעול נגד מנהל אחר.",
        "action_failed": "❌ נכשל: {error}",
        "reason_label": "סיבה: {reason}",
        "fed_only_owner": "❌ רק בעל הפדרציה יכול לעשות זאת.",
        "fed_not_found": "❌ הפדרציה לא נמצאה.",
        "fed_created": "✅ הפדרציה '{name}' נוצרה עם המזהה `{fid}`.",
        "fed_joined": "✅ הצ'אט הצטרף לפדרציה `{fid}`.",
        "fed_left": "✅ הצ'אט עזב את הפדרציה.",
        "fed_banned": "✅ {user} נחסם פדרטיבית ב-{n} צ'אטים. סיבה: {reason}",
        "fed_unbanned": "✅ {user} הוסר מרשימת חסומי הפדרציה.",
        "note_saved": "✅ הפתק `{name}` נשמר.",
        "note_cleared": "✅ הפתק `{name}` נמחק.",
        "note_missing": "❌ אין לי פתק בשם `{name}`.",
        "notes_empty": "אין פתקים בצ'אט זה.",
        "filter_saved": "✅ המסנן `{kw}` נשמר.",
        "filter_cleared": "✅ המסנן `{kw}` נמחק.",
        "filters_empty": "אין מסננים מוגדרים.",
        "lock_set": "🔒 `{type}` ננעל.",
        "unlock_set": "🔓 `{type}` נפתח.",
        "lock_unknown": "❌ סוג נעילה לא ידוע. נסה /locktypes.",
        "bl_added": "✅ נוסף לרשימה השחורה: {word}",
        "bl_removed": "✅ הוסר מהרשימה השחורה: {word}",
        "bl_empty": "הרשימה השחורה ריקה.",
        "disabled_set": "הפקודה `{cmd}` הושבתה.",
        "enabled_set": "הפקודה `{cmd}` הופעלה.",
        "afk_on": "{user} ב-AFK עכשיו. סיבה: {reason}",
        "afk_back": "{user} חזר. היה ב-AFK {dur}.",
        "afk_mentioned": "{user} ב-AFK ({dur}). סיבה: {reason}",
        "connect_ok": "✅ מחובר ל-{title}.",
        "connect_off": "מנותק.",
        "connect_none": "לא מחובר לאף צ'אט.",
        "gban_ok": "✅ {user} נחסם גלובלית.",
        "ungban_ok": "✅ {user} הוסר מרשימת החסומים הגלובלית.",
        "welcome_default": "ברוך הבא {mention} ל-{groupname}!",
        "goodbye_default": "להתראות {mention}!",
        "captcha_prompt": "👋 ברוך הבא {mention}! פתור: {a} + {b} = ?",
        "captcha_wrong": "❌ שגוי! נסה שוב.",
        "captcha_correct": "✅ נכון! ברוך הבא {mention}!",
        "captcha_timeout": "⏰ {mention} לא פתר את הקפצ'ה והוסר.",
        "settings_admin_only": "רק מנהלים יכולים להשתמש ב-/settings.",
        "where_open": "איפה לפתוח את תפריט ההגדרות?",
        "open_here": "👥 פתח כאן",
        "open_private": "👤 פתח בצ'אט פרטי",
        "settings_closed": "ההגדרות נסגרו.",
        "lang_changed": "סיום — אדבר כעת בעברית כאן.",
        "user_lang_changed": "✅ השפה שלך כעת {lang}. כל ההודעות יופיעו בשפה זו.",
        "rules_updated": "✅ הכללים עודכנו.",
        "rules_cleared": "✅ הכללים נמחקו.",
        "no_rules": "לא הוגדרו כללים.",
        "perms_title": "🕹 הרשאות\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ ההרשאות של {user} נשמרו.",
        "perm_text": "הודעות טקסט",
        "perm_photo": "תמונה",
        "perm_video": "וידאו",
        "perm_sticker": "מדבקה/GIF",
        "perm_audio": "אודיו",
        "perm_voice": "הודעה קולית",
        "perm_file": "קובץ",
        "perm_roundvideo": "וידאו עגול",
        "perm_polls": "סקרים",
        "perm_links": "הפעל תצוגת קישורים",
        "perm_tag": "ערוך תג אישי",
        "perm_save_btn": "שמור ✓",
        "cancelled": "❌ בוטל.",
        "done": "✅ בוצע.",
        "error": "❌ שגיאה: {msg}",
        "admins_only": "❌ רק למנהלים.",
        "reply_required": "❌ השב להודעה תחילה.",
        "user_not_found": "❌ המשתמש לא נמצא.",
        "invalid_args": "❌ ארגומנטים לא חוקיים.",
    },
    "ko": {
        "warned": "{user} 경고 받음 {count}/{limit}.",
        "warn_reset": "{user}의 경고가 0으로 초기화되었습니다.",
        "warn_limit": "{user}이(가) 경고 한도 {limit}에 도달했습니다. 어떻게 할까요?",
        "warns_none": "{user}에게 경고가 없습니다.",
        "muted": "{user} 🔇 음소거됨.",
        "unmuted": "{user} 🔇 음소거 해제됨.",
        "banned": "{user} 🚫 차단됨.",
        "unbanned": "{user} 차단 해제됨.",
        "kicked": "{user} 강퇴됨.",
        "no_target": "사용자에게 답장하거나 @username / 사용자 ID를 입력하세요.",
        "not_admin": "❌ 관리자 전용입니다.",
        "bot_no_perm": "❌ 권한이 없습니다.",
        "self_target": "❌ 자기 자신에게는 사용할 수 없습니다.",
        "admin_target": "❌ 다른 관리자에게는 사용할 수 없습니다.",
        "owner_target": "❌ 채팅 소유자에게는 사용할 수 없습니다.",
        "cant_self": "❌ 자기 자신에게는 사용할 수 없습니다.",
        "cant_admin": "❌ 다른 관리자에게는 사용할 수 없습니다.",
        "action_failed": "❌ 실패: {error}",
        "reason_label": "사유: {reason}",
        "fed_only_owner": "❌ 페더레이션 소유자만 가능합니다.",
        "fed_not_found": "❌ 페더레이션을 찾을 수 없습니다.",
        "fed_created": "✅ 페더레이션 '{name}' 생성됨, ID `{fid}`.",
        "fed_joined": "✅ 이 채팅이 페더레이션 `{fid}`에 참여했습니다.",
        "fed_left": "✅ 이 채팅이 페더레이션을 떠났습니다.",
        "fed_banned": "✅ {user} {n}개 채팅에서 페더 차단됨. 사유: {reason}",
        "fed_unbanned": "✅ {user} 페더레이션 차단 목록에서 제거됨.",
        "note_saved": "✅ 메모 `{name}` 저장됨.",
        "note_cleared": "✅ 메모 `{name}` 삭제됨.",
        "note_missing": "❌ `{name}`이라는 메모가 없습니다.",
        "notes_empty": "이 채팅에 메모가 없습니다.",
        "filter_saved": "✅ 필터 `{kw}` 저장됨.",
        "filter_cleared": "✅ 필터 `{kw}` 삭제됨.",
        "filters_empty": "여기에는 필터가 없습니다.",
        "lock_set": "🔒 `{type}` 잠금됨.",
        "unlock_set": "🔓 `{type}` 잠금 해제됨.",
        "lock_unknown": "❌ 알 수 없는 잠금 유형입니다. /locktypes를 시도하세요.",
        "bl_added": "✅ 차단 목록에 추가됨: {word}",
        "bl_removed": "✅ 차단 목록에서 제거됨: {word}",
        "bl_empty": "차단 목록이 비어 있습니다.",
        "disabled_set": "명령 `{cmd}` 비활성화됨.",
        "enabled_set": "명령 `{cmd}` 활성화됨.",
        "afk_on": "{user} 자리비움 상태입니다. 사유: {reason}",
        "afk_back": "{user} 돌아왔습니다. AFK 시간 {dur}.",
        "afk_mentioned": "{user} AFK 중 ({dur}). 사유: {reason}",
        "connect_ok": "✅ {title}에 연결되었습니다.",
        "connect_off": "연결 해제됨.",
        "connect_none": "연결된 채팅이 없습니다.",
        "gban_ok": "✅ {user} 글로벌 차단됨.",
        "ungban_ok": "✅ {user} 글로벌 차단 목록에서 제거됨.",
        "welcome_default": "{groupname}에 오신 {mention}님 환영합니다!",
        "goodbye_default": "잘 가요 {mention}!",
        "captcha_prompt": "👋 환영합니다 {mention}! 풀어보세요: {a} + {b} = ?",
        "captcha_wrong": "❌ 틀렸습니다! 다시 시도하세요.",
        "captcha_correct": "✅ 정답! 환영합니다 {mention}!",
        "captcha_timeout": "⏰ {mention}님이 캡차를 풀지 못해 제거되었습니다.",
        "settings_admin_only": "관리자만 /settings를 사용할 수 있습니다.",
        "where_open": "설정 메뉴를 어디서 열까요?",
        "open_here": "👥 여기에서 열기",
        "open_private": "👤 개인 채팅에서 열기",
        "settings_closed": "설정이 닫혔습니다.",
        "lang_changed": "완료 — 이제 여기서 한국어로 말합니다.",
        "user_lang_changed": "✅ 언어가 {lang}로 설정되었습니다. 모든 메시지가 이 언어로 표시됩니다.",
        "rules_updated": "✅ 규칙이 업데이트되었습니다.",
        "rules_cleared": "✅ 규칙이 삭제되었습니다.",
        "no_rules": "규칙이 설정되지 않았습니다.",
        "perms_title": "🕹 권한\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user}의 권한이 저장됨.",
        "perm_text": "텍스트 메시지",
        "perm_photo": "사진",
        "perm_video": "비디오",
        "perm_sticker": "스티커/GIF",
        "perm_audio": "오디오",
        "perm_voice": "음성",
        "perm_file": "파일",
        "perm_roundvideo": "원형 비디오",
        "perm_polls": "투표",
        "perm_links": "링크 미리보기 활성화",
        "perm_tag": "자기 태그 편집",
        "perm_save_btn": "저장 ✓",
        "cancelled": "❌ 취소됨.",
        "done": "✅ 완료.",
        "error": "❌ 오류: {msg}",
        "admins_only": "❌ 관리자 전용.",
        "reply_required": "❌ 먼저 메시지에 답장하세요.",
        "user_not_found": "❌ 사용자를 찾을 수 없습니다.",
        "invalid_args": "❌ 잘못된 인자입니다.",
    },
    "el": {
        "warned": "{user} έλαβε προειδοποίηση {count}/{limit}.",
        "warn_reset": "Οι προειδοποιήσεις του {user} μηδενίστηκαν.",
        "warn_limit": "{user} έφτασε το όριο προειδοποιήσεων {limit}. Τι κάνουμε;",
        "warns_none": "Ο {user} δεν έχει προειδοποιήσεις.",
        "muted": "{user} έγινε 🔇 σίγαση.",
        "unmuted": "{user} δεν είναι πλέον σε 🔇 σίγαση.",
        "banned": "{user} 🚫 αποκλείστηκε.",
        "unbanned": "{user} άρθηκε ο αποκλεισμός.",
        "kicked": "{user} αποβλήθηκε.",
        "no_target": "Απάντησε σε χρήστη ή δώσε @username / user-id.",
        "not_admin": "❌ Μόνο για διαχειριστές.",
        "bot_no_perm": "❌ Δεν έχω δικαίωμα.",
        "self_target": "❌ Δεν μπορείς στον εαυτό σου.",
        "admin_target": "❌ Δεν μπορώ ενάντια σε άλλο διαχειριστή.",
        "owner_target": "❌ Δεν μπορώ ενάντια στον ιδιοκτήτη της συνομιλίας.",
        "cant_self": "❌ Δεν μπορείς στον εαυτό σου.",
        "cant_admin": "❌ Δεν μπορώ ενάντια σε άλλο διαχειριστή.",
        "action_failed": "❌ Αποτυχία: {error}",
        "reason_label": "Λόγος: {reason}",
        "fed_only_owner": "❌ Μόνο ο ιδιοκτήτης της ομοσπονδίας μπορεί.",
        "fed_not_found": "❌ Η ομοσπονδία δεν βρέθηκε.",
        "fed_created": "✅ Δημιουργήθηκε η ομοσπονδία '{name}' με id `{fid}`.",
        "fed_joined": "✅ Αυτή η συνομιλία μπήκε στην ομοσπονδία `{fid}`.",
        "fed_left": "✅ Αυτή η συνομιλία έφυγε από την ομοσπονδία.",
        "fed_banned": "✅ Ο {user} αποκλείστηκε σε {n} συνομιλίες. Λόγος: {reason}",
        "fed_unbanned": "✅ Ο {user} αφαιρέθηκε από τη λίστα αποκλεισμών.",
        "note_saved": "✅ Η σημείωση `{name}` αποθηκεύτηκε.",
        "note_cleared": "✅ Η σημείωση `{name}` διαγράφηκε.",
        "note_missing": "❌ Δεν υπάρχει σημείωση με όνομα `{name}`.",
        "notes_empty": "Δεν υπάρχουν σημειώσεις σε αυτή τη συνομιλία.",
        "filter_saved": "✅ Το φίλτρο `{kw}` αποθηκεύτηκε.",
        "filter_cleared": "✅ Το φίλτρο `{kw}` διαγράφηκε.",
        "filters_empty": "Δεν υπάρχουν φίλτρα εδώ.",
        "lock_set": "🔒 Κλειδώθηκε `{type}`.",
        "unlock_set": "🔓 Ξεκλειδώθηκε `{type}`.",
        "lock_unknown": "❌ Άγνωστος τύπος κλειδώματος. Δοκίμασε /locktypes.",
        "bl_added": "✅ Προστέθηκε στη μαύρη λίστα: {word}",
        "bl_removed": "✅ Αφαιρέθηκε από τη μαύρη λίστα: {word}",
        "bl_empty": "Η μαύρη λίστα είναι κενή.",
        "disabled_set": "Η εντολή `{cmd}` απενεργοποιήθηκε.",
        "enabled_set": "Η εντολή `{cmd}` ενεργοποιήθηκε.",
        "afk_on": "{user} είναι τώρα AFK. Λόγος: {reason}",
        "afk_back": "{user} επέστρεψε. Ήταν AFK για {dur}.",
        "afk_mentioned": "{user} είναι AFK ({dur}). Λόγος: {reason}",
        "connect_ok": "✅ Συνδέθηκε στο {title}.",
        "connect_off": "Αποσυνδέθηκε.",
        "connect_none": "Δεν είναι συνδεδεμένο σε καμία συνομιλία.",
        "gban_ok": "✅ Ο {user} αποκλείστηκε καθολικά.",
        "ungban_ok": "✅ Ο {user} αφαιρέθηκε από την καθολική λίστα αποκλεισμών.",
        "welcome_default": "Καλώς ήρθες {mention} στο {groupname}!",
        "goodbye_default": "Γεια σου {mention}!",
        "captcha_prompt": "👋 Καλώς ήρθες {mention}! Λύσε: {a} + {b} = ?",
        "captcha_wrong": "❌ Λάθος! Δοκίμασε ξανά.",
        "captcha_correct": "✅ Σωστά! Καλώς ήρθες {mention}!",
        "captcha_timeout": "⏰ Ο {mention} δεν έλυσε το captcha και αφαιρέθηκε.",
        "settings_admin_only": "Μόνο διαχειριστές μπορούν να χρησιμοποιήσουν /settings.",
        "where_open": "Πού να ανοίξουμε το μενού ρυθμίσεων;",
        "open_here": "👥 Άνοιξε εδώ",
        "open_private": "👤 Άνοιξε σε ιδιωτική συνομιλία",
        "settings_closed": "Οι ρυθμίσεις έκλεισαν.",
        "lang_changed": "Έτοιμο — θα μιλάω εδώ στα Ελληνικά.",
        "user_lang_changed": "✅ Η γλώσσα σου είναι {lang}. Όλα τα μηνύματα θα εμφανίζονται σε αυτή τη γλώσσα.",
        "rules_updated": "✅ Οι κανόνες ενημερώθηκαν.",
        "rules_cleared": "✅ Οι κανόνες διαγράφηκαν.",
        "no_rules": "Δεν έχουν οριστεί κανόνες.",
        "perms_title": "🕹 Δικαιώματα\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Οι άδειες για {user} αποθηκεύτηκαν.",
        "perm_text": "Μηνύματα κειμένου",
        "perm_photo": "Φωτογραφία",
        "perm_video": "Βίντεο",
        "perm_sticker": "Αυτοκόλλητο/GIF",
        "perm_audio": "Ήχος",
        "perm_voice": "Φωνητικό",
        "perm_file": "Αρχείο",
        "perm_roundvideo": "Στρογγυλό βίντεο",
        "perm_polls": "Δημοσκοπήσεις",
        "perm_links": "Ενεργοποίηση προεπισκόπησης συνδέσμων",
        "perm_tag": "Επεξεργασία ετικέτας",
        "perm_save_btn": "Αποθήκευση ✓",
        "cancelled": "❌ Ακυρώθηκε.",
        "done": "✅ Έτοιμο.",
        "error": "❌ Σφάλμα: {msg}",
        "admins_only": "❌ Μόνο διαχειριστές.",
        "reply_required": "❌ Απάντησε πρώτα σε ένα μήνυμα.",
        "user_not_found": "❌ Χρήστης δεν βρέθηκε.",
        "invalid_args": "❌ Μη έγκυρα ορίσματα.",
    },
    "kk": {
        "warned": "{user} ескерту алды {count}/{limit}.",
        "warn_reset": "{user} ескертулері 0-ге қайтарылды.",
        "warn_limit": "{user} ескерту шегіне жетті {limit}. Не істейміз?",
        "warns_none": "{user} ескертусіз.",
        "muted": "{user} 🔇 үнсіздендірілді.",
        "unmuted": "{user} енді 🔇 үнсіз емес.",
        "banned": "{user} 🚫 бұғатталды.",
        "unbanned": "{user} бұғаттан босатылды.",
        "kicked": "{user} шығарылды.",
        "no_target": "Қолданушыға жауап бер немесе @username/user-id жібер.",
        "not_admin": "❌ Тек әкімшілерге.",
        "bot_no_perm": "❌ Менде бұл әрекетке құқық жоқ.",
        "self_target": "❌ Өзіңе қолдана алмайсың.",
        "admin_target": "❌ Басқа әкімшіге қарсы әрекет ете алмаймын.",
        "owner_target": "❌ Чат иесіне қарсы әрекет ете алмаймын.",
        "cant_self": "❌ Өзіңе қолдана алмайсың.",
        "cant_admin": "❌ Басқа әкімшіге қарсы әрекет ете алмаймын.",
        "action_failed": "❌ Сәтсіз: {error}",
        "reason_label": "Себеп: {reason}",
        "fed_only_owner": "❌ Тек федерация иесі бұны жасай алады.",
        "fed_not_found": "❌ Федерация табылмады.",
        "fed_created": "✅ '{name}' федерациясы жасалды, id `{fid}`.",
        "fed_joined": "✅ Бұл чат `{fid}` федерациясына қосылды.",
        "fed_left": "✅ Бұл чат федерациядан шықты.",
        "fed_banned": "✅ {user} {n} чатта федерациядан бұғатталды. Себеп: {reason}",
        "fed_unbanned": "✅ {user} федерация бұғат тізімінен шығарылды.",
        "note_saved": "✅ `{name}` жазбасы сақталды.",
        "note_cleared": "✅ `{name}` жазбасы өшірілді.",
        "note_missing": "❌ `{name}` атты жазба жоқ.",
        "notes_empty": "Бұл чатта жазбалар жоқ.",
        "filter_saved": "✅ `{kw}` сүзгісі сақталды.",
        "filter_cleared": "✅ `{kw}` сүзгісі өшірілді.",
        "filters_empty": "Мұнда сүзгілер жоқ.",
        "lock_set": "🔒 `{type}` бұғатталды.",
        "unlock_set": "🔓 `{type}` ашылды.",
        "lock_unknown": "❌ Белгісіз бұғат түрі. /locktypes қолданып көр.",
        "bl_added": "✅ Қара тізімге қосылды: {word}",
        "bl_removed": "✅ Қара тізімнен алынды: {word}",
        "bl_empty": "Қара тізім бос.",
        "disabled_set": "`{cmd}` командасы өшірілді.",
        "enabled_set": "`{cmd}` командасы қосылды.",
        "afk_on": "{user} енді AFK. Себеп: {reason}",
        "afk_back": "{user} оралды. {dur} AFK болды.",
        "afk_mentioned": "{user} AFK ({dur}). Себеп: {reason}",
        "connect_ok": "✅ {title} чатына қосылды.",
        "connect_off": "Ажыратылды.",
        "connect_none": "Ешбір чатқа қосылмаған.",
        "gban_ok": "✅ {user} ғаламдық бұғатталды.",
        "ungban_ok": "✅ {user} ғаламдық бұғат тізімінен алынды.",
        "welcome_default": "{groupname}-ке қош келдің {mention}!",
        "goodbye_default": "Сау бол {mention}!",
        "captcha_prompt": "👋 Қош келдің {mention}! Шеш: {a} + {b} = ?",
        "captcha_wrong": "❌ Қате! Қайта көр.",
        "captcha_correct": "✅ Дұрыс! Қош келдің {mention}!",
        "captcha_timeout": "⏰ {mention} капчаны шешпеді және шығарылды.",
        "settings_admin_only": "Тек әкімшілер /settings қолдана алады.",
        "where_open": "Параметрлер мәзірін қайдан ашамыз?",
        "open_here": "👥 Осы жерде ашу",
        "open_private": "👤 Жеке чатта ашу",
        "settings_closed": "Параметрлер жабылды.",
        "lang_changed": "Дайын — енді мен осы жерде қазақша сөйлеймін.",
        "user_lang_changed": "✅ Сенің тілің енді {lang}. Барлық хабарламалар осы тілде болады.",
        "rules_updated": "✅ Ережелер жаңартылды.",
        "rules_cleared": "✅ Ережелер өшірілді.",
        "no_rules": "Ережелер жоқ.",
        "perms_title": "🕹 Рұқсаттар\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} үшін рұқсаттар сақталды.",
        "perm_text": "Мәтіндік хабарлар",
        "perm_photo": "Фото",
        "perm_video": "Видео",
        "perm_sticker": "Стикер/GIF",
        "perm_audio": "Аудио",
        "perm_voice": "Дыбыстық хабар",
        "perm_file": "Файл",
        "perm_roundvideo": "Дөңгелек видео",
        "perm_polls": "Сауалнамалар",
        "perm_links": "Сілтеме алдын ала көру",
        "perm_tag": "Өз тегін өзгерту",
        "perm_save_btn": "Сақтау ✓",
        "cancelled": "❌ Болдырылмады.",
        "done": "✅ Дайын.",
        "error": "❌ Қате: {msg}",
        "admins_only": "❌ Тек әкімшілерге.",
        "reply_required": "❌ Алдымен хабарламаға жауап бер.",
        "user_not_found": "❌ Қолданушы табылмады.",
        "invalid_args": "❌ Жарамсыз аргументтер.",
    },
    "uz": {
        "warned": "{user} ogohlantirish oldi {count}/{limit}.",
        "warn_reset": "{user} ogohlantirishlari 0 ga tushirildi.",
        "warn_limit": "{user} ogohlantirish chegarasiga {limit} yetdi. Nima qilamiz?",
        "warns_none": "{user} da ogohlantirish yo‘q.",
        "muted": "{user} 🔇 ovozsiz qilindi.",
        "unmuted": "{user} endi 🔇 ovozsiz emas.",
        "banned": "{user} 🚫 bloklandi.",
        "unbanned": "{user} blokdan chiqarildi.",
        "kicked": "{user} chiqarib yuborildi.",
        "no_target": "Foydalanuvchiga javob ber yoki @username/user-id yubor.",
        "not_admin": "❌ Faqat adminlar uchun.",
        "bot_no_perm": "❌ Bu amalni bajarish uchun ruxsatim yo‘q.",
        "self_target": "❌ Buni o‘zingga qo‘llab bo‘lmaydi.",
        "admin_target": "❌ Boshqa adminga qarshi harakat qila olmayman.",
        "owner_target": "❌ Chat egasiga qarshi harakat qila olmayman.",
        "cant_self": "❌ Buni o‘zingga qo‘llab bo‘lmaydi.",
        "cant_admin": "❌ Boshqa adminga qarshi harakat qila olmayman.",
        "action_failed": "❌ Bajarilmadi: {error}",
        "reason_label": "Sabab: {reason}",
        "fed_only_owner": "❌ Faqat federatsiya egasi bajara oladi.",
        "fed_not_found": "❌ Federatsiya topilmadi.",
        "fed_created": "✅ '{name}' federatsiyasi yaratildi, id `{fid}`.",
        "fed_joined": "✅ Bu chat `{fid}` federatsiyasiga qo‘shildi.",
        "fed_left": "✅ Bu chat federatsiyadan chiqdi.",
        "fed_banned": "✅ {user} {n} chatda fed-banlandi. Sabab: {reason}",
        "fed_unbanned": "✅ {user} federatsiya ban ro‘yxatidan olib tashlandi.",
        "note_saved": "✅ `{name}` eslatmasi saqlandi.",
        "note_cleared": "✅ `{name}` eslatmasi o‘chirildi.",
        "note_missing": "❌ `{name}` nomli eslatma yo‘q.",
        "notes_empty": "Bu chatda eslatmalar yo‘q.",
        "filter_saved": "✅ `{kw}` filtri saqlandi.",
        "filter_cleared": "✅ `{kw}` filtri o‘chirildi.",
        "filters_empty": "Bu yerda filtrlar sozlanmagan.",
        "lock_set": "🔒 `{type}` qulflandi.",
        "unlock_set": "🔓 `{type}` ochildi.",
        "lock_unknown": "❌ Noma’lum qulf turi. /locktypes ni sinab ko‘r.",
        "bl_added": "✅ Qora ro‘yxatga qo‘shildi: {word}",
        "bl_removed": "✅ Qora ro‘yxatdan olib tashlandi: {word}",
        "bl_empty": "Qora ro‘yxat bo‘sh.",
        "disabled_set": "`{cmd}` buyrug‘i o‘chirildi.",
        "enabled_set": "`{cmd}` buyrug‘i yoqildi.",
        "afk_on": "{user} endi AFK. Sabab: {reason}",
        "afk_back": "{user} qaytdi. {dur} AFK edi.",
        "afk_mentioned": "{user} AFK ({dur}). Sabab: {reason}",
        "connect_ok": "✅ {title} ga ulandi.",
        "connect_off": "Uzildi.",
        "connect_none": "Hech qaysi chatga ulanmagan.",
        "gban_ok": "✅ {user} global bloklandi.",
        "ungban_ok": "✅ {user} global ban ro‘yxatidan olib tashlandi.",
        "welcome_default": "{groupname} ga xush kelibsiz {mention}!",
        "goodbye_default": "Xayr {mention}!",
        "captcha_prompt": "👋 Xush kelibsiz {mention}! Yech: {a} + {b} = ?",
        "captcha_wrong": "❌ Noto‘g‘ri! Qaytadan urinib ko‘r.",
        "captcha_correct": "✅ To‘g‘ri! Xush kelibsiz {mention}!",
        "captcha_timeout": "⏰ {mention} kapchani yechmadi va olib tashlandi.",
        "settings_admin_only": "Faqat adminlar /settings dan foydalana oladi.",
        "where_open": "Sozlamalar menyusini qayerda ochaman?",
        "open_here": "👥 Shu yerda och",
        "open_private": "👤 Shaxsiy chatda och",
        "settings_closed": "Sozlamalar yopildi.",
        "lang_changed": "Tayyor — endi men shu yerda o‘zbek tilida gaplashaman.",
        "user_lang_changed": "✅ Sening tiling endi {lang}. Barcha xabarlar shu tilda bo‘ladi.",
        "rules_updated": "✅ Qoidalar yangilandi.",
        "rules_cleared": "✅ Qoidalar o‘chirildi.",
        "no_rules": "Qoidalar belgilanmagan.",
        "perms_title": "🕹 Ruxsatlar\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} uchun ruxsatlar saqlandi.",
        "perm_text": "Matnli xabarlar",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Stiker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Ovozli xabar",
        "perm_file": "Fayl",
        "perm_roundvideo": "Doiraviy video",
        "perm_polls": "So‘rovnomalar",
        "perm_links": "Havola ko‘rinishini yoqish",
        "perm_tag": "O‘z tegini tahrirlash",
        "perm_save_btn": "Saqlash ✓",
        "cancelled": "❌ Bekor qilindi.",
        "done": "✅ Tayyor.",
        "error": "❌ Xato: {msg}",
        "admins_only": "❌ Faqat adminlar.",
        "reply_required": "❌ Avval xabarga javob ber.",
        "user_not_found": "❌ Foydalanuvchi topilmadi.",
        "invalid_args": "❌ Noto‘g‘ri argumentlar.",
    },
    "uz_cy": {
        "warned": "{user} огоҳлантириш олди {count}/{limit}.",
        "warn_reset": "{user} огоҳлантиришлари 0 га туширилди.",
        "warn_limit": "{user} огоҳлантириш чегарасига {limit} етди. Нима қиламиз?",
        "warns_none": "{user} да огоҳлантириш йўқ.",
        "muted": "{user} 🔇 овозсиз қилинди.",
        "unmuted": "{user} энди 🔇 овозсиз эмас.",
        "banned": "{user} 🚫 бан қилинди.",
        "unbanned": "{user} бандан чиқарилди.",
        "kicked": "{user} чиқариб юборилди.",
        "no_target": "Фойдаланувчига жавоб бер ёки @username/user-id юбор.",
        "not_admin": "❌ Фақат админлар учун.",
        "bot_no_perm": "❌ Бу амални бажариш учун рухсатим йўқ.",
        "self_target": "❌ Буни ўзингга қўллаб бўлмайди.",
        "admin_target": "❌ Бошқа админга қарши ҳаракат қила олмайман.",
        "owner_target": "❌ Чат эгасига қарши ҳаракат қила олмайман.",
        "cant_self": "❌ Буни ўзингга қўллаб бўлмайди.",
        "cant_admin": "❌ Бошқа админга қарши ҳаракат қила олмайман.",
        "action_failed": "❌ Бажарилмади: {error}",
        "reason_label": "Сабаб: {reason}",
        "fed_only_owner": "❌ Фақат федерация эгаси бажара олади.",
        "fed_not_found": "❌ Федерация топилмади.",
        "fed_created": "✅ '{name}' федерацияси яратилди, id `{fid}`.",
        "fed_joined": "✅ Бу чат `{fid}` федерациясига қўшилди.",
        "fed_left": "✅ Бу чат федерациядан чиқди.",
        "fed_banned": "✅ {user} {n} чатда фед-бан қилинди. Сабаб: {reason}",
        "fed_unbanned": "✅ {user} федерация бан рўйхатидан олиб ташланди.",
        "note_saved": "✅ `{name}` эслатмаси сақланди.",
        "note_cleared": "✅ `{name}` эслатмаси ўчирилди.",
        "note_missing": "❌ `{name}` номли эслатма йўқ.",
        "notes_empty": "Бу чатда эслатмалар йўқ.",
        "filter_saved": "✅ `{kw}` фильтри сақланди.",
        "filter_cleared": "✅ `{kw}` фильтри ўчирилди.",
        "filters_empty": "Бу ерда фильтрлар созланмаган.",
        "lock_set": "🔒 `{type}` қулфланди.",
        "unlock_set": "🔓 `{type}` очилди.",
        "lock_unknown": "❌ Номаълум қулф тури. /locktypes ни синаб кўр.",
        "bl_added": "✅ Қора рўйхатга қўшилди: {word}",
        "bl_removed": "✅ Қора рўйхатдан олиб ташланди: {word}",
        "bl_empty": "Қора рўйхат бўш.",
        "disabled_set": "`{cmd}` буйруғи ўчирилди.",
        "enabled_set": "`{cmd}` буйруғи ёқилди.",
        "afk_on": "{user} энди AFK. Сабаб: {reason}",
        "afk_back": "{user} қайтди. {dur} AFK эди.",
        "afk_mentioned": "{user} AFK ({dur}). Сабаб: {reason}",
        "connect_ok": "✅ {title} га уланди.",
        "connect_off": "Узилди.",
        "connect_none": "Ҳеч қайси чатга уланмаган.",
        "gban_ok": "✅ {user} глобал банланди.",
        "ungban_ok": "✅ {user} глобал бан рўйхатидан олиб ташланди.",
        "welcome_default": "{groupname} га хуш келибсиз {mention}!",
        "goodbye_default": "Хайр {mention}!",
        "captcha_prompt": "👋 Хуш келибсиз {mention}! Еч: {a} + {b} = ?",
        "captcha_wrong": "❌ Нотўғри! Қайтадан уриниб кўр.",
        "captcha_correct": "✅ Тўғри! Хуш келибсиз {mention}!",
        "captcha_timeout": "⏰ {mention} капчани ечмади ва олиб ташланди.",
        "settings_admin_only": "Фақат админлар /settings дан фойдалана олади.",
        "where_open": "Созламалар менюсини қаерда очаман?",
        "open_here": "👥 Шу ерда оч",
        "open_private": "👤 Шахсий чатда оч",
        "settings_closed": "Созламалар ёпилди.",
        "lang_changed": "Тайёр — энди мен шу ерда ўзбек тилида гаплашаман.",
        "user_lang_changed": "✅ Сенинг тилинг энди {lang}. Барча хабарлар шу тилда бўлади.",
        "rules_updated": "✅ Қоидалар янгиланди.",
        "rules_cleared": "✅ Қоидалар ўчирилди.",
        "no_rules": "Қоидалар белгиланмаган.",
        "perms_title": "🕹 Рухсатлар\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} учун рухсатлар сақланди.",
        "perm_text": "Матнли хабарлар",
        "perm_photo": "Фото",
        "perm_video": "Видео",
        "perm_sticker": "Стикер/GIF",
        "perm_audio": "Аудио",
        "perm_voice": "Овозли хабар",
        "perm_file": "Файл",
        "perm_roundvideo": "Доиравий видео",
        "perm_polls": "Сўровномалар",
        "perm_links": "Ҳавола кўринишини ёқиш",
        "perm_tag": "Ўз тегини таҳрирлаш",
        "perm_save_btn": "Сақлаш ✓",
        "cancelled": "❌ Бекор қилинди.",
        "done": "✅ Тайёр.",
        "error": "❌ Хато: {msg}",
        "admins_only": "❌ Фақат админлар.",
        "reply_required": "❌ Аввал хабарга жавоб бер.",
        "user_not_found": "❌ Фойдаланувчи топилмади.",
        "invalid_args": "❌ Нотўғри аргументлар.",
    },
    "az": {
        "warned": "{user} xəbərdarlıq aldı {count}/{limit}.",
        "warn_reset": "{user} xəbərdarlıqları 0-a sıfırlandı.",
        "warn_limit": "{user} xəbərdarlıq həddinə {limit} çatdı. Nə edək?",
        "warns_none": "{user}-də xəbərdarlıq yoxdur.",
        "muted": "{user} 🔇 səssizləşdirildi.",
        "unmuted": "{user} artıq 🔇 səssiz deyil.",
        "banned": "{user} 🚫 bloklandı.",
        "unbanned": "{user} blokdan çıxarıldı.",
        "kicked": "{user} qovuldu.",
        "no_target": "İstifadəçiyə cavab ver, ya da @username/user-id ötür.",
        "not_admin": "❌ Yalnız adminlər.",
        "bot_no_perm": "❌ Bunu etmək üçün icazəm yoxdur.",
        "self_target": "❌ Bunu özünə tətbiq edə bilməzsən.",
        "admin_target": "❌ Başqa adminə qarşı hərəkət edə bilmirəm.",
        "owner_target": "❌ Söhbət sahibinə qarşı hərəkət edə bilmirəm.",
        "cant_self": "❌ Bunu özünə tətbiq edə bilməzsən.",
        "cant_admin": "❌ Başqa adminə qarşı hərəkət edə bilmirəm.",
        "action_failed": "❌ Alınmadı: {error}",
        "reason_label": "Səbəb: {reason}",
        "fed_only_owner": "❌ Yalnız federasiya sahibi bunu edə bilər.",
        "fed_not_found": "❌ Federasiya tapılmadı.",
        "fed_created": "✅ '{name}' federasiyası yaradıldı, id `{fid}`.",
        "fed_joined": "✅ Bu söhbət `{fid}` federasiyasına qoşuldu.",
        "fed_left": "✅ Bu söhbət federasiyadan çıxdı.",
        "fed_banned": "✅ {user} {n} söhbətdə fed-bloklandı. Səbəb: {reason}",
        "fed_unbanned": "✅ {user} federasiya blok siyahısından çıxarıldı.",
        "note_saved": "✅ `{name}` qeydi yadda saxlandı.",
        "note_cleared": "✅ `{name}` qeydi silindi.",
        "note_missing": "❌ `{name}` adlı qeyd yoxdur.",
        "notes_empty": "Bu söhbətdə qeyd yoxdur.",
        "filter_saved": "✅ `{kw}` filtri yadda saxlandı.",
        "filter_cleared": "✅ `{kw}` filtri silindi.",
        "filters_empty": "Burada filtrlər təyin olunmayıb.",
        "lock_set": "🔒 `{type}` kilidləndi.",
        "unlock_set": "🔓 `{type}` açıldı.",
        "lock_unknown": "❌ Naməlum kilid növü. /locktypes-i yoxla.",
        "bl_added": "✅ Qara siyahıya əlavə edildi: {word}",
        "bl_removed": "✅ Qara siyahıdan çıxarıldı: {word}",
        "bl_empty": "Qara siyahı boşdur.",
        "disabled_set": "`{cmd}` əmri söndürüldü.",
        "enabled_set": "`{cmd}` əmri aktiv edildi.",
        "afk_on": "{user} indi AFK-dir. Səbəb: {reason}",
        "afk_back": "{user} qayıtdı. {dur} AFK idi.",
        "afk_mentioned": "{user} AFK-dir ({dur}). Səbəb: {reason}",
        "connect_ok": "✅ {title}-ə qoşuldu.",
        "connect_off": "Bağlantı kəsildi.",
        "connect_none": "Heç bir söhbətə qoşulmayıb.",
        "gban_ok": "✅ {user} qlobal bloklandı.",
        "ungban_ok": "✅ {user} qlobal blok siyahısından çıxarıldı.",
        "welcome_default": "{groupname}-ə xoş gəlmisən {mention}!",
        "goodbye_default": "Sağ ol {mention}!",
        "captcha_prompt": "👋 Xoş gəlmisən {mention}! Həll et: {a} + {b} = ?",
        "captcha_wrong": "❌ Səhv! Yenidən cəhd et.",
        "captcha_correct": "✅ Doğru! Xoş gəlmisən {mention}!",
        "captcha_timeout": "⏰ {mention} kapçanı həll etmədi və qovuldu.",
        "settings_admin_only": "Yalnız adminlər /settings istifadə edə bilər.",
        "where_open": "Tənzimləmələr menyusunu harada açım?",
        "open_here": "👥 Burada aç",
        "open_private": "👤 Şəxsi söhbətdə aç",
        "settings_closed": "Tənzimləmələr bağlandı.",
        "lang_changed": "Hazırdır — indi mən burada Azərbaycanca danışacağam.",
        "user_lang_changed": "✅ Sənin dilin indi {lang}. Bütün mesajlar bu dildə olacaq.",
        "rules_updated": "✅ Qaydalar yeniləndi.",
        "rules_cleared": "✅ Qaydalar silindi.",
        "no_rules": "Qaydalar təyin olunmayıb.",
        "perms_title": "🕹 İcazələr\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} üçün icazələr yadda saxlandı.",
        "perm_text": "Mətn mesajları",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Stiker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Səs mesajı",
        "perm_file": "Fayl",
        "perm_roundvideo": "Yumru video",
        "perm_polls": "Sorğular",
        "perm_links": "Link önizləməsini aktiv et",
        "perm_tag": "Öz teqini redaktə et",
        "perm_save_btn": "Saxla ✓",
        "cancelled": "❌ Ləğv edildi.",
        "done": "✅ Hazırdır.",
        "error": "❌ Xəta: {msg}",
        "admins_only": "❌ Yalnız adminlər.",
        "reply_required": "❌ Əvvəlcə mesaja cavab ver.",
        "user_not_found": "❌ İstifadəçi tapılmadı.",
        "invalid_args": "❌ Yanlış arqumentlər.",
    },
    "ms": {
        "warned": "{user} menerima amaran {count}/{limit}.",
        "warn_reset": "Amaran {user} ditetapkan semula kepada 0.",
        "warn_limit": "{user} mencapai had amaran {limit}. Apa nak buat?",
        "warns_none": "{user} tiada amaran.",
        "muted": "{user} telah 🔇 dibisukan.",
        "unmuted": "{user} tidak lagi 🔇 dibisukan.",
        "banned": "{user} telah 🚫 diharamkan.",
        "unbanned": "{user} telah dibatalkan haram.",
        "kicked": "{user} telah ditendang.",
        "no_target": "Balas pengguna, atau hantar @username / user-id.",
        "not_admin": "❌ Hanya admin sahaja.",
        "bot_no_perm": "❌ Saya tiada kebenaran untuk ini.",
        "self_target": "❌ Anda tidak boleh guna pada diri sendiri.",
        "admin_target": "❌ Saya tidak boleh bertindak terhadap admin lain.",
        "owner_target": "❌ Saya tidak boleh bertindak terhadap pemilik chat.",
        "cant_self": "❌ Anda tidak boleh guna pada diri sendiri.",
        "cant_admin": "❌ Saya tidak boleh bertindak terhadap admin lain.",
        "action_failed": "❌ Gagal: {error}",
        "reason_label": "Sebab: {reason}",
        "fed_only_owner": "❌ Hanya pemilik federasi boleh buat ini.",
        "fed_not_found": "❌ Federasi tidak dijumpai.",
        "fed_created": "✅ Federasi '{name}' dicipta dengan id `{fid}`.",
        "fed_joined": "✅ Chat ini menyertai federasi `{fid}`.",
        "fed_left": "✅ Chat ini meninggalkan federasi.",
        "fed_banned": "✅ {user} di-fedban dalam {n} chat. Sebab: {reason}",
        "fed_unbanned": "✅ {user} dialih keluar daripada senarai fedban.",
        "note_saved": "✅ Nota `{name}` disimpan.",
        "note_cleared": "✅ Nota `{name}` dipadam.",
        "note_missing": "❌ Tiada nota bernama `{name}`.",
        "notes_empty": "Tiada nota dalam chat ini.",
        "filter_saved": "✅ Penapis `{kw}` disimpan.",
        "filter_cleared": "✅ Penapis `{kw}` dipadam.",
        "filters_empty": "Tiada penapis di sini.",
        "lock_set": "🔒 `{type}` dikunci.",
        "unlock_set": "🔓 `{type}` dibuka.",
        "lock_unknown": "❌ Jenis kunci tidak diketahui. Cuba /locktypes.",
        "bl_added": "✅ Ditambah ke senarai hitam: {word}",
        "bl_removed": "✅ Dibuang dari senarai hitam: {word}",
        "bl_empty": "Senarai hitam kosong.",
        "disabled_set": "Arahan `{cmd}` dimatikan.",
        "enabled_set": "Arahan `{cmd}` dihidupkan.",
        "afk_on": "{user} kini AFK. Sebab: {reason}",
        "afk_back": "{user} sudah kembali. AFK selama {dur}.",
        "afk_mentioned": "{user} sedang AFK ({dur}). Sebab: {reason}",
        "connect_ok": "✅ Disambungkan ke {title}.",
        "connect_off": "Diputuskan.",
        "connect_none": "Tidak disambung ke mana-mana chat.",
        "gban_ok": "✅ {user} diharamkan secara global.",
        "ungban_ok": "✅ {user} dialih keluar dari senarai haram global.",
        "welcome_default": "Selamat datang {mention} ke {groupname}!",
        "goodbye_default": "Selamat tinggal {mention}!",
        "captcha_prompt": "👋 Selamat datang {mention}! Selesaikan: {a} + {b} = ?",
        "captcha_wrong": "❌ Salah! Cuba lagi.",
        "captcha_correct": "✅ Betul! Selamat datang {mention}!",
        "captcha_timeout": "⏰ {mention} tidak menyelesaikan captcha dan dialih keluar.",
        "settings_admin_only": "Hanya pentadbir boleh guna /settings.",
        "where_open": "Di mana mahu buka menu tetapan?",
        "open_here": "👥 Buka di sini",
        "open_private": "👤 Buka dalam chat peribadi",
        "settings_closed": "Tetapan ditutup.",
        "lang_changed": "Selesai — saya akan bercakap Bahasa Melayu di sini.",
        "user_lang_changed": "✅ Bahasa anda kini {lang}. Semua mesej dalam bahasa ini.",
        "rules_updated": "✅ Peraturan dikemaskini.",
        "rules_cleared": "✅ Peraturan dipadam.",
        "no_rules": "Tiada peraturan ditetapkan.",
        "perms_title": "🕹 Kebenaran\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Kebenaran disimpan untuk {user}.",
        "perm_text": "Mesej teks",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Stiker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Mesej suara",
        "perm_file": "Fail",
        "perm_roundvideo": "Video bulat",
        "perm_polls": "Tinjauan",
        "perm_links": "Aktifkan pratonton pautan",
        "perm_tag": "Edit tag sendiri",
        "perm_save_btn": "Simpan ✓",
        "cancelled": "❌ Dibatalkan.",
        "done": "✅ Selesai.",
        "error": "❌ Ralat: {msg}",
        "admins_only": "❌ Hanya pentadbir.",
        "reply_required": "❌ Balas kepada mesej dahulu.",
        "user_not_found": "❌ Pengguna tidak dijumpai.",
        "invalid_args": "❌ Argumen tidak sah.",
    },
    "so": {
        "warned": "{user} wuxuu helay digniin {count}/{limit}.",
        "warn_reset": "Digniinaha {user} waxay ku noqdeen 0.",
        "warn_limit": "{user} wuxuu gaaray xadka digniinta {limit}. Maxaa la sameeyaa?",
        "warns_none": "{user} ma haysto digniin.",
        "muted": "{user} waa la 🔇 aamusiyey.",
        "unmuted": "{user} ma sii ahan 🔇 aamus.",
        "banned": "{user} waa la 🚫 mamnuucay.",
        "unbanned": "{user} mamnuucan dib ayaa loo soo daayey.",
        "kicked": "{user} waa la saaray.",
        "no_target": "U jawaab isticmaalaha, ama gudbi @username/user-id.",
        "not_admin": "❌ Maamulayaasha kaliya.",
        "bot_no_perm": "❌ Ma haysto oggolaansho aan tan ku sameeyo.",
        "self_target": "❌ Naftaada uguma isticmaali kartid.",
        "admin_target": "❌ Ma awoodi karo inaan ka qabto maamulah kale.",
        "owner_target": "❌ Ma awoodi karo inaan ka qabto mulkiilaha sheekada.",
        "cant_self": "❌ Naftaada uguma isticmaali kartid.",
        "cant_admin": "❌ Ma awoodi karo inaan ka qabto maamulah kale.",
        "action_failed": "❌ Wuu fashilmay: {error}",
        "reason_label": "Sababta: {reason}",
        "fed_only_owner": "❌ Mulkiilaha federation-ka ayaa kaliya samayn kara.",
        "fed_not_found": "❌ Federation lama helin.",
        "fed_created": "✅ Federation '{name}' la sameeyey id `{fid}`.",
        "fed_joined": "✅ Sheekadan waxay ku biirtay federation `{fid}`.",
        "fed_left": "✅ Sheekadan waxay ka tagtay federation-ka.",
        "fed_banned": "✅ {user} fed-ban ku sameeyey {n} sheeko. Sababta: {reason}",
        "fed_unbanned": "✅ {user} laga saaray liiska fed-ban.",
        "note_saved": "✅ Qoraal `{name}` waa la kaydiyey.",
        "note_cleared": "✅ Qoraal `{name}` waa la tirtiray.",
        "note_missing": "❌ Ma haysto qoraal `{name}` magaceedu.",
        "notes_empty": "Ma jiraan qoraallo sheekadan dhexdeeda.",
        "filter_saved": "✅ Filter `{kw}` la kaydiyey.",
        "filter_cleared": "✅ Filter `{kw}` la tirtiray.",
        "filters_empty": "Ma jiraan filter halkan.",
        "lock_set": "🔒 `{type}` waa la xidhay.",
        "unlock_set": "🔓 `{type}` waa la furay.",
        "lock_unknown": "❌ Nooc qufullo aan la garanayn. Isku day /locktypes.",
        "bl_added": "✅ Liiska madow lagu daray: {word}",
        "bl_removed": "✅ Liiska madow laga saaray: {word}",
        "bl_empty": "Liiska madow waa madhan.",
        "disabled_set": "Amarka `{cmd}` waa la damiyey.",
        "enabled_set": "Amarka `{cmd}` waa la shidey.",
        "afk_on": "{user} hadda waa AFK. Sababta: {reason}",
        "afk_back": "{user} ayaa soo noqdey. Wuxuu ahaa AFK {dur}.",
        "afk_mentioned": "{user} waa AFK ({dur}). Sababta: {reason}",
        "connect_ok": "✅ La xiriiray {title}.",
        "connect_off": "Waa la kala goostay.",
        "connect_none": "Lama xiriirin sheeko.",
        "gban_ok": "✅ {user} caalami ahaan waa la mamnuucay.",
        "ungban_ok": "✅ {user} laga saaray liiska mamnuuca caalamiga ah.",
        "welcome_default": "Soo dhawow {mention} {groupname}!",
        "goodbye_default": "Nabad {mention}!",
        "captcha_prompt": "👋 Soo dhawow {mention}! Xalli: {a} + {b} = ?",
        "captcha_wrong": "❌ Khalad! Mar kale isku day.",
        "captcha_correct": "✅ Sax! Soo dhawow {mention}!",
        "captcha_timeout": "⏰ {mention} ma xalin captcha waana la saaray.",
        "settings_admin_only": "Maamulayaasha kaliya ayaa isticmaali kara /settings.",
        "where_open": "Halkee aad rabtaa inaan ka furo menu-ga settings?",
        "open_here": "👥 Halkan ka fur",
        "open_private": "👤 Sheeko gaar ah ka fur",
        "settings_closed": "Settings waa la xidhay.",
        "lang_changed": "Diyaar — hadda waxaan ku hadli doonaa Soomaali.",
        "user_lang_changed": "✅ Luqaddaada hadda waa {lang}. Dhammaan farriimahayga ayaa luqaddan ku jiri doona.",
        "rules_updated": "✅ Sharciyada waa la cusboonaysiiyay.",
        "rules_cleared": "✅ Sharciyada waa la tirtiray.",
        "no_rules": "Sharciyo lama dejin.",
        "perms_title": "🕹 Oggolaansho\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Oggolaanshaha {user} waa la kaydiyey.",
        "perm_text": "Farriimaha qoraalka",
        "perm_photo": "Sawir",
        "perm_video": "Muuqaal",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Cod",
        "perm_voice": "Codka",
        "perm_file": "Fayl",
        "perm_roundvideo": "Muuqaal goobaaran",
        "perm_polls": "Doodaha",
        "perm_links": "Awood u sii horudhaca xiriirinta",
        "perm_tag": "Wax ka beddel calaamaddaada",
        "perm_save_btn": "Kaydi ✓",
        "cancelled": "❌ Waa la joojiyey.",
        "done": "✅ Diyaar.",
        "error": "❌ Khalad: {msg}",
        "admins_only": "❌ Maamulayaasha kaliya.",
        "reply_required": "❌ Marka hore u jawaab fariin.",
        "user_not_found": "❌ Isticmaalaha lama helin.",
        "invalid_args": "❌ Doodahu sax ma aha.",
    },
    "sq": {
        "warned": "{user} mori paralajmërim {count}/{limit}.",
        "warn_reset": "Paralajmërimet e {user} u rivendosën në 0.",
        "warn_limit": "{user} arriti kufirin e paralajmërimeve {limit}. Çfarë të bëjmë?",
        "warns_none": "{user} nuk ka paralajmërime.",
        "muted": "{user} u 🔇 heshtua.",
        "unmuted": "{user} nuk është më 🔇 i heshtuar.",
        "banned": "{user} u 🚫 dëbua.",
        "unbanned": "{user} u rikthye nga dëbimi.",
        "kicked": "{user} u përjashtua.",
        "no_target": "Përgjigju një përdoruesi, ose dërgo @username/user-id.",
        "not_admin": "❌ Vetëm administratorët.",
        "bot_no_perm": "❌ Nuk kam të drejtën për këtë.",
        "self_target": "❌ Nuk mund ta përdorësh mbi vetveten.",
        "admin_target": "❌ Nuk mund të veproj kundër një tjetër administratori.",
        "owner_target": "❌ Nuk mund të veproj kundër pronarit të bisedës.",
        "cant_self": "❌ Nuk mund ta përdorësh mbi vetveten.",
        "cant_admin": "❌ Nuk mund të veproj kundër një tjetër administratori.",
        "action_failed": "❌ Dështoi: {error}",
        "reason_label": "Arsyeja: {reason}",
        "fed_only_owner": "❌ Vetëm pronari i federatës mund ta bëjë këtë.",
        "fed_not_found": "❌ Federata nuk u gjet.",
        "fed_created": "✅ Federata '{name}' u krijua me id `{fid}`.",
        "fed_joined": "✅ Kjo bisedë iu bashkua federatës `{fid}`.",
        "fed_left": "✅ Kjo bisedë e la federatën.",
        "fed_banned": "✅ {user} u dëbua nga federata në {n} biseda. Arsyeja: {reason}",
        "fed_unbanned": "✅ {user} u hoq nga lista e dëbimeve të federatës.",
        "note_saved": "✅ Shënimi `{name}` u ruajt.",
        "note_cleared": "✅ Shënimi `{name}` u fshi.",
        "note_missing": "❌ Nuk ka shënim me emrin `{name}`.",
        "notes_empty": "Asnjë shënim në këtë bisedë.",
        "filter_saved": "✅ Filtri `{kw}` u ruajt.",
        "filter_cleared": "✅ Filtri `{kw}` u fshi.",
        "filters_empty": "Pa filtra të konfiguruar këtu.",
        "lock_set": "🔒 `{type}` u kyç.",
        "unlock_set": "🔓 `{type}` u zhbllokua.",
        "lock_unknown": "❌ Lloj i panjohur kyçjeje. Provo /locktypes.",
        "bl_added": "✅ U shtua në listën e zezë: {word}",
        "bl_removed": "✅ U hoq nga lista e zezë: {word}",
        "bl_empty": "Lista e zezë është bosh.",
        "disabled_set": "Komanda `{cmd}` u çaktivizua.",
        "enabled_set": "Komanda `{cmd}` u aktivizua.",
        "afk_on": "{user} tani është AFK. Arsyeja: {reason}",
        "afk_back": "{user} u kthye. Ishte AFK për {dur}.",
        "afk_mentioned": "{user} është AFK ({dur}). Arsyeja: {reason}",
        "connect_ok": "✅ U lidh me {title}.",
        "connect_off": "U shkëput.",
        "connect_none": "Pa lidhje me asnjë bisedë.",
        "gban_ok": "✅ {user} u dëbua globalisht.",
        "ungban_ok": "✅ {user} u hoq nga lista e dëbimeve globale.",
        "welcome_default": "Mirësevjen {mention} në {groupname}!",
        "goodbye_default": "Mirupafshim {mention}!",
        "captcha_prompt": "👋 Mirësevjen {mention}! Zgjidh: {a} + {b} = ?",
        "captcha_wrong": "❌ Gabim! Provo përsëri.",
        "captcha_correct": "✅ Saktë! Mirësevjen {mention}!",
        "captcha_timeout": "⏰ {mention} nuk e zgjidhi captcha dhe u përjashtua.",
        "settings_admin_only": "Vetëm administratorët mund të përdorin /settings.",
        "where_open": "Ku të hapet menyja e cilësimeve?",
        "open_here": "👥 Hap këtu",
        "open_private": "👤 Hap në bisedë private",
        "settings_closed": "Cilësimet u mbyllën.",
        "lang_changed": "U krye — tani do flas shqip këtu.",
        "user_lang_changed": "✅ Gjuha jote tani është {lang}. Të gjitha mesazhet do shfaqen në këtë gjuhë.",
        "rules_updated": "✅ Rregullat u përditësuan.",
        "rules_cleared": "✅ Rregullat u fshinë.",
        "no_rules": "Pa rregulla të vendosura.",
        "perms_title": "🕹 Lejet\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Lejet u ruajtën për {user}.",
        "perm_text": "Mesazhe teksti",
        "perm_photo": "Foto",
        "perm_video": "Video",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Mesazh zanor",
        "perm_file": "Skedar",
        "perm_roundvideo": "Video e rrumbullakët",
        "perm_polls": "Sondazhe",
        "perm_links": "Aktivizo paraqitjen e lidhjeve",
        "perm_tag": "Modifiko etiketën tënde",
        "perm_save_btn": "Ruaj ✓",
        "cancelled": "❌ U anulua.",
        "done": "✅ U krye.",
        "error": "❌ Gabim: {msg}",
        "admins_only": "❌ Vetëm administratorët.",
        "reply_required": "❌ Përgjigju fillimisht një mesazhi.",
        "user_not_found": "❌ Përdoruesi nuk u gjet.",
        "invalid_args": "❌ Argumente të pavlefshme.",
    },
    "sr": {
        "warned": "{user} je dobio upozorenje {count}/{limit}.",
        "warn_reset": "Upozorenja za {user} resetovana na 0.",
        "warn_limit": "{user} je dostigao limit upozorenja {limit}. Šta da radimo?",
        "warns_none": "{user} nema upozorenja.",
        "muted": "{user} je 🔇 ućutkan.",
        "unmuted": "{user} više nije 🔇 ućutkan.",
        "banned": "{user} je 🚫 banovan.",
        "unbanned": "{user} je odbanovan.",
        "kicked": "{user} je izbačen.",
        "no_target": "Odgovori korisniku, ili pošalji @username/user-id.",
        "not_admin": "❌ Samo administratori.",
        "bot_no_perm": "❌ Nemam dozvolu za ovo.",
        "self_target": "❌ Ne možeš ovo na sebi.",
        "admin_target": "❌ Ne mogu protiv drugog admina.",
        "owner_target": "❌ Ne mogu protiv vlasnika ćaskanja.",
        "cant_self": "❌ Ne možeš ovo na sebi.",
        "cant_admin": "❌ Ne mogu protiv drugog admina.",
        "action_failed": "❌ Neuspeh: {error}",
        "reason_label": "Razlog: {reason}",
        "fed_only_owner": "❌ Samo vlasnik federacije može ovo.",
        "fed_not_found": "❌ Federacija nije pronađena.",
        "fed_created": "✅ Federacija '{name}' kreirana sa id `{fid}`.",
        "fed_joined": "✅ Ovaj čat se pridružio federaciji `{fid}`.",
        "fed_left": "✅ Ovaj čat je napustio federaciju.",
        "fed_banned": "✅ {user} fed-banovan u {n} čatova. Razlog: {reason}",
        "fed_unbanned": "✅ {user} uklonjen sa liste federacijskih banova.",
        "note_saved": "✅ Beleška `{name}` sačuvana.",
        "note_cleared": "✅ Beleška `{name}` obrisana.",
        "note_missing": "❌ Nemam belešku pod imenom `{name}`.",
        "notes_empty": "Nema beležaka u ovom čatu.",
        "filter_saved": "✅ Filter `{kw}` sačuvan.",
        "filter_cleared": "✅ Filter `{kw}` obrisan.",
        "filters_empty": "Ovde nema filtera.",
        "lock_set": "🔒 `{type}` zaključano.",
        "unlock_set": "🔓 `{type}` otključano.",
        "lock_unknown": "❌ Nepoznat tip zaključavanja. Probaj /locktypes.",
        "bl_added": "✅ Dodato na crnu listu: {word}",
        "bl_removed": "✅ Uklonjeno sa crne liste: {word}",
        "bl_empty": "Crna lista je prazna.",
        "disabled_set": "Komanda `{cmd}` onemogućena.",
        "enabled_set": "Komanda `{cmd}` omogućena.",
        "afk_on": "{user} je sada AFK. Razlog: {reason}",
        "afk_back": "{user} se vratio. Bio AFK {dur}.",
        "afk_mentioned": "{user} je AFK ({dur}). Razlog: {reason}",
        "connect_ok": "✅ Povezano sa {title}.",
        "connect_off": "Diskonektovano.",
        "connect_none": "Nije povezano ni sa jednim čatom.",
        "gban_ok": "✅ {user} globalno banovan.",
        "ungban_ok": "✅ {user} uklonjen sa globalne ban liste.",
        "welcome_default": "Dobrodošao {mention} u {groupname}!",
        "goodbye_default": "Doviđenja {mention}!",
        "captcha_prompt": "👋 Dobrodošao {mention}! Reši: {a} + {b} = ?",
        "captcha_wrong": "❌ Pogrešno! Pokušaj ponovo.",
        "captcha_correct": "✅ Tačno! Dobrodošao {mention}!",
        "captcha_timeout": "⏰ {mention} nije rešio captcha i uklonjen je.",
        "settings_admin_only": "Samo administratori mogu da koriste /settings.",
        "where_open": "Gde želiš da otvorim meni podešavanja?",
        "open_here": "👥 Otvori ovde",
        "open_private": "👤 Otvori u privatnom čatu",
        "settings_closed": "Podešavanja zatvorena.",
        "lang_changed": "Gotovo — sada govorim srpski ovde.",
        "user_lang_changed": "✅ Tvoj jezik je sada {lang}. Sve poruke će biti na ovom jeziku.",
        "rules_updated": "✅ Pravila ažurirana.",
        "rules_cleared": "✅ Pravila obrisana.",
        "no_rules": "Nema postavljenih pravila.",
        "perms_title": "🕹 Dozvole\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Dozvole sačuvane za {user}.",
        "perm_text": "Tekstualne poruke",
        "perm_photo": "Fotografija",
        "perm_video": "Video",
        "perm_sticker": "Stiker/GIF",
        "perm_audio": "Audio",
        "perm_voice": "Glasovna poruka",
        "perm_file": "Fajl",
        "perm_roundvideo": "Kružni video",
        "perm_polls": "Ankete",
        "perm_links": "Omogući pregled linkova",
        "perm_tag": "Uredi sopstveni tag",
        "perm_save_btn": "Sačuvaj ✓",
        "cancelled": "❌ Otkazano.",
        "done": "✅ Gotovo.",
        "error": "❌ Greška: {msg}",
        "admins_only": "❌ Samo administratori.",
        "reply_required": "❌ Prvo odgovori na poruku.",
        "user_not_found": "❌ Korisnik nije pronađen.",
        "invalid_args": "❌ Nevažeći argumenti.",
    },
    "am": {
        "warned": "{user} ማሳሰቢያ ተቀብሏል {count}/{limit}.",
        "warn_reset": "ለ{user} ማሳሰቢያዎች ወደ 0 ተመልሰዋል።",
        "warn_limit": "{user} የማሳሰቢያ ገደብ {limit} ደርሷል። ምን እናድርግ?",
        "warns_none": "{user} ምንም ማሳሰቢያ የለውም።",
        "muted": "{user} 🔇 ዝምታ ተደርጓል።",
        "unmuted": "{user} ከ🔇 ዝምታ ተለቀቀ።",
        "banned": "{user} 🚫 ታግዷል።",
        "unbanned": "{user} እገዳው ተነስቷል።",
        "kicked": "{user} ተባርሯል።",
        "no_target": "ለተጠቃሚ መልስ ስጥ፣ ወይም @username/user-id አቅርብ።",
        "not_admin": "❌ ለአስተዳዳሪዎች ብቻ።",
        "bot_no_perm": "❌ ይህን ለመስራት ፈቃድ የለኝም።",
        "self_target": "❌ በራስህ ላይ መጠቀም አትችልም።",
        "admin_target": "❌ በሌላ አስተዳዳሪ ላይ መንቀሳቀስ አልችልም።",
        "owner_target": "❌ በቻቱ ባለቤት ላይ መንቀሳቀስ አልችልም።",
        "cant_self": "❌ በራስህ ላይ መጠቀም አትችልም።",
        "cant_admin": "❌ በሌላ አስተዳዳሪ ላይ መንቀሳቀስ አልችልም።",
        "action_failed": "❌ አልተሳካም: {error}",
        "reason_label": "ምክንያት: {reason}",
        "fed_only_owner": "❌ የፌዴሬሽኑ ባለቤት ብቻ ይህን ማድረግ ይችላል።",
        "fed_not_found": "❌ ፌዴሬሽን አልተገኘም።",
        "fed_created": "✅ ፌዴሬሽን '{name}' በመለያ `{fid}` ተፈጥሯል።",
        "fed_joined": "✅ ይህ ቻት ወደ ፌዴሬሽን `{fid}` ተቀላቅሏል።",
        "fed_left": "✅ ይህ ቻት ከፌዴሬሽኑ ወጥቷል።",
        "fed_banned": "✅ {user} በ{n} ቻቶች ፌድ-ታግዷል። ምክንያት: {reason}",
        "fed_unbanned": "✅ {user} ከፌዴሬሽን እገዳ ዝርዝር ተወግዷል።",
        "note_saved": "✅ ማስታወሻ `{name}` ተቀምጧል።",
        "note_cleared": "✅ ማስታወሻ `{name}` ተሰርዟል።",
        "note_missing": "❌ `{name}` የተባለ ማስታወሻ የለም።",
        "notes_empty": "በዚህ ቻት ውስጥ ማስታወሻ የለም።",
        "filter_saved": "✅ ማጣሪያ `{kw}` ተቀምጧል።",
        "filter_cleared": "✅ ማጣሪያ `{kw}` ተሰርዟል።",
        "filters_empty": "እዚህ ምንም ማጣሪያ የለም።",
        "lock_set": "🔒 `{type}` ተቆልፏል።",
        "unlock_set": "🔓 `{type}` ተከፍቷል።",
        "lock_unknown": "❌ ያልታወቀ የመቆለፊያ አይነት። /locktypes ሞክር።",
        "bl_added": "✅ ወደ ጥቁር ዝርዝር ተጨምሯል: {word}",
        "bl_removed": "✅ ከጥቁር ዝርዝር ተወግዷል: {word}",
        "bl_empty": "ጥቁር ዝርዝሩ ባዶ ነው።",
        "disabled_set": "ትዕዛዝ `{cmd}` ጠፍቷል።",
        "enabled_set": "ትዕዛዝ `{cmd}` በርቷል።",
        "afk_on": "{user} አሁን AFK ነው። ምክንያት: {reason}",
        "afk_back": "{user} ተመልሷል። ለ{dur} AFK ነበር።",
        "afk_mentioned": "{user} AFK ነው ({dur})። ምክንያት: {reason}",
        "connect_ok": "✅ ከ{title} ጋር ተገናኝቷል።",
        "connect_off": "ተቋርጧል።",
        "connect_none": "ከማንኛውም ቻት ጋር አልተገናኘም።",
        "gban_ok": "✅ {user} በዓለም አቀፍ ደረጃ ታግዷል።",
        "ungban_ok": "✅ {user} ከዓለም አቀፍ እገዳ ዝርዝር ተወግዷል።",
        "welcome_default": "እንኳን ደህና መጣህ {mention} ወደ {groupname}!",
        "goodbye_default": "ደህና ሁን {mention}!",
        "captcha_prompt": "👋 እንኳን ደህና መጣህ {mention}! ፍታ: {a} + {b} = ?",
        "captcha_wrong": "❌ ስህተት! እንደገና ሞክር።",
        "captcha_correct": "✅ ትክክል! እንኳን ደህና መጣህ {mention}!",
        "captcha_timeout": "⏰ {mention} captcha-ውን አልፈታም እና ተወግዷል።",
        "settings_admin_only": "/settings ን አስተዳዳሪዎች ብቻ ሊጠቀሙበት ይችላሉ።",
        "where_open": "የቅንብር ሜኑ የት ይከፈት?",
        "open_here": "👥 እዚህ ክፈት",
        "open_private": "👤 በግል ቻት ክፈት",
        "settings_closed": "ቅንብሮች ተዘግተዋል።",
        "lang_changed": "ተጠናቅቋል — አሁን እዚህ በአማርኛ እናገራለሁ።",
        "user_lang_changed": "✅ ቋንቋህ አሁን {lang} ነው። ሁሉም መልዕክቶቼ በዚህ ቋንቋ ይታያሉ።",
        "rules_updated": "✅ ህጎች ተዘምነዋል።",
        "rules_cleared": "✅ ህጎች ተወግደዋል።",
        "no_rules": "ህጎች አልተዋቀሩም።",
        "perms_title": "🕹 ፈቃዶች\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ ፈቃዶች ለ{user} ተቀምጠዋል።",
        "perm_text": "ጽሑፍ መልዕክቶች",
        "perm_photo": "ፎቶ",
        "perm_video": "ቪዲዮ",
        "perm_sticker": "ስቲከር/GIF",
        "perm_audio": "ድምጽ",
        "perm_voice": "የድምጽ መልዕክት",
        "perm_file": "ፋይል",
        "perm_roundvideo": "ክብ ቪዲዮ",
        "perm_polls": "ምርጫዎች",
        "perm_links": "የሊንክ ቅድመ እይታ አንቃ",
        "perm_tag": "የራስ መለያ አስተካክል",
        "perm_save_btn": "አስቀምጥ ✓",
        "cancelled": "❌ ተሰርዟል።",
        "done": "✅ ተጠናቅቋል።",
        "error": "❌ ስህተት: {msg}",
        "admins_only": "❌ ለአስተዳዳሪዎች ብቻ።",
        "reply_required": "❌ መጀመሪያ ለመልዕክት መልስ ስጥ።",
        "user_not_found": "❌ ተጠቃሚ አልተገኘም።",
        "invalid_args": "❌ የተሳሳቱ መለኪያዎች።",
    },
    "ku": {
        "warned": "{user} hişyariyek wergirt {count}/{limit}.",
        "warn_reset": "Hişyariyên {user} ji nû ve bûne 0.",
        "warn_limit": "{user} gihîşt sînorê hişyariyê {limit}. Em çi bikin?",
        "warns_none": "{user} hişyarî tune.",
        "muted": "{user} hate 🔇 bêdengkirin.",
        "unmuted": "{user} êdî 🔇 bêdeng nine.",
        "banned": "{user} hate 🚫 qedexekirin.",
        "unbanned": "{user} ji qedexe hate derxistin.",
        "kicked": "{user} hate avêtin.",
        "no_target": "Bersivê bide bikarhênerekê, an @username/user-id bişîne.",
        "not_admin": "❌ Tenê rêveber.",
        "bot_no_perm": "❌ Destûra min ji bo vê tune.",
        "self_target": "❌ Tu nikarî vê li ser xwe bikar bînî.",
        "admin_target": "❌ Ez nikarim li dijî rêvebereke din tevbigerim.",
        "owner_target": "❌ Ez nikarim li dijî xwediyê chatê tevbigerim.",
        "cant_self": "❌ Tu nikarî vê li ser xwe bikar bînî.",
        "cant_admin": "❌ Ez nikarim li dijî rêvebereke din tevbigerim.",
        "action_failed": "❌ Têk çû: {error}",
        "reason_label": "Sedem: {reason}",
        "fed_only_owner": "❌ Tenê xwediyê federasyonê dikare vê bike.",
        "fed_not_found": "❌ Federasyon nehate dîtin.",
        "fed_created": "✅ Federasyona '{name}' bi id `{fid}` hate çêkirin.",
        "fed_joined": "✅ Ev chat tevlî federasyona `{fid}` bû.",
        "fed_left": "✅ Ev chat ji federasyonê derket.",
        "fed_banned": "✅ {user} di {n} chatan de fed-banê bûye. Sedem: {reason}",
        "fed_unbanned": "✅ {user} ji lîsteya federasyona ban hate rakirin.",
        "note_saved": "✅ Nota `{name}` hate tomarkirin.",
        "note_cleared": "✅ Nota `{name}` hate jêbirin.",
        "note_missing": "❌ Notek bi navê `{name}` tune.",
        "notes_empty": "Di vê chatê de not tune.",
        "filter_saved": "✅ Parzûna `{kw}` hate tomarkirin.",
        "filter_cleared": "✅ Parzûna `{kw}` hate jêbirin.",
        "filters_empty": "Li vir parzûn nînin.",
        "lock_set": "🔒 `{type}` hate kilîtkirin.",
        "unlock_set": "🔓 `{type}` hate vekirin.",
        "lock_unknown": "❌ Cûrê kilît nayê nasîn. /locktypes biceribîne.",
        "bl_added": "✅ Li lîsteya reş hate zêdekirin: {word}",
        "bl_removed": "✅ Ji lîsteya reş hate rakirin: {word}",
        "bl_empty": "Lîsteya reş vala ye.",
        "disabled_set": "Fermana `{cmd}` hate vegirtin.",
        "enabled_set": "Fermana `{cmd}` hate çalakkirin.",
        "afk_on": "{user} niha AFK ye. Sedem: {reason}",
        "afk_back": "{user} vegeriya. {dur} AFK bû.",
        "afk_mentioned": "{user} AFK ye ({dur}). Sedem: {reason}",
        "connect_ok": "✅ Bi {title} re hate girêdan.",
        "connect_off": "Hate qutkirin.",
        "connect_none": "Bi tu chatê re ne girêdayî.",
        "gban_ok": "✅ {user} bi gerdûnî hate qedexekirin.",
        "ungban_ok": "✅ {user} ji lîsteya qedexeya gerdûnî hate rakirin.",
        "welcome_default": "Bi xêr hatî {mention} li {groupname}!",
        "goodbye_default": "Bi xatirê te {mention}!",
        "captcha_prompt": "👋 Bi xêr hatî {mention}! Çareser bike: {a} + {b} = ?",
        "captcha_wrong": "❌ Çewt! Dîsa biceribîne.",
        "captcha_correct": "✅ Rast! Bi xêr hatî {mention}!",
        "captcha_timeout": "⏰ {mention} captcha çareser nekir û hate avêtin.",
        "settings_admin_only": "Tenê rêvebir dikarin /settings bi kar bînin.",
        "where_open": "Tu dixwazî menûya mîhengan li ku derê vekim?",
        "open_here": "👥 Li vir veke",
        "open_private": "👤 Di chata taybet de veke",
        "settings_closed": "Mîheng hatin girtin.",
        "lang_changed": "Hate qedandin — niha ezê li vir bi Kurdî biaxivim.",
        "user_lang_changed": "✅ Zimanê te niha {lang} ye. Hemû peyamên min wê bi vî zimanî bin.",
        "rules_updated": "✅ Rêzik hatin nûjenkirin.",
        "rules_cleared": "✅ Rêzik hatin jêbirin.",
        "no_rules": "Rêzik nehatine danîn.",
        "perms_title": "🕹 Destûr\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ Destûr ji bo {user} hatin tomarkirin.",
        "perm_text": "Peyamên nivîsê",
        "perm_photo": "Wêne",
        "perm_video": "Vîdyo",
        "perm_sticker": "Sticker/GIF",
        "perm_audio": "Deng",
        "perm_voice": "Peyama dengî",
        "perm_file": "Pel",
        "perm_roundvideo": "Vîdyoya gilover",
        "perm_polls": "Rapirsî",
        "perm_links": "Pêşdîtina lînkan çalak bike",
        "perm_tag": "Tagê xwe biguherîne",
        "perm_save_btn": "Tomar bike ✓",
        "cancelled": "❌ Hate betalkirin.",
        "done": "✅ Tewaw.",
        "error": "❌ Çewtî: {msg}",
        "admins_only": "❌ Tenê rêvebir.",
        "reply_required": "❌ Pêşî bersiva peyamekê bide.",
        "user_not_found": "❌ Bikarhêner nehate dîtin.",
        "invalid_args": "❌ Argumantên nederbasdar.",
    },
    "si": {
        "warned": "{user}ට අනතුරු ඇඟවීමක් ලැබුණා {count}/{limit}.",
        "warn_reset": "{user}ගේ අනතුරු ඇඟවීම් 0 ට යළි සකසා ඇත.",
        "warn_limit": "{user} අනතුරු ඇඟවීම් සීමාව {limit} ට ළඟාවී ඇත. කුමක් කළ යුතු ද?",
        "warns_none": "{user}ට අනතුරු ඇඟවීම් නැත.",
        "muted": "{user} 🔇 නිහඬ කර ඇත.",
        "unmuted": "{user} තවදුරටත් 🔇 නිහඬ නැත.",
        "banned": "{user} 🚫 තහනම් කර ඇත.",
        "unbanned": "{user} තහනමින් මුදවා ඇත.",
        "kicked": "{user} ඉවත් කර ඇත.",
        "no_target": "පරිශීලකයෙකුට පිළිතුරු දෙන්න, හෝ @username/user-id යවන්න.",
        "not_admin": "❌ පාලකයන්ට පමණයි.",
        "bot_no_perm": "❌ මෙය කිරීමට මට අවසර නැත.",
        "self_target": "❌ ඔබට මෙය ඔබ මතම යෙදිය නොහැක.",
        "admin_target": "❌ වෙනත් පාලකයෙකුට එරෙහිව ක්‍රියා කළ නොහැක.",
        "owner_target": "❌ සංවාද හිමිකරුට එරෙහිව ක්‍රියා කළ නොහැක.",
        "cant_self": "❌ ඔබට මෙය ඔබ මතම යෙදිය නොහැක.",
        "cant_admin": "❌ වෙනත් පාලකයෙකුට එරෙහිව ක්‍රියා කළ නොහැක.",
        "action_failed": "❌ අසාර්ථකයි: {error}",
        "reason_label": "හේතුව: {reason}",
        "fed_only_owner": "❌ ෆෙඩරේෂන් හිමිකරුට පමණක් මෙය කළ හැක.",
        "fed_not_found": "❌ ෆෙඩරේෂන් හමු නොවීය.",
        "fed_created": "✅ ෆෙඩරේෂන් '{name}' id `{fid}` සහිතව සාදන ලදී.",
        "fed_joined": "✅ මෙම සංවාදය ෆෙඩරේෂන් `{fid}` සමඟ සම්බන්ධ විය.",
        "fed_left": "✅ මෙම සංවාදය ෆෙඩරේෂන් වෙතින් ඉවත් විය.",
        "fed_banned": "✅ {user} සංවාද {n} ක ෆෙඩ්-තහනම් කරන ලදී. හේතුව: {reason}",
        "fed_unbanned": "✅ {user} ෆෙඩරේෂන් තහනම් ලැයිස්තුවෙන් ඉවත් කරන ලදී.",
        "note_saved": "✅ සටහන `{name}` සුරැකින ලදී.",
        "note_cleared": "✅ සටහන `{name}` මකා ඇත.",
        "note_missing": "❌ `{name}` නමින් සටහනක් නැත.",
        "notes_empty": "මෙම සංවාදයේ සටහන් නැත.",
        "filter_saved": "✅ පෙරහන `{kw}` සුරැකින ලදී.",
        "filter_cleared": "✅ පෙරහන `{kw}` මකා ඇත.",
        "filters_empty": "මෙහි පෙරහන් නැත.",
        "lock_set": "🔒 `{type}` අගුළු දමා ඇත.",
        "unlock_set": "🔓 `{type}` අගුළු හරවා ඇත.",
        "lock_unknown": "❌ නොදන්නා අගුළු වර්ගය. /locktypes උත්සාහ කරන්න.",
        "bl_added": "✅ කළු ලැයිස්තුවට එක් කරන ලදී: {word}",
        "bl_removed": "✅ කළු ලැයිස්තුවෙන් ඉවත් කරන ලදී: {word}",
        "bl_empty": "කළු ලැයිස්තුව හිස්ය.",
        "disabled_set": "අණ `{cmd}` අක්‍රිය කර ඇත.",
        "enabled_set": "අණ `{cmd}` සක්‍රිය කර ඇත.",
        "afk_on": "{user} දැන් AFK වේ. හේතුව: {reason}",
        "afk_back": "{user} ආපසු පැමිණ ඇත. {dur} ක් AFK විය.",
        "afk_mentioned": "{user} AFK ({dur}). හේතුව: {reason}",
        "connect_ok": "✅ {title} වෙත සම්බන්ධ විය.",
        "connect_off": "විසන්ධි විය.",
        "connect_none": "කිසිම සංවාදයකට සම්බන්ධ නැත.",
        "gban_ok": "✅ {user} ගෝලීයව තහනම් කර ඇත.",
        "ungban_ok": "✅ {user} ගෝලීය තහනම් ලැයිස්තුවෙන් ඉවත් කර ඇත.",
        "welcome_default": "{groupname} වෙත {mention} සාදරයෙන් පිළිගනිමු!",
        "goodbye_default": "ආයුබෝවන් {mention}!",
        "captcha_prompt": "👋 සාදරයෙන් පිළිගනිමු {mention}! විසඳන්න: {a} + {b} = ?",
        "captcha_wrong": "❌ වැරදියි! නැවත උත්සාහ කරන්න.",
        "captcha_correct": "✅ නිවැරදියි! සාදරයෙන් පිළිගනිමු {mention}!",
        "captcha_timeout": "⏰ {mention} captcha විසඳීමට අසමත් වී ඉවත් කරන ලදී.",
        "settings_admin_only": "පාලකයන්ට පමණක් /settings භාවිතා කළ හැක.",
        "where_open": "සැකසුම් මෙනුව කොතැන විවෘත කළ යුතු ද?",
        "open_here": "👥 මෙහි විවෘත කරන්න",
        "open_private": "👤 පුද්ගලික සංවාදයේ විවෘත කරන්න",
        "settings_closed": "සැකසුම් වසා ඇත.",
        "lang_changed": "අවසන් — දැන් මම මෙහි සිංහලෙන් කතා කරමි.",
        "user_lang_changed": "✅ ඔබේ භාෂාව දැන් {lang}. සියලු පණිවිඩ මෙම භාෂාවෙන් පෙන්වේ.",
        "rules_updated": "✅ නීති යාවත්කාලීන කරන ලදී.",
        "rules_cleared": "✅ නීති මකා දමා ඇත.",
        "no_rules": "නීති සකසා නැත.",
        "perms_title": "🕹 අවසර\n👤 {handle} [{uid}]\n👥 {groupname}",
        "perms_saved": "✅ {user} සඳහා අවසර සුරැකින ලදී.",
        "perm_text": "පෙළ පණිවිඩ",
        "perm_photo": "ඡායාරූප",
        "perm_video": "වීඩියෝ",
        "perm_sticker": "ස්ටිකර්/GIF",
        "perm_audio": "ශ්‍රව්‍ය",
        "perm_voice": "හඬ පණිවිඩය",
        "perm_file": "ගොනුව",
        "perm_roundvideo": "වෘත්තාකාර වීඩියෝ",
        "perm_polls": "මත විමසුම්",
        "perm_links": "සබැඳි පෙරදසුන සක්‍රිය කරන්න",
        "perm_tag": "ඔබේම tag සකසන්න",
        "perm_save_btn": "සුරකින්න ✓",
        "cancelled": "❌ අවලංගු කළා.",
        "done": "✅ අවසන්.",
        "error": "❌ දෝෂය: {msg}",
        "admins_only": "❌ පාලකයන්ට පමණයි.",
        "reply_required": "❌ පළමුව පණිවිඩයකට පිළිතුරු දෙන්න.",
        "user_not_found": "❌ පරිශීලකයා හමු නොවීය.",
        "invalid_args": "❌ වලංගු නොවන තර්ක.",
    },
}


# ----------------------------------------------------------------------
# AUTO_TRANSLATE: english phrase -> {lang_code: translation}.
#
# The bot patches Message.reply_text / Bot.send_message to look the
# outgoing English phrase up here and substitute the active language.
# Phrases not present here are sent through unchanged.
# ----------------------------------------------------------------------
AUTO_TRANSLATE: Dict[str, Dict[str, str]] = {
    # ----- Admin gates -----
    "Only administrators can use /settings.": {
        "hi": "Sirf admins /settings use kar sakte hain.",
        "bn": "শুধু অ্যাডমিনরা /settings ব্যবহার করতে পারবেন।",
        "ur": "صرف ایڈمن /settings استعمال کر سکتے ہیں۔",
        "ar": "يمكن للمشرفين فقط استخدام /settings.",
        "es": "Solo los administradores pueden usar /settings.",
        "fr": "Seuls les administrateurs peuvent utiliser /settings.",
        "de": "Nur Administratoren können /settings verwenden.",
        "ru": "Только администраторы могут использовать /settings.",
        "zh": "只有管理员可以使用 /settings。",
        "zt": "只有管理員可以使用 /settings。",
        "pt": "Apenas administradores podem usar /settings.",
        "id": "Hanya admin yang dapat menggunakan /settings.",
        "tr": "Yalnızca yöneticiler /settings komutunu kullanabilir.",
        "it": "Solo gli amministratori possono usare /settings.",
        "ro": "Doar administratorii pot folosi /settings.",
        "nl": "Alleen beheerders kunnen /settings gebruiken.",
        "uk": "Лише адміністратори можуть використовувати /settings.",
        "fa": "فقط مدیران می‌توانند /settings را استفاده کنند.",
        "he": "רק מנהלים יכולים להשתמש ב-/settings.",
        "ko": "관리자만 /settings를 사용할 수 있습니다.",
        "el": "Μόνο διαχειριστές μπορούν να χρησιμοποιήσουν /settings.",
    },
    "Admins/moderators only.": {
        "hi": "Sirf admins/moderators ke liye.",
        "bn": "শুধু অ্যাডমিন/মডারেটরদের জন্য।",
        "ur": "صرف ایڈمنز/ماڈریٹرز کے لیے۔",
        "ar": "للمشرفين/المعدّلين فقط.",
        "es": "Solo administradores/moderadores.",
        "fr": "Réservé aux admins/modérateurs.",
        "de": "Nur für Admins/Moderatoren.",
        "ru": "Только для администраторов/модераторов.",
        "zh": "仅限管理员/版主。",
        "zt": "僅限管理員/版主。",
        "pt": "Apenas administradores/moderadores.",
        "id": "Hanya admin/moderator.",
        "tr": "Sadece yöneticiler/moderatörler.",
        "it": "Solo amministratori/moderatori.",
        "ro": "Doar administratori/moderatori.",
        "nl": "Alleen beheerders/moderators.",
        "uk": "Лише для адміністраторів/модераторів.",
        "fa": "فقط مدیران/ناظمان.",
        "he": "רק מנהלים/מודרטורים.",
        "ko": "관리자/모더레이터 전용.",
        "el": "Μόνο διαχειριστές/συντονιστές.",
    },
    "❌ Admins only.": {
        "hi": "❌ Sirf admins ke liye.", "bn": "❌ শুধু অ্যাডমিনদের জন্য।",
        "ur": "❌ صرف ایڈمنز کے لیے۔", "ar": "❌ للمشرفين فقط.",
        "es": "❌ Solo administradores.", "fr": "❌ Réservé aux administrateurs.",
        "de": "❌ Nur für Admins.", "ru": "❌ Только для администраторов.",
        "zh": "❌ 仅限管理员。", "zt": "❌ 僅限管理員。",
        "pt": "❌ Apenas administradores.", "id": "❌ Hanya admin.",
        "tr": "❌ Sadece yöneticiler.", "it": "❌ Solo amministratori.",
        "ro": "❌ Doar administratori.", "nl": "❌ Alleen beheerders.",
        "uk": "❌ Лише адміністратори.", "fa": "❌ فقط مدیران.",
        "he": "❌ רק מנהלים.", "ko": "❌ 관리자 전용.",
        "el": "❌ Μόνο διαχειριστές.",
    },
    "Admins needed!": {
        "hi": "Admins ki zarurat hai!", "bn": "অ্যাডমিন দরকার!",
        "ur": "ایڈمنز کی ضرورت ہے!", "ar": "نحتاج إلى مشرفين!",
        "es": "¡Se necesitan administradores!", "fr": "Admins requis !",
        "de": "Admins benötigt!", "ru": "Нужны администраторы!",
        "zh": "需要管理员！", "zt": "需要管理員！",
        "pt": "Precisa de administradores!", "id": "Butuh admin!",
        "tr": "Yöneticiler gerekli!", "it": "Servono amministratori!",
        "ro": "Sunt necesari administratori!", "nl": "Beheerders nodig!",
        "uk": "Потрібні адміністратори!", "fa": "به مدیران نیاز است!",
        "he": "צריך מנהלים!", "ko": "관리자가 필요합니다!",
        "el": "Χρειάζονται διαχειριστές!",
    },
    # ----- Targeting / replies -----
    "Reply to a user, or pass an @username / user id.": {
        "hi": "Kisi user ko reply karo, ya @username / user-id do.",
        "bn": "ইউজারকে রিপ্লাই করুন, অথবা @username / user-id দিন।",
        "ur": "صارف کو ریپلائی کریں، یا @username / user-id بھیجیں۔",
        "ar": "ردّ على مستخدم أو أرسل @username / user-id.",
        "es": "Responde a un usuario o pasa @username / user-id.",
        "fr": "Réponds à un utilisateur ou passe @username / user-id.",
        "de": "Antworte einem Nutzer oder übergib @username / user-id.",
        "ru": "Ответь пользователю или укажи @username / user-id.",
        "zh": "请回复某用户或提供 @username / 用户 ID。",
        "zt": "請回覆某用戶或提供 @username / 使用者 ID。",
        "pt": "Responda a um utilizador ou passe @username / user-id.",
        "id": "Balas user atau berikan @username / user-id.",
        "tr": "Bir kullanıcıya cevap ver veya @kullanici / id geç.",
        "it": "Rispondi a un utente o passa @username / id.",
        "ro": "Răspunde unui utilizator sau dă @username / id.",
        "nl": "Reageer op een gebruiker of geef @username / id.",
        "uk": "Дай відповідь користувачу або вкажи @username / id.",
        "fa": "به یک کاربر پاسخ دهید یا @username / user-id بدهید.",
        "he": "השב למשתמש או העבר @username / user-id.",
        "ko": "사용자에게 답장하거나 @username / 사용자 ID를 입력하세요.",
        "el": "Απάντησε σε χρήστη ή δώσε @username / user-id.",
    },
    "Reply to a user, or pass @username / user-id.": {
        "hi": "Kisi user ko reply karo, ya @username / user-id do.",
        "bn": "ইউজারকে রিপ্লাই করুন, অথবা @username / user-id দিন।",
        "ur": "صارف کو ریپلائی کریں، یا @username / user-id بھیجیں۔",
        "ar": "ردّ على مستخدم أو أرسل @username / user-id.",
        "es": "Responde a un usuario o pasa @username / user-id.",
        "fr": "Réponds à un utilisateur ou passe @username / user-id.",
        "de": "Antworte einem Nutzer oder übergib @username / user-id.",
        "ru": "Ответь пользователю или укажи @username / user-id.",
        "zh": "请回复某用户或提供 @username / 用户 ID。",
        "zt": "請回覆某用戶或提供 @username / 使用者 ID。",
        "pt": "Responda a um utilizador ou passe @username / user-id.",
        "id": "Balas user atau berikan @username / user-id.",
        "tr": "Bir kullanıcıya cevap ver veya @kullanici / id geç.",
        "it": "Rispondi a un utente o passa @username / id.",
        "ro": "Răspunde unui utilizator sau dă @username / id.",
        "nl": "Reageer op een gebruiker of geef @username / id.",
        "uk": "Дай відповідь користувачу або вкажи @username / id.",
        "fa": "به یک کاربر پاسخ دهید یا @username / user-id بدهید.",
        "he": "השב למשתמש או העבר @username / user-id.",
        "ko": "사용자에게 답장하거나 @username / 사용자 ID를 입력하세요.",
        "el": "Απάντησε σε χρήστη ή δώσε @username / user-id.",
    },
    "❌ User not found.": {
        "hi": "❌ User nahi mila.", "bn": "❌ ইউজার পাওয়া যায়নি।",
        "ur": "❌ صارف نہیں ملا۔", "ar": "❌ المستخدم غير موجود.",
        "es": "❌ Usuario no encontrado.", "fr": "❌ Utilisateur introuvable.",
        "de": "❌ Nutzer nicht gefunden.", "ru": "❌ Пользователь не найден.",
        "zh": "❌ 找不到该用户。", "zt": "❌ 找不到該使用者。",
        "pt": "❌ Utilizador não encontrado.", "id": "❌ Pengguna tidak ditemukan.",
        "tr": "❌ Kullanıcı bulunamadı.", "it": "❌ Utente non trovato.",
        "ro": "❌ Utilizator negăsit.", "nl": "❌ Gebruiker niet gevonden.",
        "uk": "❌ Користувача не знайдено.", "fa": "❌ کاربر پیدا نشد.",
        "he": "❌ המשתמש לא נמצא.", "ko": "❌ 사용자를 찾을 수 없습니다.",
        "el": "❌ Χρήστης δεν βρέθηκε.",
    },
    "❌ I don't have permission for this.": {
        "hi": "❌ Mujhe iski permission nahi hai.",
        "bn": "❌ এই কাজের অনুমতি আমার নেই।",
        "ur": "❌ مجھے اس کی اجازت نہیں۔",
        "ar": "❌ ليس لدي صلاحية لذلك.",
        "es": "❌ No tengo permiso para esto.",
        "fr": "❌ Je n'ai pas la permission.",
        "de": "❌ Ich habe nicht die Berechtigung dafür.",
        "ru": "❌ У меня нет нужных прав.",
        "zh": "❌ 我没有相应的权限。",
        "zt": "❌ 我沒有相應的權限。",
        "pt": "❌ Não tenho permissão para isto.",
        "id": "❌ Saya tidak punya izin.",
        "tr": "❌ Bunun için iznim yok.",
        "it": "❌ Non ho il permesso.",
        "ro": "❌ Nu am permisiunea.",
        "nl": "❌ Ik heb hier geen rechten voor.",
        "uk": "❌ У мене немає прав.",
        "fa": "❌ من اجازهٔ این کار را ندارم.",
        "he": "❌ אין לי הרשאה לכך.",
        "ko": "❌ 권한이 없습니다.",
        "el": "❌ Δεν έχω δικαίωμα.",
    },
    # ----- Generic confirmations -----
    "✅ Done.": {
        "hi": "✅ Ho gaya.", "bn": "✅ সম্পন্ন।", "ur": "✅ ہو گیا۔",
        "ar": "✅ تم.", "es": "✅ Hecho.", "fr": "✅ Fait.",
        "de": "✅ Erledigt.", "ru": "✅ Готово.", "zh": "✅ 完成。",
        "zt": "✅ 完成。", "pt": "✅ Pronto.", "id": "✅ Selesai.",
        "tr": "✅ Tamam.", "it": "✅ Fatto.", "ro": "✅ Gata.",
        "nl": "✅ Klaar.", "uk": "✅ Готово.", "fa": "✅ انجام شد.",
        "he": "✅ בוצע.", "ko": "✅ 완료.", "el": "✅ Έτοιμο.",
    },
    "❌ Cancelled.": {
        "hi": "❌ Cancel kar diya.", "bn": "❌ বাতিল।", "ur": "❌ منسوخ۔",
        "ar": "❌ تم الإلغاء.", "es": "❌ Cancelado.", "fr": "❌ Annulé.",
        "de": "❌ Abgebrochen.", "ru": "❌ Отменено.", "zh": "❌ 已取消。",
        "zt": "❌ 已取消。", "pt": "❌ Cancelado.", "id": "❌ Dibatalkan.",
        "tr": "❌ İptal edildi.", "it": "❌ Annullato.", "ro": "❌ Anulat.",
        "nl": "❌ Geannuleerd.", "uk": "❌ Скасовано.", "fa": "❌ لغو شد.",
        "he": "❌ בוטל.", "ko": "❌ 취소됨.", "el": "❌ Ακυρώθηκε.",
    },
    "Settings closed.": {
        "hi": "Settings band kar diye.", "bn": "সেটিংস বন্ধ।",
        "ur": "سیٹنگز بند۔", "ar": "تم إغلاق الإعدادات.",
        "es": "Ajustes cerrados.", "fr": "Paramètres fermés.",
        "de": "Einstellungen geschlossen.", "ru": "Настройки закрыты.",
        "zh": "设置已关闭。", "zt": "設定已關閉。",
        "pt": "Definições fechadas.", "id": "Pengaturan ditutup.",
        "tr": "Ayarlar kapatıldı.", "it": "Impostazioni chiuse.",
        "ro": "Setări închise.", "nl": "Instellingen gesloten.",
        "uk": "Налаштування закрито.", "fa": "تنظیمات بسته شد.",
        "he": "הגדרות נסגרו.", "ko": "설정이 닫혔습니다.",
        "el": "Οι ρυθμίσεις έκλεισαν.",
    },
    "Where do you want to open the settings menu?": {
        "hi": "Settings menu kahaan kholna hai?",
        "bn": "সেটিংস মেনু কোথায় খুলবেন?",
        "ur": "سیٹنگز مینو کہاں کھولنا ہے؟",
        "ar": "أين تريد فتح قائمة الإعدادات؟",
        "es": "¿Dónde quieres abrir el menú de ajustes?",
        "fr": "Où veux-tu ouvrir le menu des paramètres ?",
        "de": "Wo soll das Einstellungsmenü geöffnet werden?",
        "ru": "Где открыть меню настроек?",
        "zh": "在哪里打开设置菜单？",
        "zt": "在哪裡打開設定選單？",
        "pt": "Onde queres abrir o menu de definições?",
        "id": "Di mana mau membuka menu pengaturan?",
        "tr": "Ayarlar menüsünü nerede açmak istiyorsun?",
        "it": "Dove vuoi aprire il menu impostazioni?",
        "ro": "Unde vrei să deschizi meniul setări?",
        "nl": "Waar wil je het instellingenmenu openen?",
        "uk": "Де відкрити меню налаштувань?",
        "fa": "منوی تنظیمات را کجا باز کنیم؟",
        "he": "איפה לפתוח את תפריט ההגדרות?",
        "ko": "설정 메뉴를 어디서 열까요?",
        "el": "Πού να ανοίξουμε το μενού ρυθμίσεων;",
    },
    # ----- Rules -----
    "✅ Rules updated.": {
        "hi": "✅ Rules update ho gaye.", "bn": "✅ নিয়ম আপডেট হলো।",
        "ur": "✅ قواعد اپ ڈیٹ ہو گئے۔", "ar": "✅ تم تحديث القواعد.",
        "es": "✅ Reglas actualizadas.", "fr": "✅ Règles mises à jour.",
        "de": "✅ Regeln aktualisiert.", "ru": "✅ Правила обновлены.",
        "zh": "✅ 规则已更新。", "zt": "✅ 規則已更新。",
        "pt": "✅ Regras atualizadas.", "id": "✅ Aturan diperbarui.",
        "tr": "✅ Kurallar güncellendi.", "it": "✅ Regole aggiornate.",
        "ro": "✅ Reguli actualizate.", "nl": "✅ Regels bijgewerkt.",
        "uk": "✅ Правила оновлено.", "fa": "✅ قوانین به‌روزرسانی شد.",
        "he": "✅ הכללים עודכנו.", "ko": "✅ 규칙이 업데이트되었습니다.",
        "el": "✅ Οι κανόνες ενημερώθηκαν.",
    },
    "✅ Rules cleared.": {
        "hi": "✅ Rules saaf kar diye.", "bn": "✅ নিয়ম মোছা হলো।",
        "ur": "✅ قواعد صاف کر دیے۔", "ar": "✅ تم مسح القواعد.",
        "es": "✅ Reglas borradas.", "fr": "✅ Règles effacées.",
        "de": "✅ Regeln gelöscht.", "ru": "✅ Правила удалены.",
        "zh": "✅ 规则已清除。", "zt": "✅ 規則已清除。",
        "pt": "✅ Regras apagadas.", "id": "✅ Aturan dihapus.",
        "tr": "✅ Kurallar temizlendi.", "it": "✅ Regole cancellate.",
        "ro": "✅ Reguli șterse.", "nl": "✅ Regels gewist.",
        "uk": "✅ Правила очищено.", "fa": "✅ قوانین پاک شد.",
        "he": "✅ הכללים נמחקו.", "ko": "✅ 규칙이 삭제되었습니다.",
        "el": "✅ Οι κανόνες διαγράφηκαν.",
    },
    "No rules set.": {
        "hi": "Koi rules set nahi hain.", "bn": "কোনো নিয়ম সেট নেই।",
        "ur": "کوئی قاعدہ سیٹ نہیں۔", "ar": "لا توجد قواعد.",
        "es": "No hay reglas configuradas.", "fr": "Aucune règle définie.",
        "de": "Keine Regeln gesetzt.", "ru": "Правила не заданы.",
        "zh": "未设置规则。", "zt": "未設定規則。",
        "pt": "Sem regras definidas.", "id": "Belum ada aturan.",
        "tr": "Kural tanımlı değil.", "it": "Nessuna regola impostata.",
        "ro": "Nicio regulă setată.", "nl": "Geen regels ingesteld.",
        "uk": "Правил не задано.", "fa": "هیچ قانونی تنظیم نشده.",
        "he": "לא הוגדרו כללים.", "ko": "규칙이 설정되지 않았습니다.",
        "el": "Δεν έχουν οριστεί κανόνες.",
    },
    # ----- Notes / Filters / Blacklist -----
    "No notes in this chat.": {
        "hi": "Is chat me koi note nahi hai.", "bn": "এই চ্যাটে কোনো নোট নেই।",
        "ur": "اس چیٹ میں کوئی نوٹ نہیں۔", "ar": "لا توجد ملاحظات في هذه المحادثة.",
        "es": "No hay notas en este chat.", "fr": "Aucune note dans ce chat.",
        "de": "Keine Notizen in diesem Chat.", "ru": "В этом чате нет заметок.",
        "zh": "此聊天中没有记事。", "zt": "此聊天中沒有筆記。",
        "pt": "Sem notas neste chat.", "id": "Tidak ada catatan di chat ini.",
        "tr": "Bu sohbette not yok.", "it": "Nessuna nota in questa chat.",
        "ro": "Nicio notă în acest chat.", "nl": "Geen notities in deze chat.",
        "uk": "У цьому чаті немає нотаток.", "fa": "در این چت یادداشتی نیست.",
        "he": "אין הערות בצ'אט זה.", "ko": "이 채팅에 메모가 없습니다.",
        "el": "Δεν υπάρχουν σημειώσεις σε αυτή τη συνομιλία.",
    },
    "No filters configured here.": {
        "hi": "Yahaan koi filter nahi hai.", "bn": "এখানে কোনো ফিল্টার নেই।",
        "ur": "یہاں کوئی فلٹر نہیں۔", "ar": "لا توجد فلاتر هنا.",
        "es": "Sin filtros configurados aquí.", "fr": "Aucun filtre configuré ici.",
        "de": "Hier sind keine Filter konfiguriert.", "ru": "Фильтры здесь не настроены.",
        "zh": "此处未配置过滤器。", "zt": "此處未設定過濾器。",
        "pt": "Sem filtros configurados aqui.", "id": "Tidak ada filter di sini.",
        "tr": "Burada filtre yok.", "it": "Nessun filtro configurato qui.",
        "ro": "Nu sunt filtre configurate aici.", "nl": "Geen filters ingesteld.",
        "uk": "Тут не налаштовано фільтрів.", "fa": "هیچ فیلتری اینجا تنظیم نشده.",
        "he": "אין מסננים מוגדרים כאן.", "ko": "여기에는 필터가 없습니다.",
        "el": "Δεν έχουν οριστεί φίλτρα εδώ.",
    },
    "Blacklist is empty.": {
        "hi": "Blacklist khaali hai.", "bn": "ব্ল্যাকলিস্ট খালি।",
        "ur": "بلیک لسٹ خالی ہے۔", "ar": "القائمة السوداء فارغة.",
        "es": "La lista negra está vacía.", "fr": "La liste noire est vide.",
        "de": "Schwarze Liste ist leer.", "ru": "Чёрный список пуст.",
        "zh": "黑名单为空。", "zt": "黑名單為空。",
        "pt": "Lista negra vazia.", "id": "Daftar hitam kosong.",
        "tr": "Kara liste boş.", "it": "La lista nera è vuota.",
        "ro": "Lista neagră este goală.", "nl": "Zwarte lijst is leeg.",
        "uk": "Чорний список порожній.", "fa": "لیست سیاه خالی است.",
        "he": "הרשימה השחורה ריקה.", "ko": "차단 목록이 비어 있습니다.",
        "el": "Η μαύρη λίστα είναι κενή.",
    },
    "Removed.": {
        "hi": "Hata diya.", "bn": "সরানো হলো।", "ur": "ہٹا دیا۔",
        "ar": "تمت الإزالة.", "es": "Eliminado.", "fr": "Supprimé.",
        "de": "Entfernt.", "ru": "Удалено.", "zh": "已移除。",
        "zt": "已移除。", "pt": "Removido.", "id": "Dihapus.",
        "tr": "Kaldırıldı.", "it": "Rimosso.", "ro": "Eliminat.",
        "nl": "Verwijderd.", "uk": "Видалено.", "fa": "حذف شد.",
        "he": "הוסר.", "ko": "제거됨.", "el": "Αφαιρέθηκε.",
    },
    "Sent in DM.": {
        "hi": "DM me bhej diya.", "bn": "DM-এ পাঠানো হয়েছে।",
        "ur": "DM میں بھیج دیا۔", "ar": "تم الإرسال في الخاص.",
        "es": "Enviado por DM.", "fr": "Envoyé en DM.",
        "de": "Per DM gesendet.", "ru": "Отправлено в ЛС.",
        "zh": "已私聊发送。", "zt": "已私訊發送。",
        "pt": "Enviado por DM.", "id": "Dikirim via DM.",
        "tr": "DM olarak gönderildi.", "it": "Inviato in DM.",
        "ro": "Trimis în DM.", "nl": "Verzonden via DM.",
        "uk": "Надіслано в ЛС.", "fa": "در پیام خصوصی فرستاده شد.",
        "he": "נשלח בהודעה פרטית.", "ko": "DM으로 전송됨.",
        "el": "Στάλθηκε σε DM.",
    },
    # ----- Locks / Connection -----
    "❌ Unknown lock type. Try /locktypes.": {
        "hi": "❌ Lock type pata nahi. /locktypes try karo.",
        "bn": "❌ অজানা লক টাইপ। /locktypes দেখুন।",
        "ur": "❌ نامعلوم لاک قسم۔ /locktypes دیکھیں۔",
        "ar": "❌ نوع قفل غير معروف. جرّب /locktypes.",
        "es": "❌ Tipo de bloqueo desconocido. Prueba /locktypes.",
        "fr": "❌ Type de verrou inconnu. Essaie /locktypes.",
        "de": "❌ Unbekannter Sperrtyp. Versuche /locktypes.",
        "ru": "❌ Неизвестный тип блокировки. Попробуй /locktypes.",
        "zh": "❌ 未知的锁定类型，试试 /locktypes。",
        "zt": "❌ 未知的鎖定類型，試試 /locktypes。",
        "pt": "❌ Tipo de bloqueio desconhecido. Tenta /locktypes.",
        "id": "❌ Tipe lock tidak dikenal. Coba /locktypes.",
        "tr": "❌ Bilinmeyen kilit türü. /locktypes deneyin.",
        "it": "❌ Tipo di blocco sconosciuto. Prova /locktypes.",
        "ro": "❌ Tip de blocaj necunoscut. Încearcă /locktypes.",
        "nl": "❌ Onbekend sloottype. Probeer /locktypes.",
        "uk": "❌ Невідомий тип блокування. Спробуй /locktypes.",
        "fa": "❌ نوع قفل ناشناخته. /locktypes را امتحان کنید.",
        "he": "❌ סוג נעילה לא ידוע. נסה /locktypes.",
        "ko": "❌ 알 수 없는 잠금 유형입니다. /locktypes를 시도하세요.",
        "el": "❌ Άγνωστος τύπος κλειδώματος. Δοκιμάστε /locktypes.",
    },
    "Disconnected.": {
        "hi": "Disconnect ho gaya.", "bn": "সংযোগ বিচ্ছিন্ন।",
        "ur": "ڈسکنیکٹ ہو گیا۔", "ar": "تم قطع الاتصال.",
        "es": "Desconectado.", "fr": "Déconnecté.",
        "de": "Verbindung getrennt.", "ru": "Отключено.",
        "zh": "已断开连接。", "zt": "已斷開連線。",
        "pt": "Desligado.", "id": "Terputus.",
        "tr": "Bağlantı kesildi.", "it": "Disconnesso.",
        "ro": "Deconectat.", "nl": "Verbinding verbroken.",
        "uk": "Відключено.", "fa": "قطع شد.",
        "he": "מנותק.", "ko": "연결 해제됨.",
        "el": "Αποσυνδέθηκε.",
    },
    "Not connected to any chat.": {
        "hi": "Kisi chat se connect nahi hai.", "bn": "কোনো চ্যাটে সংযুক্ত নয়।",
        "ur": "کسی چیٹ سے کنیکٹ نہیں۔", "ar": "غير متصل بأي محادثة.",
        "es": "No conectado a ningún chat.", "fr": "Connecté à aucun chat.",
        "de": "Mit keinem Chat verbunden.", "ru": "Не подключено ни к одному чату.",
        "zh": "未连接任何聊天。", "zt": "未連線任何聊天。",
        "pt": "Não conectado a nenhum chat.", "id": "Tidak terhubung ke chat manapun.",
        "tr": "Hiçbir sohbete bağlı değil.", "it": "Nessuna chat connessa.",
        "ro": "Neconectat la niciun chat.", "nl": "Niet met een chat verbonden.",
        "uk": "Не під'єднано до жодного чату.", "fa": "به هیچ چتی متصل نیست.",
        "he": "לא מחובר לאף צ'אט.", "ko": "연결된 채팅이 없습니다.",
        "el": "Δεν συνδέεται σε κανένα chat.",
    },
    # ----- Self / cross-admin guards -----
    "You can't warn yourself.": {
        "hi": "Khud ko warn nahi kar sakte.", "bn": "নিজেকে সতর্ক করা যাবে না।",
        "ur": "خود کو وارن نہیں کر سکتے۔", "ar": "لا يمكنك تحذير نفسك.",
        "es": "No puedes advertirte a ti mismo.", "fr": "Tu ne peux pas t'avertir toi-même.",
        "de": "Du kannst dich nicht selbst verwarnen.", "ru": "Нельзя предупреждать себя.",
        "zh": "你不能警告自己。", "zt": "你不能警告自己。",
        "pt": "Não te podes avisar a ti próprio.", "id": "Tidak bisa memperingatkan diri sendiri.",
        "tr": "Kendini uyaramazsın.", "it": "Non puoi avvertire te stesso.",
        "ro": "Nu te poți avertiza pe tine.", "nl": "Je kunt jezelf niet waarschuwen.",
        "uk": "Не можна попередити себе.", "fa": "نمی‌توانید خودتان را اخطار دهید.",
        "he": "אי אפשר להזהיר את עצמך.", "ko": "자기 자신을 경고할 수 없습니다.",
        "el": "Δεν μπορείς να προειδοποιήσεις τον εαυτό σου.",
    },
    "I can't warn another admin.": {
        "hi": "Doosre admin ko warn nahi kar sakta.",
        "bn": "অন্য অ্যাডমিনকে সতর্ক করা যাবে না।",
        "ur": "دوسرے ایڈمن کو وارن نہیں کر سکتا۔",
        "ar": "لا يمكنني تحذير مشرف آخر.",
        "es": "No puedo advertir a otro admin.",
        "fr": "Je ne peux pas avertir un autre admin.",
        "de": "Ich kann keinen anderen Admin verwarnen.",
        "ru": "Я не могу предупредить другого админа.",
        "zh": "我不能警告其他管理员。",
        "zt": "我不能警告其他管理員。",
        "pt": "Não posso avisar outro admin.",
        "id": "Tidak bisa memperingatkan admin lain.",
        "tr": "Başka bir yöneticiyi uyaramam.",
        "it": "Non posso avvertire un altro admin.",
        "ro": "Nu pot avertiza alt admin.",
        "nl": "Ik kan een andere admin niet waarschuwen.",
        "uk": "Не можу попередити іншого адміна.",
        "fa": "نمی‌توانم به ادمین دیگر اخطار دهم.",
        "he": "אני לא יכול להזהיר מנהל אחר.",
        "ko": "다른 관리자를 경고할 수 없습니다.",
        "el": "Δεν μπορώ να προειδοποιήσω άλλον διαχειριστή.",
    },
    "You can't ban yourself.": {
        "hi": "Khud ko ban nahi kar sakte.", "bn": "নিজেকে ব্যান করা যাবে না।",
        "ur": "خود کو بین نہیں کر سکتے۔", "ar": "لا يمكنك حظر نفسك.",
        "es": "No puedes banearte a ti mismo.", "fr": "Tu ne peux pas te bannir toi-même.",
        "de": "Du kannst dich nicht selbst bannen.", "ru": "Нельзя забанить себя.",
        "zh": "你不能封禁自己。", "zt": "你不能封禁自己。",
        "pt": "Não te podes banir a ti próprio.", "id": "Tidak bisa banned diri sendiri.",
        "tr": "Kendini banlayamazsın.", "it": "Non puoi bannarti.",
        "ro": "Nu te poți bana pe tine.", "nl": "Je kunt jezelf niet verbannen.",
        "uk": "Не можна забанити себе.", "fa": "نمی‌توانید خودتان را مسدود کنید.",
        "he": "אי אפשר לחסום את עצמך.", "ko": "자기 자신을 차단할 수 없습니다.",
        "el": "Δεν μπορείς να αποκλείσεις τον εαυτό σου.",
    },
    "I can't ban another admin.": {
        "hi": "Doosre admin ko ban nahi kar sakta.",
        "bn": "অন্য অ্যাডমিনকে ব্যান করা যাবে না।",
        "ur": "دوسرے ایڈمن کو بین نہیں کر سکتا۔",
        "ar": "لا يمكنني حظر مشرف آخر.",
        "es": "No puedo banear a otro admin.",
        "fr": "Je ne peux pas bannir un autre admin.",
        "de": "Ich kann keinen anderen Admin bannen.",
        "ru": "Я не могу забанить другого админа.",
        "zh": "我不能封禁其他管理员。",
        "zt": "我不能封禁其他管理員。",
        "pt": "Não posso banir outro admin.",
        "id": "Tidak bisa banned admin lain.",
        "tr": "Başka bir yöneticiyi banlayamam.",
        "it": "Non posso bannare un altro admin.",
        "ro": "Nu pot bana alt admin.",
        "nl": "Ik kan een andere admin niet verbannen.",
        "uk": "Не можу забанити іншого адміна.",
        "fa": "نمی‌توانم ادمین دیگر را مسدود کنم.",
        "he": "אני לא יכול לחסום מנהל אחר.",
        "ko": "다른 관리자를 차단할 수 없습니다.",
        "el": "Δεν μπορώ να αποκλείσω άλλον διαχειριστή.",
    },
    "You can't mute yourself.": {
        "hi": "Khud ko mute nahi kar sakte.", "bn": "নিজেকে মিউট করা যাবে না।",
        "ur": "خود کو میوٹ نہیں کر سکتے۔", "ar": "لا يمكنك كتم نفسك.",
        "es": "No puedes silenciarte a ti mismo.", "fr": "Tu ne peux pas te mute toi-même.",
        "de": "Du kannst dich nicht selbst stummschalten.", "ru": "Нельзя замутить себя.",
        "zh": "你不能禁言自己。", "zt": "你不能禁言自己。",
        "pt": "Não te podes silenciar a ti próprio.", "id": "Tidak bisa membisukan diri sendiri.",
        "tr": "Kendini sessize alamazsın.", "it": "Non puoi silenziarti.",
        "ro": "Nu te poți silenția pe tine.", "nl": "Je kunt jezelf niet dempen.",
        "uk": "Не можна замутити себе.", "fa": "نمی‌توانید خودتان را ساکت کنید.",
        "he": "אי אפשר להשתיק את עצמך.", "ko": "자기 자신을 음소거할 수 없습니다.",
        "el": "Δεν μπορείς να σιγάσεις τον εαυτό σου.",
    },
    "I can't mute another admin.": {
        "hi": "Doosre admin ko mute nahi kar sakta.",
        "bn": "অন্য অ্যাডমিনকে মিউট করা যাবে না।",
        "ur": "دوسرے ایڈمن کو میوٹ نہیں کر سکتا۔",
        "ar": "لا يمكنني كتم مشرف آخر.",
        "es": "No puedo silenciar a otro admin.",
        "fr": "Je ne peux pas mute un autre admin.",
        "de": "Ich kann keinen anderen Admin stummschalten.",
        "ru": "Я не могу замутить другого админа.",
        "zh": "我不能禁言其他管理员。",
        "zt": "我不能禁言其他管理員。",
        "pt": "Não posso silenciar outro admin.",
        "id": "Tidak bisa membisukan admin lain.",
        "tr": "Başka bir yöneticiyi sessize alamam.",
        "it": "Non posso silenziare un altro admin.",
        "ro": "Nu pot silenția alt admin.",
        "nl": "Ik kan een andere admin niet dempen.",
        "uk": "Не можу замутити іншого адміна.",
        "fa": "نمی‌توانم ادمین دیگر را ساکت کنم.",
        "he": "אני לא יכול להשתיק מנהל אחר.",
        "ko": "다른 관리자를 음소거할 수 없습니다.",
        "el": "Δεν μπορώ να σιγάσω άλλον διαχειριστή.",
    },
    "You can't kick yourself.": {
        "hi": "Khud ko kick nahi kar sakte.", "bn": "নিজেকে কিক করা যাবে না।",
        "ur": "خود کو کک نہیں کر سکتے۔", "ar": "لا يمكنك طرد نفسك.",
        "es": "No puedes expulsarte a ti mismo.", "fr": "Tu ne peux pas t'expulser toi-même.",
        "de": "Du kannst dich nicht selbst kicken.", "ru": "Нельзя кикнуть себя.",
        "zh": "你不能踢自己。", "zt": "你不能踢自己。",
        "pt": "Não te podes expulsar a ti próprio.", "id": "Tidak bisa kick diri sendiri.",
        "tr": "Kendini atamazsın.", "it": "Non puoi espellerti.",
        "ro": "Nu te poți da afară pe tine.", "nl": "Je kunt jezelf niet kicken.",
        "uk": "Не можна кікнути себе.", "fa": "نمی‌توانید خودتان را اخراج کنید.",
        "he": "אי אפשר להוציא את עצמך.", "ko": "자기 자신을 강퇴할 수 없습니다.",
        "el": "Δεν μπορείς να αποβάλεις τον εαυτό σου.",
    },
    "I can't kick another admin.": {
        "hi": "Doosre admin ko kick nahi kar sakta.",
        "bn": "অন্য অ্যাডমিনকে কিক করা যাবে না।",
        "ur": "دوسرے ایڈمن کو کک نہیں کر سکتا۔",
        "ar": "لا يمكنني طرد مشرف آخر.",
        "es": "No puedo expulsar a otro admin.",
        "fr": "Je ne peux pas expulser un autre admin.",
        "de": "Ich kann keinen anderen Admin kicken.",
        "ru": "Я не могу кикнуть другого админа.",
        "zh": "我不能踢其他管理员。",
        "zt": "我不能踢其他管理員。",
        "pt": "Não posso expulsar outro admin.",
        "id": "Tidak bisa kick admin lain.",
        "tr": "Başka bir yöneticiyi atamam.",
        "it": "Non posso espellere un altro admin.",
        "ro": "Nu pot da afară alt admin.",
        "nl": "Ik kan een andere admin niet kicken.",
        "uk": "Не можу кікнути іншого адміна.",
        "fa": "نمی‌توانم ادمین دیگر را اخراج کنم.",
        "he": "אני לא יכול להוציא מנהל אחר.",
        "ko": "다른 관리자를 강퇴할 수 없습니다.",
        "el": "Δεν μπορώ να αποβάλω άλλον διαχειριστή.",
    },
    "No warns to remove.": {
        "hi": "Hata\u200d\u200dne ke liye koi warn nahi.",
        "bn": "সরানোর মতো কোনো সতর্কতা নেই।",
        "ur": "ہٹانے کے لیے کوئی وارن نہیں۔",
        "ar": "لا توجد تحذيرات لإزالتها.",
        "es": "No hay avisos para eliminar.",
        "fr": "Aucun avertissement à retirer.",
        "de": "Keine Verwarnungen zum Entfernen.",
        "ru": "Нет предупреждений для удаления.",
        "zh": "没有可移除的警告。",
        "zt": "沒有可移除的警告。",
        "pt": "Sem avisos para remover.",
        "id": "Tidak ada peringatan untuk dihapus.",
        "tr": "Kaldırılacak uyarı yok.",
        "it": "Nessun avviso da rimuovere.",
        "ro": "Nicio avertizare de eliminat.",
        "nl": "Geen waarschuwingen om te verwijderen.",
        "uk": "Немає попереджень для видалення.",
        "fa": "اخطاری برای حذف نیست.",
        "he": "אין אזהרות להסרה.",
        "ko": "제거할 경고가 없습니다.",
        "el": "Δεν υπάρχουν προειδοποιήσεις για αφαίρεση.",
    },
}


# ----------------------------------------------------------------------
# Public helpers used by bot.py.
# ----------------------------------------------------------------------
def t(lang: str, key: str, **kwargs) -> str:
    """Translate ``key`` into ``lang`` using the merged table."""
    lang = lang if lang in I18N else "en"
    template = I18N[lang].get(key) or I18N["en"].get(key) or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def auto_translate(lang: str, text: str) -> str:
    """If ``text`` matches a known English phrase, return its translation in ``lang``.

    Falls back to the original text when no entry exists.
    """
    if not text or not lang or lang == "en":
        return text
    if lang not in TRANSLATED_LOCALES:
        return text
    mapping = AUTO_TRANSLATE.get(text.strip())
    if not mapping:
        return text
    return mapping.get(lang, text)


def language_label(code: str) -> str:
    """Return the menu label for ``code`` (or the code itself if missing)."""
    for c, label in LANGUAGES:
        if c == code:
            return label
    return code

# =============================================================================
# CONFIGURATION (hardcoded - replace with your values before running)
# =============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8940585917:AAEhrsIXN1I_w5XJHj44E6Fo8Bh2IJ0ufek")
SUPPORT_LINK = os.environ.get("SUPPORT_LINK", "https://t.me/CHS_SAPPORT_TEAM")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/CHS_TEAM_OFC")
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/SantoBhaiOfc")


def normalize_telegram_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith(("t.me/", "telegram.me/", "www.")):
        return "https://" + value
    if not value.lower().startswith(("http://", "https://")):
        return "https://" + value
    return value

SUPPORT_LINK = normalize_telegram_url(SUPPORT_LINK)
GROUP_LINK = normalize_telegram_url(GROUP_LINK)
CHANNEL_LINK = normalize_telegram_url(CHANNEL_LINK)
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "0") or 0)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@CHS_AuraTeamBot")
BOT_NAME = os.environ.get("BOT_NAME", "CHS AuraTeam")
BOT_OWNER_ID = int(os.environ.get("8889726455", "8889726455") or 0)
DB_PATH = os.environ.get("DB_PATH", "bot.db")
USERBOT_API_ID = int(os.environ.get("USERBOT_API_ID", "37365094") or 0)
USERBOT_API_HASH = os.environ.get("USERBOT_API_HASH", "3e480e1f28d344f1f59cf3fd409082f2")
USERBOT_SESSION = os.environ.get("USERBOT_SESSION", "BQI6JWYArByzxk2-R-Snu3P9a-jpwaJJWgBqTSeP4c91YKfn1RzkWvsDpTHpMnvHBSoR1Rau8hqNE_5DJrvlIWlyqwcZKU5Asg2q-q2lc8sAPZkBE8wxmLBghQY-UzGBU6ZRwkoibk3ldvNSCY8FRW_3h8EWyszP5N5kxUGlFHTt8WHJq0x9CCXnkTcsIJJTBnQDkxWiuhVznDNcaYWgQxW3Ess3199Zq7D_tKlC9lfAvKaXYgBknEqWTvGuMbOSzwVYmlkaFTl8HynOcSLPJLDPtL-PKB6PIww5n1hvtvVduAfWS0xg_bRiV2kHb8wMt5kzoR4kOXBdB9PCfL88zDv0b-Y0oAAAAAIUmAPpAA")
NUKE_COOLDOWN_HOURS = int(os.environ.get("NUKE_COOLDOWN_HOURS", "42"))

try:
    from pyrogram import Client as PyroClient  # type: ignore
    from pyrogram.errors import FloodWait  # type: ignore
    PYROGRAM_AVAILABLE = True
except ImportError:
    PyroClient = None  # type: ignore
    FloodWait = Exception  # type: ignore
    PYROGRAM_AVAILABLE = False

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("missrose")


# =============================================================================
# DATABASE
# =============================================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    username TEXT,
    members INTEGER DEFAULT 0,
    lang TEXT DEFAULT 'en',
    rules TEXT DEFAULT '',
    added_at INTEGER
);

CREATE TABLE IF NOT EXISTS group_settings (
    chat_id INTEGER PRIMARY KEY,
    welcome_on INTEGER DEFAULT 1,
    welcome_text TEXT DEFAULT 'Welcome {MENTION} to {GROUPNAME}!',
    welcome_media TEXT DEFAULT '',
    welcome_buttons TEXT DEFAULT '',
    welcome_media_below INTEGER DEFAULT 0,
    welcome_topic INTEGER DEFAULT 0,
    welcome_mode TEXT DEFAULT 'always',
    welcome_delete_last INTEGER DEFAULT 0,
    last_welcome_msg INTEGER DEFAULT 0,
    goodbye_on INTEGER DEFAULT 0,
    goodbye_text TEXT DEFAULT 'Goodbye {MENTION}',
    goodbye_media TEXT DEFAULT '',
    goodbye_buttons TEXT DEFAULT '',
    captcha_on INTEGER DEFAULT 0,
    captcha_timeout INTEGER DEFAULT 60,
    antispam_arabic INTEGER DEFAULT 0,
    antispam_chinese INTEGER DEFAULT 0,
    antispam_caps INTEGER DEFAULT 0,
    antispam_forwards INTEGER DEFAULT 0,
    antispam_inlinebots INTEGER DEFAULT 0,
    antispam_action TEXT DEFAULT 'warn',
    antispam_max INTEGER DEFAULT 3,
    antispam_links_action TEXT DEFAULT 'off',
    antispam_links_delete INTEGER DEFAULT 0,
    antispam_username_on INTEGER DEFAULT 0,
    antispam_bots_on INTEGER DEFAULT 0,
    antispam_forward_action TEXT DEFAULT 'off',
    antispam_quote_action TEXT DEFAULT 'off',
    antispam_totallinks_action TEXT DEFAULT 'off',
    lang TEXT DEFAULT 'en',
    goodbye_pm INTEGER DEFAULT 0,
    goodbye_delete_last INTEGER DEFAULT 0,
    antiflood_on INTEGER DEFAULT 0,
    antiflood_messages INTEGER DEFAULT 5,
    antiflood_seconds INTEGER DEFAULT 5,
    antiflood_action TEXT DEFAULT 'mute',
    antiflood_mute_minutes INTEGER DEFAULT 60,
    night_on INTEGER DEFAULT 0,
    night_start INTEGER DEFAULT 23,
    night_end INTEGER DEFAULT 7,
    approval_on INTEGER DEFAULT 0,
    block_links INTEGER DEFAULT 0,
    max_mentions INTEGER DEFAULT 5,
    media_photo TEXT DEFAULT 'off',
    media_video TEXT DEFAULT 'off',
    media_sticker TEXT DEFAULT 'off',
    media_gif TEXT DEFAULT 'off',
    media_doc TEXT DEFAULT 'off',
    media_voice TEXT DEFAULT 'off',
    media_videonote TEXT DEFAULT 'off',
    media_forward TEXT DEFAULT 'off',
    media_link TEXT DEFAULT 'off',
    media_inline TEXT DEFAULT 'off',
    media_audio TEXT DEFAULT 'off',
    media_album TEXT DEFAULT 'off',
    media_story TEXT DEFAULT 'off',
    media_animsticker TEXT DEFAULT 'off',
    media_animgame TEXT DEFAULT 'off',
    media_animemoji TEXT DEFAULT 'off',
    media_premium TEXT DEFAULT 'off',
    porn_on INTEGER DEFAULT 0,
    tag_on INTEGER DEFAULT 0,
    warn_limit INTEGER DEFAULT 3,
    warn_action TEXT DEFAULT 'mute',
    silence_on INTEGER DEFAULT 0,
    edit_check_on INTEGER DEFAULT 0,
    delete_commands INTEGER DEFAULT 0,
    selfdestruct_seconds INTEGER DEFAULT 0,
    block_cancel INTEGER DEFAULT 0,
    delete_all INTEGER DEFAULT 0,
    service_join_minutes INTEGER DEFAULT 0,
    service_exit_minutes INTEGER DEFAULT 0,
    service_photo INTEGER DEFAULT 0,
    service_title INTEGER DEFAULT 0,
    service_pinned INTEGER DEFAULT 0,
    service_topic INTEGER DEFAULT 0,
    service_boost INTEGER DEFAULT 0,
    service_videochat INTEGER DEFAULT 0,
    service_checklist INTEGER DEFAULT 0,
    scheduled_delete INTEGER DEFAULT 0,
    welcome_card_on INTEGER DEFAULT 1,
    welcome_card_style TEXT DEFAULT 'aurora',
    welcome_card_show_inviter INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS member_invites (
    chat_id INTEGER,
    inviter_id INTEGER,
    inviter_name TEXT DEFAULT '',
    count INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, inviter_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    lang TEXT,
    seen_at INTEGER
);

CREATE TABLE IF NOT EXISTS group_members (
    chat_id INTEGER,
    user_id INTEGER,
    joined_at INTEGER,
    last_message INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    role TEXT DEFAULT '',
    approved INTEGER DEFAULT 1,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS warns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    user_id INTEGER,
    admin_id INTEGER,
    reason TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS blacklist (
    chat_id INTEGER,
    word TEXT,
    PRIMARY KEY (chat_id, word)
);

CREATE TABLE IF NOT EXISTS blocks (
    chat_id INTEGER,
    user_id INTEGER,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS link_whitelist (
    chat_id INTEGER,
    domain TEXT,
    PRIMARY KEY (chat_id, domain)
);

CREATE TABLE IF NOT EXISTS captchas (
    chat_id INTEGER,
    user_id INTEGER,
    answer INTEGER,
    deadline INTEGER,
    msg_id INTEGER,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    chat_id INTEGER,
    user_id INTEGER,
    requested_at INTEGER,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS member_history (
    chat_id INTEGER,
    day TEXT,
    members INTEGER,
    PRIMARY KEY (chat_id, day)
);

CREATE TABLE IF NOT EXISTS flood_track (
    chat_id INTEGER,
    user_id INTEGER,
    last_messages TEXT,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS pinned_msgs (
    chat_id INTEGER PRIMARY KEY,
    msg_id INTEGER,
    text TEXT
);

CREATE TABLE IF NOT EXISTS adminlist_cache (
    chat_id INTEGER PRIMARY KEY,
    admins TEXT,
    refreshed_at INTEGER
);

CREATE TABLE IF NOT EXISTS pending_inputs (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    target_chat INTEGER,
    action TEXT,
    payload TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS log_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    actor_id INTEGER,
    target_id INTEGER,
    action TEXT,
    info TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS nuke_cooldowns (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);

-- Notes / Saved messages: trigger -> stored content (text or media file_id).
CREATE TABLE IF NOT EXISTS notes (
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    content TEXT DEFAULT '',
    file_id TEXT DEFAULT '',
    file_type TEXT DEFAULT '',
    buttons TEXT DEFAULT '',
    created_by INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, name)
);

-- Filters: keyword -> auto-reply when seen in a message.
CREATE TABLE IF NOT EXISTS filters (
    chat_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    reply TEXT DEFAULT '',
    file_id TEXT DEFAULT '',
    file_type TEXT DEFAULT '',
    created_by INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, keyword)
);

-- Locks: per-chat lock state for media types and other behaviours.
CREATE TABLE IF NOT EXISTS locks (
    chat_id INTEGER NOT NULL,
    lock_type TEXT NOT NULL,
    locked INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, lock_type)
);

-- Disabled commands: admins can disable specific commands per chat.
CREATE TABLE IF NOT EXISTS disabled_cmds (
    chat_id INTEGER NOT NULL,
    cmd TEXT NOT NULL,
    deletes INTEGER DEFAULT 1,
    PRIMARY KEY (chat_id, cmd)
);

-- Federations: groups of chats sharing a global ban list.
CREATE TABLE IF NOT EXISTS federations (
    fed_id TEXT PRIMARY KEY,
    name TEXT,
    owner_id INTEGER,
    log_chat INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fed_members (
    fed_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    joined_at INTEGER DEFAULT 0,
    PRIMARY KEY (fed_id, chat_id)
);
CREATE TABLE IF NOT EXISTS fed_admins (
    fed_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (fed_id, user_id)
);
CREATE TABLE IF NOT EXISTS fed_bans (
    fed_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    by_user INTEGER DEFAULT 0,
    banned_at INTEGER DEFAULT 0,
    PRIMARY KEY (fed_id, user_id)
);

-- PM <-> group connection: lets admins use group commands from private chat.
CREATE TABLE IF NOT EXISTS pm_connections (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    connected_at INTEGER DEFAULT 0
);

-- Global ban / mute list (sudo / owner managed).
CREATE TABLE IF NOT EXISTS gbans (
    user_id INTEGER PRIMARY KEY,
    reason TEXT DEFAULT '',
    by_user INTEGER DEFAULT 0,
    banned_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS gmutes (
    user_id INTEGER PRIMARY KEY,
    reason TEXT DEFAULT '',
    by_user INTEGER DEFAULT 0,
    muted_at INTEGER DEFAULT 0
);

-- Sudo users (can use global commands; bot owner is implicit).
CREATE TABLE IF NOT EXISTS sudo_users (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER DEFAULT 0,
    added_at INTEGER DEFAULT 0
);

-- AFK status table.
CREATE TABLE IF NOT EXISTS afk_users (
    user_id INTEGER PRIMARY KEY,
    reason TEXT DEFAULT '',
    since INTEGER DEFAULT 0
);

-- Reports log (per-chat reports raised by users).
CREATE TABLE IF NOT EXISTS reports_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    reporter_id INTEGER,
    target_id INTEGER,
    msg_id INTEGER,
    reason TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0
);

-- Welcome / Goodbye per-user delivery counters (for "send only once" mode).
CREATE TABLE IF NOT EXISTS welcome_seen (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    seen_at INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
);

-- Per-user language preference (DM Languages button in /start menu).
CREATE TABLE IF NOT EXISTS user_lang (
    user_id INTEGER PRIMARY KEY,
    lang TEXT DEFAULT 'en'
);
"""


_db: Optional[aiosqlite.Connection] = None


async def db_init() -> None:
    """Open the SQLite connection and run schema migrations."""
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    # Lightweight migrations for existing DBs (ADD COLUMN if missing)
    async with _db.execute("PRAGMA table_info(group_settings)") as cur:
        existing_cols = {row[1] for row in await cur.fetchall()}
    migrations = [
        ("antispam_links_action", "TEXT DEFAULT 'off'"),
        ("antispam_links_delete", "INTEGER DEFAULT 0"),
        ("antispam_username_on", "INTEGER DEFAULT 0"),
        ("antispam_bots_on", "INTEGER DEFAULT 0"),
        ("antispam_forward_action", "TEXT DEFAULT 'off'"),
        ("antispam_quote_action", "TEXT DEFAULT 'off'"),
        ("antispam_totallinks_action", "TEXT DEFAULT 'off'"),
        ("lang", "TEXT DEFAULT 'en'"),
        ("goodbye_pm", "INTEGER DEFAULT 0"),
        ("goodbye_delete_last", "INTEGER DEFAULT 0"),
        ("media_audio", "TEXT DEFAULT 'off'"),
        ("media_album", "TEXT DEFAULT 'off'"),
        ("media_story", "TEXT DEFAULT 'off'"),
        ("media_animsticker", "TEXT DEFAULT 'off'"),
        ("media_animgame", "TEXT DEFAULT 'off'"),
        ("media_animemoji", "TEXT DEFAULT 'off'"),
        ("media_premium", "TEXT DEFAULT 'off'"),
        ("welcome_card_on", "INTEGER DEFAULT 1"),
        ("welcome_card_style", "TEXT DEFAULT 'aurora'"),
        ("welcome_card_show_inviter", "INTEGER DEFAULT 1"),
    ]
    # Ensure the member_invites table exists for older databases.
    try:
        await _db.execute(
            "CREATE TABLE IF NOT EXISTS member_invites ("
            "chat_id INTEGER, inviter_id INTEGER, inviter_name TEXT DEFAULT '', "
            "count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, inviter_id))"
        )
    except Exception:
        pass
    for col, decl in migrations:
        if col not in existing_cols:
            try:
                await _db.execute(f"ALTER TABLE group_settings ADD COLUMN {col} {decl}")
            except Exception:
                pass
    await _db.commit()


async def db() -> aiosqlite.Connection:
    """Return the global database connection."""
    if _db is None:
        await db_init()
    assert _db is not None
    return _db


async def _get_db() -> aiosqlite.Connection:
    """Return the single global SQLite connection.

    All callers (legacy code that did `db = await _get_db()` and the new
    `db_exec/db_one/db_all` helpers) MUST share the same connection, otherwise
    SQLite locks fight each other and writes done by one connection are not
    visible to the other until commit ordering aligns.
    """
    if _db is None:
        await db_init()
    assert _db is not None
    return _db


async def db_exec(query: str, params: tuple = ()) -> None:
    conn = await db()
    await conn.execute(query, params)
    await conn.commit()


async def db_one(query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
    conn = await db()
    async with conn.execute(query, params) as cur:
        return await cur.fetchone()


# -- Per-user language preference -----------------------------------------
_USER_LANG_CACHE: dict[int, tuple[str, float]] = {}
_USER_LANG_TTL = 60.0


async def get_user_lang(user_id: int) -> str:
    """Return the user's chosen DM language, defaulting to English."""
    if not user_id:
        return "en"
    now = time.time()
    cached = _USER_LANG_CACHE.get(user_id)
    if cached and cached[1] > now:
        return cached[0]
    try:
        row = await db_one(
            "SELECT lang FROM user_lang WHERE user_id=?", (user_id,)
        )
    except Exception:
        return "en"
    code = (row["lang"] if row and row["lang"] else "en") or "en"
    _USER_LANG_CACHE[user_id] = (code, now + _USER_LANG_TTL)
    return code


async def set_user_lang(user_id: int, lang: str) -> None:
    """Persist the user's DM language and bust the cache."""
    await db_exec(
        "INSERT OR REPLACE INTO user_lang(user_id, lang) VALUES (?, ?)",
        (user_id, lang),
    )
    _USER_LANG_CACHE.pop(user_id, None)


async def db_all(query: str, params: tuple = ()) -> list[aiosqlite.Row]:
    conn = await db()
    async with conn.execute(query, params) as cur:
        return await cur.fetchall()


async def ensure_group(chat: Chat) -> None:
    """Insert chat row + default settings row if missing."""
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    now = int(time.time())
    await db_exec(
        "INSERT OR IGNORE INTO groups(chat_id, title, username, added_at) VALUES (?,?,?,?)",
        (chat.id, chat.title or "", chat.username or "", now),
    )
    await db_exec(
        "UPDATE groups SET title=?, username=? WHERE chat_id=?",
        (chat.title or "", chat.username or "", chat.id),
    )
    await db_exec(
        "INSERT OR IGNORE INTO group_settings(chat_id) VALUES (?)", (chat.id,)
    )


async def ensure_user(user: User) -> None:
    if user is None:
        return
    await db_exec(
        "INSERT OR REPLACE INTO users(user_id, first_name, last_name, username, lang, seen_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            user.id,
            user.first_name or "",
            user.last_name or "",
            user.username or "",
            user.language_code or "",
            int(time.time()),
        ),
    )


async def get_settings(chat_id: int) -> dict:
    row = await db_one("SELECT * FROM group_settings WHERE chat_id=?", (chat_id,))
    if row is None:
        await db_exec("INSERT INTO group_settings(chat_id) VALUES (?)", (chat_id,))
        row = await db_one("SELECT * FROM group_settings WHERE chat_id=?", (chat_id,))
    return dict(row) if row else {}


_ALLOWED_SETTING_COLS: set[str] = set()


async def _settings_columns() -> set[str]:
    """Return (and cache) the set of valid columns in ``group_settings``."""
    global _ALLOWED_SETTING_COLS
    if _ALLOWED_SETTING_COLS:
        return _ALLOWED_SETTING_COLS
    conn = await db()
    async with conn.execute("PRAGMA table_info(group_settings)") as cur:
        rows = await cur.fetchall()
    _ALLOWED_SETTING_COLS = {r["name"] for r in rows}
    return _ALLOWED_SETTING_COLS


async def set_setting(chat_id: int, key: str, value) -> None:
    cols = await _settings_columns()
    if key not in cols:
        raise ValueError(f"unknown group_settings column: {key!r}")
    # `key` is now whitelisted against the live schema, so the f-string is safe.
    await db_exec(f"UPDATE group_settings SET {key}=? WHERE chat_id=?", (value, chat_id))


async def toggle_setting(chat_id: int, key: str) -> int:
    s = await get_settings(chat_id)
    cur = int(s.get(key, 0) or 0)
    new = 0 if cur else 1
    await set_setting(chat_id, key, new)
    return new


# =============================================================================
# UTILITIES
# =============================================================================
ON = "✔"
OFF = "✖"


def onoff(value) -> str:
    return ON if value else OFF


def now_ts() -> int:
    return int(time.time())


def fmt_user(user: User) -> str:
    name = html.escape((user.full_name or user.first_name or "User"))
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def fmt_user_id(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'


def parse_duration(s: str) -> Optional[int]:
    """Parse strings like 30m, 2h, 7d, 90s into seconds."""
    if not s:
        return None
    m = re.match(r"^(\d+)\s*([smhdw]?)$", s.strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2) or "m"
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]


_ENTITY_HTML_OPEN = {
    "bold": "<b>", "italic": "<i>", "underline": "<u>",
    "strikethrough": "<s>", "spoiler": '<span class="tg-spoiler">',
    "code": "<code>", "pre": "<pre>",
    "blockquote": "<blockquote>",
    "expandable_blockquote": '<blockquote expandable>',
}
_ENTITY_HTML_CLOSE = {
    "bold": "</b>", "italic": "</i>", "underline": "</u>",
    "strikethrough": "</s>", "spoiler": "</span>",
    "code": "</code>", "pre": "</pre>",
    "blockquote": "</blockquote>",
    "expandable_blockquote": "</blockquote>",
}


def entities_to_html(text: str, entities) -> str:
    """Convert a Telegram message text + entities into HTML preserving formatting."""
    if not text:
        return ""
    if not entities:
        return html.escape(text)
    # work with utf-16 code units like Telegram does
    utf16 = text.encode("utf-16-le")
    opens: dict[int, list[str]] = {}
    closes: dict[int, list[str]] = {}
    for ent in entities:
        start = ent.offset * 2
        end = (ent.offset + ent.length) * 2
        t = ent.type
        if t in _ENTITY_HTML_OPEN:
            opens.setdefault(start, []).append(_ENTITY_HTML_OPEN[t])
            closes.setdefault(end, []).insert(0, _ENTITY_HTML_CLOSE[t])
        elif t == "text_link":
            url = ent.url or ""
            opens.setdefault(start, []).append(f'<a href="{html.escape(url, quote=True)}">')
            closes.setdefault(end, []).insert(0, "</a>")
        elif t == "text_mention" and ent.user:
            opens.setdefault(start, []).append(f'<a href="tg://user?id={ent.user.id}">')
            closes.setdefault(end, []).insert(0, "</a>")
        elif t == "custom_emoji":
            cid = getattr(ent, "custom_emoji_id", "")
            if cid:
                opens.setdefault(start, []).append(f'<tg-emoji emoji-id="{html.escape(str(cid), quote=True)}">')
                closes.setdefault(end, []).insert(0, "</tg-emoji>")
    out = []
    i = 0
    n = len(utf16)
    while i <= n:
        for tag in closes.get(i, []):
            out.append(tag)
        for tag in opens.get(i, []):
            out.append(tag)
        if i < n:
            ch = utf16[i:i + 2].decode("utf-16-le", errors="replace")
            out.append(html.escape(ch))
        i += 2
    return "".join(out)


def capture_html(msg: Message) -> str:
    """Return the message body as HTML (text or caption), preserving entities including blockquote."""
    if msg.text is not None:
        return entities_to_html(msg.text, msg.entities or [])
    if msg.caption is not None:
        return entities_to_html(msg.caption, msg.caption_entities or [])
    return ""


def render_template(template: str, user: User, chat: Chat, rules: str = "") -> str:
    now = datetime.now(timezone.utc)
    name = (user.first_name or "")
    surname = (user.last_name or "")
    namesurname = (name + " " + surname).strip()
    mention = f'<a href="tg://user?id={user.id}">{html.escape(name or "user")}</a>'
    repl = {
        "{ID}": str(user.id),
        "{NAME}": html.escape(name),
        "{SURNAME}": html.escape(surname),
        "{NAMESURNAME}": html.escape(namesurname),
        "{LANG}": html.escape(user.language_code or ""),
        "{DATE}": now.strftime("%Y-%m-%d"),
        "{TIME}": now.strftime("%H:%M"),
        "{WEEKDAY}": now.strftime("%A"),
        "{MENTION}": mention,
        "{USERNAME}": "@" + user.username if user.username else mention,
        "{GROUPNAME}": html.escape(chat.title or ""),
        "{RULES}": html.escape(rules or ""),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def parse_button_string(text: str) -> Optional[InlineKeyboardMarkup]:
    """Parse Miss Rose style button text into an InlineKeyboardMarkup.

    Format:
        Title - https://example.com
        Foo - t.me/x && Bar - t.me/y
        Title - popup: text
        Title - alert: text
        Title - rules
        Title - share: text
        Title - copy: text
    """
    if not text or not text.strip():
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        row: list[InlineKeyboardButton] = []
        for part in line.split("&&"):
            part = part.strip()
            if " - " not in part:
                continue
            title, target = part.split(" - ", 1)
            title = title.strip()
            target = target.strip()
            low = target.lower()
            if low.startswith("popup:") or low.startswith("alert:"):
                payload = target.split(":", 1)[1].strip()
                row.append(InlineKeyboardButton(title, callback_data=f"popup:{payload[:48]}"))
            elif low == "rules":
                row.append(InlineKeyboardButton(title, callback_data="show_rules"))
            elif low.startswith("share:"):
                payload = target.split(":", 1)[1].strip()
                row.append(
                    InlineKeyboardButton(
                        title,
                        url=f"https://t.me/share/url?url={requests.utils.quote(payload)}",
                    )
                )
            elif low.startswith("copy:"):
                payload = target.split(":", 1)[1].strip()
                row.append(InlineKeyboardButton(title, callback_data=f"copy:{payload[:48]}"))
            elif target.startswith("http") or target.startswith("t.me") or target.startswith("tg:"):
                if target.startswith("t.me"):
                    target = "https://" + target
                row.append(InlineKeyboardButton(title, url=target))
            else:
                row.append(InlineKeyboardButton(title, callback_data=f"noop:{title[:32]}"))
        if row:
            rows.append(row)
    return InlineKeyboardMarkup(rows) if rows else None


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    if user_id == BOT_OWNER_ID:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except TelegramError:
        return False


async def is_user_role(chat_id: int, user_id: int, role: str) -> bool:
    row = await db_one(
        "SELECT role FROM group_members WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    return bool(row and row["role"] == role)


async def has_min_role(bot: Bot, chat_id: int, user_id: int, *roles: str) -> bool:
    if await is_admin(bot, chat_id, user_id):
        return True
    row = await db_one(
        "SELECT role FROM group_members WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    return bool(row and row["role"] in roles)


async def refresh_admins(bot: Bot, chat_id: int) -> list[int]:
    try:
        admins = await bot.get_chat_administrators(chat_id)
    except TelegramError:
        return []
    ids = [a.user.id for a in admins]
    serialized = ",".join(str(i) for i in ids)
    await db_exec(
        "INSERT OR REPLACE INTO adminlist_cache(chat_id, admins, refreshed_at) VALUES (?,?,?)",
        (chat_id, serialized, now_ts()),
    )
    return ids


async def log_action(chat_id: int, actor_id: int, target_id: int, action: str, info: str = "") -> None:
    await db_exec(
        "INSERT INTO log_actions(chat_id, actor_id, target_id, action, info, created_at) VALUES (?,?,?,?,?,?)",
        (chat_id, actor_id, target_id, action, info, now_ts()),
    )


async def send_log(bot: Bot, text: str) -> None:
    if LOG_CHANNEL_ID:
        try:
            await bot.send_message(LOG_CHANNEL_ID, text, parse_mode=ParseMode.HTML)
        except TelegramError:
            pass


# =============================================================================
# WELCOME CARD (Pillow)
# =============================================================================
def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _circle_avatar(img: Image.Image, size: int = 220) -> Image.Image:
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _draw_snowflakes(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    rng = random.Random(7)
    for _ in range(40):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.randint(1, 3)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 80))


def _setting_truthy(s, key: str, default: bool = False) -> bool:
    """Safely read a boolean-ish setting from a sqlite3.Row / dict-like."""
    try:
        v = s[key]
    except (IndexError, KeyError, TypeError):
        return default
    if v is None:
        return default
    try:
        return bool(int(v))
    except (TypeError, ValueError):
        return bool(v)


def _setting_str(s, key: str, default: str = "") -> str:
    """Safely read a string setting from a sqlite3.Row / dict-like."""
    try:
        v = s[key]
    except (IndexError, KeyError, TypeError):
        return default
    if v is None or v == "":
        return default
    return str(v)


def _ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', 11 -> '11th', etc."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# -----------------------------------------------------------------------------
# Welcome card styles (user-selectable themes)
# -----------------------------------------------------------------------------
# Each style defines:
#   gradient_top / gradient_bottom — RGB tuples for the background gradient
#   ring_color                     — RGBA tuple for the circle ring around avatar
#   accent                         — RGBA decoration color (snowflakes, dots, etc.)
#   title_color / name_color / info_color / member_color — text colors
#   decoration                     — name of the decoration drawer
WELCOME_CARD_STYLES: dict = {
    "aurora": {
        "label": "Aurora 💜",
        "gradient_top": (35, 12, 60),
        "gradient_bottom": (90, 25, 110),
        "ring_color": (255, 80, 160, 255),
        "accent": (255, 255, 255, 80),
        "title_color": (255, 200, 230),
        "name_color": (255, 255, 255),
        "info_color": (220, 220, 240),
        "member_color": (255, 180, 220),
        "decoration": "snowflakes",
    },
    "sunset": {
        "label": "Sunset 🌅",
        "gradient_top": (250, 100, 60),
        "gradient_bottom": (110, 30, 80),
        "ring_color": (255, 230, 100, 255),
        "accent": (255, 240, 200, 110),
        "title_color": (255, 240, 200),
        "name_color": (255, 255, 255),
        "info_color": (255, 230, 200),
        "member_color": (255, 210, 140),
        "decoration": "stars",
    },
    "ocean": {
        "label": "Ocean 🌊",
        "gradient_top": (15, 70, 130),
        "gradient_bottom": (10, 160, 200),
        "ring_color": (180, 240, 255, 255),
        "accent": (200, 240, 255, 100),
        "title_color": (200, 240, 255),
        "name_color": (255, 255, 255),
        "info_color": (220, 245, 255),
        "member_color": (180, 230, 255),
        "decoration": "bubbles",
    },
    "forest": {
        "label": "Forest 🌿",
        "gradient_top": (20, 70, 50),
        "gradient_bottom": (50, 140, 80),
        "ring_color": (210, 255, 180, 255),
        "accent": (180, 255, 200, 90),
        "title_color": (200, 255, 210),
        "name_color": (255, 255, 255),
        "info_color": (220, 255, 220),
        "member_color": (180, 240, 180),
        "decoration": "dots",
    },
    "midnight": {
        "label": "Midnight 🌙",
        "gradient_top": (8, 10, 30),
        "gradient_bottom": (25, 35, 70),
        "ring_color": (130, 180, 255, 255),
        "accent": (255, 255, 255, 140),
        "title_color": (180, 200, 255),
        "name_color": (255, 255, 255),
        "info_color": (200, 215, 240),
        "member_color": (160, 190, 240),
        "decoration": "stars",
    },
    "candy": {
        "label": "Candy 🍭",
        "gradient_top": (255, 150, 200),
        "gradient_bottom": (180, 80, 200),
        "ring_color": (255, 240, 250, 255),
        "accent": (255, 255, 255, 120),
        "title_color": (255, 255, 255),
        "name_color": (255, 255, 255),
        "info_color": (255, 240, 250),
        "member_color": (255, 230, 245),
        "decoration": "hearts",
    },
    "minimal": {
        "label": "Minimal ⬜",
        "gradient_top": (245, 245, 248),
        "gradient_bottom": (220, 222, 230),
        "ring_color": (60, 70, 90, 255),
        "accent": (180, 185, 200, 60),
        "title_color": (90, 100, 120),
        "name_color": (30, 35, 50),
        "info_color": (90, 95, 110),
        "member_color": (120, 80, 160),
        "decoration": "lines",
    },
}


def _draw_stars(draw: ImageDraw.ImageDraw, w: int, h: int, color) -> None:
    rng = random.Random(11)
    for _ in range(45):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.randint(1, 2)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        if rng.random() < 0.25:
            draw.line((x - 4, y, x + 4, y), fill=color, width=1)
            draw.line((x, y - 4, x, y + 4), fill=color, width=1)


def _draw_bubbles(draw: ImageDraw.ImageDraw, w: int, h: int, color) -> None:
    rng = random.Random(13)
    for _ in range(28):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.randint(4, 14)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=2)


def _draw_dots(draw: ImageDraw.ImageDraw, w: int, h: int, color) -> None:
    rng = random.Random(17)
    for _ in range(60):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.randint(2, 5)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _draw_hearts(draw: ImageDraw.ImageDraw, w: int, h: int, color) -> None:
    rng = random.Random(19)
    for _ in range(22):
        x = rng.randint(20, w - 20)
        y = rng.randint(20, h - 20)
        s = rng.randint(4, 9)
        # two circles + triangle to look like a tiny heart
        draw.ellipse((x - s, y - s, x, y), fill=color)
        draw.ellipse((x, y - s, x + s, y), fill=color)
        draw.polygon([(x - s, y - 1), (x + s, y - 1), (x, y + s + 2)], fill=color)


def _draw_lines(draw: ImageDraw.ImageDraw, w: int, h: int, color) -> None:
    for i in range(0, w, 40):
        draw.line([(i, 0), (i, h)], fill=color, width=1)


def _draw_card_decoration(draw: ImageDraw.ImageDraw, w: int, h: int, name: str, accent) -> None:
    if name == "snowflakes":
        _draw_snowflakes(draw, w, h)
    elif name == "stars":
        _draw_stars(draw, w, h, accent)
    elif name == "bubbles":
        _draw_bubbles(draw, w, h, accent)
    elif name == "dots":
        _draw_dots(draw, w, h, accent)
    elif name == "hearts":
        _draw_hearts(draw, w, h, accent)
    elif name == "lines":
        _draw_lines(draw, w, h, accent)


def make_welcome_card(
    name: str,
    user_id: int,
    username: str,
    members: int,
    avatar_bytes: Optional[bytes],
    style: str = "aurora",
    inviter_text: Optional[str] = None,
) -> bytes:
    """Render the 800x400 welcome card as PNG bytes.

    style         — key from WELCOME_CARD_STYLES (falls back to 'aurora')
    inviter_text  — optional small line shown under "Member #N", e.g.
                    "Added by @alice (3rd invite)"
    """
    cfg = WELCOME_CARD_STYLES.get(style) or WELCOME_CARD_STYLES["aurora"]
    w, h = 800, 400
    base = Image.new("RGB", (w, h), (10, 10, 25))
    top = cfg["gradient_top"]
    bot = cfg["gradient_bottom"]
    for y in range(h):
        ratio = y / h
        r = int(top[0] + (bot[0] - top[0]) * ratio)
        g = int(top[1] + (bot[1] - top[1]) * ratio)
        b = int(top[2] + (bot[2] - top[2]) * ratio)
        ImageDraw.Draw(base).line([(0, y), (w, y)], fill=(r, g, b))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    _draw_card_decoration(od, w, h, cfg.get("decoration", "snowflakes"), cfg["accent"])
    od.line([(40, 50), (760, 50)], fill=cfg["accent"], width=2)
    od.line([(40, 350), (760, 350)], fill=cfg["accent"], width=2)
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    # avatar
    avatar_img: Optional[Image.Image] = None
    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes))
        except Exception:
            avatar_img = None
    if avatar_img is None:
        avatar_img = Image.new("RGB", (220, 220), cfg["ring_color"][:3])
        d = ImageDraw.Draw(avatar_img)
        f = _font(120)
        letter = (name[:1] or "?").upper()
        try:
            tw = d.textlength(letter, font=f)
        except AttributeError:
            tw = 80
        d.text(((220 - tw) / 2, 30), letter, fill="white", font=f)

    avatar_circle = _circle_avatar(avatar_img, 220)
    ring = Image.new("RGBA", (250, 250), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((0, 0, 250, 250), fill=cfg["ring_color"])
    rd.ellipse((10, 10, 240, 240), fill=(0, 0, 0, 0))
    base = base.convert("RGBA")
    base.paste(ring, (40, 75), ring)
    base.paste(avatar_circle, (55, 90), avatar_circle)

    d = ImageDraw.Draw(base)
    name_font = _font(40)
    info_font = _font(22)
    small_font = _font(20)
    tiny_font = _font(18)

    d.text((310, 90), "WELCOME", fill=cfg["title_color"], font=info_font)
    d.text((310, 120), name[:30], fill=cfg["name_color"], font=name_font)
    d.text((310, 180), f"ID: {user_id}", fill=cfg["info_color"], font=info_font)
    if username:
        d.text((310, 215), f"@{username}", fill=cfg["info_color"], font=info_font)
    d.text((310, 260), f"Member #{members}", fill=cfg["member_color"], font=info_font)
    if inviter_text:
        d.text((310, 295), inviter_text[:40], fill=cfg["info_color"], font=tiny_font)
    d.text((310, 350), BOT_NAME, fill=cfg["title_color"], font=small_font)

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out.getvalue()


async def fetch_avatar_bytes(bot: Bot, user_id: int) -> Optional[bytes]:
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count and photos.photos:
            f = await bot.get_file(photos.photos[0][-1].file_id)
            buf = io.BytesIO()
            await f.download_to_memory(out=buf)
            return buf.getvalue()
    except TelegramError:
        return None
    return None


# =============================================================================
# MEMBER TREND CHART
# =============================================================================
async def make_member_chart(chat_id: int, title: str) -> Optional[bytes]:
    rows = await db_all(
        "SELECT day, members FROM member_history WHERE chat_id=? ORDER BY day", (chat_id,)
    )
    if not rows:
        return None
    days = [datetime.strptime(r["day"], "%Y-%m-%d") for r in rows]
    members = [r["members"] for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(days, members, color="#e91e63", marker="o", linewidth=2)
    ax.fill_between(days, members, color="#e91e63", alpha=0.18)
    ax.set_title(f"Members trend - {title}", fontsize=13)
    ax.set_xlabel("Date")
    ax.set_ylabel("Members")
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# =============================================================================
# /start MENU
# =============================================================================
def start_text() -> str:
    return (
        "👋 <b>Hello!</b>\n"
        f"<b>{html.escape(BOT_NAME)}</b> is the most complete Bot to help you\n"
        "manage your groups easily and safely!\n\n"
        "👉 Add me in a Supergroup and promote me as Admin\n"
        "to let me get in action!\n\n"
        "❓ <b>WHICH ARE THE COMMANDS?</b> ❓\n"
        "Press /help to see all the commands and how they work!\n"
        "📋 Privacy policy"
    )


def start_keyboard() -> InlineKeyboardMarkup:
    add_url = f"https://t.me/{BOT_USERNAME}?startgroup=true"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add me to a Group ➕", url=add_url)],
            [InlineKeyboardButton("⚙️ Manage group Settings ✍️", callback_data="dm:settings")],
            [
                InlineKeyboardButton("👥 Group ↗", url=GROUP_LINK),
                InlineKeyboardButton("📢 Channel ↗", url=CHANNEL_LINK),
            ],
            [
                InlineKeyboardButton("🆘 Support", callback_data="dm:support"),
                InlineKeyboardButton("💬 Information", callback_data="dm:info"),
            ],
            [InlineKeyboardButton("🇬🇧 Languages 🇬🇧", callback_data="dm:lang")],
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None:
        return
    await ensure_user(user)
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await ensure_group(chat)
        await update.effective_message.reply_text(
            f"Hi {fmt_user(user)}! Press the button below to talk to me in private.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Open in private", url=f"https://t.me/{BOT_USERNAME}?start=hi")]]
            ),
        )
        return
    await update.effective_message.reply_text(
        start_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=start_keyboard(),
        disable_web_page_preview=True,
    )


# Sub-pages from the start menu
async def cb_dm_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "dm:home":
        await q.edit_message_text(
            start_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=start_keyboard(),
            disable_web_page_preview=True,
        )
        return
    back = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="dm:home")]])
    if data == "dm:support":
        await q.edit_message_text(
            "🆘 <b>Support</b>\n\nNeed help? Reach out to our support team.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Open Support", url=SUPPORT_LINK)],
                    [InlineKeyboardButton("↩️ Back", callback_data="dm:home")],
                ]
            ),
        )
    elif data == "dm:info":
        await q.edit_message_text(
            f"💬 <b>Information</b>\n\n"
            f"• Bot name: {html.escape(BOT_NAME)}\n"
            f"• Username: @{BOT_USERNAME}\n"
            "• Built with python-telegram-bot 20.7\n"
            "• Manage groups with anti-spam, captcha, warns, welcome cards, and more.",
            parse_mode=ParseMode.HTML,
            reply_markup=back,
        )
    elif data == "dm:lang":
        try:
            _DM_LANGS = LANGUAGES  # inlined from lang.py
        except Exception:
            _DM_LANGS = [("en", "🇬🇧 English")]
        cur = await get_user_lang(q.from_user.id)
        rows = []
        row: list[InlineKeyboardButton] = []
        for code, label in _DM_LANGS:
            mark = "✅ " if code == cur else ""
            row.append(InlineKeyboardButton(
                f"{mark}{label}", callback_data=f"setulang:{code}"
            ))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("↩️ Back", callback_data="dm:home")])
        await q.edit_message_text(
            "🇬🇧 <b>Choose your language</b>\n\n"
            "Pick the language the bot should reply to <i>you</i> in (DMs and groups).",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(rows),
        )
    elif data == "dm:settings":
        await render_group_picker(q, context)


async def cb_set_user_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the user's chosen DM language."""
    q = update.callback_query
    try:
        await q.answer()
    except TelegramError:
        pass
    parts = q.data.split(":", 1)
    if len(parts) != 2:
        return
    lang_code = parts[1].strip() or "en"
    try:
        _SET_LANGS = LANGUAGES  # inlined from lang.py
    except Exception:
        _SET_LANGS = [("en", "🇬🇧 English")]
    if lang_code not in {c for c, _ in _SET_LANGS}:
        return
    await set_user_lang(q.from_user.id, lang_code)
    # Use the module-level language_label() — defining a local fallback above
    # makes Python treat the name as a local in this function and raises
    # UnboundLocalError on the happy path (the inner def never executes).
    try:
        label = language_label(lang_code)
    except Exception:
        label = lang_code
    try:
        await q.edit_message_text(
            f"✅ Language changed to {label}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ Back", callback_data="dm:home")]]
            ),
        )
    except TelegramError:
        try:
            await context.bot.send_message(
                q.from_user.id, f"✅ Language changed to {label}",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass


# =============================================================================
# /help
# =============================================================================
HELP_HOME_TEXT = (
    "❓ <b>Help &amp; Commands</b>\n\n"
    "Below you can find all the commands grouped by topic. "
    "Pick one of the sections to see the details."
)


def help_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Base Commands", callback_data="help:base")],
            [InlineKeyboardButton("⚡ Advanced Commands", callback_data="help:adv")],
            [InlineKeyboardButton("🔬 Expert Commands", callback_data="help:expert")],
            [InlineKeyboardButton("⚡ Create Clone quickly", url="https://t.me/" + BOT_USERNAME)],
            [InlineKeyboardButton("↩️ Back to Help", callback_data="help:home")],
        ]
    )


HELP_BASE = (
    "<b>Base Commands</b>\n"
    "👮 Available to Admins&amp;Moderators / 👮 Available to Admins\n\n"
    "/reload - updates the Admins list and their privileges\n"
    "/settings - lets you manage all the Bot settings in a group\n"
    "/ban - lets you ban a user from the group without giving\n"
    "       him the possibility to join again using the link\n"
    "/mute - puts a user in read-only mode\n"
    "/kick - bans a user giving him the possibility to join again\n"
    "/unban - remove a user from group's blacklist\n"
    "/info - gives information about a user\n"
    "/infopvt - same of /info but sends infos in private chat\n"
    "/staff - gives the complete List of group Staff"
)

HELP_ADV = (
    "<b>Advanced Commands</b>\n"
    "👮 Admins / 👮 Admins&amp;Moderators / 🧹 Admins&amp;Cleaners\n\n"
    "<b>WARN MANAGEMENT</b>\n"
    "/warn - adds a warn to the user\n"
    "/unwarn - removes a warn to the user\n"
    "/warns - lets you see and manage user warns\n"
    "/delwarn - deletes the message and add a warn to the user\n\n"
    "🧹 /del - deletes the selected message\n"
    "🧹 /logdel - deletes the selected message and sends it to Log Channel\n\n"
    "/me - sends in private chat a message with his own infos,\n"
    "      group infos, warns received, rules of the group,\n"
    "      banned words list...\n\n"
    "/send - permits to send a post using HTML in the group\n"
    "        Example: /send Hello World!\n\n"
    "/intervention - lets you request the intervention of a\n"
    "               member of Official Bot Support"
)

HELP_EXPERT = (
    "<b>Expert commands</b>\n"
    "👥 all users / 👮 Admins&amp;Moderators / 👮 Admins\n\n"
    "👥 /geturl - by replying to a message, you receive the link\n"
    "             that refers directly to that message\n\n"
    "👮 /inactives [days] - sends in private chat the list of\n"
    "    users who have not sent a message in the last [days],\n"
    "    with the possibility to punish them\n\n"
    "<b>Pinned Messages:</b>\n"
    "👮 /pin [message] - sends the message through the Bot and pins it\n"
    "👮 /pin - pins the message in reply\n"
    "👮 /editpin [message] - edits the current pinned message\n"
    "👮 /delpin - removes the pinned message\n"
    "👮 /repin - removes and pins again with notification!\n"
    "👥 /pinned - refers to the current pinned message\n\n"
    "👮 /list - sends in private chat the list of users with\n"
    "           the number of messages sent by them\n"
    "👮 /list roles - sends in private chat the list of all\n"
    "                 the special roles assigned to users\n\n"
    "👮 /graphic - sends a graph showing the trend of the group members\n"
    "👮 /trend - sends the group's growth statistics"
)


def back_to_help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Help", callback_data="help:home")]])


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await msg.reply_text(HELP_HOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=help_home_kb())


async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "help:home":
        await q.edit_message_text(HELP_HOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=help_home_kb())
    elif data == "help:base":
        await q.edit_message_text(HELP_BASE, parse_mode=ParseMode.HTML, reply_markup=back_to_help_kb())
    elif data == "help:adv":
        await q.edit_message_text(HELP_ADV, parse_mode=ParseMode.HTML, reply_markup=back_to_help_kb())
    elif data == "help:expert":
        await q.edit_message_text(HELP_EXPERT, parse_mode=ParseMode.HTML, reply_markup=back_to_help_kb())


# =============================================================================
# /settings — group picker + per-group menu tree
# =============================================================================
async def list_user_groups(bot: Bot, user_id: int) -> list[tuple[int, str]]:
    rows = await db_all("SELECT chat_id, title FROM groups", ())
    out: list[tuple[int, str]] = []
    for r in rows:
        try:
            m = await bot.get_chat_member(r["chat_id"], user_id)
            if m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                out.append((r["chat_id"], r["title"] or str(r["chat_id"])))
        except TelegramError:
            continue
    return out


async def render_group_picker(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = query.from_user
    groups = await list_user_groups(context.bot, user.id)
    text = (
        "<b>Manage group Settings</b>\n"
        "👉 Select the group whose settings you want to change.\n\n"
        "If a group in which you are an administrator doesn't appear:\n"
        "• Send /reload in the group and try again\n"
        "• Send /settings in the group and then press 'Open in pvt'"
    )
    rows: list[list[InlineKeyboardButton]] = []
    for chat_id, title in groups:
        rows.append([InlineKeyboardButton(f"{title} ↗", callback_data=f"st:open:{chat_id}")])
    if not rows:
        rows.append([InlineKeyboardButton("(no groups found)", callback_data="noop:none")])
    rows.append([InlineKeyboardButton("↩️ Back", callback_data="dm:home")])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return
    await ensure_user(user)
    if chat.type == ChatType.PRIVATE:
        # Synthesize a callback-style render
        class FakeQ:
            def __init__(self, msg, user):
                self.from_user = user
                self._msg = msg
            async def edit_message_text(self, *a, **kw):
                await self._msg.reply_text(*a, **kw)
        await render_group_picker(FakeQ(update.effective_message, user), context)
        return
    await ensure_group(chat)
    if not await is_admin(context.bot, chat.id, user.id):
        await update.effective_message.reply_text("Only administrators can use /settings.")
        return
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Open here", callback_data=f"st:openhere:{chat.id}")],
            [InlineKeyboardButton("👤 Open in Private Chat",
                                  url=f"https://t.me/{BOT_USERNAME}?start=settings_{chat.id}")],
        ]
    )
    await update.effective_message.reply_text(
        "Where do you want to open the settings menu?",
        reply_markup=kb,
    )


# Settings menus -------------------------------------------------------------
def kb_settings_root(chat_id: int) -> InlineKeyboardMarkup:
    cd = lambda x: f"st:{x}:{chat_id}"  # noqa: E731
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Regulation", callback_data=cd("rules")),
             InlineKeyboardButton("📨 Anti-Spam", callback_data=cd("spam"))],
            [InlineKeyboardButton("💬 Welcome", callback_data=cd("welcome")),
             InlineKeyboardButton("👁 Anti-Flood", callback_data=cd("flood"))],
            [InlineKeyboardButton("👋 Goodbye NEW", callback_data=cd("goodbye")),
             InlineKeyboardButton("🕉 Alphabets", callback_data=cd("alpha"))],
            [InlineKeyboardButton("🧠 Captcha", callback_data=cd("captcha")),
             InlineKeyboardButton("🔍 Checks NEW", callback_data=cd("checks"))],
            [InlineKeyboardButton("🆘 @Admin", callback_data=cd("admincall")),
             InlineKeyboardButton("🔒 Blocks", callback_data=cd("blocks"))],
            [InlineKeyboardButton("📸 Media", callback_data=cd("media")),
             InlineKeyboardButton("🔞 Porn", callback_data=cd("porn"))],
            [InlineKeyboardButton("❗ Warns", callback_data=cd("warns")),
             InlineKeyboardButton("🌙 Night", callback_data=cd("night"))],
            [InlineKeyboardButton("🔔 Tag", callback_data=cd("tag")),
             InlineKeyboardButton("🔗 Link", callback_data=cd("link"))],
            [InlineKeyboardButton("📑 Approval mode", callback_data=cd("approval"))],
            [InlineKeyboardButton("🗑 Deleting Messages", callback_data=cd("delmsg"))],
            [InlineKeyboardButton("🇬🇧 Lang", callback_data=cd("lang")),
             InlineKeyboardButton("✅ Close", callback_data=cd("close")),
             InlineKeyboardButton("▶️ Other", callback_data=cd("other"))],
        ]
    )


async def render_settings_root(query, chat_id: int) -> None:
    g = await db_one("SELECT title FROM groups WHERE chat_id=?", (chat_id,))
    title = g["title"] if g else str(chat_id)
    text = (
        "<b>SETTINGS</b>\n"
        f"Group: <b>{html.escape(title)}</b>\n\n"
        "Select one of the settings that you want to change."
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_settings_root(chat_id))


def back_button(chat_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton("↩️ Back", callback_data=f"st:open:{chat_id}")


# Welcome submenu -------------------------------------------------------------
async def render_welcome(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    status = "Active ✅" if s["welcome_on"] else "Inactive ❌"
    mode = (
        "Send the welcome message at every join of the users in the group"
        if s["welcome_mode"] == "always"
        else "Send the welcome only on first join"
    )
    text = (
        "💬 <b>Welcome Message</b>\n"
        "From this menu you can set a welcome message that will\n"
        "be sent when someone joins the group.\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Mode:</b> {mode}"
    )
    cd = lambda x: f"st:welcome:{chat_id}:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Turn off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} Turn on", callback_data=cd("on"))],
            [InlineKeyboardButton("🤝 Customize message", callback_data=f"st:welcomecz:{chat_id}")],
            [InlineKeyboardButton("🔔 Always send", callback_data=cd("always")),
             InlineKeyboardButton("1️⃣ Send 1st join", callback_data=cd("first"))],
            [InlineKeyboardButton(f"♻ Delete last message {onoff(s['welcome_delete_last'])}", callback_data=cd("dellast"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_welcome_customize(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    style_key = _setting_str(s, "welcome_card_style", "aurora")
    style_label = (WELCOME_CARD_STYLES.get(style_key) or WELCOME_CARD_STYLES["aurora"])["label"]
    card_status = onoff(_setting_truthy(s, "welcome_card_on", True))
    text = (
        "💬 <b>Welcome Message</b>\n"
        f"📄 Text {onoff(bool(s['welcome_text']))}\n"
        f"🎬 Media {onoff(bool(s['welcome_media']))}\n"
        f"🆎 Url Buttons {onoff(bool(s['welcome_buttons']))}\n"
        f"🎨 Auto card {card_status} (<i>{html.escape(style_label)}</i>)\n"
        "👉 Use the buttons below to choose what you want to set"
    )
    cd = lambda x: f"st:welcomecz:{chat_id}:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📄 Text", callback_data=cd("settext")),
             InlineKeyboardButton("👀 See", callback_data=cd("seetext"))],
            [InlineKeyboardButton("🎬 Media", callback_data=cd("setmedia")),
             InlineKeyboardButton("👀 See", callback_data=cd("seemedia"))],
            [InlineKeyboardButton("🆎 Url Buttons", callback_data=cd("setbtn")),
             InlineKeyboardButton("👀 See", callback_data=cd("seebtn"))],
            [InlineKeyboardButton(f"🖼 Media below the text {onoff(s['welcome_media_below'])}",
                                  callback_data=cd("below"))],
            [InlineKeyboardButton("🎨 Card style & invites", callback_data=cd("cardstyle"))],
            [InlineKeyboardButton("👀 Full preview", callback_data=cd("preview"))],
            [InlineKeyboardButton("📂 Select a Topic NEW", callback_data=cd("topic"))],
            [InlineKeyboardButton("↩️ Back", callback_data=f"st:welcome:{chat_id}")],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_welcome_cardstyle(query, chat_id: int) -> None:
    """Submenu: choose welcome-card style + toggle inviter line / auto-card."""
    s = await get_settings(chat_id)
    current = _setting_str(s, "welcome_card_style", "aurora")
    auto_on = _setting_truthy(s, "welcome_card_on", True)
    show_inv = _setting_truthy(s, "welcome_card_show_inviter", True)
    cur_label = (WELCOME_CARD_STYLES.get(current) or WELCOME_CARD_STYLES["aurora"])["label"]
    text = (
        "🎨 <b>Welcome card style</b>\n"
        f"Current style: <b>{html.escape(cur_label)}</b>\n"
        f"Auto card image: <b>{'ON' if auto_on else 'OFF'}</b>\n"
        f"Show inviter line: <b>{'ON' if show_inv else 'OFF'}</b>\n\n"
        "Pick a style below — the new welcome card will use it for "
        "every member that joins from now on. Use 👀 Preview to see "
        "what the card looks like for you."
    )
    cd = lambda x: f"st:welcomecz:{chat_id}:{x}"  # noqa: E731
    rows: list = []
    # 2 styles per row
    items = list(WELCOME_CARD_STYLES.items())
    for i in range(0, len(items), 2):
        row = []
        for key, cfg in items[i : i + 2]:
            mark = "✅ " if key == current else ""
            row.append(
                InlineKeyboardButton(
                    f"{mark}{cfg['label']}",
                    callback_data=cd(f"cstyle:{key}"),
                )
            )
        rows.append(row)
    rows.append([
        InlineKeyboardButton(
            f"🖼 Auto card {onoff(auto_on)}",
            callback_data=cd("ctoggle"),
        ),
        InlineKeyboardButton(
            f"👤 Show inviter {onoff(show_inv)}",
            callback_data=cd("cinviter"),
        ),
    ])
    rows.append([InlineKeyboardButton("👀 Preview", callback_data=cd("cpreview"))])
    rows.append([InlineKeyboardButton("↩️ Back", callback_data=cd("back"))])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


# Goodbye submenu -------------------------------------------------------------
async def render_goodbye(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    status = "Active ✅" if s["goodbye_on"] else "Off ❌"
    text = (
        "👋 <b>Goodbye</b>\n"
        "From this menu you can set a goodbye message that will\n"
        "be sent when someone leaves the group.\n\n"
        f"<b>Status:</b> {status}"
    )
    cd = lambda x: f"st:goodbye:{chat_id}:{x}"  # noqa: E731
    pm_mark = "✔" if s.get("goodbye_pm") else "✖"
    del_mark = "✔" if s.get("goodbye_delete_last") else "✖"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Turn off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} Turn on", callback_data=cd("on"))],
            [InlineKeyboardButton("✍️ Customize message", callback_data=cd("customize"))],
            [InlineKeyboardButton(f"💌 Send in private chat {pm_mark}", callback_data=cd("pm"))],
            [InlineKeyboardButton(f"♻️ Delete last message {del_mark}", callback_data=cd("dellast"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_goodbye_customize(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "👋 <b>Goodbye</b>\n"
        f"📄 Text {onoff(bool(s.get('goodbye_text')))}\n"
        f"🎬 Media {onoff(bool(s.get('goodbye_media')))}\n"
        f"🆎 Url Buttons {onoff(bool(s.get('goodbye_buttons')))}\n\n"
        "👉 Use the buttons below to choose what you want to set"
    )
    cd = lambda x: f"st:goodbye:{chat_id}:cz:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📄 Text", callback_data=cd("settext")),
             InlineKeyboardButton("👀 See", callback_data=cd("seetext"))],
            [InlineKeyboardButton("🎬 Media", callback_data=cd("setmedia")),
             InlineKeyboardButton("👀 See", callback_data=cd("seemedia"))],
            [InlineKeyboardButton("🆎 Url Buttons", callback_data=cd("setbtn")),
             InlineKeyboardButton("👀 See", callback_data=cd("seebtn"))],
            [InlineKeyboardButton("👀 Full preview", callback_data=cd("preview"))],
            [InlineKeyboardButton("📂 Select a Topic 🆕", callback_data=cd("topic"))],
            [InlineKeyboardButton("↩️ Back", callback_data=f"st:goodbye:{chat_id}")],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Anti-spam submenu -----------------------------------------------------------
PENALTY_LABELS = {
    "off": "❌ Off",
    "warn": "❗ Warn",
    "kick": "❕ Kick",
    "mute": "🔇 Mute",
    "ban": "🚫 Ban",
}
PENALTY_ORDER = ["off", "warn", "kick", "mute", "ban"]


def _penalty_button(current: str, target: str, key: str, chat_id: int, prefix: str) -> InlineKeyboardButton:
    label = PENALTY_LABELS[target]
    if current == target:
        label = f"·{label}·"
    return InlineKeyboardButton(label, callback_data=f"st:spam:{chat_id}:{prefix}:set:{key}:{target}")


async def render_antispam(query, chat_id: int) -> None:
    text = (
        "📨 <b>Anti-Spam</b>\n"
        "In this menu you can decide whether to protect your\n"
        "groups from unnecessary links, forwards, and quotes."
    )
    cd = lambda k: f"st:spam:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📘 Telegram links", callback_data=cd("links"))],
            [InlineKeyboardButton("📤 Forwarding", callback_data=cd("forwarding")),
             InlineKeyboardButton("💬 Quote", callback_data=cd("quote"))],
            [InlineKeyboardButton("🔗 Total links block", callback_data=cd("totallinks"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_antispam_links(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    cur = (s.get("antispam_links_action") or "off")
    deletion = "Yes" if s.get("antispam_links_delete") else "No"
    text = (
        "📘 <b>Telegram links</b>\n"
        "From this menu you can set a punishment for users who\n"
        "send messages that contain Telegram links.\n\n"
        "🎯 <b>Username Antispam:</b> this option triggers the antispam\n"
        "when a <b>username</b> considered spam is sent.\n\n"
        "🤖 <b>Bots Antispam:</b> this option triggers the antispam when\n"
        "a Bot link is sent.\n\n"
        f"Penalty: {cur.title()}\n"
        f"Deletion: {deletion}"
    )
    un_mark = "✔" if s.get("antispam_username_on") else "✖"
    bot_mark = "✔" if s.get("antispam_bots_on") else "✖"
    del_mark = "✔" if s.get("antispam_links_delete") else "✖"
    rows = [
        [
            _penalty_button(cur, "off", "links", chat_id, "links"),
            _penalty_button(cur, "warn", "links", chat_id, "links"),
            _penalty_button(cur, "kick", "links", chat_id, "links"),
        ],
        [
            _penalty_button(cur, "mute", "links", chat_id, "links"),
            _penalty_button(cur, "ban", "links", chat_id, "links"),
        ],
        [InlineKeyboardButton(f"🗑 Delete Messages {del_mark}",
                              callback_data=f"st:spam:{chat_id}:links:delete")],
        [InlineKeyboardButton(f"🎯 Username Antispam {un_mark}",
                              callback_data=f"st:spam:{chat_id}:links:username")],
        [InlineKeyboardButton(f"🤖 Bots Antispam {bot_mark}",
                              callback_data=f"st:spam:{chat_id}:links:bots")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:spam:{chat_id}"),
         InlineKeyboardButton("☀️ Exceptions", callback_data=f"st:spam:{chat_id}:links:exc")],
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


async def render_antispam_simple(query, chat_id: int, key: str, prefix: str, title: str, desc: str) -> None:
    s = await get_settings(chat_id)
    cur = (s.get(key) or "off")
    text = f"<b>{title}</b>\n{desc}\n\nPenalty: {cur.title()}"
    rows = [
        [
            _penalty_button(cur, "off", prefix, chat_id, prefix),
            _penalty_button(cur, "warn", prefix, chat_id, prefix),
            _penalty_button(cur, "kick", prefix, chat_id, prefix),
        ],
        [
            _penalty_button(cur, "mute", prefix, chat_id, prefix),
            _penalty_button(cur, "ban", prefix, chat_id, prefix),
        ],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:spam:{chat_id}")],
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


# Anti-flood submenu ----------------------------------------------------------
async def render_antiflood(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "👁 <b>Anti-Flood</b>\n\n"
        f"Status: {'Active ✅' if s['antiflood_on'] else 'Inactive ❌'}\n"
        f"Trigger: {s['antiflood_messages']} messages in {s['antiflood_seconds']} seconds\n"
        f"Action: {s['antiflood_action']}\n"
        f"Mute duration: {s['antiflood_mute_minutes']} min"
    )
    cd = lambda k: f"st:flood:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [InlineKeyboardButton("Messages -", callback_data=cd("msg-")),
             InlineKeyboardButton(str(s["antiflood_messages"]), callback_data="noop:n"),
             InlineKeyboardButton("Messages +", callback_data=cd("msg+"))],
            [InlineKeyboardButton("Seconds -", callback_data=cd("sec-")),
             InlineKeyboardButton(str(s["antiflood_seconds"]), callback_data="noop:n"),
             InlineKeyboardButton("Seconds +", callback_data=cd("sec+"))],
            [InlineKeyboardButton(f"Action: {s['antiflood_action']}", callback_data=cd("cycle_action"))],
            [InlineKeyboardButton("Mute -", callback_data=cd("mute-")),
             InlineKeyboardButton(f"{s['antiflood_mute_minutes']} min", callback_data="noop:n"),
             InlineKeyboardButton("Mute +", callback_data=cd("mute+"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Captcha submenu -------------------------------------------------------------
async def render_captcha(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "🧠 <b>Captcha</b>\n\n"
        f"Status: {'Active ✅' if s['captcha_on'] else 'Inactive ❌'}\n"
        f"Timeout: {s['captcha_timeout']} seconds\n\n"
        "When enabled, new members must solve a math captcha or be kicked."
    )
    cd = lambda k: f"st:captcha:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [InlineKeyboardButton("Timeout -10", callback_data=cd("t-")),
             InlineKeyboardButton("Timeout +10", callback_data=cd("t+"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Warns submenu ---------------------------------------------------------------
async def render_warns_settings(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "❗ <b>Warns</b>\n\n"
        f"Limit: {s['warn_limit']}\n"
        f"Action when limit reached: {s['warn_action']}"
    )
    cd = lambda k: f"st:warns:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Limit -1", callback_data=cd("lim-")),
             InlineKeyboardButton(str(s["warn_limit"]), callback_data="noop:n"),
             InlineKeyboardButton("Limit +1", callback_data=cd("lim+"))],
            [InlineKeyboardButton(f"Action: {s['warn_action']}", callback_data=cd("cycle_action"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Night submenu ---------------------------------------------------------------
async def render_night(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "🌙 <b>Night Mode</b>\n\n"
        f"Status: {'Active ✅' if s['night_on'] else 'Inactive ❌'}\n"
        f"Active from {s['night_start']:02d}:00 to {s['night_end']:02d}:00\n\n"
        "When active the group is read-only during night hours."
    )
    cd = lambda k: f"st:night:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [InlineKeyboardButton("Start -1", callback_data=cd("s-")),
             InlineKeyboardButton(f"{s['night_start']:02d}:00", callback_data="noop:n"),
             InlineKeyboardButton("Start +1", callback_data=cd("s+"))],
            [InlineKeyboardButton("End -1", callback_data=cd("e-")),
             InlineKeyboardButton(f"{s['night_end']:02d}:00", callback_data="noop:n"),
             InlineKeyboardButton("End +1", callback_data=cd("e+"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Approval submenu ------------------------------------------------------------
async def render_approval(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    status = "Activated" if s["approval_on"] else "Deactivated"
    text = (
        "📑 <b>Approval mode</b>\n"
        "Through this menu you can decide to delegate the\n"
        "management of group approvals to the bot, for users who\n"
        "ask to enter via link with approval.\n\n"
        "🧠 Since the <u>Captcha</u> is not active, if you enable\n"
        "Auto-approval, <b>users will be automatically accepted into\n"
        "the group</b> as soon as they make a request (unless another\n"
        "check is triggered).\n\n"
        "👥 If a user joins with a <u>link</u> that <u>doesn't require approval</u>,\n"
        "the procedures will be carried out regularly <b>in the group</b>.\n\n"
        f"💡 <b>Status:</b>\n• Auto-approval: {status}"
    )
    cd = lambda k: f"st:approval:{chat_id}:{k}"  # noqa: E731
    lock = "🔓" if s["approval_on"] else "🔒"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{lock} Auto-approval ⤵", callback_data=cd("toggle"))],
            [InlineKeyboardButton(f"{OFF} Turn off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} Turn on", callback_data=cd("on"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Blocks submenu --------------------------------------------------------------
async def render_blocks(query, chat_id: int) -> None:
    rows = await db_all("SELECT user_id FROM blocks WHERE chat_id=?", (chat_id,))
    text = (
        "🔒 <b>Blocks</b>\n\n"
        f"Currently blocked users: <b>{len(rows)}</b>\n\n"
        "Use /block (in reply) and /unblock to manage the blocklist.\n"
        "Use /blocklist to view all blocked users."
    )
    kb = InlineKeyboardMarkup([[back_button(chat_id)]])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Media submenu ---------------------------------------------------------------
MEDIA_ITEMS = [
    ("📖", "Story", "media_story"),
    ("🖼", "Photo", "media_photo"),
    ("🎞", "Video", "media_video"),
    ("🖼", "Album", "media_album"),
    ("🎬", "GIF", "media_gif"),
    ("🎤", "Voice", "media_voice"),
    ("🎧", "Audio", "media_audio"),
    ("🩰", "Sticker", "media_sticker"),
    ("✨", "Animated stickers", "media_animsticker"),
    ("🎮", "Animated Games", "media_animgame"),
    ("😀", "Animated Emoji", "media_animemoji"),
    ("👾", "Premium Emoji", "media_premium"),
    ("📁", "File", "media_doc"),
]

ACTION_LABELS = {
    "off": "✅",
    "warn": "❗",
    "kick": "❕",
    "mute": "🔊",
    "ban": "🚫",
    "del": "🗑",
}
ACTION_ORDER = ["off", "warn", "kick", "mute", "ban", "del"]


def _action_button(current: str, target: str, key: str, chat_id: int) -> InlineKeyboardButton:
    """Show the action label, highlighted with brackets if it's the current setting."""
    label = ACTION_LABELS[target]
    if current == target:
        label = f"·{label}·"
    return InlineKeyboardButton(label, callback_data=f"st:media:{chat_id}:set:{key}:{target}")


async def render_media(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "📸 <b>Media Block</b>\n\n"
        "❗ = Warn | ❕ = Kick\n"
        "🔊 = Mute | 🚫 = Ban\n"
        "🗑 = Deletion\n"
        "✅ = Off (allowed)\n"
        "<i>Tap an icon next to a media type to set the action.</i>\n\n"
    )
    legend_lines = []
    for emoji, label, key in MEDIA_ITEMS:
        cur = (s.get(key) or "off")
        legend_lines.append(f"{emoji} {label} = {ACTION_LABELS.get(cur, '✅')} {cur.title()}")
    text += "\n".join(legend_lines)

    rows = []
    for emoji, _label, key in MEDIA_ITEMS:
        cur = (s.get(key) or "off")
        rows.append(
            [
                InlineKeyboardButton(emoji, callback_data="noop:lbl"),
                _action_button(cur, "off", key, chat_id),
                _action_button(cur, "warn", key, chat_id),
                _action_button(cur, "kick", key, chat_id),
                _action_button(cur, "mute", key, chat_id),
                _action_button(cur, "ban", key, chat_id),
                _action_button(cur, "del", key, chat_id),
            ]
        )
    rows.append([back_button(chat_id)])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


# Porn / Tag / Link / Alphabets / Checks / @Admin / Other / Lang -------------
async def render_simple_toggle(query, chat_id: int, title: str, key: str, label: str) -> None:
    s = await get_settings(chat_id)
    text = f"<b>{title}</b>\n\nStatus: {'Active ✅' if s[key] else 'Inactive ❌'}"
    cd = lambda k: f"st:{label}:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_alphabets(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = "🕉 <b>Alphabets</b>\nBlock messages written in specific alphabets."
    cd = lambda k: f"st:alpha:{chat_id}:{k}"  # noqa: E731
    rows = [
        [InlineKeyboardButton("Arabic", callback_data="noop:lbl"),
         InlineKeyboardButton(onoff(s["antispam_arabic"]), callback_data=cd("arabic"))],
        [InlineKeyboardButton("Chinese", callback_data="noop:lbl"),
         InlineKeyboardButton(onoff(s["antispam_chinese"]), callback_data=cd("chinese"))],
        [back_button(chat_id)],
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


async def render_link_settings(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "🔗 <b>Link filter</b>\n\n"
        f"Block links: {'Yes ✅' if s['block_links'] else 'No ❌'}\n"
        f"Whitelisted domains: managed via /addwhitelist /delwhitelist"
    )
    cd = lambda k: f"st:link:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_tag_settings(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "🔔 <b>Tag filter</b>\n\n"
        f"Block excessive mentions: {'Yes ✅' if s['tag_on'] else 'No ❌'}\n"
        f"Max mentions per message: {s['max_mentions']}"
    )
    cd = lambda k: f"st:tag:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [InlineKeyboardButton("Max -1", callback_data=cd("m-")),
             InlineKeyboardButton(str(s["max_mentions"]), callback_data="noop:n"),
             InlineKeyboardButton("Max +1", callback_data=cd("m+"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_checks(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "🔍 <b>Checks</b>\n\n"
        f"Edit checks: {'Active ✅' if s['edit_check_on'] else 'Off ❌'}\n"
        "When active, the bot inspects edited messages with the same anti-spam rules."
    )
    cd = lambda k: f"st:checks:{chat_id}:{k}"  # noqa: E731
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{OFF} Off", callback_data=cd("off")),
             InlineKeyboardButton(f"{ON} On", callback_data=cd("on"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_admincall(query, chat_id: int) -> None:
    text = (
        "🆘 <b>@admin call</b>\n\n"
        "Members can request admin attention with /report (in reply) or /admin.\n"
        "Reports are forwarded to all administrators of the group."
    )
    kb = InlineKeyboardMarkup([[back_button(chat_id)]])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


def kb_other(chat_id: int) -> InlineKeyboardMarkup:
    cd = lambda x: f"st:other:{chat_id}:{x}"  # noqa: E731
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📂 Topic", callback_data=cd("topic"))],
            [InlineKeyboardButton("🆎 Banned Words", callback_data=cd("banned"))],
            [InlineKeyboardButton("🕐 Recurring messages", callback_data=cd("recurring"))],
            [InlineKeyboardButton("👥 Members Management", callback_data=cd("members"))],
            [InlineKeyboardButton("🥸 Masked users", callback_data=cd("masked"))],
            [InlineKeyboardButton("📣 Discussion group 🆕", callback_data=cd("discussion"))],
            [InlineKeyboardButton("⌨️ Personal Commands", callback_data=cd("personal"))],
            [InlineKeyboardButton("🪄 Magic Stickers&GIFs", callback_data=cd("magic"))],
            [InlineKeyboardButton("📏 Message length", callback_data=cd("msglen"))],
            [InlineKeyboardButton("📢 Channels management 🆕", callback_data=cd("channels"))],
            [
                InlineKeyboardButton("📝 Permissions", callback_data=cd("perms")),
                InlineKeyboardButton("📜 Log Channel", callback_data=cd("logchan")),
            ],
            [
                back_button(chat_id),
                InlineKeyboardButton("✅ Close", callback_data=f"st:close:{chat_id}"),
                InlineKeyboardButton("🇬🇧 Lang", callback_data=f"st:lang:{chat_id}"),
            ],
        ]
    )


async def render_other(query, chat_id: int) -> None:
    g = await db_one("SELECT title FROM groups WHERE chat_id=?", (chat_id,))
    title = g["title"] if g else str(chat_id)
    text = (
        "<b>SETTINGS</b>\n"
        f"Group: <b>{html.escape(title)}</b>\n\n"
        "Select one of the additional settings you want to change."
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=kb_other(chat_id),
    )


_SETTINGS_LANGUAGES = LANGUAGES  # inlined from lang.py
LANGUAGES = list(_SETTINGS_LANGUAGES)


async def render_lang(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    cur = (s.get("lang") or "en")
    cur_label = next((lbl for code, lbl in LANGUAGES if code == cur), "🇬🇧 English (Default)")
    text = (
        "🌐 <b>Language</b>\n\n"
        "Choose the language for the bot in this group.\n"
        "English is the default.\n\n"
        f"<b>Current:</b> {cur_label}"
    )
    rows = []
    for code, label in LANGUAGES:
        marker = "✅ " if code == cur else ""
        rows.append([InlineKeyboardButton(f"{marker}{label}",
                                          callback_data=f"st:lang:{chat_id}:set:{code}")])
    rows.append([back_button(chat_id)])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


async def render_rules_settings(query, chat_id: int) -> None:
    g = await db_one("SELECT rules FROM groups WHERE chat_id=?", (chat_id,))
    rules = (g["rules"] if g else "") or "(no regulation set)"
    text = (
        "📋 <b>Regulation</b>\n\n"
        f"<i>{html.escape(rules)[:1500]}</i>\n\n"
        "Use /setrules in the group to set the regulation."
    )
    kb = InlineKeyboardMarkup([[back_button(chat_id)]])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# Deleting Messages submenu ---------------------------------------------------
async def render_delmsg(query, chat_id: int) -> None:
    text = "🗑 <b>Deleting Messages</b>\nWhat messages do you want the Bot to delete?"
    cd = lambda x: f"st:delmsg:{chat_id}:{x}"  # noqa: E731
    s = await get_settings(chat_id)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🤖 Commands {onoff(s['delete_commands'])}", callback_data=cd("cmd"))],
            [InlineKeyboardButton(f"🤫 Global Silence {onoff(s['silence_on'])}", callback_data=cd("silence"))],
            [InlineKeyboardButton(f"✏ Edit Checks {onoff(s['edit_check_on'])}", callback_data=cd("edit"))],
            [InlineKeyboardButton("💥 Service Messages", callback_data=f"st:service:{chat_id}")],
            [InlineKeyboardButton(f"🕐 Scheduled deletion {s['scheduled_delete']}s", callback_data=cd("sched"))],
            [InlineKeyboardButton(f"📓 Block cancellation {onoff(s['block_cancel'])}", callback_data=cd("blockcancel"))],
            [InlineKeyboardButton("💥 Delete all messages", callback_data=cd("nuke1"))],
            [InlineKeyboardButton(f"♻ Self-destruction {s['selfdestruct_seconds']}s", callback_data=cd("selfd"))],
            [back_button(chat_id)],
        ]
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_service(query, chat_id: int) -> None:
    s = await get_settings(chat_id)
    text = (
        "💥 <b>Service Messages</b>\n\n"
        "The Service Messages are those messages sent by\n"
        "Telegram when someone joins or exits the group.\n\n"
        "<b>Status:</b>\n"
        f"Join: after {s['service_join_minutes']} mins\n"
        f"Exit: after {s['service_exit_minutes']} mins\n"
        f"New Photo: {'On' if s['service_photo'] else 'Off'}\n"
        f"New Title: {'On' if s['service_title'] else 'Off'}\n"
        f"Pinned messages: {'On' if s['service_pinned'] else 'Off'}\n"
        f"Topics: {'On' if s['service_topic'] else 'Off'}\n"
        f"Boost: {'On' if s['service_boost'] else 'Off'}\n"
        f"Video Chats invites: {'On' if s['service_videochat'] else 'Off'}\n"
        f"Checklist: {'On' if s['service_checklist'] else 'Off'}"
    )
    cd = lambda k: f"st:service:{chat_id}:{k}"  # noqa: E731
    rows = [
        [InlineKeyboardButton("Join", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("join_off")),
         InlineKeyboardButton(ON, callback_data=cd("join_on"))],
        [InlineKeyboardButton(" ", callback_data="noop:lbl"),
         InlineKeyboardButton("-1", callback_data=cd("join-")),
         InlineKeyboardButton("+1", callback_data=cd("join+"))],
        [InlineKeyboardButton("Exit", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("exit_off")),
         InlineKeyboardButton(ON, callback_data=cd("exit_on"))],
        [InlineKeyboardButton(" ", callback_data="noop:lbl"),
         InlineKeyboardButton("-1", callback_data=cd("exit-")),
         InlineKeyboardButton("+1", callback_data=cd("exit+"))],
        [InlineKeyboardButton("Photos", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("photo_off")),
         InlineKeyboardButton(ON, callback_data=cd("photo_on"))],
        [InlineKeyboardButton("Title", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("title_off")),
         InlineKeyboardButton(ON, callback_data=cd("title_on"))],
        [InlineKeyboardButton("Pinned", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("pin_off")),
         InlineKeyboardButton(ON, callback_data=cd("pin_on"))],
        [InlineKeyboardButton("Topic", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("topic_off")),
         InlineKeyboardButton(ON, callback_data=cd("topic_on"))],
        [InlineKeyboardButton("Boost", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("boost_off")),
         InlineKeyboardButton(ON, callback_data=cd("boost_on"))],
        [InlineKeyboardButton("Video Chats", callback_data="noop:lbl"),
         InlineKeyboardButton(OFF, callback_data=cd("vc_off")),
         InlineKeyboardButton(ON, callback_data=cd("vc_on"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:delmsg:{chat_id}")],
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))


# Settings dispatcher --------------------------------------------------------
async def cb_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    # patterns we use:
    # st:open:<chat>
    # st:<menu>:<chat>
    # st:<menu>:<chat>:<key>
    # st:welcomecz:<chat>(:<key>)
    # st:service:<chat>(:<key>)
    if len(parts) < 3:
        return
    menu = parts[1]
    try:
        chat_id = int(parts[2])
    except ValueError:
        return
    if not await is_admin(context.bot, chat_id, q.from_user.id):
        await q.answer("Admins only.", show_alert=True)
        return
    sub = parts[3] if len(parts) >= 4 else ""

    if menu == "open":
        await render_settings_root(q, chat_id)
        return
    if menu == "rules":
        await render_rules_settings(q, chat_id)
        return
    if menu == "spam":
        # parts: ["st", "spam", chat_id, sub, ...]
        if not sub:
            await render_antispam(q, chat_id)
            return
        # Penalty submenu actions: st:spam:<chat>:<section>:set:<key>:<action>
        if len(parts) >= 7 and parts[4] == "set":
            section = sub  # links | forwarding | quote | totallinks
            action = parts[6]
            key_map = {
                "links": "antispam_links_action",
                "forwarding": "antispam_forward_action",
                "quote": "antispam_quote_action",
                "totallinks": "antispam_totallinks_action",
            }
            if section in key_map and action in PENALTY_ORDER:
                await set_setting(chat_id, key_map[section], action)
        # Toggle sub-options on the Telegram links page
        elif sub == "links" and len(parts) >= 5:
            opt = parts[4] if len(parts) >= 5 else ""
            if opt == "delete":
                await toggle_setting(chat_id, "antispam_links_delete")
            elif opt == "username":
                await toggle_setting(chat_id, "antispam_username_on")
            elif opt == "bots":
                await toggle_setting(chat_id, "antispam_bots_on")
            elif opt == "exc":
                await q.answer("Use /addexception and /delexception in group.", show_alert=True)
            await render_antispam_links(q, chat_id)
            return

        if sub == "links":
            await render_antispam_links(q, chat_id)
        elif sub == "forwarding":
            await render_antispam_simple(
                q, chat_id, "antispam_forward_action", "forwarding",
                "📤 Forwarding",
                "From this menu you can set a punishment for users who forward\nmessages from channels or other chats.",
            )
        elif sub == "quote":
            await render_antispam_simple(
                q, chat_id, "antispam_quote_action", "quote",
                "💬 Quote",
                "From this menu you can set a punishment for users who\nreply quoting messages from outside this group.",
            )
        elif sub == "totallinks":
            await render_antispam_simple(
                q, chat_id, "antispam_totallinks_action", "totallinks",
                "🔗 Total links block",
                "From this menu you can set a punishment for users who send\nany kind of link (including web URLs).",
            )
        else:
            await render_antispam(q, chat_id)
        return
    if menu == "welcome":
        if sub == "off":
            await set_setting(chat_id, "welcome_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "welcome_on", 1)
        elif sub == "always":
            await set_setting(chat_id, "welcome_mode", "always")
        elif sub == "first":
            await set_setting(chat_id, "welcome_mode", "first")
        elif sub == "dellast":
            await toggle_setting(chat_id, "welcome_delete_last")
        await render_welcome(q, chat_id)
        return
    if menu == "welcomecz":
        await handle_welcome_customize(q, context, chat_id, sub)
        return
    if menu == "goodbye":
        if sub == "off":
            await set_setting(chat_id, "goodbye_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "goodbye_on", 1)
        elif sub == "pm":
            await toggle_setting(chat_id, "goodbye_pm")
        elif sub == "dellast":
            await toggle_setting(chat_id, "goodbye_delete_last")
        elif sub == "customize":
            await render_goodbye_customize(q, chat_id)
            return
        elif sub == "cz" and len(parts) >= 5:
            action = parts[4]
            if action == "settext":
                await stage_input(q.from_user.id, q.message.chat.id, chat_id, "goodbye_text")
                await q.message.reply_text(
                    f"{fmt_user(q.from_user)}, send the goodbye message text now. Use /cancel to abort.",
                    parse_mode=ParseMode.HTML,
                )
                return
            elif action == "setmedia":
                await stage_input(q.from_user.id, q.message.chat.id, chat_id, "goodbye_media")
                await q.message.reply_text(
                    "Send a photo / video / sticker / GIF to use as the goodbye media. /cancel to abort."
                )
                return
            elif action == "setbtn":
                await stage_input(q.from_user.id, q.message.chat.id, chat_id, "goodbye_buttons")
                await q.message.reply_text(
                    "Send button definitions, e.g. <code>Title - https://t.me/...</code>. /cancel to abort.",
                    parse_mode=ParseMode.HTML,
                )
                return
            elif action == "seetext":
                txt = (await get_settings(chat_id)).get("goodbye_text") or "(not set)"
                await q.message.reply_text(txt[:3500])
                return
            elif action == "seemedia":
                m = (await get_settings(chat_id)).get("goodbye_media") or ""
                await q.message.reply_text(f"Goodbye media file_id: <code>{html.escape(m)}</code>" if m else "(no media set)",
                                           parse_mode=ParseMode.HTML)
                return
            elif action == "seebtn":
                b = (await get_settings(chat_id)).get("goodbye_buttons") or ""
                await q.message.reply_text(f"<pre>{html.escape(b)}</pre>" if b else "(no buttons set)",
                                           parse_mode=ParseMode.HTML)
                return
            elif action == "preview":
                await q.message.reply_text("Preview will be sent the next time a member leaves.")
                return
            elif action == "topic":
                await q.message.reply_text("Use /topic_goodbye in the topic where the message should be sent.")
                return
            await render_goodbye_customize(q, chat_id)
            return
        await render_goodbye(q, chat_id)
        return
    if menu == "alpha":
        if sub == "arabic":
            await toggle_setting(chat_id, "antispam_arabic")
        elif sub == "chinese":
            await toggle_setting(chat_id, "antispam_chinese")
        await render_alphabets(q, chat_id)
        return
    if menu == "captcha":
        if sub == "off":
            await set_setting(chat_id, "captcha_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "captcha_on", 1)
        elif sub == "t-":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "captcha_timeout", max(15, s["captcha_timeout"] - 10))
        elif sub == "t+":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "captcha_timeout", min(600, s["captcha_timeout"] + 10))
        await render_captcha(q, chat_id)
        return
    if menu == "checks":
        if sub == "off":
            await set_setting(chat_id, "edit_check_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "edit_check_on", 1)
        await render_checks(q, chat_id)
        return
    if menu == "admincall":
        await render_admincall(q, chat_id)
        return
    if menu == "blocks":
        await render_blocks(q, chat_id)
        return
    if menu == "media":
        # New format: st:media:<chat>:set:<key>:<action>
        if sub == "set" and len(parts) >= 6:
            key = parts[4]
            action = parts[5]
            valid_keys = {k for _, _, k in MEDIA_ITEMS}
            if key in valid_keys and action in ACTION_ORDER:
                await set_setting(chat_id, key, action)
        # Backwards-compat: cycle action if just a key was passed
        elif sub:
            valid_keys = {k for _, _, k in MEDIA_ITEMS}
            if sub in valid_keys:
                s = await get_settings(chat_id)
                cur = (s.get(sub) or "off")
                idx = (ACTION_ORDER.index(cur) + 1) % len(ACTION_ORDER) if cur in ACTION_ORDER else 0
                await set_setting(chat_id, sub, ACTION_ORDER[idx])
        await render_media(q, chat_id)
        return
    if menu == "openhere":
        await render_settings_root(q, chat_id)
        return
    if menu == "porn":
        if sub == "off":
            await set_setting(chat_id, "porn_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "porn_on", 1)
        await render_simple_toggle(q, chat_id, "🔞 Porn filter", "porn_on", "porn")
        return
    if menu == "warns":
        if sub == "lim+":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "warn_limit", min(20, s["warn_limit"] + 1))
        elif sub == "lim-":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "warn_limit", max(1, s["warn_limit"] - 1))
        elif sub == "cycle_action":
            cycle = ["mute", "kick", "ban"]
            s = await get_settings(chat_id)
            idx = (cycle.index(s["warn_action"]) + 1) % len(cycle) if s["warn_action"] in cycle else 0
            await set_setting(chat_id, "warn_action", cycle[idx])
        await render_warns_settings(q, chat_id)
        return
    if menu == "night":
        if sub == "off":
            await set_setting(chat_id, "night_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "night_on", 1)
        elif sub == "s-":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "night_start", (s["night_start"] - 1) % 24)
        elif sub == "s+":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "night_start", (s["night_start"] + 1) % 24)
        elif sub == "e-":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "night_end", (s["night_end"] - 1) % 24)
        elif sub == "e+":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "night_end", (s["night_end"] + 1) % 24)
        await render_night(q, chat_id)
        return
    if menu == "tag":
        if sub == "off":
            await set_setting(chat_id, "tag_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "tag_on", 1)
        elif sub == "m+":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "max_mentions", min(50, s["max_mentions"] + 1))
        elif sub == "m-":
            s = await get_settings(chat_id)
            await set_setting(chat_id, "max_mentions", max(1, s["max_mentions"] - 1))
        await render_tag_settings(q, chat_id)
        return
    if menu == "link":
        if sub == "off":
            await set_setting(chat_id, "block_links", 0)
        elif sub == "on":
            await set_setting(chat_id, "block_links", 1)
        await render_link_settings(q, chat_id)
        return
    if menu == "approval":
        if sub == "off":
            await set_setting(chat_id, "approval_on", 0)
        elif sub == "on":
            await set_setting(chat_id, "approval_on", 1)
        elif sub == "toggle":
            await toggle_setting(chat_id, "approval_on")
        await render_approval(q, chat_id)
        return
    if menu == "delmsg":
        await handle_delmsg(q, chat_id, sub)
        return
    if menu == "service":
        await handle_service(q, chat_id, sub)
        return
    if menu == "flood":
        await handle_flood(q, chat_id, sub)
        return
    if menu == "lang":
        if sub == "set" and len(parts) >= 5:
            code = parts[4]
            valid = {c for c, _ in LANGUAGES}
            if code in valid:
                # Make sure the chat actually has a row in group_settings;
                # otherwise the bare UPDATE in set_setting() silently saves
                # nothing for chats that have never used /settings before.
                await db_exec(
                    "INSERT OR IGNORE INTO group_settings(chat_id) VALUES (?)",
                    (chat_id,),
                )
                await set_setting(chat_id, "lang", code)
                _chat_lang_invalidate(chat_id)
                label = next(lbl for c, lbl in LANGUAGES if c == code)
                # NOTE: the dispatcher above already called q.answer(); a second
                # answer raises "Query is too old" in Telegram and would abort
                # the rest of this branch (including the menu re-render with
                # the new ✅ marker). Wrap defensively.
                try:
                    await q.answer(f"Language set: {label}")
                except TelegramError:
                    pass
                # Send the "I will speak <lang> here" confirmation in the
                # newly-selected language so the user immediately sees the
                # change take effect (matches Miss Rose UX).
                try:
                    confirm_text = _lang_t(code, "lang_changed")
                    if confirm_text and confirm_text != "lang_changed":
                        await context.bot.send_message(
                            chat_id, confirm_text,
                        )
                except Exception:
                    log.exception("lang confirmation send failed")
        await render_lang(q, chat_id)
        return
    if menu == "other":
        await handle_other(q, context, chat_id, sub, parts)
        return
    if menu == "close":
        try:
            await q.edit_message_text("Settings closed.")
        except TelegramError:
            pass
        return


async def handle_flood(q, chat_id: int, sub: str) -> None:
    s = await get_settings(chat_id)
    if sub == "off":
        await set_setting(chat_id, "antiflood_on", 0)
    elif sub == "on":
        await set_setting(chat_id, "antiflood_on", 1)
    elif sub == "msg+":
        await set_setting(chat_id, "antiflood_messages", min(50, s["antiflood_messages"] + 1))
    elif sub == "msg-":
        await set_setting(chat_id, "antiflood_messages", max(2, s["antiflood_messages"] - 1))
    elif sub == "sec+":
        await set_setting(chat_id, "antiflood_seconds", min(120, s["antiflood_seconds"] + 1))
    elif sub == "sec-":
        await set_setting(chat_id, "antiflood_seconds", max(1, s["antiflood_seconds"] - 1))
    elif sub == "cycle_action":
        cycle = ["mute", "kick", "ban"]
        idx = (cycle.index(s["antiflood_action"]) + 1) % len(cycle) if s["antiflood_action"] in cycle else 0
        await set_setting(chat_id, "antiflood_action", cycle[idx])
    elif sub == "mute+":
        await set_setting(chat_id, "antiflood_mute_minutes", min(10080, s["antiflood_mute_minutes"] + 15))
    elif sub == "mute-":
        await set_setting(chat_id, "antiflood_mute_minutes", max(1, s["antiflood_mute_minutes"] - 15))
    await render_antiflood(q, chat_id)


async def handle_delmsg(q, chat_id: int, sub: str) -> None:
    s = await get_settings(chat_id)
    if sub == "cmd":
        await toggle_setting(chat_id, "delete_commands")
    elif sub == "silence":
        await toggle_setting(chat_id, "silence_on")
    elif sub == "edit":
        await toggle_setting(chat_id, "edit_check_on")
    elif sub == "sched":
        await set_setting(chat_id, "scheduled_delete", (s["scheduled_delete"] + 30) % 360)
    elif sub == "blockcancel":
        await toggle_setting(chat_id, "block_cancel")
    elif sub == "all":
        # legacy: kept as no-op (button now uses nuke flow)
        pass
    elif sub == "nuke1":
        await render_nuke_step(q, chat_id, 1)
        return
    elif sub == "nuke2":
        await render_nuke_step(q, chat_id, 2)
        return
    elif sub == "nuke3":
        await render_nuke_step(q, chat_id, 3)
        return
    elif sub == "nukego":
        await execute_nuke(q, chat_id)
        return
    elif sub == "selfd":
        await set_setting(chat_id, "selfdestruct_seconds", (s["selfdestruct_seconds"] + 30) % 360)
    await render_delmsg(q, chat_id)


async def render_nuke_step(q, chat_id: int, step: int) -> None:
    """Render one of three confirmation screens before the group-wide deletion."""
    user_id = q.from_user.id
    chat_title_row = await db_one("SELECT title FROM groups WHERE chat_id=?", (chat_id,))
    title = chat_title_row["title"] if chat_title_row else str(chat_id)

    remaining = await get_nuke_cooldown_remaining(chat_id, user_id)
    if remaining and remaining > 0:
        h = remaining // 3600
        m = (remaining % 3600) // 60
        text = (
            "🚫 <b>Cooldown active</b>\n\n"
            f"You already used <b>Delete all messages</b> in <b>{html.escape(title)}</b>.\n"
            f"Try again in <b>{h}h {m}m</b>."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=f"st:delmsg:{chat_id}")]])
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    cd_yes = f"st:delmsg:{chat_id}:nuke{step + 1}" if step < 3 else f"st:delmsg:{chat_id}:nukego"
    cd_no = f"st:delmsg:{chat_id}"

    if step == 1:
        text = (
            "💥 <b>Delete all messages</b>\n\n"
            f"Group: <b>{html.escape(title)}</b>\n\n"
            "⚠️ This will <b>permanently delete every message</b> in this group "
            "for everyone. This cannot be undone.\n\n"
            "Continue?"
        )
        yes_label = "✅ Yes, continue"
    elif step == 2:
        text = (
            "💥 <b>Are you absolutely sure?</b>\n\n"
            f"Group: <b>{html.escape(title)}</b>\n\n"
            "⚠️ A user account will be added to the group as admin, "
            "wipe all messages in seconds, then leave.\n\n"
            "Tap Yes again to confirm."
        )
        yes_label = "✅ Yes, I'm sure"
    else:
        text = (
            "💥 <b>FINAL WARNING</b>\n\n"
            f"Group: <b>{html.escape(title)}</b>\n\n"
            f"⚠️ After this, you will be on a <b>{NUKE_COOLDOWN_HOURS}h cooldown</b> "
            "and cannot use this button again in this group.\n\n"
            "Tap the red button to wipe everything now."
        )
        yes_label = "💥 DELETE EVERYTHING NOW"

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(yes_label, callback_data=cd_yes)],
            [InlineKeyboardButton("✖ No, cancel", callback_data=cd_no)],
        ]
    )
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def get_nuke_cooldown_remaining(chat_id: int, user_id: int) -> int:
    row = await db_one(
        "SELECT expires_at FROM nuke_cooldowns WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    if not row:
        return 0
    return max(0, int(row["expires_at"]) - now_ts())


async def set_nuke_cooldown(chat_id: int, user_id: int) -> None:
    expires = now_ts() + NUKE_COOLDOWN_HOURS * 3600
    await db_exec(
        "INSERT OR REPLACE INTO nuke_cooldowns(chat_id, user_id, expires_at) VALUES (?,?,?)",
        (chat_id, user_id, expires),
    )


async def execute_nuke(q, chat_id: int) -> None:
    """Run the user account, join the group, delete everything, leave, set cooldown."""
    user_id = q.from_user.id
    bot: Bot = q.get_bot()

    # gate: cooldown
    remaining = await get_nuke_cooldown_remaining(chat_id, user_id)
    if remaining > 0:
        await render_nuke_step(q, chat_id, 1)
        return

    # gate: pyrogram + creds
    if not PYROGRAM_AVAILABLE:
        await q.edit_message_text(
            "❌ Pyrogram library not installed. Cannot run user account.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=f"st:delmsg:{chat_id}")]]),
        )
        return
    if not (USERBOT_API_ID and USERBOT_API_HASH and USERBOT_SESSION):
        await q.edit_message_text(
            "❌ User account not configured.\nMissing USERBOT_API_ID / USERBOT_API_HASH / USERBOT_SESSION.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=f"st:delmsg:{chat_id}")]]),
        )
        return

    await q.edit_message_text("🧹 Preparing… creating one-time invite link.", parse_mode=ParseMode.HTML)

    # 1) Create a one-time invite link
    try:
        invite = await bot.create_chat_invite_link(chat_id, member_limit=1)
        invite_link = invite.invite_link
    except TelegramError as e:
        await q.edit_message_text(
            f"❌ Couldn't create invite link: {html.escape(str(e))}\n"
            f"Make sure the bot is admin with <b>Invite users</b> permission.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=f"st:delmsg:{chat_id}")]]),
        )
        return

    deleted = 0
    err: Optional[str] = None
    userbot_id = 0

    try:
        async with PyroClient(
            "missrose_userbot",
            api_id=USERBOT_API_ID,
            api_hash=USERBOT_API_HASH,
            session_string=USERBOT_SESSION,
            in_memory=True,
            no_updates=True,
        ) as ub:
            me = await ub.get_me()
            userbot_id = me.id

            # 2) Join via invite (skip if already a member)
            try:
                await q.edit_message_text("🧹 User account joining the group…", parse_mode=ParseMode.HTML)
                await ub.join_chat(invite_link)
            except Exception as e:
                log.info("userbot join: %s", e)

            await asyncio.sleep(2)

            # 3) Promote user account to admin with delete permission
            try:
                await q.edit_message_text("🧹 Promoting user account to admin…", parse_mode=ParseMode.HTML)
                await bot.promote_chat_member(
                    chat_id,
                    userbot_id,
                    can_delete_messages=True,
                    can_invite_users=True,
                    can_restrict_members=False,
                    can_pin_messages=False,
                    can_change_info=False,
                    can_promote_members=False,
                    can_manage_chat=True,
                    can_manage_video_chats=False,
                )
            except TelegramError as e:
                log.warning("promote userbot: %s", e)

            await asyncio.sleep(1)

            # 4) Iterate full history and delete in batches of 100
            await q.edit_message_text("🧹 Deleting all messages…", parse_mode=ParseMode.HTML)
            buf: list[int] = []
            async for msg in ub.get_chat_history(chat_id):
                buf.append(msg.id)
                if len(buf) >= 100:
                    deleted += await _ub_delete_batch(ub, chat_id, buf)
                    buf = []
            if buf:
                deleted += await _ub_delete_batch(ub, chat_id, buf)

            # 5) Confirmation message in the group
            try:
                await bot.send_message(
                    chat_id,
                    "💥 <b>Cleared all messages</b>",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass

            # 6) Userbot leaves
            try:
                await ub.leave_chat(chat_id, delete=False)
            except Exception as e:
                log.info("userbot leave: %s", e)

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        log.exception("nuke failed")

    # 7) Cooldown ONLY if we actually deleted something successfully
    success = (err is None) and (deleted > 0)
    if success:
        await set_nuke_cooldown(chat_id, user_id)

    # Revoke the unused invite link if userbot didn't join (keeps things clean)
    if not success:
        try:
            await bot.revoke_chat_invite_link(chat_id, invite_link)
        except TelegramError:
            pass

    await log_action(chat_id, user_id, userbot_id, "nuke_all", f"deleted={deleted} err={err or ''}")
    await send_log(
        bot,
        f"💥 <b>NUKE</b>\nGroup: <code>{chat_id}</code>\n"
        f"By: <a href=\"tg://user?id={user_id}\">user</a>\n"
        f"Deleted: <b>{deleted}</b>" + (f"\nError: {html.escape(err)}" if err else ""),
    )

    if err:
        text = (
            f"⚠️ <b>Failed.</b>\nDeleted: <b>{deleted}</b>\n"
            f"<code>{html.escape(err)}</code>\n\n"
            "<i>No cooldown applied — you can try again.</i>"
        )
    elif deleted == 0:
        text = (
            "ℹ️ <b>Nothing to delete.</b>\n"
            "The user account couldn't see any messages to delete "
            "(it may not have been promoted in time, or the chat is empty).\n\n"
            "<i>No cooldown applied — you can try again.</i>"
        )
    else:
        text = (
            f"✅ <b>Done.</b>\nDeleted: <b>{deleted}</b> messages.\n"
            f"Cooldown of {NUKE_COOLDOWN_HOURS}h applied."
        )
    await q.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=f"st:delmsg:{chat_id}")]]),
    )


async def _ub_delete_batch(ub, chat_id: int, ids: list[int]) -> int:
    """Delete a batch of message IDs with FloodWait handling. Returns how many were sent for deletion."""
    try:
        await ub.delete_messages(chat_id, ids, revoke=True)
        return len(ids)
    except FloodWait as fw:
        try:
            await asyncio.sleep(int(getattr(fw, "value", 5)) + 1)
            await ub.delete_messages(chat_id, ids, revoke=True)
            return len(ids)
        except Exception:
            return 0
    except Exception as e:
        log.info("delete batch failed: %s", e)
        return 0


async def handle_service(q, chat_id: int, sub: str) -> None:
    s = await get_settings(chat_id)
    mapping = {
        "photo_on": ("service_photo", 1),
        "photo_off": ("service_photo", 0),
        "title_on": ("service_title", 1),
        "title_off": ("service_title", 0),
        "pin_on": ("service_pinned", 1),
        "pin_off": ("service_pinned", 0),
        "topic_on": ("service_topic", 1),
        "topic_off": ("service_topic", 0),
        "boost_on": ("service_boost", 1),
        "boost_off": ("service_boost", 0),
        "vc_on": ("service_videochat", 1),
        "vc_off": ("service_videochat", 0),
        "join_on": ("service_join_minutes", max(1, s["service_join_minutes"] or 1)),
        "join_off": ("service_join_minutes", 0),
        "exit_on": ("service_exit_minutes", max(1, s["service_exit_minutes"] or 1)),
        "exit_off": ("service_exit_minutes", 0),
    }
    if sub in mapping:
        key, val = mapping[sub]
        await set_setting(chat_id, key, val)
    elif sub == "join+":
        await set_setting(chat_id, "service_join_minutes", min(60, s["service_join_minutes"] + 1))
    elif sub == "join-":
        await set_setting(chat_id, "service_join_minutes", max(0, s["service_join_minutes"] - 1))
    elif sub == "exit+":
        await set_setting(chat_id, "service_exit_minutes", min(60, s["service_exit_minutes"] + 1))
    elif sub == "exit-":
        await set_setting(chat_id, "service_exit_minutes", max(0, s["service_exit_minutes"] - 1))
    await render_service(q, chat_id)


# =============================================================================
# Welcome customize (text/media/buttons capture)
# =============================================================================
WELCOME_TEXT_PROMPT = (
    "{user}, send now the message you want to set!\n"
    "You can use HTML and:\n"
    "• {{ID}} = user ID\n"
    "• {{NAME}} = user name\n"
    "• {{SURNAME}} = user surname\n"
    "• {{NAMESURNAME}} = name and surname\n"
    "• {{LANG}} = user language\n"
    "• {{DATE}} = current date\n"
    "• {{TIME}} = current time\n"
    "• {{WEEKDAY}} = week day\n"
    "• {{MENTION}} = link to the user profile\n"
    "• {{USERNAME}} = username\n"
    "• {{GROUPNAME}} = group name\n"
    "• {{RULES}} = group regulation"
)

BUTTON_PROMPT = (
    "👉 Set the buttons to be placed under the message\n"
    "Send a message structured as follows:\n\n"
    "• Add a single button:\n"
    "Button title - t.me/LinkExample\n\n"
    "• Add multiple buttons on a single line:\n"
    "Button title - t.me/LinkExample &amp;&amp; Button text - t.me/LinkExample\n\n"
    "• Add multiple rows of buttons:\n"
    "Button title - t.me/LinkExample\n"
    "Button title - t.me/LinkExample\n\n"
    "<b>Special buttons:</b>\n"
    "• Button title - popup: Popup text\n"
    "  or Button title - alert: Popup text\n"
    "• Button title - rules\n"
    "• Button title - share: Text to be shared\n"
    "• Button title - copy: Text copied on click"
)


async def stage_input(user_id: int, dm_chat_id: int, target_chat: int, action: str, prompt_msg_id: int = 0) -> None:
    await db_exec(
        "INSERT OR REPLACE INTO pending_inputs(user_id, chat_id, target_chat, action, payload, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (user_id, dm_chat_id, target_chat, action, str(prompt_msg_id), now_ts()),
    )


async def safe_edit(q, text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
    """Edit the message tied to a callback query. Handles text→text and
    media→text swap, swallows 'not modified', falls back to plain text when
    Telegram rejects HTML entities, and resends a fresh message when the
    original was already deleted (e.g. by a previous safe_edit_media)."""
    msg = q.message
    bot = q.get_bot()

    async def _send_fresh(parse_html: bool) -> None:
        try:
            await bot.send_message(
                msg.chat.id,
                text,
                parse_mode=(ParseMode.HTML if parse_html else None),
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except BadRequest as e2:
            if parse_html and ("entity" in str(e2).lower() or "parse" in str(e2).lower()):
                # Strip HTML tags and resend as plain text.
                stripped = re.sub(r"<[^>]+>", "", text)
                stripped = html.unescape(stripped)
                try:
                    await bot.send_message(
                        msg.chat.id, stripped, reply_markup=kb,
                        disable_web_page_preview=True,
                    )
                except TelegramError:
                    pass

    try:
        if msg.photo or msg.video or msg.animation or msg.document or msg.audio or msg.sticker:
            # current message is media: replace caption
            try:
                await bot.edit_message_caption(
                    chat_id=msg.chat.id,
                    message_id=msg.message_id,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                return
            except BadRequest as e:
                msg_lower = str(e).lower()
                if "entity" in msg_lower or "parse" in msg_lower:
                    # User-saved HTML is malformed → retry without parsing.
                    try:
                        stripped = re.sub(r"<[^>]+>", "", text)
                        stripped = html.unescape(stripped)
                        await bot.edit_message_caption(
                            chat_id=msg.chat.id,
                            message_id=msg.message_id,
                            caption=stripped,
                            reply_markup=kb,
                        )
                        return
                    except TelegramError:
                        pass
                # cannot edit caption -> delete media and send a fresh text we then track
                try:
                    await bot.delete_message(msg.chat.id, msg.message_id)
                except TelegramError:
                    pass
                await _send_fresh(parse_html=True)
                # Note: CallbackQuery.message is read-only; the next callback
                # will already be tied to whichever message the user taps.
                return
        await bot.edit_message_text(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        msg_lower = str(e).lower()
        if "not modified" in msg_lower:
            return
        # Original message was already deleted (common after a previous
        # safe_edit_media that fell back to delete-and-resend). Send a new
        # message instead so the user still sees the menu.
        if "message to edit not found" in msg_lower or "message can't be edited" in msg_lower:
            await _send_fresh(parse_html=True)
            return
        # Telegram rejected our HTML entities — fall back to plain text.
        if "entity" in msg_lower or "parse" in msg_lower or "can't parse" in msg_lower:
            try:
                stripped = re.sub(r"<[^>]+>", "", text)
                stripped = html.unescape(stripped)
                await bot.edit_message_text(
                    chat_id=msg.chat.id,
                    message_id=msg.message_id,
                    text=stripped,
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
                return
            except BadRequest as e2:
                if "message to edit not found" in str(e2).lower():
                    await _send_fresh(parse_html=False)
                    return
            except TelegramError:
                return
        raise


async def safe_edit_media(q, file_id: str, caption: str, kb: Optional[InlineKeyboardMarkup] = None,
                          kind: str = "photo") -> None:
    """Edit the menu message into a media message (photo/video/animation/document) with caption."""
    from telegram import InputMediaPhoto, InputMediaVideo, InputMediaAnimation, InputMediaDocument
    msg = q.message
    bot = q.get_bot()
    cls_map = {
        "photo": InputMediaPhoto, "video": InputMediaVideo,
        "animation": InputMediaAnimation, "document": InputMediaDocument,
    }
    cls = cls_map.get(kind, InputMediaPhoto)
    media = cls(media=file_id, caption=caption, parse_mode=ParseMode.HTML)
    try:
        await bot.edit_message_media(
            chat_id=msg.chat.id, message_id=msg.message_id, media=media, reply_markup=kb,
        )
    except BadRequest:
        # fallback: delete current and send fresh
        try:
            await bot.delete_message(msg.chat.id, msg.message_id)
        except TelegramError:
            pass
        send_fn = {
            "photo": bot.send_photo, "video": bot.send_video,
            "animation": bot.send_animation, "document": bot.send_document,
        }.get(kind, bot.send_photo)
        await send_fn(
            msg.chat.id, file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
        # Note: CallbackQuery.message is read-only — see safe_edit() comment.


async def get_pending(user_id: int) -> Optional[aiosqlite.Row]:
    return await db_one("SELECT * FROM pending_inputs WHERE user_id=?", (user_id,))


async def clear_pending(user_id: int) -> None:
    await db_exec("DELETE FROM pending_inputs WHERE user_id=?", (user_id,))


async def handle_welcome_customize(q, context: ContextTypes.DEFAULT_TYPE, chat_id: int, sub: str) -> None:
    if not sub:
        await render_welcome_customize(q, chat_id)
        return
    if sub == "below":
        await toggle_setting(chat_id, "welcome_media_below")
        await render_welcome_customize(q, chat_id)
        return
    back_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ Back", callback_data=f"st:welcomecz:{chat_id}")]]
    )

    if sub == "settext":
        await safe_edit(
            q,
            WELCOME_TEXT_PROMPT.format(user=fmt_user(q.from_user)),
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🚫 Remove message", callback_data=f"st:welcomecz:{chat_id}:rmtext")],
                    [InlineKeyboardButton("✖ Cancel", callback_data=f"st:welcomecz:{chat_id}:cancel")],
                ]
            ),
        )
        await stage_input(q.from_user.id, q.message.chat.id, chat_id, "welcome_text", q.message.message_id)
        return
    if sub == "setbtn":
        await safe_edit(
            q,
            BUTTON_PROMPT,
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🚫 Remove Keyboard", callback_data=f"st:welcomecz:{chat_id}:rmbtn")],
                    [InlineKeyboardButton("✖ Cancel", callback_data=f"st:welcomecz:{chat_id}:cancel")],
                ]
            ),
        )
        await stage_input(q.from_user.id, q.message.chat.id, chat_id, "welcome_buttons", q.message.message_id)
        return
    if sub == "setmedia":
        await safe_edit(
            q,
            "👉 Send the media (photo / video / animation / GIF / sticker / document) you want as the welcome.\n"
            "<i>You can also include a caption — it will become the welcome text.</i>",
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🚫 Remove media", callback_data=f"st:welcomecz:{chat_id}:rmmedia")],
                    [InlineKeyboardButton("✖ Cancel", callback_data=f"st:welcomecz:{chat_id}:cancel")],
                ]
            ),
        )
        await stage_input(q.from_user.id, q.message.chat.id, chat_id, "welcome_media", q.message.message_id)
        return
    if sub == "rmtext":
        await set_setting(chat_id, "welcome_text", "")
        await clear_pending(q.from_user.id)
        await render_welcome_customize(q, chat_id)
        return
    if sub == "rmmedia":
        await set_setting(chat_id, "welcome_media", "")
        await clear_pending(q.from_user.id)
        await render_welcome_customize(q, chat_id)
        return
    if sub == "rmbtn":
        await set_setting(chat_id, "welcome_buttons", "")
        await clear_pending(q.from_user.id)
        await render_welcome_customize(q, chat_id)
        return
    if sub == "cancel":
        await clear_pending(q.from_user.id)
        await render_welcome_customize(q, chat_id)
        return
    if sub == "seetext":
        s = await get_settings(chat_id)
        body = s["welcome_text"] or "<i>(none)</i>"
        # Admin's saved text — show it verbatim.
        try:
            _skip_translate.set(True)
        except Exception:
            pass
        await safe_edit(q, "<b>Current welcome text:</b>\n\n" + body, back_kb)
        return
    if sub == "seemedia":
        s = await get_settings(chat_id)
        if s["welcome_media"]:
            try:
                await safe_edit_media(q, s["welcome_media"], "<b>Current welcome media</b>", back_kb, kind="photo")
            except TelegramError:
                # try as video, then animation, then document
                for k in ("video", "animation", "document"):
                    try:
                        await safe_edit_media(q, s["welcome_media"], "<b>Current welcome media</b>", back_kb, kind=k)
                        return
                    except TelegramError:
                        continue
                await safe_edit(q, "Welcome media is set but couldn't be displayed.", back_kb)
        else:
            await safe_edit(q, "No welcome media set.", back_kb)
        return
    if sub == "seebtn":
        s = await get_settings(chat_id)
        kb = parse_button_string(s["welcome_buttons"] or "")
        if kb:
            rows = list(kb.inline_keyboard) + [[InlineKeyboardButton("↩️ Back", callback_data=f"st:welcomecz:{chat_id}")]]
            await safe_edit(q, "<b>Current welcome buttons:</b>", InlineKeyboardMarkup(rows))
        else:
            await safe_edit(q, "No welcome buttons set.", back_kb)
        return
    if sub == "preview":
        # Preview shows the admin's literal welcome content — never translate it.
        try:
            _skip_translate.set(True)
        except Exception:
            pass
        s = await get_settings(chat_id)
        text = render_template(s["welcome_text"] or "Welcome!", q.from_user, q.message.chat)
        wbtns = parse_button_string(s["welcome_buttons"] or "")
        rows = list(wbtns.inline_keyboard) if wbtns else []
        rows.append([InlineKeyboardButton("↩️ Back", callback_data=f"st:welcomecz:{chat_id}")])
        kb = InlineKeyboardMarkup(rows)
        if s["welcome_media"]:
            caption = text if len(text) <= 1024 else (text[:1020] + "…")
            try:
                await safe_edit_media(q, s["welcome_media"], caption, kb, kind="photo")
                return
            except TelegramError:
                pass
        await safe_edit(q, text, kb)
        return
    if sub == "topic":
        await safe_edit(q, "📂 <b>Select a Topic</b>\n\nTopic selection coming soon — defaults to general.", back_kb)
        return
    # ----- Welcome card style submenu -----
    if sub == "cardstyle":
        await render_welcome_cardstyle(q, chat_id)
        return
    if sub == "ctoggle":
        await toggle_setting(chat_id, "welcome_card_on")
        await render_welcome_cardstyle(q, chat_id)
        return
    if sub == "cinviter":
        await toggle_setting(chat_id, "welcome_card_show_inviter")
        await render_welcome_cardstyle(q, chat_id)
        return
    if sub.startswith("cstyle:"):
        new_style = sub.split(":", 1)[1]
        if new_style in WELCOME_CARD_STYLES:
            await set_setting(chat_id, "welcome_card_style", new_style)
            try:
                await q.answer(f"Style set: {WELCOME_CARD_STYLES[new_style]['label']}")
            except TelegramError:
                pass
        await render_welcome_cardstyle(q, chat_id)
        return
    if sub == "cpreview":
        # Render a sample card for the admin themselves so they see what it looks like.
        s2 = await get_settings(chat_id)
        style = _setting_str(s2, "welcome_card_style", "aurora")
        avatar = await fetch_avatar_bytes(context.bot, q.from_user.id)
        members = 0
        try:
            members = await context.bot.get_chat_member_count(chat_id)
        except TelegramError:
            pass
        # Top inviter for this chat (if any)
        top_inv = await db_one(
            "SELECT inviter_name, count FROM member_invites "
            "WHERE chat_id=? ORDER BY count DESC LIMIT 1",
            (chat_id,),
        )
        inv_text = None
        if top_inv and _setting_truthy(s2, "welcome_card_show_inviter", True):
            iname = (top_inv["inviter_name"] or "someone")[:20]
            inv_text = f"Added by {iname} ({_ordinal(int(top_inv['count']))} invite)"
        try:
            card = make_welcome_card(
                q.from_user.full_name or q.from_user.first_name or "User",
                q.from_user.id,
                q.from_user.username or "",
                max(members, 1),
                avatar,
                style=style,
                inviter_text=inv_text,
            )
            await context.bot.send_photo(
                q.message.chat.id,
                photo=InputFile(io.BytesIO(card), filename="preview.png"),
                caption=f"🎨 Preview — <b>{html.escape(WELCOME_CARD_STYLES[style]['label'])}</b>",
                parse_mode=ParseMode.HTML,
            )
            await q.answer("Preview sent.")
        except TelegramError as e:
            try:
                await q.answer(f"Couldn't send preview: {e}", show_alert=True)
            except TelegramError:
                pass
        return


# Capture pending DM input
async def dm_input_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    user = update.effective_user
    msg = update.effective_message
    if user is None or msg is None:
        return
    pending = await get_pending(user.id)
    if pending is None:
        return
    if msg.text and msg.text.strip().lower() in ("/cancel", "✖ cancel"):
        await clear_pending(user.id)
        await msg.reply_text("Cancelled.")
        return
    chat_id = pending["target_chat"]
    action = pending["action"]
    try:
        prompt_msg_id = int(pending["payload"] or 0)
    except (ValueError, TypeError):
        prompt_msg_id = 0
    dm_chat_id = pending["chat_id"]

    async def edit_prompt(text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
        """Try to edit the original prompt message; if not possible, do nothing (no spam)."""
        if not prompt_msg_id:
            return
        try:
            await context.bot.edit_message_text(
                chat_id=dm_chat_id, message_id=prompt_msg_id,
                text=text, parse_mode=ParseMode.HTML, reply_markup=kb,
                disable_web_page_preview=True,
            )
        except BadRequest:
            try:
                await context.bot.edit_message_caption(
                    chat_id=dm_chat_id, message_id=prompt_msg_id,
                    caption=text, parse_mode=ParseMode.HTML, reply_markup=kb,
                )
            except BadRequest:
                pass
        except TelegramError:
            pass

    async def show_menu_back_in_prompt() -> None:
        """After saving, re-render the customize menu in the same prompt message."""
        if not prompt_msg_id:
            return
        try:
            s2 = await get_settings(chat_id)
            text2 = (
                "💬 <b>Welcome Message</b>\n"
                f"📄 Text {onoff(bool(s2['welcome_text']))}\n"
                f"🎬 Media {onoff(bool(s2['welcome_media']))}\n"
                f"🆎 Url Buttons {onoff(bool(s2['welcome_buttons']))}\n"
                "👉 Use the buttons below to choose what you want to set"
            )
            cd = lambda x: f"st:welcomecz:{chat_id}:{x}"  # noqa: E731
            kb2 = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📄 Text", callback_data=cd("settext")),
                     InlineKeyboardButton("👀 See", callback_data=cd("seetext"))],
                    [InlineKeyboardButton("🎬 Media", callback_data=cd("setmedia")),
                     InlineKeyboardButton("👀 See", callback_data=cd("seemedia"))],
                    [InlineKeyboardButton("🆎 Url Buttons", callback_data=cd("setbtn")),
                     InlineKeyboardButton("👀 See", callback_data=cd("seebtn"))],
                    [InlineKeyboardButton(f"🖼 Media below the text {onoff(s2['welcome_media_below'])}",
                                          callback_data=cd("below"))],
                    [InlineKeyboardButton("👀 Full preview", callback_data=cd("preview"))],
                    [InlineKeyboardButton("📂 Select a Topic", callback_data=cd("topic"))],
                    [InlineKeyboardButton("↩️ Back", callback_data=f"st:welcome:{chat_id}")],
                ]
            )
            try:
                await context.bot.edit_message_text(
                    chat_id=dm_chat_id, message_id=prompt_msg_id,
                    text=text2, parse_mode=ParseMode.HTML, reply_markup=kb2,
                    disable_web_page_preview=True,
                )
            except BadRequest:
                # current prompt may be media; try caption then delete+resend
                try:
                    await context.bot.delete_message(dm_chat_id, prompt_msg_id)
                except TelegramError:
                    pass
                await context.bot.send_message(
                    dm_chat_id, text2, parse_mode=ParseMode.HTML, reply_markup=kb2,
                    disable_web_page_preview=True,
                )
        except TelegramError:
            pass

    # Always remove the user's submitted message to keep the chat clean
    async def delete_user_msg() -> None:
        try:
            await msg.delete()
        except TelegramError:
            pass

    if action == "welcome_text":
        body = capture_html(msg)
        await set_setting(chat_id, "welcome_text", body)
        await delete_user_msg()
        await show_menu_back_in_prompt()
    elif action == "goodbye_text":
        body = capture_html(msg)
        await set_setting(chat_id, "goodbye_text", body)
        await delete_user_msg()
        await edit_prompt("✅ Goodbye text saved.")
    elif action == "welcome_buttons":
        kb = parse_button_string(msg.text or "")
        if kb is None:
            await edit_prompt(
                BUTTON_PROMPT + "\n\n⚠️ <i>Couldn't parse any buttons. Try again or press cancel.</i>",
                InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🚫 Remove Keyboard", callback_data=f"st:welcomecz:{chat_id}:rmbtn")],
                        [InlineKeyboardButton("✖ Cancel", callback_data=f"st:welcomecz:{chat_id}:cancel")],
                    ]
                ),
            )
            await delete_user_msg()
            return
        await set_setting(chat_id, "welcome_buttons", msg.text)
        await delete_user_msg()
        await show_menu_back_in_prompt()
    elif action == "welcome_media":
        file_id = ""
        if msg.photo:
            file_id = msg.photo[-1].file_id
        elif msg.video:
            file_id = msg.video.file_id
        elif msg.animation:
            file_id = msg.animation.file_id
        elif msg.sticker:
            file_id = msg.sticker.file_id
        elif msg.document:
            file_id = msg.document.file_id
        elif msg.audio:
            file_id = msg.audio.file_id
        elif msg.voice:
            file_id = msg.voice.file_id
        elif msg.video_note:
            file_id = msg.video_note.file_id
        if not file_id:
            await edit_prompt(
                "⚠️ Send a photo, video, GIF, sticker, document, audio or voice.",
                InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🚫 Remove media", callback_data=f"st:welcomecz:{chat_id}:rmmedia")],
                        [InlineKeyboardButton("✖ Cancel", callback_data=f"st:welcomecz:{chat_id}:cancel")],
                    ]
                ),
            )
            await delete_user_msg()
            return
        await set_setting(chat_id, "welcome_media", file_id)
        if msg.caption:
            cap_html = capture_html(msg)
            if cap_html:
                await set_setting(chat_id, "welcome_text", cap_html)
        await delete_user_msg()
        await show_menu_back_in_prompt()
    elif action == "broadcast":
        await broadcast_text(context.bot, msg.text or "")
        await edit_prompt("✅ Broadcast queued.")
    await clear_pending(user.id)


# =============================================================================
# WELCOME / GOODBYE on join/leave + member tracking
# =============================================================================
async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu = update.chat_member or update.my_chat_member
    if cmu is None:
        return
    chat = cmu.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    await ensure_group(chat)
    new = cmu.new_chat_member
    old = cmu.old_chat_member
    user = new.user
    await ensure_user(user)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        members = await context.bot.get_chat_member_count(chat.id)
        await db_exec(
            "INSERT OR REPLACE INTO member_history(chat_id, day, members) VALUES (?,?,?)",
            (chat.id, today, members),
        )
        await db_exec("UPDATE groups SET members=? WHERE chat_id=?", (members, chat.id))
    except TelegramError:
        members = 0

    # Inviter tracking — when an existing member adds someone else,
    # `cmu.from_user` is the inviter. Self-joins (via link/search) have
    # from_user == the joining user, which we do NOT count.
    inviter_user: Optional[User] = getattr(cmu, "from_user", None)
    inviter_count: Optional[int] = None
    if (
        inviter_user is not None
        and not inviter_user.is_bot
        and inviter_user.id != user.id
    ):
        try:
            iname = inviter_user.full_name or inviter_user.first_name or ""
            await db_exec(
                "INSERT INTO member_invites(chat_id, inviter_id, inviter_name, count) "
                "VALUES (?,?,?,1) "
                "ON CONFLICT(chat_id, inviter_id) DO UPDATE SET "
                "count = count + 1, inviter_name = excluded.inviter_name",
                (chat.id, inviter_user.id, iname),
            )
            row = await db_one(
                "SELECT count FROM member_invites WHERE chat_id=? AND inviter_id=?",
                (chat.id, inviter_user.id),
            )
            if row:
                inviter_count = int(row["count"])
        except Exception:
            inviter_count = None

    is_join = (
        old.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED)
        and new.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED)
    )
    is_leave = (
        old.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED, ChatMemberStatus.ADMINISTRATOR)
        and new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
    )
    s = await get_settings(chat.id)
    if is_join:
        await db_exec(
            "INSERT OR REPLACE INTO group_members(chat_id, user_id, joined_at, last_message, message_count, role, approved) "
            "VALUES (?,?,?, COALESCE((SELECT last_message FROM group_members WHERE chat_id=? AND user_id=?),0), "
            "COALESCE((SELECT message_count FROM group_members WHERE chat_id=? AND user_id=?),0), "
            "COALESCE((SELECT role FROM group_members WHERE chat_id=? AND user_id=?),''), ?)",
            (chat.id, user.id, now_ts(), chat.id, user.id, chat.id, user.id, chat.id, user.id,
             0 if s["approval_on"] else 1),
        )
        if s["approval_on"]:
            await start_approval(chat, user, context)
        elif s["captcha_on"]:
            await start_captcha(chat, user, context)
        if s["welcome_on"]:
            inv_text: Optional[str] = None
            if (
                inviter_user is not None
                and inviter_count is not None
                and _setting_truthy(s, "welcome_card_show_inviter", True)
            ):
                handle = inviter_user.username and f"@{inviter_user.username}" or (
                    inviter_user.full_name or inviter_user.first_name or "someone"
                )
                inv_text = f"Added by {handle} ({_ordinal(inviter_count)} invite)"
            await deliver_welcome(chat, user, members, context, inviter_text=inv_text)
        await send_log(
            context.bot,
            f"➕ <b>JOIN</b>\nGroup: {html.escape(chat.title or '')}\nUser: {fmt_user(user)} (<code>{user.id}</code>)",
        )
    elif is_leave:
        if s["goodbye_on"]:
            # Goodbye text is admin-authored — bypass the live translator.
            try:
                _skip_translate.set(True)
            except Exception:
                pass
            text = render_template(s["goodbye_text"] or "Goodbye {MENTION}", user, chat)
            try:
                await context.bot.send_message(chat.id, text, parse_mode=ParseMode.HTML)
            except TelegramError:
                pass
        await send_log(
            context.bot,
            f"➖ <b>LEAVE</b>\nGroup: {html.escape(chat.title or '')}\nUser: {fmt_user(user)} (<code>{user.id}</code>)",
        )


async def deliver_welcome(
    chat: Chat,
    user: User,
    members: int,
    context: ContextTypes.DEFAULT_TYPE,
    inviter_text: Optional[str] = None,
) -> None:
    # Welcome content is admin-authored — never run it through the translator.
    try:
        _skip_translate.set(True)
    except Exception:
        pass
    s = await get_settings(chat.id)
    g = await db_one("SELECT rules FROM groups WHERE chat_id=?", (chat.id,))
    rules = g["rules"] if g else ""
    text = render_template(s["welcome_text"] or "Welcome {MENTION}!", user, chat, rules)
    kb = parse_button_string(s["welcome_buttons"] or "")

    if s["welcome_delete_last"] and s["last_welcome_msg"]:
        try:
            await context.bot.delete_message(chat.id, s["last_welcome_msg"])
        except TelegramError:
            pass

    sent: Optional[Message] = None

    async def _send_media(file_id: str, caption: Optional[str], reply_markup) -> Optional[Message]:
        """Try every media kind in sequence — photo, video, animation, document, sticker — until one works."""
        senders = [
            ("photo", context.bot.send_photo),
            ("video", context.bot.send_video),
            ("animation", context.bot.send_animation),
            ("document", context.bot.send_document),
        ]
        last_err: Optional[Exception] = None
        for _, fn in senders:
            try:
                return await fn(
                    chat.id, file_id, caption=caption,
                    parse_mode=ParseMode.HTML if caption else None,
                    reply_markup=reply_markup,
                )
            except TelegramError as e:
                last_err = e
                continue
        # sticker (no caption support)
        try:
            return await context.bot.send_sticker(chat.id, file_id)
        except TelegramError as e:
            last_err = e
        if last_err:
            raise last_err
        return None

    try:
        if s["welcome_media"]:
            # auto-split when caption too long for media (Telegram limit 1024)
            split_mode = bool(s["welcome_media_below"]) or len(text) > 1024
            try:
                if split_mode:
                    # send media first (no caption), then text+buttons below as the "main" message
                    try:
                        await _send_media(s["welcome_media"], None, None)
                    except TelegramError:
                        pass
                    sent = await context.bot.send_message(
                        chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb,
                        disable_web_page_preview=True,
                    )
                else:
                    sent = await _send_media(s["welcome_media"], text, kb)
            except TelegramError:
                # last-resort fallback: ensure user still sees something
                sent = await context.bot.send_message(
                    chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb,
                    disable_web_page_preview=True,
                )
        else:
            # No admin-set media — render the welcome card image
            # (only when the auto-card is enabled). Otherwise just send text.
            if _setting_truthy(s, "welcome_card_on", True):
                avatar = await fetch_avatar_bytes(context.bot, user.id)
                style = _setting_str(s, "welcome_card_style", "aurora")
                card = make_welcome_card(
                    user.full_name or user.first_name or "User",
                    user.id,
                    user.username or "",
                    members,
                    avatar,
                    style=style,
                    inviter_text=inviter_text,
                )
                try:
                    sent = await context.bot.send_photo(
                        chat.id, photo=InputFile(io.BytesIO(card), filename="welcome.png"),
                        caption=text, parse_mode=ParseMode.HTML, reply_markup=kb,
                    )
                except TelegramError:
                    sent = await context.bot.send_message(
                        chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb,
                        disable_web_page_preview=True,
                    )
            else:
                sent = await context.bot.send_message(
                    chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb,
                    disable_web_page_preview=True,
                )
    except TelegramError:
        log.exception("welcome failed")
    if sent:
        await set_setting(chat.id, "last_welcome_msg", sent.message_id)


# =============================================================================
# CAPTCHA
# =============================================================================
async def start_captcha(chat: Chat, user: User, context: ContextTypes.DEFAULT_TYPE) -> None:
    a, b = random.randint(2, 9), random.randint(2, 9)
    answer = a + b
    options = {answer}
    while len(options) < 4:
        options.add(answer + random.randint(-5, 5))
    options = list(options)
    random.shuffle(options)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(str(o), callback_data=f"cap:{user.id}:{o}") for o in options[:2]],
            [InlineKeyboardButton(str(o), callback_data=f"cap:{user.id}:{o}") for o in options[2:]],
        ]
    )
    s = await get_settings(chat.id)
    timeout = s["captcha_timeout"] or 60
    try:
        await context.bot.restrict_chat_member(
            chat.id, user.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
    except TelegramError:
        pass
    try:
        msg = await context.bot.send_message(
            chat.id,
            f"{fmt_user(user)}, solve this to talk in the group: <b>{a} + {b} = ?</b>\n"
            f"You have <b>{timeout}</b> seconds.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except TelegramError:
        return
    deadline = now_ts() + timeout
    await db_exec(
        "INSERT OR REPLACE INTO captchas(chat_id, user_id, answer, deadline, msg_id) VALUES (?,?,?,?,?)",
        (chat.id, user.id, answer, deadline, msg.message_id),
    )

    async def reaper():
        await asyncio.sleep(timeout + 1)
        row = await db_one("SELECT * FROM captchas WHERE chat_id=? AND user_id=?", (chat.id, user.id))
        if row:
            try:
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.unban_chat_member(chat.id, user.id)
            except TelegramError:
                pass
            try:
                await context.bot.delete_message(chat.id, row["msg_id"])
            except TelegramError:
                pass
            await db_exec("DELETE FROM captchas WHERE chat_id=? AND user_id=?", (chat.id, user.id))

    context.application.create_task(reaper())


async def cb_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Acknowledge immediately so Telegram stops the spinner; show_alert / text
    # answers are still sent later by the specific branches when needed.
    try:
        await update.callback_query.answer()
    except TelegramError:
        pass
    q = update.callback_query
    parts = q.data.split(":")
    if len(parts) != 3:
        await q.answer()
        return
    target_id = int(parts[1])
    pick = int(parts[2])
    if q.from_user.id != target_id:
        await q.answer("This captcha isn't for you.", show_alert=True)
        return
    row = await db_one(
        "SELECT * FROM captchas WHERE chat_id=? AND user_id=?",
        (q.message.chat.id, target_id),
    )
    if row is None:
        await q.answer("Captcha expired.", show_alert=True)
        return
    if pick != row["answer"]:
        await q.answer("Wrong answer.", show_alert=True)
        return
    try:
        await context.bot.restrict_chat_member(
            q.message.chat.id, target_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_change_info=False, can_invite_users=True,
                can_pin_messages=False,
            ),
        )
    except TelegramError:
        pass
    try:
        await context.bot.delete_message(q.message.chat.id, row["msg_id"])
    except TelegramError:
        pass
    await db_exec("DELETE FROM captchas WHERE chat_id=? AND user_id=?", (q.message.chat.id, target_id))
    await q.answer("Welcome!")


# =============================================================================
# APPROVAL MODE
# =============================================================================
async def start_approval(chat: Chat, user: User, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.restrict_chat_member(
            chat.id, user.id, permissions=ChatPermissions(can_send_messages=False)
        )
    except TelegramError:
        pass
    await db_exec(
        "INSERT OR REPLACE INTO approvals(chat_id, user_id, requested_at) VALUES (?,?,?)",
        (chat.id, user.id, now_ts()),
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"app:ok:{user.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"app:no:{user.id}"),
            ]
        ]
    )
    try:
        await context.bot.send_message(
            chat.id,
            f"📑 New member awaiting approval: {fmt_user(user)}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except TelegramError:
        pass


async def cb_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.callback_query.answer()
    except TelegramError:
        pass
    q = update.callback_query
    parts = q.data.split(":")
    if len(parts) != 3:
        await q.answer()
        return
    decision = parts[1]
    target = int(parts[2])
    chat = q.message.chat
    if not await is_admin(context.bot, chat.id, q.from_user.id):
        await q.answer("Admins only.", show_alert=True)
        return
    if decision == "ok":
        try:
            await context.bot.restrict_chat_member(
                chat.id, target,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                    can_add_web_page_previews=True, can_change_info=False,
                    can_invite_users=True, can_pin_messages=False,
                ),
            )
            await db_exec("UPDATE group_members SET approved=1 WHERE chat_id=? AND user_id=?", (chat.id, target))
            await q.edit_message_text("✅ User approved.")
        except TelegramError:
            await q.answer("Failed to approve.", show_alert=True)
    else:
        try:
            await context.bot.ban_chat_member(chat.id, target)
            await q.edit_message_text("❌ User rejected and banned.")
        except TelegramError:
            await q.answer("Failed to reject.", show_alert=True)
    await db_exec("DELETE FROM approvals WHERE chat_id=? AND user_id=?", (chat.id, target))


# =============================================================================
# WARN SYSTEM
# =============================================================================
def _resolve_target_id(msg: Message, args: list[str]) -> Optional[int]:
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user.id
    for a in args:
        if a.isdigit():
            return int(a)
        if a.startswith("@") and msg.entities:
            return None  # username resolution requires get_chat
    return None


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[User]:
    """Resolve a target user from reply / @username / user_id / text_mention.

    Backwards-compatible wrapper around `_resolve_target_and_reason`.
    """
    target, _ = await _resolve_target_and_reason(update, context)
    return target


async def _resolve_target_and_reason(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[Optional[User], str]:
    """Universal target resolver supporting every common input style.

    Resolution order:
      1. ``reply`` — when the command is sent as a reply to another user.
      2. ``text_mention`` — Telegram's tap-to-mention chip (no username needed).
      3. First ``@username`` argument anywhere in ``context.args``.
      4. First numeric user-id argument anywhere in ``context.args``.
      5. ``mention`` entity — also picked up from a leading ``@``.

    The returned ``reason`` strips the resolved token so the caller can pass
    the rest of the command line straight into a ban/warn/mute reason.
    """
    msg = update.effective_message
    chat = update.effective_chat
    args = list(context.args or [])
    target: Optional[User] = None
    reason_parts = list(args)

    # Strip any @BotUsername (anywhere in the args) that Telegram or users
    # append to commands like "/ban @MyBot @victim spam".
    bot_uname = ""
    try:
        bu = getattr(context.bot, "username", None) or BOT_USERNAME or ""
        if bu:
            bot_uname = ("@" + bu).lower()
    except Exception:
        bot_uname = ("@" + (BOT_USERNAME or "")).lower()
    if bot_uname and bot_uname != "@":
        args = [a for a in args if a.lower() != bot_uname]
        reason_parts = list(args)
        try:
            context.args = args  # downstream commands re-read this
        except Exception:
            pass

    # 1) Reply to another user — args become the reason. Strip any leftover
    #    @mentions or @BotName so the reason text is clean.
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        clean_args = [
            a for a in args
            if a.lower() != bot_uname and not a.startswith("@")
        ]
        return msg.reply_to_message.from_user, " ".join(clean_args).strip()

    # 2) text_mention entity (works even for users without a public @username).
    if msg and msg.entities:
        for ent in msg.entities:
            if ent.type == "text_mention" and ent.user:
                target = ent.user
                # Drop the mention token from the reason if present.
                token = msg.text[ent.offset: ent.offset + ent.length]
                reason_parts = [a for a in args if a != token]
                return target, " ".join(reason_parts).strip()

    # 3) @username anywhere in the args.
    for i, ident in enumerate(args):
        if ident.startswith("@") and len(ident) > 1:
            try:
                ch = await context.bot.get_chat(ident)
                target = User(
                    id=ch.id,
                    first_name=getattr(ch, "first_name", None) or getattr(ch, "title", "") or "",
                    is_bot=False,
                    last_name=getattr(ch, "last_name", None),
                    username=getattr(ch, "username", None),
                )
                reason_parts = args[:i] + args[i + 1:]
                return target, " ".join(reason_parts).strip()
            except TelegramError:
                continue

    # 4) Numeric user-id anywhere in the args (supports negative ids too).
    for i, ident in enumerate(args):
        token = ident.lstrip("-")
        if token.isdigit() and len(token) >= 5:
            uid = int(ident)
            try:
                m = await context.bot.get_chat_member(chat.id, uid)
                reason_parts = args[:i] + args[i + 1:]
                return m.user, " ".join(reason_parts).strip()
            except TelegramError:
                pass
            try:
                ch = await context.bot.get_chat(uid)
                target = User(
                    id=ch.id,
                    first_name=getattr(ch, "first_name", None) or getattr(ch, "title", "") or "",
                    is_bot=False,
                    last_name=getattr(ch, "last_name", None),
                    username=getattr(ch, "username", None),
                )
                reason_parts = args[:i] + args[i + 1:]
                return target, " ".join(reason_parts).strip()
            except TelegramError:
                continue

    # Nothing resolved — caller should ask for a reply / target.
    return None, " ".join(args).strip()


async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await has_min_role(context.bot, chat.id, update.effective_user.id, "moderator"):
        await msg.reply_text("Admins/moderators only.")
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply to a user or pass @username/userid.")
        return
    if target.id == update.effective_user.id:
        await msg.reply_text("You can't warn yourself.")
        return
    if await _is_chat_admin(chat.id, target.id, context.bot):
        await msg.reply_text("I can't warn another admin.")
        return
    await db_exec(
        "INSERT INTO warns(chat_id, user_id, admin_id, reason, created_at) VALUES (?,?,?,?,?)",
        (chat.id, target.id, update.effective_user.id, reason or "", now_ts()),
    )
    count = (await db_one("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?", (chat.id, target.id)))["c"]
    s = await get_settings(chat.id)
    handle = f"@{target.username}" if target.username else fmt_user(target)
    if count >= s["warn_limit"]:
        text = (
            f"{handle} <b>[{target.id}]</b> has reached the limit of "
            f"{s['warn_limit']} warnings. What do you want to do?"
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🚫 Ban", callback_data=f"warn:ban:{chat.id}:{target.id}"),
                    InlineKeyboardButton("❗ Kick", callback_data=f"warn:kick:{chat.id}:{target.id}"),
                    InlineKeyboardButton("🔇 Mute", callback_data=f"warn:mute:{chat.id}:{target.id}"),
                ],
                [InlineKeyboardButton("-1", callback_data=f"warn:dec:{chat.id}:{target.id}")],
                [InlineKeyboardButton("♻️ Reset Warns", callback_data=f"warn:reset:{chat.id}:{target.id}")],
            ]
        )
        await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        text = (
            f"{handle} <b>[{target.id}]</b> received {count} warning out of "
            f"{s['warn_limit']}"
            + (f"\nReason: {html.escape(reason)}" if reason else "")
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("-1", callback_data=f"warn:dec:{chat.id}:{target.id}"),
                    InlineKeyboardButton("+1", callback_data=f"warn:inc:{chat.id}:{target.id}"),
                ],
                [InlineKeyboardButton("♻️ Reset Warns", callback_data=f"warn:reset:{chat.id}:{target.id}")],
            ]
        )
        await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await log_action(chat.id, update.effective_user.id, target.id, "warn", reason)


async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not await has_min_role(context.bot, chat.id, update.effective_user.id, "moderator"):
        await msg.reply_text("Admins/moderators only.")
        return
    target = await _resolve_target(update, context)
    if target is None:
        await msg.reply_text("Reply to a user or pass @username/userid.")
        return
    row = await db_one(
        "SELECT id FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
        (chat.id, target.id),
    )
    if row is None:
        await msg.reply_text("No warns to remove.")
        return
    await db_exec("DELETE FROM warns WHERE id=?", (row["id"],))
    await msg.reply_text(f"✅ Removed last warn from {fmt_user(target)}", parse_mode=ParseMode.HTML)


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    target = await _resolve_target(update, context) or update.effective_user
    rows = await db_all(
        "SELECT reason, created_at FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC",
        (chat.id, target.id),
    )
    if not rows:
        await msg.reply_text(f"{fmt_user(target)} has no warns.", parse_mode=ParseMode.HTML)
        return
    lines = [f"<b>Warns for {fmt_user(target)}:</b>"]
    for r in rows:
        ts = datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"• {ts} — {html.escape(r['reason']) or '(no reason)'}")
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Reset all", callback_data=f"warns:reset:{chat.id}:{target.id}")]]
    )
    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


async def cmd_resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await has_min_role(context.bot, chat.id, update.effective_user.id, "moderator"):
        return
    target = await _resolve_target(update, context)
    if target is None:
        await update.effective_message.reply_text(
            "Reply to a user, or pass @username / user_id."
        )
        return
    await db_exec("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat.id, target.id))
    await update.effective_message.reply_text(f"✅ Reset warns for {fmt_user(target)}", parse_mode=ParseMode.HTML)


async def cmd_setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /setwarnlimit <number>")
        return
    await set_setting(chat.id, "warn_limit", max(1, int(context.args[0])))
    await update.effective_message.reply_text(f"✅ Warn limit set to {context.args[0]}")


async def cmd_setwarnaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    if not context.args or context.args[0] not in ("mute", "kick", "ban"):
        await update.effective_message.reply_text("Usage: /setwarnaction mute|kick|ban")
        return
    await set_setting(chat.id, "warn_action", context.args[0])
    await update.effective_message.reply_text(f"✅ Warn action set to {context.args[0]}")


async def cmd_delwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not await has_min_role(context.bot, chat.id, update.effective_user.id, "moderator"):
        return
    if msg.reply_to_message:
        try:
            await context.bot.delete_message(chat.id, msg.reply_to_message.message_id)
        except TelegramError:
            pass
    await cmd_warn(update, context)


async def cb_warns_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    # Ack immediately so the inline-button spinner stops within Telegram's
    # short callback-query window even if the DB / admin check is slow.
    try:
        await q.answer()
    except TelegramError:
        pass
    parts = q.data.split(":")
    if len(parts) != 4:
        return
    chat_id, user_id = int(parts[2]), int(parts[3])
    if not await is_admin(context.bot, chat_id, q.from_user.id):
        try:
            await q.answer("Admins only.", show_alert=True)
        except TelegramError:
            pass
        return
    await db_exec("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    try:
        await q.edit_message_text("✅ Warns reset.")
    except TelegramError:
        pass


async def cb_warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle warn:* inline buttons (-1, +1, reset, ban, kick, mute)."""
    q = update.callback_query
    # Ack immediately to clear the inline spinner — every branch below either
    # edits the message (implicit response) or returns silently, so without
    # an early answer Telegram would leave the button "loading" for the user.
    try:
        await q.answer()
    except TelegramError:
        pass
    parts = q.data.split(":")
    if len(parts) != 4:
        return
    action, chat_id, user_id = parts[1], int(parts[2]), int(parts[3])
    if not await is_admin(context.bot, chat_id, q.from_user.id):
        await q.answer("Admins only.", show_alert=True)
        return

    s = await get_settings(chat_id)
    limit = int(s.get("warn_limit") or 3)

    try:
        target = await context.bot.get_chat(user_id)
        handle = f"@{target.username}" if target.username else f"<a href='tg://user?id={user_id}'>user</a>"
    except TelegramError:
        handle = f"<a href='tg://user?id={user_id}'>user</a>"

    if action == "inc":
        await db_exec(
            "INSERT INTO warns(chat_id, user_id, admin_id, reason, created_at) VALUES (?,?,?,?,?)",
            (chat_id, user_id, q.from_user.id, "(via +1)", now_ts()),
        )
    elif action == "dec":
        row = await db_one(
            "SELECT id FROM warns WHERE chat_id=? AND user_id=? ORDER BY id DESC LIMIT 1",
            (chat_id, user_id),
        )
        if row:
            await db_exec("DELETE FROM warns WHERE id=?", (row["id"],))
    elif action == "reset":
        await db_exec("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await q.edit_message_text(f"♻️ Warns reset for {handle} <b>[{user_id}]</b>.",
                                  parse_mode=ParseMode.HTML)
        return
    elif action in ("ban", "kick", "mute"):
        await _apply_action(context.bot, chat_id, user_id, action)
        await db_exec("DELETE FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await q.edit_message_text(
            f"🚫 Action <b>{action}</b> applied to {handle} <b>[{user_id}]</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    count = (await db_one(
        "SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    ))["c"]

    if count >= limit:
        text = (f"{handle} <b>[{user_id}]</b> has reached the limit of "
                f"{limit} warnings. What do you want to do?")
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🚫 Ban", callback_data=f"warn:ban:{chat_id}:{user_id}"),
                    InlineKeyboardButton("❗ Kick", callback_data=f"warn:kick:{chat_id}:{user_id}"),
                    InlineKeyboardButton("🔇 Mute", callback_data=f"warn:mute:{chat_id}:{user_id}"),
                ],
                [InlineKeyboardButton("-1", callback_data=f"warn:dec:{chat_id}:{user_id}")],
                [InlineKeyboardButton("♻️ Reset Warns",
                                      callback_data=f"warn:reset:{chat_id}:{user_id}")],
            ]
        )
    elif count <= 0:
        await q.edit_message_text(f"♻️ No warnings remaining for {handle} <b>[{user_id}]</b>.",
                                  parse_mode=ParseMode.HTML)
        return
    else:
        text = (f"{handle} <b>[{user_id}]</b> received {count} warning out of {limit}")
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("-1", callback_data=f"warn:dec:{chat_id}:{user_id}"),
                    InlineKeyboardButton("+1", callback_data=f"warn:inc:{chat_id}:{user_id}"),
                ],
                [InlineKeyboardButton("♻️ Reset Warns",
                                      callback_data=f"warn:reset:{chat_id}:{user_id}")],
            ]
        )
    try:
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except TelegramError:
        await q.answer()


async def cb_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle mute:unmute inline button."""
    q = update.callback_query
    # Ack immediately to clear the spinner; actual feedback (alert / edit)
    # happens in the branch below.
    try:
        await q.answer()
    except TelegramError:
        pass
    parts = q.data.split(":")
    if len(parts) != 4:
        return
    action, chat_id, user_id = parts[1], int(parts[2]), int(parts[3])
    if not await is_admin(context.bot, chat_id, q.from_user.id):
        try:
            await q.answer("Admins only.", show_alert=True)
        except TelegramError:
            pass
        return
    if action == "unmute":
        try:
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True,
                    can_send_other_messages=True, can_add_web_page_previews=True,
                    can_change_info=False, can_invite_users=True, can_pin_messages=False,
                ),
            )
            try:
                target = await context.bot.get_chat(user_id)
                handle = f"@{target.username}" if target.username else f"<a href='tg://user?id={user_id}'>user</a>"
            except TelegramError:
                handle = f"<a href='tg://user?id={user_id}'>user</a>"
            await q.edit_message_text(
                f"{handle} <b>[{user_id}]</b> is no longer 🔇 muted.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            await q.answer(f"Failed: {e}", show_alert=True)


# =============================================================================
# Per-user permissions panel (DM toggle UI shown after /mute)
# =============================================================================

# Order of permissions shown in the DM keyboard.
# Each entry: (perm_attr, label).
_PERM_FIELDS: list[tuple[str, str]] = [
    ("can_send_messages", "Text messages"),
    ("can_send_photos", "Photo"),
    ("can_send_videos", "Video"),
    ("can_send_other_messages", "Sticker/GIF"),
    ("can_send_audios", "Audio"),
    ("can_send_voice_notes", "Voice"),
    ("can_send_documents", "File"),
    ("can_send_video_notes", "Round Video"),
    ("can_send_polls", "Polls"),
    ("can_add_web_page_previews", "Enable link previews"),
    ("can_change_info", "Edit own tag"),
]


def _perms_state_key(admin_id: int, chat_id: int, user_id: int) -> str:
    return f"perms_{admin_id}_{chat_id}_{user_id}"


async def _read_current_perms(bot, chat_id: int, user_id: int) -> dict[str, bool]:
    """Best-effort read of the user's current ChatPermissions in the group."""
    state = {f: False for f, _ in _PERM_FIELDS}
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        for f, _ in _PERM_FIELDS:
            v = getattr(member, f, None)
            if v is None:
                # Fall back to chat default permissions
                try:
                    chat = await bot.get_chat(chat_id)
                    v = getattr(getattr(chat, "permissions", None), f, False)
                except TelegramError:
                    v = False
            state[f] = bool(v)
    except TelegramError:
        pass
    return state


def _build_perms_keyboard(
    chat_id: int, user_id: int, state: dict[str, bool]
) -> InlineKeyboardMarkup:
    """Build the toggle keyboard. Layout matches the Miss Rose style screenshot."""
    def btn(field: str, label: str) -> InlineKeyboardButton:
        mark = "✅" if state.get(field) else "❌"
        return InlineKeyboardButton(
            f"{mark} {label}",
            callback_data=f"ptog:{chat_id}:{user_id}:{field}",
        )

    rows = [
        [btn("can_send_messages", "Text messages")],
        [btn("can_send_photos", "Photo"), btn("can_send_videos", "Video")],
        [btn("can_send_other_messages", "Sticker/GIF"), btn("can_send_audios", "Audio")],
        [btn("can_send_voice_notes", "Voice"), btn("can_send_documents", "File")],
        [btn("can_send_video_notes", "Round Video"), btn("can_send_polls", "Polls")],
        [btn("can_add_web_page_previews", "Enable link previews")],
        [btn("can_change_info", "Edit own tag")],
        [InlineKeyboardButton("Save ✓", callback_data=f"psave:{chat_id}:{user_id}")],
    ]
    return InlineKeyboardMarkup(rows)


def _perms_header(chat_title: str, target: User) -> str:
    handle = f"@{target.username}" if target.username else (target.first_name or "user")
    handle_html = html.escape(handle)
    title_html = html.escape(chat_title or "")
    return (
        "🕹 <b>Permissions</b>\n"
        f"👤 {handle_html} <b>[{target.id}]</b>\n"
        f"👥 {title_html}"
    )


async def cb_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the per-user permissions panel in the admin's DM."""
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) != 3:
        return
    try:
        chat_id = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        return
    admin_id = q.from_user.id
    if not await is_admin(context.bot, chat_id, admin_id):
        await q.answer("Admins only.", show_alert=True)
        return
    # Prime the in-memory state from current member status
    state = await _read_current_perms(context.bot, chat_id, user_id)
    context.bot_data[_perms_state_key(admin_id, chat_id, user_id)] = state
    # Get target + chat info for the header
    try:
        target = await context.bot.get_chat(user_id)
    except TelegramError:
        target = User(id=user_id, first_name="user", is_bot=False)
    try:
        chat = await context.bot.get_chat(chat_id)
        chat_title = chat.title or chat.username or str(chat_id)
    except TelegramError:
        chat_title = str(chat_id)
    text = _perms_header(chat_title, target)
    kb = _build_perms_keyboard(chat_id, user_id, state)
    try:
        await context.bot.send_message(
            admin_id, text, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
        await q.answer("Opened in DM.")
    except TelegramError:
        await q.answer(
            "Start me in DM first, then tap Permissions again.",
            show_alert=True,
        )


async def cb_perm_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Flip a single permission in the in-memory state and re-render."""
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) != 4:
        return
    try:
        chat_id = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        return
    field = parts[3]
    if field not in {f for f, _ in _PERM_FIELDS}:
        return
    admin_id = q.from_user.id
    if not await is_admin(context.bot, chat_id, admin_id):
        await q.answer("Admins only.", show_alert=True)
        return
    key = _perms_state_key(admin_id, chat_id, user_id)
    state = context.bot_data.get(key)
    if state is None:
        state = await _read_current_perms(context.bot, chat_id, user_id)
    state[field] = not bool(state.get(field))
    context.bot_data[key] = state
    kb = _build_perms_keyboard(chat_id, user_id, state)
    try:
        await q.edit_message_reply_markup(reply_markup=kb)
    except TelegramError:
        pass


async def cb_perm_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply the current toggle state to the user via restrict_chat_member."""
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) != 3:
        return
    try:
        chat_id = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        return
    admin_id = q.from_user.id
    if not await is_admin(context.bot, chat_id, admin_id):
        await q.answer("Admins only.", show_alert=True)
        return
    key = _perms_state_key(admin_id, chat_id, user_id)
    state = context.bot_data.get(key)
    if state is None:
        await q.answer("Open Permissions first.", show_alert=True)
        return
    perms = ChatPermissions(
        can_send_messages=state.get("can_send_messages", False),
        can_send_audios=state.get("can_send_audios", False),
        can_send_documents=state.get("can_send_documents", False),
        can_send_photos=state.get("can_send_photos", False),
        can_send_videos=state.get("can_send_videos", False),
        can_send_video_notes=state.get("can_send_video_notes", False),
        can_send_voice_notes=state.get("can_send_voice_notes", False),
        can_send_polls=state.get("can_send_polls", False),
        can_send_other_messages=state.get("can_send_other_messages", False),
        can_add_web_page_previews=state.get("can_add_web_page_previews", False),
        can_change_info=state.get("can_change_info", False),
    )
    try:
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=perms)
        context.bot_data.pop(key, None)
        await q.edit_message_text(
            "✅ <b>Permissions saved.</b>", parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        await q.answer(f"Failed: {e}", show_alert=True)


# =============================================================================
# ADMIN ACTION COMMANDS (ban, mute, kick, unban, promote, demote, etc.)
# =============================================================================
async def _apply_action(
    bot: Bot,
    chat_id: int,
    user_id: int,
    action: str,
    duration_seconds: int = 0,
) -> None:
    """Apply ``action`` ('mute' | 'kick' | 'ban' | 'warn') to a user.

    When ``duration_seconds`` is > 0 and ``action`` is 'mute' or 'ban', the
    restriction is applied with an ``until_date`` so it auto-lifts.
    """
    try:
        if action == "mute":
            kwargs: dict = {
                "permissions": ChatPermissions(can_send_messages=False),
            }
            if duration_seconds and duration_seconds > 0:
                kwargs["until_date"] = now_ts() + duration_seconds
            await bot.restrict_chat_member(chat_id, user_id, **kwargs)
        elif action == "kick":
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
        elif action == "ban":
            if duration_seconds and duration_seconds > 0:
                await bot.ban_chat_member(
                    chat_id, user_id, until_date=now_ts() + duration_seconds,
                )
            else:
                await bot.ban_chat_member(chat_id, user_id)
        elif action == "warn":
            pass
    except TelegramError:
        pass


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply to a user or pass @username/userid.")
        return
    if target.id == update.effective_user.id:
        await msg.reply_text("You can't ban yourself.")
        return
    if await _is_chat_admin(chat.id, target.id, context.bot):
        await msg.reply_text("I can't ban another admin.")
        return
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
        suffix = f"\n<i>Reason:</i> {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"🚫 Banned {fmt_user(target)}{suffix}",
            parse_mode=ParseMode.HTML,
        )
        await log_action(chat.id, update.effective_user.id, target.id, "ban", reason)
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_tban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Usage: /tban <reply | @user | id> <duration> [reason]")
        return
    # Find the duration token in the remaining reason text.
    parts = reason.split()
    secs: Optional[int] = None
    duration_str = ""
    new_parts: list[str] = []
    for tok in parts:
        if secs is None and parse_duration(tok) is not None:
            secs = parse_duration(tok)
            duration_str = tok
        else:
            new_parts.append(tok)
    if secs is None:
        await msg.reply_text("Duration chahiye: e.g. 30m, 2h, 1d, 1w.")
        return
    reason = " ".join(new_parts)
    try:
        await context.bot.ban_chat_member(chat.id, target.id, until_date=now_ts() + secs)
        suffix = f"\n<i>Reason:</i> {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"🚫 Temp-banned {fmt_user(target)} for {duration_str}{suffix}",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply to a user, or pass @username / user-id.")
        return
    if target.id == update.effective_user.id:
        await msg.reply_text("You can't kick yourself.")
        return
    if await _is_chat_admin(chat.id, target.id, context.bot):
        await msg.reply_text("I can't kick another admin.")
        return
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
        await context.bot.unban_chat_member(chat.id, target.id)
        suffix = f"\n<i>Reason:</i> {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"👢 Kicked {fmt_user(target)}{suffix}",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply to a user or pass @username / user-id.")
        return
    try:
        await context.bot.unban_chat_member(chat.id, target.id, only_if_banned=True)
        await msg.reply_text(f"♻️ Unbanned {fmt_user(target)}", parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply to a user, or pass @username / user-id.")
        return
    if target.id == update.effective_user.id:
        await msg.reply_text("You can't mute yourself.")
        return
    if await _is_chat_admin(chat.id, target.id, context.bot):
        await msg.reply_text("I can't mute another admin.")
        return
    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        handle = f"@{target.username}" if target.username else fmt_user(target)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🕹 Permissions ↗",
                                         callback_data=f"perms:{chat.id}:{target.id}"),
                    InlineKeyboardButton("✅ Unmute",
                                         callback_data=f"mute:unmute:{chat.id}:{target.id}"),
                ]
            ]
        )
        await msg.reply_text(
            f"{handle} <b>[{target.id}]</b> has been 🔇 muted.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_tmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Usage: /tmute <reply | @user | id> <duration> [reason]")
        return
    if target.id == update.effective_user.id:
        await msg.reply_text("You can't mute yourself.")
        return
    if await _is_chat_admin(chat.id, target.id, context.bot):
        await msg.reply_text("I can't mute another admin.")
        return
    parts = reason.split()
    secs: Optional[int] = None
    duration_str = ""
    new_parts: list[str] = []
    for tok in parts:
        if secs is None and parse_duration(tok) is not None:
            secs = parse_duration(tok)
            duration_str = tok
        else:
            new_parts.append(tok)
    if secs is None:
        await msg.reply_text("Duration chahiye: e.g. 30m, 2h, 1d.")
        return
    reason = " ".join(new_parts)
    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=now_ts() + secs,
        )
        suffix = f"\n<i>Reason:</i> {html.escape(reason)}" if reason else ""
        await msg.reply_text(
            f"🔇 Muted {fmt_user(target)} for {duration_str}{suffix}",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply to a user or pass @user/id.")
        return
    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_change_info=False,
                can_invite_users=True, can_pin_messages=False,
            ),
        )
        handle = f"@{target.username}" if target.username else fmt_user(target)
        await msg.reply_text(
            f"{handle} <b>[{target.id}]</b> is no longer 🔇 muted.",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Telegram-promote a user OR set a bot-internal role (admin/mod/cleaner)."""
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target = await _resolve_target(update, context)
    if target is None:
        await msg.reply_text("Reply to a user. Optional: /promote @user [admin|mod|cleaner]")
        return
    role = ""
    for a in (context.args or []):
        if a.lower() in ("admin", "mod", "moderator", "cleaner"):
            role = {"mod": "moderator", "moderator": "moderator",
                    "admin": "admin", "cleaner": "cleaner"}[a.lower()]
    if role:
        await db_exec(
            "INSERT OR REPLACE INTO group_members(chat_id, user_id, role, joined_at, last_message, message_count, approved) "
            "VALUES (?,?,?, COALESCE((SELECT joined_at FROM group_members WHERE chat_id=? AND user_id=?), ?), "
            "COALESCE((SELECT last_message FROM group_members WHERE chat_id=? AND user_id=?), 0), "
            "COALESCE((SELECT message_count FROM group_members WHERE chat_id=? AND user_id=?), 0), 1)",
            (chat.id, target.id, role, chat.id, target.id, now_ts(), chat.id, target.id, chat.id, target.id),
        )
        await msg.reply_text(f"✅ {fmt_user(target)} role set to <b>{role}</b>", parse_mode=ParseMode.HTML)
        return
    try:
        await context.bot.promote_chat_member(
            chat.id, target.id,
            can_change_info=False, can_post_messages=False, can_edit_messages=False,
            can_delete_messages=True, can_invite_users=True, can_restrict_members=True,
            can_pin_messages=True, can_promote_members=False, can_manage_chat=True,
            can_manage_video_chats=False,
        )
        await msg.reply_text(f"✅ Promoted {fmt_user(target)}", parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target = await _resolve_target(update, context)
    if target is None:
        return
    await db_exec(
        "UPDATE group_members SET role='' WHERE chat_id=? AND user_id=?",
        (chat.id, target.id),
    )
    try:
        await context.bot.promote_chat_member(
            chat.id, target.id,
            can_change_info=False, can_post_messages=False, can_edit_messages=False,
            can_delete_messages=False, can_invite_users=False, can_restrict_members=False,
            can_pin_messages=False, can_promote_members=False, can_manage_chat=False,
            can_manage_video_chats=False,
        )
    except TelegramError:
        pass
    await msg.reply_text(f"✅ Demoted {fmt_user(target)}", parse_mode=ParseMode.HTML)


async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    text = " ".join(context.args or []).strip()
    target_msg: Optional[Message] = None
    if msg.reply_to_message:
        target_msg = msg.reply_to_message
    elif text:
        try:
            target_msg = await context.bot.send_message(chat.id, text, parse_mode=ParseMode.HTML)
        except TelegramError:
            target_msg = await context.bot.send_message(chat.id, text)
    if target_msg is None:
        await msg.reply_text("Reply to a message or pass text.")
        return
    try:
        await context.bot.pin_chat_message(chat.id, target_msg.message_id, disable_notification=False)
        await db_exec(
            "INSERT OR REPLACE INTO pinned_msgs(chat_id, msg_id, text) VALUES (?,?,?)",
            (chat.id, target_msg.message_id, target_msg.text or target_msg.caption or ""),
        )
    except TelegramError as e:
        await msg.reply_text(f"Failed: {e}")


async def cmd_editpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    row = await db_one("SELECT msg_id FROM pinned_msgs WHERE chat_id=?", (chat.id,))
    if row is None or not context.args:
        await update.effective_message.reply_text("Usage: /editpin <new text> (a message must be pinned)")
        return
    new = " ".join(context.args)
    try:
        await context.bot.edit_message_text(chat_id=chat.id, message_id=row["msg_id"], text=new, parse_mode=ParseMode.HTML)
        await db_exec("UPDATE pinned_msgs SET text=? WHERE chat_id=?", (new, chat.id))
    except TelegramError as e:
        await update.effective_message.reply_text(f"Failed: {e}")


async def cmd_delpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    try:
        await context.bot.unpin_all_chat_messages(chat.id)
        await db_exec("DELETE FROM pinned_msgs WHERE chat_id=?", (chat.id,))
        await update.effective_message.reply_text("Unpinned.")
    except TelegramError as e:
        await update.effective_message.reply_text(f"Failed: {e}")


async def cmd_repin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    row = await db_one("SELECT msg_id FROM pinned_msgs WHERE chat_id=?", (chat.id,))
    if row is None:
        return
    try:
        await context.bot.unpin_chat_message(chat.id, row["msg_id"])
        await context.bot.pin_chat_message(chat.id, row["msg_id"], disable_notification=False)
    except TelegramError:
        pass


async def cmd_pinned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    row = await db_one("SELECT msg_id, text FROM pinned_msgs WHERE chat_id=?", (chat.id,))
    if row is None:
        await update.effective_message.reply_text("No pinned message tracked.")
        return
    link = f"https://t.me/c/{str(chat.id)[4:]}/{row['msg_id']}" if str(chat.id).startswith("-100") else None
    text = "📌 <b>Pinned:</b>\n" + (html.escape(row["text"]) or "(media)")
    if link:
        text += f"\n<a href=\"{link}\">Open message</a>"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    body = " ".join(context.args or [])
    if not body:
        await update.effective_message.reply_text("Usage: /send <html>")
        return
    try:
        await context.bot.send_message(chat.id, body, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
    except TelegramError as e:
        await update.effective_message.reply_text(f"Failed: {e}")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != BOT_OWNER_ID:
        return
    body = " ".join(context.args or [])
    if not body:
        await update.effective_message.reply_text("Usage: /broadcast <message>")
        return
    sent, failed = await broadcast_text(context.bot, body)
    await update.effective_message.reply_text(f"Broadcast done. Sent: {sent}, failed: {failed}.")


async def broadcast_text(bot: Bot, text: str) -> tuple[int, int]:
    rows = await db_all("SELECT chat_id FROM groups", ())
    sent = failed = 0
    for r in rows:
        try:
            await bot.send_message(r["chat_id"], text, parse_mode=ParseMode.HTML)
            sent += 1
        except TelegramError:
            failed += 1
    return sent, failed


async def cmd_intervention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    await update.effective_message.reply_text(
        "🆘 Support intervention requested.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open Support", url=SUPPORT_LINK)]]),
    )
    if BOT_OWNER_ID:
        try:
            await context.bot.send_message(
                BOT_OWNER_ID,
                f"🆘 Intervention requested in <b>{html.escape(chat.title or '')}</b> by {fmt_user(update.effective_user)}",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass


async def cmd_logdel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await has_min_role(context.bot, chat.id, update.effective_user.id, "moderator", "cleaner"):
        return
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a message to /logdel it.")
        return
    target = msg.reply_to_message
    if LOG_CHANNEL_ID:
        try:
            await context.bot.forward_message(LOG_CHANNEL_ID, chat.id, target.message_id)
        except TelegramError:
            pass
    try:
        await context.bot.delete_message(chat.id, target.message_id)
        await context.bot.delete_message(chat.id, msg.message_id)
    except TelegramError:
        pass


async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not await has_min_role(context.bot, chat.id, update.effective_user.id, "moderator", "cleaner"):
        return
    if not msg.reply_to_message:
        return
    try:
        await context.bot.delete_message(chat.id, msg.reply_to_message.message_id)
        await context.bot.delete_message(chat.id, msg.message_id)
    except TelegramError:
        pass


# =============================================================================
# USER COMMANDS
# =============================================================================
async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    target = msg.reply_to_message.from_user if msg.reply_to_message and msg.reply_to_message.from_user else update.effective_user
    text = (
        f"👤 <b>User ID</b>\n"
        f"Name: {fmt_user(target)}\n"
        f"ID: <code>{target.id}</code>\n"
        f"Chat ID: <code>{update.effective_chat.id}</code>"
    )
    await msg.reply_text(text, parse_mode=ParseMode.HTML)


async def _user_info_text(bot: Bot, chat_id: int, user: User) -> str:
    warns = await db_one("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?", (chat_id, user.id))
    member_row = await db_one("SELECT * FROM group_members WHERE chat_id=? AND user_id=?", (chat_id, user.id))
    role = (member_row["role"] if member_row else "") or "member"
    msg_count = member_row["message_count"] if member_row else 0
    last = datetime.fromtimestamp(member_row["last_message"]).strftime("%Y-%m-%d %H:%M") if member_row and member_row["last_message"] else "never"
    return (
        f"👤 <b>User info</b>\n"
        f"Name: {fmt_user(user)}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: {('@' + user.username) if user.username else '—'}\n"
        f"Language: {html.escape(user.language_code or '—')}\n"
        f"Role: {role}\n"
        f"Messages: {msg_count}\n"
        f"Last seen: {last}\n"
        f"Warns: {warns['c']}"
    )


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _resolve_target(update, context) or update.effective_user
    chat = update.effective_chat
    text = await _user_info_text(context.bot, chat.id, target)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_infopvt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _resolve_target(update, context) or update.effective_user
    chat = update.effective_chat
    text = await _user_info_text(context.bot, chat.id, target)
    try:
        await context.bot.send_message(update.effective_user.id, text, parse_mode=ParseMode.HTML)
        await update.effective_message.reply_text("Sent in private.")
    except TelegramError:
        await update.effective_message.reply_text("Open me in DM first.")


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.effective_message.reply_text("Use this command in a group.")
        return
    g = await db_one("SELECT title, rules FROM groups WHERE chat_id=?", (chat.id,))
    info = await _user_info_text(context.bot, chat.id, user)
    rules = (g["rules"] if g else "") or "(no rules set)"
    blacklist = await db_all("SELECT word FROM blacklist WHERE chat_id=?", (chat.id,))
    bw = ", ".join(html.escape(r["word"]) for r in blacklist) or "(none)"
    text = (
        f"{info}\n\n"
        f"<b>Group:</b> {html.escape(g['title'] if g else '')}\n\n"
        f"<b>Rules:</b>\n{html.escape(rules)[:1500]}\n\n"
        f"<b>Banned words:</b> {bw}"
    )
    try:
        await context.bot.send_message(user.id, text, parse_mode=ParseMode.HTML)
        await update.effective_message.reply_text("Sent in DM.")
    except TelegramError:
        await update.effective_message.reply_text("Please /start me in DM first.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows_g = await db_one("SELECT COUNT(*) c FROM groups", ())
    rows_u = await db_one("SELECT COUNT(*) c FROM users", ())
    text = (
        "📊 <b>Bot stats</b>\n"
        f"Groups: <b>{rows_g['c']}</b>\n"
        f"Users tracked: <b>{rows_u['c']}</b>"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Rules are admin-authored — show them verbatim, no translation.
    try:
        _skip_translate.set(True)
    except Exception:
        pass
    chat = update.effective_chat
    g = await db_one("SELECT rules FROM groups WHERE chat_id=?", (chat.id,))
    rules = (g["rules"] if g else "") or "(no rules set)"
    await update.effective_message.reply_text(
        f"📋 <b>Rules</b>\n\n{html.escape(rules)}", parse_mode=ParseMode.HTML
    )


async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    rules = " ".join(context.args or []).strip()
    if not rules:
        await update.effective_message.reply_text("Usage: /setrules <text>")
        return
    await db_exec("UPDATE groups SET rules=? WHERE chat_id=?", (rules, chat.id))
    await update.effective_message.reply_text("✅ Rules updated.")


async def cmd_inviters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the top 15 members who have added the most users to this group."""
    chat = update.effective_chat
    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.effective_message.reply_text("Use this in a group.")
        return
    rows = await db_all(
        "SELECT inviter_id, inviter_name, count FROM member_invites "
        "WHERE chat_id=? ORDER BY count DESC LIMIT 15",
        (chat.id,),
    )
    if not rows:
        await update.effective_message.reply_text(
            "No invite data yet — once members start adding users, "
            "this list will fill up.",
        )
        return
    lines = [f"🏆 <b>Top inviters in {html.escape(chat.title or 'this group')}</b>"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        marker = medals[i] if i < 3 else f"{i+1}."
        name = html.escape((r["inviter_name"] or "user")[:32])
        lines.append(
            f"{marker} <a href=\"tg://user?id={int(r['inviter_id'])}\">{name}</a> "
            f"— <b>{int(r['count'])}</b> invite{'s' if int(r['count']) != 1 else ''}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True,
    )


async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except TelegramError:
        await update.effective_message.reply_text("Couldn't fetch admins.")
        return
    lines = ["<b>Admins:</b>"]
    for a in admins:
        u = a.user
        title = ""
        if isinstance(a, ChatMemberAdministrator) and a.custom_title:
            title = f" — <i>{html.escape(a.custom_title)}</i>"
        lines.append(f"• {fmt_user(u)}{title}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_staff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except TelegramError:
        return
    lines = [f"<b>Staff for {html.escape(chat.title or '')}</b>"]
    for a in admins:
        lines.append(f"👮 {fmt_user(a.user)}")
    rows = await db_all(
        "SELECT user_id, role FROM group_members WHERE chat_id=? AND role IN ('moderator','cleaner')",
        (chat.id,),
    )
    for r in rows:
        u = await db_one("SELECT first_name, last_name FROM users WHERE user_id=?", (r["user_id"],))
        name = (u["first_name"] if u else f"User {r['user_id']}") or f"User {r['user_id']}"
        lines.append(f"{'🛡' if r['role']=='moderator' else '🧹'} {fmt_user_id(r['user_id'], name)} — {r['role']}")
    text = "\n".join(lines)
    try:
        await context.bot.send_message(user.id, text, parse_mode=ParseMode.HTML)
        await update.effective_message.reply_text("Sent in DM.")
    except TelegramError:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a message to report it.")
        return
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except TelegramError:
        admins = []
    target = msg.reply_to_message.from_user
    text = (
        f"🆘 Report by {fmt_user(update.effective_user)} for {fmt_user(target)}.\n"
        f"<a href=\"https://t.me/c/{str(chat.id)[4:]}/{msg.reply_to_message.message_id}\">Open message</a>"
        if str(chat.id).startswith("-100") else f"🆘 Report by {fmt_user(update.effective_user)} for {fmt_user(target)}."
    )
    mentions = " ".join(fmt_user(a.user) for a in admins)
    await msg.reply_text(text + "\n" + mentions, parse_mode=ParseMode.HTML)


async def cmd_geturl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a message.")
        return
    if str(chat.id).startswith("-100"):
        link = f"https://t.me/c/{str(chat.id)[4:]}/{msg.reply_to_message.message_id}"
        await msg.reply_text(link, disable_web_page_preview=True)
    else:
        await msg.reply_text("Only available for supergroups.")


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    ids = await refresh_admins(context.bot, chat.id)
    await update.effective_message.reply_text(f"✅ Admin list refreshed ({len(ids)} admins).")


# =============================================================================
# BLACKLIST / BLOCKS / WHITELIST
# =============================================================================
async def cmd_addblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /addblacklist <word>")
        return
    word = " ".join(context.args).lower()
    await db_exec("INSERT OR IGNORE INTO blacklist(chat_id, word) VALUES (?,?)", (chat.id, word))
    await update.effective_message.reply_text(f"✅ Added '{word}' to blacklist.")


async def cmd_delblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /delblacklist <word>")
        return
    word = " ".join(context.args).lower()
    await db_exec("DELETE FROM blacklist WHERE chat_id=? AND word=?", (chat.id, word))
    await update.effective_message.reply_text(f"✅ Removed '{word}'.")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    rows = await db_all("SELECT word FROM blacklist WHERE chat_id=?", (chat.id,))
    text = "<b>Blacklist:</b>\n" + ("\n".join("• " + html.escape(r["word"]) for r in rows) or "(empty)")
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target = await _resolve_target(update, context)
    if target is None:
        await update.effective_message.reply_text(
            "Reply to a user, or pass @username / user_id."
        )
        return
    await db_exec("INSERT OR IGNORE INTO blocks(chat_id, user_id) VALUES (?,?)", (chat.id, target.id))
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
    except TelegramError:
        pass
    await update.effective_message.reply_text(f"🔒 Blocked {fmt_user(target)}", parse_mode=ParseMode.HTML)


async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    target = await _resolve_target(update, context)
    if target is None:
        return
    await db_exec("DELETE FROM blocks WHERE chat_id=? AND user_id=?", (chat.id, target.id))
    try:
        await context.bot.unban_chat_member(chat.id, target.id, only_if_banned=True)
    except TelegramError:
        pass
    await update.effective_message.reply_text(f"♻️ Unblocked {fmt_user(target)}", parse_mode=ParseMode.HTML)


async def cmd_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    rows = await db_all("SELECT user_id FROM blocks WHERE chat_id=?", (chat.id,))
    text = "<b>Blocklist:</b>\n" + ("\n".join(f"• <code>{r['user_id']}</code>" for r in rows) or "(empty)")
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_addwhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /addwhitelist <domain>")
        return
    await db_exec(
        "INSERT OR IGNORE INTO link_whitelist(chat_id, domain) VALUES (?,?)",
        (chat.id, context.args[0].lower()),
    )
    await update.effective_message.reply_text(f"✅ Whitelisted {context.args[0]}")


async def cmd_delwhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    if not context.args:
        return
    await db_exec(
        "DELETE FROM link_whitelist WHERE chat_id=? AND domain=?",
        (chat.id, context.args[0].lower()),
    )
    await update.effective_message.reply_text("✅ Removed.")


# =============================================================================
# INACTIVE MEMBERS
# =============================================================================
async def cmd_inactives(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await is_admin(context.bot, chat.id, user.id):
        return
    days = 7
    if context.args and context.args[0].isdigit():
        days = max(1, int(context.args[0]))
    cutoff = now_ts() - days * 86400
    rows = await db_all(
        "SELECT gm.user_id, gm.last_message, u.first_name FROM group_members gm "
        "LEFT JOIN users u ON u.user_id=gm.user_id "
        "WHERE gm.chat_id=? AND gm.last_message<? ORDER BY gm.last_message ASC LIMIT 50",
        (chat.id, cutoff),
    )
    if not rows:
        await update.effective_message.reply_text(f"No inactive members in the last {days} days.")
        return
    try:
        await context.bot.send_message(user.id, f"<b>Inactive members ({days}+ days):</b>", parse_mode=ParseMode.HTML)
        for r in rows:
            name = r["first_name"] or f"User {r['user_id']}"
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⚠️ Warn", callback_data=f"inact:warn:{chat.id}:{r['user_id']}"),
                        InlineKeyboardButton("🔇 Mute", callback_data=f"inact:mute:{chat.id}:{r['user_id']}"),
                        InlineKeyboardButton("👢 Kick", callback_data=f"inact:kick:{chat.id}:{r['user_id']}"),
                    ]
                ]
            )
            last = datetime.fromtimestamp(r["last_message"]).strftime("%Y-%m-%d") if r["last_message"] else "never"
            await context.bot.send_message(
                user.id,
                f"• {fmt_user_id(r['user_id'], name)} — last seen {last}",
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        await update.effective_message.reply_text("Sent the inactive list in DM.")
    except TelegramError:
        await update.effective_message.reply_text("Open me in DM first.")


async def cb_inactives(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    try:
        await q.answer()
    except TelegramError:
        pass
    parts = q.data.split(":")
    if len(parts) != 4:
        return
    action, chat_id, user_id = parts[1], int(parts[2]), int(parts[3])
    if not await is_admin(context.bot, chat_id, q.from_user.id):
        await q.answer("Admins only.", show_alert=True)
        return
    if action == "warn":
        await db_exec(
            "INSERT INTO warns(chat_id, user_id, admin_id, reason, created_at) VALUES (?,?,?,?,?)",
            (chat_id, user_id, q.from_user.id, "inactive", now_ts()),
        )
        await q.answer("Warned.")
    elif action == "mute":
        await _apply_action(context.bot, chat_id, user_id, "mute")
        await q.answer("Muted.")
    elif action == "kick":
        await _apply_action(context.bot, chat_id, user_id, "kick")
        await q.answer("Kicked.")


# =============================================================================
# /list and statistics
# =============================================================================
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await is_admin(context.bot, chat.id, user.id):
        return
    if context.args and context.args[0] == "roles":
        rows = await db_all(
            "SELECT user_id, role FROM group_members WHERE chat_id=? AND role!='' ORDER BY role",
            (chat.id,),
        )
        lines = ["<b>Roles:</b>"]
        for r in rows:
            u = await db_one("SELECT first_name FROM users WHERE user_id=?", (r["user_id"],))
            name = u["first_name"] if u else f"User {r['user_id']}"
            lines.append(f"• {fmt_user_id(r['user_id'], name)} — {r['role']}")
        text = "\n".join(lines) if rows else "No special roles assigned."
    else:
        rows = await db_all(
            "SELECT user_id, message_count FROM group_members WHERE chat_id=? ORDER BY message_count DESC LIMIT 50",
            (chat.id,),
        )
        lines = ["<b>Top users by messages:</b>"]
        for r in rows:
            u = await db_one("SELECT first_name FROM users WHERE user_id=?", (r["user_id"],))
            name = u["first_name"] if u else f"User {r['user_id']}"
            lines.append(f"• {fmt_user_id(r['user_id'], name)} — {r['message_count']}")
        text = "\n".join(lines) if rows else "No data yet."
    try:
        await context.bot.send_message(user.id, text, parse_mode=ParseMode.HTML)
        await update.effective_message.reply_text("Sent in DM.")
    except TelegramError:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_graphic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if not await is_admin(context.bot, chat.id, update.effective_user.id):
        return
    img = await make_member_chart(chat.id, chat.title or "")
    if img is None:
        await update.effective_message.reply_text("Not enough data yet.")
        return
    await context.bot.send_photo(
        chat.id,
        photo=InputFile(io.BytesIO(img), filename="trend.png"),
        caption=f"📈 Member trend — {html.escape(chat.title or '')}",
    )


async def cmd_trend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    rows = await db_all("SELECT day, members FROM member_history WHERE chat_id=? ORDER BY day", (chat.id,))
    if not rows:
        await update.effective_message.reply_text("Not enough data yet.")
        return
    first = rows[0]["members"]
    last = rows[-1]["members"]
    days = len(rows)
    delta = last - first
    text = (
        f"📊 <b>Trend</b>\n"
        f"Tracked days: {days}\n"
        f"Members start: {first}\n"
        f"Members now: {last}\n"
        f"Net change: {'+' if delta >= 0 else ''}{delta}\n"
        f"Average daily: {(delta / max(days,1)):.2f}"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


# =============================================================================
# MESSAGE PIPELINE: track, anti-spam, anti-flood, blocks, media, links, etc.
# =============================================================================
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]+")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")
URL_RE = re.compile(r"https?://\S+|t\.me/\S+|www\.\S+", re.IGNORECASE)


async def _is_punishable(bot: Bot, chat_id: int, user_id: int) -> bool:
    if user_id == BOT_OWNER_ID:
        return False
    if await is_admin(bot, chat_id, user_id):
        return False
    return True


async def _track_message(chat_id: int, user_id: int) -> None:
    await db_exec(
        "INSERT INTO group_members(chat_id, user_id, joined_at, last_message, message_count, role, approved) "
        "VALUES (?,?,?,?,1,'',1) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET last_message=excluded.last_message, "
        "message_count=group_members.message_count+1",
        (chat_id, user_id, now_ts(), now_ts()),
    )


def _is_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) > 0.7


async def _check_flood(chat_id: int, user_id: int, threshold: int, window: int) -> bool:
    row = await db_one(
        "SELECT last_messages FROM flood_track WHERE chat_id=? AND user_id=?",
        (chat_id, user_id),
    )
    history = []
    if row and row["last_messages"]:
        try:
            history = [int(x) for x in row["last_messages"].split(",") if x]
        except ValueError:
            history = []
    now = now_ts()
    history = [t for t in history if now - t <= window]
    history.append(now)
    serialized = ",".join(str(x) for x in history[-50:])
    await db_exec(
        "INSERT OR REPLACE INTO flood_track(chat_id, user_id, last_messages) VALUES (?,?,?)",
        (chat_id, user_id, serialized),
    )
    return len(history) >= threshold


async def message_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await _message_pipeline_impl(update, context)
    except Exception:
        # Never let a single bad message kill the whole pipeline — log and move on.
        log.exception("message_pipeline failed for update")


async def _message_pipeline_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if msg is None or chat is None or user is None:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if user.is_bot and user.username == BOT_USERNAME:
        return
    await ensure_group(chat)
    await ensure_user(user)
    await _track_message(chat.id, user.id)
    s = await get_settings(chat.id)

    # blocks
    if await db_one("SELECT 1 FROM blocks WHERE chat_id=? AND user_id=?", (chat.id, user.id)):
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
        except TelegramError:
            pass
        return

    if not await _is_punishable(context.bot, chat.id, user.id):
        return

    # global silence
    if s["silence_on"]:
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except TelegramError:
            pass
        return

    # night mode
    if s["night_on"]:
        h = datetime.now(timezone.utc).hour
        start, end = s["night_start"], s["night_end"]
        active = (start < end and start <= h < end) or (start > end and (h >= start or h < end))
        if active:
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
            return

    text = (msg.text or msg.caption or "")
    low = text.lower()

    # blacklist
    bl = await db_all("SELECT word FROM blacklist WHERE chat_id=?", (chat.id,))
    for r in bl:
        if r["word"] and r["word"] in low:
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
            await _apply_action(context.bot, chat.id, user.id, s["antispam_action"])
            return

    # anti-spam alphabets / caps / forwards / inline
    violation = False
    if s["antispam_arabic"] and ARABIC_RE.search(text):
        violation = True
    if s["antispam_chinese"] and CHINESE_RE.search(text):
        violation = True
    if s["antispam_caps"] and _is_caps(text):
        violation = True
    if s["antispam_forwards"] and msg.forward_origin:
        violation = True
    if s["antispam_inlinebots"] and msg.via_bot:
        violation = True
    if violation:
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except TelegramError:
            pass
        await _apply_action(context.bot, chat.id, user.id, s["antispam_action"])
        return

    # New per-section antispam (Telegram links / Forwarding / Quote / Total links)
    async def _enforce(action_key: str, delete_too: bool = True) -> bool:
        action = (s.get(action_key) or "off")
        if action == "off":
            return False
        if delete_too:
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
        await _apply_action(context.bot, chat.id, user.id, action)
        return True

    has_tg_link = ("t.me/" in low) or ("telegram.me/" in low) or ("tg://" in low)
    if not has_tg_link and msg.entities:
        for ent in msg.entities:
            if ent.type == "url":
                seg = text[ent.offset: ent.offset + ent.length].lower()
                if "t.me/" in seg or "telegram.me/" in seg:
                    has_tg_link = True
                    break
            if ent.type == "mention" and s.get("antispam_username_on"):
                has_tg_link = True
                break
    if has_tg_link:
        if await _enforce("antispam_links_action",
                          delete_too=bool(s.get("antispam_links_delete"))):
            return

    if msg.forward_origin:
        if await _enforce("antispam_forward_action"):
            return

    if msg.reply_to_message and msg.reply_to_message.forward_origin:
        if await _enforce("antispam_quote_action"):
            return

    # link filter
    if (s["block_links"] or (s.get("antispam_totallinks_action") or "off") != "off") and URL_RE.search(text):
        whitelisted = False
        wl = await db_all("SELECT domain FROM link_whitelist WHERE chat_id=?", (chat.id,))
        for r in wl:
            if r["domain"] in low:
                whitelisted = True
                break
        if not whitelisted:
            if (s.get("antispam_totallinks_action") or "off") != "off":
                if await _enforce("antispam_totallinks_action"):
                    return
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
            return

    # tag filter
    if s["tag_on"] and msg.entities:
        mentions = sum(1 for e in msg.entities if e.type in ("mention", "text_mention"))
        if mentions > s["max_mentions"]:
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
            return

    # media filter (per-type action)
    media_keys = []
    if msg.photo:
        media_keys.append("media_photo")
        if msg.media_group_id:
            media_keys.append("media_album")
    if msg.video:
        media_keys.append("media_video")
        if msg.media_group_id:
            media_keys.append("media_album")
    if msg.sticker:
        sticker = msg.sticker
        if getattr(sticker, "is_animated", False) or getattr(sticker, "is_video", False):
            media_keys.append("media_animsticker")
        else:
            media_keys.append("media_sticker")
        if getattr(sticker, "premium_animation", None):
            media_keys.append("media_premium")
    if msg.animation:
        media_keys.append("media_gif")
    if msg.document:
        media_keys.append("media_doc")
    if msg.voice:
        media_keys.append("media_voice")
    if msg.audio:
        media_keys.append("media_audio")
    if msg.video_note:
        media_keys.append("media_videonote")
    if msg.story:
        media_keys.append("media_story")
    if msg.game:
        media_keys.append("media_animgame")
    if msg.entities:
        for ent in msg.entities:
            if ent.type == "custom_emoji":
                media_keys.append("media_animemoji")
                break

    for mkey in media_keys:
        action = (s.get(mkey) or "off")
        if action == "off":
            continue
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except TelegramError:
            pass
        if action != "del":
            await _apply_action(context.bot, chat.id, user.id, action)
        return

    # anti-flood
    if s["antiflood_on"]:
        if await _check_flood(chat.id, user.id, s["antiflood_messages"], s["antiflood_seconds"]):
            await _apply_action(context.bot, chat.id, user.id, s["antiflood_action"])
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
            return

    # delete commands setting
    if s["delete_commands"] and msg.text and msg.text.startswith("/"):
        try:
            await context.bot.delete_message(chat.id, msg.message_id)
        except TelegramError:
            pass
        return

    # self destruct
    if s["selfdestruct_seconds"]:
        async def _kill(mid: int, secs: int):
            await asyncio.sleep(secs)
            try:
                await context.bot.delete_message(chat.id, mid)
            except TelegramError:
                pass
        context.application.create_task(_kill(msg.message_id, s["selfdestruct_seconds"]))


async def edited_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.edited_message
    if msg is None:
        return
    chat = msg.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    s = await get_settings(chat.id)
    if not s["edit_check_on"]:
        return
    # Re-run a simplified inspection on edits
    text = (msg.text or msg.caption or "").lower()
    bl = await db_all("SELECT word FROM blacklist WHERE chat_id=?", (chat.id,))
    for r in bl:
        if r["word"] in text:
            try:
                await context.bot.delete_message(chat.id, msg.message_id)
            except TelegramError:
                pass
            return


# =============================================================================
# Service messages cleanup (join/leave)
# =============================================================================
async def service_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    chat = msg.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    s = await get_settings(chat.id)

    async def schedule_delete(seconds: int):
        try:
            if seconds <= 0:
                await context.bot.delete_message(chat.id, msg.message_id)
            else:
                async def runner():
                    await asyncio.sleep(seconds)
                    try:
                        await context.bot.delete_message(chat.id, msg.message_id)
                    except TelegramError:
                        pass
                context.application.create_task(runner())
        except TelegramError:
            pass

    if msg.new_chat_members and s["service_join_minutes"]:
        await schedule_delete(s["service_join_minutes"] * 60)
    elif msg.left_chat_member and s["service_exit_minutes"]:
        await schedule_delete(s["service_exit_minutes"] * 60)
    elif msg.new_chat_photo and s["service_photo"]:
        await schedule_delete(0)
    elif msg.new_chat_title and s["service_title"]:
        await schedule_delete(0)
    elif msg.pinned_message and s["service_pinned"]:
        await schedule_delete(0)
    elif (msg.video_chat_started or msg.video_chat_ended or msg.video_chat_scheduled or msg.video_chat_participants_invited) and s["service_videochat"]:
        await schedule_delete(0)
    elif msg.forum_topic_created or msg.forum_topic_closed or msg.forum_topic_reopened:
        if s["service_topic"]:
            await schedule_delete(0)


# =============================================================================
# Generic noop / popup callback / show_rules
# =============================================================================
async def cb_misc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q.data is None:
        try:
            await q.answer()
        except TelegramError:
            pass
        return
    if q.data.startswith("popup:"):
        await q.answer(q.data[6:], show_alert=True)
        return
    if q.data.startswith("copy:"):
        await q.answer(q.data[5:], show_alert=True)
        return
    if q.data == "show_rules":
        chat = q.message.chat
        g = await db_one("SELECT rules FROM groups WHERE chat_id=?", (chat.id,))
        rules = (g["rules"] if g else "") or "(no rules)"
        await q.answer(rules[:200], show_alert=True)
        return
    await q.answer()


# =============================================================================
# Error handler
# =============================================================================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Telegram uses BadRequest for a harmless no-op edit when the requested
    # content/keyboard is already identical to the current message.
    if isinstance(context.error, BadRequest) and "message is not modified" in str(context.error).lower():
        return
    log.error("Exception while handling update", exc_info=context.error)
    if BOT_OWNER_ID:
        try:
            tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))[-3500:]
            await context.bot.send_message(
                BOT_OWNER_ID,
                f"<b>Error</b>\n<pre>{html.escape(tb)}</pre>",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass


# =============================================================================
# main()
# =============================================================================
async def _post_init(app: Application) -> None:
    await db_init()
    await _other_init()
    _other_schedule_recurring(app)
    global BOT_USERNAME
    try:
        me = await app.bot.get_me()
        if me.username:
            BOT_USERNAME = me.username
    except TelegramError:
        pass
    try:
        # Telegram supports up to 100 commands per command-menu scope.
        # Register the same menu for private chats AND groups so slash commands
        # are visible after the bot is added as an administrator.
        menu = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help"),
            BotCommand("allcommands", "Show all commands"),
            BotCommand("settings", "Manage group settings"),
            BotCommand("welcome", "Welcome settings"),
            BotCommand("setwelcome", "Set welcome message"),
            BotCommand("goodbye", "Goodbye settings"),
            BotCommand("setgoodbye", "Set goodbye message"),
            BotCommand("cleanservice", "Clean service messages"),
            BotCommand("cleanservicetypes", "Service message types"),
            BotCommand("cleancommand", "Clean commands"),
            BotCommand("cleancommandtypes", "Command types"),
            BotCommand("rules", "Show group rules"),
            BotCommand("info", "User info"),
            BotCommand("me", "Your info"),
            BotCommand("admins", "List admins"),
            BotCommand("staff", "List staff"),
            BotCommand("stats", "Bot stats"),
            BotCommand("warns", "List warns"),
            BotCommand("ban", "Ban a user"),
            BotCommand("mute", "Mute a user"),
            BotCommand("kick", "Kick a user"),
            BotCommand("unban", "Unban a user"),
            BotCommand("promote", "Promote a user"),
            BotCommand("demote", "Demote a user"),
            BotCommand("flood", "Antiflood settings"),
            BotCommand("setflood", "Set antiflood"),
            BotCommand("floodmode", "Flood action"),
            BotCommand("blocklist", "Blocklist"),
            BotCommand("addblocklist", "Add blocklist item"),
            BotCommand("rmblocklist", "Remove blocklist item"),
        ]
        await app.bot.set_my_commands(menu, scope=BotCommandScopeAllPrivateChats())
        await app.bot.set_my_commands(menu, scope=BotCommandScopeAllGroupChats())
        await app.bot.set_my_commands(menu)
    except TelegramError as e:
        log.warning("Could not set Telegram command menu: %s", e)


# ======================================================================
# ADVANCED MODULES: i18n, Notes, Filters, Locks, Disable, Federations,
# Connect, Global ban/mute, Mass / Silent actions, AFK, Mini tools.
# Each module is grouped with its own helpers + commands + handlers and
# registered in main() further below.
# ======================================================================


# ----------------------------------------------------------------------
# i18n: translations live in bot/lang.py.  The table below kept here for
# backwards compatibility with very old chats — the real source of truth
# is the imported ``I18N``/``AUTO_TRANSLATE`` maps.
# ----------------------------------------------------------------------
_LEGACY_I18N: dict[str, dict[str, str]] = {
    "en": {
        "warned": "{user} has been warned. ({count}/{limit})",
        "warn_reset": "Warns for {user} reset to 0.",
        "muted": "{user} has been muted.",
        "unmuted": "{user} has been unmuted.",
        "banned": "{user} has been banned.",
        "unbanned": "{user} has been unbanned.",
        "kicked": "{user} has been kicked.",
        "no_target": "Reply to a user, or pass an @username / user id.",
        "not_admin": "You need to be an admin to use this.",
        "bot_no_perm": "I don't have the right permission to do this.",
        "self_target": "You can't use this on yourself.",
        "admin_target": "I can't act against another admin.",
        "owner_target": "I can't act against the chat owner.",
        "fed_only_owner": "Only the federation owner can do this.",
        "fed_not_found": "Federation not found.",
        "fed_created": "Federation '{name}' created with id `{fid}`.",
        "fed_joined": "This chat joined federation `{fid}`.",
        "fed_left": "This chat left the federation.",
        "fed_banned": "{user} fed-banned across {n} chats. Reason: {reason}",
        "fed_unbanned": "{user} removed from federation ban list.",
        "note_saved": "Note `{name}` saved.",
        "note_cleared": "Note `{name}` cleared.",
        "note_missing": "I don't have a note named `{name}`.",
        "filter_saved": "Filter `{kw}` saved.",
        "filter_cleared": "Filter `{kw}` cleared.",
        "filters_empty": "No filters are configured here.",
        "lock_set": "Locked `{type}`.",
        "unlock_set": "Unlocked `{type}`.",
        "lock_unknown": "Unknown lock type. Try /locktypes.",
        "disabled_set": "Command `{cmd}` disabled.",
        "enabled_set": "Command `{cmd}` enabled.",
        "afk_on": "{user} is now AFK. Reason: {reason}",
        "afk_back": "{user} is back. Was AFK for {dur}.",
        "connect_ok": "Connected to {title}.",
        "connect_off": "Disconnected.",
        "connect_none": "Not connected to any chat.",
        "gban_ok": "Globally banned {user}.",
        "ungban_ok": "Removed {user} from the global ban list.",
    },
    "bn": {
        "warned": "{user} সতর্ক করা হয়েছে। ({count}/{limit})",
        "warn_reset": "{user}-এর সতর্কতা ০ করা হয়েছে।",
        "muted": "{user} মিউট করা হয়েছে।",
        "unmuted": "{user} আনমিউট করা হয়েছে।",
        "banned": "{user} ব্যান করা হয়েছে।",
        "unbanned": "{user} আনব্যান করা হয়েছে।",
        "kicked": "{user} কিক করা হয়েছে।",
        "no_target": "ইউজারকে রিপ্লাই করুন, অথবা @username / user-id দিন।",
        "not_admin": "এই কমান্ড ব্যবহারের জন্য অ্যাডমিন হতে হবে।",
        "bot_no_perm": "এই কাজটা করার অনুমতি আমার নেই।",
        "self_target": "নিজের উপর প্রয়োগ করা যাবে না।",
        "admin_target": "অন্য অ্যাডমিনের বিরুদ্ধে এই অ্যাকশন নেওয়া যাবে না।",
        "owner_target": "চ্যাট-ওনারের বিরুদ্ধে এই অ্যাকশন নেওয়া যাবে না।",
        "fed_only_owner": "শুধু ফেডারেশন ওনার এটি করতে পারবেন।",
        "fed_not_found": "ফেডারেশন পাওয়া যায়নি।",
        "fed_created": "ফেডারেশন '{name}' তৈরি হয়েছে। আইডি `{fid}`।",
        "fed_joined": "এই চ্যাট ফেডারেশন `{fid}`-এ যুক্ত হলো।",
        "fed_left": "এই চ্যাট ফেডারেশন থেকে বের হলো।",
        "fed_banned": "{user} {n}টি চ্যাটে ফেড-ব্যান হয়েছে। কারণ: {reason}",
        "fed_unbanned": "{user} ফেডারেশন ব্যান-লিস্ট থেকে সরানো হলো।",
        "note_saved": "নোট `{name}` সংরক্ষিত।",
        "note_cleared": "নোট `{name}` মুছে ফেলা হলো।",
        "note_missing": "`{name}` নামে কোনো নোট নেই।",
        "filter_saved": "ফিল্টার `{kw}` সংরক্ষিত।",
        "filter_cleared": "ফিল্টার `{kw}` মুছে ফেলা হলো।",
        "filters_empty": "এখানে কোনো ফিল্টার নেই।",
        "lock_set": "`{type}` লক করা হলো।",
        "unlock_set": "`{type}` আনলক হলো।",
        "lock_unknown": "অজানা লক টাইপ। /locktypes দেখুন।",
        "disabled_set": "কমান্ড `{cmd}` বন্ধ করা হলো।",
        "enabled_set": "কমান্ড `{cmd}` চালু করা হলো।",
        "afk_on": "{user} এখন AFK। কারণ: {reason}",
        "afk_back": "{user} ফিরে এসেছে। AFK ছিল {dur}।",
        "connect_ok": "{title}-এর সাথে সংযুক্ত।",
        "connect_off": "সংযোগ বিচ্ছিন্ন।",
        "connect_none": "কোনো চ্যাটের সাথে সংযুক্ত নয়।",
        "gban_ok": "{user} গ্লোবাল-ব্যান হলো।",
        "ungban_ok": "{user} গ্লোবাল ব্যান-লিস্ট থেকে সরানো হলো।",
    },
    "ur": {
        "warned": "{user} کو تنبیہ دی گئی۔ ({count}/{limit})",
        "warn_reset": "{user} کی وارننگز ۰ کر دی گئیں۔",
        "muted": "{user} میوٹ کر دیا گیا۔",
        "unmuted": "{user} اَن-میوٹ کر دیا گیا۔",
        "banned": "{user} پر پابندی لگا دی گئی۔",
        "unbanned": "{user} سے پابندی ہٹا دی گئی۔",
        "kicked": "{user} کو نکال دیا گیا۔",
        "no_target": "صارف کو ریپلائی کریں، یا @username / user-id بھیجیں۔",
        "not_admin": "اس کمانڈ کے لیے آپ کا ایڈمن ہونا ضروری ہے۔",
        "bot_no_perm": "یہ کام کرنے کی اجازت میرے پاس نہیں۔",
        "self_target": "خود پر استعمال نہیں ہو سکتا۔",
        "admin_target": "کسی اور ایڈمن پر یہ کارروائی نہیں ہو سکتی۔",
        "owner_target": "چیٹ اونر پر یہ کارروائی نہیں ہو سکتی۔",
        "fed_only_owner": "صرف فیڈریشن اونر یہ کر سکتا ہے۔",
        "fed_not_found": "فیڈریشن نہیں ملی۔",
        "fed_created": "فیڈریشن '{name}' بنا دی گئی۔ آئی ڈی `{fid}`۔",
        "fed_joined": "یہ چیٹ فیڈریشن `{fid}` میں شامل ہو گئی۔",
        "fed_left": "یہ چیٹ فیڈریشن سے نکل گئی۔",
        "fed_banned": "{user} {n} چیٹس میں فیڈ-بین ہوا۔ وجہ: {reason}",
        "fed_unbanned": "{user} فیڈریشن بین-لسٹ سے ہٹا دیا گیا۔",
        "note_saved": "نوٹ `{name}` محفوظ کر لیا گیا۔",
        "note_cleared": "نوٹ `{name}` ہٹا دیا گیا۔",
        "note_missing": "`{name}` نام کا کوئی نوٹ نہیں۔",
        "filter_saved": "فلٹر `{kw}` محفوظ ہو گیا۔",
        "filter_cleared": "فلٹر `{kw}` ہٹا دیا گیا۔",
        "filters_empty": "یہاں کوئی فلٹر نہیں ہے۔",
        "lock_set": "`{type}` لاک کر دیا گیا۔",
        "unlock_set": "`{type}` اَن-لاک کر دیا گیا۔",
        "lock_unknown": "نامعلوم لاک قسم۔ /locktypes دیکھیں۔",
        "disabled_set": "کمانڈ `{cmd}` بند کر دی گئی۔",
        "enabled_set": "کمانڈ `{cmd}` چالو کر دی گئی۔",
        "afk_on": "{user} اب AFK ہے۔ وجہ: {reason}",
        "afk_back": "{user} واپس آ گیا۔ AFK وقت: {dur}۔",
        "connect_ok": "{title} سے کنیکٹ ہو گیا۔",
        "connect_off": "ڈسکنیکٹ ہو گیا۔",
        "connect_none": "کسی چیٹ سے کنیکٹ نہیں۔",
        "gban_ok": "{user} گلوبل-بین ہوا۔",
        "ungban_ok": "{user} گلوبل بین-لسٹ سے ہٹا دیا گیا۔",
    },
}


# Translations & language menu live in bot/lang.py
_LANG_I18N = I18N  # inlined from lang.py
_lang_auto_translate = auto_translate  # inlined from lang.py
_lang_t = t  # inlined from lang.py


# ---------------------------------------------------------------------------
# Live Google-Translate fallback so EVERY outgoing reply (not just the few
# strings present in AUTO_TRANSLATE) appears in the triggering user's saved
# language. The static dictionary above is still consulted first (instant +
# offline), and only when it has no entry do we hit Google Translate via the
# `deep_translator` package. Results are cached forever in-process so each
# unique (lang, text) pair is translated at most once per bot run.
# ---------------------------------------------------------------------------
try:
    from deep_translator import GoogleTranslator as _GoogleTranslator  # type: ignore
except Exception:  # pragma: no cover — translator is optional at import time
    _GoogleTranslator = None  # type: ignore

# Telegram language codes -> Google Translate language codes.
_GOOGLE_LANG_MAP: dict[str, str] = {
    "zh": "zh-CN", "zt": "zh-TW", "uz_cy": "uz", "ku": "ckb",
    "he": "iw",  # Google still uses the legacy Hebrew code.
}

# (lang, text) -> translated text
_TRANSLATE_CACHE: dict[tuple[str, str], str] = {}
# Avoid hammering Google when it is unreachable / rate-limiting.
_TRANSLATE_DISABLED_UNTIL: float = 0.0


def _google_translate_sync(lang: str, text: str) -> str:
    """Blocking Google-Translate call. Always wrap in run_in_executor."""
    global _TRANSLATE_DISABLED_UNTIL
    if _GoogleTranslator is None:
        return text
    target = _GOOGLE_LANG_MAP.get(lang, lang)
    try:
        out = _GoogleTranslator(source="auto", target=target).translate(text)
        if isinstance(out, str) and out.strip():
            return out
    except Exception:
        # Back off for 60s on any network/rate error so the bot stays snappy.
        import time as _time
        _TRANSLATE_DISABLED_UNTIL = _time.time() + 60.0
    return text


async def _lang_translate_live(lang: str, text: str) -> str:
    """Translate ``text`` into ``lang`` using dict first, then Google."""
    if not text or not lang or lang == "en":
        return text
    # 1. Try the inlined static dictionary first (fast / offline).
    static = _lang_auto_translate(lang, text)
    if static is not None and static != text:
        return static
    # 2. Network fallback via Google Translate, with permanent cache.
    if _GoogleTranslator is None:
        return text
    key = (lang, text)
    cached = _TRANSLATE_CACHE.get(key)
    if cached is not None:
        return cached
    import time as _time
    if _time.time() < _TRANSLATE_DISABLED_UNTIL:
        return text
    try:
        loop = asyncio.get_running_loop()
        out = await asyncio.wait_for(
            loop.run_in_executor(None, _google_translate_sync, lang, text),
            timeout=4.0,
        )
    except Exception:
        return text
    if isinstance(out, str) and out.strip():
        _TRANSLATE_CACHE[key] = out
        return out
    return text

# Merge the legacy in-file table with the lang.py table so any historic key
# the bot still references (but lang.py hasn't picked up yet) keeps working.
I18N: dict[str, dict[str, str]] = {}
for _code in set(list(_LEGACY_I18N.keys()) + list(_LANG_I18N.keys())):
    merged = {}
    merged.update(_LEGACY_I18N.get(_code, {}))
    merged.update(_LANG_I18N.get(_code, {}))
    I18N[_code] = merged

# In-memory chat-language cache (chat_id -> (lang_code, expiry_ts)).
_CHAT_LANG_CACHE: dict[int, tuple[str, float]] = {}
_CHAT_LANG_TTL = 60.0  # seconds


async def _chat_lang(chat_id: int) -> str:
    """Fetch the configured language for a chat (cached, defaults to English)."""
    now = time.time()
    cached = _CHAT_LANG_CACHE.get(chat_id)
    if cached and cached[1] > now:
        return cached[0]
    db = await _get_db()
    async with db.execute(
        "SELECT lang FROM group_settings WHERE chat_id = ?",
        (chat_id,),
    ) as cur:
        row = await cur.fetchone()
    code = (row[0] if row and row[0] else "en") or "en"
    _CHAT_LANG_CACHE[chat_id] = (code, now + _CHAT_LANG_TTL)
    return code


def _chat_lang_invalidate(chat_id: int) -> None:
    """Drop the cached language for ``chat_id`` so the next lookup re-reads."""
    _CHAT_LANG_CACHE.pop(chat_id, None)


def _t(lang: str, key: str, **kwargs) -> str:
    """Translate ``key`` into ``lang`` using the merged table."""
    lang = lang if lang in I18N else "en"
    template = (
        I18N.get(lang, {}).get(key)
        or I18N.get("en", {}).get(key)
        or key
    )
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


async def tr(chat_id: int, key: str, **kwargs) -> str:
    """Convenience: lookup chat language then translate."""
    return _t(await _chat_lang(chat_id), key, **kwargs)


# ----------------------------------------------------------------------
# Auto-translate hook -- patches Message.reply_text / Bot.send_message so
# any plain-string outgoing message gets converted to the chat's selected
# language (when a translation exists in lang.AUTO_TRANSLATE).
# ----------------------------------------------------------------------
import telegram as _tg  # noqa: E402

_orig_msg_reply_text = _tg.Message.reply_text
_orig_msg_reply_html = _tg.Message.reply_html
_orig_msg_reply_markdown = _tg.Message.reply_markdown
_orig_msg_reply_markdown_v2 = _tg.Message.reply_markdown_v2
_orig_bot_send_message = _tg.Bot.send_message
# Per-update triggering-user tracker — every Update handler calls _capture_trigger_user
# (registered as a TypeHandler in main()) which stores the originating user_id into
# this ContextVar. _maybe_translate_for_chat then prefers that user's saved language
# whenever it has to translate an outgoing message, so welcome / warn / captcha /
# antispam / antiflood / ban / mute / kick / help / settings / etc. all appear in the
# language the user picked from the welcome-message language button or /settings.
_current_trigger_user: contextvars.ContextVar = contextvars.ContextVar(
    "current_trigger_user", default=None,
)

# Set to True around sends that contain admin-authored content (welcome,
# goodbye, rules, notes, filter replies, etc.) so the live translator does
# NOT mangle the text the group owner explicitly typed.
_skip_translate: contextvars.ContextVar = contextvars.ContextVar(
    "skip_translate", default=False,
)


async def _capture_trigger_user(update, context):
    """TypeHandler-driven hook: remember which user triggered the current update."""
    try:
        if update is not None and update.effective_user is not None:
            _current_trigger_user.set(update.effective_user.id)
    except Exception:
        pass




async def _maybe_translate_for_chat(chat_id, text, user_id=None):
    """Return ``text`` translated for the chat's (or user's) language.

    Resolution order, so that EVERY user-facing string the bot sends ends up
    in the language the user picked from the welcome-message language button
    or from /settings:

    1. ``user_id`` argument (the message we're replying to / the recipient).
    2. The triggering user of the current update (captured into a ContextVar
       by ``_capture_trigger_user`` before any other handler runs).
    3. For private chats, the chat_id (which equals the recipient user_id).
    4. For groups with no known triggering user, the configured group language.
    """
    if not isinstance(text, str) or not text:
        return text
    # Admin-authored content (welcome, goodbye, rules, notes, filter replies)
    # is opted out via the _skip_translate ContextVar so we never translate
    # the literal text a group owner typed.
    try:
        if _skip_translate.get():
            return text
    except Exception:
        pass
    try:
        cid = int(chat_id) if chat_id is not None else None
    except (TypeError, ValueError):
        cid = None
    # Fall back to the triggering user from the ContextVar set by
    # _capture_trigger_user (registered as a TypeHandler in main()).
    if not user_id:
        try:
            user_id = _current_trigger_user.get()
        except Exception:
            user_id = None
    lang = "en"
    try:
        if user_id:
            # Always prefer the originating / recipient user's saved language
            # — this covers welcome, goodbye, warns, captcha, antispam, antiflood,
            #   ban / mute / kick replies, help text, settings menu, and every
            #   other reply triggered by a specific user.
            lang = await get_user_lang(int(user_id))
        elif cid is not None and cid > 0:
            # Private chat with no explicit user — chat_id IS the recipient.
            lang = await get_user_lang(int(cid))
        elif cid is not None:
            # Pure group-wide broadcast (no triggering user, no recipient user)
            # — fall back to the group's configured language.
            lang = await _chat_lang(cid)
    except Exception:
        return text
    if lang == "en":
        return text
    # HTML-safe path: if the text contains tags, translate only the text
    # nodes between tags so the menus / help cards stay properly formatted
    # and Telegram doesn't reject them with "can't parse entities".
    if "<" in text and ">" in text:
        return await _lang_translate_html_safe(lang, text)
    return await _lang_translate_live(lang, text)


_HTML_TAG_RE = re.compile(r"<[^<>]+>")


async def _lang_translate_html_safe(lang: str, text: str) -> str:
    """Translate ``text`` while preserving any HTML tags it contains.

    Splits on tags, translates only the visible text segments, then re-joins
    the tags verbatim. This stops Google Translate from mangling ``<b>``,
    ``<a href=...>``, ``<code>``, etc. and keeps Telegram parse_mode='HTML'
    happy.
    """
    if not text or not lang or lang == "en":
        return text
    try:
        tags = _HTML_TAG_RE.findall(text)
        parts = _HTML_TAG_RE.split(text)
        new_parts = []
        for part in parts:
            if part and part.strip():
                try:
                    new_parts.append(await _lang_translate_live(lang, part))
                except Exception:
                    new_parts.append(part)
            else:
                new_parts.append(part)
        # Reassemble: parts and tags alternate, parts has len(tags)+1 entries.
        out = []
        for i, p in enumerate(new_parts):
            out.append(p)
            if i < len(tags):
                out.append(tags[i])
        return "".join(out)
    except Exception:
        return text


def _msg_chat_user(self):
    chat_id = getattr(getattr(self, "chat", None), "id", None)
    user_id = getattr(getattr(self, "from_user", None), "id", None)
    return chat_id, user_id


async def _patched_msg_reply_text(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    return await _orig_msg_reply_text(self, text, *args, **kwargs)


async def _patched_msg_reply_html(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    return await _orig_msg_reply_html(self, text, *args, **kwargs)


async def _patched_msg_reply_markdown(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    return await _orig_msg_reply_markdown(self, text, *args, **kwargs)


async def _patched_msg_reply_markdown_v2(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    return await _orig_msg_reply_markdown_v2(self, text, *args, **kwargs)


async def _patched_bot_send_message(self, chat_id, text, *args, **kwargs):
    # For DMs the chat_id IS the recipient user id, so reuse it as user_id.
    user_id = None
    try:
        if chat_id is not None and int(chat_id) > 0:
            user_id = int(chat_id)
    except (TypeError, ValueError):
        pass
    text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    return await _orig_bot_send_message(self, chat_id, text, *args, **kwargs)


_tg.Message.reply_text = _patched_msg_reply_text
_tg.Message.reply_html = _patched_msg_reply_html
_tg.Message.reply_markdown = _patched_msg_reply_markdown
_tg.Message.reply_markdown_v2 = _patched_msg_reply_markdown_v2
_tg.Bot.send_message = _patched_bot_send_message


# ----------------------------------------------------------------------
# Full-coverage translation: buttons, captions, edits, popups, media.
# Resolves the "switched to Hindi but English still appears on buttons /
# DMs / settings menu" issue by walking InlineKeyboardMarkup and patching
# every send/edit method that takes a text or caption argument.
# ----------------------------------------------------------------------
async def _translate_markup_for(reply_markup, chat_id, user_id):
    """Return a copy of ``reply_markup`` with every visible button label
    translated for the recipient's language. Non-keyboard markup is returned
    unchanged. URL/callback/switch-inline payloads are preserved verbatim."""
    if reply_markup is None:
        return None
    try:
        if not isinstance(reply_markup, _tg.InlineKeyboardMarkup):
            return reply_markup
        new_rows = []
        for row in reply_markup.inline_keyboard:
            new_row = []
            for btn in row:
                label = getattr(btn, "text", "") or ""
                new_label = await _maybe_translate_for_chat(
                    chat_id, label, user_id=user_id,
                )
                # Rebuild the button preserving every action field.
                new_row.append(_tg.InlineKeyboardButton(
                    text=new_label,
                    url=getattr(btn, "url", None),
                    callback_data=getattr(btn, "callback_data", None),
                    web_app=getattr(btn, "web_app", None),
                    login_url=getattr(btn, "login_url", None),
                    switch_inline_query=getattr(btn, "switch_inline_query", None),
                    switch_inline_query_current_chat=getattr(
                        btn, "switch_inline_query_current_chat", None,
                    ),
                    switch_inline_query_chosen_chat=getattr(
                        btn, "switch_inline_query_chosen_chat", None,
                    ),
                    callback_game=getattr(btn, "callback_game", None),
                    pay=getattr(btn, "pay", None),
                    copy_text=getattr(btn, "copy_text", None),
                ))
            new_rows.append(new_row)
        return _tg.InlineKeyboardMarkup(new_rows)
    except Exception:
        return reply_markup


def _bot_target_user(chat_id):
    """For DMs, chat_id == user_id, so use it as the recipient hint."""
    try:
        if chat_id is not None and int(chat_id) > 0:
            return int(chat_id)
    except (TypeError, ValueError):
        pass
    return None


async def _maybe_translate_kwargs(kwargs, chat_id, user_id):
    """Translate caption / text / reply_markup buttons inside kwargs in-place.

    Every individual translation call is wrapped so that any failure leaves
    the original value intact — guaranteeing the underlying Telegram call
    still fires, so back / settings / help / cancel callbacks never break
    even if the live translator times out or rate-limits.
    """
    try:
        if "caption" in kwargs and isinstance(kwargs["caption"], str):
            kwargs["caption"] = await _maybe_translate_for_chat(
                chat_id, kwargs["caption"], user_id=user_id,
            )
    except Exception:
        pass
    try:
        if "text" in kwargs and isinstance(kwargs["text"], str):
            kwargs["text"] = await _maybe_translate_for_chat(
                chat_id, kwargs["text"], user_id=user_id,
            )
    except Exception:
        pass
    try:
        if "reply_markup" in kwargs and kwargs["reply_markup"] is not None:
            kwargs["reply_markup"] = await _translate_markup_for(
                kwargs["reply_markup"], chat_id, user_id,
            )
    except Exception:
        pass
    return kwargs


async def _safe_translate_text(chat_id, text, user_id):
    """Translate ``text`` defensively — original on any error."""
    if not isinstance(text, str):
        return text
    try:
        return await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    except Exception:
        return text


# --- Re-wrap reply_text / reply_html / reply_markdown / reply_markdown_v2
# so they also translate the reply_markup buttons (the previous patches only
# translated the text body).
_orig_reply_text_v1 = _tg.Message.reply_text
_orig_reply_html_v1 = _tg.Message.reply_html
_orig_reply_md_v1 = _tg.Message.reply_markdown
_orig_reply_md2_v1 = _tg.Message.reply_markdown_v2


async def _patched_msg_reply_text_v2(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    return await _orig_reply_text_v1(self, text, *args, **kwargs)


async def _patched_msg_reply_html_v2(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    return await _orig_reply_html_v1(self, text, *args, **kwargs)


async def _patched_msg_reply_md_v2(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    return await _orig_reply_md_v1(self, text, *args, **kwargs)


async def _patched_msg_reply_md2_v2(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    return await _orig_reply_md2_v1(self, text, *args, **kwargs)


_tg.Message.reply_text = _patched_msg_reply_text_v2
_tg.Message.reply_html = _patched_msg_reply_html_v2
_tg.Message.reply_markdown = _patched_msg_reply_md_v2
_tg.Message.reply_markdown_v2 = _patched_msg_reply_md2_v2


# --- Bot.send_message: also translate buttons.
_orig_bot_send_message_v1 = _tg.Bot.send_message


async def _patched_bot_send_message_v2(self, chat_id, text, *args, **kwargs):
    user_id = _bot_target_user(chat_id)
    if isinstance(text, str):
        text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    return await _orig_bot_send_message_v1(self, chat_id, text, *args, **kwargs)


_tg.Bot.send_message = _patched_bot_send_message_v2


# --- Message.edit_text: covers settings menu navigation, help cards, etc.
_orig_msg_edit_text = _tg.Message.edit_text


async def _patched_msg_edit_text(self, text, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    if isinstance(text, str):
        text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    try:
        return await _orig_msg_edit_text(self, text, *args, **kwargs)
    except BadRequest as e:
        # Telegram raises this when the requested text/markup is identical
        # to the current message. It is not a real failure.
        if "message is not modified" in str(e).lower():
            return self
        raise


_tg.Message.edit_text = _patched_msg_edit_text


# --- Message.edit_caption: media caption edits.
_orig_msg_edit_caption = _tg.Message.edit_caption


async def _patched_msg_edit_caption(self, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    if args and isinstance(args[0], str):
        # caption was passed positionally
        new_caption = await _maybe_translate_for_chat(
            chat_id, args[0], user_id=user_id,
        )
        args = (new_caption,) + args[1:]
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    return await _orig_msg_edit_caption(self, *args, **kwargs)


_tg.Message.edit_caption = _patched_msg_edit_caption


# --- Message.edit_reply_markup: just translate the buttons.
_orig_msg_edit_markup = _tg.Message.edit_reply_markup


async def _patched_msg_edit_markup(self, reply_markup=None, *args, **kwargs):
    chat_id, user_id = _msg_chat_user(self)
    reply_markup = await _translate_markup_for(reply_markup, chat_id, user_id)
    return await _orig_msg_edit_markup(self, reply_markup=reply_markup, *args, **kwargs)


_tg.Message.edit_reply_markup = _patched_msg_edit_markup


# --- Bot.edit_message_text / edit_message_caption / edit_message_reply_markup
_orig_bot_edit_text = _tg.Bot.edit_message_text


async def _patched_bot_edit_text(self, text=None, chat_id=None, message_id=None,
                                 inline_message_id=None, *args, **kwargs):
    user_id = _bot_target_user(chat_id)
    if isinstance(text, str):
        text = await _maybe_translate_for_chat(chat_id, text, user_id=user_id)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    try:
        return await _orig_bot_edit_text(
            self, text=text, chat_id=chat_id, message_id=message_id,
            inline_message_id=inline_message_id, *args, **kwargs,
        )
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            return None
        raise


_tg.Bot.edit_message_text = _patched_bot_edit_text


_orig_bot_edit_caption = _tg.Bot.edit_message_caption


async def _patched_bot_edit_caption(self, chat_id=None, message_id=None,
                                    inline_message_id=None, caption=None,
                                    *args, **kwargs):
    user_id = _bot_target_user(chat_id)
    if isinstance(caption, str):
        caption = await _maybe_translate_for_chat(chat_id, caption, user_id=user_id)
    kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
    try:
        return await _orig_bot_edit_caption(
            self, chat_id=chat_id, message_id=message_id,
            inline_message_id=inline_message_id, caption=caption,
            *args, **kwargs,
        )
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            return None
        raise


_tg.Bot.edit_message_caption = _patched_bot_edit_caption


_orig_bot_edit_markup = _tg.Bot.edit_message_reply_markup


async def _patched_bot_edit_markup(self, chat_id=None, message_id=None,
                                   inline_message_id=None, reply_markup=None,
                                   *args, **kwargs):
    user_id = _bot_target_user(chat_id)
    reply_markup = await _translate_markup_for(reply_markup, chat_id, user_id)
    return await _orig_bot_edit_markup(
        self, chat_id=chat_id, message_id=message_id,
        inline_message_id=inline_message_id, reply_markup=reply_markup,
        *args, **kwargs,
    )


_tg.Bot.edit_message_reply_markup = _patched_bot_edit_markup


# --- Media reply / send methods with caption + reply_markup.
def _make_caption_patch(orig):
    async def _patched(self, *args, **kwargs):
        chat_id, user_id = _msg_chat_user(self)
        kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
        return await orig(self, *args, **kwargs)
    return _patched


for _meth in (
    "reply_photo", "reply_video", "reply_audio", "reply_voice",
    "reply_animation", "reply_document", "reply_sticker",
    "reply_video_note", "reply_location", "reply_venue", "reply_contact",
    "reply_dice", "reply_poll", "reply_invoice",
):
    _orig = getattr(_tg.Message, _meth, None)
    if _orig is not None:
        setattr(_tg.Message, _meth, _make_caption_patch(_orig))


def _make_bot_send_patch(orig):
    async def _patched(self, chat_id, *args, **kwargs):
        user_id = _bot_target_user(chat_id)
        kwargs = await _maybe_translate_kwargs(kwargs, chat_id, user_id)
        return await orig(self, chat_id, *args, **kwargs)
    return _patched


for _meth in (
    "send_photo", "send_video", "send_audio", "send_voice",
    "send_animation", "send_document", "send_sticker",
    "send_video_note", "send_location", "send_venue", "send_contact",
    "send_dice", "send_poll", "send_invoice", "send_chat_action",
):
    _orig = getattr(_tg.Bot, _meth, None)
    if _orig is not None:
        setattr(_tg.Bot, _meth, _make_bot_send_patch(_orig))


# --- CallbackQuery.answer popup text.
_orig_cb_answer = _tg.CallbackQuery.answer


async def _patched_cb_answer(self, text=None, *args, **kwargs):
    try:
        user_id = getattr(getattr(self, "from_user", None), "id", None)
        chat_id = getattr(getattr(getattr(self, "message", None), "chat", None),
                          "id", None)
        if isinstance(text, str):
            text = await _maybe_translate_for_chat(
                chat_id, text, user_id=user_id,
            )
    except Exception:
        pass
    return await _orig_cb_answer(self, text=text, *args, **kwargs)


_tg.CallbackQuery.answer = _patched_cb_answer


# --- Bot.answer_callback_query (some code paths call it directly).
_orig_bot_answer_cb = getattr(_tg.Bot, "answer_callback_query", None)
if _orig_bot_answer_cb is not None:
    async def _patched_bot_answer_cb(self, callback_query_id, text=None,
                                     *args, **kwargs):
        # We cannot resolve the user from id alone — use the ContextVar.
        try:
            user_id = _current_trigger_user.get()
        except Exception:
            user_id = None
        if isinstance(text, str) and user_id:
            text = await _maybe_translate_for_chat(None, text, user_id=user_id)
        return await _orig_bot_answer_cb(
            self, callback_query_id, text=text, *args, **kwargs,
        )
    _tg.Bot.answer_callback_query = _patched_bot_answer_cb


# ----------------------------------------------------------------------
# Common admin / target helpers shared by the new commands.
# ----------------------------------------------------------------------
async def _is_chat_admin(chat_id: int, user_id: int, bot) -> bool:
    """Return True if ``user_id`` is admin/owner in ``chat_id``.

    Delegates to the legacy ``is_admin`` so the same rules apply (BOT_OWNER_ID
    is always treated as admin, statuses checked via Telegram).
    """
    try:
        return await is_admin(bot, chat_id, user_id)
    except TelegramError:
        return False


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Reply with ``not_admin`` text and return False if user isn't an admin."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return False
    if chat.type == "private":
        return True
    if not await _is_chat_admin(chat.id, user.id, context.bot):
        await update.effective_message.reply_text(
            await tr(chat.id, "not_admin"),
        )
        return False
    return True


def _user_link(u: User) -> str:
    """Return an HTML mention for a user."""
    name = (u.first_name or "user").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={u.id}">{name}</a>'


def _format_duration(seconds: int) -> str:
    """Return a short human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    mins, sec = divmod(seconds, 60)
    if mins < 60:
        return f"{mins}m {sec}s" if sec else f"{mins}m"
    hours, mins = divmod(mins, 60)
    if hours < 24:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h" if hours else f"{days}d"


def _parse_duration(text: str) -> Optional[int]:
    """Parse strings like ``10m``, ``2h``, ``1d`` into seconds."""
    if not text:
        return None
    s = text.strip().lower()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    if s[-1] in units and s[:-1].isdigit():
        return int(s[:-1]) * units[s[-1]]
    if s.isdigit():
        return int(s) * 60  # bare number = minutes
    return None


# ----------------------------------------------------------------------
# Notes / Saved messages module.
# ----------------------------------------------------------------------
NOTE_TYPES = {
    "text": "text", "photo": "photo", "video": "video", "audio": "audio",
    "voice": "voice", "document": "document", "sticker": "sticker",
    "animation": "animation", "video_note": "video_note",
}


def _extract_note_payload(msg) -> tuple[str, str, str]:
    """Inspect a message and return ``(content, file_id, file_type)``."""
    text = (msg.text or msg.caption or "").strip()
    if msg.photo:
        return text, msg.photo[-1].file_id, "photo"
    if msg.video:
        return text, msg.video.file_id, "video"
    if msg.audio:
        return text, msg.audio.file_id, "audio"
    if msg.voice:
        return text, msg.voice.file_id, "voice"
    if msg.document:
        return text, msg.document.file_id, "document"
    if msg.sticker:
        return text, msg.sticker.file_id, "sticker"
    if msg.animation:
        return text, msg.animation.file_id, "animation"
    if msg.video_note:
        return text, msg.video_note.file_id, "video_note"
    return text, "", ""


async def _resolve_chat_for_pm(update: Update) -> Optional[int]:
    """If a PM-only command, look up the connected group via /connect."""
    chat = update.effective_chat
    if chat and chat.type != "private":
        return chat.id
    if update.effective_user is None:
        return None
    db = await _get_db()
    async with db.execute(
        "SELECT chat_id FROM pm_connections WHERE user_id = ?",
        (update.effective_user.id,),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else None


async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save a note: ``/save <name> <content>`` or reply to a message + name."""
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        await msg.reply_text("Please run this in a group, or /connect first.")
        return
    args = context.args or []
    if not args:
        await msg.reply_text("Usage: /save <name> <text>  (or reply to media)")
        return
    name = args[0].lower().lstrip("#")
    rest = " ".join(args[1:])
    if msg.reply_to_message:
        text, file_id, file_type = _extract_note_payload(msg.reply_to_message)
        if rest:
            text = rest  # explicit text overrides caption
    else:
        text, file_id, file_type = rest, "", ""
    if not text and not file_id:
        await msg.reply_text("Note ke liye content ya media chahiye.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO notes(chat_id, name, content, file_id, file_type, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (chat_id, name, text, file_id, file_type, update.effective_user.id, int(time.time())),
    )
    await db.commit()
    await msg.reply_text(_t(await _chat_lang(chat_id), "note_saved", name=name))


async def cmd_get(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recall a saved note: ``/get <name>``."""
    msg = update.effective_message
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await msg.reply_text("Usage: /get <name>")
        return
    name = args[0].lower().lstrip("#")
    await _send_note(context.bot, chat_id, name, reply_to=msg.message_id)


async def _send_note(bot, chat_id: int, name: str, reply_to: Optional[int] = None) -> None:
    """Resolve a note row and send it back to the chat."""
    # Saved notes are admin-authored — bypass the live translator.
    try:
        _skip_translate.set(True)
    except Exception:
        pass
    db = await _get_db()
    async with db.execute(
        "SELECT content, file_id, file_type FROM notes WHERE chat_id = ? AND name = ?",
        (chat_id, name),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        try:
            await bot.send_message(
                chat_id,
                _t(await _chat_lang(chat_id), "note_missing", name=name),
                reply_to_message_id=reply_to,
            )
        except TelegramError:
            pass
        return
    content, file_id, file_type = row
    kwargs = {"reply_to_message_id": reply_to} if reply_to else {}
    try:
        if file_type == "photo":
            await bot.send_photo(chat_id, file_id, caption=content or None, **kwargs)
        elif file_type == "video":
            await bot.send_video(chat_id, file_id, caption=content or None, **kwargs)
        elif file_type == "audio":
            await bot.send_audio(chat_id, file_id, caption=content or None, **kwargs)
        elif file_type == "voice":
            await bot.send_voice(chat_id, file_id, caption=content or None, **kwargs)
        elif file_type == "document":
            await bot.send_document(chat_id, file_id, caption=content or None, **kwargs)
        elif file_type == "sticker":
            await bot.send_sticker(chat_id, file_id, **kwargs)
        elif file_type == "animation":
            await bot.send_animation(chat_id, file_id, caption=content or None, **kwargs)
        elif file_type == "video_note":
            await bot.send_video_note(chat_id, file_id, **kwargs)
        else:
            await bot.send_message(chat_id, content or "(empty note)", **kwargs)
    except TelegramError:
        await bot.send_message(chat_id, content or "(unable to send note)", **kwargs)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a saved note: ``/clear <name>``."""
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await msg.reply_text("Usage: /clear <name>")
        return
    name = args[0].lower().lstrip("#")
    db = await _get_db()
    await db.execute(
        "DELETE FROM notes WHERE chat_id = ? AND name = ?",
        (chat_id, name),
    )
    await db.commit()
    await msg.reply_text(_t(await _chat_lang(chat_id), "note_cleared", name=name))


async def cmd_clearall_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wipe every note for the current chat (owner only)."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    await db.execute("DELETE FROM notes WHERE chat_id = ?", (chat_id,))
    await db.commit()
    await update.effective_message.reply_text("Saare notes hata diye gaye.")


async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List every saved note for the chat."""
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    async with db.execute(
        "SELECT name FROM notes WHERE chat_id = ? ORDER BY name",
        (chat_id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Is chat ke liye koi notes nahi hain.")
        return
    text = "Notes in this chat:\n" + "\n".join(f"• #{r[0]}" for r in rows)
    await update.effective_message.reply_text(text)


async def hashtag_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow ``#notename`` shortcut to recall notes inside group messages."""
    msg = update.effective_message
    if not msg or not msg.text or not msg.text.startswith("#"):
        return
    name = msg.text.split()[0][1:].lower()
    if not name:
        return
    chat_id = msg.chat.id
    db = await _get_db()
    async with db.execute(
        "SELECT 1 FROM notes WHERE chat_id = ? AND name = ?",
        (chat_id, name),
    ) as cur:
        row = await cur.fetchone()
    if row:
        await _send_note(context.bot, chat_id, name, reply_to=msg.message_id)


# ----------------------------------------------------------------------
# Filters module: reply when a keyword appears in chat.
# ----------------------------------------------------------------------
async def cmd_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a keyword auto-reply: ``/filter <keyword> <reply>`` or reply."""
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await msg.reply_text("Usage: /filter <keyword> <reply>  (or reply to media)")
        return
    kw = args[0].lower()
    rest = " ".join(args[1:])
    if msg.reply_to_message:
        text, file_id, file_type = _extract_note_payload(msg.reply_to_message)
        if rest:
            text = rest
    else:
        text, file_id, file_type = rest, "", ""
    if not text and not file_id:
        await msg.reply_text("Filter ke liye content ya media chahiye.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO filters(chat_id, keyword, reply, file_id, file_type, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (chat_id, kw, text, file_id, file_type, update.effective_user.id, int(time.time())),
    )
    await db.commit()
    await msg.reply_text(_t(await _chat_lang(chat_id), "filter_saved", kw=kw))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a single filter: ``/stop <keyword>``."""
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await msg.reply_text("Usage: /stop <keyword>")
        return
    kw = args[0].lower()
    db = await _get_db()
    await db.execute(
        "DELETE FROM filters WHERE chat_id = ? AND keyword = ?",
        (chat_id, kw),
    )
    await db.commit()
    await msg.reply_text(_t(await _chat_lang(chat_id), "filter_cleared", kw=kw))


async def cmd_stopall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove every filter for the chat."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    await db.execute("DELETE FROM filters WHERE chat_id = ?", (chat_id,))
    await db.commit()
    await update.effective_message.reply_text("Saare filters hata diye gaye.")


async def cmd_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List configured filters."""
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    async with db.execute(
        "SELECT keyword FROM filters WHERE chat_id = ? ORDER BY keyword",
        (chat_id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text(
            _t(await _chat_lang(chat_id), "filters_empty"),
        )
        return
    text = "Filters in this chat:\n" + "\n".join(f"• {r[0]}" for r in rows)
    await update.effective_message.reply_text(text)


async def filters_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inspect group messages for any active filter trigger and reply."""
    msg = update.effective_message
    if not msg or not msg.chat or msg.chat.type == "private":
        return
    # Filter replies are admin-authored — bypass the live translator.
    try:
        _skip_translate.set(True)
    except Exception:
        pass
    text = (msg.text or msg.caption or "").lower()
    if not text:
        return
    db = await _get_db()
    async with db.execute(
        "SELECT keyword, reply, file_id, file_type FROM filters WHERE chat_id = ?",
        (msg.chat.id,),
    ) as cur:
        rows = await cur.fetchall()
    for kw, reply, file_id, file_type in rows:
        # whole-word style match (start of word boundary).
        if re.search(rf"\b{re.escape(kw)}\b", text):
            try:
                if file_id:
                    await _send_filter_media(context.bot, msg.chat.id, reply, file_id, file_type, msg.message_id)
                else:
                    await msg.reply_text(reply)
            except TelegramError:
                pass
            break


async def _send_filter_media(bot, chat_id: int, caption: str, file_id: str, file_type: str, reply_to: int) -> None:
    """Helper used by the filter pipeline to send rich responses."""
    kwargs = {"reply_to_message_id": reply_to}
    if file_type == "photo":
        await bot.send_photo(chat_id, file_id, caption=caption or None, **kwargs)
    elif file_type == "video":
        await bot.send_video(chat_id, file_id, caption=caption or None, **kwargs)
    elif file_type == "audio":
        await bot.send_audio(chat_id, file_id, caption=caption or None, **kwargs)
    elif file_type == "voice":
        await bot.send_voice(chat_id, file_id, caption=caption or None, **kwargs)
    elif file_type == "document":
        await bot.send_document(chat_id, file_id, caption=caption or None, **kwargs)
    elif file_type == "sticker":
        await bot.send_sticker(chat_id, file_id, **kwargs)
    elif file_type == "animation":
        await bot.send_animation(chat_id, file_id, caption=caption or None, **kwargs)
    else:
        await bot.send_message(chat_id, caption or "(filter)", **kwargs)


# ----------------------------------------------------------------------
# Locks module: per-chat lock toggles (mapped to permissions / pipeline).
# ----------------------------------------------------------------------
LOCK_TYPES = [
    "all", "messages", "media", "photo", "video", "gif", "sticker",
    "audio", "voice", "document", "videonote", "poll", "game", "inline",
    "url", "forward", "mention", "phone", "command", "email",
    "rtl", "anonchannel", "premiumstickers", "spoiler", "bot", "comment",
]


async def cmd_locktypes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show every supported lock type."""
    text = "Available lock types:\n" + ", ".join(f"`{t}`" for t in LOCK_TYPES)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lock one or more types: ``/lock photo url forward``."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /lock <type> [type...]")
        return
    db = await _get_db()
    saved = []
    unknown = []
    for t in args:
        t = t.lower().strip()
        if t not in LOCK_TYPES:
            unknown.append(t)
            continue
        await db.execute(
            "INSERT OR REPLACE INTO locks(chat_id, lock_type, locked) VALUES (?,?,1)",
            (chat_id, t),
        )
        saved.append(t)
    await db.commit()
    parts = []
    if saved:
        parts.append("Locked: " + ", ".join(saved))
    if unknown:
        parts.append("Unknown: " + ", ".join(unknown))
    await update.effective_message.reply_text(
        " | ".join(parts) or _t(await _chat_lang(chat_id), "lock_unknown"),
    )


async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unlock previously locked types."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /unlock <type> [type...]")
        return
    db = await _get_db()
    cleared = []
    for t in args:
        t = t.lower().strip()
        if t not in LOCK_TYPES:
            continue
        await db.execute(
            "INSERT OR REPLACE INTO locks(chat_id, lock_type, locked) VALUES (?,?,0)",
            (chat_id, t),
        )
        cleared.append(t)
    await db.commit()
    await update.effective_message.reply_text(
        "Unlocked: " + ", ".join(cleared) if cleared else _t(await _chat_lang(chat_id), "lock_unknown"),
    )


async def cmd_locks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current lock state for the chat."""
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    async with db.execute(
        "SELECT lock_type, locked FROM locks WHERE chat_id = ?",
        (chat_id,),
    ) as cur:
        rows = {r[0]: r[1] for r in await cur.fetchall()}
    lines = ["Lock state in this chat:"]
    for t in LOCK_TYPES:
        flag = "🔒" if rows.get(t) else "🔓"
        lines.append(f"{flag} {t}")
    await update.effective_message.reply_text("\n".join(lines))


def _msg_matches_lock(msg, lock_type: str) -> bool:
    """Return True if ``msg`` is the kind of content blocked by ``lock_type``."""
    if lock_type == "all":
        return True
    if lock_type == "messages":
        return bool(msg.text and not msg.text.startswith("/"))
    if lock_type == "media":
        return bool(msg.photo or msg.video or msg.audio or msg.voice or msg.document or msg.animation or msg.sticker)
    if lock_type == "photo":
        return bool(msg.photo)
    if lock_type == "video":
        return bool(msg.video)
    if lock_type == "gif":
        return bool(msg.animation)
    if lock_type == "sticker":
        return bool(msg.sticker)
    if lock_type == "audio":
        return bool(msg.audio)
    if lock_type == "voice":
        return bool(msg.voice)
    if lock_type == "document":
        return bool(msg.document)
    if lock_type == "videonote":
        return bool(msg.video_note)
    if lock_type == "poll":
        return bool(msg.poll)
    if lock_type == "game":
        return bool(msg.game)
    if lock_type == "inline":
        return bool(msg.via_bot)
    if lock_type == "forward":
        return bool(msg.forward_origin)
    if lock_type == "url":
        text = (msg.text or msg.caption or "")
        return bool(re.search(r"https?://|t\.me/|telegram\.me/", text))
    if lock_type == "mention":
        text = (msg.text or msg.caption or "")
        return bool(re.search(r"@[A-Za-z0-9_]{4,}", text))
    if lock_type == "phone":
        text = (msg.text or msg.caption or "")
        return bool(re.search(r"\+?\d[\d\-\s]{7,}\d", text))
    if lock_type == "command":
        return bool(msg.text and msg.text.startswith("/"))
    if lock_type == "email":
        text = (msg.text or msg.caption or "")
        return bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
    if lock_type == "rtl":
        text = (msg.text or msg.caption or "")
        return bool(re.search(r"[\u0600-\u06FF\u0590-\u05FF]", text))
    if lock_type == "anonchannel":
        return bool(msg.sender_chat and msg.sender_chat.id != msg.chat.id)
    if lock_type == "premiumstickers":
        return bool(msg.sticker and getattr(msg.sticker, "premium_animation", None))
    if lock_type == "spoiler":
        ents = list(msg.entities or []) + list(msg.caption_entities or [])
        return any(e.type == "spoiler" for e in ents)
    if lock_type == "bot":
        return bool(msg.from_user and msg.from_user.is_bot)
    if lock_type == "comment":
        return bool(msg.is_topic_message and msg.message_thread_id)
    return False


async def locks_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete messages matching active locks. Skips admins."""
    msg = update.effective_message
    if not msg or msg.chat.type == "private":
        return
    if msg.from_user and await _is_chat_admin(msg.chat.id, msg.from_user.id, context.bot):
        return
    db = await _get_db()
    async with db.execute(
        "SELECT lock_type FROM locks WHERE chat_id = ? AND locked = 1",
        (msg.chat.id,),
    ) as cur:
        active = [r[0] for r in await cur.fetchall()]
    for lt in active:
        if _msg_matches_lock(msg, lt):
            try:
                await msg.delete()
            except TelegramError:
                pass
            return


# ----------------------------------------------------------------------
# Disable / Enable commands per-chat.
# ----------------------------------------------------------------------
DISABLEABLE = {
    "warn", "mute", "unmute", "ban", "kick", "tban", "tmute", "info",
    "id", "rules", "stats", "help", "report", "admins", "staff",
    "notes", "get", "filters", "lock", "unlock", "locks", "afk",
    "save", "clear", "filter", "stop", "ud", "weather", "translate",
    "calc", "qr", "shorten", "dice", "coin", "8ball", "pick", "reverse",
}


async def cmd_disable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable a command in this chat."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /disable <command>")
        return
    cmd = args[0].lower().lstrip("/")
    if cmd not in DISABLEABLE:
        await update.effective_message.reply_text("Yeh command disable nahi ki ja sakti.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO disabled_cmds(chat_id, cmd, deletes) VALUES (?,?,1)",
        (chat_id, cmd),
    )
    await db.commit()
    await update.effective_message.reply_text(_t(await _chat_lang(chat_id), "disabled_set", cmd=cmd))


async def cmd_enable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Re-enable a previously disabled command."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /enable <command>")
        return
    cmd = args[0].lower().lstrip("/")
    db = await _get_db()
    await db.execute(
        "DELETE FROM disabled_cmds WHERE chat_id = ? AND cmd = ?",
        (chat_id, cmd),
    )
    await db.commit()
    await update.effective_message.reply_text(_t(await _chat_lang(chat_id), "enabled_set", cmd=cmd))


async def cmd_disableable(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List every command that can be toggled with /disable."""
    text = "Disable-able commands:\n" + ", ".join(sorted(DISABLEABLE))
    await update.effective_message.reply_text(text)


async def cmd_disabled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show which commands are currently disabled."""
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    async with db.execute(
        "SELECT cmd FROM disabled_cmds WHERE chat_id = ?",
        (chat_id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Koi command disabled nahi hai.")
        return
    text = "Disabled commands:\n" + ", ".join(r[0] for r in rows)
    await update.effective_message.reply_text(text)


async def disabled_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete disabled command messages from non-admins before they run."""
    msg = update.effective_message
    if not msg or not msg.text or not msg.text.startswith("/") or msg.chat.type == "private":
        return
    cmd = msg.text.split()[0].lstrip("/").split("@")[0].lower()
    if cmd not in DISABLEABLE:
        return
    if msg.from_user and await _is_chat_admin(msg.chat.id, msg.from_user.id, context.bot):
        return
    db = await _get_db()
    async with db.execute(
        "SELECT 1 FROM disabled_cmds WHERE chat_id = ? AND cmd = ?",
        (msg.chat.id, cmd),
    ) as cur:
        row = await cur.fetchone()
    if row:
        try:
            await msg.delete()
        except TelegramError:
            pass


# ----------------------------------------------------------------------
# Federation module: cross-group ban list.
# ----------------------------------------------------------------------
def _new_fed_id() -> str:
    """Random 12-char federation id."""
    return uuid.uuid4().hex[:12]


async def cmd_newfed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a federation: ``/newfed <name>`` (PM only)."""
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text("Federation banane ke liye PM use kare.")
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /newfed <name>")
        return
    name = " ".join(args)
    fid = _new_fed_id()
    db = await _get_db()
    await db.execute(
        "INSERT INTO federations(fed_id, name, owner_id, created_at) VALUES (?,?,?,?)",
        (fid, name, update.effective_user.id, int(time.time())),
    )
    await db.execute(
        "INSERT OR REPLACE INTO fed_admins(fed_id, user_id) VALUES (?,?)",
        (fid, update.effective_user.id),
    )
    await db.commit()
    await update.effective_message.reply_text(
        f"Federation '{name}' created.\nID: <code>{fid}</code>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_delfed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a federation you own."""
    if update.effective_chat.type != "private":
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /delfed <fed_id>")
        return
    fid = args[0]
    db = await _get_db()
    async with db.execute(
        "SELECT owner_id FROM federations WHERE fed_id = ?", (fid,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        await update.effective_message.reply_text("Federation not found.")
        return
    if row[0] != update.effective_user.id:
        await update.effective_message.reply_text("Sirf federation owner delete kar sakta hai.")
        return
    await db.execute("DELETE FROM federations WHERE fed_id = ?", (fid,))
    await db.execute("DELETE FROM fed_members WHERE fed_id = ?", (fid,))
    await db.execute("DELETE FROM fed_admins WHERE fed_id = ?", (fid,))
    await db.execute("DELETE FROM fed_bans WHERE fed_id = ?", (fid,))
    await db.commit()
    await update.effective_message.reply_text("Federation removed.")


async def cmd_joinfed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add the current chat to a federation: ``/joinfed <fed_id>``."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.effective_message.reply_text("Group ke andar use karen.")
        return
    if not await _require_admin(update, context):
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /joinfed <fed_id>")
        return
    fid = args[0]
    db = await _get_db()
    async with db.execute("SELECT 1 FROM federations WHERE fed_id = ?", (fid,)) as cur:
        if not await cur.fetchone():
            await update.effective_message.reply_text("Federation nahi mili.")
            return
    await db.execute(
        "INSERT OR REPLACE INTO fed_members(fed_id, chat_id, joined_at) VALUES (?,?,?)",
        (fid, chat.id, int(time.time())),
    )
    await db.commit()
    await update.effective_message.reply_text(f"Joined federation `{fid}`.", parse_mode=ParseMode.MARKDOWN)


async def cmd_leavefed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove the current chat from any federation."""
    chat = update.effective_chat
    if chat.type == "private":
        return
    if not await _require_admin(update, context):
        return
    db = await _get_db()
    await db.execute("DELETE FROM fed_members WHERE chat_id = ?", (chat.id,))
    await db.commit()
    await update.effective_message.reply_text("Chat federation se exit ho gaya.")


async def _chat_fed_id(chat_id: int) -> Optional[str]:
    db = await _get_db()
    async with db.execute(
        "SELECT fed_id FROM fed_members WHERE chat_id = ?", (chat_id,),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else None


async def cmd_fban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user across every chat in this group's federation."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.effective_message.reply_text("Group me se chalao.")
        return
    if not await _require_admin(update, context):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await update.effective_message.reply_text(await tr(chat.id, "no_target"))
        return
    fid = await _chat_fed_id(chat.id)
    if not fid:
        await update.effective_message.reply_text("Yeh chat kisi federation me nahi hai.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO fed_bans(fed_id, user_id, reason, by_user, banned_at) "
        "VALUES (?,?,?,?,?)",
        (fid, target.id, reason, update.effective_user.id, int(time.time())),
    )
    await db.commit()
    async with db.execute(
        "SELECT chat_id FROM fed_members WHERE fed_id = ?", (fid,),
    ) as cur:
        chats = [r[0] for r in await cur.fetchall()]
    n = 0
    for cid in chats:
        try:
            await context.bot.ban_chat_member(cid, target.id)
            n += 1
        except TelegramError:
            continue
    await update.effective_message.reply_text(
        await tr(chat.id, "fed_banned", user=_user_link(target), n=n, reason=reason or "—"),
        parse_mode=ParseMode.HTML,
    )


async def cmd_unfban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lift a federation ban."""
    chat = update.effective_chat
    if chat.type == "private":
        return
    if not await _require_admin(update, context):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        await update.effective_message.reply_text(await tr(chat.id, "no_target"))
        return
    fid = await _chat_fed_id(chat.id)
    if not fid:
        return
    db = await _get_db()
    await db.execute(
        "DELETE FROM fed_bans WHERE fed_id = ? AND user_id = ?",
        (fid, target.id),
    )
    await db.commit()
    async with db.execute(
        "SELECT chat_id FROM fed_members WHERE fed_id = ?", (fid,),
    ) as cur:
        chats = [r[0] for r in await cur.fetchall()]
    for cid in chats:
        try:
            await context.bot.unban_chat_member(cid, target.id)
        except TelegramError:
            continue
    await update.effective_message.reply_text(
        await tr(chat.id, "fed_unbanned", user=_user_link(target)),
        parse_mode=ParseMode.HTML,
    )


async def cmd_fedinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show details about the chat's federation (or one by id in PM)."""
    chat = update.effective_chat
    args = context.args or []
    fid = args[0] if args else await _chat_fed_id(chat.id)
    if not fid:
        await update.effective_message.reply_text("Federation id chahiye, ya group me run kare.")
        return
    db = await _get_db()
    async with db.execute(
        "SELECT name, owner_id, created_at FROM federations WHERE fed_id = ?", (fid,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        await update.effective_message.reply_text("Federation not found.")
        return
    name, owner, created = row
    async with db.execute(
        "SELECT COUNT(*) FROM fed_members WHERE fed_id = ?", (fid,),
    ) as cur:
        members = (await cur.fetchone())[0]
    async with db.execute(
        "SELECT COUNT(*) FROM fed_bans WHERE fed_id = ?", (fid,),
    ) as cur:
        bans = (await cur.fetchone())[0]
    text = (
        f"<b>Federation:</b> {name}\n"
        f"<b>ID:</b> <code>{fid}</code>\n"
        f"<b>Owner:</b> <code>{owner}</code>\n"
        f"<b>Chats:</b> {members}\n"
        f"<b>Bans:</b> {bans}\n"
        f"<b>Created:</b> {time.strftime('%Y-%m-%d', time.gmtime(created))}"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_fedbanlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the first 50 fed-banned users for the chat's federation."""
    chat = update.effective_chat
    fid = await _chat_fed_id(chat.id)
    if not fid:
        await update.effective_message.reply_text("Chat kisi federation me nahi hai.")
        return
    db = await _get_db()
    async with db.execute(
        "SELECT user_id, reason FROM fed_bans WHERE fed_id = ? LIMIT 50", (fid,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Federation ban list khali hai.")
        return
    text = "Federation bans:\n" + "\n".join(
        f"• <code>{u}</code>" + (f" — {r}" if r else "") for u, r in rows
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def fed_join_enforcer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-ban fed-banned users who try to join a member chat."""
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    fid = await _chat_fed_id(msg.chat.id)
    if not fid:
        return
    db = await _get_db()
    for m in msg.new_chat_members:
        async with db.execute(
            "SELECT reason FROM fed_bans WHERE fed_id = ? AND user_id = ?",
            (fid, m.id),
        ) as cur:
            row = await cur.fetchone()
        if row:
            try:
                await context.bot.ban_chat_member(msg.chat.id, m.id)
                await msg.reply_text(
                    f"{_user_link(m)} federation-banned — auto removed.",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass


# ----------------------------------------------------------------------
# PM <-> Group connection module.
# ----------------------------------------------------------------------
async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Connect a group to your PM so you can run admin commands from PM."""
    user = update.effective_user
    chat = update.effective_chat
    args = context.args or []
    target_chat_id: Optional[int] = None
    if chat and chat.type != "private":
        target_chat_id = chat.id
    elif args and args[0].lstrip("-").isdigit():
        target_chat_id = int(args[0])
    if target_chat_id is None:
        await update.effective_message.reply_text("Group me /connect chalao, ya PM me /connect <chat_id>.")
        return
    if not await _is_chat_admin(target_chat_id, user.id, context.bot):
        await update.effective_message.reply_text("Aap us group me admin nahi hain.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO pm_connections(user_id, chat_id, connected_at) VALUES (?,?,?)",
        (user.id, target_chat_id, int(time.time())),
    )
    await db.commit()
    title = "this chat"
    try:
        ch = await context.bot.get_chat(target_chat_id)
        title = ch.title or title
    except TelegramError:
        pass
    await update.effective_message.reply_text(_t(await _chat_lang(target_chat_id), "connect_ok", title=title))


async def cmd_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disconnect a previous PM<->group link."""
    user = update.effective_user
    db = await _get_db()
    await db.execute("DELETE FROM pm_connections WHERE user_id = ?", (user.id,))
    await db.commit()
    await update.effective_message.reply_text(_t("en", "connect_off"))


async def cmd_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show which group your PM is currently connected to."""
    user = update.effective_user
    db = await _get_db()
    async with db.execute(
        "SELECT chat_id, connected_at FROM pm_connections WHERE user_id = ?", (user.id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        await update.effective_message.reply_text(_t("en", "connect_none"))
        return
    cid, when = row
    title = str(cid)
    try:
        ch = await context.bot.get_chat(cid)
        title = ch.title or title
    except TelegramError:
        pass
    await update.effective_message.reply_text(
        f"Connected to <b>{title}</b> (<code>{cid}</code>) since "
        f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(when))}.",
        parse_mode=ParseMode.HTML,
    )


# ----------------------------------------------------------------------
# Global ban / mute (sudo-only).
# ----------------------------------------------------------------------
async def _is_sudo(user_id: int) -> bool:
    """Return True if the user is in ``sudo_users`` (or owner via env)."""
    owner = os.environ.get("BOT_OWNER_ID")
    if owner and owner.isdigit() and int(owner) == user_id:
        return True
    db = await _get_db()
    async with db.execute(
        "SELECT 1 FROM sudo_users WHERE user_id = ?", (user_id,),
    ) as cur:
        return bool(await cur.fetchone())


async def cmd_addsudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: add a sudo user."""
    user = update.effective_user
    owner = os.environ.get("BOT_OWNER_ID")
    if not owner or not owner.isdigit() or int(owner) != user.id:
        await update.effective_message.reply_text("Sirf bot owner add kar sakta hai.")
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        await update.effective_message.reply_text("Reply ya user-id de.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO sudo_users(user_id, added_by, added_at) VALUES (?,?,?)",
        (target.id, user.id, int(time.time())),
    )
    await db.commit()
    await update.effective_message.reply_text(f"Added sudo: {target.id}")


async def cmd_delsudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only: remove a sudo user."""
    user = update.effective_user
    owner = os.environ.get("BOT_OWNER_ID")
    if not owner or not owner.isdigit() or int(owner) != user.id:
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        return
    db = await _get_db()
    await db.execute("DELETE FROM sudo_users WHERE user_id = ?", (target.id,))
    await db.commit()
    await update.effective_message.reply_text(f"Removed sudo: {target.id}")


async def cmd_sudolist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List sudo users."""
    db = await _get_db()
    async with db.execute("SELECT user_id FROM sudo_users") as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("No sudo users configured.")
        return
    await update.effective_message.reply_text(
        "Sudo users:\n" + "\n".join(f"• <code>{r[0]}</code>" for r in rows),
        parse_mode=ParseMode.HTML,
    )


async def cmd_gban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sudo-only: globally ban a user."""
    if not await _is_sudo(update.effective_user.id):
        return
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await update.effective_message.reply_text("Reply / @user / id chahiye.")
        return
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO gbans(user_id, reason, by_user, banned_at) VALUES (?,?,?,?)",
        (target.id, reason, update.effective_user.id, int(time.time())),
    )
    await db.commit()
    # ban from current chat right away
    chat = update.effective_chat
    if chat and chat.type != "private":
        try:
            await context.bot.ban_chat_member(chat.id, target.id)
        except TelegramError:
            pass
    await update.effective_message.reply_text(
        await tr(chat.id if chat else 0, "gban_ok", user=_user_link(target)),
        parse_mode=ParseMode.HTML,
    )


async def cmd_ungban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sudo-only: lift a global ban."""
    if not await _is_sudo(update.effective_user.id):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        return
    db = await _get_db()
    await db.execute("DELETE FROM gbans WHERE user_id = ?", (target.id,))
    await db.commit()
    await update.effective_message.reply_text(
        await tr(update.effective_chat.id if update.effective_chat else 0, "ungban_ok", user=_user_link(target)),
        parse_mode=ParseMode.HTML,
    )


async def cmd_gbanlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show first 50 globally banned users (sudo only)."""
    if not await _is_sudo(update.effective_user.id):
        return
    db = await _get_db()
    async with db.execute("SELECT user_id, reason FROM gbans LIMIT 50") as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Global ban list khali hai.")
        return
    text = "Global bans:\n" + "\n".join(
        f"• <code>{u}</code>" + (f" — {r}" if r else "") for u, r in rows
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def gban_join_enforcer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-ban globally banned users on join."""
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    db = await _get_db()
    for m in msg.new_chat_members:
        async with db.execute("SELECT reason FROM gbans WHERE user_id = ?", (m.id,)) as cur:
            row = await cur.fetchone()
        if row:
            try:
                await context.bot.ban_chat_member(msg.chat.id, m.id)
                await msg.reply_text(
                    f"{_user_link(m)} globally banned — auto removed.",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass


# ----------------------------------------------------------------------
# Mass / silent action commands.
# ----------------------------------------------------------------------
async def cmd_sban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silent ban — no reply, deletes original message."""
    if not await _require_admin(update, context):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        return
    chat = update.effective_chat
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
    except TelegramError:
        pass
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def cmd_skick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silent kick (ban + unban)."""
    if not await _require_admin(update, context):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        return
    chat = update.effective_chat
    try:
        await context.bot.ban_chat_member(chat.id, target.id)
        await context.bot.unban_chat_member(chat.id, target.id)
    except TelegramError:
        pass
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def cmd_smute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silent mute (no reply text, deletes the command)."""
    if not await _require_admin(update, context):
        return
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        return
    chat = update.effective_chat
    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
        )
    except TelegramError:
        pass
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def cmd_dwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the replied message (if any) and warn the user.

    Also accepts ``/dwarn @username [reason]`` or ``/dwarn <user_id> [reason]``
    — in that case there's no message to delete, so it just warns.
    """
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    # If invoked as a reply, delete the offending message first.
    if msg.reply_to_message:
        try:
            await msg.reply_to_message.delete()
        except TelegramError:
            pass
        await cmd_warn(update, context)
        return
    # No reply — make sure we at least have a target via @username / user_id.
    target = await _resolve_target(update, context)
    if target is None:
        await msg.reply_text(
            "Reply to a user, or pass @username / user_id. "
            "Usage: /dwarn <reply | @user | id> [reason]"
        )
        return
    await cmd_warn(update, context)


async def cmd_kickme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Self-kick: user removes themselves from the group."""
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        return
    try:
        await context.bot.ban_chat_member(chat.id, user.id)
        await context.bot.unban_chat_member(chat.id, user.id)
        await update.effective_message.reply_text(f"Bye {_user_link(user)}!", parse_mode=ParseMode.HTML)
    except TelegramError:
        await update.effective_message.reply_text("Mujhe permission nahi hai.")


async def cmd_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Make the bot leave the chat (admin only)."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    await update.effective_message.reply_text("Bye! Bot leaving the chat.")
    try:
        await context.bot.leave_chat(chat.id)
    except TelegramError:
        pass


async def cmd_listadmins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick admin list for the current chat."""
    chat = update.effective_chat
    if chat.type == "private":
        return
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except TelegramError:
        await update.effective_message.reply_text("Admin list nahi le saka.")
        return
    lines = []
    for a in admins:
        u = a.user
        tag = "👑" if a.status == "creator" else "🛡"
        lines.append(f"{tag} {_user_link(u)}")
    await update.effective_message.reply_text(
        "<b>Admins:</b>\n" + "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# ----------------------------------------------------------------------
# AFK module.
# ----------------------------------------------------------------------
async def cmd_afk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark yourself as AFK with an optional reason."""
    user = update.effective_user
    reason = " ".join(context.args or []) or "—"
    db = await _get_db()
    await db.execute(
        "INSERT OR REPLACE INTO afk_users(user_id, reason, since) VALUES (?,?,?)",
        (user.id, reason, int(time.time())),
    )
    await db.commit()
    await update.effective_message.reply_text(
        await tr(update.effective_chat.id if update.effective_chat else 0, "afk_on",
                 user=_user_link(user), reason=reason),
        parse_mode=ParseMode.HTML,
    )


async def afk_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify chat when an AFK user returns or is mentioned."""
    msg = update.effective_message
    if not msg or msg.chat.type == "private":
        return
    db = await _get_db()
    user = msg.from_user
    if user:
        async with db.execute(
            "SELECT since FROM afk_users WHERE user_id = ?", (user.id,),
        ) as cur:
            row = await cur.fetchone()
        if row and not (msg.text and msg.text.lower().startswith("/afk")):
            since = row[0]
            await db.execute("DELETE FROM afk_users WHERE user_id = ?", (user.id,))
            await db.commit()
            try:
                await msg.reply_text(
                    await tr(msg.chat.id, "afk_back",
                             user=_user_link(user),
                             dur=_format_duration(int(time.time()) - since)),
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass
    # Mention notice
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        async with db.execute(
            "SELECT reason, since FROM afk_users WHERE user_id = ?", (target.id,),
        ) as cur:
            row = await cur.fetchone()
        if row:
            reason, since = row
            try:
                await msg.reply_text(
                    f"{_user_link(target)} is AFK ({_format_duration(int(time.time()) - since)})\n"
                    f"Reason: {reason}",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass


# ----------------------------------------------------------------------
# Mini tools.
# ----------------------------------------------------------------------
async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Roll a dice in chat."""
    try:
        await context.bot.send_dice(update.effective_chat.id, emoji="🎲")
    except TelegramError:
        pass


async def cmd_coin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Flip a coin."""
    result = random.choice(["Heads", "Tails"])
    await update.effective_message.reply_text(f"🪙 {result}")


async def cmd_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Magic 8-ball."""
    answers = [
        "Yes.", "No.", "Maybe.", "Definitely.", "Ask again later.",
        "Don't count on it.", "Without a doubt.", "Very doubtful.",
        "Outlook good.", "Cannot predict now.", "Most likely.", "Better not tell you now.",
    ]
    await update.effective_message.reply_text(f"🎱 {random.choice(answers)}")


async def cmd_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pick a random option: ``/pick a, b, c``."""
    text = " ".join(context.args or [])
    if not text:
        await update.effective_message.reply_text("Usage: /pick option1, option2, ...")
        return
    options = [o.strip() for o in text.split(",") if o.strip()]
    if not options:
        return
    await update.effective_message.reply_text(f"Picked: {random.choice(options)}")


async def cmd_calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Evaluate a simple arithmetic expression (digits + operators only)."""
    expr = " ".join(context.args or [])
    if not expr:
        await update.effective_message.reply_text("Usage: /calc 2 + 2 * 5")
        return
    if not re.fullmatch(r"[0-9+\-*/().\s%]+", expr):
        await update.effective_message.reply_text("Sirf numbers + - * / % () allowed hain.")
        return
    try:
        result = eval(expr, {"__builtins__": {}}, {})  # safe due to regex above
        await update.effective_message.reply_text(f"= {result}")
    except Exception:
        await update.effective_message.reply_text("Expression invalid.")


async def cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a QR-code image link for the given text."""
    text = " ".join(context.args or [])
    if not text:
        await update.effective_message.reply_text("Usage: /qr <text>")
        return
    encoded = urllib.parse.quote(text, safe="")
    url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}"
    try:
        await update.effective_message.reply_photo(url, caption=text[:200])
    except TelegramError:
        await update.effective_message.reply_text(url)


async def cmd_shorten(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shorten a URL via the public is.gd service."""
    text = " ".join(context.args or [])
    if not text:
        await update.effective_message.reply_text("Usage: /shorten <url>")
        return
    api = f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(text, safe='')}"
    try:
        loop = asyncio.get_event_loop()
        short = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(api, timeout=5).read().decode().strip(),
        )
    except Exception:
        await update.effective_message.reply_text("Shorten service abhi available nahi.")
        return
    await update.effective_message.reply_text(short)


async def cmd_reverse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reverse the given text."""
    text = " ".join(context.args or [])
    if not text and update.effective_message.reply_to_message:
        text = update.effective_message.reply_to_message.text or ""
    if not text:
        await update.effective_message.reply_text("Usage: /reverse <text>")
        return
    await update.effective_message.reply_text(text[::-1])


async def cmd_runs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a random witty 'runs' line."""
    runs = [
        "Slipping into a black hole.", "Tip-toeing past the admins.",
        "Dodging Telegram's API limits.", "Touching grass.",
        "Searching for the lost socks.", "Outsmarting CAPTCHAs.",
        "Rebooting the matrix.", "Hiding behind a sticker pack.",
    ]
    await update.effective_message.reply_text(random.choice(runs))


async def cmd_throw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Throw a random object at someone (for fun)."""
    target, _ = await _resolve_target_and_reason(update, context)
    item = random.choice(["a chair", "a banana", "a snowball", "a pillow", "a watermelon", "a stinky shoe"])
    if target:
        await update.effective_message.reply_text(
            f"Threw {item} at {_user_link(target)}!", parse_mode=ParseMode.HTML,
        )
    else:
        await update.effective_message.reply_text(f"Threw {item} into the void.")


async def cmd_decide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Yes/no decider."""
    options = ["Yes!", "No.", "Probably.", "I wouldn't.", "Go for it!", "Wait a bit."]
    await update.effective_message.reply_text(random.choice(options))


async def cmd_ud(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lookup a word in Urban Dictionary."""
    term = " ".join(context.args or [])
    if not term:
        await update.effective_message.reply_text("Usage: /ud <term>")
        return
    api = f"https://api.urbandictionary.com/v0/define?term={urllib.parse.quote(term)}"
    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(api, timeout=5).read().decode(),
        )
        data = json.loads(raw)
    except Exception:
        await update.effective_message.reply_text("Service abhi available nahi.")
        return
    items = data.get("list") or []
    if not items:
        await update.effective_message.reply_text("Koi definition nahi mili.")
        return
    top = items[0]
    definition = top.get("definition", "").replace("[", "").replace("]", "")[:1500]
    example = top.get("example", "").replace("[", "").replace("]", "")[:500]
    text = f"<b>{term}</b>\n\n{definition}"
    if example:
        text += f"\n\n<i>{example}</i>"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_paste(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Upload the replied message text to dpaste.org."""
    msg = update.effective_message
    text = ""
    if msg.reply_to_message and msg.reply_to_message.text:
        text = msg.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await msg.reply_text("Reply de ya text bhej.")
        return
    try:
        loop = asyncio.get_event_loop()
        data = urllib.parse.urlencode({"content": text, "syntax": "text", "expiry_days": 7}).encode()
        link = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen("https://dpaste.org/api/", data=data, timeout=5).read().decode().strip().strip('"'),
        )
        await msg.reply_text(link)
    except Exception:
        await msg.reply_text("Paste service abhi available nahi.")


async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lookup a Wikipedia summary."""
    term = " ".join(context.args or [])
    if not term:
        await update.effective_message.reply_text("Usage: /wiki <term>")
        return
    api = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(term)
    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(api, timeout=5).read().decode(),
        )
        data = json.loads(raw)
    except Exception:
        await update.effective_message.reply_text("Wiki service abhi available nahi.")
        return
    title = data.get("title", term)
    extract = data.get("extract", "Koi summary nahi mila.")
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    text = f"<b>{title}</b>\n\n{extract[:1500]}"
    if url:
        text += f"\n\n<a href=\"{url}\">Read more</a>"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)


# ----------------------------------------------------------------------
# Sticker / chat-info helpers.
# ----------------------------------------------------------------------
async def cmd_chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show metadata about the current chat."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.effective_message.reply_text("Yeh ek private chat hai.")
        return
    try:
        full = await context.bot.get_chat(chat.id)
        count = await context.bot.get_chat_member_count(chat.id)
    except TelegramError:
        await update.effective_message.reply_text("Chat info nahi mila.")
        return
    text = (
        f"<b>Chat:</b> {full.title}\n"
        f"<b>ID:</b> <code>{full.id}</code>\n"
        f"<b>Type:</b> {full.type}\n"
        f"<b>Members:</b> {count}\n"
    )
    if full.username:
        text += f"<b>Link:</b> @{full.username}\n"
    if full.description:
        text += f"<b>Bio:</b> {full.description[:300]}"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_pingmsg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick ping with round-trip latency."""
    start = time.monotonic()
    m = await update.effective_message.reply_text("Pinging...")
    elapsed = (time.monotonic() - start) * 1000
    try:
        await m.edit_text(f"🏓 Pong — {elapsed:.0f} ms")
    except TelegramError:
        pass


async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show how long the bot has been running."""
    started = getattr(context.application, "_started_at", None)
    if not started:
        await update.effective_message.reply_text("Uptime info nahi.")
        return
    secs = int(time.time()) - started
    await update.effective_message.reply_text(f"Uptime: {_format_duration(secs)}")


async def cmd_speed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Estimate Telegram round-trip and DB query time."""
    t0 = time.monotonic()
    m = await update.effective_message.reply_text("Measuring...")
    rt = (time.monotonic() - t0) * 1000
    db = await _get_db()
    t1 = time.monotonic()
    async with db.execute("SELECT 1") as cur:
        await cur.fetchone()
    db_ms = (time.monotonic() - t1) * 1000
    try:
        await m.edit_text(f"Telegram RTT: {rt:.0f} ms\nDB latency: {db_ms:.1f} ms")
    except TelegramError:
        pass


async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete every message between the replied one and the /purge command."""
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("/purge ko reply pe use karen.")
        return
    chat_id = msg.chat.id
    start_id = msg.reply_to_message.message_id
    end_id = msg.message_id
    deleted = 0
    for mid in range(start_id, end_id + 1):
        try:
            await context.bot.delete_message(chat_id, mid)
            deleted += 1
        except TelegramError:
            continue
    try:
        await context.bot.send_message(chat_id, f"Purged {deleted} messages.")
    except TelegramError:
        pass


async def cmd_zombies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect deleted-account members and optionally remove them."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    if chat.type == "private":
        return
    args = context.args or []
    do_clean = "clean" in [a.lower() for a in args]
    db = await _get_db()
    async with db.execute(
        "SELECT user_id FROM group_members WHERE chat_id = ?",
        (chat.id,),
    ) as cur:
        members = [r[0] for r in await cur.fetchall()]
    zombies = 0
    cleaned = 0
    for uid in members:
        try:
            m = await context.bot.get_chat_member(chat.id, uid)
            if m.user.first_name in ("", None) and not m.user.username:
                zombies += 1
                if do_clean:
                    try:
                        await context.bot.ban_chat_member(chat.id, uid)
                        await context.bot.unban_chat_member(chat.id, uid)
                        cleaned += 1
                    except TelegramError:
                        pass
        except TelegramError:
            continue
    text = f"Zombie scan: {zombies} deleted accounts found."
    if do_clean:
        text += f"\nCleaned: {cleaned}."
    await update.effective_message.reply_text(text)


async def cmd_promote_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set a custom admin title on a promoted user: ``/title <title>``."""
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    target, reason = await _resolve_target_and_reason(update, context)
    if target is None:
        await msg.reply_text("Reply ya @user / id de.")
        return
    title = reason or " ".join(context.args or [])
    if not title:
        await msg.reply_text("Title text chahiye.")
        return
    try:
        await context.bot.set_chat_administrator_custom_title(
            update.effective_chat.id, target.id, title[:16],
        )
        await msg.reply_text(f"{_user_link(target)} ka title '{title[:16]}' set kiya.", parse_mode=ParseMode.HTML)
    except TelegramError as e:
        await msg.reply_text(f"Title set nahi ho saka: {e}")


# ----------------------------------------------------------------------
# Extended help cards.
# ----------------------------------------------------------------------
HELP_CARDS = {
    "notes": (
        "<b>Notes / Saved messages</b>\n"
        "/save <name> <text> — save a note (or reply to media + name)\n"
        "/get <name> — recall a note (also: #name)\n"
        "/notes — list every note\n"
        "/clear <name> — delete a note\n"
        "/clearnotes — wipe every note (owner)"
    ),
    "filters": (
        "<b>Filters</b>\n"
        "/filter <kw> <reply> — auto-reply when keyword seen\n"
        "/filters — list filters\n"
        "/stop <kw> — remove a filter\n"
        "/stopall — remove all filters"
    ),
    "locks": (
        "<b>Locks</b>\n"
        "/lock <type> [type ...] — block message types\n"
        "/unlock <type> — release locks\n"
        "/locks — show current state\n"
        "/locktypes — list every supported type"
    ),
    "disable": (
        "<b>Disable / Enable</b>\n"
        "/disable <cmd> — silence a command for non-admins\n"
        "/enable <cmd> — re-enable\n"
        "/disabled — list disabled commands\n"
        "/disableable — list toggleable commands"
    ),
    "feds": (
        "<b>Federations</b>\n"
        "/newfed <name> — create one (PM)\n"
        "/joinfed <id> — link this chat\n"
        "/leavefed — unlink this chat\n"
        "/fban — fed-ban a user (reply / @user / id)\n"
        "/unfban — lift a fed ban\n"
        "/fedinfo — show federation details\n"
        "/fedbanlist — list bans"
    ),
    "connect": (
        "<b>PM Connect</b>\n"
        "/connect — link the current group to your PM\n"
        "/disconnect — unlink\n"
        "/connection — show current link"
    ),
    "global": (
        "<b>Global ban (sudo only)</b>\n"
        "/gban — ban a user from every group bot is in\n"
        "/ungban — lift a global ban\n"
        "/gbanlist — list global bans\n"
        "/addsudo, /delsudo, /sudolist (owner)"
    ),
    "fun": (
        "<b>Mini tools</b>\n"
        "/dice /coin /8ball /pick /decide /runs /throw\n"
        "/calc /qr /shorten /reverse /paste /wiki /ud\n"
        "/chatinfo /uptime /pingmsg /speed"
    ),
}


async def cmd_helpcards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show one of the new help cards: ``/helpcard <name>``."""
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Cards: " + ", ".join(sorted(HELP_CARDS.keys())),
        )
        return
    card = HELP_CARDS.get(args[0].lower())
    if not card:
        await update.effective_message.reply_text("Unknown card.")
        return
    await update.effective_message.reply_text(card, parse_mode=ParseMode.HTML)


# ----------------------------------------------------------------------
# Word blacklist (regex per-chat).
# ----------------------------------------------------------------------
async def cmd_addblword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a word to the chat blacklist (matches whole words)."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /addblword <word> [word...]")
        return
    db = await _get_db()
    added = []
    for w in args:
        await db.execute(
            "INSERT OR IGNORE INTO blacklist(chat_id, word) VALUES (?,?)",
            (chat_id, w.lower()),
        )
        added.append(w.lower())
    await db.commit()
    await update.effective_message.reply_text("Added: " + ", ".join(added))


async def cmd_rmblword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove words from the chat blacklist."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /rmblword <word>")
        return
    db = await _get_db()
    for w in args:
        await db.execute(
            "DELETE FROM blacklist WHERE chat_id = ? AND word = ?",
            (chat_id, w.lower()),
        )
    await db.commit()
    await update.effective_message.reply_text("Removed.")


async def cmd_blwords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the chat blacklist."""
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    async with db.execute(
        "SELECT word FROM blacklist WHERE chat_id = ? ORDER BY word", (chat_id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Blacklist khali hai.")
        return
    await update.effective_message.reply_text("Blacklisted words:\n" + ", ".join(r[0] for r in rows))


async def blacklist_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete messages containing any blacklisted word; warn the sender."""
    try:
        msg = update.effective_message
        if not msg or msg.chat.type == "private":
            return
        if msg.from_user and await _is_chat_admin(msg.chat.id, msg.from_user.id, context.bot):
            return
        text = (msg.text or msg.caption or "").lower()
        if not text:
            return
        db = await _get_db()
        async with db.execute(
            "SELECT word FROM blacklist WHERE chat_id = ?", (msg.chat.id,),
        ) as cur:
            words = [r[0] for r in await cur.fetchall()]
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", text):
                try:
                    await msg.delete()
                except TelegramError:
                    pass
                return
    except Exception:
        log.exception("blacklist_pipeline failed for update")


# ----------------------------------------------------------------------
# Slowmode helper (Telegram-native slow_mode_delay wrapper).
# ----------------------------------------------------------------------
async def cmd_slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set the chat's slow-mode delay: ``/slowmode <seconds | off>``."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    if chat.type == "private":
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /slowmode <seconds | off>")
        return
    val = args[0].lower()
    if val in ("off", "0", "no"):
        secs = 0
    elif val.isdigit():
        secs = int(val)
    else:
        secs = _parse_duration(val) or 0
    try:
        await context.bot.set_chat_slow_mode_delay(chat.id, secs)
        await update.effective_message.reply_text(
            f"Slow mode {'off' if not secs else f'set to {secs}s'}.",
        )
    except TelegramError as e:
        await update.effective_message.reply_text(f"Failed: {e}")


# ----------------------------------------------------------------------
# Tagging helpers.
# ----------------------------------------------------------------------
TAG_COOLDOWN: dict[int, float] = {}


async def cmd_tagall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mention every member (in batches). Cooldown of 5 minutes per chat."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    if chat.type == "private":
        return
    last = TAG_COOLDOWN.get(chat.id, 0)
    if time.time() - last < 300:
        await update.effective_message.reply_text("Cooldown: 5 min me ek baar use hota hai.")
        return
    TAG_COOLDOWN[chat.id] = time.time()
    db = await _get_db()
    async with db.execute(
        "SELECT user_id FROM group_members WHERE chat_id = ? LIMIT 200",
        (chat.id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Members list khali hai.")
        return
    msg_text = " ".join(context.args or []) or "Attention!"
    batch = []
    for r in rows:
        batch.append(f'<a href="tg://user?id={r[0]}">\u2063</a>')
        if len(batch) >= 5:
            try:
                await context.bot.send_message(
                    chat.id, msg_text + "".join(batch),
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass
            batch = []
            await asyncio.sleep(1)
    if batch:
        try:
            await context.bot.send_message(
                chat.id, msg_text + "".join(batch),
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass


async def cmd_admincall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently ping every admin in the chat."""
    chat = update.effective_chat
    if chat.type == "private":
        return
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except TelegramError:
        return
    text = " ".join(context.args or []) or "Admins needed!"
    mentions = "".join(f'<a href="tg://user?id={a.user.id}">\u2063</a>' for a in admins if not a.user.is_bot)
    await update.effective_message.reply_text(text + mentions, parse_mode=ParseMode.HTML)


# ----------------------------------------------------------------------
# Random replies / bored fillers.
# ----------------------------------------------------------------------
JOKES = [
    "Why don't programmers like nature? Too many bugs.",
    "I told my computer I needed a break — it said 'No problem, I'll go to sleep.'",
    "There are 10 types of people: those who get binary and those who don't.",
    "Why do Java developers wear glasses? Because they can't C#.",
    "Debugging: removing the needles from the haystack.",
    "A SQL query walks into a bar, walks up to two tables and asks: 'Can I join you?'",
]
FACTS = [
    "Honey never spoils — archaeologists have found edible jars in Egyptian tombs.",
    "Octopuses have three hearts and blue blood.",
    "Bananas are berries; strawberries aren't.",
    "There are more possible chess games than atoms in the observable universe.",
    "Sharks predate trees by 50 million years.",
    "A day on Venus is longer than its year.",
]
QUOTES = [
    "“The journey of a thousand miles begins with one step.” — Lao Tzu",
    "“Talk is cheap. Show me the code.” — Linus Torvalds",
    "“Be yourself; everyone else is already taken.” — Oscar Wilde",
    "“In the middle of difficulty lies opportunity.” — Albert Einstein",
    "“Programs must be written for people to read.” — Hal Abelson",
]


async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tell a random joke."""
    await update.effective_message.reply_text(random.choice(JOKES))


async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Drop a fun fact."""
    await update.effective_message.reply_text(random.choice(FACTS))


async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Share an inspiring quote."""
    await update.effective_message.reply_text(random.choice(QUOTES))


# ----------------------------------------------------------------------
# Time / timezone helpers.
# ----------------------------------------------------------------------
TIMEZONES = {
    "ist": 5.5, "pkt": 5.0, "bst": 6.0, "utc": 0.0, "gmt": 0.0,
    "edt": -4.0, "est": -5.0, "pst": -8.0, "pdt": -7.0, "cet": 1.0,
    "cest": 2.0, "jst": 9.0, "kst": 9.0, "sgt": 8.0, "msk": 3.0,
    "aest": 10.0, "nzst": 12.0,
}


async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current time in a timezone: ``/time ist``."""
    args = context.args or []
    tz = (args[0] if args else "utc").lower()
    offset = TIMEZONES.get(tz)
    if offset is None:
        await update.effective_message.reply_text(
            "Supported: " + ", ".join(sorted(TIMEZONES.keys())),
        )
        return
    now = datetime.now(timezone.utc) + timedelta(hours=offset)
    await update.effective_message.reply_text(
        f"{tz.upper()}: {now.strftime('%Y-%m-%d %H:%M:%S')}",
    )


async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Schedule a one-shot reminder: ``/remind 30m text...``."""
    args = context.args or []
    if len(args) < 2:
        await update.effective_message.reply_text("Usage: /remind <duration> <text>")
        return
    secs = _parse_duration(args[0])
    if secs is None:
        await update.effective_message.reply_text("Invalid duration. Try 30m, 2h, 1d.")
        return
    text = " ".join(args[1:])
    chat_id = update.effective_chat.id
    user_link = _user_link(update.effective_user)

    async def _job(_ctx):
        try:
            await _ctx.bot.send_message(
                chat_id, f"⏰ Reminder for {user_link}: {html.escape(text)}",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass

    if context.application.job_queue:
        context.application.job_queue.run_once(_job, when=secs)
        await update.effective_message.reply_text(f"Reminder set for {_format_duration(secs)}.")
    else:
        await update.effective_message.reply_text("Job queue available nahi.")


# ----------------------------------------------------------------------
# Convenience: detailed userinfo.
# ----------------------------------------------------------------------
async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed info card for a user (reply / @user / id)."""
    target, _ = await _resolve_target_and_reason(update, context)
    if target is None:
        target = update.effective_user
    chat = update.effective_chat
    info = [
        f"<b>ID:</b> <code>{target.id}</code>",
        f"<b>Name:</b> {html.escape(target.first_name or '')}",
    ]
    if target.last_name:
        info.append(f"<b>Last name:</b> {html.escape(target.last_name)}")
    if target.username:
        info.append(f"<b>Username:</b> @{target.username}")
    if target.language_code:
        info.append(f"<b>Lang:</b> {target.language_code}")
    if chat and chat.type != "private":
        try:
            m = await context.bot.get_chat_member(chat.id, target.id)
            info.append(f"<b>Status:</b> {m.status}")
        except TelegramError:
            pass
    db = await _get_db()
    async with db.execute(
        "SELECT COUNT(*) FROM warns WHERE chat_id = ? AND user_id = ?",
        (chat.id if chat else 0, target.id),
    ) as cur:
        warns = (await cur.fetchone())[0]
    info.append(f"<b>Warns here:</b> {warns}")
    async with db.execute(
        "SELECT 1 FROM gbans WHERE user_id = ?", (target.id,),
    ) as cur:
        if await cur.fetchone():
            info.append("<b>Globally banned:</b> yes")
    await update.effective_message.reply_text("\n".join(info), parse_mode=ParseMode.HTML)


# ----------------------------------------------------------------------
# Group rules formatter.
# ----------------------------------------------------------------------
async def cmd_setrules2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set the chat rules (HTML supported)."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    text = " ".join(context.args or [])
    if not text and update.effective_message.reply_to_message:
        text = update.effective_message.reply_to_message.text or ""
    if not text:
        await update.effective_message.reply_text("Usage: /setrules2 <text> (or reply)")
        return
    db = await _get_db()
    await db.execute(
        "UPDATE groups SET rules = ? WHERE chat_id = ?",
        (text, chat_id),
    )
    await db.commit()
    await update.effective_message.reply_text("Rules updated.")


async def cmd_clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear the chat rules."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    db = await _get_db()
    await db.execute("UPDATE groups SET rules = '' WHERE chat_id = ?", (chat_id,))
    await db.commit()
    await update.effective_message.reply_text("Rules cleared.")


# ----------------------------------------------------------------------
# Anti-Raid — temporarily lock the chat to known members.
# ----------------------------------------------------------------------
RAID_FLAGS: dict[int, float] = {}


async def cmd_raid_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Engage anti-raid mode: instantly ban every new joiner for N minutes."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    if chat.type == "private":
        return
    args = context.args or []
    minutes = int(args[0]) if args and args[0].isdigit() else 10
    RAID_FLAGS[chat.id] = time.time() + minutes * 60
    await update.effective_message.reply_text(
        f"Anti-raid ON for {minutes} min — naye joiners auto-ban honge.",
    )


async def cmd_raid_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disengage anti-raid mode."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    RAID_FLAGS.pop(chat.id, None)
    await update.effective_message.reply_text("Anti-raid OFF.")


async def raid_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """While anti-raid is on, instantly ban every new chat member."""
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    expires = RAID_FLAGS.get(msg.chat.id)
    if not expires or time.time() > expires:
        RAID_FLAGS.pop(msg.chat.id, None)
        return
    for m in msg.new_chat_members:
        try:
            await context.bot.ban_chat_member(msg.chat.id, m.id)
        except TelegramError:
            pass


# ----------------------------------------------------------------------
# Banlist / mutelist viewers.
# ----------------------------------------------------------------------
async def cmd_warnstop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the warn leaderboard for the chat (top 10)."""
    chat = update.effective_chat
    if chat.type == "private":
        return
    db = await _get_db()
    async with db.execute(
        "SELECT user_id, COUNT(*) c FROM warns WHERE chat_id = ? "
        "GROUP BY user_id ORDER BY c DESC LIMIT 10",
        (chat.id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Koi warns nahi hain.")
        return
    lines = ["<b>Warn leaderboard:</b>"]
    for uid, count in rows:
        lines.append(f"• <code>{uid}</code> — {count} warns")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_logsview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the last 20 log entries for the chat (admin only)."""
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    db = await _get_db()
    async with db.execute(
        "SELECT actor_id, target_id, action, info, created_at FROM log_actions "
        "WHERE chat_id = ? ORDER BY id DESC LIMIT 20",
        (chat.id,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        await update.effective_message.reply_text("Log khali hai.")
        return
    lines = []
    for actor, target, action, info, when in rows:
        ts = time.strftime("%m-%d %H:%M", time.gmtime(when))
        lines.append(f"{ts}  {actor} → {target}  {action}  {info or ''}")
    await update.effective_message.reply_text("<pre>" + html.escape("\n".join(lines)) + "</pre>", parse_mode=ParseMode.HTML)


# ----------------------------------------------------------------------
# Echo / say commands.
# ----------------------------------------------------------------------
async def cmd_say(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Make the bot speak (admin only)."""
    if not await _require_admin(update, context):
        return
    text = " ".join(context.args or [])
    if not text and update.effective_message.reply_to_message:
        text = update.effective_message.reply_to_message.text or ""
    if not text:
        return
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass
    await context.bot.send_message(update.effective_chat.id, text)


async def cmd_echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo back the supplied text (admin)."""
    if not await _require_admin(update, context):
        return
    text = " ".join(context.args or [])
    if text:
        await update.effective_message.reply_text(text)


# ----------------------------------------------------------------------
# Polls & quiz quick-make.
# ----------------------------------------------------------------------
async def cmd_qpoll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick poll: ``/qpoll Question? | option1 | option2 | ...``."""
    if not await _require_admin(update, context):
        return
    text = " ".join(context.args or [])
    if "|" not in text:
        await update.effective_message.reply_text("Usage: /qpoll Question? | opt1 | opt2 | opt3")
        return
    parts = [p.strip() for p in text.split("|") if p.strip()]
    if len(parts) < 3:
        await update.effective_message.reply_text("At least 1 question + 2 options.")
        return
    question = parts[0]
    options = parts[1:11]
    try:
        await context.bot.send_poll(update.effective_chat.id, question, options, is_anonymous=False)
    except TelegramError as e:
        await update.effective_message.reply_text(f"Failed: {e}")


# ----------------------------------------------------------------------
# Bot owner contact.
# ----------------------------------------------------------------------
async def cmd_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the bot's configured owner."""
    owner = os.environ.get("BOT_OWNER_ID", "(not set)")
    await update.effective_message.reply_text(f"Bot owner id: <code>{owner}</code>", parse_mode=ParseMode.HTML)


# ----------------------------------------------------------------------
# Quick captcha / approval shortcuts.
# ----------------------------------------------------------------------
async def cmd_captcha_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable join-time captcha for the chat."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    await db_exec(
        "UPDATE group_settings SET captcha_on = 1 WHERE chat_id = ?", (chat_id,),
    )
    await update.effective_message.reply_text("Captcha enabled.")


async def cmd_captcha_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable join-time captcha."""
    if not await _require_admin(update, context):
        return
    chat_id = await _resolve_chat_for_pm(update)
    if chat_id is None:
        return
    await db_exec(
        "UPDATE group_settings SET captcha_on = 0 WHERE chat_id = ?", (chat_id,),
    )
    await update.effective_message.reply_text("Captcha disabled.")


# ----------------------------------------------------------------------
# Migrate-helper: when a group becomes a supergroup, copy settings.
# ----------------------------------------------------------------------
async def migration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Copy settings rows when a chat is migrated to supergroup."""
    msg = update.effective_message
    if not msg or not msg.migrate_to_chat_id:
        return
    old_id = msg.chat.id
    new_id = msg.migrate_to_chat_id
    db = await _get_db()
    for table in ("group_settings", "groups", "warns", "notes", "filters", "locks", "disabled_cmds"):
        try:
            await db.execute(
                f"UPDATE {table} SET chat_id = ? WHERE chat_id = ?",
                (new_id, old_id),
            )
        except sqlite3.OperationalError:
            continue
    await db.commit()
    log.info("Migrated chat %s -> %s", old_id, new_id)


# =============================================================================
# OTHER settings page — full feature implementation
# Topic / Banned Words / Recurring messages / Members Management /
# Masked users / Discussion group / Personal Commands / Magic Stickers&GIFs /
# Message length / Channels management / Permissions / Log Channel
# =============================================================================

_OTHER_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS personal_cmds (
        chat_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        response TEXT,
        file_id TEXT,
        file_type TEXT,
        created_by INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, name)
    )""",
    """CREATE TABLE IF NOT EXISTS magic_stickers (
        chat_id INTEGER NOT NULL,
        sticker_id TEXT NOT NULL,
        response TEXT,
        is_gif INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, sticker_id)
    )""",
    """CREATE TABLE IF NOT EXISTS recurring_msgs (
        chat_id INTEGER NOT NULL,
        rid INTEGER NOT NULL,
        text TEXT,
        interval_seconds INTEGER NOT NULL,
        last_run INTEGER DEFAULT 0,
        enabled INTEGER DEFAULT 1,
        created_at INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, rid)
    )""",
    """CREATE TABLE IF NOT EXISTS masked_users (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        until_ts INTEGER DEFAULT 0,
        reason TEXT,
        created_at INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS blocked_channels (
        chat_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        title TEXT,
        created_at INTEGER DEFAULT 0,
        PRIMARY KEY(chat_id, channel_id)
    )""",
]

_OTHER_NEW_COLUMNS = [
    ("group_settings", "max_msg_len", "INTEGER DEFAULT 0"),
    ("group_settings", "discussion_chat_id", "INTEGER DEFAULT 0"),
    ("group_settings", "log_channel_id", "INTEGER DEFAULT 0"),
    ("group_settings", "magic_on", "INTEGER DEFAULT 1"),
    ("group_settings", "personal_cmds_on", "INTEGER DEFAULT 1"),
    ("group_settings", "members_join_msg", "INTEGER DEFAULT 1"),
    ("group_settings", "members_leave_msg", "INTEGER DEFAULT 1"),
    ("group_settings", "channels_block", "INTEGER DEFAULT 0"),
    ("group_settings", "perms_admins_only", "INTEGER DEFAULT 0"),
    ("group_settings", "default_topic_id", "INTEGER DEFAULT 0"),
]


async def _other_init() -> None:
    """Create the extra tables and columns required by the Other settings page."""
    db = await _get_db()
    for sql in _OTHER_TABLES_SQL:
        try:
            await db.execute(sql)
        except sqlite3.OperationalError as e:
            log.warning("other_init table failed: %s", e)
    for table, col, decl in _OTHER_NEW_COLUMNS:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass  # already exists
    await db.commit()


# ----------------------------- helpers ---------------------------------------

def _safe_html(s: str) -> str:
    return html.escape(s or "", quote=False)


async def _get_other_setting(chat_id: int, col: str, default=0):
    row = await db_one(f"SELECT {col} AS v FROM group_settings WHERE chat_id=?", (chat_id,))
    if row is None:
        return default
    try:
        return row["v"] if row["v"] is not None else default
    except (IndexError, KeyError):
        return default


async def _toggle_setting(chat_id: int, col: str) -> int:
    cur = int(await _get_other_setting(chat_id, col, 0) or 0)
    new = 0 if cur else 1
    await set_setting(chat_id, col, new)
    return new


def _on_off_label(v) -> str:
    return "ON ✅" if int(v or 0) else "OFF ❌"


# ----------------------------- sub renderers ---------------------------------

async def render_other_topic(q, chat_id: int) -> None:
    s = await get_settings(chat_id)
    cur = int(s["default_topic_id"] if "default_topic_id" in s.keys() and s["default_topic_id"] is not None else 0)
    text = (
        "📂 <b>Default Topic</b>\n\n"
        "If your group has Topics enabled, set a default topic where the bot will send "
        "automatic messages (welcome, recurring, logs).\n\n"
        f"Current: <code>{cur or 'none (general)'}</code>\n\n"
        "Send <code>/settopic &lt;id&gt;</code> in the group to set it (reply to a message in "
        "the topic and use <code>/settopic</code> for auto-detect)."
    )
    cd = lambda x: f"st:other:{chat_id}:topic:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear default topic", callback_data=cd("clear"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_banned(q, chat_id: int) -> None:
    rows = await db_all("SELECT word FROM blacklist WHERE chat_id=? ORDER BY word LIMIT 50", (chat_id,))
    items = ", ".join(_safe_html(r["word"]) for r in rows) or "<i>(none)</i>"
    text = (
        "🆎 <b>Banned Words</b>\n\n"
        "Manage your group blacklist. Messages containing these words are deleted.\n\n"
        f"<b>Current ({len(rows)}):</b> {items}\n\n"
        "Add: <code>/addblacklist word</code>\n"
        "Remove: <code>/delblacklist word</code>\n"
        "List all: <code>/blacklist</code>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear all", callback_data=f"st:other:{chat_id}:banned:clear")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_recurring(q, chat_id: int) -> None:
    rows = await db_all(
        "SELECT rid, text, interval_seconds, enabled FROM recurring_msgs WHERE chat_id=? ORDER BY rid",
        (chat_id,),
    )
    if rows:
        lines = []
        for r in rows:
            preview = (r["text"] or "")[:40].replace("\n", " ")
            mark = "✅" if r["enabled"] else "⏸"
            lines.append(f"{mark} <code>#{r['rid']}</code> every {_format_duration(r['interval_seconds'])}: {_safe_html(preview)}")
        body = "\n".join(lines)
    else:
        body = "<i>(no recurring messages)</i>"
    text = (
        "🕐 <b>Recurring messages</b>\n\n"
        "Send a message to the group automatically every N minutes/hours.\n\n"
        f"{body}\n\n"
        "Add: <code>/addrecurring 30m Your message here</code>\n"
        "Remove: <code>/delrecurring &lt;id&gt;</code>\n"
        "Toggle: <code>/togglerecurring &lt;id&gt;</code>\n"
        "List: <code>/listrecurring</code>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear all", callback_data=f"st:other:{chat_id}:recurring:clear")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_members(q, chat_id: int) -> None:
    s = await get_settings(chat_id)
    join_on = int(s["members_join_msg"] if "members_join_msg" in s.keys() else 1)
    leave_on = int(s["members_leave_msg"] if "members_leave_msg" in s.keys() else 1)
    text = (
        "👥 <b>Members Management</b>\n\n"
        "Quick toggles for member join/leave behaviour. Detailed welcome/goodbye text "
        "is in the main settings page.\n\n"
        f"📥 Show join messages: <b>{_on_off_label(join_on)}</b>\n"
        f"📤 Show leave messages: <b>{_on_off_label(leave_on)}</b>\n\n"
        "Helpful commands: <code>/zombies</code>, <code>/inactives</code>, <code>/list</code>"
    )
    cd = lambda x: f"st:other:{chat_id}:members:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📥 Join {_on_off_label(join_on)}", callback_data=cd("join"))],
        [InlineKeyboardButton(f"📤 Leave {_on_off_label(leave_on)}", callback_data=cd("leave"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_masked(q, chat_id: int) -> None:
    rows = await db_all(
        "SELECT user_id, until_ts, reason FROM masked_users WHERE chat_id=? ORDER BY user_id LIMIT 30",
        (chat_id,),
    )
    if rows:
        now = now_ts()
        lines = []
        for r in rows:
            ut = int(r["until_ts"] or 0)
            if ut and ut < now:
                continue
            left = "permanent" if not ut else f"{_format_duration(max(0, ut - now))} left"
            reason = (r["reason"] or "").strip()
            tail = f" — {_safe_html(reason)}" if reason else ""
            lines.append(f"• <code>{r['user_id']}</code> ({left}){tail}")
        body = "\n".join(lines) or "<i>(no active masks)</i>"
    else:
        body = "<i>(none)</i>"
    text = (
        "🥸 <b>Masked users</b>\n\n"
        "Mask noisy users — their messages are silently deleted (without notifying them) "
        "for the duration you set.\n\n"
        f"{body}\n\n"
        "Add: reply to user with <code>/maskuser [duration] [reason]</code>\n"
        "    or <code>/maskuser @user 1h spam</code>\n"
        "Remove: <code>/unmaskuser @user</code>\n"
        "List: <code>/listmasked</code>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear all", callback_data=f"st:other:{chat_id}:masked:clear")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_discussion(q, chat_id: int) -> None:
    cur = int(await _get_other_setting(chat_id, "discussion_chat_id", 0) or 0)
    text = (
        "📣 <b>Discussion group</b>\n\n"
        "Link a discussion group so the bot knows where channel-post replies live.\n\n"
        f"Current: <code>{cur or 'not set'}</code>\n\n"
        "Set: <code>/setdiscussion &lt;chat_id&gt;</code>\n"
        "Clear: <code>/cleardiscussion</code>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear", callback_data=f"st:other:{chat_id}:discussion:clear")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_personal(q, chat_id: int) -> None:
    on = int(await _get_other_setting(chat_id, "personal_cmds_on", 1) or 0)
    rows = await db_all("SELECT name FROM personal_cmds WHERE chat_id=? ORDER BY name LIMIT 50", (chat_id,))
    items = ", ".join(f"<code>!{_safe_html(r['name'])}</code>" for r in rows) or "<i>(none)</i>"
    text = (
        "⌨️ <b>Personal Commands</b>\n\n"
        "Custom commands users can trigger with <code>!name</code> or <code>/name</code>.\n\n"
        f"Status: <b>{_on_off_label(on)}</b>\n"
        f"<b>Defined ({len(rows)}):</b> {items}\n\n"
        "Add (text): <code>/addcmd name your reply</code>\n"
        "Add (media): reply to photo/sticker/gif with <code>/addcmd name</code>\n"
        "Remove: <code>/delcmd name</code>\n"
        "List: <code>/listcmds</code>"
    )
    cd = lambda x: f"st:other:{chat_id}:personal:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Toggle {_on_off_label(on)}", callback_data=cd("toggle"))],
        [InlineKeyboardButton("🧹 Clear all", callback_data=cd("clear"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_magic(q, chat_id: int) -> None:
    on = int(await _get_other_setting(chat_id, "magic_on", 1) or 0)
    rows = await db_all("SELECT sticker_id, response FROM magic_stickers WHERE chat_id=? LIMIT 50", (chat_id,))
    text = (
        "🪄 <b>Magic Stickers &amp; GIFs</b>\n\n"
        "When someone sends a configured sticker/GIF the bot replies automatically.\n\n"
        f"Status: <b>{_on_off_label(on)}</b>\n"
        f"Configured: <b>{len(rows)}</b>\n\n"
        "Add: reply to a sticker/GIF with <code>/addsticker your reply</code>\n"
        "Remove: reply to the sticker/GIF with <code>/delsticker</code>\n"
        "List: <code>/liststickers</code>"
    )
    cd = lambda x: f"st:other:{chat_id}:magic:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Toggle {_on_off_label(on)}", callback_data=cd("toggle"))],
        [InlineKeyboardButton("🧹 Clear all", callback_data=cd("clear"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_msglen(q, chat_id: int) -> None:
    cur = int(await _get_other_setting(chat_id, "max_msg_len", 0) or 0)
    text = (
        "📏 <b>Message length</b>\n\n"
        "Automatically delete messages longer than the configured number of characters. "
        "Set to <code>0</code> to disable.\n\n"
        f"Current limit: <b>{cur or 'OFF'}</b>\n\n"
        "Set: <code>/setmaxlen 1000</code>\n"
        "Disable: <code>/setmaxlen 0</code>"
    )
    cd = lambda x: f"st:other:{chat_id}:msglen:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("OFF", callback_data=cd("0")),
            InlineKeyboardButton("500", callback_data=cd("500")),
            InlineKeyboardButton("1000", callback_data=cd("1000")),
        ],
        [
            InlineKeyboardButton("2000", callback_data=cd("2000")),
            InlineKeyboardButton("4000", callback_data=cd("4000")),
        ],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_channels(q, chat_id: int) -> None:
    block = int(await _get_other_setting(chat_id, "channels_block", 0) or 0)
    rows = await db_all(
        "SELECT channel_id, title FROM blocked_channels WHERE chat_id=? LIMIT 30", (chat_id,)
    )
    if rows:
        items = "\n".join(f"• <code>{r['channel_id']}</code> {_safe_html(r['title'] or '')}" for r in rows)
    else:
        items = "<i>(none)</i>"
    text = (
        "📢 <b>Channels management</b>\n\n"
        "Control posts that arrive from other channels (linked-channel auto-forwards).\n\n"
        f"🚫 Block all anonymous-channel posts: <b>{_on_off_label(block)}</b>\n\n"
        f"<b>Specifically blocked channels:</b>\n{items}\n\n"
        "Add: <code>/blockchannel &lt;channel_id&gt;</code>\n"
        "Remove: <code>/unblockchannel &lt;channel_id&gt;</code>\n"
        "List: <code>/listblockedchannels</code>"
    )
    cd = lambda x: f"st:other:{chat_id}:channels:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Block all anonymous {_on_off_label(block)}", callback_data=cd("toggle"))],
        [InlineKeyboardButton("🧹 Clear specific list", callback_data=cd("clear"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_perms(q, chat_id: int) -> None:
    only_admins = int(await _get_other_setting(chat_id, "perms_admins_only", 0) or 0)
    text = (
        "📝 <b>Permissions</b>\n\n"
        "Restrict who can change the bot's settings in this group.\n\n"
        f"Settings restricted to admins only: <b>{_on_off_label(only_admins)}</b>\n\n"
        "When ON, only chat admins (and the group owner) can call <code>/settings</code> "
        "or change configuration. When OFF, anyone with the relevant role flag can."
    )
    cd = lambda x: f"st:other:{chat_id}:perms:{x}"  # noqa: E731
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Toggle {_on_off_label(only_admins)}", callback_data=cd("toggle"))],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def render_other_logchan(q, chat_id: int) -> None:
    cur = int(await _get_other_setting(chat_id, "log_channel_id", 0) or 0)
    text = (
        "📜 <b>Log Channel</b>\n\n"
        "Send moderation actions and edited/deleted messages to a channel for auditing. "
        "Add the bot as admin in that channel first.\n\n"
        f"Current channel: <code>{cur or 'not set'}</code>\n\n"
        "Set: <code>/setlog &lt;channel_id&gt;</code>\n"
        "    or run <code>/setlog</code> inside the channel\n"
        "Clear: <code>/clearlog</code>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Clear", callback_data=f"st:other:{chat_id}:logchan:clear")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"st:other:{chat_id}")],
    ])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ----------------------------- main dispatcher --------------------------------

_OTHER_RENDERERS = {
    "topic": render_other_topic,
    "banned": render_other_banned,
    "recurring": render_other_recurring,
    "members": render_other_members,
    "masked": render_other_masked,
    "discussion": render_other_discussion,
    "personal": render_other_personal,
    "magic": render_other_magic,
    "msglen": render_other_msglen,
    "channels": render_other_channels,
    "perms": render_other_perms,
    "logchan": render_other_logchan,
}


async def handle_other(q, context, chat_id: int, sub: str, parts: list) -> None:
    """Dispatch all `st:other:<chat_id>:<sub>[:<arg>...]` callbacks."""
    if not sub:
        await render_other(q, chat_id)
        return
    arg = parts[4] if len(parts) > 4 else ""
    arg2 = parts[5] if len(parts) > 5 else ""

    # tab-specific actions ----------------------------------------------------
    if sub == "topic" and arg == "clear":
        await set_setting(chat_id, "default_topic_id", 0)
        await render_other_topic(q, chat_id); return
    if sub == "banned" and arg == "clear":
        await db_exec("DELETE FROM blacklist WHERE chat_id=?", (chat_id,))
        await render_other_banned(q, chat_id); return
    if sub == "recurring" and arg == "clear":
        await db_exec("DELETE FROM recurring_msgs WHERE chat_id=?", (chat_id,))
        await render_other_recurring(q, chat_id); return
    if sub == "members" and arg in ("join", "leave"):
        col = "members_join_msg" if arg == "join" else "members_leave_msg"
        await _toggle_setting(chat_id, col)
        await render_other_members(q, chat_id); return
    if sub == "masked" and arg == "clear":
        await db_exec("DELETE FROM masked_users WHERE chat_id=?", (chat_id,))
        await render_other_masked(q, chat_id); return
    if sub == "discussion" and arg == "clear":
        await set_setting(chat_id, "discussion_chat_id", 0)
        await render_other_discussion(q, chat_id); return
    if sub == "personal" and arg == "toggle":
        await _toggle_setting(chat_id, "personal_cmds_on")
        await render_other_personal(q, chat_id); return
    if sub == "personal" and arg == "clear":
        await db_exec("DELETE FROM personal_cmds WHERE chat_id=?", (chat_id,))
        await render_other_personal(q, chat_id); return
    if sub == "magic" and arg == "toggle":
        await _toggle_setting(chat_id, "magic_on")
        await render_other_magic(q, chat_id); return
    if sub == "magic" and arg == "clear":
        await db_exec("DELETE FROM magic_stickers WHERE chat_id=?", (chat_id,))
        await render_other_magic(q, chat_id); return
    if sub == "msglen" and arg.isdigit():
        await set_setting(chat_id, "max_msg_len", int(arg))
        await render_other_msglen(q, chat_id); return
    if sub == "channels" and arg == "toggle":
        await _toggle_setting(chat_id, "channels_block")
        await render_other_channels(q, chat_id); return
    if sub == "channels" and arg == "clear":
        await db_exec("DELETE FROM blocked_channels WHERE chat_id=?", (chat_id,))
        await render_other_channels(q, chat_id); return
    if sub == "perms" and arg == "toggle":
        await _toggle_setting(chat_id, "perms_admins_only")
        await render_other_perms(q, chat_id); return
    if sub == "logchan" and arg == "clear":
        await set_setting(chat_id, "log_channel_id", 0)
        await render_other_logchan(q, chat_id); return

    renderer = _OTHER_RENDERERS.get(sub)
    if renderer:
        await renderer(q, chat_id)
    else:
        await render_other(q, chat_id)
    _ = arg2  # reserved for future deeper sub-routes


# ----------------------------- commands --------------------------------------

async def _other_cmd_settopic(update, context):
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    msg = update.effective_message
    tid = 0
    if context.args and context.args[0].isdigit():
        tid = int(context.args[0])
    elif msg.message_thread_id:
        tid = int(msg.message_thread_id)
    elif msg.reply_to_message and getattr(msg.reply_to_message, "message_thread_id", None):
        tid = int(msg.reply_to_message.message_thread_id)
    if not tid:
        await msg.reply_text("Usage: /settopic <id>  (or run inside a topic, optionally as a reply).")
        return
    await set_setting(chat.id, "default_topic_id", tid)
    await msg.reply_text(f"✅ Default topic set to <code>{tid}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_setmaxlen(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await msg.reply_text("Usage: /setmaxlen <chars>  (0 to disable).")
        return
    n = max(0, int(context.args[0]))
    if n > 0 and n < 10:
        await msg.reply_text("Limit too small. Use 0 to disable, otherwise ≥10.")
        return
    await set_setting(update.effective_chat.id, "max_msg_len", n)
    await msg.reply_text(f"✅ Max length set to <b>{n or 'OFF'}</b>.", parse_mode=ParseMode.HTML)


async def _other_cmd_setdiscussion(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await msg.reply_text("Usage: /setdiscussion <chat_id>")
        return
    await set_setting(update.effective_chat.id, "discussion_chat_id", int(context.args[0]))
    await msg.reply_text("✅ Discussion group linked.")


async def _other_cmd_cleardiscussion(update, context):
    if not await _require_admin(update, context):
        return
    await set_setting(update.effective_chat.id, "discussion_chat_id", 0)
    await update.effective_message.reply_text("✅ Discussion group cleared.")


async def _other_cmd_setlog(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    chat = update.effective_chat
    target = None
    if context.args and context.args[0].lstrip("-").isdigit():
        target = int(context.args[0])
    elif chat.type == ChatType.CHANNEL:
        target = chat.id
    if target is None:
        await msg.reply_text("Usage: /setlog <channel_id>  (or run inside the channel).")
        return
    await set_setting(chat.id if chat.type != ChatType.CHANNEL else chat.id, "log_channel_id", target)
    await msg.reply_text(f"✅ Log channel set to <code>{target}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_clearlog(update, context):
    if not await _require_admin(update, context):
        return
    await set_setting(update.effective_chat.id, "log_channel_id", 0)
    await update.effective_message.reply_text("✅ Log channel cleared.")


# personal commands -----------------------------------------------------------
_PERSONAL_NAME_RE = re.compile(r"^[a-zA-Z0-9_]{1,32}$")


def _msg_media(msg):
    if not msg:
        return None, None
    if msg.sticker:
        return msg.sticker.file_id, "sticker"
    if msg.animation:
        return msg.animation.file_id, "animation"
    if msg.photo:
        return msg.photo[-1].file_id, "photo"
    if msg.video:
        return msg.video.file_id, "video"
    if msg.document:
        return msg.document.file_id, "document"
    if msg.audio:
        return msg.audio.file_id, "audio"
    if msg.voice:
        return msg.voice.file_id, "voice"
    return None, None


async def _other_cmd_addcmd(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    chat = update.effective_chat
    if not context.args:
        await msg.reply_text("Usage: /addcmd <name> <reply text>  (or reply to media with /addcmd <name>)")
        return
    name = context.args[0].lstrip("/!").lower()
    if not _PERSONAL_NAME_RE.match(name):
        await msg.reply_text("Invalid name. Use a-z, 0-9, _ (max 32).")
        return
    response_text = " ".join(context.args[1:]).strip()
    file_id, ftype = _msg_media(msg.reply_to_message)
    if not response_text and not file_id and msg.reply_to_message:
        response_text = capture_html(msg.reply_to_message)
    if not response_text and not file_id:
        await msg.reply_text("Provide reply text after the name, or reply to a message/media.")
        return
    await db_exec(
        "INSERT OR REPLACE INTO personal_cmds(chat_id,name,response,file_id,file_type,created_by,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (chat.id, name, response_text or "", file_id, ftype, update.effective_user.id, now_ts()),
    )
    await msg.reply_text(f"✅ Saved <code>!{html.escape(name)}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_delcmd(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("Usage: /delcmd <name>")
        return
    name = context.args[0].lstrip("/!").lower()
    cur = await db_one("SELECT 1 AS x FROM personal_cmds WHERE chat_id=? AND name=?", (update.effective_chat.id, name))
    if not cur:
        await msg.reply_text("No such command.")
        return
    await db_exec("DELETE FROM personal_cmds WHERE chat_id=? AND name=?", (update.effective_chat.id, name))
    await msg.reply_text(f"✅ Removed <code>!{html.escape(name)}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_listcmds(update, context):
    rows = await db_all("SELECT name FROM personal_cmds WHERE chat_id=? ORDER BY name", (update.effective_chat.id,))
    if not rows:
        await update.effective_message.reply_text("No personal commands defined.")
        return
    items = ", ".join(f"!{r['name']}" for r in rows)
    await update.effective_message.reply_text(f"Personal commands ({len(rows)}):\n{items}")


# magic stickers --------------------------------------------------------------

async def _other_cmd_addsticker(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    rep = msg.reply_to_message
    if not rep or not (rep.sticker or rep.animation):
        await msg.reply_text("Reply to a sticker or GIF with /addsticker <reply text>")
        return
    file_id = (rep.sticker or rep.animation).file_id
    is_gif = 1 if rep.animation else 0
    response = " ".join(context.args).strip()
    if not response:
        await msg.reply_text("Provide a reply text after /addsticker.")
        return
    await db_exec(
        "INSERT OR REPLACE INTO magic_stickers(chat_id,sticker_id,response,is_gif,created_at) VALUES (?,?,?,?,?)",
        (update.effective_chat.id, file_id, response, is_gif, now_ts()),
    )
    await msg.reply_text("✅ Magic reply saved.")


async def _other_cmd_delsticker(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    rep = msg.reply_to_message
    if not rep or not (rep.sticker or rep.animation):
        await msg.reply_text("Reply to the sticker/GIF with /delsticker")
        return
    file_id = (rep.sticker or rep.animation).file_id
    await db_exec("DELETE FROM magic_stickers WHERE chat_id=? AND sticker_id=?", (update.effective_chat.id, file_id))
    await msg.reply_text("✅ Removed.")


async def _other_cmd_liststickers(update, context):
    rows = await db_all(
        "SELECT response, is_gif FROM magic_stickers WHERE chat_id=? LIMIT 30", (update.effective_chat.id,)
    )
    if not rows:
        await update.effective_message.reply_text("No magic stickers/GIFs configured.")
        return
    lines = [f"{'🎞' if r['is_gif'] else '🩹'} {(r['response'] or '')[:60]}" for r in rows]
    await update.effective_message.reply_text(f"Magic items ({len(rows)}):\n" + "\n".join(lines))


# recurring messages ----------------------------------------------------------

async def _other_cmd_addrecurring(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if len(context.args) < 2:
        await msg.reply_text("Usage: /addrecurring <interval> <message>\nExample: /addrecurring 30m Read the rules!")
        return
    secs = parse_duration(context.args[0])
    if not secs or secs < 60:
        await msg.reply_text("Interval too short. Minimum 1m. Examples: 30m, 2h, 1d.")
        return
    text = " ".join(context.args[1:]).strip()
    if not text:
        await msg.reply_text("Message text is required.")
        return
    chat_id = update.effective_chat.id
    row = await db_one("SELECT COALESCE(MAX(rid),0)+1 AS n FROM recurring_msgs WHERE chat_id=?", (chat_id,))
    rid = int(row["n"]) if row else 1
    await db_exec(
        "INSERT INTO recurring_msgs(chat_id,rid,text,interval_seconds,last_run,enabled,created_at) "
        "VALUES (?,?,?,?,?,1,?)",
        (chat_id, rid, text, int(secs), now_ts(), now_ts()),
    )
    await msg.reply_text(f"✅ Added recurring #{rid} every {_format_duration(int(secs))}.")


async def _other_cmd_delrecurring(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args or not context.args[0].isdigit():
        await msg.reply_text("Usage: /delrecurring <id>")
        return
    rid = int(context.args[0])
    await db_exec("DELETE FROM recurring_msgs WHERE chat_id=? AND rid=?", (update.effective_chat.id, rid))
    await msg.reply_text(f"✅ Removed #{rid}.")


async def _other_cmd_togglerecurring(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args or not context.args[0].isdigit():
        await msg.reply_text("Usage: /togglerecurring <id>")
        return
    rid = int(context.args[0])
    row = await db_one("SELECT enabled FROM recurring_msgs WHERE chat_id=? AND rid=?", (update.effective_chat.id, rid))
    if not row:
        await msg.reply_text("No such recurring message.")
        return
    new = 0 if int(row["enabled"]) else 1
    await db_exec("UPDATE recurring_msgs SET enabled=? WHERE chat_id=? AND rid=?", (new, update.effective_chat.id, rid))
    await msg.reply_text(f"✅ Recurring #{rid} is now {'ON' if new else 'OFF'}.")


async def _other_cmd_listrecurring(update, context):
    rows = await db_all(
        "SELECT rid, text, interval_seconds, enabled FROM recurring_msgs WHERE chat_id=? ORDER BY rid",
        (update.effective_chat.id,),
    )
    if not rows:
        await update.effective_message.reply_text("No recurring messages.")
        return
    lines = []
    for r in rows:
        mark = "✅" if r["enabled"] else "⏸"
        preview = (r["text"] or "")[:50].replace("\n", " ")
        lines.append(f"{mark} #{r['rid']} every {_format_duration(r['interval_seconds'])}: {preview}")
    await update.effective_message.reply_text("\n".join(lines))


# masked users ----------------------------------------------------------------

async def _other_cmd_maskuser(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    target_id, reason = await _resolve_target_and_reason(update, context)
    if not target_id:
        await msg.reply_text("Reply to a user, or use /maskuser @user [duration] [reason]")
        return
    until = 0
    if reason:
        first, _, rest = reason.partition(" ")
        secs = parse_duration(first)
        if secs:
            until = now_ts() + secs
            reason = rest.strip()
    await db_exec(
        "INSERT OR REPLACE INTO masked_users(chat_id,user_id,until_ts,reason,created_at) VALUES (?,?,?,?,?)",
        (update.effective_chat.id, target_id, until, reason or "", now_ts()),
    )
    suffix = "permanently" if not until else f"for {_format_duration(until - now_ts())}"
    await msg.reply_text(f"🥸 Masked <code>{target_id}</code> {suffix}.", parse_mode=ParseMode.HTML)


async def _other_cmd_unmaskuser(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    target_id, _ = await _resolve_target_and_reason(update, context)
    if not target_id:
        await msg.reply_text("Reply to a user, or use /unmaskuser @user")
        return
    await db_exec("DELETE FROM masked_users WHERE chat_id=? AND user_id=?", (update.effective_chat.id, target_id))
    await msg.reply_text(f"✅ Unmasked <code>{target_id}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_listmasked(update, context):
    rows = await db_all(
        "SELECT user_id, until_ts, reason FROM masked_users WHERE chat_id=? ORDER BY user_id",
        (update.effective_chat.id,),
    )
    if not rows:
        await update.effective_message.reply_text("No masked users.")
        return
    now = now_ts()
    lines = []
    for r in rows:
        ut = int(r["until_ts"] or 0)
        if ut and ut < now:
            continue
        left = "permanent" if not ut else f"{_format_duration(max(0, ut - now))} left"
        reason = (r["reason"] or "").strip()
        lines.append(f"• {r['user_id']} ({left}){(' — ' + reason) if reason else ''}")
    await update.effective_message.reply_text("\n".join(lines) or "No active masks.")


# blocked channels ------------------------------------------------------------

async def _other_cmd_blockchannel(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await msg.reply_text("Usage: /blockchannel <channel_id>")
        return
    cid = int(context.args[0])
    await db_exec(
        "INSERT OR REPLACE INTO blocked_channels(chat_id,channel_id,title,created_at) VALUES (?,?,?,?)",
        (update.effective_chat.id, cid, "", now_ts()),
    )
    await msg.reply_text(f"✅ Blocked channel <code>{cid}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_unblockchannel(update, context):
    if not await _require_admin(update, context):
        return
    msg = update.effective_message
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await msg.reply_text("Usage: /unblockchannel <channel_id>")
        return
    cid = int(context.args[0])
    await db_exec("DELETE FROM blocked_channels WHERE chat_id=? AND channel_id=?", (update.effective_chat.id, cid))
    await msg.reply_text(f"✅ Unblocked <code>{cid}</code>.", parse_mode=ParseMode.HTML)


async def _other_cmd_listblockedchannels(update, context):
    rows = await db_all(
        "SELECT channel_id, title FROM blocked_channels WHERE chat_id=?", (update.effective_chat.id,)
    )
    if not rows:
        await update.effective_message.reply_text("No blocked channels.")
        return
    lines = [f"• {r['channel_id']} {r['title'] or ''}" for r in rows]
    await update.effective_message.reply_text("\n".join(lines))


# ----------------------------- pipelines / handlers --------------------------

async def _other_msg_pipeline(update, context):
    """Runs on every group text/media message: enforce length, masks, channels,
    handle personal commands and magic stickers."""
    msg = update.effective_message
    chat = update.effective_chat
    if msg is None or chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    user = update.effective_user

    # 1) channel posts (sender_chat) blocking ---------------------------------
    sc = msg.sender_chat
    if sc and sc.id != chat.id:
        if int(await _get_other_setting(chat.id, "channels_block", 0) or 0):
            try:
                await msg.delete()
            except TelegramError:
                pass
            return
        bc = await db_one(
            "SELECT 1 AS x FROM blocked_channels WHERE chat_id=? AND channel_id=?",
            (chat.id, sc.id),
        )
        if bc:
            try:
                await msg.delete()
            except TelegramError:
                pass
            return

    if user is None:
        return

    # 2) masked-user silent delete -------------------------------------------
    mrow = await db_one(
        "SELECT until_ts FROM masked_users WHERE chat_id=? AND user_id=?", (chat.id, user.id)
    )
    if mrow is not None:
        ut = int(mrow["until_ts"] or 0)
        if not ut or ut > now_ts():
            try:
                await msg.delete()
            except TelegramError:
                pass
            return
        else:
            await db_exec(
                "DELETE FROM masked_users WHERE chat_id=? AND user_id=?", (chat.id, user.id)
            )

    # 3) length enforcement (skip admins) ------------------------------------
    max_len = int(await _get_other_setting(chat.id, "max_msg_len", 0) or 0)
    if max_len > 0:
        body = msg.text or msg.caption or ""
        if len(body) > max_len and not await _is_chat_admin(chat.id, user.id, context.bot):
            try:
                await msg.delete()
            except TelegramError:
                pass
            try:
                warn = await context.bot.send_message(
                    chat.id,
                    f"📏 {user.mention_html()} your message exceeds {max_len} chars.",
                    parse_mode=ParseMode.HTML,
                )
                context.application.create_task(_other_delete_later(context.bot, warn.chat.id, warn.message_id, 6))
            except TelegramError:
                pass
            return

    # 4) magic stickers / GIFs -----------------------------------------------
    if (msg.sticker or msg.animation) and int(await _get_other_setting(chat.id, "magic_on", 1) or 0):
        fid = (msg.sticker or msg.animation).file_id
        row = await db_one(
            "SELECT response FROM magic_stickers WHERE chat_id=? AND sticker_id=?",
            (chat.id, fid),
        )
        if row and row["response"]:
            try:
                await msg.reply_text(row["response"], parse_mode=ParseMode.HTML)
            except TelegramError:
                try:
                    await msg.reply_text(row["response"])
                except TelegramError:
                    pass

    # 5) personal commands (!name or /name) ----------------------------------
    txt = (msg.text or "").strip()
    if txt and txt[0] in ("!", "/") and int(await _get_other_setting(chat.id, "personal_cmds_on", 1) or 0):
        first = txt.split()[0][1:]
        # strip @botname suffix
        if "@" in first:
            first = first.split("@", 1)[0]
        first = first.lower()
        if _PERSONAL_NAME_RE.match(first):
            row = await db_one(
                "SELECT response, file_id, file_type FROM personal_cmds WHERE chat_id=? AND name=?",
                (chat.id, first),
            )
            if row:
                response = row["response"] or ""
                file_id = row["file_id"]
                ftype = row["file_type"]
                try:
                    if file_id and ftype == "sticker":
                        await msg.reply_sticker(file_id)
                        if response:
                            await msg.reply_text(response, parse_mode=ParseMode.HTML)
                    elif file_id and ftype == "animation":
                        await msg.reply_animation(file_id, caption=response or None, parse_mode=ParseMode.HTML)
                    elif file_id and ftype == "photo":
                        await msg.reply_photo(file_id, caption=response or None, parse_mode=ParseMode.HTML)
                    elif file_id and ftype == "video":
                        await msg.reply_video(file_id, caption=response or None, parse_mode=ParseMode.HTML)
                    elif file_id and ftype == "document":
                        await msg.reply_document(file_id, caption=response or None, parse_mode=ParseMode.HTML)
                    elif file_id and ftype == "audio":
                        await msg.reply_audio(file_id, caption=response or None, parse_mode=ParseMode.HTML)
                    elif file_id and ftype == "voice":
                        await msg.reply_voice(file_id, caption=response or None, parse_mode=ParseMode.HTML)
                    elif response:
                        await msg.reply_text(response, parse_mode=ParseMode.HTML)
                except TelegramError:
                    try:
                        if response:
                            await msg.reply_text(response)
                    except TelegramError:
                        pass


async def _other_delete_later(bot, chat_id: int, message_id: int, delay: int) -> None:
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id, message_id)
    except TelegramError:
        pass


async def _other_recurring_tick(context):
    """JobQueue tick: scan recurring_msgs and send what's due."""
    # Recurring messages are admin-authored — bypass the live translator.
    try:
        _skip_translate.set(True)
    except Exception:
        pass
    now = now_ts()
    rows = await db_all("SELECT chat_id,rid,text,interval_seconds,last_run,enabled FROM recurring_msgs")
    for r in rows:
        if not int(r["enabled"]):
            continue
        if now - int(r["last_run"] or 0) < int(r["interval_seconds"]):
            continue
        topic = int(await _get_other_setting(r["chat_id"], "default_topic_id", 0) or 0)
        try:
            kwargs = {}
            if topic:
                kwargs["message_thread_id"] = topic
            await context.bot.send_message(
                r["chat_id"], r["text"], parse_mode=ParseMode.HTML, **kwargs,
            )
        except TelegramError as e:
            log.warning("recurring send failed for %s/#%s: %s", r["chat_id"], r["rid"], e)
        await db_exec(
            "UPDATE recurring_msgs SET last_run=? WHERE chat_id=? AND rid=?",
            (now, r["chat_id"], r["rid"]),
        )


def _other_schedule_recurring(app) -> None:
    if app.job_queue is None:
        return
    try:
        app.job_queue.run_repeating(_other_recurring_tick, interval=60, first=30, name="other_recurring")
    except Exception as e:
        log.warning("schedule recurring failed: %s", e)


def _register_other_handlers(app) -> None:
    app.add_handler(CommandHandler("settopic", _other_cmd_settopic))
    app.add_handler(CommandHandler("setmaxlen", _other_cmd_setmaxlen))
    app.add_handler(CommandHandler("setdiscussion", _other_cmd_setdiscussion))
    app.add_handler(CommandHandler("cleardiscussion", _other_cmd_cleardiscussion))
    app.add_handler(CommandHandler("setlog", _other_cmd_setlog))
    app.add_handler(CommandHandler("clearlog", _other_cmd_clearlog))
    app.add_handler(CommandHandler("addcmd", _other_cmd_addcmd))
    app.add_handler(CommandHandler("delcmd", _other_cmd_delcmd))
    app.add_handler(CommandHandler("listcmds", _other_cmd_listcmds))
    app.add_handler(CommandHandler("addsticker", _other_cmd_addsticker))
    app.add_handler(CommandHandler("delsticker", _other_cmd_delsticker))
    app.add_handler(CommandHandler("liststickers", _other_cmd_liststickers))
    app.add_handler(CommandHandler("addrecurring", _other_cmd_addrecurring))
    app.add_handler(CommandHandler("delrecurring", _other_cmd_delrecurring))
    app.add_handler(CommandHandler("togglerecurring", _other_cmd_togglerecurring))
    app.add_handler(CommandHandler("listrecurring", _other_cmd_listrecurring))
    app.add_handler(CommandHandler("maskuser", _other_cmd_maskuser))
    app.add_handler(CommandHandler("unmaskuser", _other_cmd_unmaskuser))
    app.add_handler(CommandHandler("listmasked", _other_cmd_listmasked))
    app.add_handler(CommandHandler("blockchannel", _other_cmd_blockchannel))
    app.add_handler(CommandHandler("unblockchannel", _other_cmd_unblockchannel))
    app.add_handler(CommandHandler("listblockedchannels", _other_cmd_listblockedchannels))
    # Pipeline runs early (group=-50) so it happens before other group filters.
    app.add_handler(
        MessageHandler(
            (filters.ChatType.GROUPS) & ~filters.StatusUpdate.ALL,
            _other_msg_pipeline,
        ),
        group=-50,
    )



ALL_COMMANDS = ['settopic', 'setmaxlen', 'setdiscussion', 'cleardiscussion', 'setlog', 'clearlog', 'addcmd', 'delcmd', 'listcmds', 'addsticker', 'delsticker', 'liststickers', 'addrecurring', 'delrecurring', 'togglerecurring', 'listrecurring', 'maskuser', 'unmaskuser', 'listmasked', 'blockchannel', 'unblockchannel', 'listblockedchannels', 'start', 'help', 'settings', 'reload', 'ban', 'tban', 'kick', 'unban', 'mute', 'tmute', 'unmute', 'promote', 'demote', 'warn', 'unwarn', 'warns', 'delwarn', 'resetwarn', 'setwarnlimit', 'setwarnaction', 'pin', 'editpin', 'delpin', 'repin', 'pinned', 'send', 'broadcast', 'intervention', 'logdel', 'del', 'id', 'info', 'infopvt', 'me', 'stats', 'rules', 'setrules', 'admins', 'inviters', 'topadders', 'staff', 'report', 'admin', 'geturl', 'addblacklist', 'delblacklist', 'blacklist', 'block', 'unblock', 'blocklist', 'addwhitelist', 'delwhitelist', 'inactives', 'list', 'graphic', 'trend', 'save', 'get', 'notes', 'saved', 'clear', 'clearnotes', 'filter', 'stop', 'stopall', 'filters', 'lock', 'unlock', 'locks', 'locktypes', 'disable', 'enable', 'disabled', 'disableable', 'newfed', 'delfed', 'joinfed', 'leavefed', 'fban', 'unfban', 'fedinfo', 'fedbanlist', 'connect', 'disconnect', 'connection', 'addsudo', 'delsudo', 'sudolist', 'gban', 'ungban', 'gbanlist', 'sban', 'skick', 'smute', 'dwarn', 'kickme', 'leave', 'listadmins', 'title', 'purge', 'zombies', 'afk', 'dice', 'coin', '8ball', 'pick', 'decide', 'calc', 'qr', 'shorten', 'reverse', 'runs', 'throw', 'ud', 'paste', 'wiki', 'chatinfo', 'pingmsg', 'uptime', 'speed', 'helpcard', 'helpcards', 'addblword', 'rmblword', 'blwords', 'slowmode', 'tagall', 'admincall', 'joke', 'fact', 'quote', 'time', 'remind', 'whois', 'setrules2', 'clearrules', 'raidon', 'raidoff', 'warnstop', 'warntop', 'logsview', 'say', 'echo', 'qpoll', 'owner', 'captchaon', 'captchaoff']

async def cmd_allcommands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show every command registered by this bot."""
    msg = update.effective_message
    if msg is None:
        return
    lines = ["📚 <b>All commands</b>", ""]
    for name in ALL_COMMANDS:
        lines.append(f"/{name}")
    # Telegram message text limit is ~4096 chars.
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > 3800:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    for chunk in chunks:
        await msg.reply_text(chunk, parse_mode=ParseMode.HTML)

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_post_init).build()
    app._started_at = int(time.time())  # used by /uptime
    _register_other_handlers(app)

    # Capture the triggering user_id of every Update into a ContextVar so that
    # _maybe_translate_for_chat can translate every outgoing reply into the
    # user's saved language (welcome / goodbye / warns / captcha / antispam /
    # antiflood / ban / mute / kick / help / settings / etc.). Group=-100 so it
    # runs before every other handler; different group => does not consume the
    # update.
    app.add_handler(TypeHandler(Update, _capture_trigger_user), group=-100)

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("allcommands", cmd_allcommands))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("reload", cmd_reload))

    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("tban", cmd_tban))
    app.add_handler(CommandHandler("kick", cmd_kick))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("tmute", cmd_tmute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("promote", cmd_promote))
    app.add_handler(CommandHandler("demote", cmd_demote))

    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("unwarn", cmd_unwarn))
    app.add_handler(CommandHandler("warns", cmd_warns))
    app.add_handler(CommandHandler("delwarn", cmd_delwarn))
    app.add_handler(CommandHandler("resetwarn", cmd_resetwarn))
    app.add_handler(CommandHandler("setwarnlimit", cmd_setwarnlimit))
    app.add_handler(CommandHandler("setwarnaction", cmd_setwarnaction))

    app.add_handler(CommandHandler("pin", cmd_pin))
    app.add_handler(CommandHandler("editpin", cmd_editpin))
    app.add_handler(CommandHandler("delpin", cmd_delpin))
    app.add_handler(CommandHandler("repin", cmd_repin))
    app.add_handler(CommandHandler("pinned", cmd_pinned))

    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("intervention", cmd_intervention))
    app.add_handler(CommandHandler("logdel", cmd_logdel))
    app.add_handler(CommandHandler("del", cmd_del))

    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("infopvt", cmd_infopvt))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("setrules", cmd_setrules))
    app.add_handler(CommandHandler("admins", cmd_admins))
    app.add_handler(CommandHandler("inviters", cmd_inviters))
    app.add_handler(CommandHandler("topadders", cmd_inviters))
    app.add_handler(CommandHandler("staff", cmd_staff))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("admin", cmd_report))
    app.add_handler(CommandHandler("geturl", cmd_geturl))

    app.add_handler(CommandHandler("addblacklist", cmd_addblacklist))
    app.add_handler(CommandHandler("delblacklist", cmd_delblacklist))
    app.add_handler(CommandHandler("blacklist", cmd_blacklist))
    app.add_handler(CommandHandler("block", cmd_block))
    app.add_handler(CommandHandler("unblock", cmd_unblock))
    app.add_handler(CommandHandler("blocklist", cmd_blocklist))
    app.add_handler(CommandHandler("addwhitelist", cmd_addwhitelist))
    app.add_handler(CommandHandler("delwhitelist", cmd_delwhitelist))

    app.add_handler(CommandHandler("inactives", cmd_inactives))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("graphic", cmd_graphic))
    app.add_handler(CommandHandler("trend", cmd_trend))

    # Notes / Saved-messages
    app.add_handler(CommandHandler("save", cmd_save))
    app.add_handler(CommandHandler("get", cmd_get))
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("saved", cmd_notes))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("clearnotes", cmd_clearall_notes))

    # Filters
    app.add_handler(CommandHandler("filter", cmd_filter))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("stopall", cmd_stopall))
    app.add_handler(CommandHandler("filters", cmd_filters))

    # Locks
    app.add_handler(CommandHandler("lock", cmd_lock))
    app.add_handler(CommandHandler("unlock", cmd_unlock))
    app.add_handler(CommandHandler("locks", cmd_locks))
    app.add_handler(CommandHandler("locktypes", cmd_locktypes))

    # Disable / Enable
    app.add_handler(CommandHandler("disable", cmd_disable))
    app.add_handler(CommandHandler("enable", cmd_enable))
    app.add_handler(CommandHandler("disabled", cmd_disabled))
    app.add_handler(CommandHandler("disableable", cmd_disableable))

    # Federations
    app.add_handler(CommandHandler("newfed", cmd_newfed))
    app.add_handler(CommandHandler("delfed", cmd_delfed))
    app.add_handler(CommandHandler("joinfed", cmd_joinfed))
    app.add_handler(CommandHandler("leavefed", cmd_leavefed))
    app.add_handler(CommandHandler("fban", cmd_fban))
    app.add_handler(CommandHandler("unfban", cmd_unfban))
    app.add_handler(CommandHandler("fedinfo", cmd_fedinfo))
    app.add_handler(CommandHandler("fedbanlist", cmd_fedbanlist))

    # PM connect
    app.add_handler(CommandHandler("connect", cmd_connect))
    app.add_handler(CommandHandler("disconnect", cmd_disconnect))
    app.add_handler(CommandHandler("connection", cmd_connection))

    # Sudo / Global ban
    app.add_handler(CommandHandler("addsudo", cmd_addsudo))
    app.add_handler(CommandHandler("delsudo", cmd_delsudo))
    app.add_handler(CommandHandler("sudolist", cmd_sudolist))
    app.add_handler(CommandHandler("gban", cmd_gban))
    app.add_handler(CommandHandler("ungban", cmd_ungban))
    app.add_handler(CommandHandler("gbanlist", cmd_gbanlist))

    # Silent / mass actions
    app.add_handler(CommandHandler("sban", cmd_sban))
    app.add_handler(CommandHandler("skick", cmd_skick))
    app.add_handler(CommandHandler("smute", cmd_smute))
    app.add_handler(CommandHandler("dwarn", cmd_dwarn))
    app.add_handler(CommandHandler("kickme", cmd_kickme))
    app.add_handler(CommandHandler("leave", cmd_leave))
    app.add_handler(CommandHandler("listadmins", cmd_listadmins))
    app.add_handler(CommandHandler("title", cmd_promote_title))
    app.add_handler(CommandHandler("purge", cmd_purge))
    app.add_handler(CommandHandler("zombies", cmd_zombies))

    # AFK
    app.add_handler(CommandHandler("afk", cmd_afk))

    # Mini tools
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CommandHandler("coin", cmd_coin))
    app.add_handler(CommandHandler("8ball", cmd_8ball))
    app.add_handler(CommandHandler("pick", cmd_pick))
    app.add_handler(CommandHandler("decide", cmd_decide))
    app.add_handler(CommandHandler("calc", cmd_calc))
    app.add_handler(CommandHandler("qr", cmd_qr))
    app.add_handler(CommandHandler("shorten", cmd_shorten))
    app.add_handler(CommandHandler("reverse", cmd_reverse))
    app.add_handler(CommandHandler("runs", cmd_runs))
    app.add_handler(CommandHandler("throw", cmd_throw))
    app.add_handler(CommandHandler("ud", cmd_ud))
    app.add_handler(CommandHandler("paste", cmd_paste))
    app.add_handler(CommandHandler("wiki", cmd_wiki))
    app.add_handler(CommandHandler("chatinfo", cmd_chatinfo))
    app.add_handler(CommandHandler("pingmsg", cmd_pingmsg))
    app.add_handler(CommandHandler("uptime", cmd_uptime))
    app.add_handler(CommandHandler("speed", cmd_speed))
    app.add_handler(CommandHandler("helpcard", cmd_helpcards))
    app.add_handler(CommandHandler("helpcards", cmd_helpcards))
    app.add_handler(CommandHandler("addblword", cmd_addblword))
    app.add_handler(CommandHandler("rmblword", cmd_rmblword))
    app.add_handler(CommandHandler("blwords", cmd_blwords))
    app.add_handler(CommandHandler("slowmode", cmd_slowmode))
    app.add_handler(CommandHandler("tagall", cmd_tagall))
    app.add_handler(CommandHandler("admincall", cmd_admincall))
    app.add_handler(CommandHandler("joke", cmd_joke))
    app.add_handler(CommandHandler("fact", cmd_fact))
    app.add_handler(CommandHandler("quote", cmd_quote))
    app.add_handler(CommandHandler("time", cmd_time))
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(CommandHandler("whois", cmd_whois))
    app.add_handler(CommandHandler("setrules2", cmd_setrules2))
    app.add_handler(CommandHandler("clearrules", cmd_clearrules))
    app.add_handler(CommandHandler("raidon", cmd_raid_on))
    app.add_handler(CommandHandler("raidoff", cmd_raid_off))
    app.add_handler(CommandHandler("warnstop", cmd_warnstop))
    app.add_handler(CommandHandler("warntop", cmd_warnstop))  # legacy alias
    app.add_handler(CommandHandler("logsview", cmd_logsview))
    app.add_handler(CommandHandler("say", cmd_say))
    app.add_handler(CommandHandler("echo", cmd_echo))
    app.add_handler(CommandHandler("qpoll", cmd_qpoll))
    app.add_handler(CommandHandler("owner", cmd_owner))
    app.add_handler(CommandHandler("captchaon", cmd_captcha_on))
    app.add_handler(CommandHandler("captchaoff", cmd_captcha_off))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION), blacklist_pipeline), group=7)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, raid_pipeline), group=7)
    app.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, migration_handler), group=8)

    # Callback queries
    app.add_handler(CallbackQueryHandler(cb_dm_router, pattern=r"^dm:"))
    app.add_handler(CallbackQueryHandler(cb_help, pattern=r"^help:"))
    app.add_handler(CallbackQueryHandler(cb_settings, pattern=r"^st:"))
    app.add_handler(CallbackQueryHandler(cb_captcha, pattern=r"^cap:"))
    app.add_handler(CallbackQueryHandler(cb_approval, pattern=r"^app:"))
    app.add_handler(CallbackQueryHandler(cb_warns_reset, pattern=r"^warns:reset:"))
    app.add_handler(CallbackQueryHandler(cb_warn, pattern=r"^warn:"))
    app.add_handler(CallbackQueryHandler(cb_mute, pattern=r"^mute:"))
    app.add_handler(CallbackQueryHandler(cb_permissions, pattern=r"^perms:"))
    app.add_handler(CallbackQueryHandler(cb_perm_toggle, pattern=r"^ptog:"))
    app.add_handler(CallbackQueryHandler(cb_perm_save, pattern=r"^psave:"))
    app.add_handler(CallbackQueryHandler(cb_set_user_lang, pattern=r"^setulang:"))
    app.add_handler(CallbackQueryHandler(cb_inactives, pattern=r"^inact:"))
    app.add_handler(CallbackQueryHandler(cb_misc))

    # Chat member updates
    app.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))

    # Service-message cleanup
    app.add_handler(MessageHandler(filters.StatusUpdate.ALL, service_cleanup), group=1)

    # Federation / Global ban auto-enforce on join (must run on join service msg)
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, fed_join_enforcer),
        group=1,
    )
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, gban_join_enforcer),
        group=1,
    )

    # DM input capture (for welcome customize etc.)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, dm_input_capture), group=2)

    # Disabled-command interceptor — runs early to delete blocked commands.
    app.add_handler(
        MessageHandler(filters.COMMAND & filters.ChatType.GROUPS, disabled_pipeline),
        group=2,
    )

    # Locks pipeline — also early so blocked content disappears fast.
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL, locks_pipeline),
        group=2,
    )

    # Group message pipeline
    app.add_handler(
        MessageHandler(
            (filters.ChatType.GROUPS) & (~filters.StatusUpdate.ALL),
            message_pipeline,
        ),
        group=3,
    )
    # AFK return-detection / mention-notice
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL, afk_pipeline),
        group=4,
    )
    # Hashtag note shortcut + filter trigger pipeline.
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            hashtag_note_handler,
        ),
        group=5,
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL & ~filters.COMMAND,
            filters_pipeline,
        ),
        group=5,
    )

    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.ChatType.GROUPS, edited_pipeline), group=6)

    app.add_error_handler(on_error)

    log.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
