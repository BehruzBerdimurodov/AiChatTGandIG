"""
SQLite Database - Professional tizim uchun
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/hotel.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS hotel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT DEFAULT "Marco Polo Hotel",
                address TEXT DEFAULT "Dombirobod Naqqoshlik 122A",
                phone TEXT DEFAULT "+998773397171",
                phone_2 TEXT DEFAULT "+998771577171",
                telegram TEXT DEFAULT "@Marcopolohotel_1",
                instagram TEXT DEFAULT "",
                about TEXT DEFAULT "",
                greeting TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                capacity INTEGER DEFAULT 2,
                amenities TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                user_type TEXT DEFAULT 'telegram',
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                phone TEXT,
                language TEXT DEFAULT 'uz',
                blocked INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                room_id TEXT,
                room_name TEXT,
                check_in TEXT,
                check_out TEXT,
                guests INTEGER DEFAULT 1,
                total_price INTEGER,
                status TEXT DEFAULT 'pending',
                name TEXT,
                phone TEXT,
                notes TEXT,
                source TEXT DEFAULT 'telegram',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id TEXT PRIMARY KEY,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                title TEXT,
                username TEXT,
                type TEXT DEFAULT 'subscription',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS post_channel (
                id INTEGER PRIMARY KEY,
                channel_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                direction TEXT,
                message_text TEXT,
                response_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id TEXT PRIMARY KEY,
                reason TEXT,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                activity_type TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                rating INTEGER,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if c.execute("SELECT COUNT(*) FROM hotel").fetchone()[0] == 0:
            c.execute("INSERT INTO hotel DEFAULT VALUES")
        
        if c.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
            default_rooms = [
                ('standart', 'Standart Room', 200000, '1 yotoq, SMART TV, Wi-Fi, Konditsioner, Toza vannaxona', 2, '📺 SMART TV|🌐 Wi-Fi|❄️ Konditsioner|🚿 Toza vannaxona', 1),
                ('deluxe', 'Deluxe Room', 250000, 'Katta xona, 1 katta yotoq, SMART TV, Wi-Fi, Konditsioner', 2, '📺 SMART TV|🌐 Wi-Fi|❄️ Konditsioner|🛏️ Katta yotoq|🚿 Vannaxona', 1),
                ('suite', 'Suite', 300000, 'Keng xona, katta yotoq, SMART TV, Wi-Fi, Konditsioner, Minibar', 2, '📺 SMART TV|🌐 Wi-Fi|❄️ Konditsioner|🛏️ Katta yotoq|🍷 Minibar|🚿 Jakuzzi', 1),
                ('vip', 'VIP Room', 350000, 'Premium xona, katta yotoq, SPA kirish, Lounge bar, Jakuzzi', 2, '📺 SMART TV|🌐 Wi-Fi|❄️ Konditsioner|🛏️ Katta yotoq|💆 SPA|🍷 Lounge bar|🛁 Jakuzzi', 1),
                ('family', 'Family Room', 400000, 'Oilaviy xona, 2 yotoq, SMART TV, Wi-Fi, SPA, Oshxona', 4, '📺 SMART TV|🌐 Wi-Fi|❄️ Konditsioner|🛏️ 2 yotoq|💆 SPA|🍳 Oshxona', 1),
                ('premium', 'Premium Room', 450000, 'Eng yaxshi xona, katta yotoq, SPA, Lounge bar, barcha qulayliklar', 2, '📺 SMART TV|🌐 Wi-Fi|❄️ Konditsioner|🛏️ Katta yotoq|💆 SPA|🍷 Lounge bar|🛁 Jakuzzi|🍷 Minibar', 1),
            ]
            c.executemany("INSERT INTO rooms (id, name, price, description, capacity, amenities, active) VALUES (?, ?, ?, ?, ?, ?, ?)", default_rooms)
        
        conn.commit()


def get_hotel() -> Dict:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hotel LIMIT 1")
        row = c.fetchone()
        if row:
            return dict(row)
        return {}


def update_hotel(field: str, value: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE hotel SET {field} = ?", (value,))
        conn.commit()


def get_rooms(only_active: bool = False) -> List[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        if only_active:
            c.execute("SELECT * FROM rooms WHERE active = 1")
        else:
            c.execute("SELECT * FROM rooms")
        return [dict(row) for row in c.fetchall()]


def get_room(room_id: str) -> Optional[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
        row = c.fetchone()
        return dict(row) if row else None


def add_room(room_id: str, data: Dict):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO rooms (id, name, price, description, capacity, amenities, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (room_id, data.get('name'), data.get('price'), data.get('description'),
              data.get('capacity', 2), data.get('amenities', ''), data.get('active', 1)))
        conn.commit()


def update_room(room_id: str, field: str, value):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE rooms SET {field} = ? WHERE id = ?", (value, room_id))
        conn.commit()


def delete_room(room_id: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        conn.commit()


def register_user(user_id: str, user_type: str = 'telegram', first_name: str = '', 
                  last_name: str = '', username: str = '', phone: str = ''):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO users (user_id, user_type, first_name, last_name, username, phone, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, user_type, first_name, last_name, username, phone))
        conn.commit()


def get_user(user_id: str) -> Optional[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None


def update_user(user_id: str, field: str, value):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()


def get_user_count() -> int:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        return c.fetchone()[0]


def get_all_users() -> List[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users ORDER BY last_activity DESC")
        return [dict(row) for row in c.fetchall()]


def get_user_ids() -> List[str]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [row[0] for row in c.fetchall()]


def create_order(order_data: Dict) -> str:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO orders (id, user_id, room_id, room_name, check_in, check_out, guests, total_price, status, name, phone, notes, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_data['id'], order_data['user_id'], order_data['room_id'],
            order_data['room_name'], order_data['check_in'], order_data['check_out'],
            order_data['guests'], order_data['total_price'], 'pending',
            order_data['name'], order_data['phone'], order_data.get('notes', ''),
            order_data.get('source', 'telegram')
        ))
        conn.commit()
        return order_data['id']


def get_orders(status: str = None) -> List[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        if status:
            c.execute("SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            c.execute("SELECT * FROM orders ORDER BY created_at DESC")
        return [dict(row) for row in c.fetchall()]


def get_order(order_id: str) -> Optional[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = c.fetchone()
        return dict(row) if row else None


def update_order(order_id: str, field: str, value):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE orders SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, order_id))
        conn.commit()


def get_orders_count(status: str = None) -> int:
    with get_db() as conn:
        c = conn.cursor()
        if status:
            c.execute("SELECT COUNT(*) FROM orders WHERE status = ?", (status,))
        else:
            c.execute("SELECT COUNT(*) FROM orders")
        return c.fetchone()[0]


def get_revenue(month: str = None) -> int:
    with get_db() as conn:
        c = conn.cursor()
        if month:
            c.execute("SELECT SUM(total_price) FROM orders WHERE status = 'completed' AND created_at LIKE ?", (f'{month}%',))
        else:
            c.execute("SELECT SUM(total_price) FROM orders WHERE status = 'completed'")
        result = c.fetchone()[0]
        return result if result else 0


def get_admins() -> List[str]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        return [row[0] for row in c.fetchall()]


def add_admin(user_id: str, role: str = 'admin'):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO admins (user_id, role) VALUES (?, ?)", (user_id, role))
        conn.commit()


def remove_admin(user_id: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()


def is_admin(user_id: str, super_admin_id: str = None) -> bool:
    if super_admin_id and str(user_id) == str(super_admin_id):
        return True
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM admins WHERE user_id = ?", (user_id,))
        return c.fetchone()[0] > 0


def get_channels() -> List[Dict]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM channels")
        return [dict(row) for row in c.fetchall()]


def add_channel(channel_data: Dict):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO channels (channel_id, title, username, type)
            VALUES (?, ?, ?, ?)
        """, (channel_data['channel_id'], channel_data['title'], 
              channel_data.get('username', ''), channel_data.get('type', 'subscription')))
        conn.commit()


def remove_channel(channel_id: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        conn.commit()


def get_post_channel() -> Optional[str]:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT channel_id FROM post_channel LIMIT 1")
        row = c.fetchone()
        return row[0] if row else None


def set_post_channel(channel_id: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM post_channel")
        c.execute("INSERT INTO post_channel (channel_id) VALUES (?)", (channel_id,))
        conn.commit()


def log_message(user_id: str, direction: str, message: str, response: str = ''):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO messages (user_id, direction, message_text, response_text)
            VALUES (?, ?, ?, ?)
        """, (user_id, direction, message, response))
        conn.commit()


def log_activity(user_id: str, activity_type: str, details: str = ''):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO user_activities (user_id, activity_type, details)
            VALUES (?, ?, ?)
        """, (user_id, activity_type, details))
        conn.commit()


def get_daily_stats() -> Dict:
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE created_at LIKE ?", (f'{today}%',))
        new_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f'{today}%',))
        new_orders = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM messages WHERE created_at LIKE ?", (f'{today}%',))
        messages = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = c.fetchone()[0]
        
        return {
            'new_users': new_users,
            'new_orders': new_orders,
            'messages': messages,
            'pending_orders': pending_orders
        }


def get_monthly_stats() -> Dict:
    month = datetime.now().strftime('%Y-%m')
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE created_at LIKE ?", (f'{month}%',))
        new_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f'{month}%',))
        total_orders = c.fetchone()[0]
        
        c.execute("SELECT SUM(total_price) FROM orders WHERE status = 'completed' AND created_at LIKE ?", (f'{month}%',))
        revenue = c.fetchone()[0] or 0
        
        return {
            'new_users': new_users,
            'total_orders': total_orders,
            'revenue': revenue
        }
