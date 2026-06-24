# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (3): جدولة القرص (Disk Scheduling) — "جدولة شاحنات التوصيل"
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# في نظام التشغيل، رأس القرص الصلب (Disk Head) يجب أن يتحرك بين عدة "أسطوانات"
# (Cylinders/Tracks) لخدمة طلبات القراءة/الكتابة، وكل حركة تكلّف وقتاً
# (Seek Time). خوارزميات جدولة القرص تحدد بأي ترتيب نخدم الطلبات لتقليل
# إجمالي حركة الرأس.
#
# في هذه المحاكاة:
#   - "الشارع" المرقَّم من 0 إلى 199 = أسطوانات القرص (Track Numbers).
#   - "طلبات التوصيل" (منازل بأرقام معيّنة على الشارع) = طلبات القرص
#     (Disk Requests).
#   - "الشاحنة" 🚚 وموقعها الحالي = رأس القرص (Disk Head).
#   - "المسافة الكلية التي تقطعها الشاحنة" = إجمالي حركة رأس القرص
#     (Total Head Movement / Seek Time).
#
# الخوارزميات المطبّقة:
#   • FCFS    : تُخدَم الطلبات بترتيب وصولها (بدون أي تحسين).
#   • SSTF    : في كل مرة، تذهب الشاحنة لأقرب منزل لم تُوصِّل له بعد
#               (Shortest Seek Time First).
#   • SCAN    : تتحرك الشاحنة في اتجاه واحد حتى نهاية الشارع وهي توصّل كل
#               الطلبات في طريقها، ثم تعكس الاتجاه وتُكمل الباقي.
#   • C-SCAN  : كـ SCAN، لكن عند الوصول لنهاية الشارع تعود فوراً (بدون توصيل)
#               إلى البداية، ثم تستمر بنفس الاتجاه الأصلي — محاكاة لشارع
#               دائري (Circular Queue).
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import scrolledtext
import random

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)


# ── ثوابت المحاكاة ────────────────────────────────────────────────────────────
MAX_TRACK = 199            # الشارع مرقَّم من 0 إلى 199 (200 منزل)
DEFAULT_HEAD = 100          # موقع الشاحنة الابتدائي (المستودع)
DEFAULT_NUM_REQUESTS = 8    # عدد طلبات التوصيل

DIR_UP   = "up"     # نحو الأرقام الأكبر
DIR_DOWN = "down"   # نحو الأرقام الأصغر

ALG_FCFS  = "FCFS"
ALG_SSTF  = "SSTF"
ALG_SCAN  = "SCAN"
ALG_CSCAN = "C-SCAN"

ALG_COLORS = {
    ALG_FCFS:  "#f85149",
    ALG_SSTF:  "#00e5c3",
    ALG_SCAN:  "#a78bfa",
    ALG_CSCAN: "#ffb454",
}
ALG_LABELS = {
    ALG_FCFS:  "FCFS (ترتيب الوصول)",
    ALG_SSTF:  "SSTF (الأقرب أولاً)",
    ALG_SCAN:  "SCAN (مسح باتجاه واحد)",
    ALG_CSCAN: "C-SCAN (مسح دائري)",
}

NUM_SUBSTEPS = 10   # عدد الإطارات الوسيطة بين كل محطة وأخرى (للأنيميشن السلس)


# ═══════════════════════════════════════════════════════════════════════════════
# توليد طلبات توصيل عشوائية
# ═══════════════════════════════════════════════════════════════════════════════
def generate_requests(count=DEFAULT_NUM_REQUESTS, max_track=MAX_TRACK):
    """يولّد عدداً من طلبات التوصيل (منازل) عشوائية وفريدة على الشارع."""
    count = max(1, min(count, max_track))
    return random.sample(range(0, max_track + 1), count)


# ═══════════════════════════════════════════════════════════════════════════════
# خوارزميات جدولة القرص (Disk Scheduling)
# تُعيد كل خوارزمية: (path, order, total)
#   path  : التسلسل الكامل لحركة الشاحنة (يشمل نقاط نهاية الشارع للقفزات
#           في SCAN / C-SCAN حتى لو لم تكن طلبات فعلية)
#   order : ترتيب توصيل الطلبات الفعلية فقط (للعرض في قائمة "سجل التوصيل")
#   total : إجمالي المسافة المقطوعة (Total Head Movement)
# ═══════════════════════════════════════════════════════════════════════════════
def compute_fcfs(requests, head, max_track=MAX_TRACK):
    """FCFS: تخدم الطلبات بالترتيب الذي وصلت به — بدون أي تحسين."""
    order = list(requests)
    path = [head] + order
    total = sum(abs(path[i] - path[i + 1]) for i in range(len(path) - 1))
    return path, order, total


def compute_sstf(requests, head, max_track=MAX_TRACK):
    """SSTF: في كل خطوة، اختر أقرب طلب متبقٍ للموقع الحالي."""
    remaining = list(requests)
    order = []
    cur = head
    path = [head]
    while remaining:
        nxt = min(remaining, key=lambda r: abs(r - cur))
        order.append(nxt)
        path.append(nxt)
        cur = nxt
        remaining.remove(nxt)
    total = sum(abs(path[i] - path[i + 1]) for i in range(len(path) - 1))
    return path, order, total


def compute_scan(requests, head, max_track=MAX_TRACK, direction=DIR_UP):
    """
    SCAN: تتحرك الشاحنة في اتجاه واحد حتى نهاية الشارع (0 أو max_track)
    خادمة كل الطلبات في طريقها، ثم تعكس الاتجاه وتخدم الباقي.
    """
    sorted_reqs = sorted(requests)
    path = [head]
    order = []

    if direction == DIR_UP:
        higher = [r for r in sorted_reqs if r >= head]
        lower = [r for r in sorted_reqs if r < head]
        # نحو الأعلى حتى نهاية الشارع
        for r in higher:
            path.append(r)
            order.append(r)
        if not higher or higher[-1] != max_track:
            path.append(max_track)
        # ثم نحو الأسفل لخدمة الباقي
        for r in reversed(lower):
            path.append(r)
            order.append(r)
    else:  # DIR_DOWN
        lower = [r for r in sorted_reqs if r <= head]
        higher = [r for r in sorted_reqs if r > head]
        for r in reversed(lower):
            path.append(r)
            order.append(r)
        if not lower or lower[0] != 0:
            path.append(0)
        for r in higher:
            path.append(r)
            order.append(r)

    total = sum(abs(path[i] - path[i + 1]) for i in range(len(path) - 1))
    return path, order, total


def compute_cscan(requests, head, max_track=MAX_TRACK, direction=DIR_UP):
    """
    C-SCAN: كـ SCAN، لكن عند الوصول لنهاية الشارع تعود فوراً (بدون توصيل)
    إلى البداية (الطرف الآخر)، ثم تستمر بنفس الاتجاه الأصلي.
    """
    sorted_reqs = sorted(requests)
    path = [head]
    order = []

    if direction == DIR_UP:
        higher = [r for r in sorted_reqs if r >= head]
        lower = [r for r in sorted_reqs if r < head]
        for r in higher:
            path.append(r)
            order.append(r)
        if not higher or higher[-1] != max_track:
            path.append(max_track)
        # عودة دائرية فورية إلى الطرف الآخر
        path.append(0)
        for r in lower:  # نفس الاتجاه الأصلي (تصاعدي)
            path.append(r)
            order.append(r)
    else:  # DIR_DOWN
        lower = [r for r in sorted_reqs if r <= head]
        higher = [r for r in sorted_reqs if r > head]
        for r in reversed(lower):
            path.append(r)
            order.append(r)
        if not lower or lower[0] != 0:
            path.append(0)
        path.append(max_track)
        for r in reversed(higher):  # نفس الاتجاه الأصلي (تنازلي)
            path.append(r)
            order.append(r)

    total = sum(abs(path[i] - path[i + 1]) for i in range(len(path) - 1))
    return path, order, total


ALG_FUNCS = {
    ALG_FCFS:  compute_fcfs,
    ALG_SSTF:  compute_sstf,
    ALG_SCAN:  compute_scan,
    ALG_CSCAN: compute_cscan,
}


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: جدولة شاحنات التوصيل (Disk Scheduling)
# ═══════════════════════════════════════════════════════════════════════════════
class DiskSchedulingTab(tk.Frame):
    """
    تبويب كامل يعرض:
      - شارع مرقَّم (0-199) مع منازل طلبات التوصيل
      - رسم متحرك لمسار الشاحنة حسب الخوارزمية المختارة
      - رسم بياني لحركة الرأس (Head Movement Graph) عبر الزمن
      - مقارنة المسافة الكلية بين الخوارزميات الأربع
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self.head = DEFAULT_HEAD
        self.requests = generate_requests()

        self.path = []
        self.order = []
        self.total = 0
        self.step_idx = 0       # الفهرس الحالي ضمن path (المحطة السابقة)
        self.substep = 0        # الإطار الوسيط الحالي بين step_idx و step_idx+1
        self.running = False
        self._after_id = None

        self._build_ui()
        self._recompute_current_algo()
        self._render(0, 0)
        self._draw_compare_placeholder()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#1a0a20")
        title_f.pack(fill="x")
        tk.Label(title_f, text="🚚 جدولة شاحنات التوصيل — محاكاة جدولة القرص (Disk Scheduling)",
                 font=("Arial", 13, "bold"), fg="#d2a8ff", bg="#1a0a20").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text="الشارع = أسطوانات القرص (0-199) | الشاحنة = رأس القرص | إجمالي المسافة = Total Head Movement",
                 font=("Arial", 9), fg="#5a3a6a", bg="#1a0a20").pack(side="right", padx=10)

        # ── شريط التحكم 1 ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl_f, text="عدد طلبات التوصيل:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(10, 4), pady=8)
        self.count_var = tk.IntVar(value=DEFAULT_NUM_REQUESTS)
        tk.Spinbox(ctrl_f, from_=4, to=15, textvariable=self.count_var, width=3,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        tk.Label(ctrl_f, text="موقع الشاحنة الحالي (Head):", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(15, 4))
        self.head_var = tk.IntVar(value=DEFAULT_HEAD)
        tk.Spinbox(ctrl_f, from_=0, to=MAX_TRACK, textvariable=self.head_var, width=4,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        self._btn(ctrl_f, "🔀 طلبات جديدة", BLUE, self._on_new_requests).pack(side="right", padx=8)

        tk.Label(ctrl_f, text="اتجاه المسح:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="left", padx=(10, 4))
        self.dir_var = tk.StringVar(value=DIR_UP)
        tk.Radiobutton(ctrl_f, text="⬆ نحو الأرقام الأكبر", variable=self.dir_var, value=DIR_UP,
                       bg=BG2, fg=ACCENT, selectcolor="#1a2a3a", activebackground=BG2,
                       font=("Arial", 9, "bold"), command=self._on_algo_changed).pack(side="left", padx=4)
        tk.Radiobutton(ctrl_f, text="⬇ نحو الأرقام الأصغر", variable=self.dir_var, value=DIR_DOWN,
                       bg=BG2, fg=ACCENT, selectcolor="#1a2a3a", activebackground=BG2,
                       font=("Arial", 9, "bold"), command=self._on_algo_changed).pack(side="left", padx=4)

        # ── شريط التحكم 2 ──
        ctrl_f2 = tk.Frame(self, bg=BG2)
        ctrl_f2.pack(fill="x", padx=10, pady=(0, 5))

        tk.Label(ctrl_f2, text="الخوارزمية:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(10, 4), pady=6)
        self.algo_var = tk.StringVar(value=ALG_FCFS)
        for value in (ALG_FCFS, ALG_SSTF, ALG_SCAN, ALG_CSCAN):
            tk.Radiobutton(
                ctrl_f2, text=ALG_LABELS[value], variable=self.algo_var, value=value,
                bg=BG2, fg=ALG_COLORS[value], selectcolor="#1a2a3a", activebackground=BG2,
                font=("Arial", 9, "bold"), command=self._on_algo_changed
            ).pack(side="right", padx=4)

        tk.Label(ctrl_f2, text="السرعة:", font=("Arial", 9),
                 fg="#8aa8c8", bg=BG2).pack(side="left", padx=(10, 4))
        self.speed_var = tk.DoubleVar(value=0.4)
        tk.Scale(ctrl_f2, from_=0.05, to=1.0, resolution=0.05, variable=self.speed_var,
                 orient="horizontal", bg=BG2, fg=ACCENT, highlightthickness=0,
                 length=120, troughcolor="#1a2a3a").pack(side="left", padx=4)

        self.play_btn = self._btn(ctrl_f2, "▶ تشغيل", GREEN, self._on_play)
        self.play_btn.pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f2, "⏹ إيقاف", RED, self._on_stop).pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f2, "↩ إعادة", "#5a7a9a", self._on_reset).pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f2, "📊 مقارنة الخوارزميات", PURPLE, self._on_compare).pack(side="left", padx=12, pady=4)

        # ── إحصائيات حية ──
        stats_f = tk.Frame(self, bg=BG2)
        stats_f.pack(fill="x", padx=10, pady=5)
        self.dist_var = tk.StringVar(value="0")
        self.pos_var = tk.StringVar(value=str(DEFAULT_HEAD))
        self.step_var = tk.StringVar(value="0 / 0")
        self.delivered_var = tk.StringVar(value="0 / 0")
        for i, (lbl, var, col) in enumerate([
            ("📏 المسافة المقطوعة", self.dist_var, YELLOW),
            ("📍 الموقع الحالي", self.pos_var, ACCENT),
            ("🔢 الخطوة", self.step_var, "#8aa8c8"),
            ("📦 التوصيلات المكتملة", self.delivered_var, GREEN),
        ]):
            fr = tk.Frame(stats_f, bg=BG2)
            fr.grid(row=0, column=i, padx=20, pady=4, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg=BG2, font=("Arial", 10, "bold")).pack()
            tk.Label(fr, textvariable=var, fg=col, bg=BG2, font=("Arial", 18, "bold")).pack()
        for i in range(4):
            stats_f.columnconfigure(i, weight=1)

        # ── المنطقة الرئيسية: الرسم البياني الكبير ──
        main_f = tk.Frame(self, bg=BG2)
        main_f.pack(fill="both", expand=True, padx=10, pady=5)
        self._section_title(main_f, "🛣 الشارع ومسار الشاحنة + رسم حركة الرأس عبر الزمن")
        self.fig, (self.street_ax, self.graph_ax) = plt.subplots(
            2, 1, figsize=(9, 5.2), facecolor=BG2, gridspec_kw={'height_ratios': [1, 2]})
        for ax in (self.street_ax, self.graph_ax):
            ax.set_facecolor(BG2)
            ax.tick_params(colors=FG, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_f)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        # ── منطقة سفلية: السجل + مقارنة الخوارزميات ──
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="both", expand=False, padx=10, pady=(0, 8))

        left_panel = tk.Frame(bottom, bg=BG2, width=420)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._section_title(left_panel, "📋 سجل التوصيل")
        self.log_box = scrolledtext.ScrolledText(
            left_panel, height=9, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("info", "#8aa8c8"), ("ok", GREEN), ("warn", YELLOW), ("scenario", PURPLE)]:
            self.log_box.tag_config(tag, foreground=col)

        right_panel = tk.Frame(bottom, bg=BG2, width=420)
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "📊 مقارنة إجمالي المسافة (Total Head Movement)")
        self.fig_cmp, self.cmp_ax = plt.subplots(figsize=(5, 2.6), facecolor=BG2)
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.cmp_canvas = FigureCanvasTkAgg(self.fig_cmp, master=right_panel)
        self.cmp_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

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
    def _on_new_requests(self):
        self._on_stop()
        self.requests = generate_requests(self.count_var.get())
        self.head = self.head_var.get()
        self._recompute_current_algo()
        self._render(0, 0)
        self._draw_compare_placeholder()
        self._append_log(
            f"🔀 طلبات توصيل جديدة ({len(self.requests)}): {sorted(self.requests)} "
            f"— موقع الشاحنة الحالي: {self.head}", "scenario")

    def _on_algo_changed(self):
        self._on_stop()
        self._recompute_current_algo()
        self._render(0, 0)
        self._append_log(f"تم اختيار الخوارزمية: {ALG_LABELS[self.algo_var.get()]}", "scenario")

    def _on_play(self):
        if self.running:
            return
        if self.step_idx >= len(self.path) - 1:
            self.step_idx = 0
            self.substep = 0
        self.running = True
        self._append_log(f"▶ بدء محاكاة {ALG_LABELS[self.algo_var.get()]}", "scenario")
        self._animate()

    def _on_stop(self):
        self.running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _on_reset(self):
        self._on_stop()
        self.step_idx = 0
        self.substep = 0
        self._render(0, 0)
        self._append_log("↩ إعادة المحاكاة من البداية", "info")

    # ── إعادة حساب نتائج الخوارزمية الحالية ──────────────────────────────────
    def _recompute_current_algo(self):
        self.head = self.head_var.get()
        algo = self.algo_var.get()
        direction = self.dir_var.get()
        func = ALG_FUNCS[algo]
        if algo in (ALG_SCAN, ALG_CSCAN):
            self.path, self.order, self.total = func(self.requests, self.head, MAX_TRACK, direction)
        else:
            self.path, self.order, self.total = func(self.requests, self.head, MAX_TRACK)
        self.step_idx = 0
        self.substep = 0

    # ── حلقة الأنيميشن ────────────────────────────────────────────────────────
    def _animate(self):
        if not self.running:
            return
        if self.step_idx >= len(self.path) - 1:
            self.running = False
            self._append_log(
                f"✅ انتهت كل التوصيلات — المسافة الكلية المقطوعة = {self.total} "
                f"(لـ {ALG_LABELS[self.algo_var.get()]})", "scenario")
            return

        self.substep += 1
        if self.substep > NUM_SUBSTEPS:
            self.substep = 0
            self.step_idx += 1
            # وصلنا لمحطة جديدة — هل هي طلب توصيل فعلي؟
            arrived = self.path[self.step_idx]
            if arrived in self.requests:
                self._append_log(f"📦 تم التوصيل للمنزل رقم {arrived}", "ok")
            elif self.step_idx < len(self.path) - 1 or arrived in (0, MAX_TRACK):
                self._append_log(f"🔁 الشاحنة وصلت لنهاية الشارع عند {arrived} وتغيّر اتجاهها", "warn")

        self._render(self.step_idx, self.substep)

        delay_ms = int(self.speed_var.get() * 1000)
        self._after_id = self.after(max(15, delay_ms), self._animate)

    # ── الموقع الحالي المُتداخل (Interpolated) ───────────────────────────────
    def _current_position(self, step_idx, substep):
        if step_idx >= len(self.path) - 1:
            return self.path[-1]
        a, b = self.path[step_idx], self.path[step_idx + 1]
        frac = substep / NUM_SUBSTEPS
        return a + (b - a) * frac

    # ── الرسم ─────────────────────────────────────────────────────────────────
    def _render(self, step_idx, substep):
        cur_pos = self._current_position(step_idx, substep)

        # ── إحصائيات ──
        traveled = sum(abs(self.path[i] - self.path[i + 1]) for i in range(step_idx))
        if step_idx < len(self.path) - 1:
            traveled += abs(self.path[step_idx + 1] - self.path[step_idx]) * (substep / NUM_SUBSTEPS)
        delivered = sum(1 for p in self.path[1:step_idx + 1] if p in self.requests)

        self.dist_var.set(f"{traveled:.0f}")
        self.pos_var.set(f"{cur_pos:.0f}")
        self.step_var.set(f"{step_idx} / {len(self.path) - 1}")
        self.delivered_var.set(f"{delivered} / {len(self.requests)}")

        # ── رسم "الشارع" ──
        ax = self.street_ax
        ax.clear()
        ax.set_facecolor(BG2)
        ax.set_xlim(-5, MAX_TRACK + 5)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.tick_params(colors=FG, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#1a2a3a")
        ax.axhline(0, color="#3a4a5a", lw=2, zorder=1)

        # نقاط منازل التوصيل
        for r in self.requests:
            delivered_flag = r in self.path[1:step_idx + 1] or (
                r == self.path[step_idx] and substep == 0)
            color = GREEN if delivered_flag else "#d2a8ff"
            ax.scatter([r], [0], s=110, color=color, edgecolors="white",
                       linewidths=1, zorder=3)
            ax.text(r, 0.28, str(r), ha="center", va="bottom",
                   color=FG, fontsize=8, zorder=4)

        # المسار المقطوع حتى الآن
        traveled_path = self.path[:step_idx + 1] + [cur_pos]
        ax.plot(traveled_path, [0] * len(traveled_path), color=YELLOW, lw=2.5,
               alpha=0.8, zorder=2)

        # الشاحنة 🚚
        ax.scatter([cur_pos], [0], s=600, color="#1a2a3a", edgecolors=ACCENT,
                   linewidths=2, zorder=5)
        ax.text(cur_pos, 0, "🚚", ha="center", va="center", fontsize=16, zorder=6)
        ax.text(cur_pos, -0.45, f"{cur_pos:.0f}", ha="center", va="top",
               color=ACCENT, fontsize=9, fontweight="bold", zorder=6)
        ax.set_title("🛣 الشارع (0 → 199) — موقع الشاحنة الحالي ومنازل التوصيل",
                     color=FG, fontsize=9)

        # ── رسم حركة الرأس عبر الزمن ──
        gx = self.graph_ax
        gx.clear()
        gx.set_facecolor(BG2)
        gx.tick_params(colors=FG, labelsize=8)
        for sp in gx.spines.values():
            sp.set_color("#1a2a3a")
        xs = list(range(len(self.path)))
        gx.plot(xs, self.path, color="#3a5a7a", lw=1.5, ls="--", alpha=0.6, zorder=1)

        done_xs = list(range(step_idx + 1)) + [step_idx + (substep / NUM_SUBSTEPS)]
        done_ys = self.path[:step_idx + 1] + [cur_pos]
        gx.plot(done_xs, done_ys, color=ACCENT, lw=2.5, zorder=2)

        for i, p in enumerate(self.path):
            is_req = p in self.requests
            color = GREEN if (is_req and i <= step_idx) else (
                "#d2a8ff" if is_req else "#5a7a9a")
            gx.scatter([i], [p], s=40, color=color, zorder=3)

        gx.scatter([step_idx + (substep / NUM_SUBSTEPS)], [cur_pos], s=120,
                   color="#1a2a3a", edgecolors=ACCENT, linewidths=2, zorder=4)
        gx.set_xlabel("رقم الخطوة", color=FG, fontsize=8)
        gx.set_ylabel("الموقع على الشارع (Track)", color=FG, fontsize=8)
        gx.set_ylim(-5, MAX_TRACK + 5)
        gx.set_title("📈 رسم حركة الرأس (Head Movement) عبر الزمن", color=FG, fontsize=9)

        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ── مقارنة الخوارزميات الأربع ─────────────────────────────────────────────
    def _on_compare(self):
        self._on_stop()
        head = self.head_var.get()
        direction = self.dir_var.get()

        results = {}
        for algo, func in ALG_FUNCS.items():
            if algo in (ALG_SCAN, ALG_CSCAN):
                _, _, total = func(self.requests, head, MAX_TRACK, direction)
            else:
                _, _, total = func(self.requests, head, MAX_TRACK)
            results[algo] = total

        self._draw_compare(results)

        summary = " | ".join(f"{a}: {results[a]}" for a in ALG_FUNCS)
        best = min(results, key=results.get)
        self._append_log(
            f"📊 مقارنة (Head={head}, {len(self.requests)} طلبات): {summary} "
            f"→ الأفضل: {best} ✅", "scenario")

    def _draw_compare_placeholder(self):
        self.cmp_ax.clear()
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.cmp_ax.text(0.5, 0.5, "اضغط 'مقارنة الخوارزميات' لعرض النتائج",
                         ha="center", va="center", color="#5a7a9a",
                         fontsize=9, transform=self.cmp_ax.transAxes)
        self.cmp_ax.set_xticks([])
        self.cmp_ax.set_yticks([])
        self.cmp_canvas.draw_idle()

    def _draw_compare(self, results):
        self.cmp_ax.clear()
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")

        algos = [ALG_FCFS, ALG_SSTF, ALG_SCAN, ALG_CSCAN]
        totals = [results[a] for a in algos]
        colors = [ALG_COLORS[a] for a in algos]
        bars = self.cmp_ax.bar(algos, totals, color=colors)
        for b, t in zip(bars, totals):
            self.cmp_ax.text(b.get_x() + b.get_width() / 2, t + max(totals) * 0.02,
                             str(t), ha="center", color=FG, fontsize=9, fontweight="bold")
        self.cmp_ax.set_title("إجمالي المسافة المقطوعة (Total Head Movement)", color=FG, fontsize=9)
        self.fig_cmp.tight_layout()
        self.cmp_canvas.draw_idle()
