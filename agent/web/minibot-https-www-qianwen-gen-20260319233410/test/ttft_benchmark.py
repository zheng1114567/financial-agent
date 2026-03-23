import time
import requests
import statistics

def benchmark_ttft(url: str = "http://127.0.0.1:3000/api/v2/chat", n: int = 1000):
    """
    Benchmark Time-To-First-Token (TTFT) for /api/v2/chat endpoint.
    Measures time from POST request until first SSE 'message' event arrives.
    """
    ttft_times = []

    for i in range(n):
        start = time.time()
        try:
            # Send streaming request
            with requests.post(
                url,
                json={"messages": [{"role": "user", "content": "Hello"}], "model": "qwen-plus"},
                stream=True,
                timeout=10
            ) as r:
                if r.status_code != 200:
                    print(f"[{i}] HTTP {r.status_code}")
                    continue

                # Read stream until first 'message' event
                for line in r.iter_lines():
                    if line.startswith(b'event: message'):
                        ttft = time.time() - start
                        ttft_times.append(ttft)
                        break
        except Exception as e:
            print(f"[{i}] Error: {e}")

    if not ttft_times:
        print("No valid TTFT measurements collected.")
        return

    p95 = statistics.quantiles(ttft_times, n=20)[-1]  # 95th percentile
    print(f"TTFT Benchmark (n={n}):")
    print(f"  Mean: {statistics.mean(ttft_times):.3f}s")
    print(f"  Median: {statistics.median(ttft_times):.3f}s")
    print(f"  P95: {p95:.3f}s")
    print(f"  Pass: {p95 <= 1.5}")

if __name__ == "__main__":
    benchmark_ttft()
