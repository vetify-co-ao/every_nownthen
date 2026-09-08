from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import Announcement, Cargo, Product

REQUEST_TIMEOUT_SECONDS = 60
PAGE_SIZE = 100
MAX_PAGES = 20
VENDUS_PAGE_SIZE = 200
DASHY_LOT_LIMIT = 200
DASHY_HORIZON_DAYS = 720
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
IN_TRANSIT_STATUSES = {
    "Aguarda BL/AWB",
    "À Espera de Impostos",
    "Espera Pagamento de Impostos",
    "Espera Nota de Desalfandegamento",
}


def default_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session


def text(value: object, limit: int = 500) -> str:
    return str(value or "").replace("\x00", " ").strip()[:limit]


def number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def date_value(value: object) -> dt.date | None:
    raw = text(value, 32)
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def safe_https_url(value: object) -> str:
    raw = text(value, 2000)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        return ""
    return raw


class AntboxClient:
    def __init__(self, base_url: str, api_key: str, session=None):
        if not api_key:
            raise ValueError("Antbox API key is required")
        self.base_url = base_url.rstrip("/")
        self.session = session or default_session()
        self.session.headers.update(
            {
                "Authorization": f"ApiKey {api_key}",
                "Accept": "application/json",
                "User-Agent": "every-nownthen-ixlsx/1.2.0",
            }
        )

    def find_all(self, filters: list[list[object]]) -> list[dict]:
        nodes: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            response = self.session.post(
                f"{self.base_url}/nodes/-/find",
                json={"filters": filters, "pageSize": PAGE_SIZE, "pageToken": page},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("nodes") if isinstance(payload, dict) else None
            if not isinstance(batch, list):
                raise TypeError(f"Invalid Antbox node response from {self.base_url}")
            nodes.extend(node for node in batch if isinstance(node, dict))
            if len(batch) < PAGE_SIZE:
                return nodes
        raise RuntimeError(f"Antbox pagination exceeded {MAX_PAGES * PAGE_SIZE} nodes")

    def localized_article(self, node_id: str, locale: str = "pt") -> dict:
        response = self.session.get(
            f"{self.base_url}/articles/{node_id}/-/localized",
            params={"locale": locale},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError(f"Invalid localized article response for {node_id}")
        return payload

    def export(self, node_id: str, target: Path) -> Path:
        response = self.session.get(
            f"{self.base_url}/nodes/{node_id}/-/export",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.content
        if not content:
            raise RuntimeError(f"VCRM template {node_id} is empty")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target


class VendusClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.vendus.pt/ws/v1.2",
        session=None,
    ):
        if not api_key:
            raise ValueError("VENDUS_API_KEY is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or default_session()
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": "every-nownthen-ixlsx/1.2.0"}
        )

    def products(self) -> list[dict]:
        records: list[dict] = []
        try:
            for page in range(1, MAX_PAGES + 1):
                response = self.session.get(
                    f"{self.base_url}/products/",
                    params={
                        "api_key": self.api_key,
                        "per_page": VENDUS_PAGE_SIZE,
                        "page": page,
                    },
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise TypeError("Invalid Vendus product response")
                records.extend(record for record in payload if isinstance(record, dict))
                total_pages_header = response.headers.get("X-Paginator-Pages")
                if total_pages_header is None:
                    if len(payload) < VENDUS_PAGE_SIZE:
                        return records
                    continue
                if page >= int(total_pages_header) or not payload:
                    return records
        except (requests.RequestException, TypeError, ValueError) as error:
            raise RuntimeError(str(error).replace(self.api_key, "***")) from error
        raise RuntimeError(
            f"Vendus pagination exceeded {MAX_PAGES * VENDUS_PAGE_SIZE} products"
        )


class DashyClient:
    def __init__(
        self, api_key: str, base_url: str = "https://bi.vetify.co.ao", session=None
    ):
        if not api_key:
            raise ValueError("DASHY_API_KEY is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or default_session()
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": "every-nownthen-ixlsx/1.2.0"}
        )

    def future_expiries(self, today: dt.date) -> dict[str, dt.date]:
        try:
            auth = self.session.get(
                f"{self.base_url}/api/dimensions/product",
                params={"api_key": self.api_key},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            auth.raise_for_status()
            response = self.session.get(
                f"{self.base_url}/api/datasets/stock_lots_at_risk",
                params={"horizon_days": DASHY_HORIZON_DAYS, "limit": DASHY_LOT_LIMIT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(str(error).replace(self.api_key, "***")) from error
        if not isinstance(payload, dict):
            raise TypeError("Invalid Dashy lot response")
        labels = payload.get("x")
        series = payload.get("series")
        quantities = series.get("remaining_qty") if isinstance(series, dict) else None
        if not isinstance(labels, list) or not isinstance(quantities, list):
            raise TypeError("Invalid Dashy lot series")
        if len(labels) >= DASHY_LOT_LIMIT:
            raise RuntimeError(
                f"Dashy lot result reached limit {DASHY_LOT_LIMIT}; refusing truncated enrichment"
            )

        candidates: dict[str, list[dt.date]] = {}
        for index, label in enumerate(labels):
            if index >= len(quantities) or number(quantities[index]) <= 0:
                continue
            parts = [part.strip() for part in str(label).split("|")]
            if len(parts) < 4:
                continue
            expiry = date_value(parts[3])
            if expiry and expiry > today and parts[0]:
                candidates.setdefault(parts[0], []).append(expiry)
        return {sku: min(values) for sku, values in candidates.items()}


def load_recipients(client: AntboxClient) -> list[str]:
    recipients = set()
    for node in client.find_all([["aspects", "contains", "reseller"]]):
        properties = node.get("properties") or {}
        if properties.get("reseller:status") not in {"Activo", "Incumprimento"}:
            continue
        email = text(properties.get("reseller:email"), 254).lower()
        if EMAIL_PATTERN.fullmatch(email):
            recipients.add(email)
    return sorted(recipients)


def load_announcements(client: AntboxClient, today: dt.date) -> list[Announcement]:
    announcements = []
    for node in client.find_all([["aspects", "contains", "announcement"]]):
        properties = node.get("properties") or {}
        starts_at = date_value(properties.get("announcement:start-date"))
        ends_at = date_value(properties.get("announcement:end-date"))
        if not starts_at or starts_at > today or (ends_at and ends_at < today):
            continue
        article = client.localized_article(text(node.get("uuid"), 160))
        title = text(
            article.get("articleTitle")
            or properties.get("announcement:title")
            or node.get("title"),
            300,
        )
        if not title:
            continue
        announcements.append(
            Announcement(
                title=title,
                resume=text(article.get("articleResume"), 1000),
                body=text(article.get("articleBody"), 10000),
                starts_at=starts_at,
            )
        )
    return sorted(
        announcements, key=lambda item: (item.starts_at, item.title.casefold())
    )


def _node_map(nodes: Iterable[dict]) -> dict[str, dict]:
    return {
        text(node.get("uuid"), 160): node
        for node in nodes
        if text(node.get("uuid"), 160)
    }


def _vendus_stock(record: dict) -> float:
    stock = record.get("stock")
    stores = stock.get("stores") if isinstance(stock, dict) else None
    if not isinstance(stores, list):
        return 0.0
    return sum(
        number(store.get("stock")) for store in stores if isinstance(store, dict)
    )


def load_products(
    vpim: AntboxClient,
    vendus_records: list[dict],
    expiries: dict[str, dt.date],
) -> tuple[list[Product], list[str]]:
    product_nodes = vpim.find_all(
        [["aspects", "contains", "product"], ["product:status", "==", "Activo"]]
    )
    if not product_nodes:
        raise RuntimeError("VPIM returned no active products")
    categories = _node_map(vpim.find_all([["aspects", "contains", "category"]]))
    subcategories = _node_map(vpim.find_all([["aspects", "contains", "subcategory"]]))
    brands = _node_map(vpim.find_all([["aspects", "contains", "brand"]]))
    vendus = {
        text(record.get("reference"), 160): record
        for record in vendus_records
        if record.get("status") == "on" and text(record.get("reference"), 160)
    }

    anomalies: list[str] = []
    products: list[Product] = []
    for node in product_nodes:
        properties = node.get("properties") or {}
        sku = text(node.get("uuid"), 160)
        title = text(node.get("title"), 300)
        if not sku or not title:
            anomalies.append("VPIM product omitted because SKU or title is missing")
            continue

        minimum_raw = properties.get("commercial-performance:minimum-stock")
        try:
            minimum_stock = float(minimum_raw)
            if not math.isfinite(minimum_stock) or minimum_stock < 0:
                raise ValueError
            used_minimum_fallback = False
        except (TypeError, ValueError):
            minimum_stock = 10.0
            used_minimum_fallback = True
            anomalies.append(
                f"{sku}: missing or invalid VPIM minimum stock; used fallback 10"
            )

        vendus_record = vendus.get(sku)
        stock = _vendus_stock(vendus_record) if vendus_record else None
        if stock is None:
            availability = "SOB CONSULTA"
            anomalies.append(f"{sku}: no Vendus match")
        elif stock <= 0:
            availability = "ESGOTADO"
        elif stock <= minimum_stock:
            availability = "ULTIMAS UNIDADES"
        else:
            availability = "EM STOCK"

        subcategory_ids = [
            text(value, 160) for value in properties.get("product:subcategories") or []
        ]
        category_titles: list[str] = []
        subcategory_titles: list[str] = []
        for subcategory_id in subcategory_ids:
            subcategory = subcategories.get(subcategory_id, {})
            subcategory_title = (
                text(subcategory.get("title"))
                or subcategory_id.replace("-", " ").title()
            )
            if subcategory_title and subcategory_title not in subcategory_titles:
                subcategory_titles.append(subcategory_title)
            category = categories.get(text(subcategory.get("parent"), 160), {})
            category_title = text(category.get("title"))
            if category_title and category_title not in category_titles:
                category_titles.append(category_title)
        department = text(properties.get("product:department")) or "Produto"
        if not category_titles:
            category_titles.append(department)

        brand_id = text(properties.get("product:brand"), 160)
        brand = (
            text(brands.get(brand_id, {}).get("title"))
            or brand_id.replace("-", " ").title()
        )
        images = [
            safe_https_url(value)
            for value in properties.get("product:image-urls") or []
        ]
        vat_rate = number(properties.get("product:vat-rate"))
        if vat_rate > 1:
            vat_rate /= 100

        products.append(
            Product(
                sku=sku,
                slug=text(node.get("fid"), 200),
                title=title,
                description=text(node.get("description"), 5000),
                availability=availability,
                net_price=number(properties.get("product:price")),
                vat_rate=vat_rate,
                expiry=expiries.get(sku) if stock is not None and stock > 0 else None,
                categories=" · ".join(category_titles),
                subcategories=" · ".join(subcategory_titles),
                brand=brand,
                department=department,
                featured=properties.get("product:featured") is True,
                image_url=next((image for image in images if image), ""),
                used_minimum_stock_fallback=used_minimum_fallback,
            )
        )
    products.sort(
        key=lambda item: (item.brand.casefold(), item.title.casefold(), item.sku)
    )
    return products, anomalies


def load_cargo(vsco: AntboxClient, today: dt.date) -> tuple[list[Cargo], list[Cargo]]:
    processes = vsco.find_all([["aspects", "contains", "import-process"]])
    documents = vsco.find_all([["aspects", "contains", "import-document"]])
    suppliers = _node_map(vsco.find_all([["aspects", "contains", "supplier"]]))
    documents_by_process: dict[str, list[dict]] = {}
    for document in documents:
        properties = document.get("properties") or {}
        process_id = text(
            properties.get("import-document:process") or document.get("parent"), 160
        )
        if process_id:
            documents_by_process.setdefault(process_id, []).append(document)

    def cargo_from(process: dict, cargo_date: dt.date | None) -> Cargo:
        process_id = text(process.get("uuid"), 160)
        properties = process.get("properties") or {}
        supplier_id = text(properties.get("import-process:supplier"), 160)
        supplier = suppliers.get(supplier_id, {})
        supplier_properties = supplier.get("properties") or {}
        supplier_name = (
            text(properties.get("import-process:supplier-name-snapshot"))
            or text(supplier.get("title"))
            or "Fornecedor não indicado"
        )
        origin = text(supplier_properties.get("supplier:country"))
        nature = ""
        estimated_arrival = None
        preference = {"Factura Comercial": 0, "Proforma": 1, "Packing List": 2}
        process_documents = sorted(
            documents_by_process.get(process_id, []),
            key=lambda item: preference.get(
                text(
                    (item.get("properties") or {}).get("import-document:document-type")
                ),
                9,
            ),
        )
        for document in process_documents:
            document_properties = document.get("properties") or {}
            extracted = document_properties.get("import-document:extracted-data")
            extracted = extracted if isinstance(extracted, dict) else {}
            nature = nature or text(extracted.get("productDescription"), 1000)
            origin = origin or text(extracted.get("originCountry"), 120)
            estimated_arrival = estimated_arrival or date_value(
                document_properties.get("transport-document:estimated-arrival")
            )
        return Cargo(
            supplier=supplier_name,
            origin=origin,
            date=cargo_date or estimated_arrival,
            nature=nature,
        )

    cutoff = today - dt.timedelta(days=7)
    recent: list[Cargo] = []
    transit: list[Cargo] = []
    for process in processes:
        properties = process.get("properties") or {}
        status = text(properties.get("import-process:status"))
        if status == "Desalfandegado":
            cleared_at = date_value(properties.get("import-process:customs-cleared-at"))
            if cleared_at and cutoff <= cleared_at <= today:
                recent.append(cargo_from(process, cleared_at))
        elif status in IN_TRANSIT_STATUSES:
            transit.append(cargo_from(process, None))
    sort_key = lambda item: (item.date or dt.date.max, item.supplier.casefold())
    return sorted(recent, key=sort_key), sorted(transit, key=sort_key)
