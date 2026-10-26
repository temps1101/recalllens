#!/usr/bin/env python3
"""Find repeatedly photographed places from the local Apple Photos database.

The database is opened read-only. No photographs or Photos records are modified.
"""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
EARTH_RADIUS_METERS = 6_371_000.0


@dataclass(frozen=True)
class Asset:
    uuid: str
    filename: str
    directory: str
    local_state: int
    latitude: float
    longitude: float
    captured_at: datetime


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        first_root, second_root = self.find(first), self.find(second)
        if first_root == second_root:
            return
        if self.rank[first_root] < self.rank[second_root]:
            first_root, second_root = second_root, first_root
        self.parent[second_root] = first_root
        if self.rank[first_root] == self.rank[second_root]:
            self.rank[first_root] += 1


def haversine(first: Asset, second: Asset) -> float:
    lat1, lon1 = math.radians(first.latitude), math.radians(first.longitude)
    lat2, lon2 = math.radians(second.latitude), math.radians(second.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(value))


def load_assets(database: Path) -> list[Asset]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            SELECT ZUUID, ZFILENAME, ZDIRECTORY, COALESCE(ZCLOUDLOCALSTATE, 0),
                   ZLATITUDE, ZLONGITUDE, ZDATECREATED
            FROM ZASSET
            WHERE ZKIND = 0
              AND COALESCE(ZTRASHEDSTATE, 0) = 0
              AND ZLATITUDE IS NOT NULL
              AND ZLONGITUDE IS NOT NULL
              AND ZLATITUDE BETWEEN -90 AND 90
              AND ZLONGITUDE BETWEEN -180 AND 180
              AND NOT (ZLATITUDE = 0 AND ZLONGITUDE = 0)
              AND ZDATECREATED IS NOT NULL
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        Asset(str(uuid), str(filename), str(directory), int(local_state), float(latitude), float(longitude), APPLE_EPOCH + timedelta(seconds=float(created)))
        for uuid, filename, directory, local_state, latitude, longitude, created in rows
    ]


def cluster(assets: list[Asset], radius: float) -> list[list[int]]:
    # A latitude degree is about 111.32 km. Fixed small cells keep neighborhood
    # searches bounded; longitude search width expands toward the poles.
    cell_degrees = radius / 111_320.0
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    union_find = UnionFind(len(assets))
    for index, asset in enumerate(assets):
        latitude_cell = math.floor(asset.latitude / cell_degrees)
        longitude_cell = math.floor(asset.longitude / cell_degrees)
        longitude_span = max(1, math.ceil(1 / max(0.1, math.cos(math.radians(asset.latitude)))))
        for latitude_offset in (-1, 0, 1):
            for longitude_offset in range(-longitude_span, longitude_span + 1):
                for other_index in buckets.get((latitude_cell + latitude_offset, longitude_cell + longitude_offset), []):
                    if haversine(asset, assets[other_index]) <= radius:
                        union_find.union(index, other_index)
        buckets[(latitude_cell, longitude_cell)].append(index)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(assets)):
        groups[union_find.find(index)].append(index)
    return list(groups.values())


def write_results(output: Path, assets: list[Asset], groups: list[list[int]], min_days: int, min_photos: int) -> None:
    candidates = []
    for members in groups:
        items = [assets[index] for index in members]
        days = {item.captured_at.date() for item in items}
        if len(items) < min_photos or len(days) < min_days:
            continue
        candidates.append((items, days))
    candidates.sort(key=lambda item: (len(item[1]), len(item[0])), reverse=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_name(output.stem + "_assets.csv")
    with output.open("w", newline="", encoding="utf-8") as target:
        fields = ["cluster_id", "photo_count", "distinct_days", "first_date", "last_date", "latitude", "longitude"]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for cluster_number, (items, days) in enumerate(candidates, start=1):
            writer.writerow({
                "cluster_id": f"place_{cluster_number:03d}",
                "photo_count": len(items),
                "distinct_days": len(days),
                "first_date": min(item.captured_at for item in items).isoformat(),
                "last_date": max(item.captured_at for item in items).isoformat(),
                "latitude": round(sum(item.latitude for item in items) / len(items), 7),
                "longitude": round(sum(item.longitude for item in items) / len(items), 7),
            })
    with manifest_path.open("w", newline="", encoding="utf-8") as target:
        fields = ["cluster_id", "uuid", "filename", "directory", "local_state", "captured_at", "latitude", "longitude"]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for cluster_number, (items, _) in enumerate(candidates, start=1):
            for item in sorted(items, key=lambda value: value.captured_at):
                writer.writerow({
                    "cluster_id": f"place_{cluster_number:03d}", "uuid": item.uuid,
                    "filename": item.filename, "directory": item.directory, "local_state": item.local_state,
                    "captured_at": item.captured_at.isoformat(),
                    "latitude": item.latitude, "longitude": item.longitude,
                })
    print(f"photos={len(assets)} candidate_places={len(candidates)}")
    print(f"summary={output}")
    print(f"assets={manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster Apple Photos by GPS without modifying the library.")
    parser.add_argument("--database", type=Path, default=Path.home() / "Pictures/Photos Library.photoslibrary/database/Photos.sqlite")
    parser.add_argument("--output", type=Path, default=Path(__file__).parents[1] / "experiments/output/photo_library_places.csv")
    parser.add_argument("--radius", type=float, default=35.0)
    parser.add_argument("--min-days", type=int, default=1)
    parser.add_argument("--min-photos", type=int, default=3)
    args = parser.parse_args()
    assets = load_assets(args.database)
    groups = cluster(assets, args.radius)
    write_results(args.output, assets, groups, args.min_days, args.min_photos)


if __name__ == "__main__":
    main()
