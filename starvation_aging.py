# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (7): Starvation & Aging — طابور أولوية خدمة الزبائن
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# في جدولة العمليات (Process Scheduling) باستخدام Priority Queue، قد تحدث
# مشكلة "Starvation" (التجويع): إذا استمر وصول عمليات/عملاء بأولوية أعلى
# باستمرار، فإن العملية/العميل ذو الأولوية المنخفضة قد لا يُخدَم *أبداً*،
# لأنه يُؤجَّل في كل مرة لصالح القادم الجديد الأعلى أولوية.
#
# الحل الكلاسيكي: Aging (الشيخوخة) — كل ما طال انتظار عنصر في الطابور،
# "تتحسّن" أولويته الفعلية تدريجياً، حتى يتجاوز في النهاية العناصر الأحدث
# الأعلى أولوية → يُضمَن خدمته (No Starvation).
#
# هذا التبويب يستخدم AgingPriorityItem / AgingPriorityQueue (الإضافة الجديدة
# في core.py، والتي تبني على PriorityItem / PriorityQueue الأصليين دون أي
# تعديل عليهما) لمحاكاة:
#
#   - 🙋 "عميل ذو أولوية منخفضة" يصل أولاً (Priority = 4).
#   - 🚨 تيار مستمر من "عملاء VIP / طلبات عاجلة" (Priority = 0-2) يصلون
#     تباعاً للطابور.
#   - خادم (Thread) يُخرج من الطابور العنصر الأعلى أولوية (فعلياً) ويخدمه.
#
# مع تبديل "تفعيل/تعطيل Aging"، نشاهد:
#   - بدون Aging  → العميل ذو الأولوية المنخفضة يبقى عالقاً (Starvation).
#   - مع Aging    → أولويته الفعلية تتحسّن مع وقت الانتظار حتى يُخدَم.
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import random
import queue as pyqueue

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)
from core import AgingPriorityQueue


# ── ثوابت ─────────────────────────────────────────────────────────────────────
STUDY_PRIORITY = 4          # أولوية "العميل ذو الأولوية المنخفضة"
HIGH_PRIORITIES = [0, 1, 2]  # أولويات عملاء VIP / الطلبات العاجلة المستمرة
DEFAULT_AGING_RATE = 0.5     # مقدار تحسّن الأولوية الفعلية لكل ثانية انتظار
ARRIVAL_DELAY = (0.2, 0.4)   # فترة وصول عملاء VIP جدد (ثانية) — أسرع من الخدمة
SERVICE_DELAY = 0.5          # وقت "خدمة" كل عميل (ثانية)
SERVER_WARMUP_SEC = 2.0      # فترة انتظار الخادم قبل بدء الخدمة (لتجمّع VIP أولاً)
MAX_WAIT_NO_AGING = 20.0     # الحد الأقصى للانتظار في وضع المقارنة بدون Aging

PRIORITY_LABELS = {
    0: "🚨 عاجل جداً",
    1: "🔴 عالية",
    2: "🟠 متوسطة",
    3: "🟡 منخفضة",
    4: "🔵 منخفضة جداً",
}
PRIORITY_COLORS = {
    0: "#f85149",
    1: "#ff9800",
    2: "#d29922",
    3: "#79c0ff",
    4: "#a78bfa",
}


# ═══════════════════════════════════════════════════════════════════════════════
# محاكاة Starvation & Aging
# ═══════════════════════════════════════════════════════════════════════════════
class StarvationSimulation:
    """
    يشغّل AgingPriorityQueue مع:
      - عميل واحد ذو أولوية منخفضة (يُضاف عند البدء فقط).
      - تيار مستمر من عملاء VIP (أولوية 0-2) يصلون تباعاً.
      - خادم (Thread) يخدم دائماً العنصر الأعلى أولوية فعلياً.
    """

    def __init__(self, log_cb=None):
        self.log_cb = log_cb or (lambda *a, **k: None)
        self.queue = AgingPriorityQueue()
        self.aging_enabled = False
        self.aging_rate = DEFAULT_AGING_RATE
        self.running = False
        self.stop_event = threading.Event()
        self.study_start_time = None
        self.study_served_time = None
        self.served_count = 0
        self.next_id = 1
        self._lock = threading.Lock()

    def start(self, aging_enabled, aging_rate=DEFAULT_AGING_RATE, max_wait=None, label_prefix=""):
        if self.running:
            return
        self.aging_enabled = aging_enabled
        self.aging_rate = aging_rate
        self.max_wait = max_wait
        self.label_prefix = label_prefix
        self.stop_event.clear()
        self.running = True
        self.study_start_time = time.time()
        self.study_served_time = None
        self.served_count = 0
        self.next_id = 1
        self.queue = AgingPriorityQueue()

        # العميل ذو الأولوية المنخفضة — يصل أولاً
        self.queue.put_with_aging(
            {"id": 0, "label": "🙋 العميل ذو الأولوية المنخفضة", "priority": STUDY_PRIORITY,
             "is_study": True},
            priority=STUDY_PRIORITY, aging_rate=self.aging_rate)

        mode = "🟢 مع Aging (الحل)" if aging_enabled else "🔴 بدون Aging (المشكلة)"
        self.log_cb(f"{label_prefix}▶ بدأت المحاكاة — {mode}", "scenario")

        threading.Thread(target=self._arrival_loop, daemon=True,
                         name="StarvationArrival").start()
        threading.Thread(target=self._server_loop, daemon=True,
                         name="StarvationServer").start()

    def stop(self):
        self.stop_event.set()
        self.running = False

    def _arrival_loop(self):
        while not self.stop_event.is_set():
            time.sleep(random.uniform(*ARRIVAL_DELAY))
            if self.stop_event.is_set():
                break
            with self._lock:
                cid = self.next_id
                self.next_id += 1
            pr = random.choice(HIGH_PRIORITIES)
            label = f"{PRIORITY_LABELS[pr]} — طلب #{cid}"
            self.queue.put_with_aging(
                {"id": cid, "label": label, "priority": pr, "is_study": False},
                priority=pr, aging_rate=self.aging_rate)
            self.log_cb(f"{self.label_prefix}➕ وصل {label} إلى الطابور", "info")

    def _server_loop(self):
        # ── فترة بدء (Warmup) ──
        # ننتظر قليلاً قبل أن يبدأ الخادم بالخدمة، حتى يتجمّع عدد كافٍ من
        # عملاء VIP في الطابور أولاً. بدون هذا الانتظار، الخادم قد يأخذ
        # العميل ذو الأولوية المنخفضة فوراً (لأنه الوحيد في الطابور في
        # اللحظة الأولى) فلا تظهر مشكلة Starvation أساساً.
        warmup_end = time.time() + SERVER_WARMUP_SEC
        while time.time() < warmup_end and not self.stop_event.is_set():
            time.sleep(0.05)

        while not self.stop_event.is_set():
            try:
                item = self.queue.get_with_aging(aging_enabled=self.aging_enabled, timeout=0.3)
            except pyqueue.Empty:
                # تحقّق من الحد الأقصى للانتظار (لوضع المقارنة)
                if self.max_wait is not None:
                    elapsed = time.time() - self.study_start_time
                    if elapsed >= self.max_wait:
                        self.log_cb(
                            f"{self.label_prefix}⏰ انتهى الوقت المحدد ({self.max_wait:.0f}s) "
                            f"بدون خدمة العميل ذو الأولوية المنخفضة → Starvation!", "err")
                        self.study_served_time = self.max_wait
                        self.stop_event.set()
                        self.running = False
                continue

            cust = item.item
            with self._lock:
                self.served_count += 1
            time.sleep(SERVICE_DELAY)  # محاكاة وقت الخدمة

            if cust["is_study"]:
                self.study_served_time = time.time() - self.study_start_time
                self.log_cb(
                    f"{self.label_prefix}🎉 تمت خدمة العميل ذو الأولوية المنخفضة "
                    f"بعد {self.study_served_time:.1f} ثانية!", "ok")
                self.stop_event.set()
                self.running = False
            else:
                self.log_cb(f"{self.label_prefix}✅ تمت خدمة {cust['label']}", "ok")

            # تحقّق من الحد الأقصى للانتظار حتى لو لم تكن الطابور خالية
            if self.max_wait is not None and not self.stop_event.is_set():
                elapsed = time.time() - self.study_start_time
                if elapsed >= self.max_wait:
                    self.log_cb(
                        f"{self.label_prefix}⏰ انتهى الوقت المحدد ({self.max_wait:.0f}s) "
                        f"بدون خدمة العميل ذو الأولوية المنخفضة → Starvation!", "err")
                    self.study_served_time = self.max_wait
                    self.stop_event.set()
                    self.running = False

    # ── لقطة حالة حالية ───────────────────────────────────────────────────────
    def snapshot(self):
        items = self.queue.snapshot_with_effective_priorities(self.aging_enabled)
        items.sort(key=lambda d: (d["effective_priority"],
                                   -d["waited"] if self.aging_enabled else 0))
        study_waited = None
        if self.study_start_time is not None:
            if self.study_served_time is not None:
                study_waited = self.study_served_time
            else:
                study_waited = time.time() - self.study_start_time
        return {
            "queue_items": items,
            "served_count": self.served_count,
            "study_waited": study_waited,
            "study_served": self.study_served_time is not None,
            "running": self.running,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: Starvation & Aging
# ═══════════════════════════════════════════════════════════════════════════════
class StarvationAgingTab(tk.Frame):
    """
    تبويب يعرض طابور أولوية خدمة الزبائن مع/بدون Aging، ويقارن وقت انتظار
    العميل ذو الأولوية المنخفضة في الحالتين.
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self.sim = StarvationSimulation(
            log_cb=lambda m, t="info": self._log_queue.put((m, t)))
        self._log_queue = pyqueue.Queue()

        # للمقارنة
        self.compare_running = False
        self.compare_results = {}

        self._build_ui()
        self._draw_compare_placeholder()
        self._tick()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#2a0a1a")
        title_f.pack(fill="x")
        tk.Label(title_f, text="⏳ Starvation & Aging — طابور أولوية خدمة الزبائن",
                 font=("Arial", 13, "bold"), fg="#ffb454", bg="#2a0a1a").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text="عميل ذو أولوية منخفضة يصل أولاً، وتيار مستمر من عملاء VIP "
                      "— هل سيُخدَم العميل أبداً بدون Aging؟",
                 font=("Arial", 9), fg="#5a2a3a", bg="#2a0a1a").pack(side="right", padx=10)

        # ── شريط التحكم ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=5)

        self.aging_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl_f, text="🕰 تفعيل Aging (الحل)", variable=self.aging_var,
                      bg=BG2, fg=GREEN, selectcolor="#1a2a3a", activebackground=BG2,
                      font=("Arial", 11, "bold")).pack(side="right", padx=10, pady=6)

        tk.Label(ctrl_f, text="معدّل Aging (لكل ثانية انتظار):", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(15, 4))
        self.aging_rate_var = tk.DoubleVar(value=DEFAULT_AGING_RATE)
        tk.Spinbox(ctrl_f, from_=0.1, to=2.0, increment=0.1, textvariable=self.aging_rate_var,
                   width=4, font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        self.play_btn = self._btn(ctrl_f, "▶ بدء المحاكاة", GREEN, self._on_start)
        self.play_btn.pack(side="left", padx=4, pady=4)
        self.stop_btn = self._btn(ctrl_f, "⏹ إيقاف", RED, self._on_stop)
        self.stop_btn.pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f, "↩ إعادة", "#5a7a9a", self._on_reset).pack(side="left", padx=4, pady=4)
        self.compare_btn = self._btn(ctrl_f, "📊 قارن: بدون Aging مقابل مع Aging", PURPLE, self._on_compare)
        self.compare_btn.pack(side="left", padx=12, pady=4)

        self.status_var = tk.StringVar(value="جاهز")
        tk.Label(ctrl_f, textvariable=self.status_var, font=("Arial", 10, "bold"),
                 fg=YELLOW, bg=BG2).pack(side="left", padx=10)

        # ── إحصائيات حية ──
        stats_f = tk.Frame(self, bg=BG2)
        stats_f.pack(fill="x", padx=10, pady=5)
        self.wait_var = tk.StringVar(value="0.0s")
        self.served_var = tk.StringVar(value="0")
        self.qsize_var = tk.StringVar(value="0")
        self.study_status_var = tk.StringVar(value="⏳ في الانتظار")
        self.study_status_lbl = None
        for i, (lbl, var, col) in enumerate([
            ("🙋 حالة العميل ذو الأولوية المنخفضة", self.study_status_var, "#a78bfa"),
            ("⏱ وقت انتظاره", self.wait_var, YELLOW),
            ("✅ عملاء تمت خدمتهم", self.served_var, GREEN),
            ("📥 في الطابور الآن", self.qsize_var, ACCENT),
        ]):
            fr = tk.Frame(stats_f, bg=BG2)
            fr.grid(row=0, column=i, padx=20, pady=4, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg=BG2, font=("Arial", 10, "bold")).pack()
            var_lbl = tk.Label(fr, textvariable=var, fg=col, bg=BG2, font=("Arial", 16, "bold"))
            var_lbl.pack()
            if i == 0:
                self.study_status_lbl = var_lbl
        for i in range(4):
            stats_f.columnconfigure(i, weight=1)

        # ── المنطقة الرئيسية ──
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        left_panel = tk.Frame(mid, bg=BG2)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._section_title(left_panel, "📥 طابور الانتظار (مرتّب حسب الأولوية الفعلية)")

        style = ttk.Style()
        style.configure("Starve.Treeview", background="#1a2a3a", foreground="#c9d1d9",
                        fieldbackground="#1a2a3a", font=("Arial", 10), rowheight=26)
        style.configure("Starve.Treeview.Heading", background="#0d1a2a", foreground="#00e5c3",
                        font=("Arial", 10, "bold"))
        style.map("Starve.Treeview", background=[("selected", "#1f6feb")])

        cols = ("rank", "label", "orig", "eff", "waited")
        headers = {
            "rank": ("الترتيب", 60),
            "label": ("العميل / الطلب", 240),
            "orig": ("الأولوية الأصلية", 120),
            "eff": ("الأولوية الفعلية", 120),
            "waited": ("وقت الانتظار (s)", 110),
        }
        self.tree = ttk.Treeview(left_panel, columns=cols, show="headings",
                                  height=14, style="Starve.Treeview")
        for c in cols:
            label, width = headers[c]
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=5)
        self.tree.tag_configure("study", foreground="#a78bfa", font=("Arial", 10, "bold"))
        self.tree.tag_configure("normal", foreground=FG)

        right_panel = tk.Frame(mid, bg=BG2, width=420)
        right_panel.pack(side="right", fill="both", padx=(5, 0))
        right_panel.pack_propagate(False)

        self._section_title(right_panel, "📈 الأولوية الفعلية للعميل عبر الزمن")
        self.fig_eff, self.ax_eff = plt.subplots(figsize=(5, 2.6), facecolor=BG2)
        self.ax_eff.set_facecolor(BG2)
        self.ax_eff.tick_params(colors=FG, labelsize=8)
        for sp in self.ax_eff.spines.values():
            sp.set_color("#1a2a3a")
        self.canvas_eff = FigureCanvasTkAgg(self.fig_eff, master=right_panel)
        self.canvas_eff.get_tk_widget().pack(fill="both", expand=False, padx=8, pady=5)
        self.eff_history = []   # (t, effective_priority)

        self._section_title(right_panel, "📊 مقارنة وقت الانتظار: بدون Aging مقابل مع Aging")
        self.fig_cmp, self.cmp_ax = plt.subplots(figsize=(5, 2.6), facecolor=BG2)
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.cmp_canvas = FigureCanvasTkAgg(self.fig_cmp, master=right_panel)
        self.cmp_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        # ── السجل ──
        self._section_title(self, "📋 سجل الطابور (وصول / خدمة)")
        self.log_box = scrolledtext.ScrolledText(
            self, height=8, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=False, padx=10, pady=(0, 8))
        for tag, col in [("info", "#8aa8c8"), ("ok", GREEN), ("err", RED),
                          ("warn", YELLOW), ("scenario", PURPLE)]:
            self.log_box.tag_config(tag, foreground=col)

    # ── أدوات مساعدة للستايل ─────────────────────────────────────────────────
    def _btn(self, parent, text, color, cmd, size=10):
        return tk.Button(parent, text=text, font=("Arial", size, "bold"),
                         bg=color, fg="white", activebackground=color,
                         relief="flat", bd=0, padx=10, pady=6,
                         cursor="hand2", command=cmd)

    def _section_title(self, parent, text):
        bg = BG
        try:
            bg = parent.cget("bg")
        except Exception:
            pass
        tk.Label(parent, text=text, font=("Arial", 11, "bold"),
                 fg=FG, bg=bg).pack(pady=(8, 4))

    def _append_log(self, msg, tag="info"):
        _styled_log(self.log_box, f"[{_ts()}] {msg}", tag)

    # ── أوامر التحكم ──────────────────────────────────────────────────────────
    def _on_start(self):
        if self.sim.running or self.compare_running:
            return
        self.eff_history = []
        aging = self.aging_var.get()
        rate = self.aging_rate_var.get()
        self.sim.start(aging_enabled=aging, aging_rate=rate, max_wait=None)
        self.status_var.set(f"⏳ يعمل — {'مع Aging' if aging else 'بدون Aging'}")

    def _on_stop(self):
        self.sim.stop()
        self.status_var.set("⏹ متوقف")

    def _on_reset(self):
        self.sim.stop()
        self.eff_history = []
        self.tree.delete(*self.tree.get_children())
        self.wait_var.set("0.0s")
        self.served_var.set("0")
        self.qsize_var.set("0")
        self.study_status_var.set("⏳ في الانتظار")
        self.study_status_lbl.config(fg="#a78bfa")
        self.status_var.set("جاهز")
        self._draw_eff_chart()

    # ── المقارنة ──────────────────────────────────────────────────────────────
    def _on_compare(self):
        if self.sim.running or self.compare_running:
            return
        rate = self.aging_rate_var.get()
        self.compare_running = True
        self.compare_results = {}
        self.compare_btn.config(state="disabled")
        self.play_btn.config(state="disabled")
        self.status_var.set("⏳ تشغيل المقارنة (بدون Aging أولاً)...")
        self._append_log("📊 بدء مقارنة شاملة: بدون Aging ثم مع Aging", "scenario")

        threading.Thread(target=self._compare_worker, args=(rate,), daemon=True).start()

    def _compare_worker(self, rate):
        # 1) بدون Aging — حتى MAX_WAIT_NO_AGING
        sim1 = StarvationSimulation(log_cb=lambda m, t="info": self._log_queue.put((m, t)))
        self.sim = sim1
        sim1.start(aging_enabled=False, aging_rate=rate,
                   max_wait=MAX_WAIT_NO_AGING, label_prefix="[بدون Aging] ")
        while sim1.running:
            time.sleep(0.2)
        self.compare_results["no_aging"] = sim1.study_served_time

        time.sleep(0.5)

        # 2) مع Aging
        sim2 = StarvationSimulation(log_cb=lambda m, t="info": self._log_queue.put((m, t)))
        self.sim = sim2
        self._log_queue.put(("⏳ الآن: مع Aging...", "scenario"))
        sim2.start(aging_enabled=True, aging_rate=rate,
                   max_wait=MAX_WAIT_NO_AGING * 2, label_prefix="[مع Aging] ")
        while sim2.running:
            time.sleep(0.2)
        self.compare_results["aging"] = sim2.study_served_time

        self._log_queue.put(("__compare_done__", "internal"))

    # ── حلقة التحديث ──────────────────────────────────────────────────────────
    def _tick(self):
        # تفريغ السجل
        while True:
            try:
                msg, tag = self._log_queue.get_nowait()
            except pyqueue.Empty:
                break
            if msg == "__compare_done__":
                self._finish_compare()
                continue
            self._append_log(msg, tag)

        snap = self.sim.snapshot()

        # ── تحديث الجدول ──
        self.tree.delete(*self.tree.get_children())
        study_eff = None
        for i, it in enumerate(snap["queue_items"], start=1):
            cust = it["item"]
            tag = "study" if cust["is_study"] else "normal"
            orig_label = f"{it['original_priority']} — {PRIORITY_LABELS.get(it['original_priority'], '')}"
            self.tree.insert("", "end", values=(
                i, cust["label"], orig_label,
                f"{it['effective_priority']:.2f}", f"{it['waited']:.1f}"
            ), tags=(tag,))
            if cust["is_study"]:
                study_eff = it["effective_priority"]

        # ── الإحصائيات ──
        self.qsize_var.set(str(len(snap["queue_items"])))
        self.served_var.set(str(snap["served_count"]))
        if snap["study_waited"] is not None:
            self.wait_var.set(f"{snap['study_waited']:.1f}s")
        if snap["study_served"]:
            if self.sim.study_served_time == MAX_WAIT_NO_AGING and not self.sim.aging_enabled:
                self.study_status_var.set("☠ تجويع (Starvation)!")
                self.study_status_lbl.config(fg=RED)
            else:
                self.study_status_var.set("🎉 تمت خدمته!")
                self.study_status_lbl.config(fg=GREEN)
            if not self.sim.running and not self.compare_running:
                self.status_var.set("✅ انتهت المحاكاة")
        elif snap["running"]:
            self.study_status_var.set("⏳ في الانتظار")
            self.study_status_lbl.config(fg="#a78bfa")

        # ── رسم تطور الأولوية الفعلية ──
        if study_eff is not None and snap["running"]:
            t = snap["study_waited"] or 0
            self.eff_history.append((t, study_eff))
            if len(self.eff_history) > 200:
                self.eff_history.pop(0)
        self._draw_eff_chart()

        self.after(250, self._tick)

    def _finish_compare(self):
        self.compare_running = False
        self.compare_btn.config(state="normal")
        self.play_btn.config(state="normal")
        self.status_var.set("✅ انتهت المقارنة")

        no_aging = self.compare_results.get("no_aging")
        aging = self.compare_results.get("aging")
        self._draw_compare(no_aging, aging)

        if no_aging is not None and aging is not None:
            self._append_log(
                f"📊 النتيجة: بدون Aging = {no_aging:.1f}s "
                f"{'(تجويع! لم يُخدَم)' if no_aging >= MAX_WAIT_NO_AGING else ''} "
                f"| مع Aging = {aging:.1f}s (تمت خدمته)", "scenario")
            self._append_log(
                "🔎 الخلاصة: Aging يضمن عدم تجويع العناصر منخفضة الأولوية، "
                "عن طريق رفع أولويتها الفعلية تدريجياً مع وقت الانتظار حتى "
                "تتجاوز العناصر الأحدث الأعلى أولوية.", "scenario")

    # ── رسم تطور الأولوية الفعلية ─────────────────────────────────────────────
    def _draw_eff_chart(self):
        self.ax_eff.clear()
        self.ax_eff.set_facecolor(BG2)
        self.ax_eff.tick_params(colors=FG, labelsize=8)
        for sp in self.ax_eff.spines.values():
            sp.set_color("#1a2a3a")

        if not self.eff_history:
            self.ax_eff.text(0.5, 0.5, "ابدأ المحاكاة لعرض تطور الأولوية",
                            ha="center", va="center", color="#5a7a9a",
                            fontsize=9, transform=self.ax_eff.transAxes)
            self.ax_eff.set_xticks([])
            self.ax_eff.set_yticks([])
        else:
            xs = [p[0] for p in self.eff_history]
            ys = [p[1] for p in self.eff_history]
            self.ax_eff.plot(xs, ys, color="#a78bfa", lw=2)
            self.ax_eff.axhline(0, color=PRIORITY_COLORS[0], lw=1, ls="--", alpha=0.6)
            self.ax_eff.fill_between(xs, ys, color="#a78bfa", alpha=0.2)
            self.ax_eff.set_xlabel("وقت الانتظار (s)", color=FG, fontsize=8)
            self.ax_eff.set_ylabel("الأولوية الفعلية", color=FG, fontsize=8)
            self.ax_eff.set_title(
                "أولوية أصلية = 4 → كل ما طال الانتظار اقتربت من 0 (VIP)"
                if self.sim.aging_enabled else
                "بدون Aging: الأولوية تبقى ثابتة عند 4 إلى الأبد",
                color=FG, fontsize=9)

        self.fig_eff.tight_layout()
        self.canvas_eff.draw_idle()

    # ── رسم مقارنة وقت الانتظار ───────────────────────────────────────────────
    def _draw_compare_placeholder(self):
        self.cmp_ax.clear()
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.cmp_ax.text(0.5, 0.5, "اضغط 'قارن: بدون Aging مقابل مع Aging'",
                         ha="center", va="center", color="#5a7a9a",
                         fontsize=9, transform=self.cmp_ax.transAxes)
        self.cmp_ax.set_xticks([])
        self.cmp_ax.set_yticks([])
        self.cmp_canvas.draw_idle()

    def _draw_compare(self, no_aging, aging):
        self.cmp_ax.clear()
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")

        labels = ["بدون Aging", "مع Aging"]
        values = [no_aging or 0, aging or 0]
        colors = [RED, GREEN]
        bars = self.cmp_ax.bar(labels, values, color=colors)
        for b, v, no_age in zip(bars, values, [no_aging, aging]):
            txt = f"{v:.1f}s"
            if no_age == MAX_WAIT_NO_AGING:
                txt += "+ (Starvation)"
            self.cmp_ax.text(b.get_x() + b.get_width() / 2, v + max(values) * 0.02,
                             txt, ha="center", color=FG, fontsize=9, fontweight="bold")
        self.cmp_ax.set_ylabel("وقت انتظار العميل (s)", color=FG, fontsize=8)
        self.cmp_ax.set_title("وقت انتظار العميل ذو الأولوية المنخفضة حتى الخدمة", color=FG, fontsize=9)
        self.fig_cmp.tight_layout()
        self.cmp_canvas.draw_idle()

    # ── إيقاف (يُستدعى عند إغلاق التطبيق) ─────────────────────────────────────
    def stop(self):
        self.sim.stop()
