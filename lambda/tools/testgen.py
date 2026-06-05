# FILE: ./lambda/tools/testgen.py
import ast
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def generate_unit_test(code: str) -> dict:
    """
    제출된 파이썬 코드의 AST(추상 구문 트리)를 분석하여,
    Bedrock Agent가 멱등성 있고 정밀한 pytest 코드를 생성할 수 있도록 가이드를 반환합니다.
    """
    if not code or not code.strip():
        logger.warning("No code provided for test generation.")
        return {"status": "error", "message": "분석할 소스 코드가 비어 있습니다."}
        
    try:
        # 소스 코드를 AST 구문 트리로 파싱
        tree = ast.parse(code)
        functions = []
        
        # 트리 내부를 순회하며 함수 정의(FunctionDef) 객체 탐색 및 메타데이터 추출
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 함수의 매개변수 목록 추출 (예: arg1, arg2)
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args
                })
                
        # 추출된 함수가 없을 경우의 기본 방어 로직
        if not functions:
            logger.info("No explicit functions found in the provided code.")
            return {
                "status": "success",
                "instruction": (
                    "주어진 코드에 명시적인 함수가 정의되어 있지 않습니다. "
                    "코드 전체의 논리적 흐름에 대한 기본 pytest 코드를 작성하고, "
                    "최소 1개의 에지 케이스를 포함해 주십시오."
                )
            }

        # 추출된 함수명 및 파라미터 조합 생성
        func_signatures = ", ".join([f"{f['name']}({', '.join(f['args'])})" for f in functions])
        logger.info(f"Successfully extracted functions for testing: {func_signatures}")
        
        # Agent에게 전달할 강력한 컨텍스트 프롬프트
        instruction = (
            f"다음 식별된 함수들에 대한 pytest 기반 단위 테스트 코드를 작성하십시오: {func_signatures}. "
            "요구사항:\n"
            "1. 각 함수당 최소 1개의 '정상 케이스(Happy path)'와 1개의 '경계값/예외 케이스(Edge case)'를 필수 포함할 것.\n"
            "2. 테스트용 Mocking이 필요하다면 `pytest-mock` 구조를 사용할 것.\n"
            "3. 응답은 마크다운 코드 블록(```python) 형태로만 깔끔하게 작성할 것."
        )
        
        return {
            "status": "success",
            "detected_functions": len(functions),
            "instruction": instruction
        }
        
    except SyntaxError as syntax_err:
        logger.error(f"Syntax error in provided code: {str(syntax_err)}")
        return {
            "status": "error", 
            "message": f"제출된 코드의 문법 오류로 인해 테스트를 생성할 수 없습니다: {str(syntax_err)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error during AST parsing: {str(e)}")
        return {
            "status": "error", 
            "message": f"AST 분석 중 알 수 없는 오류 발생: {str(e)}"
        }