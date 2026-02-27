from datetime import datetime, time, timedelta

from django.db import models
from django.core.exceptions import ValidationError


class RegionOption(models.Model):
    name = models.CharField("地域名称", max_length=50, unique=True)
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "地域选项"
        verbose_name_plural = "地域选项"
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.name


class ManagerOption(models.Model):
    name = models.CharField("主管姓名", max_length=50, unique=True)
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "主管选项"
        verbose_name_plural = "主管选项"
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.name


class DepartmentOption(models.Model):
    name = models.CharField("部门名称", max_length=50, unique=True)
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "部门选项"
        verbose_name_plural = "部门选项"
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.name


class HolidayPeriod(models.Model):
    """假期/休息时段：用于报表按“即将到来的假期或周末”分组显示。"""
    name = models.CharField("时段名称", max_length=100, help_text="如：春节假期、2月第1个周末")
    start_date = models.DateField("开始日期")
    end_date = models.DateField("结束日期")
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "假期/时段"
        verbose_name_plural = "假期/时段"
        ordering = ("start_date", "order")

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date} ~ {self.end_date})"

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("结束日期不能早于开始日期。")


class Notice(models.Model):
    """公告/规则说明，后台编辑后在前台展示。"""
    title = models.CharField("标题", max_length=200)
    content = models.TextField("内容", help_text="支持多行，可写规则说明。")
    is_active = models.BooleanField("是否展示", default=True)
    order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "公告/规则"
        verbose_name_plural = "公告/规则"
        ordering = ("order", "-updated_at")

    def __str__(self) -> str:
        return self.title


class OvertimeRecord(models.Model):

    employee_name = models.CharField("姓名", max_length=50)
    employee_id = models.CharField("工号", max_length=50)

    start_datetime = models.DateTimeField("加班开始时间")
    end_datetime = models.DateTimeField("加班结束时间")

    include_lunch_break = models.BooleanField(
        "跨午休时段时扣除 12:00-13:30", default=False
    )
    include_evening_break = models.BooleanField(
        "跨晚间时段时扣除 17:00-17:30", default=False
    )

    reason = models.TextField("加班原因", blank=True)
    department = models.CharField(
        "部门", max_length=50, blank=True, default="高斯实验室"
    )
    region = models.CharField("地域", max_length=20, blank=True, default="")
    manager = models.CharField("主管", max_length=50, blank=True, default="")

    overtime_hours = models.DecimalField(
        "加班时长（小时）", max_digits=5, decimal_places=2, editable=False
    )

    is_locked = models.BooleanField(
        "已冻结，不可再修改", default=False, help_text="冻结后只能在后台解除，前台无法再编辑。"
    )

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "加班记录"
        verbose_name_plural = "加班记录"
        ordering = ["-start_datetime", "employee_name"]

    def __str__(self) -> str:
        return f"{self.employee_name} {self.start_datetime.date()} 加班"

    @property
    def date(self):
        return self.start_datetime.date()

    def clean(self):
        # 已冻结的记录不允许修改（仅超管在后台可解锁）
        if self.pk:
            original = OvertimeRecord.objects.filter(pk=self.pk).first()
            if original:
                if original.is_locked:
                    raise ValidationError("该记录已冻结，无法修改。")
                # 禁止修改已保存记录的日期，只允许调整具体时间
                if (
                    self.start_datetime.date() != original.start_datetime.date()
                    or self.end_datetime.date() != original.end_datetime.date()
                ):
                    raise ValidationError("已保存记录的日期不能修改，只能调整时间。")

        if self.start_datetime >= self.end_datetime:
            raise ValidationError("结束时间必须晚于开始时间。")

        # 只允许同一天内的加班（跨天逻辑暂不支持）
        if self.start_datetime.date() != self.end_datetime.date():
            raise ValidationError("开始和结束时间必须在同一天内。")

        self.overtime_hours = self._calculate_overtime_hours()

        if self.overtime_hours > 8:
            raise ValidationError("扣除休息时间后，当日加班时间不能超过 8 小时。")

    def _calculate_overtime_hours(self) -> float:
        """
        计算扣除休息时间后的加班时长，单位小时。
        午休：12:00-13:30
        晚休：17:00-17:30
        """
        start = self.start_datetime
        end = self.end_datetime

        total_seconds = (end - start).total_seconds()
        if total_seconds <= 0:
            return 0

        # 基础时长（小时）
        hours = total_seconds / 3600.0

        base_date = start.date()

        def overlap_seconds(a_start, a_end, b_start, b_end) -> float:
            latest_start = max(a_start, b_start)
            earliest_end = min(a_end, b_end)
            if latest_start >= earliest_end:
                return 0
            return (earliest_end - latest_start).total_seconds()

        # 午休时间段
        if self.include_lunch_break:
            lunch_start = datetime.combine(base_date, time(12, 0))
            lunch_end = datetime.combine(base_date, time(13, 30))
            hours -= overlap_seconds(start, end, lunch_start, lunch_end) / 3600.0

        # 晚间休息时间段
        if self.include_evening_break:
            evening_start = datetime.combine(base_date, time(17, 0))
            evening_end = datetime.combine(base_date, time(17, 30))
            hours -= overlap_seconds(start, end, evening_start, evening_end) / 3600.0

        # 不允许负数
        if hours < 0:
            hours = 0

        # 四舍五入到 2 位小数
        return round(hours, 2)
