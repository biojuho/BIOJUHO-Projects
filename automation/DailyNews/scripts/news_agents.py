"""Multi-agent news pipeline for DailyNews.

Domain-specialized AI agents analyze news by expertise area:
- TechAgent: AI, software, hardware, startups
- FinanceAgent: markets, economy, investment, regulation
- ScienceAgent: research, biotech, climate, health

Each agent uses domain-specific prompts for deeper analysis.
An orchestrator distributes articles and merges briefings.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.llm import TaskTier, get_client

logger = logging.getLogger(__name__)


# ---- Domain definitions ----

DOMAIN_KEYWORDS = {
    "tech": {
        "keywords": [
            "AI",
            "인공지능",
            "머신러닝",
            "딥러닝",
            "GPT",
            "LLM",
            "스타트업",
            "앱",
            "소프트웨어",
            "하드웨어",
            "반도체",
            "클라우드",
            "사이버보안",
            "블록체인",
            "메타버스",
            "apple",
            "google",
            "microsoft",
            "openai",
            "meta",
            "startup",
            "software",
            "chip",
            "quantum",
        ],
        "system": "AI·테크 전문 뉴스 분석가. 기술적 임팩트와 산업 영향을 중심으로 분석하세요.",
    },
    "finance": {
        "keywords": [
            "시장",
            "주식",
            "경제",
            "금리",
            "환율",
            "투자",
            "코스피",
            "나스닥",
            "S&P",
            "다우",
            "GDP",
            "연준",
            "한은",
            "기준금리",
            "인플레이션",
            "IPO",
            "M&A",
            "실적",
            "매출",
            "영업이익",
            "market",
            "stock",
            "economy",
            "interest rate",
            "fed",
            "inflation",
            "ipo",
            "earnings",
        ],
        "system": "금융·경제 전문 뉴스 분석가. 시장 영향과 투자 시사점을 중심으로 분석하세요.",
    },
    "science": {
        "keywords": [
            "연구",
            "논문",
            "실험",
            "임상",
            "바이오",
            "유전자",
            "기후",
            "탄소",
            "에너지",
            "우주",
            "NASA",
            "nature",
            "science",
            "cell",
            "research",
            "study",
            "clinical",
            "genome",
            "climate",
            "renewable",
            "space",
            "health",
            "의료",
            "신약",
            "백신",
            "진단",
        ],
        "system": "과학·바이오 전문 뉴스 분석가. 과학적 의미와 실용적 영향을 중심으로 분석하세요.",
    },
}

ANALYSIS_PROMPT = """\
다음 {domain} 뉴스들을 전문가 관점으로 분석해주세요.

## 뉴스 목록
{articles_text}

## 분석 형식
### {domain_kr} 주요 뉴스
각 뉴스에 대해:
1. **제목** (출처)
   - 핵심 내용 요약 (1~2문장)
   - 영향 분석 (1문장)

### 종합 인사이트
- 이 분야의 전반적 트렌드 (1~2문장)

간결하고 전문적으로 작성하세요."""

DOMAIN_KR = {
    "tech": "기술",
    "finance": "금융·경제",
    "science": "과학·바이오",
}


@dataclass
class AgentResult:
    """Result from a single domain agent."""

    domain: str = ""
    article_count: int = 0
    analysis: str = ""
    success: bool = True
    error: str = ""


@dataclass
class OrchestratorResult:
    """Result from the full multi-agent pipeline."""

    agent_results: list[AgentResult] = field(default_factory=list)
    merged_briefing: str = ""
    total_articles: int = 0
    unclassified_count: int = 0


class NewsAgent:
    """Domain-specialized news analysis agent."""

    def __init__(self, domain: str):
        self.domain = domain
        self.config = DOMAIN_KEYWORDS.get(domain, {})
        self.keywords = [k.lower() for k in self.config.get("keywords", [])]
        self.system_prompt = self.config.get("system", "뉴스 분석가.")
        self._llm = get_client()

    def matches(self, title: str, description: str = "") -> bool:
        """Check if article belongs to this agent's domain."""
        text = (title + " " + description).lower()
        return any(kw in text for kw in self.keywords)

    async def analyze(self, articles: list[dict]) -> AgentResult:
        """Analyze articles for this domain."""
        if not articles:
            return AgentResult(domain=self.domain, article_count=0, analysis="")

        # Format articles for prompt
        articles_text = "\n".join(
            f"- {a.get('title', 'N/A')} ({a.get('source', 'N/A')}): " f"{a.get('description', '')[:150]}"
            for a in articles[:10]  # Max 10 per agent
        )

        prompt = ANALYSIS_PROMPT.format(
            domain=self.domain,
            domain_kr=DOMAIN_KR.get(self.domain, self.domain),
            articles_text=articles_text,
        )

        try:
            resp = await self._llm.acreate(
                tier=TaskTier.STANDARD,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
            )
            logger.info(
                "Agent [%s]: analyzed %d articles",
                self.domain,
                len(articles),
            )
            return AgentResult(
                domain=self.domain,
                article_count=len(articles),
                analysis=resp.text.strip(),
            )
        except Exception as e:
            logger.error("Agent [%s] failed: %s", self.domain, e)
            return AgentResult(
                domain=self.domain,
                article_count=len(articles),
                success=False,
                error=str(e),
            )


class AgentOrchestrator:
    """Distribute articles to domain agents and merge results."""

    def __init__(self, domains: list[str] | None = None):
        domain_list = domains or ["tech", "finance", "science"]
        self.agents = [NewsAgent(d) for d in domain_list]
        self._llm = get_client()

    def classify_articles(self, articles: list[dict]) -> dict[str, list[dict]]:
        """Classify articles by domain.

        Articles matching multiple domains go to the first matching agent.
        Unmatched articles go to 'general'.
        """
        classified: dict[str, list[dict]] = {a.domain: [] for a in self.agents}
        classified["general"] = []

        for article in articles:
            title = article.get("title", "")
            desc = article.get("description", "")
            assigned = False

            for agent in self.agents:
                if agent.matches(title, desc):
                    classified[agent.domain].append(article)
                    assigned = True
                    break

            if not assigned:
                classified["general"].append(article)

        for domain, items in classified.items():
            if items:
                logger.info("Classified [%s]: %d articles", domain, len(items))

        return classified

    async def run(self, articles: list[dict]) -> OrchestratorResult:
        """Run the multi-agent pipeline.

        1. Classify articles by domain
        2. Each agent analyzes its domain
        3. Merge results into unified briefing
        """
        classified = self.classify_articles(articles)

        # Run agents
        agent_results: list[AgentResult] = []
        for agent in self.agents:
            domain_articles = classified.get(agent.domain, [])
            if domain_articles:
                result = await agent.analyze(domain_articles)
                agent_results.append(result)

        # Handle general (unclassified) articles
        general = classified.get("general", [])

        # Merge briefings
        merged = self._merge_briefings(agent_results, general)

        return OrchestratorResult(
            agent_results=agent_results,
            merged_briefing=merged,
            total_articles=len(articles),
            unclassified_count=len(general),
        )

    def _merge_briefings(
        self,
        results: list[AgentResult],
        general: list[dict],
    ) -> str:
        """Merge agent results into a single briefing."""
        sections = []

        for result in results:
            if result.success and result.analysis:
                sections.append(result.analysis)

        # Add general articles summary
        if general:
            general_lines = "\n".join(f"- {a.get('title', 'N/A')} ({a.get('source', 'N/A')})" for a in general[:5])
            sections.append(f"### 기타 뉴스\n{general_lines}")

        return "\n\n---\n\n".join(sections)
