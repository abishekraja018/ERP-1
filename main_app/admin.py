from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Account_User, Regulation, AcademicYear, Semester,
    Faculty_Profile, NonTeachingStaff_Profile, Student_Profile,
    Course, Course_Assignment, Attendance,
    Publication, Student_Achievement, Lab_Issue_Log,
    LeaveRequest, Feedback, Event, EventRegistration,
    Notification, Announcement
)


# =============================================================================
# USER ADMIN
# =============================================================================

@admin.register(Account_User)
class AccountUserAdmin(UserAdmin):
    list_display = ('email', 'full_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'gender')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'gender', 'phone', 'profile_pic', 'address')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )


# =============================================================================
# ACADEMIC STRUCTURE ADMINS
# =============================================================================

@admin.register(Regulation)
class RegulationAdmin(admin.ModelAdmin):
    list_display = ('year', 'name', 'is_active', 'effective_from')
    list_filter = ('is_active',)
    search_fields = ('year', 'name')


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'semester_number', 'semester_type', 'is_current')
    list_filter = ('academic_year', 'semester_type', 'is_current')


# =============================================================================
# PROFILE ADMINS
# =============================================================================

@admin.register(Faculty_Profile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'designation', 'is_external', 'specialization')
    list_filter = ('designation', 'is_external')
    search_fields = ('staff_id', 'user__full_name', 'user__email', 'specialization')
    raw_id_fields = ('user',)


@admin.register(NonTeachingStaff_Profile)
class NonTeachingStaffProfileAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'staff_type', 'department', 'assigned_lab')
    list_filter = ('staff_type', 'department')
    search_fields = ('staff_id', 'user__full_name', 'user__email')
    raw_id_fields = ('user',)


@admin.register(Student_Profile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('register_no', 'user', 'branch', 'batch_label', 'current_sem', 'program_type')
    list_filter = ('branch', 'batch_label', 'current_sem', 'program_type', 'regulation')
    search_fields = ('register_no', 'user__full_name', 'user__email')
    raw_id_fields = ('user', 'advisor')


# =============================================================================
# ACADEMIC & ATTENDANCE ADMINS
# =============================================================================

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'title', 'regulation', 'semester', 'credits', 'course_type', 'branch')
    list_filter = ('regulation', 'semester', 'course_type', 'branch', 'is_lab')
    search_fields = ('course_code', 'title')


@admin.register(Course_Assignment)
class CourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ('course', 'faculty', 'batch_label', 'academic_year', 'semester', 'is_active')
    list_filter = ('academic_year', 'semester', 'batch_label', 'is_active')
    search_fields = ('course__course_code', 'course__title', 'faculty__user__full_name')
    raw_id_fields = ('course', 'faculty')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'date', 'period', 'status')
    list_filter = ('status', 'date', 'period')
    search_fields = ('student__register_no', 'student__user__full_name')
    date_hierarchy = 'date'
    raw_id_fields = ('student', 'assignment', 'marked_by')


# =============================================================================
# RESEARCH & ACHIEVEMENT ADMINS
# =============================================================================

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('title_short', 'faculty', 'pub_type', 'journal_name', 'year', 'indexing', 'is_verified')
    list_filter = ('pub_type', 'indexing', 'year', 'is_verified')
    search_fields = ('title', 'journal_name', 'faculty__user__full_name', 'doi')
    raw_id_fields = ('faculty', 'verified_by')
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'


@admin.register(Student_Achievement)
class StudentAchievementAdmin(admin.ModelAdmin):
    list_display = ('student', 'event_name', 'event_type', 'award_category', 'event_date', 'is_verified')
    list_filter = ('event_type', 'award_category', 'is_verified')
    search_fields = ('event_name', 'student__register_no', 'student__user__full_name')
    date_hierarchy = 'event_date'
    raw_id_fields = ('student', 'verified_by')


# =============================================================================
# LAB SUPPORT ADMIN
# =============================================================================

@admin.register(Lab_Issue_Log)
class LabIssueLogAdmin(admin.ModelAdmin):
    list_display = ('lab_name', 'place_code', 'issue_category', 'priority', 'status', 'reported_by', 'reported_at')
    list_filter = ('lab_name', 'issue_category', 'status', 'priority')
    search_fields = ('place_code', 'description', 'reported_by__full_name')
    date_hierarchy = 'reported_at'
    raw_id_fields = ('reported_by', 'assigned_to')


# =============================================================================
# LEAVE & FEEDBACK ADMINS
# =============================================================================

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('leave_type', 'status')
    search_fields = ('user__full_name', 'user__email', 'reason')
    date_hierarchy = 'start_date'
    raw_id_fields = ('user', 'approved_by')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'feedback_type', 'subject', 'status', 'is_anonymous', 'created_at')
    list_filter = ('feedback_type', 'status', 'is_anonymous')
    search_fields = ('subject', 'message', 'user__full_name')
    raw_id_fields = ('user', 'replied_by', 'related_course')


# =============================================================================
# EVENTS ADMINS
# =============================================================================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'start_datetime', 'venue', 'status', 'coordinator')
    list_filter = ('event_type', 'status', 'is_online', 'is_department_only')
    search_fields = ('title', 'description', 'venue')
    date_hierarchy = 'start_datetime'
    raw_id_fields = ('coordinator',)


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'attendance_status', 'registration_time', 'certificate_issued')
    list_filter = ('attendance_status', 'certificate_issued')
    search_fields = ('event__title', 'user__full_name')
    raw_id_fields = ('event', 'user')


# =============================================================================
# NOTIFICATION & ANNOUNCEMENT ADMINS
# =============================================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('title', 'message', 'recipient__full_name')
    raw_id_fields = ('recipient', 'sender')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'priority', 'posted_by', 'is_pinned', 'is_active', 'created_at')
    list_filter = ('audience', 'priority', 'is_pinned', 'is_active')
    search_fields = ('title', 'content')
    raw_id_fields = ('posted_by',)

