"""
PDF Converter - Gotenberg 기반 PDF 변환기
"""

import os
import requests
import zipfile
from pathlib import Path
from typing import Tuple, Optional
import logging

from .config import PDFConverterConfig
from .exceptions import (
    PDFConverterError, 
    GotenbergConnectionError, 
    UnsupportedFileError,
    FileSizeError
)


logger = logging.getLogger(__name__)


class PDFConverter:
    """Gotenberg 기반 PDF 변환기"""
    
    def __init__(self, gotenberg_url: Optional[str] = None, timeout: Optional[int] = None):
        """
        PDF 변환기 초기화
        
        Args:
            gotenberg_url: Gotenberg 서버 URL (기본값: 설정에서 가져옴)
            timeout: 요청 타임아웃 (초, 기본값: 설정에서 가져옴)
        """
        self.gotenberg_url = gotenberg_url or PDFConverterConfig.GOTENBERG_URL
        self.timeout = timeout or PDFConverterConfig.GOTENBERG_TIMEOUT
        self.convert_endpoint = f"{self.gotenberg_url}/forms/libreoffice/convert"
        
        logger.info(f"PDF Converter initialized with Gotenberg URL: {self.gotenberg_url}")
    
    def _detect_file_extension(self, file_path: str) -> str:
        """
        파일 확장자 감지 (파일 시그니처 기반)
        
        Args:
            file_path: 파일 경로
            
        Returns:
            감지된 파일 확장자
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read(16)  # 시그니처 확인용 처음 16바이트
            
            # OLE2 기반 파일 (PPT, DOC 등) 확인
            if content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
                logger.debug("OLE2 파일 시그니처 감지: ppt로 가정")
                return 'ppt'
            
            # ZIP 기반 파일 (PPTX, DOCX 등) 확인
            elif content.startswith(b'PK'):
                try:
                    with zipfile.ZipFile(file_path) as zip_ref:
                        file_list = zip_ref.namelist()
                        
                        # PPTX 확인 - ppt 폴더 존재
                        if any(name.startswith('ppt/') for name in file_list):
                            logger.debug("ZIP 파일 내 ppt/ 폴더 감지: pptx로 확인")
                            return 'pptx'
                        # DOCX 확인 - word 폴더 존재
                        elif any(name.startswith('word/') for name in file_list):
                            logger.debug("ZIP 파일 내 word/ 폴더 감지: docx로 확인")
                            return 'docx'
                        # XLSX 확인 - xl 폴더 존재
                        elif any(name.startswith('xl/') for name in file_list):
                            logger.debug("ZIP 파일 내 xl/ 폴더 감지: xlsx로 확인")
                            return 'xlsx'
                        else:
                            logger.debug("알 수 없는 ZIP 파일: pptx로 가정")
                            return 'pptx'
                            
                except zipfile.BadZipFile:
                    logger.debug("유효하지 않은 ZIP 파일: ppt로 가정")
                    return 'ppt'
            
            # 기타 알 수 없는 형식
            else:
                logger.debug("알 수 없는 파일 형식: ppt로 가정")
                return 'ppt'
                
        except Exception as e:
            logger.warning(f"파일 시그니처 분석 중 오류: {e}. ppt로 가정")
            return 'ppt'
    
    def _validate_file(self, file_path: str) -> Tuple[str, str]:
        """
        파일 유효성 검증
        
        Args:
            file_path: 파일 경로
            
        Returns:
            (파일명, 파일 확장자) 튜플
            
        Raises:
            PDFConverterError: 파일이 존재하지 않는 경우
            FileSizeError: 파일 크기가 초과된 경우
            UnsupportedFileError: 지원하지 않는 파일 형식인 경우
        """
        if not os.path.exists(file_path):
            raise PDFConverterError(f"파일을 찾을 수 없습니다: {file_path}")
        
        # 파일 크기 확인
        file_size = os.path.getsize(file_path)
        max_file_size = PDFConverterConfig.get_max_file_size()
        if file_size > max_file_size:
            raise FileSizeError(file_size, max_file_size)
        
        # 파일명과 확장자 추출
        path_obj = Path(file_path)
        filename = path_obj.name
        file_ext = path_obj.suffix.lstrip('.').lower()
        
        # 확장자가 없는 경우 파일 시그니처로 감지
        if not file_ext:
            logger.warning(f"확장자가 없는 파일: {filename}, 시그니처로 감지 시도")
            file_ext = self._detect_file_extension(file_path)
            logger.info(f"시그니처 기반 감지된 확장자: {file_ext}")
        
        # 지원하는 파일 형식인지 확인
        if not PDFConverterConfig.is_supported_format(file_ext):
            raise UnsupportedFileError(file_ext)
        
        return filename, file_ext
    
    def convert_to_pdf(self, file_path: str) -> Tuple[bytes, str]:
        """
        Office 문서를 PDF로 변환
        
        Args:
            file_path: 변환할 파일 경로
            
        Returns:
            (PDF 바이너리 데이터, 파일 확장자) 튜플
            
        Raises:
            PDFConverterError: 변환 실패
            GotenbergConnectionError: Gotenberg 서버 연결 실패
            UnsupportedFileError: 지원하지 않는 파일 형식
            FileSizeError: 파일 크기 초과
        """
        # 파일 유효성 검증
        filename, file_ext = self._validate_file(file_path)
        
        logger.info(f"PDF 변환 시작: {filename} (확장자: {file_ext})")
        
        # MIME 타입 설정
        mime_type = PDFConverterConfig.get_mime_type(file_ext)
        
        try:
            # 파일 확장자 보정이 필요한 경우
            corrected_path = file_path
            path_obj = Path(file_path)
            current_ext = path_obj.suffix.lstrip('.')
            
            if current_ext != file_ext and current_ext:
                # 임시 파일 생성하여 올바른 확장자로 복사
                new_filename = f"{path_obj.stem}.{file_ext}"
                temp_dir = os.path.dirname(file_path)
                corrected_path = os.path.join(temp_dir, new_filename)
                
                logger.info(f"파일 확장자 보정: {path_obj.name} → {new_filename}")
                
                # 파일 복사
                with open(file_path, 'rb') as src, open(corrected_path, 'wb') as dst:
                    dst.write(src.read())
                
                filename = new_filename
            
            # Gotenberg API 호출
            with open(corrected_path, 'rb') as f:
                files = {
                    'files': (filename, f, mime_type)
                }
                
                logger.debug(f"Gotenberg 요청: {self.convert_endpoint}")
                response = requests.post(
                    self.convert_endpoint, 
                    files=files, 
                    timeout=self.timeout
                )
            
            # 임시 파일 정리 (보정된 파일인 경우)
            if corrected_path != file_path and os.path.exists(corrected_path):
                os.remove(corrected_path)
            
            if response.status_code == 200:
                logger.info(f"PDF 변환 성공: {filename}")
                return response.content, file_ext
            else:
                error_msg = f"Gotenberg 변환 실패 (코드: {response.status_code})"
                if response.text:
                    error_msg += f", 메시지: {response.text}"
                logger.error(error_msg)
                raise PDFConverterError(error_msg)
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Gotenberg 서버 연결 실패: {e}")
            raise GotenbergConnectionError(f"Gotenberg 서버에 연결할 수 없습니다: {e}")
        
        except requests.exceptions.Timeout as e:
            logger.error(f"Gotenberg 요청 타임아웃: {e}")
            raise PDFConverterError(f"변환 요청이 타임아웃되었습니다 ({self.timeout}초)")
        
        except Exception as e:
            logger.error(f"PDF 변환 중 예상치 못한 오류: {e}")
            raise PDFConverterError(f"PDF 변환 중 오류가 발생했습니다: {str(e)}")
    
    def health_check(self) -> bool:
        """
        Gotenberg 서버 상태 확인
        
        Returns:
            서버가 정상인 경우 True, 그렇지 않으면 False
        """
        try:
            health_url = f"{self.gotenberg_url}/health"
            response = requests.get(health_url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False