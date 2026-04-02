from datetime import date, timedelta
from decimal import Decimal
from typing import Optional


def list_accounts(service) -> list[dict]:
    """List all AdMob publisher accounts (handles pagination)."""
    accounts = []
    request = service.accounts().list()
    while request is not None:
        resp = request.execute()
        accounts.extend(resp.get("account", []))
        request = service.accounts().list_next(request, resp)
    return accounts


def get_account(service, account_id: str) -> dict:
    """Get a specific account by ID."""
    name = _ensure_resource_name(account_id, "accounts")
    return service.accounts().get(name=name).execute()


def list_apps(service, account_id: str) -> list[dict]:
    """List all apps under an account (handles pagination)."""
    parent = _ensure_resource_name(account_id, "accounts")
    apps = []
    request = service.accounts().apps().list(parent=parent)
    while request is not None:
        resp = request.execute()
        apps.extend(resp.get("apps", []))
        request = service.accounts().apps().list_next(request, resp)
    return apps


def list_ad_units(service, account_id: str) -> list[dict]:
    """List all ad units under an account (handles pagination)."""
    parent = _ensure_resource_name(account_id, "accounts")
    ad_units = []
    request = service.accounts().adUnits().list(parent=parent)
    while request is not None:
        resp = request.execute()
        ad_units.extend(resp.get("adUnits", []))
        request = service.accounts().adUnits().list_next(request, resp)
    return ad_units


def _ensure_resource_name(account_id: str, prefix: str = "accounts") -> str:
    """Normalize account_id to resource name format with validation."""
    raw = account_id.strip()
    if not raw:
        raise ValueError("account_id must not be empty")
    if raw.startswith(f"{prefix}/"):
        suffix = raw[len(prefix) + 1:]
        if not suffix or "/" in suffix:
            raise ValueError(f"invalid {prefix} resource name: {account_id}")
        return raw
    if "/" in raw:
        raise ValueError(f"invalid {prefix} id: {account_id}")
    return f"{prefix}/{raw}"


def _make_date_range(days: int) -> dict:
    """Create date range dict for the last N days (inclusive on both ends)."""
    if days < 1:
        raise ValueError("days must be >= 1")
    end = date.today()
    start = end - timedelta(days=days - 1)
    return {
        "startDate": {"year": start.year, "month": start.month, "day": start.day},
        "endDate": {"year": end.year, "month": end.month, "day": end.day},
    }


def generate_network_report(
    service,
    account_id: str,
    days: int = 7,
    dimensions: Optional[list[str]] = None,
    metrics: Optional[list[str]] = None,
    currency_code: str = "USD",
    max_rows: int = 100000,
) -> dict:
    """Generate AdMob network report. Returns rows and footer metadata."""
    if dimensions is None:
        dimensions = ["DATE"]
    if metrics is None:
        metrics = [
            "ESTIMATED_EARNINGS",
            "IMPRESSIONS",
            "CLICKS",
            "AD_REQUESTS",
            "IMPRESSION_CTR",
            "IMPRESSION_RPM",
            "MATCHED_REQUESTS",
            "MATCH_RATE",
        ]

    parent = _ensure_resource_name(account_id, "accounts")
    body = {
        "reportSpec": {
            "dateRange": _make_date_range(days),
            "dimensions": dimensions,
            "metrics": metrics,
            "localizationSettings": {"currencyCode": currency_code},
            "maxReportRows": max_rows,
        }
    }
    response = (
        service.accounts()
        .networkReport()
        .generate(parent=parent, body=body)
        .execute()
    )
    return _parse_report_response(response)


def generate_mediation_report(
    service,
    account_id: str,
    days: int = 7,
    dimensions: Optional[list[str]] = None,
    metrics: Optional[list[str]] = None,
    currency_code: str = "USD",
    max_rows: int = 100000,
) -> dict:
    """Generate AdMob mediation report. Returns rows and footer metadata."""
    if dimensions is None:
        dimensions = ["DATE", "AD_SOURCE"]
    if metrics is None:
        metrics = [
            "ESTIMATED_EARNINGS",
            "IMPRESSIONS",
            "CLICKS",
            "MATCHED_REQUESTS",
            "OBSERVED_ECPM",
        ]

    parent = _ensure_resource_name(account_id, "accounts")
    body = {
        "reportSpec": {
            "dateRange": _make_date_range(days),
            "dimensions": dimensions,
            "metrics": metrics,
            "localizationSettings": {"currencyCode": currency_code},
            "maxReportRows": max_rows,
        }
    }
    response = (
        service.accounts()
        .mediationReport()
        .generate(parent=parent, body=body)
        .execute()
    )
    return _parse_report_response(response)


def _parse_report_response(response: list[dict]) -> dict:
    """Parse AdMob report response into clean row dicts with footer metadata.

    The API returns a list: [{header}, {row}, {row}, ..., {footer}].
    Each row has dimensionValues and metricValues as dicts keyed by name.
    microsValue fields are converted to Decimal string for precision.
    Returns dict with 'rows', 'matching_row_count', and 'warnings'.
    """
    rows = []
    footer = {}
    for element in response:
        if "row" in element:
            row = element["row"]
            entry = {}
            for key, val in row.get("dimensionValues", {}).items():
                entry[key] = val.get("value", "")
                display = val.get("displayLabel")
                if display and display != entry[key]:
                    entry[f"{key}_LABEL"] = display
            for key, val in row.get("metricValues", {}).items():
                if "integerValue" in val:
                    entry[key] = int(val["integerValue"])
                elif "doubleValue" in val:
                    entry[key] = val["doubleValue"]
                elif "microsValue" in val:
                    entry[key] = str(
                        Decimal(val["microsValue"]) / Decimal("1000000")
                    )
                else:
                    entry[key] = str(val)
            rows.append(entry)
        elif "footer" in element:
            footer = element["footer"]

    return {
        "rows": rows,
        "matching_row_count": int(footer.get("matchingRowCount", len(rows))),
        "warnings": footer.get("warnings", []),
    }
