# ══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول الرئيسية — supermarket_v2_1
# ══════════════════════════════════════════════════════════════════════════════
from auto_install import _auto_install
from database import init_db
from ui_windows import LoginWindow

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    app = LoginWindow()
    app.mainloop()
