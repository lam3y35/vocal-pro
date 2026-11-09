# VocalPro v3.0.0 — Windows Release

هذا المجلد يحتوي على النسخة المترجمة الجاهزة للتشغيل للمستخدم النهائي مباشرة (**Production Release**).

## 🚀 كيفية تشغيل التطبيق (End-User Quick Start):

1. **التشغيل المباشر:**
   * اضغط مرتين على `vocalpro.exe` وسيعمل التطبيق مباشرة بواجهة استوديو متكاملة (Tauri v2 + React 19).
   * أو اضغط على `Start-VocalPro.bat` للتحقق التلقائي من توافر المحرك وتشغيل التطبيق.

2. **الملفات الموجودة داخل هذا المجلد (`release/`):**
   * `vocalpro.exe`: التطبيق التنفيذي المترجم بالكامل بلغة Rust و Tauri v2 (حجمه ~15 ميجابايت).
   * `worker/`: كود المعالجة وعزل المسارات الصوتية (Python AI Worker).
   * `Start-VocalPro.bat`: مشغل تلقائي يقوم بالتشغيل المباشر.

## 📦 رابط التحميل المباشر من GitHub Releases:
يمكن أيضاً تحميل ملف التثبيت المجمع بصيغة مثبت Windows من صفحة الإصدارات الرسمية:
👉 **[تحميل VocalPro v3 من GitHub Releases](https://github.com/lam3y35/vocal-pro-rebuild/releases)**
