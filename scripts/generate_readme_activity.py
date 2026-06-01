from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = ROOT / "assets" / "readme" / "content-activity.svg"
README = ROOT / "README.md"

SOURCES = [
    ("library.json", "papers", "论文"),
    ("blogs.json", "posts", "技术分享"),
    ("projects.json", "projects", "代码项目"),
]

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_activity() -> dict[date, Counter[str]]:
    activity: dict[date, Counter[str]] = defaultdict(Counter)

    for filename, collection_key, label in SOURCES:
        payload = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
        for item in payload.get(collection_key, []):
            if (item.get("status") or "approved") != "approved":
                continue
            added_at = item.get("added_at")
            if not added_at:
                continue
            activity[parse_date(added_at)][label] += 1

    return dict(sorted(activity.items()))


def week_start(day: date) -> date:
    return day - timedelta(days=(day.weekday() + 1) % 7)


def week_end(day: date) -> date:
    return week_start(day) + timedelta(days=6)


def level_for_count(count: int) -> int:
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 9:
        return 2
    if count <= 24:
        return 3
    return 4


def render_svg(activity: dict[date, Counter[str]]) -> str:
    if not activity:
        raise ValueError("No approved content with added_at was found.")

    first_day = min(activity)
    last_day = max(activity)
    grid_start = week_start(date(last_day.year, 1, 1))
    grid_end = week_end(last_day)

    weeks = ((grid_end - grid_start).days // 7) + 1
    cell = 14
    gap = 4
    grid_x = 58
    grid_y = 92
    grid_w = weeks * cell + (weeks - 1) * gap
    grid_h = 7 * cell + 6 * gap
    right_x = grid_x + grid_w + 54
    width = max(860, right_x + 240)
    height = 270

    daily_totals = {day: sum(counter.values()) for day, counter in activity.items()}
    total = sum(daily_totals.values())
    active_days = sum(1 for count in daily_totals.values() if count > 0)
    peak_day, peak_count = max(daily_totals.items(), key=lambda item: (item[1], item[0]))
    category_totals = Counter()
    for counter in activity.values():
        category_totals.update(counter)

    month_labels: list[str] = []
    previous_month = None
    year_start = date(last_day.year, 1, 1)
    for week_index in range(weeks):
        week_day = grid_start + timedelta(days=week_index * 7)
        month_in_week = None
        for offset in range(7):
            current = week_day + timedelta(days=offset)
            if current < year_start:
                continue
            if current.day == 1:
                month_in_week = current.month
                break
        if month_in_week and month_in_week != previous_month:
            x = grid_x + week_index * (cell + gap)
            month_labels.append(f'<text class="month" x="{x}" y="{grid_y - 14}">{MONTHS[month_in_week - 1]}</text>')
            previous_month = month_in_week

    weekday_labels = []
    for weekday_index in [1, 3, 5]:
        y = grid_y + weekday_index * (cell + gap) + 11
        weekday_labels.append(f'<text class="weekday" x="28" y="{y}">{WEEKDAYS[weekday_index]}</text>')

    cells = []
    for week_index in range(weeks):
        for weekday_index in range(7):
            current = grid_start + timedelta(days=week_index * 7 + weekday_index)
            count = daily_totals.get(current, 0)
            level = level_for_count(count)
            x = grid_x + week_index * (cell + gap)
            y = grid_y + weekday_index * (cell + gap)
            if current < first_day or current > last_day:
                klass = "outside"
            else:
                klass = f"lvl{level}"
            tooltip_parts = [f"{current.isoformat()}: {count}"]
            for _, _, label in SOURCES:
                value = activity.get(current, {}).get(label, 0)
                if value:
                    tooltip_parts.append(f"{label} {value}")
            tooltip = " / ".join(tooltip_parts)
            cells.append(
                f'<rect class="{klass}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3">'
                f"<title>{escape(tooltip)}</title></rect>"
            )

    category_rows = []
    bar_x = right_x
    bar_y = 112
    bar_w = 210
    category_colors = {
        "论文": "#0f766e",
        "技术分享": "#d97706",
        "代码项目": "#2563eb",
    }
    for index, (_, _, label) in enumerate(SOURCES):
        y = bar_y + index * 34
        value = category_totals[label]
        fill_w = round(bar_w * value / total) if total else 0
        category_rows.append(
            f'<text class="category-label" x="{bar_x}" y="{y - 5}">{label}</text>'
            f'<text class="category-value" x="{bar_x + bar_w}" y="{y - 5}" text-anchor="end">{value}</text>'
            f'<rect class="bar-track" x="{bar_x}" y="{y + 2}" width="{bar_w}" height="8" rx="4"/>'
            f'<rect x="{bar_x}" y="{y + 2}" width="{fill_w}" height="8" rx="4" fill="{category_colors[label]}"/>'
        )

    legend_x = grid_x
    legend_y = grid_y + grid_h + 30
    legend_cells = []
    for level in range(5):
        x = legend_x + 28 + level * 22
        legend_cells.append(f'<rect class="lvl{level}" x="{x}" y="{legend_y - 12}" width="14" height="14" rx="3"/>')

    generated = datetime.now().strftime("%Y-%m-%d")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Content activity heatmap</title>
  <desc id="desc">A static README calendar heatmap generated from added_at fields for approved papers, technical posts, and code projects.</desc>
  <style>
    .panel{{fill:#ffffff;stroke:#d0d7de}}
    .title{{font:700 22px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#24292f}}
    .subtitle,.month,.weekday,.legend,.meta{{font:500 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#57606a}}
    .stat-label,.category-label{{font:600 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#57606a}}
    .stat-value{{font:800 24px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#24292f}}
    .category-value{{font:800 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#24292f}}
    .lvl0{{fill:#ebedf0}}
    .lvl1{{fill:#9be9a8}}
    .lvl2{{fill:#40c463}}
    .lvl3{{fill:#30a14e}}
    .lvl4{{fill:#216e39}}
    .outside{{fill:#f6f8fa}}
    .bar-track{{fill:#ebedf0}}
    @media (prefers-color-scheme: dark){{
      .panel{{fill:#0d1117;stroke:#30363d}}
      .title,.stat-value,.category-value{{fill:#e6edf3}}
      .subtitle,.month,.weekday,.legend,.meta,.stat-label,.category-label{{fill:#8b949e}}
      .lvl0,.bar-track{{fill:#161b22}}
      .outside{{fill:#0d1117}}
    }}
  </style>

  <rect class="panel" x="8" y="8" width="{width - 16}" height="{height - 16}" rx="8"/>

  <text class="title" x="28" y="42">内容入库 Activity</text>
  <text class="subtitle" x="28" y="64">按 added_at 统计正式内容，生成静态 SVG 供 README 稳定展示。</text>

  <g transform="translate({right_x}, 36)">
    <text class="stat-label" x="0" y="0">总新增</text>
    <text class="stat-value" x="0" y="28">{total}</text>
    <text class="stat-label" x="92" y="0">活跃天数</text>
    <text class="stat-value" x="92" y="28">{active_days}</text>
    <text class="stat-label" x="184" y="0">峰值</text>
    <text class="stat-value" x="184" y="28">{peak_count}</text>
  </g>

  <g>
    {''.join(month_labels)}
    {''.join(weekday_labels)}
    {''.join(cells)}
  </g>

  <g>
    <text class="stat-label" x="{right_x}" y="92">分类占比</text>
    {''.join(category_rows)}
    <text class="meta" x="{right_x}" y="218">峰值日期：{peak_day.isoformat()} · 更新：{generated}</text>
  </g>

  <g>
    <text class="legend" x="{legend_x}" y="{legend_y}">少</text>
    {''.join(legend_cells)}
    <text class="legend" x="{legend_x + 146}" y="{legend_y}">多</text>
    <text class="legend" x="{legend_x + 214}" y="{legend_y}">0 / 1-2 / 3-9 / 10-24 / 25+</text>
  </g>
</svg>
"""


def markdown_table(activity: dict[date, Counter[str]]) -> str:
    lines = [
        "| 日期 | 论文 | 技术分享 | 代码项目 | 总计 |",
        "|---|---:|---:|---:|---:|",
    ]
    for day, counter in activity.items():
        paper_count = counter["论文"]
        blog_count = counter["技术分享"]
        project_count = counter["代码项目"]
        total = paper_count + blog_count + project_count
        lines.append(f"| {day.isoformat()} | {paper_count} | {blog_count} | {project_count} | {total} |")
    return "\n".join(lines)


def update_readme(activity: dict[date, Counter[str]]) -> None:
    table = markdown_table(activity)
    content = README.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(\| 日期 \| 论文 \| 技术分享 \| 代码项目 \| 总计 \|\n"
        r"\|---\|---:\|---:\|---:\|---:\|\n"
        r"(?:\| .+\n)+)"
    )
    updated, replacements = pattern.subn(table + "\n", content, count=1)
    if replacements != 1:
        raise ValueError("Could not find the activity count table in README.md.")
    README.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the README content activity heatmap.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--update-readme", action="store_true")
    args = parser.parse_args()

    activity = load_activity()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(activity), encoding="utf-8")
    if args.update_readme:
        update_readme(activity)


if __name__ == "__main__":
    main()
