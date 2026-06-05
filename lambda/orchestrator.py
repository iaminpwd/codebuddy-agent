# FILE: ./lambda/orchestrator.py
import os
import json
import boto3
import requests
import logging

from tools.github_pr import get_github_pr, post_pr_comment
from tools.complexity import analyze_complexity
from tools.testgen import generate_unit_test
from tools.refactor import suggest_refactor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_runtime = boto3.client(service_name="bedrock-agent-runtime", region_name="ap-northeast-2")

def send_slack_notification(pr_url: str, status: str, summary: str):
    # (기존과 동일하므로 생략 없이 유지)
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
    payload = {"text": f" *CodeBuddy 리뷰 완료*\n*PR:* {pr_url}\n*상태:* {status}\n*요약:* {summary[:200]}..."}
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Slack notification failed: {str(e)}")

# ==========================================
# [추가됨] Bedrock Agent Action Group 라우터
# ==========================================
def handle_agent_action(event):
    """Bedrock Agent가 도구를 호출할 때의 로직을 처리합니다."""
    api_path = event.get("apiPath")
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}
    request_body = {}
    if "requestBody" in event and "content" in event["requestBody"]:
        # application/json 파싱
        request_body = json.loads(event["requestBody"]["content"]["application/json"]["properties"])

    response_body = {}
    
    # OpenAPI 스키마에 정의된 경로(apiPath)에 따라 도구 실행
    try:
        if api_path == "/github/pr":
            response_body = get_github_pr(parameters.get("owner"), parameters.get("repo"), int(parameters.get("pr_number")))
        elif api_path == "/github/comment":
            response_body = post_pr_comment(request_body.get("owner"), request_body.get("repo"), int(request_body.get("pr_number")), request_body.get("comment"))
        elif api_path == "/analyze/complexity":
            response_body = analyze_complexity(request_body.get("code"))
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

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    # 분기 1: Bedrock Agent의 Action Group 호출인 경우
    if "apiPath" in event and "actionGroup" in event:
        return handle_agent_action(event)
        
    # 분기 2: API Gateway를 통한 GitHub Webhook 호출인 경우
    try:
        body = json.loads(event.get("body", "{}"))
        pr_info = body.get("pull_request")
        if not pr_info:
            return {"statusCode": 200, "body": json.dumps("Not a PR event, ignoring.")} # 핑 테스트 등 방어
            
        pr_url = pr_info.get("html_url", "unknown-url")
        url_parts = pr_url.split("/")
        owner = url_parts[-4]
        repo = url_parts[-3]
        pr_number = int(url_parts[-1])
    except Exception as e:
        logger.error(f"Webhook parsing failed: {str(e)}")
        return {"statusCode": 400, "body": json.dumps("Invalid Webhook Payload")}

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
        return {"statusCode": 200, "body": json.dumps({"status": "success"})}
        
    except Exception as agent_err:
        logger.error(f"Agent failed: {str(agent_err)}")
        send_slack_notification(pr_url, "실패", str(agent_err))
        return {"statusCode": 500, "body": json.dumps("Agent Error")}