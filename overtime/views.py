from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import OvertimeRecordForm
from .models import ApprovalBatch, HolidayPeriod, ManagerOption, Notice, OvertimeRecord, RegionOption


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


def _report_query_and_params(request):
    """报表筛选逻辑：返回 (queryset, selected_month, selected_regions, selected_manager, start_date, end_date)。"""
    qs = OvertimeRecord.objects.all()
    month = request.GET.get("month")
    regions = request.GET.getlist("region")
    manager = request.GET.get("manager") or ""
    today = date.today()
    if not month or len(month) != 7 or month[4] != "-":
        month = f"{today.year:04d}-{today.month:02d}"
    try:
        year, m = int(month[:4]), int(month[5:7])
        if not (1 <= m <= 12):
            raise ValueError("invalid month")
        start_date = date(year, m, 1)
        end_date = date(year + 1, 1, 1) if m == 12 else date(year, m + 1, 1)
    except (ValueError, IndexError):
        month = f"{today.year:04d}-{today.month:02d}"
        start_date = date(today.year, today.month, 1)
        end_date = (
            date(today.year + 1, 1, 1)
            if today.month == 12
            else date(today.year, today.month + 1, 1)
        )
    qs = qs.filter(start_datetime__date__gte=start_date, start_datetime__date__lt=end_date)
    if regions:
        qs = qs.filter(region__in=regions)
    if manager:
        qs = qs.filter(manager=manager)
    qs = qs.order_by("region", "manager", "employee_name", "start_datetime")
    return qs, month or "", regions, manager, start_date, end_date


def overtime_report_copy(request):
    """
    复制用完整表视图：按假期分组，完整列格式便于复制到 Excel；冻结/邮件/可上报仅在状态参考区显示，不进入表格。
    """
    qs, selected_month, selected_regions, selected_manager, start_date, end_date = _report_query_and_params(request)
    records_list = list(qs)

    periods_in_month = list(
        HolidayPeriod.objects.filter(
            start_date__lt=end_date,
            end_date__gte=start_date,
        ).order_by("start_date", "order")
    )
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
    period_sections = [(p, period_to_records[p]) for p in periods_in_month]
    if other_records:
        period_sections.append((None, other_records))
    if not period_sections and records_list:
        period_sections = [(None, records_list)]

    context = {
        "period_sections": period_sections,
        "records": records_list,
        "selected_month": selected_month,
        "selected_regions": selected_regions,
        "selected_manager": selected_manager,
        "region_options": RegionOption.objects.all(),
        "manager_options": ManagerOption.objects.all(),
    }
    return render(request, "overtime/report_copy.html", context)


def batch_unified_approval(request):
    """
    批量标记为「已统一发邮件」：先由报表页提交选中的记录 id，再本页上传一封邮件附件，一次生效多条。
    """
    # 从报表页 POST 过来的选中 id 及筛选参数
    if request.method == "POST" and not request.FILES.get("attachment"):
        ids = [int(x) for x in request.POST.getlist("ids") if str(x).isdigit()]
        if ids:
            request.session["batch_approval_ids"] = ids
            request.session["batch_approval_report_params"] = {
                "month": request.POST.get("month") or "",
                "manager": request.POST.get("manager") or "",
                "regions": request.POST.getlist("region"),
            }
        return redirect("batch_unified_approval")

    ids = request.session.get("batch_approval_ids") or []
    report_params = request.session.get("batch_approval_report_params") or {}
    if not ids:
        for key in ("batch_approval_ids", "batch_approval_report_params"):
            request.session.pop(key, None)
        return redirect("overtime_report")

    if request.method == "POST" and request.FILES.get("attachment"):
        note = (request.POST.get("note") or "").strip()
        batch = ApprovalBatch.objects.create(note=note, attachment=request.FILES["attachment"])
        valid_ids = [
            pk for pk in ids
            if isinstance(pk, int)
            and OvertimeRecord.objects.filter(pk=pk, email_status=OvertimeRecord.EMAIL_STATUS_PENDING).exists()
        ]
        n = OvertimeRecord.objects.filter(pk__in=valid_ids).update(
            email_status=OvertimeRecord.EMAIL_STATUS_UNIFIED,
            approval_batch=batch,
            approval_attachment=None,
        )
        for key in ("batch_approval_ids", "batch_approval_report_params"):
            if key in request.session:
                del request.session[key]
        messages.success(request, f"已成功将 {n} 条记录标记为「已统一发邮件」并关联审批附件。")
        params = {
            k: v for k, v in [
                ("month", report_params.get("month")),
                ("manager", report_params.get("manager")),
            ] if v
        }
        if report_params.get("regions"):
            params["region"] = report_params["regions"]
        url = reverse("overtime_report")
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"
        return redirect(url)

    records = list(OvertimeRecord.objects.filter(pk__in=ids).order_by("start_datetime")[:100])
    return render(
        request,
        "overtime/batch_approval.html",
        {"record_ids": ids, "records": records, "report_params": report_params},
    )


def personal_approval(request, pk: int):
    """单条记录上传「个人补发」邮件附件，标记为已个人补发并可上报。"""
    record = get_object_or_404(OvertimeRecord, pk=pk)
    if request.method == "POST":
        attachment = request.FILES.get("attachment")
        if attachment:
            if record.approval_attachment:
                record.approval_attachment.delete(save=False)
            record.approval_attachment = attachment
            record.email_status = OvertimeRecord.EMAIL_STATUS_PERSONAL
            record.approval_batch = None
            record.save()
            messages.success(request, "已上传补发邮件附件，该条记录已标记为「已个人补发」并可上报。")
        params = {}
        if request.POST.get("month"):
            params["month"] = request.POST.get("month")
        if request.POST.get("manager"):
            params["manager"] = request.POST.get("manager")
        for r in request.POST.getlist("region"):
            params.setdefault("region", []).append(r)
        url = reverse("overtime_report")
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"
        return redirect(url)
    # GET：从报表带来的筛选参数，用于个人上传页的表单隐藏域
    report_params = {
        "month": request.GET.get("month", ""),
        "manager": request.GET.get("manager", ""),
        "regions": request.GET.getlist("region"),
    }
    return render(
        request,
        "overtime/personal_approval.html",
        {"record": record, "report_params": report_params},
    )


def overtime_delete(request, pk: int):
    """
    报表中单条记录删除。
    仅接受 POST 请求，删除后回到报表页，并尽量保留当前筛选条件。
    """
    record = get_object_or_404(OvertimeRecord, pk=pk)
    if request.method != "POST":
        return redirect("overtime_report")

    record.delete()

    # 删除后带着原有筛选条件返回报表
    month = request.POST.get("month") or ""
    manager = request.POST.get("manager") or ""
    regions = request.POST.getlist("region")

    params = {}
    if month:
        params["month"] = month
    if manager:
        params["manager"] = manager
    if regions:
        params["region"] = regions

    url = reverse("overtime_report")
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    return redirect(url)

