"""Script to clean, update, and re-index Maharashtra MPSIMS BDS data (dated 20-Oct-2026).

Executes:
1. Reads data/raw/mpsims_raw_20_oct_2026.csv.
2. Deduplicates & parses 104 unique schemes (General, SCCS, TCS).
3. Standardizes numeric formatting (converting Indian comma separated amounts to floats).
4. Generates updated CSV: data/raw/maharashtra_agriculture_schemes_2026_2027.csv.
5. Generates updated JSON: data/raw/maharashtra_agriculture_schemes_2026_2027.json.
6. Regenerates compendium text: data/raw/maharashtra_agriculture_active_schemes_2026_2027.txt.
7. Updates SQLite Document and Scheme database records.
8. Re-indexes the updated compendium in ChromaDB vectorstore.
"""
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fix stdout encoding for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.db import Document as DbDocument, Scheme, SessionLocal, init_db
from app.rag.loader import load_file
from app.rag.retriever import get_store, index_documents
from app.schemes.normalizer import get_canonical_scheme_id
from app.schemes.pipeline import normalize_text


def parse_indian_number(val: str) -> float:
    if not val:
        return 0.0
    val_clean = str(val).strip().replace(",", "")
    try:
        return round(float(val_clean), 2)
    except ValueError:
        return 0.0


def format_indian_lakh(val: float) -> str:
    """Format a float into standard Indian lakh presentation."""
    return f"{val:,.2f}"


def main():
    raw_csv_path = ROOT_DIR / "data" / "raw" / "mpsims_raw_20_oct_2026.csv"
    if not raw_csv_path.exists():
        print(f"Error: {raw_csv_path} does not exist.")
        sys.exit(1)

    print(f"Reading raw MPSIMS scraped CSV: {raw_csv_path}")

    schemes_by_sr = {}
    with open(raw_csv_path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                sr = int(row.get("sr_no", 0))
            except (ValueError, TypeError):
                continue

            if sr <= 0 or sr > 104:
                continue

            # Keep first valid occurrence for each sr_no
            if sr not in schemes_by_sr:
                schemes_by_sr[sr] = {
                    "sr_no": sr,
                    "plan_type": row.get("plan_type", "General").strip(),
                    "scheme_code": row.get("phone", "").strip(),
                    "scheme_title": row.get("scheme_title", "").strip(),
                    "outlay_2024_25_lakh": parse_indian_number(row.get("2024_-_25_outlay", "0")),
                    "actual_exp_2024_25_lakh": parse_indian_number(row.get("2024_-_25_actual_expenditure", "0")),
                    "outlay_2025_26_lakh": parse_indian_number(row.get("2025_-_26_outlay", "0")),
                    "anticipated_exp_2025_26_lakh": parse_indian_number(row.get("2025_-_26_anticipated_expenditure", "0")),
                    "demand_outlay_2026_27_lakh": parse_indian_number(row.get("2026_-_27_demand_outlay", "0")),
                    "proposed_outlay_2026_27_lakh": parse_indian_number(row.get("2026_-_27_proposed_outlay", "0")),
                    "outlay_for_budgeting_2026_27_lakh": parse_indian_number(row.get("2026_-_27_outlay_for_budgeting", "0")),
                    "bds_budget_till_20_oct_26_lakh": parse_indian_number(row.get("bds_budget_(till_20-oct-26)", "0")),
                    "s1_till_20_oct_26_lakh": parse_indian_number(row.get("s1_(till_20-oct-26)_(bds)", "0")),
                    "s2_till_20_oct_26_lakh": parse_indian_number(row.get("s2_(till_20-oct-26)_(bds)", "0")),
                    "s3_till_20_oct_26_lakh": parse_indian_number(row.get("s3_(till_20-oct-26)_(bds)", "0")),
                    "final_budget_till_20_oct_26_lakh": parse_indian_number(row.get("final_budget_(till_20-oct-26)_(bds)", "0")),
                    "bds_release_by_fd_till_20_oct_26_lakh": parse_indian_number(row.get("bds_release_by_fd_(till_20-oct-26)", "0")),
                    "bds_expenditure_till_20_oct_26_lakh": parse_indian_number(row.get("bds_expenditure_(till_20-oct-26)", "0")),
                    "sdg_status": row.get("sdg_status", "A").strip(),
                }

    sorted_schemes = [schemes_by_sr[k] for k in sorted(schemes_by_sr.keys())]
    print(f"Successfully parsed and deduplicated {len(sorted_schemes)} schemes.")

    # Calculate overall budget aggregates
    tot_demand = sum(s["demand_outlay_2026_27_lakh"] for s in sorted_schemes)
    tot_proposed = sum(s["proposed_outlay_2026_27_lakh"] for s in sorted_schemes)
    tot_budgeting = sum(s["outlay_for_budgeting_2026_27_lakh"] for s in sorted_schemes)
    tot_final_bds = sum(s["final_budget_till_20_oct_26_lakh"] for s in sorted_schemes)
    tot_release = sum(s["bds_release_by_fd_till_20_oct_26_lakh"] for s in sorted_schemes)
    tot_exp = sum(s["bds_expenditure_till_20_oct_26_lakh"] for s in sorted_schemes)
    exp_pct = (tot_exp / tot_release * 100.0) if tot_release > 0 else 0.0

    general_count = sum(1 for s in sorted_schemes if s["plan_type"] == "General")
    sccs_count = sum(1 for s in sorted_schemes if s["plan_type"] == "SCCS")
    tcs_count = sum(1 for s in sorted_schemes if s["plan_type"] == "TCS")

    print("\n--- Budget Aggregate Summary (Till 20-Oct-2026) ---")
    print(f"Total Active Schemes: {len(sorted_schemes)} (General: {general_count}, SCCS: {sccs_count}, TCS: {tcs_count})")
    print(f"2026-27 Demand Outlay: Rs. {tot_demand:,.2f} Lakh (~Rs. {tot_demand/100:,.2f} Crore)")
    print(f"2026-27 Proposed Outlay: Rs. {tot_proposed:,.2f} Lakh (~Rs. {tot_proposed/100:,.2f} Crore)")
    print(f"Final BDS Budget (Till 20-Oct-26): Rs. {tot_final_bds:,.2f} Lakh (~Rs. {tot_final_bds/100:,.2f} Crore)")
    print(f"BDS Funds Released by FD: Rs. {tot_release:,.2f} Lakh (~Rs. {tot_release/100:,.2f} Crore)")
    print(f"BDS Actual Expenditure: Rs. {tot_exp:,.2f} Lakh (~Rs. {tot_exp/100:,.2f} Crore) ({exp_pct:.2f}% of release)")

    # 1. Save standardized CSV
    out_csv_path = ROOT_DIR / "data" / "raw" / "maharashtra_agriculture_schemes_2026_2027.csv"
    fieldnames = [
        "sr_no",
        "plan_type",
        "scheme_code",
        "scheme_title",
        "outlay_2024_25_lakh",
        "actual_exp_2024_25_lakh",
        "outlay_2025_26_lakh",
        "anticipated_exp_2025_26_lakh",
        "demand_outlay_2026_27_lakh",
        "proposed_outlay_2026_27_lakh",
        "outlay_for_budgeting_2026_27_lakh",
        "bds_budget_till_20_oct_26_lakh",
        "s1_till_20_oct_26_lakh",
        "s2_till_20_oct_26_lakh",
        "s3_till_20_oct_26_lakh",
        "final_budget_till_20_oct_26_lakh",
        "bds_release_by_fd_till_20_oct_26_lakh",
        "bds_expenditure_till_20_oct_26_lakh",
        "sdg_status",
    ]
    with open(out_csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_schemes)
    print(f"Saved standardized CSV: {out_csv_path}")

    # 2. Save JSON
    out_json_path = ROOT_DIR / "data" / "raw" / "maharashtra_agriculture_schemes_2026_2027.json"
    with open(out_json_path, mode="w", encoding="utf-8") as f:
        json.dump(sorted_schemes, f, indent=2, ensure_ascii=False)
    print(f"Saved standardized JSON: {out_json_path}")

    # 3. Generate updated compendium text
    txt_lines = [
        "# Official Compendium: Active Schemes & Outlay Allocations (2026-2027)",
        "Authority: Department of Agriculture, Government of Maharashtra",
        "Source URL: https://krishi.maharashtra.gov.in / Budget Distribution System (BDS)",
        "Document Type: Official Budgetary Statement & Active Schemes Directory",
        "Publication Date: 2026-10-20",
        "Updated Date: 2026-10-20",
        "Version: 2026-27.2",
        "",
        "## Executive Budgetary Overview",
        "- Department: Agriculture, Government of Maharashtra",
        f"- Total Active Schemes: {len(sorted_schemes)} (General: {general_count}, SCCS: {sccs_count}, TCS: {tcs_count})",
        f"- 2026-27 Total Demand Outlay: Rs. {tot_demand:,.2f} Lakh (~Rs. {tot_demand/100:,.2f} Crore)",
        f"- 2026-27 Proposed Outlay: Rs. {tot_proposed:,.2f} Lakh (~Rs. {tot_proposed/100:,.2f} Crore)",
        f"- 2026-27 Outlay for Budgeting: Rs. {tot_budgeting:,.2f} Lakh",
        f"- Final BDS Budget (Till 20-Oct-26): Rs. {tot_final_bds:,.2f} Lakh (~Rs. {tot_final_bds/100:,.2f} Crore)",
        f"- BDS Funds Released by Finance Dept: Rs. {tot_release:,.2f} Lakh (~Rs. {tot_release/100:,.2f} Crore)",
        f"- BDS Actual Expenditure: Rs. {tot_exp:,.2f} Lakh (~Rs. {tot_exp/100:,.2f} Crore, {exp_pct:.2f}% of released funds)",
        "",
        "## Key Strategic Allocations & Flagship Programs",
        "1. **Namo Shetakari Mahasanmaan Nidhi Yojana (100% State Scheme)**:",
        "   - Total 2026-27 Proposed Outlay: Rs. 6,06,000.00 Lakh (General: Rs. 4,78,740.00 Lakh | SCCS: Rs. 69,690.00 Lakh | TCS: Rs. 57,570.00 Lakh). Top priority direct farmer income assistance scheme matching PM-KISAN.",
        "2. **Krushi Samrudhi Yojana**:",
        "   - 2026-27 Proposed Outlay: Rs. 2,00,000.00 Lakh (Demand was Rs. 5,00,000.00 Lakh). Rs. 60,000 Lakh released and utilized as of Oct 2026.",
        "3. **Project on Climate Resilient Agriculture (POCRA Phase-II)**:",
        "   - Scheme Code: 1101010317 | Proposed Outlay: Rs. 44,200.00 Lakh | Final BDS: Rs. 47,400.00 Lakh | Expenditure: Rs. 37,358.60 Lakh.",
        "4. **SMART (State of Maharashtra Agri-business and Rural Transformation Program)**:",
        "   - Scheme Code: 1101010299 | Proposed Outlay: Rs. 40,000.00 Lakh | Release: Rs. 13,949.00 Lakh | Expenditure: Rs. 13,949.00 Lakh.",
        "5. **Agricultural Mechanization Sub Mission & State Mechanization Scheme**:",
        "   - SMAM (1101010022): Proposed Rs. 32,000.00 Lakh | Release: Rs. 34,361.67 Lakh | Expenditure: Rs. 31,809.26 Lakh; State Mechanization (1101010296): Proposed Rs. 2,000.00 Lakh.",
        "6. **PMKSY - Per Drop More Crop (Micro Irrigation)**:",
        "   - General (1101010276): Proposed Rs. 30,545.00 Lakh | Final BDS: Rs. 37,609.93 Lakh | Release: Rs. 32,857.34 Lakh | Expenditure: Rs. 32,584.14 Lakh.",
        "7. **Maharashtra Agriculture Artificial Intelligence Policy 2025-2029**:",
        "   - Scheme Code: 1101100034 | Proposed Outlay: Rs. 10,000.00 Lakh (~Rs. 100 Crore) | BDS Release: Rs. 2,489.84 Lakh | Expenditure: Rs. 383.70 Lakh.",
        "8. **Digital Public Infrastructure & Early Warning (AgriStack & WINDS)**:",
        "   - AgriStack: General (1101010316) Rs. 4,277.50 L, SCCS Rs. 250.00 L, TCS Rs. 405.00 L.",
        "   - WINDS (Weather Information Network Data System): Central (1101010326) and State (1101010327).",
        "9. **State Agricultural Universities (Grants-in-Aid & ICAR Schemes)**:",
        "   - Mahatma Phule Krishi Vidyapeeth (MPKV), Dr. Punjabrao Deshmukh Krishi Vidyapeeth (PDKV), Vasantrao Naik Marathwada Krishi Vidyapeeth (VNMKV), Dr. Balasaheb Sawant Konkan Krishi Vidyapeeth (BSKKV), and new Agriculture College at Sonapur, Gadchiroli (TCS).",
        "",
        "## Complete Directory of All 104 Active Schemes",
        "",
    ]

    current_plan = ""
    for s in sorted_schemes:
        if s["plan_type"] != current_plan:
            current_plan = s["plan_type"]
            txt_lines.append(f"### Plan Type: {current_plan}")

        txt_lines.append(f"#### [{s['sr_no']}] {s['scheme_title']}")
        txt_lines.append(f"- Scheme Code: {s['scheme_code']} | Plan: {s['plan_type']} | SDG Status: {s['sdg_status']}")
        txt_lines.append(f"- 2024-25 Outlay: Rs. {s['outlay_2024_25_lakh']:,.2f} Lakh | Actual Exp: Rs. {s['actual_exp_2024_25_lakh']:,.2f} Lakh")
        txt_lines.append(f"- 2025-26 Outlay: Rs. {s['outlay_2025_26_lakh']:,.2f} Lakh | Anticipated Exp: Rs. {s['anticipated_exp_2025_26_lakh']:,.2f} Lakh")
        txt_lines.append(f"- 2026-27 Demand Outlay: Rs. {s['demand_outlay_2026_27_lakh']:,.2f} Lakh | Proposed Outlay: Rs. {s['proposed_outlay_2026_27_lakh']:,.2f} Lakh | Outlay for Budgeting: Rs. {s['outlay_for_budgeting_2026_27_lakh']:,.2f} Lakh")
        txt_lines.append(f"- BDS Final Budget (Till 20-Oct-26): Rs. {s['final_budget_till_20_oct_26_lakh']:,.2f} Lakh | FD Release: Rs. {s['bds_release_by_fd_till_20_oct_26_lakh']:,.2f} Lakh | BDS Exp: Rs. {s['bds_expenditure_till_20_oct_26_lakh']:,.2f} Lakh")

    out_txt_path = ROOT_DIR / "data" / "raw" / "maharashtra_agriculture_active_schemes_2026_2027.txt"
    with open(out_txt_path, mode="w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines) + "\n")
    print(f"Updated compendium text file: {out_txt_path}")

    # 4. Update Database records in research.db
    init_db()
    with SessionLocal() as db:
        # Update or create Document
        doc_title = "Maharashtra Active Agricultural Schemes & Budget Outlay Compendium (2026-2027)"
        doc = db.query(DbDocument).filter(DbDocument.title == doc_title).first()
        if not doc:
            doc = DbDocument(
                title=doc_title,
                authority="Department of Agriculture, Government of Maharashtra",
                source_url="https://krishi.maharashtra.gov.in/bds",
                document_type="txt",
                publication_date="2026-10-20",
                updated_date="2026-10-20",
                version="2026-27.2",
                file_path="data/raw/maharashtra_agriculture_active_schemes_2026_2027.txt",
                indexed=False,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            print(f"Created new Document record #{doc.id}")
        else:
            doc.publication_date = "2026-10-20"
            doc.updated_date = "2026-10-20"
            doc.version = "2026-27.2"
            doc.indexed = False
            db.commit()
            print(f"Updated existing Document record #{doc.id}")

        # Update structured Scheme records for key flagship schemes with fresh 20-Oct-2026 budget metrics
        flagship_updates = {
            "NAMO-SHETAKARI": (
                "Namo Shetakari Mahasanmaan Nidhi Yojana (100% State Scheme)",
                "नमो शेतकरी महासन्मान निधी योजना",
                "Direct financial assistance of ₹6,000 per year paid in 3 installments of ₹2,000 each, supplementary to PM-KISAN (total ₹12,000/yr). 2026-27 Proposed Outlay: ₹6,06,000.00 Lakh (General ₹4,78,740.00 L, SCCS ₹69,690.00 L, TCS ₹57,570.00 L). BDS Budget till 20-Oct-2026: ₹4,78,740.00 Lakh.",
            ),
            "POCRA-II": (
                "Project on Climate Resilient Agriculture (Phase-II)",
                "हवामान अनुकूल कृषी प्रकल्प (फेज-२)",
                "Climate adaptation, micro-irrigation, and farmer community resilience in 21 districts of Vidarbha and Marathwada. Scheme Code: 1101010317. 2026-27 Proposed Outlay: ₹44,200.00 Lakh. Final BDS Budget till 20-Oct-2026: ₹47,400.00 Lakh. FD Released: ₹47,378.57 Lakh. BDS Expenditure: ₹37,358.60 Lakh.",
            ),
            "SMART": (
                "State of Maharashtra Agri-business and Rural Transformation Program",
                "स्मार्ट प्रकल्प (कृषी व्यवसाय व ग्रामीण परिवर्तन)",
                "Empowering Farmer Producer Companies (FPCs) and value chain infrastructure. Scheme Code: 1101010299. 2026-27 Proposed Outlay: ₹40,000.00 Lakh. Final BDS Budget: ₹40,000.00 Lakh. FD Released: ₹13,949.00 Lakh. BDS Expenditure: ₹13,949.00 Lakh.",
            ),
            "SMAM": (
                "Agricultural Mechanisation Sub Mission",
                "कृषी यांत्रिकीकरण उप अभियान",
                "Subsidies up to 50% for tractors, power tillers, harvesters, and custom hiring centers. Scheme Code: 1101010022. 2026-27 Proposed Outlay: ₹32,000.00 Lakh. Final BDS Budget: ₹40,225.00 Lakh. FD Released: ₹34,361.67 Lakh. BDS Expenditure till 20-Oct-2026: ₹31,809.26 Lakh.",
            ),
            "PDMC": (
                "Pradhan Mantri Krishi Sinchayee Yojna (PDMC) - Micro Irrigation",
                "पंतप्रधान कृषी सिंचन योजना (प्रति थेंब अधिक पीक)",
                "Drip and sprinkler irrigation subsidies for water conservation. Scheme Code: 1101010276. 2026-27 Proposed Outlay: ₹30,545.00 Lakh. Final BDS Budget: ₹37,609.93 Lakh. FD Released: ₹32,857.34 Lakh. BDS Expenditure till 20-Oct-2026: ₹32,584.14 Lakh.",
            ),
            "AGRI-AI-POLICY": (
                "Maharashtra Agriculture Artificial Intelligence Policy 2025-2029",
                "महाराष्ट्र कृषी कृत्रिम बुद्धिमत्ता (AI) धोरण २०२५-२०२९",
                "Deployment of generative AI, satellite imagery, yield forecasting, and computerized advisories. Scheme Code: 1101100034. 2026-27 Proposed Outlay: ₹10,000.00 Lakh (~₹100 Crore). Final BDS Budget: ₹10,000.00 Lakh. FD Released: ₹2,489.84 Lakh. BDS Expenditure: ₹383.70 Lakh.",
            ),
        }

        for sid, (sname, hname, bdesc) in flagship_updates.items():
            existing_s = db.query(Scheme).filter(
                (Scheme.scheme_id == sid) | (Scheme.scheme_name.ilike(f"%{sname[:20]}%"))
            ).first()
            if existing_s:
                existing_s.benefits = normalize_text(bdesc)
                existing_s.updated_at = datetime.now(timezone.utc)
                print(f"Updated flagship Scheme record [{existing_s.scheme_id}]: {existing_s.scheme_name}")
            else:
                new_s = Scheme(
                    scheme_id=sid,
                    scheme_name=normalize_text(sname),
                    hindi_name=normalize_text(hname),
                    category="Agriculture, Farming & Rural Development",
                    beneficiary="Farmers and agrarian producers in Maharashtra",
                    eligibility="Registered farmers, FPCs, and landholders in Maharashtra with verified 7/12 extract.",
                    benefits=normalize_text(bdesc),
                    documents="Aadhaar Card, 7/12 land extract, 8-A land record, Bank passbook, Mobile number.",
                    state_district="Maharashtra",
                    status="Active",
                    official_source_url="https://krishi.maharashtra.gov.in/bds",
                    authority="Department of Agriculture, Government of Maharashtra",
                    guidelines_summary=normalize_text(f"{sname} under Maharashtra BDS Budget 2026-27.\n{bdesc}"),
                )
                db.add(new_s)
                print(f"Added new flagship Scheme record: [{sid}] {sname}")
        db.commit()

        # 5. Re-index in ChromaDB vectorstore
        print("\nLoading compendium text into vector embeddings...")
        meta = {
            "title": doc.title,
            "authority": doc.authority,
            "source_url": doc.source_url,
            "document_type": doc.document_type,
            "publication_date": doc.publication_date,
            "updated_date": doc.updated_date,
            "version": doc.version,
        }
        pages = load_file(str(out_txt_path), meta)
        indexed_count = index_documents(pages, force=True)
        doc.content_hash = pages[0].metadata.get("content_hash", "") if pages else ""
        doc.indexed = True
        db.commit()
        print(f"Successfully indexed {indexed_count} chunks into ChromaDB.")

    print("\n✓ Maharashtra BDS 20-Oct-2026 Ingestion and Vectorstore Re-indexing Completed Successfully!")


if __name__ == "__main__":
    main()
