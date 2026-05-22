"""Selector executor for CST query language."""
from __future__ import annotations

from typing import Any

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.query.index_builder import Match, NodeInfo, build_index_from_tree
from ai_editor.formatters.cst.query.parser import (
    Combinator,
    Predicate,
    PredicateOp,
    Query,
    SelectorStep,
    parse_selector,
)


def _compare(left: Any, op: PredicateOp, right: str) -> bool:
    left_s = "" if left is None else str(left)
    if op == PredicateOp.EQ:
        return left_s == right
    if op == PredicateOp.NE:
        return left_s != right
    return right in left_s


def _get_attr(info: NodeInfo, key: str) -> Any:
    if key == "name":
        return info.name
    if key == "qualname":
        return info.qualname
    if key == "kind":
        return info.kind
    if key == "node_type":
        return info.node_type
    if key == "stable_id":
        return info.stable_id
    return None


def _matches_predicate(info: NodeInfo, predicate: Predicate) -> bool:
    return _compare(_get_attr(info, predicate.key), predicate.op, predicate.value)


def _matches_node_type(info: NodeInfo, node_type: str) -> bool:
    return info.kind == node_type or info.node_type == node_type


def _matches_step(info: NodeInfo, step: SelectorStep) -> bool:
    if not _matches_node_type(info, step.node_type):
        return False
    return all(_matches_predicate(info, pred) for pred in step.predicates)


def _apply_combinator(
    prev_matches: list[NodeInfo],
    candidates: list[NodeInfo],
    combinator: Combinator,
    all_by_obj: dict[str, NodeInfo],
) -> list[NodeInfo]:
    if not prev_matches:
        return candidates
    prev_by_obj = {str(id(info.node)): info for info in prev_matches}
    if combinator == Combinator.CHILD:
        allowed = {str(id(p.node)) for p in prev_matches}
        return [cand for cand in candidates if cand.parent is not None and str(id(cand.parent)) in allowed]
    out: list[NodeInfo] = []
    for cand in candidates:
        cur = cand.parent
        while cur is not None:
            if str(id(cur)) in prev_by_obj:
                out.append(cand)
                break
            parent_info = all_by_obj.get(str(id(cur)))
            cur = parent_info.parent if parent_info else None
    return out


def _apply_step(all_nodes: list[NodeInfo], prior: list[NodeInfo], step: SelectorStep) -> list[NodeInfo]:
    base = [info for info in all_nodes if _matches_step(info, step)]
    all_by_obj = {str(id(info.node)): info for info in all_nodes}
    return _apply_combinator(prior, base, step.combinator, all_by_obj)


def _eval_query(nodes: list[NodeInfo], query: Query) -> list[NodeInfo]:
    current: list[NodeInfo] = []
    for idx, step in enumerate(query.steps):
        current = _apply_step(nodes, [] if idx == 0 else current, step)
    return current


def _to_match(info: NodeInfo, include_code: bool = False) -> Match:
    code = info.node.code if include_code else None
    return Match(
        stable_id=info.stable_id,
        kind=info.kind,
        node_type=info.node_type,
        name=info.name,
        qualname=info.qualname,
        start_line=info.start_line,
        start_col=info.start_col,
        end_line=info.end_line,
        end_col=info.end_col,
        code=code,
    )


def query_source(source: str, selector: str, include_code: bool = False) -> list[Match]:
    """Query raw source by selector string."""
    from ai_editor.formatters.cst.tree_builder import create_tree_from_code

    tree = create_tree_from_code(source)
    return query_tree(tree, selector, include_code=include_code)


def query_tree(tree: CSTTree, selector: str, include_code: bool = False) -> list[Match]:
    """Run selector query on a CSTTree and return match list."""
    query = parse_selector(selector)
    nodes = build_index_from_tree(tree)
    hits = _eval_query(nodes, query)
    return [_to_match(hit, include_code=include_code) for hit in hits]


def cst_list_units(tree: CSTTree) -> list[dict[str, object]]:
    """Return flat list of stable-id addressed units from CST metadata."""
    rows = [
        {
            "stable_id": meta.stable_id,
            "type": meta.type,
            "kind": meta.kind,
            "name": meta.name,
            "qualname": meta.qualname,
            "start_line": meta.start_line,
            "end_line": meta.end_line,
        }
        for meta in tree.metadata_map.values()
        if meta.stable_id
    ]
    rows.sort(key=lambda row: (int(row["start_line"]), int(row["end_line"])))
    return rows
