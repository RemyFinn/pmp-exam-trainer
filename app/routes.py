from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .db import transaction
from .models import (
    AttemptIn,
    AttemptCountPatch,
    AttemptOut,
    ExamOut,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    StrategyLinkOut,
    StrategyOut,
    StrategyQuestionOut,
    WrongCountPatch,
    WrongItemPatch,
)
from .utils import is_answer_correct, normalize_answer, normalize_correct_answer

router = APIRouter(prefix="/api")


QUESTION_STATS_SQL = """
    SELECT question_id,
           COUNT(*) AS attempt_count,
           SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS raw_wrong_count,
           MAX(CASE WHEN is_correct = 0 THEN created_at ELSE NULL END) AS last_wrong_at
    FROM attempts
    GROUP BY question_id
"""


def fetch_question(conn, question_id: int) -> dict:
    row = conn.execute(
        f"""
        SELECT q.*, e.code AS exam_code, e.title AS exam_title,
               COALESCE(w.active, 0) AS is_wrong_active,
               MAX(0, COALESCE(s.raw_wrong_count, 0) + COALESCE(w.wrong_count_delta, 0)) AS wrong_count,
               MAX(0, COALESCE(s.attempt_count, 0) + COALESCE(w.attempt_count_delta, 0)) AS attempt_count,
               s.last_wrong_at AS last_wrong_at
        FROM questions q
        JOIN exams e ON e.id = q.exam_id
        LEFT JOIN wrong_items w ON w.question_id = q.id
        LEFT JOIN ({QUESTION_STATS_SQL}) s ON s.question_id = q.id
        WHERE q.id = ? AND q.deleted_at IS NULL
        """,
        (question_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return dict(row)


def fetch_options(conn, question_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, label, text FROM options WHERE question_id = ? ORDER BY label",
        (question_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_question_strategies(conn, question_id: int) -> list[StrategyLinkOut]:
    rows = conn.execute(
        """
        SELECT s.id, s.exam_code, s.category, s.title, s.summary
        FROM strategies s
        JOIN strategy_question_links l ON l.strategy_id = s.id
        WHERE l.question_id = ?
        ORDER BY s.sort_order, s.category, s.id
        """,
        (question_id,),
    ).fetchall()
    return [StrategyLinkOut(**dict(row)) for row in rows]


def build_question(conn, row: dict) -> QuestionOut:
    return QuestionOut(
        id=row["id"],
        exam_code=row["exam_code"],
        exam_title=row["exam_title"],
        number=row["number"],
        stem=row["stem"],
        is_multi=bool(row["is_multi"]),
        correct_answer=row["correct_answer"],
        explanation=row["explanation"],
        imported_user_answer=row["imported_user_answer"] or "",
        imported_judgement=row["imported_judgement"] or "",
        imported_note=row["imported_note"] or "",
        is_wrong_active=bool(row["is_wrong_active"]),
        wrong_count=int(row.get("wrong_count") or 0),
        attempt_count=int(row.get("attempt_count") or 0),
        last_wrong_at=row.get("last_wrong_at"),
        strategies=fetch_question_strategies(conn, row["id"]),
        options=fetch_options(conn, row["id"]),
    )


@router.get("/exams", response_model=list[ExamOut])
def list_exams() -> list[ExamOut]:
    with transaction() as conn:
        rows = conn.execute(
            f"""
            SELECT e.id, e.code, e.title,
                   COUNT(q.id) AS total_questions,
                   COUNT(CASE WHEN COALESCE(w.active, 0) = 1 THEN q.id END) AS wrong_questions,
                   COALESCE(SUM(MAX(0, COALESCE(s.attempt_count, 0) + COALESCE(w.attempt_count_delta, 0))), 0) AS attempts
            FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id AND q.deleted_at IS NULL
            LEFT JOIN wrong_items w ON w.question_id = q.id
            LEFT JOIN ({QUESTION_STATS_SQL}) s ON s.question_id = q.id
            GROUP BY e.id
            ORDER BY e.code
            """
        ).fetchall()
        return [ExamOut(**dict(row)) for row in rows]


@router.get("/questions", response_model=list[QuestionOut])
def list_questions(
    mode: str = Query("mixed", pattern="^(exam|mixed|wrong|admin)$"),
    exam: str | None = None,
    shuffle: bool = False,
    search: str | None = None,
) -> list[QuestionOut]:
    where = ["q.deleted_at IS NULL"]
    params: list[object] = []

    if mode == "exam":
        if not exam:
            raise HTTPException(status_code=400, detail="exam is required for exam mode")
        where.append("e.code = ?")
        params.append(exam)
    elif mode == "wrong":
        where.append("COALESCE(w.active, 0) = 1")
        if exam:
            where.append("e.code = ?")
            params.append(exam)

    if search:
        where.append("(q.stem LIKE ? OR q.explanation LIKE ? OR q.correct_answer LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    if shuffle:
        order_by = "RANDOM()"
    elif mode == "wrong":
        order_by = "wrong_count DESC, last_wrong_at DESC, e.code, q.number"
    else:
        order_by = "e.code, q.number"

    sql = f"""
        SELECT q.*, e.code AS exam_code, e.title AS exam_title,
               COALESCE(w.active, 0) AS is_wrong_active,
               MAX(0, COALESCE(s.raw_wrong_count, 0) + COALESCE(w.wrong_count_delta, 0)) AS wrong_count,
               MAX(0, COALESCE(s.attempt_count, 0) + COALESCE(w.attempt_count_delta, 0)) AS attempt_count,
               s.last_wrong_at AS last_wrong_at
        FROM questions q
        JOIN exams e ON e.id = q.exam_id
        LEFT JOIN wrong_items w ON w.question_id = q.id
        LEFT JOIN ({QUESTION_STATS_SQL}) s ON s.question_id = q.id
        WHERE {" AND ".join(where)}
        ORDER BY {order_by}
    """

    with transaction() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [build_question(conn, dict(row)) for row in rows]


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(exam: str | None = None, search: str | None = None) -> list[StrategyOut]:
    where: list[str] = []
    params: list[object] = []
    if exam:
        where.append("s.exam_code = ?")
        params.append(exam)
    if search:
        where.append("(s.category LIKE ? OR s.title LIKE ? OR s.summary LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    sql = """
        SELECT s.id, s.exam_code, s.category, s.title, s.summary, s.source_file, s.sort_order
        FROM strategies s
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += """
        ORDER BY CASE s.exam_code
            WHEN 'sim7' THEN 1
            WHEN 'sim8' THEN 2
            WHEN 'sim9' THEN 3
            WHEN 'sim10' THEN 4
            ELSE 99
        END, s.sort_order, s.category, s.id
    """

    with transaction() as conn:
        rows = conn.execute(sql, params).fetchall()
        result: list[StrategyOut] = []
        for row in rows:
            strategy = StrategyOut(**dict(row))
            qrows = conn.execute(
                """
                SELECT q.id, e.code AS exam_code, q.number, q.stem,
                       COALESCE(w.active, 0) AS is_wrong_active
                FROM strategy_question_links l
                JOIN questions q ON q.id = l.question_id AND q.deleted_at IS NULL
                JOIN exams e ON e.id = q.exam_id
                LEFT JOIN wrong_items w ON w.question_id = q.id
                WHERE l.strategy_id = ?
                ORDER BY CASE e.code
                    WHEN 'sim7' THEN 1
                    WHEN 'sim8' THEN 2
                    WHEN 'sim9' THEN 3
                    WHEN 'sim10' THEN 4
                    ELSE 99
                END, q.number
                """,
                (strategy.id,),
            ).fetchall()
            strategy.questions = [StrategyQuestionOut(**dict(qrow)) for qrow in qrows]
            result.append(strategy)
        return result


@router.get("/questions/{question_id}", response_model=QuestionOut)
def get_question(question_id: int) -> QuestionOut:
    with transaction() as conn:
        return build_question(conn, fetch_question(conn, question_id))


@router.post("/attempts", response_model=AttemptOut)
def submit_attempt(payload: AttemptIn) -> AttemptOut:
    selected_answer = normalize_answer(payload.selected_options)
    elapsed_seconds = None if payload.elapsed_seconds is None else max(0, int(payload.elapsed_seconds))
    with transaction() as conn:
        question = fetch_question(conn, payload.question_id)
        correct = is_answer_correct(selected_answer, question["correct_answer"])
        conn.execute(
            """
            INSERT INTO attempts (question_id, mode, selected_answer, is_correct, elapsed_seconds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.question_id, payload.mode, selected_answer, int(correct), elapsed_seconds),
        )
        if not correct:
            conn.execute(
                """
                INSERT INTO wrong_items (question_id, active, source, added_at, learned_at, updated_at)
                VALUES (?, 1, 'attempt', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(question_id) DO UPDATE SET
                    active = 1,
                    source = 'attempt',
                    learned_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (payload.question_id,),
            )
        wrong = conn.execute(
            "SELECT active FROM wrong_items WHERE question_id = ?",
            (payload.question_id,),
        ).fetchone()
        stats = conn.execute(
            f"SELECT * FROM ({QUESTION_STATS_SQL}) WHERE question_id = ?",
            (payload.question_id,),
        ).fetchone()
        return AttemptOut(
            question_id=payload.question_id,
            selected_answer=selected_answer,
            correct_answer=question["correct_answer"],
            is_correct=correct,
            explanation=question["explanation"],
            is_wrong_active=bool(wrong["active"]) if wrong else False,
            elapsed_seconds=elapsed_seconds,
            wrong_count=int(fetch_question(conn, payload.question_id)["wrong_count"] or 0),
            attempt_count=int(fetch_question(conn, payload.question_id)["attempt_count"] or 0),
            last_wrong_at=stats["last_wrong_at"] if stats else None,
        )


@router.patch("/wrong-items/{question_id}")
def patch_wrong_item(question_id: int, payload: WrongItemPatch) -> dict:
    with transaction() as conn:
        fetch_question(conn, question_id)
        if payload.learned or payload.active is False:
            conn.execute(
                """
                INSERT INTO wrong_items (question_id, active, source, learned_at, updated_at)
                VALUES (?, 0, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(question_id) DO UPDATE SET
                    active = 0,
                    source = excluded.source,
                    learned_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (question_id, payload.source),
            )
        else:
            conn.execute(
                """
                INSERT INTO wrong_items (question_id, active, source, added_at, learned_at, updated_at)
                VALUES (?, 1, ?, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(question_id) DO UPDATE SET
                    active = 1,
                    source = excluded.source,
                    learned_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (question_id, payload.source),
            )
        row = conn.execute(
            "SELECT active, learned_at FROM wrong_items WHERE question_id = ?",
            (question_id,),
        ).fetchone()
        return {"question_id": question_id, "active": bool(row["active"]), "learned_at": row["learned_at"]}


@router.patch("/questions/{question_id}/wrong-count", response_model=QuestionOut)
def patch_wrong_count(question_id: int, payload: WrongCountPatch) -> QuestionOut:
    with transaction() as conn:
        fetch_question(conn, question_id)
        raw = conn.execute(
            """
            SELECT SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS raw_wrong_count
            FROM attempts
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchone()
        raw_wrong_count = int(raw["raw_wrong_count"] or 0) if raw else 0
        target_wrong_count = max(0, int(payload.wrong_count))
        delta = target_wrong_count - raw_wrong_count
        active = int(target_wrong_count > 0)
        learned_at_sql = "NULL" if active else "CURRENT_TIMESTAMP"
        conn.execute(
            f"""
            INSERT INTO wrong_items (question_id, active, source, wrong_count_delta, added_at, learned_at, updated_at)
            VALUES (?, ?, 'manual_adjustment', ?, CURRENT_TIMESTAMP, {learned_at_sql}, CURRENT_TIMESTAMP)
            ON CONFLICT(question_id) DO UPDATE SET
                active = excluded.active,
                source = 'manual_adjustment',
                wrong_count_delta = excluded.wrong_count_delta,
                learned_at = excluded.learned_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (question_id, active, delta),
        )
        return build_question(conn, fetch_question(conn, question_id))


@router.patch("/questions/{question_id}/attempt-count", response_model=QuestionOut)
def patch_attempt_count(question_id: int, payload: AttemptCountPatch) -> QuestionOut:
    with transaction() as conn:
        fetch_question(conn, question_id)
        raw = conn.execute(
            """
            SELECT COUNT(*) AS raw_attempt_count
            FROM attempts
            WHERE question_id = ?
            """,
            (question_id,),
        ).fetchone()
        raw_attempt_count = int(raw["raw_attempt_count"] or 0) if raw else 0
        target_attempt_count = max(0, int(payload.attempt_count))
        delta = target_attempt_count - raw_attempt_count
        conn.execute(
            """
            INSERT INTO wrong_items (question_id, active, source, attempt_count_delta, added_at, updated_at)
            VALUES (?, 0, 'manual_adjustment', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(question_id) DO UPDATE SET
                source = 'manual_adjustment',
                attempt_count_delta = excluded.attempt_count_delta,
                updated_at = CURRENT_TIMESTAMP
            """,
            (question_id, delta),
        )
        return build_question(conn, fetch_question(conn, question_id))


@router.post("/questions", response_model=QuestionOut)
def create_question(payload: QuestionCreate) -> QuestionOut:
    with transaction() as conn:
        exam = conn.execute("SELECT id FROM exams WHERE code = ?", (payload.exam_code,)).fetchone()
        if exam is None:
            raise HTTPException(status_code=400, detail="Unknown exam_code")
        try:
            cur = conn.execute(
                """
                INSERT INTO questions (exam_id, number, stem, is_multi, correct_answer, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    exam["id"],
                    payload.number,
                    payload.stem,
                    int(payload.is_multi),
                    normalize_correct_answer(payload.correct_answer),
                    payload.explanation,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        question_id = cur.lastrowid
        for option in payload.options:
            conn.execute(
                "INSERT INTO options (question_id, label, text) VALUES (?, ?, ?)",
                (question_id, option.label.upper(), option.text),
            )
        return build_question(conn, fetch_question(conn, question_id))


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdate) -> QuestionOut:
    fields = []
    params: list[object] = []
    if payload.stem is not None:
        fields.append("stem = ?")
        params.append(payload.stem)
    if payload.number is not None:
        fields.append("number = ?")
        params.append(payload.number)
    if payload.is_multi is not None:
        fields.append("is_multi = ?")
        params.append(int(payload.is_multi))
    if payload.correct_answer is not None:
        fields.append("correct_answer = ?")
        params.append(normalize_correct_answer(payload.correct_answer))
    if payload.explanation is not None:
        fields.append("explanation = ?")
        params.append(payload.explanation)
    if payload.imported_note is not None:
        fields.append("imported_note = ?")
        params.append(payload.imported_note)

    with transaction() as conn:
        fetch_question(conn, question_id)
        if payload.exam_code is not None:
            exam = conn.execute("SELECT id FROM exams WHERE code = ?", (payload.exam_code,)).fetchone()
            if exam is None:
                raise HTTPException(status_code=400, detail="Unknown exam_code")
            fields.append("exam_id = ?")
            params.append(exam["id"])
        if fields:
            params.append(question_id)
            try:
                conn.execute(
                    f"UPDATE questions SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    params,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload.options is not None:
            conn.execute("DELETE FROM options WHERE question_id = ?", (question_id,))
            for option in payload.options:
                conn.execute(
                    "INSERT INTO options (question_id, label, text) VALUES (?, ?, ?)",
                    (question_id, option.label.upper(), option.text),
                )
        return build_question(conn, fetch_question(conn, question_id))


@router.delete("/questions/{question_id}")
def delete_question(question_id: int) -> dict:
    with transaction() as conn:
        fetch_question(conn, question_id)
        conn.execute(
            "UPDATE questions SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (question_id,),
        )
        return {"question_id": question_id, "deleted": True}
