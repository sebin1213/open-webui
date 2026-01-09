import time
import re
from typing import Optional

from open_webui.internal.db import Base, JSONField, get_db


from open_webui.env import DATABASE_USER_ACTIVE_STATUS_UPDATE_INTERVAL
from open_webui.models.chats import Chats
from open_webui.models.groups import Groups
from open_webui.utils.misc import throttle


from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text, cast, Date
from sqlalchemy import or_, func

import datetime

####################
# User DB Schema
####################


class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True)
    name = Column(String)

    email = Column(String)
    username = Column(String(50), nullable=True)

    role = Column(String)
    profile_image_url = Column(Text)

    bio = Column(Text, nullable=True)
    gender = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)

    info = Column(JSONField, nullable=True)
    settings = Column(JSONField, nullable=True)

    api_key = Column(String, nullable=True, unique=True)
    oauth_sub = Column(Text, unique=True)

    last_active_at = Column(BigInteger)

    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


class UserSettings(BaseModel):
    ui: Optional[dict] = {}
    model_config = ConfigDict(extra="allow")
    pass


class UserModel(BaseModel):
    id: str
    name: str

    email: str
    username: Optional[str] = None

    role: str = "pending"
    profile_image_url: str

    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None

    info: Optional[dict] = None
    settings: Optional[UserSettings] = None

    api_key: Optional[str] = None
    oauth_sub: Optional[str] = None

    last_active_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class UpdateProfileForm(BaseModel):
    profile_image_url: str
    name: str
    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None


class UserListResponse(BaseModel):
    users: list[UserModel]
    total: int


class UserInfoResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str


class UserIdNameResponse(BaseModel):
    id: str
    name: str


class UserInfoListResponse(BaseModel):
    users: list[UserInfoResponse]
    total: int


class UserIdNameListResponse(BaseModel):
    users: list[UserIdNameResponse]
    total: int


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    profile_image_url: str


class UserNameResponse(BaseModel):
    id: str
    name: str
    role: str
    profile_image_url: str


class UserRoleUpdateForm(BaseModel):
    id: str
    role: str


class UserUpdateForm(BaseModel):
    role: str
    name: str
    email: str
    profile_image_url: str
    password: Optional[str] = None
    team: Optional[str] = None
    division: Optional[str] = None
    position: Optional[str] = None
    headquarters: Optional[str] = None


class UsersTable:
    @staticmethod
    def _sanitize_strings_in_obj(obj):
        """Trim leading/trailing whitespace from all string values in nested structures."""
        if isinstance(obj, dict):
            return {k: UsersTable._sanitize_strings_in_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [UsersTable._sanitize_strings_in_obj(v) for v in obj]
        if isinstance(obj, str):
            s = obj.strip()
            # Remove all internal whitespace between words as well
            s = re.sub(r"\s+", "", s)
            return s
        return obj
    def insert_new_user(
        self,
        id: str,
        name: str,
        email: str,
        profile_image_url: str = "/user.png",
        role: str = "pending",
        oauth_sub: Optional[str] = None,
    ) -> Optional[UserModel]:
        with get_db() as db:
            user = UserModel(
                **{
                    "id": id,
                    "name": name,
                    "email": email,
                    "role": role,
                    "profile_image_url": profile_image_url,
                    "last_active_at": int(time.time()),
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                    "oauth_sub": oauth_sub,
                }
            )
            result = User(**user.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)
            if result:
                return user
            else:
                return None

    def get_user_by_id(self, id: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_api_key(self, api_key: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(api_key=api_key).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(email=email).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_by_oauth_sub(self, sub: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(oauth_sub=sub).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_users(
        self,
        filter: Optional[dict] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        with get_db() as db:
            query = db.query(User)
            dialect_name = getattr(getattr(db, 'bind', None), 'dialect', None)
            dialect_name = getattr(dialect_name, 'name', '') if dialect_name else ''

            if filter:
                query_key = filter.get("query")
                if query_key:
                    # Build both raw and whitespace-agnostic patterns
                    like = f"%{query_key}%"
                    query_key_nospace = re.sub(r"\s+", "", str(query_key)).strip()
                    like_nospace = f"%{query_key_nospace}%"
                    conditions = [
                        # Raw matches
                        User.name.ilike(like),
                        User.email.ilike(like),
                        cast(User.info, String).ilike(like),
                        # Space-insensitive matches
                        func.replace(User.name, " ", "").ilike(like_nospace),
                        func.replace(User.email, " ", "").ilike(like_nospace),
                        func.replace(cast(User.info, String), " ", "").ilike(like_nospace),
                    ]

                    # For SQLite (JSON1), query individual keys for more reliable matches
                    if dialect_name == "sqlite":
                        try:
                            conditions.extend(
                                [
                                    func.json_extract(User.info, "$.team").ilike(like),
                                    func.json_extract(User.info, "$.division").ilike(like),
                                    func.json_extract(User.info, "$.position").ilike(like),
                                    func.json_extract(User.info, "$.headquarters").ilike(like),
                                    # Space-insensitive JSON key matches
                                    func.replace(func.json_extract(User.info, "$.team"), " ", "").ilike(like_nospace),
                                    func.replace(func.json_extract(User.info, "$.division"), " ", "").ilike(like_nospace),
                                    func.replace(func.json_extract(User.info, "$.position"), " ", "").ilike(like_nospace),
                                    func.replace(func.json_extract(User.info, "$.headquarters"), " ", "").ilike(like_nospace),
                                ]
                            )
                        except Exception:
                            pass

                    query = query.filter(or_(*conditions))

                order_by = filter.get("order_by")
                direction = filter.get("direction")

                if order_by == "name":
                    if direction == "asc":
                        query = query.order_by(User.name.asc())
                    else:
                        query = query.order_by(User.name.desc())
                elif order_by == "email":
                    if direction == "asc":
                        query = query.order_by(User.email.asc())
                    else:
                        query = query.order_by(User.email.desc())

                elif order_by == "created_at":
                    if direction == "asc":
                        query = query.order_by(User.created_at.asc())
                    else:
                        query = query.order_by(User.created_at.desc())

                elif order_by == "last_active_at":
                    if direction == "asc":
                        query = query.order_by(User.last_active_at.asc())
                    else:
                        query = query.order_by(User.last_active_at.desc())

                elif order_by == "updated_at":
                    if direction == "asc":
                        query = query.order_by(User.updated_at.asc())
                    else:
                        query = query.order_by(User.updated_at.desc())
                elif order_by == "role":
                    if direction == "asc":
                        query = query.order_by(User.role.asc())
                    else:
                        query = query.order_by(User.role.desc())

            else:
                query = query.order_by(User.created_at.desc())

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            users = query.all()
            return {
                "users": [UserModel.model_validate(user) for user in users],
                "total": db.query(User).count(),
            }

    def get_users_by_user_ids(self, user_ids: list[str]) -> list[UserModel]:
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [UserModel.model_validate(user) for user in users]

    def get_num_users(self) -> Optional[int]:
        with get_db() as db:
            return db.query(User).count()

    def has_users(self) -> bool:
        with get_db() as db:
            return db.query(db.query(User).exists()).scalar()

    def get_first_user(self) -> UserModel:
        try:
            with get_db() as db:
                user = db.query(User).order_by(User.created_at).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def get_user_webhook_url_by_id(self, id: str) -> Optional[str]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()

                if user.settings is None:
                    return None
                else:
                    return (
                        user.settings.get("ui", {})
                        .get("notifications", {})
                        .get("webhook_url", None)
                    )
        except Exception:
            return None

    def update_user_role_by_id(self, id: str, role: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update({"role": role})
                db.commit()
                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_profile_image_url_by_id(
        self, id: str, profile_image_url: str
    ) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"profile_image_url": profile_image_url}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    @throttle(DATABASE_USER_ACTIVE_STATUS_UPDATE_INTERVAL)
    def update_user_last_active_by_id(self, id: str) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update(
                    {"last_active_at": int(time.time())}
                )
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_oauth_sub_by_id(
        self, id: str, oauth_sub: str
    ) -> Optional[UserModel]:
        try:
            with get_db() as db:
                db.query(User).filter_by(id=id).update({"oauth_sub": oauth_sub})
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def update_user_by_id(self, id: str, updated: dict) -> Optional[UserModel]:
        try:
            with get_db() as db:
                # Sanitize info payload strings by trimming whitespace
                if "info" in updated and isinstance(updated["info"], dict):
                    updated = {**updated, "info": UsersTable._sanitize_strings_in_obj(updated["info"]) }
                db.query(User).filter_by(id=id).update(updated)
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
                # return UserModel(**user.dict())
        except Exception as e:
            print(e)
            return None

    def update_user_settings_by_id(self, id: str, updated: dict) -> Optional[UserModel]:
        try:
            with get_db() as db:
                user_settings = db.query(User).filter_by(id=id).first().settings

                if user_settings is None:
                    user_settings = {}

                user_settings.update(updated)

                db.query(User).filter_by(id=id).update({"settings": user_settings})
                db.commit()

                user = db.query(User).filter_by(id=id).first()
                return UserModel.model_validate(user)
        except Exception:
            return None

    def delete_user_by_id(self, id: str) -> bool:
        try:
            # Remove User from Groups
            Groups.remove_user_from_all_groups(id)

            # Delete User Chats
            result = Chats.delete_chats_by_user_id(id)
            if result:
                with get_db() as db:
                    # Delete User
                    db.query(User).filter_by(id=id).delete()
                    db.commit()

                return True
            else:
                return False
        except Exception:
            return False

    def update_user_api_key_by_id(self, id: str, api_key: str) -> bool:
        try:
            with get_db() as db:
                result = db.query(User).filter_by(id=id).update({"api_key": api_key})
                db.commit()
                return True if result == 1 else False
        except Exception:
            return False

    def get_user_api_key_by_id(self, id: str) -> Optional[str]:
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=id).first()
                return user.api_key
        except Exception:
            return None

    def get_valid_user_ids(self, user_ids: list[str]) -> list[str]:
        with get_db() as db:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            return [user.id for user in users]

    def get_super_admin_user(self) -> Optional[UserModel]:
        with get_db() as db:
            user = db.query(User).filter_by(role="admin").first()
            if user:
                return UserModel.model_validate(user)
            else:
                return None

    def get_user_info_by_ids(self, user_ids: list[str]) -> dict:
        """
        Get user information (name, email) for a list of user IDs.
        Returns dictionary mapping user_id to user info.
        """
        try:
            with get_db() as db:
                users = db.query(User).filter(User.id.in_(user_ids)).all()
                
                user_info = {}
                for user in users:
                    user_info[user.id] = {
                        'name': user.name,
                        'email': user.email,
                        'role': user.role
                    }
                
                return user_info
                
        except Exception as e:
            return {}


Users = UsersTable()
