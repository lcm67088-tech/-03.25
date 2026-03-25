"""
ImportJob 처리 서비스
Wave 1: Google Sheet URL 직접 입력 방식. 동기 처리.
Wave 2: Celery 비동기 이관 예정.

지원 source_type:
  - google_sheet_import (1차): gspread 기반 시트 파싱
  - excel_import (보조): 로컬 파일 파싱
"""
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.models.order import OrderRawInput
from app.models.place import PlaceRawSnapshot

logger = logging.getLogger(__name__)


async def run_import_job(job_id: uuid.UUID, db: AsyncSession) -> None:
    """
    ImportJob 처리 진입점.
    Wave 1: 동기 처리. 실패 시 status=failed로 업데이트.
    """
    job = (
        await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    ).scalar_one_or_none()
    if not job:
        logger.error(f"ImportJob not found: {job_id}")
        return

    job.status = "running"
    await db.commit()

    try:
        if job.source_type == "google_sheet_import":
            await _process_google_sheet(job, db)
        elif job.source_type == "excel_import":
            await _process_excel(job, db)
        else:
            raise ValueError(f"지원하지 않는 source_type: {job.source_type}")

    except Exception as exc:
        logger.exception(f"ImportJob {job_id} 처리 실패: {exc}")
        job.status = "failed"
        job.error_log = {"error": str(exc), "job_id": str(job_id)}
        await db.commit()


async def _process_google_sheet(job: ImportJob, db: AsyncSession) -> None:
    """
    Google Sheet 파싱 처리.
    Wave 1: gspread 라이브러리 사용.
    실제 Google Service Account 설정 필요.
    """
    from app.core.config import get_settings
    import os

    settings = get_settings()

    # Google Sheets API 클라이언트 초기화
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
        if not creds_path or not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Google Service Account JSON을 찾을 수 없습니다: {creds_path}. "
                f".env의 GOOGLE_SERVICE_ACCOUNT_JSON_PATH를 확인하세요."
            )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)

    except ImportError:
        raise ImportError(
            "gspread 또는 google-auth 미설치. "
            "`pip install gspread google-auth` 후 재시도하세요."
        )

    # 시트 URL에서 스프레드시트 열기
    source_ref = job.source_ref
    try:
        spreadsheet = gc.open_by_url(source_ref)
    except Exception as e:
        raise ValueError(f"Google Sheet를 열 수 없습니다: {source_ref}. 오류: {e}")

    # 시트 선택
    if job.sheet_name:
        worksheet = spreadsheet.worksheet(job.sheet_name)
    else:
        worksheet = spreadsheet.get_worksheet(0)

    # 헤더 + 데이터 파싱
    all_records = worksheet.get_all_records()
    total_rows = len(all_records)
    success_count = 0
    failed_count = 0
    error_details = []

    for idx, row_data in enumerate(all_records):
        try:
            raw_input = await _save_raw_input(
                db=db,
                job=job,
                row_data=row_data,
                row_number=idx + 2,  # 1 = 헤더, 2 = 첫 데이터 행
            )
            success_count += 1
        except Exception as row_exc:
            failed_count += 1
            error_details.append({
                "row": idx + 2,
                "data": str(row_data)[:200],
                "error": str(row_exc),
            })
            logger.warning(f"Row {idx + 2} 처리 실패: {row_exc}")

    # 결과 업데이트
    job.total_rows = total_rows
    job.success_rows = success_count
    job.failed_rows = failed_count
    job.status = "done" if failed_count == 0 else ("failed" if success_count == 0 else "partial")
    job.error_log = {"errors": error_details} if error_details else None
    job.result_summary = {
        "total": total_rows,
        "success": success_count,
        "failed": failed_count,
        "sheet_title": worksheet.title,
        "spreadsheet_title": spreadsheet.title,
    }
    await db.commit()

    logger.info(
        f"ImportJob {job.id} 완료: "
        f"total={total_rows}, success={success_count}, failed={failed_count}"
    )


async def _process_excel(job: ImportJob, db: AsyncSession) -> None:
    """
    Excel 파일 파싱 처리. (보조 경로)
    Wave 1: 파일 업로드 없이 서버 로컬 파일 경로만 지원.
    실제 파일 업로드 처리는 Wave 2에서 구현.
    """
    raise NotImplementedError(
        "Excel 임포트는 Wave 2에서 구현 예정입니다. "
        "현재는 Google Sheet URL 입력 방식을 사용하세요."
    )


async def _save_raw_input(
    db: AsyncSession,
    job: ImportJob,
    row_data: dict[str, Any],
    row_number: int,
) -> OrderRawInput:
    """
    개별 row를 OrderRawInput 또는 PlaceRawSnapshot으로 저장.
    job.job_type에 따라 분기.
    """
    if job.job_type == "order_import":
        raw = OrderRawInput(
            source_type=job.source_type,
            source_ref=f"{job.source_ref}#row{row_number}",
            source_row_index=row_number,   # 마이그레이션 기준: source_row_index
            import_job_id=job.id,
            raw_data=row_data,
        )
        db.add(raw)
        await db.flush()
        return raw

    elif job.job_type == "place_import":
        snap = PlaceRawSnapshot(
            source_type=job.source_type,
            source_ref=f"{job.source_ref}#row{row_number}",
            import_job_id=job.id,
            raw_data=row_data,
        )
        db.add(snap)
        await db.flush()
        return snap  # type: ignore[return-value]

    else:
        raise ValueError(f"알 수 없는 job_type: {job.job_type}")
