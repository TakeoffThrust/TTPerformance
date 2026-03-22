import asyncio
import logging
import os
import re
import time
import html
import sqlite3
from typing import List, Optional, Tuple

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
TG_USERNAME = os.getenv("TG_USERNAME", "your_username")
MAX_UPLOAD_MB = 60

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in environment")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "catalog.db")

logging.basicConfig(level=logging.INFO)

# ================== DB ==================
def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    conn = db_connect()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ecus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(brand_id, name),
            FOREIGN KEY(brand_id) REFERENCES brands(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bodies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ecu_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(ecu_id, name),
            FOREIGN KEY(ecu_id) REFERENCES ecus(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(body_id, name),
            FOREIGN KEY(body_id) REFERENCES bodies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            link TEXT NOT NULL DEFAULT '',
            pkey TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(folder_id) REFERENCES folders(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    conn.close()

def seed_if_empty() -> None:
    """Заполняем стартовыми данными, если база пустая."""
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM brands")
    if cur.fetchone()["c"] > 0:
        conn.close()
        return

    def get_or_create_brand(name: str) -> int:
        cur.execute("INSERT OR IGNORE INTO brands(name) VALUES (?)", (name,))
        cur.execute("SELECT id FROM brands WHERE name=?", (name,))
        return int(cur.fetchone()["id"])

    def get_or_create_ecu(brand_id: int, name: str) -> int:
        cur.execute("INSERT OR IGNORE INTO ecus(brand_id, name) VALUES (?,?)", (brand_id, name))
        cur.execute("SELECT id FROM ecus WHERE brand_id=? AND name=?", (brand_id, name))
        return int(cur.fetchone()["id"])

    def get_or_create_body(ecu_id: int, name: str) -> int:
        cur.execute("INSERT OR IGNORE INTO bodies(ecu_id, name) VALUES (?,?)", (ecu_id, name))
        cur.execute("SELECT id FROM bodies WHERE ecu_id=? AND name=?", (ecu_id, name))
        return int(cur.fetchone()["id"])

    def get_or_create_folder(body_id: int, name: str) -> int:
        cur.execute("INSERT OR IGNORE INTO folders(body_id, name) VALUES (?,?)", (body_id, name))
        cur.execute("SELECT id FROM folders WHERE body_id=? AND name=?", (body_id, name))
        return int(cur.fetchone()["id"])

    def add_product(folder_id: int, title: str, price: int, link: str, pkey: str) -> None:
        cur.execute(
            "INSERT INTO products(folder_id, title, price, link, pkey) VALUES (?,?,?,?,?)",
            (folder_id, title, price, link, pkey),
        )

    # ===== BMW =====
    bmw = get_or_create_brand("BMW")
    bmw_ecu = get_or_create_ecu(bmw, "Bosch MD1CP002")
    bmw_body = get_or_create_body(bmw_ecu, "G05")
    bmw_folder = get_or_create_folder(bmw_body, "BMW_G05_MD1CP002")
    add_product(bmw_folder, "Original", 1000, "https://mega.nz/file/DDZR2QqC", "5u5F8nzgGIS9W8Lf27AK0iX7by19zrbYkg3wbd-kHYM")
    add_product(bmw_folder, "Stage 1", 1000, "https://mega.nz/file/DDZR2QqC", "Ключ выдаётся продавцом")
    add_product(bmw_folder, "EGR OFF", 1000, "https://mega.nz/file/DDZR2QqC", "Ключ выдаётся продавцом")
    add_product(bmw_folder, "DPF OFF", 1000, "https://mega.nz/file/DDZR2QqC", "Ключ выдаётся продавцом")
    add_product(bmw_folder, "SCR OFF", 1000, "https://mega.nz/file/DDZR2QqC", "Ключ выдаётся продавцом")
    add_product(bmw_folder, "Stage1_EGR_DPF_SCR", 1000, "https://mega.nz/file/DDZR2QqC", "Ключ выдаётся продавцом")

    # ===== AUDI =====
    audi = get_or_create_brand("AUDI")
    audi_ecu = get_or_create_ecu(audi, "EDC17C74")
    audi_body = get_or_create_body(audi_ecu, "A4-B9 / 2.0TDI-190PS")
    audi_folder = get_or_create_folder(audi_body, "058546_9970_04L906026T")
    add_product(audi_folder, "Original", 1000, "https://mega.nz/file/DOISkRaD", "Ключ выдаётся продавцом")
    add_product(audi_folder, "EGR_by_TTPerformance", 5000, "https://mega.nz/file/bCZgXALC", "Ключ выдаётся продавцом")
    add_product(audi_folder, "DPF_by_TTPerformance", 7000, "https://mega.nz/file/DeAgzDhL", "Ключ выдаётся продавцом")
    add_product(audi_folder, "DPF_EGR_by_TTPerformance", 8000, "https://mega.nz/file/bfxRmJ4a", "Ключ выдаётся продавцом")

    # ===== FORD =====
    ford = get_or_create_brand("FORD")
    ford_ecu = get_or_create_ecu(ford, "SID212/212EVO")

    ford_body1 = get_or_create_body(ford_ecu, "Ford_Transit_Custom_2017_2.0_TDCI_EcoBlue_EU6_190_hp")
    ford_folder1 = get_or_create_folder(ford_body1, "JK21-14C204-GP")
    add_product(ford_folder1, "Original", 5000, "https://mega.nz/file/7S4h3apS", "Ключ выдаётся продавцом")
    add_product(ford_folder1, "Stage1+EGR+DPF+SCR+SS_by_TTPerformance", 18000, "https://mega.nz/file/eDonWLRb", "Ключ выдаётся продавцом")

    ford_body2 = get_or_create_body(ford_ecu, "Ford_Galaxy_2019_(MKIII-phaseII)_190_hp")
    ford_folder2 = get_or_create_folder(ford_body2, "Ford_Galaxy_2019_MKIII_phaseII_190hp")
    add_product(ford_folder2, "Original", 5000, "https://mega.nz/file/PASTE_LINK_HERE", "Ключ выдаётся продавцом")
    add_product(ford_folder2, "Stage1_by_TTPerformance", 18000, "https://mega.nz/file/PASTE_LINK_HERE", "Ключ выдаётся продавцом")

    # ===== KIA =====
    kia = get_or_create_brand("KIA")
    kia_ecu = get_or_create_ecu(kia, "EDC17C57")
    kia_body = get_or_create_body(kia_ecu, "Sorento 2.2")
    kia_folder = get_or_create_folder(kia_body, "KIA_Sorento_2.2_EDC17C57")
    add_product(kia_folder, "Original", 1000, "https://mega.nz/file/PASTE_LINK_HERE", "Ключ выдаётся продавцом")
    add_product(kia_folder, "Stage1_by_TTPerformance", 8000, "https://mega.nz/file/PASTE_LINK_HERE", "Ключ выдаётся продавцом")

    conn.commit()
    conn.close()

# ================== FSM ==================
class CustomFlow(StatesGroup):
    waiting_file = State()

class AdminFlow(StatesGroup):
    menu = State()

class AdminAddBrand(StatesGroup):
    name = State()

class AdminAddEcu(StatesGroup):
    pick_brand = State()
    name = State()

class AdminAddBody(StatesGroup):
    pick_ecu = State()
    name = State()

class AdminAddFolder(StatesGroup):
    pick_body = State()
    name = State()

class AdminAddProduct(StatesGroup):
    pick_folder = State()
    title = State()
    price = State()
    link = State()
    pkey = State()

class AdminDelete(StatesGroup):
    pick_type = State()
    pick_item = State()

# ================== ACCESS ==================
def is_admin(user_id: int) -> bool:
    return ADMIN_ID and user_id == ADMIN_ID

# ================== UI (reply) ==================
def main_menu_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🛍 Магазин"), types.KeyboardButton(text="🧩 Заказать софт")],
            [types.KeyboardButton(text="💬 Связаться"), types.KeyboardButton(text="ℹ️ Помощь")],
            [types.KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True
    )

def back_reply_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

def admin_reply_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Марка"), types.KeyboardButton(text="➕ Блок")],
            [types.KeyboardButton(text="➕ Кузов"), types.KeyboardButton(text="➕ Папка")],
            [types.KeyboardButton(text="➕ Версия"), types.KeyboardButton(text="❌ Удалить")],
            [types.KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True
    )

def contact_inline_kb() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💬 Открыть чат", url=f"https://t.me/{TG_USERNAME}")],
        [types.InlineKeyboardButton(text="🏠 Домой", callback_data="nav:home")],
    ])

# ================== TEXTS ==================
HOME_TEXT_MD = (
    "🚗 *Каталог прошивок*\n\n"
    "Этот бот поможет тебе:\n"
    "• 🚀 увеличить производительность твоей машины\n"
    "• 🌿 помочь разобраться с экологическими проблемами (EGR / DPF / SCR)\n"
    "• 🧩 подобрать прошивку под ECU / кузов\n"
    "• 💳 получить ключ/доступ после оплаты\n\n"
    "Выбери действие ниже 👇"
)

HELP_TEXT_MD = (
    "ℹ️ *Помощь*\n\n"
    "• Магазин: Марка → Блок → Кузов → Папка → Версии\n"
    "• Кнопка ⬅️ Назад — шаг назад\n"
    "• /id — узнать твой Telegram ID\n"
    "• /admin — админка (только ADMIN_ID)\n"
)

CUSTOM_TEXT_MD = (
    "🧩 *Заказать софт*\n\n"
    "Загрузи файл *как документ*.\n"
    f"Лимит: до {MAX_UPLOAD_MB} MB."
)

# ================== SHOP KB (inline) ==================
def kb_home_inline() -> List[List[types.InlineKeyboardButton]]:
    return [[types.InlineKeyboardButton(text="🏠 Домой", callback_data="nav:home")]]

def kb_back_inline(callback_data: str) -> List[List[types.InlineKeyboardButton]]:
    return [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)]]

def kb_brands_inline() -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute("SELECT id, name FROM brands ORDER BY name").fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["name"], callback_data=f"shop:brand:{r['id']}")] for r in rows]
    keyboard += kb_home_inline()
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def kb_ecus_inline(brand_id: int) -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute("SELECT id, name FROM ecus WHERE brand_id=? ORDER BY name", (brand_id,)).fetchall()
    brand = conn.execute("SELECT name FROM brands WHERE id=?", (brand_id,)).fetchone()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["name"], callback_data=f"shop:ecu:{r['id']}")] for r in rows]
    keyboard += kb_back_inline("shop:brands")
    keyboard += kb_home_inline()
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard), (brand["name"] if brand else "—")

def kb_bodies_inline(ecu_id: int) -> Tuple[types.InlineKeyboardMarkup, str]:
    conn = db_connect()
    ecu = conn.execute(
        "SELECT e.name AS ecu, b.name AS brand, b.id AS brand_id "
        "FROM ecus e JOIN brands b ON b.id=e.brand_id WHERE e.id=?",
        (ecu_id,)
    ).fetchone()
    rows = conn.execute("SELECT id, name FROM bodies WHERE ecu_id=? ORDER BY name", (ecu_id,)).fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["name"], callback_data=f"shop:body:{r['id']}")] for r in rows]
    keyboard += kb_back_inline(f"shop:brand:{ecu['brand_id']}")
    keyboard += kb_home_inline()
    title = f"{ecu['brand']} → {ecu['ecu']}" if ecu else "—"
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard), title

def kb_folders_inline(body_id: int) -> Tuple[types.InlineKeyboardMarkup, str, int]:
    conn = db_connect()
    info = conn.execute(
        "SELECT bo.name AS body, e.id AS ecu_id, e.name AS ecu, br.name AS brand "
        "FROM bodies bo JOIN ecus e ON e.id=bo.ecu_id JOIN brands br ON br.id=e.brand_id "
        "WHERE bo.id=?",
        (body_id,)
    ).fetchone()
    rows = conn.execute("SELECT id, name FROM folders WHERE body_id=? ORDER BY name", (body_id,)).fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["name"], callback_data=f"shop:folder:{r['id']}")] for r in rows]
    keyboard += kb_back_inline(f"shop:ecu:{info['ecu_id']}")
    keyboard += kb_home_inline()
    title = f"{info['brand']} → {info['ecu']} → {info['body']}"
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard), title, int(info["ecu_id"])

def kb_products_inline(folder_id: int) -> Tuple[types.InlineKeyboardMarkup, str, int]:
    conn = db_connect()
    info = conn.execute(
        "SELECT f.name AS folder, bo.id AS body_id, bo.name AS body, e.name AS ecu, br.name AS brand "
        "FROM folders f JOIN bodies bo ON bo.id=f.body_id JOIN ecus e ON e.id=bo.ecu_id "
        "JOIN brands br ON br.id=e.brand_id WHERE f.id=?",
        (folder_id,)
    ).fetchone()
    rows = conn.execute(
        "SELECT id, title, price FROM products WHERE folder_id=? ORDER BY id",
        (folder_id,)
    ).fetchall()
    conn.close()
    keyboard = [
        [types.InlineKeyboardButton(text=f"{r['title']} • {r['price']}₽", callback_data=f"shop:prod:{r['id']}")]
        for r in rows
    ]
    keyboard += kb_back_inline(f"shop:body:{info['body_id']}")
    keyboard += kb_home_inline()
    title = f"{info['brand']} → {info['ecu']} → {info['body']}\n<b>{html.escape(info['folder'])}</b>"
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard), title, int(info["body_id"])

def kb_product_view_inline(product_id: int, folder_id: int) -> types.InlineKeyboardMarkup:
    keyboard = [
        [types.InlineKeyboardButton(text="💳 Оплатил — запросить ключ", callback_data=f"pay:req:{product_id}")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"shop:folder:{folder_id}")],
        [types.InlineKeyboardButton(text="🏠 Домой", callback_data="nav:home")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# ================== ADMIN KB (inline pickers) ==================
def kb_pick_brands(prefix: str, back: str) -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute("SELECT id, name FROM brands ORDER BY name").fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["name"], callback_data=f"{prefix}:{r['id']}")] for r in rows]
    keyboard += [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back)]]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def kb_pick_ecus(prefix: str, back: str) -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute(
        "SELECT e.id, (b.name || ' • ' || e.name) AS title "
        "FROM ecus e JOIN brands b ON b.id=e.brand_id ORDER BY b.name, e.name"
    ).fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["title"], callback_data=f"{prefix}:{r['id']}")] for r in rows]
    keyboard += [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back)]]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def kb_pick_bodies(prefix: str, back: str) -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute(
        "SELECT bo.id, (b.name || ' • ' || e.name || ' • ' || bo.name) AS title "
        "FROM bodies bo JOIN ecus e ON e.id=bo.ecu_id JOIN brands b ON b.id=e.brand_id "
        "ORDER BY b.name, e.name, bo.name"
    ).fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["title"], callback_data=f"{prefix}:{r['id']}")] for r in rows]
    keyboard += [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back)]]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def kb_pick_folders(prefix: str, back: str) -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute(
        "SELECT f.id, (b.name || ' • ' || e.name || ' • ' || bo.name || ' • ' || f.name) AS title "
        "FROM folders f JOIN bodies bo ON bo.id=f.body_id JOIN ecus e ON e.id=bo.ecu_id "
        "JOIN brands b ON b.id=e.brand_id ORDER BY b.name, e.name, bo.name, f.name"
    ).fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["title"], callback_data=f"{prefix}:{r['id']}")] for r in rows]
    keyboard += [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back)]]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

def kb_pick_products(prefix: str, back: str) -> types.InlineKeyboardMarkup:
    conn = db_connect()
    rows = conn.execute(
        "SELECT p.id, (b.name || ' • ' || e.name || ' • ' || bo.name || ' • ' || f.name || ' • ' || p.title) AS title "
        "FROM products p JOIN folders f ON f.id=p.folder_id JOIN bodies bo ON bo.id=f.body_id "
        "JOIN ecus e ON e.id=bo.ecu_id JOIN brands b ON b.id=e.brand_id "
        "ORDER BY b.name, e.name, bo.name, f.name, p.id"
    ).fetchall()
    conn.close()
    keyboard = [[types.InlineKeyboardButton(text=r["title"], callback_data=f"{prefix}:{r['id']}")] for r in rows]
    keyboard += [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back)]]
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# ================== PAY FLOW ==================
PENDING = {}  # req_id -> dict

def new_req_id() -> str:
    return f"REQ{int(time.time()*1000)}"

def kb_admin_req(req_id: str) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Выдать ключ", callback_data=f"admin:approve:{req_id}")],
        [types.InlineKeyboardButton(text="⛔️ Отказать", callback_data=f"admin:deny:{req_id}")],
    ])

# ================== HANDLERS: START / MENU ==================
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(HOME_TEXT_MD, reply_markup=main_menu_kb(), parse_mode="Markdown")

async def cmd_id(message: types.Message):
    await message.answer(f"Твой Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

async def menu_shop(message: types.Message, state: FSMContext):
    await state.set_state(None)
    await message.answer("🛍 <b>Каталог</b>\nВыбери марку:", reply_markup=kb_brands_inline(), parse_mode="HTML")

async def menu_custom(message: types.Message, state: FSMContext):
    await state.set_state(CustomFlow.waiting_file)
    await message.answer(CUSTOM_TEXT_MD, reply_markup=back_reply_kb(), parse_mode="Markdown")

async def menu_contact(message: types.Message, state: FSMContext):
    await state.set_state(None)
    await message.answer("💬 <b>Связаться со мной</b>", reply_markup=contact_inline_kb(), parse_mode="HTML")

async def menu_help(message: types.Message, state: FSMContext):
    await state.set_state(None)
    await message.answer(HELP_TEXT_MD, reply_markup=back_reply_kb(), parse_mode="Markdown")

async def menu_back(message: types.Message, state: FSMContext):
    # Простая логика: назад из текстовых экранов -> домой
    await state.clear()
    await message.answer(HOME_TEXT_MD, reply_markup=main_menu_kb(), parse_mode="Markdown")

async def nav_home(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer(HOME_TEXT_MD, reply_markup=main_menu_kb(), parse_mode="Markdown")
    await call.answer()

# ================== HANDLERS: SHOP CALLBACKS ==================
async def cb_shop_brands(call: types.CallbackQuery):
    await call.message.edit_text("🛍 <b>Каталог</b>\nВыбери марку:", reply_markup=kb_brands_inline(), parse_mode="HTML")
    await call.answer()

async def cb_shop_brand(call: types.CallbackQuery):
    brand_id = int(call.data.split("shop:brand:", 1)[1])
    kb, brand_name = kb_ecus_inline(brand_id)
    await call.message.edit_text(f"<b>{html.escape(brand_name)}</b>\nВыбери блок:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

async def cb_shop_ecu(call: types.CallbackQuery):
    ecu_id = int(call.data.split("shop:ecu:", 1)[1])
    kb, title = kb_bodies_inline(ecu_id)
    await call.message.edit_text(f"{html.escape(title)}\nВыбери кузов:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

async def cb_shop_body(call: types.CallbackQuery):
    body_id = int(call.data.split("shop:body:", 1)[1])
    kb, title, _ecu_id = kb_folders_inline(body_id)
    await call.message.edit_text(f"{html.escape(title)}\nПапки:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

async def cb_shop_folder(call: types.CallbackQuery):
    folder_id = int(call.data.split("shop:folder:", 1)[1])
    kb, title, _body_id = kb_products_inline(folder_id)
    await call.message.edit_text(f"{title}\nВерсии:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

async def cb_shop_prod(call: types.CallbackQuery):
    product_id = int(call.data.split("shop:prod:", 1)[1])
    conn = db_connect()
    p = conn.execute("SELECT id, folder_id, title, price, link, pkey FROM products WHERE id=?", (product_id,)).fetchone()
    info = conn.execute(
        "SELECT br.name AS brand, e.name AS ecu, bo.name AS body, f.name AS folder "
        "FROM products p "
        "JOIN folders f ON f.id=p.folder_id "
        "JOIN bodies bo ON bo.id=f.body_id "
        "JOIN ecus e ON e.id=bo.ecu_id "
        "JOIN brands br ON br.id=e.brand_id "
        "WHERE p.id=?",
        (product_id,)
    ).fetchone()
    conn.close()
    if not p or not info:
        await call.answer("Товар не найден", show_alert=True)
        return

    text = (
        f"{html.escape(info['brand'])} → {html.escape(info['ecu'])} → {html.escape(info['body'])}\n"
        f"<b>{html.escape(info['folder'])}</b>\n\n"
        f"Версия: <b>{html.escape(p['title'])}</b>\n"
        f"Цена: <b>{int(p['price'])} ₽</b>\n\n"
        f"Ссылка (без ключа):\n{html.escape(p['link'])}\n\n"
        f"Ключ/доступ выдаётся <b>после оплаты</b>."
    )
    await call.message.edit_text(text, reply_markup=kb_product_view_inline(int(p["id"]), int(p["folder_id"])), parse_mode="HTML")
    await call.answer()

# ================== PAY CALLBACKS ==================
async def cb_pay_request(call: types.CallbackQuery, bot: Bot):
    product_id = int(call.data.split("pay:req:", 1)[1])

    if not ADMIN_ID or ADMIN_ID <= 0:
        await call.answer("ADMIN_ID не настроен (/id)", show_alert=True)
        return

    conn = db_connect()
    p = conn.execute("SELECT id, folder_id, title, price, link, pkey FROM products WHERE id=?", (product_id,)).fetchone()
    info = conn.execute(
        "SELECT br.name AS brand, e.name AS ecu, bo.name AS body, f.name AS folder "
        "FROM products p "
        "JOIN folders f ON f.id=p.folder_id "
        "JOIN bodies bo ON bo.id=f.body_id "
        "JOIN ecus e ON e.id=bo.ecu_id "
        "JOIN brands br ON br.id=e.brand_id "
        "WHERE p.id=?",
        (product_id,)
    ).fetchone()
    conn.close()
    if not p or not info:
        await call.answer("Товар не найден", show_alert=True)
        return

    req_id = new_req_id()
    PENDING[req_id] = {
        "user_id": call.from_user.id,
        "username": call.from_user.username or "",
        "product_id": product_id,
        "brand": info["brand"],
        "ecu": info["ecu"],
        "body": info["body"],
        "folder": info["folder"],
        "title": p["title"],
        "price": int(p["price"]),
        "link": p["link"],
        "key": p["pkey"],
        "ts": time.time(),
    }

    await call.message.answer("✅ Заявка отправлена. После подтверждения оплаты пришлю ключ/доступ.")
    await call.answer("Отправлено ✅")

    admin_text = (
        "💳 <b>Запрос ключа (после оплаты)</b>\n\n"
        f"REQ: <code>{html.escape(req_id)}</code>\n"
        f"User: <code>{call.from_user.id}</code> (@{html.escape(call.from_user.username or '—')})\n\n"
        f"{html.escape(info['brand'])} / {html.escape(info['ecu'])} / {html.escape(info['body'])}\n"
        f"Папка: <code>{html.escape(info['folder'])}</code>\n"
        f"Версия: <b>{html.escape(p['title'])}</b>\n"
        f"Цена: <b>{int(p['price'])} ₽</b>\n"
        f"MEGA: {html.escape(p['link'])}\n"
    )
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=kb_admin_req(req_id))

async def cb_admin_approve(call: types.CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    req_id = call.data.split("admin:approve:", 1)[1]
    req = PENDING.get(req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    user_text = (
        "✅ <b>Доступ выдан</b>\n\n"
        f"{html.escape(req['brand'])} / {html.escape(req['ecu'])} / {html.escape(req['body'])}\n"
        f"Папка: <code>{html.escape(req['folder'])}</code>\n"
        f"Версия: <b>{html.escape(req['title'])}</b>\n"
        f"Цена: <b>{req['price']} ₽</b>\n\n"
        f"Ссылка:\n{html.escape(req['link'])}\n\n"
        f"🔑 Ключ/доступ:\n<code>{html.escape(req['key'])}</code>"
    )
    await bot.send_message(req["user_id"], user_text, parse_mode="HTML")
    await call.message.edit_text(f"✅ Выдано: <code>{html.escape(req_id)}</code>", parse_mode="HTML")
    await call.answer("Выдано ✅")
    PENDING.pop(req_id, None)

async def cb_admin_deny(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    req_id = call.data.split("admin:deny:", 1)[1]
    PENDING.pop(req_id, None)
    await call.message.edit_text(f"⛔️ Отказ: <code>{html.escape(req_id)}</code>", parse_mode="HTML")
    await call.answer("Ок")

# ================== ADMIN: MENU ==================
async def cmd_admin(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Нет доступа")
        return
    await state.set_state(AdminFlow.menu)
    await message.answer("🔧 Админка", reply_markup=admin_reply_kb())

# ---- add brand
async def admin_add_brand_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddBrand.name)
    await message.answer("Введи название марки:", reply_markup=back_reply_kb())

async def admin_add_brand_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if not name:
        await message.answer("Название пустое. Введи ещё раз.")
        return
    conn = db_connect()
    try:
        conn.execute("INSERT INTO brands(name) VALUES (?)", (name,))
        conn.commit()
        await message.answer(f"✅ Марка добавлена: {name}", reply_markup=admin_reply_kb())
        await state.set_state(AdminFlow.menu)
    except sqlite3.IntegrityError:
        await message.answer("❌ Такая марка уже есть. Введи другое имя.")
    finally:
        conn.close()

# ---- add ecu
async def admin_add_ecu_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddEcu.pick_brand)
    await message.answer("Выбери марку для нового блока:", reply_markup=kb_pick_brands("admin:add_ecu_brand", "admin:back_menu"))

async def admin_add_ecu_pick_brand(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    brand_id = int(call.data.split("admin:add_ecu_brand:", 1)[1])
    await state.update_data(brand_id=brand_id)
    await state.set_state(AdminAddEcu.name)
    await call.message.answer("Введи название блока (ECU):", reply_markup=back_reply_kb())
    await call.answer()

async def admin_add_ecu_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    brand_id = int(data["brand_id"])
    name = message.text.strip()
    if not name:
        await message.answer("Название пустое. Введи ещё раз.")
        return
    conn = db_connect()
    try:
        conn.execute("INSERT INTO ecus(brand_id, name) VALUES (?,?)", (brand_id, name))
        conn.commit()
        await message.answer("✅ Блок добавлен.", reply_markup=admin_reply_kb())
        await state.set_state(AdminFlow.menu)
    except sqlite3.IntegrityError:
        await message.answer("❌ Такой блок уже есть у этой марки. Введи другое имя.")
    finally:
        conn.close()

# ---- add body
async def admin_add_body_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddBody.pick_ecu)
    await message.answer("Выбери блок, к которому добавить кузов:", reply_markup=kb_pick_ecus("admin:add_body_ecu", "admin:back_menu"))

async def admin_add_body_pick_ecu(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    ecu_id = int(call.data.split("admin:add_body_ecu:", 1)[1])
    await state.update_data(ecu_id=ecu_id)
    await state.set_state(AdminAddBody.name)
    await call.message.answer("Введи название кузова:", reply_markup=back_reply_kb())
    await call.answer()

async def admin_add_body_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    ecu_id = int(data["ecu_id"])
    name = message.text.strip()
    if not name:
        await message.answer("Название пустое. Введи ещё раз.")
        return
    conn = db_connect()
    try:
        conn.execute("INSERT INTO bodies(ecu_id, name) VALUES (?,?)", (ecu_id, name))
        conn.commit()
        await message.answer("✅ Кузов добавлен.", reply_markup=admin_reply_kb())
        await state.set_state(AdminFlow.menu)
    except sqlite3.IntegrityError:
        await message.answer("❌ Такой кузов уже есть у этого блока. Введи другое имя.")
    finally:
        conn.close()

# ---- add folder
async def admin_add_folder_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddFolder.pick_body)
    await message.answer("Выбери кузов, к которому добавить папку:", reply_markup=kb_pick_bodies("admin:add_folder_body", "admin:back_menu"))

async def admin_add_folder_pick_body(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    body_id = int(call.data.split("admin:add_folder_body:", 1)[1])
    await state.update_data(body_id=body_id)
    await state.set_state(AdminAddFolder.name)
    await call.message.answer("Введи название папки:", reply_markup=back_reply_kb())
    await call.answer()

async def admin_add_folder_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    body_id = int(data["body_id"])
    name = message.text.strip()
    if not name:
        await message.answer("Название пустое. Введи ещё раз.")
        return
    conn = db_connect()
    try:
        conn.execute("INSERT INTO folders(body_id, name) VALUES (?,?)", (body_id, name))
        conn.commit()
        await message.answer("✅ Папка добавлена.", reply_markup=admin_reply_kb())
        await state.set_state(AdminFlow.menu)
    except sqlite3.IntegrityError:
        await message.answer("❌ Такая папка уже есть у этого кузова. Введи другое имя.")
    finally:
        conn.close()

# ---- add product
async def admin_add_product_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddProduct.pick_folder)
    await message.answer("Выбери папку, куда добавить версию:", reply_markup=kb_pick_folders("admin:add_prod_folder", "admin:back_menu"))

async def admin_add_product_pick_folder(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    folder_id = int(call.data.split("admin:add_prod_folder:", 1)[1])
    await state.update_data(folder_id=folder_id)
    await state.set_state(AdminAddProduct.title)
    await call.message.answer("Введи название версии (title):", reply_markup=back_reply_kb())
    await call.answer()

async def admin_add_product_title(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    title = message.text.strip()
    if not title:
        await message.answer("Название пустое. Введи ещё раз.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminAddProduct.price)
    await message.answer("Введи цену (числом, ₽):", reply_markup=back_reply_kb())

async def admin_add_product_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip())
        if price < 0:
            raise ValueError
    except Exception:
        await message.answer("Цена должна быть числом (например 1000). Введи ещё раз:")
        return
    await state.update_data(price=price)
    await state.set_state(AdminAddProduct.link)
    await message.answer("Введи ссылку MEGA (без ключа):", reply_markup=back_reply_kb())

async def admin_add_product_link(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = message.text.strip()
    if not link:
        await message.answer("Ссылка пустая. Введи ещё раз.")
        return
    await state.update_data(link=link)
    await state.set_state(AdminAddProduct.pkey)
    await message.answer("Введи ключ (или текст 'Ключ выдаётся продавцом'):", reply_markup=back_reply_kb())

async def admin_add_product_key(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    pkey = message.text.strip()
    if not pkey:
        await message.answer("Ключ пустой. Введи ещё раз.")
        return
    data = await state.get_data()
    folder_id = int(data["folder_id"])
    title = data["title"]
    price = int(data["price"])
    link = data["link"]

    conn = db_connect()
    conn.execute(
        "INSERT INTO products(folder_id, title, price, link, pkey) VALUES (?,?,?,?,?)",
        (folder_id, title, price, link, pkey),
    )
    conn.commit()
    conn.close()

    await state.set_state(AdminFlow.menu)
    await message.answer("✅ Версия добавлена.", reply_markup=admin_reply_kb())

# ---- delete flow
async def admin_delete_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminDelete.pick_type)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Марка", callback_data="admin:deltype:brand")],
        [types.InlineKeyboardButton(text="Блок", callback_data="admin:deltype:ecu")],
        [types.InlineKeyboardButton(text="Кузов", callback_data="admin:deltype:body")],
        [types.InlineKeyboardButton(text="Папка", callback_data="admin:deltype:folder")],
        [types.InlineKeyboardButton(text="Версия", callback_data="admin:deltype:product")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back_menu")],
    ])
    await message.answer("Что удалить?", reply_markup=kb)

async def admin_delete_pick_type(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    dtype = call.data.split("admin:deltype:", 1)[1]
    await state.update_data(del_type=dtype)
    await state.set_state(AdminDelete.pick_item)

    if dtype == "brand":
        kb = kb_pick_brands("admin:delitem:brand", "admin:back_menu")
        await call.message.answer("Выбери марку для удаления (удалится всё внутри):", reply_markup=kb)
    elif dtype == "ecu":
        kb = kb_pick_ecus("admin:delitem:ecu", "admin:back_menu")
        await call.message.answer("Выбери блок для удаления (удалится всё внутри):", reply_markup=kb)
    elif dtype == "body":
        kb = kb_pick_bodies("admin:delitem:body", "admin:back_menu")
        await call.message.answer("Выбери кузов для удаления (удалится всё внутри):", reply_markup=kb)
    elif dtype == "folder":
        kb = kb_pick_folders("admin:delitem:folder", "admin:back_menu")
        await call.message.answer("Выбери папку для удаления (удалится всё внутри):", reply_markup=kb)
    elif dtype == "product":
        kb = kb_pick_products("admin:delitem:product", "admin:back_menu")
        await call.message.answer("Выбери версию для удаления:", reply_markup=kb)
    else:
        await call.message.answer("Неизвестный тип.")
    await call.answer()

async def admin_delete_pick_item(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    dtype = data.get("del_type")

    # callback: admin:delitem:<dtype>:<id>
    parts = call.data.split(":")
    # ["admin", "delitem", "<dtype>", "<id>"]
    if len(parts) != 4:
        await call.answer("Неверная кнопка", show_alert=True)
        return
    _, _, ctype, cid = parts
    if ctype != dtype:
        await call.answer("Кнопка устарела", show_alert=True)
        return

    item_id = int(cid)
    conn = db_connect()
    cur = conn.cursor()

    if dtype == "brand":
        cur.execute("DELETE FROM brands WHERE id=?", (item_id,))
    elif dtype == "ecu":
        cur.execute("DELETE FROM ecus WHERE id=?", (item_id,))
    elif dtype == "body":
        cur.execute("DELETE FROM bodies WHERE id=?", (item_id,))
    elif dtype == "folder":
        cur.execute("DELETE FROM folders WHERE id=?", (item_id,))
    elif dtype == "product":
        cur.execute("DELETE FROM products WHERE id=?", (item_id,))
    else:
        conn.close()
        await call.answer("Неизвестный тип", show_alert=True)
        return

    conn.commit()
    conn.close()

    await state.set_state(AdminFlow.menu)
    await call.message.answer("✅ Удалено.", reply_markup=admin_reply_kb())
    await call.answer()

async def admin_back_menu(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminFlow.menu)
    await call.message.answer("🔧 Админка", reply_markup=admin_reply_kb())
    await call.answer()

# ================== UPLOAD (ANALYZE) ==================
def extract_fields_min(file_bytes: bytes) -> dict:
    text = file_bytes[:8_000_000].decode("latin-1", errors="ignore")

    # минимально что ты просил ранее: марка/кузов/ecu/размер/sw/istep/двигатель
    brand = "не определено"
    body = "не определено"
    ecu = "не определено"
    sw = "не определено"
    istep = "не определено"
    engine = "не определено"

    # BMW patterns (оставлено)
    m_body = re.search(r"\bG[0-9]{2}\b", text, flags=re.IGNORECASE)
    if m_body:
        body = m_body.group(0).upper()
        brand = "BMW"

    m_engine = re.search(r"\bB[0-9]{2}[A-Za-z0-9]{3,12}\b", text, flags=re.IGNORECASE)
    if m_engine:
        engine = m_engine.group(0).upper()
        brand = "BMW"

    m_ecu = re.search(r"\b(MG1[A-Za-z]{2}\d{3}|MD1[A-Za-z]{2}\d{3}|EDC17[A-Za-z0-9]+)\b", text, flags=re.IGNORECASE)
    if m_ecu:
        ecu = m_ecu.group(1).upper()

    m_10sw = re.search(r"\b10SW\d{6}\b", text, flags=re.IGNORECASE)
    if m_10sw:
        sw = m_10sw.group(0).upper()

    m_istep = re.search(r"\bR[04]C[0-9A-Za-z]{7,24}\b", text, flags=re.IGNORECASE)
    if m_istep:
        istep = m_istep.group(0).upper()
    else:
        m_epst = re.search(r"EPST:(R[04]C[0-9A-Za-z]{6,24})", text, flags=re.IGNORECASE)
        if m_epst:
            istep = m_epst.group(1).upper()

    return {
        "brand": brand,
        "body": body,
        "ecu": ecu,
        "sw": sw,
        "istep": istep,
        "engine": engine,
        "size_bytes": len(file_bytes),
    }

async def handle_upload(message: types.Message, state: FSMContext, bot: Bot):
    if not message.document:
        await message.answer("Пришли файл как *Документ*.", parse_mode="Markdown")
        return

    doc = message.document
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if doc.file_size and doc.file_size > max_bytes:
        await message.answer(f"Файл слишком большой. Максимум {MAX_UPLOAD_MB} MB.")
        return

    await message.answer("🔍 Анализ…", reply_markup=back_reply_kb())

    file = await bot.get_file(doc.file_id)
    stream = await bot.download_file(file.file_path)
    file_bytes = stream.read()

    r = extract_fields_min(file_bytes)
    out = (
        "✅ *Готово*\n\n"
        f"Марка: *{r['brand']}*\n"
        f"Блок (ECU): *{r['ecu']}*\n"
        f"Кузов: *{r['body']}*\n"
        f"Двигатель: *{r['engine']}*\n"
        f"SW: *{r['sw']}*\n"
        f"ISTEP: *{r['istep']}*\n"
        f"Размер: *{r['size_bytes']} bytes*"
    )
    await message.answer(out, reply_markup=back_reply_kb(), parse_mode="Markdown")

# ================== FALLBACK ==================
async def cb_fallback(call: types.CallbackQuery):
    await call.answer("Кнопка устарела. Нажми /start и зайди снова.", show_alert=True)

# ================== MAIN ==================
async def main():
    init_db()
    seed_if_empty()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # commands
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_id, F.text == "/id")
    dp.message.register(cmd_admin, F.text == "/admin")

    # reply menu
    dp.message.register(menu_shop, F.text == "🛍 Магазин")
    dp.message.register(menu_custom, F.text == "🧩 Заказать софт")
    dp.message.register(menu_contact, F.text == "💬 Связаться")
    dp.message.register(menu_help, F.text == "ℹ️ Помощь")
    dp.message.register(menu_back, F.text == "⬅️ Назад")

    # admin reply buttons
    dp.message.register(admin_add_brand_start, F.text == "➕ Марка")
    dp.message.register(admin_add_ecu_start, F.text == "➕ Блок")
    dp.message.register(admin_add_body_start, F.text == "➕ Кузов")
    dp.message.register(admin_add_folder_start, F.text == "➕ Папка")
    dp.message.register(admin_add_product_start, F.text == "➕ Версия")
    dp.message.register(admin_delete_start, F.text == "❌ Удалить")

    # admin states (messages)
    dp.message.register(admin_add_brand_name, AdminAddBrand.name)
    dp.message.register(admin_add_ecu_name, AdminAddEcu.name)
    dp.message.register(admin_add_body_name, AdminAddBody.name)
    dp.message.register(admin_add_folder_name, AdminAddFolder.name)
    dp.message.register(admin_add_product_title, AdminAddProduct.title)
    dp.message.register(admin_add_product_price, AdminAddProduct.price)
    dp.message.register(admin_add_product_link, AdminAddProduct.link)
    dp.message.register(admin_add_product_key, AdminAddProduct.pkey)

    # upload
    dp.message.register(handle_upload, CustomFlow.waiting_file)

    # nav
    dp.callback_query.register(nav_home, F.data == "nav:home")

    # shop callbacks
    dp.callback_query.register(cb_shop_brands, F.data == "shop:brands")
    dp.callback_query.register(cb_shop_brand, F.data.startswith("shop:brand:"))
    dp.callback_query.register(cb_shop_ecu, F.data.startswith("shop:ecu:"))
    dp.callback_query.register(cb_shop_body, F.data.startswith("shop:body:"))
    dp.callback_query.register(cb_shop_folder, F.data.startswith("shop:folder:"))
    dp.callback_query.register(cb_shop_prod, F.data.startswith("shop:prod:"))

    # pay
    dp.callback_query.register(cb_pay_request, F.data.startswith("pay:req:"))
    dp.callback_query.register(cb_admin_approve, F.data.startswith("admin:approve:"))
    dp.callback_query.register(cb_admin_deny, F.data.startswith("admin:deny:"))

    # admin callbacks (pickers + delete)
    dp.callback_query.register(admin_add_ecu_pick_brand, F.data.startswith("admin:add_ecu_brand:"))
    dp.callback_query.register(admin_add_body_pick_ecu, F.data.startswith("admin:add_body_ecu:"))
    dp.callback_query.register(admin_add_folder_pick_body, F.data.startswith("admin:add_folder_body:"))
    dp.callback_query.register(admin_add_product_pick_folder, F.data.startswith("admin:add_prod_folder:"))

    dp.callback_query.register(admin_delete_pick_type, F.data.startswith("admin:deltype:"))
    dp.callback_query.register(admin_delete_pick_item, F.data.startswith("admin:delitem:"))
    dp.callback_query.register(admin_back_menu, F.data == "admin:back_menu")

    # fallback last
    dp.callback_query.register(cb_fallback)

    me = await bot.get_me()
    logging.info(f"Bot started as @{me.username} (id={me.id})")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")