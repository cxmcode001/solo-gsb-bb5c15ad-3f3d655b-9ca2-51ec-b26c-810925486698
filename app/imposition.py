"""小册子拼版核心算法。

规则
----
1. 按原页顺序分帖，每帖最多容纳 ``max_sheets * 4`` 页；
2. 仅末帖在尾部补空白页至 4 的倍数，空白页用 ``None`` 表示；
3. 每帖内部按纸张“从外到内”给出正反面左右页码；
4. 左装订（left）：最外张正面 = 末页/首页，背面 = 次页/倒数第二页，
   逐张向内递推；右装订（right）将左右页位镜像交换。
"""
from __future__ import annotations

from typing import List, Literal, Optional

Binding = Literal["left", "right"]

# 单张纸的一页描述：(全局页码或 None, 在帖内纸张上的位置)
# side: "front" 正面 / "back" 背面；position: "left" 左页 / "right" 右页


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
