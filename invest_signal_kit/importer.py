"""Data Import & Normalization.

Import common CSV/JSON inputs and convert them into formats compatible
with invest-signal-kit workflows: backtest scenarios, portfolio analysis,
and rebalance planning.

Supported imports:
  - price CSV  -> normalized price_series for backtest
  - signal CSV -> normalized signal_events for backtest
  - holdings CSV -> portfolio/rebalance compatible holdings
  - benchmark CSV -> benchmark series

All functions return (data, errors) tuples. On success errors is empty.
On failure data is None and errors contains human-readable messages.

This is research tooling, not financial advice. No external APIs.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Validation Error Model
# ---------------------------------------------------------------------------

@dataclass
class ImportError:
    """A single import validation error."""
    row: int = 0
    """1-based row number (0 = file-level error)."""
    column: str = ""
    """Column name, or empty for row-level errors."""
    message: str = ""
    """Human-readable error description."""


@dataclass
class ImportResult:
    """Result of an import operation."""
    data: Any = None
    """The imported and normalized data, or None on failure."""
    errors: List[ImportError] = field(default_factory=list)
    """List of validation errors. Empty on success."""
    warnings: List[ImportError] = field(default_factory=list)
    """Non-fatal issues found during import."""
    row_count: int = 0
    """Number of data rows processed (excluding header)."""


# ---------------------------------------------------------------------------
# CSV Parsing Helpers
# ---------------------------------------------------------------------------

_REQUIRED_PRICE_COLUMNS = {"date", "close"}
_OPTIONAL_PRICE_COLUMNS = {"open", "high", "low", "volume"}
_ALL_PRICE_COLUMNS = _REQUIRED_PRICE_COLUMNS | _OPTIONAL_PRICE_COLUMNS

_REQUIRED_SIGNAL_COLUMNS = {"date", "asset", "action"}
_OPTIONAL_SIGNAL_COLUMNS = {
    "quantity", "price", "reason", "confidence",
    "stop_price", "target_price", "time_stop_days",
}
_ALL_SIGNAL_COLUMNS = _REQUIRED_SIGNAL_COLUMNS | _OPTIONAL_SIGNAL_COLUMNS

_VALID_ACTIONS = {
    "enter", "add", "trim", "exit", "stop", "target",
    "time_stop", "skip", "blocked",
}

_REQUIRED_HOLDINGS_COLUMNS = {"code", "shares", "current_price"}
_OPTIONAL_HOLDINGS_COLUMNS = {
    "name", "asset_type", "sector", "entry_price",
    "stop_price", "direction",
}
_ALL_HOLDINGS_COLUMNS = _REQUIRED_HOLDINGS_COLUMNS | _OPTIONAL_HOLDINGS_COLUMNS


def _read_csv_rows(text: str) -> Tuple[List[str], List[Dict[str, str]], List[ImportError]]:
    """Parse CSV text into header and row dicts.

    Returns (headers, rows, errors). On fatal parse error, rows is empty.
    """
    errors: List[ImportError] = []
    if not text.strip():
        errors.append(ImportError(row=0, message="File is empty."))
        return [], [], errors

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        errors.append(ImportError(row=0, message="Could not parse CSV header."))
        return [], [], errors

    headers = [h.strip() for h in reader.fieldnames]
    rows: List[Dict[str, str]] = []
    for i, row in enumerate(reader, start=2):
        rows.append({k.strip(): (v.strip() if v else "") for k, v in row.items()})

    return headers, rows, errors


def _check_required_columns(
    headers: List[str], required: set, label: str,
) -> List[ImportError]:
    """Check that required columns are present."""
    errors: List[ImportError] = []
    header_set = {h.lower() for h in headers}
    missing = required - header_set
    if missing:
        errors.append(ImportError(
            row=0,
            message=f"Missing required {label} column(s): {', '.join(sorted(missing))}. "
                    f"Found: {', '.join(headers)}",
        ))
    return errors


def _parse_float(
    value: str, row: int, column: str, required: bool = False,
) -> Tuple[Optional[float], Optional[ImportError]]:
    """Parse a float value, returning (value, error)."""
    if not value or not value.strip():
        if required:
            return None, ImportError(row=row, column=column,
                                     message=f"Column '{column}' is required but empty.")
        return 0.0, None
    try:
        return float(value), None
    except ValueError:
        return None, ImportError(
            row=row, column=column,
            message=f"Cannot parse '{value}' as number in column '{column}'.")


def _parse_int(
    value: str, row: int, column: str, required: bool = False,
) -> Tuple[Optional[int], Optional[ImportError]]:
    """Parse an int value, returning (value, error)."""
    if not value or not value.strip():
        if required:
            return None, ImportError(row=row, column=column,
                                     message=f"Column '{column}' is required but empty.")
        return 0, None
    try:
        return int(float(value)), None
    except ValueError:
        return None, ImportError(
            row=row, column=column,
            message=f"Cannot parse '{value}' as integer in column '{column}'.")


# ---------------------------------------------------------------------------
# Price CSV Import
# ---------------------------------------------------------------------------

def import_price_csv(text: str) -> ImportResult:
    """Import a price CSV and normalize to backtest-compatible format.

    Required columns: date, close
    Optional columns: open, high, low, volume, asset

    When an 'asset' column is present, duplicate dates are allowed across
    different assets (multi-asset price CSV). Without an 'asset' column,
    duplicate dates within the file are flagged as errors.

    Returns ImportResult with data as list of price dicts, sorted by date.
    """
    headers, rows, errors = _read_csv_rows(text)
    if errors:
        return ImportResult(errors=errors)

    errors.extend(_check_required_columns(headers, _REQUIRED_PRICE_COLUMNS, "price"))
    if errors:
        return ImportResult(errors=errors, row_count=len(rows))

    if not rows:
        return ImportResult(errors=[ImportError(row=0, message="CSV has header but no data rows.")])

    data = []
    seen_dates: Dict[str, int] = {}
    seen_date_assets: Dict[Tuple[str, str], int] = {}
    warnings: List[ImportError] = []
    header_set = {h.lower() for h in headers}
    has_asset_col = "asset" in header_set

    for i, row in enumerate(rows, start=2):
        date = row.get("date", "").strip()
        if not date:
            errors.append(ImportError(row=i, column="date", message="Date is empty."))
            continue

        asset = row.get("asset", "").strip() if has_asset_col else ""

        if has_asset_col:
            key = (date, asset)
            if key in seen_date_assets:
                errors.append(ImportError(
                    row=i, column="date",
                    message=f"Duplicate date '{date}' for asset '{asset}' "
                            f"(first seen on row {seen_date_assets[key]})."))
                continue
            seen_date_assets[key] = i
        else:
            if date in seen_dates:
                errors.append(ImportError(
                    row=i, column="date",
                    message=f"Duplicate date '{date}' (first seen on row {seen_dates[date]})."))
                continue
            seen_dates[date] = i

        close_val, err = _parse_float(row.get("close", ""), i, "close", required=True)
        if err:
            errors.append(err)
            continue

        entry: Dict[str, Any] = {"date": date, "close": close_val}
        if has_asset_col and asset:
            entry["asset"] = asset

        for col in ("open", "high", "low", "volume"):
            if col in header_set:
                val, err = _parse_float(row.get(col, ""), i, col)
                if err:
                    errors.append(err)
                    break
                entry[col] = val

        else:
            data.append(entry)

    # Sort by date (and asset for stable ordering in multi-asset)
    data.sort(key=lambda d: (d["date"], d.get("asset", "")))

    if errors:
        return ImportResult(errors=errors, warnings=warnings, row_count=len(rows))

    return ImportResult(data=data, warnings=warnings, row_count=len(rows))


def import_price_json(text: str) -> ImportResult:
    """Import a price series from JSON (list of price dicts).

    When entries contain an 'asset' field, duplicate dates are allowed
    across different assets (multi-asset price data).
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ImportResult(errors=[ImportError(message=f"Invalid JSON: {exc}")])

    if not isinstance(data, list):
        return ImportResult(errors=[ImportError(message="JSON must be a list of price objects.")])

    if not data:
        return ImportResult(errors=[ImportError(message="JSON price list is empty.")])

    result = []
    seen_dates: Dict[str, int] = {}
    seen_date_assets: Dict[Tuple[str, str], int] = {}
    errors: List[ImportError] = []

    has_asset_field = any(isinstance(e, dict) and "asset" in e for e in data if isinstance(e, dict))

    for i, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            errors.append(ImportError(row=i, message="Entry is not a JSON object."))
            continue
        date = str(entry.get("date", ""))
        if not date:
            errors.append(ImportError(row=i, column="date", message="Date is missing."))
            continue

        asset = str(entry.get("asset", "")) if has_asset_field else ""

        if has_asset_field:
            key = (date, asset)
            if key in seen_date_assets:
                errors.append(ImportError(
                    row=i, column="date",
                    message=f"Duplicate date '{date}' for asset '{asset}' "
                            f"(first seen at index {seen_date_assets[key]})."))
                continue
            seen_date_assets[key] = i
        else:
            if date in seen_dates:
                errors.append(ImportError(
                    row=i, column="date",
                    message=f"Duplicate date '{date}' (first seen at index {seen_dates[date]})."))
                continue
            seen_dates[date] = i

        close_val = entry.get("close")
        if close_val is None:
            errors.append(ImportError(row=i, column="close", message="Close price is required."))
            continue

        try:
            close_val = float(close_val)
        except (TypeError, ValueError):
            errors.append(ImportError(row=i, column="close",
                                      message=f"Cannot parse '{close_val}' as number."))
            continue

        out: Dict[str, Any] = {"date": date, "close": close_val}
        if has_asset_field and asset:
            out["asset"] = asset
        for col in ("open", "high", "low", "volume"):
            if col in entry:
                try:
                    out[col] = float(entry[col])
                except (TypeError, ValueError):
                    errors.append(ImportError(row=i, column=col,
                                              message=f"Cannot parse '{entry[col]}' as number."))
        result.append(out)

    result.sort(key=lambda d: (d["date"], d.get("asset", "")))

    if errors:
        return ImportResult(errors=errors, row_count=len(data))

    return ImportResult(data=result, row_count=len(data))


# ---------------------------------------------------------------------------
# Signal CSV Import
# ---------------------------------------------------------------------------

def import_signal_csv(text: str) -> ImportResult:
    """Import a signal CSV and normalize to backtest signal events.

    Required columns: date, asset, action
    Optional columns: quantity, price, reason, confidence,
                      stop_price, target_price, time_stop_days

    Valid actions: enter, add, trim, exit, stop, target, time_stop, skip, blocked
    """
    headers, rows, errors = _read_csv_rows(text)
    if errors:
        return ImportResult(errors=errors)

    errors.extend(_check_required_columns(headers, _REQUIRED_SIGNAL_COLUMNS, "signal"))
    if errors:
        return ImportResult(errors=errors, row_count=len(rows))

    if not rows:
        return ImportResult(errors=[ImportError(row=0, message="CSV has header but no data rows.")])

    data = []
    warnings: List[ImportError] = []

    for i, row in enumerate(rows, start=2):
        date = row.get("date", "").strip()
        if not date:
            errors.append(ImportError(row=i, column="date", message="Date is empty."))
            continue

        asset = row.get("asset", "").strip()
        if not asset:
            errors.append(ImportError(row=i, column="asset", message="Asset is empty."))
            continue

        action = row.get("action", "").strip().lower()
        if not action:
            errors.append(ImportError(row=i, column="action", message="Action is empty."))
            continue
        if action not in _VALID_ACTIONS:
            errors.append(ImportError(
                row=i, column="action",
                message=f"Unknown action '{action}'. Valid: {', '.join(sorted(_VALID_ACTIONS))}."))
            continue

        quantity, err = _parse_float(row.get("quantity", ""), i, "quantity")
        if err:
            errors.append(err)
            continue

        price, err = _parse_float(row.get("price", ""), i, "price")
        if err:
            errors.append(err)
            continue

        reason = row.get("reason", "").strip()

        confidence, err = _parse_float(row.get("confidence", ""), i, "confidence")
        if err:
            errors.append(err)
            continue

        stop_price, err = _parse_float(row.get("stop_price", ""), i, "stop_price")
        if err:
            errors.append(err)
            continue

        target_price, err = _parse_float(row.get("target_price", ""), i, "target_price")
        if err:
            errors.append(err)
            continue

        time_stop_days, err = _parse_int(row.get("time_stop_days", ""), i, "time_stop_days")
        if err:
            errors.append(err)
            continue

        entry = {
            "date": date,
            "asset": asset,
            "action": action,
        }
        if quantity:
            entry["quantity"] = quantity
        if price:
            entry["price"] = price
        if reason:
            entry["reason"] = reason
        if confidence:
            entry["confidence"] = confidence
        if stop_price:
            entry["stop_price"] = stop_price
        if target_price:
            entry["target_price"] = target_price
        if time_stop_days:
            entry["time_stop_days"] = time_stop_days

        data.append(entry)

    if errors:
        return ImportResult(errors=errors, warnings=warnings, row_count=len(rows))

    return ImportResult(data=data, warnings=warnings, row_count=len(rows))


def import_signal_json(text: str) -> ImportResult:
    """Import signal events from JSON (list of signal event dicts)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ImportResult(errors=[ImportError(message=f"Invalid JSON: {exc}")])

    if not isinstance(data, list):
        return ImportResult(errors=[ImportError(message="JSON must be a list of signal event objects.")])

    if not data:
        return ImportResult(errors=[ImportError(message="JSON signal list is empty.")])

    result = []
    errors: List[ImportError] = []

    for i, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            errors.append(ImportError(row=i, message="Entry is not a JSON object."))
            continue

        date = str(entry.get("date", ""))
        if not date:
            errors.append(ImportError(row=i, column="date", message="Date is missing."))
            continue

        asset = str(entry.get("asset", ""))
        if not asset:
            errors.append(ImportError(row=i, column="asset", message="Asset is missing."))
            continue

        action = str(entry.get("action", "")).lower()
        if action not in _VALID_ACTIONS:
            errors.append(ImportError(
                row=i, column="action",
                message=f"Unknown action '{action}'. Valid: {', '.join(sorted(_VALID_ACTIONS))}."))
            continue

        out = {"date": date, "asset": asset, "action": action}
        for col in ("quantity", "price", "confidence", "stop_price", "target_price"):
            if col in entry:
                try:
                    out[col] = float(entry[col])
                except (TypeError, ValueError):
                    errors.append(ImportError(row=i, column=col,
                                              message=f"Cannot parse '{entry[col]}' as number."))
        if "reason" in entry:
            out["reason"] = str(entry["reason"])
        if "time_stop_days" in entry:
            try:
                out["time_stop_days"] = int(float(entry["time_stop_days"]))
            except (TypeError, ValueError):
                errors.append(ImportError(row=i, column="time_stop_days",
                                          message=f"Cannot parse '{entry['time_stop_days']}' as integer."))
        result.append(out)

    if errors:
        return ImportResult(errors=errors, row_count=len(data))

    return ImportResult(data=result, row_count=len(data))


# ---------------------------------------------------------------------------
# Holdings CSV Import
# ---------------------------------------------------------------------------

def import_holdings_csv(text: str) -> ImportResult:
    """Import a holdings CSV for portfolio/rebalance use.

    Required columns: code, shares, current_price
    Optional columns: name, asset_type, sector, entry_price, stop_price, direction
    """
    headers, rows, errors = _read_csv_rows(text)
    if errors:
        return ImportResult(errors=errors)

    errors.extend(_check_required_columns(headers, _REQUIRED_HOLDINGS_COLUMNS, "holdings"))
    if errors:
        return ImportResult(errors=errors, row_count=len(rows))

    if not rows:
        return ImportResult(errors=[ImportError(row=0, message="CSV has header but no data rows.")])

    data = []
    warnings: List[ImportError] = []

    for i, row in enumerate(rows, start=2):
        code = row.get("code", "").strip()
        if not code:
            errors.append(ImportError(row=i, column="code", message="Instrument code is empty."))
            continue

        shares, err = _parse_float(row.get("shares", ""), i, "shares", required=True)
        if err:
            errors.append(err)
            continue

        current_price, err = _parse_float(row.get("current_price", ""), i, "current_price", required=True)
        if err:
            errors.append(err)
            continue

        entry_price, err = _parse_float(row.get("entry_price", ""), i, "entry_price")
        if err:
            errors.append(err)
            continue

        stop_price, err = _parse_float(row.get("stop_price", ""), i, "stop_price")
        if err:
            errors.append(err)
            continue

        name = row.get("name", "").strip()
        asset_type = row.get("asset_type", "stock").strip() or "stock"
        sector = row.get("sector", "").strip()
        direction = row.get("direction", "long").strip() or "long"

        if direction not in ("long", "short"):
            warnings.append(ImportError(
                row=i, column="direction",
                message=f"Unknown direction '{direction}', defaulting to 'long'."))
            direction = "long"

        entry = {
            "code": code,
            "shares": shares,
            "current_price": current_price,
        }
        if name:
            entry["name"] = name
        if asset_type != "stock":
            entry["asset_type"] = asset_type
        if sector:
            entry["sector"] = sector
        if entry_price:
            entry["entry_price"] = entry_price
        if stop_price:
            entry["stop_price"] = stop_price
        if direction != "long":
            entry["direction"] = direction

        data.append(entry)

    if errors:
        return ImportResult(errors=errors, warnings=warnings, row_count=len(rows))

    return ImportResult(data=data, warnings=warnings, row_count=len(rows))


def import_holdings_json(text: str) -> ImportResult:
    """Import holdings from JSON (list of holding dicts)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ImportResult(errors=[ImportError(message=f"Invalid JSON: {exc}")])

    if not isinstance(data, list):
        return ImportResult(errors=[ImportError(message="JSON must be a list of holding objects.")])

    if not data:
        return ImportResult(errors=[ImportError(message="JSON holdings list is empty.")])

    result = []
    errors: List[ImportError] = []

    for i, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            errors.append(ImportError(row=i, message="Entry is not a JSON object."))
            continue

        code = str(entry.get("code", ""))
        if not code:
            errors.append(ImportError(row=i, column="code", message="Instrument code is missing."))
            continue

        shares = entry.get("shares")
        if shares is None:
            errors.append(ImportError(row=i, column="shares", message="Shares is required."))
            continue
        try:
            shares = float(shares)
        except (TypeError, ValueError):
            errors.append(ImportError(row=i, column="shares",
                                      message=f"Cannot parse '{shares}' as number."))
            continue

        current_price = entry.get("current_price")
        if current_price is None:
            errors.append(ImportError(row=i, column="current_price", message="Current price is required."))
            continue
        try:
            current_price = float(current_price)
        except (TypeError, ValueError):
            errors.append(ImportError(row=i, column="current_price",
                                      message=f"Cannot parse '{current_price}' as number."))
            continue

        out = {"code": code, "shares": shares, "current_price": current_price}
        for col in ("name", "asset_type", "sector", "direction"):
            if col in entry:
                out[col] = str(entry[col])
        for col in ("entry_price", "stop_price"):
            if col in entry:
                try:
                    out[col] = float(entry[col])
                except (TypeError, ValueError):
                    errors.append(ImportError(row=i, column=col,
                                              message=f"Cannot parse '{entry[col]}' as number."))
        result.append(out)

    if errors:
        return ImportResult(errors=errors, row_count=len(data))

    return ImportResult(data=result, row_count=len(data))


# ---------------------------------------------------------------------------
# Generic Auto-Detect Import
# ---------------------------------------------------------------------------

def import_prices(path_or_text: str, *, is_path: bool = True) -> ImportResult:
    """Import prices from a CSV or JSON file/text.

    If is_path=True, reads from the file path.
    If is_path=False, treats path_or_text as file content.
    """
    if is_path:
        p = Path(path_or_text)
        if not p.exists():
            return ImportResult(errors=[ImportError(message=f"File not found: {path_or_text}")])
        text = p.read_text(encoding="utf-8")
    else:
        text = path_or_text

    if path_or_text.rstrip().endswith(".json") or (not is_path and text.lstrip().startswith("[")):
        return import_price_json(text)
    return import_price_csv(text)


def import_signals(path_or_text: str, *, is_path: bool = True) -> ImportResult:
    """Import signal events from a CSV or JSON file/text."""
    if is_path:
        p = Path(path_or_text)
        if not p.exists():
            return ImportResult(errors=[ImportError(message=f"File not found: {path_or_text}")])
        text = p.read_text(encoding="utf-8")
    else:
        text = path_or_text

    if path_or_text.rstrip().endswith(".json") or (not is_path and text.lstrip().startswith("[")):
        return import_signal_json(text)
    return import_signal_csv(text)


def import_holdings(path_or_text: str, *, is_path: bool = True) -> ImportResult:
    """Import holdings from a CSV or JSON file/text."""
    if is_path:
        p = Path(path_or_text)
        if not p.exists():
            return ImportResult(errors=[ImportError(message=f"File not found: {path_or_text}")])
        text = p.read_text(encoding="utf-8")
    else:
        text = path_or_text

    if path_or_text.rstrip().endswith(".json") or (not is_path and text.lstrip().startswith("[")):
        return import_holdings_json(text)
    return import_holdings_csv(text)


# ---------------------------------------------------------------------------
# Markdown Report
# ---------------------------------------------------------------------------

def render_import_markdown(result: ImportResult, label: str = "Import") -> str:
    """Render import result as Markdown."""
    lines: List[str] = []
    lines.append(f"# {label} Report")
    lines.append("")

    if result.errors:
        lines.append("## Errors")
        for e in result.errors:
            loc = f"row {e.row}" if e.row else "file"
            if e.column:
                loc += f", column '{e.column}'"
            lines.append(f"- **[{loc}]** {e.message}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        for w in result.warnings:
            loc = f"row {w.row}" if w.row else "file"
            if w.column:
                loc += f", column '{w.column}'"
            lines.append(f"- [{loc}] {w.message}")
        lines.append("")

    if result.data is not None:
        lines.append("## Result")
        lines.append(f"- **Rows processed:** {result.row_count}")
        if isinstance(result.data, list):
            lines.append(f"- **Records imported:** {len(result.data)}")
        lines.append("")

    if not result.errors and not result.warnings:
        lines.append("Import completed successfully with no issues.")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by invest-signal-kit import. Not investment advice.*")
    return "\n".join(lines)
