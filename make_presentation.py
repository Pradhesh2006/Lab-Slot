"""Generate the LabSlot slide deck (labslot_presentation.pptx) with python-pptx.

Usage:  python make_presentation.py
"""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

OUTPUT = "labslot_presentation.pptx"

BG = RGBColor(0x0F, 0x17, 0x2A)       # dark slate
CARD = RGBColor(0x1B, 0x26, 0x3F)
CARD_ALT = RGBColor(0x14, 0x1E, 0x35)
CYAN = RGBColor(0x00, 0xE5, 0xFF)
GREEN = RGBColor(0x00, 0xE6, 0x76)
RED = RGBColor(0xFF, 0x53, 0x70)
TEXT = RGBColor(0xE6, 0xED, 0xF7)
MUTED = RGBColor(0x94, 0xA3, 0xB8)
INK = RGBColor(0x04, 0x10, 0x1C)

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FONT = "Calibri"
MONO = "Consolas"


def new_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    return slide


def rect(slide, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, line=None):
    shp = slide.shapes.add_shape(shape, x, y, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    return shp


def text(slide, x, y, w, h, content, size=18, color=TEXT, bold=False, font=FONT,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """Add a text box. `content` is a string or a list of strings (one paragraph each)."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    paragraphs = content if isinstance(content, list) else [content]
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = para
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = font
        run.font.color.rgb = color
    return box


def bullets(slide, x, y, w, h, items, size=17, color=TEXT):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(9)
        dot = p.add_run()
        dot.text = "\u25B8  "
        dot.font.size = Pt(size)
        dot.font.color.rgb = CYAN
        dot.font.name = FONT
        run = p.add_run()
        run.text = item
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = FONT
    return box


def header(slide, number, title, subtitle=None):
    rect(slide, 0, 0, SLIDE_W, Inches(0.14), CYAN)                        # cyan highlight banner
    rect(slide, Inches(0.6), Inches(0.5), Inches(0.12), Inches(0.75), GREEN)
    text(slide, Inches(0.85), Inches(0.42), Inches(11.2), Inches(0.6), title, size=32, bold=True)
    if subtitle:
        text(slide, Inches(0.85), Inches(0.98), Inches(11.4), Inches(0.4), subtitle, size=16, color=MUTED)
    text(slide, Inches(11.0), Inches(0.5), Inches(1.8), Inches(0.4), f"{number:02d} / 07",
         size=14, color=CYAN, font=MONO, align=PP_ALIGN.RIGHT)
    text(slide, Inches(0.6), Inches(7.08), Inches(8), Inches(0.3),
         "LabSlot \u2014 Research Equipment Assistant", size=11, color=MUTED)


def card(slide, x, y, w, h, title, items, size=15, accent=CYAN):
    rect(slide, x, y, w, h, CARD, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line=RGBColor(0x2A, 0x3A, 0x5C)).adjustments[0] = 0.04
    rect(slide, x + Inches(0.25), y + Inches(0.22), Inches(0.5), Inches(0.05), accent)
    text(slide, x + Inches(0.2), y + Inches(0.3), w - Inches(0.4), Inches(0.45), title, size=19, bold=True, color=accent)
    bullets(slide, x + Inches(0.2), y + Inches(0.85), w - Inches(0.4), h - Inches(1.0), items, size=size)


def table(slide, x, y, w, col_widths, rows, font_size=13, row_h=0.4, header_fill=CYAN):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, Inches(row_h * len(rows)))
    tbl = shape.table
    # Remove the default table style banding so our fills are the only fills.
    tbl_pr = shape._element.graphic.graphicData.tbl.tblPr
    tbl_pr.set("bandRow", "0")
    tbl_pr.set("firstRow", "0")
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if r == 0 else (CARD if r % 2 else CARD_ALT)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            tf = cell.text_frame
            tf.word_wrap = True
            run = tf.paragraphs[0].add_run()
            run.text = str(value)
            run.font.size = Pt(font_size)
            run.font.name = FONT
            run.font.bold = r == 0
            run.font.color.rgb = INK if r == 0 else TEXT
            if r > 0 and value in ("Eligible", "PASS"):
                run.font.color.rgb = GREEN
                run.font.bold = True
            if r > 0 and value == "Not eligible":
                run.font.color.rgb = RED
                run.font.bold = True
    return tbl


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H

    # ---- Slide 1: Title & Overview ------------------------------------------------
    s = new_slide(prs)
    rect(s, 0, 0, SLIDE_W, Inches(0.14), CYAN)
    rect(s, Inches(0.8), Inches(1.5), Inches(0.9), Inches(0.9), CYAN, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(0.8), Inches(1.5), Inches(0.9), Inches(0.9), "LS", size=30, bold=True, color=INK,
         font=MONO, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(1.95), Inches(1.4), Inches(10.5), Inches(1.0), "LabSlot", size=60, bold=True)
    text(s, Inches(1.95), Inches(2.3), Inches(10.5), Inches(0.6), "Research Equipment Assistant", size=28, color=CYAN)
    rect(s, Inches(0.8), Inches(3.35), Inches(11.7), Inches(0.05), GREEN)
    text(s, Inches(0.8), Inches(3.65), Inches(11.7), Inches(1.0),
         "A retrieval-augmented assistant with a deterministic booking validator and secure sign-in, "
         "built to answer lab-equipment policy questions and pre-check session requests.", size=20, color=TEXT)
    for i, (label, value) in enumerate([("Equipment", "MIC-01 \u00B7 PRN-01 \u00B7 SCN-01"),
                                        ("Booking window", "09:00 \u2013 17:00, same day"),
                                        ("Stack", "Flask \u00B7 SQLite \u00B7 TF-IDF \u00B7 Gemini")]):
        x = Inches(0.8 + i * 4.0)
        rect(s, x, Inches(5.1), Inches(3.7), Inches(1.2), CARD, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line=RGBColor(0x2A, 0x3A, 0x5C))
        text(s, x + Inches(0.15), Inches(5.2), Inches(3.4), Inches(0.35), label.upper(), size=12, color=MUTED, bold=True)
        text(s, x + Inches(0.15), Inches(5.6), Inches(3.4), Inches(0.5), value, size=14, color=CYAN, font=MONO)
    text(s, Inches(0.8), Inches(6.85), Inches(11), Inches(0.35),
         "Passing LabSlot checks makes a session eligible to request \u2014 it never confirms availability.",
         size=13, color=MUTED)

    # ---- Slide 2: Scenario, objectives, boundaries --------------------------------
    s = new_slide(prs)
    header(s, 2, "Scenario, Objectives & System Boundaries", "Why LabSlot exists and where it stops")
    card(s, Inches(0.6), Inches(1.65), Inches(4.0), Inches(5.1), "Scenario", [
        "Researchers share a microscope, a 3D printer and a scanner.",
        "Each device has its own training module and session limit.",
        "Staff repeatedly answer the same administrative questions.",
    ], size=19)
    card(s, Inches(4.77), Inches(1.65), Inches(4.0), Inches(5.1), "Objectives", [
        "Answer policy questions from approved documents only.",
        "Validate a session deterministically: training, duration, hours.",
        "Protect access with registered, hashed-password accounts.",
        "Decline anything outside the administrative scope.",
    ], size=19, accent=GREEN)
    card(s, Inches(8.93), Inches(1.65), Inches(3.8), Inches(5.1), "Boundaries (declined)", [
        "Live availability or \u201Cis it booked?\u201D checks.",
        "Reserving, changing or cancelling slots.",
        "Disassembly, repair or technical operating steps.",
        "Faults go to the laboratory supervisor.",
    ], size=19, accent=RED)

    # ---- Slide 3: Architecture -----------------------------------------------------
    s = new_slide(prs)
    header(s, 3, "System Architecture", "RAG retrieval + deterministic LabSlot engine + auth layer")

    def node(x, y, w, h, title, sub, accent):
        rect(s, x, y, w, h, CARD, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line=accent)
        text(s, x + Inches(0.1), y + Inches(0.12), w - Inches(0.2), Inches(0.4), title, size=17, bold=True, color=accent, align=PP_ALIGN.CENTER)
        text(s, x + Inches(0.1), y + Inches(0.55), w - Inches(0.2), h - Inches(0.6), sub, size=13, color=TEXT, align=PP_ALIGN.CENTER)

    def arrow(x, y, w, h, shape):
        rect(s, x, y, w, h, MUTED, shape=shape)

    node(Inches(0.6), Inches(1.85), Inches(2.9), Inches(1.5), "Browser UI", ["Dark dashboard", "Validation form + chat"], CYAN)
    arrow(Inches(3.6), Inches(2.35), Inches(0.6), Inches(0.5), MSO_SHAPE.RIGHT_ARROW)
    node(Inches(4.3), Inches(1.85), Inches(4.6), Inches(1.5), "Flask app \u00B7 app.py",
         ["Session guard (user_id) \u00B7 CSRF", "/api/check \u00B7 /api/ask"], GREEN)
    arrow(Inches(9.0), Inches(2.35), Inches(0.6), Inches(0.5), MSO_SHAPE.RIGHT_ARROW)
    node(Inches(9.7), Inches(1.85), Inches(3.0), Inches(1.5), "Auth layer", ["database.py \u00B7 SQLite", "werkzeug salted hashes"], CYAN)
    arrow(Inches(5.2), Inches(3.45), Inches(0.5), Inches(0.55), MSO_SHAPE.DOWN_ARROW)
    arrow(Inches(7.5), Inches(3.45), Inches(0.5), Inches(0.55), MSO_SHAPE.DOWN_ARROW)
    node(Inches(2.4), Inches(4.1), Inches(4.5), Inches(2.4), "RAG pipeline \u00B7 rag.py",
         ["1. Scope guardrail (regex pre-filter)", "2. TF-IDF retrieval, cosine top-3", "3. Gemini grounded answer", "   (offline extractive fallback)"], CYAN)
    node(Inches(7.1), Inches(4.1), Inches(4.3), Inches(2.4), "LabSlot Engine \u00B7 tools.py",
         ["check_equipment_session()", "Integer-minute rule checks", "No LLM \u2014 fully deterministic"], GREEN)
    node(Inches(0.6), Inches(4.1), Inches(1.6), Inches(2.4), "docs/", ["catalogue", "booking", "usage"], MUTED)

    # ---- Slide 4: Chunking & retrieval ---------------------------------------------
    s = new_slide(prs)
    header(s, 4, "Knowledge Base Chunking & Vector Retrieval", "From three policy files to grounded, cited answers")
    card(s, Inches(0.6), Inches(1.65), Inches(6.0), Inches(5.1), "Chunking strategy", [
        "Ingest every docs/*.txt file (catalogue, booking, usage).",
        "Split on blank lines: one self-contained block per equipment item or rule.",
        "Long blocks split by line (max 400 chars, 1-line overlap).",
        "Each chunk is prefixed with its document title for context.",
        "Result: 10 small, precise chunks with source + index metadata.",
    ], size=18)
    card(s, Inches(6.8), Inches(1.65), Inches(5.9), Inches(5.1), "Retrieval & generation", [
        "TfidfVectorizer: unigrams + bigrams, English stop words, sublinear tf.",
        "Cosine similarity against the query vector; top-3, min score 0.08.",
        "Chunks passed to Gemini (google-genai) with strict system rules.",
        "UI shows citation tags: source file, chunk id, similarity.",
        "No key or API error? Offline extractive answer from top chunks.",
    ], size=18, accent=GREEN)

    # ---- Slide 5: Validator & rule matrix ------------------------------------------
    s = new_slide(prs)
    header(s, 5, "Deterministic Booking Validator", "check_equipment_session \u2014 rule matrix and verified cases")
    table(s, Inches(0.6), Inches(1.55), Inches(12.1), [3.2, 2.4, 2.6, 3.9], [
        ["Equipment", "Training module", "Max session", "Hours rule"],
        ["MIC-01 Digital Microscope", "MIC-BASIC", "120 min (2 h)", "Start \u2265 09:00, end \u2264 17:00"],
        ["PRN-01 3D Printer", "PRINT-BASIC", "240 min (4 h)", "Same day, no midnight wrap"],
        ["SCN-01 Document Scanner", "None", "60 min (1 h)", "Integer minutes: 540 \u2192 1020"],
    ], font_size=14, row_h=0.42)
    text(s, Inches(0.6), Inches(3.5), Inches(12), Inches(0.4), "Verified test cases", size=18, bold=True, color=CYAN)
    table(s, Inches(0.6), Inches(3.95), Inches(12.1), [3.9, 1.6, 1.8, 4.8], [
        ["Input", "End time", "Result", "Reason"],
        ["MIC-01 \u00B7 10:00 \u00B7 90 min \u00B7 [MIC-BASIC]", "11:30", "Eligible", "All checks satisfied"],
        ["MIC-01 \u00B7 10:00 \u00B7 90 min \u00B7 []", "11:30", "Not eligible", "Missing training MIC-BASIC"],
        ["PRN-01 \u00B7 14:00 \u00B7 240 min \u00B7 [PRINT-BASIC]", "18:00", "Not eligible", "Ends after 17:00 closing time"],
        ["SCN-01 \u00B7 16:00 \u00B7 60 min \u00B7 []", "17:00", "Eligible", "No training needed; ends at 17:00"],
    ], font_size=14, row_h=0.45)
    text(s, Inches(0.6), Inches(6.45), Inches(12), Inches(0.6),
         "Unknown equipment or training codes, malformed times and non-positive durations raise explicit errors. "
         "Duplicate training codes are removed.", size=13, color=MUTED)

    # ---- Slide 6: Promptfoo ---------------------------------------------------------
    s = new_slide(prs)
    header(s, 6, "Promptfoo Guardrail Verification", "Test suite defined in prompt-eval.yaml, run through provider.py")
    table(s, Inches(0.6), Inches(1.65), Inches(12.1), [4.6, 3.9, 1.5, 2.1], [
        ["Test question", "Assertion", "Guardrail", "Expected"],
        ["Which training module is required for the 3D printer?", "Answer contains PRINT-BASIC", "Grounding", "PASS"],
        ["What should users do with malfunctioning equipment?", "Answer directs to laboratory supervisor", "Fault policy", "PASS"],
        ["Is MIC-01 already booked tomorrow?", "States it cannot check availability or reserve", "Boundary", "PASS"],
    ], font_size=14, row_h=0.62)
    card(s, Inches(0.6), Inches(4.4), Inches(5.9), Inches(2.4), "How it runs", [
        "npx promptfoo eval  (uses promptfooconfig.yaml)",
        "provider.py exposes call_api(prompt, options, context).",
    ], size=14)
    card(s, Inches(6.8), Inches(4.4), Inches(5.9), Inches(2.4), "Verification note", [
        "Assertions were also checked directly against provider.py in offline mode.",
        "Run the eval yourself to reproduce results with your Gemini key.",
    ], size=14, accent=GREEN)

    # ---- Slide 7: Deployment & verification matrix ----------------------------------
    s = new_slide(prs)
    header(s, 7, "Deployment, Reproduction & Verification", "From clone to running LabSlot in minutes")
    card(s, Inches(0.6), Inches(1.65), Inches(5.3), Inches(5.1), "Reproduction steps", [
        "python -m venv .venv  &&  activate it",
        "pip install -r requirements.txt",
        "cp .env.example .env  \u2192  add GEMINI_API_KEY",
        "python database.py   (init SQLite)",
        "python app.py  \u2192  http://127.0.0.1:5000",
        "npx promptfoo eval",
    ], size=18)
    table(s, Inches(6.1), Inches(1.7), Inches(6.6), [2.5, 2.7, 1.4], [
        ["Check", "How", "Expected"],
        ["Validator cases", "python tools.py", "4 cases match"],
        ["RAG index", "python rag.py", "10 chunks"],
        ["Login guard", "GET / signed out", "302 \u2192 /login"],
        ["Promptfoo", "npx promptfoo eval", "3 / 3 PASS"],
        ["Slide deck", "python make_presentation.py", "7 slides"],
        ["Package", "python make_zip.py", "ZIP created"],
    ], font_size=13, row_h=0.55)

    prs.save(OUTPUT)
    print(f"LabSlot presentation written to {OUTPUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()
