import os
import sys
import json
import pytest
import hmac
import hashlib

# Add lambda directory to path to import orchestrator
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../lambda')))
from orchestrator import handler, verify_signature

@pytest.fixture
def webhook_secret():
    secret = "test_secret_123"
    os.environ["WEBHOOK_SECRET"] = secret
    yield secret
    del os.environ["WEBHOOK_SECRET"]

def test_bedrock_agent_routing():
    # Test that the bedrock routing correctly parses lists
    event = {
        "apiPath": "/analyze/complexity",
        "actionGroup": "MyActionGroup",
        "httpMethod": "POST",
        "parameters": [],
        "requestBody": {
            "content": {
                "application/json": {
                    "properties": [
                        {"name": "code", "type": "string", "value": "def foo(): pass"}
                    ]
                }
            }
        }
    }
    
    response = handler(event, None)
    
    assert response["messageVersion"] == "1.0"
    assert response["response"]["httpStatusCode"] == 200
    
    body_str = response["response"]["responseBody"]["application/json"]["body"]
    body = json.loads(body_str)
    
    assert body["status"] == "success"
    assert "analysis" in body

def test_github_webhook_signature(webhook_secret):
    payload = json.dumps({"pull_request": {"html_url": "https://github.com/owner/repo/pull/1"}})
    mac = hmac.new(webhook_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    signature = f"sha256={mac.hexdigest()}"
    
    event = {
        "headers": {
            "X-Hub-Signature-256": signature
        },
        "body": payload
    }
    
    assert verify_signature(event) == True
    
def test_github_webhook_invalid_signature(webhook_secret):
    event = {
        "headers": {
            "X-Hub-Signature-256": "sha256=invalid"
        },
        "body": "{}"
    }
    
    assert verify_signature(event) == False
