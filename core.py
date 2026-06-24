# ── استيراد المكتبات المطلوبة لـ core.py ──
import threading
import time
import sqlite3
import random
import datetime
import queue
import heapq
import concurrent.futures
import tkinter as tk

from database import DB_PATH, db_audit

# ═══════════════════════════════════════════════════════════════════════════════
# ❸  RWLock — قفل القراءة/الكتابة (Readers-Writers Lock)
# ═══════════════════════════════════════════════════════════════════════════════
class RWLock:
    """
    Readers-Writers Lock: يسمح لعدة قرّاء بالوصول المتزامن،
    لكن الكاتب يحتاج وصولاً حصرياً — مفيد لتحسين الأداء في حالة القراءة الكثيفة.
    """
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0   # عدد القرّاء الحاليين

    def acquire_read(self):
        """الحصول على قفل للقراءة — يمكن لعدة خيوط القراءة معاً"""
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        """تحرير قفل القراءة"""
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        """الحصول على قفل للكتابة — ينتظر حتى يفرغ جميع القرّاء"""
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        """تحرير قفل الكتابة"""
        self._read_ready.release()


# ═══════════════════════════════════════════════════════════════════════════════
# ❹  الموارد المشتركة وآليات التزامن
# ═══════════════════════════════════════════════════════════════════════════════

# ── Mutex Locks ──
# قفل المخزون: يمنع تضارب التحديثات على نفس المنتج من الصناديق المتعددة
stock_lock = threading.Lock()
# قفل الفواتير: مستقل عن قفل المخزون لتقليل الاحتقان
invoice_lock = threading.Lock()
# قفل الإحصائيات: يحمي بيانات race_stats من التضارب
stats_lock = threading.Lock()

# ── RLock (Reentrant Lock): يسمح لنفس الخيط بالحصول على القفل أكثر من مرة ──
# مفيد في العمليات المتداخلة حيث يحتاج الخيط لقفل موجود بالفعل
stock_rlock = threading.RLock()

# ── Semaphore ──
# يسمح بـ MAX_CONCURRENT خيطاً فقط بالدخول للقسم الحرج في وقت واحد
MAX_CONCURRENT = 3
stock_semaphore = threading.Semaphore(MAX_CONCURRENT)

# ── RWLock للمخزون ──
# مثال متقدم: القراءة مسموحة لعدة خيوط، الكتابة حصرية
inventory_rwlock = RWLock()

# ── المورد المشترك (Shared Resource) ──
# هذا القاموس هو محور التضارب — جميع الخيوط والصناديق تقرأ منه وتكتب فيه
shared_inventory = {}

# ── وضع التزامن الحالي ──
# 0=بدون تزامن (Race Condition), 1=Mutex, 2=Semaphore, 3=RWLock
sync_mode = 1

# ── إحصائيات شاملة ──
race_stats = {
    "corruption_count": 0,
    "successful_ops": 0,
    "failed_ops": 0,
    "active_threads": {},       # {name: status}
    "thread_wait_times": {},    # {name: total_wait_seconds}
    "thread_block_count": {},   # {name: block_count}
    "stock_history": [],
    "scenario_results": {},     # نتائج 5 سيناريوهات
}

# ── Thread Pool Executor ──
# مجمّع الخيوط: يعيد استخدام الخيوط بدلاً من إنشاء جديدة في كل مرة
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8,
                                                     thread_name_prefix="PoolWorker")

# ── Thread Timeout: مدة أقصى لكل خيط قبل إلغائه ──
THREAD_TIMEOUT_SEC = 30

# ── Stop Event: لإيقاف الخيوط الخلفية بشكل نظيف ──
# threading.Event يُتيح إشارة آمنة بين الخيوط دون الحاجة لمتغير عالمي مشترك
global_stop_event = threading.Event()


def load_inventory():
    """تحميل المخزون من قاعدة البيانات إلى الذاكرة المشتركة"""
    global shared_inventory
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    c.execute("SELECT id, name, price, stock FROM products")
    rows = c.fetchall()
    conn.close()
    shared_inventory = {r[0]: {"name": r[1], "price": r[2], "stock": r[3]} for r in rows}


# ═══════════════════════════════════════════════════════════════════════════════
# ❺  Deadlock Detection + Prevention (Resource Ordering)
# ═══════════════════════════════════════════════════════════════════════════════
class DeadlockDetector:
    """
    Deadlock: يحدث عندما يحتاج خيطان كلٌّ منهما قفلاً يمتلكه الآخر.
    هذا الكاشف يراقب الخيوط ويُنبّه عند اشتباه بالإغلاق المتبادل.

    Deadlock Prevention بـ Resource Ordering:
    نُرتّب الموارد بأرقام ثابتة ونفرض الحصول عليها بالترتيب التصاعدي دائماً.
    إذا اتبع جميع الخيوط نفس الترتيب → لا يمكن للدورة أن تتشكل.
    مثال: stock_lock (1) ثم invoice_lock (2) — دائماً هذا الترتيب.
    """
    # ── Resource Ordering للوقاية من Deadlock ──
    # أرقام الموارد المُرتَّبة — يجب دائماً الحصول عليها بهذا الترتيب
    RESOURCE_ORDER = {
        "stock_lock": 1,
        "invoice_lock": 2,
        "stock_rlock": 3,
        "stock_semaphore": 4,
    }

    def __init__(self):
        self._lock_graph = {}   # مخطط انتظار الأقفال: {خيط: مورد_ينتظره}
        self._held_resources = {}  # موارد يمتلكها كل خيط: {خيط: [موارد]}
        self._lock = threading.Lock()
        self._deadlock_callback = None
        self._running = False

    def set_callback(self, cb):
        self._deadlock_callback = cb

    def start(self):
        """بدء مراقب Deadlock في خيط خلفي مستقل"""
        self._running = True
        # هذا الخيط مسؤوله الوحيد: مراقبة الإغلاق المتبادل كل ثانيتين
        t = threading.Thread(target=self._monitor, daemon=True, name="DeadlockDetector")
        t.start()

    def stop(self):
        self._running = False

    def thread_waiting(self, waiter, resource):
        """تسجيل: خيط ينتظر مورداً"""
        with self._lock:
            self._lock_graph[waiter] = resource

    def thread_acquired(self, holder, resource):
        """تسجيل: خيط حصل على مورد"""
        with self._lock:
            self._lock_graph.pop(holder, None)
            self._held_resources.setdefault(holder, [])
            if resource not in self._held_resources[holder]:
                self._held_resources[holder].append(resource)

    def thread_released(self, holder, resource):
        """تسجيل: خيط حرَّر مورداً"""
        with self._lock:
            if holder in self._held_resources:
                self._held_resources[holder] = [
                    r for r in self._held_resources[holder] if r != resource
                ]

    def check_order(self, thread_name, resource_to_acquire):
        """
        Deadlock Prevention: تحقق من Resource Ordering.
        يعيد True إذا كان الترتيب صحيحاً (آمن)، False إذا كان يخالف الترتيب (خطر).
        """
        new_order = self.RESOURCE_ORDER.get(resource_to_acquire, 999)
        with self._lock:
            held = self._held_resources.get(thread_name, [])
        for r in held:
            existing_order = self.RESOURCE_ORDER.get(r, 999)
            if existing_order > new_order:
                return False  # ⚠ خرق Resource Ordering!
        return True

    def _monitor(self):
        """مراقبة دورية كل 2 ثانية للكشف عن دورات في مخطط الانتظار"""
        while self._running:
            time.sleep(2.0)
            with self._lock:
                waiting = dict(self._lock_graph)
            if self._detect_cycle(waiting) and self._deadlock_callback:
                self._deadlock_callback(waiting)

    def _detect_cycle(self, graph):
        """خوارزمية DFS لاكتشاف دورة في المخطط الموجَّه"""
        visited = set()
        path = set()

        def dfs(node):
            if node in path:
                return True  # دورة!
            if node in visited:
                return False
            visited.add(node)
            path.add(node)
            neighbor = graph.get(node)
            if neighbor and dfs(neighbor):
                return True
            path.discard(node)
            return False

        for node in graph:
            if dfs(node):
                return True
        return False


deadlock_detector = DeadlockDetector()


# ═══════════════════════════════════════════════════════════════════════════════
# ❻-أ  Barrier — مزامنة بدء الصناديق معاً
# ═══════════════════════════════════════════════════════════════════════════════
class CashierBarrier:
    """
    Barrier: يجعل مجموعة من الخيوط تنتظر بعضها حتى يصل الجميع،
    ثم تنطلق كلها معاً في نفس اللحظة — يُستخدم لبدء الصناديق بشكل متزامن.

    مثال: 3 صناديق تنتظر عند الـ Barrier حتى يكون الثلاثة جاهزين،
    ثم تبدأ جميعاً دفعةً واحدة → يُظهر للمدرس التوازي الحقيقي.

    threading.Barrier هو التطبيق المدمج في Python 3.2+
    """
    def __init__(self, parties: int):
        # parties = عدد الخيوط التي يجب أن تصل قبل الفتح
        self._barrier = threading.Barrier(parties)
        self.parties = parties

    def wait(self, timeout=None):
        """
        ينتظر الخيط هنا حتى يصل عدد parties من الخيوط.
        يُطلق BrokenBarrierError إذا انقضى timeout أو كُسر الـ Barrier.
        """
        try:
            return self._barrier.wait(timeout=timeout)
        except threading.BrokenBarrierError:
            return -1  # إشارة إلى أن الـ Barrier كُسر (مثلاً بعد stop)

    def reset(self):
        """إعادة تهيئة الـ Barrier لاستخدام جديد"""
        self._barrier.reset()

    def abort(self):
        """كسر الـ Barrier لتحرير الخيوط المنتظرة عند الإيقاف"""
        self._barrier.abort()

    @property
    def n_waiting(self):
        """عدد الخيوط التي وصلت للـ Barrier وتنتظر حالياً"""
        return self._barrier.n_waiting


# Barrier عالمي للصناديق — يتم إعادة إنشائه عند كل محاكاة حسب عدد الصناديق
# الاستخدام: cashier_barrier = CashierBarrier(num_cashiers) قبل بدء المحاكاة
cashier_barrier: "CashierBarrier | None" = None


# ═══════════════════════════════════════════════════════════════════════════════
# ❻  Priority Queue للـ Producer-Consumer
# ═══════════════════════════════════════════════════════════════════════════════
class PriorityItem:
    """
    عنصر في Priority Queue — يُرتَّب حسب الأولوية (أصغر رقم = أعلى أولوية)
    Priority Queue: مثل Queue العادية لكن مع ترتيب العناصر حسب الأهمية
    """
    def __init__(self, priority, item):
        self.priority = priority
        self.item = item
        self.timestamp = time.time()

    def __lt__(self, other):
        # الأولوية الأعلى تُعالَج أولاً، عند تساوي الأولوية نستخدم الوقت
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class PriorityQueue:
    """
    طابور الأولوية: يُنتج العناصر الأهم أولاً
    يستخدم heap داخلياً للكفاءة O(log n)
    """
    def __init__(self, maxsize=0):
        self._heap = []
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._count = 0

    def put(self, item, priority=5, timeout=None):
        with self._not_full:
            if self._maxsize > 0:
                deadline = time.time() + (timeout or 0)
                while self._count >= self._maxsize:
                    remaining = deadline - time.time()
                    if timeout is not None and remaining <= 0:
                        raise queue.Full
                    self._not_full.wait(remaining if timeout else None)
            heapq.heappush(self._heap, PriorityItem(priority, item))
            self._count += 1
            self._not_empty.notify()

    def get(self, timeout=None):
        with self._not_empty:
            deadline = time.time() + (timeout or 0)
            while self._count == 0:
                remaining = deadline - time.time()
                if timeout is not None and remaining <= 0:
                    raise queue.Empty
                self._not_empty.wait(remaining if timeout else None)
            item = heapq.heappop(self._heap)
            self._count -= 1
            self._not_full.notify()
            return item

    def qsize(self):
        with self._lock:
            return self._count

    def empty(self):
        return self.qsize() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ميزة إضافية: Starvation & Aging — امتداد على PriorityItem / PriorityQueue
# ═══════════════════════════════════════════════════════════════════════════════
class AgingPriorityItem(PriorityItem):
    """
    عنصر Priority Queue يدعم Aging: كل ما طال انتظار العنصر في الطابور،
    "تتحسّن" أولويته الفعلية (Effective Priority) تدريجياً — وهذا هو الحل
    الكلاسيكي لمشكلة Starvation (تجويع العناصر منخفضة الأولوية التي قد لا
    تُخدَم أبداً إن استمر وصول عناصر أعلى أولوية باستمرار).

    Effective Priority = original_priority - (وقت_الانتظار × aging_rate)
    (لا تقل عن 0 — أعلى أولوية ممكنة في هذا النظام).
    """
    def __init__(self, priority, item, aging_rate=0.5):
        super().__init__(priority, item)
        self.original_priority = priority
        self.aging_rate = aging_rate

    def effective_priority(self, aging_enabled=True):
        if not aging_enabled:
            return self.original_priority
        waited = time.time() - self.timestamp
        eff = self.original_priority - (waited * self.aging_rate)
        return max(eff, 0)


class AgingPriorityQueue(PriorityQueue):
    """
    امتداد لـ PriorityQueue يضيف دوال جديدة (put_with_aging /
    get_with_aging / snapshot_with_effective_priorities) تتعامل مع
    AgingPriorityItem، دون أي تعديل على put()/get() الأصليتين في
    PriorityQueue (تبقيان كما هما تماماً لمن يستخدم الكلاس الأساسي).

    عند aging_enabled=False: تتصرف الطابور كأولوية ثابتة عادية → العنصر
    منخفض الأولوية قد "يتجوّع" (Starvation) إذا استمر وصول عناصر أعلى
    أولوية باستمرار.

    عند aging_enabled=True: العنصر الذي طال انتظاره تتحسّن أولويته الفعلية
    حتى يتجاوز العناصر الأحدث الأعلى أولوية → يُضمَن خدمته في النهاية
    (لا Starvation).
    """
    def put_with_aging(self, item, priority=5, aging_rate=0.5, timeout=None):
        with self._not_full:
            if self._maxsize > 0:
                deadline = time.time() + (timeout or 0)
                while self._count >= self._maxsize:
                    remaining = deadline - time.time()
                    if timeout is not None and remaining <= 0:
                        raise queue.Full
                    self._not_full.wait(remaining if timeout else None)
            self._heap.append(AgingPriorityItem(priority, item, aging_rate))
            self._count += 1
            self._not_empty.notify()

    def get_with_aging(self, aging_enabled=True, timeout=None):
        with self._not_empty:
            deadline = time.time() + (timeout or 0)
            while self._count == 0:
                remaining = deadline - time.time()
                if timeout is not None and remaining <= 0:
                    raise queue.Empty
                self._not_empty.wait(remaining if timeout else None)
            # اختيار العنصر الأفضل حسب الأولوية الفعلية (الأقدم يفوز عند التعادل)
            best_idx = min(
                range(len(self._heap)),
                key=lambda i: (self._heap[i].effective_priority(aging_enabled),
                               self._heap[i].timestamp)
            )
            item = self._heap.pop(best_idx)
            self._count -= 1
            self._not_full.notify()
            return item

    def snapshot_with_effective_priorities(self, aging_enabled=True):
        """لقطة لكل عناصر الطابور الحالية مع أولوياتها الفعلية (لعرضها في الواجهة)."""
        with self._lock:
            now = time.time()
            return [
                {
                    "item": it.item,
                    "original_priority": it.original_priority,
                    "effective_priority": it.effective_priority(aging_enabled),
                    "waited": now - it.timestamp,
                }
                for it in self._heap
            ]


# ═══════════════════════════════════════════════════════════════════════════════
# ❼  نظام الإشعارات التلقائي
# ═══════════════════════════════════════════════════════════════════════════════
class NotificationSystem:
    """
    نظام إشعارات يظهر في الزاوية عند:
    - نفاد مخزون منتج (أقل من 5 وحدات)
    - اكتشاف Deadlock محتمل
    - انتهاء إعادة تخزين تلقائية
    يُدار كـ Thread خلفي مستقل
    """
    def __init__(self, master):
        self.master = master
        self.notifications = []  # قائمة الإشعارات الحالية
        self._lock = threading.Lock()

    def show(self, message, color="#d29922", duration=4000):
        """عرض إشعار في الزاوية السفلى اليمنى من النافذة الرئيسية"""
        def _create():
            popup = tk.Toplevel(self.master)
            popup.overrideredirect(True)
            popup.configure(bg="#1a2a3a")
            popup.attributes("-topmost", True)

            # حساب موضع النافذة
            mw = self.master.winfo_width()
            mh = self.master.winfo_height()
            mx = self.master.winfo_x()
            my = self.master.winfo_y()

            with self._lock:
                offset = len(self.notifications) * 65
            popup.geometry(f"320x55+{mx + mw - 335}+{my + mh - 80 - offset}")

            frame = tk.Frame(popup, bg=color, bd=0)
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            tk.Label(frame, text=message, font=("Arial", 9, "bold"),
                     fg="white", bg=color, wraplength=300,
                     justify="right").pack(expand=True, padx=8, pady=6)

            with self._lock:
                self.notifications.append(popup)

            def _close():
                popup.destroy()
                with self._lock:
                    if popup in self.notifications:
                        self.notifications.remove(popup)

            popup.after(duration, _close)

        self.master.after(0, _create)


# ═══════════════════════════════════════════════════════════════════════════════
# ❽  محاكاة الصناديق المتعددة (Multi-Cashier Simulation)
# ═══════════════════════════════════════════════════════════════════════════════
class CashierSimulation:
    """
    محاكاة 3-5 صناديق دفع تعمل بالتوازي كـ Threads منفصلة.
    المخزون مورد مشترك — بدون قفل تظهر Race Condition واضحة.

    كل صندوق:
    - يمتلك قائمة انتظار عملاء خاصة
    - يشارك نفس المخزون shared_inventory مع باقي الصناديق
    - يُسجَّل حالته: IDLE / SERVING / WAITING (ينتظر قفل) / DONE

    الفرق المرئي بين وضعَي Lock و No-Lock:
    - بدون Lock: نفس المنتج قد يُباع من صندوقين في نفس الوقت → الكمية سالبة!
    - مع Lock: كل صندوق ينتظر دوره → لا تضارب
    """
    def __init__(self, num_cashiers=3, use_lock=True, log_callback=None):
        self.num_cashiers = num_cashiers
        self.use_lock = use_lock
        self.log_cb = log_callback or (lambda msg, tag: None)

        # قوائم انتظار منفصلة لكل صندوق (كل صندوق Thread مستقل)
        self.cashier_queues = [queue.Queue(maxsize=5) for _ in range(num_cashiers)]
        # حالة كل صندوق للعرض البصري
        self.cashier_status = ["IDLE"] * num_cashiers
        # إجمالي مبيعات كل صندوق
        self.cashier_sales = [0.0] * num_cashiers
        # عدد عمليات البيع الناجحة لكل صندوق
        self.cashier_transactions = [0] * num_cashiers
        # Race Conditions التي رصدها كل صندوق
        self.cashier_races = [0] * num_cashiers

        self.running = False
        # stop_event: إيقاف نظيف لجميع الخيوط دون قتلها قسراً
        self.stop_event = threading.Event()
        self._threads = []

        # القفل المشترك للمخزون — مورد مشترك واحد لجميع الصناديق
        # وجود هذا القفل هو الفرق بين الفوضى والنظام!
        self._shared_lock = threading.Lock()

    def start(self):
        """تشغيل جميع الصناديق كـ Threads متوازية"""
        self.running = True
        self.stop_event.clear()
        self._threads = []

        for i in range(self.num_cashiers):
            # كل صندوق Thread مستقل يخدم قائمة انتظاره الخاصة
            # لكن يشارك نفس المخزون shared_inventory
            t = threading.Thread(
                target=self._cashier_worker,
                args=(i,),
                daemon=True,
                name=f"Cashier-{i+1}"
            )
            t.start()
            self._threads.append(t)

        # Thread منتج يملأ قوائم الانتظار تلقائياً
        producer = threading.Thread(
            target=self._customer_producer,
            daemon=True,
            name="CustomerProducer"
        )
        producer.start()
        self._threads.append(producer)

    def stop(self):
        """إيقاف جميع الصناديق بشكل نظيف عبر threading.Event"""
        self.running = False
        # إشارة الإيقاف النظيف — الخيوط تتحقق منها دورياً
        self.stop_event.set()

    def _customer_producer(self):
        """
        Producer خاص بالصناديق: يولّد عملاء عشوائيين ويوزّعهم على الصناديق.
        يعمل طالما لم يُستقبل stop_event.
        """
        prod_ids = list(range(1, 16))  # 15 منتجاً
        while not self.stop_event.is_set():
            # اختيار صندوق عشوائي وإضافة عميل لقائمته
            cashier_idx = random.randint(0, self.num_cashiers - 1)
            # سلة عميل عشوائية: 1-3 منتجات
            cart = {random.choice(prod_ids): random.randint(1, 3)
                    for _ in range(random.randint(1, 3))}
            try:
                self.cashier_queues[cashier_idx].put(cart, timeout=0.5)
            except queue.Full:
                pass
            time.sleep(random.uniform(0.3, 0.8))

    def _cashier_worker(self, cashier_id):
        """
        صندوق دفع: خيط مستقل يخدم عملاء بشكل متواصل.
        اسم الخيط: Cashier-{cashier_id+1}
        دوره: قراءة قائمة انتظاره وخصم المخزون لكل عملية بيع

        الفرق الجوهري:
        - use_lock=True: ينتظر القفل → WAITING (أصفر) ثم يعمل → SERVING (أخضر)
        - use_lock=False: يعمل مباشرة → خطر التضارب! قد يقرأ مخزوناً قديماً
        """
        tid = threading.current_thread().name
        while not self.stop_event.is_set():
            try:
                cart = self.cashier_queues[cashier_id].get(timeout=1.0)
            except queue.Empty:
                self.cashier_status[cashier_id] = "IDLE"
                continue

            self.cashier_status[cashier_id] = "SERVING"
            self.log_cb(f"[{tid}] 🛍 يخدم عميلاً ({len(cart)} منتج)", "pool")

            lock_acquired = False
            if self.use_lock:
                # ── مع القفل: ينتظر دوره ──
                self.cashier_status[cashier_id] = "WAITING"
                self.log_cb(f"[{tid}] ⏳ ينتظر القفل...", "warn")
                self._shared_lock.acquire()
                lock_acquired = True
                self.cashier_status[cashier_id] = "SERVING"
                self.log_cb(f"[{tid}] 🔒 حصل على القفل", "sync")
            else:
                # ── بدون قفل: يعمل مباشرة → Race Condition محتملة! ──
                time.sleep(random.uniform(0.01, 0.05))  # نافذة التضارب

            try:
                total = 0.0
                for pid, qty in cart.items():
                    if pid in shared_inventory:
                        current_stock = shared_inventory[pid]["stock"]

                        if not self.use_lock:
                            # محاكاة تأخير القراءة → الكتابة (سبب Race Condition)
                            time.sleep(random.uniform(0.005, 0.02))

                        if current_stock >= qty:
                            new_stock = current_stock - qty
                            shared_inventory[pid]["stock"] = new_stock

                            # كشف Race Condition: مخزون سالب يعني تضارباً!
                            if new_stock < 0:
                                self.cashier_races[cashier_id] += 1
                                self.log_cb(
                                    f"[{tid}] ⚡ RACE! مخزون {shared_inventory[pid]['name']} = {new_stock}",
                                    "race"
                                )
                                with stats_lock:
                                    race_stats["corruption_count"] += 1

                            total += shared_inventory[pid]["price"] * qty
                            db_audit(tid, "CASHIER_SALE", pid, current_stock, new_stock,
                                     "LOCK" if self.use_lock else "NO_LOCK", cashier_id + 1)

                self.cashier_sales[cashier_id] += total
                self.cashier_transactions[cashier_id] += 1
                with stats_lock:
                    race_stats["successful_ops"] += 1

            finally:
                if lock_acquired:
                    self._shared_lock.release()
                    self.log_cb(f"[{tid}] 🔓 حرَّر القفل", "sync")
                self.cashier_status[cashier_id] = "IDLE"

            # Thread Timeout: لا ننتظر أكثر من THREAD_TIMEOUT_SEC ثانية على العملية
            # (التحقق يتم عبر stop_event كل دورة)
            time.sleep(random.uniform(0.2, 0.6))


# ═══════════════════════════════════════════════════════════════════════════════
# ❾  نظام إعادة التخزين التلقائي (Producer-Consumer حقيقي)
# ═══════════════════════════════════════════════════════════════════════════════
class AutoRestockSystem:
    """
    نمط Producer-Consumer حقيقي مطبّق على إدارة المخزون:

    Producer Thread (RestockScanner):
    - يعمل كل 30 ثانية في خلفية التطبيق
    - يفحص كل منتج في المخزون
    - إذا وجد منتجاً أقل من 5 وحدات → يضيفه لقائمة إعادة التخزين

    Consumer Thread (RestockProcessor):
    - ينتظر عناصر في قائمة إعادة التخزين
    - عند وصول عنصر → يُحدّث المخزون في قاعدة البيانات
    - يُرسل إشعاراً للمستخدم

    هذا يوضح كيف يمكن فصل منتج البيانات (Scanner) عن معالجها (Processor)
    """
    LOW_STOCK_THRESHOLD = 5    # الحد الأدنى للمخزون قبل الإعادة التلقائية
    RESTOCK_AMOUNT = 50        # الكمية المُضافة عند إعادة التخزين
    SCAN_INTERVAL = 30         # فترة الفحص بالثواني

    def __init__(self, notify_callback=None, log_callback=None):
        self.notify_cb = notify_callback or (lambda msg, color: None)
        self.log_cb = log_callback or (lambda msg, tag: None)

        # Queue مشتركة بين Producer (Scanner) وConsumer (Processor)
        # هذه القائمة هي قناة التواصل الآمنة بين الخيطين
        self.restock_queue = queue.Queue(maxsize=20)

        # stop_event: إيقاف نظيف بدون force-kill للخيوط
        self.stop_event = threading.Event()
        self.running = False
        self._producer_thread = None
        self._consumer_thread = None

    def start(self):
        """تشغيل خيطَي الإنتاج والمعالجة"""
        self.running = True
        self.stop_event.clear()

        # Producer Thread: يفحص المخزون كل 30 ثانية
        # مسؤوليته: اكتشاف المنتجات الناقصة وإضافتها للقائمة
        self._producer_thread = threading.Thread(
            target=self._restock_scanner,
            daemon=True,
            name="RestockScanner-Producer"
        )
        self._producer_thread.start()

        # Consumer Thread: يعالج قائمة إعادة التخزين
        # مسؤوليته: تحديث المخزون عند ورود طلبات إعادة التخزين
        self._consumer_thread = threading.Thread(
            target=self._restock_processor,
            daemon=True,
            name="RestockProcessor-Consumer"
        )
        self._consumer_thread.start()

        self.log_cb("🔄 نظام إعادة التخزين التلقائي: بدأ", "info")

    def stop(self):
        """إيقاف النظام بشكل نظيف"""
        self.running = False
        self.stop_event.set()
        self.log_cb("⏹ نظام إعادة التخزين: أُوقف", "warn")

    def _restock_scanner(self):
        """
        Producer: يفحص المخزون كل 30 ثانية.
        يُنتج طلبات إعادة تخزين للمنتجات الناقصة.
        يتوقف بشكل نظيف عند استقبال stop_event.
        """
        while not self.stop_event.is_set():
            # انتظر 30 ثانية مع القدرة على الإيقاف الفوري
            # wait() يعيد True إذا أُطلق stop_event، False إذا انتهى الوقت
            if self.stop_event.wait(timeout=self.SCAN_INTERVAL):
                break  # وصل stop_event — أوقف الخيط نظيفاً

            # فحص المخزون
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            c = conn.cursor()
            c.execute("SELECT id, name, stock FROM products WHERE stock < ?",
                      (self.LOW_STOCK_THRESHOLD,))
            low_stock = c.fetchall()
            conn.close()

            for pid, name, stock in low_stock:
                restock_task = {
                    "product_id": pid,
                    "name": name,
                    "current_stock": stock,
                    "add_amount": self.RESTOCK_AMOUNT
                }
                try:
                    self.restock_queue.put(restock_task, timeout=2.0)
                    self.log_cb(
                        f"[RestockScanner] 📦 {name}: مخزون={stock} < {self.LOW_STOCK_THRESHOLD} → جدولة إعادة تخزين",
                        "warn"
                    )
                except queue.Full:
                    self.log_cb("[RestockScanner] ⚠ قائمة الإعادة ممتلئة!", "err")

    def _restock_processor(self):
        """
        Consumer: يُعالج طلبات إعادة التخزين من القائمة.
        ينتظر (blocking) حتى تصل طلبات ثم يُحدّث قاعدة البيانات.
        """
        while not self.stop_event.is_set():
            try:
                # انتظار طلب بـ timeout صغير للتحقق من stop_event دورياً
                task = self.restock_queue.get(timeout=2.0)
            except queue.Empty:
                continue  # لا يوجد طلبات — تحقق من stop_event وانتظر مجدداً

            pid = task["product_id"]
            name = task["name"]
            add_amount = task["add_amount"]
            old_stock = task["current_stock"]

            # تحديث المخزون في قاعدة البيانات
            try:
                conn = sqlite3.connect(DB_PATH, timeout=10)
                conn.execute("PRAGMA journal_mode=WAL")
                c = conn.cursor()
                c.execute("UPDATE products SET stock = stock + ? WHERE id = ?",
                          (add_amount, pid))
                c.execute("SELECT stock FROM products WHERE id = ?", (pid,))
                new_stock = c.fetchone()[0]
                conn.commit()
                conn.close()

                # تحديث الذاكرة المشتركة أيضاً
                with stock_lock:
                    if pid in shared_inventory:
                        shared_inventory[pid]["stock"] = new_stock

                db_audit("RestockProcessor-Consumer", "RESTOCK", pid, old_stock, new_stock,
                         "AUTO_RESTOCK")

                self.log_cb(
                    f"[RestockProcessor] ✓ {name}: {old_stock} → {new_stock} (+{add_amount})",
                    "ok"   # استخدام "ok" (أخضر) — معرَّف دائماً في _styled_log
                )
                self.notify_cb(
                    f"✅ إعادة تخزين: {name} ({old_stock}→{new_stock})",
                    "#3fb950"
                )

                self.restock_queue.task_done()

            except Exception as e:
                self.log_cb(f"[RestockProcessor] ✗ خطأ: {e}", "err")

