"""
Anna University CSE Department ERP System
Faculty (Staff) Views
"""

import json
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count

from .forms import (
    LeaveRequestForm, FeedbackForm, PublicationForm, 
    FacultyProfileEditForm, AccountUserForm, BulkAttendanceForm,
    QuestionPaperSubmissionForm
)
from .models import (
    Account_User, Faculty_Profile, Student_Profile, Course_Assignment,
    Attendance, LeaveRequest, Feedback, Notification, Publication,
    Announcement, AcademicYear, Semester, QuestionPaperAssignment
)
from .utils.web_scrapper import fetch_acoe_updates
from .utils.cir_scrapper import fetch_cir_ticker_announcements


def check_faculty_permission(user):
    """Check if user is Faculty or Guest Faculty"""
    return user.is_authenticated and user.role in ['FACULTY', 'GUEST']


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def staff_home(request):
    """Faculty Dashboard"""
    if not check_faculty_permission(request.user):
        messages.error(request, "Access Denied. Faculty privileges required.")
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    
    # Get assigned courses
    assignments = Course_Assignment.objects.filter(faculty=faculty, is_active=True)
    total_courses = assignments.count()
    
    # Count students across all assigned batches
    total_students = 0
    for assignment in assignments:
        student_count = Student_Profile.objects.filter(batch_label=assignment.batch_label).count()
        total_students += student_count
    
    # Leave and attendance stats
    total_leaves = LeaveRequest.objects.filter(user=request.user).count()
    pending_leaves = LeaveRequest.objects.filter(user=request.user, status='PENDING').count()
    
    # Attendance stats per course
    course_list = []
    attendance_count_list = []
    for assignment in assignments:
        attendance_count = Attendance.objects.filter(assignment=assignment).count()
        course_list.append(assignment.course.title[:15])
        attendance_count_list.append(attendance_count)
    
    # Publications
    publications = Publication.objects.filter(faculty=faculty)
    total_publications = publications.count()
    unverified_publications = publications.filter(is_verified=False).count()
    
    # Notifications
    notifications = Notification.objects.filter(recipient=request.user, is_read=False)[:5]
    
    # Fetch announcements
    announcements = []
    try:
        acoe_updates = fetch_acoe_updates()
        announcements.extend(acoe_updates)
    except:
        pass
    
    try:
        cir_announcements = fetch_cir_ticker_announcements(limit=5)
        announcements.extend(cir_announcements)
    except:
        pass
    
    # Department announcements
    dept_announcements = Announcement.objects.filter(
        is_active=True, 
        audience__in=['ALL', 'FACULTY']
    )[:5]
    
    context = {
        'page_title': f'Faculty Dashboard - {faculty.user.full_name}',
        'faculty': faculty,
        'total_courses': total_courses,
        'total_students': total_students,
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'course_list': json.dumps(course_list),
        'attendance_count_list': json.dumps(attendance_count_list),
        'total_publications': total_publications,
        'unverified_publications': unverified_publications,
        'notifications': notifications,
        'announcements': announcements,
        'dept_announcements': dept_announcements,
        'assignments': assignments,
    }
    return render(request, 'staff_template/home_content.html', context)


# =============================================================================
# ATTENDANCE MANAGEMENT
# =============================================================================

@login_required
def staff_take_attendance(request):
    """Take attendance for assigned courses"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    assignments = Course_Assignment.objects.filter(faculty=faculty, is_active=True)
    
    context = {
        'assignments': assignments,
        'page_title': 'Take Attendance'
    }
    return render(request, 'staff_template/staff_take_attendance.html', context)


@csrf_exempt
@login_required
def get_students(request):
    """Get students for a course assignment"""
    if not check_faculty_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    assignment_id = request.POST.get('assignment')
    try:
        assignment = get_object_or_404(Course_Assignment, id=assignment_id)
        
        # Get students matching the batch label
        students = Student_Profile.objects.filter(batch_label=assignment.batch_label).select_related('user')
        
        student_data = []
        for student in students:
            data = {
                "id": str(student.id),
                "name": student.user.full_name,
                "register_no": student.register_no
            }
            student_data.append(data)
        
        return JsonResponse(json.dumps(student_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@login_required
def save_attendance(request):
    """Save attendance records"""
    if not check_faculty_permission(request.user):
        return HttpResponse("Permission denied", status=403)
    
    student_data = request.POST.get('student_ids')
    attendance_date = request.POST.get('date')
    assignment_id = request.POST.get('assignment')
    period = request.POST.get('period', 1)
    
    students = json.loads(student_data)
    
    try:
        assignment = get_object_or_404(Course_Assignment, id=assignment_id)
        
        for student_dict in students:
            student = get_object_or_404(Student_Profile, id=student_dict.get('id'))
            
            # Check if attendance already exists
            attendance, created = Attendance.objects.update_or_create(
                student=student,
                assignment=assignment,
                date=attendance_date,
                period=period,
                defaults={
                    'status': 'PRESENT' if student_dict.get('status') else 'ABSENT'
                }
            )
        
        return HttpResponse("OK")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=400)


@login_required
def staff_update_attendance(request):
    """Update attendance records"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    assignments = Course_Assignment.objects.filter(faculty=faculty, is_active=True)
    
    context = {
        'assignments': assignments,
        'page_title': 'Update Attendance'
    }
    return render(request, 'staff_template/staff_update_attendance.html', context)


@csrf_exempt
@login_required
def get_student_attendance(request):
    """Get attendance data for editing"""
    if not check_faculty_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    assignment_id = request.POST.get('assignment')
    attendance_date_id = request.POST.get('attendance_date_id')
    period = request.POST.get('period', 1)
    
    try:
        assignment = get_object_or_404(Course_Assignment, id=assignment_id)
        
        # Get the date from attendance record
        attendance_record = Attendance.objects.filter(id=attendance_date_id).first()
        if attendance_record:
            attendance_date = attendance_record.date
        else:
            return JsonResponse(json.dumps([]), content_type='application/json', safe=False)
        
        # Get students for this batch
        students = Student_Profile.objects.filter(batch_label=assignment.batch_label).select_related('user')
        
        student_data = []
        for student in students:
            # Check if attendance exists
            try:
                attendance = Attendance.objects.get(
                    student=student, 
                    assignment=assignment,
                    date=attendance_date,
                    period=period
                )
                status = attendance.status == 'PRESENT'
            except Attendance.DoesNotExist:
                status = False
            
            data = {
                "id": str(student.id),
                "name": student.user.full_name,
                "register_no": student.register_no,
                "status": status
            }
            student_data.append(data)
        
        return JsonResponse(json.dumps(student_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@login_required
def update_attendance(request):
    """Update existing attendance records"""
    if not check_faculty_permission(request.user):
        return HttpResponse("Permission denied", status=403)
    
    student_data = request.POST.get('student_ids')
    attendance_date_id = request.POST.get('date')
    assignment_id = request.POST.get('assignment')
    period = request.POST.get('period', 1)
    
    students = json.loads(student_data)
    
    try:
        assignment = get_object_or_404(Course_Assignment, id=assignment_id)
        
        # Get the date from attendance record
        attendance_record = Attendance.objects.filter(id=attendance_date_id).first()
        if attendance_record:
            attendance_date = attendance_record.date
        else:
            return HttpResponse("Invalid attendance record", status=400)
        
        for student_dict in students:
            student = get_object_or_404(Student_Profile, id=student_dict.get('id'))
            
            Attendance.objects.update_or_create(
                student=student,
                assignment=assignment,
                date=attendance_date,
                period=period,
                defaults={
                    'status': 'PRESENT' if student_dict.get('status') else 'ABSENT'
                }
            )
        
        return HttpResponse("OK")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=400)


# =============================================================================
# LEAVE MANAGEMENT
# =============================================================================

@login_required
def staff_apply_leave(request):
    """Apply for leave"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    form = LeaveRequestForm(request.POST or None, request.FILES or None)
    leave_history = LeaveRequest.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'form': form,
        'leave_history': leave_history,
        'page_title': 'Apply for Leave'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                leave = form.save(commit=False)
                leave.user = request.user
                leave.save()
                messages.success(request, "Leave application submitted for review")
                return redirect(reverse('staff_apply_leave'))
            except Exception as e:
                messages.error(request, f"Could not apply: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form")
    
    return render(request, "staff_template/staff_apply_leave.html", context)


# =============================================================================
# FEEDBACK
# =============================================================================

@login_required
def staff_feedback(request):
    """Submit feedback"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    form = FeedbackForm(request.POST or None)
    feedbacks = Feedback.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'form': form,
        'feedbacks': feedbacks,
        'page_title': 'Submit Feedback'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                feedback = form.save(commit=False)
                feedback.user = request.user
                feedback.save()
                messages.success(request, "Feedback submitted successfully")
                return redirect(reverse('staff_feedback'))
            except Exception as e:
                messages.error(request, f"Could not submit: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form")
    
    return render(request, "staff_template/staff_feedback.html", context)


# =============================================================================
# PROFILE
# =============================================================================

@login_required
def staff_view_profile(request):
    """View and update profile"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    user_form = AccountUserForm(request.POST or None, request.FILES or None, instance=request.user)
    profile_form = FacultyProfileEditForm(request.POST or None, instance=faculty)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'page_title': 'View/Update Profile'
    }
    
    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            try:
                user = user_form.save(commit=False)
                password = user_form.cleaned_data.get('password')
                if password:
                    user.set_password(password)
                
                if 'profile_pic' in request.FILES:
                    fs = FileSystemStorage()
                    filename = fs.save(request.FILES['profile_pic'].name, request.FILES['profile_pic'])
                    user.profile_pic = fs.url(filename)
                
                user.save()
                profile_form.save()
                messages.success(request, "Profile Updated!")
                return redirect(reverse('staff_view_profile'))
            except Exception as e:
                messages.error(request, f"Error updating profile: {str(e)}")
        else:
            messages.error(request, "Invalid data provided")
    
    return render(request, "staff_template/staff_view_profile.html", context)


# =============================================================================
# NOTIFICATIONS
# =============================================================================

@csrf_exempt
@login_required
def staff_fcmtoken(request):
    """Update FCM token for push notifications"""
    token = request.POST.get('token')
    try:
        user = get_object_or_404(Account_User, id=request.user.id)
        user.fcm_token = token
        user.save()
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")


@login_required
def staff_view_notification(request):
    """View notifications"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Mark as read
    notifications.filter(is_read=False).update(is_read=True)
    
    context = {
        'notifications': notifications,
        'page_title': "View Notifications"
    }
    return render(request, "staff_template/staff_view_notification.html", context)


# =============================================================================
# PUBLICATIONS
# =============================================================================

@login_required
def staff_add_publication(request):
    """Add new publication"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    form = PublicationForm(request.POST or None, request.FILES or None)
    publications = Publication.objects.filter(faculty=faculty).order_by('-created_at')
    
    context = {
        'form': form,
        'publications': publications,
        'page_title': 'Add Publication'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                publication = form.save(commit=False)
                publication.faculty = faculty
                publication.save()
                messages.success(request, "Publication added successfully. Pending verification.")
                return redirect(reverse('staff_add_publication'))
            except Exception as e:
                messages.error(request, f"Could not add: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, "staff_template/staff_add_publication.html", context)


@login_required
def staff_view_publications(request):
    """View all publications"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    publications = Publication.objects.filter(faculty=faculty).order_by('-created_at')
    
    context = {
        'publications': publications,
        'page_title': 'My Publications'
    }
    return render(request, "staff_template/staff_view_publications.html", context)


# =============================================================================
# VIEW STUDENTS
# =============================================================================

@login_required
def staff_view_students(request):
    """View students in assigned courses"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    assignments = Course_Assignment.objects.filter(faculty=faculty, is_active=True)
    
    # Get unique batch labels
    batch_labels = assignments.values_list('batch_label', flat=True).distinct()
    
    # Get students in those batches
    students = Student_Profile.objects.filter(batch_label__in=batch_labels).select_related('user', 'advisor')
    
    context = {
        'students': students,
        'assignments': assignments,
        'page_title': 'View Students'
    }
    return render(request, "staff_template/staff_view_students.html", context)


# =============================================================================
# ATTENDANCE REPORTS
# =============================================================================

@login_required
def staff_view_attendance_report(request):
    """View attendance reports for assigned courses"""
    if not check_faculty_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    assignments = Course_Assignment.objects.filter(faculty=faculty, is_active=True)
    
    selected_assignment = None
    attendance_data = []
    
    if request.GET.get('assignment'):
        selected_assignment = get_object_or_404(Course_Assignment, id=request.GET.get('assignment'))
        
        # Get students and their attendance
        students = Student_Profile.objects.filter(batch_label=selected_assignment.batch_label)
        
        for student in students:
            total = Attendance.objects.filter(student=student, assignment=selected_assignment).count()
            present = Attendance.objects.filter(
                student=student, 
                assignment=selected_assignment,
                status='PRESENT'
            ).count()
            
            percentage = (present / total * 100) if total > 0 else 0
            
            attendance_data.append({
                'student': student,
                'total': total,
                'present': present,
                'absent': total - present,
                'percentage': round(percentage, 2)
            })
    
    context = {
        'assignments': assignments,
        'selected_assignment': selected_assignment,
        'attendance_data': attendance_data,
        'page_title': 'Attendance Report'
    }
    return render(request, "staff_template/staff_attendance_report.html", context)


# =============================================================================
# QUESTION PAPER MANAGEMENT
# =============================================================================

@login_required
def staff_view_qp_assignments(request):
    """View question paper assignments for the faculty"""
    if not check_faculty_permission(request.user):
        messages.error(request, "Access Denied. Faculty privileges required.")
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    
    # Get all QP assignments for this faculty
    assignments = QuestionPaperAssignment.objects.filter(
        assigned_faculty=faculty
    ).select_related(
        'course', 'academic_year', 'semester', 'regulation'
    ).order_by('-created_at')
    
    # Statistics
    stats = {
        'total': assignments.count(),
        'pending': assignments.filter(status__in=['ASSIGNED', 'IN_PROGRESS']).count(),
        'submitted': assignments.filter(status='SUBMITTED').count(),
        'approved': assignments.filter(status='APPROVED').count(),
        'rejected': assignments.filter(status='REJECTED').count(),
    }
    
    context = {
        'assignments': assignments,
        'stats': stats,
        'page_title': 'My Question Paper Assignments'
    }
    return render(request, "staff_template/staff_qp_assignments.html", context)


@login_required
def staff_submit_question_paper(request, qp_id):
    """Submit question paper for a specific assignment"""
    if not check_faculty_permission(request.user):
        messages.error(request, "Access Denied. Faculty privileges required.")
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    qp_assignment = get_object_or_404(QuestionPaperAssignment, id=qp_id, assigned_faculty=faculty)
    
    # Check if already approved
    if qp_assignment.status == 'APPROVED':
        messages.info(request, "This question paper has already been approved.")
        return redirect('staff_view_qp_assignments')
    
    form = QuestionPaperSubmissionForm(request.POST or None, request.FILES or None, instance=qp_assignment)
    
    context = {
        'form': form,
        'qp_assignment': qp_assignment,
        'page_title': f'Submit QP - {qp_assignment.course.course_code}'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                qp = form.save(commit=False)
                qp.status = 'SUBMITTED'
                qp.submitted_at = datetime.now()
                qp.save()
                
                # Create notification for HOD
                hod_users = Account_User.objects.filter(role='HOD', is_active=True)
                for hod in hod_users:
                    Notification.objects.create(
                        recipient=hod,
                        title='Question Paper Submitted',
                        message=f'{faculty.user.full_name} has submitted the {qp.get_exam_type_display()} question paper for {qp.course.course_code} - {qp.course.title}',
                        notification_type='INFO',
                        link=reverse('review_question_paper', args=[qp.id])
                    )
                
                messages.success(request, "Question paper submitted successfully! Waiting for review.")
                return redirect('staff_view_qp_assignments')
            except Exception as e:
                messages.error(request, f"Error submitting: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form")
    
    return render(request, "staff_template/staff_submit_qp.html", context)


@login_required
def staff_view_qp_details(request, qp_id):
    """View details of a specific question paper assignment"""
    if not check_faculty_permission(request.user):
        messages.error(request, "Access Denied. Faculty privileges required.")
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, user=request.user)
    qp_assignment = get_object_or_404(QuestionPaperAssignment, id=qp_id, assigned_faculty=faculty)
    
    context = {
        'qp_assignment': qp_assignment,
        'page_title': f'QP Details - {qp_assignment.course.course_code}'
    }
    return render(request, "staff_template/staff_qp_details.html", context)