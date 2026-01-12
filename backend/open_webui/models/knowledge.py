import json
import logging
import time
from typing import Optional
import uuid

from open_webui.internal.db import Base, get_db
from open_webui.env import SRC_LOG_LEVELS

from open_webui.models.files import FileMetadataResponse
from open_webui.models.groups import Groups
from open_webui.models.users import Users, UserResponse


from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, JSON

from open_webui.utils.access_control import has_access

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

####################
# Knowledge DB Schema
####################


class Knowledge(Base):
    __tablename__ = "knowledge"

    id = Column(Text, unique=True, primary_key=True)
    user_id = Column(Text)

    name = Column(Text)
    description = Column(Text)

    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    access_control = Column(JSON, nullable=True)  # Controls data access levels.
    # Defines access control rules for this entry.
    # - `None`: Public access, available to all users with the "user" role.
    # - `{}`: Private access, restricted exclusively to the owner.
    # - Custom permissions: Specific access control for reading and writing;
    #   Can specify group or user-level restrictions:
    #   {
    #      "read": {
    #          "group_ids": ["group_id1", "group_id2"],
    #          "user_ids":  ["user_id1", "user_id2"]
    #      },
    #      "write": {
    #          "group_ids": ["group_id1", "group_id2"],
    #          "user_ids":  ["user_id1", "user_id2"]
    #      }
    #   }

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class KnowledgeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str

    name: str
    description: str

    data: Optional[dict] = None
    meta: Optional[dict] = None

    access_control: Optional[dict] = None

    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch


####################
# Forms
####################


class KnowledgeUserModel(KnowledgeModel):
    user: Optional[UserResponse] = None


class KnowledgeResponse(KnowledgeModel):
    files: Optional[list[FileMetadataResponse | dict]] = None


class KnowledgeUserResponse(KnowledgeUserModel):
    files: Optional[list[FileMetadataResponse | dict]] = None


class KnowledgeForm(BaseModel):
    name: str
    description: str
    data: Optional[dict] = None
    access_control: Optional[dict] = None


class KnowledgeTable:
    def insert_new_knowledge(
        self, user_id: str, form_data: KnowledgeForm
    ) -> Optional[KnowledgeModel]:
        with get_db() as db:
            knowledge = KnowledgeModel(
                **{
                    **form_data.model_dump(),
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            try:
                result = Knowledge(**knowledge.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return KnowledgeModel.model_validate(result)
                else:
                    return None
            except Exception:
                return None

    def get_knowledge_bases(self) -> list[KnowledgeUserModel]:
        with get_db() as db:
            all_knowledge = (
                db.query(Knowledge).order_by(Knowledge.updated_at.desc()).all()
            )

            user_ids = list(set(knowledge.user_id for knowledge in all_knowledge))

            users = Users.get_users_by_user_ids(user_ids) if user_ids else []
            users_dict = {user.id: user for user in users}

            knowledge_bases = []
            for knowledge in all_knowledge:
                user = users_dict.get(knowledge.user_id)
                knowledge_bases.append(
                    KnowledgeUserModel.model_validate(
                        {
                            **KnowledgeModel.model_validate(knowledge).model_dump(),
                            "user": user.model_dump() if user else None,
                        }
                    )
                )
            return knowledge_bases

    def check_access_by_user_id(self, id, user_id, permission="write") -> bool:
        knowledge = self.get_knowledge_by_id(id)
        if not knowledge:
            return False
        if knowledge.user_id == user_id:
            return True
        user_group_ids = {group.id for group in Groups.get_groups_by_member_id(user_id)}
        return has_access(user_id, permission, knowledge.access_control, user_group_ids)

    def get_knowledge_bases_by_user_id(
        self, user_id: str, permission: str = "write"
    ) -> list[KnowledgeUserModel]:
        knowledge_bases = self.get_knowledge_bases()
        user_group_ids = {group.id for group in Groups.get_groups_by_member_id(user_id)}
        return [
            knowledge_base
            for knowledge_base in knowledge_bases
            if knowledge_base.user_id == user_id
            or has_access(
                user_id, permission, knowledge_base.access_control, user_group_ids
            )
        ]

    def get_knowledge_by_id(self, id: str) -> Optional[KnowledgeModel]:
        try:
            with get_db() as db:
                knowledge = db.query(Knowledge).filter_by(id=id).first()
                return KnowledgeModel.model_validate(knowledge) if knowledge else None
        except Exception:
            return None

    def update_knowledge_by_id(
        self, id: str, form_data: KnowledgeForm, overwrite: bool = False
    ) -> Optional[KnowledgeModel]:
        try:
            with get_db() as db:
                knowledge = self.get_knowledge_by_id(id=id)
                db.query(Knowledge).filter_by(id=id).update(
                    {
                        **form_data.model_dump(),
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()
                return self.get_knowledge_by_id(id=id)
        except Exception as e:
            log.exception(e)
            return None

    def update_knowledge_data_by_id(
        self, id: str, data: dict
    ) -> Optional[KnowledgeModel]:
        try:
            with get_db() as db:
                knowledge = self.get_knowledge_by_id(id=id)
                db.query(Knowledge).filter_by(id=id).update(
                    {
                        "data": data,
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()
                return self.get_knowledge_by_id(id=id)
        except Exception as e:
            log.exception(e)
            return None

    def delete_knowledge_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                db.query(Knowledge).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def delete_all_knowledge(self) -> bool:
        with get_db() as db:
            try:
                db.query(Knowledge).delete()
                db.commit()

                return True
            except Exception:
                return False

    def cleanup_knowledge_by_file_ids(self, file_ids: list[str]) -> dict:
        """파일 ID 목록에 기반해 Knowledge 레코드 정리"""
        cleaned_knowledge = []
        deleted_knowledge = []
        failed_knowledge = []

        try:
            with get_db() as db:
                # 해당 파일들을 참조하는 Knowledge 레코드들 찾기
                knowledge_records = db.query(Knowledge).all()

                for knowledge in knowledge_records:
                    try:
                        if knowledge.data and "file_ids" in knowledge.data:
                            original_file_ids = knowledge.data.get("file_ids", [])

                            # 삭제된 파일 ID들 제거
                            remaining_file_ids = [fid for fid in original_file_ids if fid not in file_ids]

                            if len(remaining_file_ids) != len(original_file_ids):
                                # 변경이 있었다면
                                if not remaining_file_ids:
                                    # 모든 파일이 삭제되었으면 Knowledge 자체 삭제
                                    db.delete(knowledge)
                                    deleted_knowledge.append({
                                        "id": knowledge.id,
                                        "name": knowledge.name,
                                        "reason": "No remaining file references"
                                    })
                                else:
                                    # 일부 파일만 삭제되었으면 업데이트
                                    knowledge.data["file_ids"] = remaining_file_ids
                                    knowledge.updated_at = int(time.time())
                                    cleaned_knowledge.append({
                                        "id": knowledge.id,
                                        "name": knowledge.name,
                                        "removed_files": len(original_file_ids) - len(remaining_file_ids),
                                        "remaining_files": len(remaining_file_ids)
                                    })
                    except Exception as e:
                        failed_knowledge.append({
                            "id": knowledge.id if hasattr(knowledge, 'id') else "unknown",
                            "name": knowledge.name if hasattr(knowledge, 'name') else "unknown",
                            "error": str(e)
                        })

                db.commit()

            return {
                "cleaned_knowledge": cleaned_knowledge,
                "deleted_knowledge": deleted_knowledge,
                "failed_knowledge": failed_knowledge,
                "total_cleaned": len(cleaned_knowledge),
                "total_deleted": len(deleted_knowledge)
            }

        except Exception as e:
            log.error(f"Error in cleanup_knowledge_by_file_ids: {e}")
            return {
                "cleaned_knowledge": [],
                "deleted_knowledge": [],
                "failed_knowledge": [],
                "total_cleaned": 0,
                "total_deleted": 0,
                "error": str(e)
            }

    def get_knowledge_by_timestamp(self, cutoff_timestamp: int) -> list[KnowledgeModel]:
        """타임스탬프 기준으로 Knowledge 조회"""
        try:
            with get_db() as db:
                knowledge_records = db.query(Knowledge).filter(Knowledge.created_at < cutoff_timestamp).all()
                return [KnowledgeModel.model_validate(knowledge) for knowledge in knowledge_records]
        except Exception as e:
            log.error(f"Error getting knowledge by timestamp: {e}")
            return []


Knowledges = KnowledgeTable()
