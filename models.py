# ── استيراد المكتبات المطلوبة لـ models.py ──
import datetime
from tkinter import scrolledtext

# ═══════════════════════════════════════════════════════════════════════════════
# الواجهات الثلاث الجديدة: DiscountTab, DeliveryTab, CashierDashTab
# ═══════════════════════════════════════════════════════════════════════════════
# ── ثوابت الألوان (مطابقة للنظام الأصلي) ──
BG       = "#060d1a"
BG2      = "#0d1526"
BG3      = "#030810"
ACCENT   = "#00e5c3"
FG       = "#c9d1d9"
BLUE     = "#1f6feb"
GREEN    = "#238636"
RED      = "#f85149"
YELLOW   = "#d29922"
PURPLE   = "#a21caf"
GRAY     = "#5a7a9a"

# ── المتغيرات العامة المشتركة مع ملف المشروع ──
# هذه معرّفة في python_supermarket_v3.py — نستخدمها مباشرةً
# DB_PATH       = "supermarket_os2.db"
# stock_lock    = threading.Lock()
# stock_rlock   = threading.RLock()
# shared_inventory = {}



# ══════════════════════════════════════════════════════════════════════════════
# مساعدات مشتركة
# ══════════════════════════════════════════════════════════════════════════════
def _ts() -> str:
    """طابع زمني مختصر للكونسول"""
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _styled_log(widget: scrolledtext.ScrolledText, msg: str, tag: str = "info"):
    """كتابة سطر في كونسول الواجهة مع تلوين حسب النوع"""
    colors = {
        "info":   FG,
        "ok":     ACCENT,       # أخضر/فيروزي — عملية ناجحة
        "warn":   YELLOW,       # تحذير
        "err":    RED,          # خطأ
        "lock":   "#58a6ff",    # أزرق — قفل
        "race":   "#ff7b72",    # أحمر فاتح — Race Condition
        "thread": "#d2a8ff",    # بنفسجي — أحداث الخيوط
        "sync":   "#79c0ff",    # أزرق فاتح — حصول/تحرير قفل Mutex
        "pool":   "#a5d6ff",    # أزرق باهت — Thread Pool
        "safe":   "#56d364",    # أخضر ساطع — عملية آمنة مع Mutex
    }
    color = colors.get(tag, FG)
    widget.config(state="normal")
    widget.tag_config(tag, foreground=color)
    widget.insert("end", msg + "\n", tag)
    widget.see("end")
    widget.config(state="disabled")

