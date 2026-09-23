# 离线小册子拼版 API（Python / FastAPI）

按**帖（signature）**对小册子进行拼版：输入总页数、每帖最多纸张数和装订方向（左/右），
按纸张**从外到内**返回每帖各张纸正反面的左右页码。空白页用 `null` 表示。

提供两个拼版接口：

- `POST /api/v1/impose`：按固定容量顺序分帖（仅末帖补白）；
- `POST /api/v1/impose/chapters`：提供**各章首页页码**，章节不跨帖、相邻章节可合帖，
  按“补白总数最少 → 帖数最少 → 最早边界优先”自动选择分帖边界。

## 一条命令启动

需要安装 Docker（含 Compose 插件），在项目根目录执行：

```bash
docker compose up -d --build
```

该命令会自动完成：构建镜像 → 安装全部依赖 → 启动 API（容器内 uvicorn 直接拉起，无数据库等额外初始化步骤）。

停止 / 查看日志：

```bash
docker compose down        # 停止
docker compose logs -f     # 查看日志
```

## 必要配置

默认无需任何配置。唯一可选配置是**宿主机端口**（容器内固定 8000）：

```bash
HOST_PORT=9000 docker compose up -d --build
```

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST_PORT` | `8000` | 宿主机暴露端口，通过环境变量覆盖；容器内端口固定为 `8000` |

服务完全离线运行，不连接任何外部服务。

## API 地址与端口

服务通过 Docker Compose 一键启动（见上文），默认监听宿主机 **8000** 端口
（容器内固定为 `8000`）：

- 服务地址：`http://localhost:8000`（改了 `HOST_PORT` 则对应替换端口）
- 健康检查：`GET http://localhost:8000/health`
- 交互式文档（Swagger UI）：`http://localhost:8000/docs`
- 常规拼版接口：`POST http://localhost:8000/api/v1/impose`
- 章节拼版接口：`POST http://localhost:8000/api/v1/impose/chapters`

## 接口说明

### 请求

`POST /api/v1/impose`，`Content-Type: application/json`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `total_pages` | 整数 | ≥ 1 | 总页数（正整数） |
| `max_sheets_per_signature` | 整数 | ≥ 1 | 每帖最多纸张数；每帖最多容纳其 **4 倍**页数 |
| `binding` | 字符串 | `left` / `right` | 装订方向：左装订 / 右装订 |

```bash
curl -X POST http://localhost:8000/api/v1/impose \
  -H "Content-Type: application/json" \
  -d '{"total_pages": 16, "max_sheets_per_signature": 4, "binding": "left"}'
```

### 响应

返回帖号 `signature_index` 与帖内纸张序号 `sheet_index`（从 1 开始，1 为最外张），
以及每张纸正面 `front` / 背面 `back` 的左 `left` / 右 `right` 页码；空白页为 `null`。

```json
{
  "total_pages": 16,
  "max_sheets_per_signature": 4,
  "binding": "left",
  "signature_count": 1,
  "signatures": [
    {
      "signature_index": 1,
      "sheet_count": 4,
      "page_count_padded": 16,
      "sheets": [
        {
          "sheet_index": 1,
          "front": { "left": 16, "right": 1 },
          "back":  { "left": 2,  "right": 15 }
        },
        {
          "sheet_index": 2,
          "front": { "left": 14, "right": 3 },
          "back":  { "left": 4,  "right": 13 }
        }
      ]
    }
  ]
}
```

> 实际响应会列出全部 4 张纸，上例只展示前 2 张。

### 拼版规则

1. 按原页顺序分帖，每帖最多容纳 `4 × max_sheets_per_signature` 页；除末帖外各帖均装满。
2. 仅**末帖**在尾部补空白页至 4 的倍数，空白位置页码为 `null`。
3. 左装订（`left`）最外张：
   - 正面（`front`）：左 = 末页，右 = 首页；
   - 背面（`back`）：左 = 次页，右 = 倒数第二页；
   - 之后逐张向内递推（帖页数为 `n`，纸张从外向内序号为 `k = 0,1,2...`，四个页位在帖内的位置索引从 0 计分别为：正左 `n-1-2k`、正右 `2k`、背左 `2k+1`、背右 `n-2-2k`，取出的即为该位置的全局页码，补齐位置为 `null`）。
4. 右装订（`right`）为镜像装订：将左装订结果的**左右页位整体交换**（正反关系不变）。

### 非法参数（4xx）

参数缺失、类型错误、`total_pages` / `max_sheets_per_signature` 小于 1、`binding` 不是
`left`/`right`、包含未定义字段时，均返回 `422 Unprocessable Entity`：

```json
{
  "detail": [
    { "type": "greater_than_equal", "loc": ["body", "total_pages"], "msg": "Input should be greater than or equal to 1" }
  ]
}
```

## 章节拼版接口

### 请求

`POST /api/v1/impose/chapters`，`Content-Type: application/json`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `total_pages` | 整数 | ≥ 1 | 总页数（正整数） |
| `max_sheets_per_signature` | 整数 | ≥ 1 | 每帖最多纸张数；每帖最多容纳其 **4 倍**页数 |
| `binding` | 字符串 | `left` / `right` | 装订方向：左装订 / 右装订 |
| `chapter_first_pages` | 整数数组 | 非空、**严格递增**、首项为 `1`、各项 ≤ `total_pages` | 各章节首页的页码 |

约束与分帖规则：

1. **章节不可跨帖**：每个章节必须完整落在同一帖内；相邻章节可以合入同一帖。
2. 每帖页数（含补白）不超过 `4 × max_sheets_per_signature`，即纸张数不超过上限。
3. 每个帖分别在**尾部补空白页**至 4 的倍数，帖内正反面页码排列复用常规拼版规则。
4. 在所有可行分帖方案中依次择优：
   ① 各帖补至 4 的倍数所需**空白总数最少**；
   ② 空白总数相同时**帖数最少**；
   ③ 仍相同时优先**最早的分帖边界**（尽量提前切分）。
5. 若某个章节自身页数已超过单帖容量（`4 × max_sheets_per_signature`），无法在不跨帖的
   前提下拼版，返回 `422 Unprocessable Entity`。

```bash
curl -X POST http://localhost:8000/api/v1/impose/chapters \
  -H "Content-Type: application/json" \
  -d '{
    "total_pages": 10,
    "max_sheets_per_signature": 2,
    "binding": "left",
    "chapter_first_pages": [1, 2, 7]
  }'
```

上例共 10 页、每帖最多 2 张纸（8 页容量），三章分别从第 1、2、7 页开始（章长 1/5/4 页）。
第 1、2 章合为一帖（6 页补 2 空白），第 3 章单独一帖（4 页无需补白）：

```json
{
  "total_pages": 10,
  "max_sheets_per_signature": 2,
  "binding": "left",
  "chapter_first_pages": [1, 2, 7],
  "signature_count": 2,
  "signatures": [
    {
      "signature_index": 1,
      "sheet_count": 2,
      "page_count_padded": 8,
      "start_page": 1,
      "end_page": 6,
      "blank_count": 2,
      "sheets": [
        {
          "sheet_index": 1,
          "front": { "left": null, "right": 1 },
          "back":  { "left": 2,    "right": null }
        },
        {
          "sheet_index": 2,
          "front": { "left": 6, "right": 3 },
          "back":  { "left": 4, "right": 5 }
        }
      ]
    },
    {
      "signature_index": 2,
      "sheet_count": 1,
      "page_count_padded": 4,
      "start_page": 7,
      "end_page": 10,
      "blank_count": 0,
      "sheets": [
        {
          "sheet_index": 1,
          "front": { "left": 10, "right": 7 },
          "back":  { "left": 8,  "right": 9 }
        }
      ]
    }
  ]
}
```

### 响应

`sheets` 的页位结构与常规接口完全一致（左装订 / 右装订规则相同），每个帖额外给出：

| 字段 | 说明 |
| --- | --- |
| `start_page` | 本帖原页起始页码 |
| `end_page` | 本帖原页结束页码（不含尾部空白） |
| `blank_count` | 本帖尾部补齐至 4 的倍数所用的空白页数 |

### 非法参数（4xx）

除与常规接口相同的参数校验外，`chapter_first_pages` 为空、首项不为 `1`、未严格递增、
页码超过 `total_pages`，或某章页数超过单帖容量时，均返回 `422 Unprocessable Entity`。
超长章节的响应示例：

```json
{
  "detail": "第 1 章共 12 页，超过单帖容量 8 页"
}
```

## 本地开发（不使用 Docker）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest -q
```

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── imposition.py   # 拼版核心算法（分帖 + 帖内拼版）
│   └── main.py         # FastAPI 路由与参数校验
├── tests/              # 算法与 API 测试（pytest）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```
