FROM python:3.11-slim

# 필요한 패키지 설치
RUN apt-get update && \
    apt-get install -y \
    fonts-nanum \
    fonts-nanum-coding \
    fonts-nanum-extra \
    fontconfig && \
    rm -rf /var/lib/apt/lists/*

# 폰트 캐시 업데이트
RUN fc-cache -f -v

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