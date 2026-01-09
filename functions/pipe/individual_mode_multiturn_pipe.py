"""
title: Dify OCR API Integration with Conversation Mapping (DB-backed)
author: taehee
version: 1.3
description: Dify OCR API integration that persists conversation mapping in the chat meta store with async streaming support
"""

import copy
import json
import logging
from typing import AsyncIterator, Union, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
import httpx
from httpx import TimeoutException
import base64
import mimetypes
from io import BytesIO
from open_webui.internal.db import get_db
from open_webui.models.chats import Chat


class Pipe:
    # 환경 변수 설정 클래스 (관리자 전용)
    class Valves(BaseModel):
        DIFY_API_URL: str = Field(
            default="https://api.dify.ai/v1", description="Dify API endpoint URL"
        )
        DIFY_API_KEY: str = Field(
            default="", description="Dify API key (관리자만 설정 가능)"
        )
        IS_STREAMING: bool = Field(default=True, description="스트리밍 응답 활성화")
        TIMEOUT_SECONDS: int = Field(default=120, description="API 요청 타임아웃 (초)")
        ENABLE_DETAILED_LOGS: bool = Field(
            default=False, description="상세 로그 활성화 (디버깅용)"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 로깅 포맷 설정
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 파이프 실행 중 DB 접근이 불가능한 경우를 대비한 로컬 상태 캐시
        self._local_state: Dict[str, Dict[str, Any]] = {}

    def _is_persistable_chat(self, chat_id: str) -> bool:
        """대화 ID가 실제 DB 레코드와 매핑 가능한지 확인"""
        return bool(chat_id) and chat_id not in {"default_chat", "local"}

    def _read_conversation_state(self, chat_id: str) -> tuple[Dict[str, Any], bool]:
        """
        대화 상태를 DB 또는 로컬 캐시에서 읽어온다.
        반환값: (state, persistable)
        """
        default_state = {
            "models": {},
        }

        if self._is_persistable_chat(chat_id):
            try:
                with get_db() as db:
                    chat_row = db.get(Chat, chat_id)
                    if chat_row:
                        chat_data = (
                            chat_row.chat if isinstance(chat_row.chat, dict) else {}
                        )
                        chat_meta = (
                            chat_data.get("meta")
                            if isinstance(chat_data.get("meta"), dict)
                            else {}
                        )
                        dify_state = (
                            chat_meta.get("dify")
                            if isinstance(chat_meta.get("dify"), dict)
                            else {}
                        )

                        models: Dict[str, Any] = {}
                        if isinstance(dify_state.get("models"), dict):
                            for model, info in dify_state["models"].items():
                                conversation_id = ""
                                messages = []
                                if isinstance(info, dict):
                                    conversation_id = info.get("conversation_id", "") or ""
                                    messages = info.get("messages", [])
                                if not isinstance(messages, list):
                                    messages = []
                                models[model] = {
                                    "conversation_id": conversation_id,
                                    "messages": messages,
                                }
                        else:
                            # Backward compatibility (single model stored at top level)
                            conversation_id = dify_state.get("conversation_id", "") or ""
                            messages = dify_state.get("messages", [])
                            if not isinstance(messages, list):
                                messages = []
                            model_name = dify_state.get("model")
                            if conversation_id or messages:
                                models[
                                    model_name or "__default__"
                                ] = {
                                    "conversation_id": conversation_id,
                                    "messages": messages,
                                }

                        state = {
                            "models": models,
                        }
                        return state, True
            except Exception as e:
                if self.valves.ENABLE_DETAILED_LOGS:
                    self.logger.error(
                        f"Failed to read conversation state from DB for chat_id={chat_id}: {e}"
                    )

        local_state = self._local_state.setdefault(
            chat_id, copy.deepcopy(default_state)
        )
        models = (
            local_state.get("models")
            if isinstance(local_state.get("models"), dict)
            else {}
        )
        normalized_models: Dict[str, Any] = {}
        for model, info in models.items():
            conversation_id = ""
            messages = []
            if isinstance(info, dict):
                conversation_id = info.get("conversation_id", "") or ""
                messages = info.get("messages", [])
            if not isinstance(messages, list):
                messages = []
            normalized_models[model] = {
                "conversation_id": conversation_id,
                "messages": messages,
            }

        return {
            "models": normalized_models,
        }, False

    def _write_conversation_state(
        self, chat_id: str, state: Dict[str, Any], persistable: bool
    ) -> None:
        """대화 상태를 DB 또는 로컬 캐시에 저장"""
        models_state = (
            state.get("models") if isinstance(state.get("models"), dict) else {}
        )
        models_store: Dict[str, Any] = {}
        for model, info in models_state.items():
            conversation_id = ""
            messages = []
            if isinstance(info, dict):
                conversation_id = info.get("conversation_id", "") or ""
                messages = info.get("messages", [])
            if not isinstance(messages, list):
                messages = []
            models_store[model] = {
                "conversation_id": conversation_id,
                "messages": messages,
            }

        state_to_store = {
            "models": models_store,
        }

        if persistable:
            try:
                with get_db() as db:
                    chat_row = db.get(Chat, chat_id)
                    if not chat_row:
                        persistable = False
                    else:
                        chat_data = (
                            copy.deepcopy(chat_row.chat)
                            if isinstance(chat_row.chat, dict)
                            else {}
                        )
                        chat_meta = chat_data.get("meta", {})
                        if not isinstance(chat_meta, dict):
                            chat_meta = {}

                        dify_meta = chat_meta.get("dify", {})
                        if not isinstance(dify_meta, dict):
                            dify_meta = {}

                        dify_meta["models"] = copy.deepcopy(models_store)
                        chat_meta["dify"] = dify_meta
                        chat_data["meta"] = chat_meta

                        chat_row.chat = chat_data
                        db.commit()
                        return
            except Exception as e:
                if self.valves.ENABLE_DETAILED_LOGS:
                    self.logger.error(
                        f"Failed to write conversation state to DB for chat_id={chat_id}: {e}"
                    )
                persistable = False

        if not persistable:
            self._local_state[chat_id] = copy.deepcopy(state_to_store)

    def get_closure_info(self, func):
        """event_emitter에서 chat_id와 message_id 추출"""
        if hasattr(func, "__closure__") and func.__closure__:
            for cell in func.__closure__:
                if isinstance(cell.cell_contents, dict):
                    return cell.cell_contents
        return None

    def manage_conversation_state(
        self, chat_id: str, message_id: str, model_name: str, messages_count: int
    ):
        """대화 진행 흐름에 맞춰 parent_message_id를 계산하고 상태를 업데이트"""
        state, persistable = self._read_conversation_state(chat_id)
        models_state = state.setdefault("models", {})
        if "__default__" in models_state and model_name not in models_state:
            models_state[model_name] = models_state.pop("__default__")
        model_state = models_state.setdefault(
            model_name,
            {
                "conversation_id": "",
                "messages": [],
            },
        )
        parent_message_id = None

        if messages_count == 1:
            # 새로운 대화 시작
            model_state["messages"] = []
            if self.valves.ENABLE_DETAILED_LOGS:
                self.logger.info(f"Started new conversation - chat_id: {chat_id}")
        else:
            chat_history = model_state.get("messages", [])
            if not isinstance(chat_history, list):
                chat_history = []

            current_msg_index = messages_count - 1

            if current_msg_index > 0 and len(chat_history) >= current_msg_index:
                previous_msg = chat_history[current_msg_index - 1]
                if isinstance(previous_msg, dict) and previous_msg:
                    parent_message_id = list(previous_msg.values())[0]

                # 분기 대화 처리: 현재 위치 이후 메시지 히스토리 재정렬
                chat_history = chat_history[:current_msg_index]

            model_state["messages"] = chat_history

            if self.valves.ENABLE_DETAILED_LOGS:
                self.logger.info(
                    f"Continuing conversation - chat_id: {chat_id}, parent_message_id: {parent_message_id}"
                )

        models_state[model_name] = model_state
        state["models"] = models_state
        self._write_conversation_state(chat_id, state, persistable)
        return parent_message_id

    def update_conversation_mapping(
        self,
        chat_id: str,
        model_name: str,
        message_id: str,
        dify_conversation_id: str,
        dify_message_id: str,
    ):
        """Dify 응답으로 받은 conversation/message ID를 저장"""
        state, persistable = self._read_conversation_state(chat_id)

        models_state = state.setdefault("models", {})
        if "__default__" in models_state and model_name not in models_state:
            models_state[model_name] = models_state.pop("__default__")
        model_state = models_state.setdefault(
            model_name,
            {
                "conversation_id": "",
                "messages": [],
            },
        )

        messages = model_state.get("messages", [])
        if not isinstance(messages, list):
            messages = []

        # 동일한 메시지 ID가 이미 있다면 덮어쓰도록 제거
        messages = [entry for entry in messages if message_id not in entry]
        messages.append({message_id: dify_message_id})

        if dify_conversation_id:
            model_state["conversation_id"] = dify_conversation_id
        model_state["messages"] = messages

        models_state[model_name] = model_state
        state["models"] = models_state
        self._write_conversation_state(chat_id, state, persistable)

        if self.valves.ENABLE_DETAILED_LOGS:
            self.logger.info(
                f"Updated conversation mapping - chat_id: {chat_id}, dify_conversation_id: {dify_conversation_id}"
            )

    def _store_streaming_conversation_id(
        self,
        chat_id: str,
        model_name: str,
        message_id: str,
        data: Dict[str, Any],
        conversation_id_saved: bool,
    ) -> bool:
        """스트리밍 이벤트에서 conversation_id와 message_id를 추출해 저장"""
        if conversation_id_saved:
            return True

        dify_conversation_id = data.get("conversation_id", "")
        dify_message_id = data.get("message_id") or data.get("id") or ""

        if dify_conversation_id and dify_message_id:
            self.update_conversation_mapping(
                chat_id, model_name, message_id, dify_conversation_id, dify_message_id
            )
            return True

        return conversation_id_saved

    def validate_api_key(self) -> None:
        """API 키 유효성 검사"""
        if not self.valves.DIFY_API_KEY:
            raise ValueError(
                "Dify API key가 설정되지 않았습니다. 관리자에게 문의해주세요."
            )

        if not self.valves.DIFY_API_KEY.startswith(
            ("app-", "sk-")
        ):  # Dify API key 형식 검증
            raise ValueError(
                "유효하지 않은 Dify API key 형식입니다. 관리자에게 문의해주세요."
            )

    def base64_to_file(
        self, base64_data_uri: str, default_filename: str = "image.png"
    ) -> Tuple[str, BytesIO, str]:
        """base64 data URI 문자열을 Dify 업로드용 파일 객체로 변환합니다."""
        if not base64_data_uri.startswith("data:image/"):
            raise ValueError(
                "지원되지 않는 데이터 형식입니다. data:image/... 형태여야 합니다."
            )

        try:
            header, encoded = base64_data_uri.split(",", 1)
        except ValueError:
            raise ValueError("올바른 base64 data URI 형식이 아닙니다.")

        # MIME 타입 추출 (예: image/png)
        try:
            mime_type = header.split(":")[1].split(";")[0]
        except IndexError:
            mime_type = "image/png"

        # 확장자 추론
        extension = mimetypes.guess_extension(mime_type) or ".png"
        filename = (
            default_filename
            if default_filename.endswith(extension)
            else f"{default_filename}{extension}"
        )

        # base64 디코딩
        binary_data = base64.b64decode(encoded)
        fileobj = BytesIO(binary_data)
        fileobj.name = filename  # 일부 라이브러리에서 사용됨

        return filename, fileobj, mime_type

    def get_query(self, messages: list) -> str:
        """사용자 메시지에서 쿼리 추출"""
        query = None

        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue

            if msg.get("role") == "user":
                if isinstance(msg.get("content"), str):
                    query = msg.get("content", "").strip()
                elif isinstance(msg.get("content"), list):
                    for item in msg.get("content", []):
                        if isinstance(item, dict) and item.get("type") == "text":
                            query = item.get("text", "").strip()
                return query

        return query

    def get_system_prompt(self, messages: list) -> str:
        """시스템 프롬프트 추출"""
        system_prompt = None

        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue

            if msg.get("role") == "system":
                if isinstance(msg.get("content"), str):
                    system_prompt = msg.get("content", "").strip()
                return system_prompt

        return system_prompt

    def get_image_files(self, messages: list) -> list:
        """사용자 메시지에서 이미지 파일 추출"""
        image_files = []

        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue

            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                for item in msg.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        image_url = item.get("image_url", {}).get("url", "")
                        filename, fileobj, mime_type = self.base64_to_file(image_url)
                        image_files.append({"file": (filename, fileobj, mime_type)})
            return image_files

        return image_files

    def get_content(self, body: dict) -> Tuple[Optional[str], Optional[str], list]:
        """사용자 입력 메시지를 안전하게 추출하여 query와 image_files로 구성된 튜플을 반환합니다."""
        try:
            messages = body.get("messages", [])
            if not messages:
                self.logger.warning("메시지 리스트가 비어있습니다.")
                return None, None, []

            # 쿼리 추출
            query = self.get_query(messages)

            # 시스템 프롬프트 추출
            system_prompt = self.get_system_prompt(messages)

            # 이미지 파일 추출
            image_files = self.get_image_files(messages)

            if not query and not image_files:
                self.logger.warning("사용자 메시지를 찾을 수 없습니다.")

            if not query and image_files:
                query = "이미지 인식 결과를 알려줘"

            return query, system_prompt, image_files

        except Exception as e:
            self.logger.error(f"메시지 추출 중 오류 발생: {str(e)}")
            return None, None, []

    def extract_model_id(self, model_string: str) -> str:
        """모델 ID를 안전하게 추출합니다."""
        if not model_string:
            return "default"

        # "." 이 있는 경우 마지막 부분 추출
        if "." in model_string:
            return model_string.split(".")[-1]

        return model_string

    async def upload_files(self, image_files: list, user_email: str) -> list:
        """이미지 파일을 Dify API에 업로드하고 파일 ID 리스트를 반환합니다."""
        file_ids = []

        async with httpx.AsyncClient(timeout=self.valves.TIMEOUT_SECONDS) as client:
            for idx, file in enumerate(image_files):
                try:
                    filename, fileobj, mime_type = file["file"]
                    if self.valves.ENABLE_DETAILED_LOGS:
                        self.logger.info(f"[{idx+1}] 업로드 시작: {filename}")

                    # 업로드 요청
                    response = await client.post(
                        f"{self.valves.DIFY_API_URL}/files/upload",
                        headers={"Authorization": f"Bearer {self.valves.DIFY_API_KEY}"},
                        data={"user": user_email},
                        files={"file": (filename, fileobj, mime_type)},
                    )

                    response.raise_for_status()
                    file_id = response.json().get("id")
                    if file_id:
                        file_ids.append(file_id)
                        if self.valves.ENABLE_DETAILED_LOGS:
                            self.logger.info(f"[{idx+1}] 업로드 완료 → file_id: {file_id}")
                    else:
                        self.logger.warning(
                            f"[{idx+1}] 응답에 file_id 없음: {response.text}"
                        )

                except Exception as e:
                    self.logger.error(f"[{idx+1}] 업로드 중 오류 발생: {str(e)}")

                # 리소스 정리
                if hasattr(fileobj, "close"):
                    fileobj.close()

        return file_ids

    def build_file_input_list(self, file_ids: list) -> list[dict]:
        """파일 ID를 Dify 입력 형식으로 변환"""
        return [
            {
                "type": "image",
                "transfer_method": "local_file",
                "upload_file_id": file_id,
            }
            for file_id in file_ids
        ]

    async def streaming_response(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        user_email: str,
        chat_id: str,
        model_id: str,
        message_id: str,
    ) -> AsyncIterator[str]:
        """스트리밍 응답을 처리합니다. (conversation mapping 포함)"""
        try:
            async with httpx.AsyncClient(timeout=self.valves.TIMEOUT_SECONDS) as client:
                async with client.stream(
                    "POST",
                    f"{self.valves.DIFY_API_URL}/chat-messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    # 상태 코드 확인
                    if response.status_code == 401:
                        yield "❌ 인증 실패: API Key가 유효하지 않습니다. 설정을 확인해주세요.\n"
                        return
                    elif response.status_code == 403:
                        yield "❌ 권한 없음: 이 리소스에 접근할 권한이 없습니다.\n"
                        return
                    elif response.status_code == 429:
                        yield "⚠️ 요청 한도 초과: 잠시 후 다시 시도해주세요.\n"
                        return
                    elif response.status_code >= 500:
                        yield f"❌ Dify 서버 오류 ({response.status_code}): 서버에 문제가 발생했습니다.\n"
                        return
                    elif response.status_code != 200:
                        error_body = await response.aread()
                        error_text = error_body.decode("utf-8", errors="ignore")
                        yield f"❌ 오류 발생 (상태 코드: {response.status_code})\n"
                        yield (
                            f"상세 정보: {error_text[:200]}...\n"
                            if len(error_text) > 200
                            else f"상세 정보: {error_text}\n"
                        )
                        return

                    # 상태 추적 변수
                    conversation_id_saved = False

                    # 스트리밍 데이터 처리
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        try:
                            json_str = line[6:]
                            if json_str == "[DONE]":
                                break

                            data = json.loads(json_str)
                            event = data.get("event", "")

                            conversation_id_saved = self._store_streaming_conversation_id(
                                chat_id, model_id, message_id, data, conversation_id_saved
                            )

                            # Dify 이벤트 타입별 처리
                            if event == "message":
                                # 실제 답변 출력
                                answer = data.get("answer", "")
                                if answer:
                                    yield answer
                                    
                            elif event == "message_end":
                                # 메타데이터는 로그가 활성화된 경우에만 표시
                                if self.valves.ENABLE_DETAILED_LOGS:
                                    metadata = data.get("metadata", {})
                                    usage = metadata.get("usage", {})
                                    if usage:
                                        yield f"\n📊 토큰 사용량: {usage.get('total_tokens', 'N/A')} tokens\n"
                                        
                            elif event == "workflow_finished":
                                # 워크플로우 완료
                                break
                            elif event == "error":
                                error_msg = data.get("message", "알 수 없는 오류")
                                yield f"\n❌ Dify 오류: {error_msg}\n"
                                return
                            elif event in ["workflow_started", "node_started", "node_finished", "tts_message", "tts_message_end"]:
                                # 기타 이벤트는 조용히 처리
                                continue

                        except json.JSONDecodeError:
                            # JSON 파싱 오류는 조용히 무시
                            continue
                        except Exception as e:
                            yield f"\n❌ 처리 중 오류가 발생했습니다: {str(e)}\n"
                            return

        except TimeoutException:
            yield f"❌ 응답 시간 초과 ({self.valves.TIMEOUT_SECONDS}초)\n"
        except httpx.ConnectError:
            yield "❌ Dify API 서버에 연결할 수 없습니다.\n"
        except Exception as e:
            yield f"❌ 오류가 발생했습니다: {str(e)}\n"

    async def blocking_response(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        user_email: str,
        chat_id: str,
        model_id: str,
        message_id: str,
    ) -> str:
        """블로킹 응답을 처리합니다. (conversation mapping 포함)"""
        try:
            async with httpx.AsyncClient(timeout=self.valves.TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self.valves.DIFY_API_URL}/chat-messages",
                    headers=headers,
                    json=payload,
                )

                # 상태 코드 확인
                if response.status_code == 401:
                    return "❌ 인증 실패: API Key가 유효하지 않습니다. 설정을 확인해주세요."
                elif response.status_code == 403:
                    return "❌ 권한 없음: 이 리소스에 접근할 권한이 없습니다."
                elif response.status_code == 429:
                    return "⚠️ 요청 한도 초과: 잠시 후 다시 시도해주세요."
                elif response.status_code >= 500:
                    return f"❌ Dify 서버 오류 ({response.status_code}): 서버에 문제가 발생했습니다."
                elif response.status_code != 200:
                    error_text = response.text
                    return f"❌ 오류 발생 (상태 코드: {response.status_code})\n상세 정보: {error_text[:500]}"

                # 응답 파싱
                try:
                    data = response.json()
                    
                    # 🔑 핵심: Conversation mapping 조용히 저장
                    dify_conversation_id = data.get("conversation_id", "")
                    dify_message_id = data.get("message_id", "")
                    
                    # 블로킹 모드에서는 최상위에 ID가 있을 수 있음
                    if not dify_message_id:
                        dify_message_id = data.get("id", "")
                    
                    if dify_conversation_id and dify_message_id:
                        self.update_conversation_mapping(
                            chat_id, model_id, message_id, dify_conversation_id, dify_message_id
                        )

                    # Dify 응답 구조에 따라 처리
                    answer = ""
                    if "answer" in data:
                        answer = data["answer"]
                    elif "data" in data and "outputs" in data["data"]:
                        outputs = data["data"]["outputs"]
                        if isinstance(outputs, dict) and "answer" in outputs:
                            answer = outputs["answer"]
                        elif isinstance(outputs, dict) and "text" in outputs:
                            answer = outputs["text"]
                        elif isinstance(outputs, str):
                            answer = outputs
                        else:
                            answer = json.dumps(outputs, ensure_ascii=False, indent=2)
                    else:
                        answer = json.dumps(data, ensure_ascii=False, indent=2)
                    
                    return answer

                except json.JSONDecodeError as e:
                    return f"❌ 응답을 파싱할 수 없습니다: {str(e)}\n원본 응답: {response.text[:500]}"

        except TimeoutException:
            return f"❌ 응답 시간 초과 ({self.valves.TIMEOUT_SECONDS}초)"
        except httpx.ConnectError:
            return "❌ Dify API 서버에 연결할 수 없습니다."
        except Exception as e:
            return f"❌ 예기치 않은 오류: {str(e)}"

    async def pipe(
        self, body: dict, __user__: Optional[Dict[str, Any]] = None, __event_emitter__: Optional[Dict] = None, **kwargs
    ) -> Union[str, AsyncIterator[str]]:
        """파이프 진입점 함수 (메모리 기반 conversation mapping 포함)"""
        try:
            # 사용자 정보 추출
            user_email = __user__.get("email", "unknown") if __user__ else "unknown"
            user_name = __user__.get("name", "User") if __user__ else "User"

            # Chat ID와 Message ID 추출
            chat_id = "default_chat"
            message_id = "default_message"

            metadata = kwargs.get("__metadata__") or {}
            if metadata:
                chat_id = metadata.get("chat_id") or chat_id
                message_id = metadata.get("message_id") or message_id

            if __event_emitter__:
                cell_contents = self.get_closure_info(__event_emitter__)
                if cell_contents:
                    chat_id = cell_contents.get("chat_id", "default_chat")
                    message_id = cell_contents.get("message_id", "default_message")

            # API 키 검증
            try:
                self.validate_api_key()
            except ValueError as e:
                error_msg = str(e)
                return f"❌ {error_msg}"

            # 사용자 입력 추출
            query, system_prompt, image_files = self.get_content(body)
            files = None

            if not query:
                return "❌ 입력 메시지를 찾을 수 없습니다. 메시지를 입력해주세요."

            # 모델 ID 추출
            model_id = self.extract_model_id(body.get("model", ""))
            
            # 메시지 개수 확인
            messages = body.get("messages", [])
            messages_count = len(messages)
            
            # 🔑 핵심: DB에 저장된 Conversation 상태 관리
            parent_message_id = self.manage_conversation_state(
                chat_id, message_id, model_id, messages_count
            )

            # 이미지 파일이 있는 경우 업로드
            if image_files:
                file_ids = await self.upload_files(image_files, user_email)
                files = self.build_file_input_list(file_ids)

            # 스트리밍 설정 사용 (관리자 설정)
            is_streaming = self.valves.IS_STREAMING

            # 🔑 저장된 conversation_id 가져오기
            existing_state, _ = self._read_conversation_state(chat_id)
            models_map = (
                existing_state.get("models")
                if isinstance(existing_state.get("models"), dict)
                else {}
            )
            model_state = models_map.get(model_id)
            if model_state is None and "__default__" in models_map:
                model_state = models_map.get("__default__")
            existing_conversation_id = (
                model_state.get("conversation_id", "") if isinstance(model_state, dict) else ""
            )

            # Dify API 페이로드 생성
            payload = {
                "inputs": {
                    "system_prompt": system_prompt,
                },
                "query": query,
                "response_mode": "streaming" if is_streaming else "blocking",
                "user": user_email,
            }

            if existing_conversation_id:
                payload["conversation_id"] = existing_conversation_id  # 저장된 기존 대화 ID 재사용
            
            # parent_message_id 추가 (분기 대화 지원)
            if parent_message_id:
                payload["parent_message_id"] = parent_message_id

            if files:
                payload["inputs"]["image_file"] = files[0]  # 첫 번째 이미지 파일만 사용 가능

            # 헤더 설정
            headers = {
                "Authorization": f"Bearer {self.valves.DIFY_API_KEY}",
                "Content-Type": "application/json",
            }

            # 요청 처리
            if is_streaming:
                return self.streaming_response(
                    headers, payload, user_email, chat_id, model_id, message_id
                )
            else:
                return await self.blocking_response(
                    headers, payload, user_email, chat_id, model_id, message_id
                )

        except Exception as e:
            return f"❌ 시스템 오류가 발생했습니다: {str(e)}\n\n관리자에게 문의해주세요."
