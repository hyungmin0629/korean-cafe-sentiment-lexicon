"""Guided, local Naver CSV collection. Does not install software or retry blocks."""
import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="카페 URL을 입력해 네이버 리뷰 CSV 만들기")
    parser.add_argument("--url", help="생략하면 질문합니다")
    parser.add_argument("--cafe-name", help="생략하면 질문합니다")
    parser.add_argument("--max-reviews", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--browser", choices=["chromium", "chrome", "msedge"], default="chromium")
    parser.add_argument("--scroll-load", action="store_true", help="스크롤 추가 로딩 시험 기능")
    args = parser.parse_args(argv)
    if args.max_reviews < 1 or args.max_pages < 1:
        print("수집 건수와 화면 수는 1 이상이어야 합니다.")
        return 2
    missing = [name for name in ("bs4", "playwright") if importlib.util.find_spec(name) is None]
    if missing:
        print("수집에 필요한 라이브러리를 먼저 설치하세요.\n"
              "python -m pip install -r requirements-naver.txt\n"
              "python -m playwright install chromium")
        return 2
    # Keep optional dependencies out of imports until after the installation check.
    from crawl_naver_place import main as collect, canonical_url
    print("네이버 리뷰 CSV 만들기\n접근이 제한되면 중단하며, 전체 리뷰 수집은 보장하지 않습니다.")
    try:
        url = (args.url or input("카페 네이버 지도/플레이스 URL: ")).strip()
        cafe_name = (args.cafe_name or input("보고서에 표시할 카페/지점 이름: ")).strip()
        canonical_url(url)
        if not cafe_name:
            raise ValueError("카페 이름을 입력하세요.")
    except (ValueError, EOFError) as exc:
        print(f"입력 확인: {exc}")
        return 2
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    output = ROOT / "data_private" / ("naver_" + run_id)
    arguments = ["--url", url, "--cafe-name", cafe_name, "--output", str(output),
                 "--max-reviews", str(args.max_reviews), "--max-pages", str(args.max_pages),
                 "--delay", "3", "--browser", args.browser]
    if args.headed:
        arguments += ["--headed"]
    if args.scroll_load:
        arguments += ["--scroll-load"]
    print(f"수집 상한: {args.max_reviews}건 / {args.max_pages}회 화면 확인\n수집을 시작합니다.")
    result = collect(arguments)
    summary = output / "collection_summary.txt"
    if summary.is_file():
        print("\n" + summary.read_text(encoding="utf-8-sig"))
        print(f"결과 폴더: {output}")
        manifest = json.loads((output / "collection_manifest.json").read_text(encoding="utf-8"))
        if manifest["usable_for_analysis"]:
            print(f"분석할 파일: {output / 'reviews.csv'}\n"
                  "CSV 분석 화면: http://127.0.0.1:8766/\n"
                  "화면이 열리지 않으면 python tools/serve_app.py 로 서버를 켜세요.")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n사용자가 실행을 취소했습니다.")
        raise SystemExit(130)
