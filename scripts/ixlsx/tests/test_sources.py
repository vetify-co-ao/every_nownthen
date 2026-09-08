import datetime as dt

from sources import (
    AntboxClient,
    DashyClient,
    VendusClient,
    load_announcements,
    load_cargo,
    load_products,
    load_recipients,
)


class FakeAntbox:
    def __init__(self, nodes_by_aspect, article=None):
        self.nodes_by_aspect = nodes_by_aspect
        self.article = article or {}

    def find_all(self, filters):
        aspect = next(value for field, operator, value in filters if field == "aspects")
        return self.nodes_by_aspect.get(aspect, [])

    def localized_article(self, node_id, locale="pt"):
        return self.article


class FakeResponse:
    def __init__(self, payload, content=b"", headers=None):
        self.payload = payload
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeExportSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse({}, b"remote-template")


class FakeDashySession:
    def __init__(self, lot_payload):
        self.headers = {}
        self.lot_payload = lot_payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(
            {"rows": []} if url.endswith("/dimensions/product") else self.lot_payload
        )


def test_antbox_export_uses_authorization_header_and_never_query_key(tmp_path):
    session = FakeExportSession()
    client = AntboxClient("https://vcrm.example/api", "secret", session)

    output = client.export("NODE", tmp_path / "template.html")

    assert output.read_bytes() == b"remote-template"
    assert session.headers["Authorization"] == "ApiKey secret"
    assert session.calls == [("https://vcrm.example/api/nodes/NODE/-/export", None, 60)]


def test_vendus_products_walk_all_reported_pages():
    class VendusSession:
        def __init__(self):
            self.headers = {}
            self.pages = []

        def get(self, url, params=None, timeout=None):
            page = params["page"]
            self.pages.append(page)
            return FakeResponse(
                [{"reference": f"SKU-{page}"}],
                headers={"X-Paginator-Pages": "2"},
            )

    session = VendusSession()

    records = VendusClient("secret", session=session).products()

    assert [record["reference"] for record in records] == ["SKU-1", "SKU-2"]
    assert session.pages == [1, 2]


def test_recipients_use_only_primary_reseller_email_and_allowed_statuses():
    client = FakeAntbox(
        {
            "reseller": [
                {
                    "properties": {
                        "reseller:status": "Activo",
                        "reseller:email": "ONE@Example.com",
                    }
                },
                {
                    "properties": {
                        "reseller:status": "Incumprimento",
                        "reseller:email": "one@example.com",
                    }
                },
                {
                    "properties": {
                        "reseller:status": "Inactivo",
                        "reseller:email": "off@example.com",
                    }
                },
                {
                    "properties": {
                        "reseller:status": "Activo",
                        "reseller:email": "invalid",
                    }
                },
            ]
        }
    )

    assert load_recipients(client) == ["one@example.com"]


def test_announcements_are_active_by_date_not_nonexistent_status():
    today = dt.date(2026, 9, 8)
    client = FakeAntbox(
        {
            "announcement": [
                {
                    "uuid": "active",
                    "title": "Fallback",
                    "properties": {
                        "announcement:start-date": "2026-09-08",
                        "announcement:end-date": "2026-09-11",
                        "announcement:target": ["Clínicas"],
                    },
                },
                {
                    "uuid": "expired",
                    "properties": {
                        "announcement:start-date": "2026-09-01",
                        "announcement:end-date": "2026-09-07",
                    },
                },
            ]
        },
        {
            "articleTitle": "Aviso",
            "articleResume": "Resumo",
            "articleBody": "**Corpo**",
        },
    )

    result = load_announcements(client, today)

    assert [item.title for item in result] == ["Aviso"]
    assert result[0].body == "**Corpo**"


def test_dashy_loads_all_lots_once_and_selects_nearest_future_expiry():
    session = FakeDashySession(
        {
            "x": [
                "SKU-1 | Supplier | LOT-A | 2026-09-07 | 2026-01-01",
                "SKU-1 | Supplier | LOT-B | 2026-10-10 | 2026-01-01",
                "SKU-1 | Supplier | LOT-C | 2026-09-20 | 2026-01-01",
            ],
            "series": {"remaining_qty": [4, 2, 1]},
        }
    )
    client = DashyClient("secret", "https://dashy.example", session)

    result = client.future_expiries(dt.date(2026, 9, 8))

    assert result == {"SKU-1": dt.date(2026, 9, 20)}
    assert session.calls[1][1] == {"horizon_days": 720, "limit": 200}
    assert len(session.calls) == 2


def test_products_apply_vendus_stock_policy_and_vpim_values():
    vpim = FakeAntbox(
        {
            "product": [
                {
                    "uuid": "SKU-1",
                    "fid": "product-one",
                    "title": "Product One",
                    "description": "Description",
                    "properties": {
                        "product:status": "Activo",
                        "product:price": 100,
                        "product:vat-rate": 14,
                        "product:brand": "brand-one",
                        "product:department": "Medicamentos",
                        "product:subcategories": ["sub-one"],
                        "product:featured": True,
                        "commercial-performance:minimum-stock": 5,
                    },
                },
                {
                    "uuid": "SKU-NO-VENDUS",
                    "fid": "missing",
                    "title": "Missing",
                    "properties": {
                        "product:price": 10,
                        "product:vat-rate": 0,
                        "product:department": "Higiene",
                    },
                },
            ],
            "category": [{"uuid": "category-one", "title": "Categoria"}],
            "subcategory": [
                {"uuid": "sub-one", "title": "Subcategoria", "parent": "category-one"}
            ],
            "brand": [{"uuid": "brand-one", "title": "Brand One"}],
        }
    )
    vendus = [
        {
            "reference": "SKU-1",
            "status": "on",
            "stock": {"stores": [{"stock": 5}]},
            "prices": {"net": "999"},
        }
    ]

    products, anomalies = load_products(vpim, vendus, {"SKU-1": dt.date(2026, 10, 1)})
    by_sku = {product.sku: product for product in products}

    assert by_sku["SKU-1"].availability == "ULTIMAS UNIDADES"
    assert by_sku["SKU-1"].net_price == 100
    assert by_sku["SKU-1"].vat_rate == 0.14
    assert by_sku["SKU-1"].expiry == dt.date(2026, 10, 1)
    assert by_sku["SKU-1"].categories == "Categoria"
    assert by_sku["SKU-NO-VENDUS"].availability == "SOB CONSULTA"
    assert any("SKU-NO-VENDUS: no Vendus match" == item for item in anomalies)


def test_vsco_cargo_uses_only_nature_description_and_relevant_statuses():
    client = FakeAntbox(
        {
            "import-process": [
                {
                    "uuid": "recent",
                    "properties": {
                        "import-process:status": "Desalfandegado",
                        "import-process:customs-cleared-at": "2026-09-06",
                        "import-process:supplier": "supplier-1",
                    },
                },
                {
                    "uuid": "transit",
                    "properties": {
                        "import-process:status": "Aguarda BL/AWB",
                        "import-process:supplier": "supplier-1",
                    },
                },
                {
                    "uuid": "not-shipped",
                    "properties": {"import-process:status": "Espera Licenciamento"},
                },
            ],
            "import-document": [
                {
                    "parent": "recent",
                    "properties": {
                        "import-document:process": "recent",
                        "import-document:document-type": "Proforma",
                        "import-document:extracted-data": {
                            "productDescription": "Medicamentos veterinários",
                            "originCountry": "Portugal",
                        },
                    },
                },
                {
                    "parent": "transit",
                    "properties": {
                        "import-document:process": "transit",
                        "import-document:document-type": "BL",
                        "import-document:extracted-data": {
                            "productDescription": "Alimentação animal",
                            "originCountry": "França",
                        },
                        "transport-document:estimated-arrival": "2026-10-01",
                    },
                },
            ],
            "supplier": [
                {
                    "uuid": "supplier-1",
                    "title": "Supplier",
                    "properties": {"supplier:country": "Portugal"},
                }
            ],
        }
    )

    recent, transit = load_cargo(client, dt.date(2026, 9, 8))

    assert [(item.supplier, item.nature) for item in recent] == [
        ("Supplier", "Medicamentos veterinários")
    ]
    assert [(item.date, item.nature) for item in transit] == [
        (dt.date(2026, 10, 1), "Alimentação animal")
    ]
