# 12306 新旧列车车次号对应关系

> 基于 Python 提取中国铁路 12306 当前发布的新旧列车车次号对应关系，提供 Excel 与 JSON 数据、来源元数据、SHA-256 完整性校验及可复现抓取脚本。

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Records: 1640](https://img.shields.io/badge/Records-1640-brightgreen.svg)

**English** · A reproducible Python extractor for China Railway 12306 old/new train number mappings, with Excel and JSON exports, provenance metadata, and SHA-256 verification.

---

## 数据快照

| 项目 | 内容 |
| --- | --- |
| 记录数 | **1,640** 条 |
| 抓取时间 | `2026-11-06T17:45:15.944853+08:00` |
| 来源页面 | [12306 车次编排公告（tab=t2）](https://mobile.12306.cn/otsmobile/h5/otsbussiness/trainPrefix/trainPrefix.html?tab=t2) |
| 业务脚本 | [trainPrefix.cc6215b.js](https://mobile.12306.cn/otsmobile/h5/otsbussiness/trainPrefix/js/trainPrefix.cc6215b.js) |
| 字段 | `old_train`、`origin`、`destination`、`new_train` |

数据来自页面公开前端脚本中的内嵌数组。抓取过程不枚举车次、不调用任何查询接口。

## 文件结构

```text
.
├── README.md
├── LICENSE
├── fetch_12306_train_prefix.py          # 可复现抓取脚本（仅标准库，无第三方依赖）
└── data
    ├── 12306_train_number_mapping.json  # 完整数据 + 来源元数据 + 校验值
    └── 12306_train_number_mapping.xlsx  # 便于人工查看的表格版本
```

## 数据格式

### JSON

顶层包含 `metadata`（来源、时间、记录数、字段、SHA-256）与 `data`（按页面原始行序排列的记录）：

```json
{
  "metadata": {
    "source_page": "https://mobile.12306.cn/.../trainPrefix.html?tab=t2",
    "source_script": "https://mobile.12306.cn/.../trainPrefix.cc6215b.js",
    "retrieved_at": "2026-11-06T17:45:15.944853+08:00",
    "record_count": 1640,
    "fields": ["old_train", "origin", "destination", "new_train"],
    "source_script_sha256": "f2664b6e…",
    "mapping_rows_sha256": "5ef8d777…",
    "extraction_note": "数据来自页面公开前端脚本中的内嵌数组；未枚举车次，未调用查询接口。"
  },
  "data": [
    { "old_train": "K3", "origin": "北京", "destination": "二连", "new_train": "V3" },
    { "old_train": "K4", "origin": "二连", "destination": "北京", "new_train": "V4" }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
| --- | --- | --- | --- |
| `old_train` | string | 变更前的车次号 | `K3` |
| `origin` | string | 始发站 | `北京` |
| `destination` | string | 终到站 | `二连` |
| `new_train` | string | 变更后的车次号 | `V3` |

### Excel

- **`车次对应关系`**：1,640 行数据，列为 `序号`、`旧车次`、`始发站`、`终到站`、`新车次`。
- **`来源与校验`**：来源链接、抓取时间、记录数、重复与空值检查结果、页面示例核验结果、SHA-256 校验值。

### 数据分布

| 维度 | 分布 |
| --- | --- |
| 旧车次号前缀 | `K` 1,067 · 无字母前缀 255 · `Z` 180 · `T` 138 |
| 新车次号前缀 | `V` 1,322 · `Z` 184 · `N` 134 |
| 车站 | 340 个始发站 · 339 个终到站 |

空字段 0 条，整行重复 0 条，旧车次重复 0 条，新车次重复 0 条。

## 快速开始

仅依赖 Python 标准库（Python 3.9+），无需 `pip install`：

```bash
git clone https://github.com/patrickxuu/12306-train-number-mapping.git
cd 12306-train-number-mapping

# 默认输出 ./train_prefix_data.json
python3 fetch_12306_train_prefix.py

# 或指定输出路径
python3 fetch_12306_train_prefix.py --output data/train_prefix_data.json
```

重新抓取会生成新的 `retrieved_at` 与 `source_script_sha256`。若页面结构或数据格式发生变化，脚本会**显式报错**，而不是静默输出空数据或不完整结果。

## 数据校验

| 对象 | SHA-256 |
| --- | --- |
| `data/12306_train_number_mapping.json`（文件） | `70c31f84e77b01ce8efbc2ef3a302fb91c9988ab8f7969bd1f6e11c73f493f1b` |
| `data/12306_train_number_mapping.xlsx`（文件） | `641e3f19b6674a2a878962396c7e6e60c1069830be5030b79a1316bdb577707b` |
| 原始对应关系数组（规范化 JSON） | `5ef8d7779ac842b13f554f2d70cb212958ec9802822a7684ef0f00a3af19014a` |
| 来源业务脚本 `trainPrefix.cc6215b.js` | `f2664b6ea160d0dc786cd99e38b48b0ee54f6f3edbde2fc421780b1048bea3e3` |

```bash
# Linux / macOS
sha256sum data/12306_train_number_mapping.json
```

```powershell
# Windows
Get-FileHash data\12306_train_number_mapping.json -Algorithm SHA256
```

其中 `mapping_rows_sha256` 针对四列原始行数组的**规范化 JSON**（UTF-8、无多余空格）计算，与输出文件的排版无关；重新运行脚本并比对 `metadata` 中的该值即可确认数据未被篡改。

## 抓取原理

1. 请求公告页面，从 HTML 中解析出唯一的 `trainPrefix*.js` 业务脚本地址（排除 `common` 公共脚本）。
2. 下载脚本，静态定位 `X.exports = [[...]]` 形式的数组，用 `json.JSONDecoder.raw_decode` 直接解析，不执行页面 JavaScript。
3. 逐行校验：必须为四元素字符串数组，首尾字段匹配车次号规则 `[A-Z]{0,2}\d{1,5}`；存在多个候选时取记录数最多者，若等长候选内容冲突则报错要求人工确认。
4. 保留页面原始行序，写入 JSON 时附上来源元数据与两级 SHA-256。

整个过程只读取公开页面与公开脚本，不使用浏览器自动化，不触发任何查询接口。

## 数据范围与限制

- 当前数据为页面已发布的**第一批（普速旅客列车）**变更；高速、动集、城际、市郊等第二批变更不在其中。
- 车次变更及开行信息以 **12306 最终运行图**为准，本数据集仅作快照参考。
- 数据会随 12306 页面更新而变化，请以 `retrieved_at` 自行判断时效。

## 许可与免责声明

- 本仓库的**代码**以 [MIT License](LICENSE) 授权。
- 数据内容来自中国铁路 12306 公开网页，相关权利归原发布方所有；本仓库仅作技术研究与数据整理示例，请遵守来源网站的服务条款，勿用于商业用途或高频抓取。

---

## English

A reproducible extractor for China Railway 12306 old/new train number mappings.

**What's included**

- `data/12306_train_number_mapping.json` — 1,640 records with provenance metadata and SHA-256 checksums.
- `data/12306_train_number_mapping.xlsx` — same dataset as a readable workbook with a dedicated provenance sheet.
- `fetch_12306_train_prefix.py` — a standard-library-only Python script that re-derives the dataset from the public page and its public business script.

**Usage**

```bash
python3 fetch_12306_train_prefix.py --output train_prefix_data.json
```

**How it works** — the page ships the full mapping table inside a front-end bundle, so the script parses the public JavaScript array statically (no browser automation, no query API calls), validates every row, preserves source order, and records both the script hash and the mapping hash.

**Verification** — recompute the canonical row array's SHA-256, or check the published file hashes, to confirm integrity. See the checksum table above.

**Notes** — the dataset reflects the first batch currently published by 12306 (conventional passenger trains). New numberings for high-speed, EMU, intercity and suburban services are not included. Always defer to the official 12306 timetable.

**License** — code under MIT; the underlying data belongs to China Railway 12306 and is provided here for research and educational reference only.
