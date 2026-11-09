import os
import re
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from app.database import create_circular, get_all_circulars
from app.rag_service import rag_service

logger = logging.getLogger("circular_parser")

def extract_text_from_file(file_path: Path) -> str:
    """Extracts text from PDF or text/markdown file."""
    suffix = file_path.suffix.lower()

    if suffix in (".txt", ".md", ".csv"):
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception:
            return file_path.read_text(encoding="latin-1", errors="ignore")

    elif suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages_text = []
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    pages_text.append(txt)
            return "\n\n".join(pages_text)
        except Exception as e:
            logger.warning(f"pypdf extraction error for {file_path.name}: {e}")
            return ""

    return ""

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Splits text into coherent overlapping chunks suitable for embeddings."""
    # Split by paragraphs or double newlines first
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) < chunk_size:
            current_chunk += ("\n" if current_chunk else "") + p
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = p

    if current_chunk:
        chunks.append(current_chunk)

    # Fallback to sentence/length window if single paragraph was too long
    refined_chunks = []
    for c in chunks:
        if len(c) > chunk_size * 1.5:
            words = c.split()
            for i in range(0, len(words), chunk_size - overlap):
                sub = " ".join(words[i:i + chunk_size])
                if sub:
                    refined_chunks.append(sub)
        else:
            refined_chunks.append(c)

    return refined_chunks if refined_chunks else [text]

def ingest_circular(title: str, content: str, circular_no: str = "", category: str = "General",
                    issue_date: str = "", file_name: str = "", uploaded_by: str = "Student Volunteer") -> int:
    """Creates a circular record, chunks it, and indexes into RAG."""
    chunks = chunk_text(content)
    summary = chunks[0][:200] + "..." if chunks else title

    circ_id = create_circular(
        title=title,
        content=content,
        circular_no=circular_no,
        category=category,
        issue_date=issue_date,
        summary=summary,
        file_name=file_name,
        uploaded_by=uploaded_by
    )

    metadata = {
        "title": title,
        "circular_no": circular_no,
        "category": category,
        "issue_date": issue_date
    }

    rag_service.index_circular_chunks(circ_id, chunks, metadata)
    logger.info(f"Ingested circular #{circ_id}: '{title}' with {len(chunks)} chunks.")
    return circ_id

def seed_sample_circulars_if_empty():
    """Seeds RGUKT college circulars matching the hackathon problem statement."""
    existing = get_all_circulars()
    if existing:
        return

    sample_circulars = [
        # --- Campus & University (RGUKTN) ---
        {
            "domain": "campus",
            "title": "Semester Examination Fee & Registration Notification - Fall 2025",
            "circular_no": "RGUKTN/ACAD/2025/EXAM-04",
            "category": "Examinations",
            "issue_date": "15/09/2025",
            "content": """RAJIV GANDHI UNIVERSITY OF KNOWLEDGE TECHNOLOGIES (RGUKT)
ACADEMIC EXAMINATION SECTION - CIRCULAR

Sub: Payment of Semester Examination Fee for B.Tech & PUC Students for Academic Year 2025-26.

1. All students of PUC-I, PUC-II, and B.Tech (E1, E2, E3, E4) are hereby informed that the online examination registration portal is open.
2. The last date to pay the semester examination fee without late penalty is 30/09/2025 (30th September 2025).
3. Late submission with a fine of Rs. 500/- is allowed up to 05/10/2025.
4. Regular examination fee is Rs. 1200/- per semester. Backlog examination fee is Rs. 350/- per subject.
5. Mode of Payment: Students must pay via the official SBI Collect / Campus Intranet Portal under 'RGUKT Examination Fee'. Cash or personal UPI transfers are strictly prohibited.
6. Hall tickets will be released on 10/10/2025 for all eligible candidates with minimum 75% attendance.

Issued by: Controller of Examinations, RGUKT Nuzvid."""
        },
        {
            "domain": "campus",
            "title": "Academic Calendar & Semester Schedule 2025-2026",
            "circular_no": "RGUKTN/ACAD/2025/CAL-01",
            "category": "Academics",
            "issue_date": "01/08/2025",
            "content": """ACADEMIC CALENDAR FOR ACADEMIC YEAR 2025-26
Rajiv Gandhi University of Knowledge Technologies, Andhra Pradesh.

- Commencement of Class Work: 18th August 2025
- Mid-Term 1 Examinations: 20th October to 25th October 2025
- Dussehra Vacation: 28th October to 04th November 2025
- Mid-Term 2 Examinations: 15th December to 20th December 2025
- Last Day of Instruction: 24th December 2025
- Semester End Practical Examinations: 27th December to 03rd January 2026
- Semester End Theory Examinations: 05th January to 20th January 2026
- Time table for Mid-terms and End-terms will be published 2 weeks prior on the campus student portal notice board."""
        },
        {
            "domain": "campus",
            "title": "Jagananna Vidya Deevena (JVD) & Merit Scholarship Verification",
            "circular_no": "RGUKTN/SCHOLAR/2025/08",
            "category": "Scholarships",
            "issue_date": "10/09/2025",
            "content": """SCHOLARSHIP SECTION NOTICE
Sub: Biometric Authentication and Documentation for JVD & National Scholarship Portal (NSP).

1. All eligible B.Tech students who have applied for Jagananna Vidya Deevena (JVD) and Vasathi Deevena are required to complete biometric authentication at the Academic Block Help Desk.
2. The last date for document verification and e-KYC submission is 25/09/2025.
3. Mandatory Documents: Income Certificate (valid for current financial year), Integrated Caste Certificate, Ration Card/Rice Card, and Student Aadhaar-linked Bank Passbook.
4. For National Scholarship Portal (NSP) applicants, bonafide certificates can be collected from Room A-204 between 2:00 PM and 5:00 PM on working days."""
        },
        {
            "domain": "campus",
            "title": "Hostel Regulations & Campus Dining Mess Timings",
            "circular_no": "RGUKTN/HOSTEL/2025/02",
            "category": "Hostel",
            "issue_date": "20/08/2025",
            "content": """CAMPUS HOSTEL & STUDENT WELFARE OFFICE

1. Mess Timings:
   - Breakfast: 07:00 AM to 08:30 AM
   - Lunch: 12:30 PM to 02:00 PM
   - Snacks: 05:00 PM to 06:00 PM
   - Dinner: 07:30 PM to 09:00 PM
2. Gate Curfew: All hostel inmates must report to their respective dormitories/blocks before 09:30 PM. Out-pass is mandatory for leaving campus.
3. Mess Rebate: Students traveling home for more than 5 consecutive days on authorized leave can apply for mess rebate via the student hostel portal at least 24 hours prior to departure."""
        },
        # --- Government Schemes Sector (Slide 5) ---
        {
            "domain": "government",
            "title": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) & State Welfare Portal",
            "circular_no": "GOV/AGRI/2025/PMK-01",
            "category": "Welfare Schemes",
            "issue_date": "01/09/2025",
            "content": """MINISTRY OF AGRICULTURE & FARMERS WELFARE
Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) Guidelines:

1. Financial benefit: Rs. 6,000/- per year is transferred directly into Aadhaar-seeded bank accounts in three equal installments of Rs. 2,000/- every 4 months.
2. Mandatory e-KYC: Beneficiary farmers must complete OTP-based e-KYC on the PM-KISAN portal or biometric e-KYC at CSC centers by 30/10/2025.
3. Required Documents: Landholding documents (RoR/Patta passbook), Aadhaar card, and Active bank account details linked to Aadhaar."""
        },
        # --- Health Sector (Slide 5) ---
        {
            "domain": "health",
            "title": "Primary Health Centre (PHC) & Ayushman Bharat Clinic Guidelines",
            "circular_no": "HEALTH/CLINIC/2025/03",
            "category": "Public Health",
            "issue_date": "12/09/2025",
            "content": """COMMUNITY HEALTHCARE & AYUSHMAN BHARAT WELLNESS CENTRE

1. Clinic & Outpatient (OPD) Timings:
   - General OPD: Monday to Saturday, 08:00 AM to 01:00 PM and 04:00 PM to 06:00 PM.
   - Emergency & Ambulance Services: Available 24/7 (Helpline: 108).
2. Immunization & Child Vaccination: Every Wednesday from 09:00 AM to 12:30 PM.
3. Free Medicines & Diagnostic Tests: Essential blood tests, glucose monitoring, and BP checks are completely free under Ayushman Arogya Mandir.
4. Non-severe Symptoms: For cold, mild fever, or body aches, consult the community health officer for paracetamol and oral hydration."""
        }
    ]

    for item in sample_circulars:
        ingest_circular(
            title=item["title"],
            content=item["content"],
            circular_no=item["circular_no"],
            category=item["category"],
            issue_date=item["issue_date"],
            file_name="sample_notice.txt",
            uploaded_by="System Initializer"
        )
    logger.info("Sample circulars seeded successfully.")

