"""API 层测试：正常请求与非法参数（4xx）。"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_impose_basic_left():
    response = client.post(
        "/api/v1/impose",
        json={
            "total_pages": 16,
            "max_sheets_per_signature": 4,
            "binding": "left",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["signature_count"] == 1
    assert data["signatures"][0]["signature_index"] == 1
    assert data["signatures"][0]["sheet_count"] == 4
    first = data["signatures"][0]["sheets"][0]
    assert first["sheet_index"] == 1
    assert first["front"] == {"left": 16, "right": 1}
    assert first["back"] == {"left": 2, "right": 15}


def test_impose_right_binding():
    response = client.post(
        "/api/v1/impose",
        json={
            "total_pages": 16,
            "max_sheets_per_signature": 4,
            "binding": "right",
        },
    )
    assert response.status_code == 200
    first = response.json()["signatures"][0]["sheets"][0]
    assert first["front"] == {"left": 1, "right": 16}
    assert first["back"] == {"left": 15, "right": 2}


def test_impose_null_blank_pages():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": 1, "max_sheets_per_signature": 1, "binding": "left"},
    )
    assert response.status_code == 200
    sheet = response.json()["signatures"][0]["sheets"][0]
    # 1 页补 3 空白：最外张正面 空白/1
    assert sheet["front"] == {"left": None, "right": 1}
    assert sheet["back"] == {"left": None, "right": None}


def test_invalid_total_pages_zero():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": 0, "max_sheets_per_signature": 4, "binding": "left"},
    )
    assert 400 <= response.status_code < 500
    assert response.status_code == 422


def test_invalid_total_pages_negative():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": -5, "max_sheets_per_signature": 4, "binding": "left"},
    )
    assert response.status_code == 422


def test_invalid_total_pages_not_integer():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": 1.5, "max_sheets_per_signature": 4, "binding": "left"},
    )
    assert response.status_code == 422


def test_invalid_max_sheets_zero():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": 10, "max_sheets_per_signature": 0, "binding": "left"},
    )
    assert response.status_code == 422


def test_invalid_binding_value():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": 10, "max_sheets_per_signature": 4, "binding": "top"},
    )
    assert response.status_code == 422


def test_missing_required_field():
    response = client.post(
        "/api/v1/impose",
        json={"total_pages": 10, "max_sheets_per_signature": 4},
    )
    assert response.status_code == 422


def test_unknown_field_rejected():
    response = client.post(
        "/api/v1/impose",
        json={
            "total_pages": 10,
            "max_sheets_per_signature": 4,
            "binding": "left",
            "extra": 1,
        },
    )
    assert response.status_code == 422


def test_empty_body_returns_422():
    response = client.post("/api/v1/impose", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/v1/impose/chapters
# ---------------------------------------------------------------------------


def test_chapter_impose_basic():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 10,
            "max_sheets_per_signature": 2,
            "binding": "left",
            "chapter_first_pages": [1, 2, 7],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["chapter_first_pages"] == [1, 2, 7]
    assert data["signature_count"] == 2
    assert data["signatures"][0]["start_page"] == 1
    assert data["signatures"][0]["end_page"] == 6
    assert data["signatures"][0]["blank_count"] == 2
    assert data["signatures"][1]["start_page"] == 7
    assert data["signatures"][1]["end_page"] == 10
    assert data["signatures"][1]["blank_count"] == 0
    # sheets 页位结构沿用原接口
    sheet = data["signatures"][0]["sheets"][0]
    assert set(sheet.keys()) == {"sheet_index", "front", "back"}
    assert set(sheet["front"].keys()) == {"left", "right"}


def test_chapter_impose_right_binding():
    payload = {
        "total_pages": 8,
        "max_sheets_per_signature": 2,
        "chapter_first_pages": [1, 5],
    }
    left = client.post(
        "/api/v1/impose/chapters", json={**payload, "binding": "left"}
    ).json()
    right = client.post(
        "/api/v1/impose/chapters", json={**payload, "binding": "right"}
    ).json()
    ls = left["signatures"][0]["sheets"][0]
    rs = right["signatures"][0]["sheets"][0]
    assert rs["front"] == {"left": ls["front"]["right"], "right": ls["front"]["left"]}
    assert rs["back"] == {"left": ls["back"]["right"], "right": ls["back"]["left"]}


def test_chapter_impose_too_long_chapter_returns_422():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 12,
            "max_sheets_per_signature": 2,
            "binding": "left",
            "chapter_first_pages": [1, 2, 11],
        },
    )
    assert response.status_code == 422
    assert "章" in response.json()["detail"]


def test_chapter_impose_first_page_must_be_one():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 10,
            "max_sheets_per_signature": 4,
            "binding": "left",
            "chapter_first_pages": [2, 5],
        },
    )
    assert response.status_code == 422


def test_chapter_impose_must_be_strictly_increasing():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 10,
            "max_sheets_per_signature": 4,
            "binding": "left",
            "chapter_first_pages": [1, 5, 5],
        },
    )
    assert response.status_code == 422


def test_chapter_impose_first_page_exceeds_total():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 4,
            "max_sheets_per_signature": 4,
            "binding": "left",
            "chapter_first_pages": [1, 5],
        },
    )
    assert response.status_code == 422


def test_chapter_impose_empty_chapters_returns_422():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 4,
            "max_sheets_per_signature": 4,
            "binding": "left",
            "chapter_first_pages": [],
        },
    )
    assert response.status_code == 422


def test_chapter_impose_unknown_field_rejected():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 4,
            "max_sheets_per_signature": 4,
            "binding": "left",
            "chapter_first_pages": [1],
            "extra": 1,
        },
    )
    assert response.status_code == 422


def test_chapter_impose_missing_field_returns_422():
    response = client.post(
        "/api/v1/impose/chapters",
        json={
            "total_pages": 4,
            "max_sheets_per_signature": 4,
            "binding": "left",
        },
    )
    assert response.status_code == 422


def test_original_impose_endpoint_unchanged_without_chapter_fields():
    # 原接口不接受章节字段，响应也不含新增的 start_page/end_page/blank_count
    response = client.post(
        "/api/v1/impose",
        json={
            "total_pages": 10,
            "max_sheets_per_signature": 2,
            "binding": "left",
        },
    )
    assert response.status_code == 200
    signature = response.json()["signatures"][0]
    assert set(signature.keys()) == {
        "signature_index",
        "sheet_count",
        "page_count_padded",
        "sheets",
    }
