# tools/refactor.py
def suggest_refactor(code: str) -> dict:
    """Agent에게 PEP8 및 클린코드 기반 리팩토링 대상 가이드를 제공합니다."""
    return {"status": "success", "instruction": "해당 코드의 함수 분할 및 명명 규칙(snake_case) 개선안을 작성하십시오."}