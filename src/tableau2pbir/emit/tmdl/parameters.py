"""Parameter emission per §5.7 Stage 6."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident, tmdl_string
from tableau2pbir.ir.parameter import Parameter, ParameterIntent


def render_parameter(p: Parameter) -> dict[str, str]:
    if p.intent == ParameterIntent.NUMERIC_WHAT_IF:
        return _numeric_what_if(p)
    if p.intent == ParameterIntent.CATEGORICAL_SELECTOR:
        return _categorical_selector(p)
    if p.intent == ParameterIntent.INTERNAL_CONSTANT:
        return _internal_constant(p)
    return {}


def _numeric_what_if(p: Parameter) -> dict[str, str]:
    vals = p.allowed_values or ("0", "1", "0.1")
    mn, mx, step = (vals + ("0", "1", "0.1"))[:3]
    body = (
        f"table {tmdl_ident(p.name)}\n"
        f"\tcolumn Value\n"
        f"\t\tdataType: double\n\n"
        f"\tpartition {tmdl_ident(p.name)} = calculated\n"
        f"\t\tsource = GENERATESERIES({mn},{mx},{step})\n\n"
        f"\tmeasure {tmdl_ident(p.name + ' SelectedValue')}\n"
        f"\t\texpression: SELECTEDVALUE('{p.name}'[Value], {p.default})\n"
    )
    return {f"tables/{p.name}.tmdl": body}


def _categorical_selector(p: Parameter) -> dict[str, str]:
    rows = ", ".join("{" + tmdl_string(v) + "}" for v in p.allowed_values)
    body = (
        f"table {tmdl_ident(p.name)}\n"
        f"\tcolumn Value\n"
        f"\t\tdataType: string\n\n"
        f"\tpartition {tmdl_ident(p.name)} = calculated\n"
        f"\t\tsource = #table({{\"Value\"}}, {{{rows}}})\n\n"
        f"\tmeasure {tmdl_ident(p.name + ' SelectedValue')}\n"
        f"\t\texpression: SELECTEDVALUE('{p.name}'[Value], {tmdl_string(p.default)})\n"
    )
    return {f"tables/{p.name}.tmdl": body}


def _internal_constant(p: Parameter) -> dict[str, str]:
    literal = p.default if p.datatype in ("integer", "real") else tmdl_string(p.default)
    body = (
        f"\tmeasure {tmdl_ident(p.name)}\n"
        f"\t\texpression: {literal}\n"
        f"\t\tisHidden: true\n"
    )
    return {f"tables/_Constants.tmdl": _constants_header() + body}


def _constants_header() -> str:
    return "table _Constants\n\tisHidden: true\n\n"
