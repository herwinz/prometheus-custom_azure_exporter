from prometheus_client import start_http_server, Gauge, Counter
from azure.identity import ClientSecretCredential
import requests
import time
import os
from datetime import datetime, timezone, timedelta

# Azure credentials
TENANT_ID = "af2c0734-cb42-464f-b6bf-2a241b6ada56"
CLIENT_ID = "aa6bdeca-20bc-4241-8772-a7df362b8a39"
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
SUBSCRIPTION_ID = "3bff15a8-79cf-44d3-b98f-94606c8f3a60"
RESOURCE_ID = "/subscriptions/3bff15a8-79cf-44d3-b98f-94606c8f3a60/resourceGroups/rg-dev/providers/Microsoft.Web/sites/app-web-ztg2yzezngfmy"

# Prometheus metrics
CPU_USAGE = Gauge('azure_appservice_cpu_time', 'CPU Time in Seconds', ['resource', 'timestamp'])
MEMORY_USAGE = Gauge('azure_appservice_memory_working_set', 'Memory Working Set in Bytes', ['resource', 'timestamp'])
REQUEST_COUNT = Counter('azure_appservice_request_count', 'Request Count', ['resource', 'timestamp'])

# Azure Monitor API base URL
AZURE_MONITOR_BASE = "https://management.azure.com"

# Get Azure access token
def get_access_token():
    try:
        credential = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
        token = credential.get_token("https://management.azure.com/.default")
        return token.token
    except Exception as e:
        print(f"Error getting Azure token: {e}")
        return None

# Get metrics from Azure Monitor
def fetch_metrics(metric_name):
    token = get_access_token()
    if not token:
        return None
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "metricnames": metric_name,
        "timespan": "PT5M",  # Fetch data from the last 5 minutes
        "interval": "PT1M",  # 1-minute granularity
        "api-version": "2018-01-01"
    }
    url = f"{AZURE_MONITOR_BASE}{RESOURCE_ID}/providers/microsoft.insights/metrics"
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching metric {metric_name}: {e}")
        return None

# Convert UTC timestamp to WIB (Jakarta time)
def convert_to_wib(utc_time):
    utc_dt = datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%SZ")
    wib_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7)))
    return wib_dt.strftime("%Y-%m-%d %H:%M:%S")

# Update Prometheus metrics
def update_metrics():
    print("---------------------------------------------------")
    print(f"Updating metrics at: {datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S')} WIB")
    try:
        # Fetch CPU Time
        cpu_data = fetch_metrics("CpuTime")
        if cpu_data and "value" in cpu_data:
            for metric in cpu_data["value"]:
                if metric["name"]["value"] == "CpuTime":
                    latest_data = metric.get("timeseries", [{}])[0].get("data", [])
                    if latest_data:
                        latest_point = latest_data[-1]
                        if "total" in latest_point:
                            timestamp = latest_point.get("timeStamp")
                            wib_timestamp = convert_to_wib(timestamp)
                            value = latest_point["total"]
                            CPU_USAGE.labels(resource=RESOURCE_ID, timestamp=wib_timestamp).set(value)
                            print(f"Updated CPU Time: {value} at {wib_timestamp} WIB")

        # Fetch Memory Working Set
        memory_data = fetch_metrics("MemoryWorkingSet")
        if memory_data and "value" in memory_data:
            for metric in memory_data["value"]:
                if metric["name"]["value"] == "MemoryWorkingSet":
                    latest_data = metric.get("timeseries", [{}])[0].get("data", [])
                    if latest_data:
                        latest_point = latest_data[-1]
                        if "average" in latest_point:
                            timestamp = latest_point.get("timeStamp")
                            wib_timestamp = convert_to_wib(timestamp)
                            value = latest_point["average"]
                            MEMORY_USAGE.labels(resource=RESOURCE_ID, timestamp=wib_timestamp).set(value)
                            print(f"Updated Memory Working Set: {value} at {wib_timestamp} WIB")

        # Fetch Request Count
        request_data = fetch_metrics("Requests")
        if request_data and "value" in request_data:
            for metric in request_data["value"]:
                if metric["name"]["value"] == "Requests":
                    latest_data = metric.get("timeseries", [{}])[0].get("data", [])
                    if latest_data:
                        latest_point = latest_data[-1]
                        if "total" in latest_point:
                            timestamp = latest_point.get("timeStamp")
                            wib_timestamp = convert_to_wib(timestamp)
                            value = latest_point["total"]
                            REQUEST_COUNT.labels(resource=RESOURCE_ID, timestamp=wib_timestamp).inc(value)
                            print(f"Updated Request Count: {value} at {wib_timestamp} WIB")
    except Exception as e:
        print(f"Error updating metrics: {e}")

# Main function
if __name__ == "__main__":
    # Start Prometheus server
    start_http_server(8000)
    print("Custom Azure Exporter running on port 8000...")

    # Update metrics periodically
    while True:
        update_metrics()
        time.sleep(60)