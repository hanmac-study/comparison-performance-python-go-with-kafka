# Python vs Go 성능 비교: Upbit WebSocket to Kafka (Docker 통합 환경)

업비트 웹소켓을 통해 실시간 거래 데이터를 받아서 Kafka로 전송하는 시나리오에서 Python과 Go의 성능을 비교하는 프로젝트입니다. **완전히 동등한 테스트 환경**을 보장하기 위해 Docker Compose로 모든 서비스를 통합 실행합니다.

## 🎯 테스트 목표

- **완전히 동등한 환경**: 5의 배수 초에 동시 시작으로 정확한 비교
- **전체 마켓 테스트**: 업비트의 모든 거래쌍 (KRW, BTC, USDT 등) 구독
- **API 제한 준수**: 업비트 초당 5개 연결 제한을 준수한 WebSocket 연결
- **공정한 비교**: 동일한 librdkafka 기반 confluent-kafka 사용

## 📁 프로젝트 구조

```
.
├── docker-compose.yml              # 전체 서비스 통합 설정
├── run_tests.sh                   # 테스트 실행 스크립트
├── README.md                      # 이 파일
├── py/                           # Python 프로듀서
│   ├── python_upbit_kafka.py     # Python 구현체
│   ├── requirements.txt          # Python 의존성
│   └── Dockerfile               # Python Docker 이미지
├── go/                          # Go 프로듀서
│   ├── go_upbit_kafka.go        # Go 구현체
│   ├── go.mod                   # Go 모듈 설정
│   └── Dockerfile               # Go Docker 이미지
└── analyzer/                    # 성능 분석기
    ├── performance_analyzer.py  # 성능 분석 로직
    ├── wait_and_analyze.py      # 분석 실행 스크립트
    ├── requirements.txt          # 분석 도구 의존성
    └── Dockerfile               # 분석기 Docker 이미지
```

## 🛠 전제 조건

- Docker & Docker Compose
- 충분한 시스템 리소스 (CPU 4코어+, 메모리 8GB+ 권장)

> **참고**: librdkafka는 Docker 이미지 내에서 자동으로 설치되므로 호스트에 별도 설치가 불필요합니다.

## 🚀 빠른 시작

### 1. 저장소 클론 및 권한 설정

```bash
# 실행 권한 부여
chmod +x run_tests.sh
```

### 2. 전체 테스트 실행

```bash
./run_tests.sh
```

이 명령으로 다음이 모두 자동 실행됩니다:
1. Kafka/Zookeeper 시작
2. Python과 Go 프로듀서 동시 실행
3. 성능 분석 및 보고서 생성

### 3. 개별 서비스 제어 (선택사항)

```bash
# 서비스 빌드
docker-compose build

# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 중지
docker-compose down
```

## 📊 테스트 특징

### 동등한 테스트 환경
- **시간 동기화**: 두 프로듀서가 5의 배수 초(5초, 10초, 15초...)에 동시 시작
- **동일한 데이터**: 같은 시점의 동일한 업비트 데이터 수신
- **동일한 인프라**: 동일한 Kafka 클러스터 사용

### 전체 마켓 구독 전략
- **마켓 분할**: 20개 마켓당 1개 WebSocket 연결
- **연결 제한 준수**: 초당 5개 연결 생성 (업비트 API 제한)
- **전체 커버**: 모든 거래쌍(KRW-*, BTC-*, USDT-*, ETH-*) 포함

### 성능 측정 항목
1. **처리량**: 초당 메시지 수
2. **총 메시지 수**: 테스트 기간 중 처리한 전체 메시지
3. **메시지 전송 성공률**: Kafka 전송 성공/실패 비율
4. **지연시간**: 메시지 처리, Kafka 전송, WebSocket 연결 시간
5. **메모리 사용량**: 평균/최대/최소 메모리 사용량
6. **WebSocket 연결 수**: 실제 생성된 연결 개수

## 📋 출력 파일

테스트 완료 후 다음 파일들이 생성됩니다:

```
reports/
├── python_performance_report.json     # Python 상세 성능 데이터
├── go_performance_report.json         # Go 상세 성능 데이터
└── performance_comparison_report.md   # 비교 분석 보고서

charts/
└── performance_comparison.png         # 성능 비교 시각화 차트
```

## 🔧 설정 커스터마이징

### 테스트 시간 변경
```yaml
# docker-compose.yml에서
environment:
  - TEST_DURATION=120  # 120초로 변경
```

### Kafka 최적화 설정
두 언어의 프로듀서 모두 동일한 최적화 설정을 사용합니다:
- 배치 크기: 32KB
- Linger 시간: 10ms
- 압축: Snappy
- 멱등성: 활성화

## 🐛 문제 해결

### Docker 관련 오류
```bash
# 이미지 재빌드
docker-compose build --no-cache

# 볼륨 정리
docker-compose down -v
docker system prune
```

### 메모리 부족
```bash
# Docker Desktop 메모리 할당 증가 (8GB+)
# 또는 테스트 시간 단축
```

### WebSocket 연결 실패
- 네트워크 연결 상태 확인
- 업비트 API 상태 확인
- 방화벽 설정 확인 (WSS 포트 443)

## 📈 예상 성능 차이

일반적으로 다음과 같은 결과를 기대할 수 있습니다:

- **처리량**: Go가 Python보다 1.5-3배 높은 처리량
- **메모리 사용량**: Go가 Python의 1/3-1/2 수준
- **지연시간**: Go가 전반적으로 낮은 지연시간
- **안정성**: 두 언어 모두 99%+ 전송 성공률

실제 결과는 시스템 환경과 네트워크 상태에 따라 달라질 수 있습니다.

## 📝 성능 최적화 포인트

### Python 최적화
- asyncio 기반 비동기 처리
- confluent-kafka의 배치 처리
- 적절한 백프레셔 제어

### Go 최적화
- 고루틴 기반 동시성
- 효율적인 메모리 풀링
- 네이티브 성능의 librdkafka

## 📚 참고 자료

- [업비트 API 문서](https://docs.upbit.com/reference/websocket-ticker)
- [Confluent Kafka Documentation](https://docs.confluent.io/)
- [confluent-kafka-python](https://github.com/confluentinc/confluent-kafka-python)
- [confluent-kafka-go](https://github.com/confluentinc/confluent-kafka-go)
- [Docker Compose 문서](https://docs.docker.com/compose/)

## 📄 라이선스

MIT License

---

**주요 개선사항:**
- ✅ 완전히 동등한 테스트 환경
- ✅ 전체 업비트 마켓 구독
- ✅ API 제한 준수 연결 전략
- ✅ Docker 통합 환경
- ✅ 자동화된 분석 및 보고서