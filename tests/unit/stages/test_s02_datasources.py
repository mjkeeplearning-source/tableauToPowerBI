from __future__ import annotations

from tableau2pbir.ir.datasource import ConnectorTier
from tableau2pbir.stages._build_data_model import build_datasources


def test_tier_1_csv():
    raw = [{
        "name": "sample.csv", "caption": "Sample",
        "connection": {"class": "textscan", "filename": "sample.csv", "directory": "."},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert len(datasources) == 1
    ds = datasources[0]
    assert ds.name == "sample.csv"
    assert ds.connector_tier == ConnectorTier.TIER_1
    assert ds.pbi_m_connector == "Csv.Document"
    assert ds.connection_params["filename"] == "sample.csv"
    assert unsupported == ()


def test_tier_2_snowflake_user_action():
    raw = [{
        "name": "sales", "caption": None,
        "connection": {"class": "snowflake", "server": "acct.snowflakecomputing.com",
                       "warehouse": "WH1"},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_2
    assert "enter credentials" in datasources[0].user_action_required
    assert unsupported == ()


def test_tier_3_cross_db_emits_deferred_feature():
    raw = [{
        "name": "joined",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "a", "caption": None, "connection": {"class": "sqlserver"}},
            {"name": "b", "caption": None, "connection": {"class": "snowflake"}},
        ],
        "extract": None, "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_3
    assert datasources[0].pbi_m_connector is None
    assert len(unsupported) == 1
    assert unsupported[0].code == "deferred_feature_tier3"
    assert unsupported[0].object_kind == "datasource"


def test_tier_4_published_emits_unsupported():
    raw = [{
        "name": "pub",
        "connection": {"class": "sqlproxy"},
        "named_connections": [], "extract": None,
        "columns": [], "calculations": [],
    }]
    datasources, unsupported = build_datasources(raw)
    assert datasources[0].connector_tier == ConnectorTier.TIER_4
    assert len(unsupported) == 1
    assert unsupported[0].code == "unsupported_datasource_tier_4"


def test_federated_single_upstream_uses_named_connection_params():
    raw = [{
        "name": "federated.abc",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "pg.xyz", "caption": "srv",
             "connection": {"class": "postgres", "server": "srv.example.com", "dbname": "mydb"}},
        ],
        "extract": None, "relations": [], "col_map": {}, "columns": [], "calculations": [],
    }]
    datasources, _ = build_datasources(raw)
    ds = datasources[0]
    assert ds.connector_tier.value == 2
    assert ds.pbi_m_connector == "PostgreSQL.Database"
    assert ds.connection_params.get("server") == "srv.example.com"
    assert ds.connection_params.get("dbname") == "mydb"


def test_extract_ignored_flag_when_hyper_with_upstream():
    raw = [{
        "name": "extract_ds",
        "connection": {"class": "federated"},
        "named_connections": [
            {"name": "u", "caption": None, "connection": {"class": "sqlserver"}},
        ],
        "extract": {"connection": {"class": "hyper"}},
        "columns": [], "calculations": [],
    }]
    datasources, _ = build_datasources(raw)
    assert datasources[0].extract_ignored is True


from lxml import etree
from tableau2pbir.extract.datasources import extract_datasources


def test_calculation_uses_caption_as_name():
    xml = b"""<workbook>
      <datasources>
        <datasource name="DS">
          <connection class="postgres" server="localhost" dbname="sales" />
          <column caption="DeltaOrder" datatype="integer"
                  name="[Calculation_0390937790091264]" role="measure" type="quantitative">
            <calculation class="tableau" formula="COUNTD([order_id]) - COUNTD([order_id (returns)])" />
          </column>
        </datasource>
      </datasources>
    </workbook>"""
    root = etree.fromstring(xml)
    result = extract_datasources(root)
    assert len(result) == 1
    calcs = result[0]["calculations"]
    assert len(calcs) == 1
    assert calcs[0]["caption"] == "DeltaOrder", "caption attribute must be captured"
    assert calcs[0]["host_column_name"] == "Calculation_0390937790091264"


def test_calculation_falls_back_to_internal_name_when_no_caption():
    xml = b"""<workbook>
      <datasources>
        <datasource name="DS">
          <connection class="postgres" server="localhost" dbname="sales" />
          <column datatype="integer" name="[MyCalc]" role="measure" type="quantitative">
            <calculation class="tableau" formula="SUM([x])" />
          </column>
        </datasource>
      </datasources>
    </workbook>"""
    root = etree.fromstring(xml)
    result = extract_datasources(root)
    calcs = result[0]["calculations"]
    assert calcs[0].get("caption") is None
    assert calcs[0]["host_column_name"] == "MyCalc"


def test_stage2_datamodel_preserves_columns():
    """DataModel.columns must be non-empty after Stage 2 runs on a datasource with columns."""
    from tableau2pbir.stages._build_data_model import build_tables
    from tableau2pbir.ir.workbook import DataModel

    raw_ds = [{
        "name": "orders",
        "connection": {"class": "sqlserver", "server": "srv", "dbname": "db"},
        "named_connections": [], "extract": None, "relations": [], "col_map": {},
        "columns": [
            {"name": "order_id", "datatype": "string", "role": "dimension", "type": "nominal"},
            {"name": "sales",    "datatype": "real",   "role": "measure",   "type": "quantitative"},
        ],
        "calculations": [],
    }]
    tables, columns = build_tables(raw_ds)
    dm = DataModel(tables=tables, columns=columns)
    assert len(dm.columns) == 2
    assert any(c.name == "order_id" for c in dm.columns)
