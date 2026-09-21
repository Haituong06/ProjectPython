"""Phân tích ngôn ngữ lập trình trên GitHub (demo môn Python).

Python làm việc với web như sau:
  1. requests  : gọi GitHub API để lấy dữ liệu trực tiếp từ web
  2. pandas    : làm sạch và thống kê dữ liệu
  3. matplotlib: vẽ biểu đồ và lưu thành ảnh

Cài thư viện:  pip install requests pandas matplotlib
Chạy:          python github_analysis.py
Kết quả:       in bảng thống kê ra màn hình, lưu 2 file CSV và 1 ảnh biểu đồ
               (github_analysis.png) cùng thư mục với file này.

Lưu ý: GitHub cho phép ~10 lần tìm kiếm/phút nếu không đăng nhập. Chương trình
tự chờ khi chạm giới hạn. Muốn nhanh hơn, tạo token miễn phí trên GitHub và đặt
biến môi trường GITHUB_TOKEN.
"""
import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

API_URL = "https://api.github.com/search/repositories"
LANGUAGES = ["Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "PHP"]
MIN_STARS = 1000      # repo có trên 1000 sao được xem là "phổ biến"
TOP_N = 100           # số repo nhiều sao nhất toàn GitHub dùng để phân tích
OUT_DIR = Path(__file__).parent
# Các "ngôn ngữ" không phải ngôn ngữ lập trình (repo tài liệu, danh sách awesome...) -> loại khi so sánh
NON_PROGRAMMING = {"Không xác định", "Markdown", "HTML", "CSS"}


# ----------------------------------------------------------------------------
# 1. LẤY DỮ LIỆU TỪ WEB (GitHub API)
# ----------------------------------------------------------------------------
def call_api(params: dict) -> dict:
    """Gọi GitHub API, tự chờ và thử lại nếu chạm giới hạn số lần gọi."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "python-course-demo"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for _ in range(3):
        resp = requests.get(API_URL, params=params, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
            reset_at = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = min(max(reset_at - time.time(), 1) + 1, 90)
            print(f"  GitHub giới hạn số lần gọi, chờ {wait:.0f} giây rồi thử lại...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError("Không lấy được dữ liệu từ GitHub sau 3 lần thử. Hãy thử lại sau ít phút.")


def fetch_language_stats() -> pd.DataFrame:
    """Với mỗi ngôn ngữ: đếm số repo phổ biến và lấy repo nhiều sao nhất."""
    rows = []
    for lang in LANGUAGES:
        print(f"  Đang lấy dữ liệu: {lang}")
        data = call_api({
            "q": f"language:{lang} stars:>{MIN_STARS}",
            "sort": "stars", "order": "desc", "per_page": 1,
        })
        top = data["items"][0] if data["items"] else {}
        rows.append({
            "language": lang,
            "popular_repos": data["total_count"],
            "top_repo": top.get("full_name", ""),
            "top_repo_stars": top.get("stargazers_count", 0),
        })
        time.sleep(1)
    return pd.DataFrame(rows)


def fetch_top_repos(n: int = TOP_N) -> pd.DataFrame:
    """Lấy n repo nhiều sao nhất toàn GitHub."""
    print(f"  Đang lấy {n} repo nhiều sao nhất")
    data = call_api({"q": f"stars:>{MIN_STARS}", "sort": "stars", "order": "desc", "per_page": n})
    return pd.DataFrame([
        {
            "repo": item["full_name"],
            "language": item["language"] or "Không xác định",
            "stars": item["stargazers_count"],
        }
        for item in data["items"]
    ])


# ----------------------------------------------------------------------------
# 2. PHÂN TÍCH BẰNG PANDAS
# ----------------------------------------------------------------------------
def analyze(languages: pd.DataFrame, top_repos: pd.DataFrame):
    languages = languages.sort_values("popular_repos", ascending=False).reset_index(drop=True)
    languages["share_%"] = (languages["popular_repos"] / languages["popular_repos"].sum() * 100).round(1)

    programming = top_repos[~top_repos["language"].isin(NON_PROGRAMMING)]
    excluded = len(top_repos) - len(programming)
    by_language = (
        programming.groupby("language")
        .agg(repos=("repo", "count"), avg_stars=("stars", "mean"))
        .sort_values("repos", ascending=False)
        .reset_index()
    )
    by_language["avg_stars"] = by_language["avg_stars"].round(0).astype(int)
    return languages, by_language, excluded


# ----------------------------------------------------------------------------
# 3. VẼ BIỂU ĐỒ BẰNG MATPLOTLIB
# ----------------------------------------------------------------------------
def draw_charts(languages: pd.DataFrame, by_language: pd.DataFrame, path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ordered = languages.sort_values("popular_repos")
    bars = ax1.barh(ordered["language"], ordered["popular_repos"], color="#1f6f5c")
    ax1.set_title(f"Số repo có trên {MIN_STARS:,} sao theo ngôn ngữ")
    ax1.set_xlabel("Số repo")
    ax1.bar_label(bars, labels=[f"{v:,}" for v in ordered["popular_repos"]], padding=3)
    ax1.set_xlim(0, ordered["popular_repos"].max() * 1.15)

    top = by_language.head(8).sort_values("repos")
    bars = ax2.barh(top["language"], top["repos"], color="#b4460f")
    ax2.set_title(f"Ngôn ngữ lập trình trong {TOP_N} repo nhiều sao nhất GitHub")
    ax2.set_xlabel("Số repo")
    ax2.bar_label(bars, padding=3)
    ax2.set_xlim(0, top["repos"].max() * 1.15)

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"  Đã lưu biểu đồ: {path.name}")
    plt.show()


# ----------------------------------------------------------------------------
# CHƯƠNG TRÌNH CHÍNH
# ----------------------------------------------------------------------------
def main() -> None:
    print("1. Lấy dữ liệu từ GitHub API...")
    languages = fetch_language_stats()
    top_repos = fetch_top_repos()

    print("\n2. Phân tích dữ liệu...")
    languages, by_language, excluded = analyze(languages, top_repos)
    languages.to_csv(OUT_DIR / "github_languages.csv", index=False, encoding="utf-8-sig")
    top_repos.to_csv(OUT_DIR / "github_top_repos.csv", index=False, encoding="utf-8-sig")

    print(f"\nSố repo có trên {MIN_STARS:,} sao theo ngôn ngữ:")
    print(languages.to_string(index=False))
    print(f"\nNgôn ngữ lập trình trong {TOP_N} repo nhiều sao nhất (kèm số sao trung bình):")
    print(by_language.head(8).to_string(index=False))
    print(f"({excluded} repo không có ngôn ngữ lập trình rõ ràng, như tài liệu hoặc danh sách tổng hợp, đã được loại khỏi bảng này)")

    print("\nNhận xét:")
    best = languages.iloc[0]
    print(f"- {best['language']} có nhiều repo phổ biến nhất trong nhóm khảo sát: "
          f"{best['popular_repos']:,} repo ({best['share_%']}%).")
    leader = by_language.iloc[0]
    print(f"- Trong {TOP_N} repo nhiều sao nhất, {leader['language']} xuất hiện nhiều nhất "
          f"({leader['repos']} repo).")
    enough = by_language[by_language["repos"] >= 3]  # bỏ nhóm quá ít repo để so sánh công bằng
    star = enough.sort_values("avg_stars", ascending=False).iloc[0]
    print(f"- Trong các ngôn ngữ có từ 3 repo trở lên, {star['language']} có số sao trung bình "
          f"cao nhất: {star['avg_stars']:,} sao/repo.")

    print("\n3. Vẽ biểu đồ...")
    draw_charts(languages, by_language, OUT_DIR / "github_analysis.png")


if __name__ == "__main__":
    main()
