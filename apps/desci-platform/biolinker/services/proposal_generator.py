import os
from pathlib import Path

import structlog
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = structlog.get_logger(__name__)

# 루트 .env 로드
_workspace_root = Path(__file__).resolve().parents[3]
load_dotenv(_workspace_root / ".env")

# LLM Imports
try:
    from langchain_google_genai import ChatGoogleGenerativeAI

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    from langchain_openai import ChatOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Centralized prompt templates
import sys

_pkg_root = Path(__file__).resolve().parents[3] / "packages"
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

try:
    from shared.prompts import get_prompt_manager as _get_pm

    _pm = _get_pm()
    PROPOSAL_SYSTEM_PROMPT = _pm.render("biolinker_proposal")
    REVIEW_SYSTEM_PROMPT = _pm.render("biolinker_review")
    LIT_REVIEW_SYSTEM_PROMPT = _pm.render("biolinker_lit_synthesis")
    _PROMPTS_LOADED = True
except Exception:
    _PROMPTS_LOADED = False
    PROPOSAL_SYSTEM_PROMPT = "You are an expert Grant Writer with a Ph.D. in Biotechnology."
    REVIEW_SYSTEM_PROMPT = None
    LIT_REVIEW_SYSTEM_PROMPT = None

USER_PROMPT_TEMPLATE = """
[RFP Details]
Title: {rfp_title}
Description:
{rfp_description}

[Research Paper Asset]
Title: {paper_title}
Abstract: {paper_abstract}
Key Content:
{paper_content}

[Task]
Write a draft proposal titled "{rfp_title} - {paper_title} Integration".
Language: Korean (Use professional R&D terminology).
"""

if not _PROMPTS_LOADED or REVIEW_SYSTEM_PROMPT is None:
    REVIEW_SYSTEM_PROMPT = """You are an expert Scientific Grant Reviewer.
Your task is to critically analyze a grant proposal draft based on the original Request for Proposal (RFP) and the Research Paper submitted.
Provide a concise, constructive critique consisting of strengths, weaknesses, and actionable improvements.
"""

REVIEW_USER_PROMPT = """
[RFP Title]
{rfp_title}

[Research Paper Abstract]
{paper_abstract}

[Draft Proposal to Review]
{draft}

[Task]
Critically analyze the draft above. Provide your response in the following format:
### 🧐 AI Peer Review (비판적 검토)
- **Strengths (강점)**: ...
- **Weaknesses (약점)**: ...
- **Actionable Improvements (개선 방향)**: ...

Language: Korean (Use professional R&D terminology).
"""


if not _PROMPTS_LOADED or LIT_REVIEW_SYSTEM_PROMPT is None:
    LIT_REVIEW_SYSTEM_PROMPT = """You are an expert Literature Reviewer.
Your task is to synthesize a compelling literature review abstract based on a provided research paper and an RFP.
You must use a two-stage process:
Stage 1: Outline the key themes, methods, and outcomes.
Stage 2: Convert the outline into full, flowing, professionally formatted scientific paragraphs without bullet points.
Output ONLY the final Phase 2 paragraphs in Korean.
"""

LIT_REVIEW_USER_PROMPT = """
[RFP Title]
{rfp_title}

[Research Paper Abstract]
{paper_abstract}

[Key Content]
{paper_content}

[Task]
Generate a rigorous literature review abstract that contextualizes the paper within the RFP's domain.
"""


class ProposalGenerator:
    def __init__(self):
        self.llm = None

        # 1. Google Gemini (Priority)
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if google_key and GOOGLE_AVAILABLE:
            self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=google_key, temperature=0.7)
            logger.info("proposal_generator_init", model="gemini-1.5-flash")

        # 2. OpenAI GPT-4 (Fallback)
        elif os.getenv("OPENAI_API_KEY") and OPENAI_AVAILABLE:
            self.llm = ChatOpenAI(model="gpt-4-turbo-preview", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.7)
            logger.info("proposal_generator_init", model="gpt-4-turbo-preview")

    async def synthesize_literature(self, rfp_data: dict, paper_data: dict) -> str:
        """
        Generates a literature review synthesis using the literature-review skill patterns.
        """
        if not self.llm:
            return "### 📚 Literature Review Synthesis\n\n[Mock] This paper provides a foundational approach..."

        prompt = ChatPromptTemplate.from_messages(
            [("system", LIT_REVIEW_SYSTEM_PROMPT), ("user", LIT_REVIEW_USER_PROMPT)]
        )

        chain = prompt | self.llm | StrOutputParser()

        try:
            response = await chain.ainvoke(
                {
                    "rfp_title": rfp_data.get("title", "Unknown RFP"),
                    "paper_abstract": paper_data.get("metadata", {}).get("abstract", ""),
                    "paper_content": paper_data.get("document", "")[:5000],
                }
            )
            return response
        except Exception as e:
            logger.error("lit_review_failed", error=str(e))
            return "### 📚 Literature Review Synthesis\n\nError generating synthesis."

    async def generate_draft(self, rfp_data: dict, paper_data: dict) -> str:
        """
        Generates a proposal draft.
        """
        if not self.llm:
            return self._generate_mock_draft(rfp_data, paper_data)

        prompt = ChatPromptTemplate.from_messages([("system", PROPOSAL_SYSTEM_PROMPT), ("user", USER_PROMPT_TEMPLATE)])

        chain = prompt | self.llm | StrOutputParser()

        try:
            response = await chain.ainvoke(
                {
                    "rfp_title": rfp_data.get("title", "Unknown RFP"),
                    "rfp_description": rfp_data.get("document", "")[:5000],
                    "paper_title": paper_data.get("metadata", {}).get("title", "Unknown Paper"),
                    "paper_abstract": paper_data.get("metadata", {}).get("abstract", ""),
                    "paper_content": paper_data.get("document", "")[:5000],
                }
            )
            return response
        except Exception as e:
            logger.error("proposal_llm_failed", error=str(e), fallback="mock_draft")
            return self._generate_mock_draft(rfp_data, paper_data)

    async def review_draft(self, rfp_data: dict, paper_data: dict, draft: str) -> str:
        """
        Acts as a second Agent to critique the generated draft.
        """
        if not self.llm:
            return "### 🧐 AI Peer Review\n- **Strengths**: [Mock] Well structured.\n- **Weaknesses**: [Mock] Lacks deep technical integration details.\n- **Improvements**: [Mock] Elaborate on the experimental methodology."

        prompt = ChatPromptTemplate.from_messages([("system", REVIEW_SYSTEM_PROMPT), ("user", REVIEW_USER_PROMPT)])

        chain = prompt | self.llm | StrOutputParser()

        try:
            response = await chain.ainvoke(
                {
                    "rfp_title": rfp_data.get("title", "Unknown RFP"),
                    "paper_abstract": paper_data.get("metadata", {}).get("abstract", ""),
                    "draft": draft,
                }
            )
            return response
        except Exception as e:
            logger.error("review_llm_failed", error=str(e))
            return "### 🧐 AI Peer Review\nError generating review due to LLM failure."

    def _generate_mock_draft(self, rfp_data: dict, paper_data: dict) -> str:
        """
        Generates a deterministic mock draft for testing/fallback.
        """
        rfp_title = rfp_data.get("title", "Untitled RFP")
        paper_title = paper_data.get("metadata", {}).get("title", "Untitled Paper")

        return f"""# Proposal: {rfp_title}

## 1. Executive Summary
This proposal aims to address the goals of "{rfp_title}" by leveraging the innovative findings from our research on "{paper_title}". We propose a novel framework that integrates...

## 2. Methodology
Based on the provided research, we will:
- Implement the core algorithm described in "{paper_title}".
- Adapt the experimental setup to meet the RFP's specific requirements.
- Conduct validation tests using the dataset specified in the guideline.

## 3. Expected Outcomes
- A fully functional prototype achieving >95% accuracy.
- A comprehensive report detailing the integration of our technology.
- Commercialization potential in the bio-health sector.

**(Note: This is an AI-generated draft based on the provided documents.)**
"""


_generator = None


def get_proposal_generator() -> ProposalGenerator:
    global _generator
    if _generator is None:
        _generator = ProposalGenerator()
    return _generator
