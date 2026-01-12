import requests
import logging, os, tempfile
from typing import List, Dict, Optional
from pathlib import Path
from urllib.parse import quote

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from open_webui.utils.headers import include_user_info_headers
from open_webui.env import SRC_LOG_LEVELS
from open_webui.config import EXTERNAL_DOCUMENT_LOADER_MODEL, EXTERNAL_DOCUMENT_LOADER_MODEL_OCR, EXTERNAL_DOCUMENT_LOADER_TEMP_DIR

# PDF 변환기 import
try:
    from open_webui.retrieval.pdf_converter.converter import PDFConverter
    from open_webui.retrieval.pdf_converter.config import PDFConverterConfig
    from open_webui.retrieval.pdf_converter.exceptions import (
        PDFConverterError,
        GotenbergConnectionError,
        UnsupportedFileError,
        FileSizeError
    )
    PDF_CONVERTER_AVAILABLE = True
except ImportError as e:
    log = logging.getLogger(__name__)
    log.warning(f"PDF Converter module not available: {e}. Office file conversion will be skipped.")
    PDF_CONVERTER_AVAILABLE = False

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class ExternalDocumentLoader(BaseLoader):
    def __init__(
        self,
        file_path,
        url: str,
        api_key: str,
        mime_type=None,
        user=None,
        **kwargs,
    ) -> None:
        self.url = url
        self.model = EXTERNAL_DOCUMENT_LOADER_MODEL.value
        self.model_ocr = EXTERNAL_DOCUMENT_LOADER_MODEL_OCR.value
        self.api_key = api_key
        self.file_path = file_path
        self.mime_type = mime_type
        
        # PDF 변환 옵션
        self.enable_pdf_conversion = kwargs.get('enable_pdf_conversion', True)
        self.gotenberg_url = kwargs.get('gotenberg_url', None)
        self._temp_files = []  # 임시 파일 추적

        self.user = user

    def load(self) -> List[Document]:
        try:
            # 1단계: 파일 형식 확인 및 PDF 변환 (필요시)
            processed_file_path = self._prepare_file_for_processing()
            
            # 2단계: OCR API 호출
            return self._process_with_ocr_api(processed_file_path)
        finally:
            # 임시 파일 정리
            self._cleanup_temp_files()

    def _prepare_file_for_processing(self) -> str:
        """파일을 OCR 처리를 위해 준비 (필요시 PDF 변환)"""
        
        if not PDF_CONVERTER_AVAILABLE or not self.enable_pdf_conversion:
            return self.file_path
            
        if not self._should_convert_to_pdf():
            return self.file_path
            
        return self._convert_to_pdf()

    def _should_convert_to_pdf(self) -> bool:
        """PDF 변환이 필요한지 판단"""
        
        # MIME 타입으로 PDF 확인
        if self.mime_type and 'pdf' in self.mime_type.lower():
            return False
            
        # 파일 확장자로 확인
        file_ext = Path(self.file_path).suffix.lower()
        if file_ext == '.pdf':
            return False
            
        # 지원되는 Office 형식인지 확인
        return PDFConverterConfig.is_supported_format(file_ext.lstrip('.'))

    def _get_temp_conversion_dir(self) -> str:
        """PDF 변환용 임시 디렉토리 경로 반환 (없으면 생성)"""
        # 환경변수로 설정된 경로 사용 (기본값: Docker volume 경로)
        temp_dir = EXTERNAL_DOCUMENT_LOADER_TEMP_DIR.value
        
        try:
            # 디렉토리가 없으면 생성 (중간 디렉토리도 생성)
            os.makedirs(temp_dir, exist_ok=True)
            log.debug(f"Using PDF conversion directory: {temp_dir}")
            return temp_dir
        except Exception as e:
            log.warning(f"Failed to create conversion directory {temp_dir}: {e}")
            # 생성 실패 시 시스템 임시 디렉토리 사용
            fallback_dir = tempfile.gettempdir()
            log.info(f"Falling back to system temp directory: {fallback_dir}")
            return fallback_dir

    def _convert_to_pdf(self) -> str:
        """Office 파일을 PDF로 변환"""
        
        try:
            log.info(f"Converting {self.file_path} to PDF...")
            
            converter = PDFConverter(gotenberg_url=self.gotenberg_url)
            pdf_content, file_ext = converter.convert_to_pdf(self.file_path)
            
            # PDF 변환용 임시 디렉토리 확보
            conversion_dir = self._get_temp_conversion_dir()
            
            # 임시 PDF 파일 생성
            with tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.pdf', 
                prefix=f'converted_{Path(self.file_path).stem}_',
                dir=conversion_dir  # 지정된 디렉토리 사용
            ) as temp_pdf:
                temp_pdf.write(pdf_content)
                temp_pdf_path = temp_pdf.name
                
            # 임시 파일 추적에 추가
            self._temp_files.append(temp_pdf_path)
            
            log.info(f"Successfully converted {self.file_path} to PDF: {temp_pdf_path}")
            return temp_pdf_path
            
        except Exception as e:
            log.warning(f"PDF conversion failed for {self.file_path}: {e}")
            log.info("Proceeding with original file")
            return self.file_path

    def _cleanup_temp_files(self):
        """임시 파일들 정리"""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    log.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                log.warning(f"Failed to cleanup temporary file {temp_file}: {e}")
        self._temp_files.clear()

    def _process_with_ocr_api(self, file_path: str) -> List[Document]:
        """OCR API를 통한 문서 처리"""
        # JSON 응답 기대 명시
        headers = {"Accept": "application/json"}
        if self.api_key is not None:
            headers["Authorization"] = self.api_key

        try:
            headers["X-Filename"] = quote(os.path.basename(self.file_path))
        except Exception:
            pass


        if self.user is not None:
            headers = include_user_info_headers(headers, self.user)

        url = self.url
        if url.endswith("/"):
            url = url[:-1]
        # 파일 준비
        with open(file_path, "rb") as f:
            # 변환된 파일의 경우 적절한 MIME 타입과 파일명 설정
            if file_path != self.file_path:  # 변환된 파일인 경우
                file_mime_type = "application/pdf"
                file_name = f"{Path(self.file_path).stem}.pdf"  # 원본 파일명 기반으로 PDF 이름 생성
                log.debug(f"Using converted file: {file_name} with MIME type: {file_mime_type}")
            else:  # 원본 파일인 경우
                file_mime_type = self.mime_type or "application/octet-stream"
                file_name = os.path.basename(file_path)
                log.debug(f"Using original file: {file_name} with MIME type: {file_mime_type}")
                
            log.info(f"OCR 파일 : {file_name} 확장자 : {file_mime_type}")
            files = {
                # Upstage dp: 파일 필드명은 "document"
                "document": (
                    file_name,
                    f,
                    file_mime_type,
                )
            }

            # 페이지 단위 Markdown 생성을 위해 markdown 지정
            # document-parse, dp
            data = {
                "ocr": self.model_ocr,  # OCR 모델 지정
                "model": self.model, 
                "output_formats": "['markdown']" 
            }

            log.info(
                "[ExternalDocumentLoader] Sending request to OCR API ",
                extra={"file_path": file_path, "original_file": self.file_path},
            )
            log.info(f"[ExternalDocumentLoader] URL: {self.url}, Headers: {headers}")

            try:
                # POST 요청
                response = requests.post(
                    self.url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120,
                )
            except Exception as e:
                log.error(f"Error connecting to endpoint: {e}")
                raise Exception(f"Error connecting to endpoint: {e}")

        if response.ok:
            response_data = response.json()
            if response_data:
                if isinstance(response_data, dict):
                    # ------ document-parse 응답 스키마 기반 페이지 단위 Markdown 구성 ------
                    elements = response_data.get("elements", []) or []
                    usage_pages = (response_data.get("usage") or {}).get("pages")

                    # elements가 없으면 content.markdown 전체 반환(백업 경로)
                    if not elements:
                        content = response_data.get("content", {}) or {}
                        whole_md = (content.get("markdown") or "").strip()
                        if not whole_md:
                            raise Exception(
                                "Error loading document: No elements and empty content.markdown"
                            )

                        metadata = {
                            "source": os.path.basename(self.file_path),
                            "api": response_data.get("api", ""),
                            "model": response_data.get("model", ""),
                            "usage_pages": usage_pages,
                            "total_pages": usage_pages,
                        }
                        return [Document(page_content=whole_md, metadata=metadata)]

                    # 페이지별로 묶기 (page는 1-based로 옴)
                    pages_map: Dict[int, List[Dict]] = {}
                    for el in elements:
                        page_no = el.get("page")
                        if not isinstance(page_no, int):
                            page_no = 1  # page 미지정 요소는 1페이지로 보수적으로 귀속
                        pages_map.setdefault(page_no, []).append(el)

                    # 전체 페이지 수
                    total_pages = usage_pages or (max(pages_map.keys()) if pages_map else None)

                    documents: List[Document] = []
                    for page_no in sorted(pages_map.keys()):
                        # 같은 페이지 내에서 id 오름차순 → 자연스러운 읽기 순서
                        page_elements = sorted(
                            pages_map[page_no], key=lambda e: (e.get("id") or 0)
                        )

                        chunks: List[str] = []
                        for el in page_elements:
                            c = el.get("content", {}) or {}
                            md = (c.get("markdown") or "").strip()
                            if md:
                                chunks.append(md)

                        page_markdown = "\n".join(chunks).strip()

                        # 빈 페이지를 유지하고 싶지 않다면 아래 두 줄 대신 `continue`로 스킵하세요.
                        if not page_markdown:
                            page_markdown = ""

                        metadata = {
                            "source": os.path.basename(self.file_path),
                            "api": response_data.get("api", ""),
                            "model": response_data.get("model", ""),
                            "usage_pages": usage_pages,
                            "page_label": page_no,   # 1-based
                            "total_pages": total_pages,
                            "element_count_on_page": len(page_elements),
                        }

                        documents.append(
                            Document(page_content=page_markdown, metadata=metadata)
                        )

                    # 모든 페이지가 빈 markdown이면 오류로 처리
                    if all((not d.page_content) for d in documents):
                        raise Exception(
                            "Error loading document: Empty markdown on all pages"
                        )

                    return documents
                    # ------ 페이지 단위 Markdown 구성 끝 ------
                else:
                    raise Exception("Error loading document: Unexpected response format")
            else:
                raise Exception("Error loading document: No content returned")
        else:
            raise Exception(
                f"Error loading document: {response.status_code} {response.text}"
            )
