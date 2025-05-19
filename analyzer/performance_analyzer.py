import json
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import shutil
import datetime
from typing import Dict, Any


class PerformanceAnalyzer:
    def __init__(self, python_report_path: str, go_report_path: str):
        with open(python_report_path, 'r', encoding='utf-8') as f:
            self.python_report = json.load(f)

        with open(go_report_path, 'r', encoding='utf-8') as f:
            self.go_report = json.load(f)

    def compare_metrics(self):
        """주요 성능 지표 비교"""
        comparison = {}

        # 메시지 처리 성능 (새로운 구조에 맞게 수정)
        python_test_info = self.python_report.get('test_info', {})
        go_test_info = self.go_report.get('test_info', {})

        comparison['throughput'] = {
            'Python (msg/sec)': python_test_info.get('messages_per_second', 0),
            'Go (msg/sec)': go_test_info.get('messages_per_second', 0)
        }

        # 총 메시지 수
        comparison['total_messages'] = {
            'Python': python_test_info.get('total_messages', 0),
            'Go': go_test_info.get('total_messages', 0)
        }

        # WebSocket 연결 수
        comparison['websocket_connections'] = {
            'Python': python_test_info.get('websocket_connections', 0),
            'Go': go_test_info.get('websocket_connections', 0)
        }

        # 전체 마켓 수
        comparison['total_markets'] = {
            'Python': python_test_info.get('total_markets', 0),
            'Go': go_test_info.get('total_markets', 0)
        }

        # 메모리 사용량
        if 'memory' in self.python_report and 'memory' in self.go_report:
            comparison['memory'] = {
                'Python (MB)': self.python_report['memory']['avg_mb'],
                'Go (MB)': self.go_report['memory']['avg_mb']
            }

        # 각 작업별 성능 비교
        operations = ['message_processing', 'kafka_send', 'websocket_connection']
        for op in operations:
            if op in self.python_report and op in self.go_report:
                comparison[f'{op}_latency'] = {
                    'Python (ms)': self.python_report[op]['avg_ms'],
                    'Go (ms)': self.go_report[op]['avg_ms']
                }

                comparison[f'{op}_p95'] = {
                    'Python (ms)': self.python_report[op]['p95_ms'],
                    'Go (ms)': self.go_report[op]['p95_ms']
                }

        return comparison

    def create_visualizations(self):
        """성능 비교 시각화"""
        import matplotlib.font_manager as fm

        # 폰트 설정
        plt.rcParams['font.family'] = 'NanumGothic'
        plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

        # 폰트가 제대로 설정되었는지 확인
        font_list = [f.name for f in fm.fontManager.ttflist]
        if 'NanumGothic' not in font_list:
            # 나눔고딕이 없으면 기본 폰트 사용
            print("Warning: NanumGothic font not found. Using default font.")
            plt.rcParams['font.family'] = 'DejaVu Sans'

        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('Python vs Go Performance Comparison (Confluent Kafka)', fontsize=16, fontweight='bold')

        # 새로운 구조에서 데이터 추출
        python_test_info = self.python_report.get('test_info', {})
        go_test_info = self.go_report.get('test_info', {})

        # 1. 처리량 비교
        ax1 = axes[0, 0]
        throughput_data = [
            python_test_info.get('messages_per_second', 0),
            go_test_info.get('messages_per_second', 0)
        ]
        bars1 = ax1.bar(['Python', 'Go'], throughput_data, color=['#3776ab', '#00ADD8'])
        ax1.set_ylabel('Messages per Second')
        ax1.set_title('Throughput Comparison')


        # 값 표시
        for bar, value in zip(bars1, throughput_data):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + value*0.01,
                    f'{value:.1f}', ha='center', va='bottom')

        # 2. 총 메시지 수 비교
        ax2 = axes[0, 1]
        total_messages_data = [
            python_test_info.get('total_messages', 0),
            go_test_info.get('total_messages', 0)
        ]
        bars2 = ax2.bar(['Python', 'Go'], total_messages_data, color=['#3776ab', '#00ADD8'])
        ax2.set_ylabel('Total Messages')
        ax2.set_title('Total Messages')

        # 값 표시
        for bar, value in zip(bars2, total_messages_data):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + value*0.01,
                    f'{value:,}', ha='center', va='bottom')

        # 3. 메모리 사용량 비교
        ax3 = axes[0, 2]
        if 'memory' in self.python_report and 'memory' in self.go_report:
            memory_data = [
                self.python_report['memory']['avg_mb'],
                self.go_report['memory']['avg_mb']
            ]
            bars3 = ax3.bar(['Python', 'Go'], memory_data, color=['#3776ab', '#00ADD8'])
            ax3.set_ylabel('Memory Usage (MB)')
            ax3.set_title('Avg. Memory Usage')

            # 값 표시
            for bar, value in zip(bars3, memory_data):
                ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + value*0.01,
                        f'{value:.1f}', ha='center', va='bottom')

        # 4. 메시지 처리 지연시간 비교
        ax4 = axes[1, 0]
        if 'message_processing' in self.python_report and 'message_processing' in self.go_report:
            latency_metrics = ['avg_ms', 'p95_ms', 'p99_ms']
            python_latencies = [self.python_report['message_processing'][metric] for metric in latency_metrics]
            go_latencies = [self.go_report['message_processing'][metric] for metric in latency_metrics]

            x = np.arange(len(latency_metrics))
            width = 0.35

            ax4.bar(x - width/2, python_latencies, width, label='Python', color='#3776ab')
            ax4.bar(x + width/2, go_latencies, width, label='Go', color='#00ADD8')

            ax4.set_ylabel('Latency (ms)')
            ax4.set_title('Message Processing Latency')
            ax4.set_xticks(x)
            ax4.set_xticklabels(['Avg', 'P95', 'P99'])
            ax4.legend()

        # 5. Kafka 전송 지연시간 비교
        ax5 = axes[1, 1]
        if 'kafka_send' in self.python_report and 'kafka_send' in self.go_report:
            kafka_metrics = ['avg_ms', 'p95_ms', 'p99_ms']
            python_kafka = [self.python_report['kafka_send'][metric] for metric in kafka_metrics]
            go_kafka = [self.go_report['kafka_send'][metric] for metric in kafka_metrics]

            x = np.arange(len(kafka_metrics))
            width = 0.35

            ax5.bar(x - width/2, python_kafka, width, label='Python', color='#3776ab')
            ax5.bar(x + width/2, go_kafka, width, label='Go', color='#00ADD8')

            ax5.set_ylabel('Latency (ms)')
            ax5.set_title('Kafka Send Latency')
            ax5.set_xticks(x)
            ax5.set_xticklabels(['Average', 'P95', 'P99'])
            ax5.legend()

        # 6. WebSocket 연결 수 및 성공률
        ax6 = axes[1, 2]
        # WebSocket 연결 수
        connections_data = [
            python_test_info.get('websocket_connections', 0),
            go_test_info.get('websocket_connections', 0)
        ]

        # 메시지 전송 성공률
        python_delivery = self.python_report.get('delivery_reports', {})
        go_delivery = self.go_report.get('delivery_reports', {})

        python_success_rate = 0
        if python_delivery.get('success', 0) + python_delivery.get('error', 0) > 0:
            python_success_rate = python_delivery.get('success', 0) / (python_delivery.get('success', 0) + python_delivery.get('error', 0)) * 100

        go_success_rate = 0
        if go_delivery.get('success', 0) + go_delivery.get('error', 0) > 0:
            go_success_rate = go_delivery.get('success', 0) / (go_delivery.get('success', 0) + go_delivery.get('error', 0)) * 100

        # 이중 축 사용
        ax6_twin = ax6.twinx()

        # 연결 수 (막대)
        bars = ax6.bar(['Python', 'Go'], connections_data, color=['#3776ab', '#00ADD8'], alpha=0.7, label='WebSocket Connections')
        ax6.set_ylabel('WebSocket Connections', color='black')
        ax6.set_title('WebSocket Connections & Success Rate')

        # 성공률 (선)
        success_rates = [python_success_rate, go_success_rate]
        ax6_twin.plot(['Python', 'Go'], success_rates, color='red', marker='o', linewidth=2, markersize=8, label='Message Delivery Success Rate
')
        ax6_twin.set_ylabel('Message Delivery Success Rate (%)', color='red')
        ax6_twin.set_ylim([95, 100])

        # 값 표시
        for bar, value in zip(bars, connections_data):
            ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + value*0.01,
                    f'{value}', ha='center', va='bottom')

        for i, (x, y) in enumerate(zip(['Python', 'Go'], success_rates)):
            ax6_twin.text(i, y + 0.1, f'{y:.2f}%', ha='center', va='bottom', color='red')

        plt.tight_layout()
        os.makedirs('/app/charts', exist_ok=True)
        plt.savefig('/app/charts/performance_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()

    def generate_report(self):
        """상세 성능 보고서 생성"""
        comparison = self.compare_metrics()

        # 승자 결정
        winners = {}
        for metric, values in comparison.items():
            if 'latency' in metric or 'memory' in metric:
                # 낮을수록 좋음
                winner = min(values.items(), key=lambda x: x[1])
            else:
                # 높을수록 좋음
                winner = max(values.items(), key=lambda x: x[1])
            winners[metric] = winner[0].split(' ')[0]  # 언어 이름만 추출

        # Kafka 라이브러리 정보 추출
        python_kafka_lib = self.python_report.get('kafka_config', {}).get('library', 'N/A')
        go_kafka_lib = self.go_report.get('kafka_config', {}).get('library', 'N/A')

        # 메시지 전송 성공률 계산
        python_delivery = self.python_report.get('delivery_reports', {})
        go_delivery = self.go_report.get('delivery_reports', {})

        python_success_rate = 0
        if python_delivery.get('success', 0) + python_delivery.get('error', 0) > 0:
            python_success_rate = python_delivery.get('success', 0) / (python_delivery.get('success', 0) + python_delivery.get('error', 0)) * 100

        go_success_rate = 0
        if go_delivery.get('success', 0) + go_delivery.get('error', 0) > 0:
            go_success_rate = go_delivery.get('success', 0) / (go_delivery.get('success', 0) + go_delivery.get('error', 0)) * 100

        # WebSocket 연결 정보
        python_test_info = self.python_report.get('test_info', {})
        go_test_info = self.go_report.get('test_info', {})

        # CPU 정보 추출
        python_cpu_info = self.python_report.get('system_info', {}).get('cpu', 'N/A')
        go_cpu_info = self.go_report.get('system_info', {}).get('cpu', 'N/A')

        report = f"""
# Python vs Go 성능 테스트 결과 (Confluent Kafka - 전체 업비트 마켓)

## 테스트 개요
| 항목 | 내용 |
|------|------|
| **테스트 시나리오** | Upbit WebSocket을 통한 실시간 거래 데이터 수신 및 Kafka로 전송 |
| **테스트 대상** | 업비트 전체 마켓 (KRW, BTC, USDT 등 모든 거래쌍) |
| **테스트 시간** | {python_test_info.get('total_runtime_seconds', 0):.1f}초 |
| **Python Kafka 라이브러리** | {python_kafka_lib} |
| **Go Kafka 라이브러리** | {go_kafka_lib} |
| **동기화** | 5의 배수 초에 동시 시작하여 동등한 테스트 환경 보장 |

## 테스트 환경
| 항목 | Python | Go |
|------|--------|-----|
| **CPU** | {python_cpu_info} | {go_cpu_info} |
| **WebSocket 연결 전략** | 마켓 20개당 1개 연결 | 마켓 20개당 1개 연결 |
| **전체 마켓 수** | {python_test_info.get('total_markets', 0)}개 | {go_test_info.get('total_markets', 0)}개 |
| **WebSocket 연결 수** | {python_test_info.get('websocket_connections', 0)}개 | {go_test_info.get('websocket_connections', 0)}개 |

## 주요 성능 지표

### 1. 처리량 (Messages per Second)
| 언어 | 처리량 (msg/sec) | 승자 |
|------|----------------|------|
| **Python** | {python_test_info.get('messages_per_second', 0):.2f} | {':trophy:' if winners.get('throughput', 'N/A') == 'Python' else ''} |
| **Go** | {go_test_info.get('messages_per_second', 0):.2f} | {':trophy:' if winners.get('throughput', 'N/A') == 'Go' else ''} |

### 2. 총 메시지 처리량
| 언어 | 총 메시지 수 | 승자 |
|------|------------|------|
| **Python** | {python_test_info.get('total_messages', 0):,}개 | {':trophy:' if winners.get('total_messages', 'N/A') == 'Python' else ''} |
| **Go** | {go_test_info.get('total_messages', 0):,}개 | {':trophy:' if winners.get('total_messages', 'N/A') == 'Go' else ''} |

### 3. 메시지 전송 성공률
| 언어 | 성공률 | 성공 | 실패 |
|------|-------|------|------|
| **Python** | {python_success_rate:.2f}% | {python_delivery.get('success', 0):,} | {python_delivery.get('error', 0):,} |
| **Go** | {go_success_rate:.2f}% | {go_delivery.get('success', 0):,} | {go_delivery.get('error', 0):,} |
"""

        if 'memory' in comparison:
            report += f"""
### 4. 메모리 사용량 (평균)
| 언어 | 메모리 사용량 (MB) | 승자 |
|------|-----------------|------|
| **Python** | {self.python_report['memory']['avg_mb']:.2f} | {':trophy:' if winners.get('memory', 'N/A') == 'Python' else ''} |
| **Go** | {self.go_report['memory']['avg_mb']:.2f} | {':trophy:' if winners.get('memory', 'N/A') == 'Go' else ''} |
"""

        # 각 작업별 성능
        operations = {
            'message_processing': '메시지 처리',
            'kafka_send': 'Kafka 전송',
            'websocket_connection': 'WebSocket 연결'
        }

        for op_key, op_name in operations.items():
            if op_key in self.python_report and op_key in self.go_report:
                report += f"""
### {op_name} 지연시간
| 언어 | 평균 (ms) | P95 (ms) | P99 (ms) | 승자 (평균) |
|------|-----------|----------|----------|------------|
| **Python** | {self.python_report[op_key]['avg_ms']:.2f} | {self.python_report[op_key]['p95_ms']:.2f} | {self.python_report[op_key]['p99_ms']:.2f} | {':trophy:' if winners.get(f'{op_key}_latency', 'N/A') == 'Python' else ''} |
| **Go** | {self.go_report[op_key]['avg_ms']:.2f} | {self.go_report[op_key]['p95_ms']:.2f} | {self.go_report[op_key]['p99_ms']:.2f} | {':trophy:' if winners.get(f'{op_key}_latency', 'N/A') == 'Go' else ''} |
"""

        # 전체 요약
        python_wins = list(winners.values()).count('Python')
        go_wins = list(winners.values()).count('Go')

        report += f"""
## 종합 평가

| 언어 | 승리 지표 수 |
|------|-------------|
| **Python** | {python_wins}개 |
| **Go** | {go_wins}개 |

### 결론
"""

        if go_wins > python_wins:
            report += """
Go가 전반적으로 더 나은 성능을 보였습니다. 특히 메모리 사용량과 지연시간에서 우수한 결과를 보였습니다.
Go의 컴파일된 바이너리와 효율적인 가비지 컬렉터가 실시간 스트리밍 작업에 적합함을 확인할 수 있습니다.
"""
        elif python_wins > go_wins:
            report += """
Python이 전반적으로 더 나은 성능을 보였습니다.
Python의 비동기 프로그래밍과 최적화된 라이브러리가 효과적으로 작동했습니다.
"""
        else:
            report += """
두 언어 모두 비슷한 성능을 보였습니다. 
각각의 장단점이 있으므로 사용 사례에 따라 적절한 언어를 선택하는 것이 중요합니다.
"""

        # 보고서 파일 저장
        with open('performance_comparison_report.md', 'w', encoding='utf-8') as f:
            f.write(report)

        # 생성된 보고서를 reports 폴더에도 저장
        os.makedirs('reports', exist_ok=True)
        with open('reports/performance_comparison_report.md', 'w', encoding='utf-8') as f:
            f.write(report)

        return report


def main():
    analyzer = PerformanceAnalyzer('python_performance_report.json', 'go_performance_report.json')

    print("성능 비교 분석을 시작합니다...")

    # 시각화 생성
    analyzer.create_visualizations()

    # 상세 보고서 생성
    analyzer.generate_report()
    
    # 결과 파일 이동
    # 현재 시간을 YYYYMMDD_HHMMSS 형식으로 포맷팅
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    
    # 결과 저장 디렉토리 생성
    results_dir = f"/app/results/reports_{timestamp}"
    os.makedirs(results_dir, exist_ok=True)
    
    # reports 폴더의 파일을 새 디렉토리로 이동
    if os.path.exists("reports"):
        for file_name in os.listdir("reports"):
            source_path = os.path.join("reports", file_name)
            if os.path.isfile(source_path):
                target_path = os.path.join(results_dir, file_name)
                shutil.copy2(source_path, target_path)
        print(f"분석 결과가 {results_dir} 폴더로 복사되었습니다.")
    else:
        # reports 폴더가 없으면 현재 디렉토리의 결과 파일을 이동
        result_files = ["performance_comparison.png", "performance_comparison_report.md"]
        for file_name in result_files:
            if os.path.exists(file_name):
                target_path = os.path.join(results_dir, file_name)
                shutil.copy2(file_name, target_path)
        print(f"분석 결과가 {results_dir} 폴더로 복사되었습니다.")

    print("분석 완료! performance_comparison.png와 performance_comparison_report.md 파일을 확인하세요.")


if __name__ == "__main__":
    main()