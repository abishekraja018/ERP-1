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
    Course, Course_Assignment, Attendance, Regulation, AcademicYear, Semester,
    Publication, Student_Achievement, Lab_Issue_Log, LeaveRequest, Feedback,
    Event, EventRegistration, Notification, Announcement, QuestionPaperAssignment,
    Timetable, TimetableEntry, TimeSlot, Program
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
    
    # Current academic context
    current_year = AcademicYear.objects.filter(is_current=True).first()
    current_semester = Semester.objects.filter(is_current=True).first()

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
    
    context = {
        'students': students,
        'page_title': 'Manage Students',
        'branch_choices': Student_Profile.BRANCH_CHOICES,
        'batch_choices': Student_Profile.BATCH_LABEL_CHOICES,
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
    
    courses = Course.objects.select_related('regulation').all()
    
    # Apply filters
    regulation = request.GET.get('regulation')
    semester = request.GET.get('semester')
    branch = request.GET.get('branch')
    
    if regulation:
        courses = courses.filter(regulation_id=regulation)
    if semester:
        courses = courses.filter(semester=semester)
    if branch:
        courses = courses.filter(branch=branch)
    
    regulations = Regulation.objects.all()
    
    context = {
        'courses': courses,
        'regulations': regulations,
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
    """Manage academic years"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    academic_years = AcademicYear.objects.all()
    context = {'academic_years': academic_years, 'page_title': 'Manage Academic Years'}
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
def add_semester(request):
    """Add semester"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = SemesterForm(request.POST or None)
    context = {'form': form, 'page_title': 'Add Semester'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Semester added successfully!")
                return redirect(reverse('manage_semester'))
            except Exception as e:
                messages.error(request, f"Could not add: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields correctly")
    
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
    
    return redirect(reverse('manage_semester'))


@login_required
def add_regulation(request):
    """Add regulation"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = RegulationForm(request.POST or None)
    context = {'form': form, 'page_title': 'Add Regulation'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
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
    
    regulations = Regulation.objects.all()
    context = {'regulations': regulations, 'page_title': 'Manage Regulations'}
    return render(request, "hod_template/manage_regulation.html", context)


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
            messages.error(request, "Please fill all required fields correctly")
    
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
    context = {'form': form, 'program': program, 'page_title': f'Edit Program - {program.code}'}
    
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
    
    context = {
        'timetables': timetables,
        'academic_years': academic_years,
        'year_choices': Timetable.YEAR_CHOICES,
        'batch_choices': Timetable.BATCH_CHOICES,
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
                    
                    if batch not in ['N', 'P', 'Q']:
                        errors.append(f"Row {row_num}: Batch must be N, P, or Q")
                        error_count += 1
                        continue
                    
                    if branch not in ['CSE', 'AIML', 'CSBS']:
                        errors.append(f"Row {row_num}: Branch must be CSE, AIML, or CSBS")
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
        'page_title': 'Bulk Upload Students'
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
        is_graduated=False
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