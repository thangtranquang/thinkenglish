"""TC-18.19: no string-formatted SQL in repositories; routers never run SQL."""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
EXEC_NAMES = {"execute", "executemany", "executescript"}


def _exec_calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in EXEC_NAMES:
            yield node


def _is_formatted(arg: ast.expr) -> bool:
    if isinstance(arg, ast.JoinedStr):
        return True
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Mod, ast.Add)):
        return True
    return (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
            and arg.func.attr == "format")


def test_repositories_use_only_parameterized_sql():
    files = sorted((APP / "repositories").glob("*.py"))
    assert files
    violations = [
        f"{p.name}:{call.lineno}"
        for p in files for call in _exec_calls(p)
        if call.args and _is_formatted(call.args[0])
    ]
    assert violations == []


def test_routers_contain_no_sql_execution():
    offenders = [p.name for p in (APP / "routers").glob("*.py") if list(_exec_calls(p))]
    assert offenders == []
