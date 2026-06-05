# FILE: ./lambda/orchestrator.py
import os
import json
import boto3
import urllib.request
import logging
import hmac
import hashlib

from tools.github_pr import get_github_pr, post_pr_comment
from tools.complexity import analyze_complexity
from tools.testgen import generate_unit_test
from tools.refactor import suggest_refactor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_runtime = boto3.client(service_name="bedrock-agent-runtime", region_name="ap-northeast-2")

def verify_signature(event):
    """Verifies the GitHub webhook signature."""
    secret = os.environ.get("WEBHOOK_SECRET")
    if not secret:
        return False
    
    headers = event.get("headers", {})
    # API Gateway converts headers to lowercase in some contexts, so check both
    signature = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")
    if not signature:
        return False
        
    body = event.get("body", "")
    mac = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256)
    expected_signature = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected_signature, signature)

def send_slack_notification(pr_url: str, status: str, summary: str):
    # (기존과 동일하므로 생략 없이 유지)
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL is missing"}
    payload = {"text": f"🚀 *CodeBuddy 리뷰 완료*\n*PR:* {pr_url}\n*상태:* {status}\n*요약:* {summary[:200]}..."}
    try:
        req = urllib.request.Request(webhook_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as res:
            return {"status": "success", "message": "Slack 알림 전송 성공", "api_status": res.status}
    except Exception as e:
        logger.error(f"Slack notification failed: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==========================================
# [추가됨] Bedrock Agent Action Group 라우터
# ==========================================
def handle_agent_action(event):
    """Bedrock Agent가 도구를 호출할 때의 로직을 처리합니다."""
    api_path = event.get("apiPath")
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}
    request_body = {}
    if "requestBody" in event and "content" in event["requestBody"]:
        # properties is a list of dicts: [{'name': '...', 'type': '...', 'value': '...'}]
        properties = event["requestBody"]["content"]["application/json"].get("properties", [])
        if isinstance(properties, list):
            request_body = {p["name"]: p["value"] for p in properties}
        else:
             # Fallback if somehow it's already parsed as dict
             request_body = properties

    response_body = {}
    
    # OpenAPI 스키마에 정의된 경로(apiPath)에 따라 도구 실행
    try:
        if api_path == "/github/pr":
            response_body = get_github_pr(parameters.get("owner"), parameters.get("repo"), int(parameters.get("pr_number")))
        elif api_path == "/github/comment":
            response_body = post_pr_comment(request_body.get("owner"), request_body.get("repo"), int(request_body.get("pr_number")), request_body.get("comment"))
        elif api_path == "/analyze/complexity":
            response_body = analyze_complexity(request_body.get("code"))
        elif api_path == "/generate/test":
            response_body = generate_unit_test(request_body.get("code"))
        elif api_path == "/analyze/refactor":
            response_body = suggest_refactor(request_body.get("code"))
        elif api_path == "/slack/send":
            response_body = send_slack_notification(request_body.get("pr_url"), request_body.get("status"), request_body.get("summary"))
        else:
            response_body = {"status": "error", "message": f"Unknown API path: {api_path}"}
    except Exception as e:
        response_body = {"status": "error", "message": str(e)}

    # Bedrock Agent가 이해할 수 있는 지정된 포맷으로 반환 필수
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "apiPath": api_path,
            "httpMethod": event.get("httpMethod"),
            "httpStatusCode": 200,
            "responseBody": {
                "application/json": {"body": json.dumps(response_body)}
            }
        }
    }

lambda_client = boto3.client('lambda', region_name='ap-northeast-2')

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    # 0. 백그라운드 워커 모드인지 확인 (Self Asynchronous Invocation)
    if event.get("is_async_worker"):
        return run_agent_workflow(event)
        
    # 1. Bedrock Agent의 Action Group 호출인 경우
    if "apiPath" in event and "actionGroup" in event:
        return handle_agent_action(event)
        
    # 2. API Gateway를 통한 GitHub Webhook 호출인 경우
    
    # Verify GitHub Webhook Signature
    if not verify_signature(event):
        logger.error("Invalid Webhook Signature")
        return {"statusCode": 401, "body": json.dumps("Unauthorized")}

    try:
        # payload parsing validation before async passing
        body = json.loads(event.get("body", "{}"))
        pr_info = body.get("pull_request")
        if not pr_info:
            return {"statusCode": 200, "body": json.dumps("Not a PR event, ignoring.")}
            
        # API Gateway의 29초 Timeout 방지를 위해 스스로를 비동기 호출
        new_event = event.copy()
        new_event["is_async_worker"] = True
        
        lambda_client.invoke(
            FunctionName=context.invoked_function_arn,
            InvocationType='Event',
            Payload=json.dumps(new_event)
        )
        return {"statusCode": 200, "body": json.dumps({"status": "Accepted", "message": "Processing in background"})}
    except Exception as e:
        logger.error(f"Failed to trigger async worker: {str(e)}")
        return {"statusCode": 500, "body": json.dumps("Internal Server Error")}

def run_agent_workflow(event):
    """비동기로 실행되는 Bedrock Agent 실제 호출 로직"""
    try:
        body = json.loads(event.get("body", "{}"))
        pr_info = body.get("pull_request")
        pr_url = pr_info.get("html_url", "unknown-url")
        url_parts = pr_url.split("/")
        owner = url_parts[-4]
        repo = url_parts[-3]
        pr_number = int(url_parts[-1])
    except Exception as e:
        logger.error(f"Webhook parsing failed: {str(e)}")
        return
        
    agent_id = os.environ.get("AGENT_ID")
    agent_alias_id = os.environ.get("ALIAS_ID")
    session_id = f"webhook-{owner}-{repo}-{pr_number}"
    prompt = f"PR {pr_url}의 데이터를 가져와 정적 분석 및 보안 검사를 수행하고, 최종 결과를 PR에 댓글로 남긴 후 요약을 반환해줘."
    
    try:
        response = bedrock_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=prompt
        )
        
        completion = ""
        for stream_event in response.get("completion", []):
            chunk = stream_event.get("chunk", {})
            if chunk:
                completion += chunk.get("bytes", b"").decode("utf-8")
                
        send_slack_notification(pr_url, "성공", completion)
    except Exception as agent_err:
        logger.error(f"Agent failed: {str(agent_err)}")
        send_slack_notification(pr_url, "실패", str(agent_err))