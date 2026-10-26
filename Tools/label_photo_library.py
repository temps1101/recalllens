#!/usr/bin/env python3
"""Keyboard-first, symmetric pair labeling for Recalllens."""

from __future__ import annotations

import csv
import html
import io
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

ROOT = Path(__file__).parents[1]
EXPERIMENTS = ROOT / "experiments"
PLACES_CSV = EXPERIMENTS / "output/photo_library_places.csv"
ASSETS_CSV = EXPERIMENTS / "output/photo_library_places_assets.csv"
LABELS_CSV = EXPERIMENTS / "data/photo_library_pair_labels.csv"
CANDIDATES_CSV = EXPERIMENTS / "output/photo_library_label_candidates.csv"
ORIGINALS = Path.home() / "Pictures/Photos Library.photoslibrary/originals"
MAX_IMAGES = 8
LABEL_NAMES = {"same_scene": "同じシーン", "different_scene": "違うシーン", "skip": "保留"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def image_path(asset: dict[str, str]) -> Path:
    return ORIGINALS / asset["directory"] / asset["filename"]


def representative_images(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    """Select a small, time-diverse subset; same-day photographs remain eligible."""
    local = [asset for asset in assets if image_path(asset).exists()]
    if len(local) <= MAX_IMAGES:
        return local
    local.sort(key=lambda row: row["captured_at"])
    indices = sorted({round(index * (len(local) - 1) / (MAX_IMAGES - 1)) for index in range(MAX_IMAGES)})
    return [local[index] for index in indices]


def review_pairs(assets: list[dict[str, str]]) -> list[tuple[dict[str, str], dict[str, str]]]:
    """Build a bounded graph: adjacent times plus long-range comparisons."""
    images = representative_images(assets)
    if len(images) < 2:
        return []
    index_pairs: list[tuple[int, int]] = [(index, index + 1) for index in range(len(images) - 1)]
    distance = 2
    while len(index_pairs) < MAX_PAIRS and distance < len(images):
        for left in range(len(images) - distance):
            pair = (left, left + distance)
            if pair not in index_pairs:
                index_pairs.append(pair)
                if len(index_pairs) == MAX_PAIRS:
                    break
        distance += 1
    return [(images[left], images[right]) for left, right in index_pairs]


def pair_key(cluster: str, first: str, second: str) -> tuple[str, str, str]:
    left, right = sorted((first, second))
    return cluster, left, right


def load_labels() -> dict[tuple[str, str, str], dict[str, str]]:
    if not LABELS_CSV.exists():
        return {}
    return {pair_key(row["cluster_id"], row["asset_a_uuid"], row["asset_b_uuid"]): row for row in read_csv(LABELS_CSV)}


def save_labels(rows: dict[tuple[str, str, str], dict[str, str]]) -> None:
    LABELS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = ["cluster_id", "asset_a_uuid", "asset_b_uuid", "asset_a_filename", "asset_b_filename", "label", "recorded_at"]
    temporary = LABELS_CSV.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: (row["cluster_id"], row["asset_a_uuid"], row["asset_b_uuid"])))
    temporary.replace(LABELS_CSV)


class Handler(BaseHTTPRequestHandler):
    places = read_csv(PLACES_CSV)
    assets_by_cluster: dict[str, list[dict[str, str]]] = defaultdict(list)
    assets_by_uuid: dict[str, dict[str, str]] = {}
    for asset in read_csv(ASSETS_CSV):
        assets_by_cluster[asset["cluster_id"]].append(asset)
        assets_by_uuid[asset["uuid"]] = asset
    for assets in assets_by_cluster.values():
        assets.sort(key=lambda row: row["captured_at"])
    candidate_pairs_by_cluster: dict[str, list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    if CANDIDATES_CSV.exists():
        for candidate in read_csv(CANDIDATES_CSV):
            first = assets_by_uuid.get(candidate["asset_a_uuid"])
            second = assets_by_uuid.get(candidate["asset_b_uuid"])
            if first and second:
                candidate_pairs_by_cluster[candidate["cluster_id"]].append((first, second))

    @classmethod
    def all_pairs(cls) -> list[tuple[str, dict[str, str], dict[str, str]]]:
        return [
            (cluster, first, second)
            for cluster in sorted(cls.candidate_pairs_by_cluster)
            for first, second in cls.candidate_pairs_by_cluster[cluster]
        ]

    @classmethod
    def pairs_for_cluster(cls, cluster: str) -> list[tuple[dict[str, str], dict[str, str]]]:
        return cls.candidate_pairs_by_cluster.get(cluster, review_pairs(cls.assets_by_cluster.get(cluster, [])))

    def page(self, content: str, title: str = "Recalllens Pair Labeler", status: HTTPStatus = HTTPStatus.OK) -> None:
        document = f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>
<style>
:root{{--bg:#080b10;--panel:#111720;--line:#293342;--text:#f4f7fb;--muted:#9aa6b6;--blue:#2f81f7;--green:#238636;--orange:#b86b16;--gray:#424b57}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px -apple-system,BlinkMacSystemFont,sans-serif}}header{{height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 22px;border-bottom:1px solid var(--line)}}main{{max-width:1500px;margin:auto;padding:18px}}a{{color:#6aa7ff;text-decoration:none}}.muted{{color:var(--muted)}}
.places{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}}.place{{display:block;padding:14px;background:var(--panel);border:1px solid var(--line);border-radius:10px}}.place:hover{{border-color:var(--blue)}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:14px;height:calc(100vh - 220px);min-height:430px}}.photo{{position:relative;background:#000;border:1px solid var(--line);border-radius:12px;overflow:hidden}}.photo img{{width:100%;height:100%;object-fit:contain}}.badge{{position:absolute;top:12px;left:12px;padding:7px 10px;background:#000b;border-radius:7px}}.meta{{position:absolute;bottom:0;left:0;right:0;padding:24px 12px 10px;background:linear-gradient(transparent,#000e);font-size:13px}}
.actions{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:12px}}button{{padding:13px;border:0;border-radius:9px;color:white;font-weight:700;font-size:15px;cursor:pointer}}.same{{background:var(--green)}}.different{{background:var(--orange)}}.skip{{background:var(--gray)}}.nav{{display:flex;justify-content:center;gap:22px;margin-top:10px}}.key{{display:inline-grid;place-items:center;min-width:27px;padding:3px 7px;background:#222b36;border:1px solid #455166;border-radius:5px;font:12px ui-monospace}}.progress{{height:4px;background:#202834;margin:8px 0 14px}}.progress span{{display:block;height:100%;background:var(--blue)}}
@media(max-width:800px){{.pair{{grid-template-columns:1fr;height:auto}}.photo{{height:42vh}}}}
</style></head><body><header><strong>Recalllens — 対称ペア分類</strong><span class='muted'>左右は対等です</span></header><main>{content}</main></body></html>"""
        payload = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, target: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", target)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/image":
            return self.serve_image(query.get("uuid", [""])[0])
        if parsed.path == "/review":
            return self.review(query)
        if parsed.path == "/cluster":
            cluster = query.get("id", [""])[0]
            pairs = self.all_pairs()
            index = next((i for i, item in enumerate(pairs) if item[0] == cluster), 0)
            return self.redirect(f"/review?i={index}")
        return self.redirect("/review")

    def priority_places(self) -> list[dict[str, str]]:
        labels = load_labels()
        result = []
        for place in self.places:
            pairs = self.pairs_for_cluster(place["cluster_id"])
            if not pairs:
                continue
            reviewed = sum(pair_key(place["cluster_id"], first["uuid"], second["uuid"]) in labels for first, second in pairs)
            score = min(int(place["distinct_days"]), 10) * 3 + len(pairs) - reviewed * 3
            result.append({**place, "pair_count": str(len(pairs)), "reviewed": str(reviewed), "score": str(score)})
        return sorted(result, key=lambda row: (-int(row["score"]), int(row["photo_count"])))

    def review(self, query: dict[str, list[str]]) -> None:
        pairs = self.all_pairs()
        if not pairs:
            return self.page("<p>比較可能な写真がありません。</p>", status=HTTPStatus.NOT_FOUND)
        labels = load_labels()
        requested = int(query.get("i", ["-1"])[0])
        if requested < 0:
            requested = next((index for index, (cluster, a, b) in enumerate(pairs) if pair_key(cluster, a["uuid"], b["uuid"]) not in labels), 0)
        index = max(0, min(requested, len(pairs) - 1))
        cluster, first, second = pairs[index]
        existing = labels.get(pair_key(cluster, first["uuid"], second["uuid"]))
        previous_url = f"/review?i={max(0,index-1)}"
        next_url = f"/review?i={min(len(pairs)-1,index+1)}"
        percent = round((index + 1) / len(pairs) * 100)
        status = f"・保存済み: {LABEL_NAMES[existing['label']]}" if existing else ""
        reviewed_count = sum(pair_key(c, a["uuid"], b["uuid"]) in labels for c, a, b in pairs)
        content = f"""<div><strong>{cluster}</strong>　<span class='muted'>全体 {index+1}/{len(pairs)}・分類済み {reviewed_count}/{len(pairs)}{status}</span></div><div class='progress'><span style='width:{percent}%'></span></div>
<div class='pair'>{self.photo(first, '写真 A')}{self.photo(second, '写真 B')}</div>
<form id='form' method='post' action='/label'><input type='hidden' name='cluster_id' value='{cluster}'><input type='hidden' name='asset_a_uuid' value='{first['uuid']}'><input type='hidden' name='asset_b_uuid' value='{second['uuid']}'><input type='hidden' name='index' value='{index}'><input id='label' type='hidden' name='label'>
<div class='actions'><button type='button' class='same' onclick="submitLabel('same_scene')"><span class='key'>S</span> 同じシーン</button><button type='button' class='different' onclick="submitLabel('different_scene')"><span class='key'>D</span> 違うシーン</button><button type='button' class='skip' onclick="submitLabel('skip')"><span class='key'>X</span> 保留</button></div></form>
<div class='nav'><a href='{previous_url}'>← 前</a><a href='{next_url}'>次 →</a></div>
<script>const form=document.getElementById('form'),field=document.getElementById('label');function submitLabel(v){{field.value=v;form.submit()}}document.addEventListener('keydown',e=>{{if(e.repeat)return;const k=e.key.toLowerCase();if(k==='s')submitLabel('same_scene');else if(k==='d')submitLabel('different_scene');else if(k==='x')submitLabel('skip');else if(e.key==='ArrowLeft')location.href='{previous_url}';else if(e.key==='ArrowRight'||e.key===' ')location.href='{next_url}'}})</script>"""
        self.page(content, cluster)

    def photo(self, asset: dict[str, str], label: str) -> str:
        return f"<section class='photo'><img src='/image?uuid={asset['uuid']}'><span class='badge'>{label}</span><div class='meta'>{html.escape(asset['captured_at'][:16])}<br>{html.escape(asset['filename'])}</div></section>"

    def serve_image(self, uuid: str) -> None:
        asset = self.assets_by_uuid.get(uuid)
        if not asset or not image_path(asset).exists():
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            with Image.open(image_path(asset)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1200, 1200))
                output = io.BytesIO()
                image.save(output, "JPEG", quality=86)
            payload = output.getvalue()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "private,max-age=3600")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as error:
            self.send_error(HTTPStatus.UNPROCESSABLE_ENTITY, str(error))

    def do_POST(self) -> None:
        if urllib.parse.urlparse(self.path).path != "/label":
            return self.send_error(HTTPStatus.NOT_FOUND)
        length = int(self.headers.get("Content-Length", "0"))
        form = {key: values[0] for key, values in urllib.parse.parse_qs(self.rfile.read(length).decode()).items()}
        cluster, first_uuid, second_uuid, label = form.get("cluster_id", ""), form.get("asset_a_uuid", ""), form.get("asset_b_uuid", ""), form.get("label", "")
        if label not in LABEL_NAMES or first_uuid not in self.assets_by_uuid or second_uuid not in self.assets_by_uuid:
            return self.send_error(HTTPStatus.BAD_REQUEST)
        first, second = self.assets_by_uuid[first_uuid], self.assets_by_uuid[second_uuid]
        rows = load_labels()
        key = pair_key(cluster, first_uuid, second_uuid)
        ordered = sorted((first, second), key=lambda row: row["uuid"])
        rows[key] = {"cluster_id": cluster, "asset_a_uuid": ordered[0]["uuid"], "asset_b_uuid": ordered[1]["uuid"], "asset_a_filename": ordered[0]["filename"], "asset_b_filename": ordered[1]["filename"], "label": label, "recorded_at": datetime.now(timezone.utc).isoformat()}
        save_labels(rows)
        all_pairs = self.all_pairs()
        next_index = min(int(form.get("index", "0")) + 1, len(all_pairs) - 1)
        self.redirect(f"/review?i={next_index}")

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    if not PLACES_CSV.exists() or not ASSETS_CSV.exists():
        raise SystemExit("Run Tools/cluster_photos_library.py first.")
    if not CANDIDATES_CSV.exists():
        raise SystemExit("Run Tools/build_label_candidates.py first.")
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Recalllens symmetric pair labeler: http://127.0.0.1:8765")
    print(f"Labels: {LABELS_CSV}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
