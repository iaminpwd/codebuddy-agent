import logging
from radon.visitors import ComplexityVisitor

logger = logging.getLogger()

def analyze_complexity(code: str) -> dict:
    """제출된 파이썬 코드의 Cyclomatic Complexity를 측정합니다."""
    try:
        if not code.strip():
            return {"status": "error", "message": "분석할 코드가 비어있습니다."}
            
        visitor = ComplexityVisitor.from_code(code)
        blocks = []
        for block in visitor.blocks:
            blocks.append({
                "name": block.name,
                "complexity": block.complexity,
                "rank": block.letter # A~F 등급 산출
            })
        return {"status": "success", "analysis": blocks}
    except SyntaxError as e:
        return {"status": "error", "message": f"Syntax Error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}