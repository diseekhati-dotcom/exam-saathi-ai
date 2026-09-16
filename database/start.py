"""
/start command — logic layer (see handlers/exam_commands.py docstring for
the plain-dict message/button spec shape shared by all handlers).

Phase 1 scope only: no mock tests, current affairs, rankings, progress,
notifications, subscriptions, or AI tutor menu items, per the project
brief.
"""


def build_start_message() -> dict:
    text = (
        "🎓 <b>Rajasthan Exam Information Bot</b>\n\n"
        "I help you find <b>official</b> syllabus, previous question papers, "
        "and answer keys for Rajasthan government &amp; competitive exams — "
        "verified directly from the conducting authority's own website.\n\n"
        "Usage:\n"
        "<code>/exam SI</code>\n"
        "<code>/exam Patwar</code>\n"
        "<code>/exam CET 12</code>\n"
        "<code>/exam REET Level 1</code>\n\n"
        "⚠️ If an official document can't be verified, I'll tell you honestly "
        "instead of guessing a link."
    )
    return {"text": text, "buttons": [], "parse_mode": "HTML"}
