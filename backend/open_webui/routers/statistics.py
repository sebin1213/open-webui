import io
import re
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import BaseModel

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_admin_user
from open_webui.models.users import Users
from open_webui.models.chats import Chats
from open_webui.models.files import Files
from open_webui.models.knowledge import Knowledges
from open_webui.models.vector_storage import VectorStorage
from open_webui.config import UPLOAD_DIR
from open_webui.env import DATA_DIR
from open_webui.storage.provider import Storage
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.models.auths import Auths
import xlsxwriter


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class DateRangeForm(BaseModel):
    # Dates are optional; default range is last 7 days (inclusive)
    start_date: str | None = None  # YYYY-MM-DD
    end_date: str | None = None  # YYYY-MM-DD

    # Optional time components; if omitted defaults are 00:00 for start, 23:59 for end
    start_time: str | None = None  # HH:MM or HH:MM:SS
    end_time: str | None = None  # HH:MM or HH:MM:SS

    # Optional filters (independent). If None, do not filter.
    team: str | None = None
    headquarters: str | None = None
    division: str | None = None


def _parse_date_range(form_data: DateRangeForm) -> tuple[int, int, dict]:
    """
    Convert provided date and time strings to epoch seconds [start, end_exclusive).

    - If dates are not provided, default to a 7-day window ending today: [today-6d 00:00:00, today 23:59:59].
    - If only one date is provided:
        - Only end_date -> start_date = end_date - 6 days
        - Only start_date -> end_date = start_date + 6 days
    - If times are omitted, defaults are 00:00:00 for start, 23:59:59 for end.

    Returns (start_ts, end_exclusive_ts, normalized_meta)
    where normalized_meta contains the normalized start/end date/time strings used.
    """
    def parse_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d")

    def parse_time(time_str: str, is_start: bool) -> tuple[int, int, int]:
        # Accept HH:MM or HH:MM:SS
        try:
            parts = [int(x) for x in time_str.split(":")]
            if len(parts) == 2:
                hh, mm = parts
                ss = 0 if is_start else 59
            elif len(parts) == 3:
                hh, mm, ss = parts
            else:
                raise ValueError("Invalid time format")
            if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
                raise ValueError("Time out of range")
            return hh, mm, ss
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid time format: {e}")

    # Resolve dates
    today = datetime.now()
    start_date_str = form_data.start_date
    end_date_str = form_data.end_date

    try:
        if start_date_str and not end_date_str:
            start_date = parse_date(start_date_str)
            end_date = start_date + timedelta(days=6)
        elif end_date_str and not start_date_str:
            end_date = parse_date(end_date_str)
            start_date = end_date - timedelta(days=6)
        elif start_date_str and end_date_str:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
        else:
            # Default last 7 days window ending today
            end_date = datetime(year=today.year, month=today.month, day=today.day)
            start_date = end_date - timedelta(days=6)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    # Resolve times with defaults
    if form_data.start_time:
        sh, sm, ss = parse_time(form_data.start_time, is_start=True)
    else:
        sh, sm, ss = 0, 0, 0  # 00:00:00

    if form_data.end_time:
        eh, em, es = parse_time(form_data.end_time, is_start=False)
    else:
        # Default 23:59:59
        eh, em, es = 23, 59, 59

    start_dt = datetime(
        year=start_date.year, month=start_date.month, day=start_date.day, hour=sh, minute=sm, second=ss
    )
    end_inclusive_dt = datetime(
        year=end_date.year, month=end_date.month, day=end_date.day, hour=eh, minute=em, second=es
    )

    # Ensure chronological order
    if end_inclusive_dt < start_dt:
        raise HTTPException(status_code=400, detail="end datetime must be after start datetime")

    # End is exclusive for DB queries
    end_exclusive_dt = end_inclusive_dt + timedelta(seconds=1)

    start_ts = int(start_dt.timestamp())
    end_exclusive_ts = int(end_exclusive_dt.timestamp())

    normalized = {
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "start_time": start_dt.strftime("%H:%M:%S"),
        "end_date": end_inclusive_dt.strftime("%Y-%m-%d"),
        "end_time": end_inclusive_dt.strftime("%H:%M:%S"),
    }
    return start_ts, end_exclusive_ts, normalized


def _clean_str(val: str | None) -> str | None:
    if val is None:
        return None
    return re.sub(r"\s+", "", val.strip())


def _compute_usage_users_data(
    start_ts: int,
    end_next_ts: int,
    *,
    team_filter: str | None = None,
    hq_filter: str | None = None,
    division_filter: str | None = None,
) -> list[dict]:
    def _sum_compacted_usage_from_info(user_info, start_ts: int, end_ts: int) -> tuple[int, int]:
        """
        user.info에 저장된 압축 사용량 합계 계산
        
        파일 업로드만 압축됨. 메시지 수는 데이터베이스에서 직접 조회.
        (prompts, uploads) 반환 - prompts는 호환성 유지용
        """
        try:
            if not user_info or not isinstance(user_info, dict):
                return 0, 0

            usage = user_info.get("usage", {}) or {}
            daily = usage.get("daily", {}) or {}

            if not isinstance(daily, dict):
                return 0, 0

            prompts_sum = 0
            uploads_sum = 0

            for day_str, counts in daily.items():
                try:
                    day_dt = datetime.strptime(day_str, "%Y-%m-%d")
                    day_start_ts = int(day_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
                except Exception:
                    continue

                if start_ts <= day_start_ts < end_ts:
                    if isinstance(counts, dict):
                        prompts_sum += int(counts.get("prompts", 0) or 0)
                        uploads_sum += int(counts.get("uploads", 0) or 0)

            return prompts_sum, uploads_sum
        except Exception:
            return 0, 0

    try:
        msg_counts = dict(Chats.get_message_counts_by_user_in_timerange(start_ts, end_next_ts))
        file_counts = dict(Files.get_file_counts_by_user_in_timerange(start_ts, end_next_ts))
        
        # 모든 사용자 조회
        all_users_response = Users.get_users()
        users_data: list[dict] = []

        # 필터 값 정리 (공백 제거)
        team_filter_clean = _clean_str(team_filter)
        hq_filter_clean = _clean_str(hq_filter)
        division_filter_clean = _clean_str(division_filter)

        for user in all_users_response["users"]:
            team = user.info.get("team", "") if user.info else ""
            hq = user.info.get("headquarters", "") if user.info else ""
            division = user.info.get("division", "") if user.info else ""

            # 저장된 값도 정리하여 비교
            team_clean = _clean_str(team) or ""
            hq_clean = _clean_str(hq) or ""
            division_clean = _clean_str(division) or ""

            # 필터 적용 (정확히 일치해야 함)
            if team_filter_clean and team_clean != team_filter_clean:
                continue
            if hq_filter_clean and hq_clean != hq_filter_clean:
                continue
            if division_filter_clean and division_clean != division_filter_clean:
                continue

            # 압축된 파일 업로드 수 조회
            _, compacted_uploads = _sum_compacted_usage_from_info(
                user.info if user.info else {}, start_ts, end_next_ts
            )

            users_data.append(
                {
                    "user_id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "team": team,
                    "headquarters": hq,
                    "division": division,
                    "position": user.info.get("position", "") if user.info else "",
                    "message_count": int(msg_counts.get(user.id, 0) or 0),
                    "file_upload_count": compacted_uploads + int(file_counts.get(user.id, 0) or 0),
                }
            )

        # 메시지수 → 파일수 → 이름 순으로 정렬
        users_data.sort(key=lambda x: (-x["message_count"], -x["file_upload_count"], x["name"]))
        return users_data
    except Exception as e:
        log.error(f"Error computing usage data: {e}")
        return []


@router.post("/stats/usage")
async def get_usage_stats(
    form_data: DateRangeForm,
    user=Depends(get_admin_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
):
    try:
        start_ts, end_next_ts, norm = _parse_date_range(form_data)
        users_data = _compute_usage_users_data(
            start_ts,
            end_next_ts,
            team_filter=_clean_str(form_data.team),
            hq_filter=_clean_str(form_data.headquarters),
            division_filter=_clean_str(form_data.division),
        )

        total = len(users_data)
        size = max(1, size)
        page = max(1, page)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paged = users_data[start_idx:end_idx]

        return {
            "start_date": norm.get("start_date"),
            "start_time": norm.get("start_time"),
            "end_date": norm.get("end_date"),
            "end_time": norm.get("end_time"),
            "team": _clean_str(form_data.team),
            "headquarters": _clean_str(form_data.headquarters),
            "division": _clean_str(form_data.division),
            "total": total,
            "page": page,
            "size": size,
            "users": paged,
        }
    except Exception as e:
        log.error(f"Error getting usage stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/stats/usage/export")
async def export_usage_stats_excel(
    form_data: DateRangeForm,
    user=Depends(get_admin_user),
):
    try:
        # Export all filtered results (no pagination)
        start_ts, end_next_ts, norm = _parse_date_range(form_data)
        users = _compute_usage_users_data(
            start_ts,
            end_next_ts,
            team_filter=_clean_str(form_data.team),
            hq_filter=_clean_str(form_data.headquarters),
            division_filter=_clean_str(form_data.division),
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("통계")

        header = ["이름", "이메일", "소속", "본부", "부문", "직급(직책)", "사용량", "파일 업로드 수"]
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#F2F2F2"})

        for col, h in enumerate(header):
            worksheet.write(0, col, h, header_fmt)

        for row_idx, u in enumerate(users, start=1):
            worksheet.write(row_idx, 0, u.get("name", ""))
            worksheet.write(row_idx, 1, u.get("email", ""))
            worksheet.write(row_idx, 2, u.get("team", ""))
            worksheet.write(row_idx, 3, u.get("headquarters", ""))
            worksheet.write(row_idx, 4, u.get("division", ""))
            worksheet.write(row_idx, 5, u.get("position", ""))
            worksheet.write_number(row_idx, 6, int(u.get("message_count", 0) or 0))
            worksheet.write_number(row_idx, 7, int(u.get("file_upload_count", 0) or 0))

        worksheet.autofilter(0, 0, max(len(users), 1), len(header) - 1)
        worksheet.freeze_panes(1, 0)

        workbook.close()
        output.seek(0)

        filename = f"{norm.get('start_date')}_{norm.get('end_date')}_statistics.xlsx"
        
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    except Exception as e:
        log.error(f"Error exporting usage stats: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


class FileStorageStatsForm(BaseModel):
    pass  # No parameters needed, just current storage status


class DataCleanupForm(BaseModel):
    cutoff_date: str  # YYYY-MM-DD
    cutoff_time: str = "23:59:59"  # HH:MM:SS
    delete_files: bool = True  # 업로드된 파일 삭제 여부
    delete_vectors: bool = True  # 벡터 데이터 삭제 여부
    delete_db_records: bool = True  # DB 레코드 삭제 여부
    dry_run: bool = False  # 실제 삭제하지 않고 미리보기만
    confirm_password: str | None = None  # 삭제 실행 시 재인증용 비밀번호


def _get_directory_size(directory_path: Path) -> int:
    """디렉토리의 총 크기를 바이트 단위로 계산"""
    total_size = 0
    try:
        if directory_path.exists() and directory_path.is_dir():
            for dirpath, _, filenames in os.walk(directory_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        continue
    except Exception as e:
        log.error(f"Error calculating directory size for {directory_path}: {e}")
    return total_size





def _format_bytes(bytes_size: int) -> str:
    """바이트를 사람이 읽기 쉬운 형태로 변환"""
    if bytes_size == 0:
        return "0 B"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def _count_files_recursive(directory_path: Path) -> int:
    count = 0
    try:
        if directory_path.exists() and directory_path.is_dir():
            for _, _, filenames in os.walk(directory_path):
                count += len(filenames)
    except Exception as e:
        log.error(f"Error counting files for {directory_path}: {e}")
    return count


def _get_top_files_by_size(directory_path: Path, limit: int = 5) -> list[dict]:
    """디렉토리에서 크기가 큰 파일 상위 N개 조회"""
    files = []
    try:
        if directory_path.exists() and directory_path.is_dir():
            for root, _, filenames in os.walk(directory_path):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    try:
                        size = os.path.getsize(filepath)
                        relative_path = os.path.relpath(filepath, directory_path)
                        files.append({
                            "name": filename,
                            "path": relative_path,
                            "size": size,
                            "size_formatted": _format_bytes(size)
                        })
                    except (OSError, FileNotFoundError):
                        continue

            # 크기 기준 내림차순 정렬 후 상위 limit개 반환
            files.sort(key=lambda x: x["size"], reverse=True)
            return files[:limit]
    except Exception as e:
        log.error(f"Error getting top files for {directory_path}: {e}")
    return []


def _get_webui_db_size() -> dict:
    """webui.db 파일 크기 조회"""
    try:
        possible_paths = [
            # DATA_DIR에서 webui.db 찾기 
            os.path.join(DATA_DIR, "webui.db"),
            # 기존 경로들 (fallback)
            os.path.join(os.getcwd(), "webui.db"),
            os.path.join(os.getcwd(), "backend", "webui.db"),
            os.path.join(os.path.dirname(__file__), "..", "..", "webui.db"),
            os.environ.get("DATABASE_URL", "").replace("sqlite:///", "") if os.environ.get("DATABASE_URL", "").startswith("sqlite:///") else None
        ]

        # None 값 제거
        possible_paths = [p for p in possible_paths if p]

        for db_path in possible_paths:
            if os.path.isfile(db_path):
                size = os.path.getsize(db_path)
                return {
                    "path": db_path,
                    "size": size,
                    "size_formatted": _format_bytes(size),
                    "exists": True
                }

        return {
            "path": f"{DATA_DIR}/webui.db (not found)",
            "size": 0,
            "size_formatted": "0 B",
            "exists": False
        }
    except Exception as e:
        log.error(f"Error getting webui.db size: {e}")
        return {
            "path": "webui.db",
            "size": 0,
            "size_formatted": "0 B",
            "exists": False,
            "error": str(e)
        }










def _compact_usage_to_users(start_ts: int, end_ts: int) -> dict:
    """
    삭제 전에 파일 업로드 데이터를 사용자별·일자별로 집계하여
    user.info.usage.daily['YYYY-MM-DD']에 합산합니다.
    """
    try:
        # 삭제될 파일들의 업로드 수를 집계
        files_to_delete = Files.get_files_by_timestamp(end_ts)
        file_ids = [f.id for f in (files_to_delete or [])]
        file_rows = Files.get_file_counts_by_user_and_date_for_file_ids(file_ids) if file_ids else []

        # 사용자별·일자별 집계
        uploads_map: dict[tuple[str, str], int] = {}

        for uid, day, cnt in (file_rows or []):
            uploads_map[(uid, day)] = int(cnt)

        affected_users = set([uid for uid, _, _ in (file_rows or [])])

        updated_users = 0
        updated_days = 0

        for user_id in affected_users:
            user = Users.get_user_by_id(user_id)
            if not user:
                continue
            info = user.info or {}
            usage = info.get("usage", {}) or {}
            daily = usage.get("daily", {}) or {}

            # 해당 사용자의 모든 일자 수집
            days = set([day for (uid, day), _ in uploads_map.items() if uid == user_id])

            changed = False
            for day in sorted(days):
                existing = daily.get(day)
                if existing is None:
                    daily[day] = {
                        "prompts": 0,  # 호환성 유지용
                        "uploads": int(uploads_map.get((user_id, day), 0) or 0),
                    }
                    updated_days += 1
                    changed = True
                else:
                    # 기존값에 새 집계값 합산
                    if not isinstance(existing, dict):
                        existing = {}
                    existing_uploads = int(existing.get("uploads", 0) or 0)
                    add_uploads = int(uploads_map.get((user_id, day), 0) or 0)
                    new_uploads = existing_uploads + add_uploads
                    if new_uploads != existing_uploads:
                        existing["uploads"] = new_uploads
                        changed = True
                    daily[day] = existing

            if changed:
                usage["daily"] = daily
                info["usage"] = usage
                Users.update_user_by_id(user_id, {"info": info})
                updated_users += 1

        return {
            "updated_users": updated_users,
            "updated_days": updated_days,
            "start": start_ts,
            "end": end_ts,
        }
    except Exception as e:
        log.error(f"Error compacting usage to users: {e}")
        return {"updated_users": 0, "updated_days": 0, "error": str(e)}


@router.post("/stats/file-storage")
async def get_file_storage_stats(
    form_data: FileStorageStatsForm,
    user=Depends(get_admin_user),
):
    """현재 파일 스토리지 현황 조회 (기간별 분석 제외)"""
    try:
        # 업로드 디렉토리 통계
        upload_dir = Path(UPLOAD_DIR)
        upload_total_size = _get_directory_size(upload_dir)
        upload_total_count = _count_files_recursive(upload_dir)
        top_files = _get_top_files_by_size(upload_dir, 5)

        # VectorStorage 모델을 통한 벡터 컬렉션 정보 조회
        vector_collections_info = VectorStorage.get_vector_collections_info()

        # webui.db 크기 조회
        webui_db_info = _get_webui_db_size()

        return {
            "uploads": {
                "total_size": upload_total_size,
                "total_size_formatted": _format_bytes(upload_total_size),
                "total_count": upload_total_count,
                "directory_path": str(upload_dir),
                "top_files": top_files,
            },
            "vector_db": {
                "collection_count": vector_collections_info["collection_folders_count"],
                "total_size": vector_collections_info["total_vector_size"],
                "total_size_formatted": vector_collections_info["total_vector_size_formatted"],
            },
            "database": {
                "webui_db": webui_db_info,
            }
        }

    except Exception as e:
        log.error(f"Error getting file storage stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _delete_files_with_storage_cleanup(cutoff_timestamp: int, dry_run: bool = False) -> dict:
    """파일과 Storage 정리를 포함한 통합 삭제"""
    try:
        # Files 모델을 통한 DB 삭제
        db_result = Files.delete_files_by_timestamp(cutoff_timestamp) if not dry_run else {"deleted_files": Files.get_files_by_timestamp(cutoff_timestamp), "failed_files": [], "total_files_deleted": len(Files.get_files_by_timestamp(cutoff_timestamp))}

        deleted_files_with_storage = []
        failed_files = db_result.get("failed_files", [])
        total_size_deleted = 0
        kb_vector_deleted = 0
        file_collections_deleted = 0

        # Knowledge 목록 캐시
        knowledge_bases = Knowledges.get_knowledge_bases()
        knowledge_ids = [kb.id for kb in knowledge_bases]

        # Storage / Vector / Knowledge 정리
        for file_info in db_result.get("deleted_files", []):
            try:
                file_dict = file_info if isinstance(file_info, dict) else {
                    "id": file_info.id,
                    "filename": file_info.filename,
                    "path": file_info.path,
                    "created_at": file_info.created_at
                }

                if not dry_run:
                    # Vector: 지식베이스 컬렉션에서 해당 file_id 데이터 제거
                    for kb_id in knowledge_ids:
                        try:
                            VECTOR_DB_CLIENT.delete(collection_name=kb_id, filter={"file_id": file_dict["id"]})
                            kb_vector_deleted += 1
                        except Exception:
                            pass

                    # Vector: 파일 전용 컬렉션 제거
                    try:
                        coll = f"file-{file_dict['id']}"
                        if VECTOR_DB_CLIENT.has_collection(collection_name=coll):
                            VECTOR_DB_CLIENT.delete_collection(collection_name=coll)
                            file_collections_deleted += 1
                    except Exception:
                        pass

                    # 물리적 파일 삭제
                    if file_dict.get("path") and os.path.exists(file_dict["path"]):
                        file_size = os.path.getsize(file_dict["path"])
                        os.remove(file_dict["path"])
                        total_size_deleted += file_size

                    # Storage provider 삭제
                    try:
                        Storage.delete_file(file_dict.get("path") or file_dict.get("filename", ""))
                    except Exception as storage_e:
                        log.debug(f"Storage deletion failed for {file_dict.get('filename', 'unknown')}: {storage_e}")

                    # Knowledge 레코드 정리
                    Knowledges.cleanup_knowledge_by_file_ids([file_dict["id"]])

                deleted_files_with_storage.append(file_dict)

            except Exception as e:
                log.error(f"Failed to delete file with storage cleanup: {e}")
                failed_files.append({
                    "id": file_dict.get("id", "unknown"),
                    "filename": file_dict.get("filename", "unknown"),
                    "error": str(e)
                })

        return {
            "deleted_files": deleted_files_with_storage,
            "failed_files": failed_files,
            "total_files_deleted": len(deleted_files_with_storage),
            "total_size_deleted": total_size_deleted,
            "total_size_deleted_formatted": _format_bytes(total_size_deleted),
            "vector_cleanup": {
                "kb_deletes": kb_vector_deleted,
                "file_collections_deleted": file_collections_deleted,
            }
        }

    except Exception as e:
        log.error(f"Error in _delete_files_with_storage_cleanup: {e}")
        return {
            "deleted_files": [],
            "failed_files": [],
            "total_files_deleted": 0,
            "total_size_deleted": 0,
            "total_size_deleted_formatted": "0 B",
            "error": str(e)
        }


@router.post("/cleanup/preview")
async def preview_data_cleanup(
    form_data: DataCleanupForm,
    user=Depends(get_admin_user),
):
    """데이터 삭제 미리보기"""
    try:
        # 날짜 및 시간 파싱
        cutoff_datetime = datetime.strptime(f"{form_data.cutoff_date} {form_data.cutoff_time}", "%Y-%m-%d %H:%M:%S")
        cutoff_timestamp = int(cutoff_datetime.timestamp())

        preview_result = {
            "cutoff_datetime": cutoff_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "cutoff_timestamp": cutoff_timestamp,
        }

        # 삭제 대상 파일 미리보기 - Files 모델 활용
        if form_data.delete_files:
            files_to_delete = Files.get_files_by_timestamp(cutoff_timestamp)
            files_list = []
            total_files_size = 0

            for file in files_to_delete[:10]:  # 처음 10개만 미리보기
                file_size = os.path.getsize(file.path) if file.path and os.path.exists(file.path) else 0
                total_files_size += file_size
                files_list.append({
                    "id": file.id,
                    "filename": file.filename,
                    "path": file.path,
                    "created_at": file.created_at,
                    "size": file_size
                })

            preview_result["files"] = {
                "count": len(files_to_delete),
                "total_size": total_files_size,
                "total_size_formatted": _format_bytes(total_files_size),
                "files": files_list
            }

        # 삭제 대상 벡터 컬렉션 미리보기 - VectorStorage 모델 활용
        if form_data.delete_vectors:
            collections_to_delete = VectorStorage.get_vector_collections_by_timestamp(cutoff_timestamp)
            total_collections_size = sum(c["size"] for c in collections_to_delete)

            preview_result["vector_collections"] = {
                "count": len(collections_to_delete),
                "total_size": total_collections_size,
                "total_size_formatted": _format_bytes(total_collections_size),
                "collections": collections_to_delete
            }


        return preview_result

    except Exception as e:
        log.error(f"Error in preview_data_cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/cleanup/execute")
async def execute_data_cleanup(
    form_data: DataCleanupForm,
    user=Depends(get_admin_user),
):
    """데이터 삭제 실행"""
    try:
        # 날짜 및 시간 파싱
        cutoff_datetime = datetime.strptime(f"{form_data.cutoff_date} {form_data.cutoff_time}", "%Y-%m-%d %H:%M:%S")
        cutoff_timestamp = int(cutoff_datetime.timestamp())

        execution_result = {
            "cutoff_datetime": cutoff_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "cutoff_timestamp": cutoff_timestamp,
            "dry_run": form_data.dry_run,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 0) 재인증(비밀번호) + 삭제 전에 사용자별 집계값을 user.info에 반영 (0 ~ cutoff)
        if not form_data.dry_run:
            if not form_data.confirm_password or not form_data.confirm_password.strip():
                raise HTTPException(status_code=400, detail="비밀번호를 입력하세요.")
            if not Auths.authenticate_user(user.email, form_data.confirm_password):
                raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

            compaction = _compact_usage_to_users(0, cutoff_timestamp)
            execution_result["compaction"] = compaction

        # 파일 삭제 - 통합 삭제 함수 활용
        if form_data.delete_files:
            files_result = _delete_files_with_storage_cleanup(cutoff_timestamp, form_data.dry_run)
            execution_result["files"] = files_result

        # 벡터 컬렉션 삭제 - VectorStorage 모델 활용
        if form_data.delete_vectors:
            vectors_result = VectorStorage.delete_vector_collections_by_timestamp(cutoff_timestamp, form_data.dry_run)
            execution_result["vector_collections"] = vectors_result


        execution_result["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 간단 검증: 삭제 후 동일 기준으로 남은 개수 확인 (dry_run이 아닐 때)
        if not form_data.dry_run:
            verify = {}
            try:
                if form_data.delete_files:
                    remaining_files = Files.get_files_by_timestamp(cutoff_timestamp)
                    verify["files_remaining_before_cutoff"] = len(remaining_files)
            except Exception:
                pass
            try:
                if form_data.delete_vectors:
                    remaining_vectors = VectorStorage.get_vector_collections_by_timestamp(cutoff_timestamp)
                    verify["vector_collections_remaining_before_cutoff"] = len(remaining_vectors)
            except Exception:
                pass
            execution_result["verify"] = verify

        return execution_result

    except Exception as e:
        log.error(f"Error in execute_data_cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup execution failed: {str(e)}")
