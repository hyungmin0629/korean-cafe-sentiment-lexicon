"""Loopback-only upload/preview/analyze app. No external service requests."""
import argparse
import csv
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .cli import parse_date, run, write_csv
from .upload import FIELDS, MAX_BYTES, UploadError, prepare_upload

ASSETS = {"/": ("upload.html", "text/html; charset=utf-8"),
          "/analyze.html": ("upload.html", "text/html; charset=utf-8"),
          "/assets/upload.css": ("upload.css", "text/css; charset=utf-8"),
          "/assets/upload.js": ("upload.js", "text/javascript; charset=utf-8"),
          "/api/sample": ("upload_sample.csv", "text/csv; charset=utf-8")}
ARTIFACTS = {"report.html": "text/html; charset=utf-8", "summary.csv": "text/csv; charset=utf-8",
             "reviews.jsonl": "application/x-ndjson; charset=utf-8", "input_issues.csv": "text/csv; charset=utf-8",
             "run_metadata.json": "application/json; charset=utf-8"}
INPUTS = {"reviews.csv": "text/csv; charset=utf-8", "upload_issues.csv": "text/csv; charset=utf-8"}


class AppState:
    def __init__(self, directory, project=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.jobs = {}
        self.lock = threading.RLock()
        self.workers = threading.Semaphore(2)
        self.legacy = {}
        if project:
            project = Path(project)
            self.legacy = {"/demo.html": project / "examples/report.synthetic.html",
                           "/report.final.html": project / "outputs_private/actual_all_v031/report.html",
                           "/review.html": project / "outputs_private/review_workspace_v01/review.html",
                           "/review-demo.html": project / "examples/annotation.synthetic.html"}

    def persist(self, job):
        target = self.directory / job["id"] / "job.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    def preview(self, payload):
        rows, issues, preview = prepare_upload(payload.get("csv"), payload.get("cafe_name", ""), payload.get("source", "naver_place"))
        token = uuid.uuid4().hex
        directory = self.directory / token / "input"
        directory.mkdir(parents=True)
        write_csv(directory / "reviews.csv", rows, FIELDS)
        write_csv(directory / "upload_issues.csv", issues, ["record_number", "review_id", "issue", "action"])
        filename = payload.get("filename", "reviews.csv")
        if not isinstance(filename, str):
            filename = "reviews.csv"
        job = {"id": token, "status": "ready", "filename": filename[:200], "preview": preview,
               "created_at": datetime.now(timezone.utc).isoformat()}
        with self.lock:
            self.jobs[token] = job
            self.persist(job)
        return job

    def get(self, token):
        with self.lock:
            if token not in self.jobs:
                raise UploadError("입력을 다시 확인해주세요. 서버 재시작 후에는 CSV를 다시 올려야 합니다.")
            return json.loads(json.dumps(self.jobs[token]))

    def analyze(self, token, options):
        period = options.get("period", "month")
        if period not in {"month", "quarter", "all"}:
            raise UploadError("집계 단위를 다시 선택해주세요.")
        start, end = options.get("start") or None, options.get("end") or None
        try:
            lower, upper = parse_date(start) if start else None, parse_date(end) if end else None
        except (ValueError, TypeError):
            raise UploadError("기간은 YYYY-MM-DD 날짜로 입력해주세요.")
        if lower and upper and lower > upper:
            raise UploadError("시작일은 종료일보다 늦을 수 없습니다.")
        job = self.get(token)
        settings = {"period": period, "start": start, "end": end}
        if job["status"] in {"running", "complete"}:
            if job.get("settings") != settings:
                raise UploadError("다른 기간으로 분석하려면 입력 확인을 다시 눌러주세요.")
            return job
        if job["status"] != "ready":
            raise UploadError("CSV 입력을 다시 확인한 뒤 분석해주세요.")
        source = self.directory / token / "input/reviews.csv"
        included = 0
        with source.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                day = parse_date(row["review_date"]) if row["review_date"] else None
                if day is None:
                    included += not (lower or upper)
                elif (not lower or day >= lower) and (not upper or day <= upper):
                    included += 1
        if not included:
            raise UploadError("선택한 기간에 집계할 리뷰가 없습니다. 날짜 범위를 바꾸거나 비워주세요.")
        with self.lock:
            if self.jobs[token]["status"] != "ready":
                return self.get(token)
            self.jobs[token].update(status="running", settings=settings, included_rows=included)
            self.persist(self.jobs[token])
        threading.Thread(target=self._work, args=(token, settings), daemon=True).start()
        return self.get(token)

    def _work(self, token, settings):
        directory = self.directory / token
        try:
            with self.workers:
                run(SimpleNamespace(input=str(directory / "input/reviews.csv"), output=str(directory / "result"),
                                    min_samples=10, lexicon=None, rules=None, aliases=None, no_report=False,
                                    report_examples=3, **settings))
            metadata = json.loads((directory / "result/run_metadata.json").read_text(encoding="utf-8"))
            with self.lock:
                self.jobs[token].update(status="complete", analysis_counts=metadata["counts"],
                                        completed_at=datetime.now(timezone.utc).isoformat(),
                                        report_url=f"/runs/{token}/result/report.html",
                                        downloads={name: f"/runs/{token}/result/{name}?download=1" for name in ARTIFACTS},
                                        normalized_csv=f"/runs/{token}/input/reviews.csv?download=1",
                                        upload_issues=f"/runs/{token}/input/upload_issues.csv?download=1")
                self.persist(self.jobs[token])
        except Exception:
            with self.lock:
                self.jobs[token].update(status="failed", error="분석 중 문제가 발생했습니다. CSV를 다시 확인해주세요.")
                self.persist(self.jobs[token])


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, data, content_type, status=200, attachment=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
            if attachment:
                self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, data, status=200):
            self.send_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def local_request(self):
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if "http://" + self.headers.get("Host", "") not in allowed:
                self.send_json({"error": "이 PC의 로컬 주소에서 실행해주세요."}, 403)
                return False
            if self.headers.get("Origin") and self.headers["Origin"] not in allowed:
                self.send_json({"error": "분석 화면에서 요청해주세요."}, 403)
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_json({"error": "분석 화면에서 요청해주세요."}, 403)
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            parsed = urlsplit(self.path)
            path = parsed.path
            try:
                if path in ASSETS:
                    resource, content_type = ASSETS[path]
                    return self.send_bytes(files("cafe_sentiment").joinpath("resources", resource).read_bytes(), content_type)
                if path == "/api/health":
                    return self.send_json({"status": "ok", "version": __version__, "demo_available": state.legacy.get("/demo.html", Path("/nonexistent")).is_file()})
                match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})", path)
                if match:
                    return self.send_json(state.get(match.group(1)))
                match = re.fullmatch(r"/runs/([a-f0-9]{32})/(input|result)/([a-z_.]+)", path)
                if match:
                    token, kind, name = match.groups()
                    allowlist = INPUTS if kind == "input" else ARTIFACTS
                    target = state.directory / token / kind / name
                    if name not in allowlist or not target.resolve().is_relative_to(state.directory) or not target.is_file():
                        return self.send_json({"error": "파일을 찾을 수 없습니다."}, 404)
                    job_path = state.directory / token / "job.json"
                    if kind == "result" and (not job_path.is_file() or json.loads(job_path.read_text(encoding="utf-8"))["status"] != "complete"):
                        return self.send_json({"error": "보고서를 생성 중입니다."}, 409)
                    attachment = name if parse_qs(parsed.query).get("download") == ["1"] else None
                    return self.send_bytes(target.read_bytes(), allowlist[name], attachment=attachment)
                if path in state.legacy and state.legacy[path].is_file():
                    return self.send_bytes(state.legacy[path].read_bytes(), "text/html; charset=utf-8")
                return self.send_json({"error": "페이지를 찾을 수 없습니다."}, 404)
            except UploadError as exc:
                return self.send_json({"error": str(exc)}, 404)
            except OSError:
                return self.send_json({"error": "파일을 읽지 못했습니다."}, 500)

        def do_POST(self):
            if not self.local_request():
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send_json({"error": "분석 화면에서 CSV를 올려주세요."}, 415)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BYTES * 3:
                    return self.send_json({"error": "업로드 파일 크기를 확인해주세요."}, 413)
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise UploadError("입력 형식을 확인해주세요.")
                path = urlsplit(self.path).path
                if path == "/api/preview":
                    return self.send_json(state.preview(payload), 201)
                match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})/analyze", path)
                if match:
                    return self.send_json(state.analyze(match.group(1), payload), 202)
                return self.send_json({"error": "요청을 찾을 수 없습니다."}, 404)
            except (ValueError, UnicodeError, TypeError) as exc:
                message = str(exc) if isinstance(exc, UploadError) else "입력 형식을 확인해주세요."
                return self.send_json({"error": message}, 400)
            except OSError:
                return self.send_json({"error": "CSV를 저장하지 못했습니다. 출력 폴더를 확인해주세요."}, 500)

        def log_message(self, format, *args):
            # Do not log CSV contents, cafe names, or upload filenames.
            pass
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="리뷰 CSV 업로드와 감성분석 보고서 — 이 PC에서 실행")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--output", default="outputs_private/web_runs")
    parser.add_argument("--project-dir", default=str(Path.cwd()), help="Project directory for existing report previews")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("포트는 1~65535 범위여야 합니다.")
    state = AppState(args.output, args.project_dir)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    except OSError:
        parser.error("이 포트가 이미 사용 중입니다. 기존 서버를 종료하거나 --port를 바꾸세요.")
    print(f"Local: http://127.0.0.1:{args.port}/", flush=True)
    print(f"Results: {state.directory}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
