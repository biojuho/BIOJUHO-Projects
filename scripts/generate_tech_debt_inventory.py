#!/usr/bin/env python3
"""
기술 부채 인벤토리 자동 생성 스크립트

코드베이스에서 TODO, FIXME, HACK, XXX 주석을 자동으로 수집하여
우선순위가 지정된 인벤토리 문서를 생성합니다.

Usage:
    python scripts/generate_tech_debt_inventory.py --output docs/TECH_DEBT_INVENTORY.md
"""

import argparse
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict


@dataclass
class TechDebtItem:
    """기술 부채 항목"""
    marker: str  # TODO, FIXME, HACK, XXX
    file_path: str
    line_number: int
    content: str
    context: str  # 해당 줄의 전후 컨텍스트
    priority: str  # P0, P1, P2, P3 (자동 분류)
    category: str  # security, performance, refactor, documentation, etc.


class TechDebtAnalyzer:
    """기술 부채 분석기"""

    # 우선순위 결정 키워드
    PRIORITY_KEYWORDS = {
        'P0': ['security', 'vulnerability', 'exploit', 'critical', 'urgent', 'broken'],
        'P1': ['performance', 'bug', 'error', 'fix', 'issue', 'problem'],
        'P2': ['refactor', 'cleanup', 'optimize', 'improve', 'enhance'],
        'P3': ['document', 'comment', 'clarify', 'explain', 'note'],
    }

    # 카테고리 결정 키워드
    CATEGORY_KEYWORDS = {
        'security': ['security', 'auth', 'permission', 'credential', 'token', 'secret'],
        'performance': ['performance', 'slow', 'optimize', 'cache', 'speed'],
        'bug': ['bug', 'error', 'fix', 'broken', 'issue'],
        'refactor': ['refactor', 'cleanup', 'restructure', 'reorganize'],
        'documentation': ['document', 'comment', 'explain', 'clarify'],
        'testing': ['test', 'coverage', 'mock', 'assertion'],
        'dependency': ['dependency', 'upgrade', 'deprecate', 'version'],
    }

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.items: List[TechDebtItem] = []

    def collect_items(self) -> None:
        """코드베이스에서 기술 부채 항목 수집"""
        print("기술 부채 항목 수집 중...")

        # Git grep으로 TODO/FIXME/HACK/XXX 검색
        markers = ['TODO', 'FIXME', 'HACK', 'XXX']
        pattern = '|'.join(markers)

        try:
            result = subprocess.run(
                ['git', 'grep', '-n', '-E', f'({pattern})'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',  # Windows 인코딩 문제 우회
                timeout=30
            )

            if result.returncode == 0 and result.stdout:
                self._parse_grep_output(result.stdout)
            elif result.returncode == 1:
                print("No tech debt markers found (this is good!)")
            else:
                print(f"Warning: git grep returned code {result.returncode}")
                if result.stderr:
                    print(f"stderr: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            print("Error: git grep timeout (30s)")
        except Exception as e:
            print(f"Error running git grep: {e}")

        print(f"수집 완료: {len(self.items)}개 항목")

    def _parse_grep_output(self, output: str) -> None:
        """Git grep 출력 파싱"""
        for line in output.strip().split('\n'):
            if not line:
                continue

            # Format: file.py:123:# TODO: fix this
            match = re.match(r'^([^:]+):(\d+):(.+)$', line)
            if not match:
                continue

            file_path, line_num, content = match.groups()

            # 마커 추출
            marker = None
            for m in ['TODO', 'FIXME', 'HACK', 'XXX']:
                if m in content:
                    marker = m
                    break

            if not marker:
                continue

            # 컨텍스트 추출 (마커 이후 텍스트)
            context = content.split(marker, 1)[1].strip(':- ').strip()

            # 우선순위 및 카테고리 자동 분류
            priority = self._determine_priority(context, file_path)
            category = self._determine_category(context)

            item = TechDebtItem(
                marker=marker,
                file_path=file_path,
                line_number=int(line_num),
                content=content.strip(),
                context=context,
                priority=priority,
                category=category
            )

            self.items.append(item)

    def _determine_priority(self, text: str, file_path: str) -> str:
        """텍스트 내용 및 파일 경로로 우선순위 결정"""
        text_lower = text.lower()

        # 1. 문서 파일은 기본 P3 (단, 보안 키워드는 예외)
        if file_path.endswith(('.md', '.txt', '.rst')):
            # 보안/취약점 키워드가 있으면 P0
            if any(kw in text_lower for kw in ['security', 'vulnerability', 'critical', 'exploit']):
                return 'P0'
            # 그 외 문서는 모두 P3
            return 'P3'

        # 2. 세션 히스토리/워크플로우/QA 리포트는 제외 (P3)
        excluded_patterns = ['.agent/', '.sessions/', 'qa-reports/', 'session-history/']
        if any(pattern in file_path for pattern in excluded_patterns):
            return 'P3'

        # 3. 코드 파일 우선순위 분류
        for priority, keywords in self.PRIORITY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return priority

        return 'P3'  # 기본값

    def _determine_category(self, text: str) -> str:
        """텍스트 내용으로 카테고리 결정"""
        text_lower = text.lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return 'other'

    def generate_report(self, output_path: Path) -> None:
        """인벤토리 리포트 생성"""
        print(f"리포트 생성 중: {output_path}")

        # 우선순위 및 카테고리별로 그룹화
        by_priority = defaultdict(list)
        by_category = defaultdict(list)
        by_project = defaultdict(list)

        for item in self.items:
            by_priority[item.priority].append(item)
            by_category[item.category].append(item)

            # 프로젝트 추출 (첫 번째 디렉토리)
            project = item.file_path.split('/')[0] if '/' in item.file_path else 'root'
            by_project[project].append(item)

        # Markdown 생성
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self._generate_header())
            f.write(self._generate_summary(by_priority, by_category, by_project))
            f.write(self._generate_priority_sections(by_priority))
            f.write(self._generate_category_sections(by_category))
            f.write(self._generate_project_sections(by_project))
            f.write(self._generate_footer())

        print(f"리포트 생성 완료: {output_path}")

    def _generate_header(self) -> str:
        """문서 헤더 생성"""
        return f"""# 기술 부채 인벤토리 (Tech Debt Inventory)

**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**워크스페이스**: {self.workspace_root.name}
**총 항목**: {len(self.items)}

---

## 개요

이 문서는 코드베이스에서 자동으로 수집된 기술 부채 항목(TODO, FIXME, HACK, XXX)을
우선순위 및 카테고리별로 분류한 인벤토리입니다.

### 우선순위 분류

- **P0 (Critical)**: 보안/취약점/긴급 - 즉시 수정 필요
- **P1 (High)**: 성능/버그/에러 - 2주 내 수정
- **P2 (Medium)**: 리팩토링/최적화 - 1개월 내 수정
- **P3 (Low)**: 문서화/개선 - 백로그

### 카테고리

- **security**: 보안 관련
- **performance**: 성능 관련
- **bug**: 버그 수정
- **refactor**: 리팩토링
- **documentation**: 문서화
- **testing**: 테스트
- **dependency**: 의존성 관리
- **other**: 기타

---

"""

    def _generate_summary(self, by_priority: Dict, by_category: Dict, by_project: Dict) -> str:
        """요약 통계 생성"""
        content = "## 요약 통계\n\n"

        # 우선순위별
        content += "### 우선순위별\n\n"
        content += "| 우선순위 | 항목 수 | 비율 |\n"
        content += "|---------|--------|------|\n"

        for priority in ['P0', 'P1', 'P2', 'P3']:
            count = len(by_priority.get(priority, []))
            percentage = (count / len(self.items) * 100) if self.items else 0
            content += f"| {priority} | {count} | {percentage:.1f}% |\n"

        # 카테고리별
        content += "\n### 카테고리별\n\n"
        content += "| 카테고리 | 항목 수 |\n"
        content += "|---------|--------|\n"

        sorted_categories = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)
        for category, items in sorted_categories:
            content += f"| {category} | {len(items)} |\n"

        # 프로젝트별
        content += "\n### 프로젝트별\n\n"
        content += "| 프로젝트 | 항목 수 |\n"
        content += "|---------|--------|\n"

        sorted_projects = sorted(by_project.items(), key=lambda x: len(x[1]), reverse=True)
        for project, items in sorted_projects[:10]:  # 상위 10개만
            content += f"| {project} | {len(items)} |\n"

        content += "\n---\n\n"
        return content

    def _generate_priority_sections(self, by_priority: Dict) -> str:
        """우선순위별 섹션 생성"""
        content = "## 우선순위별 상세\n\n"

        for priority in ['P0', 'P1', 'P2', 'P3']:
            items = by_priority.get(priority, [])
            if not items:
                continue

            content += f"### {priority} - {len(items)}개 항목\n\n"

            for item in items:
                content += f"- **[{item.marker}]** [{item.file_path}:{item.line_number}]({item.file_path}#L{item.line_number})\n"
                content += f"  - Category: `{item.category}`\n"
                content += f"  - Context: {item.context}\n"
                content += f"  - Code: `{item.content}`\n\n"

        content += "---\n\n"
        return content

    def _generate_category_sections(self, by_category: Dict) -> str:
        """카테고리별 섹션 생성"""
        content = "## 카테고리별 상세\n\n"

        sorted_categories = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)

        for category, items in sorted_categories:
            content += f"### {category.capitalize()} - {len(items)}개 항목\n\n"

            # 우선순위별로 정렬
            sorted_items = sorted(items, key=lambda x: x.priority)

            for item in sorted_items:
                content += f"- **[{item.priority}]** [{item.file_path}:{item.line_number}]({item.file_path}#L{item.line_number})\n"
                content += f"  - {item.context}\n\n"

        content += "---\n\n"
        return content

    def _generate_project_sections(self, by_project: Dict) -> str:
        """프로젝트별 섹션 생성"""
        content = "## 프로젝트별 상세\n\n"

        sorted_projects = sorted(by_project.items(), key=lambda x: len(x[1]), reverse=True)

        for project, items in sorted_projects:
            content += f"### {project} - {len(items)}개 항목\n\n"

            # 우선순위별 요약
            priority_counts = defaultdict(int)
            for item in items:
                priority_counts[item.priority] += 1

            content += "**우선순위 분포**: "
            content += ", ".join([f"{p}: {c}" for p, c in sorted(priority_counts.items())])
            content += "\n\n"

            # 우선순위별로 정렬
            sorted_items = sorted(items, key=lambda x: (x.priority, x.file_path))

            for item in sorted_items:
                content += f"- **[{item.priority}]** [{item.file_path}:{item.line_number}]({item.file_path}#L{item.line_number})\n"
                content += f"  - [{item.marker}] {item.context}\n\n"

        content += "---\n\n"
        return content

    def _generate_footer(self) -> str:
        """문서 푸터 생성"""
        return f"""## 다음 단계

1. **P0 항목 즉시 처리**: 보안 및 긴급 이슈부터 해결
2. **GitHub Issues 생성**: 각 항목을 이슈로 등록하여 추적
3. **주간 부채 상환**: 매주 금요일 "Tech Debt Friday" 운영
4. **월간 리뷰**: 진행 상황 및 남은 부채 리뷰

---

**자동 생성 스크립트**: `scripts/generate_tech_debt_inventory.py`
**마지막 업데이트**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


def main():
    parser = argparse.ArgumentParser(description='기술 부채 인벤토리 자동 생성')
    parser.add_argument(
        '--output',
        default='docs/TECH_DEBT_INVENTORY.md',
        help='출력 파일 경로 (기본값: docs/TECH_DEBT_INVENTORY.md)'
    )
    parser.add_argument(
        '--workspace',
        default='.',
        help='워크스페이스 루트 경로 (기본값: 현재 디렉토리)'
    )

    args = parser.parse_args()

    workspace_root = Path(args.workspace).resolve()
    output_path = workspace_root / args.output

    print(f"워크스페이스: {workspace_root}")
    print(f"출력 경로: {output_path}")

    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 분석 실행
    analyzer = TechDebtAnalyzer(workspace_root)
    analyzer.collect_items()
    analyzer.generate_report(output_path)

    print("\n완료!")
    print(f"총 {len(analyzer.items)}개 기술 부채 항목이 발견되었습니다.")
    print(f"인벤토리 문서: {output_path}")


if __name__ == '__main__':
    main()
