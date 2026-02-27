from django.contrib import admin

from .models import (
    DepartmentOption,
    HolidayPeriod,
    ManagerOption,
    Notice,
    OvertimeRecord,
    RegionOption,
)


@admin.register(RegionOption)
class RegionOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    ordering = ("order", "id")


@admin.register(ManagerOption)
class ManagerOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    ordering = ("order", "id")


@admin.register(DepartmentOption)
class DepartmentOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    ordering = ("order", "id")


@admin.register(HolidayPeriod)
class HolidayPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "order")
    list_editable = ("order",)
    ordering = ("start_date", "order")


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "order", "updated_at")
    list_editable = ("is_active", "order")
    ordering = ("order", "-updated_at")


@admin.register(OvertimeRecord)
class OvertimeRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee_name",
        "employee_id",
        "date",
        "department",
        "region",
        "manager",
        "overtime_hours",
        "is_locked",
        "start_datetime",
        "end_datetime",
        "include_lunch_break",
        "include_evening_break",
    )
    list_filter = ("region", "manager", "is_locked", "start_datetime")
    list_editable = ("is_locked",)
    search_fields = ("employee_name", "employee_id")
    actions = ["bulk_freeze", "bulk_unfreeze"]

    @admin.action(description="批量冻结选中记录")
    def bulk_freeze(self, request, queryset):
        n = queryset.update(is_locked=True)
        self.message_user(request, f"已冻结 {n} 条记录，前台将无法再编辑。")

    @admin.action(description="批量解冻选中记录")
    def bulk_unfreeze(self, request, queryset):
        n = queryset.update(is_locked=False)
        self.message_user(request, f"已解冻 {n} 条记录，前台可继续编辑。")
