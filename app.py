"""Web trắc nghiệm ôn thi Python - có thống kê và gợi ý chủ đề yếu.

Python (pandas) đảm nhiệm phần xử lý chính:
  - đọc ngân hàng câu hỏi từ questions.csv
  - chấm điểm và thống kê tỉ lệ đúng theo từng chủ đề
  - phát hiện chủ đề yếu và đưa ra gợi ý ôn tập
  - lưu lịch sử làm bài (history.csv) và thống kê qua nhiều lần thi

Chạy:  python app.py   ->   mở http://127.0.0.1:5000
"""
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).parent
QUESTIONS_CSV = BASE_DIR / "questions.csv"
HISTORY_CSV = BASE_DIR / "history.csv"

WEAK_THRESHOLD = 0.6  # tỉ lệ đúng dưới 60% được xem là chủ đề yếu

STUDY_TIPS = {
    "Biến & kiểu dữ liệu": "Ôn lại các kiểu int, float, str, bool và cách ép kiểu bằng int(), str(), float().",
    "Vòng lặp & điều kiện": "Luyện for/while với range(start, stop, step) và phân biệt break với continue.",
    "Hàm": "Xem lại cú pháp def, giá trị trả về (return/None) và tham số mặc định.",
    "List & Dict": "Thực hành chỉ số âm, append(), và dict.get() thay cho truy cập trực tiếp.",
    "File & thư viện": "Tập dùng with open(...) và làm quen pandas, Flask qua các ví dụ nhỏ.",
}

app = Flask(__name__)


def load_questions() -> pd.DataFrame:
    # keep_default_na=False để chữ "None" trong đáp án không bị hiểu thành giá trị rỗng
    return pd.read_csv(QUESTIONS_CSV, dtype=str, keep_default_na=False)


def load_history() -> pd.DataFrame:
    if not HISTORY_CSV.exists():
        return pd.DataFrame(columns=["attempt", "time", "topic", "correct"])
    history = pd.read_csv(HISTORY_CSV)
    history["correct"] = history["correct"].astype(bool)
    return history


def grade(questions: pd.DataFrame, form) -> pd.DataFrame:
    """Gắn đáp án đã chọn và kết quả đúng/sai vào bảng câu hỏi."""
    graded = questions.copy()
    graded["chosen"] = graded["id"].map(lambda qid: form.get(f"q{qid}", ""))
    graded["correct"] = graded["chosen"] == graded["answer"]
    return graded


def topic_stats(graded: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp số câu đúng, tổng số câu và tỉ lệ đúng theo chủ đề."""
    stats = (
        graded.groupby("topic", sort=False)
        .agg(right=("correct", "sum"), total=("correct", "size"))
        .reset_index()
    )
    stats["rate"] = stats["right"] / stats["total"]
    stats["weak"] = stats["rate"] < WEAK_THRESHOLD
    return stats


def save_attempt(graded: pd.DataFrame) -> None:
    now = datetime.now()
    rows = graded[["topic", "correct"]].copy()
    rows.insert(0, "time", now.strftime("%Y-%m-%d %H:%M"))
    rows.insert(0, "attempt", now.strftime("%Y%m%d%H%M%S%f"))
    rows.to_csv(HISTORY_CSV, mode="a", header=not HISTORY_CSV.exists(), index=False)


@app.route("/")
def quiz():
    questions = load_questions()
    topics = [
        (topic, group.to_dict("records"))
        for topic, group in questions.groupby("topic", sort=False)
    ]
    return render_template("quiz.html", topics=topics, total=len(questions))


@app.route("/submit", methods=["POST"])
def submit():
    graded = grade(load_questions(), request.form)
    stats = topic_stats(graded)
    save_attempt(graded)

    weak_topics = stats.loc[stats["weak"], "topic"].tolist()
    return render_template(
        "result.html",
        score=int(graded["correct"].sum()),
        total=len(graded),
        stats=stats.to_dict("records"),
        tips=[(topic, STUDY_TIPS.get(topic, "")) for topic in weak_topics],
        wrong=graded[~graded["correct"]].to_dict("records"),
    )


@app.route("/history")
def history():
    data = load_history()
    if data.empty:
        return render_template("history.html", attempts=[], topics=[], best=None, average=None)

    per_attempt = (
        data.groupby(["attempt", "time"])
        .agg(right=("correct", "sum"), total=("correct", "size"))
        .reset_index()
        .sort_values("attempt")
    )
    per_attempt["percent"] = (per_attempt["right"] / per_attempt["total"] * 100).round()

    per_topic = data.groupby("topic", sort=False)["correct"].mean().reset_index(name="rate")
    per_topic["weak"] = per_topic["rate"] < WEAK_THRESHOLD

    return render_template(
        "history.html",
        attempts=per_attempt.to_dict("records"),
        topics=per_topic.sort_values("rate").to_dict("records"),
        best=int(per_attempt["percent"].max()),
        average=int(round(per_attempt["percent"].mean())),
    )


@app.route("/reset", methods=["POST"])
def reset():
    HISTORY_CSV.unlink(missing_ok=True)
    return redirect(url_for("history"))


if __name__ == "__main__":
    app.run(debug=True)
