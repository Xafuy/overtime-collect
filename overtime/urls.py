from django.urls import path

from . import views


urlpatterns = [
    path("", views.overtime_apply, name="overtime_apply"),
    path("success/", views.overtime_success, name="overtime_success"),
    path("report/", views.overtime_report, name="overtime_report"),
    path("edit/<int:pk>/", views.overtime_edit, name="overtime_edit"),
    path("delete/<int:pk>/", views.overtime_delete, name="overtime_delete"),
    path("notice/", views.notice_list, name="notice_list"),
]

