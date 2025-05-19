import json
import os
import time

from performance_analyzer import PerformanceAnalyzer


def wait_for_reports():
    """두 프로듀서의 보고서 파일이 생성될 때까지 대기"""
    python_report_path = '/app/reports/python_performance_report.json'
    go_report_path = '/app/reports/go_performance_report.json'

    max_wait_time = 3600  # 최대 5분 대기
    check_interval = 5   # 5초마다 확인
    waited_time = 0

    print("두 프로듀서의 보고서 파일을 기다리는 중...")

    while waited_time < max_wait_time:
        python_exists = os.path.exists(python_report_path)
        go_exists = os.path.exists(go_report_path)

        print(f"대기 시간: {waited_time}초 - Python: {'✓' if python_exists else '✗'}, Go: {'✓' if go_exists else '✗'}")

        if python_exists and go_exists:
            print("두 보고서 파일이 모두 생성되었습니다!")
            return python_report_path, go_report_path

        time.sleep(check_interval)
        waited_time += check_interval

    # 타임아웃 발생 시 존재하는 파일만 반환
    if os.path.exists(python_report_path) or os.path.exists(go_report_path):
        print("일부 보고서만 생성되었지만 분석을 진행합니다...")
        return python_report_path if os.path.exists(python_report_path) else None, \
               go_report_path if os.path.exists(go_report_path) else None

    print("보고서 파일을 찾을 수 없습니다. 분석을 건너뜁니다.")
    return None, None

def create_dummy_report_if_missing(path, producer_type):
    """누락된 보고서에 대해 더미 보고서 생성"""
    if not os.path.exists(path):
        dummy_report = {
            "test_info": {
                "producer_id": producer_type,
                "total_messages": 0,
                "messages_per_second": 0,                "total_runtime_seconds": 0,
                "total_markets": 0,
                "krw_markets": 0,
                "websocket_connections": 0
            },
            "memory": {"avg_mb": 0, "max_mb": 0, "min_mb": 0},
            "delivery_reports": {"success": 0, "error": 0},
            "message_processing": {"avg_ms": 0, "p95_ms": 0, "p99_ms": 0, "count": 0, "min_ms": 0, "max_ms": 0},
            "kafka_send": {"avg_ms": 0, "p95_ms": 0, "p99_ms": 0, "count": 0, "min_ms": 0, "max_ms": 0},
            "websocket_connection": {"avg_ms": 0, "p95_ms": 0, "p99_ms": 0, "count": 0, "min_ms": 0, "max_ms": 0},
            "kafka_config": {
                "library": f"confluent-kafka-{producer_type}",
                "batch_size": 32768,
                "linger_ms": 10,
                "compression": "snappy"
            },
            "websocket_info": {
                "connections": [],
                "markets_per_connection": 20,
                "connection_rate_limit": 5
            }
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(dummy_report, f, indent=2, ensure_ascii=False)
        print(f"더미 보고서 생성됨: {path}")

def validate_report_file(path):
    """보고서 파일이 유효한 JSON인지 확인"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, FileNotFoundError, Exception) as e:
        print(f"보고서 파일 검증 실패 {path}: {e}")
        return False

def main():
    print("=== 성능 분석 시작 ===")

    # 보고서 파일 대기
    python_path, go_path = wait_for_reports()

    if python_path is None and go_path is None:
        print("분석할 보고서가 없습니다. 종료합니다.")
        return

    # 보고서 파일 검증
    if python_path and not validate_report_file(python_path):
        print(f"Python 보고서 파일이 손상되었습니다: {python_path}")
        python_path = None

    if go_path and not validate_report_file(go_path):
        print(f"Go 보고서 파일이 손상되었습니다: {go_path}")
        go_path = None

    # 누락된 보고서에 대해 더미 파일 생성
    if python_path is None:
        python_path = '/app/reports/python_performance_report.json'
        create_dummy_report_if_missing(python_path, 'python')

    if go_path is None:
        go_path = '/app/reports/go_performance_report.json'
        create_dummy_report_if_missing(go_path, 'go')

    # 성능 분석 실행
    try:
        analyzer = PerformanceAnalyzer(python_path, go_path)

        print("시각화 생성 중...")
        analyzer.create_visualizations()

        print("상세 보고서 생성 중...")
        analyzer.generate_report()

        print("=== 분석 완료 ===")
        print("결과 파일:")
        print("- /app/charts/performance_comparison.png: 성능 비교 차트")
        print("- /app/reports/performance_comparison_report.md: 상세 비교 보고서")

        # 결과 요약 출력
        print("\n=== 성능 비교 요약 ===")
        try:
            with open('/app/reports/performance_comparison_report.md', 'r', encoding='utf-8') as f:
                content = f.read()
                # 주요 지표 섹션 찾기
                if "## 주요 성능 지표" in content:
                    summary_start = content.find("## 주요 성능 지표")
                    summary_end = content.find("## ", summary_start + 1)
                    if summary_end == -1:
                        summary_end = content.find("# ", summary_start + 1)
                    if summary_end == -1:
                        summary_end = len(content)
                    summary = content[summary_start:summary_end].strip()
                    print(summary)
        except Exception as e:
            print(f"요약 출력 중 오류: {e}")

    except Exception as e:
        print(f"분석 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()