from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

_db_url = DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False} if _db_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def _now():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    source_url = Column(String, default="")
    authority = Column(String, default="unknown")
    document_type = Column(String, default="")
    publication_date = Column(String, default="")
    updated_date = Column(String, default="")
    version = Column(String, default="")
    file_path = Column(String, nullable=False)
    content_hash = Column(String, default="")
    indexed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)


class ResearchHistory(Base):
    __tablename__ = "research_history"
    id = Column(Integer, primary_key=True)
    user_query = Column(Text, nullable=False)
    answer = Column(Text, default="")
    sources = Column(JSON, default=list)
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=_now)


SECTION_GROUP_MAP = {
    "women_child": "Women & Child Development (Sections 1-11)",
    "central_farmer": "Central Agriculture & Farmer Welfare",
    "maharashtra_agri": "Maharashtra Agriculture Budget (2026-2027)",
    "agri_budget_bds": "Maharashtra Agriculture Budget (2026-2027)",
    "education_scholarship": "Education & Scholarships",
    "credit_enterprise": "Credit & Entrepreneurship",
    "healthcare_housing": "Healthcare & Social Protection",
}


def get_section_group_id(group_name: str) -> str:
    name_l = (group_name or "").lower()
    if "women" in name_l or "child" in name_l:
        return "women_child"
    if "central" in name_l and ("agri" in name_l or "farmer" in name_l):
        return "central_farmer"
    if "maharashtra" in name_l or "bds" in name_l:
        return "maharashtra_agri"
    if "education" in name_l or "scholarship" in name_l:
        return "education_scholarship"
    if "credit" in name_l or "enterprise" in name_l or "entrepreneur" in name_l:
        return "credit_enterprise"
    if "health" in name_l or "housing" in name_l or "protection" in name_l:
        return "healthcare_housing"
    return "general"


class Scheme(Base):
    """Structured Government Scheme Record (PostgreSQL/SQL relational storage).
    
    Fields defined in the pipeline architecture:
    - Scheme name
    - Hindi name
    - Category
    - Beneficiary
    - Eligibility
    - Benefits
    - Documents
    - State/District
    - Status
    """
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(String, nullable=True, index=True)              # Stable unique scheme identifier (e.g. PM-KISAN, MH-WOM-01)
    scheme_name = Column(String, nullable=False, index=True)          # Scheme name
    hindi_name = Column(String, nullable=False, index=True)           # Hindi name
    category = Column(String, nullable=False, index=True)             # Category
    beneficiary = Column(Text, nullable=False)                        # Beneficiary
    eligibility = Column(Text, nullable=False)                        # Eligibility
    benefits = Column(Text, nullable=False)                           # Benefits
    documents = Column(Text, nullable=False)                          # Documents
    state_district = Column(String, nullable=False, index=True)       # State/District
    status = Column(String, nullable=False, default="Active", index=True)  # Status

    # Official citation & metadata
    official_source_url = Column(String, default="")
    authority = Column(String, default="")
    guidelines_summary = Column(Text, default="")
    application_process = Column(Text, default="")
    dataset_section = Column(String, default="", index=True)
    section_group = Column(String, default="", index=True)

    # Automated Sync Pipeline & Change Detection fields
    content_hash = Column(String, default="", index=True)             # Deterministic SHA-256 hash of core scheme content
    department = Column(String, default="")                           # Administering Ministry / Department
    level = Column(String, default="Central / State")                 # Central, State (e.g. State - Maharashtra)
    application_url = Column(String, default="")                      # Official online registration / application URL
    last_checked = Column(DateTime, nullable=True)                    # Timestamp when official source was last checked
    last_verified = Column(DateTime, nullable=True)                  # Timestamp when content was verified from official guidelines
    verification_status = Column(String, default="Verified", index=True)  # "Verified", "Pending Review", "Unverified"
    is_discontinued = Column(Boolean, default=False, index=True)      # True if officially discontinued / sunset

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now)

    def to_dict(self):
        from app.schemes.normalizer import get_canonical_scheme_id
        effective_scheme_id = self.scheme_id or get_canonical_scheme_id(
            self.scheme_name, self.hindi_name, self.official_source_url
        )
        source_citations = []
        if self.official_source_url or self.authority:
            source_citations.append({
                "source": self.authority or self.scheme_name,
                "authority": self.authority or self.department or "Government Authority",
                "source_url": self.official_source_url or "",
                "document_type": "Official Scheme Portal / Guidelines",
            })

        sec_name = self.dataset_section
        sec_grp = self.section_group
        if not sec_name or not sec_grp:
            d_sec, d_grp = get_scheme_dataset_section_info(effective_scheme_id, self.scheme_name, self.category)
            sec_name = sec_name or d_sec
            sec_grp = sec_grp or d_grp

        sec_grp_id = get_section_group_id(sec_grp)

        return {
            "id": self.id,
            "scheme_id": effective_scheme_id,
            "scheme_name": self.scheme_name,
            "hindi_name": self.hindi_name,
            "category": self.category,
            "beneficiary": self.beneficiary,
            "eligibility": self.eligibility,
            "benefits": self.benefits,
            "documents": self.documents,
            "state_district": self.state_district,
            "status": self.status,
            "official_source_url": self.official_source_url,
            "authority": self.authority or self.department or "",
            "department": self.department or self.authority or "",
            "level": self.level or "Central / State",
            "application_url": self.application_url or self.official_source_url or "",
            "guidelines_summary": self.guidelines_summary,
            "application_process": self.application_process or "",
            "dataset_section": sec_name,
            "section_group": sec_grp,
            "section_group_id": sec_grp_id,
            "content_hash": self.content_hash or "",
            "last_checked": self.last_checked.isoformat() if self.last_checked else (self.updated_at.isoformat() if self.updated_at else None),
            "last_verified": self.last_verified.isoformat() if self.last_verified else (self.updated_at.isoformat() if self.updated_at else None),
            "verification_status": self.verification_status or "Verified",
            "is_discontinued": bool(self.is_discontinued),
            "source_citations": source_citations,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def get_scheme_dataset_section_info(scheme_id: str | None, scheme_name: str, category: str) -> tuple[str, str]:
    """Map any scheme to its exact official dataset section and compendium section group."""
    sid = (scheme_id or "").upper().strip()
    name_l = (scheme_name or "").lower()
    cat_l = (category or "").lower()

    # Maharashtra & Central Women and Child Development Welfare Schemes Compendium (Sections 1-11)
    wcd_sections = {
        "MH-WOM-01": ("Section 1: Mukhyamantri Majhi Ladki Bahin Yojana", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-02": ("Section 2: Lek Ladki Yojana", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-03": ("Section 3: Pradhan Mantri Matru Vandana Yojana (PMMVY)", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-04": ("Section 4: One Stop Centre (Sakhi Centre)", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-05": ("Section 5: Women Helpline (181)", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-06": ("Section 6: Nari Adalat", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-07": ("Section 7: Ujjawala Anti-Trafficking Scheme", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-08": ("Section 8: Shakti Sadan Integrated Shelter", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-09": ("Section 9: Hub for Empowerment of Women (HEW)", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-10": ("Section 10: Mahila Arthik Vikas Mahamandal (MAVIM)", "Women & Child Development (Sections 1-11)"),
        "MH-WOM-11": ("Section 11: Saksham Anganwadi & Poshan 2.0", "Women & Child Development (Sections 1-11)"),
    }
    if sid in wcd_sections:
        return wcd_sections[sid]

    # Central Agriculture & Farmer Welfare
    central_agri = {
        "PM-KISAN": ("Central Flagship: Direct Income Support", "Central Agriculture & Farmer Welfare"),
        "KCC": ("Central Flagship: Concessional Farm Credit & RuPay", "Central Agriculture & Farmer Welfare"),
        "PMFBY": ("Central Flagship: Comprehensive Crop Insurance", "Central Agriculture & Farmer Welfare"),
        "PM-KUSUM": ("Central Flagship: Standalone Solar Agri Pumps (Component B)", "Central Agriculture & Farmer Welfare"),
        "SMAM": ("Central Sub-Mission: Agricultural Mechanization", "Central Agriculture & Farmer Welfare"),
        "SOIL HEALTH": ("National Mission: Soil Health & Fertility Management", "Central Agriculture & Farmer Welfare"),
    }
    if sid in central_agri:
        return central_agri[sid]

    # Maharashtra Agriculture Budget BDS
    if sid in ("NAMO SHETAKARI", "NAMO-SHETAKARI") or "namo shetakari" in name_l:
        return ("BDS Flagship: Namo Shetakari Mahasanmaan Nidhi", "Maharashtra Agriculture Budget (2026-2027)")
    if sid in ("SHAASHWAT", "SHET-TALE") or "sustainable agriculture irrigation" in name_l:
        return ("BDS Sustainable Irrigation: Chief Minister Shettale Scheme", "Maharashtra Agriculture Budget (2026-2027)")

    if sid == "SCHOLARSHIP" or "scholarship" in name_l or "shikshan" in name_l or "education" in cat_l:
        return ("MahaDBT State Scholarship: Post-Matric & Higher Education", "Education & Scholarships")

    if sid == "MUDRA" or "mudra" in name_l or "credit" in cat_l or "entrepreneur" in cat_l:
        return ("MSME Credit: Pradhan Mantri Mudra Yojana (PMMY)", "Credit & Entrepreneurship")

    if sid in ("PM-JAY", "PMJAY") or "ayushman" in name_l or "health" in cat_l:
        return ("National Health Protection: Ayushman Bharat (PM-JAY)", "Healthcare & Social Protection")

    if sid in ("PMAY-G", "PMAY") or "awas" in name_l or "housing" in cat_l:
        return ("Rural Housing: Pradhan Mantri Awas Yojana - Gramin", "Rural Housing & Infrastructure")

    if "women" in cat_l or "child" in cat_l:
        return ("State Women & Child Welfare Scheme", "Women & Child Development (Sections 1-11)")

    if "agri" in cat_l or "farmer" in cat_l:
        return ("State Agriculture Scheme (BDS Active)", "Maharashtra Agriculture Budget (2026-2027)")

    return ("General Public Scheme", "General Public Schemes")



class SchemeHistory(Base):
    """Audit log tracking all changes, revisions, and status transitions for schemes."""
    __tablename__ = "scheme_history"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(String, nullable=False, index=True)
    change_type = Column(String, nullable=False)  # "CREATED", "UPDATED", "DISCONTINUED", "VERIFIED"
    previous_hash = Column(String, default="")
    new_hash = Column(String, default="")
    changed_fields = Column(JSON, default=list)
    snapshot = Column(JSON, default=dict)
    source_url = Column(String, default="")
    recorded_at = Column(DateTime, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "scheme_id": self.scheme_id,
            "change_type": self.change_type,
            "previous_hash": self.previous_hash,
            "new_hash": self.new_hash,
            "changed_fields": self.changed_fields or [],
            "snapshot": self.snapshot or {},
            "source_url": self.source_url or "",
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class SyncLog(Base):
    """Execution statistics, health status, and failure logs for source synchronizations."""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    sync_id = Column(String, nullable=False, index=True)
    source_name = Column(String, nullable=False)
    source_url = Column(String, default="")
    source_type = Column(String, default="")
    status = Column(String, default="RUNNING", index=True)  # "SUCCESS", "FAILED", "PARTIAL"
    schemes_discovered = Column(Integer, default=0)
    schemes_created = Column(Integer, default=0)
    schemes_updated = Column(Integer, default=0)
    schemes_discontinued = Column(Integer, default=0)
    schemes_unchanged = Column(Integer, default=0)
    error_message = Column(Text, default="")
    started_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "sync_id": self.sync_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "status": self.status,
            "schemes_discovered": self.schemes_discovered,
            "schemes_created": self.schemes_created,
            "schemes_updated": self.schemes_updated,
            "schemes_discontinued": self.schemes_discontinued,
            "schemes_unchanged": self.schemes_unchanged,
            "error_message": self.error_message or "",
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds or 0,
        }


def init_db():
    Base.metadata.create_all(engine)
    # Ensure scheme_id, application_process, dataset_section, section_group, and sync columns exist
    try:
        inspector = inspect(engine)
        if "schemes" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("schemes")]
            cols_to_add = [
                ("scheme_id", "VARCHAR"),
                ("application_process", "TEXT"),
                ("dataset_section", "VARCHAR DEFAULT ''"),
                ("section_group", "VARCHAR DEFAULT ''"),
                ("content_hash", "VARCHAR DEFAULT ''"),
                ("department", "VARCHAR DEFAULT ''"),
                ("level", "VARCHAR DEFAULT 'Central / State'"),
                ("application_url", "VARCHAR DEFAULT ''"),
                ("last_checked", "TIMESTAMP"),
                ("last_verified", "TIMESTAMP"),
                ("verification_status", "VARCHAR DEFAULT 'Verified'"),
                ("is_discontinued", "BOOLEAN DEFAULT FALSE"),
            ]
            with engine.connect() as conn:
                for col_name, col_type in cols_to_add:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE schemes ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                        except Exception:
                            pass

        # Backfill scheme_id, dataset_section, and section_group for records
        from app.schemes.normalizer import get_canonical_scheme_id
        with SessionLocal() as db:
            unassigned = db.query(Scheme).all()
            dirty = False
            for s in unassigned:
                if not s.scheme_id:
                    s.scheme_id = get_canonical_scheme_id(s.scheme_name, s.hindi_name, s.official_source_url)
                    dirty = True
                if not s.dataset_section or not s.section_group:
                    sec_name, sec_grp = get_scheme_dataset_section_info(s.scheme_id, s.scheme_name, s.category)
                    s.dataset_section = s.dataset_section or sec_name
                    s.section_group = s.section_group or sec_grp
                    dirty = True
                if not s.department and s.authority:
                    s.department = s.authority
                    dirty = True
                if not s.application_url and s.official_source_url:
                    s.application_url = s.official_source_url
                    dirty = True
                if not s.verification_status:
                    s.verification_status = "Verified"
                    dirty = True
            if dirty:
                db.commit()
    except Exception:
        pass

