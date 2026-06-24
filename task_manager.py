# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (6): Task Manager شبيه Windows — مراقبة خيوط البرنامج Live
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# نظام التشغيل يحتفظ لكل Thread بحالة (Thread State) من بين:
#   - Running   : الخيط يُنفَّذ فعلياً على المعالج الآن.
#   - Ready     : الخيط جاهز للتنفيذ وينتظر دوره من جدولة المعالج.
#   - Waiting/Blocked : الخيط متوقف لأنه ينتظر مورداً (قفل / مدخل/مخرج / ...).
#   - Terminated: الخيط انتهى تنفيذه.
#
# هذا التبويب يعرض **كل الخيوط (Threads) الحقيقية** العاملة فعلياً داخل هذا
# التطبيق (Live)، تماماً كتبويب "Processes" في Task Manager بنظام Windows،
# ويُحدِّد حالة كل خيط بدمج معلومتين:
#
#   1) `deadlock_detector._lock_graph` — يخبرنا أي الخيوط تنتظر قفلاً (Lock)
#      حالياً → حالة "Blocked/Waiting" (مأخوذة من DeadlockDetector الموجود
#      أصلاً في core.py، بدون أي تعديل عليه).
#
#   2) `psutil` — نقيس "وقت المعالج" (CPU Time) لكل Thread بين قراءتين
#      متتاليتين: إن زاد وقت المعالج للخيط منذ آخر قراءة → الخيط كان
#      "Running" فعلياً على المعالج، وإن لم يزد ولم يكن منتظراً قفلاً →
#      "Idle/Sleeping" (مثل خيط نائم بـ time.sleep()).
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import os

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)
from core import deadlock_detector

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ── ثوابت ─────────────────────────────────────────────────────────────────────
STATUS_RUNNING  = "RUNNING"
STATUS_BLOCKED  = "BLOCKED"
STATUS_IDLE     = "IDLE"
STATUS_STOPPED  = "STOPPED"

STATUS_LABELS = {
    STATUS_RUNNING: "🟢 يعمل (Running)",
    STATUS_BLOCKED: "🔒 محظور (Blocked)",
    STATUS_IDLE:    "🟡 خامل (Idle/Waiting)",
    STATUS_STOPPED: "⚪ متوقف (Terminated)",
}
STATUS_COLORS = {
    STATUS_RUNNING: GREEN,
    STATUS_BLOCKED: RED,
    STATUS_IDLE:    YELLOW,
    STATUS_STOPPED: "#5a7a9a",
}

REFRESH_MS = 1000   # فترة التحديث التلقائي (مللي ثانية)


# ═══════════════════════════════════════════════════════════════════════════════
# جمع لقطة حالة الخيوط الحالية
# ═══════════════════════════════════════════════════════════════════════════════
def collect_threads_snapshot(prev_cpu_times):
    """
    يُعيد (rows, new_cpu_times):
      rows : قائمة قواميس، كل قاموس يمثّل Thread واحد بالحقول:
             name, native_id, daemon, status, cpu_time, holds, waiting_for
      new_cpu_times : {native_id: cpu_time} للقراءة القادمة (لحساب الفرق)
    """
    lock_graph = dict(deadlock_detector._lock_graph)
    held_resources = {k: list(v) for k, v in deadlock_detector._held_resources.items()}

    # ── أوقات المعالج لكل Thread عبر psutil (إن وُجدت) ──
    cpu_times = {}
    if HAS_PSUTIL:
        try:
            proc = psutil.Process(os.getpid())
            for th in proc.threads():
                cpu_times[th.id] = th.user_time + th.system_time
        except Exception:
            pass

    rows = []
    for t in threading.enumerate():
        native_id = getattr(t, "native_id", None)
        if native_id is None:
            native_id = t.ident

        cpu_time = cpu_times.get(native_id)
        prev_time = prev_cpu_times.get(native_id)

        waiting_for = lock_graph.get(t.name)
        holds = held_resources.get(t.name, [])

        if not t.is_alive():
            status = STATUS_STOPPED
        elif waiting_for:
            status = STATUS_BLOCKED
        elif cpu_time is not None and prev_time is not None and (cpu_time - prev_time) > 0.001:
            status = STATUS_RUNNING
        elif cpu_time is not None and prev_time is None:
            # أول قراءة — لا يمكن معرفة الفرق بعد، نفترض Idle بشكل مبدئي
            status = STATUS_IDLE
        else:
            status = STATUS_IDLE

        rows.append({
            "name": t.name,
            "native_id": native_id,
            "daemon": t.daemon,
            "alive": t.is_alive(),
            "status": status,
            "cpu_time": cpu_time,
            "holds": holds,
            "waiting_for": waiting_for,
        })

    new_cpu_times = dict(cpu_times)
    return rows, new_cpu_times


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: Task Manager
# ═══════════════════════════════════════════════════════════════════════════════
class TaskManagerTab(tk.Frame):
    """
    تبويب يعرض كل خيوط (Threads) البرنامج Live: الاسم، رقم الخيط (Native ID)،
    الحالة (Running/Blocked/Idle/Terminated)، وقت المعالج، الموارد التي
    يملكها/ينتظرها كل خيط (من DeadlockDetector).
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self._prev_cpu_times = {}
        self.auto_refresh = tk.BooleanVar(value=True)
        self._after_id = None

        self._build_ui()
        self._refresh()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#1a1a2e")
        title_f.pack(fill="x")
        tk.Label(title_f, text="🖥 مدير المهام — Task Manager (مراقبة خيوط البرنامج Live)",
                 font=("Arial", 13, "bold"), fg="#79c0ff", bg="#1a1a2e").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text="حالة كل Thread (Running/Blocked/Idle) مدمجة من DeadlockDetector + psutil"
                      + ("" if HAS_PSUTIL else " — ⚠ psutil غير مثبّتة، الحالات Running/Idle تقريبية"),
                 font=("Arial", 9), fg="#3a3a5a", bg="#1a1a2e").pack(side="right", padx=10)

        # ── شريط التحكم ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=5)

        self._btn(ctrl_f, "🔄 تحديث الآن", BLUE, self._refresh).pack(side="right", padx=8, pady=6)
        tk.Checkbutton(ctrl_f, text="تحديث تلقائي كل ثانية", variable=self.auto_refresh,
                      bg=BG2, fg=FG, selectcolor="#1a2a3a", activebackground=BG2,
                      font=("Arial", 10, "bold"), command=self._on_toggle_auto
                      ).pack(side="right", padx=8)

        self.cpu_var = tk.StringVar(value="—")
        self.ram_var = tk.StringVar(value="—")
        tk.Label(ctrl_f, text="🧠 CPU النظام:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="left", padx=(10, 4))
        tk.Label(ctrl_f, textvariable=self.cpu_var, font=("Arial", 11, "bold"),
                 fg=GREEN, bg=BG2).pack(side="left")
        tk.Label(ctrl_f, text="💾 RAM النظام:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="left", padx=(15, 4))
        tk.Label(ctrl_f, textvariable=self.ram_var, font=("Arial", 11, "bold"),
                 fg="#79c0ff", bg=BG2).pack(side="left")

        # ── إحصائيات حية ──
        stats_f = tk.Frame(self, bg=BG2)
        stats_f.pack(fill="x", padx=10, pady=5)
        self.stat_vars = {}
        for i, (key, lbl, col) in enumerate([
            ("total",   "🧵 إجمالي الخيوط",        ACCENT),
            ("running", STATUS_LABELS[STATUS_RUNNING], STATUS_COLORS[STATUS_RUNNING]),
            ("blocked", STATUS_LABELS[STATUS_BLOCKED], STATUS_COLORS[STATUS_BLOCKED]),
            ("idle",    STATUS_LABELS[STATUS_IDLE],    STATUS_COLORS[STATUS_IDLE]),
            ("daemon",  "👻 خيوط Daemon",            "#a78bfa"),
        ]):
            fr = tk.Frame(stats_f, bg=BG2)
            fr.grid(row=0, column=i, padx=15, pady=4, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg=BG2, font=("Arial", 10, "bold")).pack()
            var = tk.StringVar(value="0")
            self.stat_vars[key] = var
            tk.Label(fr, textvariable=var, fg=col, bg=BG2, font=("Arial", 18, "bold")).pack()
        for i in range(5):
            stats_f.columnconfigure(i, weight=1)

        # ── المنطقة الرئيسية: جدول الخيوط + رسوم بيانية ──
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        left_panel = tk.Frame(mid, bg=BG2)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._section_title(left_panel, "📋 الخيوط الحالية (Threads)")

        style = ttk.Style()
        style.configure("TaskMgr.Treeview", background="#1a2a3a", foreground="#c9d1d9",
                        fieldbackground="#1a2a3a", font=("Arial", 9), rowheight=24)
        style.configure("TaskMgr.Treeview.Heading", background="#0d1a2a", foreground="#00e5c3",
                        font=("Arial", 9, "bold"))
        style.map("TaskMgr.Treeview", background=[("selected", "#1f6feb")])

        cols = ("name", "id", "status", "daemon", "cpu", "holds", "waiting")
        headers = {
            "name": ("اسم الخيط", 220),
            "id": ("Native ID", 80),
            "status": ("الحالة", 150),
            "daemon": ("Daemon", 60),
            "cpu": ("وقت المعالج (s)", 100),
            "holds": ("يملك (Holds)", 160),
            "waiting": ("ينتظر (Waiting for)", 160),
        }
        self.tree = ttk.Treeview(left_panel, columns=cols, show="headings",
                                  height=16, style="TaskMgr.Treeview")
        for c in cols:
            label, width = headers[c]
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=5)

        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, foreground=color)

        right_panel = tk.Frame(mid, bg=BG2, width=380)
        right_panel.pack(side="right", fill="both", padx=(5, 0))
        right_panel.pack_propagate(False)

        self._section_title(right_panel, "📊 توزيع حالات الخيوط")
        self.fig_status, self.ax_status = plt.subplots(figsize=(4, 2.6), facecolor=BG2)
        self.ax_status.set_facecolor(BG2)
        self.ax_status.tick_params(colors=FG, labelsize=8)
        for sp in self.ax_status.spines.values():
            sp.set_color("#1a2a3a")
        self.canvas_status = FigureCanvasTkAgg(self.fig_status, master=right_panel)
        self.canvas_status.get_tk_widget().pack(fill="both", expand=False, padx=8, pady=5)

        self._section_title(right_panel, "🔥 أعلى الخيوط استخداماً للمعالج")
        self.fig_cpu, self.ax_cpu = plt.subplots(figsize=(4, 3.0), facecolor=BG2)
        self.ax_cpu.set_facecolor(BG2)
        self.ax_cpu.tick_params(colors=FG, labelsize=8)
        for sp in self.ax_cpu.spines.values():
            sp.set_color("#1a2a3a")
        self.canvas_cpu = FigureCanvasTkAgg(self.fig_cpu, master=right_panel)
        self.canvas_cpu.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        # ── شرح حالات الخيوط ──
        legend_f = tk.Frame(self, bg=BG2)
        legend_f.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(legend_f, text="📖 حالات الخيط:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(10, 4), pady=6)
        for status in (STATUS_RUNNING, STATUS_BLOCKED, STATUS_IDLE, STATUS_STOPPED):
            tk.Label(legend_f, text=STATUS_LABELS[status], font=("Arial", 9, "bold"),
                     fg=STATUS_COLORS[status], bg=BG2).pack(side="right", padx=10)

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

    # ── تبديل التحديث التلقائي ────────────────────────────────────────────────
    def _on_toggle_auto(self):
        if self.auto_refresh.get():
            self._schedule_refresh()
        elif self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _schedule_refresh(self):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(REFRESH_MS, self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        self._refresh()
        if self.auto_refresh.get():
            self._schedule_refresh()

    # ── التحديث الفعلي ────────────────────────────────────────────────────────
    def _refresh(self):
        rows, new_cpu_times = collect_threads_snapshot(self._prev_cpu_times)
        self._prev_cpu_times = new_cpu_times

        # ── تحديث الجدول ──
        self.tree.delete(*self.tree.get_children())
        counts = {STATUS_RUNNING: 0, STATUS_BLOCKED: 0, STATUS_IDLE: 0, STATUS_STOPPED: 0}
        daemon_count = 0
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            if r["daemon"]:
                daemon_count += 1

            cpu_str = f"{r['cpu_time']:.3f}" if r["cpu_time"] is not None else "—"
            holds_str = ", ".join(r["holds"]) if r["holds"] else "—"
            waiting_str = r["waiting_for"] or "—"

            self.tree.insert("", "end", values=(
                r["name"], r["native_id"], STATUS_LABELS[r["status"]],
                "✔" if r["daemon"] else "—", cpu_str, holds_str, waiting_str,
            ), tags=(r["status"],))

        # ── تحديث الإحصائيات ──
        self.stat_vars["total"].set(str(len(rows)))
        self.stat_vars["running"].set(str(counts.get(STATUS_RUNNING, 0)))
        self.stat_vars["blocked"].set(str(counts.get(STATUS_BLOCKED, 0)))
        self.stat_vars["idle"].set(str(counts.get(STATUS_IDLE, 0)))
        self.stat_vars["daemon"].set(str(daemon_count))

        # ── تحديث CPU/RAM النظام ──
        if HAS_PSUTIL:
            try:
                self.cpu_var.set(f"{psutil.cpu_percent(interval=None):.1f}%")
                self.ram_var.set(f"{psutil.virtual_memory().percent:.1f}%")
            except Exception:
                self.cpu_var.set("—")
                self.ram_var.set("—")
        else:
            self.cpu_var.set("N/A")
            self.ram_var.set("N/A")

        # ── الرسوم البيانية ──
        self._draw_status_chart(counts)
        self._draw_cpu_chart(rows)

        # ── جدولة التحديث التالي ──
        if self.auto_refresh.get() and self._after_id is None:
            self._schedule_refresh()

    # ── رسم توزيع الحالات ─────────────────────────────────────────────────────
    def _draw_status_chart(self, counts):
        self.ax_status.clear()
        self.ax_status.set_facecolor(BG2)
        self.ax_status.tick_params(colors=FG, labelsize=8)
        for sp in self.ax_status.spines.values():
            sp.set_color("#1a2a3a")

        statuses = [STATUS_RUNNING, STATUS_BLOCKED, STATUS_IDLE, STATUS_STOPPED]
        labels = [STATUS_LABELS[s].split(" ")[0] for s in statuses]
        values = [counts.get(s, 0) for s in statuses]
        colors = [STATUS_COLORS[s] for s in statuses]

        if sum(values) == 0:
            self.ax_status.text(0.5, 0.5, "لا توجد بيانات", ha="center", va="center",
                                color="#5a7a9a", fontsize=9, transform=self.ax_status.transAxes)
            self.ax_status.set_xticks([])
            self.ax_status.set_yticks([])
        else:
            bars = self.ax_status.bar(labels, values, color=colors)
            for b, v in zip(bars, values):
                if v > 0:
                    self.ax_status.text(b.get_x() + b.get_width() / 2, v + 0.05,
                                        str(v), ha="center", color=FG, fontsize=9, fontweight="bold")
            self.ax_status.set_ylim(0, max(values) + 1)

        self.fig_status.tight_layout()
        self.canvas_status.draw_idle()

    # ── رسم أعلى الخيوط استخداماً للمعالج ─────────────────────────────────────
    def _draw_cpu_chart(self, rows):
        self.ax_cpu.clear()
        self.ax_cpu.set_facecolor(BG2)
        self.ax_cpu.tick_params(colors=FG, labelsize=8)
        for sp in self.ax_cpu.spines.values():
            sp.set_color("#1a2a3a")

        with_cpu = [r for r in rows if r["cpu_time"] is not None and r["alive"]]
        with_cpu.sort(key=lambda r: r["cpu_time"], reverse=True)
        top = with_cpu[:8]

        if not top:
            self.ax_cpu.text(0.5, 0.5, "psutil غير متاح" if not HAS_PSUTIL else "لا توجد بيانات",
                            ha="center", va="center", color="#5a7a9a",
                            fontsize=9, transform=self.ax_cpu.transAxes)
            self.ax_cpu.set_xticks([])
            self.ax_cpu.set_yticks([])
        else:
            names = [r["name"][:18] for r in top][::-1]
            times = [r["cpu_time"] for r in top][::-1]
            colors = [STATUS_COLORS[r["status"]] for r in top][::-1]
            self.ax_cpu.barh(names, times, color=colors)
            self.ax_cpu.set_xlabel("وقت المعالج (ثانية)", color=FG, fontsize=8)

        self.fig_cpu.tight_layout()
        self.canvas_cpu.draw_idle()

    # ── إيقاف التحديث (يُستدعى عند إغلاق التطبيق) ──────────────────────────────
    def stop(self):
        self.auto_refresh.set(False)
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
