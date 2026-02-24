"""
BioLinker - VC Data Crawler
국내외 바이오 VC 데이터를 수집하는 모듈
Expanded with curated real Korean biotech VC ecosystem data
"""
import uuid
from typing import List, Optional
from models import VCFirm


class VCCrawler:
    """VC 데이터 크롤러 - 국내 바이오 VC 생태계 DB"""

    def fetch_vc_list(self) -> List[VCFirm]:
        """주요 바이오 VC 목록 반환 (Curated real-world data)"""
        return self._get_korea_bio_vcs() + self._get_global_bio_vcs()

    def _get_korea_bio_vcs(self) -> List[VCFirm]:
        """국내 주요 바이오 VC 데이터 (실제 공개 정보 기반)"""
        return [
            VCFirm(
                id="vc-kip-001",
                name="Korea Investment Partners (한국투자파트너스)",
                country="KR",
                website="https://www.kipvc.com",
                investment_thesis="Leading biotech investor in Korea with 30+ year track record. Focus on innovative drug discovery, digital health, and medical devices. Strong preference for teams with global expansion potential. Active in oncology, CNS, rare diseases, and cell/gene therapy.",
                preferred_stages=["Series A", "Series B", "Growth"],
                portfolio_keywords=["Oncology", "CNS", "Medical Device", "Digital Health", "Global"],
                contact_email="bio@kipvc.com"
            ),
            VCFirm(
                id="vc-intervest-002",
                name="InterVest (인터베스트)",
                country="KR",
                website="https://www.intervest.co.kr",
                investment_thesis="Deep tech and biotech specialist. Platform technologies in gene therapy, cell therapy, and AI-driven drug discovery. Supporting early-stage startups with high technical barriers and strong IP.",
                preferred_stages=["Seed", "Series A"],
                portfolio_keywords=["Gene Therapy", "AI Drug Discovery", "Platform Technology"],
                contact_email="invest@intervest.co.kr"
            ),
            VCFirm(
                id="vc-dsc-003",
                name="DSC Investment (DSC인베스트먼트)",
                country="KR",
                website="https://www.dscinvestment.com",
                investment_thesis="Investing in future unicorns across digital healthcare, telemedicine, and bio-IT convergence. Values rapid execution, market adaptability, and scalable business models.",
                preferred_stages=["Pre-Series A", "Series A", "Series B"],
                portfolio_keywords=["Digital Health", "Telemedicine", "Bio-IT Convergence"],
                contact_email="hello@dsc.co.kr"
            ),
            VCFirm(
                id="vc-kb-004",
                name="KB Investment (KB인베스트먼트)",
                country="KR",
                website="https://www.kbic.co.kr",
                investment_thesis="Major Korean financial group VC arm. Large scale fund focused on late-stage clinical biotech and pre-IPO companies. Strategic partnerships with pharma companies for co-development and licensing.",
                preferred_stages=["Series B", "Series C", "Pre-IPO"],
                portfolio_keywords=["Late Stage Clinical", "Pharma Partnership", "Pre-IPO"],
                contact_email="bio_team@kbic.co.kr"
            ),
            VCFirm(
                id="vc-bluepoint-005",
                name="Bluepoint Partners (블루포인트파트너스)",
                country="KR",
                website="https://bluepoint.ac",
                investment_thesis="Korea's premier deep-tech accelerator. Investing in scientist-founders from lab to company. Focus on deep tech, novel biomarkers, diagnostics, and synthetic biology.",
                preferred_stages=["Seed", "Pre-Series A"],
                portfolio_keywords=["Deep Tech", "Synthetic Biology", "Diagnostics", "Accelerator"],
                contact_email="apply@bluepoint.ac"
            ),
            VCFirm(
                id="vc-stonebridge-006",
                name="StoneBridge Ventures (스톤브릿지벤처스)",
                country="KR",
                website="https://www.stonebridge.co.kr",
                investment_thesis="Multi-stage investor in Korean biotech ecosystem. Strong healthcare vertical with focus on novel therapeutics, precision medicine, and companion diagnostics. Portfolio support includes regulatory strategy and clinical trial design.",
                preferred_stages=["Series A", "Series B"],
                portfolio_keywords=["Precision Medicine", "Companion Diagnostics", "Novel Therapeutics"],
                contact_email="healthcare@stonebridge.co.kr"
            ),
            VCFirm(
                id="vc-lbinvest-007",
                name="LB Investment (엘비인베스트먼트)",
                country="KR",
                website="https://www.lbinvestment.com",
                investment_thesis="One of Korea's largest VC firms with dedicated bio healthcare fund. Active in antibody engineering, ADC (Antibody-Drug Conjugate), and mRNA therapeutics. Supports Korean bio companies seeking global partnerships.",
                preferred_stages=["Series A", "Series B", "Growth"],
                portfolio_keywords=["Antibody Engineering", "ADC", "mRNA", "Global Partnership"],
                contact_email="bio@lbinvestment.com"
            ),
            VCFirm(
                id="vc-mirae-008",
                name="Mirae Asset Venture Investment (미래에셋벤처투자)",
                country="KR",
                website="https://www.miraeassetvi.com",
                investment_thesis="Financial conglomerate backed VC with significant healthcare allocation. Interest in digital therapeutics (DTx), health data analytics, and AI-powered clinical solutions. Cross-border investment capability with global network.",
                preferred_stages=["Series A", "Series B", "Series C"],
                portfolio_keywords=["Digital Therapeutics", "Health Data", "AI Clinical", "Cross-border"],
                contact_email="venture@miraeasset.com"
            ),
            VCFirm(
                id="vc-spring-009",
                name="SpringCamp (스프링캠프)",
                country="KR",
                website="https://www.springcamp.co",
                investment_thesis="Naver-backed early stage investor. Strong track record in bio-AI convergence, digital health platforms, and healthcare SaaS. Provides access to Naver's tech ecosystem and data infrastructure.",
                preferred_stages=["Seed", "Pre-Series A", "Series A"],
                portfolio_keywords=["Bio-AI", "Healthcare SaaS", "Digital Health Platform"],
                contact_email="invest@springcamp.co"
            ),
            VCFirm(
                id="vc-atinum-010",
                name="Atinum Investment (아티넘인베스트먼트)",
                country="KR",
                website="https://www.atinum.com",
                investment_thesis="Technology-driven venture capital with bio-pharma expertise. Focus on first-in-class drug candidates, biosimilars, and CDMO (Contract Development Manufacturing). Strong network with Korean pharmaceutical companies.",
                preferred_stages=["Series A", "Series B"],
                portfolio_keywords=["First-in-class", "Biosimilar", "CDMO", "Pharma"],
                contact_email="bio@atinum.com"
            ),
        ]

    def _get_global_bio_vcs(self) -> List[VCFirm]:
        """글로벌 주요 바이오 VC 데이터"""
        return [
            VCFirm(
                id="vc-racap-101",
                name="RA Capital Management",
                country="US",
                website="https://www.racap.com",
                investment_thesis="Evidence-based investing in public and private healthcare. Requires clear biological proof of concept and strong IP. Major focus on mRNA therapeutics, protein degradation, gene editing, and next-gen oncology.",
                preferred_stages=["Series A", "Series B", "Crossover"],
                portfolio_keywords=["mRNA", "Gene Editing", "Protein Degradation", "Oncology"],
                contact_email="deals@racap.com"
            ),
            VCFirm(
                id="vc-orbimed-102",
                name="OrbiMed Advisors",
                country="US",
                website="https://www.orbimed.com",
                investment_thesis="One of the world's largest healthcare-dedicated investment firms. Multi-stage, global portfolio spanning pharmaceuticals, biotechnology, medical devices, and healthcare IT. Over $18B AUM.",
                preferred_stages=["Series A", "Series B", "Growth", "Public"],
                portfolio_keywords=["Global Pharma", "Biotech", "MedTech", "Large Scale"],
                contact_email="info@orbimed.com"
            ),
            VCFirm(
                id="vc-a16zbio-103",
                name="a16z Bio + Health",
                country="US",
                website="https://a16z.com/bio-health",
                investment_thesis="Andreessen Horowitz's dedicated bio fund. Investing in bold founders applying engineering principles to biology. Focus areas: bio-AI platforms, computational drug discovery, synthetic biology, and health tech infrastructure.",
                preferred_stages=["Seed", "Series A", "Series B"],
                portfolio_keywords=["Bio-AI", "Computational Biology", "Synthetic Biology", "Health Tech"],
                contact_email="bio@a16z.com"
            ),
            VCFirm(
                id="vc-sofinnova-104",
                name="Sofinnova Partners",
                country="FR",
                website="https://www.sofinnovapartners.com",
                investment_thesis="Europe's leading life sciences investor with 50+ year history. Deep expertise in rare diseases, oncology, and industrial biotech. Strong connections to European academic research institutions and pharma companies.",
                preferred_stages=["Seed", "Series A", "Series B"],
                portfolio_keywords=["Rare Disease", "Industrial Biotech", "European Pharma"],
                contact_email="info@sofinnova.fr"
            ),
        ]


# Singleton
_vc_crawler: Optional[VCCrawler] = None

def get_vc_crawler() -> VCCrawler:
    global _vc_crawler
    if _vc_crawler is None:
        _vc_crawler = VCCrawler()
    return _vc_crawler
