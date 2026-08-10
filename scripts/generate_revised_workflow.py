from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUT = Path("output/pdf/Pharmacy_Inventory_Project_Workflow_Revised.pdf")


def build_pdf() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleX", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=colors.HexColor("#075B57"), alignment=TA_CENTER, spaceAfter=14))
    styles.add(ParagraphStyle(name="SubX", parent=styles["Normal"], fontSize=11, leading=16, textColor=colors.HexColor("#426A67"), alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="H1X", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor("#075B57"), spaceBefore=8, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2X", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#0B7D75"), spaceBefore=7, spaceAfter=5))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=9.4, leading=14, textColor=colors.HexColor("#173C3A"), spaceAfter=7))
    styles.add(ParagraphStyle(name="SmallX", parent=styles["BodyText"], fontSize=8.1, leading=11, textColor=colors.HexColor("#426A67")))
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=16*mm, bottomMargin=16*mm, title="Pharmacy Inventory & Expiry Management System - Revised Workflow")
    story = []

    def p(text, style="BodyX"):
        story.append(Paragraph(text, styles[style]))

    def h(text, level=1):
        p(text, "H1X" if level == 1 else "H2X")

    def table(headers, rows, widths=None):
        data = [[Paragraph(f"<b>{x}</b>", styles["SmallX"]) for x in headers]] + [[Paragraph(str(x), styles["SmallX"]) for x in row] for row in rows]
        t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#075B57")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CFE2DE")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3FAF8")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 9))

    story += [Spacer(1, 42*mm)]
    p("PHARMACY INVENTORY &<br/>EXPIRY MANAGEMENT SYSTEM", "TitleX")
    p("Practical Hospital Pharmacy Operations Platform", "SubX")
    p("Revised Project Workflow & Implementation Report", "SubX")
    story.append(Spacer(1, 12*mm))
    table(["Field", "Details"], [
        ["Domain", "Healthcare Operations / Hospital Pharmacy"],
        ["Frontend", "React.js + Chart.js"],
        ["Backend", "FastAPI (Python)"],
        ["Current database", "SQLite for local deployment; PostgreSQL-ready configuration"],
        ["Core capabilities", "Inventory, expiry safety, FEFO dispensing, sales billing, procurement and alerts"],
    ], [45*mm, 120*mm])
    p("Prepared as a revised practical workflow document for the implemented final-year project system.", "SubX")
    story.append(PageBreak())

    h("1. Practical Project Scope")
    p("The system digitises the hospital pharmacy workflow from medicine catalogue creation and batch receipt to safe issue, pharmacy-counter sales, alerting, storage lookup, reporting and controlled procurement. The implementation prioritises usable daily operations while retaining forecasting support for reorder planning.")
    table(["In scope in the developed system", "Operational outcome"], [
        ["Role-based access", "Admin, Pharmacist and Viewer views are separated at both UI and API levels."],
        ["Batch and expiry tracking", "Each batch keeps quantity, expiry, supplier and physical storage location."],
        ["FEFO dispensing", "The earliest valid-expiry batch is selected for issue or sale."],
        ["Critical stock alerts", "Low stock is critical only at five or fewer total units for a medicine."],
        ["Email alerts", "Configured Admin and Pharmacist recipients receive threshold-crossing notifications."],
        ["Sales and buyer billing", "Pharmacists can sell medicine and issue a detailed printable bill."],
        ["Procurement review", "Admin can review safety-driven supplier requests before sending them."],
    ], [68*mm, 97*mm])
    h("2. Architecture", 1)
    p("React single-page application → JWT-authenticated FastAPI REST API → relational database. The frontend provides role-specific navigation and polished operational screens. The backend applies RBAC to every sensitive endpoint and records stock movements. Forecast calculations are served through an internal forecasting service module.")
    story.append(PageBreak())

    h("3. Role-Based Workflow")
    table(["Role", "Access in the developed system"], [
        ["Admin", "Manages users and alert emails; maintains catalogue and batches; views reports, suppliers, transactions, storage, forecasts and procurement; approves supplier orders."],
        ["Pharmacist", "Receives stock, manages batches, dispenses using FEFO, sells medicine, generates bills, views alerts, storage map, reports and reorder information."],
        ["Viewer", "Receives a deliberately restricted, read-only safety overview. Hospital operational details, suppliers, locations, transactions, reports, forecasts and orders are not retrievable."],
    ], [35*mm, 130*mm])
    h("4. Inventory and Storage Workflow")
    p("Admin or Pharmacist creates a medicine record and records each received batch with supplier, received date, expiry date, quantity and an approved storage code. The Storage Reference screen is location-first: it separates a medicine location directory from a storage-station guide for drawers, refrigerators and controlled areas.")
    p("Stock is reduced through FEFO dispensing or sales. Each movement creates an immutable inventory transaction. Batch records retain the location code, enabling the pharmacist to find stock quickly without relying on memory.")
    h("5. Safety Alert Workflow")
    p("Near-expiry alerts are evaluated from batch expiry dates. Low-stock alerts are evaluated from the aggregate quantity of all batches for a medicine. The safety threshold is fixed at ≤5 units; it is intentionally separate from the planning reorder level.")
    p("When stock crosses from above five to five or fewer units, the backend sends an SMTP email to saved Admin and Pharmacist alert-email addresses. The crossing rule avoids repeated emails for the same continuing critical state.")
    story.append(PageBreak())

    h("6. Pharmacist Dispensing, Sales and Billing")
    p("The dispensing workspace accepts a SKU or batch number and finds the earliest-expiring valid batch. The pharmacist enters quantity, receiving department and optional note. The system validates available quantity, decrements stock and logs the FEFO transaction.")
    table(["Sales & Billing step", "System action"], [
        ["1. Identify item", "Pharmacist enters a medicine SKU or batch number."],
        ["2. FEFO validation", "System selects the earliest valid saleable batch and checks quantity."],
        ["3. Buyer entry", "Buyer name, optional phone number, quantity and unit price are entered."],
        ["4. Invoice creation", "A unique sale invoice is created and a Sale inventory transaction is recorded."],
        ["5. Printable bill", "Bill displays invoice number, buyer details, medicine, SKU, batch, quantity, price, total, seller and date/time."],
        ["6. Safety check", "If the sale crosses the critical threshold, notification email is triggered."],
    ], [52*mm, 113*mm])
    h("7. Procurement Workflow")
    p("Safety scans group low-stock and near-expiry risks into reviewable procurement requests. Requests are visible only to Admin. The Admin explicitly approves a request before it is sent to the supplier; the system records the supplier order and generates a pro-forma invoice. This preserves clinical safety while preventing automatic, unreviewed purchasing.")
    h("8. Forecasting and Reorder Planning")
    p("Historical consumption records are analysed for 30, 60 and 90-day horizons. The current application provides a forecasting service and reorder recommendation view. The next academic enhancement is to replace or extend the current estimator with validated Prophet/XGBoost models, performance metrics and scheduled retraining.")
    story.append(PageBreak())

    h("9. Reports, Audit and Data Controls")
    table(["Capability", "Developed behaviour"], [
        ["Inventory export", "CSV export provides medicine, batch, quantity, expiry and reorder information."],
        ["Alert export", "CSV and PDF alert reports provide critical-stock and near-expiry information."],
        ["Transaction record", "Dispensing, purchase and sale movements are retained with reference values."],
        ["Audit record", "Procurement and critical-stock email actions are auditable."],
        ["Sensitive data control", "API role dependencies prevent Viewer accounts from obtaining protected hospital operational data."],
    ], [55*mm, 110*mm])
    h("10. Core Data Model")
    table(["Entity", "Purpose"], [
        ["users", "Credentials, role and optional alert email."],
        ["medicines", "Master medicine record, unit, category, reorder target and ideal stock."],
        ["batch_stocks", "Batch number, supplier, quantity, dates and physical storage location."],
        ["inventory_transactions", "Immutable issue, purchase, dispense and sale movement history."],
        ["sale_invoices", "Buyer, item, batch, quantity, pricing, total, seller and sale timestamp."],
        ["procurement_requests / invoices", "Admin-reviewed supplier order workflow."],
        ["storage_locations", "Approved drawers, shelves, refrigerators and controlled zones."],
    ], [58*mm, 107*mm])
    h("11. Key API Workflows")
    table(["Method", "Endpoint", "Role"], [
        ["POST", "/auth/login", "All authenticated users"],
        ["POST", "/batches", "Admin, Pharmacist"],
        ["POST", "/dispense", "Admin, Pharmacist"],
        ["POST", "/sales", "Admin, Pharmacist"],
        ["GET", "/alerts", "Admin, Pharmacist"],
        ["POST", "/procurement/scan", "Admin"],
        ["GET", "/reports/alerts.pdf", "Admin, Pharmacist"],
    ], [22*mm, 80*mm, 63*mm])
    story.append(PageBreak())

    h("12. Implementation Status")
    table(["Module", "Status", "Notes"], [
        ["Authentication and RBAC", "Completed", "JWT login, protected API routes and role-aware frontend navigation."],
        ["Medicine and batch management", "Completed", "CRUD, locations, batch tracking and expiry dates."],
        ["FEFO dispensing", "Completed", "Valid earliest-expiry selection and transaction logging."],
        ["Safety alerts and email", "Completed", "Near-expiry, ≤5 low-stock alerts and SMTP notification hook."],
        ["Sales and buyer bill", "Completed", "Counter sale, persisted invoice and print-friendly bill."],
        ["Procurement review", "Completed", "Admin-controlled safety scan, supplier order and invoice record."],
        ["Forecasting UI", "Completed", "30/60/90-day display and reorder guidance."],
        ["Prophet/XGBoost validation", "Planned enhancement", "Model comparison, metrics and scheduled retraining remain future academic work."],
        ["Automated scheduler", "Planned enhancement", "Nightly scans and weekly retraining can be added for production deployment."],
    ], [45*mm, 34*mm, 86*mm])
    h("13. Testing and Deployment")
    p("The frontend is production-built using Vite and the backend source is compilation-checked. Recommended next validation includes API tests for role boundaries, FEFO selection, stock threshold crossing, invoice creation and SMTP delivery using a test mail account. Docker Compose and PostgreSQL configuration remain available for a production-oriented deployment phase.")
    h("14. Conclusion")
    p("This revised workflow documents the system as a practical pharmacy operations platform. It preserves the academic strengths of batch-level stock safety, expiry monitoring, forecasting and RBAC, while adding controlled procurement, pharmacist sales billing, physical storage clarity and critical-email escalation for day-to-day usability.")

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CFE2DE"))
        canvas.line(17*mm, 11*mm, A4[0]-17*mm, 11*mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#426A67"))
        canvas.drawString(17*mm, 7*mm, "Pharmacy Inventory & Expiry Management System - Revised Workflow")
        canvas.drawRightString(A4[0]-17*mm, 7*mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    build_pdf()
