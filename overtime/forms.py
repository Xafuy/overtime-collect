from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone

from .models import ManagerOption, OvertimeRecord, RegionOption


class OvertimeRecordForm(forms.ModelForm):
    class Meta:
        model = OvertimeRecord
        fields = [
            "employee_name",
            "employee_id",
            "start_datetime",
            "end_datetime",
            "include_lunch_break",
            "include_evening_break",
            "reason",
            "region",
            "manager",
        ]
        widgets = {
            "start_datetime": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "class": "form-control"},
            ),
            "end_datetime": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "class": "form-control"},
            ),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 新建表单时，默认次日 8:00 - 17:30，并勾选休息扣除选项
        if not self.is_bound and not self.instance.pk:
            now = timezone.now()
            tomorrow = (now + timedelta(days=1)).date()

            default_start = datetime.combine(tomorrow, time(8, 0))
            default_end = datetime.combine(tomorrow, time(17, 30))

            self.initial.setdefault("start_datetime", default_start)
            self.initial.setdefault("end_datetime", default_end)
            # 显式设置字段初始值为符合 datetime-local 的字符串
            start_str = default_start.strftime("%Y-%m-%dT%H:%M")
            end_str = default_end.strftime("%Y-%m-%dT%H:%M")
            if "start_datetime" in self.fields:
                self.fields["start_datetime"].initial = start_str
            if "end_datetime" in self.fields:
                self.fields["end_datetime"].initial = end_str

            # 默认勾选“跨午休/晚间时段时扣除”
            if "include_lunch_break" in self.fields:
                self.fields["include_lunch_break"].initial = True
            if "include_evening_break" in self.fields:
                self.fields["include_evening_break"].initial = True

        # 用 ChoiceField 替换地域、主管，确保下拉框有选项（ModelForm 的 CharField 不保证渲染 options）
        region_choices = [("", "请选择地域")] + [
            (r.name, r.name) for r in RegionOption.objects.order_by("order", "id")
        ]
        manager_choices = [("", "请选择主管")] + [
            (m.name, m.name) for m in ManagerOption.objects.order_by("order", "id")
        ]
        self.fields["region"] = forms.ChoiceField(
            label="地域",
            choices=region_choices,
            required=False,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        self.fields["manager"] = forms.ChoiceField(
            label="主管",
            choices=manager_choices,
            required=False,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        # 编辑时回填已保存的值
        if self.instance and self.instance.pk:
            self.fields["region"].initial = self.instance.region or ""
            self.fields["manager"].initial = self.instance.manager or ""

        # 统一样式
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            # 对已经设置 class 的选择框不会被覆盖
            field.widget.attrs["class"] = (css + " form-control").strip()

        # 勾选框单独处理
        for name in ("include_lunch_break", "include_evening_break"):
            if name in self.fields:
                self.fields[name].widget.attrs["class"] = "form-check-input"

