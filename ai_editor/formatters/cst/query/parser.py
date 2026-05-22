"""Selector parser for CST query expressions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lark import Lark, Token, Transformer, v_args


class QueryParseError(ValueError):
    """Raised when selector syntax is invalid."""


class Combinator(str, Enum):
    DESCENDANT = "descendant"
    CHILD = "child"
    ADJACENT = "adjacent"
    SIBLING = "sibling"


class PredicateOp(str, Enum):
    EXISTS = "exists"
    EQ = "eq"
    NE = "ne"
    CONTAINS = "contains"


@dataclass(frozen=True)
class Predicate:
    attr: str
    op: PredicateOp
    value: str | None = None


class PseudoKind(str, Enum):
    FIRST_CHILD = "first-child"
    LAST_CHILD = "last-child"
    NTH_CHILD = "nth-child"


@dataclass(frozen=True)
class Pseudo:
    kind: PseudoKind
    value: str | None = None


@dataclass(frozen=True)
class SelectorStep:
    node_type: str | None
    predicates: tuple[Predicate, ...] = ()
    pseudos: tuple[Pseudo, ...] = ()
    combinator: Combinator = Combinator.DESCENDANT


@dataclass(frozen=True)
class Query:
    steps: tuple[SelectorStep, ...] = ()
    raw: str = ""


_GRAMMAR = r"""
start: selector
selector: step (combinator step)*
combinator: ">"              -> child
          | "+"              -> adjacent
          | "~"              -> sibling
          | WS               -> descendant
step: node_name predicate* pseudo*
node_name: IDENT             -> node_name
         | STAR              -> wildcard
predicate: "[" IDENT pred_expr? "]"
pred_expr: "=" scalar        -> eq
         | "!=" scalar       -> ne
         | "*=" scalar       -> contains
pseudo: ":" IDENT pseudo_arg?
pseudo_arg: "(" scalar ")"
scalar: ESCAPED_STRING       -> quoted
      | IDENT                -> ident
      | SIGNED_INT           -> integer
STAR: "*"
IDENT: /[A-Za-z_][A-Za-z0-9_.-]*/
WS: /[ \t]+/
%import common.ESCAPED_STRING
%import common.SIGNED_INT
%ignore /[ \t]*\n[ \t]*/
"""


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


@v_args(inline=True)
class _AstBuilder(Transformer):
    def node_name(self, token: Token) -> str | None:
        return str(token)

    def wildcard(self, _token: Token) -> str | None:
        return None

    def quoted(self, token: Token) -> str:
        return _unquote(str(token))

    def ident(self, token: Token) -> str:
        return str(token)

    def integer(self, token: Token) -> str:
        return str(token)

    def eq(self, value: str) -> tuple[PredicateOp, str]:
        return (PredicateOp.EQ, value)

    def ne(self, value: str) -> tuple[PredicateOp, str]:
        return (PredicateOp.NE, value)

    def contains(self, value: str) -> tuple[PredicateOp, str]:
        return (PredicateOp.CONTAINS, value)

    def predicate(
        self,
        name: Token,
        expression: tuple[PredicateOp, str] | None = None,
    ) -> Predicate:
        if expression is None:
            return Predicate(attr=str(name), op=PredicateOp.EXISTS, value=None)
        op, value = expression
        return Predicate(attr=str(name), op=op, value=value)

    def pseudo_arg(self, value: str) -> str:
        return value

    def pseudo(self, name: Token, value: str | None = None) -> Pseudo:
        raw = str(name)
        try:
            kind = PseudoKind(raw)
        except ValueError as exc:
            raise QueryParseError(f"Unknown pseudo selector: {raw}") from exc
        return Pseudo(kind=kind, value=value)

    def child(self) -> Combinator:
        return Combinator.CHILD

    def adjacent(self) -> Combinator:
        return Combinator.ADJACENT

    def sibling(self) -> Combinator:
        return Combinator.SIBLING

    def descendant(self, _token: Token) -> Combinator:
        return Combinator.DESCENDANT

    def step(
        self,
        node_type: str | None,
        *parts: Any,
    ) -> SelectorStep:
        predicates: list[Predicate] = []
        pseudos: list[Pseudo] = []
        for part in parts:
            if isinstance(part, Predicate):
                predicates.append(part)
            elif isinstance(part, Pseudo):
                pseudos.append(part)
        return SelectorStep(
            node_type=node_type,
            predicates=tuple(predicates),
            pseudos=tuple(pseudos),
        )

    def selector(self, first: SelectorStep, *rest: Any) -> Query:
        steps = [first]
        pending = Combinator.DESCENDANT
        for part in rest:
            if isinstance(part, Combinator):
                pending = part
            elif isinstance(part, SelectorStep):
                steps.append(
                    SelectorStep(
                        node_type=part.node_type,
                        predicates=part.predicates,
                        pseudos=part.pseudos,
                        combinator=pending,
                    )
                )
                pending = Combinator.DESCENDANT
        return Query(steps=tuple(steps))

    def start(self, query: Query) -> Query:
        return query


_PARSER = Lark(_GRAMMAR, parser="lalr", maybe_placeholders=False)


def parse_selector(selector: str) -> Query:
    """Parse selector text into a Query AST."""
    text = selector.strip()
    if not text:
        raise QueryParseError("Selector is empty")
    try:
        tree = _PARSER.parse(text)
        query = _AstBuilder().transform(tree)
    except QueryParseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise QueryParseError(f"Invalid selector: {selector}") from exc
    if not isinstance(query, Query):
        raise QueryParseError(f"Invalid selector: {selector}")
    return Query(steps=query.steps, raw=text)
