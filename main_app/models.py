"""
Anna University CSE Department ERP System
Database Models for Django with PostgreSQL

Designed for:
- User & Authentication Management
- Role-Specific Profiles (Faculty, Student, Non-Teaching Staff)
- Academic & Attendance Management
- Research & Achievement Tracking (NIRF/Ranking Data)
- Lab Support System
- Leave, Feedback, Events, and Notifications
"""

import uuid
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager, AbstractUser
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from datetime import datetime, timedelta


# =============================================================================
# CUSTOM USER MANAGER
# =============================================================================

class CustomUserManager(UserManager):
    """Custom manager for Account_User model using email as the identifier."""
    
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "HOD")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


# =============================================================================
# 1. USER & AUTHENTICATION (CORE)
# =============================================================================

class Account_User(AbstractUser):
    """
    Custom User Model for Anna University CSE ERP.
    Uses email as the login identifier instead of username.
    """
    
    ROLE_CHOICES = [
        ('HOD', 'Head of Department'),
        ('FACULTY', 'Faculty'),
        ('STAFF', 'Non-Teaching Staff'),
        ('STUDENT', 'Student'),
        ('GUEST', 'Guest Faculty'),
    ]
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Remove username field
    email = models.EmailField(unique=True, verbose_name='Email Address')
    full_name = models.CharField(max_length=200, verbose_name='Full Name')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='STUDENT')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    fcm_token = models.TextField(default="", blank=True)  # Firebase notifications
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    
    objects = CustomUserManager()
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
    
    @property
    def first_name_display(self):
        return self.full_name.split()[0] if self.full_name else ""
    
    @property
    def last_name_display(self):
        parts = self.full_name.split()
        return parts[-1] if len(parts) > 1 else ""
    
    @property
    def is_hod(self):
        return self.role == 'HOD'
    
    @property
    def is_faculty(self):
        return self.role == 'FACULTY'
    
    @property
    def is_staff(self):
        return self.role == 'STAFF'
    
    @property
    def is_student(self):
        return self.role == 'STUDENT'
    
    @property
    def is_guest(self):
        return self.role == 'GUEST'


# =============================================================================
# 2. ACADEMIC STRUCTURE MODELS
# =============================================================================

class Regulation(models.Model):
    """Regulation/Curriculum version (e.g., 2017, 2021)"""
    
    year = models.IntegerField(unique=True, validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    name = models.CharField(max_length=100, blank=True)  # e.g., "R2021"
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-year']
    
    def __str__(self):
        return f"R{self.year}"


class Program(models.Model):
    """
    Academic Programs offered by the department.
    Examples:
    - B.E. Computer Science and Engineering (UG)
    - M.E. Computer Science and Engineering (PG)
    - M.E. Computer Science & Engg. Spl. in Operations Research (PG)
    - M.E. Computer Science & Engg. Spl. in Big Data Analytics (PG)
    - M.E. Software Engineering (PG)
    """
    
    PROGRAM_LEVEL_CHOICES = [
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
        ('PHD', 'Ph.D.'),
    ]
    
    DEGREE_CHOICES = [
        ('BE', 'B.E.'),
        ('BTECH', 'B.Tech.'),
        ('ME', 'M.E.'),
        ('MTECH', 'M.Tech.'),
        ('MS', 'M.S.'),
        ('PHD', 'Ph.D.'),
    ]
    
    code = models.CharField(max_length=20, unique=True, help_text="e.g., CSE, CSE-OR, CSE-BDA, SE")
    name = models.CharField(max_length=200, help_text="Full program name")
    degree = models.CharField(max_length=10, choices=DEGREE_CHOICES, default='BE')
    level = models.CharField(max_length=5, choices=PROGRAM_LEVEL_CHOICES, default='UG')
    specialization = models.CharField(max_length=200, blank=True, null=True, 
                                       help_text="e.g., Operations Research, Big Data Analytics")
    duration_years = models.IntegerField(default=4, validators=[MinValueValidator(1), MaxValueValidator(6)],
                                          help_text="Program duration in years")
    total_semesters = models.IntegerField(default=8, validators=[MinValueValidator(1), MaxValueValidator(12)])
    regulations = models.ManyToManyField(Regulation, related_name='programs', blank=True,
                                          help_text="Regulations under which this program is offered")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['level', 'name']
        verbose_name = 'Academic Program'
        verbose_name_plural = 'Academic Programs'
    
    def __str__(self):
        if self.specialization:
            return f"{self.get_degree_display()} {self.name} - {self.specialization}"
        return f"{self.get_degree_display()} {self.name}"
    
    @property
    def full_name(self):
        """Return full program name with degree"""
        if self.specialization:
            return f"{self.get_degree_display()} {self.name} Spl. in {self.specialization}"
        return f"{self.get_degree_display()} {self.name}"


class AcademicYear(models.Model):
    """Academic Year Management"""
    
    year = models.CharField(max_length=10, unique=True)  # e.g., "2025-26"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Academic Year'
        verbose_name_plural = 'Academic Years'
    
    def __str__(self):
        return self.year
    
    def save(self, *args, **kwargs):
        # Ensure only one academic year is marked as current
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Semester(models.Model):
    """Semester Management"""
    
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]
    TYPE_CHOICES = [
        ('ODD', 'Odd Semester'),
        ('EVEN', 'Even Semester'),
    ]
    
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='semesters')
    semester_number = models.IntegerField(choices=SEMESTER_CHOICES)
    semester_type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('academic_year', 'semester_number')
        ordering = ['-academic_year', 'semester_number']
    
    @property
    def semester_name(self):
        """Returns formatted semester name"""
        return f"Semester {self.semester_number}"
    
    def __str__(self):
        return f"{self.academic_year} - Sem {self.semester_number}"


# =============================================================================
# 3. ROLE-SPECIFIC PROFILES
# =============================================================================

class Faculty_Profile(models.Model):
    """Profile for Faculty members including Guest Faculty"""
    
    DESIGNATION_CHOICES = [
        ('AP', 'Assistant Professor'),
        ('ASP', 'Associate Professor'),
        ('PROF', 'Professor'),
        ('HOD', 'Head of Department'),
    ]
    
    user = models.OneToOneField(Account_User, on_delete=models.CASCADE, related_name='faculty_profile')
    staff_id = models.CharField(max_length=20, unique=True, verbose_name='Staff ID')
    designation = models.CharField(max_length=5, choices=DESIGNATION_CHOICES, default='AP')
    is_external = models.BooleanField(default=False, verbose_name='External/Guest Faculty',
                                       help_text='Mark True for Naan Mudhalvan/SDC/Guest staff')
    specialization = models.CharField(max_length=200, blank=True, null=True)
    qualification = models.CharField(max_length=200, blank=True, null=True)  # e.g., "Ph.D., M.Tech"
    experience_years = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    date_of_joining = models.DateField(null=True, blank=True)
    contract_expiry = models.DateField(null=True, blank=True, 
                                        help_text='For Guest faculty access control')
    cabin_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Faculty Profile'
        verbose_name_plural = 'Faculty Profiles'
    
    def __str__(self):
        external = " (Guest)" if self.is_external else ""
        return f"{self.user.full_name} - {self.get_designation_display()}{external}"
    
    @property
    def is_contract_expired(self):
        if self.contract_expiry:
            return self.contract_expiry < datetime.now().date()
        return False


class NonTeachingStaff_Profile(models.Model):
    """Profile for Non-Teaching Staff (Lab Assistants, Office Staff)"""
    
    STAFF_TYPE_CHOICES = [
        ('LAB_ASST', 'Lab Assistant'),
        ('LAB_TECH', 'Lab Technician'),
        ('OFFICE', 'Office Staff'),
        ('ADMIN', 'Administrative Staff'),
        ('OTHER', 'Other'),
    ]
    
    user = models.OneToOneField(Account_User, on_delete=models.CASCADE, related_name='nonteaching_profile')
    staff_id = models.CharField(max_length=20, unique=True, verbose_name='Staff ID')
    staff_type = models.CharField(max_length=10, choices=STAFF_TYPE_CHOICES, default='LAB_ASST')
    department = models.CharField(max_length=100, default='CSE')
    date_of_joining = models.DateField(null=True, blank=True)
    assigned_lab = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Non-Teaching Staff Profile'
        verbose_name_plural = 'Non-Teaching Staff Profiles'
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_staff_type_display()}"


class Student_Profile(models.Model):
    """Profile for Students"""
    
    BATCH_LABEL_CHOICES = [
        ('N', 'N Section'),
        ('P', 'P Section'),
        ('Q', 'Q Section'),
    ]
    
    BRANCH_CHOICES = [
        ('CSE', 'Computer Science and Engineering'),
        ('AIML', 'Artificial Intelligence and Machine Learning'),
        ('CSBS', 'Computer Science and Business Systems'),
    ]
    
    PROGRAM_TYPE_CHOICES = [
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
        ('PHD', 'Ph.D.'),
    ]
    
    register_validator = RegexValidator(
        regex=r'^\d{12}$',
        message='Register number must be exactly 12 digits'
    )
    
    user = models.OneToOneField(Account_User, on_delete=models.CASCADE, related_name='student_profile')
    register_no = models.CharField(max_length=12, unique=True, validators=[register_validator],
                                    verbose_name='Register Number')
    batch_label = models.CharField(max_length=1, choices=BATCH_LABEL_CHOICES, 
                                    verbose_name='Classroom Section')
    branch = models.CharField(max_length=10, choices=BRANCH_CHOICES, default='CSE')
    program_type = models.CharField(max_length=5, choices=PROGRAM_TYPE_CHOICES, default='UG')
    regulation = models.ForeignKey(Regulation, on_delete=models.SET_NULL, null=True, blank=True)
    current_sem = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(8)])
    admission_year = models.IntegerField(null=True, blank=True)
    advisor = models.ForeignKey(Faculty_Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='advisees', verbose_name='Faculty Advisor/Counselor')
    parent_name = models.CharField(max_length=200, blank=True, null=True)
    parent_phone = models.CharField(max_length=15, blank=True, null=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
    
    def __str__(self):
        return f"{self.register_no} - {self.user.full_name} ({self.branch})"


# =============================================================================
# 4. ACADEMIC & ATTENDANCE MANAGEMENT
# =============================================================================

class Course(models.Model):
    """Course/Subject Master Table"""
    
    COURSE_TYPE_CHOICES = [
        ('THEORY', 'Theory'),
        ('LAB', 'Laboratory'),
        ('PROJECT', 'Project'),
        ('SEMINAR', 'Seminar'),
    ]
    
    course_code = models.CharField(max_length=10, primary_key=True)  # e.g., "CS3401"
    title = models.CharField(max_length=200)
    regulation = models.ForeignKey(Regulation, on_delete=models.CASCADE, related_name='courses')
    course_type = models.CharField(max_length=10, choices=COURSE_TYPE_CHOICES, default='THEORY')
    is_lab = models.BooleanField(default=False)
    credits = models.IntegerField(default=3, validators=[MinValueValidator(0), MaxValueValidator(10)])
    lecture_hours = models.IntegerField(default=3, validators=[MinValueValidator(0)])
    tutorial_hours = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    practical_hours = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    semester = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(8)])
    branch = models.CharField(max_length=10, choices=Student_Profile.BRANCH_CHOICES, default='CSE')
    syllabus_file = models.FileField(upload_to='syllabus/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['semester', 'course_code']
    
    def __str__(self):
        return f"{self.course_code} - {self.title}"


class Course_Assignment(models.Model):
    """
    Links Course to Faculty for a specific batch and semester.
    This is the key table for academic operations.
    """
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    faculty = models.ForeignKey(Faculty_Profile, on_delete=models.CASCADE, related_name='course_assignments')
    batch_label = models.CharField(max_length=1, choices=Student_Profile.BATCH_LABEL_CHOICES)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('course', 'batch_label', 'academic_year', 'semester')
        verbose_name = 'Course Assignment'
        verbose_name_plural = 'Course Assignments'
        ordering = ['-academic_year', 'course']
    
    def __str__(self):
        return f"{self.course.course_code} - {self.faculty.user.full_name} ({self.batch_label})"


class Attendance(models.Model):
    """Individual Attendance Record"""
    
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('OD', 'On Duty'),
        ('LEAVE', 'On Leave'),
    ]
    
    student = models.ForeignKey(Student_Profile, on_delete=models.CASCADE, related_name='attendances')
    assignment = models.ForeignKey(Course_Assignment, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    period = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PRESENT')
    marked_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, 
                                   related_name='marked_attendances')
    remarks = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'assignment', 'date', 'period')
        ordering = ['-date', 'period']
    
    def __str__(self):
        return f"{self.student.register_no} - {self.assignment.course.course_code} - {self.date} - P{self.period}"


# =============================================================================
# 5. RESEARCH & ACHIEVEMENT (NIRF/RANKING DATA)
# =============================================================================

class Publication(models.Model):
    """Faculty Publication Records for NIRF and Rankings"""
    
    PUB_TYPE_CHOICES = [
        ('JOURNAL', 'Journal Article'),
        ('CONFERENCE', 'Conference Paper'),
        ('PATENT', 'Patent'),
        ('BOOK', 'Book'),
        ('CHAPTER', 'Book Chapter'),
    ]
    
    INDEXING_CHOICES = [
        ('SCOPUS', 'Scopus'),
        ('WOS', 'Web of Science'),
        ('UGC_CARE', 'UGC CARE'),
        ('SCI', 'SCI'),
        ('SCIE', 'SCIE'),
        ('OTHER', 'Other'),
    ]
    
    faculty = models.ForeignKey(Faculty_Profile, on_delete=models.CASCADE, related_name='publications')
    title = models.CharField(max_length=500)
    journal_name = models.CharField(max_length=300)
    pub_type = models.CharField(max_length=15, choices=PUB_TYPE_CHOICES, default='JOURNAL')
    doi = models.CharField(max_length=200, unique=True, blank=True, null=True, verbose_name='DOI')
    indexing = models.CharField(max_length=15, choices=INDEXING_CHOICES, default='OTHER')
    year = models.IntegerField(validators=[MinValueValidator(1990), MaxValueValidator(2100)])
    month = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(12)])
    authors = models.TextField(help_text='Comma-separated list of all authors')
    impact_factor = models.DecimalField(max_digits=5, decimal_places=3, blank=True, null=True)
    citation_count = models.IntegerField(default=0)
    proof_file = models.FileField(upload_to='publications/', blank=True, null=True)
    is_verified = models.BooleanField(default=False, help_text='Verified by HOD')
    verified_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='verified_publications')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.title[:50]}... ({self.year})"


class Student_Achievement(models.Model):
    """Student Achievement Records"""
    
    AWARD_CATEGORY_CHOICES = [
        ('GOLD', 'Gold'),
        ('SILVER', 'Silver'),
        ('BRONZE', 'Bronze'),
        ('WINNER', 'Winner'),
        ('RUNNER_UP', 'Runner Up'),
        ('PARTICIPATION', 'Participation'),
        ('MERIT', 'Merit'),
    ]
    
    EVENT_TYPE_CHOICES = [
        ('HACKATHON', 'Hackathon'),
        ('CODING', 'Coding Competition'),
        ('PAPER', 'Paper Presentation'),
        ('PROJECT', 'Project Competition'),
        ('SPORTS', 'Sports'),
        ('CULTURAL', 'Cultural'),
        ('WORKSHOP', 'Workshop'),
        ('INTERNSHIP', 'Internship'),
        ('PLACEMENT', 'Placement'),
        ('OTHER', 'Other'),
    ]
    
    student = models.ForeignKey(Student_Profile, on_delete=models.CASCADE, related_name='achievements')
    event_name = models.CharField(max_length=300)
    event_type = models.CharField(max_length=15, choices=EVENT_TYPE_CHOICES, default='OTHER')
    award_category = models.CharField(max_length=15, choices=AWARD_CATEGORY_CHOICES)
    organizing_body = models.CharField(max_length=200, blank=True, null=True)
    event_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    proof_file = models.FileField(upload_to='achievements/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-event_date']
        verbose_name = 'Student Achievement'
        verbose_name_plural = 'Student Achievements'
    
    def __str__(self):
        return f"{self.student.register_no} - {self.event_name} ({self.get_award_category_display()})"


# =============================================================================
# 6. LAB SUPPORT SYSTEM
# =============================================================================

class Lab_Issue_Log(models.Model):
    """Lab Equipment Issue Tracking"""
    
    LAB_CHOICES = [
        ('CASE_TOOLS', 'CASE Tools Lab'),
        ('PROGRAMMING', 'Programming Lab'),
        ('NETWORKS', 'Networks Lab'),
        ('DBMS', 'DBMS Lab'),
        ('OS', 'Operating Systems Lab'),
        ('WEB', 'Web Technology Lab'),
        ('AI_ML', 'AI/ML Lab'),
        ('IOT', 'IoT Lab'),
        ('PROJECT', 'Project Lab'),
        ('RESEARCH', 'Research Lab'),
    ]
    
    ISSUE_CATEGORY_CHOICES = [
        ('MONITOR', 'Monitor Issue'),
        ('KEYBOARD', 'Keyboard Issue'),
        ('MOUSE', 'Mouse Issue'),
        ('CPU', 'CPU/System Issue'),
        ('SOFTWARE', 'Software Issue'),
        ('NETWORK', 'Network Issue'),
        ('PRINTER', 'Printer Issue'),
        ('PROJECTOR', 'Projector Issue'),
        ('AC', 'AC Issue'),
        ('FURNITURE', 'Furniture Issue'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('ESCALATED', 'Escalated'),
        ('CLOSED', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    lab_name = models.CharField(max_length=20, choices=LAB_CHOICES)
    place_code = models.CharField(max_length=10, help_text='Physical desk/system location (e.g., D23)')
    reported_by = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='reported_issues')
    issue_category = models.CharField(max_length=15, choices=ISSUE_CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    assigned_to = models.ForeignKey(NonTeachingStaff_Profile, on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='assigned_issues')
    resolution_notes = models.TextField(blank=True, null=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-reported_at']
        verbose_name = 'Lab Issue Log'
        verbose_name_plural = 'Lab Issue Logs'
    
    def __str__(self):
        return f"{self.get_lab_name_display()} - {self.place_code} - {self.get_issue_category_display()}"


# =============================================================================
# 7. LEAVE MANAGEMENT
# =============================================================================

class LeaveRequest(models.Model):
    """Unified Leave Request for all user types"""
    
    LEAVE_TYPE_CHOICES = [
        ('CASUAL', 'Casual Leave'),
        ('MEDICAL', 'Medical Leave'),
        ('OD', 'On Duty'),
        ('VACATION', 'Vacation'),
        ('MATERNITY', 'Maternity Leave'),
        ('PATERNITY', 'Paternity Leave'),
        ('EMERGENCY', 'Emergency Leave'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=15, choices=LEAVE_TYPE_CHOICES, default='CASUAL')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    supporting_document = models.FileField(upload_to='leave_documents/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='approved_leaves')
    admin_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1


# =============================================================================
# 8. FEEDBACK SYSTEM
# =============================================================================

class Feedback(models.Model):
    """Unified Feedback System"""
    
    FEEDBACK_TYPE_CHOICES = [
        ('GENERAL', 'General Feedback'),
        ('COURSE', 'Course Feedback'),
        ('INFRASTRUCTURE', 'Infrastructure'),
        ('FACULTY', 'Faculty Feedback'),
        ('SUGGESTION', 'Suggestion'),
        ('COMPLAINT', 'Complaint'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('RESOLVED', 'Resolved'),
    ]
    
    user = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='feedbacks')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES, default='GENERAL')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    related_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    reply = models.TextField(blank=True, null=True)
    replied_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='feedback_replies')
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'
    
    def __str__(self):
        return f"{self.get_feedback_type_display()} - {self.subject[:50]}"


# =============================================================================
# 9. EVENTS MANAGEMENT
# =============================================================================

class Event(models.Model):
    """Department Events and Activities"""
    
    EVENT_TYPE_CHOICES = [
        ('WORKSHOP', 'Workshop'),
        ('SEMINAR', 'Seminar'),
        ('WEBINAR', 'Webinar'),
        ('HACKATHON', 'Hackathon'),
        ('CULTURAL', 'Cultural Event'),
        ('SPORTS', 'Sports Event'),
        ('PLACEMENT', 'Placement Drive'),
        ('GUEST_LECTURE', 'Guest Lecture'),
        ('FDP', 'Faculty Development Program'),
        ('CONFERENCE', 'Conference'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('UPCOMING', 'Upcoming'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=300)
    event_type = models.CharField(max_length=15, choices=EVENT_TYPE_CHOICES, default='OTHER')
    description = models.TextField()
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    venue = models.CharField(max_length=300)
    is_online = models.BooleanField(default=False)
    online_link = models.URLField(blank=True, null=True)
    max_participants = models.IntegerField(default=0, help_text='0 for unlimited')
    registration_deadline = models.DateTimeField(null=True, blank=True)
    coordinator = models.ForeignKey(Faculty_Profile, on_delete=models.SET_NULL, null=True, 
                                     related_name='coordinated_events')
    poster = models.ImageField(upload_to='event_posters/', blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='UPCOMING')
    is_department_only = models.BooleanField(default=False, help_text='Only for CSE department')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_datetime']
    
    def __str__(self):
        return f"{self.title} ({self.start_datetime.strftime('%d %b %Y')})"
    
    @property
    def registration_count(self):
        return self.registrations.count()
    
    @property
    def is_registration_open(self):
        if self.registration_deadline:
            return datetime.now() < self.registration_deadline
        return self.status == 'UPCOMING'


class EventRegistration(models.Model):
    """Event Registration Records"""
    
    ATTENDANCE_STATUS = [
        ('REGISTERED', 'Registered'),
        ('ATTENDED', 'Attended'),
        ('NO_SHOW', 'No Show'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='event_registrations')
    attendance_status = models.CharField(max_length=15, choices=ATTENDANCE_STATUS, default='REGISTERED')
    registration_time = models.DateTimeField(auto_now_add=True)
    check_in_time = models.DateTimeField(null=True, blank=True)
    certificate_issued = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('event', 'user')
        ordering = ['-registration_time']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.event.title}"


# =============================================================================
# 10. NOTIFICATIONS
# =============================================================================

class Notification(models.Model):
    """Unified Notification System"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('URGENT', 'Urgent'),
        ('REMINDER', 'Reminder'),
        ('ANNOUNCEMENT', 'Announcement'),
    ]
    
    recipient = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='sent_notifications')
    notification_type = models.CharField(max_length=15, choices=NOTIFICATION_TYPE_CHOICES, default='INFO')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    link = models.CharField(max_length=500, blank=True, null=True)  # Optional link to related content
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.full_name}"


# =============================================================================
# 11. ANNOUNCEMENT SYSTEM
# =============================================================================

class Announcement(models.Model):
    """Department-wide Announcements"""
    
    AUDIENCE_CHOICES = [
        ('ALL', 'All Users'),
        ('FACULTY', 'Faculty Only'),
        ('STUDENTS', 'Students Only'),
        ('STAFF', 'Staff Only'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    title = models.CharField(max_length=300)
    content = models.TextField()
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='ALL')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    posted_by = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='announcements')
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
    
    def __str__(self):
        return self.title


# =============================================================================
# 11. QUESTION PAPER MANAGEMENT
# =============================================================================

class QuestionPaperAssignment(models.Model):
    """Question Paper Setting Assignment by HOD to Faculty"""
    
    EXAM_TYPE_CHOICES = [
        ('CAT1', 'CAT 1'),
        ('CAT2', 'CAT 2'),
        ('ENDSEM', 'End Semester'),
        ('REEXAM', 'Re-Examination'),
        ('ARREAR', 'Arrear Exam'),
        ('MODEL', 'Model Exam'),
    ]
    
    STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('REVISION_REQUIRED', 'Revision Required'),
    ]
    
    # Assignment details
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='qp_assignments')
    assigned_faculty = models.ForeignKey(Faculty_Profile, on_delete=models.CASCADE, 
                                          related_name='qp_assignments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    regulation = models.ForeignKey(Regulation, on_delete=models.CASCADE, null=True, blank=True)
    
    # Timeline
    assigned_date = models.DateField(auto_now_add=True)
    deadline = models.DateField()
    
    # Instructions and guidelines
    max_marks = models.IntegerField(default=100)
    duration_hours = models.DecimalField(max_digits=3, decimal_places=1, default=3.0)
    instructions = models.TextField(blank=True, null=True, 
                                     help_text='Special instructions for question paper preparation')
    syllabus_units = models.CharField(max_length=50, blank=True, null=True,
                                       help_text='Units to cover, e.g., "1,2,3,4,5" or "All"')
    
    # Question paper submission
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED')
    question_paper = models.FileField(upload_to='question_papers/', blank=True, null=True)
    answer_key = models.FileField(upload_to='answer_keys/', blank=True, null=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    faculty_remarks = models.TextField(blank=True, null=True)
    
    # Review details
    reviewed_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reviewed_qp_assignments')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True, null=True)
    
    # Metadata
    assigned_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True,
                                     related_name='assigned_qp_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Question Paper Assignment'
        verbose_name_plural = 'Question Paper Assignments'
        unique_together = ('course', 'academic_year', 'semester', 'exam_type', 'regulation')
    
    def __str__(self):
        return f"{self.course.course_code} - {self.get_exam_type_display()} ({self.academic_year})"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.deadline < timezone.now().date() and self.status not in ['SUBMITTED', 'APPROVED']
    
    @property
    def days_remaining(self):
        from django.utils import timezone
        delta = self.deadline - timezone.now().date()
        return delta.days


# =============================================================================
# TIMETABLE MANAGEMENT
# =============================================================================

class TimeSlot(models.Model):
    """Defines time slots for timetable (8 periods per day)"""
    
    slot_number = models.IntegerField(unique=True, validators=[MinValueValidator(1), MaxValueValidator(8)])
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False, help_text="Mark True for lunch break slot")
    
    class Meta:
        ordering = ['slot_number']
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
    
    def __str__(self):
        return f"Period {self.slot_number}: {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


class Timetable(models.Model):
    """
    Master timetable for a specific Academic Year + Semester + Year + Batch combination.
    """
    
    YEAR_CHOICES = [
        (1, '1st Year'),
        (2, '2nd Year'),
        (3, '3rd Year'),
        (4, '4th Year'),
    ]
    
    BATCH_CHOICES = [
        ('N', 'N Batch'),
        ('P', 'P Batch'),
        ('Q', 'Q Batch'),
    ]
    
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='timetables')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='timetables')
    year = models.IntegerField(choices=YEAR_CHOICES)
    batch = models.CharField(max_length=1, choices=BATCH_CHOICES)
    regulation = models.ForeignKey(Regulation, on_delete=models.SET_NULL, null=True, blank=True)
    effective_from = models.DateField(help_text="Date from which this timetable is effective")
    created_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, 
                                    related_name='created_timetables')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('academic_year', 'semester', 'year', 'batch')
        ordering = ['-academic_year', 'year', 'batch']
        verbose_name = 'Timetable'
        verbose_name_plural = 'Timetables'
    
    def __str__(self):
        return f"{self.academic_year} - Sem {self.semester.semester_number} - Year {self.year} - Batch {self.batch}"


class TimetableEntry(models.Model):
    """Individual entry in a timetable (one slot for one day)"""
    
    DAY_CHOICES = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
    ]
    
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    faculty = models.ForeignKey(Faculty_Profile, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='timetable_entries')
    is_lab = models.BooleanField(default=False, help_text="Mark if this is a lab session spanning multiple slots")
    lab_end_slot = models.ForeignKey(TimeSlot, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='lab_end_entries')
    special_note = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        unique_together = ('timetable', 'day', 'time_slot')
        ordering = ['day', 'time_slot']
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'
    
    def __str__(self):
        course_info = self.course.course_code if self.course else self.special_note or 'Free'
        return f"{self.timetable} - {self.day} Period {self.time_slot.slot_number}: {course_info}"


# =============================================================================
# LOGIN OTP
# =============================================================================

class LoginOTP(models.Model):
    """OTP for first-time student login via college email"""
    
    user = models.ForeignKey(Account_User, on_delete=models.CASCADE, related_name='login_otps')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Login OTP'
        verbose_name_plural = 'Login OTPs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.user.email} - {'Used' if self.is_used else 'Active'}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired
    
    @classmethod
    def generate_otp(cls, user, validity_minutes=15):
        import random
        from django.utils import timezone
        
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        expires_at = timezone.now() + timedelta(minutes=validity_minutes)
        
        otp = cls.objects.create(user=user, otp=otp_code, expires_at=expires_at)
        return otp
    
    @classmethod
    def verify_otp(cls, user, otp_code):
        try:
            otp = cls.objects.filter(user=user, otp=otp_code, is_used=False).latest('created_at')
            if otp.is_valid:
                otp.is_used = True
                otp.save()
                return True
            return False
        except cls.DoesNotExist:
            return False


# =============================================================================
# SEMESTER PROMOTION
# =============================================================================

class SemesterPromotion(models.Model):
    """Tracks semester promotions for audit purposes."""
    
    PROMOTION_TYPE_CHOICES = [
        ('AUTO', 'Automatic'),
        ('MANUAL', 'Manual'),
        ('BULK', 'Bulk Promotion'),
    ]
    
    student = models.ForeignKey(Student_Profile, on_delete=models.CASCADE, related_name='promotions')
    from_semester = models.IntegerField()
    to_semester = models.IntegerField()
    from_year = models.IntegerField(help_text="Year of study before promotion")
    to_year = models.IntegerField(help_text="Year of study after promotion")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True)
    promotion_type = models.CharField(max_length=10, choices=PROMOTION_TYPE_CHOICES, default='AUTO')
    promoted_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True)
    promoted_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-promoted_at']
        verbose_name = 'Semester Promotion'
        verbose_name_plural = 'Semester Promotions'
    
    def __str__(self):
        return f"{self.student.register_no}: Sem {self.from_semester} → {self.to_semester}"


class PromotionSchedule(models.Model):
    """Stores scheduled promotions to avoid repeated processing."""
    
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='promotion_schedules')
    target_semester_number = models.IntegerField(help_text="Students currently in this sem will be promoted")
    scheduled_date = models.DateField(help_text="5 days before semester start")
    executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    students_promoted = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ('semester', 'target_semester_number')
        ordering = ['-scheduled_date']
    
    def __str__(self):
        status = "✓ Done" if self.executed else "⏳ Pending"
        return f"Promote Sem {self.target_semester_number} → {self.target_semester_number + 1} on {self.scheduled_date} [{status}]"


# =============================================================================
# PROMOTION HELPER FUNCTIONS
# =============================================================================

def check_and_promote_students(promoted_by=None, force=False):
    """Automatically promotes students 5 days before the next semester starts."""
    from django.utils import timezone
    from django.db import transaction
    
    today = timezone.now().date()
    results = {'total_promoted': 0, 'semesters_processed': [], 'errors': []}
    
    pending_schedules = PromotionSchedule.objects.filter(
        scheduled_date__lte=today, executed=False
    ).select_related('semester', 'semester__academic_year')
    
    with transaction.atomic():
        for schedule in pending_schedules:
            try:
                students_to_promote = Student_Profile.objects.filter(
                    current_sem=schedule.target_semester_number
                ).exclude(current_sem=8)
                
                promoted_count = 0
                for student in students_to_promote:
                    old_sem = student.current_sem
                    old_year = student.year_of_study
                    student.current_sem += 1
                    student.save()
                    
                    SemesterPromotion.objects.create(
                        student=student, from_semester=old_sem, to_semester=student.current_sem,
                        from_year=old_year, to_year=student.year_of_study,
                        academic_year=schedule.semester.academic_year,
                        promotion_type='AUTO' if promoted_by is None else 'MANUAL',
                        promoted_by=promoted_by,
                        remarks=f"Auto-promoted for {schedule.semester}"
                    )
                    promoted_count += 1
                
                schedule.executed = True
                schedule.executed_at = timezone.now()
                schedule.students_promoted = promoted_count
                schedule.save()
                
                results['total_promoted'] += promoted_count
                results['semesters_processed'].append({
                    'semester': str(schedule.semester), 'students': promoted_count
                })
            except Exception as e:
                results['errors'].append({'schedule': str(schedule), 'error': str(e)})
    
    return results


def create_promotion_schedules_for_semester(semester):
    """Creates promotion schedules when a new semester is added."""
    if not semester.start_date:
        return []
    
    scheduled_date = semester.start_date - timedelta(days=5)
    created_schedules = []
    target_from_sem = semester.semester_number - 1
    
    if target_from_sem > 0:
        schedule, created = PromotionSchedule.objects.get_or_create(
            semester=semester, target_semester_number=target_from_sem,
            defaults={'scheduled_date': scheduled_date}
        )
        if created:
            created_schedules.append(schedule)
    
    return created_schedules


def promote_students_manually(students, to_semester, promoted_by, academic_year=None):
    """Manually promote a list of students to a specific semester."""
    from django.db import transaction
    
    results = {'success': 0, 'errors': []}
    
    with transaction.atomic():
        for student in students:
            try:
                old_sem = student.current_sem
                old_year = student.year_of_study
                student.current_sem = to_semester
                student.save()
                
                SemesterPromotion.objects.create(
                    student=student, from_semester=old_sem, to_semester=to_semester,
                    from_year=old_year, to_year=student.year_of_study,
                    academic_year=academic_year, promotion_type='MANUAL',
                    promoted_by=promoted_by, remarks="Manual bulk promotion by HOD"
                )
                results['success'] += 1
            except Exception as e:
                results['errors'].append({'student': str(student), 'error': str(e)})
    
    return results


# =============================================================================
# SIGNALS FOR AUTO PROFILE CREATION
# =============================================================================

@receiver(post_save, sender=Account_User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create role-specific profile when user is created"""
    if created:
        if instance.role in ['FACULTY', 'HOD', 'GUEST']:
            Faculty_Profile.objects.get_or_create(
                user=instance,
                defaults={
                    'staff_id': f'TEMP_{instance.id.hex[:8].upper()}',
                    'is_external': (instance.role == 'GUEST'),
                    'designation': 'HOD' if instance.role == 'HOD' else 'AP'
                }
            )
        elif instance.role == 'STAFF':
            NonTeachingStaff_Profile.objects.get_or_create(
                user=instance,
                defaults={'staff_id': f'TEMP_{instance.id.hex[:8].upper()}'}
            )
        elif instance.role == 'STUDENT':
            Student_Profile.objects.get_or_create(
                user=instance,
                defaults={
                    'register_no': f'000000000000',  # Placeholder - must be updated
                    'batch_label': 'N'
                }
            )


# =============================================================================
# HELPER FUNCTION FOR ATTENDANCE PERCENTAGE
# =============================================================================

def get_student_attendance_percentage(student_profile, course_assignment=None):
    """Calculate attendance percentage for a student"""
    attendances = Attendance.objects.filter(student=student_profile)
    if course_assignment:
        attendances = attendances.filter(assignment=course_assignment)
    
    total = attendances.count()
    if total == 0:
        return 0.0
    
    present = attendances.filter(status__in=['PRESENT', 'OD']).count()
    return round((present / total) * 100, 2)


# =============================================================================
# EXAM SCHEDULE FOR QUESTION PAPERS
# =============================================================================

class ExamSchedule(models.Model):
    """
    Exam scheduling for question papers.
    HOD sets exam date/time, editable until exam ends.
    QP and answers are released to students after exam ends.
    """
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('ONGOING', 'Exam Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    structured_qp = models.OneToOneField(
        'StructuredQuestionPaper',
        on_delete=models.CASCADE,
        related_name='exam_schedule',
        help_text='The approved question paper for this exam'
    )
    
    # Exam timing
    exam_date = models.DateField(verbose_name='Exam Date')
    start_time = models.TimeField(verbose_name='Start Time')
    end_time = models.TimeField(verbose_name='End Time')
    duration_minutes = models.IntegerField(
        default=180,
        validators=[MinValueValidator(30), MaxValueValidator(300)],
        verbose_name='Duration (minutes)'
    )
    
    # Venue info
    venue = models.CharField(max_length=200, blank=True, null=True, verbose_name='Exam Venue')
    
    # Target audience - which students can see this
    batch_labels = models.CharField(
        max_length=20,
        default='N,P,Q',
        help_text='Comma-separated batch labels (e.g., "N,P,Q")'
    )
    semester = models.ForeignKey('Semester', on_delete=models.CASCADE, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Release control
    release_qp_after_exam = models.BooleanField(
        default=True,
        verbose_name='Release QP to students after exam',
        help_text='If checked, students can view QP after exam ends'
    )
    release_answers_after_exam = models.BooleanField(
        default=True,
        verbose_name='Release answers to students after exam',
        help_text='If checked, students can view answer key after exam ends'
    )
    
    # Metadata
    scheduled_by = models.ForeignKey(
        Account_User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='scheduled_exams'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'main_app_examschedule'
        verbose_name = 'Exam Schedule'
        verbose_name_plural = 'Exam Schedules'
        ordering = ['-exam_date', '-start_time']
    
    def __str__(self):
        return f"{self.structured_qp.course.course_code} - {self.exam_date} ({self.get_status_display()})"
    
    @property
    def exam_datetime(self):
        """Returns combined datetime for exam start"""
        from datetime import datetime as dt
        return dt.combine(self.exam_date, self.start_time)
    
    @property
    def exam_end_datetime(self):
        """Returns combined datetime for exam end"""
        from datetime import datetime as dt
        return dt.combine(self.exam_date, self.end_time)
    
    @property
    def is_exam_started(self):
        """Check if exam has started"""
        from django.utils import timezone
        now = timezone.now()
        exam_start = timezone.make_aware(self.exam_datetime) if timezone.is_naive(self.exam_datetime) else self.exam_datetime
        return now >= exam_start
    
    @property
    def is_exam_ended(self):
        """Check if exam has ended"""
        from django.utils import timezone
        now = timezone.now()
        exam_end = timezone.make_aware(self.exam_end_datetime) if timezone.is_naive(self.exam_end_datetime) else self.exam_end_datetime
        return now > exam_end
    
    @property
    def is_editable(self):
        """Schedule is editable until exam ends"""
        return not self.is_exam_ended
    
    @property
    def is_qp_released(self):
        """Check if QP should be visible to students"""
        return self.is_exam_ended and self.release_qp_after_exam and self.status == 'COMPLETED'
    
    @property
    def is_answers_released(self):
        """Check if answers should be visible to students"""
        return self.is_exam_ended and self.release_answers_after_exam and self.status == 'COMPLETED'
    
    def update_status(self):
        """Auto-update status based on time"""
        if self.status == 'CANCELLED':
            return
        
        if self.is_exam_ended:
            self.status = 'COMPLETED'
        elif self.is_exam_started:
            self.status = 'ONGOING'
        else:
            self.status = 'SCHEDULED'
        self.save(update_fields=['status'])
    
    def get_batch_labels_list(self):
        """Return batch labels as a list"""
        return [label.strip() for label in self.batch_labels.split(',') if label.strip()]


# =============================================================================
# STRUCTURED QUESTION PAPER (Anna University R2023 Format)
# =============================================================================

class StructuredQuestionPaper(models.Model):
    """Stores structured question paper metadata with CO descriptions"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted for Review'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    qp_assignment = models.OneToOneField(
        'QuestionPaperAssignment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='structured_qp',
        help_text='Optional link to question paper assignment'
    )
    
    faculty = models.ForeignKey(Faculty_Profile, on_delete=models.CASCADE, related_name='structured_qps')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    regulation = models.ForeignKey(Regulation, on_delete=models.CASCADE)
    
    exam_month_year = models.CharField(
        max_length=50,
        help_text='e.g., NOV/DEC 2023',
        verbose_name='Exam Month/Year'
    )
    
    # Course Outcome Descriptions
    co1_description = models.TextField(blank=True, verbose_name='CO1 Description')
    co2_description = models.TextField(blank=True, verbose_name='CO2 Description')
    co3_description = models.TextField(blank=True, verbose_name='CO3 Description')
    co4_description = models.TextField(blank=True, verbose_name='CO4 Description')
    co5_description = models.TextField(blank=True, verbose_name='CO5 Description')
    
    # Status & Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    hod_comments = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(Account_User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_qps')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Generated Document
    generated_document = models.FileField(
        upload_to='question_papers/structured/%Y/%m/',
        null=True,
        blank=True,
        help_text='Auto-generated .docx file in R2023 format'
    )
    
    # Uploaded Document (for direct uploads)
    uploaded_document = models.FileField(
        upload_to='question_papers/uploads/%Y/%m/',
        null=True,
        blank=True,
        help_text='Directly uploaded question paper document'
    )
    
    # Flag to indicate if this is an uploaded QP vs structured
    is_uploaded = models.BooleanField(default=False, help_text='True if QP was uploaded directly instead of created through structured form')
    
    class Meta:
        db_table = 'main_app_structuredquestionpaper'
        verbose_name = 'Structured Question Paper'
        verbose_name_plural = 'Structured Question Papers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.course.course_code} - {self.exam_month_year} ({self.get_status_display()})'
    
    def get_part_a_questions(self):
        """Get all Part A questions ordered by question number"""
        return self.questions.filter(part='A').order_by('question_number')
    
    def get_part_b_questions(self):
        """Get all Part B questions ordered by OR pair and option"""
        return self.questions.filter(part='B').order_by('or_pair_number', 'option_label')
    
    def get_part_c_questions(self):
        """Get all Part C questions"""
        return self.questions.filter(part='C').order_by('question_number')
    
    def calculate_marks_distribution(self):
        """Calculate marks distribution by CO and Bloom's level"""
        by_co = {'CO1': 0, 'CO2': 0, 'CO3': 0, 'CO4': 0, 'CO5': 0}
        by_bloom = {'L1': 0, 'L2': 0, 'L3': 0, 'L4': 0, 'L5': 0, 'L6': 0}
        total_marks = 0
        part_a_count = 0
        part_b_count = 0
        part_c_count = 0
        
        # Part A: 10 questions × 2 marks = 20 marks
        for q in self.get_part_a_questions():
            marks = 2
            if q.course_outcome:
                by_co[q.course_outcome] = by_co.get(q.course_outcome, 0) + marks
            if q.bloom_level:
                by_bloom[q.bloom_level] = by_bloom.get(q.bloom_level, 0) + marks
            total_marks += marks
            part_a_count += 1
        
        # Part B: 5 questions × 13 marks = 65 marks (only count one from each OR pair)
        counted_pairs = set()
        for q in self.get_part_b_questions():
            if q.or_pair_number and q.or_pair_number not in counted_pairs:
                marks = 13
                if q.course_outcome:
                    by_co[q.course_outcome] = by_co.get(q.course_outcome, 0) + marks
                if q.bloom_level:
                    by_bloom[q.bloom_level] = by_bloom.get(q.bloom_level, 0) + marks
                total_marks += marks
                counted_pairs.add(q.or_pair_number)
                part_b_count += 1
        
        # Part C: 1 question × 15 marks = 15 marks
        for q in self.get_part_c_questions():
            marks = 15
            if q.course_outcome:
                by_co[q.course_outcome] = by_co.get(q.course_outcome, 0) + marks
            if q.bloom_level:
                by_bloom[q.bloom_level] = by_bloom.get(q.bloom_level, 0) + marks
            total_marks += marks
            part_c_count += 1
        
        # Calculate Bloom's level totals and percentages
        l1_l2_total = by_bloom.get('L1', 0) + by_bloom.get('L2', 0)
        l3_l4_total = by_bloom.get('L3', 0) + by_bloom.get('L4', 0)
        l5_l6_total = by_bloom.get('L5', 0) + by_bloom.get('L6', 0)
        
        l1_l2_percentage = (l1_l2_total / total_marks * 100) if total_marks > 0 else 0
        l3_l4_percentage = (l3_l4_total / total_marks * 100) if total_marks > 0 else 0
        l5_l6_percentage = (l5_l6_total / total_marks * 100) if total_marks > 0 else 0
        
        # Calculate CO distribution
        co_distribution = {}
        for co, marks in by_co.items():
            co_distribution[co] = {
                'marks': marks,
                'percentage': (marks / total_marks * 100) if total_marks > 0 else 0
            }
        
        return {
            'by_co': by_co,
            'by_bloom': by_bloom,
            'total_marks': total_marks,
            'part_a_count': part_a_count,
            'part_b_count': part_b_count,
            'part_c_count': part_c_count,
            # Template-expected fields
            'l1_l2_total': l1_l2_total,
            'l3_l4_total': l3_l4_total,
            'l5_l6_total': l5_l6_total,
            'l1_l2_percentage': l1_l2_percentage,
            'l3_l4_percentage': l3_l4_percentage,
            'l5_l6_percentage': l5_l6_percentage,
            'co_distribution': co_distribution,
        }
    
    def validate_distribution(self):
        """Validate question paper meets R2023 requirements"""
        errors = []
        dist = self.calculate_marks_distribution()
        
        # Check total marks
        if dist['total_marks'] != 100:
            errors.append(f"Total marks should be 100, got {dist['total_marks']}")
        
        # Check Part A count
        if dist['part_a_count'] != 10:
            errors.append(f"Part A should have 10 questions, got {dist['part_a_count']}")
        
        # Check Part B count (5 OR pairs)
        if dist['part_b_count'] != 5:
            errors.append(f"Part B should have 5 question pairs, got {dist['part_b_count']}")
        
        # Check Part C count
        if dist['part_c_count'] != 1:
            errors.append(f"Part C should have 1 question, got {dist['part_c_count']}")
        
        return errors


class QPQuestion(models.Model):
    """Individual questions for structured question papers"""
    
    PART_CHOICES = [
        ('A', 'Part A - Short Answer (2 marks)'),
        ('B', 'Part B - Descriptive (13 marks)'),
        ('C', 'Part C - Problem Solving (15 marks)'),
    ]
    
    CO_CHOICES = [
        ('CO1', 'CO1'),
        ('CO2', 'CO2'),
        ('CO3', 'CO3'),
        ('CO4', 'CO4'),
        ('CO5', 'CO5'),
    ]
    
    BLOOM_CHOICES = [
        ('L1', 'L1 - Remember'),
        ('L2', 'L2 - Understand'),
        ('L3', 'L3 - Apply'),
        ('L4', 'L4 - Analyze'),
        ('L5', 'L5 - Evaluate'),
        ('L6', 'L6 - Create'),
    ]
    
    question_paper = models.ForeignKey(StructuredQuestionPaper, on_delete=models.CASCADE, related_name='questions')
    part = models.CharField(max_length=1, choices=PART_CHOICES)
    question_number = models.IntegerField(help_text='Question number (1-16)')
    
    # OR options (for Part B)
    is_or_option = models.BooleanField(default=False)
    or_pair_number = models.IntegerField(null=True, blank=True, help_text='For Part B: 11, 12, 13, 14, 15')
    option_label = models.CharField(max_length=5, blank=True, help_text='(a) or (b) for OR options')
    
    # Question text
    question_text = models.TextField(help_text='Main question text')
    
    # Answer for the question (selected by faculty from AI suggestions)
    answer = models.TextField(blank=True, help_text='Selected answer for answer key')
    
    # Subdivisions (max 2 for Part B)
    has_subdivisions = models.BooleanField(default=False)
    subdivision_1_text = models.TextField(blank=True)
    subdivision_1_marks = models.IntegerField(null=True, blank=True)
    subdivision_2_text = models.TextField(blank=True)
    subdivision_2_marks = models.IntegerField(null=True, blank=True)
    
    # Mapping
    course_outcome = models.CharField(max_length=5, choices=CO_CHOICES)
    bloom_level = models.CharField(max_length=5, choices=BLOOM_CHOICES)
    marks = models.IntegerField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'main_app_qpquestion'
        verbose_name = 'Question Paper Question'
        verbose_name_plural = 'Question Paper Questions'
        ordering = ['part', 'question_number', 'option_label']
    
    def __str__(self):
        return f'Q{self.question_number}{self.option_label} - {self.question_text[:50]}'
