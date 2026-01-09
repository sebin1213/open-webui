import logging
import time
from typing import Optional

from open_webui.internal.db import Base, JSONField, get_db
from open_webui.env import SRC_LOG_LEVELS
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, JSON, func, and_, text

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

####################
# Files DB Schema
####################


class File(Base):
    __tablename__ = "file"
    id = Column(String, primary_key=True)
    user_id = Column(String)
    hash = Column(Text, nullable=True)

    filename = Column(Text)
    path = Column(Text, nullable=True)

    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    access_control = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class FileModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    hash: Optional[str] = None

    filename: str
    path: Optional[str] = None

    data: Optional[dict] = None
    meta: Optional[dict] = None

    access_control: Optional[dict] = None

    created_at: Optional[int]  # timestamp in epoch
    updated_at: Optional[int]  # timestamp in epoch


####################
# Forms
####################


class FileMeta(BaseModel):
    name: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class FileModelResponse(BaseModel):
    id: str
    user_id: str
    hash: Optional[str] = None

    filename: str
    data: Optional[dict] = None
    meta: FileMeta

    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch

    model_config = ConfigDict(extra="allow")


class FileMetadataResponse(BaseModel):
    id: str
    hash: Optional[str] = None
    meta: dict
    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch


class FileForm(BaseModel):
    id: str
    hash: Optional[str] = None
    filename: str
    path: str
    data: dict = {}
    meta: dict = {}
    access_control: Optional[dict] = None


class FilesTable:
    def get_files_older_than(self, cutoff_ts: int, limit: Optional[int] = None) -> list[FileModel]:
        """
        Return files with created_at < cutoff_ts. Optional limit.
        """
        with get_db() as db:
            query = db.query(File).filter(File.created_at < cutoff_ts).order_by(File.created_at.asc())
            if limit and isinstance(limit, int) and limit > 0:
                query = query.limit(limit)
            rows = query.all()
            return [FileModel.model_validate(row) for row in rows]

    def get_file_counts_by_user_in_timerange(self, start_ts: int, end_ts: int) -> list[tuple[str, int]]:
        """
        Returns a list of (user_id, file_count) where files are counted by
        File.created_at within [start_ts, end_ts). Only DB querying here.
        """
        results: list[tuple[str, int]] = []
        with get_db() as db:
            rows = (
                db.query(File.user_id, func.count(File.id))
                .filter(and_(File.created_at >= start_ts, File.created_at < end_ts))
                .group_by(File.user_id)
                .all()
            )
            for row in rows:
                uid = row[0] if not hasattr(row, "user_id") else row.user_id
                cnt = int(row[1])
                results.append((uid, cnt))
        return results

    def get_file_counts_by_user_and_date_in_timerange(self, start_ts: int, end_ts: int) -> list[tuple[str, str, int]]:
        """
        Returns a list of (user_id, date_str, count) where date_str is 'YYYY-MM-DD'.
        Counts files with created_at within [start_ts, end_ts).
        """
        out: list[tuple[str, str, int]] = []
        with get_db() as db:
            dialect_name = db.bind.dialect.name if hasattr(db, "bind") else ""
            if dialect_name == "sqlite":
                query = text(
                    """
                    SELECT f.user_id AS user_id,
                           date(f.created_at, 'unixepoch') AS day,
                           COUNT(*) AS cnt
                    FROM file f
                    WHERE f.created_at >= :start_ts
                      AND f.created_at < :end_ts
                    GROUP BY f.user_id, day
                    ORDER BY day ASC
                    """
                )
                rows = db.execute(query, {"start_ts": start_ts, "end_ts": end_ts}).fetchall()
                out = [(row[0], row[1], int(row[2])) for row in rows]
            elif dialect_name == "postgresql":
                query = text(
                    """
                    SELECT f.user_id AS user_id,
                           to_timestamp(f.created_at)::date AS day,
                           COUNT(*) AS cnt
                    FROM file f
                    WHERE f.created_at >= :start_ts
                      AND f.created_at < :end_ts
                    GROUP BY f.user_id, day
                    ORDER BY day ASC
                    """
                )
                rows = db.execute(query, {"start_ts": start_ts, "end_ts": end_ts}).fetchall()
                out = [(row[0], str(row[1]), int(row[2])) for row in rows]
            else:
                # Fallback: group in Python (may be inefficient for large datasets)
                rows = db.query(File.user_id, File.created_at).filter(
                    and_(File.created_at >= start_ts, File.created_at < end_ts)
                ).all()
                tmp: dict[tuple[str, str], int] = {}
                for uid, ts in rows:
                    try:
                        day_str = time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
                    except Exception:
                        continue
                    key = (uid, day_str)
                    tmp[key] = tmp.get(key, 0) + 1
                out = [(k[0], k[1], v) for k, v in tmp.items()]
        return out

    def get_file_counts_by_user_and_date_for_file_ids(self, file_ids: list[str], chunk_size: int = 1000) -> list[tuple[str, str, int]]:
        """
        Returns (user_id, date_str, count) grouped for the given file IDs only.
        date_str is 'YYYY-MM-DD'.
        """
        if not file_ids:
            return []
        results: dict[tuple[str, str], int] = {}
        with get_db() as db:
            dialect = db.bind.dialect.name if hasattr(db, "bind") else ""
            for i in range(0, len(file_ids), chunk_size):
                subset = file_ids[i:i + chunk_size]
                if not subset:
                    continue
                if dialect == "sqlite":
                    params = {f"id_{idx}": fid for idx, fid in enumerate(subset)}
                    placeholders = ",".join([f":id_{idx}" for idx in range(len(subset))])
                    query = text(
                        f"""
                        SELECT f.user_id AS user_id,
                               date(f.created_at, 'unixepoch') AS day,
                               COUNT(*) AS cnt
                        FROM file f
                        WHERE f.id IN ({placeholders})
                        GROUP BY f.user_id, day
                        """
                    )
                    rows = db.execute(query, params).fetchall()
                    for row in rows:
                        key = (row[0], row[1])
                        results[key] = results.get(key, 0) + int(row[2])
                elif dialect == "postgresql":
                    query = text(
                        """
                        SELECT f.user_id AS user_id,
                               to_timestamp(f.created_at)::date AS day,
                               COUNT(*) AS cnt
                        FROM file f
                        WHERE f.id = ANY(:ids)
                        GROUP BY f.user_id, day
                        """
                    )
                    rows = db.execute(query, {"ids": subset}).fetchall()
                    for row in rows:
                        key = (row[0], str(row[1]))
                        results[key] = results.get(key, 0) + int(row[2])
                else:
                    # Python fallback
                    rows = db.query(File.user_id, File.created_at, File.id).filter(File.id.in_(subset)).all()
                    for uid, ts, _ in rows:
                        try:
                            day = time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
                        except Exception:
                            continue
                        key = (uid, day)
                        results[key] = results.get(key, 0) + 1
        return [(k[0], k[1], v) for k, v in results.items()]
    
    def insert_new_file(self, user_id: str, form_data: FileForm) -> Optional[FileModel]:
        with get_db() as db:
            file = FileModel(
                **{
                    **form_data.model_dump(),
                    "user_id": user_id,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            try:
                result = File(**file.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return FileModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception(f"Error inserting a new file: {e}")
                return None

    def get_file_by_id(self, id: str) -> Optional[FileModel]:
        with get_db() as db:
            try:
                file = db.get(File, id)
                return FileModel.model_validate(file)
            except Exception:
                return None

    def get_file_by_id_and_user_id(self, id: str, user_id: str) -> Optional[FileModel]:
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id, user_id=user_id).first()
                if file:
                    return FileModel.model_validate(file)
                else:
                    return None
            except Exception:
                return None

    def get_file_metadata_by_id(self, id: str) -> Optional[FileMetadataResponse]:
        with get_db() as db:
            try:
                file = db.get(File, id)
                return FileMetadataResponse(
                    id=file.id,
                    hash=file.hash,
                    meta=file.meta,
                    created_at=file.created_at,
                    updated_at=file.updated_at,
                )
            except Exception:
                return None

    def get_files(self) -> list[FileModel]:
        with get_db() as db:
            return [FileModel.model_validate(file) for file in db.query(File).all()]

    def check_access_by_user_id(self, id, user_id, permission="write") -> bool:
        file = self.get_file_by_id(id)
        if not file:
            return False
        if file.user_id == user_id:
            return True
        # Implement additional access control logic here as needed
        return False

    def get_files_by_ids(self, ids: list[str]) -> list[FileModel]:
        with get_db() as db:
            return [
                FileModel.model_validate(file)
                for file in db.query(File)
                .filter(File.id.in_(ids))
                .order_by(File.updated_at.desc())
                .all()
            ]

    def get_file_metadatas_by_ids(self, ids: list[str]) -> list[FileMetadataResponse]:
        with get_db() as db:
            return [
                FileMetadataResponse(
                    id=file.id,
                    hash=file.hash,
                    meta=file.meta,
                    created_at=file.created_at,
                    updated_at=file.updated_at,
                )
                for file in db.query(
                    File.id, File.hash, File.meta, File.created_at, File.updated_at
                )
                .filter(File.id.in_(ids))
                .order_by(File.updated_at.desc())
                .all()
            ]

    def get_files_by_user_id(self, user_id: str) -> list[FileModel]:
        with get_db() as db:
            return [
                FileModel.model_validate(file)
                for file in db.query(File).filter_by(user_id=user_id).all()
            ]

    def update_file_hash_by_id(self, id: str, hash: str) -> Optional[FileModel]:
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id).first()
                file.hash = hash
                db.commit()

                return FileModel.model_validate(file)
            except Exception:
                return None

    def update_file_data_by_id(self, id: str, data: dict) -> Optional[FileModel]:
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id).first()
                file.data = {**(file.data if file.data else {}), **data}
                db.commit()
                return FileModel.model_validate(file)
            except Exception as e:

                return None

    def update_file_metadata_by_id(self, id: str, meta: dict) -> Optional[FileModel]:
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id).first()
                file.meta = {**(file.meta if file.meta else {}), **meta}
                db.commit()
                return FileModel.model_validate(file)
            except Exception:
                return None

    def delete_file_by_id(self, id: str) -> bool:
        with get_db() as db:
            try:
                db.query(File).filter_by(id=id).delete()
                db.commit()

                return True
            except Exception:
                return False

    def delete_all_files(self) -> bool:
        with get_db() as db:
            try:
                db.query(File).delete()
                db.commit()

                return True
            except Exception:
                return False

    def get_files_by_timestamp(self, cutoff_timestamp: int) -> list[FileModel]:
        """타임스탬프 기준으로 파일 조회"""
        with get_db() as db:
            try:
                files = db.query(File).filter(File.created_at < cutoff_timestamp).all()
                return [FileModel.model_validate(file) for file in files]
            except Exception as e:
                log.exception(f"Error getting files by timestamp: {e}")
                return []

    def delete_files_by_timestamp(self, cutoff_timestamp: int) -> dict:
        """타임스탬프 기준으로 파일 삭제 (DB 레코드만)"""
        deleted_files = []
        failed_files = []

        try:
            files_to_delete = self.get_files_by_timestamp(cutoff_timestamp)

            for file in files_to_delete:
                try:
                    success = self.delete_file_by_id(file.id)
                    if success:
                        deleted_files.append({
                            "id": file.id,
                            "filename": file.filename,
                            "path": file.path,
                            "created_at": file.created_at
                        })
                    else:
                        failed_files.append({
                            "id": file.id,
                            "filename": file.filename,
                            "error": "Database deletion failed"
                        })
                except Exception as e:
                    failed_files.append({
                        "id": file.id,
                        "filename": file.filename,
                        "error": str(e)
                    })

            return {
                "deleted_files": deleted_files,
                "failed_files": failed_files,
                "total_files_deleted": len(deleted_files)
            }

        except Exception as e:
            log.error(f"Error in delete_files_by_timestamp: {e}")
            return {
                "deleted_files": [],
                "failed_files": [],
                "total_files_deleted": 0,
                "error": str(e)
            }


Files = FilesTable()
