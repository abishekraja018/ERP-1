"""
Anna University CSE Department ERP System
HOD (Head of Department) Views
"""

import json
import requests
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

from .forms import (
    FacultyRegistrationForm, StudentRegistrationForm, NonTeachingStaffRegistrationForm,
    CourseForm, CourseAssignmentForm, RegulationForm, AcademicYearForm, SemesterForm,
    EventForm, LeaveApprovalForm, FeedbackReplyForm, AnnouncementForm,
    FacultyProfileEditForm, StudentProfileEditForm, AccountUserForm,
    QuestionPaperAssignmentForm, QuestionPaperReviewForm
)
from .models import (
    Account_User, Faculty_Profile, Student_Profile, NonTeachingStaff_Profile,
    Course, Course_Assignment, Attendance, Regulation, AcademicYear, Semester,
    Publication, Student_Achievement, Lab_Issue_Log, LeaveRequest, Feedback,
    Event, EventRegistration, Notification, Announcement, QuestionPaperAssignment
)
from .utils.web_scrapper import fetch_acoe_updates
from .utils.cir_scrapper import fetch_cir_ticker_announcements


def check_hod_permission(user):
    """Check if user is HOD"""
    return user.is_authenticated and user.role == 'HOD'


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
    """Add new student"""
    if not check_hod_permission(request.user):
        return redirect('/')
    
    form = StudentRegistrationForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Student'}
    
    if request.method == 'POST':
        if form.is_valid():
            try:
                # Create user
                user = Account_User.objects.create_user(
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    full_name=form.cleaned_data['full_name'],
                    role='STUDENT',
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
                
                # Update student profile
                student = user.student_profile
                student.register_no = form.cleaned_data['register_no']
                student.batch_label = form.cleaned_data['batch_label']
                student.branch = form.cleaned_data['branch']
                student.program_type = form.cleaned_data['program_type']
                student.regulation = form.cleaned_data.get('regulation')
                student.current_sem = form.cleaned_data.get('current_sem', 1)
                student.admission_year = form.cleaned_data.get('admission_year')
                student.advisor = form.cleaned_data.get('advisor')
                student.parent_name = form.cleaned_data.get('parent_name')
                student.parent_phone = form.cleaned_data.get('parent_phone')
                student.blood_group = form.cleaned_data.get('blood_group')
                student.save()
                
                messages.success(request, "Student added successfully!")
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