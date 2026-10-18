"""
Synthetic Data Generator & Initial Seeder for Legal & Investigation Vault.

Creates standard Administrator and Investigator accounts, realistic legal cases,
physical evidence files with cryptographic SHA-256 seals, and initial audit logs.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.orm import Session

from legal_system.app.config import settings
from legal_system.app.database import SessionLocal, init_db
from legal_system.app.models import User, Case, EvidenceDocument, AuditLog
from legal_system.app.auth import hash_password
from legal_system.app.hashing import compute_sha256


def seed_legal_data():
    """Run full legal data seeding."""
    print("⚖️  Initializing Legal & Investigation Evidence Vault Database...")
    init_db()

    db: Session = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("✓ Database already seeded. Skipping initial seeding.")
            return

        print("Creating core personnel accounts...")
        # 1. Personnel (Admin & Investigators)
        h_admin, s_admin = hash_password("admin123")
        admin_user = User(
            username="admin",
            full_name="Chief Elena Vance",
            badge_number="ADM-001",
            role="administrator",
            password_hash=h_admin,
            password_salt=s_admin,
            is_active=True,
        )

        h_inv1, s_inv1 = hash_password("investigator123")
        inv1 = User(
            username="mcole",
            full_name="Detective Marcus Cole",
            badge_number="INV-401",
            role="investigator",
            password_hash=h_inv1,
            password_salt=s_inv1,
            is_active=True,
        )

        h_inv2, s_inv2 = hash_password("investigator123")
        inv2 = User(
            username="schen",
            full_name="Dr. Sarah Chen (Cyber Forensics)",
            badge_number="INV-508",
            role="investigator",
            password_hash=h_inv2,
            password_salt=s_inv2,
            is_active=True,
        )

        db.add_all([admin_user, inv1, inv2])
        db.commit()
        db.refresh(admin_user)
        db.refresh(inv1)
        db.refresh(inv2)

        print("Creating investigation cases...")
        # 2. Cases
        case1 = Case(
            case_number="CASE-2026-1042",
            title="Operation Silverline: Cross-Border Wire Fraud",
            description="Multi-jurisdictional shell companies funnelling illicit offshore transfers through decentralized exchanges.",
            category="Financial Fraud",
            status="Under Investigation",
            priority="Critical",
            lead_investigator_id=inv1.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=14),
        )

        case2 = Case(
            case_number="CASE-2026-1089",
            title="Apex BioTech Intellectual Property Extortion",
            description="Exfiltration of clinical genomics database following insider credential compromise and ransomware deployment.",
            category="Cybercrime",
            status="Open",
            priority="Critical",
            lead_investigator_id=inv2.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )

        case3 = Case(
            case_number="CASE-2026-2155",
            title="State v. Sterling Port Syndicate",
            description="Narcotics and illicit freight shipping manifests impounded at Terminal 4 cargo customs check.",
            category="Narcotics",
            status="In Court",
            priority="High",
            lead_investigator_id=inv1.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )

        case4 = Case(
            case_number="CASE-2026-0914",
            title="Municipal Transit Procurement Kickbacks",
            description="Falsified infrastructure subcontracts and undisclosed conflict-of-interest payments to city officials.",
            category="Public Corruption",
            status="Closed",
            priority="Medium",
            lead_investigator_id=inv1.id,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )

        db.add_all([case1, case2, case3, case4])
        db.commit()
        db.refresh(case1)
        db.refresh(case2)
        db.refresh(case3)
        db.refresh(case4)

        print("Generating secured evidence files with SHA-256 seals...")
        # 3. Evidence Files
        evidence_samples = [
            {
                "case": case1,
                "title": "Trauma Admission & EMS Field Telemetry (Run #994-AZ)",
                "description": "Authenticated paramedic field transmission telemetry showing vital sign deterioration during highway multi-trauma transport.",
                "category": "Medical Forensic Record",
                "filename": "trauma_ems_telemetry_batch_994az.pdf",
                "content": b"%PDF-1.4 [SECURED EXHIBIT: Trauma Admission & EMS Telemetry #994-AZ - Authenticated by Emergency Medicine Forensic Seal]",
                "uploader": inv1,
            },
            {
                "case": case1,
                "title": "Falsified Shell Entity Incorporation Articles",
                "description": "Forged notary certification and nominee director filings seized under search warrant W-4902.",
                "category": "Forensic Report",
                "filename": "shell_corp_incorporation_notary_forgery.pdf",
                "content": b"%PDF-1.4 [EVIDENCE RECORD: Articles of Incorporation - Notarized Signatures Identified as Fraudulent by Handwriting Analysis]",
                "uploader": inv1,
            },
            {
                "case": case2,
                "title": "C2 Server Memory Dump & Exploit Artifact",
                "description": "Volatile RAM capture of compromised domain controller containing injected Beacon payload strings.",
                "category": "Cyber Forensics",
                "filename": "volatility_ram_dump_dc01_exfiltration.raw",
                "content": b"[FORENSIC RAW MEMORY DUMP: DC01.CORP - Process ID: 4192 - CobaltStrike Beacon Detected - Hash Validated]",
                "uploader": inv2,
            },
            {
                "case": case2,
                "title": "Ransomware Threat Actor PGP Negotiation Log",
                "description": "Cryptographically signed correspondence on darkweb portal demanding 45 BTC ransom payment.",
                "category": "Witness Deposition",
                "filename": "threat_actor_pgp_negotiation_transcripts.txt",
                "content": b"-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\nWe possess 4.2TB of Apex BioTech clinical trials. Contact key 0x9F41E...\n-----END PGP SIGNED MESSAGE-----",
                "uploader": inv2,
            },
            {
                "case": case3,
                "title": "Terminal 4 Cargo Bay 12 Manifest Inspection",
                "description": "Impounded bill of lading mismatched against container contents; sealed under customs seal #99214.",
                "category": "Physical Evidence",
                "filename": "bill_of_lading_container_99214_inspected.pdf",
                "content": b"%PDF-1.4 [CUSTOMS IMPERIAL INSPECTION RECORD: Container #99214 - Discrepancy confirmed 450kg]",
                "uploader": inv1,
            },
        ]

        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        for item in evidence_samples:
            content = item["content"]
            sha256 = compute_sha256(content)
            stored_name = f"CASE_{item['case'].case_number}_{item['filename']}"
            stored_path = upload_dir / stored_name

            with open(stored_path, "wb") as f:
                f.write(content)

            # Keep canonical backup for tamper demonstration
            backup_path = upload_dir / f"{stored_name}.canonical_bak"
            with open(backup_path, "wb") as f:
                f.write(content)

            doc = EvidenceDocument(
                case_id=item["case"].id,
                title=item["title"],
                description=item["description"],
                category=item["category"],
                original_filename=item["filename"],
                stored_filename=stored_name,
                file_size_bytes=len(content),
                mime_type="application/pdf" if item["filename"].endswith(".pdf") else "text/plain",
                sha256_hash=sha256,
                original_sha256_hash=sha256,
                uploaded_by_id=item["uploader"].id,
                is_tampered=False,
                created_at=datetime.now(timezone.utc) - timedelta(days=3),
            )
            db.add(doc)

            # Audit entry
            log = AuditLog(
                timestamp=datetime.now(timezone.utc) - timedelta(days=3),
                user_id=item["uploader"].id,
                username=item["uploader"].username,
                user_role=item["uploader"].role,
                action="UPLOAD_EVIDENCE",
                resource_type="Evidence",
                resource_id=item["case"].case_number,
                details=f"Exhibit '{item['title']}' ingested into evidence vault. SHA-256 seal computed and permanently recorded.",
                sha256_snapshot=sha256,
                ip_address="192.168.1.104",
            )
            db.add(log)

        # Add initial administrative audit events
        admin_logs = [
            AuditLog(
                timestamp=datetime.now(timezone.utc) - timedelta(days=14),
                user_id=admin_user.id,
                username=admin_user.username,
                user_role=admin_user.role,
                action="SYSTEM_INIT",
                resource_type="System",
                details="Legal Vault cryptographic registry initialized. FIPS-compliant SHA-256 verification enabled.",
                ip_address="127.0.0.1",
            ),
            AuditLog(
                timestamp=datetime.now(timezone.utc) - timedelta(days=1),
                user_id=inv1.id,
                username=inv1.username,
                user_role=inv1.role,
                action="VERIFY_HASH_VALID",
                resource_type="Evidence",
                resource_id="CASE-2026-1042",
                details="Routine chain-of-custody verification: Trauma Admission & EMS Field Telemetry hash verified against canonical ledger.",
                sha256_snapshot="d5b78c93...",
                ip_address="192.168.1.104",
            ),
        ]
        db.add_all(admin_logs)

        db.commit()
        print("✅ Legal System initialized successfully with 3 users, 4 cases, and secured evidence files.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error during legal data seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_legal_data()
