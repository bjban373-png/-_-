# ── استيراد المكتبات المطلوبة لـ ui_windows.py ──
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import time
import sqlite3
import random
import datetime
import os
import hashlib
import queue
import collections
import concurrent.futures
import traceback
import sys

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from database import DB_PATH, db_audit, init_db
from reports import generate_pdf_report, REPORTLAB_AVAILABLE
from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)
from core import (
    RWLock, stock_lock, invoice_lock, stats_lock, stock_rlock,
    MAX_CONCURRENT, stock_semaphore, inventory_rwlock,
    shared_inventory, sync_mode, race_stats, thread_pool,
    THREAD_TIMEOUT_SEC, global_stop_event,
    load_inventory, DeadlockDetector, deadlock_detector,
    PriorityItem, PriorityQueue, NotificationSystem,
    CashierSimulation, AutoRestockSystem,
    AgingPriorityItem, AgingPriorityQueue
)

# ── ميزة جديدة (1): تبويب Deadlock تفاعلي — غرفة استراحة الموظفين ──
from deadlock_room import DeadlockRoomTab

# ── ميزة جديدة (2): محاكاة إدارة الذاكرة (Paging) — مدير تخزين الرفوف ──
from paging_simulation import PagingTab

# ── ميزة جديدة (3): جدولة القرص (Disk Scheduling) — جدولة شاحنات التوصيل ──
from disk_scheduling import DiskSchedulingTab

# ── ميزة جديدة (4): Multiprocessing حقيقي — تقرير المبيعات اليومي ──
from sales_report import SalesReportTab

# ── ميزة جديدة (5): Asyncio / Sockets — نظام طلبات أونلاين ──
from online_orders import OnlineOrdersTab

# ── ميزة جديدة (6): Task Manager شبيه Windows — مراقبة خيوط البرنامج Live ──
from task_manager import TaskManagerTab

# ── ميزة جديدة (7): Starvation & Aging — طابور أولوية خدمة الزبائن ──
from starvation_aging import StarvationAgingTab

# ═══════════════════════════════════════════════════════════════════════════════
# ❿  نافذة تسجيل الدخول
# ═══════════════════════════════════════════════════════════════════════════════
class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("سوبر ماركت OS2 — تسجيل الدخول")
        self.geometry("460x580")
        self.resizable(False, False)
        self.configure(bg="#060d1a")
        self._build_ui()

    def _build_ui(self):
        header = tk.Canvas(self, width=460, height=140, bg="#060d1a", highlightthickness=0)
        header.pack()
        for i in range(140):
            r = int(6 + (i / 140) * 8)
            g = int(13 + (i / 140) * 10)
            b = int(26 + (i / 140) * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            header.create_line(0, i, 460, i, fill=color)

        header.create_text(230, 50, text="🛒 سوبر ماركت", font=("Arial", 28, "bold"), fill="#00e5c3")
        header.create_text(230, 90, text="نظام التشغيل 2 — v2.1 المتقدم", font=("Arial", 11), fill="#4a7a9a")
        header.create_text(230, 118,
            text="Auto-Install • Multi-Cashier • Restock • OS Learning",
            font=("Courier", 8), fill="#1a3a5a")

        frame = tk.Frame(self, bg="#0d1526", bd=0)
        frame.pack(padx=40, fill="x", pady=5)

        self._lbl(frame, "اسم المستخدم").pack(fill="x", padx=20, pady=(20, 3))
        self.user_entry = self._entry(frame)
        self.user_entry.pack(fill="x", padx=20, pady=(0, 10))
        self.user_entry.insert(0, "admin")

        self._lbl(frame, "كلمة المرور").pack(fill="x", padx=20, pady=(5, 3))
        self.pass_entry = self._entry(frame, show="●")
        self.pass_entry.pack(fill="x", padx=20, pady=(0, 20))

        btn = tk.Button(frame, text="تسجيل الدخول ←", font=("Arial", 13, "bold"),
                        bg="#00e5c3", fg="#060d1a", activebackground="#00c4a7",
                        relief="flat", bd=0, pady=12, cursor="hand2", command=self._login)
        btn.pack(fill="x", padx=20, pady=(0, 25))
        self.pass_entry.bind("<Return>", lambda e: self._login())

        info = tk.Frame(self, bg="#060d1a")
        info.pack(fill="x", padx=40, pady=8)
        concepts = [
            ("⚡", "Race Condition"), ("🔒", "Mutex/RLock"), ("🚦", "Semaphore"),
            ("🔄", "Auto-Restock"), ("📅", "CPU Scheduling"), ("🔍", "Deadlock"),
            ("🏪", "Multi-Cashier"), ("💾", "Thread Pool"), ("📚", "تعلّم OS"),
        ]
        for i, (icon, text) in enumerate(concepts):
            tk.Label(info, text=f"{icon} {text}", font=("Courier", 8),
                     fg="#2a5a7a", bg="#060d1a").grid(row=i // 3, column=i % 3,
                                                       sticky="w", padx=4, pady=1)

        tk.Label(self, text="المصمم: إسماعيل اليوسف | نظام التشغيل 2 v2.1",
                 font=("Arial", 8), fg="#1a2a3a", bg="#060d1a").pack(side="bottom", pady=10)

    def _lbl(self, p, t):
        return tk.Label(p, text=t, font=("Arial", 11), fg="#8aa8c8", bg="#0d1526", anchor="e")

    def _entry(self, p, show=None):
        kw = dict(font=("Arial", 12), bg="#1a2a3a", fg="white",
                  insertbackground="white", relief="flat", bd=8, justify="right")
        if show:
            kw["show"] = show
        return tk.Entry(p, **kw)

    def _login(self):
        user = self.user_entry.get().strip()
        pw = hashlib.sha256(self.pass_entry.get().encode()).hexdigest()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, role FROM users WHERE username=? AND password=?", (user, pw))
        row = c.fetchone()
        conn.close()
        if row:
            self.destroy()
            app = MainApp(username=user, role=row[1])
            app.mainloop()
        else:
            messagebox.showerror("خطأ", "اسم المستخدم أو كلمة المرور غير صحيحة\n(admin / 12345678)")


# ═══════════════════════════════════════════════════════════════════════════════
# ⓫  النافذة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════
class MainApp(tk.Tk):
    def __init__(self, username="admin", role="admin"):
        super().__init__()
        self.username = username
        self.role = role
        self.title(f"سوبر ماركت OS2 v2.1 Advanced | {username}")
        self.geometry("1440x900")
        self.configure(bg="#060d1a")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        load_inventory()
        self._deadlock_history = []   # سجل أحداث Deadlock — يُستخدم في تقرير PDF
        deadlock_detector.set_callback(self._on_deadlock)
        deadlock_detector.start()

        # نظام الإشعارات
        self.notif = NotificationSystem(self)

        # نظام إعادة التخزين التلقائي
        self.restock_sys = AutoRestockSystem(
            notify_callback=lambda msg, color: self.notif.show(msg, color),
            log_callback=lambda msg, tag: self.after(0, lambda: self._log_to_sell(msg, tag))
        )

        # محاكاة الصناديق
        self.cashier_sim = None

        self._build_ui()
        self._load_products_table()
        self._schedule_thread_monitor()
        self._schedule_dashboard_update()
        if HAS_PSUTIL:
            self._schedule_perf_monitor()

        # تشغيل إعادة التخزين التلقائي
        self.restock_sys.start()

        # خيط Daemon لمراقبة الفواتير المتأخرة (أكثر من 7 أيام بدون دفع كامل)
        # يعمل كـ Daemon Thread: يتوقف تلقائياً عند إغلاق البرنامج
        t_overdue = threading.Thread(
            target=self._overdue_invoice_monitor,
            daemon=True,
            name="OverdueInvoiceMonitor"
        )
        t_overdue.start()

    def _on_close(self):
        """إغلاق نظيف: إيقاف جميع الخيوط قبل إغلاق النافذة"""
        global_stop_event.set()
        self.restock_sys.stop()
        deadlock_detector.stop()
        if self.cashier_sim:
            self.cashier_sim.stop()
        if hasattr(self, "breakroom_tab") and self.breakroom_tab.sim.running:
            self.breakroom_tab.sim.stop()
        if hasattr(self, "paging_tab"):
            self.paging_tab._on_stop()
        if hasattr(self, "disksched_tab"):
            self.disksched_tab._on_stop()
        if hasattr(self, "onlineorders_tab") and self.onlineorders_tab.server.running:
            self.onlineorders_tab.server.stop()
        if hasattr(self, "taskmgr_tab"):
            self.taskmgr_tab.stop()
        if hasattr(self, "starvation_tab"):
            self.starvation_tab.stop()
        self.destroy()

    # ── بناء الواجهة الرئيسية ──────────────────────────────────────────────────
    def _build_ui(self):
        # ══ الشريط العلوي ══════════════════════════════════════════════════════
        top = tk.Frame(self, bg="#080f20", height=56)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Frame(self, bg="#00e5c3", height=2).pack(fill="x")  # خط فاصل

        tk.Label(top, text="🛒 سوبر ماركت OS2 v2.1 | نظام التشغيل 2",
                 font=("Arial", 14, "bold"), fg="#00e5c3", bg="#080f20").pack(side="right", padx=20, pady=10)

        self.thread_status_var = tk.StringVar(value="الخيوط: 0")
        tk.Label(top, textvariable=self.thread_status_var, font=("Courier", 9),
                 fg="#3a9a6a", bg="#080f20").pack(side="left", padx=10)

        self.deadlock_var = tk.StringVar(value="")
        self.deadlock_lbl = tk.Label(top, textvariable=self.deadlock_var,
                                     font=("Arial", 11, "bold"), fg="#f85149", bg="#080f20")
        self.deadlock_lbl.pack(side="left", padx=15)

        tk.Label(top, text=f"👤 {self.username}", font=("Arial", 10),
                 fg="#5a7a9a", bg="#080f20").pack(side="left", padx=15)

        # ── زر تصدير تقرير PDF شامل ──
        tk.Button(top, text="📄 تصدير PDF", font=("Arial", 9, "bold"),
                  bg="#1a2a3a", fg="#00e5c3", relief="flat", bd=0,
                  padx=12, pady=4, cursor="hand2",
                  command=self._export_pdf_report).pack(side="left", padx=8)

        # ══ الهيكل الأفقي: Sidebar يسار + منطقة محتوى يمين ══════════════════
        body = tk.Frame(self, bg="#060d1a")
        body.pack(fill="both", expand=True)

        # ── Sidebar الثابت (عرض 220px) ──────────────────────────────────────
        sidebar_outer = tk.Frame(body, bg="#0d1526", width=220)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        # شعار صغير داخل السيدبار (ثابت أعلى السيدبار)
        tk.Label(sidebar_outer, text="🛒 OS2", font=("Arial", 12, "bold"),
                 fg="#00e5c3", bg="#0d1526").pack(pady=(14, 2))
        tk.Frame(sidebar_outer, bg="#00e5c3", height=1).pack(fill="x", padx=12, pady=(0, 8))

        # ── منطقة التمرير: Canvas + Scrollbar لقائمة التبويبات ──────────────
        sb_scroll_area = tk.Frame(sidebar_outer, bg="#0d1526")
        sb_scroll_area.pack(fill="both", expand=True)

        sb_canvas = tk.Canvas(sb_scroll_area, bg="#0d1526", highlightthickness=0,
                               width=200)
        sb_scrollbar = tk.Scrollbar(sb_scroll_area, orient="vertical",
                                     command=sb_canvas.yview)
        sb_canvas.configure(yscrollcommand=sb_scrollbar.set)

        sb_scrollbar.pack(side="left", fill="y")
        sb_canvas.pack(side="right", fill="both", expand=True)

        # الإطار الداخلي الذي يحوي كل أزرار التبويبات (هو ما يُمرَّر)
        sb_inner = tk.Frame(sb_canvas, bg="#0d1526")
        _sb_window = sb_canvas.create_window((0, 0), window=sb_inner, anchor="nw")

        def _sb_on_inner_configure(event):
            sb_canvas.configure(scrollregion=sb_canvas.bbox("all"))
        sb_inner.bind("<Configure>", _sb_on_inner_configure)

        def _sb_on_canvas_configure(event):
            sb_canvas.itemconfig(_sb_window, width=event.width)
        sb_canvas.bind("<Configure>", _sb_on_canvas_configure)

        # ── دعم التمرير بعجلة الفأرة فوق السيدبار ──
        def _sb_mousewheel(event):
            if event.num == 4 or getattr(event, "delta", 0) > 0:
                sb_canvas.yview_scroll(-2, "units")
            elif event.num == 5 or getattr(event, "delta", 0) < 0:
                sb_canvas.yview_scroll(2, "units")

        def _sb_bind_wheel(event):
            sb_canvas.bind_all("<MouseWheel>", _sb_mousewheel)
            sb_canvas.bind_all("<Button-4>", _sb_mousewheel)
            sb_canvas.bind_all("<Button-5>", _sb_mousewheel)

        def _sb_unbind_wheel(event):
            sb_canvas.unbind_all("<MouseWheel>")
            sb_canvas.unbind_all("<Button-4>")
            sb_canvas.unbind_all("<Button-5>")

        sb_canvas.bind("<Enter>", _sb_bind_wheel)
        sb_canvas.bind("<Leave>", _sb_unbind_wheel)

        # self._sidebar يشير إلى الإطار الداخلي القابل للتمرير
        # (أزرار التبويبات تُضاف هنا فقط — وتتمرّر مع المحتوى)
        self._sidebar = sb_inner

        # ── منطقة المحتوى (يمين السيدبار) ──────────────────────────────────
        content_area = tk.Frame(body, bg="#060d1a")
        content_area.pack(side="left", fill="both", expand=True)

        # ══ تعريف التبويبات الـ 17 ══════════════════════════════════════════
        # كل عنصر: (attr, أيقونة, اسم_عربي, مجموعة, thread_indicator)
        # thread_indicator=True → تظهر نقطة خضراء إذا يوجد خيط نشط مرتبط
        self._tab_defs = [
            # ── إدارة المبيعات ──
            ("dash_frame",       "📊", "لوحة التحكم",       "مبيعات",  False),
            ("sell_frame",       "🛍",  "البيع",              "مبيعات",  False),
            ("products_frame",   "📦", "المنتجات",           "مبيعات",  False),
            ("inv_frame",        "🧾", "الفواتير",           "مبيعات",  False),
            ("manual_inv_frame", "📝", "فاتورة يدوية",       "مبيعات",  False),
            ("payments_frame",   "💳", "المدفوعات",          "مبيعات",  False),
            ("cashier_frame",    "🏪", "الصناديق",           "مبيعات",  False),
            ("discount_frame",   "🏷",  "الخصومات",           "مبيعات",  False),
            ("delivery_frame",   "🚚", "التوصيل",            "مبيعات",  False),
            # ── مفاهيم OS ──
            ("thread_vis_frame", "🎨", "مرئية الخيوط",       "نظام التشغيل", True),
            ("race_frame",       "⚡", "Race Condition",      "نظام التشغيل", True),
            ("pc_frame",         "🔄", "Producer-Consumer",   "نظام التشغيل", True),
            ("sched_frame",      "📅", "CPU Scheduling",      "نظام التشغيل", False),
            ("perf_frame",       "📈", "الأداء",              "نظام التشغيل", True),
            ("cashdash_frame",   "🏦", "Multi-Cashier",       "نظام التشغيل", True),
            ("breakroom_frame",  "🍵", "غرفة الاستراحة (Deadlock)", "نظام التشغيل", True),
            ("paging_frame",     "🗄",  "مدير تخزين الرفوف (Paging)", "نظام التشغيل", False),
            ("disksched_frame",  "🚚", "جدولة شاحنات التوصيل", "نظام التشغيل", False),
            ("salesreport_frame", "📑", "تقرير المبيعات اليومي (Multiprocessing)", "نظام التشغيل", False),
            ("onlineorders_frame", "🌐", "نظام طلبات أونلاين (Asyncio)", "نظام التشغيل", False),
            ("taskmgr_frame",    "🖥",  "مدير المهام (Task Manager)", "نظام التشغيل", False),
            ("starvation_frame", "⏳", "Starvation & Aging", "نظام التشغيل", False),
            # ── سجلات وتعلّم ──
            ("audit_frame",      "📋", "Audit Log",           "أخرى",    False),
            ("learn_frame",      "📚", "تعلّم OS",            "أخرى",    False),
        ]

        # ── بناء أزرار السيدبار مجمّعة حسب الفئة ───────────────────────────
        self._sidebar_btns   = {}   # {attr: زر الـ Frame}
        self._sidebar_dots   = {}   # {attr: Label نقطة النشاط}
        self._active_tab_attr = None

        current_group = None
        for attr, icon, name, group, has_dot in self._tab_defs:
            # عنوان المجموعة عند التغيير
            if group != current_group:
                current_group = group
                tk.Label(self._sidebar, text=group.upper(),
                         font=("Arial", 7, "bold"), fg="#3a5a7a", bg="#0d1526",
                         anchor="w").pack(fill="x", padx=16, pady=(10, 2))

            # إطار كل زر في السيدبار
            btn_frame = tk.Frame(self._sidebar, bg="#0d1526", cursor="hand2")
            btn_frame.pack(fill="x", padx=8, pady=1)

            # الأيقونة + الاسم
            lbl_icon = tk.Label(btn_frame, text=icon, font=("Arial", 11),
                                fg="#8aa8c8", bg="#0d1526", width=3)
            lbl_icon.pack(side="right", padx=(4, 2), pady=6)

            lbl_name = tk.Label(btn_frame, text=name, font=("Arial", 10),
                                fg="#8aa8c8", bg="#0d1526", anchor="e", justify="right")
            lbl_name.pack(side="right", fill="x", expand=True, pady=6)

            # نقطة المؤشر (خضراء = خيط نشط، رمادية = لا خيط)
            dot = tk.Label(btn_frame, text="●", font=("Arial", 8),
                           fg="#1a2a3a", bg="#0d1526")   # مخفية ابتداءً
            dot.pack(side="left", padx=(4, 2))
            self._sidebar_dots[attr] = dot

            # ربط النقر
            _attr = attr  # capture للـ lambda
            for w in (btn_frame, lbl_icon, lbl_name, dot):
                w.bind("<Button-1>", lambda e, a=_attr: self._show_tab(a))
                w.bind("<Enter>",    lambda e, f=btn_frame: f.config(bg="#132035") or
                                    [c.config(bg="#132035") for c in f.winfo_children()])
                w.bind("<Leave>",    lambda e, f=btn_frame, a=_attr: (
                                    f.config(bg="#0d1526" if a != self._active_tab_attr else "#0a1a2e"),
                                    [c.config(bg="#0d1526" if a != self._active_tab_attr else "#0a1a2e")
                                     for c in f.winfo_children()]))

            self._sidebar_btns[attr] = (btn_frame, lbl_icon, lbl_name)

        # فاصل وزر الإغلاق أسفل السيدبار (ثابت — خارج منطقة التمرير)
        tk.Button(sidebar_outer, text="🚪 خروج", font=("Arial", 9, "bold"),
                  bg="#1a0a0a", fg="#f85149", relief="flat", bd=0, pady=6,
                  cursor="hand2", command=self._on_close).pack(fill="x", padx=12, pady=(0, 10), side="bottom")
        tk.Frame(sidebar_outer, bg="#1a2a3a", height=1).pack(fill="x", padx=12, pady=(4, 4), side="bottom")

        # ══ إنشاء Frames التبويبات ══════════════════════════════════════════
        # كل Frame يُبنى داخل content_area ويُخفى حتى يُختار تبويبه
        self._tab_frames = {}
        for attr, _icon, _name, _group, _dot in self._tab_defs:
            fr = tk.Frame(content_area, bg="#060d1a")
            fr.place(x=0, y=0, relwidth=1, relheight=1)
            fr.lower()                       # مخفي ابتداءً
            setattr(self, attr, fr)
            self._tab_frames[attr] = fr

        # بناء محتوى كل تبويب
        self._build_dashboard_tab()
        self._build_sell_tab()
        self._build_products_tab()
        self._build_invoices_tab()
        self._build_manual_invoice_tab()
        self._build_cashier_tab()
        self._build_thread_vis_tab()
        self._build_race_tab()
        self._build_producer_consumer_tab()
        self._build_scheduling_tab()
        self._build_performance_tab()
        self._build_audit_tab()
        self._build_learn_tab()
        DiscountTab(self.discount_frame).pack(fill="both", expand=True)
        DeliveryTab(self.delivery_frame).pack(fill="both", expand=True)
        CashierDashTab(self.cashdash_frame).pack(fill="both", expand=True)
        PaymentManagerTab(self.payments_frame).pack(fill="both", expand=True)

        # ── ميزة جديدة (1): تبويب Deadlock تفاعلي — غرفة استراحة الموظفين ──
        self.breakroom_tab = DeadlockRoomTab(self.breakroom_frame)
        self.breakroom_tab.pack(fill="both", expand=True)

        # ── ميزة جديدة (2): محاكاة إدارة الذاكرة (Paging) — مدير تخزين الرفوف ──
        self.paging_tab = PagingTab(self.paging_frame)
        self.paging_tab.pack(fill="both", expand=True)

        # ── ميزة جديدة (3): جدولة القرص (Disk Scheduling) — جدولة شاحنات التوصيل ──
        self.disksched_tab = DiskSchedulingTab(self.disksched_frame)
        self.disksched_tab.pack(fill="both", expand=True)

        # ── ميزة جديدة (4): Multiprocessing حقيقي — تقرير المبيعات اليومي ──
        self.salesreport_tab = SalesReportTab(self.salesreport_frame)
        self.salesreport_tab.pack(fill="both", expand=True)

        # ── ميزة جديدة (5): Asyncio / Sockets — نظام طلبات أونلاين ──
        self.onlineorders_tab = OnlineOrdersTab(self.onlineorders_frame)
        self.onlineorders_tab.pack(fill="both", expand=True)

        # ── ميزة جديدة (6): Task Manager شبيه Windows — مراقبة خيوط البرنامج Live ──
        self.taskmgr_tab = TaskManagerTab(self.taskmgr_frame)
        self.taskmgr_tab.pack(fill="both", expand=True)

        # ── ميزة جديدة (7): Starvation & Aging — طابور أولوية خدمة الزبائن ──
        self.starvation_tab = StarvationAgingTab(self.starvation_frame)
        self.starvation_tab.pack(fill="both", expand=True)

        # عرض أول تبويب (لوحة التحكم) افتراضياً
        self._show_tab("dash_frame")

        # تحديث مؤشرات النشاط كل ثانيتين
        self._schedule_sidebar_dots()

    def _show_tab(self, attr: str):
        """إظهار التبويب المطلوب وإخفاء الباقي — بدون إعادة بناء الواجهة"""
        # إعادة لون الزر القديم للحالة العادية
        if self._active_tab_attr and self._active_tab_attr in self._sidebar_btns:
            old_f, old_i, old_n = self._sidebar_btns[self._active_tab_attr]
            old_f.config(bg="#0d1526")
            old_i.config(fg="#8aa8c8", bg="#0d1526")
            old_n.config(fg="#8aa8c8", bg="#0d1526", font=("Arial", 10))
            if self._active_tab_attr in self._sidebar_dots:
                self._sidebar_dots[self._active_tab_attr].config(bg="#0d1526")

        # إخفاء جميع الـ Frames
        for a, fr in self._tab_frames.items():
            fr.lower()

        # إظهار الـ Frame المطلوب
        if attr in self._tab_frames:
            self._tab_frames[attr].lift()

        # تمييز الزر النشط في السيدبار
        self._active_tab_attr = attr
        if attr in self._sidebar_btns:
            btn_f, lbl_i, lbl_n = self._sidebar_btns[attr]
            btn_f.config(bg="#0a1a2e")
            lbl_i.config(fg="#00e5c3", bg="#0a1a2e")
            lbl_n.config(fg="#00e5c3", bg="#0a1a2e", font=("Arial", 10, "bold"))
            if attr in self._sidebar_dots:
                self._sidebar_dots[attr].config(bg="#0a1a2e")

            # خط تمييز أيسر (تأثير بصري بسيط)
            btn_f.config(highlightbackground="#00e5c3", highlightthickness=0,
                         relief="flat", bd=0)

    def _schedule_sidebar_dots(self):
        """تحديث نقاط النشاط في السيدبار كل ثانيتين"""
        self._update_sidebar_dots()
        self.after(2000, self._schedule_sidebar_dots)

    def _update_sidebar_dots(self):
        """
        تحديث نقاط المؤشر لكل تبويب:
        - نقطة خضراء: يوجد خيط نشط مرتبط بهذا التبويب
        - نقطة رمادية/مخفية: لا يوجد نشاط

        يتحقق من أسماء الخيوط النشطة ليقرر أي التبويبات "حية"
        """
        # الكلمات المفتاحية لكل تبويب للبحث عنها في أسماء الخيوط
        thread_keywords = {
            "thread_vis_frame": ["Cashier", "RestockScanner", "RestockProcessor",
                                 "PoolWorker", "RaceThread"],
            "race_frame":       ["RaceThread", "StressTest"],
            "pc_frame":         ["RestockScanner", "RestockProcessor", "PCProducer", "PCConsumer"],
            "perf_frame":       ["PerfMonitor", "OverdueInvoice"],
            "cashdash_frame":   ["Cashier-"],
            "breakroom_frame":  ["BreakRoom-"],
        }

        active_names = {t.name for t in threading.enumerate() if t.is_alive()}

        for attr, _icon, _name, _group, has_dot in self._tab_defs:
            dot = self._sidebar_dots.get(attr)
            if not dot or not has_dot:
                continue

            keywords = thread_keywords.get(attr, [])
            is_active = any(
                any(kw in name for kw in keywords)
                for name in active_names
            )

            bg = "#0a1a2e" if attr == self._active_tab_attr else "#0d1526"
            if is_active:
                dot.config(fg="#3fb950", bg=bg)   # نقطة خضراء — خيط نشط
            else:
                dot.config(fg="#1a2a3a", bg=bg)   # مخفية عملياً

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب لوحة التحكم (Dashboard)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_dashboard_tab(self):
        f = self.dash_frame

        # ── الرأس ──
        tk.Label(f, text="📊 لوحة التحكم الحية",
                 font=("Arial", 15, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(10, 5))

        # ── 4 بطاقات إحصائية ──
        cards_f = tk.Frame(f, bg="#060d1a")
        cards_f.pack(fill="x", padx=15, pady=5)

        self.dash_vars = {}
        cards = [
            ("invoices_today", "🧾 فواتير اليوم", "#1f6feb", "0"),
            ("total_sales", "💰 إجمالي المبيعات", "#238636", "0.0 ل.س"),
            ("products_count", "📦 المنتجات", "#9a7000", "0"),
            ("active_threads", "⚡ الخيوط النشطة", "#a21caf", "0"),
        ]
        for i, (key, title, color, default) in enumerate(cards):
            card = tk.Frame(cards_f, bg=color, bd=0)
            card.grid(row=0, column=i, padx=8, pady=5, sticky="ew", ipady=8)
            tk.Label(card, text=title, font=("Arial", 10, "bold"),
                     fg="white", bg=color).pack(padx=10, pady=(8, 2))
            var = tk.StringVar(value=default)
            self.dash_vars[key] = var
            tk.Label(card, textvariable=var, font=("Arial", 22, "bold"),
                     fg="white", bg=color).pack(padx=10, pady=(0, 8))
        for i in range(4):
            cards_f.columnconfigure(i, weight=1)

        # ── رسم بياني حي: المبيعات عبر الزمن ──
        chart_f = tk.Frame(f, bg="#0d1526")
        chart_f.pack(fill="both", expand=True, padx=15, pady=5)
        tk.Label(chart_f, text="📈 تطور المبيعات والخيوط (يتحدث كل ثانية)",
                 font=("Arial", 10, "bold"), fg="#8aa8c8", bg="#0d1526").pack(pady=(5, 0))

        self.dash_fig, (self.dash_ax1, self.dash_ax2) = plt.subplots(
            1, 2, figsize=(13, 3.5), facecolor="#060d1a")
        for ax in (self.dash_ax1, self.dash_ax2):
            ax.set_facecolor("#0d1526")
            ax.tick_params(colors="#c9d1d9", labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
        self.dash_ax1.set_title("مجموع المبيعات عبر الزمن", color="#c9d1d9", fontsize=9)
        self.dash_ax2.set_title("عدد الخيوط النشطة", color="#c9d1d9", fontsize=9)

        self.dash_canvas = FigureCanvasTkAgg(self.dash_fig, master=chart_f)
        self.dash_canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        # بيانات الرسم البياني
        self._dash_sales_history = []
        self._dash_threads_history = []

        # ── إشعارات المخزون المنخفض ──
        notif_f = tk.Frame(f, bg="#0d1526")
        notif_f.pack(fill="x", padx=15, pady=(0, 5))
        tk.Label(notif_f, text="⚠ تنبيهات المخزون المنخفض:", font=("Arial", 9, "bold"),
                 fg="#d29922", bg="#0d1526").pack(side="right", padx=8)
        self.low_stock_var = tk.StringVar(value="لا يوجد")
        tk.Label(notif_f, textvariable=self.low_stock_var, font=("Arial", 9),
                 fg="#f85149", bg="#0d1526", justify="right").pack(side="right", padx=8)

    def _schedule_dashboard_update(self):
        """تحديث لوحة التحكم كل ثانية"""
        self._update_dashboard()
        self.after(1000, self._schedule_dashboard_update)

    def _update_dashboard(self):
        """تحديث جميع إحصائيات لوحة التحكم"""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            # فواتير اليوم
            today = datetime.date.today().strftime("%Y-%m-%d")
            c.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM invoices WHERE created_at LIKE ?",
                      (f"{today}%",))
            row = c.fetchone()
            inv_today = row[0] or 0
            total_sales = row[1] or 0.0

            # عدد المنتجات
            c.execute("SELECT COUNT(*) FROM products")
            prod_count = c.fetchone()[0]

            # منتجات منخفضة المخزون
            c.execute("SELECT name, stock FROM products WHERE stock < 10 ORDER BY stock")
            low = c.fetchall()
            conn.close()

            self.dash_vars["invoices_today"].set(str(inv_today))
            self.dash_vars["total_sales"].set(f"{total_sales:.1f} ل.س")
            self.dash_vars["products_count"].set(str(prod_count))
            self.dash_vars["active_threads"].set(str(threading.active_count()))

            if low:
                low_str = " | ".join(f"{n}({s})" for n, s in low[:5])
                self.low_stock_var.set(low_str)
                # إشعار تلقائي لكل منتج بمخزون ≤ 3
                for name, stock in low:
                    if stock <= 3:
                        self.notif.show(f"⚠ مخزون منخفض جداً: {name} ({stock} وحدة)", "#d29922")
            else:
                self.low_stock_var.set("جميع المنتجات متوفرة ✓")

            # تحديث الرسم البياني
            self._dash_sales_history.append(total_sales)
            self._dash_threads_history.append(threading.active_count())
            if len(self._dash_sales_history) > 60:
                self._dash_sales_history = self._dash_sales_history[-60:]
                self._dash_threads_history = self._dash_threads_history[-60:]

            self.dash_ax1.clear()
            self.dash_ax1.set_facecolor("#0d1526")
            self.dash_ax1.set_title("إجمالي المبيعات (ل.س)", color="#c9d1d9", fontsize=9)
            self.dash_ax1.tick_params(colors="#c9d1d9", labelsize=7)
            for sp in self.dash_ax1.spines.values():
                sp.set_color("#1a2a3a")
            if self._dash_sales_history:
                xs = range(len(self._dash_sales_history))
                self.dash_ax1.fill_between(xs, self._dash_sales_history,
                                           color="#1f6feb", alpha=0.4)
                self.dash_ax1.plot(xs, self._dash_sales_history, color="#1f6feb", linewidth=1.5)

            self.dash_ax2.clear()
            self.dash_ax2.set_facecolor("#0d1526")
            self.dash_ax2.set_title("الخيوط النشطة", color="#c9d1d9", fontsize=9)
            self.dash_ax2.tick_params(colors="#c9d1d9", labelsize=7)
            for sp in self.dash_ax2.spines.values():
                sp.set_color("#1a2a3a")
            if self._dash_threads_history:
                xs = range(len(self._dash_threads_history))
                self.dash_ax2.fill_between(xs, self._dash_threads_history,
                                           color="#3fb950", alpha=0.4)
                self.dash_ax2.plot(xs, self._dash_threads_history, color="#3fb950", linewidth=1.5)

            self.dash_canvas.draw()

        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب البيع
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sell_tab(self):
        f = self.sell_frame
        self._log_sell_box = None

        left = tk.Frame(f, bg="#0d1526", width=470)
        left.pack(side="left", fill="both", padx=(0, 4), pady=0)
        left.pack_propagate(False)

        self._section_title(left, "قائمة المنتجات")
        sf = tk.Frame(left, bg="#0d1526")
        sf.pack(fill="x", padx=12, pady=4)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_products)
        tk.Label(sf, text="🔍", fg="#5a7a9a", bg="#0d1526", font=("Arial", 12)).pack(side="right")
        tk.Entry(sf, textvariable=self.search_var, bg="#1a2a3a", fg="white",
                 insertbackground="white", relief="flat", bd=6, justify="right",
                 font=("Arial", 11)).pack(side="right", fill="x", expand=True, padx=(0, 4))

        cols = ("id", "name", "price", "stock")
        self.prod_tree = self._make_treeview(left, cols,
            {"id": ("ID", 40), "name": ("المنتج", 120), "price": ("السعر", 90), "stock": ("المخزون", 80)},
            height=15)
        self.prod_tree.pack(fill="both", expand=True, padx=12, pady=4)

        right = tk.Frame(f, bg="#0d1526")
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        self._section_title(right, "سلة المشتريات")
        cart_cols = ("name", "qty", "price", "total")
        self.cart_tree = self._make_treeview(right, cart_cols,
            {"name": ("المنتج", 130), "qty": ("الكمية", 60), "price": ("السعر", 80), "total": ("الإجمالي", 80)},
            height=8)
        self.cart_tree.pack(fill="x", padx=12, pady=4)

        cf = tk.Frame(right, bg="#0d1526")
        cf.pack(fill="x", padx=12, pady=4)
        for i, (lbl, attr) in enumerate([("اسم المشتري:", "cust_name"), ("رقم الهاتف:", "cust_phone")]):
            tk.Label(cf, text=lbl, fg="#8aa8c8", bg="#0d1526", font=("Arial", 10)).grid(
                row=i, column=1, sticky="e", padx=4, pady=3)
            entry = tk.Entry(cf, bg="#1a2a3a", fg="white", insertbackground="white",
                             relief="flat", bd=6, font=("Arial", 11), justify="right")
            entry.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            setattr(self, attr, entry)
        cf.columnconfigure(0, weight=1)

        bf = tk.Frame(right, bg="#0d1526")
        bf.pack(fill="x", padx=12, pady=4)
        self._btn(bf, "➕ أضف للسلة", "#238636", self._add_to_cart).pack(side="right", fill="x", expand=True, padx=2)
        self._btn(bf, "➖ إزالة", "#b91c1c", self._remove_from_cart).pack(side="right", fill="x", expand=True, padx=2)

        self._btn(right, "🧾 إصدار فاتورة (Thread Pool)", "#1f6feb",
                  self._issue_invoice, size=12).pack(fill="x", padx=12, pady=2)

        sync_f = tk.Frame(right, bg="#0d1526")
        sync_f.pack(fill="x", padx=12, pady=6)
        tk.Label(sync_f, text="وضع التزامن:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10, "bold")).pack(side="right")
        self.sync_mode_var = tk.IntVar(value=1)
        modes = [
            ("بدون ⚠", 0, "#f85149"),
            ("Mutex 🔒", 1, "#3fb950"),
            ("Semaphore 🚦", 2, "#d29922"),
            ("RWLock 📖", 3, "#00e5c3"),
        ]
        for lbl, val, col in modes:
            tk.Radiobutton(sync_f, text=lbl, variable=self.sync_mode_var, value=val,
                           bg="#0d1526", fg=col, selectcolor="#1a2a3a", activebackground="#0d1526",
                           font=("Arial", 9, "bold"), command=self._on_sync_change).pack(side="right", padx=5)

        sem_f = tk.Frame(right, bg="#0d1526")
        sem_f.pack(fill="x", padx=12, pady=2)
        tk.Label(sem_f, text="حد Semaphore:", fg="#8aa8c8", bg="#0d1526", font=("Arial", 10)).pack(side="right")
        self.sem_limit_var = tk.IntVar(value=3)
        tk.Spinbox(sem_f, from_=1, to=10, textvariable=self.sem_limit_var,
                   bg="#1a2a3a", fg="white", insertbackground="white",
                   relief="flat", bd=4, font=("Arial", 11), width=4,
                   command=self._update_semaphore).pack(side="right", padx=6)

        pool_f = tk.Frame(right, bg="#0d1526")
        pool_f.pack(fill="x", padx=12, pady=2)
        tk.Label(pool_f, text="حجم Thread Pool:", fg="#8aa8c8", bg="#0d1526", font=("Arial", 10)).pack(side="right")
        self.pool_size_var = tk.IntVar(value=4)
        tk.Spinbox(pool_f, from_=1, to=16, textvariable=self.pool_size_var,
                   bg="#1a2a3a", fg="white", insertbackground="white",
                   relief="flat", bd=4, font=("Arial", 11), width=4).pack(side="right", padx=6)

        self._btn(right, "🔄 إعادة ضبط المخزون", "#d29922", self._reset_stock, size=10).pack(fill="x", padx=12, pady=3)

        tk.Label(right, text="📋 سجل الأحداث:", fg="#5a7a9a", bg="#0d1526", font=("Arial", 9)).pack(anchor="e", padx=12)
        self.log_box = scrolledtext.ScrolledText(right, height=8, bg="#030810", fg="#3fb950",
                                                  font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self._log_sell_box = self.log_box
        for tag, col in [("info", "#3fb950"), ("warn", "#d29922"), ("err", "#f85149"),
                          ("sync", "#00e5c3"), ("race", "#ff6b6b"), ("sem", "#ffa500"),
                          ("rw", "#a78bfa"), ("pool", "#60a5fa"), ("safe", "#3fb950"),
                          ("ok", "#56d364")]:
            self.log_box.tag_config(tag, foreground=col)

        self.cart = {}

    def _log_to_sell(self, msg, tag="info"):
        """تسجيل رسالة في سجل تبويب البيع — يُستخدم من الخيوط الخلفية"""
        if hasattr(self, "log_box"):
            self._log(msg, tag)

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب كتابة فاتورة يدوياً (Manual Invoice)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_manual_invoice_tab(self):
        f = self.manual_inv_frame
        self._manual_items = []  # قائمة المنتجات المضافة يدوياً

        # ── عنوان ──
        tk.Label(f, text="📝 كتابة فاتورة يدوية",
                 font=("Arial", 15, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(12, 3))
        tk.Label(f, text="أدخل اسم المشتري ورقمه ثم أضف المنتجات يدوياً وأصدر الفاتورة",
                 font=("Arial", 9), fg="#5a7a9a", bg="#060d1a").pack(pady=(0, 8))

        body = tk.Frame(f, bg="#060d1a")
        body.pack(fill="both", expand=True, padx=15, pady=5)

        # ── العمود الأيسر: بيانات المشتري + إدخال المنتج ──
        left = tk.Frame(body, bg="#0d1526", width=440)
        left.pack(side="left", fill="both", padx=(0, 8))
        left.pack_propagate(False)

        # بيانات المشتري
        self._section_title(left, "👤 بيانات المشتري")
        cust_f = tk.Frame(left, bg="#0d1526")
        cust_f.pack(fill="x", padx=12, pady=4)

        tk.Label(cust_f, text="اسم المشتري:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10)).grid(row=0, column=1, sticky="e", padx=6, pady=4)
        self.manual_cust_name = tk.Entry(cust_f, bg="#1a2a3a", fg="white",
                                         insertbackground="white", relief="flat", bd=6,
                                         font=("Arial", 11), justify="right")
        self.manual_cust_name.grid(row=0, column=0, sticky="ew", padx=6, pady=4)

        tk.Label(cust_f, text="رقم الهاتف:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10)).grid(row=1, column=1, sticky="e", padx=6, pady=4)
        self.manual_cust_phone = tk.Entry(cust_f, bg="#1a2a3a", fg="white",
                                          insertbackground="white", relief="flat", bd=6,
                                          font=("Arial", 11), justify="right")
        self.manual_cust_phone.grid(row=1, column=0, sticky="ew", padx=6, pady=4)
        cust_f.columnconfigure(0, weight=1)

        tk.Frame(left, bg="#1a2a3a", height=1).pack(fill="x", padx=12, pady=8)

        # إدخال منتج
        self._section_title(left, "📦 إضافة منتج")
        prod_f = tk.Frame(left, bg="#0d1526")
        prod_f.pack(fill="x", padx=12, pady=4)

        tk.Label(prod_f, text="اسم المنتج:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10)).grid(row=0, column=1, sticky="e", padx=6, pady=4)
        self.manual_prod_name = tk.Entry(prod_f, bg="#1a2a3a", fg="white",
                                         insertbackground="white", relief="flat", bd=6,
                                         font=("Arial", 11), justify="right")
        self.manual_prod_name.grid(row=0, column=0, sticky="ew", padx=6, pady=4)

        tk.Label(prod_f, text="السعر (ل.س):", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10)).grid(row=1, column=1, sticky="e", padx=6, pady=4)
        self.manual_prod_price = tk.Entry(prod_f, bg="#1a2a3a", fg="white",
                                          insertbackground="white", relief="flat", bd=6,
                                          font=("Arial", 11), justify="right")
        self.manual_prod_price.grid(row=1, column=0, sticky="ew", padx=6, pady=4)

        tk.Label(prod_f, text="الكمية:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10)).grid(row=2, column=1, sticky="e", padx=6, pady=4)
        self.manual_prod_qty = tk.Entry(prod_f, bg="#1a2a3a", fg="white",
                                        insertbackground="white", relief="flat", bd=6,
                                        font=("Arial", 11), justify="right")
        self.manual_prod_qty.insert(0, "1")
        self.manual_prod_qty.grid(row=2, column=0, sticky="ew", padx=6, pady=4)
        prod_f.columnconfigure(0, weight=1)

        # ربط Enter بإضافة المنتج
        self.manual_prod_qty.bind("<Return>", lambda e: self._manual_add_item())

        btn_add = tk.Button(left, text="➕ أضف المنتج للفاتورة",
                            font=("Arial", 11, "bold"), bg="#238636", fg="white",
                            relief="flat", bd=0, pady=9, cursor="hand2",
                            command=self._manual_add_item)
        btn_add.pack(fill="x", padx=12, pady=(6, 4))

        btn_clear_item = tk.Button(left, text="🗑 حذف المنتج المحدد",
                                   font=("Arial", 10, "bold"), bg="#b91c1c", fg="white",
                                   relief="flat", bd=0, pady=7, cursor="hand2",
                                   command=self._manual_delete_item)
        btn_clear_item.pack(fill="x", padx=12, pady=2)

        btn_reset = tk.Button(left, text="🔄 مسح كل شيء",
                              font=("Arial", 10, "bold"), bg="#d29922", fg="white",
                              relief="flat", bd=0, pady=7, cursor="hand2",
                              command=self._manual_reset)
        btn_reset.pack(fill="x", padx=12, pady=2)

        # ── العمود الأيمن: جدول المنتجات + معاينة + زر الإصدار ──
        right = tk.Frame(body, bg="#0d1526")
        right.pack(side="right", fill="both", expand=True)

        self._section_title(right, "🧾 قائمة المنتجات في الفاتورة")

        # جدول المنتجات
        item_cols = ("num", "name", "price", "qty", "total")
        self.manual_items_tree = self._make_treeview(right, item_cols, {
            "num":   ("#",       40),
            "name":  ("المنتج", 160),
            "price": ("السعر",   90),
            "qty":   ("الكمية",  70),
            "total": ("الإجمالي",100),
        }, height=10)
        self.manual_items_tree.pack(fill="both", expand=True, padx=12, pady=4)

        # مجموع الفاتورة
        total_f = tk.Frame(right, bg="#0d1526")
        total_f.pack(fill="x", padx=12, pady=6)
        tk.Label(total_f, text="المجموع الكلي:", fg="#c9d1d9", bg="#0d1526",
                 font=("Arial", 13, "bold")).pack(side="right", padx=8)
        self.manual_total_var = tk.StringVar(value="0.00 ل.س")
        tk.Label(total_f, textvariable=self.manual_total_var,
                 fg="#00e5c3", bg="#0d1526", font=("Arial", 18, "bold")).pack(side="right")

        # مكان حفظ الفواتير
        save_f = tk.Frame(right, bg="#0d1526")
        save_f.pack(fill="x", padx=12, pady=4)
        tk.Label(save_f, text="📁 مجلد الحفظ:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10)).pack(side="right", padx=5)
        self.manual_save_path = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "فواتير"))
        path_entry = tk.Entry(save_f, textvariable=self.manual_save_path,
                              bg="#1a2a3a", fg="#c9d1d9", insertbackground="white",
                              relief="flat", bd=6, font=("Arial", 9), justify="right")
        path_entry.pack(side="right", fill="x", expand=True, padx=4)
        tk.Button(save_f, text="📂 تصفح", font=("Arial", 9, "bold"),
                  bg="#1f6feb", fg="white", relief="flat", bd=0, padx=8, pady=4,
                  cursor="hand2",
                  command=self._manual_browse_folder).pack(side="left")

        # زر إصدار الفاتورة
        tk.Button(right, text="🧾 إصدار الفاتورة وحفظها",
                  font=("Arial", 13, "bold"), bg="#1f6feb", fg="white",
                  relief="flat", bd=0, pady=12, cursor="hand2",
                  command=self._manual_issue_invoice).pack(fill="x", padx=12, pady=(4, 2))

        # سجل صغير
        tk.Label(right, text="📋 آخر العمليات:", fg="#5a7a9a", bg="#0d1526",
                 font=("Arial", 9)).pack(anchor="e", padx=12)
        self.manual_log_box = scrolledtext.ScrolledText(
            right, height=5, bg="#030810", fg="#3fb950",
            font=("Courier", 9), state="disabled", relief="flat")
        self.manual_log_box.pack(fill="both", expand=False, padx=12, pady=(0, 8))
        for tag, col in [("ok", "#3fb950"), ("err", "#f85149"), ("info", "#8aa8c8")]:
            self.manual_log_box.tag_config(tag, foreground=col)

    def _manual_log(self, msg, tag="info"):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.manual_log_box.config(state="normal")
        self.manual_log_box.insert("end", f"[{now}] {msg}\n", tag)
        self.manual_log_box.see("end")
        self.manual_log_box.config(state="disabled")

    def _manual_add_item(self):
        name  = self.manual_prod_name.get().strip()
        price_str = self.manual_prod_price.get().strip()
        qty_str   = self.manual_prod_qty.get().strip()

        if not name:
            messagebox.showwarning("تنبيه", "أدخل اسم المنتج!")
            return
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("تنبيه", "السعر يجب أن يكون رقماً موجباً!")
            return
        try:
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("تنبيه", "الكمية يجب أن تكون عدداً صحيحاً موجباً!")
            return

        item_total = price * qty
        num = len(self._manual_items) + 1
        self._manual_items.append({"name": name, "price": price, "qty": qty, "total": item_total})
        self.manual_items_tree.insert("", "end", values=(
            num, name, f"{price:.2f}", qty, f"{item_total:.2f}"))

        # تحديث المجموع
        grand = sum(i["total"] for i in self._manual_items)
        self.manual_total_var.set(f"{grand:.2f} ل.س")

        # مسح حقول المنتج
        self.manual_prod_name.delete(0, "end")
        self.manual_prod_price.delete(0, "end")
        self.manual_prod_qty.delete(0, "end")
        self.manual_prod_qty.insert(0, "1")
        self.manual_prod_name.focus()

        self._manual_log(f"✓ أُضيف: {name} × {qty} = {item_total:.2f} ل.س", "ok")

    def _manual_delete_item(self):
        sel = self.manual_items_tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر منتجاً لحذفه")
            return
        idx = self.manual_items_tree.index(sel[0])
        self.manual_items_tree.delete(sel[0])
        if 0 <= idx < len(self._manual_items):
            removed = self._manual_items.pop(idx)
            self._manual_log(f"🗑 حُذف: {removed['name']}", "err")
        # إعادة ترقيم الجدول
        for row in self.manual_items_tree.get_children():
            self.manual_items_tree.delete(row)
        for i, item in enumerate(self._manual_items):
            self.manual_items_tree.insert("", "end", values=(
                i+1, item["name"], f"{item['price']:.2f}", item["qty"], f"{item['total']:.2f}"))
        grand = sum(i["total"] for i in self._manual_items)
        self.manual_total_var.set(f"{grand:.2f} ل.س")

    def _manual_reset(self):
        if self._manual_items and not messagebox.askyesno("تأكيد", "مسح الفاتورة الحالية؟"):
            return
        self._manual_items.clear()
        for row in self.manual_items_tree.get_children():
            self.manual_items_tree.delete(row)
        self.manual_total_var.set("0.00 ل.س")
        self.manual_cust_name.delete(0, "end")
        self.manual_cust_phone.delete(0, "end")
        self.manual_prod_name.delete(0, "end")
        self.manual_prod_price.delete(0, "end")
        self.manual_prod_qty.delete(0, "end")
        self.manual_prod_qty.insert(0, "1")
        self._manual_log("🔄 تمت إعادة الضبط", "info")

    def _manual_browse_folder(self):
        folder = filedialog.askdirectory(title="اختر مجلد حفظ الفواتير")
        if folder:
            self.manual_save_path.set(folder)

    def _manual_issue_invoice(self):
        if not self._manual_items:
            messagebox.showwarning("تنبيه", "الفاتورة فارغة! أضف منتجاً على الأقل.")
            return
        cname  = self.manual_cust_name.get().strip() or "زبون"
        cphone = self.manual_cust_phone.get().strip() or "-"
        grand  = sum(i["total"] for i in self._manual_items)
        inv_num = f"MAN-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
        created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── بناء نص الفاتورة ──
        sep = "═" * 48
        lines = [
            sep,
            "          🛒 سوبر ماركت OS2 — فاتورة يدوية",
            sep,
            f"  رقم الفاتورة : {inv_num}",
            f"  الزبون       : {cname}",
            f"  الهاتف       : {cphone}",
            f"  التاريخ      : {created}",
            "─" * 48,
            f"  {'المنتج':<20} {'السعر':>8} {'الكمية':>6} {'الإجمالي':>9}",
            "─" * 48,
        ]
        items_str_parts = []
        for item in self._manual_items:
            line = f"  {item['name']:<20} {item['price']:>8.2f} {item['qty']:>6} {item['total']:>9.2f}"
            lines.append(line)
            items_str_parts.append(f"{item['name']} × {item['qty']} @ {item['price']:.2f} = {item['total']:.2f}")
        lines += [
            "─" * 48,
            f"  {'المجموع الكلي':>36} {grand:>9.2f} ل.س",
            sep,
            "         شكراً لتسوقكم معنا  🙏",
            sep,
        ]
        invoice_text = "\n".join(lines)
        items_str = "\n".join(items_str_parts)

        # ── حفظ في قاعدة البيانات ──
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""INSERT INTO invoices
                (invoice_number, customer_name, customer_phone, total, created_at, items)
                VALUES (?,?,?,?,?,?)""",
                (inv_num, cname, cphone, grand, created, items_str))
            conn.execute("COMMIT")
            conn.close()
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل حفظ الفاتورة في قاعدة البيانات:\n{e}")
            return

        # ── حفظ كملف نصي ──
        save_dir = self.manual_save_path.get().strip()
        if not save_dir:
            save_dir = os.path.join(os.path.expanduser("~"), "فواتير")
        try:
            os.makedirs(save_dir, exist_ok=True)
            filename = f"فاتورة_{inv_num}.txt"
            filepath = os.path.join(save_dir, filename)
            with open(filepath, "w", encoding="utf-8") as fout:
                fout.write(invoice_text)
            self._manual_log(f"✓ حُفظت الفاتورة: {filepath}", "ok")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل حفظ الملف:\n{e}")
            return

        # ── عرض نافذة الفاتورة ──
        self._refresh_invoices()
        self._manual_log(f"✓ فاتورة {inv_num} — {cname} — {grand:.2f} ل.س", "ok")
        ManualInvoicePopup(self, invoice_text, filepath)
        self._manual_reset()

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب الصناديق المتعددة (Multi-Cashier)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_cashier_tab(self):
        f = self.cashier_frame

        # ── عنوان ──
        tk.Label(f, text="🏪 محاكاة الصناديق المتعددة — Race Condition الحقيقي",
                 font=("Arial", 13, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(10, 3))
        tk.Label(f,
            text="كل صندوق Thread مستقل — المخزون مورد مشترك — الفرق بين Lock وبدونه واضح جداً!",
            font=("Arial", 9), fg="#5a7a9a", bg="#060d1a").pack(pady=(0, 5))

        # ── أزرار التحكم ──
        ctrl = tk.Frame(f, bg="#060d1a")
        ctrl.pack(fill="x", padx=15, pady=5)

        tk.Label(ctrl, text="عدد الصناديق:", fg="#8aa8c8", bg="#060d1a",
                 font=("Arial", 10)).pack(side="right", padx=5)
        self.num_cashiers_var = tk.IntVar(value=3)
        tk.Spinbox(ctrl, from_=2, to=5, textvariable=self.num_cashiers_var,
                   bg="#1a2a3a", fg="white", width=3, font=("Arial", 11),
                   relief="flat", bd=4).pack(side="right", padx=5)

        # خيار Lock/No-Lock — هذا هو الفرق الجوهري
        self.cashier_lock_var = tk.BooleanVar(value=True)
        lock_f = tk.Frame(ctrl, bg="#060d1a")
        lock_f.pack(side="right", padx=15)
        tk.Radiobutton(lock_f, text="🔒 مع Lock", variable=self.cashier_lock_var, value=True,
                       bg="#060d1a", fg="#3fb950", selectcolor="#1a2a3a",
                       font=("Arial", 10, "bold")).pack(side="right")
        tk.Radiobutton(lock_f, text="⚡ بدون Lock", variable=self.cashier_lock_var, value=False,
                       bg="#060d1a", fg="#f85149", selectcolor="#1a2a3a",
                       font=("Arial", 10, "bold")).pack(side="right", padx=10)

        self._btn(ctrl, "▶ تشغيل الصناديق", "#238636", self._start_cashier_sim, size=10).pack(side="left", padx=5)
        self._btn(ctrl, "⏹ إيقاف", "#b91c1c", self._stop_cashier_sim, size=10).pack(side="left", padx=5)
        self._btn(ctrl, "🔄 إعادة ضبط المخزون", "#d29922", self._reset_stock, size=10).pack(side="left", padx=5)

        # ── عرض بصري للصناديق ──
        self.cashier_canvas = tk.Canvas(f, bg="#030810", height=180,
                                        highlightthickness=1, highlightbackground="#1a2a3a")
        self.cashier_canvas.pack(fill="x", padx=15, pady=5)

        # ── إحصائيات الصناديق ──
        stats_f = tk.Frame(f, bg="#0d1526")
        stats_f.pack(fill="x", padx=15, pady=3)
        tk.Label(stats_f, text="إحصائيات الصناديق:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 9, "bold")).pack(side="right", padx=8)

        self.cashier_stats_frame = tk.Frame(stats_f, bg="#0d1526")
        self.cashier_stats_frame.pack(side="right", fill="x", expand=True)
        self.cashier_stat_labels = []

        # رسم بياني للمبيعات حسب الصندوق
        self.cashier_fig, (self.cashier_ax1, self.cashier_ax2) = plt.subplots(
            1, 2, figsize=(13, 2.8), facecolor="#060d1a")
        for ax in (self.cashier_ax1, self.cashier_ax2):
            ax.set_facecolor("#0d1526")
            ax.tick_params(colors="#c9d1d9", labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
        self.cashier_ax1.set_title("مبيعات كل صندوق (ل.س)", color="#c9d1d9", fontsize=9)
        self.cashier_ax2.set_title("Race Conditions لكل صندوق", color="#c9d1d9", fontsize=9)

        self.cashier_chart_canvas = FigureCanvasTkAgg(self.cashier_fig, master=f)
        self.cashier_chart_canvas.get_tk_widget().pack(fill="x", padx=15, pady=3)

        # ── سجل الصناديق ──
        tk.Label(f, text="📋 سجل الصناديق:", fg="#5a7a9a", bg="#060d1a", font=("Arial", 9)).pack(anchor="e", padx=15)
        self.cashier_log = scrolledtext.ScrolledText(f, height=6, bg="#030810", fg="#c9d1d9",
                                                      font=("Courier", 9), state="disabled", relief="flat")
        self.cashier_log.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        for tag, col in [("pool", "#60a5fa"), ("sync", "#00e5c3"), ("race", "#f85149"),
                          ("warn", "#d29922"), ("info", "#8aa8c8"), ("safe", "#3fb950")]:
            self.cashier_log.tag_config(tag, foreground=col)

    def _start_cashier_sim(self):
        """تشغيل محاكاة الصناديق المتعددة"""
        if self.cashier_sim:
            self.cashier_sim.stop()
            time.sleep(0.3)

        n = self.num_cashiers_var.get()
        use_lock = self.cashier_lock_var.get()

        self.cashier_sim = CashierSimulation(
            num_cashiers=n,
            use_lock=use_lock,
            log_callback=lambda msg, tag: self.after(0, lambda m=msg, t=tag: self._cashier_log(m, t))
        )
        self.cashier_sim.start()

        mode_txt = "🔒 مع Lock" if use_lock else "⚡ بدون Lock"
        self._cashier_log(f"▶ تشغيل {n} صناديق [{mode_txt}]", "sync")
        self._update_cashier_display()

    def _stop_cashier_sim(self):
        if self.cashier_sim:
            self.cashier_sim.stop()
            self._cashier_log("⏹ أُوقفت الصناديق", "warn")

    def _cashier_log(self, msg, tag="info"):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.cashier_log.config(state="normal")
        self.cashier_log.insert("end", f"[{now}] {msg}\n", tag)
        self.cashier_log.see("end")
        self.cashier_log.config(state="disabled")

    def _update_cashier_display(self):
        """تحديث العرض البصري للصناديق كل 300ms"""
        if not self.cashier_sim or not self.cashier_sim.running:
            return

        c = self.cashier_canvas
        c.delete("all")
        w = c.winfo_width() or 800
        h = 180
        c.create_rectangle(0, 0, w, h, fill="#030810")

        n = self.cashier_sim.num_cashiers
        box_w = max(100, min(160, (w - 40) // n - 10))
        colors = {"IDLE": "#30363d", "SERVING": "#238636", "WAITING": "#d29922", "DONE": "#1f6feb"}
        text_colors = {"IDLE": "#8aa8c8", "SERVING": "#ffffff", "WAITING": "#ffcc00", "DONE": "#ffffff"}
        icons = {"IDLE": "😴", "SERVING": "🛍", "WAITING": "⏳", "DONE": "✓"}

        for i in range(n):
            x = 20 + i * (box_w + 10)
            status = self.cashier_sim.cashier_status[i]
            sales = self.cashier_sim.cashier_sales[i]
            txns = self.cashier_sim.cashier_transactions[i]
            races = self.cashier_sim.cashier_races[i]
            col = colors.get(status, "#30363d")
            tc = text_colors.get(status, "#8aa8c8")
            icon = icons.get(status, "?")

            c.create_rectangle(x, 15, x+box_w, 165, fill=col, outline="#1a2a3a", width=2)
            c.create_text(x + box_w//2, 35, text=f"صندوق {i+1}", font=("Arial", 11, "bold"),
                          fill=tc)
            c.create_text(x + box_w//2, 60, text=f"{icon} {status}", font=("Arial", 9),
                          fill=tc)
            c.create_text(x + box_w//2, 90, text=f"مبيعات: {sales:.0f}", font=("Courier", 9),
                          fill="#c9d1d9")
            c.create_text(x + box_w//2, 112, text=f"عمليات: {txns}", font=("Courier", 9),
                          fill="#8aa8c8")
            if races > 0:
                c.create_text(x + box_w//2, 135, text=f"⚡ تضارب: {races}", font=("Arial", 9, "bold"),
                              fill="#f85149")
            # مؤشر انتظار القفل
            if status == "WAITING":
                c.create_oval(x+5, 148, x+15, 158, fill="#d29922", outline="#ffa500")
            elif status == "SERVING":
                c.create_oval(x+5, 148, x+15, 158, fill="#3fb950", outline="#00ff80")

        self.after(300, self._update_cashier_display)

        # تحديث الرسوم البيانية
        if self.cashier_sim.cashier_transactions:
            try:
                labels = [f"ص{i+1}" for i in range(n)]
                sales = self.cashier_sim.cashier_sales
                races = self.cashier_sim.cashier_races

                self.cashier_ax1.clear()
                self.cashier_ax1.set_facecolor("#0d1526")
                self.cashier_ax1.set_title("مبيعات كل صندوق (ل.س)", color="#c9d1d9", fontsize=9)
                self.cashier_ax1.tick_params(colors="#c9d1d9", labelsize=8)
                for sp in self.cashier_ax1.spines.values():
                    sp.set_color("#1a2a3a")
                bars = self.cashier_ax1.bar(labels, sales,
                                             color=["#1f6feb", "#238636", "#9a7000", "#a21caf", "#b91c1c"][:n])
                for bar, val in zip(bars, sales):
                    self.cashier_ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                                          f"{val:.0f}", ha="center", va="bottom",
                                          color="#c9d1d9", fontsize=8)

                self.cashier_ax2.clear()
                self.cashier_ax2.set_facecolor("#0d1526")
                self.cashier_ax2.set_title("Race Conditions لكل صندوق", color="#c9d1d9", fontsize=9)
                self.cashier_ax2.tick_params(colors="#c9d1d9", labelsize=8)
                for sp in self.cashier_ax2.spines.values():
                    sp.set_color("#1a2a3a")
                self.cashier_ax2.bar(labels, races,
                                      color="#f85149" if any(r > 0 for r in races) else "#3fb950")

                self.cashier_chart_canvas.draw()
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب مرئية الخيوط (Thread Visualization)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_thread_vis_tab(self):
        f = self.thread_vis_frame

        tk.Label(f, text="🎨 مرئية الخيوط المباشرة — Timeline بالألوان",
                 font=("Arial", 13, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(10, 3))
        tk.Label(f,
            text="أخضر = يعمل | أصفر = ينتظر قفل | أحمر = محجوب | رمادي = خامل",
            font=("Arial", 9), fg="#5a7a9a", bg="#060d1a").pack(pady=(0, 5))

        # لوحة Timeline المباشرة
        self.thread_vis_fig, self.thread_vis_ax = plt.subplots(figsize=(13, 4), facecolor="#060d1a")
        self.thread_vis_ax.set_facecolor("#0d1526")
        self.thread_vis_ax.tick_params(colors="#c9d1d9", labelsize=8)
        for sp in self.thread_vis_ax.spines.values():
            sp.set_color("#1a2a3a")

        self.thread_vis_canvas = FigureCanvasTkAgg(self.thread_vis_fig, master=f)
        self.thread_vis_canvas.get_tk_widget().pack(fill="x", padx=10, pady=5)

        # مفتاح الألوان
        legend_f = tk.Frame(f, bg="#0d1526")
        legend_f.pack(fill="x", padx=10, pady=3)
        for text, color in [("● يعمل", "#3fb950"), ("● ينتظر قفل", "#d29922"),
                             ("● محجوب", "#f85149"), ("● خامل", "#30363d")]:
            tk.Label(legend_f, text=text, font=("Arial", 10, "bold"),
                     fg=color, bg="#0d1526").pack(side="right", padx=10)

        # قائمة الخيوط الحالية
        threads_list_f = tk.Frame(f, bg="#0d1526")
        threads_list_f.pack(fill="both", expand=True, padx=10, pady=5)
        tk.Label(threads_list_f, text="قائمة الخيوط الحالية:", fg="#8aa8c8", bg="#0d1526",
                 font=("Arial", 10, "bold")).pack(side="right", padx=8, pady=5)

        self.thread_list_box = scrolledtext.ScrolledText(
            threads_list_f, height=10, bg="#030810", fg="#c9d1d9",
            font=("Courier", 9), state="disabled", relief="flat")
        self.thread_list_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("running", "#3fb950"), ("waiting", "#d29922"),
                          ("blocked", "#f85149"), ("idle", "#5a7a9a")]:
            self.thread_list_box.tag_config(tag, foreground=col)

        # بيانات Timeline
        self._thread_timeline = {}  # {thread_name: [(time, status), ...]}
        self._schedule_thread_vis_update()

    def _schedule_thread_vis_update(self):
        """تحديث مرئية الخيوط كل 500ms"""
        self._update_thread_vis()
        self.after(500, self._schedule_thread_vis_update)

    def _update_thread_vis(self):
        """تحديث رسم Timeline للخيوط"""
        try:
            now = time.time()
            threads = threading.enumerate()
            relevant = [t for t in threads
                        if any(kw in t.name for kw in
                               ["Pool", "Sale", "Producer", "Consumer", "Cashier",
                                "Race", "Restock", "Detector"])]

            # تحديث قائمة الخيوط
            self.thread_list_box.config(state="normal")
            self.thread_list_box.delete("1.0", "end")

            for t in relevant[:15]:
                status = "running" if t.is_alive() else "idle"
                # تلوين حسب الحالة
                if "Cashier" in t.name:
                    cidx = int(t.name.split("-")[-1]) - 1
                    if self.cashier_sim and cidx < len(self.cashier_sim.cashier_status):
                        st = self.cashier_sim.cashier_status[cidx]
                        status = {"WAITING": "waiting", "SERVING": "running"}.get(st, "idle")
                elif "Race" in t.name:
                    status = "blocked"

                icon = {"running": "🟢", "waiting": "🟡", "blocked": "🔴", "idle": "⚪"}.get(status, "⚪")
                self.thread_list_box.insert("end",
                    f"{icon} {t.name:<30} {'نشط' if t.is_alive() else 'خامل'}\n", status)

            self.thread_list_box.config(state="disabled")

            # رسم Timeline
            status_colors = {"running": "#3fb950", "waiting": "#d29922",
                             "blocked": "#f85149", "idle": "#30363d"}

            ax = self.thread_vis_ax
            ax.clear()
            ax.set_facecolor("#0d1526")
            ax.set_title("Timeline الخيوط المباشر", color="#c9d1d9", fontsize=9)
            ax.tick_params(colors="#c9d1d9", labelsize=7)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")

            y_pos = 0
            y_labels = []
            y_ticks = []

            for t in relevant[:8]:
                name = t.name[:20]
                status = "running" if t.is_alive() else "idle"

                if "Cashier" in t.name:
                    try:
                        cidx = int(t.name.split("-")[-1]) - 1
                        if self.cashier_sim and cidx < len(self.cashier_sim.cashier_status):
                            st = self.cashier_sim.cashier_status[cidx]
                            status = {"WAITING": "waiting", "SERVING": "running"}.get(st, "idle")
                    except Exception:
                        pass

                color = status_colors.get(status, "#30363d")
                ax.barh(y_pos, 1, left=0, height=0.6, color=color, alpha=0.85)
                ax.text(0.5, y_pos, f"{'نشط' if status == 'running' else 'ينتظر' if status == 'waiting' else 'خامل'}",
                        ha="center", va="center", color="white", fontsize=8)

                y_labels.append(name)
                y_ticks.append(y_pos)
                y_pos += 1

            if y_ticks:
                ax.set_yticks(y_ticks)
                ax.set_yticklabels(y_labels, color="#c9d1d9", fontsize=8)
            ax.set_xticks([])
            ax.set_xlim(0, 1)

            self.thread_vis_canvas.draw()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب إدارة المنتجات — إضافة / تعديل / حذف
    # ══════════════════════════════════════════════════════════════════════════
    def _build_products_tab(self):
        f = self.products_frame

        # ── عنوان ──
        tk.Label(f, text="📦 إدارة المنتجات",
                 font=("Arial", 15, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(12, 2))
        tk.Label(f, text="يمكنك إضافة منتجات جديدة، تعديل الأسعار والكميات، أو حذف منتج",
                 font=("Arial", 9), fg="#5a7a9a", bg="#060d1a").pack(pady=(0, 8))

        body = tk.Frame(f, bg="#060d1a")
        body.pack(fill="both", expand=True, padx=15, pady=5)

        # ══ يسار: جدول المنتجات ══
        left = tk.Frame(body, bg="#0d1526")
        left.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self._section_title(left, "قائمة المنتجات الحالية")

        # شريط بحث
        search_f = tk.Frame(left, bg="#0d1526")
        search_f.pack(fill="x", padx=10, pady=4)
        tk.Label(search_f, text="🔍", fg="#5a7a9a", bg="#0d1526",
                 font=("Arial", 12)).pack(side="right")
        self._pm_search_var = tk.StringVar()
        self._pm_search_var.trace("w", lambda *a: self._pm_refresh_table())
        tk.Entry(search_f, textvariable=self._pm_search_var,
                 bg="#1a2a3a", fg="white", insertbackground="white",
                 relief="flat", bd=6, justify="right",
                 font=("Arial", 11)).pack(side="right", fill="x", expand=True, padx=(0, 4))

        # الجدول
        cols = ("id", "name", "price", "stock")
        self._pm_tree = self._make_treeview(left, cols, {
            "id":    ("ID",      45),
            "name":  ("المنتج", 160),
            "price": ("السعر ل.س", 100),
            "stock": ("المخزون",  90),
        }, height=18)
        self._pm_tree.pack(fill="both", expand=True, padx=10, pady=4)
        self._pm_tree.bind("<<TreeviewSelect>>", self._pm_on_select)

        # أزرار الجدول
        btn_row = tk.Frame(left, bg="#0d1526")
        btn_row.pack(fill="x", padx=10, pady=(0, 8))
        self._btn(btn_row, "🔄 تحديث القائمة", "#1f6feb",
                  self._pm_refresh_table, size=10).pack(side="right", padx=3)
        self._btn(btn_row, "🗑 حذف المنتج المحدد", "#b91c1c",
                  self._pm_delete_product, size=10).pack(side="left", padx=3)

        # ══ يمين: نموذج الإدخال ══
        right = tk.Frame(body, bg="#0d1526", width=290)
        right.pack(side="left", fill="y", padx=(0, 5))
        right.pack_propagate(False)

        self._section_title(right, "إضافة / تعديل منتج")

        # حقول الإدخال
        fields_f = tk.Frame(right, bg="#0d1526")
        fields_f.pack(fill="x", padx=12, pady=8)

        def _lbl(text):
            tk.Label(fields_f, text=text, fg="#8aa8c8", bg="#0d1526",
                     font=("Arial", 10), anchor="e").pack(fill="x", pady=(6, 0))

        def _entry(var):
            e = tk.Entry(fields_f, textvariable=var,
                         bg="#1a2a3a", fg="white", insertbackground="white",
                         relief="flat", bd=6, font=("Arial", 12), justify="right")
            e.pack(fill="x", pady=(2, 0))
            return e

        self._pm_id_var    = tk.StringVar(value="")    # يُملأ تلقائياً عند اختيار منتج
        self._pm_name_var  = tk.StringVar()
        self._pm_price_var = tk.StringVar()
        self._pm_stock_var = tk.StringVar()

        _lbl("اسم المنتج:")
        _entry(self._pm_name_var)

        _lbl("السعر (ل.س):")
        _entry(self._pm_price_var)

        _lbl("الكمية في المخزون:")
        _entry(self._pm_stock_var)

        # مؤشر وضع التحرير
        self._pm_mode_var = tk.StringVar(value="➕ وضع الإضافة")
        mode_lbl = tk.Label(right, textvariable=self._pm_mode_var,
                            font=("Arial", 10, "bold"), fg="#d29922", bg="#0d1526")
        mode_lbl.pack(pady=(8, 2))

        # أزرار الإجراءات
        self._btn(right, "✅ حفظ / تعديل المنتج", "#238636",
                  self._pm_save_product, size=11).pack(fill="x", padx=12, pady=4)
        self._btn(right, "🆕 مسح النموذج (إضافة جديد)", "#9a7000",
                  self._pm_clear_form, size=10).pack(fill="x", padx=12, pady=2)

        # ── سجل العمليات ──
        tk.Label(right, text="📋 سجل العمليات:", fg="#5a7a9a", bg="#0d1526",
                 font=("Arial", 9)).pack(anchor="e", padx=12, pady=(12, 0))
        self._pm_log_box = scrolledtext.ScrolledText(
            right, height=10, bg="#030810", fg="#3fb950",
            font=("Courier", 9), state="disabled", relief="flat")
        self._pm_log_box.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        for tag, col in [("ok", "#3fb950"), ("err", "#f85149"),
                          ("warn", "#d29922"), ("info", "#8aa8c8")]:
            self._pm_log_box.tag_config(tag, foreground=col)

        # تحميل أولي
        self._pm_refresh_table()

    def _pm_log(self, msg, tag="info"):
        """تسجيل رسالة في سجل إدارة المنتجات"""
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._pm_log_box.config(state="normal")
        self._pm_log_box.insert("end", f"[{now}] {msg}\n", tag)
        self._pm_log_box.see("end")
        self._pm_log_box.config(state="disabled")

    def _pm_refresh_table(self):
        """تحديث جدول المنتجات من قاعدة البيانات"""
        keyword = self._pm_search_var.get().strip().lower()
        for row in self._pm_tree.get_children():
            self._pm_tree.delete(row)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()
            c.execute("SELECT id, name, price, stock FROM products ORDER BY id")
            for row in c.fetchall():
                pid, name, price, stock = row
                if keyword and keyword not in name.lower():
                    continue
                tag = "low" if stock <= 5 else ""
                self._pm_tree.insert("", "end", values=(pid, name, f"{price:.2f}", stock),
                                     tags=(tag,))
            conn.close()
            # لون أحمر للمنتجات المنخفضة
            self._pm_tree.tag_configure("low", foreground="#f85149")
        except Exception as e:
            self._pm_log(f"خطأ في تحميل المنتجات: {e}", "err")

        # تحديث shared_inventory أيضاً
        load_inventory()

    def _pm_on_select(self, event=None):
        """عند اختيار منتج من الجدول — يملأ النموذج تلقائياً للتعديل"""
        sel = self._pm_tree.selection()
        if not sel:
            return
        vals = self._pm_tree.item(sel[0], "values")
        if not vals:
            return
        pid, name, price, stock = vals
        self._pm_id_var.set(pid)
        self._pm_name_var.set(name)
        self._pm_price_var.set(price)
        self._pm_stock_var.set(stock)
        self._pm_mode_var.set(f"✏ وضع التعديل — المنتج #{pid}")

    def _pm_clear_form(self):
        """مسح النموذج للإضافة من جديد"""
        self._pm_id_var.set("")
        self._pm_name_var.set("")
        self._pm_price_var.set("")
        self._pm_stock_var.set("")
        self._pm_mode_var.set("➕ وضع الإضافة")
        # إلغاء التحديد في الجدول
        for item in self._pm_tree.selection():
            self._pm_tree.selection_remove(item)

    def _pm_save_product(self):
        """حفظ منتج جديد أو تعديل موجود حسب وضع النموذج"""
        name  = self._pm_name_var.get().strip()
        price_str = self._pm_price_var.get().strip()
        stock_str = self._pm_stock_var.get().strip()

        # ── تحقق من الحقول ──
        if not name:
            messagebox.showwarning("تنبيه", "يرجى إدخال اسم المنتج!")
            return
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("تنبيه", "يرجى إدخال سعر صحيح (رقم موجب)!")
            return
        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("تنبيه", "يرجى إدخال كمية صحيحة (رقم صحيح موجب)!")
            return

        pid_str = self._pm_id_var.get().strip()

        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")

            if pid_str:
                # ── تعديل منتج موجود ──
                pid = int(pid_str)
                conn.execute("UPDATE products SET name=?, price=?, stock=? WHERE id=?",
                             (name, price, stock, pid))
                conn.commit()
                conn.close()
                self._pm_log(f"✓ تم تعديل المنتج #{pid}: {name} | {price:.2f} ل.س | مخزون: {stock}", "ok")
                # تسجيل في audit_log
                db_audit("ProductManager", "EDIT_PRODUCT", pid, 0, stock, "DIRECT")
            else:
                # ── إضافة منتج جديد ──
                c = conn.cursor()
                c.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                          (name, price, stock))
                conn.commit()
                new_id = c.lastrowid
                conn.close()
                self._pm_log(f"✓ تمت إضافة منتج جديد: #{new_id} {name} | {price:.2f} ل.س | مخزون: {stock}", "ok")
                db_audit("ProductManager", "ADD_PRODUCT", new_id, 0, stock, "DIRECT")

        except Exception as e:
            self._pm_log(f"❌ خطأ في الحفظ: {e}", "err")
            messagebox.showerror("خطأ", f"فشل الحفظ:\n{e}")
            return

        # تحديث الجدول + مسح النموذج
        self._pm_refresh_table()
        self._pm_clear_form()
        # تحديث قائمة منتجات تبويب البيع أيضاً
        if hasattr(self, "_load_products"):
            self._load_products()

    def _pm_delete_product(self):
        """حذف المنتج المحدد من الجدول بعد تأكيد"""
        sel = self._pm_tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "يرجى تحديد منتج من القائمة أولاً!")
            return
        vals = self._pm_tree.item(sel[0], "values")
        pid, name = int(vals[0]), vals[1]

        if not messagebox.askyesno("تأكيد الحذف",
                                   f"هل تريد حذف المنتج:\n«{name}» (#{pid}) ؟\n\nلا يمكن التراجع عن هذه العملية!"):
            return
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
            conn.close()
            self._pm_log(f"🗑 تم حذف المنتج: #{pid} {name}", "warn")
            db_audit("ProductManager", "DELETE_PRODUCT", pid, 0, 0, "DIRECT")
        except Exception as e:
            self._pm_log(f"❌ خطأ في الحذف: {e}", "err")
            messagebox.showerror("خطأ", f"فشل الحذف:\n{e}")
            return

        self._pm_refresh_table()
        self._pm_clear_form()
        if hasattr(self, "_load_products"):
            self._load_products()

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب الفواتير
    # ══════════════════════════════════════════════════════════════════════════
    def _build_invoices_tab(self):
        f = self.inv_frame
        self._section_title(f, "الفواتير المحفوظة")

        sf = tk.Frame(f, bg="#060d1a")
        sf.pack(fill="x", padx=20, pady=5)
        self.inv_search = tk.StringVar()
        tk.Entry(sf, textvariable=self.inv_search, bg="#1a2a3a", fg="white",
                 insertbackground="white", relief="flat", bd=6, font=("Arial", 11),
                 justify="right").pack(side="right", fill="x", expand=True, padx=(0, 5))
        self._btn(sf, "🔍 بحث", "#1f6feb", self._refresh_invoices, size=10).pack(side="right")
        self._btn(sf, "📄 تصدير تقرير", "#238636", self._export_report, size=10).pack(side="left")

        cols = ("inv_num", "customer", "phone", "date", "total")
        self.inv_tree = self._make_treeview(f, cols, {
            "inv_num": ("رقم الفاتورة", 200), "customer": ("العميل", 130),
            "phone": ("الهاتف", 110), "date": ("التاريخ", 170), "total": ("الإجمالي", 100)
        }, height=12)
        self.inv_tree.pack(fill="x", padx=20, pady=5)
        self.inv_tree.bind("<<TreeviewSelect>>", self._show_invoice_detail)

        detail_f = tk.Frame(f, bg="#0d1526")
        detail_f.pack(fill="both", expand=True, padx=20, pady=5)
        self.inv_detail = scrolledtext.ScrolledText(detail_f, bg="#030810", fg="#c9d1d9",
                                                     font=("Courier", 10), relief="flat")
        self.inv_detail.pack(fill="both", expand=True, padx=10, pady=10)
        self._refresh_invoices()

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب Race Condition — 5 سيناريوهات
    # ══════════════════════════════════════════════════════════════════════════
    def _build_race_tab(self):
        f = self.race_frame

        top_f = tk.Frame(f, bg="#1a0808")
        top_f.pack(fill="x")
        self.corruption_var = tk.StringVar(value="0")
        self.success_var = tk.StringVar(value="0")
        self.fail_var = tk.StringVar(value="0")
        self.corruption_pct_var = tk.StringVar(value="نسبة الفساد: 0.0%")

        metrics = [
            ("⚡ تضارب بيانات", self.corruption_var, "#f85149"),
            ("✅ عمليات ناجحة", self.success_var, "#3fb950"),
            ("❌ عمليات فاشلة", self.fail_var, "#d29922"),
        ]
        for i, (lbl, var, col) in enumerate(metrics):
            fr = tk.Frame(top_f, bg="#1a0808")
            fr.grid(row=0, column=i, padx=20, pady=8, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg="#1a0808", font=("Arial", 10, "bold")).pack()
            tk.Label(fr, textvariable=var, fg=col, bg="#1a0808", font=("Arial", 26, "bold")).pack()
        tk.Label(top_f, textvariable=self.corruption_pct_var,
                 fg="#f85149", bg="#1a0808", font=("Arial", 11, "bold")).grid(row=0, column=3, padx=20)
        for i in range(4):
            top_f.columnconfigure(i, weight=1)

        mid_top = tk.Frame(f, bg="#060d1a")
        mid_top.pack(fill="x", padx=10, pady=3)
        self._section_title(mid_top, "⏱ Timeline مرئي للتضارب")

        self.timeline_fig, self.timeline_ax = plt.subplots(figsize=(12, 2.5), facecolor="#060d1a")
        self.timeline_ax.set_facecolor("#0d1526")
        self.timeline_ax.tick_params(colors="#c9d1d9")
        for sp in self.timeline_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.timeline_canvas = FigureCanvasTkAgg(self.timeline_fig, master=mid_top)
        self.timeline_canvas.get_tk_widget().pack(fill="x", padx=5)

        mid = tk.Frame(f, bg="#060d1a")
        mid.pack(fill="both", expand=True, padx=10, pady=3)

        left_panel = tk.Frame(mid, bg="#0d1526", width=310)
        left_panel.pack(side="left", fill="both", padx=(0, 5))
        left_panel.pack_propagate(False)
        self._section_title(left_panel, "🔍 مراقب الخيوط (Live)")
        self.thread_monitor_box = scrolledtext.ScrolledText(
            left_panel, height=14, bg="#030810", fg="#00e5c3",
            font=("Courier", 10), state="disabled", relief="flat")
        self.thread_monitor_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("running", "#00e5c3"), ("waiting", "#d29922"),
                          ("done", "#3fb950"), ("race", "#f85149"),
                          ("sync", "#79c0ff"), ("safe", "#56d364")]:
            self.thread_monitor_box.tag_config(tag, foreground=col)

        right_panel = tk.Frame(mid, bg="#0d1526")
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "📋 سجل Race Condition المفصّل")
        self.race_detail_log = scrolledtext.ScrolledText(
            right_panel, height=14, bg="#030810", fg="#c9d1d9",
            font=("Courier", 9), state="disabled", relief="flat")
        self.race_detail_log.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("race", "#f85149"), ("safe", "#3fb950"), ("info", "#8aa8c8"),
                          ("warn", "#d29922"), ("scenario", "#a78bfa"),
                          ("sync", "#79c0ff"), ("ok", "#56d364")]:
            self.race_detail_log.tag_config(tag, foreground=col)

        scenarios_f = tk.Frame(f, bg="#060d1a")
        scenarios_f.pack(fill="x", padx=10, pady=5)
        tk.Label(scenarios_f, text="5 سيناريوهات للاختبار:", fg="#8aa8c8",
                 bg="#060d1a", font=("Arial", 10, "bold")).pack(side="right", padx=8)

        self.scenario_btns = []
        scenario_defs = [
            ("1. بدون قفل", "#b91c1c", 0),
            ("2. مع Mutex", "#238636", 1),
            ("3. Semaphore(2)", "#9a7000", 2),
            ("4. RWLock", "#1a4a8a", 3),
            ("5. Barrier+Mutex", "#6a2a8a", 4),
        ]
        for label, color, scenario_id in scenario_defs:
            btn = self._btn(scenarios_f, label, color,
                            lambda sid=scenario_id: self._run_race_scenario(sid), size=9)
            btn.pack(side="right", padx=3, pady=3)
            self.scenario_btns.append(btn)

        ctrl_f = tk.Frame(f, bg="#060d1a")
        ctrl_f.pack(fill="x", padx=10, pady=2)
        self._btn(ctrl_f, "▶ شغّل الجميع", "#238636",
                  self._run_all_scenarios, size=10).pack(side="right", padx=5)
        self._btn(ctrl_f, "🗑 مسح السجل", "#30363d",
                  self._clear_race_log, size=10).pack(side="left", padx=5)

        # ══ منطقة Stress Test ═══════════════════════════════════════════════
        stress_outer = tk.Frame(f, bg="#1a0508", bd=0,
                                highlightbackground="#f85149", highlightthickness=1)
        stress_outer.pack(fill="x", padx=10, pady=(4, 8))

        # ── رأس Stress Test ──────────────────────────────────────────────────
        stress_hdr = tk.Frame(stress_outer, bg="#1a0508")
        stress_hdr.pack(fill="x", padx=10, pady=(6, 2))

        tk.Label(stress_hdr,
                 text="🔥 Stress Test — 20 خيطاً يهجمون على نفس المورد",
                 font=("Arial", 11, "bold"), fg="#f85149", bg="#1a0508").pack(side="right")

        tk.Label(stress_hdr,
                 text="يُظهر الفرق الحقيقي بين Race Condition و Mutex أمام المدرس",
                 font=("Arial", 8), fg="#6a2a2a", bg="#1a0508").pack(side="left", padx=5)

        # ── عدادات حية (Race / ناجح / فاشل) ─────────────────────────────────
        counters_f = tk.Frame(stress_outer, bg="#1a0508")
        counters_f.pack(fill="x", padx=10, pady=2)

        self.stress_race_var    = tk.StringVar(value="0")
        self.stress_success_var = tk.StringVar(value="0")
        self.stress_fail_var    = tk.StringVar(value="0")
        self.stress_phase_var   = tk.StringVar(value="جاهز")

        for col_idx, (lbl, var, color) in enumerate([
            ("⚡ Race Conditions", self.stress_race_var,    "#f85149"),
            ("✅ ناجحة",           self.stress_success_var, "#3fb950"),
            ("❌ فاشلة",           self.stress_fail_var,    "#d29922"),
        ]):
            cf = tk.Frame(counters_f, bg="#1a0508")
            cf.grid(row=0, column=col_idx, padx=18, pady=4)
            tk.Label(cf, text=lbl, fg=color, bg="#1a0508",
                     font=("Arial", 9, "bold")).pack()
            tk.Label(cf, textvariable=var, fg=color, bg="#1a0508",
                     font=("Arial", 22, "bold")).pack()

        # مؤشر المرحلة الحالية
        tk.Label(counters_f, textvariable=self.stress_phase_var,
                 fg="#d29922", bg="#1a0508",
                 font=("Arial", 10, "bold")).grid(row=0, column=3, padx=20)
        for c in range(4):
            counters_f.columnconfigure(c, weight=1)

        # ── أشرطة تقدم الـ 20 خيط ────────────────────────────────────────────
        bars_lbl = tk.Label(stress_outer,
                            text="شريط تقدم الخيوط الـ 20:",
                            fg="#6a3a3a", bg="#1a0508", font=("Arial", 8))
        bars_lbl.pack(anchor="e", padx=10)

        bars_outer = tk.Frame(stress_outer, bg="#1a0508")
        bars_outer.pack(fill="x", padx=10, pady=(0, 4))

        self._stress_bars    = []   # قائمة Canvas لكل خيط
        self._stress_bar_ids = []   # معرّف المستطيل داخل كل Canvas

        # 20 شريط مقسّمة على صفين (10 في كل صف)
        BAR_W, BAR_H = 50, 14
        COLORS_20 = [
            "#f85149","#ff7b72","#ffa657","#d29922","#e3b341",
            "#3fb950","#56d364","#00e5c3","#26c6da","#1f6feb",
            "#58a6ff","#79c0ff","#a5d6ff","#a78bfa","#c084fc",
            "#f0abfc","#fb7185","#fb923c","#a3e635","#34d399",
        ]
        for row in range(2):
            row_f = tk.Frame(bars_outer, bg="#1a0508")
            row_f.pack(fill="x", pady=1)
            for col in range(10):
                idx = row * 10 + col
                c = tk.Canvas(row_f, width=BAR_W, height=BAR_H,
                              bg="#030810", highlightthickness=0)
                c.pack(side="left", padx=1)
                bar_id = c.create_rectangle(0, 0, 0, BAR_H,
                                            fill=COLORS_20[idx], outline="")
                self._stress_bars.append(c)
                self._stress_bar_ids.append((bar_id, BAR_W, COLORS_20[idx]))

        # ── زر التشغيل + تقدم كلي ────────────────────────────────────────────
        stress_ctrl = tk.Frame(stress_outer, bg="#1a0508")
        stress_ctrl.pack(fill="x", padx=10, pady=(4, 8))

        self.stress_btn = tk.Button(
            stress_ctrl,
            text="🔥 Stress Test — ابدأ (20 خيطاً)",
            font=("Arial", 11, "bold"),
            bg="#b91c1c", fg="white",
            activebackground="#991010", activeforeground="white",
            relief="flat", bd=0, pady=10, cursor="hand2",
            command=self._run_stress_test
        )
        self.stress_btn.pack(side="right", fill="x", expand=True, padx=(0, 6))

        self._stress_overall = ttk.Progressbar(
            stress_ctrl, length=180, mode="determinate",
            style="red.Horizontal.TProgressbar"
        )
        self._stress_overall.pack(side="left", padx=4, pady=6)

        # تهيئة style شريط التقدم
        _st = ttk.Style()
        _st.configure("red.Horizontal.TProgressbar",
                       troughcolor="#0d0408", background="#f85149",
                       darkcolor="#f85149", lightcolor="#f85149",
                       bordercolor="#1a0508")
        _st.configure("green.Horizontal.TProgressbar",
                       troughcolor="#040d04", background="#3fb950",
                       darkcolor="#3fb950", lightcolor="#3fb950",
                       bordercolor="#1a0508")

        # متغير داخلي لمنع تشغيل مزدوج
        self._stress_running = False

    # ══════════════════════════════════════════════════════════════════════════
    # منطق Stress Test
    # ══════════════════════════════════════════════════════════════════════════
    def _run_stress_test(self):
        """
        Stress Test: 20 خيطاً يهجمون على نفس المنتج مرتين:
          المرة الأولى  → بدون Sync  → يظهر الفوضى والتضارب
          المرة الثانية → مع Mutex   → يظهر النظام والترتيب
        """
        if self._stress_running:
            return
        self._stress_running = True
        self.stress_btn.config(state="disabled", text="⏳ الاختبار جارٍ...")

        # تشغيل في خيط مستقل حتى لا تتجمّد الواجهة
        t = threading.Thread(target=self._stress_test_worker,
                             daemon=True, name="StressTest-Master")
        t.start()

    def _stress_test_worker(self):
        """
        عامل Stress Test — يعمل في خيط خلفي.
        يُشغّل جولتين متتاليتين: بدون Sync ثم مع Mutex.
        يُحدّث الواجهة عبر self.after() لأمان الخيوط.
        """
        NUM_THREADS  = 20       # عدد الخيوط في كل جولة
        PRODUCT_ID   = 1        # منتج الاختبار (id=1)
        INITIAL_STOCK = 100     # مخزون ابتدائي لكل جولة

        results = {}            # نتائج الجولتين لعرضها في النافذة المنبثقة

        for phase_idx, (phase_name, use_lock) in enumerate([
            ("بدون Sync ⚡",  False),
            ("مع Mutex 🔒",   True),
        ]):
            # ── تهيئة الجولة ────────────────────────────────────────────────
            self.after(0, lambda p=phase_name: self.stress_phase_var.set(f"المرحلة: {p}"))
            self.after(0, lambda: self.stress_race_var.set("0"))
            self.after(0, lambda: self.stress_success_var.set("0"))
            self.after(0, lambda: self.stress_fail_var.set("0"))
            self.after(0, lambda: self._reset_stress_bars())
            self.after(0, lambda s="red" if not use_lock else "green":
                       self._stress_overall.config(
                           style=f"{s}.Horizontal.TProgressbar", value=0))

            # إعادة ضبط مخزون المنتج في الذاكرة
            import core as _core
            with _core.stock_lock:
                if PRODUCT_ID in _core.shared_inventory:
                    _core.shared_inventory[PRODUCT_ID]["stock"] = INITIAL_STOCK
                else:
                    _core.shared_inventory[PRODUCT_ID] = {
                        "name": "منتج الاختبار", "price": 1.0,
                        "stock": INITIAL_STOCK
                    }

            # مُتغيرات النتائج المشتركة بين الخيوط
            local_lock      = threading.Lock()   # لحماية متغيرات النتائج فقط
            shared_mutex    = threading.Lock()   # قفل Mutex للجولة الثانية
            race_count      = [0]
            success_count   = [0]
            fail_count      = [0]
            negative_stock  = [False]
            done_count      = [0]

            # حاجز الانطلاق: جميع الـ 20 خيطاً تنتظر هنا ثم تنطلق معاً
            # هذا هو أوضح تطبيق لـ Barrier — تضمن أن الخيوط تبدأ في نفس اللحظة
            start_barrier = threading.Barrier(NUM_THREADS)

            def thread_worker(tid, use_lock=use_lock):
                """عامل خيط واحد في Stress Test"""
                bar_idx = tid          # فهرس شريط التقدم
                bar_progress = [0]     # تقدم هذا الخيط (0→100)

                try:
                    # ── انتظر عند الـ Barrier حتى يكون الجميع جاهزين ──
                    start_barrier.wait(timeout=5.0)
                except threading.BrokenBarrierError:
                    return

                # تحديث شريط التقدم: جارٍ
                self.after(0, lambda i=bar_idx: self._set_stress_bar(i, 20))

                # ── قراءة المخزون الحالي ──
                import core as _core_inner
                time.sleep(random.uniform(0.005, 0.03))  # تأخير عشوائي (نافذة التضارب)
                bar_progress[0] = 40
                self.after(0, lambda i=bar_idx, p=bar_progress[0]:
                           self._set_stress_bar(i, p))

                if use_lock:
                    # ── وضع Mutex: انتظر القفل ──
                    self._race_log(f"[StressThread-{tid:02d}] ⏳ ينتظر القفل...", "warn")
                    shared_mutex.acquire()
                    self._race_log(f"[StressThread-{tid:02d}] 🔒 حصل على القفل", "safe")

                try:
                    # ── العملية الحرجة (Critical Section) ──
                    current = _core_inner.shared_inventory.get(PRODUCT_ID, {}).get("stock", 0)
                    time.sleep(random.uniform(0.002, 0.015))  # محاكاة معالجة

                    if not use_lock:
                        # نافذة التضارب: نقرأ ونكتب بدون حماية
                        time.sleep(random.uniform(0.001, 0.01))

                    new_stock = current - 1

                    if new_stock < 0:
                        # تضارب مكتشف: مخزون سالب = Race Condition حقيقية!
                        with local_lock:
                            race_count[0] += 1
                            negative_stock[0] = True
                        self._race_log(
                            f"[StressThread-{tid:02d}] ⚡ RACE! مخزون={new_stock} (تضارب!)",
                            "race"
                        )
                        with _core_inner.stats_lock:
                            _core_inner.race_stats["corruption_count"] += 1
                        with local_lock:
                            fail_count[0] += 1
                    else:
                        _core_inner.shared_inventory[PRODUCT_ID]["stock"] = new_stock
                        with local_lock:
                            success_count[0] += 1
                        if use_lock:
                            self._race_log(
                                f"[StressThread-{tid:02d}] ✅ نجح | مخزون={new_stock}",
                                "safe"
                            )

                finally:
                    if use_lock:
                        shared_mutex.release()
                        self._race_log(f"[StressThread-{tid:02d}] 🔓 حرَّر القفل", "sync")

                # ── تحديث العدادات الحية كل 0.1 ثانية ──
                with local_lock:
                    done_count[0] += 1
                    _r = race_count[0]
                    _s = success_count[0]
                    _f = fail_count[0]
                    _d = done_count[0]

                self.after(0, lambda r=_r, s=_s, f=_f: (
                    self.stress_race_var.set(str(r)),
                    self.stress_success_var.set(str(s)),
                    self.stress_fail_var.set(str(f)),
                ))
                self.after(0, lambda d=_d: self._stress_overall.config(
                    value=(d / NUM_THREADS) * 100))
                self.after(0, lambda i=bar_idx: self._set_stress_bar(i, 100))

            # ── إطلاق الـ 20 خيطاً ──────────────────────────────────────────
            threads = []
            for i in range(NUM_THREADS):
                t = threading.Thread(
                    target=thread_worker, args=(i,),
                    daemon=True,
                    name=f"StressThread-{i:02d}-{'Lock' if use_lock else 'NoLock'}"
                )
                threads.append(t)

            for t in threads:
                t.start()

            for t in threads:
                t.join(timeout=10.0)

            # حفظ نتائج هذه الجولة
            results[phase_name] = {
                "races":    race_count[0],
                "success":  success_count[0],
                "fail":     fail_count[0],
                "negative": negative_stock[0],
            }

            # فاصل بين الجولتين
            self.after(0, lambda p=phase_name: self._race_log(
                f"\n{'='*50}\n✅ انتهت المرحلة: {p}\n{'='*50}\n", "scenario"))
            time.sleep(1.2)

        # ── عرض النتائج النهائية ────────────────────────────────────────────
        self.after(0, lambda: self._show_stress_results(results))
        self.after(0, lambda: self.stress_phase_var.set("✅ اكتمل"))
        self.after(0, lambda: self.stress_btn.config(
            state="normal", text="🔥 Stress Test — ابدأ (20 خيطاً)"))
        self._stress_running = False

    def _reset_stress_bars(self):
        """إعادة جميع أشرطة التقدم لـ 0"""
        for i, (c, bar_id_w) in enumerate(
                zip(self._stress_bars, self._stress_bar_ids)):
            bar_id, bar_w, color = bar_id_w
            c.coords(bar_id, 0, 0, 0, 14)

    def _set_stress_bar(self, idx: int, pct: int):
        """تحديث شريط تقدم خيط معيّن (pct: 0-100)"""
        if idx >= len(self._stress_bars):
            return
        c = self._stress_bars[idx]
        bar_id, bar_w, color = self._stress_bar_ids[idx]
        filled = int(bar_w * pct / 100)
        c.coords(bar_id, 0, 0, filled, 14)

    def _race_log(self, msg: str, tag: str = "info"):
        """تسجيل رسالة في سجل Race Condition بأمان من أي خيط"""
        def _do():
            if hasattr(self, "race_detail_log"):
                self.race_detail_log.config(state="normal")
                self.race_detail_log.insert("end", f"[{_ts()}] {msg}\n", tag)
                self.race_detail_log.see("end")
                self.race_detail_log.config(state="disabled")
        self.after(0, _do)

    def _show_stress_results(self, results: dict):
        """عرض نافذة منبثقة بنتائج Stress Test"""
        no_sync = results.get("بدون Sync ⚡", {})
        with_mutex = results.get("مع Mutex 🔒", {})

        races_no   = no_sync.get("races", 0)
        races_yes  = with_mutex.get("races", 0)
        neg_no     = "نعم ❌" if no_sync.get("negative") else "لا ✅"
        neg_yes    = "لا ✅" if not with_mutex.get("negative") else "نعم ❌"
        fail_no    = no_sync.get("fail", 0)
        fail_yes   = with_mutex.get("fail", 0)

        prevented = races_no - races_yes
        pct = (prevented / races_no * 100) if races_no > 0 else 100.0

        popup = tk.Toplevel(self)
        popup.title("نتائج Stress Test 🔥")
        popup.configure(bg="#0d1526")
        popup.geometry("480x420")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.grab_set()

        tk.Label(popup, text="🔥 نتائج Stress Test",
                 font=("Arial", 15, "bold"), fg="#f85149", bg="#0d1526").pack(pady=(18, 6))
        tk.Frame(popup, bg="#00e5c3", height=2).pack(fill="x", padx=30)

        body = tk.Frame(popup, bg="#0d1526")
        body.pack(fill="both", expand=True, padx=30, pady=10)

        # ── جدول النتائج ────────────────────────────────────────────────────
        rows = [
            ("",              "بدون Sync ⚡",   "مع Mutex 🔒"),
            ("Race Conditions", f"{races_no} ⚡", f"{races_yes} {'✅' if races_yes == 0 else '⚠'}"),
            ("مخزون سالب",     neg_no,           neg_yes),
            ("عمليات فاشلة",   str(fail_no),      str(fail_yes)),
        ]
        col_colors = ["#8aa8c8", "#f85149", "#3fb950"]
        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row):
                bg = "#0d1526" if r_idx > 0 else "#0a1a2e"
                fg = col_colors[c_idx] if r_idx == 0 else (
                    "#f85149" if c_idx == 1 and r_idx > 0 else
                    "#3fb950" if c_idx == 2 and r_idx > 0 else "#c9d1d9"
                )
                font = ("Arial", 10, "bold") if r_idx == 0 else ("Arial", 11)
                tk.Label(body, text=cell, fg=fg, bg=bg,
                         font=font, width=18, relief="flat",
                         pady=6).grid(row=r_idx, column=c_idx,
                                      padx=3, pady=2, sticky="ew")
        for c in range(3):
            body.columnconfigure(c, weight=1)

        tk.Frame(popup, bg="#1a2a3a", height=1).pack(fill="x", padx=30)

        # ── الخلاصة ─────────────────────────────────────────────────────────
        summary_color = "#3fb950" if pct >= 100 else "#d29922"
        summary_text = (
            f"🏆 Mutex منع {pct:.0f}% من التضارب!"
            if pct >= 100 else
            f"⚠ Mutex خفّض التضارب بنسبة {pct:.0f}%"
        )
        tk.Label(popup, text=summary_text,
                 font=("Arial", 13, "bold"),
                 fg=summary_color, bg="#0d1526").pack(pady=(10, 4))

        detail = (
            "✅ نتيجة مثالية: Mutex أزال جميع حالات Race Condition\n"
            "هذا يُثبت أهمية التزامن في أنظمة التشغيل!"
        ) if pct >= 100 else (
            f"تم منع {prevented} حالة تضارب من أصل {races_no}\n"
            "قد تحتاج لزيادة عدد الخيوط لرؤية الفرق بوضوح أكثر."
        )
        tk.Label(popup, text=detail, font=("Arial", 9),
                 fg="#8aa8c8", bg="#0d1526", justify="center").pack(pady=2)

        tk.Button(popup, text="✓ إغلاق",
                  font=("Arial", 11, "bold"),
                  bg="#00e5c3", fg="#060d1a",
                  relief="flat", bd=0, pady=8,
                  command=popup.destroy).pack(fill="x", padx=60, pady=(8, 18))

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب Producer-Consumer المتقدم
    # ══════════════════════════════════════════════════════════════════════════
    def _build_producer_consumer_tab(self):
        f = self.pc_frame
        self.pc_running = False
        self.pc_priority_queue = PriorityQueue(maxsize=15)
        self.pc_producers = []
        self.pc_consumers = []

        title_f = tk.Frame(f, bg="#0a180a")
        title_f.pack(fill="x")
        tk.Label(title_f, text="🔄 Producer-Consumer المتقدم (Priority Queue)",
                 font=("Arial", 13, "bold"), fg="#3fb950", bg="#0a180a").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text="عدة Producers تُنتج → Priority Queue مشتركة → عدة Consumers تستهلك",
                 font=("Arial", 10), fg="#3a6a3a", bg="#0a180a").pack(side="right", padx=10)

        mid = tk.Frame(f, bg="#060d1a")
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        left_panel = tk.Frame(mid, bg="#0d1526", width=400)
        left_panel.pack(side="left", fill="both", padx=(0, 5))
        left_panel.pack_propagate(False)
        self._section_title(left_panel, "📦 Priority Queue (سعة 15)")

        self.pc_canvas = tk.Canvas(left_panel, bg="#030810", width=380, height=200,
                                   highlightthickness=1, highlightbackground="#1a2a3a")
        self.pc_canvas.pack(padx=8, pady=5)

        self.pc_fig, self.pc_ax = plt.subplots(figsize=(4.5, 2.5), facecolor="#060d1a")
        self.pc_ax.set_facecolor("#0d1526")
        self.pc_ax.set_title("Queue Size عبر الزمن", color="#c9d1d9", fontsize=9)
        self.pc_ax.tick_params(colors="#c9d1d9", labelsize=8)
        for sp in self.pc_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.pc_chart_canvas = FigureCanvasTkAgg(self.pc_fig, master=left_panel)
        self.pc_chart_canvas.get_tk_widget().pack(fill="x", padx=8)
        self.pc_history = []

        stats_f = tk.Frame(left_panel, bg="#0d1526")
        stats_f.pack(fill="x", padx=8, pady=3)
        self.pc_produced_var = tk.StringVar(value="0")
        self.pc_consumed_var = tk.StringVar(value="0")
        self.pc_overflow_var = tk.StringVar(value="0")
        for i, (lbl, var, col) in enumerate([
            ("منتَج:", self.pc_produced_var, "#3fb950"),
            ("مستهلَك:", self.pc_consumed_var, "#f85149"),
            ("تجاوز Buffer:", self.pc_overflow_var, "#ffa500"),
        ]):
            tk.Label(stats_f, text=lbl, fg="#8aa8c8", bg="#0d1526", font=("Arial", 9)).grid(row=0, column=i*2, padx=4)
            tk.Label(stats_f, textvariable=var, fg=col, bg="#0d1526", font=("Arial", 14, "bold")).grid(row=0, column=i*2+1, padx=4)

        ctrl_f = tk.Frame(left_panel, bg="#0d1526")
        ctrl_f.pack(fill="x", padx=8, pady=3)
        tk.Label(ctrl_f, text="عدد Producers:", fg="#3fb950", bg="#0d1526", font=("Arial", 10)).pack(side="right")
        self.pc_num_producers = tk.IntVar(value=2)
        tk.Spinbox(ctrl_f, from_=1, to=5, textvariable=self.pc_num_producers,
                   bg="#1a2a3a", fg="#3fb950", width=3, font=("Arial", 10),
                   relief="flat", bd=4).pack(side="right", padx=4)
        tk.Label(ctrl_f, text="Consumers:", fg="#f85149", bg="#0d1526", font=("Arial", 10)).pack(side="right", padx=10)
        self.pc_num_consumers = tk.IntVar(value=1)
        tk.Spinbox(ctrl_f, from_=1, to=5, textvariable=self.pc_num_consumers,
                   bg="#1a2a3a", fg="#f85149", width=3, font=("Arial", 10),
                   relief="flat", bd=4).pack(side="right", padx=4)

        speed_f = tk.Frame(left_panel, bg="#0d1526")
        speed_f.pack(fill="x", padx=8, pady=3)
        tk.Label(speed_f, text="إنتاج (ث):", fg="#3fb950", bg="#0d1526", font=("Arial", 9)).pack(side="right")
        self.pc_prod_speed = tk.DoubleVar(value=0.5)
        tk.Scale(speed_f, from_=0.1, to=2.0, resolution=0.1, variable=self.pc_prod_speed,
                 orient="horizontal", bg="#0d1526", fg="#3fb950", highlightthickness=0,
                 length=90, troughcolor="#1a2a3a").pack(side="right")
        tk.Label(speed_f, text="استهلاك (ث):", fg="#f85149", bg="#0d1526", font=("Arial", 9)).pack(side="right", padx=8)
        self.pc_cons_speed = tk.DoubleVar(value=1.0)
        tk.Scale(speed_f, from_=0.1, to=3.0, resolution=0.1, variable=self.pc_cons_speed,
                 orient="horizontal", bg="#0d1526", fg="#f85149", highlightthickness=0,
                 length=90, troughcolor="#1a2a3a").pack(side="right")

        btn_f = tk.Frame(left_panel, bg="#0d1526")
        btn_f.pack(fill="x", padx=8, pady=5)
        self._btn(btn_f, "▶ تشغيل", "#238636", self._start_pc, size=10).pack(side="right", padx=3, fill="x", expand=True)
        self._btn(btn_f, "⏹ إيقاف", "#b91c1c", self._stop_pc, size=10).pack(side="right", padx=3, fill="x", expand=True)

        right_panel = tk.Frame(mid, bg="#0d1526")
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "📋 سجل Producer-Consumer")
        self.pc_log_box = scrolledtext.ScrolledText(
            right_panel, height=20, bg="#030810", fg="#c9d1d9",
            font=("Courier", 9), state="disabled", relief="flat")
        self.pc_log_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("produce", "#3fb950"), ("consume", "#f85149"),
                          ("overflow", "#ffa500"), ("empty", "#5a7a9a"),
                          ("wait", "#d29922")]:
            self.pc_log_box.tag_config(tag, foreground=col)

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب CPU Scheduling
    # ══════════════════════════════════════════════════════════════════════════
    def _build_scheduling_tab(self):
        f = self.sched_frame
        self._section_title(f, "📅 محاكاة جدولة المعالج (CPU Scheduling)")

        top = tk.Frame(f, bg="#060d1a")
        top.pack(fill="x", padx=10, pady=5)

        # جدول العمليات
        proc_f = tk.Frame(top, bg="#0d1526", width=400)
        proc_f.pack(side="right", fill="y", padx=(0, 10))
        proc_f.pack_propagate(False)
        self._section_title(proc_f, "العمليات")
        cols = ("pid", "arrival", "burst", "priority")
        self.proc_tree = self._make_treeview(proc_f, cols, {
            "pid": ("PID", 60), "arrival": ("وصول", 70), "burst": ("زمن CPU", 80), "priority": ("أولوية", 70)
        }, height=8)
        self.proc_tree.pack(fill="x", padx=8, pady=5)

        btn_f = tk.Frame(proc_f, bg="#0d1526")
        btn_f.pack(fill="x", padx=8)
        self._btn(btn_f, "➕ أضف", "#238636", self._add_process, size=9).pack(side="right", padx=2, fill="x", expand=True)
        self._btn(btn_f, "➖ احذف", "#b91c1c", self._delete_process, size=9).pack(side="right", padx=2, fill="x", expand=True)
        self._btn(btn_f, "🔄 إعادة", "#d29922", self._reset_processes, size=9).pack(side="right", padx=2, fill="x", expand=True)

        # اختيار الخوارزمية
        alg_f = tk.Frame(top, bg="#060d1a")
        alg_f.pack(side="left", fill="both", expand=True, pady=5)
        self._section_title(alg_f, "الخوارزمية")
        self.sched_alg = tk.StringVar(value="FCFS")
        for alg, col in [("FCFS", "#3fb950"), ("SJF", "#d29922"), ("RR", "#00e5c3")]:
            tk.Radiobutton(alg_f, text=alg, variable=self.sched_alg, value=alg,
                           bg="#060d1a", fg=col, selectcolor="#1a2a3a", activebackground="#060d1a",
                           font=("Arial", 12, "bold")).pack(anchor="e", padx=20, pady=3)

        quantum_f = tk.Frame(alg_f, bg="#060d1a")
        quantum_f.pack(fill="x", padx=15, pady=5)
        tk.Label(quantum_f, text="Quantum (RR):", fg="#8aa8c8", bg="#060d1a", font=("Arial", 10)).pack(side="right")
        self.rr_quantum = tk.IntVar(value=2)
        tk.Spinbox(quantum_f, from_=1, to=10, textvariable=self.rr_quantum,
                   bg="#1a2a3a", fg="white", width=4, font=("Arial", 11),
                   relief="flat", bd=4).pack(side="right", padx=6)

        self._btn(f, "▶ تشغيل الجدولة ورسم Gantt Chart", "#1f6feb",
                  self._run_scheduling, size=12).pack(fill="x", padx=10, pady=5)

        self.gantt_fig, (self.gantt_ax, self.stats_ax) = plt.subplots(
            1, 2, figsize=(13, 3.5), facecolor="#060d1a",
            gridspec_kw={'width_ratios': [3, 1]})
        for ax in (self.gantt_ax, self.stats_ax):
            ax.set_facecolor("#0d1526")
            ax.tick_params(colors="#c9d1d9")
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
        self.gantt_canvas = FigureCanvasTkAgg(self.gantt_fig, master=f)
        self.gantt_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

        self.sched_results_var = tk.StringVar(value="")
        tk.Label(f, textvariable=self.sched_results_var,
                 fg="#c9d1d9", bg="#060d1a", font=("Courier", 10), justify="right").pack(pady=3)

        self.processes = []
        self._reset_processes()

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب مراقبة الأداء
    # ══════════════════════════════════════════════════════════════════════════
    def _build_performance_tab(self):
        f = self.perf_frame
        self.perf_cpu_history = []
        self.perf_mem_history = []
        self.perf_time_history = []

        self.perf_fig, axes = plt.subplots(2, 2, figsize=(13, 6), facecolor="#060d1a")
        (self.ax_cpu, self.ax_mem), (self.ax_race_line, self.ax_race_bar) = axes
        for ax in [self.ax_cpu, self.ax_mem, self.ax_race_line, self.ax_race_bar]:
            ax.set_facecolor("#0d1526")
            ax.tick_params(colors="#c9d1d9", labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")

        self.ax_cpu.set_title("CPU% (Real-time)" + (" — psutil" if HAS_PSUTIL else " — N/A"), color="#c9d1d9", fontsize=9)
        self.ax_mem.set_title("RAM% (Real-time)" + (" — psutil" if HAS_PSUTIL else " — N/A"), color="#c9d1d9", fontsize=9)
        self.ax_race_line.set_title("تطور المخزون: Race vs Sync", color="#c9d1d9", fontsize=9)
        self.ax_race_bar.set_title("مقارنة النتائج النهائية", color="#c9d1d9", fontsize=9)

        self.perf_canvas = FigureCanvasTkAgg(self.perf_fig, master=f)
        self.perf_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

        self.perf_race_data = {}

        stats_panel = tk.Frame(f, bg="#0d1526")
        stats_panel.pack(fill="x", padx=10, pady=5)
        self.perf_stats_vars = {}
        items = [
            ("total_threads", "إجمالي الخيوط", "#00e5c3"),
            ("successful", "عمليات ناجحة", "#3fb950"),
            ("failed", "عمليات فاشلة", "#f85149"),
            ("corruptions", "تضاربات", "#d29922"),
        ]
        for i, (key, lbl, col) in enumerate(items):
            fr = tk.Frame(stats_panel, bg="#0d1526")
            fr.grid(row=0, column=i, padx=15, pady=8, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg="#0d1526", font=("Arial", 9, "bold")).pack()
            var = tk.StringVar(value="0")
            self.perf_stats_vars[key] = var
            tk.Label(fr, textvariable=var, fg=col, bg="#0d1526", font=("Arial", 18, "bold")).pack()
        for i in range(4):
            stats_panel.columnconfigure(i, weight=1)

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب Audit Log
    # ══════════════════════════════════════════════════════════════════════════
    def _build_audit_tab(self):
        f = self.audit_frame
        self._section_title(f, "📋 سجل المراجعة (Audit Log) — يوثّق كل عملية مع اسم Thread")

        btn_f = tk.Frame(f, bg="#060d1a")
        btn_f.pack(fill="x", padx=15, pady=5)
        self._btn(btn_f, "🔄 تحديث", "#1f6feb", self._refresh_audit, size=10).pack(side="right", padx=5)
        self._btn(btn_f, "🗑 مسح", "#b91c1c", self._clear_audit, size=10).pack(side="left", padx=5)

        cols = ("id", "thread", "action", "product", "old", "new", "timestamp", "mode")
        self.audit_tree = self._make_treeview(f, cols, {
            "id": ("ID", 40), "thread": ("Thread", 160), "action": ("العملية", 90),
            "product": ("المنتج", 70), "old": ("قبل", 50), "new": ("بعد", 50),
            "timestamp": ("الوقت", 160), "mode": ("وضع التزامن", 100),
        }, height=25)
        self.audit_tree.pack(fill="both", expand=True, padx=15, pady=5)
        self._refresh_audit()

    # ══════════════════════════════════════════════════════════════════════════
    # تبويب تعلّم OS التفاعلي
    # ══════════════════════════════════════════════════════════════════════════
    def _build_learn_tab(self):
        f = self.learn_frame

        tk.Label(f, text="📚 تعلّم مفاهيم نظام التشغيل تفاعلياً",
                 font=("Arial", 14, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(10, 5))
        tk.Label(f, text="كل مفهوم بشرح + محاكاة مصغّرة + تجربة مباشرة",
                 font=("Arial", 9), fg="#5a7a9a", bg="#060d1a").pack(pady=(0, 8))

        # منطقة البطاقات القابلة للتمرير
        canvas_outer = tk.Canvas(f, bg="#060d1a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(f, orient="vertical", command=canvas_outer.yview)
        canvas_outer.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")
        canvas_outer.pack(fill="both", expand=True)

        cards_frame = tk.Frame(canvas_outer, bg="#060d1a")
        _cards_win = canvas_outer.create_window((0, 0), window=cards_frame, anchor="nw")

        def update_scroll(event=None):
            canvas_outer.configure(scrollregion=canvas_outer.bbox("all"))
        cards_frame.bind("<Configure>", update_scroll)

        def _on_canvas_resize(event):
            canvas_outer.itemconfig(_cards_win, width=event.width)
        canvas_outer.bind("<Configure>", _on_canvas_resize)

        # ── دعم التمرير بعجلة الفأرة (Windows/Linux/Mac) ──
        def _on_mousewheel(event):
            if event.num == 4 or event.delta > 0:
                canvas_outer.yview_scroll(-2, "units")
            elif event.num == 5 or event.delta < 0:
                canvas_outer.yview_scroll(2, "units")

        def _bind_wheel(event):
            canvas_outer.bind_all("<MouseWheel>", _on_mousewheel)   # Windows / Mac
            canvas_outer.bind_all("<Button-4>", _on_mousewheel)     # Linux scroll up
            canvas_outer.bind_all("<Button-5>", _on_mousewheel)     # Linux scroll down

        def _unbind_wheel(event):
            canvas_outer.unbind_all("<MouseWheel>")
            canvas_outer.unbind_all("<Button-4>")
            canvas_outer.unbind_all("<Button-5>")

        # تفعيل التمرير فقط عندما الفأرة على هذا التبويب (لا يتعارض مع تبويبات أخرى)
        canvas_outer.bind("<Enter>", _bind_wheel)
        canvas_outer.bind("<Leave>", _unbind_wheel)

        # سجل نتائج التجارب
        self.learn_result_box = None

        concepts = [
            {
                "title": "🧵 Thread (خيط التنفيذ)",
                "color": "#1f6feb",
                "explanation":
                    "Thread هو وحدة تنفيذ مستقلة داخل نفس العملية (Process).\n"
                    "• يشارك Thread الذاكرة وموارد النظام مع باقي الخيوط\n"
                    "• أخف من Process بكثير — لا يحتاج نسخ ذاكرة\n"
                    "• Python threading: كل خيط يُشغَّل بدالة منفصلة\n"
                    "• في هذا البرنامج: كل عملية بيع = Thread في Pool",
                "experiment": "thread",
            },
            {
                "title": "🔒 Lock / Mutex (القفل)",
                "color": "#238636",
                "explanation":
                    "Lock (المقفل) هو آلية تمنع أكثر من خيط من تعديل مورد مشترك في آنٍ واحد.\n"
                    "• acquire(): يطلب الخيط القفل — إن كان حراً أخذه، وإلا انتظر\n"
                    "• release(): يُحرر الخيط القفل عند انتهائه\n"
                    "• Critical Section: القسم المحمي بالقفل — خيط واحد فيه في كل وقت\n"
                    "• بدون Lock → Race Condition | مع Lock → أمان تام",
                "experiment": "lock",
            },
            {
                "title": "🔁 RLock (القفل القابل لإعادة الدخول)",
                "color": "#9a7000",
                "explanation":
                    "RLock (Reentrant Lock) يسمح لنفس الخيط بالحصول عليه أكثر من مرة.\n"
                    "• مفيد في الدوال المتداخلة (recursive functions) التي تحتاج نفس القفل\n"
                    "• Lock العادي يتجمد إذا حاول نفس الخيط أخذه مرتين (Deadlock ذاتي!)\n"
                    "• RLock يحتفظ بعداد — يُحرر فقط عند وصول العداد لصفر\n"
                    "• في البرنامج: stock_rlock للعمليات المتداخلة",
                "experiment": "rlock",
            },
            {
                "title": "🚦 Semaphore (السيمافور)",
                "color": "#00e5c3",
                "explanation":
                    "Semaphore هو عداد يحدد عدد الخيوط المسموح لها بالدخول للمورد.\n"
                    "• acquire(): يُخفّض العداد — إن كان صفراً ينتظر\n"
                    "• release(): يرفع العداد — يُوقظ خيطاً منتظراً\n"
                    "• Semaphore(1) = Lock عادي (Mutex)\n"
                    "• Semaphore(3): يسمح لـ 3 خيوط بالوصول المتزامن",
                "experiment": "semaphore",
            },
            {
                "title": "☠ Deadlock (الإغلاق المتبادل)",
                "color": "#b91c1c",
                "explanation":
                    "Deadlock: حالة يتوقف فيها خيطان (أو أكثر) كل منهما ينتظر الآخر إلى الأبد.\n"
                    "• الشروط الأربعة: Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait\n"
                    "• Prevention: Resource Ordering — احصل على الموارد بترتيب ثابت دائماً\n"
                    "• Detection: مراقب يبحث عن دورات في مخطط الانتظار (DFS)\n"
                    "• Recovery: إنهاء أحد الخيوط أو سحب موارده",
                "experiment": "deadlock",
            },
            {
                "title": "⚡ Race Condition (تضارب البيانات)",
                "color": "#d29922",
                "explanation":
                    "Race Condition: عندما تعتمد نتيجة البرنامج على ترتيب تنفيذ الخيوط.\n"
                    "• يحدث في: قراءة-تعديل-كتابة بدون قفل\n"
                    "• مثال: خيطان يقرآن مخزون=10، كلاهما يبيع 3 → المخزون 7 بدل 4!\n"
                    "• يصعب اكتشافه لأنه غير منتظم\n"
                    "• الحل: Lock يحمي القسم الحرج من البداية للنهاية",
                "experiment": "race",
            },
            {
                "title": "🔄 Producer-Consumer",
                "color": "#a78bfa",
                "explanation":
                    "نمط تصميم كلاسيكي: خيوط تُنتج بيانات + خيوط تستهلكها.\n"
                    "• Queue المشتركة تعمل كـ Buffer بين المنتجين والمستهلكين\n"
                    "• Producer ينتظر إذا كانت Queue ممتلئة (Buffer Full)\n"
                    "• Consumer ينتظر إذا كانت Queue فارغة (Buffer Empty)\n"
                    "• في البرنامج: RestockScanner (P) → Queue → RestockProcessor (C)",
                "experiment": "producer_consumer",
            },
        ]

        # منطقة نتائج التجارب
        result_outer = tk.Frame(cards_frame, bg="#0a0a1a")
        result_outer.pack(fill="x", padx=10, pady=5)
        tk.Label(result_outer, text="📋 نتائج التجارب:", font=("Arial", 10, "bold"),
                 fg="#8aa8c8", bg="#0a0a1a").pack(anchor="e", padx=8, pady=3)
        self.learn_result_box = scrolledtext.ScrolledText(
            result_outer, height=5, bg="#030810", fg="#00e5c3",
            font=("Courier", 9), state="disabled", relief="flat")
        self.learn_result_box.pack(fill="x", padx=8, pady=(0, 5))
        for tag, col in [("info", "#00e5c3"), ("result", "#3fb950"),
                          ("warn", "#d29922"), ("race", "#f85149")]:
            self.learn_result_box.tag_config(tag, foreground=col)

        # بناء البطاقات
        for row_idx in range(0, len(concepts), 2):
            row_f = tk.Frame(cards_frame, bg="#060d1a")
            row_f.pack(fill="x", padx=10, pady=5)

            for col_idx in range(2):
                if row_idx + col_idx >= len(concepts):
                    break
                concept = concepts[row_idx + col_idx]
                self._build_learn_card(row_f, concept)

    def _build_learn_card(self, parent, concept):
        """بناء بطاقة تعليمية مع شرح ومحاكاة مصغّرة"""
        card = tk.Frame(parent, bg="#0d1526", bd=2, relief="groove")
        card.pack(side="left", fill="both", expand=True, padx=5, pady=3)

        # عنوان البطاقة
        tk.Label(card, text=concept["title"], font=("Arial", 11, "bold"),
                 fg=concept["color"], bg="#0d1526").pack(pady=(8, 3), padx=10)

        tk.Frame(card, bg=concept["color"], height=2).pack(fill="x", padx=10)

        # الشرح النصي
        explanation_box = scrolledtext.ScrolledText(card, height=6, bg="#030810", fg="#c9d1d9",
                                                     font=("Arial", 9), relief="flat", wrap="word",
                                                     state="normal")
        explanation_box.pack(fill="x", padx=10, pady=5)
        explanation_box.insert("1.0", concept["explanation"])
        explanation_box.config(state="disabled")

        # زر التجربة
        tk.Button(card, text=f"▶ شغّل التجربة",
                  font=("Arial", 10, "bold"), bg=concept["color"], fg="white",
                  relief="flat", cursor="hand2", pady=6,
                  command=lambda exp=concept["experiment"]: self._run_learn_experiment(exp)
                  ).pack(fill="x", padx=10, pady=(0, 8))

    def _run_learn_experiment(self, experiment_type):
        """تشغيل تجربة تعليمية مصغّرة"""
        def log_result(msg, tag="result"):
            if self.learn_result_box:
                self.learn_result_box.config(state="normal")
                self.learn_result_box.insert("end", f"[{experiment_type}] {msg}\n", tag)
                self.learn_result_box.see("end")
                self.learn_result_box.config(state="disabled")

        def run():
            log_result(f"=== تجربة {experiment_type} ===", "info")

            if experiment_type == "thread":
                # محاكاة بسيطة لـ 3 خيوط
                results = []
                lock = threading.Lock()

                def worker(tid):
                    time.sleep(random.uniform(0.05, 0.2))
                    with lock:
                        results.append(f"Thread-{tid} انتهى")

                threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                self.after(0, lambda: [log_result(r, "result") for r in results])
                self.after(0, lambda: log_result("✓ جميع الخيوط الـ 3 أنهت عملها", "result"))

            elif experiment_type == "lock":
                # إثبات Lock يمنع Race Condition
                counter_unsafe = {"v": 0}
                counter_safe = {"v": 0}
                lock = threading.Lock()

                def unsafe():
                    for _ in range(50):
                        v = counter_unsafe["v"]
                        time.sleep(0.0001)
                        counter_unsafe["v"] = v + 1

                def safe():
                    for _ in range(50):
                        with lock:
                            counter_safe["v"] += 1

                t_unsafe = [threading.Thread(target=unsafe) for _ in range(5)]
                t_safe = [threading.Thread(target=safe) for _ in range(5)]
                for t in t_unsafe: t.start()
                for t in t_unsafe: t.join()
                for t in t_safe: t.start()
                for t in t_safe: t.join()

                expected = 250
                self.after(0, lambda: log_result(
                    f"بدون Lock: {counter_unsafe['v']} (متوقع {expected}) "
                    f"{'⚡ تضارب!' if counter_unsafe['v'] != expected else '✓'}", "race"))
                self.after(0, lambda: log_result(
                    f"مع Lock: {counter_safe['v']} (متوقع {expected}) ✓ آمن", "result"))

            elif experiment_type == "rlock":
                rlock = threading.RLock()
                result = []

                def nested_op():
                    with rlock:  # أخذ القفل أول مرة
                        result.append("المستوى الأول: ✓ حصل على RLock")
                        with rlock:  # أخذ القفل ثانية — يعمل مع RLock!
                            result.append("المستوى الثاني: ✓ RLock يسمح بإعادة الدخول")
                    result.append("تحرير نهائي — العداد وصل صفر")

                t = threading.Thread(target=nested_op)
                t.start()
                t.join()
                self.after(0, lambda: [log_result(r, "result") for r in result])

            elif experiment_type == "semaphore":
                sem = threading.Semaphore(2)
                results = []
                lock = threading.Lock()

                def worker(tid):
                    with lock:
                        results.append(f"T{tid}: ينتظر Semaphore(2)...")
                    acquired = sem.acquire(timeout=1.0)
                    if acquired:
                        with lock:
                            results.append(f"T{tid}: ✓ دخل (عداد -1)")
                        time.sleep(0.15)
                        sem.release()
                        with lock:
                            results.append(f"T{tid}: خرج (عداد +1)")
                    else:
                        with lock:
                            results.append(f"T{tid}: ✗ انتهى الانتظار!")

                threads = [threading.Thread(target=worker, args=(i+1,)) for i in range(4)]
                for t in threads: t.start()
                for t in threads: t.join()
                time.sleep(0.1)
                self.after(0, lambda r=results[:]: [log_result(x, "result") for x in r])

            elif experiment_type == "deadlock":
                lock_a = threading.Lock()
                lock_b = threading.Lock()
                result = []

                def thread1_bad():
                    lock_a.acquire()
                    result.append("T1: أخذ Lock-A")
                    time.sleep(0.1)
                    acquired = lock_b.acquire(timeout=0.5)
                    if acquired:
                        result.append("T1: أخذ Lock-B")
                        lock_b.release()
                    else:
                        result.append("T1: ⚠ Deadlock! تعذّر أخذ Lock-B")
                    lock_a.release()

                def thread2_bad():
                    lock_b.acquire()
                    result.append("T2: أخذ Lock-B")
                    time.sleep(0.1)
                    acquired = lock_a.acquire(timeout=0.5)
                    if acquired:
                        result.append("T2: أخذ Lock-A")
                        lock_a.release()
                    else:
                        result.append("T2: ⚠ Deadlock! تعذّر أخذ Lock-A")
                    lock_b.release()

                t1 = threading.Thread(target=thread1_bad)
                t2 = threading.Thread(target=thread2_bad)
                t1.start()
                t2.start()
                t1.join()
                t2.join()
                result.append("← Resource Ordering الحل: دائماً A قبل B!")
                self.after(0, lambda r=result[:]: [log_result(x, "warn") for x in r])

            elif experiment_type == "race":
                stock = {"value": 10}
                races_detected = [0]
                lock = threading.Lock()

                def buy_without_lock(n):
                    v = stock["value"]
                    time.sleep(0.005)
                    stock["value"] = v - n
                    if stock["value"] < 0:
                        races_detected[0] += 1

                threads = [threading.Thread(target=buy_without_lock, args=(2,)) for _ in range(6)]
                for t in threads: t.start()
                for t in threads: t.join()

                self.after(0, lambda: log_result(
                    f"مخزون نهائي بدون Lock: {stock['value']} (كان 10، المتوقع -2) ⚡ تضارب!", "race"))
                self.after(0, lambda: log_result(
                    f"تضاربات مكتشفة: {races_detected[0]}", "race"))

            elif experiment_type == "producer_consumer":
                buf = queue.Queue(maxsize=3)
                results = []

                def producer():
                    for i in range(5):
                        try:
                            buf.put(f"منتج-{i}", timeout=0.5)
                            results.append(f"P: أضاف منتج-{i} | حجم Queue: {buf.qsize()}")
                            time.sleep(0.1)
                        except queue.Full:
                            results.append("P: ⚠ Queue ممتلئة! ينتظر...")

                def consumer():
                    for _ in range(5):
                        try:
                            item = buf.get(timeout=1.0)
                            results.append(f"C: استهلك {item} | حجم Queue: {buf.qsize()}")
                            time.sleep(0.2)
                        except queue.Empty:
                            results.append("C: ⏳ Queue فارغة! ينتظر...")

                p = threading.Thread(target=producer)
                c = threading.Thread(target=consumer)
                p.start(); c.start()
                p.join(); c.join()
                self.after(0, lambda r=results[:]: [log_result(x, "result") for x in r])

        threading.Thread(target=run, daemon=True, name=f"LearnExp-{experiment_type}").start()

    # ══════════════════════════════════════════════════════════════════════════
    # منطق البيع — Thread Pool مع Timed Lock وRLock
    # ══════════════════════════════════════════════════════════════════════════
    def _on_sync_change(self):
        global sync_mode
        sync_mode = self.sync_mode_var.get()
        labels = {0: "بدون تزامن ⚠", 1: "Mutex 🔒", 2: "Semaphore 🚦", 3: "RWLock 📖"}
        tags = {0: "race", 1: "sync", 2: "sem", 3: "rw"}
        self._log(f"وضع التزامن: {labels[sync_mode]}", tags[sync_mode])

    def _update_semaphore(self):
        global stock_semaphore
        limit = self.sem_limit_var.get()
        stock_semaphore = threading.Semaphore(limit)
        self._log(f"Semaphore محدَّث: {limit} خيوط", "sem")

    def _issue_invoice(self):
        """إصدار فاتورة عبر Thread Pool — يعيد استخدام الخيوط"""
        if not self.cart:
            messagebox.showwarning("تنبيه", "السلة فارغة!")
            return
        cname = self.cust_name.get().strip() or "زبون"
        cphone = self.cust_phone.get().strip()
        future = thread_pool.submit(self._process_sale, cname, cphone, dict(self.cart))
        self._log(f"[Pool] مهمة أُرسلت للThread Pool", "pool")
        future.add_done_callback(lambda f: self.after(0, self._on_sale_complete, f))

    def _on_sale_complete(self, future):
        if future.exception():
            self._log(f"[Pool] خطأ: {future.exception()}", "err")
        else:
            self.after(0, self._update_stats_display)

    def _process_sale(self, cname, cphone, cart_snapshot):
        """
        عملية البيع الأساسية — تعمل داخل Thread Pool Worker.
        يطبّق Thread Timeout (30 ثانية) عبر Future.
        يدعم Timed Lock: محاولة الحصول على القفل لمدة 5 ثوانٍ.
        يدعم RLock: للعمليات المتداخلة التي تحتاج نفس القفل.
        """
        global sync_mode
        tid = threading.current_thread().name
        self._log(f"[{tid}] بدأ تنفيذ عملية البيع", "sync")
        start_time = time.time()

        with stats_lock:
            race_stats["active_threads"][tid] = "RUNNING"
            race_stats["thread_wait_times"].setdefault(tid, 0.0)
            race_stats["thread_block_count"].setdefault(tid, 0)

        lock_acquired = False
        wait_start = time.time()

        try:
            # ── Thread Timeout: تحقق من انقضاء 30 ثانية ──
            if time.time() - start_time > THREAD_TIMEOUT_SEC:
                self._log(f"[{tid}] ✗ Thread Timeout! تجاوز {THREAD_TIMEOUT_SEC}ث", "err")
                return

            # ── اختيار آلية التزامن ──
            if sync_mode == 1:
                # Mutex: الأكثر أماناً — خيط واحد فقط
                # Timed Lock: محاولة لمدة 5 ثوانٍ ثم التخلي
                deadlock_detector.thread_waiting(tid, "stock_lock")
                self._log(f"[{tid}] ينتظر Mutex (Timed: 5ث)...", "sync")
                with stats_lock:
                    race_stats["active_threads"][tid] = "WAITING"

                # Timed Lock: acquire(timeout=5) بدلاً من الانتظار إلى الأبد
                lock_acquired = stock_lock.acquire(timeout=5.0)
                if not lock_acquired:
                    self._log(f"[{tid}] ✗ Timed Lock انتهى! القفل مشغول لأكثر من 5ث", "err")
                    return

                wait_time = time.time() - wait_start
                with stats_lock:
                    race_stats["thread_wait_times"][tid] += wait_time
                    race_stats["thread_block_count"][tid] += 1
                deadlock_detector.thread_acquired(tid, "stock_lock")
                self._log(f"[{tid}] ✓ Mutex (انتظر {wait_time:.2f}ث)", "sync")

            elif sync_mode == 2:
                # Semaphore: يسمح بعدد محدود من الخيوط
                self._log(f"[{tid}] ينتظر Semaphore...", "sem")
                with stats_lock:
                    race_stats["active_threads"][tid] = "WAITING"
                stock_semaphore.acquire()
                lock_acquired = True
                wait_time = time.time() - wait_start
                with stats_lock:
                    race_stats["thread_wait_times"][tid] += wait_time
                self._log(f"[{tid}] 🚦 Semaphore (انتظر {wait_time:.2f}ث)", "sem")

            elif sync_mode == 3:
                # RWLock: قفل الكتابة الحصري
                self._log(f"[{tid}] يطلب قفل الكتابة (RWLock)...", "rw")
                inventory_rwlock.acquire_write()
                lock_acquired = True
                self._log(f"[{tid}] ✓ قفل الكتابة RWLock", "rw")

            with stats_lock:
                race_stats["active_threads"][tid] = "RUNNING"

            # ── تنفيذ البيع ──
            total = 0.0
            items_desc = []

            for pid, info in cart_snapshot.items():
                qty = info["qty"]

                if sync_mode == 0:
                    time.sleep(random.uniform(0.05, 0.15))  # نافذة خطر التضارب

                conn = sqlite3.connect(DB_PATH, timeout=15)
                conn.execute("PRAGMA journal_mode=WAL")
                try:
                    conn.execute("BEGIN TRANSACTION")
                    c = conn.cursor()
                    c.execute("SELECT stock FROM products WHERE id=?", (pid,))
                    row = c.fetchone()
                    old_stock = row[0] if row else 0

                    if old_stock < qty:
                        with stats_lock:
                            race_stats["failed_ops"] += 1
                        conn.execute("ROLLBACK")
                        conn.close()
                        continue

                    if sync_mode == 0:
                        time.sleep(random.uniform(0.02, 0.08))

                    new_stock = old_stock - qty
                    c.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, pid))
                    conn.execute("COMMIT")

                    db_audit(tid, "SALE", pid, old_stock, new_stock,
                             ["NO_SYNC","MUTEX","SEM","RWLOCK"][sync_mode])

                    # تحقق من مخزون منخفض وأرسل إشعاراً
                    if new_stock < 5:
                        self.after(0, lambda n=info["name"], s=new_stock:
                            self.notif.show(f"⚠ مخزون منخفض: {n} ({s} وحدة)", "#d29922"))

                    with stats_lock:
                        race_stats["successful_ops"] += 1
                        race_stats["stock_history"].append(new_stock)

                    line_total = info["price"] * qty
                    total += line_total
                    items_desc.append(f"{info['name']} × {qty} @ {info['price']:.1f} = {line_total:.1f}")
                    self._log(f"[{tid}] {info['name']}: {old_stock} → {new_stock}", "info")

                except Exception as e:
                    conn.execute("ROLLBACK")
                    self._log(f"[{tid}] ✗ Rollback: {e}", "err")
                finally:
                    conn.close()

            # ── إنشاء الفاتورة ──
            if items_desc:
                inv_num = f"INV-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
                created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                items_str = "\n".join(items_desc)

                with invoice_lock:
                    conn = sqlite3.connect(DB_PATH, timeout=15)
                    conn.execute("PRAGMA journal_mode=WAL")
                    try:
                        conn.execute("BEGIN TRANSACTION")
                        conn.execute("""INSERT INTO invoices
                            (invoice_number, customer_name, customer_phone, total, created_at, items)
                            VALUES (?,?,?,?,?,?)""",
                            (inv_num, cname, cphone, total, created, items_str))
                        # ── مزامنة تلقائية مع invoice_payments ──
                        # كل فاتورة تُنشأ تُضاف فوراً لنظام المدفوعات بحالة 'unpaid'
                        conn.execute("""INSERT OR IGNORE INTO invoice_payments
                            (invoice_number, total_amount, paid_amount, status, created_at, last_updated)
                            VALUES (?, ?, 0, 'unpaid', ?, ?)""",
                            (inv_num, total, created, created))
                        conn.execute("COMMIT")
                        self._log(f"[{tid}] ✓ فاتورة {inv_num} | {total:.1f} ل.س", "info")
                    except Exception as e:
                        conn.execute("ROLLBACK")
                        self._log(f"[{tid}] فاتورة: Rollback ({e})", "err")
                    finally:
                        conn.close()

                self.after(0, lambda: self._post_sale_ui(inv_num, cname, cphone, total, items_str, created))

        finally:
            # ── تحرير القفل في جميع الأحوال ──
            if sync_mode == 1 and lock_acquired:
                stock_lock.release()
                deadlock_detector.thread_released(tid, "stock_lock")
                self._log(f"[{tid}] 🔓 Mutex محرَّر", "sync")
            elif sync_mode == 2 and lock_acquired:
                stock_semaphore.release()
                self._log(f"[{tid}] 🚦 Semaphore محرَّر", "sem")
            elif sync_mode == 3 and lock_acquired:
                inventory_rwlock.release_write()
                self._log(f"[{tid}] 📖 RWLock محرَّر", "rw")

            with stats_lock:
                race_stats["active_threads"][tid] = "DONE"
            self.after(0, self._update_stats_display)
            self.after(0, self._refresh_audit)

    def _post_sale_ui(self, inv_num, cname, cphone, total, items_str, created):
        self.cart.clear()
        self._refresh_cart()
        self._load_products_table()
        self._refresh_invoices()
        InvoicePopup(self, inv_num, cname, cphone, total, items_str, created)

    # ══════════════════════════════════════════════════════════════════════════
    # Race Condition — 5 سيناريوهات
    # ══════════════════════════════════════════════════════════════════════════
    def _run_race_scenario(self, scenario_id):
        t = threading.Thread(target=self._race_scenario_worker,
                             args=(scenario_id,), daemon=True,
                             name=f"RaceScenario-{scenario_id}")
        t.start()

    def _run_all_scenarios(self):
        def run_seq():
            for i in range(5):
                self._race_scenario_worker(i)
                time.sleep(0.3)
        threading.Thread(target=run_seq, daemon=True, name="AllScenarios").start()

    def _race_scenario_worker(self, scenario_id):
        """
        5 سيناريوهات Race Condition:
        0: بدون أي قفل        → Race Condition كلاسيكي
        1: مع Mutex            → حماية كاملة
        2: Semaphore(2)        → حماية جزئية
        3: RWLock              → تمييز قراءة/كتابة
        4: Barrier + Mutex     → المزامنة الجماعية قبل البدء
        """
        INITIAL = 20
        NUM_THREADS = 5
        OPS_PER = 4

        scenario_names = {
            0: "❌ بدون قفل — Race Condition",
            1: "✅ Mutex — آمن تماماً",
            2: "🟡 Semaphore(2) — آمن جزئياً",
            3: "✅ RWLock — قراءة/كتابة",
            4: "✅ Barrier + Mutex — تزامن جماعي",
        }

        shared = {"value": INITIAL}
        lock = threading.Lock()
        semaphore = threading.Semaphore(2)
        rwlock = RWLock()
        barrier = threading.Barrier(NUM_THREADS)
        history = []
        events = []

        def worker(tid):
            if scenario_id == 4:
                self.after(0, lambda t=tid: self._detail_log(f"[{t}] عند Barrier، ينتظر...", "warn"))
                try:
                    barrier.wait(timeout=5.0)
                except threading.BrokenBarrierError:
                    return
                self.after(0, lambda t=tid: self._detail_log(f"[{t}] Barrier انكسر — جميع الخيوط انطلقت!", "info"))

            for _ in range(OPS_PER):
                t_start = time.perf_counter()

                if scenario_id == 0:
                    v = shared["value"]
                    time.sleep(random.uniform(0.003, 0.015))
                    shared["value"] = v - 1
                elif scenario_id in (1, 4):
                    with lock:
                        v = shared["value"]
                        time.sleep(random.uniform(0.001, 0.004))
                        shared["value"] = v - 1
                elif scenario_id == 2:
                    with semaphore:
                        v = shared["value"]
                        time.sleep(random.uniform(0.002, 0.008))
                        shared["value"] = v - 1
                elif scenario_id == 3:
                    rwlock.acquire_write()
                    try:
                        v = shared["value"]
                        time.sleep(random.uniform(0.001, 0.005))
                        shared["value"] = v - 1
                    finally:
                        rwlock.release_write()

                elapsed = time.perf_counter() - t_start
                with stats_lock:
                    history.append(shared["value"])
                    events.append({
                        "thread": tid, "value": shared["value"],
                        "time": time.time(), "duration": elapsed
                    })

        threads = [
            threading.Thread(target=worker, args=(f"T{i+1}",),
                             name=f"Race-S{scenario_id}-T{i+1}")
            for i in range(NUM_THREADS)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = shared["value"]
        expected = 0
        corrupted = final != expected

        def show():
            name = scenario_names[scenario_id]
            self._detail_log(f"\n{'═'*55}", "info")
            self._detail_log(f"السيناريو {scenario_id}: {name}", "scenario")
            self._detail_log(f"الخيوط: {NUM_THREADS} × {OPS_PER} = {NUM_THREADS*OPS_PER} إجمالاً", "info")
            self._detail_log(f"الأولي: {INITIAL} | المتوقع: {expected} | الفعلي: {final}", "info")

            if corrupted:
                diff = abs(final - expected)
                pct = (diff / INITIAL) * 100
                self._detail_log(f"⚡ RACE CONDITION! فساد بمقدار {diff} ({pct:.1f}%)", "race")
                with stats_lock:
                    race_stats["corruption_count"] += 1
                self.corruption_var.set(str(race_stats["corruption_count"]))
                self.corruption_pct_var.set(f"نسبة الفساد: {pct:.1f}%")
                self.notif.show(f"⚡ Race Condition! السيناريو {scenario_id}: فساد {pct:.1f}%", "#f85149")
            else:
                self._detail_log(f"✓ البيانات سليمة — {name.split(' ')[1]} يعمل صحيح", "safe")

            with stats_lock:
                race_stats["successful_ops"] += NUM_THREADS * OPS_PER
            self.success_var.set(str(race_stats["successful_ops"]))

            self._draw_race_timeline(events, scenario_id)
            self.perf_race_data[scenario_id] = {
                "history": history[:],
                "final": final,
                "name": name,
                "corrupted": corrupted
            }
            self._update_perf_charts()

        self.after(0, show)

    def _draw_race_timeline(self, events, scenario_id):
        if not events:
            return
        colors = {0: "#f85149", 1: "#3fb950", 2: "#d29922", 3: "#00e5c3", 4: "#a78bfa"}
        col = colors.get(scenario_id, "#8aa8c8")
        ax = self.timeline_ax
        ax.clear()
        ax.set_facecolor("#0d1526")
        ax.set_title(f"Timeline — السيناريو {scenario_id}", color="#c9d1d9", fontsize=9)
        ax.tick_params(colors="#c9d1d9", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#1a2a3a")

        times = list(range(len(events)))
        values = [e["value"] for e in events]
        threads = [e["thread"] for e in events]
        thread_colors = {"T1": "#f85149", "T2": "#3fb950", "T3": "#d29922",
                         "T4": "#00e5c3", "T5": "#a78bfa"}
        for i, (t, v) in enumerate(zip(times, values)):
            tc = thread_colors.get(threads[i], "#8aa8c8")
            ax.bar(t, 1, bottom=v, color=tc, alpha=0.7, width=0.8)
        ax.step(times, values, color=col, linewidth=1.5, where="post")
        ax.axhline(y=0, color="#666", linestyle="--", alpha=0.5)
        ax.set_ylabel("قيمة المورد", color="#8aa8c8", fontsize=8)
        for i in range(1, len(values)):
            if abs(values[i] - values[i-1]) > 1:
                ax.annotate("⚡", xy=(i, values[i]), fontsize=12, color="#f85149",
                            ha="center", va="bottom")
        self.timeline_canvas.draw()

    # ══════════════════════════════════════════════════════════════════════════
    # Producer-Consumer
    # ══════════════════════════════════════════════════════════════════════════
    def _start_pc(self):
        if self.pc_running:
            return
        self.pc_running = True
        self.pc_produced = 0
        self.pc_consumed = 0
        self.pc_overflow = 0
        self.pc_priority_queue = PriorityQueue(maxsize=15)
        self.pc_history = []

        products = ["خبز🥖", "حليب🥛", "تفاح🍎", "أرز🍚", "زيت🫙",
                    "شاي☕", "موز🍌", "ماء💧", "دجاج🍗", "قهوة☕"]
        num_p = self.pc_num_producers.get()
        num_c = self.pc_num_consumers.get()

        self._pc_log(f"▶ تشغيل: {num_p} Producers + {num_c} Consumers", "produce")

        self.pc_producers = []
        for i in range(num_p):
            # كل Producer خيط مستقل مسؤوله: إنتاج منتجات ووضعها في Priority Queue
            t = threading.Thread(target=self._producer_worker,
                                 args=(i+1, products), daemon=True, name=f"Producer-{i+1}")
            t.start()
            self.pc_producers.append(t)

        self.pc_consumers = []
        for i in range(num_c):
            # كل Consumer خيط مستقل مسؤوله: أخذ العنصر ذو الأولوية الأعلى من Queue
            t = threading.Thread(target=self._consumer_worker,
                                 args=(i+1,), daemon=True, name=f"Consumer-{i+1}")
            t.start()
            self.pc_consumers.append(t)

        self._pc_update_canvas()
        self._pc_update_chart()

    def _stop_pc(self):
        self.pc_running = False
        self._pc_log("⏹ إيقاف النموذج", "wait")

    def _producer_worker(self, pid, products):
        """Producer: ينتج منتجات ويضعها في Priority Queue"""
        while self.pc_running:
            product = random.choice(products)
            priority = random.randint(1, 5)
            try:
                self.pc_priority_queue.put(product, priority=priority, timeout=1.5)
                self.pc_produced += 1
                qsize = self.pc_priority_queue.qsize()
                self.after(0, lambda p=product, pr=priority, q=qsize:
                    self._pc_log(f"[P{pid}] 📦 أضاف '{p}' (أولوية {pr}) | Queue: {q}/15", "produce"))
                self.after(0, self._update_pc_stats)
                if qsize >= 12:
                    self.after(0, lambda q=qsize:
                        self._pc_log(f"⚠ Buffer شبه ممتلئ! ({q}/15)", "overflow"))
            except queue.Full:
                self.pc_overflow += 1
                self.after(0, lambda:
                    self._pc_log(f"[P{pid}] 💥 Buffer Overflow! Queue ممتلئة!", "overflow"))
                self.after(0, self._update_pc_stats)
            time.sleep(self.pc_prod_speed.get())

    def _consumer_worker(self, cid):
        """Consumer: يأخذ أعلى أولوية من Priority Queue"""
        while self.pc_running:
            try:
                item = self.pc_priority_queue.get(timeout=2.0)
                self.pc_consumed += 1
                qsize = self.pc_priority_queue.qsize()
                self.after(0, lambda p=item.item, pr=item.priority, q=qsize:
                    self._pc_log(f"[C{cid}] 🛒 استهلك '{p}' (أولوية {pr}) | Queue: {q}/15", "consume"))
                self.after(0, self._update_pc_stats)
            except queue.Empty:
                self.after(0, lambda:
                    self._pc_log(f"[C{cid}] ⏳ Queue فارغة، ينتظر...", "empty"))
            time.sleep(self.pc_cons_speed.get())

    def _update_pc_stats(self):
        self.pc_produced_var.set(str(self.pc_produced))
        self.pc_consumed_var.set(str(self.pc_consumed))
        self.pc_overflow_var.set(str(self.pc_overflow))
        self.pc_history.append(self.pc_priority_queue.qsize())
        if len(self.pc_history) > 60:
            self.pc_history = self.pc_history[-60:]

    def _pc_update_canvas(self):
        if not self.pc_running:
            return
        c = self.pc_canvas
        c.delete("all")
        w, h = 380, 200
        c.create_rectangle(0, 0, w, h, fill="#030810")
        CAPACITY = 15
        size = self.pc_priority_queue.qsize()
        box_w, box_h, start_x, start_y = 22, 28, 8, 80
        c.create_text(w//2, 18, text="📦 Priority Queue المشتركة",
                      fill="#8aa8c8", font=("Arial", 10, "bold"))
        c.create_text(w//2, 38, text=f"({size}/{CAPACITY} عناصر)",
                      fill="#d29922", font=("Arial", 9))
        for i in range(CAPACITY):
            x = start_x + i * (box_w + 2)
            filled = i < size
            color = "#238636" if filled else "#1a2a3a"
            outline = "#3fb950" if filled else "#30363d"
            c.create_rectangle(x, start_y, x+box_w, start_y+box_h,
                                fill=color, outline=outline, width=2)
        bar_w = int((size / CAPACITY) * (w - 20))
        color = "#f85149" if size >= 12 else ("#d29922" if size >= 8 else "#3fb950")
        c.create_rectangle(10, 130, w-10, 148, fill="#1a2a3a", outline="#30363d")
        if bar_w > 0:
            c.create_rectangle(10, 130, 10+bar_w, 148, fill=color)
        c.create_text(w//2, 139, text=f"{size*100//CAPACITY}% ممتلئة",
                      fill="white", font=("Arial", 8))
        num_p = len([t for t in self.pc_producers if t.is_alive()])
        num_c = len([t for t in self.pc_consumers if t.is_alive()])
        c.create_text(50, 168, text=f"Producers ({num_p})", fill="#3fb950", font=("Arial", 9, "bold"))
        c.create_text(320, 168, text=f"Consumers ({num_c})", fill="#f85149", font=("Arial", 9, "bold"))
        c.create_text(w//2, 185, text="→ أعلى أولوية تُعالَج أولاً ←", fill="#a78bfa", font=("Arial", 8))
        if self.pc_running:
            self.after(250, self._pc_update_canvas)

    def _pc_update_chart(self):
        if not self.pc_running:
            return
        ax = self.pc_ax
        ax.clear()
        ax.set_facecolor("#0d1526")
        ax.set_title("Queue Size عبر الزمن", color="#c9d1d9", fontsize=9)
        ax.tick_params(colors="#c9d1d9", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#1a2a3a")
        if self.pc_history:
            xs = list(range(len(self.pc_history)))
            ax.fill_between(xs, self.pc_history, color="#3fb950", alpha=0.3)
            ax.plot(xs, self.pc_history, color="#3fb950", linewidth=1.5)
            ax.axhline(y=15, color="#f85149", linestyle="--", alpha=0.5, label="حد Buffer")
            ax.set_ylim(0, 17)
            ax.legend(facecolor="#0d1526", labelcolor="#c9d1d9", fontsize=7)
        self.pc_chart_canvas.draw()
        if self.pc_running:
            self.after(500, self._pc_update_chart)

    def _pc_log(self, msg, tag="produce"):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.pc_log_box.config(state="normal")
        self.pc_log_box.insert("end", f"[{now}] {msg}\n", tag)
        self.pc_log_box.see("end")
        self.pc_log_box.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # CPU Scheduling
    # ══════════════════════════════════════════════════════════════════════════
    def _add_process(self):
        pid = f"P{len(self.processes)+1}"
        arrival = random.randint(0, 5)
        burst = random.randint(1, 10)
        priority = random.randint(1, 5)
        self.processes.append({"pid": pid, "arrival": arrival, "burst": burst, "priority": priority})
        self.proc_tree.insert("", "end", values=(pid, arrival, burst, priority))

    def _delete_process(self):
        sel = self.proc_tree.selection()
        if not sel:
            return
        idx = self.proc_tree.index(sel[0])
        self.proc_tree.delete(sel[0])
        if 0 <= idx < len(self.processes):
            self.processes.pop(idx)

    def _reset_processes(self):
        for row in self.proc_tree.get_children():
            self.proc_tree.delete(row)
        self.processes = [
            {"pid": "P1", "arrival": 0, "burst": 6, "priority": 3},
            {"pid": "P2", "arrival": 1, "burst": 4, "priority": 1},
            {"pid": "P3", "arrival": 2, "burst": 8, "priority": 4},
            {"pid": "P4", "arrival": 3, "burst": 2, "priority": 2},
            {"pid": "P5", "arrival": 4, "burst": 5, "priority": 5},
        ]
        for p in self.processes:
            self.proc_tree.insert("", "end", values=(p["pid"], p["arrival"], p["burst"], p["priority"]))

    def _run_scheduling(self):
        if not self.processes:
            messagebox.showwarning("تنبيه", "أضف عمليات أولاً!")
            return
        alg = self.sched_alg.get()
        procs = [dict(p) for p in self.processes]
        if alg == "FCFS":
            schedule, stats = self._fcfs(procs)
        elif alg == "SJF":
            schedule, stats = self._sjf(procs)
        else:
            schedule, stats = self._round_robin(procs, self.rr_quantum.get())
        self._draw_gantt(schedule, alg, stats)

    def _fcfs(self, procs):
        """FCFS: First Come First Served — يُنفَّذ حسب وقت الوصول"""
        procs = sorted(procs, key=lambda p: p["arrival"])
        time_now = 0
        schedule = []
        for p in procs:
            start = max(time_now, p["arrival"])
            end = start + p["burst"]
            schedule.append({"pid": p["pid"], "start": start, "end": end, "burst": p["burst"]})
            p["finish"] = end
            p["waiting"] = start - p["arrival"]
            p["turnaround"] = end - p["arrival"]
            time_now = end
        return schedule, procs

    def _sjf(self, procs):
        """SJF: Shortest Job First — تُنفَّذ أقصر مهمة متاحة"""
        procs = sorted(procs, key=lambda p: p["arrival"])
        time_now = 0
        schedule = []
        remaining = list(procs)
        while remaining:
            available = [p for p in remaining if p["arrival"] <= time_now]
            if not available:
                time_now = remaining[0]["arrival"]
                continue
            p = min(available, key=lambda x: x["burst"])
            remaining.remove(p)
            start = time_now
            end = start + p["burst"]
            schedule.append({"pid": p["pid"], "start": start, "end": end, "burst": p["burst"]})
            p["finish"] = end
            p["waiting"] = start - p["arrival"]
            p["turnaround"] = end - p["arrival"]
            time_now = end
        return schedule, procs

    def _round_robin(self, procs, quantum):
        """Round Robin: كل عملية تحصل على حصة زمنية ثابتة (Quantum)"""
        procs = sorted(procs, key=lambda p: p["arrival"])
        time_now = 0
        schedule = []
        remaining = {p["pid"]: p["burst"] for p in procs}
        arrivals = {p["pid"]: p["arrival"] for p in procs}
        finish = {}
        q = collections.deque()
        for p in procs:
            if p["arrival"] == 0:
                q.append(p["pid"])
        added = set(pid for pid in q)
        proc_map = {p["pid"]: p for p in procs}

        while q or any(remaining[pid] > 0 for pid in remaining):
            if not q:
                pending = [(arrivals[pid], pid) for pid in remaining if remaining[pid] > 0 and pid not in added]
                if not pending:
                    break
                time_now = min(pending)[0]
            if not q:
                for p in procs:
                    if p["arrival"] <= time_now and p["pid"] not in added and remaining[p["pid"]] > 0:
                        q.append(p["pid"])
                        added.add(p["pid"])
            if not q:
                break

            pid = q.popleft()
            if remaining[pid] <= 0:
                continue
            run = min(quantum, remaining[pid])
            schedule.append({"pid": pid, "start": time_now, "end": time_now + run, "burst": run})
            time_now += run
            remaining[pid] -= run

            for p in procs:
                if arrivals[p["pid"]] <= time_now and p["pid"] not in added:
                    q.append(p["pid"])
                    added.add(p["pid"])

            if remaining[pid] > 0:
                q.append(pid)
            else:
                finish[pid] = time_now
                proc_map[pid]["finish"] = time_now
                proc_map[pid]["turnaround"] = time_now - arrivals[pid]
                proc_map[pid]["waiting"] = proc_map[pid]["turnaround"] - proc_map[pid]["burst"]

        return schedule, procs

    def _draw_gantt(self, schedule, alg_name, stats):
        colors = {}
        palette = ["#1f6feb", "#238636", "#b91c1c", "#d29922", "#a78bfa",
                   "#00e5c3", "#f85149", "#3fb950", "#ffa500", "#60a5fa"]
        pids = list(dict.fromkeys(s["pid"] for s in schedule))
        for i, pid in enumerate(pids):
            colors[pid] = palette[i % len(palette)]

        ax = self.gantt_ax
        ax.clear()
        ax.set_facecolor("#0d1526")
        ax.set_title(f"Gantt Chart — {alg_name}", color="#c9d1d9", fontsize=10)
        ax.tick_params(colors="#c9d1d9")
        for sp in ax.spines.values():
            sp.set_color("#1a2a3a")

        for seg in schedule:
            pid = seg["pid"]
            col = colors.get(pid, "#8aa8c8")
            ax.barh(0, seg["end"] - seg["start"], left=seg["start"],
                    height=0.6, color=col, edgecolor="#060d1a", linewidth=1.5)
            mid = seg["start"] + (seg["end"] - seg["start"]) / 2
            ax.text(mid, 0, pid, ha="center", va="center",
                    color="white", fontsize=9, fontweight="bold")

        ax.set_yticks([])
        ax.set_xlabel("الزمن", color="#c9d1d9", fontsize=9)
        patches = [mpatches.Patch(color=colors[pid], label=pid) for pid in pids]
        ax.legend(handles=patches, facecolor="#0d1526", labelcolor="#c9d1d9",
                  fontsize=8, loc="upper right")

        ax2 = self.stats_ax
        ax2.clear()
        ax2.set_facecolor("#0d1526")
        ax2.set_title("إحصائيات", color="#c9d1d9", fontsize=9)
        ax2.tick_params(colors="#c9d1d9", labelsize=8)
        for sp in ax2.spines.values():
            sp.set_color("#1a2a3a")

        valid = [p for p in stats if "waiting" in p]
        if valid:
            pids2 = [p["pid"] for p in valid]
            waits = [p["waiting"] for p in valid]
            ax2.barh(pids2, waits, color="#1f6feb")
            ax2.set_xlabel("انتظار", color="#c9d1d9", fontsize=8)

        avg_wait = sum(p.get("waiting", 0) for p in valid) / max(len(valid), 1)
        avg_ta = sum(p.get("turnaround", 0) for p in valid) / max(len(valid), 1)
        self.sched_results_var.set(
            f"[{alg_name}]  متوسط الانتظار: {avg_wait:.2f}  |  متوسط Turnaround: {avg_ta:.2f}")

        try:
            self.gantt_fig.tight_layout()
            self.gantt_canvas.draw()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # مراقبة الأداء
    # ══════════════════════════════════════════════════════════════════════════
    def _schedule_perf_monitor(self):
        self._update_perf_monitor()
        self.after(2000, self._schedule_perf_monitor)

    def _update_perf_monitor(self):
        try:
            if HAS_PSUTIL:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
            else:
                cpu = random.uniform(10, 40)
                mem = random.uniform(30, 60)

            self.perf_cpu_history.append(cpu)
            self.perf_mem_history.append(mem)
            self.perf_time_history.append(len(self.perf_cpu_history))

            if len(self.perf_cpu_history) > 50:
                self.perf_cpu_history.pop(0)
                self.perf_mem_history.pop(0)
                self.perf_time_history.pop(0)

            self._update_perf_charts()
        except Exception:
            pass

    def _update_perf_charts(self):
        try:
            xs = self.perf_time_history or list(range(len(self.perf_cpu_history)))

            for ax, history, col, title in [
                (self.ax_cpu, self.perf_cpu_history, "#3fb950", "CPU%"),
                (self.ax_mem, self.perf_mem_history, "#1f6feb", "RAM%"),
            ]:
                ax.clear()
                ax.set_facecolor("#0d1526")
                ax.set_title(title + (" (psutil)" if HAS_PSUTIL else " (sim)"), color="#c9d1d9", fontsize=9)
                ax.tick_params(colors="#c9d1d9", labelsize=7)
                for sp in ax.spines.values():
                    sp.set_color("#1a2a3a")
                if history:
                    ax.fill_between(xs[-len(history):], history, color=col, alpha=0.3)
                    ax.plot(xs[-len(history):], history, color=col, linewidth=1.5)
                    ax.set_ylim(0, 100)

            clrs = {0: "#f85149", 1: "#3fb950", 2: "#d29922", 3: "#00e5c3", 4: "#a78bfa"}

            ax = self.ax_race_line
            ax.clear()
            ax.set_facecolor("#0d1526")
            ax.set_title("تطور المخزون: Race vs Sync", color="#c9d1d9", fontsize=9)
            ax.tick_params(colors="#c9d1d9", labelsize=7)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
            for k, data in self.perf_race_data.items():
                col = clrs.get(k, "#8aa8c8")
                ax.plot(data["history"], color=col, linewidth=1.5,
                        label=data["name"][:15], alpha=0.8)
            if self.perf_race_data:
                ax.legend(facecolor="#0d1526", labelcolor="#c9d1d9", fontsize=7)

            ax = self.ax_race_bar
            ax.clear()
            ax.set_facecolor("#0d1526")
            ax.set_title("مقارنة النتائج النهائية", color="#c9d1d9", fontsize=9)
            ax.tick_params(colors="#c9d1d9", labelsize=7)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
            if self.perf_race_data:
                labels = [f"S{k}" for k in self.perf_race_data]
                finals = [self.perf_race_data[k]["final"] for k in self.perf_race_data]
                bar_colors = [clrs.get(k, "#8aa8c8") for k in self.perf_race_data]
                bars = ax.bar(labels, finals, color=bar_colors)
                ax.axhline(y=0, color="#666", linestyle="--", alpha=0.5)
                for bar, val in zip(bars, finals):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                            str(val), ha="center", va="bottom", color="#c9d1d9", fontsize=9)

            self.perf_fig.tight_layout()
            self.perf_canvas.draw()
        except Exception:
            pass

        self._update_stats_display()

    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    # مراقبة الفواتير المتأخرة — Daemon Thread يعمل كل 60 ثانية
    # ══════════════════════════════════════════════════════════════════════════
    def _overdue_invoice_monitor(self):
        """
        خيط Daemon يفحص كل 60 ثانية وجود فواتير تجاوزت 7 أيام بدون دفع كامل.
        يُرسل إشعاراً تلقائياً عند اكتشاف فاتورة متأخرة.
        اسم الخيط: OverdueInvoiceMonitor
        نوع القفل: بدون — عملية قراءة فقط بدون تعديل
        """
        while not global_stop_event.is_set():
            try:
                # حساب تاريخ ما قبل 7 أيام
                cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)
                          ).strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect(DB_PATH, timeout=5)
                conn.execute("PRAGMA journal_mode=WAL")
                c = conn.cursor()
                c.execute("""SELECT invoice_number, total_amount, paid_amount, created_at
                             FROM invoice_payments
                             WHERE status != 'paid' AND created_at <= ?""", (cutoff,))
                rows = c.fetchall()
                conn.close()
                for inv_num, total, paid, created in rows:
                    remaining = total - paid
                    msg = (f"⏰ فاتورة متأخرة: {inv_num} | "
                           f"متبقٍّ {remaining:.2f} ل.س | "
                           f"منذ {created[:10]}")
                    self.after(0, lambda m=msg: self.notif.show(m, "#d29922", duration=7000))
            except Exception:
                pass
            # انتظر 60 ثانية أو حتى إيقاف البرنامج
            global_stop_event.wait(timeout=60)

    # مراقبة Deadlock
    # ══════════════════════════════════════════════════════════════════════════
    def _on_deadlock(self, graph):
        msg = f"⚠ Deadlock محتمل! الخيوط: {list(graph.keys())}"
        self._deadlock_history.append({
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Threads: {list(graph.keys())} — Graph: {graph}",
        })
        self.after(0, lambda: self.deadlock_var.set(msg))
        self.after(0, lambda: self._log(msg, "err"))
        self.after(0, lambda: self.notif.show(f"☠ {msg}", "#f85149", duration=6000))
        self.after(5000, lambda: self.deadlock_var.set(""))

    # ══════════════════════════════════════════════════════════════════════════
    # تصدير تقرير PDF شامل (reports.py)
    # ══════════════════════════════════════════════════════════════════════════
    def _export_pdf_report(self):
        """
        يُولِّد تقرير PDF شامل يحتوي على:
        إحصائيات الخيوط، Race Conditions، مقارنة الأداء قبل/بعد المزامنة،
        سجل Deadlock، وملخص Audit Log.
        يعمل في خيط مستقل حتى لا تتجمّد الواجهة أثناء التوليد.
        """
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "مكتبة مفقودة",
                "مكتبة reportlab غير مثبّتة على هذا النظام.\n"
                "ثبّتها بالأمر:\n\npip install reportlab"
            )
            return

        default_name = f"supermarket_os2_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        save_path = filedialog.asksaveasfilename(
            title="حفظ تقرير PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not save_path:
            return  # المستخدم ألغى

        self._log("[تقرير PDF] ⏳ جارٍ توليد التقرير...", "info")

        # جمع بيانات نتائج سيناريوهات Race (إن وُجدت من تبويب الأداء)
        perf_data = getattr(self, "perf_race_data", {})
        deadlock_hist = getattr(self, "_deadlock_history", [])

        def worker():
            ok, result = generate_pdf_report(
                save_path,
                race_stats=race_stats,
                perf_race_data=perf_data,
                deadlock_history=deadlock_hist,
                username=self.username,
            )
            self.after(0, lambda: self._on_pdf_export_done(ok, result))

        threading.Thread(target=worker, daemon=True, name="PDFReportExporter").start()

    def _on_pdf_export_done(self, ok, result):
        if ok:
            self._log(f"[تقرير PDF] ✅ تم الحفظ: {result}", "ok")
            self.notif.show("✅ تم تصدير تقرير PDF بنجاح", "#3fb950")
            if messagebox.askyesno("تم التصدير", f"تم حفظ التقرير في:\n{result}\n\nفتح الملف الآن؟"):
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(result)
                    elif sys.platform == "darwin":
                        os.system(f'open "{result}"')
                    else:
                        os.system(f'xdg-open "{result}"')
                except Exception as e:
                    self._log(f"[تقرير PDF] ✗ تعذّر فتح الملف: {e}", "err")
        else:
            self._log(f"[تقرير PDF] ✗ فشل: {result}", "err")
            messagebox.showerror("فشل التصدير", str(result))

    # ══════════════════════════════════════════════════════════════════════════
    # Audit Log
    # ══════════════════════════════════════════════════════════════════════════
    def _refresh_audit(self):
        for row in self.audit_tree.get_children():
            self.audit_tree.delete(row)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()
            c.execute("""SELECT a.id, a.thread_name, a.action, p.name,
                         a.old_value, a.new_value, a.timestamp, a.sync_mode
                         FROM audit_log a
                         LEFT JOIN products p ON a.product_id = p.id
                         ORDER BY a.id DESC LIMIT 200""")
            for row in c.fetchall():
                self.audit_tree.insert("", "end", values=row)
            conn.close()
        except Exception:
            pass

    def _clear_audit(self):
        if messagebox.askyesno("تأكيد", "مسح سجل المراجعة؟"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM audit_log")
            conn.commit()
            conn.close()
            self._refresh_audit()

    # ══════════════════════════════════════════════════════════════════════════
    # Thread Monitor الدوري
    # ══════════════════════════════════════════════════════════════════════════
    def _schedule_thread_monitor(self):
        count = threading.active_count()
        names = [t.name for t in threading.enumerate()
                 if any(kw in t.name for kw in ["Pool", "Sale", "Producer", "Consumer", "Cashier"])][:3]
        self.thread_status_var.set(f"الخيوط: {count} | {' • '.join(names)}")
        self.after(500, self._schedule_thread_monitor)

    def _update_stats_display(self):
        with stats_lock:
            self.perf_stats_vars["total_threads"].set(str(len(race_stats["active_threads"])))
            self.perf_stats_vars["successful"].set(str(race_stats["successful_ops"]))
            self.perf_stats_vars["failed"].set(str(race_stats["failed_ops"]))
            self.perf_stats_vars["corruptions"].set(str(race_stats["corruption_count"]))

    # ══════════════════════════════════════════════════════════════════════════
    # أدوات مساعدة للواجهة
    # ══════════════════════════════════════════════════════════════════════════
    def _make_treeview(self, parent, cols, headers_widths, height=10):
        style = ttk.Style()
        style.configure("Treeview", background="#1a2a3a", foreground="#c9d1d9",
                        fieldbackground="#1a2a3a", font=("Arial", 10), rowheight=26)
        style.configure("Treeview.Heading", background="#0d1a2a", foreground="#00e5c3",
                        font=("Arial", 10, "bold"))
        style.map("Treeview", background=[("selected", "#1f6feb")])
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=height)
        for c in cols:
            lbl, w = headers_widths[c]
            tv.heading(c, text=lbl)
            tv.column(c, width=w, anchor="center")
        return tv

    def _btn(self, parent, text, color, cmd, size=11):
        return tk.Button(parent, text=text, font=("Arial", size, "bold"),
                         bg=color, fg="white", activebackground=color,
                         relief="flat", bd=0, pady=8, cursor="hand2", command=cmd)

    def _section_title(self, parent, text):
        bg = "#060d1a"
        try:
            bg = parent.cget("bg")
        except Exception:
            pass
        tk.Label(parent, text=text, font=("Arial", 12, "bold"),
                 fg="#c9d1d9", bg=bg).pack(pady=(8, 4))

    def _load_products_table(self):
        for row in self.prod_tree.get_children():
            self.prod_tree.delete(row)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, name, price, stock FROM products ORDER BY id")
        for row in c.fetchall():
            tag = "low" if row[3] < 10 else ""
            self.prod_tree.insert("", "end", values=row, tags=(tag,))
        self.prod_tree.tag_configure("low", foreground="#f85149")
        conn.close()

    def _filter_products(self, *args):
        q = self.search_var.get().strip()
        for row in self.prod_tree.get_children():
            self.prod_tree.delete(row)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, name, price, stock FROM products WHERE name LIKE ?", (f"%{q}%",))
        for row in c.fetchall():
            self.prod_tree.insert("", "end", values=row)
        conn.close()

    def _add_to_cart(self):
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر منتجاً")
            return
        vals = self.prod_tree.item(sel[0])["values"]
        pid, name, price, stock = int(vals[0]), vals[1], float(vals[2]), int(vals[3])
        if stock <= 0:
            messagebox.showwarning("تنبيه", "المنتج غير متوفر")
            return
        if pid in self.cart:
            self.cart[pid]["qty"] += 1
        else:
            self.cart[pid] = {"name": name, "price": price, "qty": 1}
        self._refresh_cart()

    def _remove_from_cart(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        vals = self.cart_tree.item(sel[0])["values"]
        for pid, info in list(self.cart.items()):
            if info["name"] == vals[0]:
                del self.cart[pid]
                break
        self._refresh_cart()

    def _refresh_cart(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        for pid, info in self.cart.items():
            total = info["price"] * info["qty"]
            self.cart_tree.insert("", "end", values=(
                info["name"], info["qty"], f'{info["price"]:.1f}', f'{total:.1f}'))

    def _log(self, msg, tag="info"):
        now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"[{now}] {msg}\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _detail_log(self, msg, tag="info"):
        self.race_detail_log.config(state="normal")
        self.race_detail_log.insert("end", msg + "\n", tag)
        self.race_detail_log.see("end")
        self.race_detail_log.config(state="disabled")

    def _clear_race_log(self):
        for box in [self.race_detail_log, self.thread_monitor_box]:
            box.config(state="normal")
            box.delete("1.0", "end")
            box.config(state="disabled")
        with stats_lock:
            race_stats["corruption_count"] = 0
            race_stats["successful_ops"] = 0
            race_stats["failed_ops"] = 0
            race_stats["active_threads"].clear()
        self.corruption_var.set("0")
        self.success_var.set("0")
        self.fail_var.set("0")
        self.corruption_pct_var.set("نسبة الفساد: 0.0%")

    def _refresh_invoices(self):
        for row in self.inv_tree.get_children():
            self.inv_tree.delete(row)
        q = self.inv_search.get().strip() if hasattr(self, "inv_search") else ""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if q:
            c.execute("""SELECT invoice_number, customer_name, customer_phone, created_at, total
                         FROM invoices WHERE invoice_number LIKE ? OR customer_name LIKE ?
                         ORDER BY id DESC""", (f"%{q}%", f"%{q}%"))
        else:
            c.execute("""SELECT invoice_number, customer_name, customer_phone, created_at, total
                         FROM invoices ORDER BY id DESC""")
        for row in c.fetchall():
            self.inv_tree.insert("", "end", values=(row[0], row[1], row[2], row[3], f"{row[4]:.1f}"))
        conn.close()

    def _show_invoice_detail(self, event=None):
        sel = self.inv_tree.selection()
        if not sel:
            return
        inv_num = self.inv_tree.item(sel[0])["values"][0]
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM invoices WHERE invoice_number=?", (inv_num,))
        row = c.fetchone()
        conn.close()
        if row:
            self.inv_detail.config(state="normal")
            self.inv_detail.delete("1.0", "end")
            detail = (
                f"رقم الفاتورة : {row[1]}\n"
                f"العميل       : {row[2]}\n"
                f"الهاتف       : {row[3] or '-'}\n"
                f"التاريخ      : {row[5]}\n"
                f"الإجمالي     : {row[4]:.2f} ل.س\n"
                f"{'─'*45}\n"
                f"المنتجات:\n{row[6]}\n"
                f"{'─'*45}\n"
                f"المجموع الكلي: {row[4]:.2f} ل.س"
            )
            self.inv_detail.insert("end", detail)
            self.inv_detail.config(state="disabled")

    def _reset_stock(self):
        if messagebox.askyesno("تأكيد", "إعادة ضبط المخزون للقيم الافتراضية؟"):
            defaults = {1:100,2:50,3:30,4:20,5:80,6:60,7:70,8:25,9:40,10:55,11:35,12:45,13:20,14:200,15:60}
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            for pid, stock in defaults.items():
                c.execute("UPDATE products SET stock=? WHERE id=?", (stock, pid))
            conn.commit()
            conn.close()
            load_inventory()
            self._load_products_table()
            self._log("تمت إعادة ضبط المخزون", "warn")

    def _export_report(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=f"OS2_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not path:
            return
        lines = ["=" * 70,
                 "   تقرير نظام سوبر ماركت — مادة نظام التشغيل 2 (v2.1)",
                 "   المصمم: إسماعيل اليوسف",
                 f"   التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 "=" * 70]

        lines.append("\n[ المفاهيم المطبّقة ]")
        concepts = {
            "Auto Install": "تثبيت تلقائي للمكتبات مع شريط تقدم Tkinter",
            "Threads": "Thread Pool Worker لكل عملية بيع",
            "Thread Timeout": "إلغاء تلقائي للخيوط بعد 30 ثانية",
            "threading.Event": "إيقاف نظيف للخيوط الخلفية",
            "Mutex (Lock)": "stock_lock + Timed Lock (timeout=5s)",
            "RLock": "stock_rlock للعمليات المتداخلة",
            "Semaphore": "stock_semaphore قابل للضبط",
            "RWLock": "inventory_rwlock: قراءة متزامنة، كتابة حصرية",
            "Barrier": "مزامنة جماعية في سيناريو 4",
            "Race Condition": "5 سيناريوهات + محاكاة صناديق",
            "Multi-Cashier": "3-5 صناديق متوازية تشارك المخزون",
            "Auto Restock": "Producer-Consumer حقيقي لإعادة التخزين",
            "Deadlock Detection": "DFS Monitor + Resource Ordering Prevention",
            "DB WAL Mode": "PRAGMA journal_mode=WAL",
            "DB Indexes": "على name وinvoice_number وtimestamp",
            "CPU Scheduling": "FCFS + SJF + Round Robin",
            "Notifications": "إشعارات حية في الزاوية",
            "OS Learning": "7 بطاقات تعليمية تفاعلية",
        }
        for k, v in concepts.items():
            lines.append(f"  • {k}: {v}")

        lines.append("\n[ إحصائيات التزامن ]")
        with stats_lock:
            lines.append(f"  • تضاربات: {race_stats['corruption_count']}")
            lines.append(f"  • ناجحة: {race_stats['successful_ops']}")
            lines.append(f"  • فاشلة: {race_stats['failed_ops']}")

        lines.append("\n[ الفواتير الأخيرة ]")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT invoice_number, customer_name, total, created_at FROM invoices ORDER BY id DESC LIMIT 20")
        for row in c.fetchall():
            lines.append(f"  {row[0]} | {row[1]} | {row[2]:.1f} | {row[3]}")
        conn.close()

        lines.append("\n" + "=" * 70)
        lines.append("نهاية التقرير — نظام التشغيل 2 v2.1")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("تم", f"تم تصدير التقرير:\n{path}")
# ═══════════════════════════════════════════════════════════════════════════════
class ManualInvoicePopup(tk.Toplevel):
    def __init__(self, parent, invoice_text, filepath):
        super().__init__(parent)
        self.title("معاينة الفاتورة")
        self.geometry("560x600")
        self.configure(bg="#060d1a")
        self.resizable(True, True)

        tk.Label(self, text="🧾 معاينة الفاتورة", font=("Arial", 16, "bold"),
                 fg="#00e5c3", bg="#060d1a").pack(pady=(15, 5))

        # منطقة عرض نص الفاتورة
        box = scrolledtext.ScrolledText(self, bg="#030810", fg="#c9d1d9",
                                        font=("Courier", 10), relief="flat")
        box.pack(fill="both", expand=True, padx=20, pady=5)
        box.insert("end", invoice_text)
        box.config(state="disabled")

        # مسار الملف المحفوظ
        tk.Label(self, text=f"📁 مسار الحفظ: {filepath}",
                 font=("Arial", 8), fg="#5a7a9a", bg="#060d1a",
                 wraplength=520, justify="right").pack(padx=15, pady=3)

        btn_f = tk.Frame(self, bg="#060d1a")
        btn_f.pack(fill="x", padx=20, pady=(0, 15))

        def open_folder():
            import subprocess
            folder = os.path.dirname(filepath)
            try:
                if os.name == "nt":
                    os.startfile(folder)
                elif sys.platform == "darwin":
                    subprocess.call(["open", folder])
                else:
                    subprocess.call(["xdg-open", folder])
            except Exception:
                pass

        tk.Button(btn_f, text="📂 فتح مجلد الفواتير", font=("Arial", 11, "bold"),
                  bg="#238636", fg="white", relief="flat", bd=0, pady=8,
                  cursor="hand2", command=open_folder).pack(side="right", padx=5, fill="x", expand=True)
        tk.Button(btn_f, text="إغلاق", font=("Arial", 11, "bold"),
                  bg="#1f6feb", fg="white", relief="flat", bd=0, pady=8,
                  cursor="hand2", command=self.destroy).pack(side="left", padx=5, fill="x", expand=True)


# ═══════════════════════════════════════════════════════════════════════════════
# نافذة الفاتورة
# ═══════════════════════════════════════════════════════════════════════════════
class InvoicePopup(tk.Toplevel):
    def __init__(self, parent, inv_num, cname, cphone, total, items, created):
        super().__init__(parent)
        self.title("فاتورة الشراء")
        self.geometry("480x540")
        self.configure(bg="#060d1a")
        self.resizable(False, False)

        tk.Label(self, text="🧾 فاتورة الشراء", font=("Arial", 18, "bold"),
                 fg="#00e5c3", bg="#060d1a").pack(pady=(20, 5))
        tk.Frame(self, bg="#1a2a3a", height=1).pack(fill="x", padx=20)

        info_frame = tk.Frame(self, bg="#0d1526")
        info_frame.pack(fill="x", padx=20, pady=10)
        for lbl, val in [("رقم الفاتورة:", inv_num), ("الزبون:", cname),
                          ("الهاتف:", cphone or "-"), ("التاريخ:", created)]:
            row = tk.Frame(info_frame, bg="#0d1526")
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=val, font=("Arial", 10), fg="#c9d1d9", bg="#0d1526", anchor="w").pack(side="left")
            tk.Label(row, text=lbl, font=("Arial", 10, "bold"), fg="#8aa8c8", bg="#0d1526", anchor="e").pack(side="right")

        tk.Frame(self, bg="#1a2a3a", height=1).pack(fill="x", padx=20)
        tk.Label(self, text="المنتجات:", font=("Arial", 11, "bold"),
                 fg="#8aa8c8", bg="#060d1a").pack(anchor="e", padx=25, pady=(8, 2))

        items_box = scrolledtext.ScrolledText(self, height=8, bg="#0d1526", fg="#c9d1d9",
                                               font=("Arial", 10), relief="flat")
        items_box.pack(fill="x", padx=20, pady=5)
        items_box.insert("end", items)
        items_box.config(state="disabled")

        tk.Frame(self, bg="#1a2a3a", height=1).pack(fill="x", padx=20)
        total_f = tk.Frame(self, bg="#060d1a")
        total_f.pack(fill="x", padx=25, pady=10)
        tk.Label(total_f, text=f"{total:.2f} ل.س", font=("Arial", 16, "bold"),
                 fg="#00e5c3", bg="#060d1a").pack(side="left")
        tk.Label(total_f, text="المجموع الكلي:", font=("Arial", 13, "bold"),
                 fg="#c9d1d9", bg="#060d1a").pack(side="right")

        tk.Button(self, text="إغلاق", font=("Arial", 12, "bold"),
                  bg="#1f6feb", fg="white", relief="flat", pady=8,
                  cursor="hand2", command=self.destroy).pack(fill="x", padx=20, pady=(0, 20))


# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

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
        "info":  FG,
        "ok":    ACCENT,
        "warn":  YELLOW,
        "err":   RED,
        "lock":  "#58a6ff",
        "race":  "#ff7b72",
        "thread":"#d2a8ff",
    }
    color = colors.get(tag, FG)
    widget.config(state="normal")
    widget.tag_config(tag, foreground=color)
    widget.insert("end", msg + "\n", tag)
    widget.see("end")
    widget.config(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# ① واجهة: نظام العروض والخصومات التلقائية
#    OS Concepts: RLock, Race Condition, Threads, Shared Resource (DB prices)
# ══════════════════════════════════════════════════════════════════════════════
class DiscountTab(tk.Frame):
    """
    عدة خيوط تطبّق خصومات على فئات منتجات مختلفة في نفس الوقت.
    ─────────────────────────────────────────────────────────────
    بدون RLock  → خيطان يقرآن ويكتبان نفس السعر معاً → Race Condition
                  (السعر النهائي لا يعكس كلا الخصمين)
    مع RLock   → كل خيط يحصل على القفل كاملاً → لا تضارب
    ─────────────────────────────────────────────────────────────
    Shared Resource: جدول products في SQLite (عمود price)
    """

    # الفئات وخصوماتها
    CATEGORIES = {
        "مشروبات":  {"ids": [14, 15, 12, 13], "discount": 0.20, "color": BLUE},
        "خضار/فاكهة": {"ids": [5, 6, 7],       "discount": 0.15, "color": GREEN},
        "ألبان":    {"ids": [2, 3, 4],          "discount": 0.10, "color": PURPLE},
        "أساسيات":  {"ids": [1, 9, 10, 11],     "discount": 0.05, "color": YELLOW},
    }

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._rlock    = threading.RLock()   # القفل المعاد الدخول (Reentrant Lock)
        self._running  = False
        self._threads  = []
        self._orig_prices: dict = {}         # نسخ الأسعار الأصلية قبل الخصم
        self._build()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build(self):
        # رأس
        tk.Label(self, text="🏷  نظام العروض والخصومات التلقائية",
                 font=("Arial", 14, "bold"), fg=ACCENT, bg=BG).pack(pady=(10, 2))
        tk.Label(self,
                 text="خيوط متعددة تطبّق خصومات متزامنة | OS: RLock + Race Condition",
                 font=("Arial", 9), fg=GRAY, bg=BG).pack()

        # ── أزرار التحكم ──
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=15, pady=8)

        def _btn(parent, text, color, cmd):
            return tk.Button(parent, text=text, font=("Arial", 10, "bold"),
                             bg=color, fg="white", relief="flat", bd=0,
                             padx=12, pady=7, cursor="hand2", command=cmd)

        _btn(btn_row, "⚡ تشغيل بدون RLock (Race Condition)",
             RED, self._run_without_lock).pack(side="right", padx=5)
        _btn(btn_row, "🔒 تشغيل مع RLock (آمن)",
             GREEN, self._run_with_lock).pack(side="right", padx=5)
        _btn(btn_row, "↩ استعادة الأسعار الأصلية",
             GRAY, self._restore_prices).pack(side="right", padx=5)
        _btn(btn_row, "🗑 مسح السجل",
             BG2, self._clear_log).pack(side="left", padx=5)

        # ── جزء رئيسي: جدول الأسعار + كونسول ──
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=15, pady=5)

        # جدول الأسعار
        left = tk.Frame(main, bg=BG2, bd=0)
        left.pack(side="right", fill="both", expand=True, padx=(5, 0))

        tk.Label(left, text="📋 جدول الأسعار (قبل/بعد)",
                 font=("Arial", 10, "bold"), fg=ACCENT, bg=BG2).pack(pady=(8, 4))

        cols = ("المنتج", "السعر الأصلي", "السعر الحالي", "الخصم%", "الخيط")
        self._tree = ttk.Treeview(left, columns=cols, show="headings",
                                  height=14, style="Dark.Treeview")
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=100, anchor="center")

        style = ttk.Style()
        style.configure("Dark.Treeview",
                        background=BG3, foreground=FG,
                        fieldbackground=BG3, rowheight=24,
                        font=("Arial", 9))
        style.configure("Dark.Treeview.Heading",
                        background=BG2, foreground=ACCENT,
                        font=("Arial", 9, "bold"))

        sb = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        sb.pack(side="right", fill="y", pady=5)

        # أسطر تلوين الخصم
        self._tree.tag_configure("race",   background="#3a0a0a", foreground=RED)
        self._tree.tag_configure("safe",   background="#0a2a1a", foreground=ACCENT)
        self._tree.tag_configure("normal", background=BG3,       foreground=FG)

        # مؤشرات الخيوط الحية
        self._thread_indicators: dict[str, tk.Label] = {}
        ind_frame = tk.Frame(left, bg=BG2)
        ind_frame.pack(fill="x", padx=5, pady=(0, 5))
        tk.Label(ind_frame, text="حالة الخيوط:", font=("Arial", 8, "bold"),
                 fg=GRAY, bg=BG2).pack(side="right", padx=4)
        for cat in self.CATEGORIES:
            lbl = tk.Label(ind_frame, text=f"◉ {cat}", font=("Arial", 8),
                           fg=GRAY, bg=BG2)
            lbl.pack(side="right", padx=3)
            self._thread_indicators[cat] = lbl

        # كونسول
        right = tk.Frame(main, bg=BG2, width=340)
        right.pack(side="left", fill="both", expand=False, padx=(0, 5))
        right.pack_propagate(False)

        tk.Label(right, text="🖥  Console Log — حالة الخيوط والأقفال",
                 font=("Arial", 9, "bold"), fg=ACCENT, bg=BG2).pack(pady=(8, 2))

        self._log_box = scrolledtext.ScrolledText(
            right, bg=BG3, fg=FG, font=("Courier", 8),
            relief="flat", wrap="word", state="disabled")
        self._log_box.pack(fill="both", expand=True, padx=5, pady=5)

        # إحصائيات Race
        stats_row = tk.Frame(self, bg=BG)
        stats_row.pack(fill="x", padx=15, pady=(0, 8))
        self._race_var   = tk.StringVar(value="تضاربات: 0")
        self._success_var = tk.StringVar(value="نجاح: 0")
        tk.Label(stats_row, textvariable=self._race_var,
                 font=("Arial", 10, "bold"), fg=RED, bg=BG).pack(side="right", padx=15)
        tk.Label(stats_row, textvariable=self._success_var,
                 font=("Arial", 10, "bold"), fg=ACCENT, bg=BG).pack(side="right", padx=15)

        self._race_count   = 0
        self._success_count = 0

        # تحميل الجدول أول مرة
        self.after(300, self._refresh_table)

    # ── تحديث الجدول من DB ────────────────────────────────────────────────────
    def _refresh_table(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, name, price FROM products")
            rows = c.fetchall()
            conn.close()

            if not self._orig_prices:
                self._orig_prices = {r[0]: r[2] for r in rows}

            for item in self._tree.get_children():
                self._tree.delete(item)

            for pid, name, price in rows:
                orig = self._orig_prices.get(pid, price)
                pct  = round((1 - price / orig) * 100, 1) if orig else 0
                tag  = "safe" if pct > 0 else "normal"
                self._tree.insert("", "end",
                                  values=(name, f"{orig:.2f}", f"{price:.2f}",
                                          f"{pct}%" if pct else "—", "—"),
                                  tags=(tag,))
        except Exception:
            pass

    # ── تشغيل بدون قفل (Race Condition) ──────────────────────────────────────
    def _run_without_lock(self):
        if self._running:
            return
        self._running = True
        self._race_count = 0
        self._success_count = 0
        self._log("═" * 50, "info")
        self._log("⚡ بدء التشغيل بدون RLock — توقّع Race Condition!", "race")
        self._log("   خيوط متعددة تقرأ/تكتب السعر بدون تنسيق", "warn")
        self._log("═" * 50, "info")
        self._threads.clear()

        for cat, info in self.CATEGORIES.items():
            t = threading.Thread(
                target=self._discount_worker,
                args=(cat, info["ids"], info["discount"], info["color"], False),
                daemon=True,
                name=f"Disc-{cat}"
            )
            self._threads.append(t)

        # نطلق جميع الخيوط في نفس اللحظة → احتمال تضارب عالٍ
        barrier = threading.Barrier(len(self._threads))

        for t in self._threads:
            t._barrier = barrier  # type: ignore
            t.start()

        threading.Thread(target=self._wait_and_finish, daemon=True).start()

    # ── تشغيل مع RLock (آمن) ─────────────────────────────────────────────────
    def _run_with_lock(self):
        if self._running:
            return
        self._running = True
        self._race_count = 0
        self._success_count = 0
        self._log("═" * 50, "info")
        self._log("🔒 بدء التشغيل مع RLock — تطبيق آمن ومتسلسل", "ok")
        self._log("   كل خيط يحصل على RLock قبل تعديل السعر", "lock")
        self._log("═" * 50, "info")
        self._threads.clear()

        for cat, info in self.CATEGORIES.items():
            t = threading.Thread(
                target=self._discount_worker,
                args=(cat, info["ids"], info["discount"], info["color"], True),
                daemon=True,
                name=f"Disc-{cat}"
            )
            self._threads.append(t)

        barrier = threading.Barrier(len(self._threads))
        for t in self._threads:
            t._barrier = barrier  # type: ignore
            t.start()

        threading.Thread(target=self._wait_and_finish, daemon=True).start()

    # ── عامل الخصم الرئيسي ───────────────────────────────────────────────────
    def _discount_worker(self, category: str, product_ids: list,
                         discount: float, color: str, use_lock: bool):
        """
        خيط يطبّق خصماً على فئة من المنتجات.

        بدون lock: قراءة السعر ← حساب ← كتابة (بدون حماية = Race Condition)
        مع RLock : قراءة ← حساب ← كتابة كلها داخل المقطع الحرج
        """
        t_name = threading.current_thread().name
        barrier = threading.current_thread()._barrier  # type: ignore

        # تحديث مؤشر الخيط → أصفر (بدء)
        self.after(0, lambda: self._set_indicator(category, YELLOW, "⚙"))

        self._log(f"[{_ts()}] {t_name} | انتظار Barrier قبل البدء...", "thread")
        try:
            barrier.wait(timeout=5)
        except threading.BrokenBarrierError:
            return

        self._log(f"[{_ts()}] {t_name} | انطلق! discount={int(discount*100)}%"
                  f" | lock={'RLock' if use_lock else 'NONE'}", "thread")

        for pid in product_ids:
            if use_lock:
                # ── مع RLock: القسم الحرج محمي ──
                self._log(f"[{_ts()}] {t_name} | ⏳ ينتظر RLock للمنتج #{pid}", "lock")
                with self._rlock:
                    self._log(f"[{_ts()}] {t_name} | 🔒 حصل على RLock للمنتج #{pid}", "lock")
                    self._apply_discount_db(pid, discount, t_name, True)
                    time.sleep(random.uniform(0.05, 0.15))  # محاكاة عمل داخل القفل
                    self._log(f"[{_ts()}] {t_name} | 🔓 حرّر RLock للمنتج #{pid}", "lock")
            else:
                # ── بدون قفل: قراءة ← تأخير ← كتابة = Race Condition محتملة ──
                self._apply_discount_db(pid, discount, t_name, False)
                time.sleep(random.uniform(0.02, 0.08))

            # تحديث الجدول المرئي
            self.after(0, self._refresh_table)
            time.sleep(0.1)

        self._log(f"[{_ts()}] {t_name} | ✅ اكتمل تطبيق خصومات '{category}'", "ok")
        # تحديث مؤشر → أخضر (انتهى)
        self.after(0, lambda: self._set_indicator(category, ACCENT, "✔"))

    def _apply_discount_db(self, product_id: int, discount: float,
                           t_name: str, safe: bool):
        """
        تطبيق الخصم على منتج واحد في DB.
        في وضع عدم الأمان: نفصل القراءة والكتابة عمداً لاستفزاز Race Condition.
        """
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            # ── قراءة السعر الحالي ──
            c.execute("SELECT price FROM products WHERE id=?", (product_id,))
            row = c.fetchone()
            if not row:
                conn.close()
                return
            current_price = row[0]

            if not safe:
                # تأخير عمدي بين القراءة والكتابة → نافذة للتضارب
                time.sleep(random.uniform(0.01, 0.05))

            # ── حساب السعر الجديد ──
            new_price = round(current_price * (1 - discount), 2)

            # ── كتابة السعر الجديد ──
            c.execute("UPDATE products SET price=? WHERE id=?",
                      (new_price, product_id))
            conn.commit()
            conn.close()

            # فحص Race Condition: هل السعر الجديد منطقي؟
            if new_price <= 0 or new_price > current_price * 1.1:
                self._race_count += 1
                self.after(0, lambda: self._race_var.set(f"تضاربات: {self._race_count}"))
                self._log(f"[{_ts()}] ⚠ RACE CONDITION! {t_name} | "
                          f"منتج#{product_id} سعر={new_price:.2f} (كان {current_price:.2f})", "race")
            else:
                self._success_count += 1
                self.after(0, lambda: self._success_var.set(f"نجاح: {self._success_count}"))
                tag = "ok" if safe else "warn"
                self._log(f"[{_ts()}] {'🔒' if safe else '⚡'} {t_name} | "
                          f"منتج#{product_id}: {current_price:.2f} → {new_price:.2f} "
                          f"(-{int(discount*100)}%)", tag)

        except Exception as e:
            self._log(f"[{_ts()}] ❌ خطأ في {t_name}: {e}", "err")

    # ── استعادة الأسعار الأصلية ───────────────────────────────────────────────
    def _restore_prices(self):
        if self._running:
            self._log("⚠ انتظر انتهاء الخيوط أولاً", "warn")
            return
        if not self._orig_prices:
            self._log("⚠ لا توجد أسعار أصلية محفوظة", "warn")
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            for pid, price in self._orig_prices.items():
                c.execute("UPDATE products SET price=? WHERE id=?", (price, pid))
            conn.commit()
            conn.close()
            self._log(f"[{_ts()}] ↩ تمت استعادة {len(self._orig_prices)} سعر أصلي", "ok")
            self._refresh_table()
        except Exception as e:
            self._log(f"خطأ في الاستعادة: {e}", "err")

    # ── انتظار الخيوط وإعادة الضبط ───────────────────────────────────────────
    def _wait_and_finish(self):
        for t in self._threads:
            t.join(timeout=30)
        self._running = False
        self.after(0, self._refresh_table)
        self.after(0, lambda: self._log(
            f"\n[{_ts()}] 🏁 انتهت جميع الخيوط | "
            f"تضاربات={self._race_count} | نجاح={self._success_count}\n", "ok"))
        # إعادة المؤشرات للرمادي
        for cat in self.CATEGORIES:
            self.after(0, lambda c=cat: self._set_indicator(c, GRAY, "◉"))

    def _set_indicator(self, category: str, color: str, symbol: str):
        lbl = self._thread_indicators.get(category)
        if lbl:
            lbl.config(fg=color, text=f"{symbol} {category}")

    def _log(self, msg: str, tag: str = "info"):
        self.after(0, lambda: _styled_log(self._log_box, msg, tag))

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# ② واجهة: نظام التوصيل والطلبات
#    OS Concepts: Semaphore, Priority Queue, Threads, threading.Event
# ══════════════════════════════════════════════════════════════════════════════
class DeliveryTab(tk.Frame):
    """
    طلبات الزبائن تُوضع في Priority Queue (عاجل=0 / عادي=1).
    Delivery Threads (سائقون) يعالجون الطلبات بالتوازي.
    ─────────────────────────────────────────────────────────────
    بدون Semaphore → جميع الخيوط تنطلق دفعة واحدة →
                      تتعارض في الوصول لنفس الطلب (Race Condition)
    مع Semaphore(3) → 3 سائقين فقط يعملون في وقت واحد →
                       تنظيم حقيقي وعدالة في التوزيع
    ─────────────────────────────────────────────────────────────
    Timeline مرئي يُحدّث لحظة بلحظة لكل سائق.
    """

    MAX_DRIVERS = 5
    DRIVER_NAMES = ["أحمد", "محمد", "خالد", "يوسف", "عمر"]
    AREAS = ["المنطقة A", "المنطقة B", "المنطقة C", "حي النور", "حي السلام"]

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._sem: threading.Semaphore | None = None
        self._stop_event = threading.Event()
        self._order_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._order_counter = 0
        self._counter_lock  = threading.Lock()
        self._driver_threads: list[threading.Thread] = []
        self._running = False
        self._driver_status  = ["متاح 🟢"] * self.MAX_DRIVERS
        self._driver_orders  = [0]          * self.MAX_DRIVERS
        self._driver_labels  : list[tk.Label] = []
        self._driver_counters: list[tk.Label] = []
        self._producer_thread: threading.Thread | None = None
        self._build()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build(self):
        tk.Label(self, text="🚚  نظام التوصيل والطلبات",
                 font=("Arial", 14, "bold"), fg=ACCENT, bg=BG).pack(pady=(10, 2))
        tk.Label(self,
                 text="Priority Queue + Semaphore للتحكم في عدد السائقين المتزامنين",
                 font=("Arial", 9), fg=GRAY, bg=BG).pack()

        # ── صف الإعدادات ──
        cfg = tk.Frame(self, bg=BG2)
        cfg.pack(fill="x", padx=15, pady=8)

        tk.Label(cfg, text="عدد السائقين المتاحين (Semaphore):",
                 font=("Arial", 9, "bold"), fg=FG, bg=BG2).pack(side="right", padx=8, pady=8)
        self._sem_var = tk.IntVar(value=3)
        sem_spin = tk.Spinbox(cfg, from_=1, to=5, textvariable=self._sem_var,
                              width=4, font=("Arial", 11, "bold"),
                              bg=BG3, fg=ACCENT, insertbackground=ACCENT,
                              relief="flat", justify="center")
        sem_spin.pack(side="right", padx=5, pady=8)

        tk.Label(cfg, text="معدل الطلبات/ثانية:",
                 font=("Arial", 9, "bold"), fg=FG, bg=BG2).pack(side="right", padx=8)
        self._rate_var = tk.DoubleVar(value=1.5)
        rate_spin = tk.Spinbox(cfg, from_=0.5, to=4.0, increment=0.5,
                               textvariable=self._rate_var, width=4,
                               font=("Arial", 11, "bold"),
                               bg=BG3, fg=ACCENT, insertbackground=ACCENT,
                               relief="flat", justify="center")
        rate_spin.pack(side="right", padx=5, pady=8)

        # ── أزرار التحكم ──
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=15, pady=4)

        def _btn(parent, text, color, cmd):
            return tk.Button(parent, text=text, font=("Arial", 10, "bold"),
                             bg=color, fg="white", relief="flat", bd=0,
                             padx=12, pady=7, cursor="hand2", command=cmd)

        _btn(btn_row, "⚡ تشغيل بدون Semaphore (فوضى)",
             RED,   self._run_without_sem).pack(side="right", padx=5)
        _btn(btn_row, "🚦 تشغيل مع Semaphore (منظّم)",
             GREEN, self._run_with_sem).pack(side="right", padx=5)
        _btn(btn_row, "⬛ إيقاف",
             GRAY,  self._stop).pack(side="right", padx=5)
        _btn(btn_row, "📦 إضافة طلب عاجل",
             YELLOW, self._add_urgent).pack(side="left", padx=5)
        _btn(btn_row, "🗑 مسح",
             BG2,   self._clear_log).pack(side="left", padx=5)

        # ── الجزء الرئيسي ──
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=15, pady=5)

        # ── Timeline السائقين (يمين) ──
        right = tk.Frame(main, bg=BG2, width=320)
        right.pack(side="right", fill="y", padx=(5, 0))
        right.pack_propagate(False)

        tk.Label(right, text="📍 Timeline السائقين",
                 font=("Arial", 10, "bold"), fg=ACCENT, bg=BG2).pack(pady=(8, 4))

        # Semaphore Gauge
        gauge_f = tk.Frame(right, bg=BG3)
        gauge_f.pack(fill="x", padx=8, pady=4)
        tk.Label(gauge_f, text="Semaphore permits:", font=("Arial", 8, "bold"),
                 fg=GRAY, bg=BG3).pack(side="right", padx=5, pady=4)
        self._sem_gauge_var = tk.StringVar(value="—")
        tk.Label(gauge_f, textvariable=self._sem_gauge_var,
                 font=("Arial", 13, "bold"), fg=ACCENT, bg=BG3).pack(side="left", padx=8)

        # بطاقات السائقين
        cards_f = tk.Frame(right, bg=BG2)
        cards_f.pack(fill="both", expand=True, padx=8, pady=4)

        self._driver_labels.clear()
        self._driver_counters.clear()

        for i in range(self.MAX_DRIVERS):
            card = tk.Frame(cards_f, bg=BG3, bd=0)
            card.pack(fill="x", pady=3, padx=4, ipady=4)

            tk.Label(card, text=f"سائق {self.DRIVER_NAMES[i]}",
                     font=("Arial", 9, "bold"), fg=FG, bg=BG3).pack(side="right", padx=6)

            status_lbl = tk.Label(card, text="متاح 🟢",
                                  font=("Arial", 9), fg=ACCENT, bg=BG3)
            status_lbl.pack(side="right", padx=4)
            self._driver_labels.append(status_lbl)

            cnt_lbl = tk.Label(card, text="طلبات: 0",
                               font=("Courier", 8), fg=GRAY, bg=BG3)
            cnt_lbl.pack(side="left", padx=6)
            self._driver_counters.append(cnt_lbl)

        # إحصائيات
        stats_f = tk.Frame(right, bg=BG2)
        stats_f.pack(fill="x", padx=8, pady=4)
        self._q_size_var    = tk.StringVar(value="Queue: 0")
        self._delivered_var = tk.StringVar(value="مُسلَّم: 0")
        tk.Label(stats_f, textvariable=self._q_size_var,
                 font=("Courier", 9), fg=YELLOW, bg=BG2).pack(side="right", padx=8)
        tk.Label(stats_f, textvariable=self._delivered_var,
                 font=("Courier", 9), fg=ACCENT, bg=BG2).pack(side="left", padx=8)
        self._total_delivered = 0

        # ── كونسول (يسار) ──
        left = tk.Frame(main, bg=BG2)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(left, text="🖥  Console Log — الطلبات والخيوط",
                 font=("Arial", 9, "bold"), fg=ACCENT, bg=BG2).pack(pady=(8, 2))

        self._log_box = scrolledtext.ScrolledText(
            left, bg=BG3, fg=FG, font=("Courier", 8),
            relief="flat", wrap="word", state="disabled")
        self._log_box.pack(fill="both", expand=True, padx=5, pady=5)

        # Queue display
        queue_f = tk.Frame(left, bg=BG2)
        queue_f.pack(fill="x", padx=5, pady=(0, 5))
        tk.Label(queue_f, text="آخر طلبات في Queue:",
                 font=("Arial", 8, "bold"), fg=GRAY, bg=BG2).pack(side="right", padx=5)
        self._queue_preview_var = tk.StringVar(value="—")
        tk.Label(queue_f, textvariable=self._queue_preview_var,
                 font=("Courier", 8), fg=YELLOW, bg=BG2, justify="right").pack(
                 side="right", padx=5)

        # تحديث دوري للإحصائيات
        self._update_stats()

    # ── تشغيل بدون Semaphore ──────────────────────────────────────────────────
    def _run_without_sem(self):
        if self._running:
            return
        self._sem = None  # لا قفل!
        self._log("═" * 50, "info")
        self._log("⚡ تشغيل بدون Semaphore — جميع السائقين ينطلقون معاً!", "race")
        self._log("   لا حدّ لعدد السائقين المتزامنين → فوضى في الطلبات", "warn")
        self._log("═" * 50, "info")
        self._start_system(use_sem=False)

    # ── تشغيل مع Semaphore ────────────────────────────────────────────────────
    def _run_with_sem(self):
        if self._running:
            return
        n = self._sem_var.get()
        self._sem = threading.Semaphore(n)
        self._log("═" * 50, "info")
        self._log(f"🚦 تشغيل مع Semaphore({n}) — {n} سائقين كحد أقصى", "ok")
        self._log("   السائقون الزائدون ينتظرون حتى يتحرر مكان", "lock")
        self._log("═" * 50, "info")
        self._start_system(use_sem=True)

    # ── تشغيل النظام ─────────────────────────────────────────────────────────
    def _start_system(self, use_sem: bool):
        self._running = True
        self._stop_event.clear()
        self._order_counter = 0
        self._total_delivered = 0
        self._driver_orders = [0] * self.MAX_DRIVERS

        # إعادة تعيين الحالات
        for i in range(self.MAX_DRIVERS):
            self._set_driver_status(i, "متاح 🟢", ACCENT)
            self._driver_counters[i].config(text="طلبات: 0")

        # تشغيل Producer (يولّد طلبات)
        self._producer_thread = threading.Thread(
            target=self._order_producer,
            args=(self._rate_var.get(),),
            daemon=True, name="OrderProducer"
        )
        self._producer_thread.start()

        # تشغيل سائقين
        self._driver_threads.clear()
        for i in range(self.MAX_DRIVERS):
            t = threading.Thread(
                target=self._driver_worker,
                args=(i, use_sem),
                daemon=True, name=f"Driver-{self.DRIVER_NAMES[i]}"
            )
            self._driver_threads.append(t)
            t.start()

    # ── Producer: يولّد طلبات في Queue ───────────────────────────────────────
    def _order_producer(self, rate: float):
        """
        Producer Thread يضع طلبات في Priority Queue.
        الأولوية 0 = عاجل، 1 = عادي.
        """
        while not self._stop_event.is_set():
            priority = 0 if random.random() < 0.25 else 1  # 25% طلبات عاجلة
            area = random.choice(self.AREAS)
            with self._counter_lock:
                self._order_counter += 1
                oid = self._order_counter

            order = {
                "id":       oid,
                "area":     area,
                "priority": priority,
                "items":    random.randint(1, 5),
                "time":     _ts(),
            }
            # Priority Queue: (priority, id, order) — الأصغر يُسحب أولاً
            self._order_queue.put((priority, oid, order))
            label = "🔴 عاجل" if priority == 0 else "🔵 عادي"
            self._log(f"[{_ts()}] ➕ Producer | طلب #{oid} {label} → {area}", "thread")
            time.sleep(1.0 / rate)

    # ── Worker السائق ─────────────────────────────────────────────────────────
    def _driver_worker(self, driver_id: int, use_sem: bool):
        """
        كل سائق = Thread يسحب طلبات من Queue ويوصّلها.

        مع Semaphore: يحصل على permit قبل البدء → ينتظر إذا كان الحد مكتملاً
        بدون Semaphore: يبدأ فوراً بلا انتظار
        """
        name = f"Driver-{self.DRIVER_NAMES[driver_id]}"

        while not self._stop_event.is_set():
            try:
                _, _, order = self._order_queue.get(timeout=1)
            except queue.Empty:
                continue

            if use_sem and self._sem:
                self._log(f"[{_ts()}] {name} | ⏳ ينتظر Semaphore...", "lock")
                self._set_driver_status(driver_id, "ينتظر ⏳", YELLOW)
                self._sem.acquire()
                self._log(f"[{_ts()}] {name} | 🚦 حصل على Semaphore permit", "lock")

            try:
                label = "🔴عاجل" if order["priority"] == 0 else "🔵عادي"
                self._set_driver_status(driver_id, f"مشغول 🚗 {label}", RED)
                self._log(f"[{_ts()}] {name} | 🚚 يوصّل طلب#{order['id']} "
                          f"{label} → {order['area']} ({order['items']} عناصر)", "ok")

                # وقت التوصيل حسب الأولوية
                delivery_time = random.uniform(0.5, 1.5) if order["priority"] == 0 \
                                else random.uniform(1.0, 2.5)
                time.sleep(delivery_time)

                self._driver_orders[driver_id] += 1
                self._total_delivered += 1
                self._log(f"[{_ts()}] {name} | ✅ تمّ تسليم طلب#{order['id']} "
                          f"في {delivery_time:.1f}ث", "ok")
                self._order_queue.task_done()

            finally:
                if use_sem and self._sem:
                    self._sem.release()
                    self._log(f"[{_ts()}] {name} | 🔓 أعاد Semaphore permit", "lock")
                self._set_driver_status(driver_id, "متاح 🟢", ACCENT)

    # ── إضافة طلب عاجل يدوياً ────────────────────────────────────────────────
    def _add_urgent(self):
        with self._counter_lock:
            self._order_counter += 1
            oid = self._order_counter
        order = {"id": oid, "area": "طلب يدوي", "priority": 0, "items": 1, "time": _ts()}
        self._order_queue.put((0, oid, order))
        self._log(f"[{_ts()}] 🔴 طلب عاجل يدوي #{oid} أُضيف للـ Queue", "warn")

    # ── إيقاف ────────────────────────────────────────────────────────────────
    def _stop(self):
        self._stop_event.set()
        self._running = False
        self._log(f"[{_ts()}] ⬛ تم إيقاف النظام", "warn")
        for i in range(self.MAX_DRIVERS):
            self._set_driver_status(i, "متوقف ⬛", GRAY)

    # ── تحديث إحصائيات دورية ─────────────────────────────────────────────────
    def _update_stats(self):
        try:
            q_size = self._order_queue.qsize()
            self._q_size_var.set(f"Queue: {q_size}")
            self._delivered_var.set(f"مُسلَّم: {self._total_delivered}")

            # تحديث عدادات السائقين
            for i, cnt_lbl in enumerate(self._driver_counters):
                cnt_lbl.config(text=f"طلبات: {self._driver_orders[i]}")

            # عرض أعلى الطلبات في Queue (معاينة)
            items = list(self._order_queue.queue)[:3]
            preview = " | ".join(
                f"#{o[2]['id']}({'عاجل' if o[0]==0 else 'عادي'})"
                for o in items
            ) if items else "—"
            self._queue_preview_var.set(preview)

            # Semaphore gauge
            if self._sem:
                val = self._sem._value  # type: ignore
                self._sem_gauge_var.set(f"{val}/{self._sem_var.get()} permits")
            else:
                self._sem_gauge_var.set("بلا حد (∞)")

        except Exception:
            pass
        self.after(500, self._update_stats)

    def _set_driver_status(self, driver_id: int, text: str, color: str):
        self.after(0, lambda: self._driver_labels[driver_id].config(
            text=text, fg=color))

    def _log(self, msg: str, tag: str = "info"):
        self.after(0, lambda: _styled_log(self._log_box, msg, tag))

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# ③ واجهة: Multi-Cashier Dashboard
#    OS Concepts: Mutex (Lock), Threads, Shared Resource (DB stock), matplotlib
# ══════════════════════════════════════════════════════════════════════════════
class CashierDashTab(tk.Frame):
    """
    لوحة تحكم مرئية لـ 3-5 صناديق تعمل بالتوازي كـ Threads.
    المخزون (DB) مورد مشترك — كل صندوق يخصم منه عند البيع.
    ─────────────────────────────────────────────────────────────
    بدون Mutex → Over-selling: قد يُباع منتج أكثر من المتاح!
                 (صندوقان يقرآن نفس الكمية 1 وكلاهما يبيع)
    مع Mutex   → حماية كاملة: الصندوق الأول يُقفل، يخصم، يُفرج
    ─────────────────────────────────────────────────────────────
    رسم بياني matplotlib حي يُظهر توزيع المبيعات على الصناديق.
    """

    MAX_CASHIERS = 5
    CASHIER_COLORS = ["#1f6feb", "#238636", "#a21caf", "#d29922", "#f85149"]

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._mutex   = threading.Lock()    # المورد المشترك الوحيد
        self._db_lock = threading.Lock()    # قفل DB منفصل عن قفل المخزون
        self._running = False
        self._stop_ev = threading.Event()
        self._threads : list[threading.Thread] = []
        self._sales   = [0.0] * self.MAX_CASHIERS
        self._txns    = [0]   * self.MAX_CASHIERS
        self._oversell = 0
        self._fig_canvas = None
        self._build()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build(self):
        tk.Label(self, text="🏦  Multi-Cashier Dashboard — لوحة الصناديق الحية",
                 font=("Arial", 14, "bold"), fg=ACCENT, bg=BG).pack(pady=(10, 2))
        tk.Label(self,
                 text="Mutex يحمي المخزون المشترك من Over-selling | matplotlib حي",
                 font=("Arial", 9), fg=GRAY, bg=BG).pack()

        # ── إعدادات ──
        cfg = tk.Frame(self, bg=BG2)
        cfg.pack(fill="x", padx=15, pady=6)

        tk.Label(cfg, text="عدد الصناديق:",
                 font=("Arial", 9, "bold"), fg=FG, bg=BG2).pack(side="right", padx=8, pady=6)
        self._ncash_var = tk.IntVar(value=4)
        tk.Spinbox(cfg, from_=2, to=5, textvariable=self._ncash_var, width=3,
                   font=("Arial", 11, "bold"), bg=BG3, fg=ACCENT,
                   insertbackground=ACCENT, relief="flat", justify="center"
                   ).pack(side="right", padx=5, pady=6)

        tk.Label(cfg, text="عمليات/ثانية لكل صندوق:",
                 font=("Arial", 9, "bold"), fg=FG, bg=BG2).pack(side="right", padx=8)
        self._speed_var = tk.DoubleVar(value=1.0)
        tk.Spinbox(cfg, from_=0.5, to=5.0, increment=0.5,
                   textvariable=self._speed_var, width=4,
                   font=("Arial", 11, "bold"), bg=BG3, fg=ACCENT,
                   insertbackground=ACCENT, relief="flat", justify="center"
                   ).pack(side="right", padx=5, pady=6)

        # ── أزرار ──
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=15, pady=4)

        def _btn(parent, text, color, cmd):
            return tk.Button(parent, text=text, font=("Arial", 10, "bold"),
                             bg=color, fg="white", relief="flat", bd=0,
                             padx=12, pady=7, cursor="hand2", command=cmd)

        _btn(btn_row, "⚡ تشغيل بدون Mutex (Over-Selling)",
             RED,   self._run_without_mutex).pack(side="right", padx=5)
        _btn(btn_row, "🔒 تشغيل مع Mutex (آمن)",
             GREEN, self._run_with_mutex).pack(side="right", padx=5)
        _btn(btn_row, "⬛ إيقاف",
             GRAY,  self._stop).pack(side="right", padx=5)
        _btn(btn_row, "🔄 إعادة ضبط المخزون",
             BLUE,  self._reset_stock).pack(side="left", padx=5)
        _btn(btn_row, "🗑 مسح",
             BG2,   self._clear_log).pack(side="left", padx=5)

        # ── الجزء الرئيسي ──
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=15, pady=5)

        # ── الرسم البياني (matplotlib حي) ──
        chart_frame = tk.Frame(main, bg=BG2, width=420)
        chart_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        tk.Label(chart_frame, text="📊 توزيع المبيعات على الصناديق (حي)",
                 font=("Arial", 9, "bold"), fg=ACCENT, bg=BG2).pack(pady=(6, 2))

        self._fig, self._ax = plt.subplots(figsize=(5, 4), facecolor=BG2)
        self._ax.set_facecolor(BG3)
        self._ax.tick_params(colors=FG, labelsize=8)
        for sp in self._ax.spines.values():
            sp.set_color("#1a2a3a")
        self._ax.set_title("مبيعات الصناديق (ل.س)", color=FG, fontsize=9)

        canvas = FigureCanvasTkAgg(self._fig, master=chart_frame)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        self._fig_canvas = canvas

        # بدء تحديث الرسم البياني
        self._update_chart()

        # ── بطاقات الصناديق + كونسول (يسار) ──
        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=False)

        # بطاقات
        cards_frame = tk.Frame(left, bg=BG)
        cards_frame.pack(fill="x")

        self._card_labels:    list[tk.Label] = []
        self._card_sales:     list[tk.Label] = []
        self._card_txns:      list[tk.Label] = []
        self._card_status:    list[tk.Label] = []

        for i in range(self.MAX_CASHIERS):
            card = tk.Frame(cards_frame, bg=self.CASHIER_COLORS[i], bd=0)
            card.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="ew", ipady=4)

            tk.Label(card, text=f"صندوق {i+1}",
                     font=("Arial", 9, "bold"), fg="white",
                     bg=self.CASHIER_COLORS[i]).pack(pady=(4, 0), padx=8)

            status_lbl = tk.Label(card, text="متوقف ⬛",
                                  font=("Arial", 8), fg="white",
                                  bg=self.CASHIER_COLORS[i])
            status_lbl.pack(padx=8)
            self._card_status.append(status_lbl)

            sales_lbl = tk.Label(card, text="0.00 ل.س",
                                 font=("Arial", 10, "bold"), fg="white",
                                 bg=self.CASHIER_COLORS[i])
            sales_lbl.pack(padx=8)
            self._card_sales.append(sales_lbl)

            txn_lbl = tk.Label(card, text="0 عملية",
                               font=("Courier", 8), fg="white",
                               bg=self.CASHIER_COLORS[i])
            txn_lbl.pack(padx=8, pady=(0, 4))
            self._card_txns.append(txn_lbl)

        for c in range(3):
            cards_frame.columnconfigure(c, weight=1)

        # مؤشر Over-Selling
        os_f = tk.Frame(left, bg=BG)
        os_f.pack(fill="x", pady=4)
        self._oversell_var = tk.StringVar(value="Over-Selling: 0")
        tk.Label(os_f, textvariable=self._oversell_var,
                 font=("Arial", 11, "bold"), fg=RED, bg=BG).pack(side="right", padx=10)
        self._total_sales_var = tk.StringVar(value="إجمالي: 0.00 ل.س")
        tk.Label(os_f, textvariable=self._total_sales_var,
                 font=("Arial", 11, "bold"), fg=ACCENT, bg=BG).pack(side="left", padx=10)

        # كونسول
        console_f = tk.Frame(left, bg=BG2, width=340)
        console_f.pack(fill="both", expand=True, pady=(4, 0))
        console_f.pack_propagate(False)

        tk.Label(console_f, text="🖥  Console Log — الصناديق والأقفال",
                 font=("Arial", 9, "bold"), fg=ACCENT, bg=BG2).pack(pady=(6, 2))

        self._log_box = scrolledtext.ScrolledText(
            console_f, bg=BG3, fg=FG, font=("Courier", 8),
            relief="flat", wrap="word", state="disabled")
        self._log_box.pack(fill="both", expand=True, padx=5, pady=5)

    # ── تشغيل بدون Mutex ──────────────────────────────────────────────────────
    def _run_without_mutex(self):
        if self._running:
            return
        self._log("═" * 50, "info")
        self._log("⚡ تشغيل بدون Mutex — توقّع Over-Selling!", "race")
        self._log("   صناديق متعددة تقرأ وتخصم المخزون في نفس اللحظة", "warn")
        self._log("═" * 50, "info")
        self._start(use_mutex=False)

    # ── تشغيل مع Mutex ────────────────────────────────────────────────────────
    def _run_with_mutex(self):
        if self._running:
            return
        self._log("═" * 50, "info")
        self._log("🔒 تشغيل مع Mutex — حماية كاملة من Over-Selling", "ok")
        self._log("   كل صندوق يحصل على Lock قبل الخصم من المخزون", "lock")
        self._log("═" * 50, "info")
        self._start(use_mutex=True)

    # ── تشغيل النظام ─────────────────────────────────────────────────────────
    def _start(self, use_mutex: bool):
        self._running = True
        self._stop_ev.clear()
        self._oversell = 0
        n = self._ncash_var.get()
        speed = self._speed_var.get()

        # إعادة تعيين
        self._sales  = [0.0] * self.MAX_CASHIERS
        self._txns   = [0]   * self.MAX_CASHIERS
        self._threads.clear()

        load_inventory()

        for i in range(n):
            self._set_card_status(i, "شغّال 🟢", "white")
            t = threading.Thread(
                target=self._cashier_worker,
                args=(i, use_mutex, speed),
                daemon=True,
                name=f"Cashier-{i+1}"
            )
            self._threads.append(t)
            t.start()

        # إيقاف الصناديق الزائدة
        for i in range(n, self.MAX_CASHIERS):
            self._set_card_status(i, "غير نشط ⬛", GRAY)

    # ── عامل الصندوق ─────────────────────────────────────────────────────────
    def _cashier_worker(self, cashier_id: int, use_mutex: bool, speed: float):
        """
        صندوق = Thread يختار منتجاً عشوائياً ويخصم من مخزون DB.

        بدون Mutex:
            1. قراءة المخزون  → مثلاً stock=1
            2. [تأخير عمدي]   → صندوق آخر يقرأ stock=1 أيضاً
            3. كلاهما يكتب stock=0 → كلاهما ينجح لكن بيعا وحدة واحدة مرتين!

        مع Mutex:
            1. الحصول على Lock
            2. قراءة وخصم
            3. تحرير Lock
        """
        t_name = threading.current_thread().name
        prod_ids = list(range(1, 16))

        while not self._stop_ev.is_set():
            pid = random.choice(prod_ids)
            qty = random.randint(1, 3)

            if use_mutex:
                self._log(f"[{_ts()}] {t_name} | ⏳ ينتظر Mutex...", "lock")
                self._set_card_status(cashier_id, "ينتظر Mutex ⏳", YELLOW)

                with self._mutex:   # ── القسم الحرج المحمي ──
                    self._log(f"[{_ts()}] {t_name} | 🔒 حصل على Mutex", "lock")
                    self._set_card_status(cashier_id, "يبيع 🛒", "white")
                    result = self._sell_product(pid, qty, t_name, safe=True)
                    self._log(f"[{_ts()}] {t_name} | 🔓 حرّر Mutex", "lock")

            else:
                # بدون قفل: قراءة وكتابة مكشوفة
                result = self._sell_product(pid, qty, t_name, safe=False)

            if result == "ok":
                self._sales[cashier_id] += random.uniform(2, 10)
                self._txns[cashier_id]  += 1
                self._update_cards()
            elif result == "oversell":
                self._oversell += 1
                self.after(0, lambda: self._oversell_var.set(
                    f"⚠ Over-Selling: {self._oversell}"))
                self._log(f"[{_ts()}] 💥 {t_name} | OVER-SELL! "
                          f"منتج#{pid} كميته سالبة!", "race")

            self._set_card_status(cashier_id, "شغّال 🟢", "white")
            time.sleep(1.0 / speed)

        self._set_card_status(cashier_id, "متوقف ⬛", GRAY)
        self._log(f"[{_ts()}] {t_name} | أوقف العمل", "warn")

    def _sell_product(self, product_id: int, qty: int, t_name: str, safe: bool) -> str:
        """
        خصم الكمية من المخزون في DB.
        يعيد: "ok" | "oversell" | "empty" | "error"
        """
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            # قراءة المخزون
            c.execute("SELECT name, stock, price FROM products WHERE id=?", (product_id,))
            row = c.fetchone()
            if not row:
                conn.close()
                return "error"
            name, stock, price = row

            if stock <= 0:
                conn.close()
                return "empty"

            if not safe:
                # تأخير عمدي لاستفزاز Race Condition
                time.sleep(random.uniform(0.01, 0.04))

            new_stock = stock - qty

            if new_stock < 0 and not safe:
                # Over-selling سيحدث!
                conn.execute("UPDATE products SET stock=? WHERE id=?",
                             (new_stock, product_id))
                conn.commit()
                conn.close()

                # سجّل في audit
                try:
                    with sqlite3.connect(DB_PATH, timeout=5) as audit_conn:
                        audit_conn.execute("PRAGMA journal_mode=WAL")
                        audit_conn.execute(
                            "INSERT INTO audit_log "
                            "(thread_name,thread_id,action,product_id,"
                            "old_value,new_value,timestamp,sync_mode,cashier_id) "
                            "VALUES (?,?,?,?,?,?,?,?,?)",
                            (t_name, threading.get_ident(), "OVERSELL",
                             product_id, stock, new_stock,
                             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                             "NO_MUTEX", 0))
                except Exception:
                    pass
                return "oversell"

            # بيع طبيعي
            actual_qty = min(qty, stock)
            conn.execute("UPDATE products SET stock=? WHERE id=?",
                         (stock - actual_qty, product_id))
            conn.commit()

            sale_amount = round(price * actual_qty, 2)
            self._log(f"[{_ts()}] {'🔒' if safe else '⚡'} {t_name} | "
                      f"بيع {actual_qty}×{name} | "
                      f"مخزون: {stock}→{stock - actual_qty} | "
                      f"{sale_amount:.2f} ل.س", "ok")

            # تسجيل في audit_log
            try:
                conn2 = sqlite3.connect(DB_PATH, timeout=5)
                conn2.execute("PRAGMA journal_mode=WAL")
                conn2.execute(
                    "INSERT INTO audit_log "
                    "(thread_name,thread_id,action,product_id,"
                    "old_value,new_value,timestamp,sync_mode,cashier_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (t_name, threading.get_ident(), "SELL",
                     product_id, stock, stock - actual_qty,
                     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                     "MUTEX" if safe else "NO_MUTEX", 0))
                conn2.commit()
                conn2.close()
            except Exception:
                pass

            conn.close()
            return "ok"

        except Exception as e:
            self._log(f"[{_ts()}] ❌ خطأ في {t_name}: {e}", "err")
            return "error"

    # ── تحديث بطاقات الصناديق ─────────────────────────────────────────────────
    def _update_cards(self):
        total = sum(self._sales)
        self.after(0, lambda: self._total_sales_var.set(f"إجمالي: {total:.2f} ل.س"))
        for i in range(self.MAX_CASHIERS):
            i_local = i
            s_local  = self._sales[i]
            tx_local = self._txns[i]
            self.after(0, lambda il=i_local, sl=s_local, tx=tx_local: (
                self._card_sales[il].config(text=f"{sl:.2f} ل.س"),
                self._card_txns[il].config(text=f"{tx} عملية")
            ))

    # ── تحديث رسم matplotlib ─────────────────────────────────────────────────
    def _update_chart(self):
        try:
            n = self._ncash_var.get()
            labels = [f"صندوق {i+1}" for i in range(n)]
            values = self._sales[:n]
            colors = self.CASHIER_COLORS[:n]

            self._ax.clear()
            self._ax.set_facecolor(BG3)
            self._ax.tick_params(colors=FG, labelsize=8)
            for sp in self._ax.spines.values():
                sp.set_color("#1a2a3a")

            if any(v > 0 for v in values):
                bars = self._ax.bar(labels, values, color=colors, edgecolor="#1a2a3a")
                for bar, val in zip(bars, values):
                    if val > 0:
                        self._ax.text(
                            bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.5,
                            f"{val:.1f}",
                            ha="center", va="bottom",
                            color=FG, fontsize=7
                        )
            else:
                self._ax.text(0.5, 0.5, "في انتظار بيانات...",
                              ha="center", va="center",
                              color=GRAY, fontsize=10, transform=self._ax.transAxes)

            self._ax.set_title("مبيعات الصناديق (ل.س)", color=FG, fontsize=9)
            self._ax.set_ylabel("ل.س", color=GRAY, fontsize=8)

            if self._fig_canvas:
                self._fig_canvas.draw_idle()

        except Exception:
            pass
        self.after(1000, self._update_chart)

    # ── إيقاف ────────────────────────────────────────────────────────────────
    def _stop(self):
        self._stop_ev.set()
        self._running = False
        self._log(f"[{_ts()}] ⬛ تم إيقاف جميع الصناديق", "warn")

    # ── إعادة ضبط المخزون ────────────────────────────────────────────────────
    def _reset_stock(self):
        if self._running:
            self._log("⚠ أوقف الصناديق أولاً قبل الإعادة", "warn")
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM products")
            pids = [r[0] for r in c.fetchall()]
            for pid in pids:
                c.execute("UPDATE products SET stock=? WHERE id=?",
                          (random.randint(20, 60), pid))
            conn.commit()
            conn.close()
            load_inventory()
            self._log(f"[{_ts()}] 🔄 تم إعادة ضبط مخزون {len(pids)} منتج", "ok")
        except Exception as e:
            self._log(f"خطأ في الإعادة: {e}", "err")

    def _set_card_status(self, cid: int, text: str, color: str):
        self.after(0, lambda: self._card_status[cid].config(text=text, fg=color))

    def _log(self, msg: str, tag: str = "info"):
        self.after(0, lambda: _styled_log(self._log_box, msg, tag))

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# اختبار مستقل (يُحذف عند الدمج مع ملف المشروع الأصلي)
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# ⓬  نظام إدارة الفواتير والمدفوعات — PaymentManagerTab
# ══════════════════════════════════════════════════════════════════════════════
class PaymentManagerTab(tk.Frame):
    """
    تبويب إدارة الفواتير والمدفوعات.

    يُطبّق المفاهيم التالية:
    • كل عملية دفع أو تعديل تعمل في Thread منفصل
    • RLock لحماية المورد المشترك (سجلات الدفع)
    • وضعان: NO_MUTEX (يظهر Race Condition) و MUTEX (يحل التضارب)
    • Console Log مخصص يعرض اسم الخيط والوقت ونوع العملية
    • تسجيل كل عملية في payments_log مع اسم الخيط وsync_mode
    """

    # ── ألوان الثيم ──
    BG   = "#060d1a"
    BG2  = "#0a1628"
    BG3  = "#0d1526"
    CARD = "#1a2a3a"
    FG   = "#c9d1d9"
    CYAN = "#00e5c3"
    GRAY = "#5a7a9a"

    def __init__(self, master, **kwargs):
        super().__init__(master, bg=self.BG, **kwargs)

        # ── RLock: يحمي قراءة/كتابة سجلات الدفع (Shared Resource) ──
        # Reentrant Lock يُتيح لنفس الخيط الحصول على القفل أكثر من مرة
        # مفيد عند استدعاء دوال الدفع داخل بعضها
        self._pay_rlock = threading.RLock()

        # وضع المزامنة الحالي: True=Mutex فعّال / False=Race Condition مُتعمَّد
        self._mutex_mode = tk.BooleanVar(value=True)

        # عداد الخيوط لتمييزها
        self._thread_counter = 0
        self._tc_lock = threading.Lock()

        self._build_ui()
        self._refresh_table()

        # خيط Daemon للتحقق الدوري من الفواتير القديمة (كل 60 ثانية)
        # اسم الخيط: PaymentChecker — Daemon يتوقف تلقائياً عند إغلاق البرنامج
        self._stop_ev = threading.Event()
        t_checker = threading.Thread(
            target=self._auto_checker,
            daemon=True,
            name="PaymentChecker"
        )
        t_checker.start()

    # ─────────────────────────────────────────────────────────────────────────
    # بناء الواجهة
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        tk.Label(self, text="💳 إدارة الفواتير والمدفوعات",
                 font=("Arial", 15, "bold"), fg=self.CYAN, bg=self.BG).pack(pady=(12, 2))
        tk.Label(self,
                 text="كل عملية دفع تعمل في Thread مستقل | RLock يحمي المورد المشترك",
                 font=("Arial", 9), fg=self.GRAY, bg=self.BG).pack(pady=(0, 6))

        # ── شريط وضع التزامن ──
        mode_bar = tk.Frame(self, bg=self.BG2)
        mode_bar.pack(fill="x", padx=15, pady=(0, 5))

        tk.Label(mode_bar, text="وضع التزامن:", fg=self.FG, bg=self.BG2,
                 font=("Arial", 10, "bold")).pack(side="right", padx=10, pady=6)

        # زر تبديل Mutex/Race Condition
        self._mode_btn = tk.Button(mode_bar, text="🔒 Mutex مُفعَّل",
                                   font=("Arial", 10, "bold"),
                                   bg="#238636", fg="white", relief="flat", bd=0,
                                   padx=12, pady=5, cursor="hand2",
                                   command=self._toggle_mode)
        self._mode_btn.pack(side="right", padx=5, pady=4)

        self._mode_desc = tk.Label(mode_bar,
            text="✅ الخيوط تنتظر دورها — لا تضارب في المبالغ",
            font=("Courier", 9), fg="#3fb950", bg=self.BG2)
        self._mode_desc.pack(side="right", padx=10)

        # ── الجسم: عمودان ──
        body = tk.Frame(self, bg=self.BG)
        body.pack(fill="both", expand=True, padx=15, pady=5)

        # ── يسار: جدول الفواتير ──
        left = tk.Frame(body, bg=self.BG3)
        left.pack(side="right", fill="both", expand=True, padx=(0, 5))

        tk.Label(left, text="قائمة الفواتير وحالة الدفع",
                 font=("Arial", 11, "bold"), fg=self.CYAN, bg=self.BG3).pack(pady=(8, 3))

        # Treeview لعرض الفواتير
        cols = ("invoice", "total", "paid", "remaining", "status", "progress")
        self._tree = ttk.Treeview(left, columns=cols, show="headings",
                                   height=10, selectmode="browse")
        headers = {
            "invoice":   ("رقم الفاتورة", 120),
            "total":     ("الإجمالي", 90),
            "paid":      ("المدفوع", 90),
            "remaining": ("المتبقي", 90),
            "status":    ("حالة الدفع", 130),
            "progress":  ("نسبة الدفع", 100),
        }
        for col, (heading, width) in headers.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        style = ttk.Style()
        style.configure("Treeview", background=self.BG2, fieldbackground=self.BG2,
                         foreground=self.FG, rowheight=26)
        style.configure("Treeview.Heading", background=self.CARD, foreground=self.CYAN,
                         font=("Arial", 9, "bold"))
        style.map("Treeview", background=[("selected", "#1f6feb")])

        self._tree.tag_configure("paid",    background="#0d2a0d", foreground="#3fb950")
        self._tree.tag_configure("partial", background="#2a2a0d", foreground="#d29922")
        self._tree.tag_configure("unpaid",  background="#2a0d0d", foreground="#f85149")

        sb = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="left", fill="y", padx=(0, 2))
        self._tree.pack(fill="both", expand=True, padx=(2, 0), pady=(0, 5))

        # زر تحديث + زر إضافة فاتورة تجريبية
        btn_row = tk.Frame(left, bg=self.BG3)
        btn_row.pack(fill="x", padx=5, pady=4)
        tk.Button(btn_row, text="🔄 تحديث", font=("Arial", 9), bg="#1f6feb", fg="white",
                  relief="flat", padx=10, cursor="hand2",
                  command=self._refresh_table).pack(side="right", padx=4)
        tk.Button(btn_row, text="➕ إضافة فاتورة تجريبية", font=("Arial", 9),
                  bg="#9a7000", fg="white", relief="flat", padx=10, cursor="hand2",
                  command=self._add_sample_invoice).pack(side="right", padx=4)
        tk.Button(btn_row, text="🔗 مزامنة الفواتير المحفوظة", font=("Arial", 9),
                  bg="#6e40c9", fg="white", relief="flat", padx=10, cursor="hand2",
                  command=self._sync_invoices_from_main).pack(side="right", padx=4)

        # ── يمين: لوحات التحكم ──
        right = tk.Frame(body, bg=self.BG, width=350)
        right.pack(side="right", fill="y", padx=(5, 0))
        right.pack_propagate(False)

        # ── بطاقة: تسجيل دفعة جديدة ──
        self._card(right, "💵 تسجيل دفعة جديدة")
        pay_f = tk.Frame(right, bg=self.CARD)
        pay_f.pack(fill="x", padx=8, pady=(0, 8))

        self._lbl(pay_f, "رقم الفاتورة")
        self._inv_num_var = tk.StringVar()
        self._entry(pay_f, self._inv_num_var)

        self._lbl(pay_f, "المبلغ المدفوع (ل.س)")
        self._amount_var = tk.StringVar()
        self._entry(pay_f, self._amount_var)

        tk.Button(pay_f, text="✅ تسجيل الدفعة",
                  font=("Arial", 10, "bold"),
                  bg="#238636", fg="white", relief="flat", bd=0,
                  pady=8, cursor="hand2",
                  command=self._do_add_payment).pack(fill="x", padx=10, pady=8)

        # ── بطاقة: تعديل دفعة موجودة ──
        self._card(right, "✏ تعديل دفعة سابقة")
        edit_f = tk.Frame(right, bg=self.CARD)
        edit_f.pack(fill="x", padx=8, pady=(0, 8))

        self._lbl(edit_f, "رقم الفاتورة للتعديل")
        self._edit_inv_var = tk.StringVar()
        self._entry(edit_f, self._edit_inv_var)

        self._lbl(edit_f, "المبلغ المدفوع الجديد (ل.س)")
        self._edit_amount_var = tk.StringVar()
        self._entry(edit_f, self._edit_amount_var)

        self._lbl(edit_f, "ملاحظة التعديل (إلزامي)")
        self._edit_note_var = tk.StringVar()
        self._entry(edit_f, self._edit_note_var)

        tk.Button(edit_f, text="💾 حفظ التعديل",
                  font=("Arial", 10, "bold"),
                  bg="#9a7000", fg="white", relief="flat", bd=0,
                  pady=8, cursor="hand2",
                  command=self._do_edit_payment).pack(fill="x", padx=10, pady=8)

        # ── Console Log ──
        tk.Label(self, text="📟 Console Log الخيوط:",
                 font=("Arial", 9, "bold"), fg=self.GRAY, bg=self.BG).pack(anchor="e", padx=15)
        self._log_box = scrolledtext.ScrolledText(
            self, height=7, bg="#030810", fg=self.FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self._log_box.pack(fill="x", padx=15, pady=(0, 8))

        for tag, col in [
            ("ok",   "#3fb950"), ("err",  "#f85149"),
            ("warn", "#d29922"), ("sync", "#00e5c3"),
            ("race", "#ff6b6b"), ("info", "#8aa8c8"),
        ]:
            self._log_box.tag_config(tag, foreground=col)

    # ─────────────────────────────────────────────────────────────────────────
    # أدوات بناء الواجهة
    # ─────────────────────────────────────────────────────────────────────────
    def _card(self, parent, title):
        tk.Label(parent, text=title, font=("Arial", 10, "bold"),
                 fg=self.CYAN, bg=self.BG, anchor="e").pack(fill="x", padx=8, pady=(8, 2))

    def _lbl(self, parent, text):
        tk.Label(parent, text=text, font=("Arial", 9),
                 fg=self.FG, bg=self.CARD, anchor="e").pack(fill="x", padx=10, pady=(5, 1))

    def _entry(self, parent, var):
        tk.Entry(parent, textvariable=var, font=("Arial", 10),
                 bg="#1a2a3a", fg="white", insertbackground="white",
                 relief="flat", bd=6, justify="right").pack(fill="x", padx=10, pady=(0, 2))

    # ─────────────────────────────────────────────────────────────────────────
    # تبديل وضع التزامن
    # ─────────────────────────────────────────────────────────────────────────
    def _toggle_mode(self):
        """تبديل بين وضع Mutex الآمن ووضع No-Mutex (Race Condition مُتعمَّد)"""
        current = self._mutex_mode.get()
        self._mutex_mode.set(not current)
        if not current:
            # تفعيل Mutex
            self._mode_btn.config(text="🔒 Mutex مُفعَّل", bg="#238636")
            self._mode_desc.config(
                text="✅ الخيوط تنتظر دورها — لا تضارب في المبالغ",
                fg="#3fb950")
            self._log("🔒 تم تفعيل Mutex — وضع آمن", "sync")
        else:
            # تعطيل Mutex — Race Condition
            self._mode_btn.config(text="⚡ No-Mutex (Race!)", bg="#b91c1c")
            self._mode_desc.config(
                text="⚠ بدون قفل — قد تتضارب الخيوط على المبالغ!",
                fg="#f85149")
            self._log("⚡ تم تعطيل Mutex — قد يحدث تضارب!", "race")

    # ─────────────────────────────────────────────────────────────────────────
    # تسجيل دفعة جديدة (في Thread منفصل)
    # ─────────────────────────────────────────────────────────────────────────
    def _do_add_payment(self):
        """
        تشغيل Thread منفصل لتسجيل الدفعة.
        اسم الخيط: PayAdd-{N} — يتميز كل خيط برقم تسلسلي.
        القفل المستخدم: RLock (إذا كان Mutex مُفعَّلاً)
        """
        inv_num = self._inv_num_var.get().strip()
        amount_str = self._amount_var.get().strip()

        if not inv_num:
            messagebox.showwarning("تنبيه", "أدخل رقم الفاتورة")
            return
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("تنبيه", "أدخل مبلغاً صحيحاً أكبر من الصفر")
            return

        with self._tc_lock:
            self._thread_counter += 1
            t_num = self._thread_counter

        # خيط منفصل لكل عملية دفع — اسم الخيط واضح للتقييم الأكاديمي
        t = threading.Thread(
            target=self._add_payment_worker,
            args=(inv_num, amount, t_num),
            daemon=True,
            name=f"PayAdd-{t_num}"
        )
        t.start()

    def _add_payment_worker(self, inv_num: str, amount: float, t_num: int):
        """
        Worker للدفعة الجديدة — يعمل داخل Thread منفصل.
        RLock: يحمي عملية القراءة والكتابة من التضارب بين الخيوط.
        بدون RLock: قد يقرأ خيطان نفس المبلغ ويضيفا عليه معاً → تضارب!
        """
        t_name = threading.current_thread().name
        mode_str = "MUTEX" if self._mutex_mode.get() else "NO_MUTEX"
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

        self._log(f"[{ts}] 🧵 {t_name} | بدأ | فاتورة={inv_num} | مبلغ={amount:.2f}", "info")

        if not self._mutex_mode.get():
            # وضع No-Mutex: تأخير عمدي لاستفزاز Race Condition
            time.sleep(random.uniform(0.01, 0.05))

        # ── محاولة الحصول على RLock ──
        if self._mutex_mode.get():
            # RLock: القفل الذي يحمي سجلات الدفع (Shared Resource)
            # acquire_timeout: يحاول لمدة 5 ثوانٍ قبل الاستسلام
            acquired = self._pay_rlock.acquire(timeout=5)
            if not acquired:
                self._log(f"[{ts}] ❌ {t_name} | تعذّر الحصول على RLock!", "err")
                return
            self._log(f"[{ts}] 🔒 {t_name} | حصل على RLock", "sync")

        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            # قراءة سجل الفاتورة
            c.execute("""SELECT id, total_amount, paid_amount, status
                         FROM invoice_payments WHERE invoice_number=?""", (inv_num,))
            row = c.fetchone()

            if not row:
                self.after(0, lambda: messagebox.showwarning(
                    "تنبيه", f"الفاتورة {inv_num} غير موجودة في قاعدة البيانات"))
                conn.close()
                return

            inv_id, total, paid, status = row
            remaining = total - paid

            # التحقق من أن المبلغ لا يتجاوز المتبقي
            if amount > remaining + 0.001:
                self.after(0, lambda r=remaining: messagebox.showwarning(
                    "تنبيه",
                    f"المبلغ المُدخَل ({amount:.2f}) يتجاوز المتبقي ({r:.2f} ل.س)!\n"
                    "لا يمكن الدفع أكثر من المستحق."))
                conn.close()
                return

            if not self._mutex_mode.get():
                # تأخير إضافي بدون قفل — نافذة التضارب
                time.sleep(random.uniform(0.02, 0.06))

            new_paid = round(paid + amount, 2)
            new_status = ("paid" if new_paid >= total - 0.001
                          else "partial" if new_paid > 0 else "unpaid")
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # تحديث سجل الفاتورة داخل Transaction
            try:
                conn.execute("""UPDATE invoice_payments
                                SET paid_amount=?, status=?, last_updated=?
                                WHERE id=?""", (new_paid, new_status, now_str, inv_id))

                # تسجيل في payments_log
                conn.execute("""INSERT INTO payments_log
                    (invoice_id, thread_name, amount, action_type, note, timestamp, sync_mode)
                    VALUES (?,?,?,?,?,?,?)""",
                    (inv_id, t_name, amount, "ADD",
                     f"دفعة جديدة بواسطة {t_name}",
                     now_str, mode_str))
                conn.commit()

                ts2 = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self._log(
                    f"[{ts2}] ✅ {t_name} | تم | دُفع={amount:.2f} | "
                    f"إجمالي مدفوع={new_paid:.2f} | حالة={new_status}", "ok")

            except Exception as e:
                conn.rollback()
                self._log(f"[{ts}] ❌ {t_name} | Rollback: {e}", "err")
            finally:
                conn.close()

        finally:
            if self._mutex_mode.get():
                self._pay_rlock.release()
                self._log(f"[{ts}] 🔓 {t_name} | حرَّر RLock", "sync")

        # تحديث الجدول في الخيط الرئيسي (Thread-safe UI)
        self.after(0, self._refresh_table)

    # ─────────────────────────────────────────────────────────────────────────
    # تعديل دفعة موجودة (في Thread منفصل)
    # ─────────────────────────────────────────────────────────────────────────
    def _do_edit_payment(self):
        """
        تشغيل Thread منفصل لتعديل دفعة موجودة.
        اسم الخيط: PayEdit-{N}
        القفل: RLock يحمي عملية التعديل
        """
        inv_num = self._edit_inv_var.get().strip()
        amount_str = self._edit_amount_var.get().strip()
        note = self._edit_note_var.get().strip()

        if not inv_num:
            messagebox.showwarning("تنبيه", "أدخل رقم الفاتورة")
            return
        if not note:
            messagebox.showwarning("تنبيه", "ملاحظة التعديل إلزامية — أدخلها قبل الحفظ")
            return
        try:
            new_paid = float(amount_str)
            if new_paid < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("تنبيه", "أدخل مبلغاً صحيحاً (0 أو أكبر)")
            return

        with self._tc_lock:
            self._thread_counter += 1
            t_num = self._thread_counter

        # خيط منفصل لعملية التعديل
        t = threading.Thread(
            target=self._edit_payment_worker,
            args=(inv_num, new_paid, note, t_num),
            daemon=True,
            name=f"PayEdit-{t_num}"
        )
        t.start()

    def _edit_payment_worker(self, inv_num: str, new_paid: float,
                              note: str, t_num: int):
        """
        Worker لتعديل دفعة موجودة — يعمل داخل Thread منفصل.
        يُسجَّل التعديل في audit_log مع اسم الخيط والوقت وسبب التعديل.
        """
        t_name = threading.current_thread().name
        mode_str = "MUTEX" if self._mutex_mode.get() else "NO_MUTEX"
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

        self._log(f"[{ts}] ✏ {t_name} | تعديل فاتورة={inv_num} | جديد={new_paid:.2f}", "warn")

        if self._mutex_mode.get():
            acquired = self._pay_rlock.acquire(timeout=5)
            if not acquired:
                self._log(f"[{ts}] ❌ {t_name} | تعذّر الحصول على RLock!", "err")
                return
            self._log(f"[{ts}] 🔒 {t_name} | حصل على RLock للتعديل", "sync")

        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            c.execute("""SELECT id, total_amount, paid_amount
                         FROM invoice_payments WHERE invoice_number=?""", (inv_num,))
            row = c.fetchone()

            if not row:
                self.after(0, lambda: messagebox.showwarning(
                    "تنبيه", f"الفاتورة {inv_num} غير موجودة"))
                conn.close()
                return

            inv_id, total, old_paid = row

            if new_paid > total + 0.001:
                self.after(0, lambda t=total: messagebox.showwarning(
                    "تنبيه",
                    f"المبلغ الجديد ({new_paid:.2f}) يتجاوز إجمالي الفاتورة ({t:.2f})!"))
                conn.close()
                return

            new_status = ("paid" if new_paid >= total - 0.001
                          else "partial" if new_paid > 0 else "unpaid")
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                conn.execute("""UPDATE invoice_payments
                                SET paid_amount=?, status=?, last_updated=?
                                WHERE id=?""", (new_paid, new_status, now_str, inv_id))

                # تسجيل التعديل في payments_log مع ملاحظة التعديل وسبب الخيط
                conn.execute("""INSERT INTO payments_log
                    (invoice_id, thread_name, amount, action_type, note, timestamp, sync_mode)
                    VALUES (?,?,?,?,?,?,?)""",
                    (inv_id, t_name, new_paid, "EDIT", note, now_str, mode_str))
                conn.commit()

                ts2 = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self._log(
                    f"[{ts2}] 💾 {t_name} | تعديل ناجح | "
                    f"{old_paid:.2f}→{new_paid:.2f} | ملاحظة: {note}", "ok")

            except Exception as e:
                conn.rollback()
                self._log(f"[{ts}] ❌ {t_name} | Rollback: {e}", "err")
            finally:
                conn.close()

        finally:
            if self._mutex_mode.get():
                self._pay_rlock.release()
                self._log(f"[{ts}] 🔓 {t_name} | حرَّر RLock", "sync")

        self.after(0, self._refresh_table)

    # ─────────────────────────────────────────────────────────────────────────
    # تحديث جدول الفواتير
    # ─────────────────────────────────────────────────────────────────────────
    def _refresh_table(self):
        """تحديث Treeview بأحدث بيانات الفواتير من قاعدة البيانات"""
        for row in self._tree.get_children():
            self._tree.delete(row)
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()
            c.execute("""SELECT invoice_number, total_amount, paid_amount,
                         total_amount - paid_amount, status
                         FROM invoice_payments
                         ORDER BY id DESC""")
            rows = c.fetchall()
            conn.close()

            status_labels = {
                "paid":    "مدفوعة بالكامل ✅",
                "partial": "مدفوعة جزئياً 🟡",
                "unpaid":  "غير مدفوعة ❌",
            }

            for inv_num, total, paid, remaining, status in rows:
                pct = (paid / total * 100) if total > 0 else 0
                pct_str = f"{pct:.1f}%"
                label = status_labels.get(status, status)
                tag = status if status in ("paid", "partial", "unpaid") else "unpaid"
                self._tree.insert("", "end",
                    values=(inv_num,
                            f"{total:.2f}",
                            f"{paid:.2f}",
                            f"{max(remaining, 0):.2f}",
                            label,
                            pct_str),
                    tags=(tag,))
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # مزامنة الفواتير المحفوظة مع نظام المدفوعات
    # ─────────────────────────────────────────────────────────────────────────
    def _sync_invoices_from_main(self):
        """
        تنقل جميع الفواتير الموجودة في جدول invoices الرئيسي
        إلى invoice_payments إذا لم تكن موجودة فيه بعد.
        هذا يحل مشكلة: رقم الفاتورة موجود في الفواتير المحفوظة
        لكن غير موجود عند محاولة تسجيل دفعة عليه.
        """
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()

            # جلب كل الفواتير من الجدول الرئيسي
            c.execute("SELECT invoice_number, total, created_at FROM invoices")
            all_invoices = c.fetchall()

            added = 0
            skipped = 0
            for inv_num, total, created_at in all_invoices:
                # تحقق هل موجودة أصلاً في invoice_payments
                c.execute("SELECT id FROM invoice_payments WHERE invoice_number=?", (inv_num,))
                if c.fetchone():
                    skipped += 1
                    continue
                # أضفها بحالة unpaid
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("""INSERT INTO invoice_payments
                    (invoice_number, total_amount, paid_amount, status, created_at, last_updated)
                    VALUES (?, ?, 0, 'unpaid', ?, ?)""",
                    (inv_num, total, created_at or now_str, now_str))
                added += 1

            conn.commit()
            conn.close()

            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._log(
                f"[{ts}] 🔗 مزامنة: تم نقل {added} فاتورة جديدة | "
                f"{skipped} موجودة مسبقاً", "ok")
            self._refresh_table()

            if added > 0:
                messagebox.showinfo("مزامنة ناجحة",
                    f"✅ تم نقل {added} فاتورة من الفواتير المحفوظة\n"
                    f"يمكنك الآن تسجيل المدفوعات عليها.")
            else:
                messagebox.showinfo("مزامنة",
                    f"✔ جميع الفواتير ({skipped}) مزامَنة مسبقاً.")

        except Exception as e:
            self._log(f"خطأ في المزامنة: {e}", "err")

    # ─────────────────────────────────────────────────────────────────────────
    # إضافة فاتورة تجريبية
    # ─────────────────────────────────────────────────────────────────────────
    def _add_sample_invoice(self):
        """إدراج فاتورة تجريبية في invoice_payments لاختبار النظام"""
        inv_num = f"INV-{random.randint(1000, 9999)}"
        total = round(random.uniform(50, 500), 2)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""INSERT INTO invoice_payments
                (invoice_number, total_amount, paid_amount, status, created_at, last_updated)
                VALUES (?,?,0,'unpaid',?,?)""", (inv_num, total, now_str, now_str))
            conn.commit()
            conn.close()
            self._log(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                      f"➕ فاتورة تجريبية: {inv_num} | إجمالي={total:.2f}", "info")
            self._refresh_table()
        except Exception as e:
            self._log(f"خطأ في الإضافة: {e}", "err")

    # ─────────────────────────────────────────────────────────────────────────
    # فحص تلقائي للفواتير القديمة
    # ─────────────────────────────────────────────────────────────────────────
    def _auto_checker(self):
        """
        Daemon Thread يفحص كل 60 ثانية وجود فواتير تجاوزت 7 أيام بدون دفع كامل.
        اسم الخيط: PaymentChecker
        لا يستخدم قفلاً — عملية قراءة فقط
        """
        while not self._stop_ev.is_set():
            self._stop_ev.wait(timeout=60)
            if self._stop_ev.is_set():
                break
            try:
                cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)
                          ).strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect(DB_PATH, timeout=5)
                conn.execute("PRAGMA journal_mode=WAL")
                c = conn.cursor()
                c.execute("""SELECT COUNT(*) FROM invoice_payments
                             WHERE status != 'paid' AND created_at <= ?""", (cutoff,))
                count = c.fetchone()[0]
                conn.close()
                if count > 0:
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    self.after(0, lambda n=count: self._log(
                        f"[{ts}] ⏰ PaymentChecker: {n} فاتورة متأخرة (>7 أيام)", "warn"))
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # سجل Console
    # ─────────────────────────────────────────────────────────────────────────
    def _log(self, msg: str, tag: str = "info"):
        """إضافة رسالة للـ Console Log بشكل Thread-safe عبر self.after"""
        def _insert():
            self._log_box.config(state="normal")
            self._log_box.insert("end", msg + "\n", tag)
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, _insert)

