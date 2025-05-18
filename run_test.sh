#!/bin/bash

# Python vs Go 성능 테스트 실행 스크립트 (Docker Compose)

echo "=== Python vs Go 성능 테스트 환경 구성 (Confluent Kafka) ==="

# 결과 디렉토리 생성
mkdir -p reports charts

# Docker 이미지 빌드 및 서비스 시작
echo "1. Docker 이미지 빌드 및 서비스 시작..."
docker compose down  # 기존 서비스 정리
docker compose build  # 이미지 빌드
docker compose up

echo ""
echo "=== 테스트 완료 ==="
echo "결과 확인:"
echo "- reports/python_performance_report.json: Python 성능 결과"
echo "- reports/go_performance_report.json: Go 성능 결과"
echo "- charts/performance_comparison.png: 성능 비교 차트"
echo "- reports/performance_comparison_report.md: 상세 비교 보고서"

echo ""
echo "주요 개선사항:"
echo "- 완전히 동등한 테스트 환경: 5의 배수 초에 동시 시작"
echo "- 전체 업비트 마켓 구독: 모든 거래쌍 테스트"
echo "- 업비트 API 제한 준수: 초당 5개 WebSocket 연결"
echo "- Confluent Kafka 사용: librdkafka 기반 공정한 비교"