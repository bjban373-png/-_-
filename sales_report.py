# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (4): Multiprocessing حقيقي — "تقرير المبيعات اليومي"
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# نولّد مجموعة كبيرة من "فواتير المبيعات"، ولكل فاتورة عمل حسابي مكثف
# (CPU-bound) يحاكي "تدقيق الفاتورة ومطابقتها مع سجلات المخزون". نقارن 3 طرق
# لمعالجة هذه الفواتير:
#
#   1) تسلسلي (Sequential)   : معالجة كل فاتورة بدورها — خط الأساس.
#   2) Threads (ThreadPoolExecutor) : عدة خيوط تعمل "بالتوازي" ظاهرياً،
#      لكن بسبب GIL (Global Interpreter Lock) في بايثون، الخيوط لا تُسرّع
#      المهام الحسابية البحتة (CPU-bound) — وقد تكون أبطأ بسبب الـ Overhead!
#   3) Multiprocessing (multiprocessing.Pool) : عدة عمليات (Processes)
#      مستقلة، كل واحدة بمترجم بايثون خاص بها (لا يوجد GIL مشترك) → تسريع
#      حقيقي يقترب من عدد الأنوية (Cores) المتاحة.
#
# ⚠️ ملاحظة Windows (Spawn):
#   - دالة المعالجة process_invoice معرّفة على مستوى الملف (Module-Level)
#     وليس داخل أي كلاس أو دالة — لأن multiprocessing على Windows يستخدم
#     "spawn" الذي يحتاج تمرير (pickle) الدالة لكل عملية فرعية، ودوال
#     الكلاسات/الدوال المحلية (Local Functions) لا يمكن تمريرها (Pickling
#     Error).
#   - main.py محاط بالفعل بـ if __name__ == "__main__": — وهذا ضروري حتى
#     لا تُعاد فتح نوافذ البرنامج عند إنشاء كل عملية فرعية (لأن Windows
#     يُعيد استيراد main.py في كل عملية فرعية مع Spawn).
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import random
import os
import queue as _queue
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)


# ── ثوابت المحاكاة ────────────────────────────────────────────────────────────
PRODUCTS = [
    ("🥖 خبز", 3.0),
    ("🥛 حليب", 5.5),
    ("🍎 تفاح", 7.0),
    ("🥩 لحم", 45.0),
    ("🧃 عصير", 4.0),
    ("🍫 شوكولاتة", 6.5),
    ("🧴 منظف", 12.0),
    ("❄️ آيس كريم", 15.0),
    ("🍚 أرز", 18.0),
    ("☕ قهوة", 22.0),
]

DEFAULT_INVOICE_COUNT = 300
DEFAULT_INTENSITY = 25000     # عدد التكرارات الحسابية لكل فاتورة (محاكاة التدقيق)
DEFAULT_WORKERS = max(2, os.cpu_count() or 2)

METHOD_SEQ     = "SEQ"
METHOD_THREADS = "THREADS"
METHOD_PROC    = "PROCESS"

METHOD_LABELS = {
    METHOD_SEQ:     "تسلسلي (Sequential)",
    METHOD_THREADS: "Threads (ThreadPoolExecutor)",
    METHOD_PROC:    "Multiprocessing (Pool)",
}
METHOD_COLORS = {
    METHOD_SEQ:     "#8aa8c8",
    METHOD_THREADS: "#f85149",
    METHOD_PROC:    "#3fb950",
}


# ═══════════════════════════════════════════════════════════════════════════════
# توليد فواتير عشوائية
# ═══════════════════════════════════════════════════════════════════════════════
def generate_invoices(count=DEFAULT_INVOICE_COUNT, intensity=DEFAULT_INTENSITY):
    """
    يولّد `count` فاتورة عشوائية، كل فاتورة تحتوي 1-5 أصناف بكميات عشوائية.
    `intensity` = شدّة العمل الحسابي المطلوب لتدقيق كل فاتورة (انظر
    process_invoice أدناه).
    """
    invoices = []
    for i in range(count):
        n_items = random.randint(1, 5)
        items = []
        for _ in range(n_items):
            name, price = random.choice(PRODUCTS)
            qty = random.randint(1, 6)
            items.append((name, qty, price))
        invoices.append({"id": i + 1, "items": items, "intensity": intensity})
    return invoices


# ═══════════════════════════════════════════════════════════════════════════════
# دالة المعالجة — يجب أن تبقى على مستوى الملف (Module-Level) لأجل Pickling
# على Windows مع multiprocessing (طريقة spawn)
# ═══════════════════════════════════════════════════════════════════════════════
def process_invoice(invoice):
    """
    يحاكي "تدقيق فاتورة ومطابقتها مع المخزون":
      1) حساب الإجمالي الحقيقي للفاتورة من بنودها.
      2) عمل حسابي مكثف (CPU-bound) بعدد تكرارات = invoice["intensity"]
         لمحاكاة عملية تحقق/تشفير لكل فاتورة (نفس الفكرة في كل العمليات
         الحقيقية مثل: حساب الضرائب، فحص الاحتيال، إعادة حساب الأكواد...).

    هذه الدالة تُستخدم في الثلاث طرق (تسلسلي / Threads / Multiprocessing)
    لضمان مقارنة عادلة بينها على نفس العمل بالضبط.
    """
    total = sum(qty * price for _, qty, price in invoice["items"])

    # عمل حسابي مكثف (CPU-bound) — لا يوجد فيه أي عمليات I/O
    checksum = 0
    n = invoice["intensity"]
    inv_id = invoice["id"]
    for i in range(n):
        checksum = (checksum + (i * inv_id) % 97) % 1000003

    return {
        "id": inv_id,
        "total": round(total, 2),
        "items_count": len(invoice["items"]),
        "checksum": checksum,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# الطرق الثلاث لمعالجة الفواتير
# ═══════════════════════════════════════════════════════════════════════════════
def run_sequential(invoices):
    t0 = time.perf_counter()
    results = [process_invoice(inv) for inv in invoices]
    elapsed = time.perf_counter() - t0
    return results, elapsed


def run_threaded(invoices, num_workers):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_workers) as ex:
        results = list(ex.map(process_invoice, invoices))
    elapsed = time.perf_counter() - t0
    return results, elapsed


def run_multiprocess(invoices, num_workers):
    t0 = time.perf_counter()
    with multiprocessing.Pool(processes=num_workers) as pool:
        chunksize = max(1, len(invoices) // (num_workers * 4))
        results = pool.map(process_invoice, invoices, chunksize=chunksize)
    elapsed = time.perf_counter() - t0
    return results, elapsed


def summarize_results(invoices, results):
    """يبني تقرير المبيعات اليومي من نتائج المعالجة."""
    totals = [r["total"] for r in results]
    revenue = sum(totals)
    count = len(results)

    # توزيع المبيعات حسب المنتج
    product_totals = {}
    for inv in invoices:
        for name, qty, price in inv["items"]:
            product_totals[name] = product_totals.get(name, 0.0) + qty * price

    return {
        "count": count,
        "revenue": revenue,
        "avg": revenue / count if count else 0,
        "max": max(totals) if totals else 0,
        "min": min(totals) if totals else 0,
        "product_totals": product_totals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: تقرير المبيعات اليومي (Multiprocessing)
# ═══════════════════════════════════════════════════════════════════════════════
class SalesReportTab(tk.Frame):
    """
    تبويب يقارن 3 طرق لمعالجة دفعة فواتير المبيعات اليومية:
      تسلسلي  /  Threads (يُظهر أثر GIL)  /  Multiprocessing (تسريع حقيقي)
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self.invoices = generate_invoices()
        self.times = {}        # METHOD -> elapsed seconds
        self.last_summary = None
        self._result_queue = _queue.Queue()
        self.busy = False
        self._run_all_mode = False

        self._build_ui()
        self._draw_chart()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#0a1a2a")
        title_f.pack(fill="x")
        tk.Label(title_f, text="📑 تقرير المبيعات اليومي — Multiprocessing الحقيقي",
                 font=("Arial", 13, "bold"), fg="#79c0ff", bg="#0a1a2a").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text=f"عدد الأنوية المتاحة في جهازك: {os.cpu_count()} | "
                      "مقارنة: تسلسلي vs Threads (تأثير GIL) vs Multiprocessing (تسريع حقيقي)",
                 font=("Arial", 9), fg="#3a5a7a", bg="#0a1a2a").pack(side="right", padx=10)

        # ── شريط التحكم ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl_f, text="عدد الفواتير:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(10, 4), pady=8)
        self.count_var = tk.IntVar(value=DEFAULT_INVOICE_COUNT)
        tk.Spinbox(ctrl_f, from_=50, to=2000, increment=50, textvariable=self.count_var, width=5,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        tk.Label(ctrl_f, text="شدّة التدقيق لكل فاتورة:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(15, 4))
        self.intensity_var = tk.IntVar(value=DEFAULT_INTENSITY)
        tk.Spinbox(ctrl_f, from_=5000, to=100000, increment=5000, textvariable=self.intensity_var, width=7,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        tk.Label(ctrl_f, text="عدد العمّال (Workers):", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(15, 4))
        self.workers_var = tk.IntVar(value=DEFAULT_WORKERS)
        tk.Spinbox(ctrl_f, from_=2, to=max(2, (os.cpu_count() or 2) * 2), textvariable=self.workers_var, width=3,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="right", padx=4)

        self._btn(ctrl_f, "🔀 فواتير جديدة", BLUE, self._on_new_invoices).pack(side="right", padx=8)

        ctrl_f2 = tk.Frame(self, bg=BG2)
        ctrl_f2.pack(fill="x", padx=10, pady=(0, 5))

        self.seq_btn = self._btn(ctrl_f2, "🔢 تشغيل: تسلسلي", METHOD_COLORS[METHOD_SEQ],
                                  lambda: self._on_run(METHOD_SEQ))
        self.seq_btn.pack(side="right", padx=4, pady=4)
        self.th_btn = self._btn(ctrl_f2, "🧵 تشغيل: Threads", METHOD_COLORS[METHOD_THREADS],
                                 lambda: self._on_run(METHOD_THREADS))
        self.th_btn.pack(side="right", padx=4, pady=4)
        self.mp_btn = self._btn(ctrl_f2, "⚙ تشغيل: Multiprocessing", METHOD_COLORS[METHOD_PROC],
                                 lambda: self._on_run(METHOD_PROC))
        self.mp_btn.pack(side="right", padx=4, pady=4)
        self.cmp_btn = self._btn(ctrl_f2, "📊 تشغيل الكل وقارن", PURPLE, self._on_run_all)
        self.cmp_btn.pack(side="right", padx=12, pady=4)

        self.status_var = tk.StringVar(value="جاهز")
        tk.Label(ctrl_f2, textvariable=self.status_var, font=("Arial", 10, "bold"),
                 fg=YELLOW, bg=BG2).pack(side="left", padx=10)

        # ── منطقة سفلية: نتائج + رسم بياني ──
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        left_panel = tk.Frame(mid, bg=BG2, width=380)
        left_panel.pack(side="left", fill="both", padx=(0, 5))
        left_panel.pack_propagate(False)

        self._section_title(left_panel, "⏱ نتائج الوقت لكل طريقة")
        self.time_rows = {}
        for method in (METHOD_SEQ, METHOD_THREADS, METHOD_PROC):
            row = tk.Frame(left_panel, bg=BG3, highlightthickness=1,
                           highlightbackground="#1a2a3a")
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=METHOD_LABELS[method], font=("Arial", 10, "bold"),
                     fg=METHOD_COLORS[method], bg=BG3, anchor="e", width=24
                     ).pack(side="right", padx=6, pady=6)
            time_var = tk.StringVar(value="—")
            speed_var = tk.StringVar(value="")
            tk.Label(row, textvariable=time_var, font=("Arial", 12, "bold"),
                     fg=FG, bg=BG3, width=8).pack(side="right", padx=4)
            tk.Label(row, textvariable=speed_var, font=("Arial", 9),
                     fg="#8aa8c8", bg=BG3, width=10).pack(side="right", padx=4)
            self.time_rows[method] = {"time": time_var, "speed": speed_var}

        self._section_title(left_panel, "📊 تقرير المبيعات اليومي")
        self.summary_box = scrolledtext.ScrolledText(
            left_panel, height=14, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.summary_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("info", "#8aa8c8"), ("ok", GREEN), ("title", ACCENT), ("warn", YELLOW)]:
            self.summary_box.tag_config(tag, foreground=col)

        right_panel = tk.Frame(mid, bg=BG2)
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "📈 مقارنة زمن التنفيذ بين الطرق الثلاث")
        self.fig, self.ax = plt.subplots(figsize=(7, 4), facecolor=BG2)
        self.ax.set_facecolor(BG2)
        self.ax.tick_params(colors=FG, labelsize=9)
        for sp in self.ax.spines.values():
            sp.set_color("#1a2a3a")
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        # ── السجل ──
        self._section_title(self, "📋 سجل التنفيذ")
        self.log_box = scrolledtext.ScrolledText(
            self, height=6, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=False, padx=10, pady=(0, 8))
        for tag, col in [("info", "#8aa8c8"), ("ok", GREEN), ("warn", YELLOW), ("scenario", PURPLE), ("err", RED)]:
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

    def _set_buttons_state(self, state):
        for b in (self.seq_btn, self.th_btn, self.mp_btn, self.cmp_btn):
            b.config(state=state)

    # ── أوامر التحكم ──────────────────────────────────────────────────────────
    def _on_new_invoices(self):
        if self.busy:
            return
        count = self.count_var.get()
        intensity = self.intensity_var.get()
        self.invoices = generate_invoices(count, intensity)
        self.times = {}
        for method in (METHOD_SEQ, METHOD_THREADS, METHOD_PROC):
            self.time_rows[method]["time"].set("—")
            self.time_rows[method]["speed"].set("")
        self._draw_chart()
        self._set_summary_text("")
        self._append_log(
            f"🔀 تم توليد {count} فاتورة جديدة (شدّة التدقيق = {intensity} لكل فاتورة)",
            "scenario")

    def _on_run(self, method):
        if self.busy:
            return
        # تحديث الفواتير حسب القيم الحالية إن تغيّرت
        count = self.count_var.get()
        intensity = self.intensity_var.get()
        if len(self.invoices) != count or self.invoices[0]["intensity"] != intensity:
            self.invoices = generate_invoices(count, intensity)

        workers = self.workers_var.get()
        self.busy = True
        self._run_all_mode = False
        self._set_buttons_state("disabled")
        self.status_var.set(f"⏳ يعمل: {METHOD_LABELS[method]}...")
        self._append_log(f"▶ بدء المعالجة — {METHOD_LABELS[method]} "
                         f"({count} فاتورة، {workers} عامل)", "scenario")

        t = threading.Thread(target=self._worker_run, args=(method, workers), daemon=True)
        t.start()
        self.after(100, self._poll_results)

    def _on_run_all(self):
        if self.busy:
            return
        count = self.count_var.get()
        intensity = self.intensity_var.get()
        if len(self.invoices) != count or self.invoices[0]["intensity"] != intensity:
            self.invoices = generate_invoices(count, intensity)

        workers = self.workers_var.get()
        self.busy = True
        self._run_all_mode = True
        self._set_buttons_state("disabled")
        self.status_var.set("⏳ تشغيل الطرق الثلاث للمقارنة...")
        self._append_log(
            f"▶ بدء المقارنة الشاملة — {count} فاتورة، شدّة={intensity}، "
            f"عمّال={workers}", "scenario")

        methods = [METHOD_SEQ, METHOD_THREADS, METHOD_PROC]
        t = threading.Thread(target=self._worker_run_all, args=(methods, workers), daemon=True)
        t.start()
        self.after(100, self._poll_results)

    # ── خيوط التنفيذ الفعلية (تعمل في الخلفية لتجنّب تجميد الواجهة) ─────────────
    def _worker_run(self, method, workers):
        try:
            if method == METHOD_SEQ:
                results, elapsed = run_sequential(self.invoices)
            elif method == METHOD_THREADS:
                results, elapsed = run_threaded(self.invoices, workers)
            else:
                results, elapsed = run_multiprocess(self.invoices, workers)
            summary = summarize_results(self.invoices, results)
            self._result_queue.put(("done", method, elapsed, summary))
        except Exception as e:
            self._result_queue.put(("error", method, 0, str(e)))

    def _worker_run_all(self, methods, workers):
        for method in methods:
            try:
                if method == METHOD_SEQ:
                    results, elapsed = run_sequential(self.invoices)
                elif method == METHOD_THREADS:
                    results, elapsed = run_threaded(self.invoices, workers)
                else:
                    results, elapsed = run_multiprocess(self.invoices, workers)
                summary = summarize_results(self.invoices, results)
                self._result_queue.put(("done", method, elapsed, summary))
            except Exception as e:
                self._result_queue.put(("error", method, 0, str(e)))
        self._result_queue.put(("all_done", None, 0, None))

    # ── استقبال النتائج من الخيط الخلفي ──────────────────────────────────────
    def _poll_results(self):
        while True:
            try:
                kind, method, elapsed, payload = self._result_queue.get_nowait()
            except _queue.Empty:
                break

            if kind == "done":
                self.times[method] = elapsed
                self.time_rows[method]["time"].set(f"{elapsed:.3f}s")
                self.last_summary = payload
                self._append_log(
                    f"✅ {METHOD_LABELS[method]} انتهى في {elapsed:.3f} ثانية", "ok")
                self._update_speedups()
                self._draw_chart()
                self._set_summary_text(self._format_summary(payload))
                if not self._run_all_mode:
                    self.busy = False
                    self._set_buttons_state("normal")
                    self.status_var.set("جاهز")

            elif kind == "error":
                self._append_log(f"❌ خطأ في {METHOD_LABELS.get(method, method)}: {payload}", "err")
                if not self._run_all_mode:
                    self.busy = False
                    self._set_buttons_state("normal")
                    self.status_var.set("جاهز")

            elif kind == "all_done":
                self.busy = False
                self._set_buttons_state("normal")
                self.status_var.set("✅ انتهت المقارنة")
                self._log_comparison_summary()

        if self.busy:
            self.after(100, self._poll_results)

    # ── حسابات التسريع (Speedup) ─────────────────────────────────────────────
    def _update_speedups(self):
        base = self.times.get(METHOD_SEQ)
        for method in (METHOD_SEQ, METHOD_THREADS, METHOD_PROC):
            t = self.times.get(method)
            if t is None:
                continue
            if method == METHOD_SEQ or base is None:
                self.time_rows[method]["speed"].set("(الأساس)" if method == METHOD_SEQ else "")
            else:
                speedup = base / t if t > 0 else 0
                tag = "🚀" if speedup > 1.1 else ("≈" if 0.9 <= speedup <= 1.1 else "🐢")
                self.time_rows[method]["speed"].set(f"{tag} x{speedup:.2f}")

    # ── ملخص المقارنة في السجل ────────────────────────────────────────────────
    def _log_comparison_summary(self):
        if METHOD_SEQ in self.times and METHOD_THREADS in self.times and METHOD_PROC in self.times:
            seq_t = self.times[METHOD_SEQ]
            th_t = self.times[METHOD_THREADS]
            mp_t = self.times[METHOD_PROC]
            self._append_log(
                f"📊 النتيجة: تسلسلي={seq_t:.3f}s | Threads={th_t:.3f}s "
                f"(x{seq_t/th_t:.2f}) | Multiprocessing={mp_t:.3f}s (x{seq_t/mp_t:.2f})",
                "scenario")
            if th_t >= seq_t * 0.9:
                self._append_log(
                    "🔒 لاحظ: Threads لم تُسرّع المهمة (وقد تكون أبطأ بسبب الـ "
                    "Overhead) — لأن GIL يمنع تنفيذ أكواد بايثون الحسابية بالتوازي "
                    "الحقيقي حتى مع وجود خيوط متعددة.", "warn")
            if mp_t < seq_t * 0.9:
                self._append_log(
                    f"⚡ بينما Multiprocessing حقق تسريعاً حقيقياً (x{seq_t/mp_t:.2f}) "
                    f"لأن كل عملية (Process) تملك مترجم بايثون مستقلاً بلا GIL "
                    f"مشترك — استخدمت {self.workers_var.get()} عملية على "
                    f"{os.cpu_count()} أنوية متاحة.", "ok")

    # ── الرسم البياني ─────────────────────────────────────────────────────────
    def _draw_chart(self):
        self.ax.clear()
        self.ax.set_facecolor(BG2)
        self.ax.tick_params(colors=FG, labelsize=9)
        for sp in self.ax.spines.values():
            sp.set_color("#1a2a3a")

        methods = [METHOD_SEQ, METHOD_THREADS, METHOD_PROC]
        labels = [METHOD_LABELS[m].split(" ")[0] for m in methods]
        values = [self.times.get(m, 0) for m in methods]
        colors = [METHOD_COLORS[m] for m in methods]

        if not any(values):
            self.ax.text(0.5, 0.5, "اضغط أحد أزرار التشغيل لعرض النتائج",
                         ha="center", va="center", color="#5a7a9a",
                         fontsize=10, transform=self.ax.transAxes)
            self.ax.set_xticks([])
            self.ax.set_yticks([])
        else:
            bars = self.ax.bar(labels, values, color=colors)
            for b, v in zip(bars, values):
                if v > 0:
                    self.ax.text(b.get_x() + b.get_width() / 2, v + max(values) * 0.02,
                                 f"{v:.3f}s", ha="center", color=FG, fontsize=9, fontweight="bold")
            self.ax.set_ylabel("زمن التنفيذ (ثانية)", color=FG, fontsize=9)
            self.ax.set_title(f"معالجة {len(self.invoices)} فاتورة — "
                              f"شدّة التدقيق={self.invoices[0]['intensity'] if self.invoices else '-'}",
                              color=FG, fontsize=10)

        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ── تقرير المبيعات اليومي ─────────────────────────────────────────────────
    def _set_summary_text(self, text):
        self.summary_box.config(state="normal")
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("end", text)
        self.summary_box.config(state="disabled")

    def _format_summary(self, summary):
        if not summary:
            return ""
        lines = []
        lines.append("📊 ===== تقرير المبيعات اليومي =====\n")
        lines.append(f"عدد الفواتير المُعالَجة : {summary['count']}\n")
        lines.append(f"إجمالي المبيعات         : {summary['revenue']:.2f} ر.س\n")
        lines.append(f"متوسط الفاتورة          : {summary['avg']:.2f} ر.س\n")
        lines.append(f"أعلى فاتورة             : {summary['max']:.2f} ر.س\n")
        lines.append(f"أقل فاتورة              : {summary['min']:.2f} ر.س\n")
        lines.append("\n── المبيعات حسب المنتج ──\n")
        for name, total in sorted(summary["product_totals"].items(),
                                   key=lambda kv: -kv[1]):
            lines.append(f"  {name:<14} : {total:>10.2f} ر.س\n")
        return "".join(lines)
