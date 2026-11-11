"""In-memory question papers; no plaintext exports are retained by the server."""
from html import escape
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether


def export_quiz(quiz, answers=False):
    font = "Helvetica"
    path = Path("C:/Windows/Fonts/arial.ttf")
    if path.exists():
        if "StudioArial" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("StudioArial", str(path)))
        font = "StudioArial"
    styles = getSampleStyleSheet()
    for name in ("Normal", "BodyText", "Title", "Heading1", "Heading2"):
        styles[name].fontName = font
    styles.add(ParagraphStyle(name="Question", fontName=font, fontSize=11, leading=17, spaceAfter=8, alignment=TA_LEFT, splitLongWords=True))
    styles.add(ParagraphStyle(name="Source", fontName=font, fontSize=9, leading=13, textColor=colors.HexColor("#66506e"), spaceAfter=13))
    clean = lambda value: escape(str(value)).replace("\n", "<br/>")
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=48, leftMargin=48, topMargin=54, bottomMargin=50,
        title=quiz["title"], author="Jozi Buddy Study Studio")
    story = [Paragraph("JOZI BUDDY / STUDY STUDIO", styles["Source"]), Paragraph(clean(quiz["title"]), styles["Title"]),
        Paragraph("Answer key and marking guide" if answers else "Question paper", styles["Heading2"]), Spacer(1, 14)]
    total = sum(question["marks"] for question in quiz["questions"])
    story += [Paragraph(f"{len(quiz['questions'])} questions · {total} marks".replace("·", "|"), styles["BodyText"]), Spacer(1, 18)]
    for index, question in enumerate(quiz["questions"], 1):
        unit = "mark" if question["marks"] == 1 else "marks"
        story.append(Paragraph(f"{index}. {clean(question['prompt'])} ({question['marks']} {unit})", styles["Question"]))
        if question["type"] == "mcq":
            for option_index, option in enumerate(question["options"]):
                story.append(Paragraph(f"{chr(65 + option_index)}. {clean(option)}", styles["Question"]))
        elif not answers:
            guidance = "2-4 sentences" if question["type"] == "short" else "1-3 paragraphs"
            story.append(Paragraph(f"Suggested response: {guidance}.", styles["Source"]))
            story.append(Spacer(1, 35 if question["type"] == "short" else 70))
        if answers:
            answer = question["options"][question["correct_index"]] if question["type"] == "mcq" else question["model_answer"]
            story.append(Paragraph("Answer: " + clean(answer), styles["Question"]))
            if question.get("rubric"):
                story.append(Paragraph("Marking: " + clean(question["rubric"]), styles["BodyText"]))
            if question.get("explanation"):
                story.append(Paragraph(clean(question["explanation"]), styles["BodyText"]))
        story.append(Paragraph("Source pages: " + ", ".join(map(str, question["pages"])) + (" | Sources need review" if question.get("needs_review") else ""), styles["Source"]))
        story.append(Spacer(1, 10))

    def footer(canvas, document):
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#777078"))
        canvas.drawString(48, 28, "Jozi Buddy | AI-assisted study material; review against the source PDF.")
        canvas.drawRightString(A4[0] - 48, 28, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
