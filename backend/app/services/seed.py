from __future__ import annotations

from datetime import date, timedelta
from random import Random

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    AuditLog,
    BatchStock,
    ConsumptionRecord,
    HospitalDepartment,
    InventoryTransaction,
    Medicine,
    MedicineCategory,
    PurchaseOrder,
    Pharmacy,
    StorageLocation,
    Supplier,
    User,
)
from app.services.auth import hash_password

settings = get_settings()

# Generic names only: this is a WHO EML-inspired starter catalogue, not a claim
# that a medicine is approved, stocked, or available in every country.
WHO_STARTER_MEDICINES = [
    ("Paracetamol", "Analgesic", "tablet", "Pain and fever relief"),
    ("Amoxicillin", "Antibiotic", "capsule", "Antibiotic; follow local stewardship policy"),
    ("Ceftriaxone", "Antibiotic", "vial", "Injectable antibiotic"),
    ("Metformin", "Endocrine", "tablet", "Diabetes treatment"),
    ("Insulin human", "Hormone", "vial", "Diabetes treatment"),
    ("Amlodipine", "Cardiac", "tablet", "Hypertension treatment"),
    ("Salbutamol", "Respiratory", "inhaler", "Bronchodilator"),
    ("Oral rehydration salts", "Gastrointestinal", "sachet", "Oral rehydration"),
    ("Omeprazole", "Gastrointestinal", "capsule", "Acid suppression"),
    ("Fluconazole", "Antifungal", "tablet", "Antifungal medicine"),
    ("Acyclovir", "Antiviral", "tablet", "Antiviral medicine"),
    ("Dexamethasone", "Emergency", "vial", "Corticosteroid"),
    ("Adrenaline", "Emergency", "ampoule", "Emergency medicine"),
    ("Normal saline", "IV Fluids", "bottle", "Intravenous fluid"),
    ("Oxytocin", "Hormone", "ampoule", "Obstetric medicine"),
]


def add_who_starter_catalogue(db: Session, pharmacy_id: int) -> None:
    """Create an empty, source-labelled generic catalogue for a newly registered pharmacy."""
    if db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).count():
        return
    for index, (name, category, unit, description) in enumerate(WHO_STARTER_MEDICINES, start=1):
        db.add(Medicine(name=name, sku=f"WHO-{pharmacy_id:04d}-{index:03d}", category=category, unit=unit, reorder_level=25, ideal_stock=100, description=description, reference_source="WHO Model List of Essential Medicines", pharmacy_id=pharmacy_id))
    db.commit()


def _days_ago(days: int) -> date:
    return date.today() - timedelta(days=days)


def seed_demo_data(db: Session) -> None:
    pharmacy = db.query(Pharmacy).filter(Pharmacy.name == "ArogyaMitra Demo Pharmacy").first()
    if not pharmacy:
        pharmacy = Pharmacy(name="ArogyaMitra Demo Pharmacy", hospital_name="ArogyaMitra Hospital", licence_number="DEMO-PHARM-001", address="Demo hospital campus")
        db.add(pharmacy)
        db.flush()
    # Existing demo records belong to the demo tenant after an in-place upgrade.
    db.query(User).filter(User.pharmacy_id.is_(None)).update({User.pharmacy_id: pharmacy.id}, synchronize_session=False)
    db.query(Medicine).filter(Medicine.pharmacy_id.is_(None)).update({Medicine.pharmacy_id: pharmacy.id}, synchronize_session=False)
    categories = [
        "Antibiotic",
        "Analgesic",
        "Antipyretic",
        "Antihistamine",
        "Antacid",
        "Antiviral",
        "Antifungal",
        "Vaccine",
        "Hormone",
        "Vitamin",
        "Injection",
        "Syrup",
        "Tablet",
        "Capsule",
        "Cream",
        "Ointment",
        "Eye Drops",
        "IV Fluids",
        "Cardiac",
        "Endocrine",
        "Gastrointestinal",
        "Respiratory",
        "Neurology",
        "Emergency",
        "Critical Care",
        "Antiseptic",
        "Dermatology",
        "Ophthalmology",
        "Renal",
        "Psychiatry",
        "Anaesthesia",
        "Musculoskeletal",
        "Urology",
    ]
    existing_categories = {category.name for category in db.query(MedicineCategory).all()}
    db.add_all(
        [
            MedicineCategory(name=name, description=f"{name} medicines used in a hospital pharmacy")
            for name in categories
            if name not in existing_categories
        ]
    )

    suppliers = [
        Supplier(company_name="Apollo Health Distribution", contact_person="Rahul Sharma", phone="9876543210", email="rahul@apollohealth.example", gst_number="19ABCDE1234F1Z5", address="Kolkata, West Bengal"),
        Supplier(company_name="Cipla MedSupplies", contact_person="Neha Verma", phone="9876543211", email="neha@cipla.example", gst_number="27ABCDE1234F1Z6", address="Mumbai, Maharashtra"),
        Supplier(company_name="Sun Pharma Logistics", contact_person="Arjun Das", phone="9876543212", email="arjun@sunpharma.example", gst_number="07ABCDE1234F1Z7", address="Delhi NCR"),
        Supplier(company_name="Mankind Pharma Connect", contact_person="Priya Nair", phone="9876543213", email="priya@mankind.example", gst_number="09ABCDE1234F1Z8", address="Jaipur, Rajasthan"),
        Supplier(company_name="Dr. Reddy's Supply Hub", contact_person="Suresh Kumar", phone="9876543214", email="suresh@reddys.example", gst_number="36ABCDE1234F1Z9", address="Hyderabad, Telangana"),
    ]
    existing_suppliers = {supplier.company_name for supplier in db.query(Supplier).all()}
    db.add_all([supplier for supplier in suppliers if supplier.company_name not in existing_suppliers])

    departments = [
        HospitalDepartment(name="Emergency", floor="Ground", contact_extension="1001"),
        HospitalDepartment(name="ICU", floor="2nd", contact_extension="1002"),
        HospitalDepartment(name="General Ward", floor="3rd", contact_extension="1003"),
        HospitalDepartment(name="OPD", floor="Ground", contact_extension="1004"),
        HospitalDepartment(name="Pediatrics", floor="1st", contact_extension="1005"),
        HospitalDepartment(name="Cardiology", floor="4th", contact_extension="1006"),
        HospitalDepartment(name="Orthopedics", floor="4th", contact_extension="1007"),
    ]
    existing_departments = {department.name for department in db.query(HospitalDepartment).all()}
    db.add_all([department for department in departments if department.name not in existing_departments])

    locations = [
        StorageLocation(code="A1", name="Shelf A1", temperature_zone="Room", notes="General analgesics and common tablets"),
        StorageLocation(code="A2", name="Shelf A2", temperature_zone="Room", notes="Antibiotics"),
        StorageLocation(code="B1", name="Refrigerated B1", temperature_zone="Refrigerated", notes="Vaccines and insulin"),
        StorageLocation(code="B2", name="Refrigerated B2", temperature_zone="Refrigerated", notes="Biologics and sensitive medicines"),
        StorageLocation(code="C1", name="Controlled C1", temperature_zone="Controlled", notes="Restricted drugs"),
    ]
    existing_locations = {location.code for location in db.query(StorageLocation).all()}
    db.add_all([location for location in locations if location.code not in existing_locations])

    purchase_orders = [
        PurchaseOrder(po_number="PO1001", supplier_name=suppliers[0].company_name, order_date=date.today() - timedelta(days=12), total_amount=25000.0, status="Received", pharmacy_id=pharmacy.id),
        PurchaseOrder(po_number="PO1002", supplier_name=suppliers[1].company_name, order_date=date.today() - timedelta(days=7), total_amount=18250.0, status="In Transit", pharmacy_id=pharmacy.id),
        PurchaseOrder(po_number="PO1003", supplier_name=suppliers[2].company_name, order_date=date.today() - timedelta(days=3), total_amount=9600.0, status="Pending", pharmacy_id=pharmacy.id),
    ]
    existing_pos = {purchase_order.po_number for purchase_order in db.query(PurchaseOrder).all()}
    db.add_all([purchase_order for purchase_order in purchase_orders if purchase_order.po_number not in existing_pos])

    if db.query(User).count() == 0:
        demo_users = [
            User(username=settings.demo_admin_username, full_name="System Administrator", role="admin", password=hash_password(settings.demo_admin_password), pharmacy_id=pharmacy.id),
            User(username=settings.demo_pharmacist_username, full_name="Lead Pharmacist", role="pharmacist", password=hash_password(settings.demo_pharmacist_password), pharmacy_id=pharmacy.id),
        ]
        db.add_all(demo_users)
    if not db.query(User).filter(User.username == "platformadmin").first():
        db.add(User(username="platformadmin", full_name="Platform Administrator", role="platform_admin", password=hash_password("platform123"), pharmacy_id=None))

    medicines = [
        Medicine(name="Paracetamol 500mg", sku="MED-001", category="Analgesic", unit="tablet", reorder_level=120, ideal_stock=400, description="Fever and pain relief"),
        Medicine(name="Amoxicillin 250mg", sku="MED-002", category="Antibiotic", unit="capsule", reorder_level=80, ideal_stock=240, description="Broad-spectrum antibiotic"),
        Medicine(name="Pantoprazole 40mg", sku="MED-003", category="Antacid", unit="tablet", reorder_level=70, ideal_stock=220, description="Acid suppression therapy"),
        Medicine(name="Metformin 500mg", sku="MED-004", category="Endocrine", unit="tablet", reorder_level=100, ideal_stock=300, description="Diabetes management"),
        Medicine(name="Ondansetron 4mg", sku="MED-005", category="Emergency", unit="tablet", reorder_level=60, ideal_stock=180, description="Nausea control"),
        Medicine(name="Cetirizine 10mg", sku="MED-006", category="Antihistamine", unit="tablet", reorder_level=90, ideal_stock=260, description="Allergy relief"),
        Medicine(name="Azithromycin 500mg", sku="MED-007", category="Antibiotic", unit="tablet", reorder_level=75, ideal_stock=220, description="Macrolide antibiotic"),
        Medicine(name="Salbutamol Inhaler", sku="MED-008", category="Respiratory", unit="inhaler", reorder_level=50, ideal_stock=150, description="Bronchodilator for asthma"),
        Medicine(name="Insulin Aspart", sku="MED-009", category="Hormone", unit="vial", reorder_level=40, ideal_stock=120, description="Rapid acting insulin"),
        Medicine(name="Vitamin D3 60K", sku="MED-010", category="Vitamin", unit="capsule", reorder_level=100, ideal_stock=350, description="Vitamin supplementation"),
        Medicine(name="Ibuprofen 400mg", sku="MED-011", category="Analgesic", unit="tablet", reorder_level=100, ideal_stock=300, description="Anti-inflammatory pain relief"),
        Medicine(name="Diclofenac 50mg", sku="MED-012", category="Musculoskeletal", unit="tablet", reorder_level=80, ideal_stock=240, description="NSAID for pain and inflammation"),
        Medicine(name="Ceftriaxone 1g", sku="MED-013", category="Antibiotic", unit="vial", reorder_level=60, ideal_stock=180, description="Injectable cephalosporin antibiotic"),
        Medicine(name="Meropenem 1g", sku="MED-014", category="Critical Care", unit="vial", reorder_level=30, ideal_stock=90, description="Broad spectrum ICU antibiotic"),
        Medicine(name="Fluconazole 150mg", sku="MED-015", category="Antifungal", unit="tablet", reorder_level=50, ideal_stock=150, description="Systemic antifungal medicine"),
        Medicine(name="Acyclovir 400mg", sku="MED-016", category="Antiviral", unit="tablet", reorder_level=50, ideal_stock=150, description="Antiviral therapy"),
        Medicine(name="Omeprazole 20mg", sku="MED-017", category="Gastrointestinal", unit="capsule", reorder_level=100, ideal_stock=300, description="Acid suppression"),
        Medicine(name="ORS Sachet", sku="MED-018", category="Gastrointestinal", unit="sachet", reorder_level=120, ideal_stock=360, description="Oral rehydration salts"),
        Medicine(name="Lactulose Syrup", sku="MED-019", category="Syrup", unit="bottle", reorder_level=30, ideal_stock=90, description="Osmotic laxative"),
        Medicine(name="Amlodipine 5mg", sku="MED-020", category="Cardiac", unit="tablet", reorder_level=90, ideal_stock=270, description="Antihypertensive calcium channel blocker"),
        Medicine(name="Atorvastatin 10mg", sku="MED-021", category="Cardiac", unit="tablet", reorder_level=80, ideal_stock=240, description="Cholesterol management"),
        Medicine(name="Furosemide 40mg", sku="MED-022", category="Cardiac", unit="tablet", reorder_level=60, ideal_stock=180, description="Loop diuretic"),
        Medicine(name="Losartan 50mg", sku="MED-023", category="Cardiac", unit="tablet", reorder_level=90, ideal_stock=270, description="ARB antihypertensive"),
        Medicine(name="Levothyroxine 50mcg", sku="MED-024", category="Endocrine", unit="tablet", reorder_level=70, ideal_stock=210, description="Thyroid hormone replacement"),
        Medicine(name="Insulin Glargine", sku="MED-025", category="Hormone", unit="vial", reorder_level=35, ideal_stock=105, description="Long acting insulin"),
        Medicine(name="Dexamethasone 4mg", sku="MED-026", category="Emergency", unit="vial", reorder_level=60, ideal_stock=180, description="Corticosteroid injection"),
        Medicine(name="Adrenaline 1mg/ml", sku="MED-027", category="Emergency", unit="ampoule", reorder_level=50, ideal_stock=150, description="Emergency anaphylaxis medicine"),
        Medicine(name="Normal Saline 500ml", sku="MED-028", category="IV Fluids", unit="bottle", reorder_level=150, ideal_stock=500, description="Intravenous fluid"),
        Medicine(name="Ringer Lactate 500ml", sku="MED-029", category="IV Fluids", unit="bottle", reorder_level=120, ideal_stock=400, description="Balanced crystalloid solution"),
        Medicine(name="Enoxaparin 40mg", sku="MED-030", category="Cardiac", unit="syringe", reorder_level=45, ideal_stock=135, description="Low molecular weight anticoagulant"),
        Medicine(name="Levetiracetam 500mg", sku="MED-031", category="Neurology", unit="tablet", reorder_level=50, ideal_stock=150, description="Anticonvulsant"),
        Medicine(name="Diazepam 5mg", sku="MED-032", category="Neurology", unit="ampoule", reorder_level=30, ideal_stock=90, description="Sedative and anticonvulsant"),
        Medicine(name="Montelukast 10mg", sku="MED-033", category="Respiratory", unit="tablet", reorder_level=60, ideal_stock=180, description="Asthma controller"),
        Medicine(name="Budesonide Inhaler", sku="MED-034", category="Respiratory", unit="inhaler", reorder_level=35, ideal_stock=105, description="Inhaled corticosteroid"),
        Medicine(name="Moxifloxacin Eye Drops", sku="MED-035", category="Ophthalmology", unit="bottle", reorder_level=25, ideal_stock=75, description="Antibiotic eye drops"),
        Medicine(name="Clotrimazole Cream", sku="MED-036", category="Dermatology", unit="tube", reorder_level=40, ideal_stock=120, description="Topical antifungal"),
        Medicine(name="Povidone Iodine", sku="MED-037", category="Antiseptic", unit="bottle", reorder_level=40, ideal_stock=120, description="Skin antiseptic solution"),
        Medicine(name="Ondansetron Injection", sku="MED-038", category="Injection", unit="ampoule", reorder_level=60, ideal_stock=180, description="Antiemetic injection"),
        Medicine(name="Folic Acid 5mg", sku="MED-039", category="Vitamin", unit="tablet", reorder_level=70, ideal_stock=210, description="Vitamin B9 supplementation"),
        Medicine(name="Ferrous Ascorbate", sku="MED-040", category="Vitamin", unit="tablet", reorder_level=70, ideal_stock=210, description="Iron supplementation"),
    ]
    existing_medicines = {medicine.sku for medicine in db.query(Medicine).all()}
    medicine_objects: list[Medicine] = []
    for medicine in medicines:
        if medicine.sku in existing_medicines:
            medicine_objects.append(db.query(Medicine).filter(Medicine.sku == medicine.sku).first())
        else:
            db.add(medicine)
            medicine_objects.append(medicine)
    db.flush()

    rng = Random(42)
    wards = [department.name for department in departments]

    for medicine_index, medicine in enumerate(medicine_objects):
        if medicine is None:
            continue
        if db.query(BatchStock).filter(BatchStock.medicine_id == medicine.id).count() > 0:
            continue
        base_quantity = medicine.ideal_stock - (medicine_index * 28)
        for batch_index in range(4):
            quantity = max(15, base_quantity - batch_index * rng.randint(15, 60))
            expiry_offset = 20 + medicine_index * 12 + batch_index * 38
            batch = BatchStock(
                medicine_id=medicine.id,
                batch_number=f"{medicine.sku}-B{batch_index + 1}",
                supplier=suppliers[(medicine_index + batch_index) % len(suppliers)].company_name,
                quantity=quantity,
                received_on=_days_ago(140 - batch_index * 30),
                expiry_date=date.today() + timedelta(days=expiry_offset if batch_index != 0 else expiry_offset // 2),
                location=locations[batch_index % len(locations)].code,
            )
            db.add(batch)

        consumption_seed = 7 + medicine_index * 2
        for day_offset in range(730):
            seasonal = 2 if 280 <= day_offset % 365 <= 340 else 0
            weekend = 1 if (day_offset % 7) in (5, 6) else 0
            quantity = max(0, int(rng.gauss(consumption_seed + seasonal + weekend + (day_offset % 30) * 0.03, 1.6)))
            if quantity == 0:
                continue
            record = ConsumptionRecord(
                medicine_id=medicine.id,
                consumed_on=_days_ago(729 - day_offset),
                quantity=quantity,
                ward=wards[(medicine_index + day_offset) % len(wards)],
            )
            db.add(record)
            db.add(
                InventoryTransaction(
                    transaction_date=record.consumed_on,
                    medicine_id=medicine.id,
                    transaction_type="Issue",
                    quantity=quantity,
                    reference=f"ISS-{medicine.sku}-{day_offset:04d}",
                    department=record.ward,
                    note="Synthetic consumption history",
                )
            )

        db.add(
            InventoryTransaction(
                transaction_date=date.today() - timedelta(days=1),
                medicine_id=medicine.id,
                transaction_type="Purchase",
                quantity=medicine.ideal_stock,
                reference=f"PO-{medicine.sku}",
                department=None,
                note="Replenishment entry",
            )
        )

    if db.query(AuditLog).count() == 0:
        db.add(
            AuditLog(
                actor_username=settings.demo_admin_username,
                action="seed_demo_data",
                entity_name="system",
                entity_id=0,
                description="Seeded hospital pharmacy reference data and history",
            )
        )

    db.query(Medicine).filter(Medicine.pharmacy_id.is_(None)).update({Medicine.pharmacy_id: pharmacy.id}, synchronize_session=False)
    db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id.is_(None)).update({PurchaseOrder.pharmacy_id: pharmacy.id}, synchronize_session=False)
    db.commit()
