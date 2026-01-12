"""
PDF Converter Exceptions
"""


class PDFConverterError(Exception):
    """PDF 변환기 기본 예외 클래스"""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GotenbergConnectionError(PDFConverterError):
    """Gotenberg 서버 연결 오류"""
    
    def __init__(self, message: str = "Gotenberg 서버에 연결할 수 없습니다"):
        super().__init__(message, status_code=503)


class UnsupportedFileError(PDFConverterError):
    """지원하지 않는 파일 형식"""
    
    def __init__(self, file_extension: str):
        message = f"지원하지 않는 파일 형식입니다: .{file_extension}"
        super().__init__(message, status_code=400)


class FileSizeError(PDFConverterError):
    """파일 크기 초과"""
    
    def __init__(self, size: int, max_size: int):
        message = f"파일 크기가 초과되었습니다: {size} bytes (최대: {max_size} bytes)"
        super().__init__(message, status_code=413)