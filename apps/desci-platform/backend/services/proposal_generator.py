import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from services.logging_config import get_logger

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_AVAILABLE = True
except ImportError:
    StrOutputParser = None  # type: ignore[assignment]
    ChatPromptTemplate = None  # type: ignore[assignment]
    LANGCHAIN_AVAILABLE = False

logger = get_logger(__name__)

_workspace_root = Path(__file__).resolve().parents[3]
load_dotenv(_workspace_root / ".env")

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
    PROPOSAL_SYSTEM_PROMPT = "You are an expert grant writer with biotechnology domain expertise."
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
Language: Korean (use professional R&D terminology).
"""

if not _PROMPTS_LOADED or REVIEW_SYSTEM_PROMPT is None:
    REVIEW_SYSTEM_PROMPT = """You are an expert scientific grant reviewer.
Critically analyze a grant proposal draft against the original RFP and paper.
Provide concise strengths, weaknesses, and actionable improvements.
"""

REVIEW_USER_PROMPT = """
[RFP Title]
{rfp_title}

[Research Paper Abstract]
{paper_abstract}

[Draft Proposal to Review]
{draft}

[Task]
Critically analyze the draft above and provide strengths, weaknesses, and actionable improvements in Korean.
"""

if not _PROMPTS_LOADED or LIT_REVIEW_SYSTEM_PROMPT is None:
    LIT_REVIEW_SYSTEM_PROMPT = """You are an expert literature reviewer.
Synthesize a compelling literature review abstract from the paper and the RFP.
Output only the final scientific paragraphs in Korean.
"""

LIT_REVIEW_USER_PROMPT = """
[RFP Title]
{rfp_title}

[Research Paper Abstract]
{paper_abstract}

[Key Content]
{paper_content}

[Task]
Generate a rigorous literature review abstract that contextualizes the paper within the RFP domain.
"""


class ProposalGenerator:
    def __init__(self):
        self.llm = None

        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if google_key and GOOGLE_AVAILABLE:
            self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=google_key, temperature=0.7)
            logger.info("proposal_generator_init", model="gemini-1.5-flash")
        elif os.getenv("OPENAI_API_KEY") and OPENAI_AVAILABLE:
            self.llm = ChatOpenAI(model="gpt-4-turbo-preview", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.7)
            logger.info("proposal_generator_init", model="gpt-4-turbo-preview")

    async def synthesize_literature(self, rfp_data: dict, paper_data: dict) -> str:
        if not self.llm or not LANGCHAIN_AVAILABLE:
            return "### Literature Review Synthesis\n\n[Mock] This paper provides a foundational approach..."

        prompt = ChatPromptTemplate.from_messages(
            [("system", LIT_REVIEW_SYSTEM_PROMPT), ("user", LIT_REVIEW_USER_PROMPT)]
        )
        chain = prompt | self.llm | StrOutputParser()

        try:
            return await chain.ainvoke(
                {
                    "rfp_title": rfp_data.get("title", "Unknown RFP"),
                    "paper_abstract": paper_data.get("metadata", {}).get("abstract", ""),
                    "paper_content": paper_data.get("document", "")[:5000],
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("lit_review_failed", error=str(exc))
            return "### Literature Review Synthesis\n\nError generating synthesis."

    async def generate_draft(self, rfp_data: dict, paper_data: dict) -> str:
        if not self.llm or not LANGCHAIN_AVAILABLE:
            return self._generate_mock_draft(rfp_data, paper_data)

        prompt = ChatPromptTemplate.from_messages([("system", PROPOSAL_SYSTEM_PROMPT), ("user", USER_PROMPT_TEMPLATE)])
        chain = prompt | self.llm | StrOutputParser()

        try:
            return await chain.ainvoke(
                {
                    "rfp_title": rfp_data.get("title", "Unknown RFP"),
                    "rfp_description": rfp_data.get("document", "")[:5000],
                    "paper_title": paper_data.get("metadata", {}).get("title", "Unknown Paper"),
                    "paper_abstract": paper_data.get("metadata", {}).get("abstract", ""),
                    "paper_content": paper_data.get("document", "")[:5000],
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("proposal_llm_failed", error=str(exc), fallback="mock_draft")
            return self._generate_mock_draft(rfp_data, paper_data)

    async def review_draft(self, rfp_data: dict, paper_data: dict, draft: str) -> str:
        if not self.llm or not LANGCHAIN_AVAILABLE:
            return (
                "### AI Peer Review\n"
                "- **Strengths**: [Mock] Well structured.\n"
                "- **Weaknesses**: [Mock] Lacks deep technical integration details.\n"
                "- **Improvements**: [Mock] Elaborate on the experimental methodology."
            )

        prompt = ChatPromptTemplate.from_messages([("system", REVIEW_SYSTEM_PROMPT), ("user", REVIEW_USER_PROMPT)])
        chain = prompt | self.llm | StrOutputParser()

        try:
            return await chain.ainvoke(
                {
                    "rfp_title": rfp_data.get("title", "Unknown RFP"),
                    "paper_abstract": paper_data.get("metadata", {}).get("abstract", ""),
                    "draft": draft,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("review_llm_failed", error=str(exc))
            return "### AI Peer Review\nError generating review due to LLM failure."

    def _generate_mock_draft(self, rfp_data: dict, paper_data: dict) -> str:
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
