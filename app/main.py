"""离线小册子拼版 API。"""
from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator

from .imposition import impose, impose_chapters, ChapterTooLongError

app = FastAPI(
    title="离线小册子拼版 API",
    description=(
        "按帖拆分并完成小册子拼版（signature imposition）。"
        "左装订最外张正面为 末页/首页，背面为 次页/倒数第二页；"
        "右装订左右页位镜像交换。"
    ),
    version="1.0.0",
)


class ImpositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_pages: int = Field(
        ..., ge=1, description="总页数，正整数（1, 2, 3, ...）"
    )
    max_sheets_per_signature: int = Field(
        ..., ge=1, description="每帖最多纸张数，正整数；每帖最多容纳其 4 倍页数"
    )
    binding: Literal["left", "right"] = Field(
        ..., description="装订方向：left=左装订，right=右装订"
    )


class PagePair(BaseModel):
    left: Optional[int] = Field(..., description="左页页码，空白页为 null")
    right: Optional[int] = Field(..., description="右页页码，空白页为 null")


class Sheet(BaseModel):
    sheet_index: int = Field(..., description="帖内纸张序号，从 1 开始（1 为最外张）")
    front: PagePair = Field(..., description="正面左右页码")
    back: PagePair = Field(..., description="背面左右页码")


class Signature(BaseModel):
    signature_index: int = Field(..., description="帖号，从 1 开始")
    sheet_count: int = Field(..., description="本帖纸张数")
    page_count_padded: int = Field(..., description="本帖补齐空白后的总页数（4 的倍数）")
    sheets: list[Sheet] = Field(..., description="帖内纸张，按从外到内排列")


class ImpositionResponse(BaseModel):
    total_pages: int
    max_sheets_per_signature: int
    binding: Literal["left", "right"]
    signature_count: int
    signatures: list[Signature]


class ChapterImpositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_pages: int = Field(
        ..., ge=1, description="总页数，正整数（1, 2, 3, ...）"
    )
    max_sheets_per_signature: int = Field(
        ..., ge=1, description="每帖最多纸张数，正整数；每帖最多容纳其 4 倍页数"
    )
    binding: Literal["left", "right"] = Field(
        ..., description="装订方向：left=左装订，right=右装订"
    )
    chapter_first_pages: List[int] = Field(
        ...,
        min_length=1,
        description="各章首页页码：严格递增且首项为 1，且均不超过总页数",
    )

    @model_validator(mode="after")
    def _validate_chapter_first_pages(self) -> "ChapterImpositionRequest":
        pages = self.chapter_first_pages
        if pages[0] != 1:
            raise ValueError("chapter_first_pages 首项必须为 1")
        if any(pages[i] >= pages[i + 1] for i in range(len(pages) - 1)):
            raise ValueError("chapter_first_pages 必须严格递增")
        if pages[-1] > self.total_pages:
            raise ValueError("chapter_first_pages 中的页码不能超过 total_pages")
        return self


class ChapterSignature(Signature):
    start_page: int = Field(..., description="本帖原页起始页码")
    end_page: int = Field(..., description="本帖原页结束页码")
    blank_count: int = Field(..., description="本帖尾部补齐的空白页数")


class ChapterImpositionResponse(BaseModel):
    total_pages: int
    max_sheets_per_signature: int
    binding: Literal["left", "right"]
    chapter_first_pages: List[int]
    signature_count: int
    signatures: list[ChapterSignature]


@app.get("/health", tags=["健康检查"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/v1/impose",
    response_model=ImpositionResponse,
    tags=["拼版"],
    summary="小册子拼版",
)
def create_imposition(request: ImpositionRequest) -> ImpositionResponse:
    signatures = impose(
        total_pages=request.total_pages,
        max_sheets=request.max_sheets_per_signature,
        binding=request.binding,
    )
    return ImpositionResponse(
        total_pages=request.total_pages,
        max_sheets_per_signature=request.max_sheets_per_signature,
        binding=request.binding,
        signature_count=len(signatures),
        signatures=signatures,
    )


@app.post(
    "/api/v1/impose/chapters",
    response_model=ChapterImpositionResponse,
    tags=["拼版"],
    summary="按章节分帖的小册子拼版",
)
def create_chapter_imposition(
    request: ChapterImpositionRequest,
) -> ChapterImpositionResponse:
    try:
        signatures = impose_chapters(
            total_pages=request.total_pages,
            chapter_first_pages=request.chapter_first_pages,
            max_sheets=request.max_sheets_per_signature,
            binding=request.binding,
        )
    except ChapterTooLongError as exc:
        # 单章页数超过单帖容量：无法在不跨帖的前提下拼版
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ChapterImpositionResponse(
        total_pages=request.total_pages,
        max_sheets_per_signature=request.max_sheets_per_signature,
        binding=request.binding,
        chapter_first_pages=request.chapter_first_pages,
        signature_count=len(signatures),
        signatures=signatures,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception) -> JSONResponse:
    # 兜底：未预期错误统一返回 500，避免向前端泄漏堆栈
    return JSONResponse(status_code=500, content={"detail": "内部错误"})
