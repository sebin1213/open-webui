"""
PDF Converter Package
Gotenberg 기반 Office 문서 → PDF 변환 라이브러리
Open WebUI 통합용
"""

from .converter import PDFConverter
from .config import PDFConverterConfig
from .exceptions import (
    PDFConverterError, 
    GotenbergConnectionError, 
    UnsupportedFileError,
    FileSizeError
)

__version__ = "1.0.0"
__all__ = [
    "PDFConverter",
    "PDFConverterConfig", 
    "PDFConverterError",
    "GotenbergConnectionError",
    "UnsupportedFileError",
    "FileSizeError"
]