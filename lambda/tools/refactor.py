# lambda/tools/testgen.py
def generate_unit_test(code: str) -> dict:
    """Agent가 pytest 기반 단위 테스트 생성을 인지하도록 컨텍스트를 제공합니다."""
    return {"status": "success", "instruction": "분석된 코드의 에지 케이스에 맞는 pytest 코드를 생성하십시오."}

# lambda/tools/refactor.py
def suggest_refactor(code: str) -> dict:
    """Agent에게 PEP8 및 클린코드 기반 리팩토링 대상 가이드를 제공합니다."""
    return {"status": "success", "instruction": "해당 코드의 함수 분할 및 명명 규칙(snake_case) 개선안을 작성하십시오."}