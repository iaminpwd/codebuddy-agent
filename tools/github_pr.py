import os
import urllib.request
import urllib.error
import json
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
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            text = response.read().decode('utf-8')
            if not text.strip():
                return {"status": "success", "data": "변경 사항이 없습니다."} # 빈 PR 방어 
            return {"status": "success", "data": text}
    except urllib.error.HTTPError as e:
        return {"status": "error", "message": f"GitHub API error: {e.code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def post_pr_comment(owner: str, repo: str, pr_number: int, comment: str) -> dict:
    """Agent의 최종 리뷰 마크다운 리포트를 PR 댓글로 등록합니다."""
    headers = _get_headers()
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    payload = {"body": comment}
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as response:
            return {"status": "success", "message": "Comment posted successfully."}
    except urllib.error.HTTPError as e:
        return {"status": "error", "message": e.read().decode('utf-8')}
    except Exception as e:
        return {"status": "error", "message": str(e)}