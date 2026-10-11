from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
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
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now)

    def to_dict(self):
        from app.schemes.normalizer import get_canonical_scheme_id
        effective_scheme_id = self.scheme_id or get_canonical_scheme_id(
            self.scheme_name, self.hindi_name, self.official_source_url
        )
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
            "authority": self.authority,
            "guidelines_summary": self.guidelines_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def init_db():
    Base.metadata.create_all(engine)
    # Ensure scheme_id column exists if table was previously created without it
    try:
        inspector = inspect(engine)
        if "schemes" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("schemes")]
            if "scheme_id" not in columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE schemes ADD COLUMN scheme_id VARCHAR"))
                    conn.commit()

        # Backfill scheme_id for any existing records where it is unset
        from app.schemes.normalizer import get_canonical_scheme_id
        with SessionLocal() as db:
            unassigned = db.query(Scheme).filter(
                (Scheme.scheme_id == None) | (Scheme.scheme_id == "")  # noqa: E711
            ).all()
            if unassigned:
                for s in unassigned:
                    s.scheme_id = get_canonical_scheme_id(s.scheme_name, s.hindi_name, s.official_source_url)
                db.commit()
    except Exception:
        pass

