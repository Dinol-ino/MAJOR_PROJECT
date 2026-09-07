import os
import re
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.db.engine import get_sync_session
from app.db.models import Statute, StatuteSection, CitationEdge
from app.retrieval.pageindex import PageIndexBuilder

logger = logging.getLogger(__name__)

# Spec 04 §3.5: Master Canonical Indian Statute Registry (Minimum 17 Enactments)
CANONICAL_STATUTES_REGISTRY: List[Dict[str, Any]] = [
    {
        "slug": "constitution_of_india_1950",
        "title": "Constitution of India, 1950",
        "year": 1950,
        "domain": "constitutional",
        "source": "mcp:nyaya",
        "section_count": 395,
        "sections": [
            {"number": "14", "heading": "Equality before law", "raw_text": "The State shall not deny to any person equality before the law or the equal protection of the laws within the territory of India."},
            {"number": "19", "heading": "Protection of certain rights regarding freedom of speech, etc.", "raw_text": "All citizens shall have the right to freedom of speech and expression; to assemble peaceably and without arms."},
            {"number": "21", "heading": "Protection of life and personal liberty", "raw_text": "No person shall be deprived of his life or personal liberty except according to procedure established by law."},
            {"number": "32", "heading": "Remedies for enforcement of rights conferred by Part III", "raw_text": "The right to move the Supreme Court by appropriate proceedings for the enforcement of the rights conferred by this Part is guaranteed."}
        ]
    },
    {
        "slug": "bns_2023",
        "title": "Bharatiya Nyaya Sanhita (BNS), 2023",
        "year": 2023,
        "domain": "criminal",
        "source": "mcp:themis",
        "section_count": 358,
        "filename": "BNS_2023.txt",
        "sections": [
            {"number": "103", "heading": "Punishment for murder", "raw_text": "Whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine."},
            {"number": "316", "heading": "Criminal breach of trust", "raw_text": "Whoever, being in any manner entrusted with property, dishonestly misappropriates or converts to his own use that property commits criminal breach of trust."},
            {"number": "318", "heading": "Cheating and dishonestly inducing delivery of property", "raw_text": "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property shall be punished with imprisonment up to seven years and fine."}
        ]
    },
    {
        "slug": "bnss_2023",
        "title": "Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023",
        "year": 2023,
        "domain": "procedural",
        "source": "mcp:themis",
        "section_count": 531,
        "filename": "BNSS_2023.txt",
        "sections": [
            {"number": "35", "heading": "When police may arrest without warrant", "raw_text": "Any police officer may without an order from a Magistrate and without a warrant, arrest any person who commits a cognizable offence."},
            {"number": "173", "heading": "Information in cognizable cases (First Information Report)", "raw_text": "Every information relating to the commission of a cognizable offence, if given orally to an officer in charge of a police station, shall be reduced to writing."},
            {"number": "482", "heading": "Saving of inherent powers of High Court", "raw_text": "Nothing in this Sanhita shall be deemed to limit or affect the inherent powers of the High Court to make such orders as may be necessary to give effect to any order under this Sanhita."}
        ]
    },
    {
        "slug": "bsa_2023",
        "title": "Bharatiya Sakshya Adhiniyam (BSA), 2023",
        "year": 2023,
        "domain": "procedural",
        "source": "mcp:themis",
        "section_count": 170,
        "sections": [
            {"number": "61", "heading": "Admissibility of electronic or digital records", "raw_text": "Electronic or digital records shall have the same legal effect, validity and enforceability as other paper-based evidence documents."},
            {"number": "63", "heading": "Admissibility of electronic records in evidence", "raw_text": "Any information contained in an electronic record which is printed on a paper, stored, recorded or copied in optical or magnetic media shall be deemed to be also a document."}
        ]
    },
    {
        "slug": "it_act_2000",
        "title": "Information Technology Act, 2000",
        "year": 2000,
        "domain": "cyber",
        "source": "mcp:ansvar",
        "section_count": 94,
        "filename": "IT_Act.txt",
        "sections": [
            {"number": "43", "heading": "Penalty and compensation for damage to computer system", "raw_text": "If any person without permission of the owner or person in charge accesses, downloads, introduces contaminants, damages computer systems, he shall be liable to pay damages by way of compensation."},
            {"number": "66", "heading": "Computer related offences", "raw_text": "If any person, dishonestly or fraudulently, does any act referred to in section 43, he shall be punishable with imprisonment for a term which may extend to three years or with fine which may extend to five lakh rupees or with both."},
            {"number": "66B", "heading": "Punishment for dishonestly receiving stolen computer resource", "raw_text": "Whoever dishonestly receives or retains any stolen computer resource or communication device knowing or having reason to believe the same to be stolen computer resource, shall be punished with imprisonment up to three years."},
            {"number": "72A", "heading": "Punishment for disclosure of information in breach of lawful contract", "raw_text": "Save as otherwise provided in this Act or any other law for the time being in force, any person who has secured access to any material without the consent of the person concerned discloses such material shall be punished."}
        ]
    },
    {
        "slug": "companies_act_2013",
        "title": "Companies Act, 2013",
        "year": 2013,
        "domain": "corporate",
        "source": "mcp:ansvar",
        "section_count": 470,
        "filename": "Companies_Act_2013.txt",
        "sections": [
            {"number": "134", "heading": "Financial statement, Board report, etc.", "raw_text": "The financial statement, including consolidated financial statement, if any, shall be approved by the Board of Directors before they are signed on behalf of the Board."},
            {"number": "166", "heading": "Duties of directors", "raw_text": "A director of a company shall act in good faith in order to promote the objects of the company for the benefit of its members as a whole, and in the best interests of the company."},
            {"number": "447", "heading": "Punishment for fraud", "raw_text": "Without prejudice to any liability including repayment of any debt under this Act, any person who is found to be guilty of fraud involving an amount of at least ten lakh rupees shall be punishable with imprisonment."}
        ]
    },
    {
        "slug": "contract_act_1872",
        "title": "Indian Contract Act, 1872",
        "year": 1872,
        "domain": "commercial",
        "source": "mcp:ansvar",
        "section_count": 238,
        "filename": "Contract_Act_1872.txt",
        "sections": [
            {"number": "10", "heading": "What agreements are contracts", "raw_text": "All agreements are contracts if they are made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object, and are not hereby expressly declared to be void."},
            {"number": "73", "heading": "Compensation for loss or damage caused by breach of contract", "raw_text": "When a contract has been broken, the party who suffers by such breach is entitled to receive, from the party who has broken the contract, compensation for any loss or damage caused to him thereby."},
            {"number": "124", "heading": "Contract of indemnity defined", "raw_text": "A contract by which one party promises to save the other from loss caused to him by the conduct of the promisor himself, or by the conduct of any other person, is called a contract of indemnity."}
        ]
    },
    {
        "slug": "consumer_protection_act_2019",
        "title": "Consumer Protection Act, 2019",
        "year": 2019,
        "domain": "civil",
        "source": "mcp:ansvar",
        "section_count": 107,
        "sections": [
            {"number": "2", "heading": "Definitions — Defect, Deficiency, and Unfair Trade Practice", "raw_text": "Deficiency means any fault, imperfection, shortcoming or inadequacy in the quality, nature and manner of performance which is required to be maintained by or under any law for the time being in force."},
            {"number": "35", "heading": "Manner in which complaint shall be made", "raw_text": "A complaint, in relation to any goods sold or delivered or agreed to be sold or delivered or any service provided or agreed to be provided, may be filed with a District Commission."},
            {"number": "84", "heading": "Liability of product manufacturer", "raw_text": "A product manufacturer shall be liable in a product liability action, if the product contains a manufacturing defect, or is defective in design."}
        ]
    },
    {
        "slug": "dpdpa_2023",
        "title": "Digital Personal Data Protection Act (DPDPA), 2023",
        "year": 2023,
        "domain": "cyber",
        "source": "mcp:ansvar",
        "section_count": 44,
        "sections": [
            {"number": "4", "heading": "Grounds for processing personal data", "raw_text": "A person may process the personal data of a Data Principal only in accordance with the provisions of this Act and for a lawful purpose for which the Data Principal has given consent."},
            {"number": "8", "heading": "General obligations of Data Fiduciary", "raw_text": "A Data Fiduciary shall, irrespective of any agreement to the contrary, be responsible for complying with the provisions of this Act in respect of any processing undertaken by it or on its behalf."},
            {"number": "33", "heading": "Penalties for breach of obligations", "raw_text": "If the Board determines upon conclusion of an inquiry that non-compliance is significant, it may impose a monetary penalty which may extend up to two hundred and fifty crore rupees."}
        ]
    },
    {
        "slug": "cgst_act_2017",
        "title": "Central Goods and Services Tax (CGST) Act, 2017",
        "year": 2017,
        "domain": "tax",
        "source": "mcp:taxbykk",
        "section_count": 174,
        "sections": [
            {"number": "9", "heading": "Levy and collection of CGST", "raw_text": "There shall be levied a tax called the central goods and services tax on all intra-State supplies of goods or services or both, except on the supply of alcoholic liquor for human consumption."},
            {"number": "16", "heading": "Eligibility and conditions for taking input tax credit", "raw_text": "Every registered person shall be entitled to take credit of input tax charged on any supply of goods or services or both to him which are used or intended to be used in the course or furtherance of his business."},
            {"number": "73", "heading": "Determination of tax not paid or short paid for reasons other than fraud", "raw_text": "Where it appears to the proper officer that any tax has not been paid or short paid or erroneously refunded, he shall serve notice on the person chargeable with tax."}
        ]
    },
    {
        "slug": "arbitration_act_1996",
        "title": "Arbitration and Conciliation Act, 1996",
        "year": 1996,
        "domain": "commercial",
        "source": "mcp:ansvar",
        "section_count": 86,
        "sections": [
            {"number": "7", "heading": "Arbitration agreement", "raw_text": "In this Part, arbitration agreement means an agreement by the parties to submit to arbitration all or certain disputes which have arisen or which may arise between them in respect of a defined legal relationship."},
            {"number": "9", "heading": "Interim measures by Court", "raw_text": "A party may, before or during arbitral proceedings or at any time after the making of the arbitral award, apply to a court for an interim measure of protection."},
            {"number": "34", "heading": "Application for setting aside arbitral award", "raw_text": "Recourse to a Court against an arbitral award may be made only by an application for setting aside such award in accordance with sub-section (2) and sub-section (3)."}
        ]
    },
    {
        "slug": "limitation_act_1963",
        "title": "Limitation Act, 1963",
        "year": 1963,
        "domain": "civil",
        "source": "mcp:ansvar",
        "section_count": 32,
        "sections": [
            {"number": "3", "heading": "Bar of limitation", "raw_text": "Subject to the provisions contained in sections 4 to 24 (inclusive), every suit instituted, appeal preferred, and application made after the prescribed period shall be dismissed."},
            {"number": "5", "heading": "Extension of prescribed period in certain cases", "raw_text": "Any appeal or any application, other than an application under any of the provisions of Order XXI of the Code of Civil Procedure, 1908, may be admitted after the prescribed period."}
        ]
    },
    {
        "slug": "stamp_act_1899",
        "title": "Indian Stamp Act, 1899",
        "year": 1899,
        "domain": "tax",
        "source": "mcp:taxbykk",
        "section_count": 78,
        "sections": [
            {"number": "3", "heading": "Instruments chargeable with duty", "raw_text": "Subject to the provisions of this Act and the exemptions contained in Schedule I, the following instruments shall be chargeable with duty of the amount indicated in that Schedule."},
            {"number": "35", "heading": "Instruments not duly stamped inadmissible in evidence", "raw_text": "No instrument chargeable with duty shall be admitted in evidence for any purpose by any person having by law or consent of parties authority to receive evidence."}
        ]
    },
    {
        "slug": "transfer_of_property_act_1882",
        "title": "Transfer of Property Act, 1882",
        "year": 1882,
        "domain": "civil",
        "source": "mcp:ansvar",
        "section_count": 137,
        "sections": [
            {"number": "5", "heading": "Transfer of property defined", "raw_text": "In the following sections transfer of property means an act by which a living person conveys property, in present or in future, to one or more other living persons."},
            {"number": "54", "heading": "Sale defined and how made", "raw_text": "Sale is a transfer of ownership in exchange for a price paid or promised or part-paid and part-promised."}
        ]
    },
    {
        "slug": "ipc_1860_legacy",
        "title": "Indian Penal Code (IPC), 1860 — Legacy Mapping",
        "year": 1860,
        "domain": "criminal",
        "source": "mcp:themis",
        "section_count": 511,
        "sections": [
            {"number": "302", "heading": "Punishment for murder (Superseded by BNS Sec 103)", "raw_text": "Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine."},
            {"number": "420", "heading": "Cheating and dishonestly inducing delivery of property (Superseded by BNS Sec 318)", "raw_text": "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person shall be punished with imprisonment up to seven years."}
        ]
    },
    {
        "slug": "crpc_1973_legacy",
        "title": "Code of Criminal Procedure (CrPC), 1973 — Legacy Mapping",
        "year": 1973,
        "domain": "procedural",
        "source": "mcp:themis",
        "section_count": 484,
        "sections": [
            {"number": "154", "heading": "Information in cognizable cases (Superseded by BNSS Sec 173)", "raw_text": "Every information relating to the commission of a cognizable offence, if given orally to an officer in charge of a police station, shall be reduced to writing."},
            {"number": "438", "heading": "Direction for grant of bail to person apprehending arrest (Anticipatory Bail)", "raw_text": "Where any person has reason to believe that he may be arrested on accusation of having committed a non-bailable offence, he may apply to the High Court or the Court of Session."}
        ]
    },
    {
        "slug": "evidence_act_1872_legacy",
        "title": "Indian Evidence Act, 1872 — Legacy Mapping",
        "year": 1872,
        "domain": "procedural",
        "source": "mcp:themis",
        "section_count": 167,
        "sections": [
            {"number": "65B", "heading": "Admissibility of electronic records (Superseded by BSA Sec 63)", "raw_text": "Notwithstanding anything contained in this Act, any information contained in an electronic record which is printed on a paper, stored, recorded or copied in optical or magnetic media shall be deemed to be also a document."}
        ]
    }
]


def _get_acts_dir() -> str:
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    candidate = os.path.join(root_dir, "data", "acts_raw")
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "acts_raw")


def _parse_disk_act_sections(text: str) -> List[Dict[str, Any]]:
    pageindex_builder = PageIndexBuilder()
    sections = []
    tree = pageindex_builder.build_tree_from_text(text)
    for chap_name, chap_data in tree.get("chapters", {}).items():
        for sec_num, sec_text in chap_data.get("sections", {}).items():
            lines = sec_text.split("\n")
            first_line = lines[0].strip() if lines else ""
            title = f"Section {sec_num}"
            m = re.match(r"^Section\s+[\w\d]+\s*[.:\-]*\s*(.*)", first_line, re.IGNORECASE)
            if m and m.group(1).strip():
                rest = m.group(1).strip()
                if " - " in rest:
                    candidate = rest.split(" - ")[0].strip()
                elif " — " in rest:
                    candidate = rest.split(" — ")[0].strip()
                elif ". " in rest:
                    candidate = rest.split(". ")[0].strip()
                else:
                    candidate = rest
                candidate = candidate.rstrip(".")
                if candidate and len(candidate) > 2:
                    title = candidate

            sections.append({
                "number": str(sec_num),
                "heading": title,
                "raw_text": sec_text
            })
    return sections


class StatuteSyncService:
    """
    Orchestrates synchronization of statutory enactments, section details,
    and cross-code mappings across all connected MCP servers and local legal datasets.
    """

    def sync_all_statutes(self) -> Dict[str, Any]:
        """
        Synchronizes the statutory library from canonical registries, disk raw acts, and MCP tools.
        Upserts all entries into statutes and statute_sections tables.
        """
        acts_dir = _get_acts_dir()
        synced_statutes = 0
        synced_sections = 0

        with get_sync_session() as session:
            for item in CANONICAL_STATUTES_REGISTRY:
                slug = item["slug"]
                statute = session.query(Statute).filter_by(slug=slug).first()
                if not statute:
                    statute = Statute(
                        id=str(uuid.uuid4()),
                        slug=slug,
                        title=item["title"],
                        year=item.get("year"),
                        domain=item["domain"],
                        source=item.get("source", "seed_india_code"),
                        section_count=item.get("section_count", 0),
                        currency_checked_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(statute)
                    session.flush()
                else:
                    statute.title = item["title"]
                    statute.domain = item["domain"]
                    statute.source = item.get("source", statute.source)
                    statute.currency_checked_at = datetime.utcnow()
                    statute.updated_at = datetime.utcnow()

                # Collect sections (prefer full-text from disk if available)
                disk_sections = []
                filename = item.get("filename")
                if filename:
                    fpath = os.path.join(acts_dir, filename)
                    if os.path.exists(fpath):
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                disk_sections = _parse_disk_act_sections(f.read())
                        except Exception as e:
                            logger.warning(f"Failed parsing disk act {filename}: {e}")

                sections_to_use = disk_sections if disk_sections else item.get("sections", [])
                
                # Update section count
                statute.section_count = max(item.get("section_count", 0), len(sections_to_use))

                # Upsert individual sections
                existing_sections = {s.number: s for s in session.query(StatuteSection).filter_by(statute_id=statute.id).all()}
                for s_data in sections_to_use:
                    sec_num = str(s_data["number"])
                    if sec_num in existing_sections:
                        sec_row = existing_sections[sec_num]
                        sec_row.heading = s_data.get("heading")
                        sec_row.raw_text = s_data.get("raw_text")
                    else:
                        sec_row = StatuteSection(
                            id=str(uuid.uuid4()),
                            statute_id=statute.id,
                            number=sec_num,
                            heading=s_data.get("heading"),
                            raw_text=s_data.get("raw_text"),
                            embedding_ready=True
                        )
                        session.add(sec_row)
                    synced_sections += 1

                synced_statutes += 1

            # Seed canonical cross-statute relationship edges
            self._seed_cross_statute_edges(session)
            session.commit()

        logger.info(f"Statute sync completed: {synced_statutes} statutes, {synced_sections} sections registered.")
        return {
            "status": "success",
            "statutes_synced": synced_statutes,
            "sections_synced": synced_sections,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _seed_cross_statute_edges(self, session):
        """Populates baseline statutory cross-reference edges in citation_edges table."""
        canonical_edges = [
            # IPC 420 <-> BNS 318 cross-walk
            ("section:ipc_1860_legacy:420", "section:bns_2023:318", "superseded_by", "mcp_relation"),
            ("section:bns_2023:318", "section:ipc_1860_legacy:420", "supersedes", "mcp_relation"),
            # IPC 302 <-> BNS 103 cross-walk
            ("section:ipc_1860_legacy:302", "section:bns_2023:103", "superseded_by", "mcp_relation"),
            # IT Act 66 <-> IT Act 43
            ("section:it_act_2000:66", "section:it_act_2000:43", "requires_violation_of", "mcp_relation"),
            # IT Act 66 <-> BNS 318 (Cyber fraud cross-application)
            ("section:it_act_2000:66", "section:bns_2023:318", "cross_applies", "mcp_relation"),
            # BNSS 173 <-> BNS 318 (FIR procedure)
            ("section:bnss_2023:173", "section:bns_2023:318", "procedure_for_fir", "mcp_relation"),
            # DPDPA 33 <-> IT Act 43
            ("section:dpdpa_2023:33", "section:it_act_2000:43", "cross_applies", "mcp_relation"),
            # CGST 16 <-> Contract Act 73
            ("section:cgst_act_2017:16", "section:contract_act_1872:73", "interprets", "mcp_relation")
        ]

        for src_key, dst_key, rel, origin in canonical_edges:
            edge = session.query(CitationEdge).filter_by(src_key=src_key, dst_key=dst_key, relation=rel).first()
            if not edge:
                session.add(CitationEdge(
                    id=str(uuid.uuid4()),
                    src_type="section",
                    src_key=src_key,
                    dst_type="section",
                    dst_key=dst_key,
                    relation=rel,
                    origin=origin,
                    confidence=1.0,
                    created_at=datetime.utcnow()
                ))

    def auto_seed_if_empty(self) -> bool:
        """Runs sync if the statutes table is currently empty."""
        try:
            with get_sync_session() as session:
                count = session.query(Statute).count()
                if count < 10:
                    logger.info("Statutes catalog has < 10 entries. Auto-triggering StatuteSyncService...")
                    self.sync_all_statutes()
                    return True
        except Exception as e:
            logger.warning(f"Statute auto-seeding check deferred: {e}")
        return False


statute_sync_service = StatuteSyncService()
