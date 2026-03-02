"""
每月第 5 天及之后，自动将上一个自然月的加班记录设为已冻结。
建议用 cron 每日执行，例如：0 1 6-31 * *  (每月 6～31 号凌晨 1 点) 或每天凌晨执行一次。
"""
from datetime import date
from typing import Optional, Tuple

from django.core.management.base import BaseCommand

from overtime.models import OvertimeRecord


def get_previous_month(today: date) -> Optional[Tuple[int, int]]:
    """返回 (year, month)，若当前为 1 月则返回去年 12 月。"""
    if today.month == 1:
        return (today.year - 1, 12)
    return (today.year, today.month - 1)


class Command(BaseCommand):
    help = "每月第 5 天及之后，自动冻结上一个自然月的加班记录（is_locked=True）。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只打印将要冻结的记录数，不实际更新。",
        )
        parser.add_argument(
            "--force-date",
            type=str,
            metavar="YYYY-MM-DD",
            help="指定“今天”的日期，用于测试（默认使用系统日期）。",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force_date = options.get("force_date")

        if force_date:
            try:
                parts = force_date.strip().split("-")
                if len(parts) != 3:
                    raise ValueError("需要 YYYY-MM-DD 格式")
                today = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError) as e:
                self.stderr.write(self.style.ERROR(f"无效日期 {force_date!r}: {e}"))
                return
        else:
            today = date.today()

        if today.day < 5:
            self.stdout.write(
                f"今日为 {today}，未到当月第 5 天，不执行上月冻结。"
            )
            return

        prev = get_previous_month(today)
        if not prev:
            return
        prev_year, prev_month = prev
        start_date = date(prev_year, prev_month, 1)
        if prev_month == 12:
            end_date = date(prev_year + 1, 1, 1)
        else:
            end_date = date(prev_year, prev_month + 1, 1)

        qs = OvertimeRecord.objects.filter(
            start_datetime__date__gte=start_date,
            start_datetime__date__lt=end_date,
            is_locked=False,
        )
        count = qs.count()
        if count == 0:
            self.stdout.write(
                f"{start_date.strftime('%Y-%m')} 无未冻结记录，无需操作。"
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] 将冻结 {start_date.strftime('%Y-%m')} 的 {count} 条加班记录。"
                )
            )
            return

        qs.update(is_locked=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"已冻结 {start_date.strftime('%Y-%m')} 的 {count} 条加班记录。"
            )
        )
