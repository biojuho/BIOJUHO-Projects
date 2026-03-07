import asyncio
import sys
from mcp.client.stdio import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

async def run():
    # 서버 파라미터 설정
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. 도구 목록 확인
            await session.initialize()
            tools = await session.list_tools()
            print(f"--- 도구 목록: {[t.name for t in tools.tools]} ---")

            # 2. 검색 테스트
            print("\n--- 검색 테스트: '테스트' ---")
            search_result = await session.call_tool("search_notion", arguments={"query": "테스트"})
            print(search_result.content[0].text)

            # 3. 읽기 테스트 (검색 결과가 있다면 첫 번째 페이지 읽기)
            # 주의: 실제 페이지 ID가 필요하므로, 위 검색 결과에서 ID를 파싱하거나 하드코딩해야 함
            # 여기서는 검색 결과 텍스트에서 ID를 추출하는 간단한 로직은 생략하고, 
            # 검색이 성공했는지 여부만 확인합니다.
            
if __name__ == "__main__":
    asyncio.run(run())
