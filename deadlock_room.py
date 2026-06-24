# ══════════════════════════════════════════════════════════════════════════════
# ميزة جديدة (1): تبويب Deadlock تفاعلي — محاكاة "غرفة استراحة الموظفين"
# (Dining Philosophers Problem)
# ══════════════════════════════════════════════════════════════════════════════
#
# الشرح المفاهيمي:
# -----------------
# 5 موظفين (Threads) يجلسون حول طاولة استراحة دائرية، وعلى الطاولة 5 أدوات
# مشتركة (☕ إبريق قهوة / 🥄 ملعقة / 🍯 سكر / 🥛 حليب / 📰 جريدة) — كل أداة
# مُمثَّلة بـ threading.Lock().
#
# لكي يأخذ الموظف رقم i استراحة، يحتاج إلى الأداة على يساره (i) والأداة على
# يمينه ((i+1) % 5) في نفس الوقت — وهذا هو التجسيد الكلاسيكي لمشكلة
# Dining Philosophers في أنظمة التشغيل.
#
# Deadlock الحقيقي:
#   إذا حاول كل الموظفين أخذ "الأداة اليسرى" أولاً، فقد يحصل كل واحد منهم على
#   أداته اليسرى وينتظر إلى الأبد الأداة اليمنى (التي يحملها جاره) → دورة
#   انتظار دائرية (Circular Wait) = الشرط الرابع من الشروط الأربعة لـ Deadlock
#   (Mutual Exclusion + Hold & Wait + No Preemption + Circular Wait).
#
# هذا الملف يدمج مباشرة مع DeadlockDetector الموجود في core.py:
#   - عند الانتظار: deadlock_detector.thread_waiting(اسمي, اسم_من_يحمل_المورد)
#   - عند الحصول:   deadlock_detector.thread_acquired(اسمي, "tool_X")
#   - عند التحرير:  deadlock_detector.thread_released(اسمي, "tool_X")
# بهذه الطريقة يصبح _lock_graph = {موظف_منتظر: موظف_يحمل_المورد}، فإذا تشكّلت
# دورة كاملة بين الموظفين الخمسة، فإن _detect_cycle() (الموجودة أصلاً في
# core.py) ستكتشفها فعلياً ضمن مراقب الـ Deadlock العام لكل التطبيق، وتُفعّل
# نفس تنبيه "⚠ Deadlock محتمل" في الشريط العلوي (_on_deadlock).
#
# حلول الـ Deadlock المتاحة في هذا التبويب:
#   1) بدون حل          → لإظهار الجمود الحقيقي للمدرّس.
#   2) Resource Ordering → كل الموظفين يحصلون على الأداة ذات الرقم الأصغر أولاً
#                          (Deadlock Prevention عبر ترتيب الموارد).
#   3) Banker's Algorithm → خوارزمية المصرفي: لا يُمنح أي مورد إلا إذا بقي
#                          النظام في "حالة أمان" (Safe State) يمكن منها إنهاء
#                          جميع العمليات.
#
# عند حدوث Deadlock حقيقي (وضع "بدون حل")، يظهر زر "🚨 حل الجمود" الذي يطبّق
# Resource Preemption: انتزاع مورد من أحد الموظفين العالقين في الدورة لإجباره
# على التنازل، فتنكسر الدورة ويستمر الجميع.
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import random
import math
import queue as _queue

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import (
    BG, BG2, BG3, ACCENT, FG, BLUE, GREEN, RED, YELLOW, PURPLE, GRAY,
    _ts, _styled_log
)
from core import deadlock_detector


# ── ثوابت المحاكاة ────────────────────────────────────────────────────────────
NUM_EMPLOYEES = 5

EMPLOYEE_NAMES = ["سارة", "أحمد", "ليلى", "محمد", "نور"]
EMPLOYEE_ICONS = ["👩", "👨", "👩‍🦰", "🧑", "👱‍♀️"]

TOOL_NAMES  = ["إبريق القهوة", "الملعقة", "السكر", "الحليب", "الجريدة"]
TOOL_ICONS  = ["☕", "🥄", "🍯", "🥛", "📰"]

# أسماء الخيوط — تُستخدم كمعرّفات في DeadlockDetector العام (core.py)
THREAD_NAMES = [f"BreakRoom-{name}" for name in EMPLOYEE_NAMES]

# حالات الموظف
STATE_THINKING  = "THINKING"
STATE_HUNGRY    = "HUNGRY"
STATE_HOLDING1  = "HOLDING1"
STATE_BREAK     = "ON_BREAK"
STATE_PREEMPTED = "PREEMPTED"

STATE_LABELS = {
    STATE_THINKING:  ("🤔 يفكّر",            "#8aa8c8"),
    STATE_HUNGRY:    ("🍽 يريد استراحة",     YELLOW),
    STATE_HOLDING1:  ("✋ يحمل أداة وينتظر",  "#d29922"),
    STATE_BREAK:     ("☕ في استراحة",        GREEN),
    STATE_PREEMPTED: ("🔁 تم انتزاع موارده",  RED),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Banker's Algorithm — فحص حالة الأمان (Safety Check)
# ═══════════════════════════════════════════════════════════════════════════════
def _is_safe_state(available, allocation, need):
    """
    تُعيد True إذا كانت الحالة (available, allocation, need) "آمنة" — أي
    يوجد تسلسل تنفيذ يمكن من خلاله إكمال جميع العمليات (الموظفين) دون الدخول
    في Deadlock.

    available  : set[int]      — الأدوات المتاحة حالياً (غير مخصَّصة لأحد)
    allocation : {idx: set[int]} — الأدوات التي يملكها كل موظف حالياً
    need       : {idx: set[int]} — الأدوات التي ما زال يحتاجها كل موظف
    """
    avail = set(available)
    finished = set()
    progressed = True
    while progressed and len(finished) < NUM_EMPLOYEES:
        progressed = False
        for i in range(NUM_EMPLOYEES):
            if i in finished:
                continue
            if need[i] <= avail:
                # الموظف i يمكنه إنهاء استراحته وإعادة كل أدواته (التي يملكها
                # حالياً + التي حصل عليها الآن) إلى available
                avail = avail | allocation[i] | need[i]
                finished.add(i)
                progressed = True
    return len(finished) == NUM_EMPLOYEES


# ═══════════════════════════════════════════════════════════════════════════════
# محاكاة غرفة الاستراحة (Dining Philosophers)
# ═══════════════════════════════════════════════════════════════════════════════
class BreakRoomSimulation:
    """
    محاكاة Dining Philosophers مع 3 أوضاع:
      - FIX_NONE     : بدون أي وقاية → Deadlock حقيقي محتمل (Circular Wait)
      - FIX_ORDERING : Deadlock Prevention عبر Resource Ordering
      - FIX_BANKERS  : Deadlock Avoidance عبر Banker's Algorithm
    """
    FIX_NONE     = "none"
    FIX_ORDERING = "ordering"
    FIX_BANKERS  = "bankers"

    def __init__(self, log_cb=None):
        # log_cb(msg, tag) — يُستدعى من خيوط الموظفين، يجب أن يكون Thread-Safe
        self.log_cb = log_cb or (lambda *a, **k: None)

        # قفل داخلي يحمي بيانات الحالة المعروضة في الواجهة
        self._state_lock = threading.Lock()

        self.fix_mode = self.FIX_NONE
        self.running = False
        self.stop_event = threading.Event()
        self.threads = []

        # الأدوات الخمسة كـ Locks حقيقية (لوضعَي None / Ordering)
        self.tools = [threading.Lock() for _ in range(NUM_EMPLOYEES)]
        # tool_holder[t] = رقم الموظف الذي يملك الأداة t حالياً أو None
        self.tool_holder = [None] * NUM_EMPLOYEES
        # waiting_for[i] = رقم الأداة التي ينتظرها الموظف i حالياً أو None
        self.waiting_for = [None] * NUM_EMPLOYEES
        # حالة كل موظف للعرض
        self.status = [STATE_THINKING] * NUM_EMPLOYEES
        # عدّاد الاستراحات المُكتمَلة لكل موظف (للإحصاء — يُستخدم لإظهار التجويع)
        self.completed = [0] * NUM_EMPLOYEES

        # أعلام انتزاع الموارد (Resource Preemption) — تُستخدم لحل الجمود
        self.preempt_flags = [threading.Event() for _ in range(NUM_EMPLOYEES)]

        # حالة Deadlock المكتشفة محلياً (لرسم Wait-for Graph)
        self.deadlock_active = False
        self.cycle_nodes = set()

        # ── بيانات Banker's Algorithm ──
        self._bankers_lock = threading.Lock()
        self.available = set(range(NUM_EMPLOYEES))
        self.allocation = {i: set() for i in range(NUM_EMPLOYEES)}
        self.need = {i: {i, (i + 1) % NUM_EMPLOYEES} for i in range(NUM_EMPLOYEES)}

        # ── Barrier لمزامنة الانطلاقة الأولى في وضع "بدون حل" ──
        # الهدف: إجبار الموظفين الخمسة على طلب أداتهم اليسرى في نفس اللحظة
        # تقريباً، فيحصل كل واحد على أداته اليسرى (لا تضارب بينها لأنها 5
        # أدوات مختلفة) ثم ينتظر جميعهم الأداة اليمنى التي يحملها جاره →
        # Circular Wait حقيقية = Deadlock فعلي يمكن عرضه للمدرّس مباشرة.
        self._start_barrier = None
        self._mid_barrier = None
        self._barrier_used = threading.Event()

    # ── دورة حياة المحاكاة ───────────────────────────────────────────────────
    def start(self, fix_mode):
        if self.running:
            return
        self.fix_mode = fix_mode
        self.stop_event.clear()
        self.running = True

        # إعادة تهيئة كامل الحالة لجولة جديدة
        self.tools = [threading.Lock() for _ in range(NUM_EMPLOYEES)]
        self.tool_holder = [None] * NUM_EMPLOYEES
        self.waiting_for = [None] * NUM_EMPLOYEES
        self.status = [STATE_THINKING] * NUM_EMPLOYEES
        self.completed = [0] * NUM_EMPLOYEES
        self.deadlock_active = False
        self.cycle_nodes = set()
        for ev in self.preempt_flags:
            ev.clear()
        self.available = set(range(NUM_EMPLOYEES))
        self.allocation = {i: set() for i in range(NUM_EMPLOYEES)}
        self.need = {i: {i, (i + 1) % NUM_EMPLOYEES} for i in range(NUM_EMPLOYEES)}

        # ── إعداد Barrier المزامنة (فقط لوضع "بدون حل") ──
        if fix_mode == self.FIX_NONE:
            self._start_barrier = threading.Barrier(NUM_EMPLOYEES)
            self._mid_barrier = threading.Barrier(NUM_EMPLOYEES)
        else:
            self._start_barrier = None
            self._mid_barrier = None
        self._barrier_used.clear()

        mode_label = {
            self.FIX_NONE:     "بدون حل (Deadlock محتمل حقيقي)",
            self.FIX_ORDERING: "🛡 Resource Ordering (وقاية)",
            self.FIX_BANKERS:  "🏦 Banker's Algorithm (تجنّب)",
        }[fix_mode]
        self.log_cb(f"▶ بدأت محاكاة غرفة الاستراحة — الوضع: {mode_label}", "scenario")

        self.threads = []
        for i in range(NUM_EMPLOYEES):
            t = threading.Thread(
                target=self._employee_worker, args=(i,),
                daemon=True, name=THREAD_NAMES[i]
            )
            self.threads.append(t)
            t.start()

    def stop(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running = False
        # تحرير أي خيط قد يكون عالقاً في حلقة الانتظار (Polling)
        for ev in self.preempt_flags:
            ev.set()
        # تحرير أي خيط عالق عند الـ Barrier (لو لم يكتمل التزامن بعد)
        if self._start_barrier is not None:
            try:
                self._start_barrier.abort()
            except Exception:
                pass
        if self._mid_barrier is not None:
            try:
                self._mid_barrier.abort()
            except Exception:
                pass
        # تنظيف تسجيلات الانتظار من DeadlockDetector العام
        for name in THREAD_NAMES:
            deadlock_detector.thread_acquired(name, "__released__")
        self.log_cb("⏹ أُوقفت محاكاة غرفة الاستراحة", "warn")

    # ── أداة مساعدة: نوم قابل للمقاطعة ───────────────────────────────────────
    def _sleep(self, seconds):
        end = time.time() + seconds
        while not self.stop_event.is_set():
            remaining = end - time.time()
            if remaining <= 0:
                return
            time.sleep(min(0.1, remaining))

    # ── محاولة الحصول على أداة بطريقة Polling قابلة للانتزاع ─────────────────
    def _acquire_tool(self, idx, tool_idx):
        """
        يحاول الحصول على Lock الأداة tool_idx.
        - يُسجِّل الانتظار في DeadlockDetector العام (waiter -> holder).
        - يتحقّق دورياً من preempt_flags[idx] (انتزاع الموارد) و stop_event.
        يُعيد True عند النجاح، False إذا تم إيقافه أو انتزاع موارده.
        """
        name = THREAD_NAMES[idx]
        while not self.stop_event.is_set():
            if self.preempt_flags[idx].is_set():
                return False

            if self.tools[tool_idx].acquire(timeout=0.2):
                with self._state_lock:
                    self.tool_holder[tool_idx] = idx
                    self.waiting_for[idx] = None
                deadlock_detector.thread_acquired(name, f"tool_{tool_idx}")
                return True

            # لم نحصل عليها بعد — سجّل من نحن ننتظر (لرسم Wait-for Graph)
            with self._state_lock:
                self.waiting_for[idx] = tool_idx
                holder = self.tool_holder[tool_idx]
            if holder is not None:
                # الأهم: نُسجِّل أننا ننتظر "الخيط" الذي يحمل المورد
                # (لا اسم المورد) — هكذا يصبح _lock_graph عبارة عن
                # waiter -> holder ويستطيع _detect_cycle الموجود في
                # core.py اكتشاف الدورة الحقيقية بين الموظفين.
                deadlock_detector.thread_waiting(name, THREAD_NAMES[holder])

        return False

    def _release_tool(self, idx, tool_idx):
        name = THREAD_NAMES[idx]
        try:
            self.tools[tool_idx].release()
        except RuntimeError:
            pass
        with self._state_lock:
            self.tool_holder[tool_idx] = None
        deadlock_detector.thread_released(name, f"tool_{tool_idx}")

    # ── Banker's Algorithm: طلب وتحرير ────────────────────────────────────────
    def _bankers_acquire(self, idx, left, right):
        name = THREAD_NAMES[idx]
        needed = [left, right]
        while needed and not self.stop_event.is_set():
            tool = needed[0]
            granted = False
            with self._bankers_lock:
                if tool in self.available:
                    new_avail = self.available - {tool}
                    new_alloc = {i: set(v) for i, v in self.allocation.items()}
                    new_alloc[idx].add(tool)
                    new_need = {i: set(v) for i, v in self.need.items()}
                    new_need[idx].discard(tool)
                    if _is_safe_state(new_avail, new_alloc, new_need):
                        self.available = new_avail
                        self.allocation = new_alloc
                        self.need = new_need
                        granted = True

            if granted:
                with self._state_lock:
                    self.tool_holder[tool] = idx
                    self.waiting_for[idx] = None
                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] ✅ Banker's سمح بمنح "
                    f"{TOOL_ICONS[tool]} {TOOL_NAMES[tool]} (الحالة آمنة)", "sync"
                )
                needed.pop(0)
            else:
                with self._state_lock:
                    self.waiting_for[idx] = tool
                holder = self.tool_holder[tool]
                if holder is not None:
                    deadlock_detector.thread_waiting(name, THREAD_NAMES[holder])
                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] ⏳ Banker's: منح "
                    f"{TOOL_ICONS[tool]} {TOOL_NAMES[tool]} غير آمن الآن — ينتظر...",
                    "warn"
                )
                self._sleep(0.35)

        with self._state_lock:
            self.waiting_for[idx] = None
        deadlock_detector.thread_acquired(name, f"banker_{idx}")
        return not self.stop_event.is_set()

    def _bankers_release(self, idx, left, right):
        name = THREAD_NAMES[idx]
        with self._bankers_lock:
            for t in (left, right):
                self.allocation[idx].discard(t)
                self.available.add(t)
                with self._state_lock:
                    self.tool_holder[t] = None
            self.need[idx] = {left, right}
        deadlock_detector.thread_released(name, f"banker_{idx}")
        self.log_cb(
            f"[{EMPLOYEE_NAMES[idx]}] 🔓 حرَّر أدواته (Banker's) — انتهت استراحته", "ok"
        )

    # ── حل الجمود: Resource Preemption ───────────────────────────────────────
    def force_resolve(self):
        """
        يطبّق Resource Preemption: ينتزع موارد أحد الموظفين العالقين في دورة
        الانتظار (Wait-for Cycle) لإجباره على التنازل عنها وكسر الـ Deadlock.
        """
        with self._state_lock:
            cycle = list(self.cycle_nodes)
        if not cycle:
            return False
        victim = min(cycle)
        self.preempt_flags[victim].set()
        self.log_cb(
            f"🚨 [استعادة الموارد] تم اختيار {EMPLOYEE_ICONS[victim]} "
            f"{EMPLOYEE_NAMES[victim]} كضحية (Victim) — انتزاع موارده لكسر "
            f"الـ Deadlock (Resource Preemption)", "err"
        )
        return True

    # ── العامل الرئيسي لكل موظف (Thread) ─────────────────────────────────────
    def _employee_worker(self, idx):
        name = EMPLOYEE_NAMES[idx]
        left, right = idx, (idx + 1) % NUM_EMPLOYEES

        while not self.stop_event.is_set():
            # ── 1) يفكّر (THINKING) ──
            with self._state_lock:
                self.status[idx] = STATE_THINKING
                self.waiting_for[idx] = None
            self.log_cb(f"[{EMPLOYEE_NAMES[idx]}] 🤔 يفكّر...", "info")
            self._sleep(random.uniform(0.6, 1.4))
            if self.stop_event.is_set():
                break

            # ── 2) يصبح جائعاً (HUNGRY) ويحدد ترتيب الطلب ──
            with self._state_lock:
                self.status[idx] = STATE_HUNGRY
            self.log_cb(
                f"[{EMPLOYEE_NAMES[idx]}] 🍽 يريد استراحة — يحتاج "
                f"{TOOL_ICONS[left]} {TOOL_NAMES[left]} و "
                f"{TOOL_ICONS[right]} {TOOL_NAMES[right]}", "warn"
            )

            # ── مزامنة الانطلاقة الأولى (وضع "بدون حل" فقط) ──
            # يجعل الخمسة يطلبون أداتهم اليسرى في نفس اللحظة تقريباً، فيحصل
            # كل واحد عليها بسهولة (لا تضارب)، ثم يصطفّون جميعاً في انتظار
            # الأداة اليمنى → Circular Wait حقيقية = Deadlock فعلي.
            if (self.fix_mode == self.FIX_NONE and self._start_barrier is not None
                    and not self._barrier_used.is_set()):
                try:
                    self._start_barrier.wait(timeout=3.0)
                except threading.BrokenBarrierError:
                    pass

            if self.fix_mode == self.FIX_BANKERS:
                ok = self._bankers_acquire(idx, left, right)
                if not ok:
                    break
                first = second = None  # غير مستخدم في هذا الوضع
            else:
                order = (left, right)
                if self.fix_mode == self.FIX_ORDERING:
                    # Resource Ordering: نحصل دائماً على الأداة ذات الرقم
                    # الأصغر أولاً — يكسر إمكانية تشكّل دورة Circular Wait
                    order = tuple(sorted((left, right)))
                first, second = order

                # ── أداة 1 ──
                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] ⏳ ينتظر "
                    f"{TOOL_ICONS[first]} {TOOL_NAMES[first]}...", "warn"
                )
                if not self._acquire_tool(idx, first):
                    self.log_cb(
                        f"[{EMPLOYEE_NAMES[idx]}] 🔁 تم انتزاع الدور قبل "
                        f"الحصول على أي أداة — يعيد المحاولة", "err"
                    )
                    self.preempt_flags[idx].clear()
                    with self._state_lock:
                        self.status[idx] = STATE_PREEMPTED
                    continue

                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] 🔒 حصل على "
                    f"{TOOL_ICONS[first]} {TOOL_NAMES[first]}", "sync"
                )
                with self._state_lock:
                    self.status[idx] = STATE_HOLDING1

                # ── مزامنة ثانية (وضع "بدون حل" فقط) ──
                # ننتظر حتى يحصل الجميع على أداتهم اليسرى أولاً (دون تضارب
                # لأنها 5 أدوات مختلفة)، ثم ينطلق الجميع معاً لطلب الأداة
                # اليمنى — التي يحملها الجار بالضبط → Circular Wait مضمونة.
                if (self.fix_mode == self.FIX_NONE and self._mid_barrier is not None
                        and not self._barrier_used.is_set()):
                    try:
                        self._mid_barrier.wait(timeout=3.0)
                    except threading.BrokenBarrierError:
                        pass
                    self._barrier_used.set()

                # ── أداة 2 ──
                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] ⏳ ينتظر "
                    f"{TOOL_ICONS[second]} {TOOL_NAMES[second]}...", "warn"
                )
                if not self._acquire_tool(idx, second):
                    # تم انتزاعه — يحرّر الأداة الأولى ويعيد المحاولة
                    self._release_tool(idx, first)
                    self.log_cb(
                        f"[{EMPLOYEE_NAMES[idx]}] 🔁 [Resource Preemption] "
                        f"تم انتزاع {TOOL_ICONS[first]} {TOOL_NAMES[first]} منه "
                        f"— يعيد المحاولة من البداية", "err"
                    )
                    self.preempt_flags[idx].clear()
                    with self._state_lock:
                        self.status[idx] = STATE_PREEMPTED
                    continue

                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] 🔒 حصل على "
                    f"{TOOL_ICONS[second]} {TOOL_NAMES[second]} — "
                    f"يملك الآن كل ما يحتاجه!", "sync"
                )

            if self.stop_event.is_set():
                break

            # ── 3) في استراحة (ON_BREAK) ──
            with self._state_lock:
                self.status[idx] = STATE_BREAK
            self.log_cb(f"[{EMPLOYEE_NAMES[idx]}] ☕ يأخذ استراحته الآن...", "ok")
            self._sleep(random.uniform(0.8, 1.6))

            # ── 4) تحرير الأدوات ──
            if self.fix_mode == self.FIX_BANKERS:
                self._bankers_release(idx, left, right)
            else:
                self._release_tool(idx, first)
                self._release_tool(idx, second)
                self.log_cb(
                    f"[{EMPLOYEE_NAMES[idx]}] 🔓 حرَّر "
                    f"{TOOL_ICONS[first]} {TOOL_NAMES[first]} و "
                    f"{TOOL_ICONS[second]} {TOOL_NAMES[second]} — انتهت استراحته", "ok"
                )

            with self._state_lock:
                self.completed[idx] += 1
                self.status[idx] = STATE_THINKING
                self.waiting_for[idx] = None

    # ── حساب Wait-for Graph + اكتشاف الدورة (للعرض المحلي السريع) ────────────
    def compute_wait_graph(self):
        """
        يُعيد (edges, cycle_nodes):
          edges       : {موظف_منتظر: موظف_يحمل_ما_يريده}
          cycle_nodes : مجموعة الموظفين المشاركين في دورة انتظار (Deadlock)
        ويُحدِّث self.deadlock_active و self.cycle_nodes.
        """
        with self._state_lock:
            waiting_for = list(self.waiting_for)
            tool_holder = list(self.tool_holder)

        edges = {}
        for i in range(NUM_EMPLOYEES):
            t = waiting_for[i]
            if t is None:
                continue
            holder = tool_holder[t]
            if holder is not None and holder != i:
                edges[i] = holder

        cycle_nodes = set()
        for start in edges:
            seen = []
            node = start
            visited = set()
            while node in edges and node not in visited:
                visited.add(node)
                seen.append(node)
                node = edges[node]
            if node in seen:
                i0 = seen.index(node)
                cycle_nodes.update(seen[i0:])

        with self._state_lock:
            self.deadlock_active = len(cycle_nodes) >= 2
            self.cycle_nodes = cycle_nodes

        return edges, cycle_nodes

    # ── لقطة حالة كاملة (لتحديث الواجهة بأمان) ────────────────────────────────
    def snapshot(self):
        with self._state_lock:
            return {
                "status":      list(self.status),
                "tool_holder": list(self.tool_holder),
                "waiting_for": list(self.waiting_for),
                "completed":   list(self.completed),
                "deadlock":    self.deadlock_active,
                "cycle":       set(self.cycle_nodes),
            }


# ═══════════════════════════════════════════════════════════════════════════════
# تبويب الواجهة: غرفة استراحة الموظفين (Deadlock تفاعلي)
# ═══════════════════════════════════════════════════════════════════════════════
class DeadlockRoomTab(tk.Frame):
    """
    تبويب كامل يعرض محاكاة Dining Philosophers مع:
      - أزرار التحكم (اختيار وضع الحل + تشغيل/إيقاف + حل الجمود)
      - شبكة حالة الموظفين الخمسة (Live)
      - رسم Wait-for Graph تفاعلي بـ matplotlib
      - سجل أحداث مباشر (Live Log)
      - مؤشر تنبيه Deadlock أحمر عند اكتشاف دورة انتظار حقيقية
    """

    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        # طابور رسائل السجل — الخيوط تكتب هنا، الواجهة تقرأ بأمان
        self._log_queue = _queue.Queue()

        self.sim = BreakRoomSimulation(
            log_cb=lambda msg, tag="info": self._log_queue.put((msg, tag))
        )

        self._build_ui()
        self._tick()  # بدء حلقة تحديث الواجهة

    # ── بناء الواجهة ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── العنوان ──
        title_f = tk.Frame(self, bg="#1a1206")
        title_f.pack(fill="x")
        tk.Label(title_f, text="🍵 غرفة استراحة الموظفين — Dining Philosophers (Deadlock)",
                 font=("Arial", 13, "bold"), fg="#ffb454", bg="#1a1206").pack(side="right", padx=20, pady=8)
        tk.Label(title_f,
                 text="5 موظفين يتشاركون 5 أدوات — كل موظف يحتاج الأداتين المجاورتين له ليأخذ استراحة",
                 font=("Arial", 9), fg="#8a6a3a", bg="#1a1206").pack(side="right", padx=10)

        # ── مؤشر Deadlock ──
        self.deadlock_banner = tk.Label(
            self, text="", font=("Arial", 12, "bold"),
            fg="white", bg=BG, pady=4
        )
        self.deadlock_banner.pack(fill="x")

        # ── شريط التحكم ──
        ctrl_f = tk.Frame(self, bg=BG2)
        ctrl_f.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl_f, text="طريقة الحل:", font=("Arial", 10, "bold"),
                 fg=FG, bg=BG2).pack(side="right", padx=(10, 4), pady=8)

        self.fix_mode_var = tk.StringVar(value=BreakRoomSimulation.FIX_NONE)
        for value, label, col in [
            (BreakRoomSimulation.FIX_NONE,     "🚫 بدون حل (Deadlock حقيقي)", RED),
            (BreakRoomSimulation.FIX_ORDERING, "🛡 Resource Ordering",        BLUE),
            (BreakRoomSimulation.FIX_BANKERS,  "🏦 Banker's Algorithm",       GREEN),
        ]:
            tk.Radiobutton(
                ctrl_f, text=label, variable=self.fix_mode_var, value=value,
                bg=BG2, fg=col, selectcolor="#1a2a3a", activebackground=BG2,
                font=("Arial", 10, "bold")
            ).pack(side="right", padx=6)

        self.start_btn = self._btn(ctrl_f, "▶ تشغيل", GREEN, self._on_start)
        self.start_btn.pack(side="left", padx=4, pady=6)
        self.stop_btn = self._btn(ctrl_f, "⏹ إيقاف", RED, self._on_stop)
        self.stop_btn.pack(side="left", padx=4, pady=6)
        self.resolve_btn = self._btn(ctrl_f, "🚨 حل الجمود (Preemption)", "#6a2a8a", self._on_resolve)
        self.resolve_btn.pack(side="left", padx=4, pady=6)
        self.resolve_btn.config(state="disabled")

        # ── المنطقة الوسطى: حالة الموظفين + الرسم البياني ──
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=10, pady=5)

        # -- لوحة حالة الموظفين (يسار) --
        left_panel = tk.Frame(mid, bg=BG2, width=300)
        left_panel.pack(side="left", fill="y", padx=(0, 5))
        left_panel.pack_propagate(False)
        self._section_title(left_panel, "👥 حالة الموظفين (Live)")

        self.emp_rows = []
        for i in range(NUM_EMPLOYEES):
            row = tk.Frame(left_panel, bg=BG3, highlightthickness=1,
                           highlightbackground="#1a2a3a")
            row.pack(fill="x", padx=8, pady=3)

            name_lbl = tk.Label(
                row, text=f"{EMPLOYEE_ICONS[i]} {EMPLOYEE_NAMES[i]}",
                font=("Arial", 10, "bold"), fg=ACCENT, bg=BG3, width=14, anchor="e"
            )
            name_lbl.pack(side="right", padx=6, pady=4)

            status_var = tk.StringVar(value="🤔 يفكّر")
            status_lbl = tk.Label(row, textvariable=status_var, font=("Arial", 9),
                                  fg="#8aa8c8", bg=BG3, anchor="w", width=18)
            status_lbl.pack(side="left", padx=6, pady=4, fill="x", expand=True)

            self.emp_rows.append({"frame": row, "status_var": status_var, "status_lbl": status_lbl})

        # -- لوحة حالة الأدوات --
        self._section_title(left_panel, "🧰 حالة الأدوات (Live)")
        self.tool_rows = []
        for t in range(NUM_EMPLOYEES):
            row = tk.Frame(left_panel, bg=BG3, highlightthickness=1,
                           highlightbackground="#1a2a3a")
            row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, text=f"{TOOL_ICONS[t]} {TOOL_NAMES[t]}",
                     font=("Arial", 9, "bold"), fg="#d2a8ff", bg=BG3,
                     width=14, anchor="e").pack(side="right", padx=6, pady=3)
            holder_var = tk.StringVar(value="🟢 متاحة")
            holder_lbl = tk.Label(row, textvariable=holder_var, font=("Arial", 9),
                                  fg=GREEN, bg=BG3, anchor="w", width=14)
            holder_lbl.pack(side="left", padx=6, pady=3, fill="x", expand=True)
            self.tool_rows.append({"holder_var": holder_var, "holder_lbl": holder_lbl})

        # -- إحصائيات الاستراحات (لإظهار التجويع المحتمل) --
        self._section_title(left_panel, "📊 عدد الاستراحات المُكتمَلة")
        stats_f = tk.Frame(left_panel, bg=BG2)
        stats_f.pack(fill="x", padx=8, pady=(0, 8))
        self.completed_vars = []
        for i in range(NUM_EMPLOYEES):
            v = tk.StringVar(value="0")
            f = tk.Frame(stats_f, bg=BG2)
            f.pack(side="right", padx=6)
            tk.Label(f, text=EMPLOYEE_ICONS[i], font=("Arial", 12), fg=FG, bg=BG2).pack()
            tk.Label(f, textvariable=v, font=("Arial", 12, "bold"), fg=ACCENT, bg=BG2).pack()
            self.completed_vars.append(v)

        # -- الرسم البياني Wait-for Graph (يمين) --
        right_panel = tk.Frame(mid, bg=BG2)
        right_panel.pack(side="right", fill="both", expand=True)
        self._section_title(right_panel, "🕸 Wait-for Graph — رسم بياني لانتظار الموارد")
        self.fig, self.ax = plt.subplots(figsize=(6.5, 5.0), facecolor=BG2)
        self.ax.set_facecolor(BG2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=5)

        # ── السجل المباشر ──
        log_f = tk.Frame(self, bg=BG)
        log_f.pack(fill="both", expand=False, padx=10, pady=(0, 8))
        self._section_title(log_f, "📋 سجل أحداث غرفة الاستراحة")
        self.log_box = scrolledtext.ScrolledText(
            log_f, height=10, bg=BG3, fg=FG,
            font=("Courier", 9), state="disabled", relief="flat")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=5)
        for tag, col in [("info", "#8aa8c8"), ("warn", YELLOW), ("err", RED),
                          ("ok", GREEN), ("sync", "#79c0ff"), ("scenario", PURPLE)]:
            self.log_box.tag_config(tag, foreground=col)

        self._draw_graph({}, set())

    # ── أدوات مساعدة للستايل ─────────────────────────────────────────────────
    def _btn(self, parent, text, color, cmd, size=10):
        return tk.Button(parent, text=text, font=("Arial", size, "bold"),
                         bg=color, fg="white", activebackground=color,
                         relief="flat", bd=0, padx=10, pady=6,
                         cursor="hand2", command=cmd)

    def _section_title(self, parent, text):
        bg = BG2
        try:
            bg = parent.cget("bg")
        except Exception:
            pass
        tk.Label(parent, text=text, font=("Arial", 11, "bold"),
                 fg=FG, bg=bg).pack(pady=(8, 4))

    # ── أوامر الأزرار ─────────────────────────────────────────────────────────
    def _on_start(self):
        if self.sim.running:
            return
        self.sim.start(self.fix_mode_var.get())

    def _on_stop(self):
        self.sim.stop()

    def _on_resolve(self):
        ok = self.sim.force_resolve()
        if not ok:
            self._append_log("ℹ لا يوجد Deadlock حالياً لحلّه", "info")

    # ── حلقة التحديث الدورية ─────────────────────────────────────────────────
    def _tick(self):
        # تفريغ السجل
        while True:
            try:
                msg, tag = self._log_queue.get_nowait()
            except _queue.Empty:
                break
            self._append_log(msg, tag)

        # حساب Wait-for Graph
        edges, cycle = self.sim.compute_wait_graph()
        snap = self.sim.snapshot()

        # تحديث حالة الموظفين
        for i in range(NUM_EMPLOYEES):
            label, color = STATE_LABELS.get(snap["status"][i], ("—", FG))
            extra = ""
            if snap["waiting_for"][i] is not None:
                t = snap["waiting_for"][i]
                extra = f" ← يحتاج {TOOL_ICONS[t]}"
            self.emp_rows[i]["status_var"].set(label + extra)
            self.emp_rows[i]["status_lbl"].config(fg=color)
            if i in cycle:
                self.emp_rows[i]["frame"].config(highlightbackground=RED, highlightthickness=2)
            else:
                self.emp_rows[i]["frame"].config(highlightbackground="#1a2a3a", highlightthickness=1)
            self.completed_vars[i].set(str(snap["completed"][i]))

        # تحديث حالة الأدوات
        for t in range(NUM_EMPLOYEES):
            holder = snap["tool_holder"][t]
            if holder is None:
                self.tool_rows[t]["holder_var"].set("🟢 متاحة")
                self.tool_rows[t]["holder_lbl"].config(fg=GREEN)
            else:
                self.tool_rows[t]["holder_var"].set(
                    f"🔒 {EMPLOYEE_ICONS[holder]} {EMPLOYEE_NAMES[holder]}")
                self.tool_rows[t]["holder_lbl"].config(fg=YELLOW)

        # تنبيه Deadlock + زر الحل
        if snap["deadlock"]:
            names = "، ".join(f"{EMPLOYEE_ICONS[i]} {EMPLOYEE_NAMES[i]}" for i in sorted(cycle))
            self.deadlock_banner.config(
                text=f"☠ DEADLOCK مكتشف! دورة انتظار دائرية بين: {names}",
                bg=RED)
            if self.sim.fix_mode == BreakRoomSimulation.FIX_NONE:
                self.resolve_btn.config(state="normal")
        else:
            self.deadlock_banner.config(text="", bg=BG)
            self.resolve_btn.config(state="disabled")

        # رسم Wait-for Graph
        self._draw_graph(edges, cycle)

        # إعادة الجدولة
        self.after(400, self._tick)

    # ── السجل ─────────────────────────────────────────────────────────────────
    def _append_log(self, msg, tag="info"):
        _styled_log(self.log_box, f"[{_ts()}] {msg}", tag)

    # ── رسم Wait-for Graph بـ matplotlib ────────────────────────────────────────
    def _draw_graph(self, edges, cycle):
        self.ax.clear()
        self.ax.set_facecolor(BG2)
        self.ax.set_xlim(-1.6, 1.6)
        self.ax.set_ylim(-1.6, 1.6)
        self.ax.axis("off")

        n = NUM_EMPLOYEES
        emp_pos = {}
        tool_pos = {}
        for i in range(n):
            angle = math.pi / 2 - i * (2 * math.pi / n)  # يبدأ من الأعلى، يدور مع الساعة
            emp_pos[i] = (math.cos(angle), math.sin(angle))

        for t in range(n):
            a1 = math.pi / 2 - t * (2 * math.pi / n)
            a2 = math.pi / 2 - ((t + 1) % n) * (2 * math.pi / n)
            mx = (math.cos(a1) + math.cos(a2)) / 2
            my = (math.sin(a1) + math.sin(a2)) / 2
            norm = math.hypot(mx, my) or 1.0
            tool_pos[t] = (mx / norm * 0.55, my / norm * 0.55)

        snap = self.sim.snapshot()

        # ── خطوط ملكية الأدوات (موظف يملك أداة) ──
        for t in range(n):
            holder = snap["tool_holder"][t]
            tx, ty = tool_pos[t]
            if holder is not None:
                ex, ey = emp_pos[holder]
                self.ax.plot([tx, ex], [ty, ey], color=GREEN, lw=1.5, alpha=0.7, zorder=1)

        # ── أسهم الانتظار (Wait-for Graph) ──
        for waiter, holder in edges.items():
            wx, wy = emp_pos[waiter]
            hx, hy = emp_pos[holder]
            in_cycle = waiter in cycle and holder in cycle
            color = RED if in_cycle else YELLOW
            lw = 2.6 if in_cycle else 1.6
            self.ax.annotate(
                "", xy=(hx * 0.82, hy * 0.82), xytext=(wx * 0.82, wy * 0.82),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                 connectionstyle="arc3,rad=0.25"),
                zorder=3
            )

        # ── رسم الأدوات (دوائر صغيرة في الوسط) ──
        for t in range(n):
            tx, ty = tool_pos[t]
            free = snap["tool_holder"][t] is None
            face = "#1a3a1a" if free else "#3a2a0a"
            edge = GREEN if free else YELLOW
            self.ax.scatter([tx], [ty], s=420, color=face, edgecolors=edge,
                            linewidths=1.5, zorder=2)
            self.ax.text(tx, ty, TOOL_ICONS[t], ha="center", va="center",
                         fontsize=13, zorder=4)

        # ── رسم الموظفين (دوائر كبيرة على المحيط) ──
        for i in range(n):
            ex, ey = emp_pos[i]
            in_cycle = i in cycle
            face = "#3a0a0a" if in_cycle else "#0d2a3a"
            edge = RED if in_cycle else ACCENT
            self.ax.scatter([ex], [ey], s=1500, color=face, edgecolors=edge,
                            linewidths=2.2, zorder=4)
            self.ax.text(ex, ey, EMPLOYEE_ICONS[i], ha="center", va="center",
                         fontsize=18, zorder=5)
            self.ax.text(ex, ey - 0.27, EMPLOYEE_NAMES[i], ha="center", va="center",
                         fontsize=9, color="white", zorder=5)

        # ── مفتاح الرسم (Legend) ──
        self.ax.text(-1.55, 1.5,
                      "🟩 خط = يملك الأداة      🟨 سهم = ينتظر (آمن)      🟥 سهم = ينتظر (Deadlock)",
                      fontsize=8, color=FG, ha="left", va="top")

        self.canvas.draw_idle()
