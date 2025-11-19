from django.contrib import admin
from .models import Course, Batch, Paper, Student, StudentMark, Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    search_fields = ('user__username', 'role')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'courseid', 'created_at')
    search_fields = ('name', 'courseid')
    list_filter = ('created_at',)
    ordering = ('-created_at',)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'course', 'year', 'is_active')
    search_fields = ('name', 'course__name', 'course__courseid')
    list_filter = ('is_active',)
    ordering = ('course__name', 'name')


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name', 'paper_type', 'max_marks')
    search_fields = ('code', 'name')
    list_filter = ('paper_type',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'regno', 'name', 'batch', 'email', 'is_active', 'created_at')
    search_fields = ('regno', 'name', 'email')
    list_filter = ('is_active', 'batch__course__name')


@admin.register(StudentMark)
class StudentMarkAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'paper', 'exam_type', 'batch', 'marks', 'created_at')
    search_fields = ('student__name', 'student__regno', 'paper__code')
    list_filter = ('exam_type', 'batch')
