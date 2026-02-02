from django.contrib import admin
from .models import Regulation, Program, AcademicYear, Semester, Course


@admin.register(Regulation)
class RegulationAdmin(admin.ModelAdmin):
    list_display = ('year', 'name', 'is_active', 'effective_from')
    list_filter = ('is_active',)
    search_fields = ('year', 'name')


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'degree', 'level', 'duration_years', 'is_active')
    list_filter = ('level', 'degree', 'is_active')
    search_fields = ('code', 'name', 'specialization')
    filter_horizontal = ('regulations',)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'semester_number', 'semester_type', 'start_date', 'end_date', 'is_current')
    list_filter = ('academic_year', 'semester_type', 'is_current')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'title', 'regulation', 'course_type', 'credits', 'semester', 'branch')
    list_filter = ('regulation', 'course_type', 'branch', 'semester')
    search_fields = ('course_code', 'title')
