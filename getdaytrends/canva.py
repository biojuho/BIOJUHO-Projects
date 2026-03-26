"""
Canva API 연동 모듈 - GetDayTrends → Canva MCP 브릿지
GetDayTrends에서 분석 및 생성된 트렌드 텍스트 데이터를 기반으로 Canva 템플릿을 활용해
시각 자료(썸네일, 카드뉴스 등)를 생성하는 파이프라인.

구현 방식:
- Canva MCP 서버 (canva-mcp/)와 JSON-RPC 통신
- 트렌드 데이터 → Canva 템플릿 변수 매핑
- 생성된 이미지 URL 반환
"""

import json
import subprocess
import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger as log
from config import AppConfig
from models import ScoredTrend


class CanvaMCPClient:
    """Canva MCP 서버와 통신하는 클라이언트"""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.mcp_server_path = workspace_root / "canva-mcp"
        self.server_process: Optional[subprocess.Popen] = None

    async def start_server(self) -> bool:
        """Canva MCP 서버 시작"""
        if not (self.mcp_server_path / "package.json").exists():
            log.warning("[Canva MCP] 서버 디렉토리를 찾을 수 없습니다: {}", self.mcp_server_path)
            return False

        try:
            # MCP 서버 시작 (stdio 모드)
            self.server_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(self.mcp_server_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            log.info("[Canva MCP] 서버 시작됨 (PID: {})", self.server_process.pid)
            # 서버 초기화 대기
            await asyncio.sleep(2)
            return True

        except Exception as e:
            log.error("[Canva MCP] 서버 시작 실패: {}", e)
            return False

    async def create_design(self, payload: dict) -> list[str]:
        """
        Canva 디자인 생성 요청

        Args:
            payload: {
                "template_id": str,
                "elements": {
                    "title": str,
                    "subtitle": str,
                    "volume": str,
                    "category": str
                }
            }

        Returns:
            생성된 이미지 URL 리스트
        """
        if not self.server_process:
            log.warning("[Canva MCP] 서버가 시작되지 않았습니다")
            return []

        try:
            # JSON-RPC 2.0 요청 구성
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "create_design",
                    "arguments": payload
                }
            }

            # MCP 서버로 요청 전송
            request_json = json.dumps(request) + "\n"
            self.server_process.stdin.write(request_json)
            self.server_process.stdin.flush()

            # 응답 대기 (타임아웃 30초)
            response_line = ""
            try:
                response_line = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self.server_process.stdout.readline
                    ),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                log.error("[Canva MCP] 응답 타임아웃 (30초)")
                return []

            # JSON 파싱
            response = json.loads(response_line)

            if "error" in response:
                log.error("[Canva MCP] 오류 응답: {}", response["error"])
                return []

            # 이미지 URL 추출
            result = response.get("result", {})
            image_urls = result.get("image_urls", [])

            log.info("[Canva MCP] 디자인 생성 완료: {} 이미지", len(image_urls))
            return image_urls

        except Exception as e:
            log.error("[Canva MCP] 디자인 생성 실패: {}", e)
            return []

    def shutdown(self):
        """MCP 서버 종료"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait(timeout=5)
            log.info("[Canva MCP] 서버 종료됨")


# 전역 MCP 클라이언트 인스턴스 (싱글톤)
_mcp_client: Optional[CanvaMCPClient] = None


def get_mcp_client(workspace_root: Path = Path(__file__).resolve().parents[1]) -> CanvaMCPClient:
    """MCP 클라이언트 싱글톤 반환"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = CanvaMCPClient(workspace_root)
    return _mcp_client


async def generate_visual_assets(trend: ScoredTrend, config: AppConfig) -> list[str]:
    """
    Canva API를 호출하여 시각 자료를 생성하는 함수.

    프로세스:
    1. config.canva_api_key 등 인증 정보 확인
    2. 트렌드의 top_insight, keyword, volume 등을 Canva 템플릿 변수에 매핑
    3. Canva MCP 서버를 통해 이미지 생성 요청
    4. 생성된 이미지 URL 반환

    Args:
        trend: 트렌드 데이터
        config: 앱 설정 (canva_api_key, canva_template_id 포함)

    Returns:
        생성된 이미지 URL 리스트
    """
    # API 키 확인
    if not config.canva_api_key:
        log.debug("[Canva] API 키가 설정되지 않았습니다. 시각 자료 생성을 건너뜁니다.")
        return []

    log.info("[Canva] '{}' 시각 자료 생성 시작 (템플릿: {})",
             trend.keyword, config.canva_template_id or "default")

    # MCP 클라이언트 초기화
    mcp_client = get_mcp_client()

    # 서버 시작 (이미 시작되어 있으면 스킵)
    if not mcp_client.server_process:
        server_started = await mcp_client.start_server()
        if not server_started:
            log.warning("[Canva] MCP 서버 시작 실패 - 스켈레톤 모드로 계속")
            return await _generate_visual_assets_skeleton(trend, config)

    # Canva 템플릿 페이로드 구성
    payload = {
        "template_id": config.canva_template_id or "default",
        "elements": {
            "title": trend.keyword,
            "subtitle": trend.top_insight or "",
            "volume": str(trend.volume) if hasattr(trend, 'volume') else "",
            "category": trend.category if hasattr(trend, 'category') else ""
        }
    }

    # MCP 서버를 통해 디자인 생성
    image_urls = await mcp_client.create_design(payload)

    if not image_urls:
        log.warning("[Canva] 이미지 생성 실패 - 스켈레톤 모드로 폴백")
        return await _generate_visual_assets_skeleton(trend, config)

    log.info("[Canva] '{}' 시각 자료 생성 완료: {} 이미지",
             trend.keyword, len(image_urls))

    return image_urls


async def _generate_visual_assets_skeleton(trend: ScoredTrend, config: AppConfig) -> list[str]:
    """
    스켈레톤 모드: 실제 이미지 생성 없이 로깅만 수행

    Phase 2에서 MCP 서버 통합이 완료되면 제거 예정
    """
    log.info("[Canva Skeleton] '{}' 시각 자료 생성 요청 (스켈레톤 모드)", trend.keyword)
    log.debug("[Canva Skeleton] 템플릿 ID: {}", config.canva_template_id)
    log.debug("[Canva Skeleton] 트렌드 데이터: keyword={}, insight={}",
              trend.keyword, trend.top_insight)

    # Phase 2 TODO:
    # - MCP 서버 프로세스 관리 안정화
    # - stdin/stdout JSON-RPC 통신 디버깅
    # - Canva OAuth 인증 플로우 통합
    # - 생성된 이미지 다운로드 및 로컬 저장
    # - 이미지 URL CDN 업로드

    return []  # 스켈레톤 모드: 빈 리스트 반환
