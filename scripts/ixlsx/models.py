from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    sku: str
    slug: str
    title: str
    description: str
    availability: str
    net_price: float
    vat_rate: float
    expiry: dt.date | None
    categories: str
    subcategories: str
    brand: str
    department: str
    featured: bool
    image_url: str
    used_minimum_stock_fallback: bool = False


@dataclass(frozen=True)
class Announcement:
    title: str
    resume: str
    body: str
    starts_at: dt.date


@dataclass(frozen=True)
class Cargo:
    supplier: str
    origin: str
    date: dt.date | None
    nature: str


@dataclass
class BulletinData:
    publication_date: dt.date
    issue_number: int
    recipients: list[str]
    products: list[Product]
    announcements: list[Announcement]
    recent_arrivals: list[Cargo] = field(default_factory=list)
    in_transit: list[Cargo] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    degradations: list[str] = field(default_factory=list)
