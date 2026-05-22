"""Semantic LibCST node classification for CST formatter."""
from __future__ import annotations

from typing import Optional, Sequence

import libcst as cst


def _get_decorator_names(node: cst.FunctionDef) -> tuple[str, ...]:
    """Return decorator base names (Name/Attribute tail) in source order."""
    names: list[str] = []
    for dec in node.decorators:
        expr = dec.decorator
        if isinstance(expr, cst.Name):
            names.append(expr.value)
        elif isinstance(expr, cst.Attribute):
            names.append(expr.attr.value)
        elif isinstance(expr, cst.Call) and isinstance(expr.func, (cst.Name, cst.Attribute)):
            if isinstance(expr.func, cst.Name):
                names.append(expr.func.value)
            else:
                names.append(expr.func.attr.value)
    return tuple(names)


def get_node_kind(node: cst.CSTNode, class_stack: Sequence[str]) -> str:
    """Decorator-aware kind: property/classmethod/staticmethod override function/method."""
    if isinstance(node, cst.Module):
        return "module"
    if isinstance(node, cst.ClassDef):
        return "class"
    if isinstance(node, cst.FunctionDef):
        decs = _get_decorator_names(node)
        if "property" in decs:
            return "property"
        if "classmethod" in decs:
            return "classmethod"
        if "staticmethod" in decs:
            return "staticmethod"
        return "method" if class_stack else "function"
    if isinstance(node, (cst.Import, cst.ImportFrom)):
        return "import"
    if isinstance(node, (cst.Assign, cst.AnnAssign)):
        return "attribute" if class_stack else "variable"
    if isinstance(node, cst.BaseSmallStatement):
        return "smallstmt"
    if isinstance(node, cst.BaseStatement):
        return "stmt"
    return "node"


def get_node_name(node: cst.CSTNode) -> Optional[str]:
    """Return semantic name for declaration-like nodes when available."""
    if isinstance(node, (cst.FunctionDef, cst.ClassDef)):
        return node.name.value
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, (cst.Assign, cst.AnnAssign)):
        targets = node.targets if isinstance(node, cst.Assign) else [node.target]
        for target in targets:
            tgt = target.target if isinstance(target, cst.AssignTarget) else target
            if isinstance(tgt, cst.Name):
                return tgt.value
    return None


def get_node_qualname(
    node: cst.CSTNode,
    class_stack: Sequence[str],
    func_stack: Sequence[str],
) -> Optional[str]:
    """Return dotted qualname for class/function-like declarations."""
    if isinstance(node, cst.ClassDef):
        return ".".join([*class_stack, node.name.value]) if class_stack else node.name.value
    if isinstance(node, cst.FunctionDef):
        if class_stack:
            return ".".join([*class_stack, node.name.value])
        parts = [*func_stack[:-1], node.name.value]
        return ".".join(parts) if parts else node.name.value
    return ".".join([*class_stack, *func_stack]) if (class_stack or func_stack) else None
