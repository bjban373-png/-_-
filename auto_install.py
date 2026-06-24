"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          نظام سوبر ماركت المتقدم — مادة نظام التشغيل 2  (v2.1)            ║
║          المصمم: إسماعيل اليوسف                                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  المفاهيم المطبّقة:                                                          ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  • Auto Install          : تثبيت تلقائي للمكتبات مع شريط تقدم              ║
║  • Threads & ThreadPool  : كل عملية في خيط منفصل / ThreadPoolExecutor      ║
║  • Mutex / Lock          : قفل حصري لحماية المخزون والفواتير                ║
║  • RLock                 : Reentrant Lock للعمليات المتداخلة                ║
║  • Timed Lock            : محاولة الحصول على القفل بزمن محدد               ║
║  • Semaphore             : تحديد الخيوط المتزامنة على المورد               ║
║  • RWLock                : قفل قراءة/كتابة مميَّز (Readers-Writers)        ║
║  • Barrier               : مزامنة مجموعة خيوط قبل البدء معاً               ║
║  • threading.Event       : إيقاف الخيوط بشكل نظيف                          ║
║  • Thread Timeout        : إلغاء خيوط تتجاوز 30 ثانية                      ║
║  • Race Condition        : 5 سيناريوهات محاكاة للتضارب                     ║
║  • Producer-Consumer     : عدة Producers + Consumers مع Priority Queue     ║
║  • Auto Restock          : Producer-Consumer حقيقي لإعادة التخزين          ║
║  • Deadlock Detection    : اكتشاف تلقائي بخوارزمية DFS                     ║
║  • Deadlock Prevention   : منع Deadlock بـ Resource Ordering               ║
║  • CPU Scheduling        : FCFS / SJF / Round Robin + Gantt Chart          ║
║  • Multi-Cashier         : 3-5 صناديق متوازية مع مشاركة المخزون           ║
║  • DB WAL Mode           : تحسين الكتابة المتزامنة لـ SQLite               ║
║  • DB Indexes            : فهرسة للبحث السريع                               ║
║  • Shared Resources      : مورد مشترك بين جميع الخيوط                     ║
║  • DB Transactions       : Rollback عند الخطأ + Audit Log                  ║
║  • psutil                : مراقبة CPU% و RAM% الحقيقية                     ║
║  • لوحة التحكم           : إحصائيات حية + رسم بياني يتحدث كل ثانية        ║
║  • مرئية الخيوط          : Timeline مباشر بألوان (أخضر/أصفر/أحمر)         ║
║  • نظام إشعارات          : تنبيه نفاد المخزون واكتشاف Deadlock             ║
║  • تعلّم OS تفاعلي       : بطاقات شرح مع محاكاة مصغّرة                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════════════
# ❶  التثبيت التلقائي للمكتبات — يعمل قبل أي import آخر
# ══════════════════════════════════════════════════════════════════════════════
# المنطق (مُحسَّن):
#   • نتحقق من كل مكتبة في _PACKAGES بشكل مستقل دائماً (بدون الاعتماد على
#     وجود requirements.txt فقط — لأن وجوده لا يعني أن كل مكتبة منصّبة فعلاً)
#   • موجودة → لا نلمسها
#   • مفقودة → نثبّتها عبر pip، مع إظهار الخطأ الحقيقي لو فشل التثبيت
#   • إعادة محاولة واحدة تلقائية عند الفشل (أحياناً يفشل pip أول مرة لأسباب شبكة)
#   • في النهاية: إن بقيت مكتبات لم تُثبَّت، تظهر رسالة واضحة بالأمر اليدوي
import importlib.util
import subprocess
import sys
import os

# المكتبات الخارجية المطلوبة: {اسم_الاستيراد: اسم_التثبيت_في_pip}
# المكتبات المدمجة في Python (threading, sqlite3 ...) لا تُذكر هنا
_PACKAGES = {
    "matplotlib": "matplotlib",
    "psutil":     "psutil",
    "reportlab":  "reportlab",   # مطلوبة لتصدير تقرير PDF (reports.py)
}


def _pkg_installed(import_name):
    """
    يتحقق هل المكتبة موجودة فعلاً بمحاولة استيرادها.
    True  → موجودة وتعمل → لا تلمسها أبداً
    False → مفقودة       → ثبّتها

    نستخدم importlib.util.find_spec بدلاً من __import__ الكامل
    لتجنّب استيراد مكتبات ثقيلة (matplotlib) فعلياً قبل الحاجة،
    مع وجود fallback لـ __import__ لضمان الدقة.
    """
    try:
        if importlib.util.find_spec(import_name) is not None:
            return True
    except (ImportError, ValueError, ModuleNotFoundError):
        pass
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def _pip_install(pip_name):
    """
    يثبّت مكتبة عبر pip ويعيد (نجح: bool, رسالة_الخطأ: str).
    لا نستخدم -q ولا نُخفي stderr بالكامل — نحتفظ بالخطأ لعرضه لو فشل.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", pip_name],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout or "خطأ غير معروف").strip()[-600:]
    except Exception as e:
        return False, str(e)


def _auto_install():
    """
    التحقق من كل مكتبة في _PACKAGES بشكل مستقل وتثبيت المفقود فقط.
    يعرض نافذة تقدم Tkinter إن أمكن، وإلا يثبّت بصمت في الـ Console.
    عند فشل أي مكتبة بعد إعادة المحاولة، تظهر رسالة واضحة بالأمر اليدوي.
    """
    # ── تحقق مستقل من كل مكتبة (لا نعتمد على requirements.txt وحده) ──
    missing = [
        (imp, pip)
        for imp, pip in _PACKAGES.items()
        if not _pkg_installed(imp)
    ]

    if not missing:
        return  # جميع المكتبات موجودة أصلاً — لا شيء ينقص

    failed = []   # [(pip_name, error_msg), ...] — لعرضها في النهاية

    # ── عرض نافذة تقدم وتثبيت المفقود ──
    try:
        import tkinter as _tk
        from tkinter import ttk as _ttk
        from tkinter import messagebox as _mb
        import time as _t

        _root = _tk.Tk()
        _root.title("تثبيت المكتبات المطلوبة")
        _root.geometry("480x230")
        _root.configure(bg="#060d1a")
        _root.resizable(False, False)

        _tk.Label(_root, text="🔧 جارٍ تثبيت المكتبات المطلوبة...",
                  font=("Arial", 13, "bold"), fg="#00e5c3", bg="#060d1a").pack(pady=(20, 5))

        _status = _tk.StringVar(value="جارٍ التحقق...")
        _tk.Label(_root, textvariable=_status, font=("Arial", 10),
                  fg="#c9d1d9", bg="#060d1a", wraplength=440).pack(pady=5)

        _prog = _ttk.Progressbar(_root, length=400, mode="determinate")
        _prog.pack(pady=10, padx=40)

        _tk.Label(_root, text="يرجى الانتظار — هذا يحدث مرة واحدة فقط لكل مكتبة",
                  font=("Arial", 9), fg="#5a7a9a", bg="#060d1a").pack()

        _root.update()

        for i, (imp_name, pip_name) in enumerate(missing):
            _status.set(f"تثبيت: {pip_name} ...")
            _prog["value"] = (i / len(missing)) * 100
            _root.update()

            ok, err = _pip_install(pip_name)

            if not ok:
                # إعادة محاولة واحدة (قد يكون فشل أول لأسباب شبكة مؤقتة)
                _status.set(f"إعادة محاولة: {pip_name} ...")
                _root.update()
                ok, err = _pip_install(pip_name)

            if not ok:
                failed.append((pip_name, err))

        _prog["value"] = 100
        ok_count = len(missing) - len(failed)

        if failed:
            _status.set(f"⚠ تم تثبيت {ok_count}/{len(missing)} — فشلت {len(failed)}")
        else:
            _status.set(f"✓ تم تثبيت {ok_count} مكتبة بنجاح!")

        _root.update()
        _t.sleep(1.0)
        _root.destroy()

        # ── إظهار رسالة واضحة عن أي مكتبة فشل تثبيتها ──
        if failed:
            details = "\n\n".join(f"• {pkg}:\n{err}" for pkg, err in failed)
            manual_cmds = "\n".join(f"    {sys.executable} -m pip install {pkg}" for pkg, _ in failed)
            try:
                _err_root = _tk.Tk()
                _err_root.withdraw()
                _mb.showwarning(
                    "تعذّر تثبيت بعض المكتبات",
                    "فشل التثبيت التلقائي للمكتبات التالية:\n\n"
                    + ", ".join(p for p, _ in failed)
                    + "\n\nثبّتها يدوياً من سطر الأوامر (Terminal):\n\n"
                    + manual_cmds
                    + "\n\nتفاصيل الخطأ:\n" + details[:1000]
                )
                _err_root.destroy()
            except Exception:
                print("⚠ تعذّر تثبيت المكتبات التالية تلقائياً:")
                for pkg, err in failed:
                    print(f"  - {pkg}: {err}")
                    print(f"    ثبّتها يدوياً: {sys.executable} -m pip install {pkg}")

    except Exception:
        # ── تثبيت صامت بدون واجهة إذا فشل Tkinter لأي سبب ──
        for imp_name, pip_name in missing:
            ok, err = _pip_install(pip_name)
            if not ok:
                ok, err = _pip_install(pip_name)  # إعادة محاولة واحدة
            if not ok:
                failed.append((pip_name, err))

        if failed:
            print("⚠ تعذّر تثبيت المكتبات التالية تلقائياً:")
            for pkg, err in failed:
                print(f"  - {pkg}: {err}")
                print(f"    ثبّتها يدوياً: {sys.executable} -m pip install {pkg}")


# تشغيل منطق التثبيت قبل أي import آخر
_auto_install()
