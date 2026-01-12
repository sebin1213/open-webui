import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, List

from open_webui.config import CHROMA_DATA_PATH
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


class VectorStorageTable:
    """벡터 스토리지 관리 클래스"""

    def _get_directory_size(self, path: Path) -> int:
        """디렉토리 크기 계산"""
        total_size = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception as e:
            log.debug(f"Error calculating directory size for {path}: {e}")
        return total_size

    def _format_bytes(self, bytes_size: int) -> str:
        """바이트 크기를 읽기 쉬운 형태로 변환"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

    def get_vector_collections_info(self) -> Dict:
        """벡터 컬렉션 정보 조회"""
        try:
            vector_base_path = Path(CHROMA_DATA_PATH)
            if not vector_base_path.exists():
                return {
                    "total_vector_size": 0,
                    "total_vector_size_formatted": "0 B",
                    "chroma_db_size": 0,
                    "chroma_db_size_formatted": "0 B",
                    "collection_folders": [],
                    "collection_folders_count": 0,
                    "actual_collections_count": 0,
                    "api_collections_count": 0,
                    "api_collections": [],
                    "database_files": [],
                    "base_path": str(vector_base_path)
                }

            total_vector_size = 0
            chroma_db_size = 0
            collection_folders = []
            database_files = []
            actual_collections_count = 0

            # chroma.sqlite3 파일 크기 확인
            chroma_db_file = vector_base_path / "chroma.sqlite3"
            if chroma_db_file.exists():
                chroma_db_size = chroma_db_file.stat().st_size

            # 디렉토리 내용 분석
            for item in vector_base_path.iterdir():
                if item.name == "chroma.sqlite3":
                    database_files.append({
                        "name": item.name,
                        "type": "database",
                        "size": chroma_db_size,
                        "size_formatted": self._format_bytes(chroma_db_size),
                        "path": str(item)
                    })
                elif item.is_dir():
                    # 폴더인 경우 (실제 벡터 데이터 컬렉션)
                    folder_size = self._get_directory_size(item)
                    total_vector_size += folder_size
                    actual_collections_count += 1

                    # 폴더 내부 파일 구조 분석
                    folder_files = []
                    if item.exists():
                        for sub_item in item.iterdir():
                            if sub_item.is_file():
                                file_size = sub_item.stat().st_size if sub_item.exists() else 0
                                folder_files.append({
                                    "name": sub_item.name,
                                    "size": file_size,
                                    "size_formatted": self._format_bytes(file_size)
                                })

                    collection_folders.append({
                        "name": item.name,
                        "size": folder_size,
                        "size_formatted": self._format_bytes(folder_size),
                        "path": str(item),
                        "files": folder_files,
                        "files_count": len(folder_files),
                        "created_at": int(item.stat().st_ctime) if item.exists() else 0
                    })
                elif item.is_file() and item.name != "chroma.sqlite3":
                    # 기타 파일들
                    file_size = item.stat().st_size if item.exists() else 0
                    database_files.append({
                        "name": item.name,
                        "type": "file",
                        "size": file_size,
                        "size_formatted": self._format_bytes(file_size),
                        "path": str(item)
                    })

            # ChromaDB API를 통한 컬렉션 조회 시도
            api_collections_count = 0
            api_collections = []
            try:
                if VECTOR_DB_CLIENT:
                    collections = VECTOR_DB_CLIENT.client.list_collections()
                    api_collections_count = len(collections)

                    for collection in collections:
                        try:
                            collection_obj = VECTOR_DB_CLIENT.client.get_collection(collection.name)
                            count = collection_obj.count() if hasattr(collection_obj, 'count') else 0

                            api_collections.append({
                                "name": collection.name,
                                "id": collection.id if hasattr(collection, 'id') else "unknown",
                                "metadata": collection.metadata if hasattr(collection, 'metadata') else {},
                                "count": count
                            })
                        except Exception as e:
                            log.debug(f"Error getting collection info for {collection.name}: {e}")
                            api_collections.append({
                                "name": collection.name,
                                "id": "unknown",
                                "metadata": {},
                                "count": 0
                            })

            except Exception as e:
                log.debug(f"Error accessing ChromaDB API: {e}")

            return {
                "total_vector_size": total_vector_size,
                "total_vector_size_formatted": self._format_bytes(total_vector_size),
                "chroma_db_size": chroma_db_size,
                "chroma_db_size_formatted": self._format_bytes(chroma_db_size),
                "collection_folders": collection_folders,
                "collection_folders_count": len(collection_folders),
                "actual_collections_count": actual_collections_count,
                "api_collections_count": api_collections_count,
                "api_collections": api_collections,
                "database_files": database_files,
                "base_path": str(vector_base_path)
            }

        except Exception as e:
            log.error(f"Error getting vector collections info: {e}")
            return {
                "total_vector_size": 0,
                "total_vector_size_formatted": "0 B",
                "chroma_db_size": 0,
                "chroma_db_size_formatted": "0 B",
                "collection_folders": [],
                "collection_folders_count": 0,
                "actual_collections_count": 0,
                "api_collections_count": 0,
                "api_collections": [],
                "database_files": [],
                "base_path": str(CHROMA_DATA_PATH) if CHROMA_DATA_PATH else "N/A"
            }

    def get_vector_collections_by_timestamp(self, cutoff_timestamp: int) -> List[Dict]:
        """타임스탬프 기준으로 삭제 대상 벡터 컬렉션 조회"""
        try:
            collections_info = self.get_vector_collections_info()
            collections_to_delete = []

            for collection_folder in collections_info["collection_folders"]:
                if collection_folder["created_at"] < cutoff_timestamp:
                    collections_to_delete.append(collection_folder)

            return collections_to_delete
        except Exception as e:
            log.error(f"Error getting vector collections by timestamp: {e}")
            return []

    def delete_vector_collections_by_timestamp(self, cutoff_timestamp: int, dry_run: bool = False) -> Dict:
        """타임스탬프 기준으로 벡터 컬렉션 삭제"""
        deleted_collections = []
        failed_collections = []
        total_size_deleted = 0

        try:
            collections_to_delete = self.get_vector_collections_by_timestamp(cutoff_timestamp)

            for collection_info in collections_to_delete:
                try:
                    if not dry_run:
                        # ChromaDB API를 통한 컬렉션 삭제 시도
                        try:
                            if VECTOR_DB_CLIENT and hasattr(VECTOR_DB_CLIENT, 'delete_collection'):
                                VECTOR_DB_CLIENT.delete_collection(collection_info["name"])
                        except Exception as api_e:
                            log.debug(f"ChromaDB API deletion failed for {collection_info['name']}: {api_e}")

                        # 물리적 폴더 삭제
                        collection_path = Path(collection_info["path"])
                        if collection_path.exists():
                            shutil.rmtree(collection_path)

                    deleted_collections.append(collection_info)
                    total_size_deleted += collection_info["size"]

                except Exception as e:
                    log.error(f"Failed to delete collection {collection_info['name']}: {e}")
                    failed_collections.append({
                        **collection_info,
                        "error": str(e)
                    })

            return {
                "deleted_collections": deleted_collections,
                "failed_collections": failed_collections,
                "total_collections_deleted": len(deleted_collections),
                "total_size_deleted": total_size_deleted,
                "total_size_deleted_formatted": self._format_bytes(total_size_deleted)
            }

        except Exception as e:
            log.error(f"Error in delete_vector_collections_by_timestamp: {e}")
            return {
                "deleted_collections": [],
                "failed_collections": [],
                "total_collections_deleted": 0,
                "total_size_deleted": 0,
                "total_size_deleted_formatted": "0 B",
                "error": str(e)
            }


VectorStorage = VectorStorageTable()