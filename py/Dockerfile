FROM python:3.11-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY python_upbit_kafka.py .

# 결과 디렉토리 생성
RUN mkdir -p /app/reports

# 실행
CMD ["python", "python_upbit_kafka.py"]