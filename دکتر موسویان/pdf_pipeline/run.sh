#!/usr/bin/env bash
# اجرای رابط هوشمند ترجمهٔ PDF
cd "$(dirname "$0")"
exec python3 app.py "$@"
