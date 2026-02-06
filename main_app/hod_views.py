"""
Anna University CSE Department ERP System
HOD (Head of Department) Views
"""

import json
import csv
import io
import requests
import uuid
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import (HttpResponseRedirect, get_object_or_404, redirect, render)
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db import transaction
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from .forms import (
    FacultyRegistrationForm, StudentRegistrationForm, NonTeachingStaffRegistrationForm,
    CourseForm, CourseAssignmentForm, RegulationForm, AcademicYearForm, SemesterForm,
    EventForm, LeaveApprovalForm, FeedbackReplyForm, AnnouncementForm,
    FacultyProfileEditForm, StudentProfileEditForm, AccountUserForm,
    QuestionPaperAssignmentForm, QuestionPaperReviewForm,
    TimetableForm, TimetableEntryForm, TimeSlotForm, ProgramForm
)
from .models import (
    Account_User, Faculty_Profile, Student_Profile, NonTeachingStaff_Profile,
    Course, Course_Assignment, Attendance, Regulation, CourseCategory, AcademicYear, Semester,
    Publication, Student_Achievement, Lab_Issue_Log, LeaveRequest, Feedback,
    Event, EventRegistration, Notification, Announcement, QuestionPaperAssignment,
    Timetable, TimetableEntry, TimeSlot, Program, RegulationCoursePlan, SemesterPromotion,
    ProgramBatch, ElectiveVertical, ElectiveCourseOffering
)
from .utils.web_scrapper import fetch_acoe_updates
from .utils.cir_scrapper import fetch_cir_ticker_announcements

def check_hod_permission(user):
    """
    Check if user has HOD privileges.
    HOD is identified via Faculty_Profile.designation == 'HOD',
    not by Account_User.role field.
    """
    if not user.is_authenticated:
        return False
    return user.is_hod


# =============================================================================
# HOD VIEW MODE TOGGLE
# =============================================================================

@login_required
def toggle_hod_view_mode(request):
    """Toggle HOD between Admin and Faculty view modes"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    # Toggle the view mode
    current_mode = request.session.get('hod_view_mode', 'admin')
    new_mode = 'faculty' if current_mode == 'admin' else 'admin'
    request.session['hod_view_mode'] = new_mode
    
    # Redirect to appropriate dashboard
    if new_mode == 'faculty':
        messages.success(request, "Switched to Faculty View")
        return redirect('staff_home')
    else:
        messages.success(request, "Switched to Admin View")
        return redirect('admin_home')


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def admin_home(request):
    """HOD Dashboard with statistics and overview"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    # Statistics
    total_faculty = Faculty_Profile.objects.filter(is_external=False).count()
    total_guest_faculty = Faculty_Profile.objects.filter(is_external=True).count()
    total_students = Student_Profile.objects.count()
    total_staff = NonTeachingStaff_Profile.objects.count()
    total_courses = Course.objects.count()
    total_course = total_courses  # Alias for template
    total_assignments = Course_Assignment.objects.count()
    
    # Students by branch
    students_by_branch = Student_Profile.objects.values('branch').annotate(count=Count('branch'))
    branch_labels = [item['branch'] for item in students_by_branch]
    branch_counts = [item['count'] for item in students_by_branch]
    
    # Students by batch
    students_by_batch = Student_Profile.objects.values('batch_label').annotate(count=Count('batch_label'))
    batch_labels = [item['batch_label'] for item in students_by_batch]
    batch_counts = [item['count'] for item in students_by_batch]
    
    # Course list for charts
    courses = Course.objects.all()
    course_list = [c.title for c in courses]
    course_name_list = course_list  # Alias for template
    
    # Students per course (via course assignments)
    student_count_list_in_course = []
    assignment_count_list = []
    attendance_list = []
    for course in courses:
        # Count assignments for this course
        assignments = Course_Assignment.objects.filter(course=course)
        assignment_count_list.append(assignments.count())
        # Attendance per course
        att_count = Attendance.objects.filter(assignment__course=course).count()
        attendance_list.append(att_count)
        # Student count is just a placeholder - we'd need to filter by batch
        student_count_list_in_course.append(Student_Profile.objects.count())
    
    # Student attendance and leave stats
    students = Student_Profile.objects.all()[:20]  # Limit for chart
    student_name_list = [s.user.full_name for s in students]
    student_attendance_present_list = []
    student_attendance_leave_list = []
    for student in students:
        present = Attendance.objects.filter(student=student, status='PRESENT').count()
        absent = Attendance.objects.filter(student=student, status='ABSENT').count()
        student_attendance_present_list.append(present)
        student_attendance_leave_list.append(absent)
    
    # Pending items
    pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
    pending_feedbacks = Feedback.objects.filter(status='PENDING').count()
    pending_lab_issues = Lab_Issue_Log.objects.filter(status='PENDING').count()
    unverified_publications = Publication.objects.filter(is_verified=False).count()
    
    # Recent activities
    recent_leaves = LeaveRequest.objects.order_by('-created_at')[:5]
    recent_feedbacks = Feedback.objects.order_by('-created_at')[:5]
    
    # Fetch external announcements
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
    dept_announcements = Announcement.objects.filter(is_active=True)[:5]
    
    # Current academic context (auto-detected from dates)
    current_year = AcademicYear.get_current()
    current_semester = Semester.get_current()

    context = {
        'page_title': "HOD Dashboard - CSE Department",
        'total_faculty': total_faculty,
        'total_guest_faculty': total_guest_faculty,
        'total_students': total_students,
        'total_staff': total_staff,
        'total_courses': total_courses,
        'total_course': total_course,
        'total_assignments': total_assignments,
        'branch_labels': json.dumps(branch_labels),
        'branch_counts': json.dumps(branch_counts),
        'batch_labels': json.dumps(batch_labels),
        'batch_counts': json.dumps(batch_counts),
        'pending_leaves': pending_leaves,
        'pending_feedbacks': pending_feedbacks,
        'pending_lab_issues': pending_lab_issues,
        'unverified_publications': unverified_publications,
        'recent_leaves': recent_leaves,
        'recent_feedbacks': recent_feedbacks,
        'announcements': announcements,
        'dept_announcements': dept_announcements,
        'current_year': current_year,
        'current_semester': current_semester,
        # Chart data
        'course_list': json.dumps(course_list),
        'course_name_list': json.dumps(course_name_list),
        'student_count_list_in_course': json.dumps(student_count_list_in_course),
        'assignment_count_list': json.dumps(assignment_count_list),
        'attendance_list': json.dumps(attendance_list),
        'student_name_list': json.dumps(student_name_list),
        'student_attendance_present_list': json.dumps(student_attendance_present_list),
        'student_attendance_leave_list': json.dumps(student_attendance_leave_list),
    }
    return render(request, 'hod_template/home_content.html', context)


# =============================================================================
# FACULTY MANAGEMENT
# =============================================================================

@login_required
def add_faculty(request):
    """Add new faculty member"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = FacultyRegistrationForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Faculty'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                # Create user
                user = Account_User.objects.create_user(
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    full_name=form.cleaned_data['full_name'],
                    role='GUEST' if form.cleaned_data.get('is_external') else 'FACULTY',
                    gender=form.cleaned_data.get('gender'),
                    phone=form.cleaned_data.get('phone'),
                    address=form.cleaned_data.get('address'),
                )
                
                # Handle profile pic
                if 'profile_pic' in request.FILES:
                    fs = FileSystemStorage()
                    filename = fs.save(request.FILES['profile_pic'].name, request.FILES['profile_pic'])
                    user.profile_pic = fs.url(filename)
                    user.save()
                
                # Update faculty profile
                faculty = user.faculty_profile
                faculty.staff_id = form.cleaned_data['staff_id']
                faculty.designation = form.cleaned_data['designation']
                faculty.is_external = form.cleaned_data.get('is_external', False)
                faculty.specialization = form.cleaned_data.get('specialization')
                faculty.qualification = form.cleaned_data.get('qualification')
                faculty.experience_years = form.cleaned_data.get('experience_years', 0)
                faculty.date_of_joining = form.cleaned_data.get('date_of_joining')
                faculty.contract_expiry = form.cleaned_data.get('contract_expiry')
                faculty.cabin_number = form.cleaned_data.get('cabin_number')
                faculty.save()
                
                messages.success(request, "Faculty added successfully!")
                return redirect(reverse('add_faculty'))
            except Exception as e:
                messages.error(request, f"Could not add faculty: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_staff_template.html', context)


@login_required
def manage_faculty(request):
    """List all faculty members"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    faculty_list = Faculty_Profile.objects.select_related('user').all()
    context = {
        'faculty_list': faculty_list,
        'page_title': 'Manage Faculty'
    }
    return render(request, "hod_template/manage_staff.html", context)


@login_required
def edit_faculty(request, faculty_id):
    """Edit faculty details"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, id=faculty_id)
    user_form = AccountUserForm(request.POST or None, request.FILES or None, instance=faculty.user)
    profile_form = FacultyProfileEditForm(request.POST or None, instance=faculty)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'faculty': faculty,
        'page_title': 'Edit Faculty'
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
                
                messages.success(request, "Faculty updated successfully!")
                return redirect(reverse('manage_faculty'))
            except Exception as e:
                messages.error(request, f"Could not update: {str(e)}")
        else:
            messages.error(request, "Please fill the form correctly")
    
    return render(request, "hod_template/edit_staff_template.html", context)


@login_required
def delete_faculty(request, faculty_id):
    """Delete faculty"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    faculty = get_object_or_404(Faculty_Profile, id=faculty_id)
    try:
        faculty.user.delete()  # This will cascade delete the profile
        messages.success(request, "Faculty deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_faculty'))


# =============================================================================
# STUDENT MANAGEMENT
# =============================================================================

@login_required
def add_student(request):
    """Add new student - password is set by student via OTP first-time login
    Fields match bulk upload for consistency.
    """
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = StudentRegistrationForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Student'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                # Create user without password (student will set via OTP)
                user = Account_User.objects.create(
                    email=form.cleaned_data['email'],
                    full_name=form.cleaned_data['full_name'],
                    role='STUDENT',
                    gender=form.cleaned_data['gender'],
                    phone=form.cleaned_data.get('phone') or None,
                    is_active=True
                )
                # Mark password as unusable until student sets it
                user.set_unusable_password()
                user.save()
                
                # Update student profile (auto-created by signal)
                student = user.student_profile
                student.register_no = form.cleaned_data['register_no']
                student.batch_label = form.cleaned_data['batch_label']
                student.branch = form.cleaned_data['branch']
                student.program_type = form.cleaned_data['program_type']
                student.admission_year = form.cleaned_data['admission_year']
                student.current_sem = form.cleaned_data.get('current_sem', 1)
                
                # Auto-assign regulation based on admission year
                admission_year = form.cleaned_data['admission_year']
                regulation = Regulation.objects.filter(
                    year__lte=admission_year
                ).order_by('-year').first()
                if regulation:
                    student.regulation = regulation
                
                student.save()
                
                # Send first-time login notification to college email
                try:
                    student_data = {
                        'name': user.full_name,
                        'register_no': student.register_no,
                        'email': user.email,
                        'college_email': student.college_email,
                    }
                    send_first_login_notification(student_data)
                    messages.success(request, f"Student added successfully! Login instructions sent to {student.college_email}")
                except Exception as e:
                    messages.warning(request, f"Student added but email notification failed: {str(e)}")
                
                return redirect(reverse('add_student'))
            except Exception as e:
                messages.error(request, f"Could not add student: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_student_template.html', context)


@login_required
def manage_student(request):
    """List all students with filters"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    students = Student_Profile.objects.select_related('user', 'advisor', 'regulation').all()
    
    # Apply filters
    branch = request.GET.get('branch')
    batch = request.GET.get('batch')
    semester = request.GET.get('semester')
    
    if branch:
        students = students.filter(branch=branch)
    if batch:
        students = students.filter(batch_label=batch)
    if semester:
        students = students.filter(current_sem=semester)
    
    # Get programs from database for branch filtering
    all_programs = Program.objects.all().order_by('level', 'code')
    
    # Get batch choices from database
    current_year = AcademicYear.get_current()
    if current_year:
        batch_choices = list(ProgramBatch.objects.filter(
            academic_year=current_year,
            is_active=True
        ).values_list('batch_name', 'batch_display').distinct().order_by('batch_name'))
    else:
        batch_choices = []
    
    context = {
        'students': students,
        'page_title': 'Manage Students',
        'all_programs': all_programs,
        'batch_choices': batch_choices,
    }
    return render(request, "hod_template/manage_student.html", context)


@login_required
def edit_student(request, student_id):
    """Edit student details"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    student = get_object_or_404(Student_Profile, id=student_id)
    user_form = AccountUserForm(request.POST or None, request.FILES or None, instance=student.user)
    profile_form = StudentProfileEditForm(request.POST or None, instance=student)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'student': student,
        'page_title': 'Edit Student'
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
                
                messages.success(request, "Student updated successfully!")
                return redirect(reverse('manage_student'))
            except Exception as e:
                messages.error(request, f"Could not update: {str(e)}")
        else:
            messages.error(request, "Please fill the form correctly")
    
    return render(request, "hod_template/edit_student_template.html", context)


@login_required
def delete_student(request, student_id):
    """Delete student"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    student = get_object_or_404(Student_Profile, id=student_id)
    try:
        student.user.delete()
        messages.success(request, "Student deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_student'))


# =============================================================================
# COURSE MANAGEMENT
# =============================================================================

@login_required
def add_course(request):
    """Add new course"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = CourseForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Course'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Course added successfully!")
                return redirect(reverse('add_course'))
            except Exception as e:
                messages.error(request, f"Could not add course: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_course_template.html', context)


@login_required
def manage_course(request):
    """List all courses"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    courses = Course.objects.all()
    
    # Apply filters
    course_type = request.GET.get('course_type')
    search = request.GET.get('search', '').strip()
    
    if course_type:
        courses = courses.filter(course_type=course_type)
    if search:
        courses = courses.filter(
            Q(course_code__icontains=search) | Q(title__icontains=search)
        )
    
    context = {
        'courses': courses,
        'course_type_choices': Course.COURSE_TYPE_CHOICES,
        'page_title': 'Manage Courses'
    }
    return render(request, "hod_template/manage_course.html", context)


@login_required
def edit_course(request, course_code):
    """Edit course"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    course = get_object_or_404(Course, course_code=course_code)
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    
    # Disable course_code field (primary key)
    form.fields['course_code'].widget.attrs['readonly'] = True
    
    context = {
        'form': form,
        'course': course,
        'page_title': 'Edit Course'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Course updated successfully!")
                return redirect(reverse('manage_course'))
            except Exception as e:
                messages.error(request, f"Could not update: {str(e)}")
        else:
            messages.error(request, "Please fill the form correctly")
    
    return render(request, 'hod_template/edit_course_template.html', context)


@login_required
def delete_course(request, course_code):
    """Delete course"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    course = get_object_or_404(Course, course_code=course_code)
    try:
        course.delete()
        messages.success(request, "Course deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_course'))


# =============================================================================
# COURSE ASSIGNMENT MANAGEMENT
# =============================================================================

@login_required
def add_course_assignment(request):
    """Add course assignment (assign faculty to course)"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = CourseAssignmentForm(request.POST or None)
    context = {'form': form, 'page_title': 'Assign Course to Faculty'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Course assignment created successfully!")
                return redirect(reverse('manage_course_assignment'))
            except Exception as e:
                messages.error(request, f"Could not create assignment: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_course_allocation_template.html', context)


@login_required
def manage_course_assignment(request):
    """List all course assignments"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    assignments = Course_Assignment.objects.select_related(
        'course', 'faculty', 'faculty__user', 'academic_year', 'semester'
    ).all()
    
    context = {
        'assignments': assignments,
        'page_title': 'Manage Course Assignments'
    }
    return render(request, 'hod_template/manage_course_allocation.html', context)


@login_required
def delete_course_assignment(request, assignment_id):
    """Delete course assignment"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    assignment = get_object_or_404(Course_Assignment, id=assignment_id)
    try:
        assignment.delete()
        messages.success(request, "Assignment deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_course_assignment'))


# =============================================================================
# ACADEMIC YEAR & SEMESTER MANAGEMENT
# =============================================================================

@login_required
def add_academic_year(request):
    """Add academic year"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = AcademicYearForm(request.POST or None)
    context = {'form': form, 'page_title': 'Add Academic Year'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Academic Year added successfully!")
                return redirect(reverse('manage_academic_year'))
            except Exception as e:
                messages.error(request, f"Could not add: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, "hod_template/add_session_template.html", context)


@login_required
def manage_academic_year(request):
    """Manage academic years with their semesters - unified view"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    academic_years = AcademicYear.objects.prefetch_related('semesters').all()
    semester_form = SemesterForm()
    context = {
        'academic_years': academic_years,
        'semester_form': semester_form,
        'page_title': 'Manage Academic Years'
    }
    return render(request, "hod_template/manage_session.html", context)


@login_required
def edit_academic_year(request, year_id):
    """Edit academic year"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    year = get_object_or_404(AcademicYear, id=year_id)
    form = AcademicYearForm(request.POST or None, instance=year)
    context = {'form': form, 'year': year, 'page_title': 'Edit Academic Year'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Academic year updated successfully!")
                return redirect(reverse('manage_academic_year'))
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Please fix the errors")
    
    return render(request, "hod_template/add_session_template.html", context)


@login_required
def delete_academic_year(request, year_id):
    """Delete academic year"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    year = get_object_or_404(AcademicYear, id=year_id)
    try:
        year.delete()
        messages.success(request, "Academic year deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_academic_year'))


# =============================================================================
# SEMESTER MANAGEMENT
# =============================================================================

@login_required
def add_semester(request, year_id=None):
    """Add multiple semesters at once for an academic year"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    academic_year = None
    
    # If year_id provided, pre-select that academic year
    if year_id:
        academic_year = get_object_or_404(AcademicYear, id=year_id)
    
    # Get existing semesters for this academic year to show which are already added
    existing_semesters = []
    if academic_year:
        existing_semesters = list(Semester.objects.filter(academic_year=academic_year).values_list('semester_number', flat=True))
    
    context = {
        'academic_year': academic_year,
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'existing_semesters': existing_semesters,
        'page_title': f'Add Semesters for {academic_year.year}' if academic_year else 'Add Semesters'
    }
    
    if request.method == 'POST':
        academic_year_id = request.POST.get('academic_year') or (academic_year.id if academic_year else None)
        
        if not academic_year_id:
            messages.error(request, "Please select an academic year")
            return render(request, "hod_template/add_semester.html", context)
        
        academic_year_obj = get_object_or_404(AcademicYear, id=academic_year_id)
        
        # Get all semester data from POST
        semester_numbers = request.POST.getlist('semester_number[]')
        start_dates = request.POST.getlist('start_date[]')
        end_dates = request.POST.getlist('end_date[]')
        
        created_count = 0
        errors = []
        
        for i in range(len(semester_numbers)):
            sem_num = semester_numbers[i]
            start_date = start_dates[i] if i < len(start_dates) else ''
            end_date = end_dates[i] if i < len(end_dates) else ''
            
            if sem_num and start_date and end_date:
                try:
                    # Check if semester already exists
                    if Semester.objects.filter(academic_year=academic_year_obj, semester_number=sem_num).exists():
                        errors.append(f"Semester {sem_num} already exists for {academic_year_obj.year}")
                        continue
                    
                    Semester.objects.create(
                        academic_year=academic_year_obj,
                        semester_number=int(sem_num),
                        start_date=start_date,
                        end_date=end_date
                    )
                    created_count += 1
                except Exception as e:
                    errors.append(f"Error creating Semester {sem_num}: {str(e)}")
        
        if created_count > 0:
            messages.success(request, f"Successfully created {created_count} semester(s)!")
        
        for error in errors:
            messages.warning(request, error)
        
        if created_count > 0:
            return redirect(reverse('manage_academic_year'))
    
    return render(request, "hod_template/add_semester.html", context)


@login_required
def manage_semester(request):
    """Manage semesters"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    semesters = Semester.objects.select_related('academic_year').all()
    context = {'semesters': semesters, 'page_title': 'Manage Semesters'}
    return render(request, "hod_template/manage_semester.html", context)


@login_required
def delete_semester(request, semester_id):
    """Delete semester"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    semester = get_object_or_404(Semester, id=semester_id)
    try:
        semester.delete()
        messages.success(request, "Semester deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_academic_year'))


@login_required
def edit_semester(request, semester_id):
    """Edit an existing semester"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    semester = get_object_or_404(Semester, id=semester_id)
    academic_year = semester.academic_year
    
    if request.method == 'POST':
        semester_number = request.POST.get('semester_number')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        try:
            # Check if another semester with this number exists (excluding current)
            if Semester.objects.filter(
                academic_year=academic_year, 
                semester_number=semester_number
            ).exclude(id=semester_id).exists():
                messages.error(request, f"Semester {semester_number} already exists for {academic_year.year}")
            else:
                semester.semester_number = int(semester_number)
                semester.start_date = start_date
                semester.end_date = end_date
                semester.save()
                messages.success(request, f"Semester {semester_number} updated successfully!")
                return redirect(reverse('manage_academic_year'))
        except Exception as e:
            messages.error(request, f"Error updating semester: {str(e)}")
    
    # Get existing semester numbers for this year (excluding current)
    existing_semesters = list(
        Semester.objects.filter(academic_year=academic_year)
        .exclude(id=semester_id)
        .values_list('semester_number', flat=True)
    )
    
    context = {
        'semester': semester,
        'academic_year': academic_year,
        'existing_semesters': existing_semesters,
        'page_title': f'Edit Semester {semester.semester_number} for {academic_year.year}'
    }
    return render(request, "hod_template/edit_semester.html", context)


@login_required
def add_regulation(request):
    """Add regulation with course categories"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = RegulationForm(request.POST or None)
    course_category_choices = CourseCategory.CATEGORY_CHOICES
    
    # Default: select all categories for new regulation
    all_category_codes = [code for code, label in course_category_choices]
    
    if request.method == 'POST':
        selected_categories = request.POST.getlist('course_categories', [])
    else:
        # Pre-select all categories by default
        selected_categories = all_category_codes
    
    context = {
        'form': form, 
        'page_title': 'Add Regulation',
        'course_category_choices': course_category_choices,
        'selected_categories': selected_categories,
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                regulation = form.save()
                # Save selected predefined course categories
                for cat_code in selected_categories:
                    CourseCategory.objects.create(
                        regulation=regulation,
                        code=cat_code,
                        is_active=True
                    )
                
                # Save custom categories
                custom_codes = request.POST.getlist('custom_cat_codes', [])
                custom_descs = request.POST.getlist('custom_cat_descs', [])
                for code, desc in zip(custom_codes, custom_descs):
                    if code and desc:
                        CourseCategory.objects.create(
                            regulation=regulation,
                            code=code.upper(),
                            description=desc,
                            is_active=True
                        )
                
                messages.success(request, "Regulation added successfully!")
                return redirect(reverse('manage_regulation'))
            except Exception as e:
                messages.error(request, f"Could not add: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, "hod_template/add_regulation.html", context)


@login_required
def manage_regulation(request):
    """Manage regulations"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    regulations = Regulation.objects.prefetch_related('course_categories').all()
    context = {'regulations': regulations, 'page_title': 'Manage Regulations'}
    return render(request, "hod_template/manage_regulation.html", context)


@login_required
def edit_regulation(request, regulation_id):
    """Edit regulation with course categories"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    form = RegulationForm(request.POST or None, instance=regulation)
    course_category_choices = CourseCategory.CATEGORY_CHOICES
    predefined_codes = [code for code, label in course_category_choices]
    
    # Get currently selected predefined categories
    existing_predefined = list(regulation.course_categories.filter(code__in=predefined_codes).values_list('code', flat=True))
    # Get existing custom categories (not in predefined list)
    existing_custom_categories = regulation.course_categories.exclude(code__in=predefined_codes)
    
    if request.method == 'POST':
        selected_categories = request.POST.getlist('course_categories', [])
    else:
        selected_categories = existing_predefined
    
    context = {
        'form': form, 
        'page_title': 'Edit Regulation',
        'regulation': regulation,
        'course_category_choices': course_category_choices,
        'selected_categories': selected_categories,
        'existing_custom_categories': existing_custom_categories,
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                # Remove all predefined categories
                regulation.course_categories.filter(code__in=predefined_codes).delete()
                
                # Add selected predefined categories
                for cat_code in request.POST.getlist('course_categories', []):
                    CourseCategory.objects.create(
                        regulation=regulation,
                        code=cat_code,
                        is_active=True
                    )
                
                # Handle existing custom categories - keep checked ones, delete unchecked
                kept_custom_ids = request.POST.getlist('existing_custom_cats', [])
                regulation.course_categories.exclude(code__in=predefined_codes).exclude(id__in=kept_custom_ids).delete()
                
                # Add new custom categories
                custom_codes = request.POST.getlist('custom_cat_codes', [])
                custom_descs = request.POST.getlist('custom_cat_descs', [])
                for code, desc in zip(custom_codes, custom_descs):
                    if code and desc:
                        CourseCategory.objects.create(
                            regulation=regulation,
                            code=code.upper(),
                            description=desc,
                            is_active=True
                        )
                
                messages.success(request, "Regulation updated successfully!")
                return redirect(reverse('manage_regulation'))
            except Exception as e:
                messages.error(request, f"Could not update: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, "hod_template/edit_regulation.html", context)


@login_required
def delete_regulation(request, regulation_id):
    """Delete regulation"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    try:
        regulation = get_object_or_404(Regulation, id=regulation_id)
        regulation.delete()
        messages.success(request, "Regulation deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_regulation'))


# =============================================================================
# REGULATION COURSE PLAN MANAGEMENT
# =============================================================================

@login_required
def manage_regulation_courses(request, regulation_id):
    """Manage course plan for a specific regulation"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    
    # Get all course plans for this regulation, grouped by semester and branch
    course_plans = RegulationCoursePlan.objects.filter(
        regulation=regulation
    ).select_related('course', 'category').order_by('semester', 'branch', 'course__course_code')
    
    # Group by semester, then by branch
    plans_by_semester = {}
    for plan in course_plans:
        if plan.semester not in plans_by_semester:
            plans_by_semester[plan.semester] = {}
        if plan.branch not in plans_by_semester[plan.semester]:
            plans_by_semester[plan.semester][plan.branch] = []
        plans_by_semester[plan.semester][plan.branch].append(plan)
    
    # Get all available courses (universal, not tied to regulation)
    available_courses = Course.objects.all().order_by('course_code')
    
    # Get programs from database, grouped by level
    all_programs = Program.objects.all().order_by('level', 'code')
    program_levels = Program.PROGRAM_LEVEL_CHOICES
    
    context = {
        'page_title': f'Course Plan - {regulation}',
        'regulation': regulation,
        'plans_by_semester': dict(sorted(plans_by_semester.items())),
        'available_courses': available_courses,
        'all_programs': all_programs,
        'program_levels': program_levels,
        'semesters': range(1, 9),
    }
    return render(request, 'hod_template/manage_regulation_courses.html', context)


@login_required
def add_regulation_course(request, regulation_id):
    """Add a course to regulation course plan"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    
    if request.method == 'POST':
        course_code = request.POST.get('course_code')
        category_id = request.POST.get('category')
        semester = request.POST.get('semester')
        branch = request.POST.get('branch')
        program_type = request.POST.get('program_type', 'UG')
        is_elective = request.POST.get('is_elective') == 'on'
        
        try:
            course = Course.objects.get(course_code=course_code)
            category = CourseCategory.objects.get(id=category_id) if category_id else None
            
            # Check if already exists
            if RegulationCoursePlan.objects.filter(
                regulation=regulation,
                course=course,
                branch=branch,
                program_type=program_type
            ).exists():
                messages.warning(request, f"Course {course_code} already exists in the plan for {branch} {program_type}")
            else:
                RegulationCoursePlan.objects.create(
                    regulation=regulation,
                    course=course,
                    category=category,
                    semester=int(semester),
                    branch=branch,
                    program_type=program_type,
                    is_elective=is_elective
                )
                messages.success(request, f"Course {course_code} added to Semester {semester} for {branch}")
        except Course.DoesNotExist:
            messages.error(request, f"Course {course_code} not found")
        except Exception as e:
            messages.error(request, f"Error adding course: {str(e)}")
    
    return redirect('manage_regulation_courses', regulation_id=regulation_id)


@login_required
def remove_regulation_course(request, plan_id):
    """Remove a course from regulation course plan"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    plan = get_object_or_404(RegulationCoursePlan, id=plan_id)
    regulation_id = plan.regulation.id
    course_code = plan.course.course_code
    
    try:
        plan.delete()
        messages.success(request, f"Course {course_code} removed from course plan")
    except Exception as e:
        messages.error(request, f"Error removing course: {str(e)}")
    
    return redirect('manage_regulation_courses', regulation_id=regulation_id)


@login_required
def bulk_add_regulation_courses(request, regulation_id):
    """Bulk add courses to a semester in regulation course plan"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    
    if request.method == 'POST':
        semester = int(request.POST.get('semester'))
        branch = request.POST.get('branch')
        program_type = request.POST.get('program_type', 'UG')
        
        # Get all courses for this regulation that are defined for this semester
        courses = Course.objects.filter(regulation=regulation, semester=semester, branch=branch)
        
        added_count = 0
        for course in courses:
            if not RegulationCoursePlan.objects.filter(
                regulation=regulation,
                course=course,
                branch=branch,
                program_type=program_type
            ).exists():
                RegulationCoursePlan.objects.create(
                    regulation=regulation,
                    course=course,
                    semester=semester,
                    branch=branch,
                    program_type=program_type,
                    is_elective=False
                )
                added_count += 1
        
        if added_count > 0:
            messages.success(request, f"Added {added_count} courses to Semester {semester} for {branch}")
        else:
            messages.info(request, f"No new courses to add for Semester {semester} {branch}")
    
    return redirect('manage_regulation_courses', regulation_id=regulation_id)


@login_required
def api_get_programs_by_level(request):
    """API endpoint to get programs filtered by level (UG/PG/PHD)"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    level = request.GET.get('level', '').strip().upper()
    
    programs = Program.objects.all()
    
    if level:
        programs = programs.filter(level=level)
    
    programs = programs.order_by('code')
    
    data = [{
        'code': p.code,
        'name': p.name,
        'full_name': p.full_name,
        'level': p.level,
        'degree': p.degree,
        'specialization': p.specialization or ''
    } for p in programs]
    
    return JsonResponse({'programs': data})


@login_required
def api_get_semester_courses(request, regulation_id):
    """API endpoint to get courses for a specific semester in a regulation"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    semester = request.GET.get('semester')
    program_type = request.GET.get('program_type', 'UG')
    branch = request.GET.get('branch', '')
    
    plans = RegulationCoursePlan.objects.filter(
        regulation=regulation,
        semester=semester,
        program_type=program_type,
        branch=branch
    ).select_related('course', 'category', 'elective_vertical')
    
    data = [{
        'plan_id': p.id,
        'course_code': p.course.course_code,
        'title': p.course.title,
        'credits': p.course.credits,
        'ltp': p.course.ltp_display if not p.course.is_placeholder else '-',
        'category': p.category.code if p.category else None,
        'is_elective': p.is_elective,
        'elective_vertical': p.elective_vertical.name if p.elective_vertical else None,
        'elective_vertical_id': p.elective_vertical.id if p.elective_vertical else None,
        'is_placeholder': p.course.is_placeholder,
        'placeholder_type': p.course.placeholder_type if p.course.is_placeholder else None
    } for p in plans]
    
    return JsonResponse({'courses': data})


@login_required
@csrf_exempt
def api_add_regulation_course(request, regulation_id):
    """API endpoint to add a course to regulation plan"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    
    course_code = request.POST.get('course_code', '').strip()
    semester = request.POST.get('semester')
    category_id = request.POST.get('category')
    program_type = request.POST.get('program_type', 'UG')
    branch = request.POST.get('branch', '')
    is_elective = request.POST.get('is_elective') == '1'
    elective_vertical_id = request.POST.get('elective_vertical', '').strip() or None
    auto_placeholder = request.POST.get('auto_placeholder') == '1'  # New flag for auto-assign
    
    try:
        category = CourseCategory.objects.get(id=category_id) if category_id else None
        
        # Auto-detect elective based on category
        elective_categories = ['PEC', 'OEC', 'ETC', 'SDC', 'SLC', 'IOC', 'AC', 'NCC', 'HON', 'MIN']
        if category and category.code in elective_categories:
            is_elective = True
        
        # Auto-assign placeholder course if requested
        if auto_placeholder and category and category.code in elective_categories:
            # Find how many of this type are already in the regulation (across all semesters)
            existing_count = RegulationCoursePlan.objects.filter(
                regulation=regulation,
                program_type=program_type,
                branch=branch,
                course__is_placeholder=True,
                course__placeholder_type=category.code
            ).count()
            
            next_slot = existing_count + 1
            
            # Get or create the placeholder course for this slot
            course, created = Course.get_or_create_placeholder(category.code, next_slot)
            if not course:
                return JsonResponse({
                    'success': False, 
                    'error': f'Could not create placeholder for {category.code} slot {next_slot}'
                })
        else:
            # Regular course lookup
            if not course_code:
                return JsonResponse({'success': False, 'error': 'Please select a course'})
            try:
                course = Course.objects.get(course_code=course_code)
            except Course.DoesNotExist:
                return JsonResponse({'success': False, 'error': f'Course "{course_code}" not found'})
        
        # Get elective vertical object if provided
        elective_vertical = None
        if is_elective and elective_vertical_id:
            try:
                elective_vertical = ElectiveVertical.objects.get(id=elective_vertical_id, regulation=regulation)
            except ElectiveVertical.DoesNotExist:
                pass  # Vertical not found, leave as None
        
        # Check if this exact course already exists in this semester
        existing = RegulationCoursePlan.objects.filter(
            regulation=regulation,
            course=course,
            semester=semester,
            program_type=program_type,
            branch=branch
        ).exists()
        
        if existing:
            return JsonResponse({
                'success': False, 
                'error': f'{course.course_code} is already added to Semester {semester}'
            })
        
        RegulationCoursePlan.objects.create(
            regulation=regulation,
            course=course,
            semester=semester,
            category=category,
            program_type=program_type,
            branch=branch,
            is_elective=is_elective,
            elective_vertical=elective_vertical
        )
        
        return JsonResponse({
            'success': True,
            'course_code': course.course_code,
            'course_title': course.title
        })
    except CourseCategory.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid category selected'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def api_remove_regulation_course(request):
    """API endpoint to remove a course from regulation plan"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    plan_id = request.POST.get('plan_id')
    
    try:
        plan = RegulationCoursePlan.objects.get(id=plan_id)
        plan.delete()
        return JsonResponse({'success': True})
    except RegulationCoursePlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Course plan not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_search_courses(request):
    """API endpoint to search courses for dropdown"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 20))
    include_placeholders = request.GET.get('include_placeholders', 'true').lower() == 'true'
    placeholders_only = request.GET.get('placeholders_only', 'false').lower() == 'true'
    placeholder_type = request.GET.get('placeholder_type', '')
    
    courses = Course.objects.all()
    
    # Filter by placeholder status
    if placeholders_only:
        courses = courses.filter(is_placeholder=True)
        if placeholder_type:
            courses = courses.filter(placeholder_type=placeholder_type)
    elif not include_placeholders:
        courses = courses.filter(is_placeholder=False)
    
    if query:
        courses = courses.filter(
            Q(course_code__icontains=query) | Q(title__icontains=query)
        )
    
    # Order placeholders by slot number, others by course code
    courses = courses.order_by('-is_placeholder', 'placeholder_type', 'slot_number', 'course_code')[:limit]
    
    data = [{
        'course_code': c.course_code,
        'title': c.title,
        'credits': c.credits,
        'course_type': c.course_type,
        'ltp': c.ltp_display,
        'is_placeholder': c.is_placeholder,
        'placeholder_type': c.placeholder_type,
        'slot_number': c.slot_number,
        'display': f"{c.course_code} - {c.title}" + (" (Placeholder)" if c.is_placeholder else f" ({c.ltp_display}, {c.credits} cr)")
    } for c in courses]
    
    return JsonResponse({'courses': data})


@login_required
def api_get_placeholder_courses(request):
    """API endpoint to get placeholder courses by type"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    placeholder_type = request.GET.get('type', '')
    
    courses = Course.objects.filter(is_placeholder=True)
    if placeholder_type:
        courses = courses.filter(placeholder_type=placeholder_type)
    
    courses = courses.order_by('placeholder_type', 'slot_number')
    
    data = [{
        'course_code': c.course_code,
        'title': c.title,
        'credits': c.credits,
        'placeholder_type': c.placeholder_type,
        'slot_number': c.slot_number,
    } for c in courses]
    
    return JsonResponse({'placeholders': data})


# =============================================================================
# ELECTIVE COURSE OFFERINGS APIs
# =============================================================================

@login_required
def api_get_elective_offerings(request):
    """API endpoint to get elective offerings for a regulation course plan"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    plan_id = request.GET.get('plan_id')
    
    if not plan_id:
        return JsonResponse({'error': 'plan_id required'}, status=400)
    
    offerings = ElectiveCourseOffering.objects.filter(
        regulation_course_plan_id=plan_id
    ).select_related('actual_course', 'elective_vertical')
    
    data = [{
        'id': o.id,
        'course_code': o.actual_course.course_code,
        'course_title': o.actual_course.title,
        'batch_count': o.batch_count,
        'capacity_per_batch': o.capacity_per_batch,
        'vertical': o.elective_vertical.name if o.elective_vertical else None,
    } for o in offerings]
    
    return JsonResponse({'offerings': data})


@login_required
@csrf_exempt
def api_add_elective_offering(request):
    """API endpoint to add an elective course offering"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    plan_id = request.POST.get('plan_id')
    course_code = request.POST.get('course_code')
    batch_count = request.POST.get('batch_count', 1)
    capacity_per_batch = request.POST.get('capacity_per_batch', 30)
    faculty_id = request.POST.get('faculty_id', '').strip() or None
    semester_id = request.POST.get('semester_id')
    
    try:
        plan = RegulationCoursePlan.objects.get(id=plan_id)
        course = Course.objects.get(course_code=course_code)
        semester = Semester.objects.get(id=semester_id) if semester_id else None
        
        # Check if this course is already offered for this plan
        existing = ElectiveCourseOffering.objects.filter(
            regulation_course_plan=plan,
            actual_course=course,
            semester=semester
        ).exists()
        
        if existing:
            return JsonResponse({
                'success': False,
                'error': f'{course.course_code} is already offered for this slot'
            })
        
        ElectiveCourseOffering.objects.create(
            regulation_course_plan=plan,
            semester=semester,
            actual_course=course,
            batch_count=int(batch_count),
            capacity_per_batch=int(capacity_per_batch),
            elective_vertical=plan.elective_vertical
        )
        
        return JsonResponse({'success': True})
    except RegulationCoursePlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid plan ID'})
    except Course.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Course not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def api_remove_elective_offering(request):
    """API endpoint to remove an elective course offering"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    offering_id = request.POST.get('offering_id')
    
    try:
        offering = ElectiveCourseOffering.objects.get(id=offering_id)
        offering.delete()
        return JsonResponse({'success': True})
    except ElectiveCourseOffering.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Offering not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# ELECTIVE VERTICAL MANAGEMENT APIs
# =============================================================================

@login_required
def api_get_elective_verticals(request, regulation_id):
    """API endpoint to get all elective verticals for a regulation"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    
    verticals = ElectiveVertical.objects.filter(
        regulation=regulation,
        is_active=True
    ).order_by('name')
    
    data = [{
        'id': v.id,
        'name': v.name,
        'description': v.description or '',
        'course_count': v.course_plans.count()
    } for v in verticals]
    
    return JsonResponse({'verticals': data})


@login_required
@csrf_exempt
def api_add_elective_vertical(request, regulation_id):
    """API endpoint to add a new elective vertical to a regulation"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    regulation = get_object_or_404(Regulation, id=regulation_id)
    
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip() or None
    
    if not name:
        return JsonResponse({'success': False, 'error': 'Vertical name is required'})
    
    # Check if already exists
    if ElectiveVertical.objects.filter(regulation=regulation, name__iexact=name).exists():
        return JsonResponse({'success': False, 'error': 'A vertical with this name already exists'})
    
    try:
        vertical = ElectiveVertical.objects.create(
            regulation=regulation,
            name=name,
            description=description
        )
        return JsonResponse({
            'success': True,
            'vertical': {
                'id': vertical.id,
                'name': vertical.name,
                'description': vertical.description or ''
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def api_edit_elective_vertical(request, vertical_id):
    """API endpoint to edit an elective vertical"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    vertical = get_object_or_404(ElectiveVertical, id=vertical_id)
    
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip() or None
    
    if not name:
        return JsonResponse({'success': False, 'error': 'Vertical name is required'})
    
    # Check if name already exists (excluding current vertical)
    if ElectiveVertical.objects.filter(
        regulation=vertical.regulation, 
        name__iexact=name
    ).exclude(id=vertical_id).exists():
        return JsonResponse({'success': False, 'error': 'A vertical with this name already exists'})
    
    try:
        vertical.name = name
        vertical.description = description
        vertical.save()
        return JsonResponse({
            'success': True,
            'vertical': {
                'id': vertical.id,
                'name': vertical.name,
                'description': vertical.description or ''
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
def api_delete_elective_vertical(request, vertical_id):
    """API endpoint to delete an elective vertical"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    vertical = get_object_or_404(ElectiveVertical, id=vertical_id)
    
    # Check if any courses are using this vertical
    course_count = vertical.course_plans.count()
    if course_count > 0:
        return JsonResponse({
            'success': False, 
            'error': f'Cannot delete: {course_count} course(s) are assigned to this vertical'
        })
    
    try:
        vertical.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# SEMESTER COURSE ASSIGNMENT (for specific academic semester)
# =============================================================================

@login_required
def semester_course_assignment(request):
    """
    Assign courses for a specific semester with pre-fill from regulation course plan.
    Shows courses based on student's regulation.
    """
    if not check_hod_permission(request.user):
        return redirect('/')
    
    from django.utils import timezone
    
    # Get active/upcoming semesters
    current_academic_year = AcademicYear.get_current()
    semesters = Semester.objects.filter(
        academic_year=current_academic_year
    ).order_by('semester_number') if current_academic_year else Semester.objects.none()
    
    # Get filter parameters
    selected_semester = request.GET.get('semester_id')
    selected_branch = request.GET.get('branch', '')
    selected_batch = request.GET.get('batch')
    selected_program = request.GET.get('program_type', 'UG')
    
    # Get programs from database for dynamic branch selection
    all_programs = Program.objects.all().order_by('level', 'code')
    program_levels = Program.PROGRAM_LEVEL_CHOICES
    
    # Get branches filtered by selected program type
    filtered_programs = all_programs.filter(level=selected_program) if selected_program else all_programs
    
    # Set default branch if not selected
    if not selected_branch and filtered_programs.exists():
        selected_branch = filtered_programs.first().code
    
    # Get batch choices from database
    if current_academic_year:
        batch_choices = list(ProgramBatch.objects.filter(
            academic_year=current_academic_year,
            is_active=True
        ).values_list('batch_name', 'batch_display').distinct().order_by('batch_name'))
    else:
        batch_choices = []
    
    # Get all regulations for manual selection
    all_regulations = Regulation.objects.all().order_by('-year', 'name')
    selected_regulation_id = request.GET.get('regulation_id', '')
    
    context = {
        'page_title': 'Semester Course Assignment',
        'semesters': semesters,
        'all_programs': all_programs,
        'program_levels': program_levels,
        'filtered_programs': filtered_programs,
        'batch_choices': batch_choices,
        'selected_semester': selected_semester,
        'selected_branch': selected_branch,
        'selected_batch': selected_batch,
        'selected_program': selected_program,
        'academic_year': current_academic_year,
        'course_plans': [],
        'existing_assignments': [],
        'faculty_list': Faculty_Profile.objects.select_related('user').filter(user__is_active=True),
        'all_regulations': all_regulations,
        'selected_regulation_id': selected_regulation_id,
    }
    
    if selected_semester and selected_branch:
        semester_obj = get_object_or_404(Semester, id=selected_semester)
        context['semester_obj'] = semester_obj
        
        # Determine which regulation applies to students in this semester
        # Find students in this semester number with this branch
        students_in_sem = Student_Profile.objects.filter(
            current_sem=semester_obj.semester_number,
            branch=selected_branch,
            status='ACTIVE'
        )
        if selected_batch:
            students_in_sem = students_in_sem.filter(batch_label=selected_batch)
        if selected_program:
            students_in_sem = students_in_sem.filter(program_type=selected_program)
        
        # Get the most common regulation among these students
        regulation = None
        student_count = students_in_sem.count()
        
        if students_in_sem.exists():
            from django.db.models import Count
            reg_counts = students_in_sem.values('regulation').annotate(
                count=Count('regulation')
            ).order_by('-count')
            if reg_counts and reg_counts[0]['regulation']:
                regulation = Regulation.objects.get(id=reg_counts[0]['regulation'])
        
        # If no students or no regulation detected, allow manual selection
        if not regulation and selected_regulation_id:
            try:
                regulation = Regulation.objects.get(id=selected_regulation_id)
            except Regulation.DoesNotExist:
                pass
        
        context['regulation'] = regulation
        context['student_count'] = student_count
        context['needs_regulation_selection'] = (student_count == 0 and not regulation)
        
        # Get course plan from regulation
        if regulation:
            course_plans = RegulationCoursePlan.objects.filter(
                regulation=regulation,
                semester=semester_obj.semester_number,
                branch=selected_branch,
                program_type=selected_program
            ).select_related('course', 'category', 'elective_vertical')
            
            # Separate core and elective courses for better display
            core_courses = [p for p in course_plans if not p.is_elective]
            elective_courses = [p for p in course_plans if p.is_elective]
            
            context['course_plans'] = course_plans
            context['core_courses'] = core_courses
            context['elective_courses'] = elective_courses
            
            # Get elective offerings for placeholder courses
            elective_offerings = ElectiveCourseOffering.objects.filter(
                regulation_course_plan__in=course_plans,
                semester=semester_obj
            ).select_related('actual_course', 'elective_vertical')
            
            # Create a map of plan_id to offerings
            elective_offerings_map = {}
            for offering in elective_offerings:
                plan_id = offering.regulation_course_plan_id
                if plan_id not in elective_offerings_map:
                    elective_offerings_map[plan_id] = []
                elective_offerings_map[plan_id].append(offering)
            context['elective_offerings_map'] = elective_offerings_map
        
        # Get existing course assignments for this semester
        existing_filter = {
            'semester': semester_obj,
            'academic_year': current_academic_year,
        }
        if selected_batch:
            existing_filter['batch_label'] = selected_batch
        
        existing_assignments = Course_Assignment.objects.filter(
            **existing_filter
        ).select_related('course', 'faculty', 'faculty__user')
        context['existing_assignments'] = existing_assignments
        
        # Create a dict for quick lookup in template
        assignments_by_course = {}
        for assign in existing_assignments:
            code = assign.course.course_code
            if code not in assignments_by_course:
                assignments_by_course[code] = []
            assignments_by_course[code].append(assign)
        context['assignments_by_course'] = assignments_by_course
    
    return render(request, 'hod_template/semester_course_assignment.html', context)


@login_required
def create_course_assignments(request):
    """Create course assignments from semester course assignment page"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    if request.method == 'POST':
        semester_id = request.POST.get('semester_id')
        academic_year_id = request.POST.get('academic_year_id')
        
        semester_obj = get_object_or_404(Semester, id=semester_id)
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id)
        
        # Process each course assignment
        course_codes = request.POST.getlist('course_code[]')
        faculty_ids = request.POST.getlist('faculty_id[]')
        batch_labels = request.POST.getlist('batch_label[]')
        
        created_count = 0
        errors = []
        
        for i, course_code in enumerate(course_codes):
            if not course_code:
                continue
                
            faculty_id = faculty_ids[i] if i < len(faculty_ids) else None
            batch_label = batch_labels[i] if i < len(batch_labels) else None
            
            if not faculty_id or not batch_label:
                continue
            
            try:
                course = Course.objects.get(course_code=course_code)
                faculty = Faculty_Profile.objects.get(id=faculty_id)
                
                # Check if assignment already exists
                if not Course_Assignment.objects.filter(
                    course=course,
                    batch_label=batch_label,
                    academic_year=academic_year,
                    semester=semester_obj
                ).exists():
                    Course_Assignment.objects.create(
                        course=course,
                        faculty=faculty,
                        batch_label=batch_label,
                        academic_year=academic_year,
                        semester=semester_obj,
                        is_active=True
                    )
                    created_count += 1
            except Exception as e:
                errors.append(f"Error for {course_code}: {str(e)}")
        
        if created_count > 0:
            messages.success(request, f"Created {created_count} course assignment(s)")
        if errors:
            messages.warning(request, f"Some errors occurred: {'; '.join(errors[:3])}")
        
        # Redirect back with same filters
        return redirect(f"{reverse('semester_course_assignment')}?semester_id={semester_id}&branch={request.POST.get('branch', 'CSE')}&batch={request.POST.get('batch', '')}&program_type={request.POST.get('program_type', 'UG')}")
    
    return redirect('semester_course_assignment')


# =============================================================================
# PROGRAM BATCH MANAGEMENT
# =============================================================================

@login_required
def manage_program_batches(request, year_id=None):
    """Manage classroom batches for programs in an academic year"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    academic_years = AcademicYear.objects.all().order_by('-year')
    
    # Select academic year
    if year_id:
        selected_year = get_object_or_404(AcademicYear, id=year_id)
    else:
        selected_year = AcademicYear.get_current() or academic_years.first()
    
    # Get all programs
    programs = Program.objects.all().order_by('level', 'code')
    
    # Get Year 1 batches for the selected year, grouped by program
    year1_batches = []
    if selected_year:
        batches = ProgramBatch.objects.filter(
            academic_year=selected_year,
            year_of_study=1  # Only Year 1 batches
        ).select_related('program').order_by('program__level', 'program__code', 'batch_name')
        
        # Group batches by program
        batches_by_program = {}
        for batch in batches:
            if batch.program.code not in batches_by_program:
                # Check if students exist for this program's Year 1
                has_students = ProgramBatch.has_students(selected_year, batch.program, 1)
                batches_by_program[batch.program.code] = {
                    'program': batch.program,
                    'batches': [],
                    'has_students': has_students,
                }
            batches_by_program[batch.program.code]['batches'].append(batch)
        
        year1_batches = list(batches_by_program.values())
    
    # Get previous year for copy option
    previous_year = None
    if selected_year:
        try:
            start_year = int(selected_year.year.split('-')[0])
            prev_year_str = f"{start_year - 1}-{str(start_year)[-2:]}"
            previous_year = AcademicYear.objects.filter(year=prev_year_str).first()
        except:
            pass
    
    # Check which programs don't have Year 1 batches configured
    programs_without_batches = []
    for program in programs:
        has_year1 = ProgramBatch.objects.filter(
            academic_year=selected_year,
            program=program,
            year_of_study=1,
            is_active=True
        ).exists() if selected_year else False
        if not has_year1:
            programs_without_batches.append(program)
    
    context = {
        'page_title': 'Manage Program Batches',
        'academic_years': academic_years,
        'selected_year': selected_year,
        'programs': programs,
        'year1_batches': year1_batches,
        'previous_year': previous_year,
        'programs_without_batches': programs_without_batches,
    }
    return render(request, 'hod_template/manage_program_batches.html', context)


@login_required
def add_program_batch(request):
    """Add a new batch for a program"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    if request.method == 'POST':
        year_id = request.POST.get('academic_year')
        program_id = request.POST.get('program')
        year_of_study = request.POST.get('year_of_study')
        batch_names = request.POST.get('batch_names', '').strip()  # Comma-separated
        capacity = request.POST.get('capacity', 60)
        
        if not all([year_id, program_id, year_of_study, batch_names]):
            messages.error(request, "All fields are required")
            return redirect('manage_program_batches', year_id=year_id)
        
        academic_year = get_object_or_404(AcademicYear, id=year_id)
        program = get_object_or_404(Program, id=program_id)
        
        # Parse batch names (comma or space separated)
        import re
        batch_list = re.split(r'[,\s]+', batch_names.upper())
        batch_list = [b.strip() for b in batch_list if b.strip()]
        
        created_count = 0
        skipped_count = 0
        
        for batch_name in batch_list:
            _, was_created = ProgramBatch.objects.get_or_create(
                academic_year=academic_year,
                program=program,
                year_of_study=int(year_of_study),
                batch_name=batch_name,
                defaults={
                    'batch_display': f"{batch_name} Section",
                    'capacity': int(capacity),
                    'is_active': True
                }
            )
            if was_created:
                created_count += 1
            else:
                skipped_count += 1
        
        if created_count:
            messages.success(request, f"Added {created_count} batch(es) for {program.code} Year {year_of_study}")
        if skipped_count:
            messages.info(request, f"{skipped_count} batch(es) already existed")
        
        return redirect('manage_program_batches_year', year_id=year_id)
    
    return redirect('manage_program_batches')


@login_required
def copy_batches_from_previous_year(request):
    """Copy batch configuration from previous academic year"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    if request.method == 'POST':
        source_year_id = request.POST.get('source_year')
        target_year_id = request.POST.get('target_year')
        program_id = request.POST.get('program')  # Optional - if None, copy all
        
        if not all([source_year_id, target_year_id]):
            messages.error(request, "Source and target years are required")
            return redirect('manage_program_batches')
        
        source_year = get_object_or_404(AcademicYear, id=source_year_id)
        target_year = get_object_or_404(AcademicYear, id=target_year_id)
        program = Program.objects.filter(id=program_id).first() if program_id else None
        
        created, skipped = ProgramBatch.copy_from_previous_year(source_year, target_year, program)
        
        if created:
            messages.success(request, f"Copied {created} batch(es) from {source_year} to {target_year}")
        if skipped:
            messages.info(request, f"{skipped} batch(es) already existed")
        if not created and not skipped:
            messages.warning(request, f"No batches found to copy from {source_year}")
        
        return redirect('manage_program_batches_year', year_id=target_year_id)
    
    return redirect('manage_program_batches')


@login_required
def delete_program_batch(request, batch_id):
    """Delete a program batch"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    batch = get_object_or_404(ProgramBatch, id=batch_id)
    year_id = batch.academic_year.id
    
    # Check if any students are assigned to this batch
    student_count = Student_Profile.objects.filter(
        branch=batch.program.code,
        batch_label=batch.batch_name
    ).count()
    
    if student_count > 0:
        messages.error(request, f"Cannot delete batch {batch.batch_name} - {student_count} student(s) assigned")
    else:
        batch.delete()
        messages.success(request, f"Batch {batch.batch_name} deleted successfully")
    
    return redirect('manage_program_batches_year', year_id=year_id)


@login_required
def initialize_default_batches(request, year_id, program_id):
    """Initialize default batches for a program from its default settings"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    academic_year = get_object_or_404(AcademicYear, id=year_id)
    program = get_object_or_404(Program, id=program_id)
    
    # Only allow for Year 1 and if no students exist
    has_students = ProgramBatch.has_students(academic_year, program, 1)
    if has_students:
        messages.error(request, f"Cannot initialize batches - students already assigned to {program.code}")
        return redirect('manage_program_batches_year', year_id=year_id)
    
    # Create default batches
    created_count, created_names = ProgramBatch.create_default_batches(
        academic_year=academic_year,
        program=program,
        year_of_study=1,
        capacity=60
    )
    
    if created_count:
        messages.success(request, f"Created {created_count} batch(es) for {program.code}: {', '.join(created_names)}")
    else:
        messages.info(request, f"Batches already exist for {program.code}")
    
    return redirect('manage_program_batches_year', year_id=year_id)


@login_required
def api_get_batches(request):
    """API endpoint to get batches filtered by program, year, and academic year"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    academic_year_id = request.GET.get('academic_year')
    program_code = request.GET.get('program')
    year_of_study = request.GET.get('year_of_study')
    
    # Get academic year
    if academic_year_id:
        academic_year = AcademicYear.objects.filter(id=academic_year_id).first()
    else:
        academic_year = AcademicYear.get_current()
    
    if not academic_year:
        return JsonResponse({'batches': []})
    
    # Build query
    qs = ProgramBatch.objects.filter(academic_year=academic_year, is_active=True)
    
    if program_code:
        qs = qs.filter(program__code=program_code)
    if year_of_study:
        qs = qs.filter(year_of_study=int(year_of_study))
    
    batches = list(qs.values('id', 'batch_name', 'batch_display', 'capacity', 'year_of_study').order_by('batch_name'))
    
    return JsonResponse({'batches': batches})


# =============================================================================
# PROGRAM MANAGEMENT
# =============================================================================

@login_required
def add_program(request):
    """Add academic program"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = ProgramForm(request.POST or None)
    context = {'form': form, 'page_title': 'Add Academic Program'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Program added successfully!")
                return redirect(reverse('manage_programs'))
            except Exception as e:
                messages.error(request, f"Could not add: {str(e)}")
        else:
            # Show specific field errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        field_label = form.fields[field].label or field.replace('_', ' ').title()
                        messages.error(request, f"{field_label}: {error}")
    
    return render(request, "hod_template/add_program.html", context)


@login_required
def manage_programs(request):
    """Manage academic programs"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    programs = Program.objects.all().prefetch_related('regulations')
    context = {'programs': programs, 'page_title': 'Manage Programs'}
    return render(request, "hod_template/manage_programs.html", context)


@login_required
def edit_program(request, program_id):
    """Edit academic program"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    program = get_object_or_404(Program, id=program_id)
    form = ProgramForm(request.POST or None, instance=program)
    
    # Get actual student count using branch field (stores program code)
    student_count = Student_Profile.objects.filter(branch=program.code).count()
    
    context = {
        'form': form, 
        'program': program, 
        'student_count': student_count,
        'page_title': f'Edit Program - {program.code}'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Program updated successfully!")
                return redirect(reverse('manage_programs'))
            except Exception as e:
                messages.error(request, f"Could not update: {str(e)}")
        else:
            messages.error(request, "Please correct the errors")
    
    return render(request, "hod_template/edit_program.html", context)


@login_required
def delete_program(request, program_id):
    """Delete academic program"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    try:
        program = get_object_or_404(Program, id=program_id)
        program.delete()
        messages.success(request, "Program deleted successfully")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_programs'))


# =============================================================================
# LEAVE MANAGEMENT
# =============================================================================

@login_required
@csrf_exempt
def view_leave_requests(request):
    """View and manage all leave requests"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    if request.method == 'POST':
        leave_id = request.POST.get('id')
        status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        
        try:
            leave = get_object_or_404(LeaveRequest, id=leave_id)
            leave.status = status
            leave.admin_remarks = remarks
            leave.approved_by = request.user
            leave.save()
            
            # Send notification
            Notification.objects.create(
                recipient=leave.user,
                sender=request.user,
                title=f"Leave Request {status}",
                message=f"Your leave request from {leave.start_date} to {leave.end_date} has been {status.lower()}.",
                notification_type='INFO'
            )
            
            return HttpResponse(True)
        except Exception as e:
            return HttpResponse(False)
    
    leaves = LeaveRequest.objects.select_related('user').order_by('-created_at')
    pending_leaves = leaves.filter(status='PENDING')
    processed_leaves = leaves.exclude(status='PENDING')
    
    context = {
        'pending_leaves': pending_leaves,
        'processed_leaves': processed_leaves,
        'page_title': 'Leave Requests'
    }
    return render(request, "hod_template/staff_leave_view.html", context)


# =============================================================================
# FEEDBACK MANAGEMENT
# =============================================================================

@login_required
@csrf_exempt
def view_feedbacks(request):
    """View and respond to feedbacks"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    if request.method == 'POST':
        feedback_id = request.POST.get('id')
        reply = request.POST.get('reply')
        
        try:
            feedback = get_object_or_404(Feedback, id=feedback_id)
            feedback.reply = reply
            feedback.status = 'REVIEWED'
            feedback.replied_by = request.user
            feedback.save()
            
            # Send notification
            if not feedback.is_anonymous:
                Notification.objects.create(
                    recipient=feedback.user,
                    sender=request.user,
                    title="Feedback Response",
                    message=f"Your feedback '{feedback.subject[:30]}...' has been responded to.",
                    notification_type='INFO'
                )
            
            return HttpResponse(True)
        except Exception as e:
            return HttpResponse(False)
    
    feedbacks = Feedback.objects.select_related('user').order_by('-created_at')
    
    context = {
        'feedbacks': feedbacks,
        'page_title': 'Feedback Messages'
    }
    return render(request, 'hod_template/student_feedback_template.html', context)


# =============================================================================
# EVENT MANAGEMENT
# =============================================================================

@login_required
def add_event(request):
    """Add new event"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = EventForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Event'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Event added successfully!")
                return redirect(reverse('manage_event'))
            except Exception as e:
                messages.error(request, f"Could not add event: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_event_template.html', context)


@login_required
def manage_event(request):
    """Manage events"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    events = Event.objects.all()
    context = {
        'events': events,
        'page_title': 'Manage Events'
    }
    return render(request, 'hod_template/manage_event.html', context)


@login_required
def edit_event(request, event_id):
    """Edit event"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    event = get_object_or_404(Event, id=event_id)
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    context = {'form': form, 'event': event, 'page_title': 'Edit Event'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Event updated successfully!")
                return redirect(reverse('manage_event'))
            except Exception as e:
                messages.error(request, f"Could not update event: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_event_template.html', context)


@login_required
def delete_event(request, event_id):
    """Delete event"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    event = get_object_or_404(Event, id=event_id)
    try:
        event.delete()
        messages.success(request, "Event deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_event'))


# =============================================================================
# PUBLICATION VERIFICATION
# =============================================================================

@login_required
def verify_publications(request):
    """View and verify faculty publications"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    publications = Publication.objects.select_related('faculty', 'faculty__user').order_by('-created_at')
    unverified = publications.filter(is_verified=False)
    verified = publications.filter(is_verified=True)
    
    context = {
        'unverified_publications': unverified,
        'verified_publications': verified,
        'page_title': 'Verify Publications'
    }
    return render(request, 'hod_template/verify_publications.html', context)


@login_required
@csrf_exempt
def approve_publication(request, publication_id):
    """Approve a publication"""
    if not check_hod_permission(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    try:
        publication = get_object_or_404(Publication, id=publication_id)
        publication.is_verified = True
        publication.verified_by = request.user
        publication.save()
        
        # Notify faculty
        Notification.objects.create(
            recipient=publication.faculty.user,
            sender=request.user,
            title="Publication Verified",
            message=f"Your publication '{publication.title[:50]}...' has been verified by HOD.",
            notification_type='INFO'
        )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# LAB ISSUES MANAGEMENT
# =============================================================================

@login_required
def view_lab_issues(request):
    """View and manage lab issues"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    issues = Lab_Issue_Log.objects.select_related('reported_by', 'assigned_to').order_by('-reported_at')
    
    context = {
        'issues': issues,
        'page_title': 'Lab Issues'
    }
    return render(request, 'hod_template/view_lab_issues.html', context)


# =============================================================================
# ANNOUNCEMENTS
# =============================================================================

@login_required
def add_announcement(request):
    """Add department announcement"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = AnnouncementForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Announcement'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                announcement = form.save(commit=False)
                announcement.posted_by = request.user
                announcement.save()
                messages.success(request, "Announcement posted successfully!")
                return redirect(reverse('manage_announcement'))
            except Exception as e:
                messages.error(request, f"Could not post: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
    return render(request, 'hod_template/add_announcement.html', context)


@login_required
def manage_announcement(request):
    """Manage announcements"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    announcements = Announcement.objects.order_by('-created_at')
    context = {
        'announcements': announcements,
        'page_title': 'Manage Announcements'
    }
    return render(request, 'hod_template/manage_announcement.html', context)


@login_required
def delete_announcement(request, announcement_id):
    """Delete an announcement"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    try:
        announcement = get_object_or_404(Announcement, id=announcement_id)
        announcement.delete()
        messages.success(request, "Announcement deleted successfully!")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_announcement'))


# =============================================================================
# NOTIFICATIONS
# =============================================================================

@login_required
def send_notification_page(request):
    """Page to send notifications"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    users = Account_User.objects.filter(is_active=True).exclude(id=request.user.id)
    context = {
        'users': users,
        'page_title': 'Send Notifications'
    }
    return render(request, "hod_template/staff_notification.html", context)


@login_required
@csrf_exempt
def send_notification(request):
    """Send notification to user"""
    if not check_hod_permission(request.user):
        return HttpResponse(False)
    
    user_id = request.POST.get('id')
    message = request.POST.get('message')
    title = request.POST.get('title', 'Notification from HOD')
    
    try:
        recipient = get_object_or_404(Account_User, id=user_id)
        
        Notification.objects.create(
            recipient=recipient,
            sender=request.user,
            title=title,
            message=message,
            notification_type='INFO'
        )
        
        # Send FCM notification if token exists
        if recipient.fcm_token:
            url = "https://fcm.googleapis.com/fcm/send"
            body = {
                'notification': {
                    'title': title,
                    'body': message,
                    'icon': static('dist/img/AdminLTELogo.png')
                },
                'to': recipient.fcm_token
            }
            headers = {
                'Authorization': 'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                'Content-Type': 'application/json'
            }
            requests.post(url, data=json.dumps(body), headers=headers)
        
        return HttpResponse(True)
    except Exception as e:
        return HttpResponse(False)


# =============================================================================
# PROFILE
# =============================================================================

@login_required
def admin_view_profile(request):
    """View/edit HOD profile"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    user = request.user
    form = AccountUserForm(request.POST or None, request.FILES or None, instance=user)
    
    context = {
        'form': form,
        'page_title': 'View/Edit Profile'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                user = form.save(commit=False)
                password = form.cleaned_data.get('password')
                if password:
                    user.set_password(password)
                
                if 'profile_pic' in request.FILES:
                    fs = FileSystemStorage()
                    filename = fs.save(request.FILES['profile_pic'].name, request.FILES['profile_pic'])
                    user.profile_pic = fs.url(filename)
                
                user.save()
                messages.success(request, "Profile updated successfully!")
                return redirect(reverse('admin_view_profile'))
            except Exception as e:
                messages.error(request, f"Could not update: {str(e)}")
        else:
            messages.error(request, "Please fill the form correctly")
    
    return render(request, "hod_template/admin_view_profile.html", context)


# =============================================================================
# ATTENDANCE VIEW
# =============================================================================

@login_required
def admin_view_attendance(request):
    """View attendance reports"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    assignments = Course_Assignment.objects.select_related('course', 'faculty').filter(is_active=True)
    academic_years = AcademicYear.objects.all()
    
    context = {
        'assignments': assignments,
        'academic_years': academic_years,
        'page_title': 'View Attendance'
    }
    return render(request, "hod_template/admin_view_attendance.html", context)


@csrf_exempt
def get_admin_attendance(request):
    """API to get attendance data"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    assignment_id = request.POST.get('assignment')
    date = request.POST.get('date')
    
    try:
        assignment = get_object_or_404(Course_Assignment, id=assignment_id)
        attendance_records = Attendance.objects.filter(assignment=assignment)
        
        if date:
            attendance_records = attendance_records.filter(date=date)
        
        json_data = []
        for record in attendance_records:
            data = {
                "status": record.status,
                "name": record.student.user.full_name,
                "register_no": record.student.register_no,
                "date": str(record.date),
                "period": record.period
            }
            json_data.append(data)
        
        return JsonResponse(json.dumps(json_data), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# =============================================================================
# QUESTION PAPER MANAGEMENT
# =============================================================================

@login_required
def assign_question_paper(request):
    """Assign question paper setting task to faculty"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = QuestionPaperAssignmentForm(request.POST or None)
    
    # Get recent assignments
    recent_assignments = QuestionPaperAssignment.objects.all().order_by('-created_at')[:10]
    
    context = {
        'form': form,
        'recent_assignments': recent_assignments,
        'page_title': 'Assign Question Paper Task'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                qp_assignment = form.save(commit=False)
                qp_assignment.assigned_by = request.user
                qp_assignment.save()
                
                # Create notification for assigned faculty
                Notification.objects.create(
                    recipient=qp_assignment.assigned_faculty.user,
                    title='Question Paper Assignment',
                    message=f'You have been assigned to set {qp_assignment.get_exam_type_display()} question paper for {qp_assignment.course.course_code} - {qp_assignment.course.title}. Deadline: {qp_assignment.deadline}',
                    notification_type='ANNOUNCEMENT',
                    link=reverse('staff_view_qp_assignments')
                )
                
                messages.success(request, f"Question paper task assigned to {qp_assignment.assigned_faculty.user.full_name} successfully!")
                return redirect(reverse('manage_qp_assignments'))
            except Exception as e:
                messages.error(request, f"Could not assign: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form")
    
    return render(request, 'hod_template/assign_question_paper.html', context)


@login_required
def manage_qp_assignments(request):
    """View and manage all question paper assignments"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    # Filter options
    status_filter = request.GET.get('status', '')
    exam_type_filter = request.GET.get('exam_type', '')
    
    assignments = QuestionPaperAssignment.objects.all().select_related(
        'course', 'assigned_faculty__user', 'academic_year', 'semester'
    ).order_by('-created_at')
    
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    if exam_type_filter:
        assignments = assignments.filter(exam_type=exam_type_filter)
    
    # Statistics
    stats = {
        'total': QuestionPaperAssignment.objects.count(),
        'assigned': QuestionPaperAssignment.objects.filter(status='ASSIGNED').count(),
        'submitted': QuestionPaperAssignment.objects.filter(status='SUBMITTED').count(),
        'approved': QuestionPaperAssignment.objects.filter(status='APPROVED').count(),
        'pending_review': QuestionPaperAssignment.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).count(),
    }
    
    context = {
        'assignments': assignments,
        'stats': stats,
        'status_choices': QuestionPaperAssignment.STATUS_CHOICES,
        'exam_type_choices': QuestionPaperAssignment.EXAM_TYPE_CHOICES,
        'current_status': status_filter,
        'current_exam_type': exam_type_filter,
        'page_title': 'Manage Question Paper Assignments'
    }
    return render(request, 'hod_template/manage_qp_assignments.html', context)


@login_required
def review_question_paper(request, qp_id):
    """Review submitted question paper"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    qp_assignment = get_object_or_404(QuestionPaperAssignment, id=qp_id)
    form = QuestionPaperReviewForm(request.POST or None, instance=qp_assignment)
    
    context = {
        'qp_assignment': qp_assignment,
        'form': form,
        'page_title': f'Review QP - {qp_assignment.course.course_code}'
    }
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                qp = form.save(commit=False)
                qp.reviewed_by = request.user
                qp.reviewed_at = datetime.now()
                qp.save()
                
                # Notify faculty about review result
                status_text = qp.get_status_display()
                Notification.objects.create(
                    recipient=qp.assigned_faculty.user,
                    title=f'Question Paper Review - {status_text}',
                    message=f'Your question paper for {qp.course.course_code} has been reviewed. Status: {status_text}. Comments: {qp.review_comments or "None"}',
                    notification_type='INFO',
                    link=reverse('staff_view_qp_assignments')
                )
                
                messages.success(request, f"Review submitted. Status: {status_text}")
                return redirect(reverse('manage_qp_assignments'))
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Please correct the errors")
    
    return render(request, 'hod_template/review_question_paper.html', context)


@login_required
def delete_qp_assignment(request, qp_id):
    """Delete a question paper assignment"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    try:
        qp_assignment = get_object_or_404(QuestionPaperAssignment, id=qp_id)
        qp_assignment.delete()
        messages.success(request, "Question paper assignment deleted successfully")
    except Exception as e:
        messages.error(request, f"Could not delete: {str(e)}")
    
    return redirect(reverse('manage_qp_assignments'))


@csrf_exempt
@login_required
def get_faculty_for_course(request):
    """AJAX: Get faculty who teach a specific course"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    course_id = request.POST.get('course_id')
    
    try:
        # Get faculty who have course assignments for this course
        course_assignments = Course_Assignment.objects.filter(
            course_id=course_id, 
            is_active=True
        ).select_related('faculty__user')
        
        faculty_list = []
        seen_ids = set()
        
        for ca in course_assignments:
            if ca.faculty.id not in seen_ids:
                faculty_list.append({
                    'id': ca.faculty.id,
                    'name': ca.faculty.user.full_name,
                    'staff_id': ca.faculty.staff_id
                })
                seen_ids.add(ca.faculty.id)
        
        # If no specific faculty found, return all active faculty
        if not faculty_list:
            all_faculty = Faculty_Profile.objects.filter(user__is_active=True).select_related('user')
            for f in all_faculty:
                faculty_list.append({
                    'id': f.id,
                    'name': f.user.full_name,
                    'staff_id': f.staff_id
                })
        
        return JsonResponse({'faculty': faculty_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# =============================================================================
# UTILITY VIEWS
# =============================================================================

@csrf_exempt
def check_email_availability(request):
    """Check if email is available"""
    email = request.POST.get("email")
    try:
        exists = Account_User.objects.filter(email=email).exists()
        return HttpResponse(exists)
    except:
        return HttpResponse(False)


# Aliases for backward compatibility
add_staff = add_faculty
manage_staff = manage_faculty
edit_staff = edit_faculty
delete_staff = delete_faculty
add_session = add_academic_year
manage_session = manage_academic_year
add_course_allocation = add_course_assignment
manage_course_allocation = manage_course_assignment
delete_course_allocation = delete_course_assignment
student_feedback_message = view_feedbacks
staff_feedback_message = view_feedbacks
view_staff_leave = view_leave_requests
view_student_leave = view_leave_requests
admin_notify_staff = send_notification_page
admin_notify_student = send_notification_page
send_student_notification = send_notification
send_staff_notification = send_notification


# =============================================================================
# TIMETABLE MANAGEMENT
# =============================================================================

@login_required
def manage_timetables(request):
    """List all timetables with filtering options"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    timetables = Timetable.objects.all().select_related(
        'academic_year', 'semester', 'regulation', 'created_by'
    ).order_by('-academic_year', 'year', 'batch')
    
    # Filtering
    year_filter = request.GET.get('year')
    batch_filter = request.GET.get('batch')
    academic_year_filter = request.GET.get('academic_year')
    
    if year_filter:
        timetables = timetables.filter(year=year_filter)
    if batch_filter:
        timetables = timetables.filter(batch=batch_filter)
    if academic_year_filter:
        timetables = timetables.filter(academic_year_id=academic_year_filter)
    
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    
    # Get batch choices from database
    current_year = AcademicYear.get_current()
    if current_year:
        batch_choices = list(ProgramBatch.objects.filter(
            academic_year=current_year
        ).values_list('batch_name', 'batch_display').distinct())
    else:
        batch_choices = []
    
    context = {
        'timetables': timetables,
        'academic_years': academic_years,
        'year_choices': Timetable.YEAR_CHOICES,
        'batch_choices': batch_choices,
        'page_title': 'Manage Timetables'
    }
    return render(request, 'hod_template/manage_timetables.html', context)


@login_required
def add_timetable(request):
    """Create a new timetable"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            timetable = form.save(commit=False)
            timetable.created_by = request.user
            timetable.save()
            messages.success(request, f"Timetable created successfully for Year {timetable.year} - Batch {timetable.batch}")
            return redirect('edit_timetable', timetable_id=timetable.id)
        else:
            messages.error(request, "Error creating timetable. Please check the form.")
    else:
        form = TimetableForm()
    
    context = {
        'form': form,
        'page_title': 'Create New Timetable'
    }
    return render(request, 'hod_template/add_timetable.html', context)


@login_required
def edit_timetable(request, timetable_id):
    """Edit timetable - main grid view for entering schedule"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    # Ensure time slots exist, create defaults if not
    if TimeSlot.objects.count() == 0:
        create_default_time_slots()
    
    time_slots = TimeSlot.objects.all().order_by('slot_number')
    days = TimetableEntry.DAY_CHOICES
    
    # Get existing entries
    entries = TimetableEntry.objects.filter(timetable=timetable).select_related(
        'course', 'faculty__user', 'time_slot'
    )
    
    # Create lookup dictionary for entries
    entry_lookup = {}
    for entry in entries:
        key = f"{entry.day}_{entry.time_slot.slot_number}"
        entry_lookup[key] = entry
    
    # Get courses for this year's semester
    course_semesters = []
    if timetable.year == 1:
        course_semesters = [1, 2]
    elif timetable.year == 2:
        course_semesters = [3, 4]
    elif timetable.year == 3:
        course_semesters = [5, 6]
    elif timetable.year == 4:
        course_semesters = [7, 8]
    
    courses = Course.objects.filter(semester__in=course_semesters).order_by('course_code')
    faculty_list = Faculty_Profile.objects.filter(user__is_active=True).select_related('user').order_by('user__full_name')
    
    context = {
        'timetable': timetable,
        'time_slots': time_slots,
        'days': days,
        'entry_lookup': entry_lookup,
        'courses': courses,
        'faculty_list': faculty_list,
        'page_title': f'Edit Timetable - Year {timetable.year} Batch {timetable.batch}'
    }
    return render(request, 'hod_template/edit_timetable.html', context)


@login_required
@csrf_exempt
def save_timetable_entry(request):
    """AJAX endpoint to save a single timetable entry"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            timetable_id = data.get('timetable_id')
            day = data.get('day')
            slot_number = data.get('slot_number')
            course_code = data.get('course_code')
            faculty_id = data.get('faculty_id')
            special_note = data.get('special_note', '')
            
            timetable = get_object_or_404(Timetable, id=timetable_id)
            time_slot = get_object_or_404(TimeSlot, slot_number=slot_number)
            
            # Get or create entry
            entry, created = TimetableEntry.objects.get_or_create(
                timetable=timetable,
                day=day,
                time_slot=time_slot,
                defaults={'special_note': special_note}
            )
            
            # Update entry
            if course_code:
                entry.course = Course.objects.filter(course_code=course_code).first()
            else:
                entry.course = None
            
            if faculty_id:
                entry.faculty = Faculty_Profile.objects.filter(id=faculty_id).first()
            else:
                entry.faculty = None
            
            entry.special_note = special_note
            entry.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Entry saved',
                'entry_id': entry.id,
                'display_text': entry.display_text,
                'faculty_name': entry.faculty_name
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@csrf_exempt
def delete_timetable_entry(request):
    """AJAX endpoint to delete a timetable entry"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            timetable_id = data.get('timetable_id')
            day = data.get('day')
            slot_number = data.get('slot_number')
            
            TimetableEntry.objects.filter(
                timetable_id=timetable_id,
                day=day,
                time_slot__slot_number=slot_number
            ).delete()
            
            return JsonResponse({'success': True, 'message': 'Entry deleted'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def delete_timetable(request, timetable_id):
    """Delete a timetable"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    timetable = get_object_or_404(Timetable, id=timetable_id)
    timetable.delete()
    messages.success(request, "Timetable deleted successfully.")
    return redirect('manage_timetables')


@login_required
def view_timetable(request, timetable_id):
    """View a timetable (read-only)"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    time_slots = TimeSlot.objects.all().order_by('slot_number')
    days = TimetableEntry.DAY_CHOICES
    
    entries = TimetableEntry.objects.filter(timetable=timetable).select_related(
        'course', 'faculty__user', 'time_slot'
    )
    
    entry_lookup = {}
    for entry in entries:
        key = f"{entry.day}_{entry.time_slot.slot_number}"
        entry_lookup[key] = entry
    
    context = {
        'timetable': timetable,
        'time_slots': time_slots,
        'days': days,
        'entry_lookup': entry_lookup,
        'page_title': f'Timetable - Year {timetable.year} Batch {timetable.batch}'
    }
    return render(request, 'hod_template/view_timetable.html', context)


@login_required
def manage_time_slots(request):
    """Manage time slots configuration"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    time_slots = TimeSlot.objects.all().order_by('slot_number')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_defaults':
            create_default_time_slots()
            messages.success(request, "Default time slots created successfully.")
            return redirect('manage_time_slots')
        
        elif action == 'add':
            form = TimeSlotForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Time slot added successfully.")
                return redirect('manage_time_slots')
            else:
                messages.error(request, "Error adding time slot.")
        
        elif action == 'delete':
            slot_id = request.POST.get('slot_id')
            TimeSlot.objects.filter(id=slot_id).delete()
            messages.success(request, "Time slot deleted.")
            return redirect('manage_time_slots')
    
    form = TimeSlotForm()
    
    context = {
        'time_slots': time_slots,
        'form': form,
        'page_title': 'Manage Time Slots'
    }
    return render(request, 'hod_template/manage_time_slots.html', context)


def create_default_time_slots():
    """Create default time slots based on the provided schedule"""
    default_slots = [
        (1, '08:30', '09:20', False),
        (2, '09:25', '10:15', False),
        (3, '10:30', '11:20', False),
        (4, '11:25', '12:15', False),
        # Lunch break (slot 5 could be implicit or we skip)
        (5, '13:10', '14:00', False),
        (6, '14:05', '14:55', False),
        (7, '15:00', '15:50', False),
        (8, '15:55', '16:45', False),
    ]
    
    for slot_num, start, end, is_break in default_slots:
        TimeSlot.objects.get_or_create(
            slot_number=slot_num,
            defaults={
                'start_time': start,
                'end_time': end,
                'is_break': is_break
            }
        )


@login_required
@csrf_exempt
def get_courses_for_semester(request):
    """AJAX endpoint to get courses for a specific year/semester"""
    if request.method == 'GET':
        year = request.GET.get('year')
        
        try:
            year = int(year)
            # Map year to semesters
            course_semesters = []
            if year == 1:
                course_semesters = [1, 2]
            elif year == 2:
                course_semesters = [3, 4]
            elif year == 3:
                course_semesters = [5, 6]
            elif year == 4:
                course_semesters = [7, 8]
            
            courses = Course.objects.filter(semester__in=course_semesters).order_by('course_code')
            course_list = [{'code': c.course_code, 'title': c.title} for c in courses]
            
            return JsonResponse({'courses': course_list})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@csrf_exempt  
def get_all_faculty(request):
    """AJAX endpoint to get all active faculty with search support"""
    if request.method == 'GET':
        search = request.GET.get('search', '')
        
        faculty_qs = Faculty_Profile.objects.filter(user__is_active=True).select_related('user')
        
        if search:
            faculty_qs = faculty_qs.filter(
                Q(user__full_name__icontains=search) | 
                Q(staff_id__icontains=search)
            )
        
        faculty_list = [{
            'id': f.id,
            'name': f.user.full_name,
            'staff_id': f.staff_id,
            'designation': f.get_designation_display()
        } for f in faculty_qs.order_by('user__full_name')[:50]]
        
        return JsonResponse({'faculty': faculty_list})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


# =============================================================================
# BULK STUDENT UPLOAD
# =============================================================================

@login_required
def bulk_upload_students(request):
    """Bulk upload students via CSV file"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    # Get current academic year and configured batches
    current_year = AcademicYear.get_current()
    configured_batches = {}  # {program_code: [batch_names]}
    programs_without_batches = []
    
    if current_year:
        # Get all programs and their configured batches for Year 1
        for program in Program.objects.all():
            batches = ProgramBatch.objects.filter(
                academic_year=current_year,
                program=program,
                year_of_study=1,
                is_active=True
            ).values_list('batch_name', flat=True)
            if batches:
                configured_batches[program.code] = list(batches)
            else:
                programs_without_batches.append(program.code)
    
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, "Please upload a CSV file")
            return redirect('bulk_upload_students')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a valid CSV file")
            return redirect('bulk_upload_students')
        
        try:
            # Read CSV file (handle BOM from Excel)
            file_content = csv_file.read()
            # Try UTF-8 with BOM first, then regular UTF-8
            try:
                decoded_file = file_content.decode('utf-8-sig')  # Handles BOM
            except:
                decoded_file = file_content.decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            success_count = 0
            error_count = 0
            errors = []
            created_students = []
            
            for row_num, row in enumerate(reader, start=2):  # Start from 2 (header is row 1)
                try:
                    # Validate required fields
                    register_no = row.get('register_no', '').strip()
                    
                    # Handle Excel scientific notation (e.g., 1.24E+09 -> 1240000000)
                    if 'E' in register_no.upper() or 'e' in register_no:
                        try:
                            register_no = str(int(float(register_no)))
                        except ValueError:
                            pass
                    
                    full_name = row.get('full_name', '').strip()
                    email = row.get('email', '').strip().lower()
                    gender = row.get('gender', '').strip().upper()
                    batch = row.get('batch', '').strip().upper()
                    branch = row.get('branch', '').strip().upper()
                    program = row.get('program', 'UG').strip().upper()
                    admission_year = row.get('admission_year', '').strip()
                    current_sem = row.get('current_sem', '1').strip()
                    
                    # Optional fields
                    phone = row.get('phone', '').strip()
                    parent_name = row.get('parent_name', '').strip()
                    parent_phone = row.get('parent_phone', '').strip()
                    address = row.get('address', '').strip()
                    
                    # Validation
                    if not all([register_no, full_name, email, gender, batch, branch, admission_year]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        error_count += 1
                        continue
                    
                    if len(register_no) != 10 or not register_no.isdigit():
                        errors.append(f"Row {row_num}: Register number must be 10 digits (got '{register_no}' with length {len(register_no)})")
                        error_count += 1
                        continue
                    
                    if gender not in ['M', 'F', 'O']:
                        errors.append(f"Row {row_num}: Gender must be M, F, or O")
                        error_count += 1
                        continue
                    
                    # Validate branch exists in database
                    valid_branches = list(Program.objects.values_list('code', flat=True))
                    if branch not in valid_branches:
                        errors.append(f"Row {row_num}: Branch '{branch}' not found. Valid options: {', '.join(valid_branches)}")
                        error_count += 1
                        continue
                    
                    # Check if batches are configured for this branch
                    if branch not in configured_batches:
                        errors.append(f"Row {row_num}: No batches configured for {branch}. Please configure batches in 'Manage Batches' first.")
                        error_count += 1
                        continue
                    
                    # Validate batch against configured batches for this branch
                    valid_batches = configured_batches[branch]
                    if batch not in valid_batches:
                        errors.append(f"Row {row_num}: Batch '{batch}' not valid for {branch}. Configured batches: {', '.join(valid_batches)}")
                        error_count += 1
                        continue
                    
                    # Map program
                    program_map = {'B.E': 'UG', 'BE': 'UG', 'UG': 'UG', 'M.E': 'PG', 'ME': 'PG', 'PG': 'PG', 'PH.D': 'PHD', 'PHD': 'PHD'}
                    program_type = program_map.get(program, 'UG')
                    
                    # Check duplicates
                    if Account_User.objects.filter(email=email).exists():
                        errors.append(f"Row {row_num}: Email {email} already exists")
                        error_count += 1
                        continue
                    
                    if Student_Profile.objects.filter(register_no=register_no).exists():
                        errors.append(f"Row {row_num}: Register number {register_no} already exists")
                        error_count += 1
                        continue
                    
                    # Use transaction to rollback if any step fails
                    with transaction.atomic():
                        # Create user with unusable password (forces password setup)
                        user = Account_User.objects.create(
                            email=email,
                            full_name=full_name,
                            gender=gender,
                            phone=phone or None,
                            address=address or None,
                            role='STUDENT',
                            is_active=True
                        )
                        user.set_unusable_password()  # User must set password via email
                        user.save()
                        
                        # Update student profile (auto-created by signal)
                        student = user.student_profile
                        student.register_no = register_no
                        student.batch_label = batch
                        student.branch = branch
                        student.program_type = program_type
                        student.admission_year = int(admission_year)
                        student.current_sem = int(current_sem) if current_sem else 1
                        student.parent_name = parent_name or None
                        student.parent_phone = parent_phone or None
                        
                        # Auto-assign regulation based on admission year
                        # Find the regulation that applies to this admission year (latest regulation year <= admission year)
                        regulation = Regulation.objects.filter(
                            year__lte=int(admission_year)
                        ).order_by('-year').first()
                        if regulation:
                            student.regulation = regulation
                        
                        student.save()
                        
                        created_students.append({
                            'user': user,
                            'email': email,
                            'name': full_name,
                            'college_email': student.college_email,
                            'register_no': register_no
                        })
                        success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            # Send OTP emails to college email for first-time login
            email_success = 0
            email_failed = 0
            for student_data in created_students:
                try:
                    send_first_login_notification(student_data)
                    email_success += 1
                except Exception as e:
                    email_failed += 1
            
            # Show results
            if success_count > 0:
                messages.success(request, f"Successfully created {success_count} students. Login instructions sent to college emails: {email_success}")
            if error_count > 0:
                messages.warning(request, f"Failed to create {error_count} students. See details below.")
            
            context = {
                'page_title': 'Bulk Upload Results',
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors[:20],  # Show first 20 errors
                'total_errors': len(errors),
                'email_success': email_success,
                'email_failed': email_failed,
            }
            return render(request, 'hod_template/bulk_upload_results.html', context)
            
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")
            return redirect('bulk_upload_students')
    
    context = {
        'page_title': 'Bulk Upload Students',
        'current_year': current_year,
        'configured_batches': configured_batches,
        'programs_without_batches': programs_without_batches,
    }
    return render(request, 'hod_template/bulk_upload_students.html', context)


@login_required
def download_student_template(request):
    """Download CSV template for bulk student upload"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_upload_template.csv"'
    
    writer = csv.writer(response)
    # Header row
    writer.writerow([
        'register_no', 'full_name', 'email', 'gender', 'batch', 'branch', 
        'program', 'admission_year', 'current_sem', 'phone', 'parent_name', 
        'parent_phone', 'address'
    ])
    # Sample data rows
    writer.writerow([
        '2023105001', 'John Doe', 'john.doe@student.edu', 'M', 'N', 'CSE',
        'B.E', '2023', '1', '9876543210', 'Mr. Doe', '9876543211', 'Chennai'
    ])
    writer.writerow([
        '2023105002', 'Jane Smith', 'jane.smith@student.edu', 'F', 'P', 'AIML',
        'B.E', '2023', '1', '9876543212', 'Mrs. Smith', '9876543213', 'Coimbatore'
    ])
    
    return response


def send_first_login_notification(student_data):
    """
    Send first-time login notification to student's college email.
    The college email is auto-generated: <register_no>@student.annauniv.edu
    """
    try:
        subject = 'Welcome to CSE Department ERP - First Time Login Instructions'
        message = f"""
Dear {student_data['name']},

Your account has been created in the CSE Department ERP System.

Register Number: {student_data['register_no']}
Personal Email (for login): {student_data['email']}
College Email: {student_data['college_email']}

To set your password, please follow these steps:

1. Visit the ERP portal and click on "First Time Login"
2. Enter your 10-digit Register Number: {student_data['register_no']}
3. An OTP will be sent to THIS college email ({student_data['college_email']})
4. Enter the OTP to verify your identity
5. Set your password

After setting your password, you can login using:
- Email: {student_data['email']}
- Password: (the password you set)

If you have any issues, please contact the CSE Department office.

Regards,
CSE Department
College of Engineering Guindy
Anna University
        """
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [student_data['college_email']],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email error for {student_data['register_no']}: {e}")
        return False


def send_password_setup_email(request, user):
    """Send email to user to set up their password (legacy method)"""
    try:
        # Generate password reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build password reset URL
        reset_url = request.build_absolute_uri(
            reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        )
        
        subject = 'Welcome to CSE Department ERP - Set Your Password'
        message = f"""
Dear {user.full_name},

Your account has been created in the CSE Department ERP System.

Email: {user.email}

Please click the link below to set your password:
{reset_url}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Regards,
CSE Department
College of Engineering Guindy
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@cse.edu',
            [user.email],
            fail_silently=True,
        )
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


@login_required
def resend_password_email(request, student_id):
    """Resend password setup email to a student"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    try:
        student = get_object_or_404(Student_Profile, id=student_id)
        user = student.user
        
        if user.has_usable_password():
            return JsonResponse({'error': 'User has already set their password'}, status=400)
        
        send_password_setup_email(request, user)
        return JsonResponse({'success': True, 'message': f'Password setup email sent to {user.email}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# =============================================================================
# SEMESTER PROMOTION MANAGEMENT
# =============================================================================

from .models import SemesterPromotion, PromotionSchedule, check_and_promote_students, promote_students_manually, create_promotion_schedules_for_semester
from datetime import timedelta
from django.utils import timezone


@login_required
def manage_promotions(request):
    """View and manage student semester promotions"""
    if not check_hod_permission(request.user):
        messages.error(request, "Access Denied. HOD privileges required.")
        return redirect('/')
    
    # Get pending promotions
    today = timezone.now().date()
    pending_schedules = PromotionSchedule.objects.filter(
        executed=False
    ).select_related('semester', 'semester__academic_year').order_by('scheduled_date')
    
    # Get recent promotions
    recent_promotions = SemesterPromotion.objects.select_related(
        'student', 'student__user', 'academic_year', 'promoted_by'
    ).order_by('-promoted_at')[:50]
    
    # Get students by semester for manual promotion
    semesters = range(1, 9)  # Semesters 1-8
    students_by_sem = {}
    for sem in semesters:
        students_by_sem[sem] = Student_Profile.objects.filter(
            current_sem=sem, is_graduated=False
        ).count()
    
    # Check for overdue promotions
    overdue_count = pending_schedules.filter(scheduled_date__lt=today).count()
    
    context = {
        'page_title': 'Semester Promotions',
        'pending_schedules': pending_schedules,
        'recent_promotions': recent_promotions,
        'students_by_sem': students_by_sem,
        'overdue_count': overdue_count,
        'today': today,
    }
    
    return render(request, 'hod_template/manage_promotions.html', context)


@login_required
@csrf_exempt
def run_auto_promotion(request):
    """Manually trigger the auto-promotion check"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    results = check_and_promote_students(promoted_by=request.user)
    
    return JsonResponse({
        'success': True,
        'total_promoted': results['total_promoted'],
        'semesters_processed': results['semesters_processed'],
        'errors': results['errors']
    })


@login_required
@csrf_exempt
def manual_promote_students(request):
    """Manually promote selected students"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        to_semester = int(data.get('to_semester', 0))
        
        if not student_ids:
            return JsonResponse({'error': 'No students selected'}, status=400)
        
        if to_semester < 1 or to_semester > 8:
            return JsonResponse({'error': 'Invalid target semester'}, status=400)
        
        students = Student_Profile.objects.filter(id__in=student_ids)
        
        # Get current academic year
        academic_year = AcademicYear.objects.filter(is_active=True).first()
        
        results = promote_students_manually(
            students=students,
            to_semester=to_semester,
            promoted_by=request.user,
            academic_year=academic_year
        )
        
        return JsonResponse({
            'success': True,
            'promoted': results['success'],
            'errors': results['errors']
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def create_promotion_schedule(request):
    """Create a promotion schedule for a semester"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        semester_id = data.get('semester_id')
        from_semester = int(data.get('from_semester', 0))
        scheduled_date = data.get('scheduled_date')
        
        semester = get_object_or_404(Semester, id=semester_id)
        
        # Create or update schedule
        schedule, created = PromotionSchedule.objects.update_or_create(
            semester=semester,
            target_semester_number=from_semester,
            defaults={
                'scheduled_date': scheduled_date,
                'executed': False
            }
        )
        
        return JsonResponse({
            'success': True,
            'created': created,
            'schedule_id': schedule.id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_students_for_promotion(request):
    """Get list of students in a specific semester for promotion"""
    if not check_hod_permission(request.user):
        return JsonResponse({'error': 'Access Denied'}, status=403)
    
    semester = request.GET.get('semester')
    if not semester:
        return JsonResponse({'error': 'Semester required'}, status=400)
    
    students = Student_Profile.objects.filter(
        current_sem=int(semester),
        status='ACTIVE'
    ).select_related('user').order_by('register_no')
    
    data = [{
        'id': s.id,
        'name': s.user.get_full_name(),
        'register_no': s.register_no,
        'current_sem': s.current_sem,
        'year_of_study': s.year_of_study,
        'batch': s.batch_label
    } for s in students]
    
    return JsonResponse({'students': data})


@login_required
def bulk_promote_semester(request):
    """
    Bulk promotion for all students in a semester after its end date.
    - Odd Sem (1,3,5,7) → Next Sem (same year of study initially, then changes)
    - Even Sem (2,4,6,8) → Next Sem (year of study changes)
    - 8th Sem students → Marked as GRADUATED
    """
    if not check_hod_permission(request.user):
        return redirect('/')
    
    from django.utils import timezone
    from django.db import transaction
    today = timezone.now().date()
    
    # Get semesters that have ended (eligible for promotion)
    completed_semesters = Semester.objects.filter(
        end_date__lt=today
    ).select_related('academic_year').order_by('-end_date')
    
    # Get student counts per semester
    semester_data = []
    for sem in completed_semesters:
        student_count = Student_Profile.objects.filter(
            current_sem=sem.semester_number,
            status='ACTIVE'
        ).count()
        
        # Check if promotion already done for this semester
        already_promoted = SemesterPromotion.objects.filter(
            from_semester=sem.semester_number,
            academic_year=sem.academic_year
        ).exists()
        
        if student_count > 0 or already_promoted:
            semester_data.append({
                'semester': sem,
                'student_count': student_count,
                'already_promoted': already_promoted,
                'is_final_sem': sem.semester_number == 8,
                'next_sem': sem.semester_number + 1 if sem.semester_number < 8 else None,
                'current_year': (sem.semester_number + 1) // 2,
                'next_year': (sem.semester_number + 2) // 2 if sem.semester_number < 8 else None,
            })
    
    if request.method == 'POST':
        semester_id = request.POST.get('semester_id')
        action = request.POST.get('action', 'promote')  # 'promote' or 'graduate'
        
        semester_obj = get_object_or_404(Semester, id=semester_id)
        
        # Verify semester has ended
        if semester_obj.end_date >= today:
            messages.error(request, f"Cannot promote - Semester {semester_obj.semester_number} hasn't ended yet (ends {semester_obj.end_date})")
            return redirect('bulk_promote_semester')
        
        with transaction.atomic():
            students = Student_Profile.objects.filter(
                current_sem=semester_obj.semester_number,
                status='ACTIVE'
            )
            
            promoted_count = 0
            graduated_count = 0
            
            for student in students:
                old_sem = student.current_sem
                old_year = student.year_of_study
                
                if old_sem == 8:
                    # Final semester - Graduate the student
                    student.status = 'GRADUATED'
                    student.graduation_year = today.year
                    student.save()
                    
                    # Log the graduation
                    SemesterPromotion.objects.create(
                        student=student,
                        from_semester=old_sem,
                        to_semester=old_sem,  # Stays at 8
                        from_year=old_year,
                        to_year=old_year,
                        academic_year=semester_obj.academic_year,
                        promotion_type='BULK',
                        promoted_by=request.user,
                        remarks=f"Graduated - Completed 8th semester"
                    )
                    graduated_count += 1
                else:
                    # Promote to next semester
                    student.current_sem = old_sem + 1
                    student.save()
                    
                    # Log the promotion
                    SemesterPromotion.objects.create(
                        student=student,
                        from_semester=old_sem,
                        to_semester=student.current_sem,
                        from_year=old_year,
                        to_year=student.year_of_study,
                        academic_year=semester_obj.academic_year,
                        promotion_type='BULK',
                        promoted_by=request.user,
                        remarks=f"Bulk promoted after Sem {old_sem} completion"
                    )
                    promoted_count += 1
            
            if promoted_count > 0:
                messages.success(request, f"Successfully promoted {promoted_count} student(s) from Semester {semester_obj.semester_number} to Semester {semester_obj.semester_number + 1}")
            if graduated_count > 0:
                messages.success(request, f"Congratulations! {graduated_count} student(s) have graduated (completed 8th semester)")
            
            if promoted_count == 0 and graduated_count == 0:
                messages.info(request, "No students found to promote in this semester")
        
        return redirect('bulk_promote_semester')
    
    context = {
        'page_title': 'Bulk Semester Promotion',
        'semester_data': semester_data,
        'today': today,
    }
    return render(request, 'hod_template/bulk_promote.html', context)