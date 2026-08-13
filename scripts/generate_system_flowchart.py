from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Pharmacy_Inventory_Expiry_Management_System_Flowchart.pdf"


NAVY = HexColor("#17324D")
TEAL = HexColor("#147D7E")
BLUE = HexColor("#3874B8")
GREEN = HexColor("#2C8C5A")
GOLD = HexColor("#C88A18")
RED = HexColor("#C84F4F")
INK = HexColor("#1C2733")
MUTED = HexColor("#5D6A75")
PALE = HexColor("#F4F8FA")
LINE = HexColor("#C7D5DC")


def lines_for(text: str, max_width: float, font="Helvetica", size=8.2):
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def node(c, x, y, w, h, title, body, color=BLUE):
    c.setFillColor(colors.white)
    c.setStrokeColor(color)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
    c.setFillColor(color)
    c.roundRect(x, y + h - 21, w, 21, 8, stroke=0, fill=1)
    c.rect(x, y + h - 8, w, 8, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8.4)
    c.drawCentredString(x + w / 2, y + h - 14, title)
    c.setFillColor(INK)
    c.setFont("Helvetica", 7.6)
    text_y = y + h - 33
    for line in lines_for(body, w - 16, size=7.6):
        c.drawCentredString(x + w / 2, text_y, line)
        text_y -= 9.1


def arrow(c, x1, y1, x2, y2, color=LINE):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.25)
    c.line(x1, y1, x2, y2)
    angle = __import__("math").atan2(y2 - y1, x2 - x1)
    size = 5
    p1 = (x2 - size * __import__("math").cos(angle - .45), y2 - size * __import__("math").sin(angle - .45))
    p2 = (x2 - size * __import__("math").cos(angle + .45), y2 - size * __import__("math").sin(angle + .45))
    path = c.beginPath(); path.moveTo(x2, y2); path.lineTo(*p1); path.lineTo(*p2); path.close()
    c.drawPath(path, stroke=0, fill=1)


def title(c, heading, subheading, width, height, page):
    c.setFillColor(NAVY); c.rect(0, height - 62, width, 62, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 18); c.drawString(32, height - 32, heading)
    c.setFont("Helvetica", 8.8); c.drawString(32, height - 47, subheading)
    c.setFillColor(MUTED); c.setFont("Helvetica", 7.4)
    c.drawRightString(width - 30, 16, f"ArogyaMitra Pharmacy Inventory & Expiry Management System | Page {page}")


def page_one(c):
    width, height = landscape(A4)
    title(c, "End-to-end operating flow", "A multi-pharmacy, batch-level inventory, sales, procurement, expiry and waste-control workflow", width, height, 1)
    columns = [38, 200, 362, 524, 686]
    y_top, h, w = 400, 72, 128
    stages = [
        ("1. Platform setup", "Platform Admin creates a hospital/pharmacy workspace, country details and its first Pharmacy Admin.", NAVY),
        ("2. Local catalogue", "WHO reference starter catalogue is created. Pharmacy staff add local approved items, suppliers and real batches.", BLUE),
        ("3. Receive & store", "Record supplier, batch, quantity, price, expiry date and storage location. Stock remains batch-level.", TEAL),
        ("4. Daily operations", "Use FEFO for dispensing and sales. Each issue is recorded; department stock and buyer bill are updated.", GREEN),
        ("5. Monitor & replenish", "Forecast demand, calculate stock risk, prepare purchase request, Admin approves, supplier receives order email.", GOLD),
    ]
    for i, (head, body, color) in enumerate(stages):
        node(c, columns[i], y_top, w, h, head, body, color)
        if i < len(stages) - 1:
            arrow(c, columns[i] + w, y_top + h / 2, columns[i + 1] - 6, y_top + h / 2)
    c.setFillColor(PALE); c.roundRect(34, 287, width - 68, 78, 10, stroke=0, fill=1)
    c.setFillColor(NAVY); c.setFont("Helvetica-Bold", 11); c.drawString(50, 344, "Controlled stock movement")
    movements = [
        ("Purchase", "Supplier -> pharmacy batch stock", TEAL),
        ("Dispense", "Pharmacy -> named hospital department", BLUE),
        ("Sale", "Pharmacy -> named buyer with bill", GREEN),
        ("Return / waste", "Quarantine -> supplier or authorised collector", RED),
    ]
    mx = [53, 238, 423, 608]
    for i, (a, b, color) in enumerate(movements):
        c.setFillColor(color); c.circle(mx[i], 318, 7, stroke=0, fill=1)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 8.4); c.drawString(mx[i] + 12, 322, a)
        c.setFont("Helvetica", 7.5); c.drawString(mx[i] + 12, 310, b)
    c.setFont("Helvetica-Bold", 11); c.setFillColor(NAVY); c.drawString(38, 255, "Data accountability at every stage")
    accountability = [
        ("Pharmacy isolation", "Each hospital/pharmacy sees only its own medicines, batches, users, purchases, sales and reports."),
        ("Batch traceability", "Every movement keeps the batch number, supplier, expiry date, storage or department destination."),
        ("Financial visibility", "Sales & purchases provides separate totals, bill count, purchase-order count and per-pharmacy purchase records."),
        ("Audit evidence", "Email events, stock movements, return collection and signed handover references are retained as audit logs."),
    ]
    for i, (a, b) in enumerate(accountability):
        x = 38 + (i % 2) * 390; y = 172 - (i // 2) * 76
        node(c, x, y, 350, 54, a, b, [BLUE, TEAL, GOLD, RED][i])
    c.setFillColor(MUTED); c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(38, 49, "Important: Reference catalogues guide selection only. Each pharmacy must verify local regulatory approval, supplier credentials, prices, batches and stock before use.")


def page_two(c):
    width, height = landscape(A4)
    title(c, "Expiry prevention, returns and safe disposal", "A controlled chain of custody that prevents unsafe sale, dumping and unauthorised disposal", width, height, 2)
    zones = [
        ("GREEN - over 6 months", "Routine FEFO stock. Keep batch in active storage.", GREEN),
        ("YELLOW - 3 to 6 months", "Prioritise issue/sale; email supplier for return credit or reverse logistics.", GOLD),
        ("RED - under 3 months", "Block from new retail sales; review return or controlled internal issue policy.", RED),
        ("BLACK - expired", "Auto-exclude from sale/dispense. Move to locked labelled quarantine.", HexColor("#414141")),
    ]
    for i, (a, b, color) in enumerate(zones):
        node(c, 42 + i * 199, 400, 172, 68, a, b, color)
        if i < 3: arrow(c, 214 + i * 199, 434, 234 + i * 199, 434)
    nodes = [
        ("1. Quarantine", "Remove expired or damaged medicines immediately. Lock in labelled, non-saleable area.", 44, 255, RED),
        ("2. Select route", "Supplier/distributor return for credit, or authorised biomedical-waste handler.", 255, 255, GOLD),
        ("3. Notify & schedule", "System emails the original supplier with pharmacy, batch, quantity and expiry details.", 466, 255, BLUE),
        ("4. Verified handover", "Collect signed return challan or waste manifest. Record collector and collection reference.", 677, 255, TEAL),
        ("5. Close record", "Confirm collection; record disposal date, route, document reference and audit trail.", 466, 132, GREEN),
    ]
    for a, b, x, y, color in nodes:
        node(c, x, y, 170, 76, a, b, color)
    arrow(c, 214, 293, 249, 293); arrow(c, 425, 293, 460, 293); arrow(c, 636, 293, 671, 293); arrow(c, 762, 255, 552, 210)
    c.setFillColor(PALE); c.roundRect(41, 70, width - 82, 44, 8, stroke=0, fill=1)
    c.setFillColor(NAVY); c.setFont("Helvetica-Bold", 8.6); c.drawString(56, 95, "Communication controls")
    c.setFillColor(INK); c.setFont("Helvetica", 7.8)
    c.drawString(56, 82, "SMTP test confirms email before operations. Supplier return emails and purchase-order emails use the configured sender. Failed delivery is shown as an error, never recorded as sent.")
    c.setFillColor(MUTED); c.setFont("Helvetica", 7.2)
    c.drawString(42, 48, "Reference sources: WHO Model List of Essential Medicines; WHO National Essential Medicines Lists repository; DailyMed; openFDA NDC Directory; CDSCO India. Links are provided in the project README.")


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("Pharmacy Inventory & Expiry Management System - Full Flowchart")
    page_one(c); c.showPage(); page_two(c); c.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
