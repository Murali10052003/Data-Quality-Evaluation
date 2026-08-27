import datetime
import json
import base64
import hmac
import hashlib
import http.client
from urllib.parse import urlparse

class DQEvalLoggerBase:
    """Base logger interface for DQEval loggers."""
    def log(self, record: dict):
        raise NotImplementedError("Subclasses must implement log()")

class AzureLogAnalyticsLogger(DQEvalLoggerBase):
    """
    Logger for sending structured JSON logs to Azure Log Analytics via HTTP Data Collector API.
    """
    def __init__(self, workspace_id: str, shared_key: str, log_type: str):
        self.workspace_id = workspace_id
        self.shared_key = shared_key
        self.log_type = log_type
        self.endpoint = f"https://{workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"
        parsed = urlparse(self.endpoint)
        self.host = parsed.hostname
        self.path = parsed.path + "?" + parsed.query

    def build_signature(self, date: str, content_length: int, content_type: str, resource: str) -> str:
        string_to_hash = f"POST\n{content_length}\n{content_type}\nx-ms-date:{date}\n{resource}"
        bytes_to_hash = string_to_hash.encode("utf-8")
        decoded_key = base64.b64decode(self.shared_key)
        encoded_hash = hmac.new(decoded_key, bytes_to_hash, hashlib.sha256).digest()
        encoded_hash = base64.b64encode(encoded_hash).decode("utf-8")
        return f"SharedKey {self.workspace_id}:{encoded_hash}"

    def log(self, record: dict):
        try:
            body = json.dumps([record])
            content_type = "application/json"
            resource = "/api/logs"
            rfc1123date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            signature = self.build_signature(rfc1123date, len(body), content_type, resource)
            headers = {
                "Content-Type": content_type,
                "Authorization": signature,
                "Log-Type": self.log_type,
                "x-ms-date": rfc1123date,
            }
            conn = http.client.HTTPSConnection(self.host)
            conn.request("POST", self.path, body=body, headers=headers)
            response = conn.getresponse()
            status = response.status
            data = response.read().decode()
            conn.close()
            if not (200 <= status <= 299):
                print(f"Azure Log Analytics: Failed to send log: {status} {data}")
        except Exception as e:
            print(f"AzureLogAnalyticsLogger Exception: {e}")

class ConsoleLogger(DQEvalLoggerBase):
    """
    Simple logger that prints logs to the console.
    """
    def log(self, record: dict):
        try:
            print(json.dumps(record, indent=2))
        except Exception as e:
            print(f"ConsoleLogger Exception: {e}")

def log_dqeval_results(results, loggers, dqeval_tags=None):
    """
    Logs each DQEval result (with dqeval_score) using the provided logger(s).
    Args:
        results (list[dict]): JSON string or list of DQEval results.
        loggers (list): A list of logger instances with a .log(dict) method.
        dqeval_tags (dict, optional): Additional tags to be added to each logged result.
                                   Defaults to None.
    """
    results = json.loads(results)
    for result in results:
        try:
            if isinstance(result, dict):
                if result.get("dqeval_passed") is True:
                    result["dqeval_score"] = 100.0
                elif result.get("status") == "Success":
                    total = result.get("dqeval_total_count", 0)
                    passed = result.get("dqeval_passed_count", 0)
                    result["dqeval_score"] = round((passed / total) * 100, 2) if total else 0.0
                else:
                    result["dqeval_score"] = 0.0
                    
                if dqeval_tags:
                    result["dqeval_tags"] = dqeval_tags

                for logger in loggers:
                    try:
                        logger.log(result)
                    except Exception as e:
                        print(f"Logger {logger.__class__.__name__} failed: {e}")
        except Exception as e:
            print(f"Error processing result: {e}")