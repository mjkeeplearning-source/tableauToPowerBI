"""Top-level Workbook IR + DataModel aggregate — §5.1."""
from __future__ import annotations

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.common import IRBase, UnsupportedItem
from tableau2pbir.ir.dashboard import Dashboard
from tableau2pbir.ir.datasource import Datasource
from tableau2pbir.ir.model import Relationship, Table
from tableau2pbir.ir.parameter import Parameter
from tableau2pbir.ir.sheet import Sheet


class Hierarchy(IRBase):
    id: str
    name: str
    level_column_ids: tuple[str, ...]


class Set(IRBase):
    id: str
    name: str
    source_column: str                      # column id
    definition: str                         # free-form; TBD in stage 2


class DataModel(IRBase):
    datasources: tuple[Datasource, ...] = ()
    tables: tuple[Table, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    calculations: tuple[Calculation, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    hierarchies: tuple[Hierarchy, ...] = ()
    sets: tuple[Set, ...] = ()


class Workbook(IRBase):
    ir_schema_version: str
    source_path: str
    source_hash: str
    tableau_version: str
    config: dict[str, str]

    data_model: DataModel
    sheets: tuple[Sheet, ...]
    dashboards: tuple[Dashboard, ...]
    unsupported: tuple[UnsupportedItem, ...]
