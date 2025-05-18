# Python vs Go 성능 비교: Upbit WebSocket to Kafka (Docker 통합 환경)

업비트 웹소켓을 통해 실시간 거래 데이터를 받아서 Kafka로 전송하는 시나리오에서 Python과 Go의 성능을 비교하는 프로젝트입니다. **완전히 동등한 테스트 환경**을 보장하기 위해 Docker Compose로 모든 서비스를 통합 실행합니다.

## 🎯 테스트 목표

- **완전히 동등한 환경**: 10의 배수 초에 동시 시작으로 정확한 비교
- **전체 마켓 테스트**: 업비트의 모든 거래쌍 (KRW, BTC, USDT 등) 구독
- **API 제한 준수**: 업비트 연결 제한을 준수한 안정적인 WebSocket 연결
- **공정한 비교**: 동일한 librdkafka 기반 confluent-kafka 사용
- **정확한 시간 측정**: 정확히 60초 동안만 데이터 수집하여 비교

## 📁 프로젝트 구조

```
.
├── docker-compose.yml              # 전체 서비스 통합 설정
├── README.md                      # 이 파일
├── py/                           # Python 프로듀서
│   ├── python_upbit_kafka.py     # Python 구현체 (동기화 개선)
│   ├── requirements.txt          # Python 의존성
│   └── Dockerfile               # Python Docker 이미지
├── go/                          # Go 프로듀서  
│   ├── go_upbit_kafka.go        # Go 구현체 (동기화 개선)
│   ├── go.mod                   # Go 모듈 설정
│   └── Dockerfile               # Go Docker 이미지
├── analyzer/                    # 성능 분석기
│   ├── performance_analyzer.py  # 성능 분석 로직
│   ├── wait_and_analyze.py      # 분석 실행 스크립트
│   ├── requirements.txt          # 분석 도구 의존성
│   └── Dockerfile               # 분석기 Docker 이미지
└── reports/                     # 생성된 보고서 (자동 생성)
    ├── python_performance_report.json
    ├── go_performance_report.json
    └── performance_comparison_report.md
```

## 🛠 전제 조건

- Docker & Docker Compose
- 충분한 시스템 리소스 (CPU 4코어+, 메모리 8GB+ 권장)
- 안정적인 인터넷 연결 (업비트 WebSocket API 접속용)

> **참고**: librdkafka는 Docker 이미지 내에서 자동으로 설치되므로 호스트에 별도 설치가 불필요합니다.

## 🚀 빠른 시작

### 1. 전체 테스트 실행

```bash
# Docker Compose로 모든 서비스 시작
docker-compose up --build

# 또는 백그라운드에서 실행
docker-compose up --build -d

# 로그 실시간 모니터링
docker-compose logs -f python-producer go-producer
```

이 명령으로 다음이 모두 자동 실행됩니다:
1. Python과 Go 프로듀서 동시 빌드
2. 안정적인 WebSocket 연결 생성 (API 제한 준수)
3. 10의 배수 초에 동기화된 데이터 수집 시작
4. 정확히 60초 동안 성능 측정
5. 성능 분석 및 비교 보고서 자동 생성

### 2. 개별 서비스 제어 (선택사항)

```bash
# 특정 서비스만 실행
docker-compose up python-producer
docker-compose up go-producer

# 서비스 중지
docker-compose down

# 볼륨까지 정리
docker-compose down -v

# 이미지 재빌드 (코드 변경 시)
docker-compose build --no-cache
```

## 📊 테스트 특징

### 개선된 동기화 시스템
- **완벽한 시간 동기화**: WebSocket 연결 완료 후 다음 10의 배수 초(0초, 10초, 20초...)에 동시 시작
- **정확한 측정 시간**: 연결 시간과 데이터 수집 시간을 분리하여 정확히 60초만 측정
- **동일한 데이터**: 같은 시점의 동일한 업비트 데이터 수신
- **실시간 진행률**: 10초마다 진행 상황과 성능 지표 출력

### 안정적인 WebSocket 연결 전략
- **마켓 분할**: 15개 마켓당 1개 WebSocket 연결 (안정성 향상)
- **연결 제한 준수**: 2개 연결마다 2초 대기 (업비트 API 제한 준수)
- **전체 커버**: 모든 거래쌍(KRW-*, BTC-*, USDT-*, ETH-*) 포함
- **연결 복구**: 연결 실패 시 자동 재시도 (최대 3회)

### 상세한 성능 측정
1. **처리량**: 초당 메시지 수 (정확한 60초 기준)
2. **총 메시지 수**: 테스트 기간 중 처리한 전체 메시지
3. **전송 성공률**: Kafka 전송 성공/실패 비율
4. **지연시간 분석**:
    - WebSocket 연결 시간
    - 메시지 처리 시간
    - Kafka 전송 시간
    - P95/P99 지연시간
5. **메모리 사용량**: 평균/최대/최소 메모리 사용량 (시스템 + 추적 메모리)
6. **시간 정확도**: 목표 60초와 실제 측정 시간의 차이

## 📋 생성되는 출력 파일

테스트 완료 후 다음 파일들이 자동 생성됩니다:

```
reports/
├── python_performance_report.json     # Python 상세 성능 데이터
├── go_performance_report.json         # Go 상세 성능 데이터  
└── performance_comparison_report.md   # 자동 생성된 비교 분석 보고서

charts/ (analyzer 서비스 실행 시)
└── performance_comparison.png         # 성능 비교 시각화 차트
```

## 🔧 설정 커스터마이징

### 테스트 시간 변경
```yaml
# docker-compose.yml에서
environment:
  - TEST_DURATION=120  # 120초로 변경
```

### Kafka 브로커 변경
```yaml
# docker-compose.yml에서
environment:
  - KAFKA_BOOTSTRAP_SERVERS=your-kafka-server:9092
```

### 동일한 Kafka 최적화 설정
두 언어의 프로듀서 모두 동일한 최적화 설정을 사용합니다:
- 배치 크기: 32KB
- Linger 시간: 10ms
- 압축: Snappy
- ACK 설정: all (최대 신뢰성)
- 멱등성: 활성화

## 🐛 문제 해결

### WebSocket 연결 실패
```bash
# 1. 네트워크 연결 확인
ping api.upbit.com

# 2. 로그 확인으로 원인 파악
docker-compose logs python-producer
docker-compose logs go-producer

# 3. 컨테이너 재시작
docker-compose restart python-producer go-producer
```

### Kafka 연결 오류
```bash
# Kafka 브로커 상태 확인
docker-compose logs kafka

# Kafka 토픽 확인 (kafka-ui 사용 시)
# http://localhost:8080 접속
```

### 메모리 부족 문제
```bash
# Docker Desktop 메모리 할당 증가 (8GB+)
# 또는 설정에서 테스트 시간 단축
# docker-compose.yml에서 TEST_DURATION=30
```

### 동기화 문제
- 두 프로듀서가 다른 시간에 시작: 정상 동작 (웹소켓 연결 완료 시점이 다름)
- 데이터 수집은 동일한 10의 배수 초에 시작: 로그에서 "데이터 수집 시작" 시간 확인

## 📈 예상 성능 차이

일반적으로 다음과 같은 결과를 기대할 수 있습니다:

| 항목 | Go | Python | 비고 |
|------|-----|--------|------|
| **처리량** | 1,500-3,000 msg/s | 800-1,500 msg/s | Go가 1.5-2배 높음 |
| **메모리 사용량** | 20-50MB | 40-120MB | Go가 약 1/2-1/3 수준 |
| **지연시간 (P95)** | 1-5ms | 3-10ms | Go가 전반적으로 낮음 |
| **전송 성공률** | 99.9%+ | 99.9%+ | 두 언어 모두 높은 안정성 |
| **WebSocket 연결** | 20-30개 | 20-30개 | 동일 (전체 마켓 커버) |

> **참고**: 실제 결과는 시스템 환경, 네트워크 상태, 시장 활동 수준에 따라 달라질 수 있습니다.

## 📊 성능 분석 포인트

### Python 최적화 기법
- asyncio 기반 비동기 처리
- confluent-kafka의 효율적인 배치 처리
- 적절한 백프레셔 제어로 메모리 사용량 최적화
- WebSocket 연결 풀링

### Go 최적화 기법
- 고루틴 기반 경량 동시성
- 가비지 컬렉션 최적화
- 네이티브 성능의 librdkafka 바인딩
- 효율적인 메모리 관리

## 🔍 모니터링 및 디버깅

### 실시간 로그 모니터링
```bash
# 전체 로그
docker-compose logs -f

# 특정 서비스만
docker-compose logs -f python-producer

# 에러만 필터링
docker-compose logs python-producer 2>&1 | grep -i error
```

### 성능 지표 확인
- 로그에서 5초마다 출력되는 실시간 메트릭 확인
- 10초마다 출력되는 진행률 확인
- 메시지 수, 처리율, 메모리 사용량 모니터링

## 📚 기술적 세부사항

### WebSocket 연결 관리
- 연결당 15개 마켓 구독 (안정성과 성능의 균형)
- ping/pong을 통한 연결 유지 (20초 간격)
- 연결 실패 시 지수 백오프로 재시도

### Kafka 프로듀서 설정
- 큐 버퍼링: 100만 메시지 또는 1GB
- 압축: Snappy (성능과 압축률의 균형)
- 멱등성: 활성화 (정확히 한 번 전송)
- 재시도: 3회 (네트워크 오류 대응)

## 📚 참고 자료

- [업비트 API 문서](https://docs.upbit.com/reference/websocket-ticker)
- [Confluent Kafka Documentation](https://docs.confluent.io/)
- [confluent-kafka-python](https://github.com/confluentinc/confluent-kafka-python)
- [confluent-kafka-go](https://github.com/confluentinc/confluent-kafka-go)
- [Docker Compose 문서](https://docs.docker.com/compose/)

## 📄 라이선스

MIT License

---

**최신 개선사항 (v2.0):**
- ✅ 10의 배수 초 정확한 동기화
- ✅ 안정적인 WebSocket 연결 전략 (2개/2초)
- ✅ 정확한 60초 데이터 수집 시간 측정
- ✅ 향상된 에러 핸들링 및 재시도 로직
- ✅ 상세한 성능 메트릭 (P95/P99 지연시간)
- ✅ 실시간 진행률 및 성능 모니터링
- ✅ 개선된 메모리 추적 (system + traced memory)