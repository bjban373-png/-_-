# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (2): محاكاة إدارة الذاكرة (Paging) — "مدير تخزين الرفوف"
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# في نظام التشغيل، الذاكرة الفعلية (Physical Memory) مقسّمة إلى "إطارات"
# (Frames) محدودة العدد، والبرنامج يحتاج صفحات (Pages) أكثر من عدد الإطارات
# المتاحة → عند طلب صفحة غير موجودة في الذاكرة يحدث Page Fault، فتقوم
# خوارزمية استبدال الصفحات (Page Replacement) باختيار صفحة لإخراجها وإحضار
# الصفحة المطلوبة بدلاً منها.
#
# في هذه المحاكاة:
#   - كل "رف عرض" في السوبر ماركت = صفحة ذاكرة (Page) — منتج/قسم معيّن.
#   - "الرفوف المتاحة أمام الزبون" = الإطارات (Frames) في الذاكرة الفعلية.
#   - "سلسلة طلبات الزبائن" = Reference String (تسلسل الوصول للصفحات).
#   - إذا كان المنتج المطلوب موجوداً على الرفوف الحالي → Hit (لا تكلفة).
#   - إذا لم يكن موجوداً → Page Fault → يجب إخراج منتج آخر من الرفوف لإحضاره
#     (تكلفة عالية — مثل القراءة من القرص في نظام التشغيل الحقيقي).
#
# الخوارزميات المطبّقة:
#   • FIFO     : يُخرج أقدم منتج تم وضعه على الرفوف (بدون اعتبار للاستخدام).
#   • LRU      : يُخرج المنتج الذي لم يُطلب منذ أطول فترة (Least Recently Used).
#   • Optimal  : يُخرج المنتج الذي لن يُطلب لأطول فترة في المستقبل (أفضل
#                خوارزمية نظرياً — تُستخدم كمعيار مقارنة فقط، لأنها تحتاج
#                معرفة المستقبل، وهو غير متاح في الأنظمة الحقيقية).
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
# أقسام/منتجات السوبر ماركت — كل واحد منها "صفحة ذاكرة"
PAGES = [
    ("🥖", "خبز ومخبوزات"),
    ("🥛", "ألبان وأجبان"),
    ("🍎", "فواكه وخضار"),
    ("🥩", "لحوم ودجاج"),
    ("🧃", "عصائر ومشروبات"),
    ("🍫", "حلويات وشوكولاتة"),
    ("🧴", "منتجات تنظيف"),
    ("❄️", "مجمدات"),
]
NUM_PAGE_TYPES = len(PAGES)

DEFAULT_FRAMES = 3
DEFAULT_REF_LEN = 20

ALG_FIFO    = "FIFO"
ALG_LRU     = "LRU"
ALG_OPTIMAL = "OPTIMAL"

ALG_COLORS = {
    ALG_FIFO:    "#f85149",
    ALG_LRU:     "#00e5c3",
    ALG_OPTIMAL: "#a78bfa",
}
ALG_LABELS = {
    ALG_FIFO:    "FIFO (الأقدم أولاً)",
    ALG_LRU:     "LRU (الأقل استخداماً)",
    ALG_OPTIMAL: "Optimal (الأمثل النظري)",
}


# ═══════════════════════════════════════════════════════════════════════════════
# توليد سلسلة طلبات الزبائن (Reference String) مع "Locality" واقعية
# ═══════════════════════════════════════════════════════════════════════════════
def generate_reference_string(length=DEFAULT_REF_LEN, num_pages=NUM_PAGE_TYPES,
                               locality_size=3, jump_prob=0.25):
    """
    يولّد تسلسل طلبات يحاكي سلوك زبون حقيقي: يتجوّل غالباً بين 2-3 أقسام
    متقاربة (Locality of Reference)، ومن وقت لآخر "يقفز" لقسم بعيد جديد
    (jump_prob). هذا يُظهر فروقاً واضحة بين أداء FIFO و LRU و Optimal.
    """
    locality_size = max(1, min(locality_size, num_pages))
    seq = []
    working_set = random.sample(range(num_pages), locality_size)
    for _ in range(length):
        if random.random() < jump_prob:
            working_set = random.sample(range(num_pages), locality_size)
        seq.append(random.choice(working_set))
    return seq


# ═══════════════════════════════════════════════════════════════════════════════
# خوارزميات استبدال الصفحات
# ═══════════════════════════════════════════════════════════════════════════════
def run_fifo(num_frames, ref_string):
    """
    FIFO: عند الحاجة لإخراج صفحة، نخرج أقدم صفحة دخلت إلى الذاكرة
    (بدون أي اعتبار لمدى استخدامها مؤخراً).
    """
    frames = []   # ترتيب الدخول (الأقدم في المقدمة)
    steps = []
    faults = 0
    for page in ref_string:
        fault = False
        evicted = None
        if page not in frames:
            fault = True
            faults += 1
            if len(frames) >= num_frames:
                evicted = frames.pop(0)
            frames.append(page)
        steps.append({
            "page": page, "frames": list(frames),
            "fault": fault, "evicted": evicted, "fault_count": faults,
        })
    return steps, faults


def run_lru(num_frames, ref_string):
    """
    LRU: عند الحاجة لإخراج صفحة، نخرج الصفحة التي لم تُستخدم منذ أطول وقت.
    نُحافظ على ترتيب "آخر استخدام" — كل وصول (Hit أو إدخال جديد) يضع الصفحة
    في آخر القائمة (الأحدث استخداماً)، فتبقى الصفحة الأقدم استخداماً في المقدمة.
    """
    frames = []   # ترتيب الاستخدام (الأقل استخداماً في المقدمة)
    steps = []
    faults = 0
    for page in ref_string:
        fault = False
        evicted = None
        if page in frames:
            frames.remove(page)
            frames.append(page)
        else:
            fault = True
            faults += 1
            if len(frames) >= num_frames:
                evicted = frames.pop(0)
            frames.append(page)
        steps.append({
            "page": page, "frames": list(frames),
            "fault": fault, "evicted": evicted, "fault_count": faults,
        })
    return steps, faults


def run_optimal(num_frames, ref_string):
    """
    Optimal (Belady): عند الحاجة لإخراج صفحة، نخرج الصفحة التي لن تُستخدم
    لأطول فترة في المستقبل (أو لن تُستخدم أبداً مرة أخرى). تحتاج معرفة
    كامل التسلسل مسبقاً — غير قابلة للتطبيق عملياً، تُستخدم فقط كحدّ أعلى
    نظري للمقارنة (Lower Bound لعدد Page Faults).
    """
    frames = []
    steps = []
    faults = 0
    for i, page in enumerate(ref_string):
        fault = False
        evicted = None
        if page not in frames:
            fault = True
            faults += 1
            if len(frames) >= num_frames:
                future = ref_string[i + 1:]
                victim = frames[0]
                farthest = -1
                for f in frames:
                    if f not in future:
                        victim = f
                        break
                    idx = future.index(f)
                    if idx > farthest:
                        farthest = idx
                        victim = f
                evicted = victim
                frames.remove(victim)
            frames.append(page)
        steps.append({
            "page": page, "frames": list(frames),
            "fault": fault, "evicted": evicted, "fault_count": faults,
        })
    return steps, faults


ALG_FUNCS = {
    ALG_FIFO:    run_fifo,
    ALG_LRU:     run_lru,
    ALG_OPTIMAL: run_optimal,
}


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: مدير تخزين الرفوف (Paging)
# ═══════════════════════════════════════════════════════════════════════════════
class PagingTab(tk.Frame):
    """
    تبويب كامل يعرض:
      - سلسلة طلبات الزبائن (Reference String) مع تتبّع مباشر لكل خطوة
      - رفوف العرض الحالية (Frames) ومحتواها اللحظي
      - عداد Page Faults / Hits ونسبة الفشل
      - مقارنة بيانية بين FIFO و LRU و Optimal (عدد الأعطال + التراكمي)
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self.num_frames = DEFAULT_FRAMES
        self.ref_string = generate_reference_string(DEFAULT_REF_LEN, NUM_PAGE_TYPES)

        # نتائج الخوارزمية الحالية (للأنيميشن)
        self.steps = []
        self.step_idx = 0
        self.running = False
        self._after_id = None

        self._build_ui()
        self._recompute_current_algo()
        self._render_step(-1)
        self._draw_compare_placeholder()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#06201a")
        title_f.pack(fill="x")
        tk.Label(title_f, text="🗄 مدير تخزين الرفوف — محاكاة استبدال صفحات الذاكرة (Paging)",
                 font=("Arial", 13, "bold"), fg=ACCENT, bg="#06201a").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text="كل رف = صفحة ذاكرة | الرفوف المتاحة أمام الزبون = Frames | طلبات الزبائن = Reference String",
                 font=("Arial", 9), fg="#3a6a5a", bg="#06201a").pack(side="right", padx=10)

        # ── شريط التحكم ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl_f, text="عدد الرفوف (Frames):", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(10, 4), pady=8)
        self.frames_var = tk.IntVar(value=DEFAULT_FRAMES)
        tk.Spinbox(ctrl_f, from_=2, to=6, textvariable=self.frames_var, width=3,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4,
                   command=self._on_frames_changed).pack(side="right", padx=4)

        tk.Label(ctrl_f, text="طول سلسلة الطلبات:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(15, 4))
        self.reflen_var = tk.IntVar(value=DEFAULT_REF_LEN)
        tk.Spinbox(ctrl_f, from_=10, to=40, textvariable=self.reflen_var, width=4,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        self._btn(ctrl_f, "🔀 توليد طلبات جديدة", BLUE, self._on_new_sequence).pack(side="right", padx=8)

        tk.Label(ctrl_f, text="الخوارزمية:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="left", padx=(10, 4))
        self.algo_var = tk.StringVar(value=ALG_FIFO)
        for value in (ALG_FIFO, ALG_LRU, ALG_OPTIMAL):
            tk.Radiobutton(
                ctrl_f, text=ALG_LABELS[value], variable=self.algo_var, value=value,
                bg=BG2, fg=ALG_COLORS[value], selectcolor="#1a2a3a", activebackground=BG2,
                font=("Arial", 9, "bold"), command=self._on_algo_changed
            ).pack(side="left", padx=4)

        ctrl_f2 = tk.Frame(self, bg=BG2)
        ctrl_f2.pack(fill="x", padx=10, pady=(0, 5))

        tk.Label(ctrl_f2, text="سرعة الأنيميشن:", font=("Arial", 9),
                 fg="#8aa8c8", bg=BG2).pack(side="right", padx=(10, 4))
        self.speed_var = tk.DoubleVar(value=0.5)
        tk.Scale(ctrl_f2, from_=0.1, to=1.5, resolution=0.1, variable=self.speed_var,
                 orient="horizontal", bg=BG2, fg=ACCENT, highlightthickness=0,
                 length=140, troughcolor="#1a2a3a").pack(side="right", padx=4)

        self.play_btn = self._btn(ctrl_f2, "▶ تشغيل المحاكاة", GREEN, self._on_play, size=10)
        self.play_btn.pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f2, "⏹ إيقاف", RED, self._on_stop, size=10).pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f2, "↩ إعادة من البداية", "#5a7a9a", self._on_reset, size=10).pack(side="left", padx=4, pady=4)
        self._btn(ctrl_f2, "📊 مقارنة الخوارزميات الثلاث", PURPLE, self._on_compare, size=10).pack(side="left", padx=12, pady=4)

        # ── إحصائيات حية ──
        stats_f = tk.Frame(self, bg=BG2)
        stats_f.pack(fill="x", padx=10, pady=5)
        self.faults_var = tk.StringVar(value="0")
        self.hits_var = tk.StringVar(value="0")
        self.rate_var = tk.StringVar(value="0.0%")
        self.step_var = tk.StringVar(value="0 / 0")
        for i, (lbl, var, col) in enumerate([
            ("📦 Page Faults", self.faults_var, RED),
            ("✅ Hits", self.hits_var, GREEN),
            ("📉 نسبة الأعطال", self.rate_var, YELLOW),
            ("🔢 الخطوة", self.step_var, ACCENT),
        ]):
            fr = tk.Frame(stats_f, bg=BG2)
            fr.grid(row=0, column=i, padx=20, pady=4, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg=BG2, font=("Arial", 10, "bold")).pack()
            tk.Label(fr, textvariable=var, fg=col, bg=BG2, font=("Arial", 20, "bold")).pack()
        for i in range(4):
            stats_f.columnconfigure(i, weight=1)

        # ── سلسلة الطلبات (Reference String) ──
        self._section_title(self, "🧾 سلسلة طلبات الزبائن (Reference String)")
        self.ref_canvas_f = tk.Frame(self, bg=BG3)
        self.ref_canvas_f.pack(fill="x", padx=10, pady=(0, 5))
        self.ref_boxes = []   # تُبنى في _build_ref_boxes

        # ── الرفوف الحالية (Frames) ──
        self._section_title(self, "🛒 الرفوف المتاحة أمام الزبون (Frames)")
        self.frames_f = tk.Frame(self, bg=BG)
        self.frames_f.pack(fill="x", padx=10, pady=(0, 5))
        self.frame_boxes = []   # تُبنى في _build_frame_boxes

        # ── منطقة سفلية: السجل + الرسم البياني للمقارنة ──
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="both", expand=True, padx=10, pady=5)

        left_panel = tk.Frame(bottom, bg=BG2, width=320)
        left_panel.pack(side="left", fill="both", padx=(0, 5))
        left_panel.pack_propagate(False)
        self._section_title(left_panel, "📋 سجل الأحداث")
        self.log_box = scrolledtext.ScrolledText(
            left_panel, height=14, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("info", "#8aa8c8"), ("hit", GREEN), ("fault", RED),
                          ("evict", YELLOW), ("scenario", PURPLE)]:
            self.log_box.tag_config(tag, foreground=col)

        right_panel = tk.Frame(bottom, bg=BG2)
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "📊 مقارنة Page Faults بين الخوارزميات")
        self.fig, (self.bar_ax, self.line_ax) = plt.subplots(
            1, 2, figsize=(8, 3.2), facecolor=BG2, gridspec_kw={'width_ratios': [1, 2]})
        for ax in (self.bar_ax, self.line_ax):
            ax.set_facecolor(BG2)
            ax.tick_params(colors=FG, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
        self.compare_canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.compare_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        self._build_ref_boxes()
        self._build_frame_boxes()

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

    # ── بناء صناديق سلسلة الطلبات ─────────────────────────────────────────────
    def _build_ref_boxes(self):
        for w in self.ref_canvas_f.winfo_children():
            w.destroy()
        self.ref_boxes = []

        per_row = 15
        for i, page in enumerate(self.ref_string):
            row, col = divmod(i, per_row)
            icon, name = PAGES[page]
            cell = tk.Frame(self.ref_canvas_f, bg=BG3, highlightthickness=1,
                            highlightbackground="#1a2a3a", width=46, height=46)
            cell.grid(row=row, column=col, padx=2, pady=2)
            cell.grid_propagate(False)
            lbl = tk.Label(cell, text=icon, font=("Arial", 16), bg=BG3, fg=FG)
            lbl.place(relx=0.5, rely=0.5, anchor="center")
            self.ref_boxes.append((cell, lbl))

    # ── بناء صناديق الرفوف (Frames) ───────────────────────────────────────────
    def _build_frame_boxes(self):
        for w in self.frames_f.winfo_children():
            w.destroy()
        self.frame_boxes = []

        n = self.frames_var.get()
        for i in range(n):
            cell = tk.Frame(self.frames_f, bg=BG2, highlightthickness=2,
                            highlightbackground="#1a2a3a", width=130, height=80)
            cell.pack(side="right", padx=6, pady=4)
            cell.pack_propagate(False)
            icon_lbl = tk.Label(cell, text="—", font=("Arial", 22), bg=BG2, fg="#3a5a7a")
            icon_lbl.pack(pady=(8, 0))
            name_lbl = tk.Label(cell, text="رف فارغ", font=("Arial", 9), bg=BG2, fg="#3a5a7a")
            name_lbl.pack()
            self.frame_boxes.append({"cell": cell, "icon": icon_lbl, "name": name_lbl})

    # ── أوامر التحكم ──────────────────────────────────────────────────────────
    def _on_frames_changed(self):
        self._on_stop()
        self.num_frames = self.frames_var.get()
        self._build_frame_boxes()
        self._recompute_current_algo()
        self._render_step(-1)
        self._draw_compare_placeholder()

    def _on_algo_changed(self):
        self._on_stop()
        self._recompute_current_algo()
        self._render_step(-1)
        self._append_log(f"تم اختيار الخوارزمية: {ALG_LABELS[self.algo_var.get()]}", "scenario")

    def _on_new_sequence(self):
        self._on_stop()
        length = self.reflen_var.get()
        self.ref_string = generate_reference_string(length, NUM_PAGE_TYPES)
        self._build_ref_boxes()
        self.num_frames = self.frames_var.get()
        self._recompute_current_algo()
        self._render_step(-1)
        self._draw_compare_placeholder()
        self._append_log(f"🔀 تم توليد سلسلة طلبات جديدة بطول {length}", "scenario")

    def _on_play(self):
        if self.running:
            return
        if self.step_idx >= len(self.steps) - 1:
            self.step_idx = -1
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
        self.step_idx = -1
        self._render_step(-1)
        self._append_log("↩ إعادة المحاكاة من البداية", "info")

    # ── إعادة حساب نتائج الخوارزمية الحالية على السلسلة الحالية ────────────────
    def _recompute_current_algo(self):
        self.num_frames = self.frames_var.get()
        algo = self.algo_var.get()
        func = ALG_FUNCS[algo]
        self.steps, self.total_faults = func(self.num_frames, self.ref_string)
        self.step_idx = -1

    # ── حلقة الأنيميشن ────────────────────────────────────────────────────────
    def _animate(self):
        if not self.running:
            return
        if self.step_idx >= len(self.steps) - 1:
            self.running = False
            self._append_log(
                f"✅ انتهت المحاكاة — إجمالي Page Faults = {self.total_faults} "
                f"من {len(self.ref_string)} طلباً", "scenario")
            return

        self.step_idx += 1
        self._render_step(self.step_idx)

        delay_ms = int(self.speed_var.get() * 1000)
        self._after_id = self.after(max(80, delay_ms), self._animate)

    # ── رسم خطوة معيّنة على الواجهة ───────────────────────────────────────────
    def _render_step(self, idx):
        n = len(self.ref_string)

        # ── تلوين صناديق سلسلة الطلبات ──
        for i, (cell, lbl) in enumerate(self.ref_boxes):
            if i < idx:
                step = self.steps[i]
                bg = "#16301a" if not step["fault"] else "#3a1414"
                border = GREEN if not step["fault"] else RED
            elif i == idx:
                step = self.steps[i]
                bg = "#1f6b2c" if not step["fault"] else "#b91c1c"
                border = "#3fb950" if not step["fault"] else "#f85149"
            else:
                bg = BG3
                border = "#1a2a3a"
            cell.config(bg=bg, highlightbackground=border)
            lbl.config(bg=bg)

        # ── تحديث الرفوف (Frames) ──
        if idx >= 0:
            step = self.steps[idx]
            current_frames = step["frames"]
            evicted = step["evicted"]
        else:
            current_frames = []
            evicted = None

        for i, box in enumerate(self.frame_boxes):
            if i < len(current_frames):
                page = current_frames[i]
                icon, name = PAGES[page]
                box["icon"].config(text=icon, fg=ACCENT)
                box["name"].config(text=name, fg=FG)
                if idx >= 0 and page == self.steps[idx]["page"]:
                    fault = self.steps[idx]["fault"]
                    box["cell"].config(highlightbackground=(RED if fault else GREEN))
                else:
                    box["cell"].config(highlightbackground="#1a2a3a")
            else:
                box["icon"].config(text="—", fg="#3a5a7a")
                box["name"].config(text="رف فارغ", fg="#3a5a7a")
                box["cell"].config(highlightbackground="#1a2a3a")

        # ── تحديث الإحصائيات ──
        if idx >= 0:
            faults = self.steps[idx]["fault_count"]
            hits = (idx + 1) - faults
            rate = (faults / (idx + 1)) * 100
            self.faults_var.set(str(faults))
            self.hits_var.set(str(hits))
            self.rate_var.set(f"{rate:.1f}%")
            self.step_var.set(f"{idx + 1} / {n}")

            page = self.steps[idx]["page"]
            icon, name = PAGES[page]
            if self.steps[idx]["fault"]:
                ev_txt = ""
                if evicted is not None:
                    ev_icon, ev_name = PAGES[evicted]
                    ev_txt = f" — تم إخراج {ev_icon} {ev_name} من الرف"
                self._append_log(
                    f"❌ طلب {icon} {name} → Page Fault!{ev_txt}", "fault")
            else:
                self._append_log(f"✅ طلب {icon} {name} → موجود على الرف (Hit)", "hit")
        else:
            self.faults_var.set("0")
            self.hits_var.set("0")
            self.rate_var.set("0.0%")
            self.step_var.set(f"0 / {n}")

    # ── مقارنة الخوارزميات الثلاث ─────────────────────────────────────────────
    def _on_compare(self):
        self._on_stop()
        num_frames = self.frames_var.get()

        results = {}
        for algo, func in ALG_FUNCS.items():
            steps, total = func(num_frames, self.ref_string)
            cumulative = [s["fault_count"] for s in steps]
            results[algo] = {"steps": steps, "total": total, "cumulative": cumulative}

        self._draw_compare(results)

        summary = " | ".join(
            f"{ALG_LABELS[a]}: {results[a]['total']} عطل"
            for a in (ALG_FIFO, ALG_LRU, ALG_OPTIMAL)
        )
        self._append_log(f"📊 مقارنة على نفس السلسلة ({len(self.ref_string)} طلباً، "
                         f"{num_frames} رفوف): {summary}", "scenario")

    def _draw_compare_placeholder(self):
        self.bar_ax.clear()
        self.line_ax.clear()
        for ax in (self.bar_ax, self.line_ax):
            ax.set_facecolor(BG2)
            ax.tick_params(colors=FG, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")
        self.bar_ax.text(0.5, 0.5, "اضغط 'مقارنة الخوارزميات الثلاث'",
                         ha="center", va="center", color="#5a7a9a",
                         fontsize=9, transform=self.bar_ax.transAxes)
        self.line_ax.text(0.5, 0.5, "لعرض المقارنة البيانية",
                          ha="center", va="center", color="#5a7a9a",
                          fontsize=9, transform=self.line_ax.transAxes)
        self.bar_ax.set_xticks([])
        self.bar_ax.set_yticks([])
        self.line_ax.set_xticks([])
        self.line_ax.set_yticks([])
        self.compare_canvas.draw_idle()

    def _draw_compare(self, results):
        self.bar_ax.clear()
        self.line_ax.clear()
        for ax in (self.bar_ax, self.line_ax):
            ax.set_facecolor(BG2)
            ax.tick_params(colors=FG, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#1a2a3a")

        algos = [ALG_FIFO, ALG_LRU, ALG_OPTIMAL]

        # ── الرسم الأول: أعمدة إجمالي Page Faults ──
        totals = [results[a]["total"] for a in algos]
        colors = [ALG_COLORS[a] for a in algos]
        bars = self.bar_ax.bar(
            [ALG_LABELS[a].split(" ")[0] for a in algos], totals, color=colors)
        self.bar_ax.set_title("إجمالي Page Faults", color=FG, fontsize=9)
        for b, t in zip(bars, totals):
            self.bar_ax.text(b.get_x() + b.get_width() / 2, t + 0.3, str(t),
                             ha="center", color=FG, fontsize=9, fontweight="bold")

        # ── الرسم الثاني: التطور التراكمي لـ Page Faults ──
        for a in algos:
            cum = results[a]["cumulative"]
            self.line_ax.plot(range(1, len(cum) + 1), cum,
                              label=ALG_LABELS[a].split(" ")[0],
                              color=ALG_COLORS[a], lw=2)
        self.line_ax.set_title("Page Faults التراكمية عبر الزمن", color=FG, fontsize=9)
        self.line_ax.set_xlabel("رقم الطلب", color=FG, fontsize=8)
        self.line_ax.legend(facecolor=BG2, labelcolor=FG, fontsize=8)

        self.fig.tight_layout()
        self.compare_canvas.draw_idle()
