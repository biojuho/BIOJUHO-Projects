
"""
BioLinker - PDF Parser Service
"""
import io
from typing import Optional
import pypdf

class PDFParser:
    """PDF 파일 텍스트 추출 서비스"""
    
    @staticmethod
    def parse(file_content: bytes) -> str:
        """
        PDF 바이트 콘텐츠에서 텍스트 추출
        """
        try:
            # Create a file-like object from bytes
            file_stream = io.BytesIO(file_content)
            
            # Read PDF
            reader = pypdf.PdfReader(file_stream)
            
            text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            
            return "\n".join(text)
        except Exception as e:
            print(f"[PDF Parser Error] {e}")
            return ""

    @staticmethod
    def extract_metadata(file_content: bytes) -> dict:
        """
        PDF 메타데이터 추출
        """
        try:
            file_stream = io.BytesIO(file_content)
            reader = pypdf.PdfReader(file_stream)
            return reader.metadata or {}
        except:
            return {}

_parser = PDFParser()

def get_pdf_parser():
    return _parser
