import os
import requests
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GITHUB_API_URL = "https://api.github.com"

def _get_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("Critical Security: GITHUB_TOKEN environment variable is missing.")
        raise ValueError("GitHub Access Token is missing.")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def get_github_pr(owner: str, repo: str, pr_number: int) -> dict:
    """GitHub PR의 소스 코드 변경 분량(Diff)을 추출합니다."""
    headers = _get_headers()
    headers["Accept"] = "application/vnd.github.v3.diff" # Diff 추출용 헤더 변경
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            if not response.text.strip():
                return {"status": "success", "data": "변경 사항이 없습니다."} # 빈 PR 방어 
            return {"status": "success", "data": response.text}
        return {"status": "error", "message": f"GitHub API error: {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def post_pr_comment(owner: str, repo: str, pr_number: int, comment: str) -> dict:
    """Agent의 최종 리뷰 마크다운 리포트를 PR 댓글로 등록합니다."""
    headers = _get_headers()
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    payload = {"body": comment}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 201:
            return {"status": "success", "message": "Comment posted successfully."}
        return {"status": "error", "message": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}