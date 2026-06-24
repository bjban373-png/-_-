# ══════════════════════════════════════════════════════════════════════════════
# reports.py — توليد تقرير PDF شامل لنظام سوبر ماركت OS2
# ══════════════════════════════════════════════════════════════════════════════
#
# الأولوية السادسة: ملف جديد reports.py
#   - توليد تقرير PDF بمكتبة reportlab
#   - يحتوي على: إحصائيات الخيوط، Race Conditions المكتشفة، Audit Log،
#                 مقارنة أداء قبل/بعد Sync
#   - زر "تصدير PDF" في الواجهة الرئيسية (يُضاف في ui_windows.py)
#
# ملاحظة عن اللغة:
#   reportlab لا يدعم تشكيل/اتصال الحروف العربية (Arabic shaping) بدون
#   مكتبات خارجية إضافية (arabic_reshaper / python-bidi) وهي غير مسموحة
#   حسب قواعد المشروع (المكتبات المسموحة فقط threading/queue/sqlite3/...).
#   لذلك يتم توليد التقرير بعناوين ثنائية اللغة (AR transliteration + EN)
#   بخطوط Latin قياسية مضمَّنة في reportlab، لضمان عمل الكود على Python 3.8+
#   بدون أي تثبيت إضافي. إن توفّر خط عربي TTF داعم لاحقاً في مجلد fonts/,
#   سيتم استخدامه تلقائياً عبر _register_arabic_font().
# ══════════════════════════════════════════════════════════════════════════════

import os
import sqlite3
import datetime
import threading

from database import DB_PATH

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        PageBreak, HRFlowable
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# ❶  تسجيل خط عربي اختياري (إن وُجد) — تحسين مستقبلي بدون كسر التوافق
# ═══════════════════════════════════════════════════════════════════════════════
_ARABIC_FONT_NAME = "Helvetica"   # القيمة الافتراضية: خط Latin مدمج في reportlab
_ARABIC_FONT_BOLD = "Helvetica-Bold"


def _register_arabic_font():
    """
    يبحث عن خط TTF عربي في مجلد ./fonts بجانب البرنامج.
    إن وُجد، يسجَّله في reportlab ويستخدمه للعناوين العربية.
    إن لم يوجد، يبقى الخط الافتراضي Helvetica (Latin) — لا كسر للكود.
    """
    global _ARABIC_FONT_NAME, _ARABIC_FONT_BOLD
    if not REPORTLAB_AVAILABLE:
        return

    candidates = [
        ("fonts/NotoNaskhArabic-Regular.ttf", "fonts/NotoNaskhArabic-Bold.ttf", "ArabicFont"),
        ("fonts/Amiri-Regular.ttf",           "fonts/Amiri-Bold.ttf",           "ArabicFont"),
        ("fonts/NotoSansArabic-Regular.ttf",  "fonts/NotoSansArabic-Bold.ttf",  "ArabicFont"),
    ]
    for regular_path, bold_path, font_id in candidates:
        if os.path.exists(regular_path):
            try:
                pdfmetrics.registerFont(TTFont(font_id, regular_path))
                _ARABIC_FONT_NAME = font_id
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(font_id + "-Bold", bold_path))
                    _ARABIC_FONT_BOLD = font_id + "-Bold"
                else:
                    _ARABIC_FONT_BOLD = font_id
                return
            except Exception:
                continue


_register_arabic_font()


# ═══════════════════════════════════════════════════════════════════════════════
# ❷  دالة مساعدة: قراءة بيانات Audit Log من القاعدة
# ═══════════════════════════════════════════════════════════════════════════════
def _fetch_audit_rows(limit=50):
    """يقرأ آخر `limit` سجل من audit_log مع اسم المنتج"""
    rows = []
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()
        c.execute("""SELECT a.id, a.thread_name, a.action, p.name,
                            a.old_value, a.new_value, a.timestamp, a.sync_mode
                     FROM audit_log a
                     LEFT JOIN products p ON a.product_id = p.id
                     ORDER BY a.id DESC LIMIT ?""", (limit,))
        rows = c.fetchall()
        conn.close()
    except Exception:
        pass
    return rows


def _fetch_audit_summary():
    """يحسب ملخص إحصائي عن audit_log: عدد العمليات لكل sync_mode ولكل action"""
    summary = {"by_mode": {}, "by_action": {}, "total": 0}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM audit_log")
        summary["total"] = c.fetchone()[0]

        c.execute("SELECT sync_mode, COUNT(*) FROM audit_log GROUP BY sync_mode")
        for mode, cnt in c.fetchall():
            summary["by_mode"][mode or "—"] = cnt

        c.execute("SELECT action, COUNT(*) FROM audit_log GROUP BY action")
        for action, cnt in c.fetchall():
            summary["by_action"][action or "—"] = cnt

        conn.close()
    except Exception:
        pass
    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# ❸  الدالة الرئيسية: توليد تقرير PDF كامل
# ═══════════════════════════════════════════════════════════════════════════════
def generate_pdf_report(output_path, race_stats=None, perf_race_data=None,
                         deadlock_history=None, username="admin"):
    """
    توليد تقرير PDF شامل يحتوي على:
      1. صفحة غلاف
      2. إحصائيات الخيوط الحيّة ووقت الانتظار وعدد الحظر (Blocking)
      3. Race Conditions المكتشفة (من race_stats)
      4. مقارنة أداء قبل/بعد المزامنة (من perf_race_data — نتائج السيناريوهات الـ5)
      5. سجل Deadlock (إن وُجد)
      6. آخر 50 سجل من Audit Log + ملخص إحصائي

    المعاملات:
      output_path     : مسار حفظ ملف PDF
      race_stats       : قاموس core.race_stats (إحصائيات Race/Threads)
      perf_race_data    : قاموس نتائج سيناريوهات Race (من تبويب الأداء)
      deadlock_history  : قائمة أحداث Deadlock المكتشفة (من DeadlockDetector)
      username          : اسم المستخدم الذي يُصدِّر التقرير

    تُرجع: (True, "مسار الملف") عند النجاح، أو (False, "رسالة الخطأ") عند الفشل.
    """
    if not REPORTLAB_AVAILABLE:
        return False, (
            "مكتبة reportlab غير مثبّتة.\n"
            "ثبّتها بالأمر: pip install reportlab"
        )

    race_stats = race_stats or {}
    perf_race_data = perf_race_data or {}
    deadlock_history = deadlock_history or []

    try:
        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            topMargin=1.6 * cm, bottomMargin=1.6 * cm,
            leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle", parent=styles["Title"],
            fontName=_ARABIC_FONT_BOLD, fontSize=22,
            textColor=colors.HexColor("#0d1526"), spaceAfter=6,
            alignment=1,  # center
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle", parent=styles["Normal"],
            fontName=_ARABIC_FONT_NAME, fontSize=11,
            textColor=colors.HexColor("#3a6a9a"), alignment=1, spaceAfter=4,
        )
        section_style = ParagraphStyle(
            "SectionHeader", parent=styles["Heading2"],
            fontName=_ARABIC_FONT_BOLD, fontSize=14,
            textColor=colors.white, backColor=colors.HexColor("#0d1526"),
            spaceBefore=14, spaceAfter=8, leftIndent=6, borderPadding=6,
        )
        body_style = ParagraphStyle(
            "Body", parent=styles["Normal"],
            fontName=_ARABIC_FONT_NAME, fontSize=9.5, leading=14,
        )
        small_style = ParagraphStyle(
            "Small", parent=styles["Normal"],
            fontName=_ARABIC_FONT_NAME, fontSize=8,
            textColor=colors.HexColor("#666666"),
        )

        elements = []

        # ═══ صفحة الغلاف ═══════════════════════════════════════════════════
        elements.append(Spacer(1, 4 * cm))
        elements.append(Paragraph("Supermarket OS2 — System Report", title_style))
        elements.append(Paragraph("تقرير نظام التشغيل 2 — سوبر ماركت", subtitle_style))
        elements.append(Spacer(1, 0.6 * cm))
        elements.append(HRFlowable(width="100%", color=colors.HexColor("#00b8a3"), thickness=2))
        elements.append(Spacer(1, 0.6 * cm))

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta_table = Table([
            ["Generated at / تاريخ التصدير", now],
            ["Exported by / صدَّره", username],
            ["Active threads / الخيوط الحيّة", str(len(threading.enumerate()))],
            ["Race conditions detected / حالات تضارب", str(race_stats.get("corruption_count", 0))],
            ["Successful operations / عمليات ناجحة", str(race_stats.get("successful_ops", 0))],
            ["Failed operations / عمليات فاشلة", str(race_stats.get("failed_ops", 0))],
        ], colWidths=[8 * cm, 8 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef4f8")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(meta_table)
        elements.append(PageBreak())

        # ═══ 1. إحصائيات الخيوط الحيّة ═════════════════════════════════════
        elements.append(Paragraph("1. Thread Statistics — إحصائيات الخيوط", section_style))

        live_threads = [t for t in threading.enumerate() if t.is_alive()]
        thread_rows = [["#", "Thread Name", "Daemon", "Alive"]]
        for i, t in enumerate(live_threads, 1):
            thread_rows.append([str(i), t.name, "Yes" if t.daemon else "No", "Yes" if t.is_alive() else "No"])

        thread_table = Table(thread_rows, colWidths=[1.2 * cm, 9 * cm, 2.5 * cm, 2.5 * cm])
        thread_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
            ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1526")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fa")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(thread_table)
        elements.append(Spacer(1, 0.3 * cm))

        # ── جداول الانتظار والحظر لكل Thread (إن توفّرت) ──
        wait_times = race_stats.get("thread_wait_times", {})
        block_counts = race_stats.get("thread_block_count", {})
        if wait_times or block_counts:
            elements.append(Paragraph(
                "Wait Time &amp; Blocking per Thread — وقت الانتظار وعدد الحظر",
                ParagraphStyle("h3", parent=body_style, fontName=_ARABIC_FONT_BOLD,
                               fontSize=10, spaceBefore=6, spaceAfter=4)
            ))
            wb_rows = [["Thread", "Total Wait (s)", "Block Count"]]
            names = set(wait_times.keys()) | set(block_counts.keys())
            for name in sorted(names):
                wb_rows.append([
                    name,
                    f"{wait_times.get(name, 0.0):.3f}",
                    str(block_counts.get(name, 0)),
                ])
            wb_table = Table(wb_rows, colWidths=[7 * cm, 4 * cm, 4 * cm])
            wb_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6feb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(wb_table)

        elements.append(Spacer(1, 0.4 * cm))

        # ═══ 2. Race Conditions المكتشفة ═══════════════════════════════════
        elements.append(Paragraph("2. Race Conditions Detected — حالات التضارب المكتشفة", section_style))

        corruption = race_stats.get("corruption_count", 0)
        successful = race_stats.get("successful_ops", 0)
        failed = race_stats.get("failed_ops", 0)
        total_ops = corruption + successful + failed
        corruption_pct = (corruption / total_ops * 100) if total_ops else 0.0

        race_summary_rows = [
            ["Metric", "Value"],
            ["Corruption count / عدد حالات التضارب", str(corruption)],
            ["Successful ops / عمليات ناجحة", str(successful)],
            ["Failed ops / عمليات فاشلة", str(failed)],
            ["Corruption rate / نسبة التضارب", f"{corruption_pct:.2f}%"],
        ]
        race_table = Table(race_summary_rows, colWidths=[10 * cm, 5 * cm])
        race_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
            ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b91c1c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fdf2f2")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(race_table)
        elements.append(Spacer(1, 0.4 * cm))

        # ═══ 3. مقارنة أداء قبل/بعد المزامنة (من 5 سيناريوهات Race) ════════
        elements.append(Paragraph(
            "3. Performance Comparison: Before vs After Sync — مقارنة قبل/بعد المزامنة",
            section_style
        ))

        scenario_names_en = {
            0: "No Lock (Race Condition)",
            1: "Mutex (Lock)",
            2: "Semaphore(2)",
            3: "RWLock",
            4: "Barrier + Mutex",
        }

        if perf_race_data:
            perf_rows = [["Scenario", "Final Value", "Expected", "Corrupted?"]]
            for sid in sorted(perf_race_data.keys()):
                data = perf_race_data[sid]
                final_val = data.get("final", "—")
                corrupted = data.get("corrupted", False)
                perf_rows.append([
                    scenario_names_en.get(sid, f"Scenario {sid}"),
                    str(final_val),
                    "0",
                    "YES ⚡" if corrupted else "NO ✓",
                ])
            perf_table = Table(perf_rows, colWidths=[7 * cm, 3 * cm, 3 * cm, 3 * cm])
            perf_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#238636")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2faf2")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(perf_table)

            # ── خلاصة المقارنة: بدون قفل (سيناريو 0) مقابل مع Mutex (سيناريو 1) ──
            s0 = perf_race_data.get(0)
            s1 = perf_race_data.get(1)
            if s0 and s1:
                elements.append(Spacer(1, 0.3 * cm))
                conclusion = (
                    "Before sync (no lock), the shared counter was corrupted "
                    f"(final={s0.get('final')}, expected=0). "
                    "After applying Mutex, the result was correct "
                    f"(final={s1.get('final')}, expected=0). "
                    "This demonstrates that proper synchronization eliminates "
                    "race conditions on shared resources."
                )
                elements.append(Paragraph(conclusion, body_style))
        else:
            elements.append(Paragraph(
                "No scenario data available yet. "
                "Run the 5 race scenarios from the 'Race Condition' tab first. "
                "(لا توجد بيانات — شغّل السيناريوهات الخمسة من تبويب Race Condition أولاً)",
                small_style
            ))

        elements.append(Spacer(1, 0.4 * cm))

        # ═══ 4. سجل Deadlock ════════════════════════════════════════════════
        elements.append(Paragraph("4. Deadlock Detection Log — سجل اكتشاف Deadlock", section_style))

        if deadlock_history:
            dl_rows = [["#", "Time", "Description"]]
            for i, ev in enumerate(deadlock_history[-30:], 1):
                if isinstance(ev, dict):
                    ts = ev.get("time", "—")
                    desc = ev.get("description", str(ev))
                else:
                    ts = "—"
                    desc = str(ev)
                dl_rows.append([str(i), str(ts), str(desc)[:90]])
            dl_table = Table(dl_rows, colWidths=[1 * cm, 4 * cm, 10 * cm])
            dl_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6a2a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f2fc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(dl_table)
        else:
            elements.append(Paragraph(
                "No deadlocks detected during this session. ✓ "
                "(لم يتم اكتشاف أي Deadlock في هذه الجلسة)",
                body_style
            ))

        elements.append(PageBreak())

        # ═══ 5. ملخص Audit Log ══════════════════════════════════════════════
        elements.append(Paragraph("5. Audit Log Summary — ملخص سجل المراجعة", section_style))

        audit_summary = _fetch_audit_summary()
        elements.append(Paragraph(
            f"Total audit entries: {audit_summary['total']}",
            body_style
        ))
        elements.append(Spacer(1, 0.2 * cm))

        if audit_summary["by_mode"]:
            mode_labels = {"0": "No Sync", "1": "Mutex", "2": "Semaphore", "3": "RWLock"}
            mode_rows = [["Sync Mode", "Operation Count"]]
            for mode, cnt in audit_summary["by_mode"].items():
                mode_rows.append([mode_labels.get(str(mode), str(mode)), str(cnt)])
            mode_table = Table(mode_rows, colWidths=[8 * cm, 7 * cm])
            mode_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6feb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(mode_table)
            elements.append(Spacer(1, 0.4 * cm))

        # ═══ 6. آخر سجلات Audit Log (تفصيلي) ════════════════════════════════
        elements.append(Paragraph("6. Recent Audit Log Entries (last 50) — آخر 50 سجلاً", section_style))

        audit_rows = _fetch_audit_rows(limit=50)
        if audit_rows:
            table_data = [["ID", "Thread", "Action", "Product", "Old", "New", "Timestamp", "Mode"]]
            for row in audit_rows:
                table_data.append([str(x) if x is not None else "—" for x in row])

            audit_table = Table(
                table_data,
                colWidths=[1 * cm, 3.3 * cm, 2 * cm, 2.2 * cm, 1.3 * cm, 1.3 * cm, 3.2 * cm, 1.2 * cm],
                repeatRows=1,
            )
            audit_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), _ARABIC_FONT_NAME),
                ("FONTNAME", (0, 0), (-1, 0), _ARABIC_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1526")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fa")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]))
            elements.append(audit_table)
        else:
            elements.append(Paragraph(
                "No audit log entries found. (لا توجد سجلات Audit Log)",
                body_style
            ))

        # ═══ تذييل ════════════════════════════════════════════════════════
        elements.append(Spacer(1, 0.6 * cm))
        elements.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc"), thickness=0.5))
        elements.append(Paragraph(
            "Generated automatically by Supermarket OS2 — Operating Systems course project "
            "(تم توليده تلقائياً من نظام سوبر ماركت OS2 — مشروع مقرر نظم التشغيل)",
            small_style
        ))

        doc.build(elements)
        return True, output_path

    except Exception as e:
        return False, f"خطأ في توليد PDF: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# ❹  دالة تشغيل مستقلة (اختبار سريع من سطر الأوامر)
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # اختبار توليد تقرير تجريبي بدون بيانات حقيقية
    ok, result = generate_pdf_report(
        "test_report.pdf",
        race_stats={
            "corruption_count": 3, "successful_ops": 120, "failed_ops": 2,
            "thread_wait_times": {"PoolWorker-1": 1.234, "PoolWorker-2": 0.876},
            "thread_block_count": {"PoolWorker-1": 5, "PoolWorker-2": 2},
        },
        perf_race_data={
            0: {"final": -3, "expected": 0, "corrupted": True},
            1: {"final": 0, "expected": 0, "corrupted": False},
        },
        deadlock_history=[],
        username="admin",
    )
    print(ok, result)
