from datetime import date

from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import OvertimeRecordForm
from .models import HolidayPeriod, ManagerOption, Notice, OvertimeRecord, RegionOption


def overtime_apply(request):
    if request.method == "POST":
        form = OvertimeRecordForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("overtime_success")
    else:
        form = OvertimeRecordForm()

    return render(request, "overtime/apply.html", {"form": form, "is_edit": False})


def overtime_success(request):
    return render(request, "overtime/success.html")


def notice_list(request):
    """公告/规则列表，只展示 is_active=True 的公告。"""
    notices = Notice.objects.filter(is_active=True)
    return render(request, "overtime/notice_list.html", {"notices": notices})


def overtime_edit(request, pk: int):
    record = get_object_or_404(OvertimeRecord, pk=pk)

    if request.method == "POST":
        form = OvertimeRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            return redirect("overtime_report")
    else:
        form = OvertimeRecordForm(instance=record)

    return render(
        request,
        "overtime/apply.html",
        {
            "form": form,
            "is_edit": True,
            "record": record,
        },
    )


def overtime_report(request):
    """
    报表视图：
    - 支持按月份、地域、主管筛选
    - 结果为 HTML 表格，方便复制到 Outlook
    """
    qs = OvertimeRecord.objects.all()

    month = request.GET.get("month")  # 例如 2026-03
    regions = request.GET.getlist("region")
    manager = request.GET.get("manager") or ""

    # 报表按月总结：未提供月份或格式无效时默认当前月
    today = date.today()
    if not month or len(month) != 7 or month[4] != "-":
        month = f"{today.year:04d}-{today.month:02d}"
    try:
        year, m = int(month[:4]), int(month[5:7])
        if not (1 <= m <= 12):
            raise ValueError("invalid month")
        start_date = date(year, m, 1)
        if m == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, m + 1, 1)
    except (ValueError, IndexError):
        month = f"{today.year:04d}-{today.month:02d}"
        start_date = date(today.year, today.month, 1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1)
        else:
            end_date = date(today.year, today.month + 1, 1)
    qs = qs.filter(start_datetime__date__gte=start_date, start_datetime__date__lt=end_date)

    if regions:
        qs = qs.filter(region__in=regions)

    if manager:
        qs = qs.filter(manager=manager)

    qs = qs.order_by("region", "manager", "employee_name", "start_datetime")
    records_list = list(qs)

    # 当月内与所选月份有交集的假期/时段（按开始日期排序）
    periods_in_month = list(
        HolidayPeriod.objects.filter(
            start_date__lt=end_date,
            end_date__gte=start_date,
        ).order_by("start_date", "order")
    )

    # 把每条记录归到第一个包含其日期的时段；未归属的放进“其他日期”
    period_to_records = {p: [] for p in periods_in_month}
    other_records = []
    for record in records_list:
        rdate = record.start_datetime.date()
        assigned = False
        for period in periods_in_month:
            if period.start_date <= rdate <= period.end_date:
                period_to_records[period].append(record)
                assigned = True
                break
        if not assigned:
            other_records.append(record)

    # 前端展示：(时段, 该时段下的记录列表)；None 表示“其他日期”或“本月申报”
    period_sections = [(p, period_to_records[p]) for p in periods_in_month]
    if other_records:
        period_sections.append((None, other_records))
    # 未配置任何假期时段时，整月记录统一显示为“本月申报”
    if not period_sections and records_list:
        period_sections = [(None, records_list)]

    # 按地域 + 员工汇总（保留原有逻辑，若模板不用可后续删）
    summary = (
        qs.values("region", "employee_name", "employee_id")
        .annotate(total_hours=Sum("overtime_hours"))
        .order_by("region", "employee_name")
    )

    context = {
        "records": qs,
        "summary": summary,
        "period_sections": period_sections,
        "selected_month": month or "",
        "selected_regions": regions,
        "selected_manager": manager,
        "region_options": RegionOption.objects.all(),
        "manager_options": ManagerOption.objects.all(),
    }
    return render(request, "overtime/report.html", context)

