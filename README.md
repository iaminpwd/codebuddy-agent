# 10장. 통합 프로젝트: CodeBuddy 최종 완성

**CodeBuddy: 당신의 AI 페어 프로그래머 "GitHub PR 자동 리뷰 Agent"**

## 1. 개요 및 배울 내용

모든 기능을 통합하고, 실제 GitHub PR에서 자동 리뷰까지 실행하며, 최종 결과물을 배포합니다.

| 단계 | 작업 | 상세 내용 / 명령어 |
| --- | --- | --- |
| 1 | 인프라 배포 | CloudFormation으로 인프라 1클릭 배포 |
| 2 | PR 열기 | 이제 PR만 열면 CodeBuddy가 작동 |
| 3 | 샘플 테스트 | 샘플 PR 생성 및 자동 리뷰 확인 (`git push origin feature-branch`, `gh pr create --title "Add login" -body "..."`) |
| 4 | 고도화 | 엣지 케이스 및 성능 테스트, 비용 분석 및 Slack 알림 연동 |
| 5 | 추가 미션 | 나만의 Tool 추가 미션 |

**Agent 자동 수행 항목:**

* 코드 리뷰 댓글 등록
* 테스트 코드 제안
* 리팩토링 제안
* Slack 알림 전송

**실습 환경:**

* **환경:** Google Colab (Boto3)
* **리전:** ap-northeast-2 (서울)
* **사전 준비:** 모든 Tool과 Lambda, API Gateway, GitHub App 완성

---

## 2. CodeBuddy 최종 아키텍처

1. **GitHub PR 생성 (Webhook)**
2. **API Gateway (POST /review)**: API Key + Rate Limiting 적용
3. **Orchestrator Lambda**
   * PR URL 파싱 (owner, repo, pr_number)
   * Bedrock Agent 호출 (`sessionid=webhook-{pr}`)
   * 결과 반환
4. **Bedrock Agent (CodeBuddy)**
   * **Instructions:** 코드 리뷰
   * **Knowledge Base:** PEP8, OWASP
   * **Action Group (6개 Tools):** `get_github_pr`, `post_pr_comment`, `analyze_complexity`, `generate_unit_test`, `send_slack`, `suggest_refactor`

*이 모든 것이 단일 PR 이벤트에서 자동 실행됩니다!*

---

## 3. 실습 1: 환경 초기화 (기존 리소스 정리)

**왜 정리가 필요한가?**

* 중복 리소스로 인한 충돌 방지 및 명확한 최종 배포를 위해
* 깨끗한 환경에서 최종 배포 테스트 가능

```bash
# Lambda 함수 삭제
$ aws lambda delete-function --function-name codebuddy-orchestrator

# API Gateway 삭제 (직접 생성한 경우)
$ aws apigateway delete-rest-api --rest-api-id <api-id>
```

> **참고:** Agent와 Knowledge Base는 유지하며 다시 만들 필요 없습니다. 실습 시간이 부족하면 정리 없이 기존 리소스 활용도 가능합니다.

---

## 4. 실습 2: CloudFormation으로 인프라 코드로 정의

API Gateway, Lambda, IAM 역할, Lambda Layer 등 모든 인프라를 재현 가능하고 버전 관리 가능한 YAML로 정의합니다.

```yaml
Resources:
  OrchestratorLambda:
    Type: 'AWS::Lambda::Function'
    Properties:
      FunctionName: codebuddy-orchestrator
      Runtime: python3.12
      Handler: orchestrator.handler
      Code:
        S3Bucket: !Sub 'codebuddy-deployment-bucket-${AWS::AccountId}'
        S3Key: 'lambda_code.zip'
      Environment:
        Variables:
          AGENT_ID: !Ref AgentId
          ALIAS_ID: !Ref AliasId
          GITHUB_TOKEN: !Ref GitHubToken
          SLACK_WEBHOOK_URL: !Ref SlackWebhookUrl
          WEBHOOK_SECRET: !Ref WebhookSecret
      Timeout: 300
      MemorySize: 1024

  CodeBuddyApi:
    Type: 'AWS::ApiGateway::RestApi'
    Properties:
      Name: CodeBuddyAPI

  ReviewResource:
    Type: 'AWS::ApiGateway::Resource'
    Properties:
      RestApiId: !Ref CodeBuddyApi
      ParentId: !GetAtt CodeBuddyApi.RootResourceId
      PathPart: review
```

*(전체 템플릿은 `cloudformation/template.yaml`을 참고하세요.)*

---

## 5. 실습 3: CloudFormation으로 1클릭 배포

```bash
# 1. 배포용 S3 버킷 생성 (최초 1회 필수)
$ AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
$ aws s3 mb s3://codebuddy-deployment-bucket-${AWS_ACCOUNT_ID}

# 2. 코드 압축 및 CloudFormation 1클릭 배포 (One-Liner)
$ cd lambda && zip -r ../lambda_code.zip orchestrator.py && cd .. && zip -r lambda_code.zip tools/ && \
  aws s3 cp lambda_code.zip s3://codebuddy-deployment-bucket-${AWS_ACCOUNT_ID}/lambda_code.zip && \
  aws cloudformation deploy \
    --template-file cloudformation/template.yaml \
    --stack-name CodeBuddyStack \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        AgentId=your-agent-id \
        AliasId=your-alias-id \
        GitHubToken=github_pat_xxx \
        SlackWebhookUrl=https://hooks.slack.com/... \
        WebhookSecret=your-webhook-secret

# 3. 배포 확인 (Webhook URL 및 API Key 획득)
$ aws cloudformation describe-stacks \
    --stack-name CodeBuddyStack \
    --query "Stacks[0].Outputs" \
    --output table
```

---

## 6. 실습 4: 테스트용 Repository 연동 및 PR 올리기

API Gateway는 API Key를 필수로 요구하므로, GitHub Webhook UI 대신 **GitHub Actions**를 사용하여 보안 통신(`x-api-key` 헤더 삽입)을 수행해야 합니다.

### 6-1. Repository 설정
1. GitHub에서 `codebuddy-test` 라는 테스트용 Repository를 생성하고 Clone 합니다.
```bash
$ git clone https://github.com/your-org/codebuddy-test
$ cd codebuddy-test
```
2. Repository의 **Settings -> Secrets and variables -> Actions** 에서 다음 3가지 Secret을 등록합니다.
   - `CODEBUDDY_WEBHOOK_URL`: 위 배포 결과에서 얻은 `WebhookEndpoint` 값
   - `CODEBUDDY_API_KEY`: 위 배포 결과에서 얻은 `ApiKeySecret` 값
   - `CODEBUDDY_WEBHOOK_SECRET`: 배포 시 입력한 `your-webhook-secret` 값

3. `.github/workflows/codebuddy.yml` 파일을 생성하고, 본 CodeBuddy 템플릿의 내용을 복사하여 넣습니다. (이 워크플로가 API 호출을 담당합니다.)

### 6-2. 샘플 코드 작성 및 PR 생성

```python
# app.py (의도적으로 버그와 스타일 문제 포함)
def add(a,b):
    return a+b

def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return execute(query)
```

```bash
# PR 생성
$ git checkout -b feature/login
$ git add .
$ git commit -m "Add login functions and workflow"
$ git push origin feature/login
$ gh pr create --title "Add login" --body "Please review" --base main
```

> **참고:** PR이 생성되면 GitHub Action이 트리거되어 CodeBuddy API로 Payload를 안전하게 전송합니다. Action 탭에서 실행 로그를 확인할 수 있습니다.

---

## 7. 실습 5: 자동 리뷰 댓글 및 결과 확인

GitHub PR에서 확인할 내용은 다음과 같습니다.

| 항목 | 예상 결과 |
| --- | --- |
| **댓글** | Agent가 자동으로 댓글 등록 |
| **스타일 위반** | snake_case 권장, 들여쓰기 등 |
| **보안 취약점** | SQL Injection 경고 |
| **복잡도** | get_user 함수 복잡도 리포트 |
| **테스트 코드** | pytest 생성 제안 |
| **리팩토링 제안** | 함수 분할 권고 |

```bash
# Lambda 로그 확인
$ aws logs tail /aws/lambda/codebuddy-orchestrator --follow
```

---

## 8. 실습 6: 엣지 케이스 테스트

안정적인 서비스 운영을 위한 필수 테스트 시나리오입니다.

| 케이스 | 설명 | 예상 동작 |
| --- | --- | --- |
| **빈 PR** | 변경 파일 없음 | "변경 사항이 없습니다" 댓글 |
| **대용량 PR** | 5000줄 변경 | 청크 분할 분석, 시간 초과 없음 |
| **바이너리 파일** | 이미지, PDF 포함 | 무시하고 코드만 분석 |
| **잘못된 PR URL** | 존재하지 않는 PR | 오류 메시지 댓글 |
| **동시 PR** | 여러 PR 동시 열림 | 각각 독립적으로 처리 |

```python
# 자동화 테스트 스크립트 (선택)
import requests

test_cases = [
    {"pr_url": "https://github.com/owner/repo/pull/1", "expected": 200},
    {"pr_url": "invalid", "expected": 400},
]

for case in test_cases:
    resp = requests.post(api_url, json=case)
    assert resp.status_code == case["expected"]
```

---

## 9. 실습 7: 성능 측정 및 모니터링

| 지표 | 계산 방법 | 목표 |
| --- | --- | --- |
| **평균 리뷰 시간** | 총 처리 시간 / PR 수 | < 30초 |
| **성공률** | (성공한 PR 수 / 전체 PR수) × 100 | > 95% |
| **Tool 호출 횟수** | 한 PR당 평균 Tool 호출 횟수 | 3~5회 |

```python
# Lambda에 CloudWatch 커스텀 메트릭 추가
import time

start = time.time()
# ... Agent 호출 ...
duration = time.time() - start

cloudwatch.put_metric_data(
    Namespace='CodeBuddy',
    MetricData=[{
        'MetricName': 'ReviewDuration',
        'Value': duration,
        'Unit': 'Seconds'
    }]
)
```

---

## 10. 실습 8: 비용 분석 (월간 예상 비용)

*(서울 리전 기준, 하루 100회 / 월 22일 운영 가정)*

| 서비스 | 단가 | 일 예상 (100회) | 월 예상 (22일) |
| --- | --- | --- | --- |
| **Lambda (1024MB, 300초)** | $0.00001667/GB-초 | $0.50 | $11.00 |
| **API Gateway** | $1.00/백만 호출 | $0.003 | $0.07 |
| **Bedrock (Claude 4.6)** | 입력 $0.003/1K, 출력 $0.015/1K | $0.20 | $4.40 |
| **Bedrock (임베딩)** | $0.0001/1K 토큰 | $0.01 | $0.22 |
| **OpenSearch Serverless** | $0.24/OCU-시간 | $0.50 | $11.00 |
| **CloudWatch Logs** | $0.50/GB | $0.05 | $1.10 |
| **합계** | | **$1.26** | **$27.79** |

**비용 절감 팁:**

* 캐싱 (동일 PR 재분석 방지)
* 간단한 리뷰 시 Haiku 모델 사용
* OpenSearch를 주문형으로 설정
* Lambda 메모리 최적화

---

## 11. 실습 9: Slack 연동 (리뷰 완료 알림)

```python
# Orchestrator Lambda에 Slack 알림 추가
import requests
import os

SLACK_WEBHOOK = os.environ['SLACK_WEBHOOK_URL']

def send_slack_notification(pr_url, status, summary):
    message = {
        "text": f"🚀 *CodeBuddy 리뷰 완료*\nPR: {pr_url}\n상태: {status}\n요약: {summary[:200]}..."
    }
    requests.post(SLACK_WEBHOOK, json=message)

# handler 내에서 Agent 호출 후 실행
send_slack_notification(pr_url, "success", result_text[:200])
```

---

## 12. 문서화 자동화 결과 및 프로젝트 리포트

Agent를 활용하여 README 및 팀 코드 품질 리포트를 자동 생성할 수 있습니다.

```python
# 여러 Repository 일괄 분석 함수 예시
def batch_analyze_repos(org_name, repos_list):
    """조직의 여러 저장소를 분석하여 종합 리포트 생성"""
    results = {}
    for repo in repos_list:
        prs = get_recent_prs(org_name, repo)
        for pr in prs:
            results[f"{repo}#{pr.number}"] = analyze_pr(pr.url)
    return generate_team_report(results)
```

```markdown
# 생성된 팀 코드 품질 리포트 예시 (2025년 3월)
## 요약
- 전체 PR 수: 45
- 평균 복잡도: 7.2 (양호)
- 발견된 취약점: 12건 (8건 수정 완료)
- 테스트 코드 누락 PR: 15건
```

**실제 보안 취약점 발견 사례 (OWASP 기반 탐지):**

| 취약점 유형 | 탐지된 코드 | Agent 제안 해결책 |
| --- | --- | --- |
| **SQL Injection** | `query = f"SELECT * FROM users WHERE id={id}"` | `cursor.execute("SELECT * FROM users WHERE id = %s", (id,))` |
| **하드코딩된 비밀번호** | `API_KEY = "12345"` | 환경 변수 또는 AWS Secrets Manager 사용 |
| **디버그 코드 남김** | `console.log(secret_data)` | `if debug:` 처리 또는 제거 |
| **안전하지 않은 역직렬화** | `pickle.loads(data)` | `json.loads(data)` 사용 |

---

## 13. 최종 결과물 제출 및 트러블슈팅

**제출 항목 가이드:**

* **GitHub Repository (필수):** 모든 코드 (Lambda, CloudFormation, 샘플 등)
* **README.md (필수):** 설치 방법, 사용법, API 문서
* **데모 영상 (필수):** PR 생성 ~ 자동 리뷰 ~ Slack 알림까지 1분 내외
* **CloudFormation 템플릿 (필수):** 1클릭 배포 가능 형태
* **보고서 (선택):** 비용 분석 표, 테스트(엣지 케이스/성능) 결과 리포트

**Repository 구조 예시:**

```text
codebuddy-agent/
├── README.md
├── cloudformation/
│   └── template.yaml
├── lambda/
│   └── orchestrator.py
├── tools/
│   ├── github_pr.py
│   ├── complexity.py
│   ├── testgen.py
│   └── refactor.py
├── layer/
├── tests/
│   └── test_e2e.py
├── docs/
│   └── api-spec.yaml
└── demo/
└── demo.mp4
```

**자주 발생하는 오류 해결 가이드:**

* **Agent 호출 403:** IAM의 `bedrock:InvokeAgent` 정책 확인 
* **Lambda timeout:** timeout을 300초로 증가, maxTokens 축소 
* **API Gateway 500:** CloudWatch Logs에서 Lambda 스택 트레이스 확인 
* **Webhook 검증 실패:** GitHub Secret과 Lambda 검증 로직 값 일치 여부 확인 
* **radon 임포트 오류:** Lambda Layer에 패키지가 정상 포함되었는지 확인 
* **GitHub API rate limit:** PAT(Personal Access Token) 한도 초과 확인 및 재발급