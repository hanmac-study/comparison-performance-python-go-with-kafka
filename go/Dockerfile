FROM golang:1.21-alpine AS builder

# 빌드 의존성 설치
RUN apk add --no-cache \
    build-base \
    pkgconfig \
    librdkafka-dev

WORKDIR /app

# Go 모듈 의존성 복사 및 다운로드
COPY go.mod go.sum* ./
RUN go mod download

# 소스 코드 복사
COPY go_upbit_kafka.go .

# 빌드
RUN CGO_ENABLED=1 GOOS=linux go build -a -installsuffix cgo -o main .

# 실행 이미지
FROM alpine:latest

# 런타임 의존성 설치
RUN apk add --no-cache \
    librdkafka-dev \
    ca-certificates \
    tzdata

WORKDIR /app

# 빌드된 바이너리 복사
COPY --from=builder /app/main .

# 결과 디렉토리 생성
RUN mkdir -p /app/reports

# 실행
CMD ["./main"]