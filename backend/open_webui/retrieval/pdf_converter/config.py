"""
PDF Converter Configuration
"""

import os
from typing import Dict


class PDFConverterConfig:
    """PDF 변환기 설정 클래스"""
    
    # Gotenberg 서버 설정
    GOTENBERG_URL: str = os.getenv('GOTENBERG_URL', 'http://localhost:3000')
    GOTENBERG_TIMEOUT: int = int(os.getenv('GOTENBERG_TIMEOUT', '120'))  # 2분
    
    # 지원하는 파일 형식과 MIME 타입
    SUPPORTED_MIME_TYPES: Dict[str, str] = {
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'odp': 'application/vnd.oasis.opendocument.presentation',
        'odt': 'application/vnd.oasis.opendocument.text',
        'ods': 'application/vnd.oasis.opendocument.spreadsheet'
    }
    
    # 파일 크기 제한 - 기존 RAG_FILE_MAX_SIZE 환경변수 사용 (MB 단위, 기본값: 50MB)
    @classmethod
    def get_max_file_size(cls) -> int:
        """파일 최대 크기를 바이트 단위로 반환"""
        # RAG_FILE_MAX_SIZE는 MB 단위, MAX_FILE_SIZE는 바이트 단위 (하위 호환성)
        rag_size_mb = os.getenv('RAG_FILE_MAX_SIZE')
        if rag_size_mb:
            return int(rag_size_mb) * 1024 * 1024  # MB를 바이트로 변환
        
        # 하위 호환성을 위한 바이트 단위 환경변수
        max_size_bytes = os.getenv('MAX_FILE_SIZE', '52428800')  # 기본값: 50MB
        return int(max_size_bytes)
    
    # MAX_FILE_SIZE는 get_max_file_size() 메서드를 통해 동적으로 가져옴
    
    @classmethod
    def get_mime_type(cls, file_extension: str) -> str:
        """파일 확장자에 대한 MIME 타입 반환"""
        return cls.SUPPORTED_MIME_TYPES.get(
            file_extension.lower(), 
            'application/octet-stream'
        )
    
    @classmethod
    def is_supported_format(cls, file_extension: str) -> bool:
        """지원하는 파일 형식인지 확인"""
        return file_extension.lower() in cls.SUPPORTED_MIME_TYPES