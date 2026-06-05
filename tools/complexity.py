import logging
import ast

logger = logging.getLogger()

def analyze_complexity(code: str) -> dict:
    """제출된 파이썬 코드의 Cyclomatic Complexity를 내장 ast 모듈로 측정합니다."""
    try:
        if not code.strip():
            return {"status": "error", "message": "분석할 코드가 비어있습니다."}
            
        tree = ast.parse(code)
        blocks = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.BoolOp)):
                        if isinstance(child, ast.BoolOp):
                            complexity += len(child.values) - 1
                        else:
                            complexity += 1
                
                if complexity <= 5: rank = 'A'
                elif complexity <= 10: rank = 'B'
                elif complexity <= 20: rank = 'C'
                elif complexity <= 30: rank = 'D'
                elif complexity <= 40: rank = 'E'
                else: rank = 'F'
                
                blocks.append({
                    "name": node.name,
                    "complexity": complexity,
                    "rank": rank
                })
                
        return {"status": "success", "analysis": blocks}
    except SyntaxError as e:
        return {"status": "error", "message": f"Syntax Error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}