import asyncio
import websockets
import json
import time
import threading
import os
from collections import defaultdict
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from typing import Dict, List
import statistics
import psutil
import tracemalloc
import math


class PerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(list)
        self.start_times = {}
        self.memory_usage = []
        self.cpu_usage = []
        self.lock = threading.Lock()

    def start_timer(self, operation: str):
        with self.lock:
            self.start_times[operation] = time.perf_counter()

    def end_timer(self, operation: str):
        with self.lock:
            if operation in self.start_times:
                elapsed = time.perf_counter() - self.start_times[operation]
                self.metrics[operation].append(elapsed)
                del self.start_times[operation]

    def record_system_metrics(self):
        # 메모리 사용량 (MB)
        memory = psutil.Process().memory_info().rss / 1024 / 1024
        self.memory_usage.append(memory)

        # CPU 사용률
        cpu = psutil.Process().cpu_percent()
        self.cpu_usage.append(cpu)

    def get_report(self) -> Dict:
        with self.lock:
            report = {}
            for operation, times in self.metrics.items():
                if times:
                    report[operation] = {
                        'count': len(times),
                        'avg_ms': statistics.mean(times) * 1000,
                        'min_ms': min(times) * 1000,
                        'max_ms': max(times) * 1000,
                        'p95_ms': statistics.quantiles(times, n=20)[18] * 1000 if len(times) > 1 else times[0] * 1000,
                        'p99_ms': statistics.quantiles(times, n=100)[98] * 1000 if len(times) > 1 else times[0] * 1000
                    }

            if self.memory_usage:
                report['memory'] = {
                    'avg_mb': statistics.mean(self.memory_usage),
                    'max_mb': max(self.memory_usage),
                    'min_mb': min(self.memory_usage)
                }

            if self.cpu_usage:
                report['cpu'] = {
                    'avg_percent': statistics.mean(self.cpu_usage),
                    'max_percent': max(self.cpu_usage)
                }

            return report


class UpbitKafkaProducer:
    def __init__(self, kafka_bootstrap_servers: str, topic: str, producer_id: str):
        # Confluent Kafka Producer 설정
        self.producer_config = {
            'bootstrap.servers': kafka_bootstrap_servers,
            'client.id': f'upbit-{producer_id}-producer',
            # 성능 최적화 설정
            'batch.size': 32768,
            'linger.ms': 10,
            'compression.type': 'snappy',
            'acks': "all",  # 성능 우선을 위해 1로 설정
            'retries': 3,
            'max.in.flight.requests.per.connection': 5,
            'enable.idempotence': True,  # 단순화를 위해 비활성화
            # 처리량 최적화
            'queue.buffering.max.messages': 1000000,
            'queue.buffering.max.kbytes': 1048576,
        }

        self.kafka_producer = Producer(self.producer_config)
        self.topic = topic
        self.producer_id = producer_id
        self.monitor = PerformanceMonitor()
        self.message_count = 0
        self.running = True
        self.delivery_reports = {'success': 0, 'error': 0}
        self.websocket_connections = []

        # 토픽 생성 확인
        self._ensure_topic_exists()

        # 시스템 메트릭 모니터링 스레드
        self.monitor_thread = threading.Thread(target=self._monitor_system)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        # 메시지 delivery report 처리 스레드
        self.delivery_thread = threading.Thread(target=self._poll_delivery_reports)
        self.delivery_thread.daemon = True
        self.delivery_thread.start()

    def _ensure_topic_exists(self):
        """토픽이 존재하는지 확인하고 없으면 생성"""
        admin_config = {
            'bootstrap.servers': self.producer_config['bootstrap.servers']
        }
        admin_client = AdminClient(admin_config)

        # 토픽 메타데이터 조회
        metadata = admin_client.list_topics(timeout=10)
        if self.topic not in metadata.topics:
            print(f"[{self.producer_id}] 토픽 '{self.topic}'을 생성합니다...")
            new_topic = NewTopic(
                topic=self.topic,
                num_partitions=6,
                replication_factor=1
            )
            futures = admin_client.create_topics([new_topic])

            # 토픽 생성 대기
            for topic, future in futures.items():
                try:
                    future.result()
                    print(f"[{self.producer_id}] 토픽 '{topic}' 생성 완료")
                except Exception as e:
                    print(f"[{self.producer_id}] 토픽 생성 오류: {e}")

    def _poll_delivery_reports(self):
        """메시지 delivery report 폴링"""
        while self.running:
            try:
                self.kafka_producer.poll(0.1)
            except Exception as e:
                print(f"[{self.producer_id}] Poll 오류: {e}")

    def _monitor_system(self):
        while self.running:
            self.monitor.record_system_metrics()
            time.sleep(0.5)

    def _delivery_callback(self, err, msg):
        """Kafka 메시지 전송 결과 콜백"""
        if err is not None:
            self.delivery_reports['error'] += 1
            print(f"[{self.producer_id}] 메시지 전송 실패: {err}")
        else:
            self.delivery_reports['success'] += 1

    def wait_for_next_interval(self):
        """다음 5의 배수 초까지 대기"""
        current_time = time.time()
        current_second = int(current_time) % 60

        # 다음 5의 배수 초 계산
        next_interval = ((current_second // 5) + 1) * 5
        if next_interval >= 60:
            next_interval = 0
            target_time = math.ceil(current_time / 60) * 60
        else:
            target_time = math.floor(current_time / 60) * 60 + next_interval

        wait_time = target_time - current_time
        if wait_time > 0:
            print(f"[{self.producer_id}] 다음 시작 시점까지 {wait_time:.2f}초 대기...")
            time.sleep(wait_time)

        actual_start = time.time()
        print(f"[{self.producer_id}] 테스트 시작 시간: {actual_start:.3f} (초: {int(actual_start) % 60})")
        return actual_start

    async def get_all_markets(self):
        """전체 마켓 목록 조회"""
        self.monitor.start_timer('get_markets')
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.upbit.com/v1/market/all') as response:
                    markets = await response.json()
                    all_markets = [market['market'] for market in markets]
                    return all_markets
        finally:
            self.monitor.end_timer('get_markets')

    async def send_to_kafka(self, message: dict):
        """Kafka에 메시지 전송"""
        self.monitor.start_timer('kafka_send')
        try:
            # 메시지를 JSON 문자열로 변환
            message_json = json.dumps(message, ensure_ascii=False)

            # Kafka로 비동기 전송
            self.kafka_producer.produce(
                topic=self.topic,
                value=message_json,
                callback=self._delivery_callback
            )

            self.message_count += 1

            # 주기적으로 큐 플러시 (백프레셔 방지)
            if self.message_count % 1000 == 0:
                self.kafka_producer.poll(0)

        except Exception as e:
            print(f"[{self.producer_id}] Kafka 전송 오류: {e}")
        finally:
            self.monitor.end_timer('kafka_send')

    async def create_websocket_connection(self, markets_chunk: List[str], connection_index: int):
        """개별 웹소켓 연결 생성 및 관리"""
        url = "wss://api.upbit.com/websocket/v1"

        # 구독 메시지 생성
        subscribe_message = [
            {"ticket": f"test-{self.producer_id}-{connection_index}"},
            {
                "type": "ticker",
                "codes": markets_chunk,
                "isOnlyRealtime": True
            }
        ]

        retry_count = 0
        max_retries = 3

        while self.running and retry_count < max_retries:
            try:
                self.monitor.start_timer(f'websocket_connection_{connection_index}')
                async with websockets.connect(
                        url,
                        ping_interval=20,
                        ping_timeout=10,
                        close_timeout=10
                ) as websocket:
                    self.monitor.end_timer(f'websocket_connection_{connection_index}')

                    # 구독 메시지 전송
                    await websocket.send(json.dumps(subscribe_message))
                    print(f"[{self.producer_id}] 연결 #{connection_index}: {len(markets_chunk)}개 마켓 구독 완료")

                    # 연결 정보 저장
                    self.websocket_connections.append({
                        'index': connection_index,
                        'markets': markets_chunk,
                        'connected_at': time.time()
                    })

                    async for message in websocket:
                        if not self.running:
                            break

                        self.monitor.start_timer('message_processing')
                        try:
                            # 메시지 파싱
                            data = json.loads(message)

                            # 메타데이터 추가
                            data['received_at'] = time.time()
                            data['message_id'] = self.message_count
                            data['producer_type'] = f'python-confluent'
                            data['producer_id'] = self.producer_id
                            data['connection_index'] = connection_index

                            # Kafka에 전송
                            await self.send_to_kafka(data)

                        except Exception as e:
                            print(f"[{self.producer_id}] 메시지 처리 오류: {e}")
                        finally:
                            self.monitor.end_timer('message_processing')

            except Exception as e:
                retry_count += 1
                print(f"[{self.producer_id}] 연결 #{connection_index} 오류 (재시도 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(5)

    async def connect_all_websockets(self, markets: List[str]):
        """모든 마켓에 대한 웹소켓 연결 생성"""
        # 마켓을 20개씩 청크로 분할
        markets_per_connection = 20
        market_chunks = [
            markets[i:i + markets_per_connection]
            for i in range(0, len(markets), markets_per_connection)
        ]

        print(f"[{self.producer_id}] 총 {len(markets)}개 마켓을 {len(market_chunks)}개 연결로 분할")
        print(f"[{self.producer_id}] 업비트 API 제한에 따라 1초당 5개 연결씩 생성")

        # 연결을 5개씩 묶어서 1초 간격으로 생성
        connections_per_batch = 3
        connection_tasks = []

        for batch_index in range(0, len(market_chunks), connections_per_batch):
            batch_chunks = market_chunks[batch_index:batch_index + connections_per_batch]

            # 배치 내 연결들을 동시에 시작
            batch_tasks = []
            for chunk_index, chunk in enumerate(batch_chunks):
                connection_index = batch_index + chunk_index
                task = asyncio.create_task(
                    self.create_websocket_connection(chunk, connection_index)
                )
                batch_tasks.append(task)

            connection_tasks.extend(batch_tasks)

            # 다음 배치 전에 1초 대기 (마지막 배치가 아닌 경우)
            if batch_index + connections_per_batch < len(market_chunks):
                print(f"[{self.producer_id}] 다음 배치까지 1초 대기...")
                await asyncio.sleep(1)

        # 모든 연결 작업을 백그라운드에서 실행
        await asyncio.gather(*connection_tasks, return_exceptions=True)

    async def run(self, duration_seconds: int = 60):
        """테스트 실행"""
        # 5의 배수 초까지 대기
        start_time = self.wait_for_next_interval()

        tracemalloc.start()

        print(f"[{self.producer_id}] 전체 마켓 목록을 가져오는 중...")
        markets = await self.get_all_markets()
        krw_markets = [market for market in markets if market.startswith('KRW-')]
        print(f"[{self.producer_id}] 총 {len(markets)}개 마켓 발견 (KRW: {len(krw_markets)}개)")

        print(f"[{self.producer_id}] 전체 마켓 WebSocket 연결을 시작합니다...")

        # duration_seconds 후에 종료
        async def stop_after_duration():
            await asyncio.sleep(duration_seconds)
            self.running = False
            print(f"[{self.producer_id}] 테스트 시간 종료")

        # WebSocket 연결과 타이머를 동시에 실행
        await asyncio.gather(
            self.connect_all_websockets(markets),
            stop_after_duration()
        )

        # Kafka producer 정리
        print(f"[{self.producer_id}] 메시지 플러시 중...")
        self.kafka_producer.flush(timeout=10)

        # 메모리 사용량 측정
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 성능 보고서 생성
        elapsed_time = time.time() - start_time
        report = self.monitor.get_report()
        report['test_info'] = {
            'producer_id': self.producer_id,
            'start_time': start_time,
            'total_runtime_seconds': elapsed_time,
            'total_messages': self.message_count,
            'messages_per_second': self.message_count / elapsed_time,
            'total_markets': len(markets),
            'krw_markets': len(krw_markets),
            'websocket_connections': len(self.websocket_connections)
        }
        report['memory_traced'] = {
            'current_mb': current / 1024 / 1024,
            'peak_mb': peak / 1024 / 1024
        }
        report['delivery_reports'] = self.delivery_reports
        report['kafka_config'] = {
            'library': 'confluent-kafka-python',
            'batch_size': self.producer_config['batch.size'],
            'linger_ms': self.producer_config['linger.ms'],
            'compression': self.producer_config['compression.type']
        }
        report['websocket_info'] = {
            'connections': self.websocket_connections,
            'markets_per_connection': 20,
            'connection_rate_limit': 5  # per second
        }

        return report

    def stop(self):
        self.running = False
        if hasattr(self, 'kafka_producer'):
            self.kafka_producer.flush(timeout=5)


async def main():
    # 환경 변수에서 설정 읽기
    KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    TOPIC = os.getenv('KAFKA_TOPIC', 'upbit-krw-ticker')
    TEST_DURATION = int(os.getenv('TEST_DURATION', '60'))
    PRODUCER_ID = os.getenv('PRODUCER_ID', 'python')

    producer = UpbitKafkaProducer(KAFKA_SERVERS, TOPIC, PRODUCER_ID)

    try:
        print(f"[{PRODUCER_ID}] {TEST_DURATION}초 동안 성능 테스트를 시작합니다...")
        print(f"[{PRODUCER_ID}] 사용 라이브러리: confluent-kafka-python")
        report = await producer.run(TEST_DURATION)

        print(f"\n=== {PRODUCER_ID.upper()} (Confluent Kafka) 성능 테스트 결과 ===")
        print(json.dumps(report, indent=2, ensure_ascii=False))

        # 결과를 파일로 저장
        report_path = f'/app/reports/{PRODUCER_ID}_performance_report.json'
        os.makedirs('/app/reports', exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"[{PRODUCER_ID}] 성공한 메시지: {report['delivery_reports']['success']}")
        print(f"[{PRODUCER_ID}] 실패한 메시지: {report['delivery_reports']['error']}")
        print(f"[{PRODUCER_ID}] 보고서 저장: {report_path}")

    except KeyboardInterrupt:
        print(f"\n[{PRODUCER_ID}] 테스트가 중단되었습니다.")
        producer.stop()
    except Exception as e:
        print(f"[{PRODUCER_ID}] 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())