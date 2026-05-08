"""内置工具：安全算术表达式求值（仅四则运算与括号）。"""

from __future__ import annotations

import ast
from typing import Union


def _eval_ast(node: ast.AST) -> Union[int, float]:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        v = node.value
        if type(v) is bool:
            raise ValueError("不允许布尔字面量")
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return v
        raise ValueError("只允许整型或浮点数字面量")
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval_ast(node.operand)
        if isinstance(node.op, ast.UAdd):
            return _eval_ast(node.operand)
        raise ValueError("不支持的一元运算符")
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            raise ValueError("不支持的二元运算符（仅允许 + - * /）")
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    raise ValueError("不允许的表达式结构")


def _format_number(n: Union[int, float]) -> str:
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)


def evaluate_math(expression: str) -> str:
    """对仅含 + - * /、括号与数字常量的表达式求值。"""
    expr = (expression or "").strip()
    if not expr:
        return "错误: 表达式不能为空。"

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return f"错误: 语法无效: {e}"

    try:
        value = _eval_ast(tree)
    except ZeroDivisionError:
        return "错误: 除数不能为零。"
    except ValueError as e:
        return f"错误: {e}"

    return _format_number(value)
