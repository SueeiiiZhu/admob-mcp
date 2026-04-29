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


# ── v1beta: Mediation Group / A/B Experiment / Ad Unit Mapping ──


def _ensure_nested_name(account_id: str, *segments: str) -> str:
    """Build resource name like accounts/{aid}/adUnits/{auid}/adUnitMappings/{amid}.

    `segments` is a sequence of (collection, id) pairs flattened, e.g.
    ('adUnits', 'app/...', 'adUnitMappings', '12345').
    """
    if len(segments) % 2 != 0:
        raise ValueError("segments must come in (collection, id) pairs")
    base = _ensure_resource_name(account_id, "accounts")
    parts = [base]
    for collection, ident in zip(segments[0::2], segments[1::2]):
        ident = (ident or "").strip()
        if not ident or "/" in ident:
            raise ValueError(f"invalid {collection} id: {ident}")
        parts.append(f"{collection}/{ident}")
    return "/".join(parts)


def list_mediation_groups(
    service,
    account_id: str,
    filter_expr: Optional[str] = None,
    page_size: Optional[int] = None,
    max_items: Optional[int] = None,
    fields: Optional[str] = None,
) -> dict:
    """List mediation groups with pagination control. Requires admob.readonly scope.

    Args:
        filter_expr: AdMob list filter, e.g. 'STATE = "ENABLED" AND PLATFORM = "ANDROID"'.
            Supported fields: AD_UNIT_ID, STATE, FORMAT, PLATFORM. Function: IS_ANY_OF.
        page_size: Server-side page size (caps per-RPC payload).
        max_items: Total items cap across all pages; stops paging once reached.
        fields: Partial-response FieldMask, e.g.
            "mediationGroups(name,displayName,state,targeting),nextPageToken".

    Returns dict with keys: mediationGroups, count, truncated, nextPageToken.
    `truncated` is True when more results exist beyond what was returned.
    """
    parent = _ensure_resource_name(account_id, "accounts")
    groups: list[dict] = []
    kwargs = {"parent": parent}
    if filter_expr:
        kwargs["filter"] = filter_expr
    if page_size:
        kwargs["pageSize"] = page_size
    if fields:
        kwargs["fields"] = fields

    next_token: Optional[str] = None
    truncated = False
    request = service.accounts().mediationGroups().list(**kwargs)
    while request is not None:
        resp = request.execute()
        page_items = resp.get("mediationGroups", [])
        if max_items is not None and len(groups) + len(page_items) >= max_items:
            remaining = max_items - len(groups)
            groups.extend(page_items[:remaining])
            next_token = resp.get("nextPageToken")
            truncated = bool(next_token) or len(page_items) > remaining
            break
        groups.extend(page_items)
        request = service.accounts().mediationGroups().list_next(request, resp)

    return {
        "mediationGroups": groups,
        "count": len(groups),
        "truncated": truncated,
        "nextPageToken": next_token,
    }


def create_mediation_group(service, account_id: str, body: dict) -> dict:
    """Create a mediation group. Requires admob.monetization scope.

    body schema (MediationGroup): displayName, targeting, mediationGroupLines, state, ...
    """
    parent = _ensure_resource_name(account_id, "accounts")
    return (
        service.accounts()
        .mediationGroups()
        .create(parent=parent, body=body)
        .execute()
    )


def update_mediation_group(
    service,
    account_id: str,
    mediation_group_id: str,
    body: dict,
    update_mask: Optional[str] = None,
) -> dict:
    """Patch a mediation group. Requires admob.monetization scope.

    `update_mask` is a comma-separated FieldMask (e.g. "displayName,state,mediationGroupLines").
    """
    name = _ensure_nested_name(account_id, "mediationGroups", mediation_group_id)
    kwargs = {"name": name, "body": body}
    if update_mask:
        kwargs["updateMask"] = update_mask
    return service.accounts().mediationGroups().patch(**kwargs).execute()


def create_mediation_ab_experiment(
    service,
    account_id: str,
    mediation_group_id: str,
    body: dict,
) -> dict:
    """Create an A/B experiment under a mediation group. Requires admob.monetization scope.

    body schema (MediationAbExperiment): displayName, controlMediationLines,
    treatmentMediationLines, treatmentTrafficPercentage, variantLeader, ...
    """
    parent = _ensure_nested_name(
        account_id, "mediationGroups", mediation_group_id
    )
    return (
        service.accounts()
        .mediationGroups()
        .mediationAbExperiments()
        .create(parent=parent, body=body)
        .execute()
    )


def stop_mediation_ab_experiment(
    service,
    account_id: str,
    mediation_group_id: str,
    experiment_id: str,
    variant_choice: Optional[str] = None,
) -> dict:
    """Stop a running A/B experiment. Requires admob.monetization scope.

    `variant_choice` is the StopMediationAbExperimentRequest.variantChoice enum, e.g.
    "CHOOSE_CONTROL", "CHOOSE_TREATMENT", "CHOOSE_POLL_ENDED_VARIANT", or None.
    """
    name = _ensure_nested_name(
        account_id,
        "mediationGroups", mediation_group_id,
        "mediationAbExperiments", experiment_id,
    )
    body = {"variantChoice": variant_choice} if variant_choice else {}
    return (
        service.accounts()
        .mediationGroups()
        .mediationAbExperiments()
        .stop(name=name, body=body)
        .execute()
    )


def list_ad_unit_mappings(
    service,
    account_id: str,
    ad_unit_id: str,
    filter_expr: Optional[str] = None,
    page_size: Optional[int] = None,
) -> list[dict]:
    """List ad unit mappings under an ad unit (handles pagination)."""
    parent = _ensure_nested_name(account_id, "adUnits", ad_unit_id)
    mappings: list[dict] = []
    kwargs = {"parent": parent}
    if filter_expr:
        kwargs["filter"] = filter_expr
    if page_size:
        kwargs["pageSize"] = page_size
    request = service.accounts().adUnits().adUnitMappings().list(**kwargs)
    while request is not None:
        resp = request.execute()
        mappings.extend(resp.get("adUnitMappings", []))
        request = (
            service.accounts()
            .adUnits()
            .adUnitMappings()
            .list_next(request, resp)
        )
    return mappings


def create_ad_unit_mapping(
    service,
    account_id: str,
    ad_unit_id: str,
    body: dict,
) -> dict:
    """Create an ad unit mapping. Requires admob.monetization scope.

    body schema (AdUnitMapping): displayName, adapterId, adUnitConfigurations(map), state.
    """
    parent = _ensure_nested_name(account_id, "adUnits", ad_unit_id)
    return (
        service.accounts()
        .adUnits()
        .adUnitMappings()
        .create(parent=parent, body=body)
        .execute()
    )


def batch_create_ad_unit_mappings(
    service,
    account_id: str,
    requests: list[dict],
) -> dict:
    """Batch create ad unit mappings under an account.

    Each item in `requests` is a CreateAdUnitMappingRequest:
      {"parent": "accounts/{aid}/adUnits/{auid}", "adUnitMapping": { ... }}
    """
    parent = _ensure_resource_name(account_id, "accounts")
    body = {"requests": requests}
    return (
        service.accounts()
        .adUnitMappings()
        .batchCreate(parent=parent, body=body)
        .execute()
    )


def list_ad_sources(service, account_id: str) -> list[dict]:
    """List ad sources available to the account (handles pagination)."""
    parent = _ensure_resource_name(account_id, "accounts")
    sources: list[dict] = []
    request = service.accounts().adSources().list(parent=parent)
    while request is not None:
        resp = request.execute()
        sources.extend(resp.get("adSources", []))
        request = service.accounts().adSources().list_next(request, resp)
    return sources


def list_adapters(service, account_id: str, ad_source_id: str) -> list[dict]:
    """List adapters under an ad source (handles pagination)."""
    parent = _ensure_nested_name(account_id, "adSources", ad_source_id)
    adapters: list[dict] = []
    request = service.accounts().adSources().adapters().list(parent=parent)
    while request is not None:
        resp = request.execute()
        adapters.extend(resp.get("adapters", []))
        request = (
            service.accounts().adSources().adapters().list_next(request, resp)
        )
    return adapters


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
