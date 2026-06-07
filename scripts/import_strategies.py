from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.db import init_db, transaction


PDF_DIR = Path("/Users/remy/Library/Mobile Documents/com~apple~CloudDocs/Book/PMP")


@dataclass(frozen=True)
class StrategyItem:
    exam_code: str
    category: str
    title: str
    summary: str
    question_numbers: tuple[int, ...]
    source_file: str
    sort_order: int


SECTION_NAMES = {
    "通用思路",
    "团队管理",
    "干系人管理",
    "三大基准管理",
    "质量管理",
    "风险管理",
    "沟通管理",
    "采购管理",
    "敏捷管理",
    "直接考考纲原文",
}


SECTION_ALIASES = {
    "预测/三大基准管理": "三大基准管理",
}


def extract_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"南京卓而越.*\n", "", text)
    text = re.sub(r"全国免费咨询电话.*\n", "", text)
    text = re.sub(r"版权所有.*\n", "", text)
    text = re.sub(r"===== PAGE \\d+ =====", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def parse_numbers(value: str) -> tuple[int, ...]:
    nums = [int(item) for item in re.findall(r"\d{1,3}", value)]
    result: list[int] = []
    seen: set[int] = set()
    for number in nums:
        if 1 <= number <= 180 and number not in seen:
            result.append(number)
            seen.add(number)
    return tuple(result)


def normalize_title(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    value = value.strip("。；;，,：:")
    return value


def split_title_and_numbers(value: str) -> tuple[str, tuple[int, ...]]:
    matches = list(re.finditer(r"[（(]([^（）()]*\d[^（）()]*)[）)]", value))
    if not matches:
        return value, ()
    number_match = matches[-1]
    return value[: number_match.start()], parse_numbers(number_match.group(1))


def parse_summary_pdf(exam_code: str, path: Path) -> list[StrategyItem]:
    text = clean_text(extract_text(path))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items: list[StrategyItem] = []
    category = "通用思路"
    buffer = ""
    order = 0

    def flush() -> None:
        nonlocal buffer, order
        if not buffer:
            return
        content = re.sub(r"^\d+\.\s*", "", buffer)
        title, numbers = split_title_and_numbers(content)
        if not numbers:
            buffer = ""
            return
        title = normalize_title(title)
        if title:
            order += 1
            items.append(
                StrategyItem(
                    exam_code=exam_code,
                    category=category,
                    title=title,
                    summary=title,
                    question_numbers=numbers,
                    source_file=path.name,
                    sort_order=order,
                )
            )
        buffer = ""

    for line in lines:
        section_name = SECTION_ALIASES.get(line, line)
        if section_name in SECTION_NAMES:
            flush()
            category = section_name
            continue
        if re.match(r"^\d+\.\s*", line):
            flush()
            buffer = line
        elif buffer:
            buffer += line
    flush()
    return items


def parse_sim9_10_pdf(path: Path) -> list[StrategyItem]:
    items: list[StrategyItem] = []
    category = "其他"
    order = 0
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or len(row) < 4:
                        continue
                    raw_category, raw_title, raw_sim9, raw_sim10 = [(cell or "").strip() for cell in row[:4]]
                    if raw_category in {"套路", "南京卓而越"} or "模拟九题目" in raw_title:
                        continue
                    if raw_category:
                        category = normalize_title(raw_category)
                    title = normalize_title(raw_title)
                    if not title:
                        continue
                    for exam_code, number_text in (("sim9", raw_sim9), ("sim10", raw_sim10)):
                        numbers = parse_numbers(number_text)
                        if not numbers:
                            continue
                        order += 1
                        items.append(
                            StrategyItem(
                                exam_code=exam_code,
                                category=category,
                                title=title,
                                summary=title,
                                question_numbers=numbers,
                                source_file=path.name,
                                sort_order=order,
                            )
                        )
    return items


def question_id_map(conn) -> dict[tuple[str, int], int]:
    rows = conn.execute(
        """
        SELECT e.code, q.number, q.id
        FROM questions q
        JOIN exams e ON e.id = q.exam_id
        WHERE q.deleted_at IS NULL
        """
    ).fetchall()
    return {(row["code"], int(row["number"])): int(row["id"]) for row in rows}


def import_items(items: list[StrategyItem]) -> dict[str, int]:
    init_db()
    with transaction() as conn:
        conn.execute("DELETE FROM strategy_question_links")
        conn.execute("DELETE FROM strategies")
        qids = question_id_map(conn)
        linked = 0
        skipped = 0
        for item in items:
            conn.execute(
                """
                INSERT INTO strategies (exam_code, category, title, summary, source_file, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(exam_code, category, title) DO UPDATE SET
                    summary = excluded.summary,
                    source_file = excluded.source_file,
                    sort_order = excluded.sort_order,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (item.exam_code, item.category, item.title, item.summary, item.source_file, item.sort_order),
            )
            strategy_id = int(
                conn.execute(
                    "SELECT id FROM strategies WHERE exam_code = ? AND category = ? AND title = ?",
                    (item.exam_code, item.category, item.title),
                ).fetchone()["id"]
            )
            for number in item.question_numbers:
                question_id = qids.get((item.exam_code, number))
                if not question_id:
                    skipped += 1
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO strategy_question_links (strategy_id, question_id)
                    VALUES (?, ?)
                    """,
                    (strategy_id, question_id),
                )
                linked += 1
        counts = {
            "strategies": conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0],
            "links": conn.execute("SELECT COUNT(*) FROM strategy_question_links").fetchone()[0],
            "skipped": skipped,
        }
        for row in conn.execute(
            """
            SELECT exam_code, COUNT(*) AS strategies
            FROM strategies
            GROUP BY exam_code
            ORDER BY exam_code
            """
        ):
            counts[f"{row['exam_code']}_strategies"] = row["strategies"]
        return counts


def main() -> None:
    items: list[StrategyItem] = []
    items.extend(parse_summary_pdf("sim7", PDF_DIR / "PMP模拟七主要解题思路总结.pdf"))
    items.extend(parse_summary_pdf("sim8", PDF_DIR / "PMP模拟八主要解题思路总结.pdf"))
    items.extend(parse_sim9_10_pdf(PDF_DIR / "模拟九-模拟十题目分类.pdf"))
    counts = import_items(items)
    print(counts)


if __name__ == "__main__":
    main()
