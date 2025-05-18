FROM python:3.11-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 분석 도구 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 분석 스크립트 복사
COPY performance_analyzer.py .
COPY wait_and_analyze.py .

# 결과 디렉토리 생성
RUN mkdir -p /app/reports /app/charts

# 실행
CMD ["python", "wait_and_analyze.py"]