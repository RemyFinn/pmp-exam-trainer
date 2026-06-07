from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from .auth import (
    clear_session_cookie,
    create_session,
    current_session_token,
    current_user,
    hash_password,
    hash_token,
    require_admin,
    set_session_cookie,
    verify_password,
)
from .db import transaction
from .models import (
    AttemptIn,
    AttemptCountPatch,
    AttemptOut,
    ExamOut,
    LoginIn,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    StrategyLinkOut,
    StrategyOut,
    StrategyQuestionOut,
    UserCreate,
    UserOut,
    UserUpdate,
    WrongCountPatch,
    WrongItemPatch,
)
from .utils import is_answer_correct, normalize_answer, normalize_correct_answer

router = APIRouter(prefix="/api")


def user_out(row: dict) -> UserOut:
    return UserOut(
        id=row["id"],
        username=row["username"],
        display_name=row.get("display_name") or "",
        role=row["role"],
        is_active=bool(row["is_active"]),
    )


def fetch_question(conn, question_id: int, user_id: int) -> dict:
    row = conn.execute(
        """
        SELECT q.*, e.code AS exam_code, e.title AS exam_title,
               COALESCE(w.active, 0) AS is_wrong_active,
               GREATEST(0, COALESCE(s.raw_wrong_count, 0) + COALESCE(w.wrong_count_delta, 0)) AS wrong_count,
               GREATEST(0, COALESCE(s.attempt_count, 0) + COALESCE(w.attempt_count_delta, 0)) AS attempt_count,
               s.last_wrong_at AS last_wrong_at
        FROM questions q
        JOIN exams e ON e.id = q.exam_id
        LEFT JOIN wrong_items w ON w.question_id = q.id AND w.user_id = %s
        LEFT JOIN (
            SELECT question_id,
                   COUNT(*) AS attempt_count,
                   SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS raw_wrong_count,
                   MAX(CASE WHEN is_correct = 0 THEN created_at ELSE NULL END) AS last_wrong_at
            FROM attempts
            WHERE user_id = %s
            GROUP BY question_id
        ) s ON s.question_id = q.id
        WHERE q.id = %s AND q.deleted_at IS NULL
        """,
        (user_id, user_id, question_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return dict(row)


def fetch_options(conn, question_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, label, text FROM options WHERE question_id = %s ORDER BY label",
        (question_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_question_strategies(conn, question_id: int) -> list[StrategyLinkOut]:
    rows = conn.execute(
        """
        SELECT s.id, s.exam_code, s.category, s.title, s.summary
        FROM strategies s
        JOIN strategy_question_links l ON l.strategy_id = s.id
        WHERE l.question_id = %s
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
        last_wrong_at=str(row["last_wrong_at"]) if row.get("last_wrong_at") else None,
        strategies=fetch_question_strategies(conn, row["id"]),
        options=fetch_options(conn, row["id"]),
    )


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.post("/auth/login", response_model=UserOut)
def login(payload: LoginIn, response: Response) -> UserOut:
    with transaction() as conn:
        row = conn.execute(
            """
            SELECT id, username, display_name, password_hash, role, is_active
            FROM users
            WHERE username = %s
            """,
            (payload.username.strip(),),
        ).fetchone()
        if row is None or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = create_session(int(row["id"]))
        set_session_cookie(response, token)
        return user_out(dict(row))


@router.post("/auth/logout")
def logout(
    response: Response,
    user: dict = Depends(current_user),
    token: str | None = Depends(current_session_token),
) -> dict:
    if token:
        with transaction() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (hash_token(token),))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> UserOut:
    return user_out(user)


@router.get("/users", response_model=list[UserOut])
def list_users(admin: dict = Depends(require_admin)) -> list[UserOut]:
    with transaction() as conn:
        rows = conn.execute(
            """
            SELECT id, username, display_name, role, is_active
            FROM users
            ORDER BY role, username
            """
        ).fetchall()
        return [user_out(dict(row)) for row in rows]


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, admin: dict = Depends(require_admin)) -> UserOut:
    role = payload.role if payload.role in {"admin", "user"} else "user"
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="请输入用户名")
    with transaction() as conn:
        try:
            row = conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, role, is_active)
                VALUES (%s, %s, %s, %s, 1)
                RETURNING id, username, display_name, role, is_active
                """,
                (username, payload.display_name.strip(), hash_password(payload.password), role),
            ).fetchone()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return user_out(dict(row))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, admin: dict = Depends(require_admin)) -> UserOut:
    fields = []
    params: list[object] = []
    if payload.display_name is not None:
        fields.append("display_name = %s")
        params.append(payload.display_name.strip())
    if payload.password is not None:
        fields.append("password_hash = %s")
        params.append(hash_password(payload.password))
    if payload.role is not None:
        if payload.role not in {"admin", "user"}:
            raise HTTPException(status_code=400, detail="角色无效")
        fields.append("role = %s")
        params.append(payload.role)
    if payload.is_active is not None:
        fields.append("is_active = %s")
        params.append(int(payload.is_active))
    with transaction() as conn:
        if fields:
            params.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s", params)
        row = conn.execute(
            "SELECT id, username, display_name, role, is_active FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return user_out(dict(row))


@router.get("/exams", response_model=list[ExamOut])
def list_exams(user: dict = Depends(current_user)) -> list[ExamOut]:
    user_id = int(user["id"])
    with transaction() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.code, e.title,
                   COUNT(q.id) AS total_questions,
                   COUNT(CASE WHEN COALESCE(w.active, 0) = 1 THEN q.id END) AS wrong_questions,
                   COALESCE(SUM(GREATEST(0, COALESCE(s.attempt_count, 0) + COALESCE(w.attempt_count_delta, 0))), 0) AS attempts
            FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id AND q.deleted_at IS NULL
            LEFT JOIN wrong_items w ON w.question_id = q.id AND w.user_id = %s
            LEFT JOIN (
                SELECT question_id,
                       COUNT(*) AS attempt_count,
                       SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS raw_wrong_count,
                       MAX(CASE WHEN is_correct = 0 THEN created_at ELSE NULL END) AS last_wrong_at
                FROM attempts
                WHERE user_id = %s
                GROUP BY question_id
            ) s ON s.question_id = q.id
            GROUP BY e.id
            ORDER BY e.code
            """,
            (user_id, user_id),
        ).fetchall()
        return [ExamOut(**dict(row)) for row in rows]


@router.get("/questions", response_model=list[QuestionOut])
def list_questions(
    mode: str = Query("mixed", pattern="^(exam|mixed|wrong|admin)$"),
    exam: str | None = None,
    shuffle: bool = False,
    search: str | None = None,
    user: dict = Depends(current_user),
) -> list[QuestionOut]:
    user_id = int(user["id"])
    if mode == "admin" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    where = ["q.deleted_at IS NULL"]
    params: list[object] = [user_id, user_id]

    if mode == "exam":
        if not exam:
            raise HTTPException(status_code=400, detail="exam is required for exam mode")
        where.append("e.code = %s")
        params.append(exam)
    elif mode == "wrong":
        where.append("COALESCE(w.active, 0) = 1")
        if exam:
            where.append("e.code = %s")
            params.append(exam)

    if search:
        where.append("(q.stem LIKE %s OR q.explanation LIKE %s OR q.correct_answer LIKE %s)")
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
               GREATEST(0, COALESCE(s.raw_wrong_count, 0) + COALESCE(w.wrong_count_delta, 0)) AS wrong_count,
               GREATEST(0, COALESCE(s.attempt_count, 0) + COALESCE(w.attempt_count_delta, 0)) AS attempt_count,
               s.last_wrong_at AS last_wrong_at
        FROM questions q
        JOIN exams e ON e.id = q.exam_id
        LEFT JOIN wrong_items w ON w.question_id = q.id AND w.user_id = %s
        LEFT JOIN (
            SELECT question_id,
                   COUNT(*) AS attempt_count,
                   SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS raw_wrong_count,
                   MAX(CASE WHEN is_correct = 0 THEN created_at ELSE NULL END) AS last_wrong_at
            FROM attempts
            WHERE user_id = %s
            GROUP BY question_id
        ) s ON s.question_id = q.id
        WHERE {" AND ".join(where)}
        ORDER BY {order_by}
    """

    with transaction() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [build_question(conn, dict(row)) for row in rows]


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(
    exam: str | None = None,
    search: str | None = None,
    user: dict = Depends(current_user),
) -> list[StrategyOut]:
    user_id = int(user["id"])
    where: list[str] = []
    params: list[object] = []
    if exam:
        where.append("s.exam_code = %s")
        params.append(exam)
    if search:
        where.append("(s.category LIKE %s OR s.title LIKE %s OR s.summary LIKE %s)")
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
                LEFT JOIN wrong_items w ON w.question_id = q.id AND w.user_id = %s
                WHERE l.strategy_id = %s
                ORDER BY CASE e.code
                    WHEN 'sim7' THEN 1
                    WHEN 'sim8' THEN 2
                    WHEN 'sim9' THEN 3
                    WHEN 'sim10' THEN 4
                    ELSE 99
                END, q.number
                """,
                (user_id, strategy.id),
            ).fetchall()
            strategy.questions = [StrategyQuestionOut(**dict(qrow)) for qrow in qrows]
            result.append(strategy)
        return result


@router.get("/questions/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, user: dict = Depends(current_user)) -> QuestionOut:
    with transaction() as conn:
        return build_question(conn, fetch_question(conn, question_id, int(user["id"])))


@router.post("/attempts", response_model=AttemptOut)
def submit_attempt(payload: AttemptIn, user: dict = Depends(current_user)) -> AttemptOut:
    user_id = int(user["id"])
    selected_answer = normalize_answer(payload.selected_options)
    elapsed_seconds = None if payload.elapsed_seconds is None else max(0, int(payload.elapsed_seconds))
    with transaction() as conn:
        question = fetch_question(conn, payload.question_id, user_id)
        correct = is_answer_correct(selected_answer, question["correct_answer"])
        conn.execute(
            """
            INSERT INTO attempts (user_id, question_id, mode, selected_answer, is_correct, elapsed_seconds)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, payload.question_id, payload.mode, selected_answer, int(correct), elapsed_seconds),
        )
        if not correct:
            conn.execute(
                """
                INSERT INTO wrong_items (user_id, question_id, active, source, added_at, learned_at, updated_at)
                VALUES (%s, %s, 1, 'attempt', CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, question_id) DO UPDATE SET
                    active = 1,
                    source = 'attempt',
                    learned_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, payload.question_id),
            )
        wrong = conn.execute(
            "SELECT active FROM wrong_items WHERE user_id = %s AND question_id = %s",
            (user_id, payload.question_id),
        ).fetchone()
        updated_question = fetch_question(conn, payload.question_id, user_id)
        return AttemptOut(
            question_id=payload.question_id,
            selected_answer=selected_answer,
            correct_answer=question["correct_answer"],
            is_correct=correct,
            explanation=question["explanation"],
            is_wrong_active=bool(wrong["active"]) if wrong else False,
            elapsed_seconds=elapsed_seconds,
            wrong_count=int(updated_question["wrong_count"] or 0),
            attempt_count=int(updated_question["attempt_count"] or 0),
            last_wrong_at=str(updated_question["last_wrong_at"]) if updated_question.get("last_wrong_at") else None,
        )


@router.patch("/wrong-items/{question_id}")
def patch_wrong_item(question_id: int, payload: WrongItemPatch, user: dict = Depends(current_user)) -> dict:
    user_id = int(user["id"])
    with transaction() as conn:
        fetch_question(conn, question_id, user_id)
        if payload.learned or payload.active is False:
            conn.execute(
                """
                INSERT INTO wrong_items (user_id, question_id, active, source, learned_at, updated_at)
                VALUES (%s, %s, 0, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, question_id) DO UPDATE SET
                    active = 0,
                    source = excluded.source,
                    learned_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, question_id, payload.source),
            )
        else:
            conn.execute(
                """
                INSERT INTO wrong_items (user_id, question_id, active, source, added_at, learned_at, updated_at)
                VALUES (%s, %s, 1, %s, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, question_id) DO UPDATE SET
                    active = 1,
                    source = excluded.source,
                    learned_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, question_id, payload.source),
            )
        row = conn.execute(
            "SELECT active, learned_at FROM wrong_items WHERE user_id = %s AND question_id = %s",
            (user_id, question_id),
        ).fetchone()
        return {
            "question_id": question_id,
            "active": bool(row["active"]),
            "learned_at": str(row["learned_at"]) if row["learned_at"] else None,
        }


@router.patch("/questions/{question_id}/wrong-count", response_model=QuestionOut)
def patch_wrong_count(question_id: int, payload: WrongCountPatch, user: dict = Depends(current_user)) -> QuestionOut:
    user_id = int(user["id"])
    with transaction() as conn:
        fetch_question(conn, question_id, user_id)
        raw = conn.execute(
            """
            SELECT SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) AS raw_wrong_count
            FROM attempts
            WHERE user_id = %s AND question_id = %s
            """,
            (user_id, question_id),
        ).fetchone()
        raw_wrong_count = int(raw["raw_wrong_count"] or 0) if raw else 0
        target_wrong_count = max(0, int(payload.wrong_count))
        delta = target_wrong_count - raw_wrong_count
        active = int(target_wrong_count > 0)
        learned_at_sql = "NULL" if active else "CURRENT_TIMESTAMP"
        conn.execute(
            f"""
            INSERT INTO wrong_items (user_id, question_id, active, source, wrong_count_delta, added_at, learned_at, updated_at)
            VALUES (%s, %s, %s, 'manual_adjustment', %s, CURRENT_TIMESTAMP, {learned_at_sql}, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                active = excluded.active,
                source = 'manual_adjustment',
                wrong_count_delta = excluded.wrong_count_delta,
                learned_at = excluded.learned_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, question_id, active, delta),
        )
        return build_question(conn, fetch_question(conn, question_id, user_id))


@router.patch("/questions/{question_id}/attempt-count", response_model=QuestionOut)
def patch_attempt_count(question_id: int, payload: AttemptCountPatch, user: dict = Depends(current_user)) -> QuestionOut:
    user_id = int(user["id"])
    with transaction() as conn:
        fetch_question(conn, question_id, user_id)
        raw = conn.execute(
            """
            SELECT COUNT(*) AS raw_attempt_count
            FROM attempts
            WHERE user_id = %s AND question_id = %s
            """,
            (user_id, question_id),
        ).fetchone()
        raw_attempt_count = int(raw["raw_attempt_count"] or 0) if raw else 0
        target_attempt_count = max(0, int(payload.attempt_count))
        delta = target_attempt_count - raw_attempt_count
        conn.execute(
            """
            INSERT INTO wrong_items (user_id, question_id, active, source, attempt_count_delta, added_at, updated_at)
            VALUES (%s, %s, 0, 'manual_adjustment', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                source = 'manual_adjustment',
                attempt_count_delta = excluded.attempt_count_delta,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, question_id, delta),
        )
        return build_question(conn, fetch_question(conn, question_id, user_id))


@router.post("/questions", response_model=QuestionOut)
def create_question(payload: QuestionCreate, admin: dict = Depends(require_admin)) -> QuestionOut:
    user_id = int(admin["id"])
    with transaction() as conn:
        exam = conn.execute("SELECT id FROM exams WHERE code = %s", (payload.exam_code,)).fetchone()
        if exam is None:
            raise HTTPException(status_code=400, detail="Unknown exam_code")
        try:
            cur = conn.execute(
                """
                INSERT INTO questions (exam_id, number, stem, is_multi, correct_answer, explanation)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
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
        question_id = int(cur.fetchone()["id"])
        for option in payload.options:
            conn.execute(
                "INSERT INTO options (question_id, label, text) VALUES (%s, %s, %s)",
                (question_id, option.label.upper(), option.text),
            )
        return build_question(conn, fetch_question(conn, question_id, user_id))


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdate, admin: dict = Depends(require_admin)) -> QuestionOut:
    user_id = int(admin["id"])
    fields = []
    params: list[object] = []
    if payload.stem is not None:
        fields.append("stem = %s")
        params.append(payload.stem)
    if payload.number is not None:
        fields.append("number = %s")
        params.append(payload.number)
    if payload.is_multi is not None:
        fields.append("is_multi = %s")
        params.append(int(payload.is_multi))
    if payload.correct_answer is not None:
        fields.append("correct_answer = %s")
        params.append(normalize_correct_answer(payload.correct_answer))
    if payload.explanation is not None:
        fields.append("explanation = %s")
        params.append(payload.explanation)
    if payload.imported_note is not None:
        fields.append("imported_note = %s")
        params.append(payload.imported_note)

    with transaction() as conn:
        fetch_question(conn, question_id, user_id)
        if payload.exam_code is not None:
            exam = conn.execute("SELECT id FROM exams WHERE code = %s", (payload.exam_code,)).fetchone()
            if exam is None:
                raise HTTPException(status_code=400, detail="Unknown exam_code")
            fields.append("exam_id = %s")
            params.append(exam["id"])
        if fields:
            params.append(question_id)
            try:
                conn.execute(
                    f"UPDATE questions SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    params,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload.options is not None:
            conn.execute("DELETE FROM options WHERE question_id = %s", (question_id,))
            for option in payload.options:
                conn.execute(
                    "INSERT INTO options (question_id, label, text) VALUES (%s, %s, %s)",
                    (question_id, option.label.upper(), option.text),
                )
        return build_question(conn, fetch_question(conn, question_id, user_id))


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, admin: dict = Depends(require_admin)) -> dict:
    user_id = int(admin["id"])
    with transaction() as conn:
        fetch_question(conn, question_id, user_id)
        conn.execute(
            "UPDATE questions SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (question_id,),
        )
        return {"question_id": question_id, "deleted": True}
