from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .document_parser import (
    DocumentParseError,
    UnsupportedDocumentTypeError,
    extract_document_text,
    validate_file_extension,
)
from .review_service import ReviewServiceError, create_review_service
from .schemas import ReviewResponse

app = FastAPI(
    title="AI Design Document Reviewer API",
    description="生成AIを利用したシステム設計書レビュー支援API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"message": "AI Design Document Reviewer API is running"}


@app.post("/review", response_model=ReviewResponse)
async def review_document(
    file: Annotated[UploadFile, File(description="レビュー対象の設計書")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReviewResponse:
    filename = file.filename or "document"

    try:
        validate_file_extension(filename)
        content = await _read_upload(file, settings.max_file_size_bytes)
        document_text = await run_in_threadpool(
            extract_document_text, filename, content
        )
        service = create_review_service(settings)
        review = await run_in_threadpool(service.review, document_text)
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except DocumentParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except ReviewServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    finally:
        await file.close()

    return ReviewResponse.from_review(
        document_name=filename,
        review=review,
        demo_mode=settings.demo_mode,
    )


async def _read_upload(file: UploadFile, max_size: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while chunk := await file.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > max_size:
            max_mb = max_size // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"ファイルサイズは{max_mb}MB以下にしてください。",
            )
        chunks.append(chunk)

    return b"".join(chunks)
