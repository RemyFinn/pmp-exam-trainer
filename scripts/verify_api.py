from __future__ import annotations

import json
import os
import re
import time
import urllib.request


BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def req(path: str, method: str = "GET", data: dict | None = None):
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(
        BASE + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read().decode()
        content_type = response.headers.get("Content-Type", "")
        return raw if "text/html" in content_type else json.loads(raw)


def answer_list(answer: str) -> list[str]:
    return re.findall(r"[A-F]", answer.split("/")[0])


def main() -> None:
    html = req("/")
    assert "PMP 做题系统" in html or "PMP 练习" in html
    for frontend_path in ("/strategies", "/wrong", "/admin", "/practice"):
        route_html = req(frontend_path)
        assert "PMP 做题系统" in route_html or "PMP 练习" in route_html, frontend_path

    exams = req("/api/exams")
    assert len(exams) == 4, len(exams)

    sim7 = req("/api/questions?mode=exam&exam=sim7")
    assert len(sim7) == 180, len(sim7)

    mixed = req("/api/questions?mode=mixed")
    assert len(mixed) == 720, len(mixed)

    wrong = req("/api/questions?mode=wrong")
    assert len(wrong) >= 0, len(wrong)

    strategies = req("/api/strategies")
    assert len(strategies) > 0, len(strategies)
    linked_strategy = next((item for item in strategies if item["questions"]), None)
    assert linked_strategy is not None, strategies[:1]

    question_with_strategy = next((item for item in sim7 if item.get("strategies")), None)
    assert question_with_strategy is not None, sim7[:1]

    next_number = int(time.time())
    created = req(
        "/api/questions",
        "POST",
        {
            "exam_code": "sim7",
            "number": next_number,
            "stem": "临时验证题",
            "is_multi": False,
            "correct_answer": "A",
            "explanation": "验证解析",
            "options": [
                {"label": "A", "text": "正确"},
                {"label": "B", "text": "错误"},
            ],
        },
    )
    attempt = req(
        "/api/attempts",
        "POST",
        {
            "question_id": created["id"],
            "selected_options": answer_list(created["correct_answer"]),
            "mode": "verify",
        },
    )
    assert attempt["is_correct"] is True, attempt

    updated = req(
        f"/api/questions/{created['id']}",
        "PATCH",
        {
            "stem": "临时验证题更新",
            "correct_answer": "B",
            "options": [
                {"label": "A", "text": "旧"},
                {"label": "B", "text": "新正确"},
            ],
        },
    )
    assert updated["stem"] == "临时验证题更新"
    assert updated["correct_answer"] == "B"

    wrong_attempt = req(
        "/api/attempts",
        "POST",
        {
            "question_id": created["id"],
            "selected_options": ["A"],
            "mode": "verify",
        },
    )
    assert wrong_attempt["is_correct"] is False, wrong_attempt

    learned = req(
        f"/api/wrong-items/{created['id']}",
        "PATCH",
        {"learned": True},
    )
    assert learned["active"] is False, learned

    deleted = req(f"/api/questions/{created['id']}", "DELETE")
    assert deleted["deleted"] is True

    wrong_after = req("/api/questions?mode=wrong")
    assert len(wrong_after) == len(wrong), (len(wrong), len(wrong_after))

    print(
        json.dumps(
            {
                "exams": len(exams),
                "sim7": len(sim7),
                "mixed": len(mixed),
                "wrong_before": len(wrong),
                "wrong_after_learned": len(wrong_after),
                "strategies": len(strategies),
                "frontend_routes": "ok",
                "attempt_correct": attempt["is_correct"],
                "crud": "ok",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
