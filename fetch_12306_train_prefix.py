#!/usr/bin/env python3
"""提取 12306 全国铁路列车车次编排公告中的新旧车次对应关系。

页面把完整数据打包在前端 JavaScript 中，查询时仅在浏览器本地匹配。
本脚本只下载公开页面及其公开脚本，不枚举车次、不调用查询接口。

使用方法：
    python3 fetch_12306_train_prefix.py
    python3 fetch_12306_train_prefix.py --output train_prefix_data.json
    python3 fetch_12306_train_prefix.py --output data.json --csv data.csv

输出为 UTF-8 JSON，包含来源元数据、校验信息和完整记录；
加上 --csv 时会同时导出一份纯数据 CSV（UTF-8 无 BOM，行序与 JSON 一致）。
仅使用 Python 标准库，无需安装第三方依赖。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PAGE_URL = (
    "https://mobile.12306.cn/otsmobile/h5/otsbussiness/"
    "trainPrefix/trainPrefix.html?tab=t2"
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TRAIN_CODE_RE = re.compile(r"[A-Z]{0,2}\d{1,5}")
EXPORT_ARRAY_RE = re.compile(
    r"\b[A-Za-z_$][\w$]*\.exports\s*=\s*(?=\[\[)"
)


class ScriptParser(HTMLParser):
    """收集 HTML 中的外部脚本地址。"""

    def __init__(self) -> None:
        super().__init__()
        self.script_sources: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "script":
            return
        for key, value in attrs:
            if key.lower() == "src" and value:
                self.script_sources.append(value)


def fetch_text(url: str, timeout: int = 30, retries: int = 3) -> tuple[str, bytes]:
    """下载文本，同时对临时网络错误进行有限次重试。"""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/javascript,*/*;q=0.8",
                    "Referer": PAGE_URL,
                },
            )
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset), raw
        except Exception as error:  # 网络异常统一在最后报告
            last_error = error
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"下载失败：{url}") from last_error


def find_business_script(page_html: str, page_url: str) -> str:
    """找到 trainPrefix 业务脚本，而不是 common 公共脚本。"""
    parser = ScriptParser()
    parser.feed(page_html)
    candidates = [
        urljoin(page_url, source)
        for source in parser.script_sources
        if "trainPrefix" in source and source.lower().endswith(".js")
    ]
    if len(candidates) != 1:
        raise ValueError(
            "无法唯一确定车次业务脚本，页面结构可能已更新："
            + repr(candidates)
        )
    return candidates[0]


def is_train_mapping(candidate: Any) -> bool:
    """判断候选数组是否为四字段的新旧车次对应关系。"""
    if not isinstance(candidate, list) or not candidate:
        return False
    valid_rows = 0
    for row in candidate:
        if not (
            isinstance(row, list)
            and len(row) == 4
            and all(isinstance(value, str) for value in row)
        ):
            continue
        if TRAIN_CODE_RE.fullmatch(row[0]) and TRAIN_CODE_RE.fullmatch(row[3]):
            valid_rows += 1
    return valid_rows == len(candidate)


def extract_mapping(javascript: str) -> list[list[str]]:
    """从 webpack 模块中静态解析 JSON 兼容的原始车次数组。"""
    decoder = json.JSONDecoder()
    candidates: list[list[list[str]]] = []
    for match in EXPORT_ARRAY_RE.finditer(javascript):
        try:
            value, _ = decoder.raw_decode(javascript, match.end())
        except json.JSONDecodeError:
            continue
        if is_train_mapping(value):
            candidates.append(value)

    if not candidates:
        raise ValueError("未找到完整车次数组；脚本结构或数据格式可能已更新")

    # 若存在其他符合结构的小数组，记录数最多者才是完整数据集。
    mapping = max(candidates, key=len)
    duplicate_candidates = [item for item in candidates if len(item) == len(mapping)]
    if len(duplicate_candidates) > 1 and any(
        item != mapping for item in duplicate_candidates
    ):
        raise ValueError("找到多个等长但内容不同的候选数组，需人工确认")
    return mapping


def build_result(
    rows: list[list[str]], page_url: str, script_url: str, script_raw: bytes
) -> dict[str, Any]:
    """保留原始行序，并生成可复核的来源元数据。"""
    records = [
        {
            "old_train": old_train,
            "origin": origin,
            "destination": destination,
            "new_train": new_train,
        }
        for old_train, origin, destination, new_train in rows
    ]
    canonical_rows = json.dumps(
        rows, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return {
        "metadata": {
            "source_page": page_url,
            "source_script": script_url,
            "retrieved_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "record_count": len(records),
            "fields": ["old_train", "origin", "destination", "new_train"],
            "source_script_sha256": hashlib.sha256(script_raw).hexdigest(),
            "mapping_rows_sha256": hashlib.sha256(canonical_rows).hexdigest(),
            "extraction_note": (
                "数据来自页面公开前端脚本中的内嵌数组；未枚举车次，未调用查询接口。"
            ),
        },
        "data": records,
    }


CSV_HEADER = ("old_train", "origin", "destination", "new_train")


def write_csv(rows: list[list[str]], path: Path) -> None:
    """导出纯数据 CSV：UTF-8 无 BOM，LF 换行，行序与 JSON 完全一致。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-url", default=PAGE_URL, help="12306 公告页面地址")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("train_prefix_data.json"),
        help="JSON 输出路径（默认：当前目录 train_prefix_data.json）",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="可选：同时导出的 CSV 路径，如 data/train_prefix_data.csv",
    )
    args = parser.parse_args()

    page_html, _ = fetch_text(args.page_url)
    script_url = find_business_script(page_html, args.page_url)
    javascript, script_raw = fetch_text(script_url)
    rows = extract_mapping(javascript)
    result = build_result(rows, args.page_url, script_url, script_raw)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"提取完成：{len(rows)} 条")
    print(f"业务脚本：{script_url}")
    print(f"输出文件：{args.output.resolve()}")

    if args.csv is not None:
        write_csv(rows, args.csv)
        print(f"CSV 文件：{args.csv.resolve()}")


if __name__ == "__main__":
    main()
