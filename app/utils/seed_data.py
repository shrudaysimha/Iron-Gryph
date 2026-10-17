"""
Synthetic data generator for Hospital Surge AI.

Generates realistic hospital data including:
- Hospitals with wards and beds
- Staff with shift patterns
- Ambulance fleet
- 30 days of historical admissions with realistic patterns
- Resources and supplies

Usage:
    python -m app.utils.seed_data
"""

import random
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.hospital import Hospital, Ward, Bed
from app.models.patient import Patient, Admission
from app.models.staff import Staff
from app.models.ambulance import Ambulance
from app.models.resource import Resource
from app.models.alert import Alert


# ---- Constants ----

HOSPITAL_NAMES = [
    "City General Hospital",
    "Metro Emergency Medical Center",
    "District Public Hospital",
]

HOSPITAL_CONFIGS = [
    {"tier": "tertiary", "total_beds": 300, "icu": 40, "emergency": 30, "ventilator": 20},
    {"tier": "secondary", "total_beds": 150, "icu": 20, "emergency": 15, "ventilator": 10},
    {"tier": "primary", "total_beds": 80, "icu": 8, "emergency": 10, "ventilator": 5},
]

WARD_TEMPLATES = [
    {"name": "General Ward A", "type": "general", "floor": 1, "beds": 40},
    {"name": "General Ward B", "type": "general", "floor": 2, "beds": 35},
    {"name": "ICU", "type": "icu", "floor": 1, "beds": 20},
    {"name": "Emergency Department", "type": "emergency", "floor": 0, "beds": 15},
    {"name": "Surgical Ward", "type": "surgical", "floor": 3, "beds": 25},
    {"name": "Maternity Ward", "type": "maternity", "floor": 2, "beds": 15},
    {"name": "Pediatric Ward", "type": "pediatric", "floor": 2, "beds": 15},
    {"name": "Isolation Ward", "type": "isolation", "floor": 4, "beds": 10},
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Sai", "Arnav",
    "Dhruv", "Kabir", "Saanvi", "Ananya", "Aanya", "Aadhya", "Priya", "Ishita",
    "Neha", "Kavya", "Riya", "Meera", "Rahul", "Vikram", "Suresh", "Rajesh",
    "Amit", "Deepa", "Sunita", "Geeta", "Lakshmi", "Revathi",
]

LAST_NAMES = [
    "Sharma", "Patel", "Gupta", "Singh", "Kumar", "Reddy", "Nair", "Rao",
    "Iyer", "Menon", "Joshi", "Verma", "Desai", "Bhat", "Hegde",
]

CONDITIONS = [
    "Chest pain", "Breathing difficulty", "Road traffic accident", "Fracture",
    "Fever and body ache", "Abdominal pain", "Head injury", "Burns",
    "Cardiac arrest", "Stroke", "Diabetic emergency", "Seizures",
    "Allergic reaction", "Food poisoning", "Fall injury", "Snake bite",
    "Pregnancy complication", "Asthma attack", "Hypertension crisis",
    "Appendicitis", "Kidney stone", "Pneumonia", "Dengue fever",
    "COVID symptoms", "Heat stroke", "Electrocution",
]

DIAGNOSES = [
    "Acute myocardial infarction", "Pneumonia", "Fracture - femur",
    "Cerebrovascular accident", "Acute appendicitis", "Renal calculi",
    "Dengue hemorrhagic fever", "Diabetic ketoacidosis", "COPD exacerbation",
    "Acute gastroenteritis", "Sepsis", "Anaphylaxis", "Polytrauma",
    "Preeclampsia", "Status epilepticus", "Acute pancreatitis",
]

SPECIALIZATIONS = [
    "Emergency Medicine", "Internal Medicine", "Surgery", "Orthopedics",
    "Cardiology", "Neurology", "Pediatrics", "Obstetrics", "Anesthesiology",
    "Pulmonology", "Nephrology", "Gastroenterology",
]

BANGALORE_COORDS = (12.9716, 77.5946)


def _random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _random_phone() -> str:
    return f"+91{random.randint(7000000000, 9999999999)}"


def _random_coord(center: tuple, radius_km: float = 15) -> tuple:
    """Generate a random lat/lon near a center point."""
    lat_offset = random.uniform(-radius_km / 111, radius_km / 111)
    lon_offset = random.uniform(-radius_km / 111, radius_km / 111)
    return (center[0] + lat_offset, center[1] + lon_offset)


def seed_hospitals(db: Session) -> list[Hospital]:
    """Create hospitals."""
    hospitals = []
    for i, (name, config) in enumerate(zip(HOSPITAL_NAMES, HOSPITAL_CONFIGS)):
        lat, lon = _random_coord(BANGALORE_COORDS, radius_km=10)
        hospital = Hospital(
            name=name,
            address=f"{random.randint(1, 500)}, {random.choice(['MG Road', 'Brigade Road', 'Residency Road', 'Cunningham Road', 'Hosur Road'])}, Bangalore",
            city="Bangalore",
            state="Karnataka",
            latitude=lat,
            longitude=lon,
            phone=_random_phone(),
            total_beds=config["total_beds"],
            icu_beds=config["icu"],
            emergency_beds=config["emergency"],
            ventilator_beds=config["ventilator"],
            tier=config["tier"],
        )
        db.add(hospital)
        hospitals.append(hospital)

    db.flush()
    print(f"  ✓ Created {len(hospitals)} hospitals")
    return hospitals


def seed_wards_and_beds(db: Session, hospitals: list[Hospital]) -> None:
    """Create wards and beds for each hospital."""
    total_wards = 0
    total_beds = 0

    for hospital in hospitals:
        # Scale wards by hospital size
        scale = hospital.total_beds / 300  # Normalize to tertiary

        for template in WARD_TEMPLATES:
            bed_count = max(5, int(template["beds"] * scale))

            ward = Ward(
                hospital_id=hospital.id,
                name=template["name"],
                ward_type=template["type"],
                floor=template["floor"],
                total_beds=bed_count,
                available_beds=int(bed_count * random.uniform(0.2, 0.6)),  # 40-80% occupied
            )
            db.add(ward)
            db.flush()
            total_wards += 1

            # Create individual beds
            bed_type_map = {
                "icu": "icu",
                "isolation": "isolation",
                "maternity": "maternity",
            }
            bed_type = bed_type_map.get(template["type"], "general")

            for j in range(bed_count):
                # Some beds in ICU get ventilators
                actual_bed_type = bed_type
                if template["type"] == "icu" and j < bed_count * 0.4:
                    actual_bed_type = "ventilator"

                occupied = j >= ward.available_beds
                bed = Bed(
                    ward_id=ward.id,
                    bed_number=f"{template['name'][:3].upper()}-{j + 1:03d}",
                    bed_type=actual_bed_type,
                    status="occupied" if occupied else "available",
                    has_monitor=template["type"] in ("icu", "emergency"),
                    has_oxygen=template["type"] in ("icu", "emergency", "isolation"),
                )
                db.add(bed)
                total_beds += 1

    db.flush()
    print(f"  ✓ Created {total_wards} wards with {total_beds} beds")


def seed_staff(db: Session, hospitals: list[Hospital]) -> list[Staff]:
    """Create staff with realistic shift patterns."""
    all_staff = []
    emp_counter = 1000

    for hospital in hospitals:
        scale = hospital.total_beds / 300

        staff_configs = [
            ("doctor", int(30 * scale), SPECIALIZATIONS),
            ("nurse", int(60 * scale), [None]),
            ("paramedic", int(15 * scale), [None]),
            ("surgeon", int(8 * scale), ["General Surgery", "Orthopedic Surgery", "Neurosurgery", "Cardiac Surgery"]),
        ]

        for role, count, specializations in staff_configs:
            for _ in range(max(2, count)):
                shift = random.choice(["morning", "afternoon", "night", "off"])
                on_duty = shift != "off"

                now = datetime.now(timezone.utc)
                shift_start = None
                shift_end = None
                if on_duty:
                    shift_offsets = {"morning": 6, "afternoon": 14, "night": 22}
                    offset = shift_offsets.get(shift, 8)
                    shift_start = now.replace(hour=offset, minute=0)
                    shift_end = shift_start + timedelta(hours=8)

                staff = Staff(
                    hospital_id=hospital.id,
                    name=_random_name(),
                    employee_id=f"EMP-{emp_counter}",
                    role=role,
                    specialization=random.choice(specializations) if specializations[0] else None,
                    phone=_random_phone(),
                    current_shift=shift,
                    on_duty=on_duty,
                    shift_start=shift_start,
                    shift_end=shift_end,
                    is_available=on_duty and random.random() > 0.1,
                    max_patients={"doctor": 10, "nurse": 6, "paramedic": 5, "surgeon": 3}.get(role, 8),
                    current_patients=random.randint(0, 5) if on_duty else 0,
                )
                db.add(staff)
                all_staff.append(staff)
                emp_counter += 1

    db.flush()
    print(f"  ✓ Created {len(all_staff)} staff members")
    return all_staff


def seed_ambulances(db: Session, hospitals: list[Hospital]) -> None:
    """Create ambulance fleet for each hospital."""
    total = 0
    for hospital in hospitals:
        count = max(3, int(hospital.total_beds / 30))

        for i in range(count):
            lat, lon = _random_coord(
                (hospital.latitude or BANGALORE_COORDS[0], hospital.longitude or BANGALORE_COORDS[1]),
                radius_km=5,
            )
            status = random.choices(
                ["available", "dispatched", "en_route", "returning", "maintenance"],
                weights=[50, 15, 10, 10, 15],
            )[0]

            ambulance = Ambulance(
                hospital_id=hospital.id,
                vehicle_number=f"KA-{random.randint(1, 99):02d}-AM-{random.randint(1000, 9999)}",
                vehicle_type=random.choices(
                    ["basic", "advanced", "icu_mobile"],
                    weights=[50, 35, 15],
                )[0],
                status=status,
                current_lat=lat if status != "available" else hospital.latitude,
                current_lon=lon if status != "available" else hospital.longitude,
                driver_name=_random_name(),
                paramedic_name=_random_name(),
                eta_minutes=random.randint(5, 30) if status in ("dispatched", "en_route") else None,
            )
            db.add(ambulance)
            total += 1

    db.flush()
    print(f"  ✓ Created {total} ambulances")


def seed_historical_admissions(db: Session, hospitals: list[Hospital]) -> None:
    """
    Generate 30 days of realistic admission data with patterns:
    - Higher admissions on weekdays
    - Morning and evening peaks
    - Occasional surge events
    - Severity distribution matching real hospitals
    """
    now = datetime.now(timezone.utc)
    total_admissions = 0
    total_patients = 0

    for hospital in hospitals:
        daily_base = hospital.total_beds * 0.15  # ~15% of capacity daily

        for day_offset in range(30, 0, -1):
            day = now - timedelta(days=day_offset)

            # Weekend adjustment
            is_weekend = day.weekday() >= 5
            day_mult = 0.75 if is_weekend else 1.0

            # Random surge events (5% chance)
            is_surge = random.random() < 0.05
            surge_mult = random.uniform(1.8, 3.0) if is_surge else 1.0

            daily_count = int(daily_base * day_mult * surge_mult * random.uniform(0.8, 1.2))

            for _ in range(daily_count):
                # Time distribution — peaks at 9-11 AM and 5-8 PM
                hour_weights = [
                    0.02, 0.02, 0.01, 0.01, 0.02, 0.03,  # 0-5 AM
                    0.04, 0.06, 0.08, 0.10, 0.09, 0.07,   # 6-11 AM
                    0.06, 0.05, 0.05, 0.05, 0.06, 0.07,   # 12-5 PM
                    0.08, 0.07, 0.06, 0.04, 0.03, 0.02,   # 6-11 PM
                ]
                hour = random.choices(range(24), weights=hour_weights)[0]
                minute = random.randint(0, 59)
                admission_time = day.replace(hour=hour, minute=minute, second=0)

                # Severity distribution
                severity = random.choices(
                    ["mild", "moderate", "severe", "critical"],
                    weights=[30, 40, 20, 10],
                )[0]

                triage = {"mild": 5, "moderate": 3, "severe": 2, "critical": 1}[severity]

                arrival_mode = random.choices(
                    ["walk_in", "ambulance", "transfer"],
                    weights=[55, 35, 10],
                )[0]

                department = random.choices(
                    ["emergency", "general", "icu", "surgery", "maternity", "pediatric"],
                    weights=[35, 25, 10, 15, 8, 7],
                )[0]

                # Force ICU for critical patients
                if severity == "critical":
                    department = random.choice(["icu", "emergency"])

                # Create patient
                age = int(random.triangular(1, 90, 40))
                patient = Patient(
                    name=_random_name(),
                    age=age,
                    gender=random.choice(["male", "female"]),
                    blood_group=random.choice(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]),
                    phone=_random_phone(),
                    condition=random.choice(CONDITIONS),
                    triage_score=triage,
                    arrival_mode=arrival_mode,
                    arrival_time=admission_time,
                )
                db.add(patient)
                db.flush()
                total_patients += 1

                # Length of stay based on severity
                los_hours = {
                    "mild": random.uniform(2, 24),
                    "moderate": random.uniform(24, 96),
                    "severe": random.uniform(48, 168),
                    "critical": random.uniform(72, 336),
                }[severity]

                discharge_time = admission_time + timedelta(hours=los_hours)
                is_discharged = discharge_time < now

                admission = Admission(
                    patient_id=patient.id,
                    hospital_id=hospital.id,
                    department=department,
                    diagnosis=random.choice(DIAGNOSES),
                    severity=severity,
                    status="discharged" if is_discharged else random.choice(["admitted", "in_treatment", "observation"]),
                    admitted_at=admission_time,
                    discharged_at=discharge_time if is_discharged else None,
                    length_of_stay_hours=round(los_hours, 1) if is_discharged else None,
                )
                db.add(admission)
                total_admissions += 1

            # Commit every day to avoid memory issues
            if day_offset % 5 == 0:
                db.flush()

    db.flush()
    print(f"  ✓ Created {total_patients} patients with {total_admissions} admissions (30 days)")


def seed_resources(db: Session, hospitals: list[Hospital]) -> None:
    """Create medical resources and supplies."""
    resource_templates = [
        {"name": "Ventilators", "category": "equipment", "unit": "units", "qty": 20},
        {"name": "Oxygen Cylinders", "category": "oxygen", "unit": "cylinders", "qty": 100},
        {"name": "PPE Kits", "category": "ppe", "unit": "kits", "qty": 500},
        {"name": "Blood Units (O+)", "category": "blood_bank", "unit": "units", "qty": 50},
        {"name": "Blood Units (A+)", "category": "blood_bank", "unit": "units", "qty": 40},
        {"name": "Blood Units (B+)", "category": "blood_bank", "unit": "units", "qty": 35},
        {"name": "Surgical Masks", "category": "consumable", "unit": "pieces", "qty": 2000},
        {"name": "IV Drip Sets", "category": "consumable", "unit": "sets", "qty": 300},
        {"name": "Paracetamol 500mg", "category": "medicine", "unit": "strips", "qty": 1000},
        {"name": "Insulin Vials", "category": "medicine", "unit": "vials", "qty": 100},
        {"name": "Antibiotic (Amoxicillin)", "category": "medicine", "unit": "strips", "qty": 500},
        {"name": "Cardiac Monitors", "category": "equipment", "unit": "units", "qty": 15},
        {"name": "Defibrillators", "category": "equipment", "unit": "units", "qty": 5},
    ]

    total = 0
    for hospital in hospitals:
        scale = hospital.total_beds / 300
        for template in resource_templates:
            qty = max(5, int(template["qty"] * scale))
            available = int(qty * random.uniform(0.4, 0.9))
            resource = Resource(
                hospital_id=hospital.id,
                name=template["name"],
                category=template["category"],
                unit=template["unit"],
                total_quantity=qty,
                available_quantity=available,
                minimum_threshold=max(2, int(qty * 0.15)),
            )
            db.add(resource)
            total += 1

    db.flush()
    print(f"  ✓ Created {total} resource entries")


def seed_alerts(db: Session, hospitals: list[Hospital]) -> None:
    """Create some sample alerts."""
    sample_alerts = [
        {
            "alert_type": "bed_shortage",
            "severity": "warning",
            "title": "Bed Occupancy Approaching Capacity",
            "message": "General ward occupancy has reached 82%. Consider activating surge protocols.",
        },
        {
            "alert_type": "surge_predicted",
            "severity": "warning",
            "title": "Surge Predicted in Next 4 Hours",
            "message": "AI model predicts 35% increase in admissions in the next 4 hours due to local event.",
        },
        {
            "alert_type": "ambulance_shortage",
            "severity": "info",
            "title": "Ambulance Availability Low",
            "message": "Only 2 ambulances currently available. 3 are dispatched and 1 is returning.",
        },
    ]

    for hospital in hospitals[:1]:  # Only for the first hospital
        for alert_data in sample_alerts:
            alert = Alert(hospital_id=hospital.id, **alert_data)
            db.add(alert)

    db.flush()
    print(f"  ✓ Created {len(sample_alerts)} sample alerts")


def seed_all():
    """Run the complete seeding pipeline."""
    print("\n🏥 Hospital Surge AI — Seeding Database\n")
    print("=" * 50)

    # Create tables
    print("\n📦 Creating database tables...")
    init_db()
    print("  ✓ Tables created")

    db = SessionLocal()
    try:
        # Check if data already exists
        existing = db.query(Hospital).count()
        if existing > 0:
            print(f"\n⚠️  Database already has {existing} hospitals. Skipping seed.")
            print("   Drop and recreate the database to re-seed.")
            return

        print("\n🏗️  Generating synthetic data...\n")

        hospitals = seed_hospitals(db)
        seed_wards_and_beds(db, hospitals)
        seed_staff(db, hospitals)
        seed_ambulances(db, hospitals)
        seed_historical_admissions(db, hospitals)
        seed_resources(db, hospitals)
        seed_alerts(db, hospitals)

        db.commit()

        print("\n" + "=" * 50)
        print("✅ Database seeded successfully!")
        print(f"   Hospitals: {len(hospitals)}")
        print(f"   Historical data: 30 days")
        print("=" * 50 + "\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
