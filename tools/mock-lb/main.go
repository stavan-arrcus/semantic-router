package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	core "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	ext_proc "github.com/envoyproxy/go-control-plane/envoy/service/ext_proc/v3"
	"google.golang.org/grpc"
)

// Global state for routing
var (
	// activeQueries tracks the number of concurrent queries per model (used when rerouteByCount is false)
	activeQueries sync.Map
	// requestCount tracks total requests per model for "every Nth reroute" (used when rerouteByCount is true)
	requestCount sync.Map

	// Flags
	port            = flag.Int("port", 9000, "gRPC server port")
	maxQueries      = flag.Int("max-queries", 3, "Max concurrent queries before rerouting (concurrency mode)")
	rerouteEveryN   = flag.Int("reroute-every", 4, "Reroute every Nth request (count mode); 0 = use concurrency mode")
	targetMode      = flag.Bool("target", false, "Run as the mock target HTTP server instead of ExtProc")
	targetPort      = flag.Int("target-port", 8888, "Port for the mock target server")
	targetName      = flag.String("target-name", "Mock Target", "Name to return in response body (e.g. qwen-a, qwen-b)")
)

type server struct{}

func (s *server) Process(stream ext_proc.ExternalProcessor_ProcessServer) error {
	// Context for this request
	var modelName string
	var incremented bool

	// Ensure we decrement the counter when the stream ends (request finished)
	defer func() {
		if incremented && modelName != "" {
			val, ok := activeQueries.Load(modelName)
			if ok {
				newVal := atomic.AddInt64(val.(*int64), -1)
				log.Printf("[%s] Request finished. Active queries: %d", modelName, newVal)
			}
		}
	}()

	for {
		req, err := stream.Recv()
		if err != nil {
			return err
		}

		if headers := req.GetRequestHeaders(); headers != nil {
			log.Printf("Received request on port %d", *port)

			// 1. Check if this is already a rerouted request
			var isRerouted bool
			for _, h := range headers.Headers.Headers {
				if strings.ToLower(h.Key) == "x-rerouted-from" {
					isRerouted = true
					log.Printf("Request was rerouted from peer. Accepting immediately.")
					break
				}
				if strings.ToLower(h.Key) == "x-selected-model" {
					modelName = string(h.RawValue)
				}
			}

			// Default model if none selected
			if modelName == "" {
				modelName = "default"
			}

			mutation := &ext_proc.HeaderMutation{}
			shouldReroute := false

			// 2. If NOT rerouted, decide: accept or reroute
			if !isRerouted {
				if *rerouteEveryN > 0 {
					// Count mode: reroute every Nth request (1st, 2nd, 3rd local; 4th reroute; 5th, 6th, 7th local; 8th reroute; ...)
					counter, _ := requestCount.LoadOrStore(modelName, new(int64))
					n := atomic.AddInt64(counter.(*int64), 1)
					if n%int64(*rerouteEveryN) == 0 {
						log.Printf("[%s] Request #%d: every-%d reroute.", modelName, n, *rerouteEveryN)
						shouldReroute = true
					} else {
						log.Printf("[%s] Request #%d: accepting.", modelName, n)
					}
				} else {
					// Concurrency mode: reroute when maxQueries are already in flight
					counter, _ := activeQueries.LoadOrStore(modelName, new(int64))
					val := atomic.LoadInt64(counter.(*int64))
					if val >= int64(*maxQueries) {
						log.Printf("[%s] BUSY (Count: %d >= %d). Rerouting...", modelName, val, *maxQueries)
						shouldReroute = true
					} else {
						newVal := atomic.AddInt64(counter.(*int64), 1)
						incremented = true
						log.Printf("[%s] Accepting request. Active queries: %d", modelName, newVal)
					}
				}
			}

			if shouldReroute {
				// Reroute logic
				mutation.SetHeaders = append(mutation.SetHeaders,
					&core.HeaderValueOption{
						Header: &core.HeaderValue{
							Key:      "x-reroute-target",
							RawValue: []byte("peer"),
						},
					},
					&core.HeaderValueOption{
						Header: &core.HeaderValue{
							Key:      "x-rerouted-from",
							RawValue: []byte(fmt.Sprintf("port-%d", *port)),
						},
					},
				)
			}

			// Send response
			resp := &ext_proc.ProcessingResponse{
				Response: &ext_proc.ProcessingResponse_RequestHeaders{
					RequestHeaders: &ext_proc.HeadersResponse{
						Response: &ext_proc.CommonResponse{
							Status:          ext_proc.CommonResponse_CONTINUE,
							HeaderMutation:  mutation,
							ClearRouteCache: true,
						},
					},
				},
			}
			if err := stream.Send(resp); err != nil {
				return err
			}
		} else {
			// Handle other message types (body, trailers, etc.) by just continuing
			resp := &ext_proc.ProcessingResponse{
				Response: &ext_proc.ProcessingResponse_RequestHeaders{
					RequestHeaders: &ext_proc.HeadersResponse{
						Response: &ext_proc.CommonResponse{
							Status: ext_proc.CommonResponse_CONTINUE,
						},
					},
				},
			}
			// We might receive body/trailers, but we only constructed the response for headers above
			// The API requires matching response type. Let's make it generic or check type.
			// Actually, for this simple demo, we can just check if we need to reply to body
			if req.GetRequestBody() != nil {
				resp.Response = &ext_proc.ProcessingResponse_RequestBody{
					RequestBody: &ext_proc.BodyResponse{
						Response: &ext_proc.CommonResponse{Status: ext_proc.CommonResponse_CONTINUE},
					},
				}
			} else if req.GetResponseHeaders() != nil {
				resp.Response = &ext_proc.ProcessingResponse_ResponseHeaders{
					ResponseHeaders: &ext_proc.HeadersResponse{
						Response: &ext_proc.CommonResponse{Status: ext_proc.CommonResponse_CONTINUE},
					},
				}
			}

			if err := stream.Send(resp); err != nil {
				// Don't error out on EOF or mismatch, just log and break/return if critical
				// For the demo, simple return is fine
				return err
			}
		}
	}
}

func runTargetServer() {
	name := *targetName
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		log.Printf("[Target %s] Received request from %s", name, r.RemoteAddr)
		// Simulate processing time
		time.Sleep(2 * time.Second)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(fmt.Sprintf("Processed by %s\n", name)))
	})

	addr := fmt.Sprintf(":%d", *targetPort)
	log.Printf("Mock Target Server listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, nil))
}

func main() {
	flag.Parse()

	if *targetMode {
		runTargetServer()
		return
	}

	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", *port))
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	s := grpc.NewServer()
	ext_proc.RegisterExternalProcessorServer(s, &server{})
	log.Printf("Load Balancer ExtProc listening on :%d (Max Queries: %d)", *port, *maxQueries)
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
