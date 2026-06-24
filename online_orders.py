# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (5): Asyncio / Sockets — "نظام طلبات أونلاين"
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# نُنشئ سيرفر حقيقي (Socket) باستخدام asyncio.start_server على
# 127.0.0.1:8888، يستقبل طلبات من عدة "زبائن أونلاين" في نفس الوقت. كل طلب
# يحتاج "وقت معالجة" (محاكاة البحث في قاعدة بيانات المنتجات) عبر
# `await asyncio.sleep(...)` — وهي عملية I/O-bound حقيقية (Socket I/O + Sleep).
#
# نقارن 3 طرق لإرسال نفس عدد الطلبات لهذا السيرفر:
#
#   1) متسلسل (Sequential) : كل عميل يتصل، ينتظر الرد، ثم يأتي العميل التالي.
#      الزمن الكلي ≈ مجموع كل أوقات المعالجة (Total ≈ Σ delay_i).
#
#   2) Asyncio (Concurrency) : كل العملاء يتصلون "في نفس الوقت" من خلال
#      Thread واحد فقط ومُهمّات (Tasks) متعددة على Event Loop واحد —
#      التزامن (Concurrency) عبر تبديل المهام أثناء انتظار I/O، بدون
#      أي Thread إضافي. الزمن الكلي ≈ أكبر وقت معالجة (Total ≈ max(delay_i)).
#
#   3) Threads (Parallelism) : كل عميل في Thread نظام تشغيل مستقل (N Threads
#      لـ N عميل). كل Thread يُحجب (Block) عند انتظار الشبكة، فيُحرَّر GIL
#      ويستطيع Thread آخر العمل — تزامن حقيقي عبر تعدد الخيوط. الزمن الكلي
#      ≈ أكبر وقت معالجة أيضاً، لكن بتكلفة N Threads بدلاً من Thread واحد.
#
# الخلاصة التي يوضّحها هذا التبويب:
#   - Asyncio يحقق نفس فائدة التزامن (Concurrency) للعمليات I/O-bound التي
#     تحققها Threads — لكن بموارد أقل بكثير (Thread واحد فقط مهما زاد عدد
#     العملاء)، وهذا سبب استخدامه في سيرفرات الويب الحديثة.
#   - Threads توفّر تزامناً حقيقياً (وموازاة حقيقية أحياناً) لكن بتكلفة ذاكرة
#     وOverhead أعلى لكل عميل إضافي.
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import scrolledtext
import threading
import asyncio
import socket
import json
import time
import random
import queue as _queue

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)


# ── ثوابت ─────────────────────────────────────────────────────────────────────
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8899

PRODUCTS = ["🥖 خبز", "🥛 حليب", "🍎 تفاح", "🥩 لحم", "🧃 عصير",
            "🍫 شوكولاتة", "🧴 منظف", "❄️ آيس كريم", "🍚 أرز", "☕ قهوة"]

DEFAULT_NUM_CLIENTS = 6
MIN_DELAY, MAX_DELAY = 0.4, 1.2   # محاكاة وقت البحث في قاعدة البيانات (ثانية)

MODE_SEQ     = "SEQ"
MODE_ASYNCIO = "ASYNCIO"
MODE_THREADS = "THREADS"

MODE_LABELS = {
    MODE_SEQ:     "متسلسل (Sequential)",
    MODE_ASYNCIO: "Asyncio (Concurrency)",
    MODE_THREADS: "Threads (Parallelism)",
}
MODE_COLORS = {
    MODE_SEQ:     "#f85149",
    MODE_ASYNCIO: "#a78bfa",
    MODE_THREADS: "#00e5c3",
}


# ═══════════════════════════════════════════════════════════════════════════════
# السيرفر — asyncio.start_server على Socket حقيقي
# ═══════════════════════════════════════════════════════════════════════════════
class OrderServer:
    """
    سيرفر "طلبات أونلاين" حقيقي يعمل على 127.0.0.1:8899 باستخدام asyncio.
    يعمل في Thread خاص به (مع Event Loop خاص به) حتى لا يتعارض مع حلقة Tkinter.
    """

    def __init__(self, log_cb=None):
        self.log_cb = log_cb or (lambda *a, **k: None)
        self.loop = None
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="OrderServer-Loop")
        self.thread.start()

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start_server())
            self.loop.run_forever()
        except Exception as e:
            self.log_cb(f"❌ خطأ في السيرفر: {e}", "err")
            self.running = False

    async def _start_server(self):
        self.server = await asyncio.start_server(
            self._handle_client, SERVER_HOST, SERVER_PORT, reuse_address=True)
        self.log_cb(f"🟢 السيرفر يعمل الآن على {SERVER_HOST}:{SERVER_PORT} "
                    f"(Thread واحد، Event Loop واحد لكل العملاء)", "ok")

    async def _handle_client(self, reader, writer):
        try:
            data = await reader.readline()
            if not data:
                return
            req = json.loads(data.decode().strip())
            cid = req.get("client_id")
            product = req.get("product", "؟")
            self.log_cb(f"📥 [السيرفر] طلب من عميل #{cid} — يبحث عن «{product}» في المخزون...", "info")

            # محاكاة عملية I/O-bound حقيقية (مثل استعلام قاعدة بيانات عن بُعد)
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)

            resp = {"client_id": cid, "product": product, "status": "ok",
                    "delay": round(delay, 3)}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()
            self.log_cb(f"📤 [السيرفر] رد على عميل #{cid} بعد {delay:.2f}s "
                        f"(المنتج متوفر ✅)", "ok")
        except Exception as e:
            self.log_cb(f"❌ [السيرفر] خطأ مع عميل: {e}", "err")
        finally:
            try:
                writer.close()
            except Exception:
                pass

    def stop(self):
        if not self.running or self.loop is None:
            return
        self.running = False

        async def _shutdown():
            if self.server:
                self.server.close()
                await self.server.wait_closed()

        try:
            fut = asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)
            fut.result(timeout=2)
        except Exception:
            pass
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        self.log_cb("⏹ تم إيقاف السيرفر", "warn")


# ═══════════════════════════════════════════════════════════════════════════════
# دوال إرسال الطلبات (Client Side) — تُستخدم من خيوط منفصلة عن واجهة Tkinter
# ═══════════════════════════════════════════════════════════════════════════════
def _send_request_blocking(client_id, product, timeout=10):
    """يفتح اتصال Socket حقيقي، يرسل طلباً، وينتظر الرد (Blocking I/O)."""
    with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=timeout) as s:
        req = json.dumps({"client_id": client_id, "product": product}) + "\n"
        s.sendall(req.encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
        return json.loads(data.decode())


def run_sequential_clients(n, log_cb):
    """طلبات متسلسلة: عميل واحد في كل مرة، الزمن الكلي = مجموع أوقات المعالجة."""
    timeline = []
    t_start = time.perf_counter()
    for i in range(n):
        cid = i + 1
        product = random.choice(PRODUCTS)
        t0 = time.perf_counter() - t_start
        log_cb(f"🔵 [متسلسل] عميل #{cid} يتصل ويطلب {product}...", "info")
        resp = _send_request_blocking(cid, product)
        t1 = time.perf_counter() - t_start
        timeline.append({"client": cid, "start": t0, "end": t1, "delay": resp.get("delay", 0)})
        log_cb(f"✅ [متسلسل] عميل #{cid} استلم الرد عند t={t1:.2f}s", "ok")
    total = time.perf_counter() - t_start
    return timeline, total, 1   # 1 = عدد Threads المُستخدَمة لجانب العميل


def run_asyncio_clients(n, log_cb):
    """
    طلبات متزامنة عبر asyncio: Thread واحد فقط + Event Loop واحد + N مهمّات
    (Tasks) — Concurrency بدون Threads إضافية.
    """
    timeline = []
    t_start = time.perf_counter()

    async def client_task(i):
        cid = i + 1
        product = random.choice(PRODUCTS)
        t0 = time.perf_counter() - t_start
        log_cb(f"🟣 [Asyncio] Task للعميل #{cid} بدأ — يطلب {product}...", "info")
        reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
        req = json.dumps({"client_id": cid, "product": product}) + "\n"
        writer.write(req.encode())
        await writer.drain()
        data = await reader.readline()
        resp = json.loads(data.decode())
        writer.close()
        t1 = time.perf_counter() - t_start
        timeline.append({"client": cid, "start": t0, "end": t1, "delay": resp.get("delay", 0)})
        log_cb(f"✅ [Asyncio] Task للعميل #{cid} استلم الرد عند t={t1:.2f}s", "ok")

    async def main():
        await asyncio.gather(*[client_task(i) for i in range(n)])

    asyncio.run(main())
    total = time.perf_counter() - t_start
    timeline.sort(key=lambda d: d["client"])
    return timeline, total, 1   # 1 = Thread واحد فقط لكل العملاء


def run_threaded_clients(n, log_cb):
    """طلبات متزامنة عبر Threads: N Thread لـ N عميل — Parallelism حقيقي."""
    timeline = []
    lock = threading.Lock()
    t_start = time.perf_counter()

    def client_thread(i):
        cid = i + 1
        product = random.choice(PRODUCTS)
        t0 = time.perf_counter() - t_start
        log_cb(f"🟠 [Threads] Thread العميل #{cid} بدأ — يطلب {product}...", "info")
        resp = _send_request_blocking(cid, product)
        t1 = time.perf_counter() - t_start
        with lock:
            timeline.append({"client": cid, "start": t0, "end": t1, "delay": resp.get("delay", 0)})
        log_cb(f"✅ [Threads] Thread العميل #{cid} استلم الرد عند t={t1:.2f}s", "ok")

    threads = [threading.Thread(target=client_thread, args=(i,), name=f"OrderClient-{i+1}")
               for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total = time.perf_counter() - t_start
    timeline.sort(key=lambda d: d["client"])
    return timeline, total, n   # n = عدد Threads المُستخدَمة (واحد لكل عميل)


MODE_FUNCS = {
    MODE_SEQ:     run_sequential_clients,
    MODE_ASYNCIO: run_asyncio_clients,
    MODE_THREADS: run_threaded_clients,
}


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: نظام طلبات أونلاين (Asyncio / Sockets)
# ═══════════════════════════════════════════════════════════════════════════════
class OnlineOrdersTab(tk.Frame):
    """
    تبويب يشغّل سيرفر Socket حقيقي بـ asyncio، ويقارن إرسال طلبات العملاء
    بـ 3 طرق: متسلسل / Asyncio (Concurrency) / Threads (Parallelism).
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        self._log_queue = _queue.Queue()
        self.server = OrderServer(log_cb=lambda m, t="info": self._log_queue.put((m, t)))

        self._result_queue = _queue.Queue()
        self.busy = False
        self.last_results = {}   # mode -> (timeline, total, threads_used)

        self._build_ui()
        self._draw_chart_placeholder()
        self._draw_compare_placeholder()
        self._poll_log()

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#0a2a1a")
        title_f.pack(fill="x")
        tk.Label(title_f, text="🌐 نظام طلبات أونلاين — Asyncio / Sockets",
                 font=("Arial", 13, "bold"), fg="#3fb950", bg="#0a2a1a").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text=f"سيرفر حقيقي على {SERVER_HOST}:{SERVER_PORT} | "
                      "Concurrency (Asyncio) مقابل Parallelism (Threads) مقابل Sequential",
                 font=("Arial", 9), fg="#2a5a3a", bg="#0a2a1a").pack(side="right", padx=10)

        # ── شريط السيرفر ──
        srv_f = tk.Frame(self, bg=BG2)
        srv_f.pack(fill="x", padx=10, pady=5)
        self.server_status_var = tk.StringVar(value="🔴 السيرفر متوقف")
        self.server_status_lbl = tk.Label(srv_f, textvariable=self.server_status_var,
                                          font=("Arial", 11, "bold"), fg=RED, bg=BG2)
        self.server_status_lbl.pack(side="right", padx=10, pady=8)
        self.start_srv_btn = self._btn(srv_f, "▶ تشغيل السيرفر", GREEN, self._on_start_server)
        self.start_srv_btn.pack(side="right", padx=4, pady=6)
        self.stop_srv_btn = self._btn(srv_f, "⏹ إيقاف السيرفر", RED, self._on_stop_server)
        self.stop_srv_btn.pack(side="right", padx=4, pady=6)
        self.stop_srv_btn.config(state="disabled")

        tk.Label(srv_f, text="عدد العملاء:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="left", padx=(10, 4))
        self.num_clients_var = tk.IntVar(value=DEFAULT_NUM_CLIENTS)
        tk.Spinbox(srv_f, from_=2, to=20, textvariable=self.num_clients_var, width=3,
                   font=("Arial", 11), bg="#1a2a3a", fg="white", relief="flat", bd=4
                   ).pack(side="left", padx=4)

        # ── شريط أزرار إرسال الطلبات ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=(0, 5))
        self.run_btns = {}
        for mode in (MODE_SEQ, MODE_ASYNCIO, MODE_THREADS):
            b = self._btn(ctrl_f, f"▶ {MODE_LABELS[mode]}", MODE_COLORS[mode],
                          lambda m=mode: self._on_run(m))
            b.pack(side="right", padx=4, pady=4)
            b.config(state="disabled")
            self.run_btns[mode] = b
        self._btn(ctrl_f, "📊 مقارنة الطرق الثلاث", PURPLE, self._on_compare).pack(side="left", padx=12, pady=4)

        self.status_var = tk.StringVar(value="ابدأ بتشغيل السيرفر أولاً")
        tk.Label(ctrl_f, textvariable=self.status_var, font=("Arial", 10, "bold"),
                 fg=YELLOW, bg=BG2).pack(side="left", padx=10)

        # ── إحصائيات حية ──
        stats_f = tk.Frame(self, bg=BG2)
        stats_f.pack(fill="x", padx=10, pady=5)
        self.total_var = tk.StringVar(value="—")
        self.threads_var = tk.StringVar(value="—")
        self.mode_var = tk.StringVar(value="—")
        for i, (lbl, var, col) in enumerate([
            ("🧭 الوضع الحالي", self.mode_var, ACCENT),
            ("⏱ الزمن الكلي", self.total_var, YELLOW),
            ("🧵 Threads (جانب العميل)", self.threads_var, "#79c0ff"),
        ]):
            fr = tk.Frame(stats_f, bg=BG2)
            fr.grid(row=0, column=i, padx=25, pady=4, sticky="ew")
            tk.Label(fr, text=lbl, fg=col, bg=BG2, font=("Arial", 10, "bold")).pack()
            tk.Label(fr, textvariable=var, fg=col, bg=BG2, font=("Arial", 16, "bold")).pack()
        for i in range(3):
            stats_f.columnconfigure(i, weight=1)

        # ── المنطقة الرئيسية ──
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        left_panel = tk.Frame(mid, bg=BG2, width=380)
        left_panel.pack(side="left", fill="both", padx=(0, 5))
        left_panel.pack_propagate(False)
        self._section_title(left_panel, "📋 سجل الاتصالات (Socket Log)")
        self.log_box = scrolledtext.ScrolledText(
            left_panel, height=18, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("info", "#8aa8c8"), ("ok", GREEN), ("warn", YELLOW),
                          ("err", RED), ("scenario", PURPLE)]:
            self.log_box.tag_config(tag, foreground=col)

        right_panel = tk.Frame(mid, bg=BG2)
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "📊 خط زمني للعملاء (Gantt) — آخر تشغيل")
        self.fig, self.ax = plt.subplots(figsize=(7, 3.4), facecolor=BG2)
        self.ax.set_facecolor(BG2)
        self.ax.tick_params(colors=FG, labelsize=8)
        for sp in self.ax.spines.values():
            sp.set_color("#1a2a3a")
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        self._section_title(right_panel, "📈 مقارنة الزمن الكلي بين الطرق الثلاث")
        self.fig_cmp, self.cmp_ax = plt.subplots(figsize=(7, 2.4), facecolor=BG2)
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

    # ── حلقة استقبال سجل السيرفر ──────────────────────────────────────────────
    def _poll_log(self):
        while True:
            try:
                msg, tag = self._log_queue.get_nowait()
            except _queue.Empty:
                break
            self._append_log(msg, tag)
        self.after(150, self._poll_log)

    # ── أوامر السيرفر ─────────────────────────────────────────────────────────
    def _on_start_server(self):
        if self.server.running:
            return
        self.server.start()
        self.server_status_var.set(f"🟢 السيرفر يعمل على {SERVER_HOST}:{SERVER_PORT}")
        self.server_status_lbl.config(fg=GREEN)
        self.start_srv_btn.config(state="disabled")
        self.stop_srv_btn.config(state="normal")
        for b in self.run_btns.values():
            b.config(state="normal")
        self.status_var.set("جاهز — اختر طريقة الإرسال")

    def _on_stop_server(self):
        if not self.server.running:
            return
        self.server.stop()
        self.server_status_var.set("🔴 السيرفر متوقف")
        self.server_status_lbl.config(fg=RED)
        self.start_srv_btn.config(state="normal")
        self.stop_srv_btn.config(state="disabled")
        for b in self.run_btns.values():
            b.config(state="disabled")
        self.status_var.set("ابدأ بتشغيل السيرفر أولاً")

    # ── أوامر إرسال الطلبات ──────────────────────────────────────────────────
    def _on_run(self, mode):
        if self.busy or not self.server.running:
            return
        n = self.num_clients_var.get()
        self.busy = True
        self._set_run_buttons_state("disabled")
        self.status_var.set(f"⏳ يعمل: {MODE_LABELS[mode]}...")
        self.mode_var.set(MODE_LABELS[mode].split(" ")[0])
        self._append_log(f"▶ بدء إرسال {n} طلب — {MODE_LABELS[mode]}", "scenario")

        func = MODE_FUNCS[mode]
        t = threading.Thread(target=self._worker_run, args=(mode, func, n), daemon=True)
        t.start()
        self.after(100, self._poll_results)

    def _on_compare(self):
        if self.busy or not self.server.running:
            if not self.server.running:
                self._append_log("⚠ شغّل السيرفر أولاً قبل المقارنة", "warn")
            return
        n = self.num_clients_var.get()
        self.busy = True
        self._set_run_buttons_state("disabled")
        self.status_var.set("⏳ تشغيل الطرق الثلاث للمقارنة...")
        self._append_log(f"▶ بدء مقارنة شاملة — {n} عملاء لكل طريقة", "scenario")

        modes = [MODE_SEQ, MODE_ASYNCIO, MODE_THREADS]
        t = threading.Thread(target=self._worker_run_all, args=(modes, n), daemon=True)
        t.start()
        self.after(100, self._poll_results)

    def _set_run_buttons_state(self, state):
        for b in self.run_btns.values():
            b.config(state=state if self.server.running else "disabled")

    # ── خيوط التنفيذ ──────────────────────────────────────────────────────────
    def _worker_run(self, mode, func, n):
        try:
            timeline, total, threads_used = func(
                n, lambda m, t="info": self._log_queue.put((m, t)))
            self._result_queue.put(("done", mode, timeline, total, threads_used))
        except Exception as e:
            self._result_queue.put(("error", mode, None, str(e), 0))
        self._result_queue.put(("single_done", None, None, None, None))

    def _worker_run_all(self, modes, n):
        for mode in modes:
            try:
                func = MODE_FUNCS[mode]
                timeline, total, threads_used = func(
                    n, lambda m, t="info": self._log_queue.put((m, t)))
                self._result_queue.put(("done", mode, timeline, total, threads_used))
            except Exception as e:
                self._result_queue.put(("error", mode, None, str(e), 0))
        self._result_queue.put(("all_done", None, None, None, None))

    # ── استقبال النتائج ───────────────────────────────────────────────────────
    def _poll_results(self):
        while True:
            try:
                kind, mode, timeline, total, threads_used = self._result_queue.get_nowait()
            except _queue.Empty:
                break

            if kind == "done":
                self.last_results[mode] = (timeline, total, threads_used)
                self.total_var.set(f"{total:.2f}s")
                self.threads_var.set(str(threads_used))
                self._append_log(
                    f"✅ {MODE_LABELS[mode]} انتهى — الزمن الكلي={total:.2f}s، "
                    f"Threads المُستخدَمة (جانب العميل)={threads_used}", "ok")
                self._draw_chart(mode, timeline, total)

            elif kind == "error":
                self._append_log(f"❌ خطأ في {MODE_LABELS.get(mode, mode)}: {total}", "err")

            elif kind == "single_done":
                self.busy = False
                self._set_run_buttons_state("normal")
                self.status_var.set("جاهز — اختر طريقة الإرسال")

            elif kind == "all_done":
                self.busy = False
                self._set_run_buttons_state("normal")
                self.status_var.set("✅ انتهت المقارنة")
                self._draw_compare()
                self._log_comparison_summary()

        if self.busy:
            self.after(100, self._poll_results)

    def _log_comparison_summary(self):
        if all(m in self.last_results for m in (MODE_SEQ, MODE_ASYNCIO, MODE_THREADS)):
            seq_t = self.last_results[MODE_SEQ][1]
            asy_t = self.last_results[MODE_ASYNCIO][1]
            thr_t = self.last_results[MODE_THREADS][1]
            self._append_log(
                f"📊 النتيجة: متسلسل={seq_t:.2f}s | Asyncio={asy_t:.2f}s "
                f"(Thread واحد) | Threads={thr_t:.2f}s "
                f"({self.last_results[MODE_THREADS][2]} Threads)", "scenario")
            self._append_log(
                "🔎 لاحظ: Asyncio و Threads كلاهما أسرع بكثير من المتسلسل "
                "(Concurrency يقلّل الانتظار)، لكن Asyncio حقّق نتيجة مشابهة "
                "لـ Threads باستخدام Thread واحد فقط — لذلك يُفضَّل في "
                "سيرفرات تستقبل آلاف الاتصالات المتزامنة.", "scenario")

    # ── الرسم: الخط الزمني للعملاء (Gantt) ────────────────────────────────────
    def _draw_chart_placeholder(self):
        self.ax.clear()
        self.ax.set_facecolor(BG2)
        self.ax.tick_params(colors=FG, labelsize=8)
        for sp in self.ax.spines.values():
            sp.set_color("#1a2a3a")
        self.ax.text(0.5, 0.5, "شغّل السيرفر ثم اختر طريقة إرسال الطلبات",
                     ha="center", va="center", color="#5a7a9a",
                     fontsize=9, transform=self.ax.transAxes)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw_idle()

    def _draw_chart(self, mode, timeline, total):
        self.ax.clear()
        self.ax.set_facecolor(BG2)
        self.ax.tick_params(colors=FG, labelsize=8)
        for sp in self.ax.spines.values():
            sp.set_color("#1a2a3a")

        color = MODE_COLORS[mode]
        for item in timeline:
            self.ax.barh(item["client"], item["end"] - item["start"],
                         left=item["start"], height=0.6, color=color, alpha=0.85,
                         edgecolor="white", linewidth=0.5)
            self.ax.text(item["end"] + 0.02, item["client"],
                         f"{item['delay']:.2f}s", va="center", color=FG, fontsize=8)

        self.ax.set_xlabel("الزمن (ثانية)", color=FG, fontsize=8)
        self.ax.set_ylabel("رقم العميل", color=FG, fontsize=8)
        self.ax.set_yticks([item["client"] for item in timeline])
        self.ax.set_title(f"{MODE_LABELS[mode]} — الزمن الكلي = {total:.2f}s",
                         color=FG, fontsize=9)
        self.ax.set_xlim(0, max(total * 1.15, 0.5))

        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ── الرسم: مقارنة الزمن الكلي ─────────────────────────────────────────────
    def _draw_compare_placeholder(self):
        self.cmp_ax.clear()
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")
        self.cmp_ax.text(0.5, 0.5, "اضغط 'مقارنة الطرق الثلاث' لعرض النتائج",
                         ha="center", va="center", color="#5a7a9a",
                         fontsize=9, transform=self.cmp_ax.transAxes)
        self.cmp_ax.set_xticks([])
        self.cmp_ax.set_yticks([])
        self.cmp_canvas.draw_idle()

    def _draw_compare(self):
        self.cmp_ax.clear()
        self.cmp_ax.set_facecolor(BG2)
        self.cmp_ax.tick_params(colors=FG, labelsize=8)
        for sp in self.cmp_ax.spines.values():
            sp.set_color("#1a2a3a")

        modes = [MODE_SEQ, MODE_ASYNCIO, MODE_THREADS]
        labels = [MODE_LABELS[m].split(" ")[0] for m in modes]
        totals = [self.last_results[m][1] if m in self.last_results else 0 for m in modes]
        colors = [MODE_COLORS[m] for m in modes]

        bars = self.cmp_ax.bar(labels, totals, color=colors)
        for b, t, m in zip(bars, totals, modes):
            extra = ""
            if m in self.last_results:
                extra = f"\n({self.last_results[m][2]} Thread)"
            self.cmp_ax.text(b.get_x() + b.get_width() / 2, t + max(totals) * 0.02,
                             f"{t:.2f}s{extra}", ha="center", color=FG, fontsize=8, fontweight="bold")
        self.cmp_ax.set_ylabel("الزمن الكلي (ثانية)", color=FG, fontsize=8)
        self.cmp_ax.set_title("مقارنة الزمن الكلي لإرسال نفس عدد الطلبات", color=FG, fontsize=9)
        self.fig_cmp.tight_layout()
        self.cmp_canvas.draw_idle()
