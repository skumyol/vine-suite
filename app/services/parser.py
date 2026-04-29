"""Wine SKU parsing and query building service."""

import re
from typing import List, Optional

from app.models.wine import AnalyzeRequest, ParsedIdentity


# Common wine producer prefixes
COMMON_PRODUCER_PREFIXES = [
    "domaine", "chateau", "ch\u00e2teau", "mas", "clos", "cellier",
    "cave", "maison", "weingut", "bodega", "tenuta", "cantina",
    "quinta", "ernst", "weinbach", "arnot", "roberts"
]

# Burgundy appellations
BURGUNDY_APPELLATIONS = [
    "chablis", "gevrey-chambertin", "morey-st-denis", "morey-saint-denis",
    "chambolle-musigny", "vosne-roman\u00e9e", "nuits-st-georges",
    "nuits-saint-georges", "aloxe-corton", "beaune", "pommard",
    "volnay", "meursault", "puligny-montrachet", "chassagne-montrachet",
    "santenay", "maranges", "rully", "mercurey", "givry", "montagny",
    "bouzeron", "ratafia", "bourgogne", "c\u00f4te de nuits",
    "c\u00f4te de beaune", "c\u00f4te chalonnaise", "m\u00e2connais",
    "hautes-c\u00f4tes de nuits", "hautes-c\u00f4tes de beaune",
]

# Classification patterns
CLASSIFICATION_PATTERNS = [
    r"\b(Grand Cru)\b",
    r"\b(Premier Cru|1er Cru|1er-Cru)\b",
    r"\b(1er|Premier)\s*Cru\b",
    r"\b(Villages?)\b",
    r"\b(Vendanges Tardives|VT)\b",
    r"\b(S\u00e9lection de Grains Nobles|SGN)\b",
]

VINTAGE_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
FORMAT_PATTERN = re.compile(r"(\d+)\s*(ml|mL|ML|cl|cL|CL|L|l)\b", re.IGNORECASE)


class WineParser:
    """Parse wine names to extract structured identity fields."""

    def __init__(self):
        self.classification_regexes = [
            re.compile(p, re.IGNORECASE) for p in CLASSIFICATION_PATTERNS
        ]

    def parse(self, request: AnalyzeRequest) -> ParsedIdentity:
        """Parse a wine name into structured identity fields."""
        raw_name = request.wine_name

        classification = self._extract_classification(raw_name)
        vintage = request.vintage or self._extract_vintage(raw_name)
        format_ml = self._extract_format(request.format) if request.format else None

        name_without_classification = self._remove_classification(raw_name, classification)
        producer = self._extract_producer(name_without_classification)
        appellation = self._extract_appellation(name_without_classification)
        vineyard = self._extract_vineyard(name_without_classification, producer, appellation)

        normalized = self._normalize_text(raw_name)

        return ParsedIdentity(
            raw_wine_name=raw_name,
            normalized_wine_name=normalized,
            vintage=vintage,
            producer=producer,
            appellation=appellation,
            vineyard_or_cuvee=vineyard,
            region=request.region,
            classification=classification,
            format_ml=format_ml,
        )

    def _extract_classification(self, name: str) -> Optional[str]:
        for regex in self.classification_regexes:
            match = regex.search(name)
            if match:
                return match.group(1)
        return None

    def _extract_vintage(self, name: str) -> Optional[str]:
        match = VINTAGE_PATTERN.search(name)
        if match:
            return match.group(1)
        return None

    def _extract_format(self, format_str: str) -> Optional[int]:
        match = FORMAT_PATTERN.search(format_str)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            if unit in ["l", "L"]:
                return amount * 1000
            elif unit in ["cl", "cL", "CL"]:
                return amount * 10
            else:
                return amount
        return None

    def _remove_classification(self, name: str, classification: Optional[str]) -> str:
        if not classification:
            return name
        return re.sub(
            r"\b" + re.escape(classification) + r"\b",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()

    def _extract_producer(self, name: str) -> Optional[str]:
        parts = name.split()
        if not parts:
            return None

        producer_parts = []
        for i, part in enumerate(parts):
            lower_part = part.lower().rstrip(",;")
            if lower_part in [p.lower() for p in COMMON_PRODUCER_PREFIXES] or i == 0:
                producer_parts.append(part.rstrip(",;"))
                if lower_part not in [p.lower() for p in COMMON_PRODUCER_PREFIXES]:
                    break
            else:
                if i < 3:
                    producer_parts.append(part.rstrip(",;"))
                if i >= 1 and not part.islower():
                    break

        if producer_parts:
            return " ".join(producer_parts)
        return parts[0] if parts else None

    def _extract_appellation(self, name: str) -> Optional[str]:
        name_lower = name.lower()

        for appellation in BURGUNDY_APPELLATIONS:
            if appellation.lower() in name_lower:
                return appellation

        parts = name.split()
        producer = self._extract_producer(name)
        producer_words = set(producer.lower().split()) if producer else set()

        appellation_parts = []
        for part in parts:
            if part.lower().rstrip(",;") not in producer_words and part[0].isupper():
                appellation_parts.append(part.rstrip(",;"))

        if appellation_parts:
            return " ".join(appellation_parts[:3])

        return None

    def _extract_vineyard(
        self, name: str, producer: Optional[str], appellation: Optional[str]
    ) -> Optional[str]:
        if not producer or not appellation:
            return None

        name_clean = name
        for item in [producer, appellation]:
            if item:
                name_clean = name_clean.replace(item, "")

        name_clean = re.sub(
            r"\b(Grand Cru|Premier Cru|1er Cru)\b",
            "",
            name_clean,
            flags=re.IGNORECASE,
        )
        name_clean = name_clean.strip(",; ")

        parts = [p for p in name_clean.split() if p and p[0].isupper()]
        if parts:
            return " ".join(parts[:4])

        return None

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        normalized = text.lower()
        normalized = normalized.replace("-", " ")
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized


class QueryBuilder:
    """Build search queries from parsed wine identity."""

    def build_queries(self, parsed: ParsedIdentity, max_queries: int = 3) -> List[str]:
        """Build a list of search queries in priority order."""
        queries = []
        wine_name = parsed.raw_wine_name.strip()
        vintage = (parsed.vintage or "").strip()
        producer = (parsed.producer or "").strip()
        appellation = (parsed.appellation or "").strip()

        # Exact queries
        exact = f'"{wine_name}" {vintage} bottle'
        queries.append(exact)
        queries.append(f"{wine_name} {vintage}")
        queries.append(f'{parsed.normalized_wine_name} {vintage} bottle')
        queries.append(f'"{wine_name}" {vintage} label')
        queries.append(f'"{wine_name}" {vintage} wine')

        # Producer-based queries
        if producer:
            queries.append(f"{producer} {vintage} wine bottle")
            if appellation:
                queries.append(
                    f'{producer} "{appellation}" {vintage} bottle'
                )

        if parsed.vineyard_or_cuvee:
            queries.append(
                f'{producer or wine_name} "{parsed.vineyard_or_cuvee}" {vintage}'
            )
            queries.append(
                f'"{parsed.vineyard_or_cuvee}" {vintage} wine bottle'
            )

        # Site-restricted queries for trusted sources
        sites = ["site:wine-searcher.com", "site:vivino.com", "site:wine.com"]
        for site in sites:
            queries.append(f'"{wine_name}" {vintage} {site}')

        # Vintage fallback
        if vintage:
            without_vintage = wine_name.replace(vintage, "").strip()
            if without_vintage != wine_name:
                queries.append(f'"{without_vintage}" bottle')

        # Deduplicate while preserving order
        deduped = []
        seen = set()
        for query in queries:
            cleaned = " ".join(query.split())
            if cleaned and cleaned not in seen:
                deduped.append(cleaned)
                seen.add(cleaned)

        return deduped[:max_queries]
