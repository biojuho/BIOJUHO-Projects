"""
Canva API 연동 모듈 (Foundation)
GetDayTrends에서 분석 및 생성된 트렌드 텍스트 데이터를 기반으로 Canva 템플릿을 활용해 시각 자료(썸네일, 카드뉴스 등)를 생성하는 파이프라인.
"""

from loguru import logger as log
from config import AppConfig
from models import ScoredTrend

async def generate_visual_assets(trend: ScoredTrend, config: AppConfig) -> list[str]:
    """
    Canva API를 호출하여 시각 자료를 생성하는 함수 (기반 마련).
    
    추후 구현 내용:
    1. config.canva_api_key 등 인증 정보 로드
    2. 트렌드의 top_insight, keyword, volume 등을 Canva 템플릿 변수에 매핑
    3. Canva REST API 또는 제공되는 SDK/MCP를 통해 이미지 생성 요청
    4. 생성된 이미지 URL 반환
    """
    if not config.canva_api_key:
        log.debug("Canva API 키가 설정되지 않았습니다. 시각 자료 생성을 건너뜁니다.")
        return []

    log.info(f"[Canva] '{trend.keyword}' 시각 자료 생성 시작 (템플릿: {config.canva_template_id})")
    
    # TODO: 실제 Canva API 통신 로직 병합
    # 예시:
    # payload = {
    #     "template_id": config.canva_template_id,
    #     "elements": {
    #         "title": trend.keyword,
    #         "subtitle": trend.top_insight
    #     }
    # }
    # image_urls = await canva_client.generate(payload)
    
    return []
