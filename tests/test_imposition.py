"""拼版算法单元测试。"""
import pytest

from app.imposition import (
    split_signatures,
    impose_signature,
    impose,
    split_chapter_signatures,
    impose_chapters,
    ChapterTooLongError,
)


def test_split_exact_multiple_no_padding():
    # 10 页、每帖最多 4 张（16 页容量）-> 单帖 12 页补 2 空白
    sigs = split_signatures(10, 4)
    assert len(sigs) == 1
    assert sigs[0] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, None, None]


def test_split_full_signatures_no_padding():
    # 100 页、每帖 4 张 -> 6 个满帖 + 末帖 4 页
    sigs = split_signatures(100, 4)
    assert len(sigs) == 7
    for i in range(6):
        assert len(sigs[i]) == 16
        assert all(isinstance(p, int) for p in sigs[i])
        assert sigs[i][0] == 1 + 16 * i
        assert sigs[i][-1] == 16 + 16 * i
    assert sigs[6] == [97, 98, 99, 100]


def test_split_last_signature_padding_sizes():
    # 1..4 页、每帖 4 张，末帖（=唯一帖）都应补到 4 的倍数
    expected = {
        1: [1, None, None, None],
        2: [1, 2, None, None],
        3: [1, 2, 3, None],
        4: [1, 2, 3, 4],
    }
    for total, pages in expected.items():
        assert split_signatures(total, 4) == [pages]


def test_split_respects_max_sheets_capacity():
    # 每帖 2 张 -> 容量 8 页；18 页 -> 8 + 8 + 2(补到 4)
    sigs = split_signatures(18, 2)
    assert [len(s) for s in sigs] == [8, 8, 4]
    assert sigs[2] == [17, 18, None, None]
    # 任何帖的纸张数都不超过上限
    assert all(len(s) // 4 <= 2 for s in sigs)


def test_left_binding_outermost_sheet_4pages():
    # 最外张正面 = 末页/首页；背面 = 次页/倒数第二页
    sheets = impose_signature([1, 2, 3, 4], "left")
    assert sheets[0]["front"] == {"left": 4, "right": 1}
    assert sheets[0]["back"] == {"left": 2, "right": 3}


def test_left_binding_16_pages_order():
    pages = list(range(1, 17))
    sheets = impose_signature(pages, "left")
    assert len(sheets) == 4
    # 从外到内四张
    assert sheets[0]["front"] == {"left": 16, "right": 1}
    assert sheets[0]["back"] == {"left": 2, "right": 15}
    assert sheets[1]["front"] == {"left": 14, "right": 3}
    assert sheets[1]["back"] == {"left": 4, "right": 13}
    assert sheets[2]["front"] == {"left": 12, "right": 5}
    assert sheets[2]["back"] == {"left": 6, "right": 11}
    assert sheets[3]["front"] == {"left": 10, "right": 7}
    assert sheets[3]["back"] == {"left": 8, "right": 9}


def test_right_binding_mirrors_left():
    pages = list(range(1, 17))
    left = impose_signature(pages, "left")
    right = impose_signature(pages, "right")
    for ls, rs in zip(left, right):
        assert ls["sheet_index"] == rs["sheet_index"]
        assert rs["front"] == {"left": ls["front"]["right"], "right": ls["front"]["left"]}
        assert rs["back"] == {"left": ls["back"]["right"], "right": ls["back"]["left"]}


def test_blank_pages_appear_as_none():
    # 5 页 -> 末帖 1..5 + 3 空白
    result = impose(5, 4, "left")
    assert len(result) == 1
    sheets = result[0]["sheets"]
    # 帖共 8 页: [1,2,3,4,5,None,None,None]
    # 最外张: 正面 8(None)/1, 背面 2/7(None)
    assert sheets[0]["front"] == {"left": None, "right": 1}
    assert sheets[0]["back"] == {"left": 2, "right": None}
    # 最内张: 正面 6(None)/5, 背面 6索引? 本地索引:
    # k=1: front_left=n-1-2=5 -> pages[5]=None; front_right=pages[2]=3
    # back_left=pages[3]=4; back_right=pages[4]=5
    assert sheets[1]["front"] == {"left": None, "right": 3}
    assert sheets[1]["back"] == {"left": 4, "right": 5}


def test_impose_multi_signature_indexes_and_page_continuity():
    result = impose(20, 2, "left")  # 容量 8 页/帖 -> 8,8,4
    assert [s["signature_index"] for s in result] == [1, 2, 3]
    assert [s["sheet_count"] for s in result] == [2, 2, 1]
    assert result[2]["sheets"][0]["front"] == {"left": 20, "right": 17}
    assert result[2]["sheets"][0]["back"] == {"left": 18, "right": 19}

    # 所有非空页码 1..20 且不重不漏
    seen = []
    for sig in result:
        for sheet in sig["sheets"]:
            for side in ("front", "back"):
                for pos in ("left", "right"):
                    value = sheet[side][pos]
                    if value is not None:
                        seen.append(value)
    assert sorted(seen) == list(range(1, 21))


# ---------------------------------------------------------------------------
# 章节分帖
# ---------------------------------------------------------------------------


def test_chapter_split_single_signature_when_fits():
    # 10 页，3 章（4+3+3），容量 16：可合为一帖，补 2 空白
    groups = split_chapter_signatures(10, [1, 5, 8], 4)
    assert groups == [(1, 10)]


def test_chapter_split_forced_by_capacity():
    # 容量 8：[1..6]（6 页）后放不下第 3 章（4 页）；前两章可合帖（共 6 页）
    # 边界只能在第 2、3 章之间
    groups = split_chapter_signatures(10, [1, 2, 7], 2)
    assert groups == [(1, 6), (7, 10)]


def test_chapter_split_minimizes_blanks_before_signature_count():
    # 容量 8，三章各 4 页（4/4/4，总 12 页，单帖装不下）：
    # [1..2][3] = pad(8)+pad(4) = 0 空白、2 帖，边界 [2,3]
    # [1][2..3] = pad(4)+pad(8) = 0 空白、2 帖，边界 [1,3]
    # [1][2][3] = 0 空白、3 帖（帖数更多，不优先）
    # 前两者并列 -> 最早边界（第 1 章后）优先
    groups = split_chapter_signatures(12, [1, 5, 9], 2)
    assert groups == [(1, 4), (5, 12)]


def test_chapter_split_blanks_outrank_signature_count():
    # 容量 8，三章页数为 3、3、2（共 8 页）：
    # [1..3] 一帖：补 0 空白、1 帖 -> 全局最优
    groups = split_chapter_signatures(8, [1, 4, 7], 2)
    assert groups == [(1, 8)]


def test_chapter_split_blanks_tradeoff_against_count():
    # 容量 8，四章首页 [1,6,7,12] -> 章页数 5、1、5、1（共 12 页）：
    # [1..2][3..4]：pad(6)+pad(6) = 2+2 = 4 空白、2 帖，边界 [2,4]
    # [1][2..4]：pad(5)+pad(7) = 3+1 = 4 空白、2 帖，边界 [1,4]
    # [1][2..3][4] 等三帖方案：8 空白、3 帖（更差）
    # 前两者并列 -> 最早边界（第 1 章后）优先：[1][2..4]
    groups = split_chapter_signatures(12, [1, 6, 7, 12], 2)
    assert groups == [(1, 5), (6, 12)]


def test_chapter_split_earliest_boundary_tiebreak():
    # 容量 8，两章各 6 页（共 12 页）：只能拆成两帖，无并列
    groups = split_chapter_signatures(12, [1, 7], 2)
    assert groups == [(1, 6), (7, 12)]


def test_chapter_split_earliest_boundary_with_full_first_chapter():
    # 三章 8、4、4 页，容量 8：[1] 满帖 + [2..3]（8 页）
    # 与 [1..2] 不可行（12 页），且 [1][2][3] 帖数更多
    groups = split_chapter_signatures(16, [1, 9, 13], 2)
    assert groups == [(1, 8), (9, 16)]


def test_chapter_split_raises_when_chapter_too_long():
    # 第 2 章 9 页 > 容量 8
    with pytest.raises(ChapterTooLongError):
        split_chapter_signatures(12, [1, 2, 11], 2)


def test_chapter_split_exact_multiple_chapter_sizes():
    # 两章各 4 页，容量 8：合一帖 0 补白 1 帖
    assert split_chapter_signatures(8, [1, 5], 2) == [(1, 8)]
    # 两章各 1 页，容量 4：合一帖补 2 空白
    assert split_chapter_signatures(2, [1, 2], 1) == [(1, 2)]


def test_impose_chapters_group_fields_and_padding():
    # 容量 8，三章首页 [1,2,7] -> 章页数 1、5、4（共 10 页）：
    # 最优为 [1..2][3]：6 页补 2 空白（2 张），4 页补 0 空白（1 张）
    result = impose_chapters(10, [1, 2, 7], 2, "left")
    assert [s["signature_index"] for s in result] == [1, 2]
    assert result[0]["start_page"] == 1
    assert result[0]["end_page"] == 6
    assert result[0]["blank_count"] == 2
    assert result[0]["page_count_padded"] == 8
    assert result[0]["sheet_count"] == 2
    assert result[1]["start_page"] == 7
    assert result[1]["end_page"] == 10
    assert result[1]["blank_count"] == 0
    assert result[1]["page_count_padded"] == 4
    assert result[1]["sheet_count"] == 1


def test_impose_chapters_sheets_follow_existing_rules_and_continuity():
    # 第二帖 [7..10] 共 4 页无补白：
    # 最外张正面左 = 10（帖末）、右 = 7；背面左 = 8、右 = 9
    result = impose_chapters(10, [1, 2, 7], 2, "left")
    first_sheet = result[1]["sheets"][0]
    assert first_sheet["front"] == {"left": 10, "right": 7}
    assert first_sheet["back"] == {"left": 8, "right": 9}

    # 所有非空页码 1..10 不重不漏
    seen = []
    for sig in result:
        assert sig["blank_count"] == sum(
            1
            for sheet in sig["sheets"]
            for side in ("front", "back")
            for pos in ("left", "right")
            if sheet[side][pos] is None
        )
        for sheet in sig["sheets"]:
            for side in ("front", "back"):
                for pos in ("left", "right"):
                    value = sheet[side][pos]
                    if value is not None:
                        seen.append(value)
    assert sorted(seen) == list(range(1, 11))


def test_impose_chapters_right_binding_mirrors_left():
    common = dict(total_pages=10, chapter_first_pages=[1, 2, 7], max_sheets=2)
    left = impose_chapters(binding="left", **common)
    right = impose_chapters(binding="right", **common)
    for ls, rs in zip(left, right):
        assert ls["start_page"] == rs["start_page"]
        assert ls["end_page"] == rs["end_page"]
        assert ls["blank_count"] == rs["blank_count"]
        for lsheet, rsheet in zip(ls["sheets"], rs["sheets"]):
            assert rsheet["front"] == {
                "left": lsheet["front"]["right"],
                "right": lsheet["front"]["left"],
            }
            assert rsheet["back"] == {
                "left": lsheet["back"]["right"],
                "right": lsheet["back"]["left"],
            }


def test_impose_chapters_sheet_count_never_exceeds_limit():
    # 100 页、7 章（前 6 章各 16 页，末章 4 页）、每帖最多 4 张（16 页容量）
    result = impose_chapters(100, [1, 17, 33, 49, 65, 81, 97], 4, "left")
    assert len(result) == 7
    for sig in result:
        assert sig["sheet_count"] <= 4
        assert sig["page_count_padded"] <= 16
