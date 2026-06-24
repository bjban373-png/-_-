# ── استيراد المكتبات المطلوبة لقاعدة البيانات ──
import sqlite3
import threading
import datetime
import hashlib

# ═══════════════════════════════════════════════════════════════════════════════
# ❷  إعداد قاعدة البيانات مع Transactions و Audit Log و WAL Mode و Indexes
# ═══════════════════════════════════════════════════════════════════════════════
DB_PATH = "supermarket_os2.db"

def init_db():
    """
    تهيئة قاعدة البيانات مع إنشاء جميع الجداول.
    يُفعَّل WAL Mode لتحسين الكتابة المتزامنة من خيوط متعددة.
    تُضاف Indexes على أعمدة name وinvoice_number لتسريع البحث.
    """
    conn = sqlite3.connect(DB_PATH)

    # تفعيل WAL Mode: يسمح بالقراءة المتزامنة أثناء الكتابة
    # مهم جداً في بيئة الخيوط المتعددة لتقليل التأخير
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # أداء أفضل مع WAL

    c = conn.cursor()

    # جدول المستخدمين
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'cashier'
    )""")

    # جدول المنتجات
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    )""")

    # جدول الفواتير
    c.execute("""CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
        total REAL NOT NULL,
        created_at TEXT NOT NULL,
        items TEXT NOT NULL,
        cashier_id INTEGER DEFAULT 0
    )""")

    # ── Audit Log: يسجل كل عملية مع اسم Thread ──
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_name TEXT,
        thread_id INTEGER,
        action TEXT,
        product_id INTEGER,
        old_value INTEGER,
        new_value INTEGER,
        timestamp TEXT,
        sync_mode TEXT,
        cashier_id INTEGER DEFAULT 0
    )""")

    # ── Indexes لتسريع البحث ──
    # Index على name في products: يُسرّع البحث عن منتج بالاسم
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    # Index على invoice_number: يُسرّع البحث عن فاتورة برقمها
    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number)")
    # Index على timestamp في audit_log: يُسرّع الفرز الزمني
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")

    # المستخدم الافتراضي
    pw = hashlib.sha256("12345678".encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ("admin", pw, "admin"))
    except Exception:
        pass

    # المنتجات الافتراضية
    # ── الإضافة فقط إذا كان الجدول فارغاً تماماً ──
    # هذا يمنع تضاعف المنتجات عند تشغيل البرنامج أكثر من مرة
    c.execute("SELECT COUNT(*) FROM products")
    existing_count = c.fetchone()[0]

    if existing_count == 0:
        # أول تشغيل فقط — أدخل المنتجات الافتراضية الـ 15
        products = [
            ("خبز", 1.5, 100), ("حليب", 2.0, 50), ("زبدة", 3.0, 30),
            ("جبن", 4.5, 20), ("تفاح", 2.5, 80), ("موز", 1.8, 60),
            ("برتقال", 2.2, 70), ("دجاج", 8.0, 25), ("أرز", 3.5, 40),
            ("سكر", 2.0, 55), ("زيت", 5.0, 35), ("شاي", 4.0, 45),
            ("قهوة", 6.5, 20), ("ماء", 0.5, 200), ("عصير", 3.0, 60)
        ]
        for p in products:
            c.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", p)
    # إذا كان الجدول فيه بيانات → لا نضيف شيئاً (نحافظ على المخزون الحالي)

    conn.commit()
    conn.close()

    # استدعاء دالة إنشاء جداول المدفوعات الجديدة
    init_payments_tables()


def init_payments_tables():
    """
    إنشاء جداول نظام إدارة الفواتير والمدفوعات.
    يُستدعى من init_db() عند كل تشغيل للبرنامج.
    WAL Mode مُفعَّل دائماً لدعم الكتابة المتزامنة من الخيوط.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    c = conn.cursor()

    # جدول تتبع مدفوعات الفواتير — المورد المشترك الرئيسي في نظام الدفع
    c.execute("""CREATE TABLE IF NOT EXISTS invoice_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT NOT NULL,
        total_amount REAL NOT NULL,
        paid_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'unpaid',
        created_at TEXT,
        last_updated TEXT
    )""")

    # سجل عمليات الدفع والتعديل — يُسجَّل فيه اسم الخيط والوقت وكل تفصيل
    c.execute("""CREATE TABLE IF NOT EXISTS payments_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        thread_name TEXT,
        amount REAL,
        action_type TEXT,
        note TEXT,
        timestamp TEXT,
        sync_mode TEXT
    )""")

    # فهارس لتسريع البحث في جدول المدفوعات
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON invoice_payments(invoice_number)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_plog_invoice ON payments_log(invoice_id)")

    conn.commit()
    conn.close()


def db_audit(thread_name, action, product_id, old_val, new_val, sync_mode, cashier_id=0):
    """تسجيل عملية في Audit Log — يُستدعى داخل الخيوط"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("""INSERT INTO audit_log
            (thread_name, thread_id, action, product_id, old_value, new_value, timestamp, sync_mode, cashier_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (thread_name, threading.current_thread().ident, action,
             product_id, old_val, new_val,
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
             sync_mode, cashier_id))
        conn.commit()
        conn.close()
    except Exception:
        pass  # لا نوقف الخيط بسبب خطأ في السجل
