# -*- coding: utf-8 -*-
"""Force stdout/stderr to UTF-8 on Windows (gbk by default).

Import for side effect — no symbols are exported. No-op on macOS/Linux
where stdout is already UTF-8. Without this, subprocess-captured runs
crash with UnicodeEncodeError on emoji or Chinese characters.
"""
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8", errors="replace")
