"""
Anna University CSE Department ERP System
URL Configuration
"""

from django.urls import path
from . import hod_views, staff_views, student_views, views

urlpatterns = [
    # ==========================================================================
    # AUTHENTICATION & COMMON
    # ==========================================================================
    path("", views.login_page, name='login_page'),
    path("doLogin/", views.doLogin, name='user_login'),
    path("logout_user/", views.logout_user, name='user_logout'),
    path("firebase-messaging-sw.js", views.showFirebaseJS, name='showFirebaseJS'),
    path("announcements/", views.announcements, name="announcements"),
    
    # API endpoints
    path("get_attendance", views.get_attendance, name='get_attendance'),
    path("check_email_availability", hod_views.check_email_availability, name="check_email_availability"),
    
    # ==========================================================================
    # HOD / ADMIN ROUTES
    # ==========================================================================
    path("admin/home/", hod_views.admin_home, name='admin_home'),
    path("admin/profile/", hod_views.admin_view_profile, name='admin_view_profile'),
    
    # Faculty Management
    path("faculty/add/", hod_views.add_faculty, name='add_faculty'),
    path("faculty/manage/", hod_views.manage_faculty, name='manage_faculty'),
    path("faculty/edit/<int:faculty_id>/", hod_views.edit_faculty, name='edit_faculty'),
    path("faculty/delete/<int:faculty_id>/", hod_views.delete_faculty, name='delete_faculty'),
    
    # Backward compatible staff URLs
    path("staff/add", hod_views.add_staff, name='add_staff'),
    path("staff/manage/", hod_views.manage_staff, name='manage_staff'),
    path("staff/edit/<int:staff_id>/", hod_views.edit_staff, name='edit_staff'),
    path("staff/delete/<int:staff_id>/", hod_views.delete_staff, name='delete_staff'),
    
    # Student Management
    path("student/add/", hod_views.add_student, name='add_student'),
    path("student/manage/", hod_views.manage_student, name='manage_student'),
    path("student/edit/<int:student_id>/", hod_views.edit_student, name='edit_student'),
    path("student/delete/<int:student_id>/", hod_views.delete_student, name='delete_student'),
    
    # Course Management
    path("course/add/", hod_views.add_course, name='add_course'),
    path("course/manage/", hod_views.manage_course, name='manage_course'),
    path("course/edit/<str:course_code>/", hod_views.edit_course, name='edit_course'),
    path("course/delete/<str:course_code>/", hod_views.delete_course, name='delete_course'),
    
    # Course Assignment Management
    path("course-assignment/add/", hod_views.add_course_assignment, name='add_course_assignment'),
    path("course-assignment/manage/", hod_views.manage_course_assignment, name='manage_course_assignment'),
    path("course-assignment/delete/<int:assignment_id>/", hod_views.delete_course_assignment, name='delete_course_assignment'),
    
    # Backward compatible course allocation URLs
    path("course-allocation/add/", hod_views.add_course_allocation, name='add_course_allocation'),
    path("course-allocation/manage/", hod_views.manage_course_allocation, name='manage_course_allocation'),
    path("course-allocation/delete/<int:allocation_id>/", hod_views.delete_course_allocation, name='delete_course_allocation'),
    
    # Academic Year & Regulation Management
    path("academic-year/add/", hod_views.add_academic_year, name='add_academic_year'),
    path("academic-year/manage/", hod_views.manage_academic_year, name='manage_academic_year'),
    path("academic-year/edit/<int:year_id>/", hod_views.edit_academic_year, name='edit_academic_year'),
    path("academic-year/delete/<int:year_id>/", hod_views.delete_academic_year, name='delete_academic_year'),
    path("add_session/", hod_views.add_session, name='add_session'),
    path("session/manage/", hod_views.manage_session, name='manage_session'),
    
    # Semester Management
    path("semester/add/", hod_views.add_semester, name='add_semester'),
    path("semester/manage/", hod_views.manage_semester, name='manage_semester'),
    path("semester/delete/<int:semester_id>/", hod_views.delete_semester, name='delete_semester'),
    
    path("regulation/add/", hod_views.add_regulation, name='add_regulation'),
    path("regulation/manage/", hod_views.manage_regulation, name='manage_regulation'),
    
    # Leave Management (HOD)
    path("leave/view/", hod_views.view_leave_requests, name='view_leave_requests'),
    path("student/view/leave/", hod_views.view_student_leave, name="view_student_leave"),
    path("staff/view/leave/", hod_views.view_staff_leave, name="view_staff_leave"),
    
    # Feedback Management (HOD)
    path("feedback/view/", hod_views.view_feedbacks, name='view_feedbacks'),
    path("student/view/feedback/", hod_views.student_feedback_message, name="student_feedback_message"),
    path("staff/view/feedback/", hod_views.staff_feedback_message, name="staff_feedback_message"),
    
    # Publication Verification
    path("publications/verify/", hod_views.verify_publications, name='verify_publications'),
    path("publications/approve/<int:publication_id>/", hod_views.approve_publication, name='approve_publication'),
    
    # Lab Issues
    path("lab-issues/", hod_views.view_lab_issues, name='view_lab_issues'),
    
    # Event Management (HOD)
    path("event/add/", hod_views.add_event, name='add_event'),
    path("event/manage/", hod_views.manage_event, name='manage_event'),
    path("event/edit/<int:event_id>/", hod_views.edit_event, name='edit_event'),
    path("event/delete/<int:event_id>/", hod_views.delete_event, name='delete_event'),
    
    # Announcement Management
    path("announcement/add/", hod_views.add_announcement, name='add_announcement'),
    path("announcement/manage/", hod_views.manage_announcement, name='manage_announcement'),
    path("announcement/delete/<int:announcement_id>/", hod_views.delete_announcement, name='delete_announcement'),
    
    # Notifications (HOD)
    path("admin_notify_student", hod_views.admin_notify_student, name='admin_notify_student'),
    path("admin_notify_staff", hod_views.admin_notify_staff, name='admin_notify_staff'),
    path("notify/", hod_views.send_notification_page, name='send_notification_page'),
    path("send_student_notification/", hod_views.send_student_notification, name='send_student_notification'),
    path("send_staff_notification/", hod_views.send_staff_notification, name='send_staff_notification'),
    path("send_notification/", hod_views.send_notification, name='send_notification'),
    
    # Attendance View (HOD)
    path("attendance/view/", hod_views.admin_view_attendance, name="admin_view_attendance"),
    path("attendance/fetch/", hod_views.get_admin_attendance, name='get_admin_attendance'),
    
    # Question Paper Management (HOD)
    path("question-paper/assign/", hod_views.assign_question_paper, name='assign_question_paper'),
    path("question-paper/manage/", hod_views.manage_qp_assignments, name='manage_qp_assignments'),
    path("question-paper/review/<int:qp_id>/", hod_views.review_question_paper, name='review_question_paper'),
    path("question-paper/delete/<int:qp_id>/", hod_views.delete_qp_assignment, name='delete_qp_assignment'),
    path("question-paper/get-faculty/", hod_views.get_faculty_for_course, name='get_faculty_for_course'),
    
    # ==========================================================================
    # FACULTY / STAFF ROUTES
    # ==========================================================================
    path("staff/home/", staff_views.staff_home, name='staff_home'),
    path("staff/profile/", staff_views.staff_view_profile, name='staff_view_profile'),
    
    # Attendance Management
    path("staff/attendance/take/", staff_views.staff_take_attendance, name='staff_take_attendance'),
    path("staff/attendance/update/", staff_views.staff_update_attendance, name='staff_update_attendance'),
    path("staff/get_students/", staff_views.get_students, name='get_students'),
    path("staff/attendance/fetch/", staff_views.get_student_attendance, name='get_student_attendance'),
    path("staff/attendance/save/", staff_views.save_attendance, name='save_attendance'),
    path("staff/attendance/update/", staff_views.update_attendance, name='update_attendance'),
    path("staff/attendance/report/", staff_views.staff_view_attendance_report, name='staff_view_attendance_report'),
    
    # Leave & Feedback
    path("staff/apply/leave/", staff_views.staff_apply_leave, name='staff_apply_leave'),
    path("staff/feedback/", staff_views.staff_feedback, name='staff_feedback'),
    
    # Publications
    path("staff/publication/add/", staff_views.staff_add_publication, name='staff_add_publication'),
    path("staff/publication/view/", staff_views.staff_view_publications, name='staff_view_publications'),
    
    # View Students
    path("staff/students/", staff_views.staff_view_students, name='staff_view_students'),
    
    # Notifications
    path("staff/fcmtoken/", staff_views.staff_fcmtoken, name='staff_fcmtoken'),
    path("staff/view/notification/", staff_views.staff_view_notification, name="staff_view_notification"),
    
    # Question Paper (Staff)
    path("staff/question-paper/", staff_views.staff_view_qp_assignments, name='staff_view_qp_assignments'),
    path("staff/question-paper/submit/<int:qp_id>/", staff_views.staff_submit_question_paper, name='staff_submit_question_paper'),
    path("staff/question-paper/details/<int:qp_id>/", staff_views.staff_view_qp_details, name='staff_view_qp_details'),
    
    # ==========================================================================
    # STUDENT ROUTES
    # ==========================================================================
    path("student/home/", student_views.student_home, name='student_home'),
    path("student/profile/", student_views.student_view_profile, name='student_view_profile'),
    
    # Attendance
    path("student/view/attendance/", student_views.student_view_attendance, name='student_view_attendance'),
    
    # Leave & Feedback
    path("student/apply/leave/", student_views.student_apply_leave, name='student_apply_leave'),
    path("student/feedback/", student_views.student_feedback, name='student_feedback'),
    
    # Achievements
    path("student/achievement/add/", student_views.student_add_achievement, name='student_add_achievement'),
    path("student/achievement/view/", student_views.student_view_achievements, name='student_view_achievements'),
    
    # Courses
    path("student/courses/", student_views.student_view_courses, name='student_view_courses'),
    
    # Events
    path("student/events/", student_views.view_events, name='view_events'),
    path("student/events/register/<int:event_id>/", student_views.register_event, name='register_event'),
    path("student/events/unregister/<int:event_id>/", student_views.unregister_event, name='unregister_event'),
    path("student/events/my-registrations/", student_views.my_event_registrations, name='my_event_registrations'),
    
    # Notifications
    path("student/fcmtoken/", student_views.student_fcmtoken, name='student_fcmtoken'),
    path("student/view/notification/", student_views.student_view_notification, name="student_view_notification"),
]
