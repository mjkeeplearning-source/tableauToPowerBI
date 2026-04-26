"""Parameter reference rewriter — see spec §5.7 'Stage 3 calc translator'.

`numeric_what_if` / `categorical_selector` → `[<name> SelectedValue]` measure ref.
`internal_constant` → DAX-literal expansion of the default value.
`formatting_control` is v1-deferred; its parameters never reach stage 3
(stage 2 routes them to unsupported[]).
`unsupported` intent → leave the reference as-is and let the syntax gate
or downstream consumer flag it."""
from __future__ import annotations

import re

from tableau2pbir.ir.parameter import Parameter, ParameterIntent

_REF_RE = re.compile(r"\[(?P<name>[^\[\]]+)\]")


def rewrite_parameter_refs(
    tableau_expr: str, parameters: tuple[Parameter, ...],
) -> str:
    """Rewrite every `[ParamName]` token in `tableau_expr` per its intent.
    Tokens that don't match any known parameter are left untouched (they
    may reference fields, not parameters)."""
    by_name = {p.name: p for p in parameters}

    def _sub(match: re.Match[str]) -> str:
        name = match.group("name")
        param = by_name.get(name)
        if param is None:
            return match.group(0)
        if param.intent in (
            ParameterIntent.NUMERIC_WHAT_IF,
            ParameterIntent.CATEGORICAL_SELECTOR,
        ):
            return f"[{name} SelectedValue]"
        if param.intent is ParameterIntent.INTERNAL_CONSTANT:
            return param.default
        return match.group(0)

    return _REF_RE.sub(_sub, tableau_expr)
