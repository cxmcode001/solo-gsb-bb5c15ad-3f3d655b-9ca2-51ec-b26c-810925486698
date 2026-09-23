"""小册子拼版核心算法。

规则
----
1. 按原页顺序分帖，每帖最多容纳 ``max_sheets * 4`` 页；
2. 仅末帖在尾部补空白页至 4 的倍数，空白页用 ``None`` 表示；
3. 每帖内部按纸张“从外到内”给出正反面左右页码；
4. 左装订（left）：最外张正面 = 末页/首页，背面 = 次页/倒数第二页，
   逐张向内递推；右装订（right）将左右页位镜像交换。

章节拼版（:func:`impose_chapters`）额外约束
-------------------------------------------
* 章节不可跨帖，相邻章节可以合入同一帖；
* 每帖（含补白）实际页数不超过 ``max_sheets * 4``，即纸张数不超过上限；
* 单章页数超过容量时无法分帖，抛出 :class:`ChapterTooLongError`；
* 分帖边界依次最小化：各帖补至 4 的倍数所需空白总数 → 帖数；
  仍相同则优先最早的分帖边界。
"""
from __future__ import annotations

from typing import List, Literal, Optional, Tuple

Binding = Literal["left", "right"]

# 单张纸的一页描述：(全局页码或 None, 在帖内纸张上的位置)
# side: "front" 正面 / "back" 背面；position: "left" 左页 / "right" 右页


class ChapterTooLongError(ValueError):
    """单个章节的页数超过单帖容量（``max_sheets * 4``），无法拼版。"""


def split_signatures(total_pages: int, max_sheets: int) -> List[List[Optional[int]]]:
    """按原页顺序分帖，末帖补空白至 4 的倍数。

    返回二维列表：外层为帖（顺序），内层为该帖按原页顺序排列的页码，
    末帖补齐位置为 ``None``。
    """
    capacity = max_sheets * 4
    signatures: List[List[Optional[int]]] = []

    start = 1
    while start <= total_pages:
        end = min(start + capacity - 1, total_pages)
        pages: List[Optional[int]] = list(range(start, end + 1))
        # 仅末帖需要补齐（前面的帖都恰好装满，本身就是 4 的倍数）
        if len(pages) % 4 != 0:
            pages.extend([None] * (4 - len(pages) % 4))
        signatures.append(pages)
        start = end + 1

    return signatures


def impose_signature(
    pages: List[Optional[int]],
    binding: Binding,
) -> List[dict]:
    """对一个帖拼版，按纸张从外到内返回各张正反面的左右页码。

    ``pages`` 长度必须为 ``4s``（``s`` 为纸张数），其中保存的已是**全局页码**；
    末帖补齐位置为 ``None``，对应页位返回 ``null``。
    """
    sheet_count = len(pages) // 4
    n = len(pages)  # 帖页数（含补齐的空白）
    sheets: List[dict] = []

    for k in range(sheet_count):
        # 左装订下，第 k 张（k=0 最外张）四个页位的帖内位置索引（0-based）：
        #   正面左 n-1-2k、正面右 2k
        #   背面左 2k+1、背面右 n-2-2k
        front_left = pages[n - 1 - 2 * k]
        front_right = pages[2 * k]
        back_left = pages[2 * k + 1]
        back_right = pages[n - 2 - 2 * k]

        if binding == "right":
            # 右装订：左右页位镜像交换
            front_left, front_right = front_right, front_left
            back_left, back_right = back_right, back_left

        sheets.append(
            {
                "sheet_index": k + 1,
                "front": {"left": front_left, "right": front_right},
                "back": {"left": back_left, "right": back_right},
            }
        )

    return sheets


def impose(total_pages: int, max_sheets: int, binding: Binding) -> List[dict]:
    """完整拼版：分帖并逐帖返回拼版结果。"""
    grouped = split_signatures(total_pages, max_sheets)
    result: List[dict] = []
    for index, pages in enumerate(grouped, start=1):
        result.append(
            {
                "signature_index": index,
                "sheet_count": len(pages) // 4,
                "page_count_padded": len(pages),
                "sheets": impose_signature(pages, binding),
            }
        )
    return result


def _padding(page_count: int) -> int:
    """把 ``page_count`` 页补到 4 的倍数所需的空白页数。"""
    return (-page_count) % 4


def split_chapter_signatures(
    total_pages: int,
    chapter_first_pages: List[int],
    max_sheets: int,
) -> List[Tuple[int, int]]:
    """按章节约束分帖，返回各帖的原页 ``(起始页码, 结束页码)``。

    章节不可跨帖，相邻章节可合帖；每帖页数（补白后）不超过
    ``max_sheets * 4``。单章超长时抛出 :class:`ChapterTooLongError`。

    用动态规划依次最小化：补白总数 → 帖数；仍相同则优先最早的分帖边界
    （状态按 ``(补白总数, 帖数, 边界列表)`` 字典序比较，边界越早列表越小）。
    """
    capacity = max_sheets * 4
    chapter_count = len(chapter_first_pages)

    # 各章的页数：由相邻章节首页之差得到，末章取到 total_pages
    chapter_sizes: List[int] = []
    for index, first_page in enumerate(chapter_first_pages):
        next_first = (
            chapter_first_pages[index + 1]
            if index + 1 < chapter_count
            else total_pages + 1
        )
        size = next_first - first_page
        if size > capacity:
            raise ChapterTooLongError(
                f"第 {index + 1} 章共 {size} 页，超过单帖容量 {capacity} 页"
            )
        chapter_sizes.append(size)

    # dp[j]：覆盖前 j 章的最优状态 (补白总数, 帖数, 分帖边界列表)
    # 边界列表中的元素为“该帖结束于第几章”（章号，从 1 计）。
    # 元组按字典序比较，天然实现三级择优：
    # 补白最少 → 帖数最少 → 边界列表字典序最小（最早的分帖边界优先）。
    dp: List[Optional[Tuple[int, int, List[int]]]] = [
        None
    ] * (chapter_count + 1)
    dp[0] = (0, 0, [])

    for j in range(1, chapter_count + 1):
        best: Optional[Tuple[int, int, List[int]]] = None
        # size = 第 i..j-1 章合并后的原页页数；i 递减时逐章累加
        size = 0
        for i in range(j - 1, -1, -1):
            size += chapter_sizes[i]
            if size > capacity:
                # i 再减小只会让组更大，必然也超限
                break
            previous = dp[i]
            assert previous is not None
            candidate = (
                previous[0] + _padding(size),
                previous[1] + 1,
                previous[2] + [j],
            )
            if best is None or candidate < best:
                best = candidate
        # 单章均不超长时，按章单独成帖至少是一个可行解
        assert best is not None
        dp[j] = best

    boundaries = dp[chapter_count][2]

    # 由章边界换算为各帖原页起止页码
    groups: List[Tuple[int, int]] = []
    start_chapter = 0
    for end_chapter in boundaries:
        start_page = chapter_first_pages[start_chapter]
        end_page = (
            chapter_first_pages[end_chapter] - 1
            if end_chapter < chapter_count
            else total_pages
        )
        groups.append((start_page, end_page))
        start_chapter = end_chapter

    return groups


def impose_chapters(
    total_pages: int,
    chapter_first_pages: List[int],
    max_sheets: int,
    binding: Binding,
) -> List[dict]:
    """按章节约束完整拼版：分帖、逐帖尾部补白并复用正反面拼版规则。"""
    groups = split_chapter_signatures(total_pages, chapter_first_pages, max_sheets)
    result: List[dict] = []
    for index, (start_page, end_page) in enumerate(groups, start=1):
        pages: List[Optional[int]] = list(range(start_page, end_page + 1))
        blank_count = _padding(len(pages))
        if blank_count:
            pages.extend([None] * blank_count)
        result.append(
            {
                "signature_index": index,
                "sheet_count": len(pages) // 4,
                "page_count_padded": len(pages),
                "blank_count": blank_count,
                "start_page": start_page,
                "end_page": end_page,
                "sheets": impose_signature(pages, binding),
            }
        )
    return result
