from __future__ import annotations

import re
import os
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from .auth import create_initial_admin, hash_password
from .db import init_db, transaction
from .utils import is_answer_correct, normalize_correct_answer


SOURCE_DIR = Path("/Users/remy/Desktop/PMP学习")


@dataclass(frozen=True)
class ExamSource:
    code: str
    title: str
    markdown: Path
    excel: Path


EXAMS = [
    ExamSource("sim7", "PMP 仿真模拟试题七", SOURCE_DIR / "7模拟7题目.md", SOURCE_DIR / "PMP模拟七_阅卷结果.xlsx"),
    ExamSource("sim8", "PMP 仿真模拟试题八", SOURCE_DIR / "8模拟8题目.md", SOURCE_DIR / "PMP模拟八_阅卷结果.xlsx"),
    ExamSource("sim9", "PMP 仿真模拟试题九", SOURCE_DIR / "9模拟9题目.md", SOURCE_DIR / "PMP模拟九_阅卷结果.xlsx"),
    ExamSource("sim10", "PMP 仿真模拟试题十", SOURCE_DIR / "10模拟10题目.md", SOURCE_DIR / "PMP模拟十_阅卷结果.xlsx"),
]


OPTION_RE = re.compile(r"(?m)^([A-F])\.\s*(.+?)(?:\s{2,})?$")


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def detect_multi_from_stem(stem: str, correct_answer: str) -> bool:
    if len(re.findall(r"[A-F]", correct_answer.split("/")[0])) > 1:
        return True
    return bool(re.search(r"选择[两二三四五六]项|选择\s*\d+\s*项|哪[两二三四五六]项", stem))


def clean_markdown_text(text: str) -> str:
    text = re.sub(r"\s*  $", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_question_block(number: int, block: str) -> dict:
    option_matches = list(OPTION_RE.finditer(block))
    if not option_matches:
        raise ValueError(f"Question {number} has no options")

    stem = block[: option_matches[0].start()].strip()
    options = []
    for idx, match in enumerate(option_matches):
        label = match.group(1)
        start = match.end(2)
        end = option_matches[idx + 1].start() if idx + 1 < len(option_matches) else len(block)
        text = (match.group(2) + block[start:end]).strip()
        text = re.sub(r"\n+", "\n", text).strip()
        options.append({"label": label, "text": text})

    return {
        "number": number,
        "stem": clean_markdown_text(stem),
        "options": options,
    }


def parse_bold_number_markdown(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^\*\*(\d+)\.?\s*(.*?)\*\*")
    starts = list(pattern.finditer(text))
    if len(starts) != 180:
        raise ValueError(f"{path.name}: expected 180 bold questions, got {len(starts)}")

    questions = []
    for idx, match in enumerate(starts):
        number = int(match.group(1))
        first_line = match.group(2).strip()
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        line_end = text.find("\n", match.end())
        if line_end == -1 or line_end > end:
            line_end = end
        rest_of_line = text[match.end():line_end].strip()
        block = f"{first_line} {rest_of_line}\n{text[line_end:end]}".strip()
        questions.append(parse_question_block(number, block))
    return questions


def parse_heading_markdown(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^##\s*第\s*(\d+)\s*题\s*$")
    starts = list(pattern.finditer(text))
    if len(starts) != 180:
        raise ValueError(f"{path.name}: expected 180 heading questions, got {len(starts)}")

    questions = []
    for idx, match in enumerate(starts):
        number = int(match.group(1))
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        block = text[match.end():end]
        questions.append(parse_question_block(number, block))
    return questions


def parse_markdown(source: ExamSource) -> dict[int, dict]:
    if source.code == "sim8":
        questions = parse_heading_markdown(source.markdown)
    else:
        questions = parse_bold_number_markdown(source.markdown)
    by_number = {q["number"]: q for q in questions}
    missing = [number for number in range(1, 181) if number not in by_number]
    if missing:
        raise ValueError(f"{source.markdown.name}: missing questions {missing}")
    return by_number


def header_map(ws) -> dict[str, int]:
    headers = {}
    for idx, cell in enumerate(ws[1], start=1):
        if cell.value is not None:
            headers[str(cell.value).strip()] = idx
    return headers


def find_column(headers: dict[str, int], names: list[str]) -> int | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def parse_excel(path: Path) -> dict[int, dict]:
    workbook = load_workbook(path, data_only=True)
    if "阅卷结果" not in workbook.sheetnames:
        raise ValueError(f"{path.name}: missing sheet 阅卷结果")
    ws = workbook["阅卷结果"]
    headers = header_map(ws)
    number_col = find_column(headers, ["题号"])
    user_col = find_column(headers, ["我的答案", "你的答案"])
    answer_col = find_column(headers, ["正确答案", "标准答案"])
    judgement_col = find_column(headers, ["判定"])
    note_col = find_column(headers, ["我的备注", "你的备注"])
    extra_note_col = find_column(headers, ["附加备注", "解题思路"])
    explanation_col = find_column(headers, ["答案解析", "标准答案解析"])

    required = {
        "题号": number_col,
        "正确答案/标准答案": answer_col,
        "答案解析/标准答案解析": explanation_col,
    }
    missing = [name for name, col in required.items() if col is None]
    if missing:
        raise ValueError(f"{path.name}: missing required columns {missing}; headers={list(headers)}")

    rows = {}
    for row_idx in range(2, ws.max_row + 1):
        number_value = ws.cell(row_idx, number_col).value
        if number_value is None:
            continue
        number = int(number_value)
        note_parts = []
        if note_col:
            note_parts.append(normalize_text(ws.cell(row_idx, note_col).value))
        if extra_note_col:
            note_parts.append(normalize_text(ws.cell(row_idx, extra_note_col).value))
        rows[number] = {
            "user_answer": normalize_correct_answer(ws.cell(row_idx, user_col).value) if user_col else "",
            "correct_answer": normalize_correct_answer(ws.cell(row_idx, answer_col).value),
            "judgement": normalize_text(ws.cell(row_idx, judgement_col).value) if judgement_col else "",
            "note": "\n".join(part for part in note_parts if part),
            "explanation": normalize_text(ws.cell(row_idx, explanation_col).value),
        }
    missing_numbers = [number for number in range(1, 181) if number not in rows]
    if missing_numbers:
        raise ValueError(f"{path.name}: missing answer rows {missing_numbers}")
    return rows


def ensure_import_user(conn) -> int:
    username = os.getenv("IMPORT_OWNER_USERNAME") or os.getenv("FIRST_ADMIN_USERNAME") or "remy"
    display_name = os.getenv("IMPORT_OWNER_DISPLAY_NAME") or os.getenv("FIRST_ADMIN_DISPLAY_NAME") or username
    password = os.getenv("IMPORT_OWNER_PASSWORD") or os.getenv("FIRST_ADMIN_PASSWORD") or "change-me-now"
    row = conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
    if row:
        return int(row["id"])
    created = conn.execute(
        """
        INSERT INTO users (username, display_name, password_hash, role, is_active)
        VALUES (%s, %s, %s, 'admin', 1)
        RETURNING id
        """,
        (username, display_name, hash_password(password)),
    ).fetchone()
    return int(created["id"])


def upsert_exam(conn, source: ExamSource) -> int:
    conn.execute(
        """
        INSERT INTO exams (code, title, source_markdown, source_excel, updated_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT(code) DO UPDATE SET
            title = excluded.title,
            source_markdown = excluded.source_markdown,
            source_excel = excluded.source_excel,
            updated_at = CURRENT_TIMESTAMP
        """,
        (source.code, source.title, str(source.markdown), str(source.excel)),
    )
    row = conn.execute("SELECT id FROM exams WHERE code = %s", (source.code,)).fetchone()
    return int(row["id"])


def upsert_question(conn, user_id: int, exam_id: int, question: dict, answer: dict) -> int:
    correct_answer = answer["correct_answer"]
    is_multi = detect_multi_from_stem(question["stem"], correct_answer)
    conn.execute(
        """
        INSERT INTO questions (
            exam_id, number, stem, is_multi, correct_answer, explanation,
            imported_user_answer, imported_judgement, imported_note, deleted_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, CURRENT_TIMESTAMP)
        ON CONFLICT(exam_id, number) DO UPDATE SET
            stem = excluded.stem,
            is_multi = excluded.is_multi,
            correct_answer = excluded.correct_answer,
            explanation = excluded.explanation,
            imported_user_answer = excluded.imported_user_answer,
            imported_judgement = excluded.imported_judgement,
            imported_note = excluded.imported_note,
            deleted_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            exam_id,
            question["number"],
            question["stem"],
            int(is_multi),
            correct_answer,
            answer["explanation"],
            answer["user_answer"],
            answer["judgement"],
            answer["note"],
        ),
    )
    row = conn.execute(
        "SELECT id FROM questions WHERE exam_id = %s AND number = %s",
        (exam_id, question["number"]),
    ).fetchone()
    question_id = int(row["id"])

    conn.execute("DELETE FROM options WHERE question_id = %s", (question_id,))
    for option in question["options"]:
        conn.execute(
            "INSERT INTO options (question_id, label, text) VALUES (%s, %s, %s)",
            (question_id, option["label"], option["text"]),
        )

    if answer["user_answer"]:
        imported_correct = is_answer_correct(answer["user_answer"], correct_answer)
        conn.execute(
            """
            INSERT INTO attempts (user_id, question_id, mode, selected_answer, is_correct)
            SELECT %s, %s, 'imported_exam_result', %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM attempts
                WHERE user_id = %s AND question_id = %s AND mode = 'imported_exam_result'
            )
            """,
            (user_id, question_id, answer["user_answer"], int(imported_correct), user_id, question_id),
        )

    if answer["judgement"] == "错误":
        conn.execute(
            """
            INSERT INTO wrong_items (user_id, question_id, active, source, added_at, learned_at, updated_at)
            VALUES (%s, %s, 1, 'import', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                active = CASE WHEN wrong_items.learned_at IS NULL THEN 1 ELSE wrong_items.active END,
                source = CASE WHEN wrong_items.learned_at IS NULL THEN 'import' ELSE wrong_items.source END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, question_id),
        )
    return question_id


def import_all() -> dict:
    init_db()
    create_initial_admin()
    summary = {}
    with transaction() as conn:
        user_id = ensure_import_user(conn)
        for source in EXAMS:
            markdown_questions = parse_markdown(source)
            excel_answers = parse_excel(source.excel)
            exam_id = upsert_exam(conn, source)
            imported = 0
            for number in range(1, 181):
                upsert_question(conn, user_id, exam_id, markdown_questions[number], excel_answers[number])
                imported += 1
            summary[source.code] = imported

        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS questions,
                (SELECT COUNT(*) FROM options) AS options,
                (SELECT COUNT(*) FROM wrong_items WHERE user_id = %s AND active = 1) AS active_wrong,
                (SELECT COUNT(*) FROM attempts) AS attempts
            FROM questions
            WHERE deleted_at IS NULL
            """,
            (user_id,),
        ).fetchone()
        summary["totals"] = dict(totals)
    return summary


if __name__ == "__main__":
    print(import_all())
