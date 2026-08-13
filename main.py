import logging, time, string, random, asyncio, os, fcntl, json, hmac, hashlib, re
from io import BytesIO
from html import escape
from typing import Optional
from datetime import datetime
from telegram import Update, TelegramObject, MessageEntity, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, BadRequest, NetworkError, Forbidden, TimedOut, RetryAfter
from telegram.request import HTTPXRequest
import aiohttp as _aiohttp
import database as db
from mst import get_bin_handler as get_bin_lookup_handler
from config import (BOT_TOKEN, OWNER_ID, VERSION, DEV_LINK, CHANNEL_USERNAME, CHANNEL_LINK, GROUP_LINK, SUPPORT_LINK, BOT_LINK, BOT_USERNAME, API_TIMEOUT, REFERRAL_CREDITS, LOCK_FILE, GATE_URLS, GATE_SITES, PREMIUM_GATES, FORCE_CHANNELS, get_bin_info, kb_result, tg_emoji, get_plan_emoji_id, get_random_live_emoji, E_CARD, E_USER, E_TIME, E_DEV, E_PRO, E_LIVE, E_DECLINED, E_ERRORS, E_PROGRESS, E_GATE, PLAN_EMOJIS, PRO_EMOJI_ID, BTN_ALL_EMOJI_ID, BTN_STOP_EMOJI_ID, PROG_GATE_EMOJI_ID, PROG_LIVE_EMOJI_ID, PROG_DEAD_EMOJI_ID, PROG_ERRORS_EMOJI_ID, PROG_PROGRESS_EMOJI_ID, CARD_EMOJI_ID, USER_EMOJI_ID, TIME_EMOJI_ID, DEV_EMOJI_ID, DECLINED_EMOJI_ID)
from sh import (cmd_sh, get_sh_handler, get_me_handler, _check_card_with_retry, SITE_RETRIES, SITE_TIMEOUT, run_mass_batch, create_msh_session, MSH_SESSIONS, cb_msh_result, cb_msh_stop, _load_sites, _load_proxies, probe_all_sites, get_working_sites, start_probe_background, stop_probe_background, _send_sticker, get_random_live_emoji, _bin_lookup, _bin_str_plain)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

PREMIUM_FILE = os.environ.get("PREMIUM_FILE", "premium_users.json")

def _save_premium_file(bot_data: dict) -> None:
    now = time.time(); all_users = bot_data.get("user_data", {}); premium = {}
    for uid_str, ud in all_users.items():
        plan = ud.get("plan", "TRIAL").upper(); expires = ud.get("expires", 0)
        if plan != "TRIAL" and expires > now:
            premium[uid_str] = {"plan": plan, "expires": expires, "name": ud.get("name", ""), "username": ud.get("username", ""), "last_receipt": ud.get("last_receipt", "")}
    try:
        with open(PREMIUM_FILE, "w", encoding="utf-8") as f: json.dump(premium, f, indent=2)
    except: pass

async def _save_premium(bot_data: dict) -> None:
    await asyncio.to_thread(_save_premium_file, bot_data)
    await db.save_all_now(bot_data.get("user_data", {}))

def _load_premium_file(bot_data: dict) -> None:
    if not os.path.exists(PREMIUM_FILE): return
    try:
        with open(PREMIUM_FILE, "r", encoding="utf-8") as f: saved = json.load(f)
    except: return
    now = time.time(); user_data = bot_data.setdefault("user_data", {})
    for uid_str, pdata in saved.items():
        expires = pdata.get("expires", 0)
        if expires <= now: continue
        plan = pdata.get("plan", "TRIAL").upper()
        if plan == "TRIAL": continue
        ud = user_data.setdefault(uid_str, {})
        ud["plan"] = plan; ud["expires"] = expires
        if pdata.get("name"): ud.setdefault("name", pdata["name"])
        if pdata.get("username"): ud.setdefault("username", pdata["username"])

FORCE_JOIN_LIST = []
_config_fc = [(u, l) for u, l in FORCE_CHANNELS]
for _fc_entry in FORCE_JOIN_LIST:
    _uname = _fc_entry[0]
    if not any(_uname == u for u, _ in _config_fc): _config_fc.append((_uname, _fc_entry[1]))
FORCE_JOIN_FULL = []
for _uname, _link in _config_fc: FORCE_JOIN_FULL.append((_uname, _link, f"📢 @{_uname}"))

_lock_file_handle = None
def acquire_instance_lock() -> bool:
    global _lock_file_handle
    try: _lock_file_handle = open(LOCK_FILE, "w"); fcntl.flock(_lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB); _lock_file_handle.write(str(os.getpid())); _lock_file_handle.flush(); return True
    except: return False

def release_instance_lock():
    global _lock_file_handle
    if _lock_file_handle:
        try: fcntl.flock(_lock_file_handle, fcntl.LOCK_UN); _lock_file_handle.close(); os.unlink(LOCK_FILE)
        except: pass
        _lock_file_handle = None

def B(text: str) -> str:
    bold_map = {'A':'𝗔','B':'𝗕','C':'𝗖','D':'𝗗','E':'𝗘','F':'𝗙','G':'𝗚','H':'𝗛','I':'𝗜','J':'𝗝','K':'𝗞','L':'𝗟','M':'𝗠','N':'𝗡','O':'𝗢','P':'𝗣','Q':'𝗤','R':'𝗥','S':'𝗦','T':'𝗧','U':'𝗨','V':'𝗩','W':'𝗪','X':'𝗫','Y':'𝗬','Z':'𝗭','a':'𝗮','b':'𝗯','c':'𝗰','d':'𝗱','e':'𝗲','f':'𝗳','g':'𝗴','h':'𝗵','i':'𝗶','j':'𝗷','k':'𝗸','l':'𝗹','m':'𝗺','n':'𝗻','o':'𝗼','p':'𝗽','q':'𝗾','r':'𝗿','s':'𝘀','t':'𝘁','u':'𝘂','v':'𝘃','w':'𝘄','x':'𝘅','y':'𝘆','z':'𝘇','0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵'}
    return "".join(bold_map.get(ch, ch) for ch in text)

class RawMarkup(TelegramObject):
    __slots__ = ("_data",)
    def __init__(self, inline_keyboard: list): super().__init__(); self._data = {"inline_keyboard": inline_keyboard}
    def to_dict(self, api_kwargs=None) -> dict: return self._data
    def to_json(self) -> str: return json.dumps(self._data)

def _btn(text: str, *, cb: str = None, url: str = None, style: str = None, icon: str = None) -> dict:
    d: dict = {"text": text}
    if cb: d["callback_data"] = cb
    if url: d["url"] = url
    if style: d["style"] = style
    if icon: d["icon_custom_emoji_id"] = icon
    return d

def get_styled_plan(raw_plan: str) -> str:
    p = raw_plan.upper()
    if p == "CORE": return B("Core")
    if p == "ELITE": return B("Elite")
    if p == "ROOT": return B("Root")
    return B("Trial")

def get_user_data(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> dict:
    uid = str(user_id)
    if "user_data" not in context.bot_data: context.bot_data["user_data"] = {}
    if uid not in context.bot_data["user_data"]:
        context.bot_data["user_data"][uid] = {"name": "User", "first_name": "User", "last_name": "", "username": "", "language_code": "en", "joined": datetime.now().strftime("%Y-%m-%d %H:%M"), "last_active": datetime.now().strftime("%Y-%m-%d %H:%M"), "credits": 150, "plan": "TRIAL", "expires": 0, "pre_premium_credits": 0, "total_refs": 0, "total_checks": 0, "approved_checks": 0, "declined_checks": 0, "last_gate": "N/A", "last_card": "N/A", "codes_redeemed": 0, "keys_redeemed": 0, "banned": False, "total_charged": 0}
    return context.bot_data["user_data"][uid]

def _update_user_meta(ud: dict, user) -> None:
    ud["first_name"] = user.first_name or "User"; ud["last_name"] = user.last_name or ""; ud["name"] = user.full_name or user.first_name or "User"; ud["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if user.username: ud["username"] = user.username

def is_user_premium(ud: dict) -> bool:
    raw_plan = ud.get("plan", "TRIAL").upper(); is_prem = raw_plan != "TRIAL"
    if is_prem and ud.get("expires", 0) <= time.time():
        saved = ud.get("pre_premium_credits", 0); ud["plan"] = "TRIAL"; ud["credits"] = max(saved, 0); ud["expires"] = 0; ud["pre_premium_credits"] = 0; return False
    return is_prem

SINGLE_CHECK_COOLDOWN = 25
def get_cooldown_remaining(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> float:
    store = context.bot_data.setdefault("cooldown_store", {}); last = store.get(user_id, 0); remaining = SINGLE_CHECK_COOLDOWN - (time.time() - last); return max(0.0, remaining)
def set_cooldown(user_id: int, context: ContextTypes.DEFAULT_TYPE): context.bot_data.setdefault("cooldown_store", {})[user_id] = time.time()
def gen_code(length: int = 10) -> str: return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
def gen_receipt() -> str: return f"Superman{random.randint(100000, 999999)}-CHK"

_REF_SECRET: bytes = BOT_TOKEN.encode("utf-8")
def _ref_token(user_id: int) -> str:
    msg = str(user_id).encode("utf-8"); sig = hmac.new(_REF_SECRET, msg, hashlib.sha256).hexdigest()[:16]; return f"{user_id}_{sig}"
def _verify_ref_token(token: str):
    try:
        uid_str, sig = token.rsplit("_", 1); uid = int(uid_str); expected = hmac.new(_REF_SECRET, str(uid).encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(sig, expected): return uid
    except: pass
    return None
def get_referral_link(user_id: int) -> str: return f"https://t.me/{BOT_USERNAME}?start=ref_{_ref_token(user_id)}"

def ui_profile(user, context: ContextTypes.DEFAULT_TYPE) -> str:
    ud = get_user_data(user.id, context); raw_plan = ud.get("plan", "TRIAL").upper(); expires = ud.get("expires", 0); now = time.time()
    if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; ud["plan"] = "TRIAL"; ud["expires"] = 0; expires = 0
    premium = raw_plan != "TRIAL"; credits = "Unlimited" if premium else str(ud.get("credits", 150)); plan_emoji = tg_emoji(get_plan_emoji_id(raw_plan), "⭐")
    uname = escape(f"@{user.username}" if user.username else user.first_name or "User"); joined = ud.get("joined", datetime.now().strftime("%Y-%m-%d")).split(" ")[0]; last_active = ud.get("last_active", "N/A"); total_refs = ud.get("total_refs", 0); total_checks = ud.get("total_checks", 0)
    ban_status = f"{E_ERRORS} {B('Banned')}" if ud.get("banned", False) else f"{E_LIVE} {B('Active')}"
    if premium and expires > now: exp_date = datetime.fromtimestamp(expires).strftime("%Y-%m-%d"); rem_d = int((expires - now) / 86400); rem_h = int(((expires - now) % 86400) / 3600); expire_line = f"✰ <b>𝐄𝐱𝐩𝐢𝐫𝐞𝐬</b>   ➔ {exp_date} ({rem_d}d {rem_h}h)"
    else: expire_line = "✰ <b>𝐄𝐱𝐩𝐢𝐫𝐞𝐬</b>   ➔ Never (Trial)"
    return "\n".join(["⭅ <b>𝗨𝗦𝗘𝗥 𝗖𝗢𝗡𝗧𝗥𝗢𝗟 𝗛𝗨𝗕</b> ⭆", "━━━━━━━━━━━━━━━━━━━━", f"✰ <b>𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞</b>  ➔ {uname} {plan_emoji}", f"✰ <b>𝐔𝐬𝐞𝐫 𝐈𝐃</b>   ➔ <code>{user.id}</code>", f"✰ <b>𝐀𝐜𝐜𝐞𝐬𝐬</b>    ➔ {get_styled_plan(raw_plan)}", f"✰ <b>𝐒𝐭𝐚𝐭𝐮𝐬</b>    ➔ {ban_status}", f"✰ <b>𝐂𝐫𝐞𝐝𝐢𝐭𝐬</b>   ➔ {credits}", f"✰ <b>𝐉𝐨𝐢𝐧𝐞𝐝</b>    ➔ {joined}", expire_line, "━━━━━━━━━━━━━━━━━━━━", f"✰ <b>𝐋𝐚𝐬𝐭 𝐀𝐜𝐭𝐢𝐯𝐞</b> ➔ {last_active}", f"✰ <b>𝐓𝐨𝐭𝐚𝐥 𝐂𝐡𝐞𝐜𝐤𝐬</b> ➔ {total_checks}", f"✰ <b>𝐑𝐞𝐟𝐞𝐫𝐫𝐚𝐥𝐬</b>  ➔ {total_refs} (+{total_refs * REFERRAL_CREDITS} credits)", "━━━━━━━━━━━━━━━━━━━━", f"{E_DEV} 𝗩𝗲𝗿𝘀𝗶𝗼𝗻 ➔ {VERSION}  |  <a href='{DEV_LINK}'>Superman</a> {E_PRO}"])

def ui_full_profile(user, context: ContextTypes.DEFAULT_TYPE) -> str:
    ud = get_user_data(user.id, context); raw_plan = ud.get("plan", "TRIAL").upper(); expires = ud.get("expires", 0); now = time.time()
    if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; ud["plan"] = "TRIAL"; ud["expires"] = 0; expires = 0
    premium = raw_plan != "TRIAL"; credits = "Unlimited" if premium else str(ud.get("credits", 150)); plan_emoji = tg_emoji(get_plan_emoji_id(raw_plan), "⭐")
    uname = escape(f"@{user.username}" if user.username else user.first_name or "User"); joined = ud.get("joined", "N/A"); last_active = ud.get("last_active", "N/A"); total_refs = ud.get("total_refs", 0); total_checks = ud.get("total_checks", 0); approved = ud.get("approved_checks", 0); declined = ud.get("declined_checks", 0); last_gate = ud.get("last_gate", "N/A"); last_card = ud.get("last_card", "N/A"); codes_red = ud.get("codes_redeemed", 0); keys_red = ud.get("keys_redeemed", 0)
    ban_status = f"{E_ERRORS} {B('Banned')}" if ud.get("banned", False) else f"{E_LIVE} {B('Active')}"; approval_rate = f"{(approved / total_checks * 100):.1f}%" if total_checks > 0 else "N/A"
    if premium and expires > now: exp_date = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M"); rem_d = int((expires - now) / 86400); rem_h = int(((expires - now) % 86400) / 3600); expire_line = f"✰ <b>𝐄𝐱𝐩𝐢𝐫𝐞𝐬</b>   ➔ {exp_date}\n✰ <b>𝐓𝐢𝐦𝐞 𝐋𝐞𝐟𝐭</b>  ➔ {rem_d}d {rem_h}h"; last_receipt = ud.get("last_receipt"); expire_line += f"\n✰ <b>𝐑𝐞𝐜𝐞𝐢𝐩𝐭</b>   ➔ <code>{last_receipt}</code>" if last_receipt else ""
    else: expire_line = "✰ <b>𝐄𝐱𝐩𝐢𝐫𝐞𝐬</b>   ➔ Never (Trial)"
    lines = ["⭅ <b>𝗨𝗦𝗘𝗥 𝗣𝗥𝗢𝗙𝗜𝗟𝗘</b> ⭆", "━━━━━━━━━━━━━━━━━━━━", f"✰ <b>𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞</b>  ➔ {uname} {plan_emoji}", f"✰ <b>𝐔𝐬𝐞𝐫 𝐈𝐃</b>   ➔ <code>{user.id}</code>", f"✰ <b>𝐀𝐜𝐜𝐞𝐬𝐬</b>    ➔ {get_styled_plan(raw_plan)}", f"✰ <b>𝐒𝐭𝐚𝐭𝐮𝐬</b>    ➔ {ban_status}", f"✰ <b>𝐂𝐫𝐞𝐝𝐢𝐭𝐬</b>   ➔ {credits}", f"✰ <b>𝐉𝐨𝐢𝐧𝐞𝐝</b>    ➔ {joined}", expire_line, "━━━━━━━━━━━━━━━━━━━━", f"✰ <b>𝐋𝐚𝐬𝐭 𝐀𝐜𝐭𝐢𝐯𝐞</b>  ➔ {last_active}", f"✰ <b>𝐓𝐨𝐭𝐚𝐥 𝐂𝐡𝐞𝐜𝐤𝐬</b> ➔ {total_checks}", f"✰ <b>𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝</b>   ➔ {approved}", f"✰ <b>𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝</b>    ➔ {declined}", f"✰ <b>𝐀𝐩𝐩𝐫𝐨𝐯𝐚𝐥 𝐑𝐚𝐭𝐞</b> ➔ {approval_rate}", f"✰ <b>𝐋𝐚𝐬𝐭 𝐆𝐚𝐭𝐞</b>   ➔ {last_gate}", f"✰ <b>𝐋𝐚𝐬𝐭 𝐁𝐈𝐍</b>    ➔ <code>{last_card}</code>", "━━━━━━━━━━━━━━━━━━━━", f"✰ <b>𝐑𝐞𝐟𝐞𝐫𝐫𝐚𝐥𝐬</b>   ➔ {total_refs} (+{total_refs * REFERRAL_CREDITS} credits)", f"✰ <b>𝐂𝐨𝐝𝐞𝐬</b>      ➔ {codes_red} redeemed", f"✰ <b>𝐊𝐞𝐲𝐬</b>       ➔ {keys_red} redeemed"]
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"{E_DEV} 𝗩𝗲𝗿𝘀𝗶𝗼𝗻 ➔ {VERSION}  |  <a href='{DEV_LINK}'>Superman</a> {E_PRO}")
    return "\n".join(lines)

def ui_start_screen(user, context: ContextTypes.DEFAULT_TYPE) -> str:
    ud = get_user_data(user.id, context); raw_plan = ud.get("plan", "TRIAL").upper(); expires = ud.get("expires", 0); now = time.time()
    if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; ud["plan"] = "TRIAL"; ud["expires"] = 0
    premium = raw_plan != "TRIAL"; credits = "∞" if premium else str(ud.get("credits", 150)); uname = escape(user.first_name or "User"); joined = ud.get("joined", datetime.now().strftime("%Y-%m-%d")).split(" ")[0]; access = get_styled_plan(raw_plan)
    return f"<b><a href='{CHANNEL_LINK}'>[❆]</a> Welcome to Superman Bot 💎</b>\n────────────\n<b>User</b>    ➳ {uname}\n<b>User ID</b> ➳ <code>{user.id}</code>\n<b>Access</b>  ➳ {access}\n<b>Credits</b> ➳ {credits}\n<b>Joined</b>  ➳ {joined}\n────────────\nChoose an option below.\n────────────\n{E_DEV} <b>Dev</b>     ➳ <a href='{DEV_LINK}'>Superman</a> {E_PRO}\n<b>Version</b> ➳ {VERSION}"

async def check_force_sub(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> list:
    if user_id == OWNER_ID: return []
    return []

async def require_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    not_joined = await check_force_sub(update.effective_user.id, context)
    return not not_joined

async def require_not_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id == OWNER_ID: return True
    ud = get_user_data(user_id, context)
    if ud.get("banned", False):
        try: await update.message.reply_text(f"<b>{E_ERRORS} {B('Banned')}</b>\n──────────\nYou have been banned from using this bot.\n────────——", parse_mode="HTML")
        except: pass
        return False
    return True

def build_check_result(card_raw: str, gate_name: str, raw_response: str, bin_data: dict, username: str, plan: str, time_taken: str, is_approved: bool, is_timeout: bool = False, is_error: bool = False) -> str:
    ch_link = f'<a href="{CHANNEL_LINK}">[❆]</a>'; live_eid = get_random_live_emoji()
    if is_timeout: status_line = '<b>⏱ TIMEOUT</b>'; resp_te = f'<tg-emoji emoji-id="{PROG_ERRORS_EMOJI_ID}">⏱</tg-emoji>'
    elif is_error: status_line = '<b>⚠️ ERROR</b>'; resp_te = f'<tg-emoji emoji-id="{PROG_ERRORS_EMOJI_ID}">⚠️</tg-emoji>'
    elif is_approved: status_line = f'<b>{ch_link} HIT LIVE <tg-emoji emoji-id="{live_eid}">✅</tg-emoji></b>'; resp_te = f'<tg-emoji emoji-id="{PROG_LIVE_EMOJI_ID}">✅</tg-emoji>'
    else: status_line = f'<b>{ch_link} DEAD DECLINED <tg-emoji emoji-id="{PROG_DEAD_EMOJI_ID}">❌</tg-emoji></b>'; resp_te = f'<tg-emoji emoji-id="{PROG_DEAD_EMOJI_ID}">❌</tg-emoji>'
    plan_emoji = tg_emoji(get_plan_emoji_id(plan), "⭐"); plan_label = get_styled_plan(plan)
    bin_txt = "N/A"
    if bin_data and not bin_data.get("error"):
        scheme = str(bin_data.get("scheme", "N/A")).upper(); bank = bin_data.get("bank", "N/A"); country = str(bin_data.get("country", "N/A")).upper(); flag = bin_data.get("country_emoji", ""); bin_txt = f"{scheme} - {bank} - {flag} {country}".strip("- ")
    uname_display = escape(username)
    return f'{status_line}\n\n<b><tg-emoji emoji-id="{CARD_EMOJI_ID}">💳</tg-emoji></b>\n<b>   ⤷ <code>{card_raw}</code></b>\n<b>Gate ➛ {gate_name}</b>\n<b>──────────</b>\n<b>{resp_te} Resp ➛ {escape(raw_response)}</b>\n<b>Bin ➛ <code>{bin_txt}</code></b>\n<b>──────────</b>\n<b><tg-emoji emoji-id="{TIME_EMOJI_ID}">⏱</tg-emoji> ➛ {time_taken}s</b>\n<b><tg-emoji emoji-id="{USER_EMOJI_ID}">👤</tg-emoji> ➛ {uname_display} {plan_emoji} ({plan_label})</b>\n<b><tg-emoji emoji-id="{DEV_EMOJI_ID}">⚡</tg-emoji> ➛ <a href="{DEV_LINK}">Superman</a> <tg-emoji emoji-id="{PRO_EMOJI_ID}">⭐</tg-emoji></b>'

def kb_main(user_id: int) -> RawMarkup:
    return RawMarkup([[_btn(B("Checker"), cb="mgates", style="primary"), _btn(B("Buy Now"), cb="mprice", style="primary")], [_btn(B("Profile"), cb="mprofile", style="primary")]])
def kb_back(cb: str) -> RawMarkup: return RawMarkup([[_btn("🔙 " + B("BACK"), cb=cb, style="primary")]])
def kb_price() -> RawMarkup:
    return RawMarkup([[_btn("⭐ " + B("1.5$ — 1 Day"), cb="pay1d", style="primary"), _btn("⭐ " + B("8$ — 7 Days"), cb="pay10", style="primary")], [_btn("⭐ " + B("12$ — 15 Days"), cb="pay15", style="primary"), _btn("⭐ " + B("25$ — 30 Days"), cb="pay30", style="primary")], [_btn("🔙 " + B("BACK"), cb="bmain")]])
def kb_payment() -> RawMarkup: return RawMarkup([[_btn("🔙 " + B("BACK"), cb="mprice")]])
def kb_gate_main() -> RawMarkup: return RawMarkup([[_btn("⚡ " + B("SHOPIFY MASS"), cb="imsh", style="primary"), _btn("🔥 " + B("SHOPIFY SINGLE"), cb="ish", style="primary")], [_btn("🔙 " + B("BACK"), cb="bmain")]])
def kb_upgrade() -> RawMarkup: return RawMarkup([[_btn("💎 " + B("BUY PREMIUM"), cb="mprice", style="primary")]])
def kb_cooldown() -> RawMarkup: return RawMarkup([[_btn("💎 " + B("BUY PREMIUM") + " — No Cooldown", cb="mprice", style="primary")]])
def kb_result_raw(is_premium: bool = False) -> RawMarkup:
    if is_premium: return RawMarkup([[_btn("🤖 " + B("Open Bot"), url=BOT_LINK, style="primary"), _btn("📢 " + B("Channel"), url=CHANNEL_LINK, style="primary")]])
    return RawMarkup([[_btn("💎 " + B("BUY PREMIUM") + " — Unlimited Checks", cb="mprice", style="primary")], [_btn("📢 @superman8585_bot", url=CHANNEL_LINK)]])
def kb_msh_result(task_id: str, has_approved: bool, is_premium: bool) -> RawMarkup:
    rows = []; dl_row = []
    if has_approved: dl_row.append(_btn("📄 Approved", cb=f"dl_approved_{task_id}", style="primary"))
    dl_row.append(_btn("📋 ALL Cards", cb=f"dl_all_{task_id}")); rows.append(dl_row)
    if not is_premium: rows.append([_btn("💎 " + B("BUY PREMIUM") + " — Unlimited", cb="mprice", style="primary")])
    return RawMarkup(rows)

async def process_referral(new_user_id: int, referrer_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if new_user_id == referrer_id: return False
    referred_set = context.bot_data.setdefault("referred_users", set())
    if new_user_id in referred_set: return False
    referrer_ud = context.bot_data.get("user_data", {}).get(str(referrer_id))
    if referrer_ud is None: return False
    referred_set.add(new_user_id); referrer_ud["credits"] = referrer_ud.get("credits", 0) + REFERRAL_CREDITS; referrer_ud["total_refs"] = referrer_ud.get("total_refs", 0) + 1
    try: await context.bot.send_message(chat_id=referrer_id, text=f"<b>{E_LIVE} {B('Referral Bonus')}</b>\n────────——\nSomeone joined via your link!\n<b>Credits Added</b>   ➳ +{REFERRAL_CREDITS}\n<b>Total Referrals</b> ➳ {referrer_ud['total_refs']}\n────────——", parse_mode="HTML")
    except: pass
    return True

async def _api_request(session, url: str, card: str, site: str) -> dict:
    if "{card}" in url:
        url = url.replace("{card}", card)
        async with session.get(url) as resp:
            try: data = await resp.json(content_type=None)
            except: data = {"value": await resp.text()}
    else:
        async with session.get(url, params={"cc": card, "site": site}) as resp:
            try: data = await resp.json(content_type=None)
            except: data = {"value": await resp.text()}
    return data if isinstance(data, dict) else {"value": str(data)}

async def process_gate(update: Update, context: ContextTypes.DEFAULT_TYPE, gate_key: str, gate_name: str):
    user = update.effective_user
    if not await require_not_banned(update, context): return
    if context.bot_data.get("maintenance") and user.id != OWNER_ID: await update.message.reply_text(f"<b>{E_ERRORS} {B('Maintenance')}</b>\nBot is under maintenance.", parse_mode="HTML"); return
    if not context.bot_data.get(f"{gate_key}_on", True): await update.message.reply_text(f"<b>{E_DECLINED} Gate [{gate_name}] is currently OFF.</b>", parse_mode="HTML"); return
    if not await require_membership(update, context): return
    ud = get_user_data(user.id, context); premium = is_user_premium(ud); _update_user_meta(ud, user)
    if gate_key in PREMIUM_GATES and not premium: await update.message.reply_text(f"<b>{E_PRO} {B('Premium Only')}</b>\n────────——\nUse /plan to upgrade.", parse_mode="HTML", reply_markup=kb_upgrade()); return
    card_raw = None
    if context.args: card_raw = context.args[0].strip()
    elif update.message.reply_to_message and update.message.reply_to_message.text: card_raw = update.message.reply_to_message.text.strip()
    if not card_raw: await update.message.reply_text(f"<b>Usage:</b> <code>/{gate_key} cc|mm|yy|cvv</code>", parse_mode="HTML"); return
    if not premium:
        credits = ud.get("credits", 0)
        if credits <= 0: await update.message.reply_text(f"<b>{E_PRO} {B('Credits Used Up!')}</b>\n────────——\nYou've used all your free credits.\n\n<b>💎 Upgrade to Premium</b> for:\n• Unlimited checks — no credit limit\n• No cooldowns\n• Mass checking without daily caps\n────────——\nTap <b>Buy Now</b> below to get a plan.", reply_markup=kb_upgrade(), parse_mode="HTML"); return
        remaining = get_cooldown_remaining(user.id, context)
        if remaining > 0: await update.message.reply_text(f"<b>{E_ERRORS} {B('Cooldown')}</b>\n────────——\nPlease wait <b>{remaining:.1f}s</b> before your next check.\n\n{E_PRO} <b>Premium removes all cooldowns.</b>\n────────——", reply_markup=kb_cooldown(), parse_mode="HTML"); return
        set_cooldown(user.id, context); ud["credits"] = credits - 1
    api_url = context.bot_data.get(f"gate_url_{gate_key}") or GATE_URLS.get(gate_key, ""); site_url = GATE_SITES.get(gate_key, "example.com"); bin_num = card_raw[:6]
    if not api_url: await update.message.reply_text(f"<b>{E_ERRORS} Gate API not configured.</b>", parse_mode="HTML"); return
    msg = await update.message.reply_text(f'<b>🔄 Gate ➳ {gate_name}</b>', parse_mode="HTML")
    start_time = time.time(); uname = f"@{user.username}" if user.username else user.first_name or "User"; plan = ud.get("plan", "TRIAL")
    try:
        timeout = _aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with _aiohttp.ClientSession(timeout=timeout) as session:
            results = await asyncio.gather(_api_request(session, api_url, card_raw, site_url), get_bin_info(bin_num), return_exceptions=True)
        data = results[0] if not isinstance(results[0], Exception) else {}; bin_data = results[1] if not isinstance(results[1], Exception) else {"error": True}
        if isinstance(results[0], Exception): raise results[0]
        raw_response = str(data.get("value") or data.get("message") or data.get("Response") or data.get("category") or "ERROR").strip()
        is_approved = any(w in raw_response.lower() for w in ["approved", "captured", "success", "charged", "true"])
        ud["total_checks"] = ud.get("total_checks", 0) + 1; ud["last_gate"] = gate_name; ud["last_card"] = card_raw[:6] + "xxxxxxxxxx"; ud["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if is_approved: ud["approved_checks"] = ud.get("approved_checks", 0) + 1
        else: ud["declined_checks"] = ud.get("declined_checks", 0) + 1
        time_taken = f"{time.time() - start_time:.2f}"; text = build_check_result(card_raw=card_raw, gate_name=gate_name, raw_response=raw_response, bin_data=bin_data, username=uname, plan=plan, time_taken=time_taken, is_approved=is_approved)
        await msg.edit_text(text, parse_mode="HTML", reply_markup=kb_result_raw(premium), disable_web_page_preview=True)
    except asyncio.TimeoutError:
        if not premium: ud["credits"] = ud.get("credits", 0) + 1
        time_taken = f"{time.time() - start_time:.2f}"; text = build_check_result(card_raw=card_raw, gate_name=gate_name, raw_response="Request Timeout", bin_data={}, username=uname, plan=plan, time_taken=time_taken, is_approved=False, is_timeout=True)
        await msg.edit_text(text, parse_mode="HTML", reply_markup=kb_result_raw(premium), disable_web_page_preview=True)
    except Exception as e:
        if not premium: ud["credits"] = ud.get("credits", 0) + 1
        time_taken = f"{time.time() - start_time:.2f}"; text = build_check_result(card_raw=card_raw, gate_name=gate_name, raw_response=str(e)[:120], bin_data={}, username=uname, plan=plan, time_taken=time_taken, is_approved=False, is_error=True)
        await msg.edit_text(text, parse_mode="HTML", reply_markup=kb_result_raw(premium), disable_web_page_preview=True)

async def _gate_toggle(update, context, gate: str, state: bool):
    if update.effective_user.id != OWNER_ID: return
    context.bot_data[f"{gate}_on"] = state; icon = E_LIVE if state else E_DECLINED
    await update.message.reply_text(f"<b>{icon} Gate [{gate.upper()}] turned {'ON' if state else 'OFF'}.</b>", parse_mode="HTML")
async def cmd_onsh(u, c): await _gate_toggle(u, c, "sh", True)
async def cmd_offsh(u, c): await _gate_toggle(u, c, "sh", False)
async def cmd_onmsh(u, c): await _gate_toggle(u, c, "msh", True)
async def cmd_offmsh(u, c): await _gate_toggle(u, c, "msh", False)

async def send_activation_msg(user_id: int, plan: str, days: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    receipt = gen_receipt(); name, username = "Unknown", None
    try:
        chat = await context.bot.get_chat(user_id); name = chat.first_name or "Unknown"; username = chat.username
    except: pass
    ud = get_user_data(user_id, context)
    if ud.get("plan", "TRIAL").upper() == "TRIAL": ud["pre_premium_credits"] = ud.get("credits", 150)
    expires_ts = time.time() + days * 86400; ud["name"] = name; ud["plan"] = plan.upper(); ud["expires"] = expires_ts; ud["last_receipt"] = receipt
    if username: ud["username"] = username
    await _save_premium(context.bot_data)
    plan_emoji = tg_emoji(get_plan_emoji_id(plan), "⭐"); exp_date = datetime.fromtimestamp(expires_ts).strftime("%Y-%m-%d %H:%M"); display_name = f"@{username}" if username else name; styled = get_styled_plan(plan)
    txt = f"<b>{E_LIVE} {B('Access Activated')}</b>\n────────——\n<b>User</b>     ➳ {display_name}\n<b>Access</b>   ➳ {styled} {plan_emoji}\n<b>Days</b>     ➳ {days}\n<b>Credits</b>  ➳ Unlimited\n<b>Expires</b>  ➳ {exp_date}\n<b>Receipt</b>  ➳ <code>{receipt}</code>\n────────——\nSave this receipt ID.\n{E_DEV} Superman {E_PRO}"
    try: await context.bot.send_message(chat_id=user_id, text=txt, parse_mode="HTML")
    except: pass
    return receipt

async def resolve_user(target: str, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    target = target.strip().lstrip("@")
    if target.lstrip("-").isdigit(): return int(target)
    for attempt in (f"@{target}", target):
        try: return (await context.bot.get_chat(attempt)).id
        except: continue
    all_users = context.bot_data.get("user_data", {}); target_lower = target.lower()
    for uid_str, ud in all_users.items():
        stored = ud.get("username", "").lower().lstrip("@")
        if stored and stored == target_lower: return int(uid_str)
    return None

async def _grant(uid: int, plan: str, days: int, update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = get_user_data(uid, context); ud["plan"] = plan; ud["expires"] = time.time() + days * 86400
    display_name = ud.get("name", "Unknown"); display_uname = ud.get("username", "")
    try:
        chat = await context.bot.get_chat(uid); display_name = chat.first_name or "Unknown"; display_uname = chat.username or ""
    except: pass
    await _save_premium(context.bot_data)
    plan_emoji = tg_emoji(get_plan_emoji_id(plan), "⭐")
    await update.message.reply_text(f"<b>{E_LIVE} {B('Premium Granted')}</b>\n────────——\n<b>User</b>   ➳ {display_name} (@{display_uname or 'N/A'})\n<b>Access</b> ➳ {get_styled_plan(plan)} {plan_emoji}\n<b>Days</b>   ➳ {days}\n────────——", parse_mode="HTML")
    await send_activation_msg(uid, plan, days, context)

async def cmd_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    SECRET_CHANNEL_ID = -1004322090872
    if not context.args:
        await update.message.reply_text("<b>📄 Card Splitter</b>\n────────——\n<b>Usage (in private GC):</b>\n1. Send a message containing cards to the chat.\n2. Reply to that message with <code>/cards N</code>\n   (where N is the number of cards per file)\n\n<b>Example:</b> <code>/cards 50</code>\n────────——", parse_mode="HTML"); return
    try:
        cards_per_file = int(context.args[0])
        if cards_per_file <= 0: raise ValueError
    except: await update.message.reply_text("❌ N must be a positive number.", parse_mode="HTML"); return
    cards = []
    if update.message.reply_to_message:
        txt = (update.message.reply_to_message.text or update.message.reply_to_message.caption or "").strip()
        cards = re.findall(r'\b\d{13,19}\s*[|/:=]\s*\d{1,2}\s*[|/:=]\s*\d{2,4}\s*[|/:=]\s*\d{3,4}\b', txt)
        if not cards: cards = [c.strip() for c in txt.split() if "|" in c]
    elif len(context.args) > 1:
        txt = " ".join(context.args[1:]); cards = re.findall(r'\b\d{13,19}\s*[|/:=]\s*\d{1,2}\s*[|/:=]\s*\d{2,4}\s*[|/:=]\s*\d{3,4}\b', txt)
        if not cards: cards = [c.strip() for c in txt.split() if "|" in c]
    if not cards: await update.message.reply_text("❌ No valid cards found. Reply to a message containing cards.", parse_mode="HTML"); return
    total_cards = len(cards); total_files = (total_cards + cards_per_file - 1) // cards_per_file
    status_msg = await update.message.reply_text(f"⏳ Processing {total_cards} cards into {total_files} files...\nLooking up BINs...", parse_mode="HTML")
    file_count = 0
    for i in range(0, total_cards, cards_per_file):
        chunk = cards[i:i + cards_per_file]
        lines = ["━━━━━━━━━━━━━━━━━━━━━━━━", f"File {file_count + 1} of {total_files}", f"Cards per file: {cards_per_file}", f"Total Cards in this file: {len(chunk)}", "━━━━━━━━━━━━━━━━━━━━━━━━", ""]
        for card in chunk:
            bin_num = card[:6]
            try: bin_data = await asyncio.wait_for(_bin_lookup(bin_num), timeout=5)
            except: bin_data = {}
            bin_info_str = _bin_str_plain(bin_data)
            lines += [f"Card ➳ {card}", f"Bin ➳ {bin_info_str}", "━━━━━━━━━━━━━━━━━━━━━━━━"]
        content = "\n".join(lines); buf = BytesIO(content.encode("utf-8")); buf.seek(0); file_count += 1
        filename = f"Superman_Cards_{file_count}_of_{total_files}.txt"
        try:
            await context.bot.send_document(chat_id=SECRET_CHANNEL_ID, document=InputFile(buf, filename=filename), caption=f"<b>📄 Cards File {file_count}/{total_files}</b>\n<b>Cards:</b> {len(chunk)}", parse_mode="HTML", disable_notification=True)
        except Exception as e: logging.error(f"Error sending file to secret channel: {e}")
        await asyncio.sleep(0.5)
    await status_msg.edit_text(f"✅ Done! {total_cards} cards split into {total_files} files and sent to the secret channel.", parse_mode="HTML")

async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not context.args or len(context.args) < 2: await update.message.reply_text(f"<b>{E_DEV} {B('Generate Code / Key')}</b>\n────────——\n<b>Credit Code:</b>\n<code>/gen code &lt;credits&gt;</code>\n<code>/gen code &lt;credits&gt; &lt;count&gt;</code>\n\n<b>Premium Key:</b>\n<code>/gen key &lt;PLAN&gt; &lt;days&gt;</code>\n<code>/gen key &lt;PLAN&gt; &lt;days&gt; &lt;count&gt;</code>\n\n<b>Plans:</b>  CORE | ELITE | ROOT\n\n<b>Examples:</b>\n<code>/gen code 50</code>\n<code>/gen code 100 5</code>\n<code>/gen key ELITE 30</code>\n<code>/gen key ROOT 7 3</code>\n────────——\nUsers redeem with: <code>/rm CODE</code>", parse_mode="HTML"); return
    kind = context.args[0].lower()
    if kind == "code":
        try:
            value = int(context.args[1])
            if value <= 0: raise ValueError
        except: await update.message.reply_text(f"<b>{E_ERRORS} Credits value must be a positive number.</b>", parse_mode="HTML"); return
        count = 1
        if len(context.args) >= 3:
            try:
                count = int(context.args[2])
                if count <= 0 or count > 50: raise ValueError
            except: await update.message.reply_text(f"<b>{E_ERRORS} Count must be 1–50.</b>", parse_mode="HTML"); return
        codes_store = context.bot_data.setdefault("codes", {}); generated = []
        for _ in range(count): code = gen_code(); codes_store[code] = {"value": value, "used": False}; generated.append(code)
        if count == 1: await update.message.reply_text(f"<b>{E_LIVE} {B('Code Generated')}</b>\n────────——\n<b>Code</b>    ➳ <code>{generated[0]}</code>\n<b>Credits</b> ➳ +{value}\n────────——\nRedeem: <code>/rm {generated[0]}</code>", parse_mode="HTML")
        else:
            lines = [f"<b>{E_LIVE} {B('Codes Generated')}</b>", "────────——", f"<b>Credits each</b> ➳ +{value}", f"<b>Count</b>        ➳ {count}", "────────——"]
            for i, c in enumerate(generated, 1): lines.append(f"<b>{i}.</b> <code>{c}</code>")
            lines += ["────────——", "Redeem with: <code>/rm CODE</code>"]
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    elif kind == "key":
        if len(context.args) < 3: await update.message.reply_text(f"<b>{E_ERRORS} Usage:</b> <code>/gen key PLAN DAYS [count]</code>", parse_mode="HTML"); return
        plan_arg = context.args[1].upper()
        if plan_arg not in ("CORE", "ELITE", "ROOT"): await update.message.reply_text(f"<b>{E_ERRORS} Invalid plan.</b> Use: <b>CORE</b>, <b>ELITE</b>, or <b>ROOT</b>", parse_mode="HTML"); return
        try:
            days = int(context.args[2])
            if days <= 0: raise ValueError
        except: await update.message.reply_text(f"<b>{E_ERRORS} Days must be a positive number.</b>", parse_mode="HTML"); return
        count = 1
        if len(context.args) >= 4:
            try:
                count = int(context.args[3])
                if count <= 0 or count > 50: raise ValueError
            except: await update.message.reply_text(f"<b>{E_ERRORS} Count must be 1–50.</b>", parse_mode="HTML"); return
        keys_store = context.bot_data.setdefault("keys", {}); plan_emoji = tg_emoji(get_plan_emoji_id(plan_arg), "⭐"); generated = []
        for _ in range(count): key = gen_code(12); keys_store[key] = {"plan": plan_arg, "days": days, "used": False}; generated.append(key)
        if count == 1: await update.message.reply_text(f"<b>{E_LIVE} {B('Key Generated')}</b>\n────────——\n<b>Key</b>    ➳ <code>{generated[0]}</code>\n<b>Plan</b>   ➳ {get_styled_plan(plan_arg)} {plan_emoji}\n<b>Days</b>   ➳ {days}\n────────——\nRedeem: <code>/rm {generated[0]}</code>", parse_mode="HTML")
        else:
            lines = [f"<b>{E_LIVE} {B('Keys Generated')}</b>", "────────——", f"<b>Plan</b>  ➳ {get_styled_plan(plan_arg)} {plan_emoji}", f"<b>Days</b>  ➳ {days}", f"<b>Count</b> ➳ {count}", "────────——"]
            for i, k in enumerate(generated, 1): lines.append(f"<b>{i}.</b> <code>{k}</code>")
            lines += ["────────——", "Redeem with: <code>/rm KEY</code>"]
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    else: await update.message.reply_text(f"<b>{E_ERRORS} Unknown type.</b> Use: <b>code</b> or <b>key</b>", parse_mode="HTML")

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if len(context.args) < 3: await update.message.reply_text(f"<b>{E_DEV} {B('Grant Premium')}</b>\n────────——\n<b>Usage:</b>\n<code>/add @username PLAN DAYS</code>\n<code>/add UserID PLAN DAYS</code>\n\n<b>Plans:</b>  CORE | ELITE | ROOT\n\n<b>Example:</b>\n<code>/add @john ELITE 30</code>\n<code>/add 123456789 ROOT 7</code>\n────────——", parse_mode="HTML"); return
    raw_target = context.args[0]; uid = await resolve_user(raw_target, context)
    if not uid: await update.message.reply_text(f"{E_ERRORS} <b>User not found:</b> <code>{raw_target}</code>\nMake sure the user has started the bot first.", parse_mode="HTML"); return
    plan_arg = context.args[1].upper()
    if plan_arg not in ("CORE", "ELITE", "ROOT"): await update.message.reply_text(f"{E_ERRORS} Invalid plan. Use: <b>CORE</b>, <b>ELITE</b>, or <b>ROOT</b>", parse_mode="HTML"); return
    try:
        days = int(context.args[2])
        if days <= 0: raise ValueError
    except: await update.message.reply_text(f"{E_ERRORS} Days must be a positive number.", parse_mode="HTML"); return
    await _grant(uid, plan_arg, days, update, context)

async def cmd_rem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    target = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user: target = update.message.reply_to_message.from_user.id
    elif context.args: target = await resolve_user(context.args[0], context)
    if not target: await update.message.reply_text(f"<b>Usage:</b> /rem @user|ID or reply → /rem", parse_mode="HTML"); return
    ud = get_user_data(target, context); ud["plan"] = "TRIAL"; ud["expires"] = 0
    await _save_premium(context.bot_data)
    await update.message.reply_text(f"<b>{E_DECLINED} Premium removed for <code>{target}</code>.</b>", parse_mode="HTML")

async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not context.args: await update.message.reply_text(f"<b>{E_DEV} {B('Find User')}</b>\n────────——\n<b>Usage:</b>\n<code>/find @username</code>\n<code>/find username</code>\n<code>/find UserID</code>\n────────——\nSearches all registered bot users.", parse_mode="HTML"); return
    raw = context.args[0]; now = time.time(); uid = await resolve_user(raw, context)
    if not uid:
        needle = raw.lstrip("@").lower(); all_users = context.bot_data.get("user_data", {}); matches = []
        for uid_str, ud in all_users.items():
            stored = ud.get("username", "").lower().lstrip("@"); name = ud.get("name", "").lower()
            if stored and needle in stored: matches.append((int(uid_str), ud))
            elif needle in name: matches.append((int(uid_str), ud))
        if not matches: await update.message.reply_text(f"{E_ERRORS} <b>No user found for:</b> <code>{raw}</code>\nMake sure the user has started the bot first.", parse_mode="HTML"); return
        if len(matches) > 1:
            lines = [f"<b>{E_USER} {B('Multiple Matches')}</b>\n────────——"]
            for mid, mud in matches[:10]:
                ustr = f"@{mud.get('username','')}" if mud.get("username") else str(mid); plan = mud.get("plan", "TRIAL").upper(); lines.append(f"• {mud.get('name','?')} — {ustr} — {get_styled_plan(plan)}")
            lines.append("────────——\nRefine your search to narrow down.")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML"); return
        uid = matches[0][0]
    ud_t = get_user_data(uid, context)
    try:
        chat = await context.bot.get_chat(uid); ud_t["name"] = chat.first_name or ud_t.get("name", "Unknown"); ud_t["username"] = chat.username or ud_t.get("username", "")
    except: pass
    raw_plan = ud_t.get("plan", "TRIAL").upper(); expires = ud_t.get("expires", 0)
    if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; expires = 0
    premium = raw_plan != "TRIAL" and expires > now; plan_emoji = tg_emoji(get_plan_emoji_id(raw_plan), "⭐"); uname_d = f"@{ud_t.get('username','')}" if ud_t.get("username") else f"ID <code>{uid}</code>"
    ban_str = f"{E_ERRORS} {B('Banned')}" if ud_t.get("banned") else f"{E_LIVE} {B('Active')}"
    if premium: rem = expires - now; expire_line = f"<b>Expires</b>    ➳ {datetime.fromtimestamp(expires).strftime('%Y-%m-%d %H:%M')}\n<b>Remaining</b>  ➳ <b>{int(rem//86400)}d {int((rem%86400)//3600)}h</b>"
    else: expire_line = f"<b>Expires</b>    ➳ Trial (no expiry)"
    txt = f"<b>{E_USER} {B('User Found')}</b>\n────────——\n<b>Name</b>      ➳ {ud_t.get('name','Unknown')}\n<b>Username</b>  ➳ {uname_d}\n<b>ID</b>        ➳ <code>{uid}</code>\n<b>Status</b>    ➳ {ban_str}\n────────——\n<b>Plan</b>      ➳ {get_styled_plan(raw_plan)} {plan_emoji}\n<b>Credits</b>   ➳ {ud_t.get('credits', 150)}\n{expire_line}\n────────——\n<b>Joined</b>    ➳ {ud_t.get('joined', 'N/A')}\n<b>Last Active</b> ➳ {ud_t.get('last_active', 'N/A')}\n<b>Total Checks</b> ➳ {ud_t.get('total_checks', 0)}\n<b>Total Refs</b>   ➳ {ud_t.get('total_refs', 0)}\n────────——"
    kb = RawMarkup([[_btn(f"{E_DECLINED} Ban", cb=f"owner_ban_{uid}", style="danger"), _btn(f"{E_LIVE} Unban", cb=f"owner_unban_{uid}", style="primary")], [_btn(f"💎 Grant Plan via /sub {uid}", cb=f"find_sub_{uid}", style="primary")]])
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)

async def cmd_resub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    target_id = None; target_name, target_uname = "Unknown", ""
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        ru = update.message.reply_to_message.from_user; target_id = ru.id; target_name = ru.first_name or "Unknown"; target_uname = ru.username or ""
    elif context.args:
        raw = context.args[0]; target_id = await resolve_user(raw, context)
        if not target_id: await update.message.reply_text(f"{E_ERRORS} <b>User not found:</b> <code>{raw}</code>", parse_mode="HTML"); return
    else: await update.message.reply_text(f"<b>{E_DEV} {B('Remove Premium')}</b>\n────────——\n<b>Usage:</b>\n<code>/resub @username</code>\n<code>/resub UserID</code>\nOr reply to a user's message → <code>/resub</code>\n\n<b>Alias:</b> /rsub works too\n────────——", parse_mode="HTML"); return
    ud = get_user_data(target_id, context); old_plan = ud.get("plan", "TRIAL").upper(); old_exp = ud.get("expires", 0); now = time.time()
    if old_plan == "TRIAL" or old_exp <= now:
        try:
            chat = await context.bot.get_chat(target_id); target_name = chat.first_name or "Unknown"; target_uname = chat.username or ""
        except: target_name = ud.get("name", "Unknown"); target_uname = ud.get("username", "")
        uname_d = f"@{target_uname}" if target_uname else f"<code>{target_id}</code>"
        await update.message.reply_text(f"{E_ERRORS} <b>{target_name}</b> ({uname_d}) has no active premium.", parse_mode="HTML"); return
    try:
        chat = await context.bot.get_chat(target_id); target_name = chat.first_name or "Unknown"; target_uname = chat.username or ""
    except: target_name = ud.get("name", "Unknown"); target_uname = ud.get("username", "")
    ud["plan"] = "TRIAL"; ud["expires"] = 0; await _save_premium(context.bot_data)
    uname_d = f"@{target_uname}" if target_uname else f"<code>{target_id}</code>"; old_plan_str = get_styled_plan(old_plan); rem_was = int((old_exp - now) // 86400)
    await update.message.reply_text(f"<b>{E_DECLINED} {B('Premium Removed')}</b>\n────────——\n<b>User</b>       ➳ {target_name} ({uname_d})\n<b>ID</b>         ➳ <code>{target_id}</code>\n<b>Plan Was</b>   ➳ {old_plan_str}\n<b>Days Left</b>  ➳ {rem_was}d (cancelled)\n────────——\n<b>Status</b>     ➳ Reset to {B('Trial')}", parse_mode="HTML")
    try: await context.bot.send_message(chat_id=target_id, text=f"<b>{E_ERRORS} {B('Subscription Cancelled')}</b>\n────────——\nYour <b>{old_plan_str}</b> premium has been removed by the admin.\nUse /plan to purchase a new subscription.\n────────——", parse_mode="HTML")
    except: pass

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    uid = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user: uid = update.message.reply_to_message.from_user.id
    elif context.args: uid = await resolve_user(context.args[0], context)
    if not uid: await update.message.reply_text(f"<b>Usage:</b> /ban @user|ID or reply → /ban", parse_mode="HTML"); return
    if uid == OWNER_ID: await update.message.reply_text(f"{E_ERRORS} Cannot ban the owner.", parse_mode="HTML"); return
    get_user_data(uid, context)["banned"] = True
    await update.message.reply_text(f"<b>{E_ERRORS} User <code>{uid}</code> has been banned.</b>", parse_mode="HTML")
    try: await context.bot.send_message(chat_id=uid, text=f"<b>{E_ERRORS} {B('Banned')}</b>\n────────——\nYou have been banned from using this bot.\n────────——", parse_mode="HTML")
    except: pass

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    uid = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user: uid = update.message.reply_to_message.from_user.id
    elif context.args: uid = await resolve_user(context.args[0], context)
    if not uid: await update.message.reply_text(f"<b>Usage:</b> /unban @user|ID or reply → /unban", parse_mode="HTML"); return
    get_user_data(uid, context)["banned"] = False
    await update.message.reply_text(f"<b>{E_LIVE} User <code>{uid}</code> has been unbanned.</b>", parse_mode="HTML")
    try: await context.bot.send_message(chat_id=uid, text=f"<b>{E_LIVE} {B('Unbanned')}</b>\n────────——\nYou can now use the bot again.\n────────——", parse_mode="HTML")
    except: pass

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    now = time.time()
    if not context.args and not (update.message.reply_to_message and update.message.reply_to_message.from_user):
        all_users = context.bot_data.get("user_data", {})
        if not all_users: await update.message.reply_text("No users found."); return
        total = len(all_users); premium_count = sum(1 for ud in all_users.values() if ud.get("plan", "TRIAL").upper() != "TRIAL" and ud.get("expires", 0) > now); banned_count = sum(1 for ud in all_users.values() if ud.get("banned", False)); trial_count = total - premium_count
        header = f"<b>{E_USER} All Users</b>\n────────——\n<b>Total</b>   ➳ {total}\n<b>Premium</b> ➳ {premium_count}\n<b>Trial</b>   ➳ {trial_count}\n<b>Banned</b>  ➳ {banned_count}\n────────——\n"
        lines = []
        for uid_str, ud in list(all_users.items())[:30]:
            rp = ud.get("plan", "TRIAL").upper(); ex = ud.get("expires", 0)
            if rp != "TRIAL" and ex <= now: rp = "TRIAL"
            prem = rp != "TRIAL" and ex > now; ban = f"{E_ERRORS}" if ud.get("banned", False) else f"{E_LIVE}"
            uname_d = f"@{ud.get('username','')}" if ud.get("username") else ud.get("name", "?"); rem = f"{int((ex-now)//86400)}d" if prem else "—"
            lines.append(f"{ban} <code>{uid_str}</code> | {uname_d} | {get_styled_plan(rp)} | {rem}")
        txt = header + "\n".join(lines)
        if total > 30: txt += f"\n\n...and {total - 30} more. Use /info @user or /info ID."
        await update.message.reply_text(txt, parse_mode="HTML"); return
    target_id, target_name, target_username = None, "N/A", None
    target_last_name, target_lang = "", "N/A"
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        ru = update.message.reply_to_message.from_user; target_id, target_name = ru.id, ru.first_name or "N/A"; target_last_name, target_username, target_lang = ru.last_name or "", ru.username, ru.language_code or "N/A"
    elif context.args:
        raw = " ".join(context.args).strip().lstrip("@")
        if raw.lstrip("-").isdigit(): target_id = int(raw)
        else:
            try:
                chat = await context.bot.get_chat(f"@{raw}"); target_id, target_name = chat.id, chat.first_name or "N/A"; target_last_name, target_username = getattr(chat, "last_name", "") or "", chat.username
            except: pass
            if not target_id:
                raw_lower = raw.lower()
                for uid_str, ud in context.bot_data.get("user_data", {}).items():
                    if (raw_lower in ud.get("username", "").lower().lstrip("@") or raw_lower in ud.get("name", "").lower()): target_id = int(uid_str); target_name, target_username = ud.get("name", "N/A"), ud.get("username"); target_lang = ud.get("language_code", "N/A"); break
    if not target_id: await update.message.reply_text(f"<b>Usage:</b>\n/info — all users\n/info @username\n/info 123456789\nOr reply → /info", parse_mode="HTML"); return
    if target_name == "N/A":
        try:
            chat = await context.bot.get_chat(target_id); target_name, target_last_name, target_username = chat.first_name or "N/A", getattr(chat, "last_name", "") or "", chat.username
        except: pass
    uid_str = str(target_id); udata = context.bot_data.get("user_data", {}).get(uid_str, {}); raw_plan = udata.get("plan", "TRIAL").upper(); expires = udata.get("expires", 0)
    if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; expires = 0
    premium = raw_plan != "TRIAL" and expires > now; credits_d = "Unlimited" if premium else str(udata.get("credits", 150)); banned = udata.get("banned", False)
    plan_emoji = tg_emoji(get_plan_emoji_id(raw_plan), "⭐"); full_name = f"{target_name} {target_last_name}".strip(); uname_d = f"@{target_username}" if target_username else "None"
    total_refs = udata.get("total_refs", 0); total_checks = udata.get("total_checks", 0); approved_checks = udata.get("approved_checks", 0); declined_checks = udata.get("declined_checks", 0)
    approval_rate = f"{(approved_checks / total_checks * 100):.1f}%" if total_checks > 0 else "N/A"; ban_icon = f"{E_ERRORS} {B('Banned')}" if banned else f"{E_LIVE} {B('Active')}"
    txt = f"<b>{E_USER} {B('User Info')}</b>\n────────——\n<b>Name</b>       ➳ {full_name}\n<b>Username</b>   ➳ {uname_d}\n<b>ID</b>         ➳ <code>{target_id}</code>\n<b>Status</b>     ➳ {ban_icon}\n────────——\n<b>Plan</b>       ➳ {get_styled_plan(raw_plan)} {plan_emoji}\n<b>Credits</b>    ➳ {credits_d}\n"
    if premium and expires > now:
        rem = expires - now
        txt += f"<b>Expires</b>    ➳ {datetime.fromtimestamp(expires).strftime('%Y-%m-%d %H:%M')}\n<b>Remaining</b>  ➳ {int(rem // 86400)}d {int((rem % 86400) // 3600)}h\n"
    last_receipt = udata.get("last_receipt")
    if last_receipt: txt += f"<b>Receipt</b>    ➳ <code>{last_receipt}</code>\n"
    txt += f"────────——\n<b>Joined</b>      ➳ {udata.get('joined', 'N/A')}\n<b>Last Active</b> ➳ {udata.get('last_active', 'N/A')}\n────────——\n<b>Total Checks</b> ➳ {total_checks}\n<b>Approved</b>     ➳ {approved_checks}\n<b>Declined</b>     ➳ {declined_checks}\n<b>Rate</b>         ➳ {approval_rate}\n<b>Last Gate</b>    ➳ {udata.get('last_gate', 'N/A')}\n<b>Last BIN</b>     ➳ <code>{udata.get('last_card', 'N/A')}</code>\n────────——\n<b>Referrals</b>    ➳ {total_refs}\n<b>Codes</b>        ➳ {udata.get('codes_redeemed', 0)} redeemed\n<b>Keys</b>         ➳ {udata.get('keys_redeemed', 0)} redeemed\n────────——"
    action_kb = RawMarkup([[_btn(f"{E_ERRORS} Ban" if not banned else f"{E_LIVE} Unban", cb=f"owner_ban_{target_id}" if not banned else f"owner_unban_{target_id}", style="danger" if not banned else "primary"), _btn(f"{E_DECLINED} Remove Premium", cb=f"owner_resub_{target_id}", style="danger")], [_btn("🔙 Back", cb="owner_info_back")]])
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=action_kb)

async def cmd_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not context.args: state = context.bot_data.get("maintenance", False); await update.message.reply_text(f"Maintenance is currently: <b>{'ON' if state else 'OFF'}</b>\nUse: /maintenance on|off", parse_mode="HTML"); return
    arg = context.args[0].lower()
    if arg in ("on", "1", "true"): context.bot_data["maintenance"] = True; await update.message.reply_text(f"<b>{E_ERRORS} {B('Maintenance Mode ON.')}</b> Users cannot use commands.", parse_mode="HTML")
    elif arg in ("off", "0", "false"): context.bot_data["maintenance"] = False; await update.message.reply_text(f"<b>{E_LIVE} {B('Maintenance Mode OFF.')}</b> Bot is live.", parse_mode="HTML")
    else: await update.message.reply_text("Use: /maintenance on|off")

async def cmd_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; now = time.time()
    has_target = bool(context.args) or (update.message.reply_to_message and update.message.reply_to_message.from_user)
    if user.id == OWNER_ID and has_target:
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            ru = update.message.reply_to_message.from_user; target_id = ru.id; target_name = ru.first_name or "Unknown"; target_uname = ru.username or ""
        else:
            raw = context.args[0]; target_id = await resolve_user(raw, context)
            if not target_id: await update.message.reply_text(f"{E_ERRORS} <b>User not found:</b> <code>{raw}</code>", parse_mode="HTML"); return
            target_name, target_uname = "Unknown", ""
            try:
                chat = await context.bot.get_chat(target_id); target_name = chat.first_name or "Unknown"; target_uname = chat.username or ""
            except: pass
        ud_t = get_user_data(target_id, context); raw_plan = ud_t.get("plan", "TRIAL").upper(); expires = ud_t.get("expires", 0)
        if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; expires = 0
        premium = raw_plan != "TRIAL" and expires > now; plan_emoji = tg_emoji(get_plan_emoji_id(raw_plan), "⭐"); uname_d = f"@{target_uname}" if target_uname else f"<code>{target_id}</code>"
        if premium: rem = expires - now; expire_line = f"<b>Expires</b>   ➳ {datetime.fromtimestamp(expires).strftime('%Y-%m-%d %H:%M')}\n<b>Remaining</b> ➳ <b>{int(rem//86400)}d {int((rem%86400)//3600)}h</b>"
        else: expire_line = "<b>Expires</b>   ➳ Trial (no expiry)"
        txt = f"<b>{E_USER} {B('User Subscription')}</b>\n────────——\n<b>Name</b>     ➳ {target_name}\n<b>Username</b> ➳ {uname_d}\n<b>ID</b>       ➳ <code>{target_id}</code>\n────────——\n<b>Plan</b>     ➳ {get_styled_plan(raw_plan)} {plan_emoji}\n{expire_line}\n────────——\n<b>Grant a Plan:</b>"
        kb = RawMarkup([[_btn("⭐ CORE · 7d", cb=f"ogs_CORE_7_{target_id}", style="primary"), _btn("💎 ELITE · 15d", cb=f"ogs_ELITE_15_{target_id}", style="primary"), _btn("👑 ROOT · 30d", cb=f"ogs_ROOT_30_{target_id}", style="primary")], [_btn("⭐ CORE · 15d", cb=f"ogs_CORE_15_{target_id}", style="primary"), _btn("💎 ELITE · 30d", cb=f"ogs_ELITE_30_{target_id}", style="primary"), _btn("👑 ROOT · 60d", cb=f"ogs_ROOT_60_{target_id}", style="primary")], [_btn(f"{E_DECLINED} Remove Plan", cb=f"owner_resub_{target_id}", style="danger")]])
        await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb); return
    ud = get_user_data(user.id, context); raw_plan = ud.get("plan", "TRIAL").upper(); expires = ud.get("expires", 0)
    if raw_plan != "TRIAL" and expires <= now: raw_plan = "TRIAL"; ud["plan"] = "TRIAL"; ud["expires"] = 0; expires = 0
    premium = raw_plan != "TRIAL" and expires > now; uname = f"@{user.username}" if user.username else user.first_name or "User"; plan_emoji = tg_emoji(get_plan_emoji_id(raw_plan), "⭐"); credits_d = "Unlimited" if premium else str(ud.get("credits", 150))
    if premium: rem = expires - now; rem_d = int(rem // 86400); rem_h = int((rem % 86400) // 3600); exp_str = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M"); expire_line = f"<b>Expires</b>    ➳ {exp_str}\n<b>Remaining</b>  ➳ <b>{rem_d} days {rem_h} hours</b>"
    else: expire_line = "<b>Expires</b>    ➳ Trial (no expiry)"
    txt = f"<b>{E_USER} {B('My Subscription')}</b>\n────────——\n<b>Name</b>      ➳ {escape(uname)}\n<b>ID</b>        ➳ <code>{user.id}</code>\n────────——\n<b>Plan</b>      ➳ {get_styled_plan(raw_plan)} {plan_emoji}\n<b>Credits</b>   ➳ {credits_d}\n{expire_line}\n────────——\n<b>Joined</b>    ➳ {ud.get('joined', 'N/A')}\n────────——"
    kb = RawMarkup([[_btn("💎 " + B("Upgrade Plan"), cb="mprice", style="primary")]]) if not premium else None
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; ud = get_user_data(user.id, context); ud.setdefault("joined", datetime.now().strftime("%Y-%m-%d %H:%M")); ud.setdefault("total_refs", 0); _update_user_meta(ud, user)
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"): referrer_id = _verify_ref_token(arg[4:]); await process_referral(user.id, referrer_id, context) if referrer_id else None
    if ud.get("banned", False) and user.id != OWNER_ID: await update.message.reply_text(f"<b>{E_ERRORS} {B('Banned')}</b>\n────────——\nYou have been banned from using this bot.\n────────——", parse_mode="HTML"); return
    if not await require_membership(update, context): return
    await update.message.reply_text(ui_start_screen(user, context), parse_mode="HTML", reply_markup=kb_main(user.id), disable_web_page_preview=True)

MSH_LIMIT = 5000; TRIAL_MASS_DAY_LIMIT = 500
async def cmd_msh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await require_not_banned(update, context): return
    if context.bot_data.get("maintenance") and user.id != OWNER_ID: await update.message.reply_text("⚠️ Bot is under maintenance. Try again later.", parse_mode="HTML"); return
    if not context.bot_data.get("msh_on", True): await update.message.reply_text(f"<b>{E_ERRORS} Shopify Mass gate is currently OFF.</b>", parse_mode="HTML"); return
    if not await require_membership(update, context): return
    ud = get_user_data(user.id, context); premium = is_user_premium(ud); is_trial = not premium and user.id != OWNER_ID; today_str = datetime.now().strftime("%Y-%m-%d"); _update_user_meta(ud, user); plan = ud.get("plan", "TRIAL")
    if is_trial:
        last_date = ud.get("msh_daily_date", "")
        if last_date == today_str: used_today = ud.get("msh_daily_cards", 0); await update.message.reply_text(f"<b>{E_ERRORS} {B('Daily Limit Reached')}</b>\n────────——\nYou already used <b>/msh</b> today.\n\n<b>Used Today:</b>  {used_today} / {TRIAL_MASS_DAY_LIMIT} cards\n<b>Resets:</b>      Tomorrow midnight\n────────——\n💡 Upgrade to <b>Premium</b> for unlimited daily mass checking.", parse_mode="HTML", reply_markup=kb_upgrade()); return
        if ud.get("credits", 0) <= 0: await update.message.reply_text(f"<b>{E_PRO} {B('Credits Used Up!')}</b>\n────────——\nYou've used all your free credits.\n\n<b>💎 Upgrade to Premium</b> for:\n• Unlimited mass checking\n• No daily card caps\n• No credit limits ever\n────────——\nTap <b>Buy Now</b> below to get a plan.", parse_mode="HTML", reply_markup=kb_upgrade()); return
    cards = []; doc = update.message.document or (update.message.reply_to_message.document if update.message.reply_to_message else None)
    if doc:
        if doc.mime_type not in ("text/plain", "application/octet-stream"): await update.message.reply_text("<b>❌ Please send a .txt file with cards (one per line).</b>", parse_mode="HTML"); return
        try:
            file = await doc.get_file(); content = (await file.download_as_bytearray()).decode("utf-8", errors="ignore"); cards = [l.strip() for l in content.splitlines() if l.strip() and "|" in l]
        except Exception as e: await update.message.reply_text(f"<b>❌ Error reading file: {escape(str(e))}</b>", parse_mode="HTML"); return
    else:
        txt = ""
        if update.message.reply_to_message: txt = (update.message.reply_to_message.text or update.message.reply_to_message.caption or "").strip()
        elif context.args: txt = " ".join(context.args)
        cards = [l.strip() for l in txt.splitlines() if l.strip() and "|" in l]
    if not cards: await update.message.reply_text("<b>────────────</b>\n<b>Gate</b>    ➳ Shopify 0-20$\n<b>Command</b> ➳ <code>/msh</code>\n<b>Limit</b>   ➳ Unlimited\n<b>Type</b>    ➳ Mass Checker\n<b>Stop</b>    ➳ Button\n<b>Cost</b>    ➳ ∞ (Premium)\n<b>Credits</b> ➳ ∞\n<b>Status</b>  ➳ ✅ Available\n<b>────────────</b>", parse_mode="HTML"); return
    if len(cards) > MSH_LIMIT: cards = cards[:MSH_LIMIT]
    if is_trial:
        orig = len(cards); trial_credits = ud.get("credits", 0); eff_limit = min(TRIAL_MASS_DAY_LIMIT, trial_credits)
        if orig > eff_limit:
            cards = cards[:eff_limit]; reason = f"{TRIAL_MASS_DAY_LIMIT} cards/day limit" if eff_limit == TRIAL_MASS_DAY_LIMIT else f"{trial_credits} credits"
            await update.message.reply_text(f"<b>{E_ERRORS} {B('Trial Limit Applied')}</b>\n────────——\nYou sent <b>{orig}</b> cards. Limit: <b>{reason}</b>.\nOnly <b>{eff_limit}</b> cards will be checked.\n────────——", parse_mode="HTML")
    valid_cards = []
    for raw in cards:
        parts = raw.split("|")
        if len(parts) != 4: continue
        cc, mm, yy, cvv = [p.strip() for p in parts]; mm = mm.zfill(2)
        if len(yy) == 4: yy = yy[2:]
        valid_cards.append((f"{cc}|{mm}|{yy}|{cvv}", cc))
    if not valid_cards: await update.message.reply_text("<b>❌ No valid cards found (need cc|mm|yy|cvv format).</b>", parse_mode="HTML"); return
    total = len(valid_cards); sites = _load_sites(); proxies = _load_proxies()
    import random as _random; import string as _string; sid = "".join(_random.choices(_string.ascii_uppercase + _string.digits, k=8))
    from sh import _progress_text as _pt, _msh_buttons
    sess = create_msh_session(sid=sid, chat_id=update.message.chat_id, user_id=user.id, msg_id=0, user_msg_id=update.message.message_id, total=total, user_obj=user, plan=plan)
    msg = await update.message.reply_text(_pt(sess), parse_mode="HTML", reply_markup=_msh_buttons(sid, running=True), disable_web_page_preview=True)
    sess["msg_id"] = msg.message_id
    asyncio.create_task(run_mass_batch(context.bot, sid, valid_cards, user, plan, sites, proxies, bot_data=context.bot_data))
    if is_trial: ud["credits"] = max(0, ud.get("credits", 0) - total); ud["msh_daily_date"] = today_str; ud["msh_daily_cards"] = total
    ud["total_checks"] = ud.get("total_checks", 0) + total; ud["last_gate"] = "Shopify | 0-20$"; ud["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M")

async def cmd_1day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    count = 1
    if context.args:
        try: count = int(context.args[0])
        except: pass
    plan_emoji = tg_emoji(get_plan_emoji_id("CORE"), "⭐"); keys_store = context.bot_data.setdefault("keys", {}); generated = []
    for _ in range(count): key = gen_code(12); keys_store[key] = {"plan": "CORE", "days": 1, "used": False}; generated.append(key)
    if count == 1: await update.message.reply_text(f"<b>{E_LIVE} {B('1-Day Key Generated')}</b>\n────────——\n<b>Key</b>    ➳ <code>{generated[0]}</code>\n<b>Plan</b>   ➳ {B('Core')} {plan_emoji}\n<b>Days</b>   ➳ 1\n────────——\nRedeem: <code>/rm {generated[0]}</code>", parse_mode="HTML")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_not_banned(update, context): return
    if not await require_membership(update, context): return
    t = time.time(); msg = await update.message.reply_text('<b>🔄 Pinging...</b>', parse_mode="HTML"); ms = int((time.time() - t) * 1000)
    await msg.edit_text(f'<b>✅ {B("Pong")}</b>\n────────——\n<b>⏱ ➳ {ms}ms</b>\n────────——', parse_mode="HTML")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_not_banned(update, context): return
    if not await require_membership(update, context): return
    user_data = context.bot_data.get("user_data", {}); board = sorted([{"display": f"@{ud['username']}" if ud.get("username") else ud.get("first_name") or ud.get("name") or "User", "count": ud.get("total_charged", 0)} for ud in user_data.values() if ud.get("total_charged", 0) > 0], key=lambda x: x["count"], reverse=True)[:5]
    lines = ["⚜ <b>Leaderboard</b> 💎", "────────————"]
    if not board: lines.append("No charge cards yet — be the first! 🎯")
    else:
        for i, entry in enumerate(board): lines.append(f"{i+1}. {escape(entry['display'])} ➳ <b>{entry['count']}</b> 💎 🔝")
    lines += ["────────————", "⚡ Dev ➳ @superman8585_bot🦇"]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_not_banned(update, context): return
    if not await require_membership(update, context): return
    core_e = tg_emoji(PLAN_EMOJIS["CORE"], "⭐"); elite_e = tg_emoji(PLAN_EMOJIS["ELITE"], "⭐"); root_e = tg_emoji(PLAN_EMOJIS["ROOT"], "⭐")
    txt = f"<b>{core_e} {B('Core')} Plan</b>\n────────——\n<b>Days</b>     ➳ 1\n<b>Credits</b>  ➳ Unlimited\n<b>Price</b>    ➳ 1.5$\n────────——\n<b>{core_e} {B('Core')} Plan</b>\n────────——\n<b>Days</b>     ➳ 7\n<b>Credits</b>  ➳ Unlimited\n<b>Price</b>    ➳ 8$\n────────——\n<b>{elite_e} {B('Elite')} Plan</b>\n────────——\n<b>Days</b>     ➳ 15\n<b>Credits</b>  ➳ Unlimited\n<b>Price</b>    ➳ 12$\n────────——\n<b>{root_e} {B('Root')} Plan</b>\n────────——\n<b>Days</b>     ➳ 30\n<b>Credits</b>  ➳ Unlimited\n<b>Price</b>    ➳ 25$\n────────——"
    await update.message.reply_text(txt, reply_markup=kb_price(), parse_mode="HTML")

async def cmd_rm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_not_banned(update, context): return
    if not await require_membership(update, context): return
    if not context.args: await update.message.reply_text(f"<b>{E_CARD} {B('Redeem Code / Key')}</b>\n────────——\n<b>Usage:</b> <code>/rm CODE</code>\n\nRedeem a <b>credit code</b> to top up your balance,\nor a <b>premium key</b> to activate a plan.\n────────——", parse_mode="HTML"); return
    code = context.args[0].upper().strip(); uid = update.effective_user.id; ud = get_user_data(uid, context); codes = context.bot_data.get("codes", {}); keys = context.bot_data.get("keys", {})
    if code in codes:
        if codes[code]["used"]: await update.message.reply_text(f"<b>{E_ERRORS} Code Already Used</b>\n────────——\nThis code has already been redeemed.\n────────——", parse_mode="HTML"); return
        value = codes[code]["value"]; codes[code]["used"] = True; ud["credits"] = ud.get("credits", 0) + value; ud["codes_redeemed"] = ud.get("codes_redeemed", 0) + 1
        await update.message.reply_text(f"<b>{E_LIVE} {B('Code Redeemed')}</b>\n────────——\n<b>Code</b>           ➳ <code>{code}</code>\n<b>Credits Added</b>  ➳ +{value}\n<b>New Balance</b>    ➳ {ud['credits']}\n────────——", parse_mode="HTML"); return
    if code in keys:
        if keys[code]["used"]: await update.message.reply_text(f"<b>{E_ERRORS} Key Already Used</b>\n────────——\nThis key has already been redeemed.\n────────——", parse_mode="HTML"); return
        keys[code]["used"] = True; p = keys[code]["plan"]; ud["keys_redeemed"] = ud.get("keys_redeemed", 0) + 1; plan_emoji = tg_emoji(get_plan_emoji_id(p), "⭐")
        if "hours" in keys[code]:
            hours = keys[code]["hours"]; expires_ts = time.time() + hours * 3600
            if ud.get("plan", "TRIAL").upper() == "TRIAL": ud["pre_premium_credits"] = ud.get("credits", 150)
            ud["plan"] = p.upper(); ud["expires"] = expires_ts; receipt = gen_receipt(); ud["last_receipt"] = receipt; await _save_premium(context.bot_data)
            exp_str = datetime.fromtimestamp(expires_ts).strftime("%Y-%m-%d %H:%M")
            await update.message.reply_text(f"<b>{E_LIVE} {B('Hour Key Redeemed!')}</b>\n────────——\n<b>Key</b>      ➳ <code>{code}</code>\n<b>Access</b>   ➳ {get_styled_plan(p)} {plan_emoji}\n<b>Duration</b> ➳ {hours} hours\n<b>Expires</b>  ➳ <code>{exp_str}</code>\n<b>Receipt</b>  ➳ <code>{receipt}</code>\n────────——\nYour plan is active! Use /sub to check.", parse_mode="HTML"); return
        d = keys[code]["days"]; receipt = await send_activation_msg(uid, p, d, context)
        await update.message.reply_text(f"<b>{E_LIVE} {B('Key Redeemed')}</b>\n────────——\n<b>Key</b>     ➳ <code>{code}</code>\n<b>Access</b>  ➳ {get_styled_plan(p)} {plan_emoji}\n<b>Days</b>    ➳ {d}\n<b>Receipt</b> ➳ <code>{receipt}</code>\n────────——\nYour plan is now active! Use /sub to check.", parse_mode="HTML"); return
    await update.message.reply_text(f"<b>{E_ERRORS} {B('Invalid Code')}</b>\n────────——\nThis code or key is invalid.\nMake sure you typed it correctly (case-insensitive).\n────────——", parse_mode="HTML")

async def _cmd_sh_gated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_not_banned(update, context): return
    if not await require_membership(update, context): return
    await cmd_sh(update, context)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user = query.from_user; data = query.data
    _self_answering = (data == "check_sub" or data.startswith("mshr:") or data.startswith("mshs:") or data.startswith("stop_msh_") or data.startswith("dl_approved_") or data.startswith("dl_all_") or data.startswith("ogs_") or data.startswith("owner_ban_") or data.startswith("owner_unban_") or data.startswith("owner_resub_") or data.startswith("find_sub_"))
    if not _self_answering:
        try: await query.answer()
        except: pass
    if data == "bmain": await query.message.edit_text(ui_start_screen(user, context), parse_mode="HTML", reply_markup=kb_main(user.id), disable_web_page_preview=True); return
    if data == "mprofile": await query.message.edit_text(ui_full_profile(user, context), parse_mode="HTML", reply_markup=kb_back("bmain"), disable_web_page_preview=True); return
    if data == "mgates": await query.message.edit_text(f"<b>{E_GATE} {B('Gates')}</b>\n────────——\nChoose a gate category:", parse_mode="HTML", reply_markup=kb_gate_main()); return
    if data == "mprice":
        core_e = tg_emoji(PLAN_EMOJIS["CORE"], "⭐"); elite_e = tg_emoji(PLAN_EMOJIS["ELITE"], "⭐"); root_e = tg_emoji(PLAN_EMOJIS["ROOT"], "⭐")
        txt = f"<b>{core_e} {B('Core')}</b>  ➳ 1 day  | 1.5$\n<b>{core_e} {B('Core')}</b>  ➳ 7 days | 8$\n<b>{elite_e} {B('Elite')}</b> ➳ 15 days | 12$\n<b>{root_e} {B('Root')}</b>   ➳ 30 days | 25$\n────────——\nAll plans: Unlimited credits"
        await query.message.edit_text(txt, parse_mode="HTML", reply_markup=kb_price()); return
    if data == "imsh":
        ud_i = get_user_data(user.id, context); prem_i = is_user_premium(ud_i); _today = datetime.now().strftime("%Y-%m-%d")
        if prem_i: limit_line = "Unlimited"; status_line = "✅ Available"; credits_line = "∞"
        else:
            _used = ud_i.get("msh_daily_cards", 0) if ud_i.get("msh_daily_date", "") == _today else 0; _remain = max(0, 500 - _used); _cr = ud_i.get("credits", 0); limit_line = "500 cards / day"; credits_line = str(_cr); status_line = f"🔒 Used today ({_used}/500)" if _used >= 500 else f"⚡ {_remain} cards left today"
        await query.message.edit_text(f"<b>────────────</b>\n<b>Gate</b>    ➳ Shopify 0-20$\n<b>Command</b> ➳ <code>/msh</code>\n<b>Limit</b>   ➳ {limit_line}\n<b>Type</b>    ➳ Mass Checker\n<b>Stop</b>    ➳ Button\n<b>Cost</b>    ➳ {'∞ (Premium)' if prem_i else '1 credit / card'}\n<b>Credits</b> ➳ {credits_line}\n<b>Status</b>  ➳ {status_line}\n<b>────────────</b>", parse_mode="HTML", reply_markup=kb_back("mgates")); return
    if data == "ish":
        ud_i = get_user_data(user.id, context); prem_i = is_user_premium(ud_i); _cr = ud_i.get("credits", 0); credits_line = "∞" if prem_i else str(_cr); status_line = "✅ Available" if (prem_i or _cr > 0) else "🔒 No Credits"
        await query.message.edit_text(f"<b>────────────</b>\n<b>Gate</b>    ➳ Shopify 0-20$\n<b>Command</b> ➳ <code>/sh</code>\n<b>Limit</b>   ➳ {'Unlimited' if prem_i else '1 card / check'}\n<b>Type</b>    ➳ Single Checker\n<b>Stop</b>    ➳ Automatic\n<b>Cost</b>    ➳ {'∞ (Premium)' if prem_i else '1 Credit'}\n<b>Credits</b> ➳ {credits_line}\n<b>Status</b>  ➳ {status_line}\n<b>────────────</b>", parse_mode="HTML", reply_markup=kb_back("mgates")); return
    if data.startswith("mshs:"): await cb_msh_stop(update, context); return
    if data.startswith("mshr:"): await cb_msh_result(update, context); return
    if data.startswith("stop_msh_"):
        task_id = data[len("stop_msh_"):]; tasks = context.bot_data.get("msh_tasks", {})
        if task_id in tasks: tasks[task_id]["running"] = False; await query.answer("⏹ Stopping...", show_alert=False)
        else: await query.answer("Task already finished.", show_alert=True)
        return
    if data.startswith("dl_approved_"):
        task_id = data[len("dl_approved_"):]; results = context.bot_data.get("msh_results", {}).get(task_id)
        if not results or not results.get("approved"): await query.answer("No approved cards found or results expired.", show_alert=True); return
        await query.answer("Sending approved cards file…", show_alert=False); content = "\n".join(results["approved"]).encode("utf-8"); filename = f"approved_{task_id}.txt"
        try: await query.message.reply_document(document=BytesIO(content), filename=filename, caption=f"<b>✅ Approved Cards</b>\nTotal: <b>{len(results['approved'])}</b> cards\nGate: Shopify 0-20$", parse_mode="HTML")
        except: pass
        return
    if data.startswith("dl_all_"):
        task_id = data[len("dl_all_"):]; results = context.bot_data.get("msh_results", {}).get(task_id)
        if not results or not results.get("all"): await query.answer("Results expired or not found.", show_alert=True); return
        await query.answer("Sending all results file…", show_alert=False); content = "\n".join(results["all"]).encode("utf-8"); filename = f"all_results_{task_id}.txt"
        try: await query.message.reply_document(document=BytesIO(content), filename=filename, caption=f"<b>📋 All Checked Cards</b>\nTotal: <b>{len(results['all'])}</b> cards\nGate: Shopify 0-20$", parse_mode="HTML")
        except: pass
        return
    pay_map = {"pay1d": ("Core", 1.5, 1, "CORE"), "pay10": ("Core", 8, 7, "CORE"), "pay15": ("Elite", 12, 15, "ELITE"), "pay30": ("Root", 25, 30, "ROOT")}
    if data in pay_map:
        plan_n, price, days, plan_key = pay_map[data]; plan_emoji = tg_emoji(get_plan_emoji_id(plan_key), "⭐")
        await query.message.edit_text(f"<b>{plan_emoji} {B(plan_n)} Plan</b>\n────────——\n<b>Price</b>   ➳ ${price}\n<b>Days</b>    ➳ {days}\n<b>Credits</b> ➳ Unlimited\n────────——\nContact support to purchase:", parse_mode="HTML", reply_markup=kb_payment()); return
    if user.id == OWNER_ID:
        if data.startswith("ogs_"):
            parts = data.split("_"); plan_key = parts[1]; days = int(parts[2]); uid = int(parts[3]); ud_t = get_user_data(uid, context); ud_t["plan"] = plan_key; ud_t["expires"] = time.time() + days * 86400; plan_emoji = tg_emoji(get_plan_emoji_id(plan_key), "⭐"); target_name = ud_t.get("name", f"User {uid}"); exp_str = datetime.fromtimestamp(ud_t["expires"]).strftime("%Y-%m-%d %H:%M")
            await _save_premium(context.bot_data)
            try: await send_activation_msg(uid, plan_key, days, context)
            except: pass
            await query.answer(f"✅ {plan_key} {days}d granted!", show_alert=True)
            try: await query.message.edit_text(f"<b>{E_LIVE} {B('Plan Granted')}</b>\n────────——\n<b>User</b>    ➳ {target_name} (<code>{uid}</code>)\n<b>Plan</b>    ➳ {get_styled_plan(plan_key)} {plan_emoji}\n<b>Days</b>    ➳ {days}\n<b>Expires</b> ➳ {exp_str}\n────────——", parse_mode="HTML")
            except: pass
            return
        if data.startswith("owner_ban_"): uid = int(data.split("_")[-1]); get_user_data(uid, context)["banned"] = True; await query.answer(f"Banned {uid}", show_alert=True); return
        if data.startswith("owner_unban_"): uid = int(data.split("_")[-1]); get_user_data(uid, context)["banned"] = False; await query.answer(f"Unbanned {uid}", show_alert=True); return
        if data.startswith("owner_resub_"): uid = int(data.split("_")[-1]); ud = get_user_data(uid, context); ud["plan"] = "TRIAL"; ud["expires"] = 0; await _save_premium(context.bot_data); await query.answer(f"Premium removed for {uid}", show_alert=True); return
        if data.startswith("find_sub_"): uid = int(data.split("_")[-1]); await query.answer(f"Use: /sub {uid}  to grant a plan.", show_alert=True); return

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Conflict): logger.warning("CONFLICT detected — another session active. Waiting 30 s before retry..."); await asyncio.sleep(30); return
    if isinstance(err, (NetworkError, Forbidden)): logger.warning(f"Network/Forbidden error: {err}"); return
    logger.error(f"Unhandled exception: {err}", exc_info=err)

async def _post_shutdown(app: Application) -> None:
    await db.close_db(app.bot_data)
    try: await stop_probe_background()
    except: pass

async def _post_init(app: Application) -> None:
    await asyncio.to_thread(_load_premium_file, app.bot_data); await db.attach(app)
    try:
        import config as _cfg; me = await app.bot.get_me()
        if me.username: _cfg.BOT_USERNAME = me.username; _cfg.BOT_LINK = f"https://t.me/{me.username}"
    except: pass
    try:
        await app.bot.delete_webhook(drop_pending_updates=True); await asyncio.sleep(5)
    except: pass
    try:
        all_sites = _load_sites(); proxies = _load_proxies(); start_probe_background(all_sites, proxies)
    except: pass

def main():
    if not acquire_instance_lock(): logger.critical("Another instance is already running. Exiting."); return
    try:
        _request = HTTPXRequest(connection_pool_size=512, connect_timeout=15.0, read_timeout=60.0, write_timeout=60.0, pool_timeout=120.0)
        _get_updates_request = HTTPXRequest(connection_pool_size=8, connect_timeout=15.0, read_timeout=65.0, write_timeout=60.0, pool_timeout=120.0)
        app = Application.builder().token(BOT_TOKEN).request(_request).get_updates_request(_get_updates_request).concurrent_updates(1024).post_init(_post_init).post_shutdown(_post_shutdown).build()
        app.add_handler(CommandHandler("start", cmd_start)); app.add_handler(CommandHandler("ping", cmd_ping)); app.add_handler(CommandHandler("status", cmd_status)); app.add_handler(CommandHandler("plan", cmd_plan)); app.add_handler(CommandHandler("sub", cmd_sub)); app.add_handler(CommandHandler("rm", cmd_rm)); app.add_handler(get_bin_lookup_handler()); app.add_handler(CommandHandler("sh", _cmd_sh_gated)); app.add_handler(CommandHandler("msh", cmd_msh)); app.add_handler(get_me_handler())
        app.add_handler(CommandHandler("cards", cmd_cards)); app.add_handler(CommandHandler("1day", cmd_1day)); app.add_handler(CommandHandler("gen", cmd_gen)); app.add_handler(CommandHandler("add", cmd_add)); app.add_handler(CommandHandler("rem", cmd_rem)); app.add_handler(CommandHandler("find", cmd_find)); app.add_handler(CommandHandler("resub", cmd_resub)); app.add_handler(CommandHandler("rsub", cmd_resub)); app.add_handler(CommandHandler("ban", cmd_ban)); app.add_handler(CommandHandler("unban", cmd_unban)); app.add_handler(CommandHandler("info", cmd_info)); app.add_handler(CommandHandler("maintenance", cmd_maintenance)); app.add_handler(CommandHandler("onsh", cmd_onsh)); app.add_handler(CommandHandler("offsh", cmd_offsh)); app.add_handler(CommandHandler("onmsh", cmd_onmsh)); app.add_handler(CommandHandler("offmsh", cmd_offmsh))
        app.add_handler(CallbackQueryHandler(callback_handler)); app.add_error_handler(error_handler)
        logger.info(f"Superman Bot {VERSION} starting..."); app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except KeyboardInterrupt: pass
    except Exception as _crash_err: logger.error(f"Bot crashed: {_crash_err}", exc_info=True); raise
    finally: release_instance_lock()

if __name__ == "__main__":
    main()
