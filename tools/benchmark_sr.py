import requests
import time
import concurrent.futures
import json
from datetime import datetime

# Nodes to benchmark
NODES = [
    {"name": "Node A", "url": "http://localhost:10000/v1/chat/completions"},
    {"name": "Node B", "url": "http://192.168.64.4:10000/v1/chat/completions"},
    {"name": "Node C", "url": "http://192.168.64.8:10000/v1/chat/completions"},
]

# Test dataset: (Prompt, Expected Category)
TEST_DATA = [
    ("Calculate the integral of sin(x) from 0 to pi.", "math"),
    ("What is 15 * 24?", "math"),
    ("Solve for x: 3x + 5 = 20", "math"),
    ("How do I implement a sorting algorithm in Python?", "computer_science"),
    ("What is a class decorator in TypeScript?", "computer_science"),
    ("Explain the difference between a process and a thread.", "computer_science"),
    ("Write a bash script to find files larger than 100MB.", "computer_science"),
    ("What is the derivative of e^x?", "math"),
    ("What is the capital of France?", "geography"),
    ("Which is the longest river in the world?", "geography"),
    ("List the seven continents", "geography"),
    ("Who was the first president of the United States?", "history"),
    ("When did World War II end?", "history"),
    ("What was the Ming Dynasty known for?", "history"),
    ("What is the structure of a DNA molecule?", "biology"),
    ("How do cells produce energy?", "biology"),
    ("Explain the theory of natural selection", "biology")
]

def send_request(node, prompt, expected_category):
    payload = {
        "model": "MoM",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10
    }
    
    start_time = time.time()
    try:
        response = requests.post(node["url"], json=payload, timeout=30)
        end_time = time.time()
        
        latency = (end_time - start_time) * 1000 # ms
        
        if response.status_code == 200:
            actual_category = response.headers.get("x-vsr-selected-category", "")
            if actual_category and actual_category.endswith("_keywords"):
                actual_category = actual_category.replace("_keywords", "")
            if actual_category == "code":
                actual_category = "computer_science"

            # Robust fallback for all categories
            if not actual_category or actual_category == "unknown":
                decision = response.headers.get("x-vsr-selected-decision", "").lower()
                selected_model = response.headers.get("x-selected-model", "").lower()
                
                if "math" in decision or "qwen" in selected_model: actual_category = "math"
                elif "code" in decision or "computer_science" in decision or "tinyllama" in selected_model: actual_category = "computer_science"
                elif "geography" in decision: actual_category = "geography"
                elif "history" in decision: actual_category = "history"
                elif "biology" in decision: actual_category = "biology"
                else: actual_category = "unknown"
            
            is_correct = actual_category == expected_category
            if not is_correct:
                print(f"Mismatch on {node['name']}: got '{actual_category}' (model: {response.headers.get('x-selected-model')}), expected '{expected_category}'")
            return {
                "success": True,
                "latency": latency,
                "correct": is_correct,
                "node": node["name"]
            }
        else:
            print(f"Error from {node['name']}: HTTP {response.status_code} - {response.text[:100]}")
            return {"success": False, "error": response.status_code, "node": node["name"]}
    except Exception as e:
        print(f"Connection error to {node['name']}: {str(e)}")
        return {"success": False, "error": str(e), "node": node["name"]}

def run_benchmark(requests_per_node=5):
    print(f"Starting benchmark at {datetime.now()}")
    print(f"Targeting {len(NODES)} nodes with {requests_per_node} requests each...")
    
    results = []
    start_total = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        futures = []
        for _ in range(requests_per_node):
            for node in NODES:
                # Randomly pick from test data
                import random
                prompt, expected = random.choice(TEST_DATA)
                futures.append(executor.submit(send_request, node, prompt, expected))
                time.sleep(5)  # SLOW DOWN: ensure no overlap
        
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    end_total = time.time()
    total_time = end_total - start_total
    
    # Calculate Metrics
    successful_results = [r for r in results if r["success"]]
    if not successful_results:
        print("Error: No successful requests.")
        return

    avg_latency = sum(r["latency"] for r in successful_results) / len(successful_results)
    accuracy = sum(1 for r in successful_results if r["correct"]) / len(successful_results) * 100
    total_requests = len(results)
    rps = total_requests / total_time
    
    print("\n" + "="*40)
    print("vLLM-SR MULTI-NODE BENCHMARK RESULTS")
    print("="*40)
    print(f"Total Nodes:          {len(NODES)}")
    print(f"Total Requests:       {total_requests}")
    print(f"Successful:           {len(successful_results)}")
    print(f"Duration:             {total_time:.2f} s")
    print("-" * 40)
    print(f"Average Latency:      {avg_latency:.2f} ms")
    print(f"Requests Per Second:  {rps:.2f} RPS")
    print(f"Classification Accuracy: {accuracy:.2f} %")
    print("="*40)

if __name__ == "__main__":
    import sys
    count = 10
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    run_benchmark(count)
