"""Real multipart upload ingestion."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, File, UploadFile

from ledgerpilot.api.errors import LedgerPilotError
from ledgerpilot.ingest.loaders import (
    to_bank_txn,
    to_gateway_txn,
    to_order,
    to_payout,
)
from ledgerpilot.ingest.validate import (
    validate_bank_txns,
    validate_gateway_txns,
    validate_orders,
    validate_payouts,
)
from ledgerpilot.recon.engine import ReconContext, ReconEngine
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import (
    BankRepository,
    BreakRepository,
    GatewayRepository,
    IngestRunRepository,
    MatchRepository,
    OrderRepository,
    PayoutRepository,
    QuarantineRepository,
    ReconRunRepository,
)

router = APIRouter(prefix="", tags=["upload"])

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
_REQUIRED_FILES = {
    "orders": "orders",
    "gateway_txns": "gateway_txns",
    "payouts": "payouts",
    "bank_txns": "bank_txns",
}


class UploadValidationError(LedgerPilotError):
    status_code = 400
    code = "upload_validation_error"


def _ensure_supported(file: UploadFile) -> None:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            "Unsupported file type. Upload CSV or XLSX files only."
        )


def _ensure_size(data: bytes, filename: str) -> None:
    if len(data) > _MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            f"{filename} is too large. Maximum upload size is 10 MB per file."
        )


def _read_csv_rows(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise UploadValidationError("CSV file is missing a header row.")
    return [dict(row) for row in reader]


def _read_xlsx_rows(data: bytes) -> list[dict[str, Any]]:
    frame = pd.read_excel(io.BytesIO(data), engine="openpyxl")
    if frame.empty:
        return []
    normalized = frame.where(pd.notna(frame), None)
    return cast(list[dict[str, Any]], normalized.to_dict(orient="records"))


async def _read_rows_for_upload(file: UploadFile) -> list[dict[str, Any]]:
    _ensure_supported(file)
    data = await file.read()
    _ensure_size(data, file.filename or "uploaded file")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix == ".csv":
        return _read_csv_rows(data)
    if suffix == ".xlsx":
        return _read_xlsx_rows(data)
    raise UploadValidationError("Unsupported file type. Upload CSV or XLSX files only.")


@router.post("/upload", summary="Upload and ingest CSV/XLSX datasets")
async def upload_dataset(
    orders: UploadFile = File(..., description="Orders CSV/XLSX file"),
    gateway_txns: UploadFile = File(..., description="Gateway transactions CSV/XLSX file"),
    payouts: UploadFile = File(..., description="Payouts CSV/XLSX file"),
    bank_txns: UploadFile = File(..., description="Bank statement CSV/XLSX file"),
) -> dict[str, Any]:
    """Validate uploaded files, ingest accepted rows, and run reconciliation."""
    incoming = {
        "orders": orders,
        "gateway_txns": gateway_txns,
        "payouts": payouts,
        "bank_txns": bank_txns,
    }

    missing = [name for name, file in incoming.items() if file.filename in (None, "")]
    if missing:
        raise UploadValidationError(f"Missing required file(s): {', '.join(missing)}")

    run_id = f"RUN-UPLOAD-{uuid4().hex[:12]}"
    ingest_run_id = f"ING-{uuid4().hex[:12]}"
    counts: dict[str, int] = {
        "orders": 0,
        "gateway_txns": 0,
        "payouts": 0,
        "bank_txns": 0,
        "quarantined": 0,
        "breaks": 0,
        "matches": 0,
    }

    with session_scope() as session:
        run_repo = IngestRunRepository(session)
        quarantine_repo = QuarantineRepository(session)
        order_repo = OrderRepository(session)
        gateway_repo = GatewayRepository(session)
        payout_repo = PayoutRepository(session)
        bank_repo = BankRepository(session)

        run_repo.start(
            ingest_run_id,
            source_dir="uploaded",
            started_at=datetime.now(UTC),
            scenario=None,
        )

        file_rows: dict[str, list[dict[str, Any]]] = {}
        for key, file in incoming.items():
            try:
                file_rows[key] = await _read_rows_for_upload(file)
            except ValueError as exc:
                raise UploadValidationError(str(exc)) from exc

        rows_by_dataset = {
            "orders": file_rows["orders"],
            "gateway_txns": file_rows["gateway_txns"],
            "payouts": file_rows["payouts"],
            "bank_txns": file_rows["bank_txns"],
        }

        for key, rows in rows_by_dataset.items():
            try:
                if key == "orders":
                    accepted, report = validate_orders(rows)
                    order_records = [
                        to_order(row).model_copy(update={"run_id": run_id})
                        for row in accepted
                    ]
                    counts["orders"] = order_repo.bulk_upsert(order_records)
                elif key == "gateway_txns":
                    accepted, report = validate_gateway_txns(rows)
                    gateway_records = [
                        to_gateway_txn(row).model_copy(update={"run_id": run_id})
                        for row in accepted
                    ]
                    counts["gateway_txns"] = gateway_repo.bulk_upsert(gateway_records)
                elif key == "payouts":
                    accepted, report = validate_payouts(rows)
                    payout_records = [
                        to_payout(row).model_copy(update={"run_id": run_id})
                        for row in accepted
                    ]
                    counts["payouts"] = payout_repo.bulk_upsert(payout_records)
                else:
                    accepted, report = validate_bank_txns(rows)
                    bank_records = [
                        to_bank_txn(row).model_copy(update={"run_id": run_id})
                        for row in accepted
                    ]
                    counts["bank_txns"] = bank_repo.bulk_upsert(bank_records)
                if report.quarantined:
                    quarantine_repo.add_many(ingest_run_id, report.quarantined)
                    counts["quarantined"] += len(report.quarantined)
            except Exception as exc:  # pragma: no cover - surfaced to API caller
                raise UploadValidationError(
                    f"Dataset '{key}' failed validation: {exc}"
                ) from exc

        run_repo.finish(
            ingest_run_id,
            finished_at=datetime.now(UTC),
            counts=counts,
            status="completed",
        )

        order_records = order_repo.for_run(run_id)
        gateway_records = gateway_repo.for_run(run_id)
        payout_records = payout_repo.for_run(run_id)
        bank_records = bank_repo.for_run(run_id)

        ctx = ReconContext(
            run_id=run_id,
            orders=order_records,
            gateway_txns=gateway_records,
            payouts=payout_records,
            bank_txns=bank_records,
        )
        result = ReconEngine().run_context(ctx)

        ReconRunRepository(session).upsert(result.run)
        match_repo = MatchRepository(session)
        break_repo = BreakRepository(session)
        for match in result.matches:
            match_repo.upsert(match)
        for brk in result.breaks:
            break_repo.upsert(brk)

        counts["matches"] = len(result.matches)
        counts["breaks"] = len(result.breaks)
        result.run = result.run.model_copy(
            update={
                "counts": {
                    **result.run.counts,
                    "orders": counts["orders"],
                    "gateway_txns": counts["gateway_txns"],
                    "payouts": counts["payouts"],
                    "bank_txns": counts["bank_txns"],
                    "quarantined": counts["quarantined"],
                }
            }
        )

        response = {
            "run_id": result.run.run_id,
            "ingest_run_id": ingest_run_id,
            "status": result.run.status,
            "scenario": "uploaded",
            "counts": result.run.counts,
            "persisted": {
                "orders": counts["orders"],
                "gateway_txns": counts["gateway_txns"],
                "payouts": counts["payouts"],
                "bank_txns": counts["bank_txns"],
                "quarantined": counts["quarantined"],
            },
        }

        return response
