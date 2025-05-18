package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/gorilla/websocket"
)

type PerformanceMonitor struct {
	metrics    map[string][]float64
	startTimes map[string]time.Time
	mutex      sync.RWMutex

	memoryUsage []float64
	cpuUsage    []float64

	messageCount int64
	startTime    time.Time
}

func NewPerformanceMonitor() *PerformanceMonitor {
	return &PerformanceMonitor{
		metrics:    make(map[string][]float64),
		startTimes: make(map[string]time.Time),
		startTime:  time.Now(),
	}
}

func (pm *PerformanceMonitor) StartTimer(operation string) {
	pm.mutex.Lock()
	pm.startTimes[operation] = time.Now()
	pm.mutex.Unlock()
}

func (pm *PerformanceMonitor) EndTimer(operation string) {
	end := time.Now()
	pm.mutex.Lock()
	if start, exists := pm.startTimes[operation]; exists {
		duration := end.Sub(start).Seconds()
		pm.metrics[operation] = append(pm.metrics[operation], duration)
		delete(pm.startTimes, operation)
	}
	pm.mutex.Unlock()
}

func (pm *PerformanceMonitor) RecordSystemMetrics() {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// 메모리 사용량 (MB)
	memoryMB := float64(m.Alloc) / 1024 / 1024
	pm.mutex.Lock()
	pm.memoryUsage = append(pm.memoryUsage, memoryMB)
	pm.mutex.Unlock()
}

func (pm *PerformanceMonitor) IncrementMessageCount() {
	atomic.AddInt64(&pm.messageCount, 1)
}

func (pm *PerformanceMonitor) GetReport() map[string]interface{} {
	pm.mutex.RLock()
	defer pm.mutex.RUnlock()

	report := make(map[string]interface{})

	for operation, times := range pm.metrics {
		if len(times) == 0 {
			continue
		}

		sort.Float64s(times)

		avg := average(times)
		min := times[0]
		max := times[len(times)-1]

		var p95, p99 float64
		if len(times) > 1 {
			p95Index := int(float64(len(times)) * 0.95)
			p99Index := int(float64(len(times)) * 0.99)
			if p95Index >= len(times) {
				p95Index = len(times) - 1
			}
			if p99Index >= len(times) {
				p99Index = len(times) - 1
			}
			p95 = times[p95Index]
			p99 = times[p99Index]
		} else {
			p95 = times[0]
			p99 = times[0]
		}

		report[operation] = map[string]interface{}{
			"count":  len(times),
			"avg_ms": avg * 1000,
			"min_ms": min * 1000,
			"max_ms": max * 1000,
			"p95_ms": p95 * 1000,
			"p99_ms": p99 * 1000,
		}
	}

	if len(pm.memoryUsage) > 0 {
		report["memory"] = map[string]interface{}{
			"avg_mb": average(pm.memoryUsage),
			"max_mb": max(pm.memoryUsage),
			"min_mb": min(pm.memoryUsage),
		}
	}

	_ = time.Since(pm.startTime).Seconds()
	_ = atomic.LoadInt64(&pm.messageCount)

	return report
}

func average(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func max(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	maxVal := values[0]
	for _, v := range values {
		if v > maxVal {
			maxVal = v
		}
	}
	return maxVal
}

func min(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	minVal := values[0]
	for _, v := range values {
		if v < minVal {
			minVal = v
		}
	}
	return minVal
}

type WebSocketConnection struct {
	Index       int      `json:"index"`
	Markets     []string `json:"markets"`
	ConnectedAt float64  `json:"connected_at"`
}

type UpbitKafkaProducer struct {
	producer        *kafka.Producer
	topic           string
	producerID      string
	monitor         *PerformanceMonitor
	running         int32
	deliveryReports struct {
		success int64
		error   int64
	}
	config               kafka.ConfigMap
	websocketConnections []WebSocketConnection
	connectionsMutex     sync.Mutex
}

func NewUpbitKafkaProducer(kafkaServers string, topic string, producerID string) (*UpbitKafkaProducer, error) {
	// Confluent Kafka Producer 설정
	config := kafka.ConfigMap{
		"bootstrap.servers": kafkaServers,
		"client.id":         fmt.Sprintf("upbit-%s-producer", producerID),
		// 성능 최적화 설정
		"batch.size":                            32768,
		"linger.ms":                             10,
		"compression.type":                      "snappy",
		"acks":                                  1,
		"retries":                               3,
		"max.in.flight.requests.per.connection": 5,
		"enable.idempotence":                    true,
		// 처리량 최적화
		"queue.buffering.max.messages": 1000000,
		"queue.buffering.max.kbytes":   1048576,
		// 메모리 최적화
		"go.delivery.reports":      true,
		"go.events.channel.enable": true,
		"go.events.channel.size":   1000,
	}

	producer, err := kafka.NewProducer(&config)
	if err != nil {
		return nil, fmt.Errorf("Kafka 프로듀서 생성 실패: %v", err)
	}

	ukp := &UpbitKafkaProducer{
		producer:   producer,
		topic:      topic,
		producerID: producerID,
		monitor:    NewPerformanceMonitor(),
		running:    1,
		config:     config,
	}

	// 토픽 생성 확인
	ukp.ensureTopicExists()

	// Kafka 이벤트 핸들러
	go ukp.handleKafkaEvents()

	// 시스템 메트릭 모니터링
	go ukp.monitorSystem()

	return ukp, nil
}

func (ukp *UpbitKafkaProducer) ensureTopicExists() {
	// AdminClient로 토픽 생성 (필요시)
	adminConfig := kafka.ConfigMap{
		"bootstrap.servers": ukp.config["bootstrap.servers"],
	}

	adminClient, err := kafka.NewAdminClient(&adminConfig)
	if err != nil {
		log.Printf("[%s] AdminClient 생성 실패: %v", ukp.producerID, err)
		return
	}
	defer adminClient.Close()

	// 토픽 메타데이터 조회
	metadata, err := adminClient.GetMetadata(&ukp.topic, false, 5000)
	if err != nil {
		log.Printf("[%s] 메타데이터 조회 실패: %v", ukp.producerID, err)
		return
	}

	// 토픽이 존재하지 않으면 생성
	if _, exists := metadata.Topics[ukp.topic]; !exists {
		log.Printf("[%s] 토픽 '%s'을 생성합니다...", ukp.producerID, ukp.topic)
		topicSpec := kafka.TopicSpecification{
			Topic:             ukp.topic,
			NumPartitions:     6,
			ReplicationFactor: 1,
		}

		results, err := adminClient.CreateTopics(
			context.Background(),
			[]kafka.TopicSpecification{topicSpec},
			kafka.SetAdminOperationTimeout(10*time.Second),
		)

		if err != nil {
			log.Printf("[%s] 토픽 생성 요청 실패: %v", ukp.producerID, err)
			return
		}

		for _, result := range results {
			log.Printf("[%s] 토픽 생성 결과: %s - %v", ukp.producerID, result.Topic, result.Error)
		}
	}
}

func (ukp *UpbitKafkaProducer) handleKafkaEvents() {
	for {
		select {
		case e := <-ukp.producer.Events():
			switch ev := e.(type) {
			case *kafka.Message:
				if ev.TopicPartition.Error != nil {
					atomic.AddInt64(&ukp.deliveryReports.error, 1)
					log.Printf("[%s] 메시지 전송 실패: %v", ukp.producerID, ev.TopicPartition.Error)
				} else {
					atomic.AddInt64(&ukp.deliveryReports.success, 1)
				}
			case kafka.Error:
				log.Printf("[%s] Kafka 오류: %v", ukp.producerID, ev)
			}
		}

		if atomic.LoadInt32(&ukp.running) == 0 {
			break
		}
	}
}

func (ukp *UpbitKafkaProducer) monitorSystem() {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if atomic.LoadInt32(&ukp.running) == 0 {
				return
			}
			ukp.monitor.RecordSystemMetrics()
		}
	}
}

func (ukp *UpbitKafkaProducer) waitForNextInterval() float64 {
	currentTime := time.Now()
	currentSecond := currentTime.Second()

	// 다음 5의 배수 초 계산
	nextInterval := ((currentSecond / 5) + 1) * 5
	var targetTime time.Time
	if nextInterval >= 60 {
		nextInterval = 0
		// 다음 분의 0초로 이동
		targetTime = currentTime.Truncate(time.Minute).Add(time.Minute)
	} else {
		// 현재 분의 nextInterval 초로 이동
		targetTime = currentTime.Truncate(time.Minute).Add(time.Duration(nextInterval) * time.Second)
	}

	waitDuration := targetTime.Sub(currentTime)
	if waitDuration > 0 {
		fmt.Printf("[%s] 다음 시작 시점까지 %.2f초 대기...\n", ukp.producerID, waitDuration.Seconds())
		time.Sleep(waitDuration)
	}

	actualStart := time.Now()
	fmt.Printf("[%s] 테스트 시작 시간: %.3f (초: %d)\n", ukp.producerID, float64(actualStart.UnixNano())/1e9, actualStart.Second())
	return float64(actualStart.UnixNano()) / 1e9
}

func (ukp *UpbitKafkaProducer) GetAllMarkets() ([]string, error) {
	ukp.monitor.StartTimer("get_markets")
	defer ukp.monitor.EndTimer("get_markets")

	resp, err := http.Get("https://api.upbit.com/v1/market/all")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var markets []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&markets); err != nil {
		return nil, err
	}

	var allMarkets []string
	for _, market := range markets {
		if marketCode, ok := market["market"].(string); ok {
			allMarkets = append(allMarkets, marketCode)
		}
	}

	return allMarkets, nil
}

func (ukp *UpbitKafkaProducer) SendToKafka(message map[string]interface{}) {
	ukp.monitor.StartTimer("kafka_send")
	defer ukp.monitor.EndTimer("kafka_send")

	messageJSON, err := json.Marshal(message)
	if err != nil {
		log.Printf("[%s] JSON 마샬링 오류: %v", ukp.producerID, err)
		return
	}

	// Kafka로 메시지 전송
	err = ukp.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &ukp.topic, Partition: kafka.PartitionAny},
		Value:          messageJSON,
	}, nil)

	if err != nil {
		log.Printf("[%s] 메시지 프로듀스 오류: %v", ukp.producerID, err)
		return
	}

	ukp.monitor.IncrementMessageCount()

	// 주기적으로 이벤트 폴링
	if atomic.LoadInt64(&ukp.monitor.messageCount)%1000 == 0 {
		ukp.producer.Poll(0)
	}
}

func (ukp *UpbitKafkaProducer) createWebSocketConnection(marketsChunk []string, connectionIndex int, wg *sync.WaitGroup) {
	defer wg.Done()

	url := "wss://api.upbit.com/websocket/v1"

	subscribeMessage := []interface{}{
		map[string]string{"ticket": fmt.Sprintf("test-%s-%d", ukp.producerID, connectionIndex)},
		map[string]interface{}{
			"type":           "ticker",
			"codes":          marketsChunk,
			"isOnlyRealtime": true,
		},
	}

	retryCount := 0
	maxRetries := 3

	for atomic.LoadInt32(&ukp.running) == 1 && retryCount < maxRetries {
		ukp.monitor.StartTimer(fmt.Sprintf("websocket_connection_%d", connectionIndex))

		dialer := websocket.Dialer{
			HandshakeTimeout: 10 * time.Second,
		}

		conn, _, err := dialer.Dial(url, nil)
		if err != nil {
			ukp.monitor.EndTimer(fmt.Sprintf("websocket_connection_%d", connectionIndex))
			retryCount++
			log.Printf("[%s] 연결 #%d 오류 (재시도 %d/%d): %v", ukp.producerID, connectionIndex, retryCount, maxRetries, err)
			if retryCount < maxRetries {
				time.Sleep(5 * time.Second)
			}
			continue
		}

		ukp.monitor.EndTimer(fmt.Sprintf("websocket_connection_%d", connectionIndex))

		// 구독 메시지 전송
		if err := conn.WriteJSON(subscribeMessage); err != nil {
			log.Printf("[%s] 구독 메시지 전송 오류: %v", ukp.producerID, err)
			conn.Close()
			continue
		}

		log.Printf("[%s] 연결 #%d: %d개 마켓 구독 완료", ukp.producerID, connectionIndex, len(marketsChunk))

		// 연결 정보 저장
		ukp.connectionsMutex.Lock()
		ukp.websocketConnections = append(ukp.websocketConnections, WebSocketConnection{
			Index:       connectionIndex,
			Markets:     marketsChunk,
			ConnectedAt: float64(time.Now().UnixNano()) / 1e9,
		})
		ukp.connectionsMutex.Unlock()

		// 메시지 수신 루프
		for atomic.LoadInt32(&ukp.running) == 1 {
			ukp.monitor.StartTimer("message_processing")

			var message map[string]interface{}
			err := conn.ReadJSON(&message)
			if err != nil {
				ukp.monitor.EndTimer("message_processing")
				log.Printf("[%s] 메시지 읽기 오류: %v", ukp.producerID, err)
				break
			}

			// 메타데이터 추가
			message["received_at"] = float64(time.Now().UnixNano()) / 1e9
			message["message_id"] = atomic.LoadInt64(&ukp.monitor.messageCount)
			message["producer_type"] = "go-confluent"
			message["producer_id"] = ukp.producerID
			message["connection_index"] = connectionIndex

			// Kafka에 전송
			ukp.SendToKafka(message)

			ukp.monitor.EndTimer("message_processing")
		}

		conn.Close()
		break
	}
}

func (ukp *UpbitKafkaProducer) ConnectAllWebSockets(markets []string) error {
	// 마켓을 20개씩 청크로 분할
	marketsPerConnection := 20
	var marketChunks [][]string

	for i := 0; i < len(markets); i += marketsPerConnection {
		end := i + marketsPerConnection
		if end > len(markets) {
			end = len(markets)
		}
		marketChunks = append(marketChunks, markets[i:end])
	}

	fmt.Printf("[%s] 총 %d개 마켓을 %d개 연결로 분할\n", ukp.producerID, len(markets), len(marketChunks))
	fmt.Printf("[%s] 업비트 API 제한에 따라 1초당 5개 연결씩 생성\n", ukp.producerID)

	// 연결을 5개씩 묶어서 1초 간격으로 생성
	connectionsPerBatch := 5
	var wg sync.WaitGroup

	for batchIndex := 0; batchIndex < len(marketChunks); batchIndex += connectionsPerBatch {
		batchEnd := batchIndex + connectionsPerBatch
		if batchEnd > len(marketChunks) {
			batchEnd = len(marketChunks)
		}

		// 배치 내 연결들을 동시에 시작
		for chunkIndex := batchIndex; chunkIndex < batchEnd; chunkIndex++ {
			wg.Add(1)
			go ukp.createWebSocketConnection(marketChunks[chunkIndex], chunkIndex, &wg)
		}

		// 다음 배치 전에 1초 대기 (마지막 배치가 아닌 경우)
		if batchEnd < len(marketChunks) {
			fmt.Printf("[%s] 다음 배치까지 1초 대기...\n", ukp.producerID)
			time.Sleep(1 * time.Second)
		}
	}

	// 모든 연결이 완료될 때까지 대기하지 않고 바로 리턴
	// (연결들은 백그라운드에서 계속 실행됨)
	return nil
}

func (ukp *UpbitKafkaProducer) Run(duration time.Duration) (map[string]interface{}, error) {
	// 5의 배수 초까지 대기
	startTime := ukp.waitForNextInterval()

	// 전체 마켓 목록 조회
	fmt.Printf("[%s] 전체 마켓 목록을 가져오는 중...\n", ukp.producerID)
	markets, err := ukp.GetAllMarkets()
	if err != nil {
		return nil, err
	}

	krwMarkets := 0
	for _, market := range markets {
		if len(market) > 4 && market[:4] == "KRW-" {
			krwMarkets++
		}
	}

	fmt.Printf("[%s] 총 %d개 마켓 발견 (KRW: %d개)\n", ukp.producerID, len(markets), krwMarkets)

	// WebSocket 연결 시작
	fmt.Printf("[%s] 전체 마켓 WebSocket 연결을 시작합니다...\n", ukp.producerID)
	go ukp.ConnectAllWebSockets(markets)

	// 지정된 시간 동안 실행
	time.Sleep(duration)

	// 종료
	atomic.StoreInt32(&ukp.running, 0)
	fmt.Printf("[%s] 테스트 시간 종료\n", ukp.producerID)

	// Producer 정리
	fmt.Printf("[%s] 메시지 플러시 중...\n", ukp.producerID)
	ukp.producer.Flush(10 * 1000) // 10초 타임아웃
	ukp.producer.Close()

	// 성능 보고서 생성
	baseReport := ukp.monitor.GetReport()
	elapsedTime := time.Now().Unix() - int64(startTime)
	messageCount := atomic.LoadInt64(&ukp.monitor.messageCount)

	report := make(map[string]interface{})
	for k, v := range baseReport {
		report[k] = v
	}

	report["test_info"] = map[string]interface{}{
		"producer_id":           ukp.producerID,
		"start_time":            startTime,
		"total_runtime_seconds": float64(elapsedTime),
		"total_messages":        messageCount,
		"messages_per_second":   float64(messageCount) / float64(elapsedTime),
		"total_markets":         len(markets),
		"krw_markets":           krwMarkets,
		"websocket_connections": len(ukp.websocketConnections),
	}

	report["delivery_reports"] = map[string]interface{}{
		"success": atomic.LoadInt64(&ukp.deliveryReports.success),
		"error":   atomic.LoadInt64(&ukp.deliveryReports.error),
	}

	report["kafka_config"] = map[string]interface{}{
		"library":     "confluent-kafka-go",
		"batch_size":  ukp.config["batch.size"],
		"linger_ms":   ukp.config["linger.ms"],
		"compression": ukp.config["compression.type"],
	}

	ukp.connectionsMutex.Lock()
	report["websocket_info"] = map[string]interface{}{
		"connections":            ukp.websocketConnections,
		"markets_per_connection": 20,
		"connection_rate_limit":  5, // per second
	}
	ukp.connectionsMutex.Unlock()

	return report, nil
}

func main() {
	// 환경 변수에서 설정 읽기
	kafkaServers := getEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
	topic := getEnv("KAFKA_TOPIC", "upbit-krw-ticker")
	producerID := getEnv("PRODUCER_ID", "go")

	testDurationStr := getEnv("TEST_DURATION", "60")
	testDuration, err := strconv.Atoi(testDurationStr)
	if err != nil {
		log.Fatal("잘못된 TEST_DURATION:", err)
	}

	producer, err := NewUpbitKafkaProducer(kafkaServers, topic, producerID)
	if err != nil {
		log.Fatal("Kafka 프로듀서 생성 오류:", err)
	}

	fmt.Printf("[%s] %d초 동안 성능 테스트를 시작합니다...\n", producerID, testDuration)
	fmt.Printf("[%s] 사용 라이브러리: confluent-kafka-go\n", producerID)

	report, err := producer.Run(time.Duration(testDuration) * time.Second)
	if err != nil {
		log.Fatal("테스트 실행 오류:", err)
	}

	fmt.Printf("\n=== %s (Confluent Kafka) 성능 테스트 결과 ===\n", producerID)
	reportJSON, _ := json.MarshalIndent(report, "", "  ")
	fmt.Println(string(reportJSON))

	// 성공/실패 메시지 수 출력
	deliveryReports := report["delivery_reports"].(map[string]interface{})
	fmt.Printf("[%s] 성공한 메시지: %.0f\n", producerID, deliveryReports["success"])
	fmt.Printf("[%s] 실패한 메시지: %.0f\n", producerID, deliveryReports["error"])

	// 결과를 파일로 저장
	os.MkdirAll("/app/reports", 0755)
	reportPath := fmt.Sprintf("/app/reports/%s_performance_report.json", producerID)

	file, err := os.Create(reportPath)
	if err != nil {
		log.Printf("파일 생성 오류: %v", err)
		return
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	encoder.Encode(report)

	fmt.Printf("[%s] 보고서 저장: %s\n", producerID, reportPath)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
