"""
Anna University CSE Department ERP System
Django Forms for all models
"""

from django import forms
from django.forms.widgets import DateInput, TextInput, Select, Textarea
from django.core.exceptions import ValidationError

from .models import (
    Account_User, Regulation, AcademicYear, Semester, Program,
    Faculty_Profile, NonTeachingStaff_Profile, Student_Profile,
    Course, Course_Assignment, Attendance,
    Publication, Student_Achievement, Lab_Issue_Log,
    LeaveRequest, Feedback, Event, EventRegistration,
    Notification, Announcement, QuestionPaperAssignment,
    Timetable, TimetableEntry, TimeSlot,
    StructuredQuestionPaper, QPQuestion
)


# =============================================================================
# BASE FORM SETTINGS
# =============================================================================

class FormSettings(forms.ModelForm):
    """Base form class with Bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super(FormSettings, self).__init__(*args, **kwargs)
        for field in self.visible_fields():
            if isinstance(field.field.widget, forms.CheckboxInput):
                field.field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.field.widget, forms.Select):
                field.field.widget.attrs['class'] = 'form-control form-select'
            elif isinstance(field.field.widget, forms.Textarea):
                field.field.widget.attrs['class'] = 'form-control'
                field.field.widget.attrs['rows'] = 3
            else:
                field.field.widget.attrs['class'] = 'form-control'


# =============================================================================
# USER & AUTHENTICATION FORMS
# =============================================================================

class AccountUserForm(FormSettings):
    """Form for creating/editing Account_User"""
    
    email = forms.EmailField(required=True)
    full_name = forms.CharField(required=True, max_length=200)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = Account_User
        fields = ['email', 'full_name', 'role', 'gender', 'phone', 'profile_pic', 'address']
    
    def __init__(self, *args, **kwargs):
        super(AccountUserForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['password'].widget.attrs['placeholder'] = "Leave empty to keep current password"
            self.fields['confirm_password'].widget.attrs['placeholder'] = "Confirm new password"
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if self.instance.pk is None:
            if Account_User.objects.filter(email=email).exists():
                raise ValidationError("This email is already registered")
        else:
            existing = Account_User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("This email is already registered")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and password != confirm_password:
            raise ValidationError("Passwords do not match")
        return cleaned_data


class FacultyRegistrationForm(FormSettings):
    """Combined form for Faculty user + profile creation"""
    
    # User fields
    email = forms.EmailField(required=True)
    full_name = forms.CharField(required=True, max_length=200)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    gender = forms.ChoiceField(choices=Account_User.GENDER_CHOICES, required=False)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    profile_pic = forms.ImageField(required=False)
    
    # Profile fields
    staff_id = forms.CharField(max_length=20, required=True)
    designation = forms.ChoiceField(choices=Faculty_Profile.DESIGNATION_CHOICES)
    is_external = forms.BooleanField(required=False, label='Guest/External Faculty')
    specialization = forms.CharField(max_length=200, required=False)
    qualification = forms.CharField(max_length=200, required=False)
    experience_years = forms.IntegerField(min_value=0, required=False, initial=0)
    date_of_joining = forms.DateField(widget=DateInput(attrs={'type': 'date'}), required=False)
    contract_expiry = forms.DateField(widget=DateInput(attrs={'type': 'date'}), required=False)
    cabin_number = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = Faculty_Profile
        fields = ['staff_id', 'designation', 'is_external', 'specialization', 
                  'qualification', 'experience_years', 'date_of_joining', 
                  'contract_expiry', 'cabin_number']
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Account_User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered")
        return email
    
    def clean_staff_id(self):
        staff_id = self.cleaned_data['staff_id']
        if Faculty_Profile.objects.filter(staff_id=staff_id).exists():
            raise ValidationError("This Staff ID is already registered")
        return staff_id


class StudentRegistrationForm(FormSettings):
    """Combined form for Student user + profile creation
    Note: Password is not required here - students set their own password via OTP first-time login
    Fields match bulk upload CSV format for consistency.
    """
    
    # User fields (required)
    full_name = forms.CharField(required=True, max_length=200, label='Full Name')
    email = forms.EmailField(required=True, label='Personal Email', 
                            help_text='Student will use this email to login')
    gender = forms.ChoiceField(choices=Account_User.GENDER_CHOICES, required=True, label='Gender')
    
    # Profile fields (required)
    register_no = forms.CharField(max_length=10, required=True, label='Register Number',
                                  help_text='10-digit register number (e.g., 2023103543)')
    batch_label = forms.ChoiceField(choices=Student_Profile.BATCH_LABEL_CHOICES, label='Batch (Section)')
    branch = forms.ChoiceField(choices=Student_Profile.BRANCH_CHOICES, label='Branch')
    program_type = forms.ChoiceField(choices=Student_Profile.PROGRAM_TYPE_CHOICES, label='Program Type')
    admission_year = forms.IntegerField(min_value=2000, max_value=2100, required=True, label='Admission Year')
    current_sem = forms.IntegerField(min_value=1, max_value=8, initial=1, label='Current Semester')
    
    # Optional fields
    phone = forms.CharField(max_length=15, required=False, label='Phone Number')
    
    class Meta:
        model = Student_Profile
        fields = ['register_no', 'batch_label', 'branch', 'program_type',
                  'current_sem', 'admission_year']
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Account_User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered")
        return email
    
    def clean_register_no(self):
        register_no = self.cleaned_data['register_no']
        if not register_no.isdigit() or len(register_no) != 10:
            raise ValidationError("Register number must be exactly 10 digits")
        if Student_Profile.objects.filter(register_no=register_no).exists():
            raise ValidationError("This Register Number is already registered")
        return register_no


class NonTeachingStaffRegistrationForm(FormSettings):
    """Combined form for Non-Teaching Staff user + profile creation"""
    
    # User fields
    email = forms.EmailField(required=True)
    full_name = forms.CharField(required=True, max_length=200)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    gender = forms.ChoiceField(choices=Account_User.GENDER_CHOICES, required=False)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    profile_pic = forms.ImageField(required=False)
    
    # Profile fields
    staff_id = forms.CharField(max_length=20, required=True)
    staff_type = forms.ChoiceField(choices=NonTeachingStaff_Profile.STAFF_TYPE_CHOICES)
    department = forms.CharField(max_length=100, initial='CSE')
    date_of_joining = forms.DateField(widget=DateInput(attrs={'type': 'date'}), required=False)
    assigned_lab = forms.CharField(max_length=100, required=False)
    
    class Meta:
        model = NonTeachingStaff_Profile
        fields = ['staff_id', 'staff_type', 'department', 'date_of_joining', 'assigned_lab']
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Account_User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered")
        return email
    
    def clean_staff_id(self):
        staff_id = self.cleaned_data['staff_id']
        if NonTeachingStaff_Profile.objects.filter(staff_id=staff_id).exists():
            raise ValidationError("This Staff ID is already registered")
        return staff_id


# =============================================================================
# PROFILE EDIT FORMS
# =============================================================================

class FacultyProfileEditForm(FormSettings):
    """Form for editing Faculty profile"""
    
    class Meta:
        model = Faculty_Profile
        fields = ['designation', 'is_external', 'specialization', 'qualification',
                  'experience_years', 'date_of_joining', 'contract_expiry', 'cabin_number']
        widgets = {
            'date_of_joining': DateInput(attrs={'type': 'date'}),
            'contract_expiry': DateInput(attrs={'type': 'date'}),
        }


class StudentProfileEditForm(FormSettings):
    """Form for editing Student profile"""
    
    class Meta:
        model = Student_Profile
        fields = ['batch_label', 'branch', 'program_type', 'regulation', 'current_sem',
                  'advisor', 'parent_name', 'parent_phone', 'blood_group']


class NonTeachingStaffProfileEditForm(FormSettings):
    """Form for editing Non-Teaching Staff profile"""
    
    class Meta:
        model = NonTeachingStaff_Profile
        fields = ['staff_type', 'department', 'date_of_joining', 'assigned_lab']
        widgets = {
            'date_of_joining': DateInput(attrs={'type': 'date'}),
        }


# =============================================================================
# ACADEMIC STRUCTURE FORMS
# =============================================================================

class RegulationForm(FormSettings):
    """Form for Regulation"""
    
    class Meta:
        model = Regulation
        fields = ['year', 'name', 'description', 'is_active', 'effective_from']
        widgets = {
            'effective_from': DateInput(attrs={'type': 'date'}),
        }


class ProgramForm(FormSettings):
    """Form for Academic Programs"""
    
    class Meta:
        model = Program
        fields = ['code', 'name', 'degree', 'level', 'specialization', 
                  'duration_years', 'total_semesters', 'regulations', 'is_active']
        widgets = {
            'regulations': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['specialization'].required = False
        self.fields['regulations'].required = False


class AcademicYearForm(FormSettings):
    """Form for Academic Year"""
    
    class Meta:
        model = AcademicYear
        fields = ['year', 'start_date', 'end_date', 'is_current']
        widgets = {
            'start_date': DateInput(attrs={'type': 'date'}),
            'end_date': DateInput(attrs={'type': 'date'}),
        }


class SemesterForm(FormSettings):
    """Form for Semester"""
    
    class Meta:
        model = Semester
        fields = ['academic_year', 'semester_number', 'semester_type', 'start_date', 'end_date', 'is_current']
        widgets = {
            'start_date': DateInput(attrs={'type': 'date'}),
            'end_date': DateInput(attrs={'type': 'date'}),
        }


# =============================================================================
# COURSE & ASSIGNMENT FORMS
# =============================================================================

class CourseForm(FormSettings):
    """Form for Course"""
    
    class Meta:
        model = Course
        fields = ['course_code', 'title', 'regulation', 'course_type', 'is_lab',
                  'credits', 'lecture_hours', 'tutorial_hours', 'practical_hours',
                  'semester', 'branch', 'syllabus_file']


class CourseAssignmentForm(FormSettings):
    """Form for Course Assignment"""
    
    course = forms.ModelChoiceField(queryset=Course.objects.all(), empty_label="Select Course")
    faculty = forms.ModelChoiceField(queryset=Faculty_Profile.objects.all(), empty_label="Select Faculty")
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.all(), empty_label="Select Academic Year")
    semester = forms.ModelChoiceField(queryset=Semester.objects.all(), empty_label="Select Semester")
    
    class Meta:
        model = Course_Assignment
        fields = ['course', 'faculty', 'batch_label', 'academic_year', 'semester', 'is_active']


# =============================================================================
# ATTENDANCE FORMS
# =============================================================================

class AttendanceForm(FormSettings):
    """Form for marking attendance"""
    
    class Meta:
        model = Attendance
        fields = ['student', 'assignment', 'date', 'period', 'status', 'remarks']
        widgets = {
            'date': DateInput(attrs={'type': 'date'}),
        }


class BulkAttendanceForm(forms.Form):
    """Form for bulk attendance marking"""
    
    assignment = forms.ModelChoiceField(queryset=Course_Assignment.objects.filter(is_active=True))
    date = forms.DateField(widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    period = forms.IntegerField(min_value=1, max_value=8, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.NumberInput):
                field.widget.attrs['class'] = 'form-control'


# =============================================================================
# RESEARCH & ACHIEVEMENT FORMS
# =============================================================================

class PublicationForm(FormSettings):
    """Form for Faculty Publications"""
    
    class Meta:
        model = Publication
        fields = ['title', 'journal_name', 'pub_type', 'doi', 'indexing', 'year',
                  'month', 'authors', 'impact_factor', 'citation_count', 'proof_file']


class StudentAchievementForm(FormSettings):
    """Form for Student Achievements"""
    
    class Meta:
        model = Student_Achievement
        fields = ['event_name', 'event_type', 'award_category', 'organizing_body',
                  'event_date', 'description', 'proof_file']
        widgets = {
            'event_date': DateInput(attrs={'type': 'date'}),
        }


# =============================================================================
# LAB ISSUE FORMS
# =============================================================================

class LabIssueForm(FormSettings):
    """Form for reporting Lab Issues"""
    
    class Meta:
        model = Lab_Issue_Log
        fields = ['lab_name', 'place_code', 'issue_category', 'priority', 'description']


class LabIssueUpdateForm(FormSettings):
    """Form for updating Lab Issue status"""
    
    class Meta:
        model = Lab_Issue_Log
        fields = ['status', 'assigned_to', 'resolution_notes']


# =============================================================================
# LEAVE REQUEST FORMS
# =============================================================================

class LeaveRequestForm(FormSettings):
    """Form for Leave Requests"""
    
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason', 'supporting_document']
        widgets = {
            'start_date': DateInput(attrs={'type': 'date'}),
            'end_date': DateInput(attrs={'type': 'date'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("End date must be after start date")
        return cleaned_data


class LeaveApprovalForm(FormSettings):
    """Form for approving/rejecting leave requests"""
    
    class Meta:
        model = LeaveRequest
        fields = ['status', 'admin_remarks']


# =============================================================================
# FEEDBACK FORMS
# =============================================================================

class FeedbackForm(FormSettings):
    """Form for submitting Feedback"""
    
    class Meta:
        model = Feedback
        fields = ['feedback_type', 'subject', 'message', 'related_course', 'is_anonymous']


class FeedbackReplyForm(FormSettings):
    """Form for replying to Feedback"""
    
    class Meta:
        model = Feedback
        fields = ['status', 'reply']


# =============================================================================
# EVENT FORMS
# =============================================================================

class EventForm(FormSettings):
    """Form for Events"""
    
    class Meta:
        model = Event
        fields = ['title', 'event_type', 'description', 'start_datetime', 'end_datetime',
                  'venue', 'is_online', 'online_link', 'max_participants',
                  'registration_deadline', 'coordinator', 'poster', 'status', 'is_department_only']
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'registration_deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class EventRegistrationForm(FormSettings):
    """Form for Event Registration"""
    
    class Meta:
        model = EventRegistration
        fields = []


# =============================================================================
# NOTIFICATION & ANNOUNCEMENT FORMS
# =============================================================================

class NotificationForm(FormSettings):
    """Form for sending Notifications"""
    
    class Meta:
        model = Notification
        fields = ['recipient', 'notification_type', 'title', 'message', 'link']


class AnnouncementForm(FormSettings):
    """Form for Announcements"""
    
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'audience', 'priority', 'attachment', 
                  'is_pinned', 'is_active', 'expiry_date']
        widgets = {
            'expiry_date': DateInput(attrs={'type': 'date'}),
        }


# =============================================================================
# SEARCH & FILTER FORMS
# =============================================================================

class StudentSearchForm(forms.Form):
    """Form for searching students"""
    
    register_no = forms.CharField(max_length=12, required=False)
    name = forms.CharField(max_length=200, required=False)
    branch = forms.ChoiceField(choices=[('', 'All')] + list(Student_Profile.BRANCH_CHOICES), required=False)
    batch_label = forms.ChoiceField(choices=[('', 'All')] + list(Student_Profile.BATCH_LABEL_CHOICES), required=False)
    current_sem = forms.IntegerField(min_value=1, max_value=8, required=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class AttendanceFilterForm(forms.Form):
    """Form for filtering attendance reports"""
    
    course_assignment = forms.ModelChoiceField(
        queryset=Course_Assignment.objects.filter(is_active=True),
        required=False,
        empty_label="All Courses"
    )
    start_date = forms.DateField(widget=DateInput(attrs={'type': 'date'}), required=False)
    end_date = forms.DateField(widget=DateInput(attrs={'type': 'date'}), required=False)
    batch_label = forms.ChoiceField(
        choices=[('', 'All')] + list(Student_Profile.BATCH_LABEL_CHOICES),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


# =============================================================================
# QUESTION PAPER ASSIGNMENT FORMS
# =============================================================================

class QuestionPaperAssignmentForm(FormSettings):
    """Form for HOD to assign question paper setting task"""
    
    class Meta:
        model = QuestionPaperAssignment
        fields = ['course', 'assigned_faculty', 'academic_year', 'semester', 
                  'exam_type', 'regulation', 'deadline', 'instructions']
        widgets = {
            'deadline': DateInput(attrs={'type': 'date'}),
            'instructions': Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter faculty who are actively teaching courses
        self.fields['assigned_faculty'].queryset = Faculty_Profile.objects.filter(
            user__is_active=True
        ).select_related('user')
        self.fields['course'].queryset = Course.objects.all().order_by('course_code')
        self.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-start_date')
        self.fields['semester'].queryset = Semester.objects.all().order_by('-academic_year', 'semester_number')
        # Pull regulations from database
        self.fields['regulation'].queryset = Regulation.objects.filter(is_active=True).order_by('-year')
        self.fields['regulation'].required = False


class QuestionPaperSubmissionForm(FormSettings):
    """Form for Faculty to submit question paper"""
    
    class Meta:
        model = QuestionPaperAssignment
        fields = ['question_paper', 'answer_key', 'faculty_remarks']
        widgets = {
            'faculty_remarks': Textarea(attrs={'rows': 3, 'placeholder': 'Any remarks or notes about the question paper'}),
        }
    
    def clean_question_paper(self):
        file = self.cleaned_data.get('question_paper')
        if file:
            # Check file extension
            allowed_extensions = ['.doc', '.docx', '.pdf']
            ext = '.' + file.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise ValidationError('Only Word documents (.doc, .docx) and PDF files are allowed.')
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('File size must be under 10MB.')
        return file


class QuestionPaperReviewForm(FormSettings):
    """Form for HOD to review submitted question paper"""
    
    class Meta:
        model = QuestionPaperAssignment
        fields = ['status', 'review_comments']
        widgets = {
            'review_comments': Textarea(attrs={'rows': 4, 'placeholder': 'Enter review comments or feedback'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show review-related status choices
        self.fields['status'].choices = [
            ('UNDER_REVIEW', 'Under Review'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
            ('REVISION_REQUIRED', 'Revision Required'),
        ]


# =============================================================================
# TIMETABLE FORMS
# =============================================================================

class TimetableForm(FormSettings):
    """Form for creating/editing a Timetable"""
    
    class Meta:
        model = Timetable
        fields = ['academic_year', 'semester', 'year', 'batch', 'regulation', 'effective_from']
        widgets = {
            'effective_from': DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-start_date')
        self.fields['semester'].queryset = Semester.objects.all().order_by('-academic_year', 'semester_number')
        self.fields['regulation'].queryset = Regulation.objects.filter(is_active=True).order_by('-year')
        self.fields['regulation'].required = False


class TimetableEntryForm(FormSettings):
    """Form for creating/editing a single Timetable Entry"""
    
    class Meta:
        model = TimetableEntry
        fields = ['day', 'time_slot', 'course', 'faculty', 'is_lab', 'lab_end_slot', 'special_note']
    
    def __init__(self, *args, timetable=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(is_break=False).order_by('slot_number')
        self.fields['lab_end_slot'].queryset = TimeSlot.objects.filter(is_break=False).order_by('slot_number')
        self.fields['lab_end_slot'].required = False
        
        # Filter courses by semester if timetable is provided
        if timetable:
            semester_num = timetable.semester.semester_number
            # Get the corresponding course semester based on year
            # Year 1: Sem 1,2 | Year 2: Sem 3,4 | Year 3: Sem 5,6 | Year 4: Sem 7,8
            course_semesters = []
            if timetable.year == 1:
                course_semesters = [1, 2]
            elif timetable.year == 2:
                course_semesters = [3, 4]
            elif timetable.year == 3:
                course_semesters = [5, 6]
            elif timetable.year == 4:
                course_semesters = [7, 8]
            
            self.fields['course'].queryset = Course.objects.filter(
                semester__in=course_semesters
            ).order_by('course_code')
        else:
            self.fields['course'].queryset = Course.objects.all().order_by('course_code')
        
        # All active faculty
        self.fields['faculty'].queryset = Faculty_Profile.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('user__full_name')
        
        # Make course not required (for free periods or special notes)
        self.fields['course'].required = False
        self.fields['faculty'].required = False


class TimeSlotForm(FormSettings):
    """Form for creating/editing Time Slots"""
    
    class Meta:
        model = TimeSlot
        fields = ['slot_number', 'start_time', 'end_time', 'is_break']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


# =============================================================================

# Forms restored - need multi-field implementation

# =============================================================================
# STRUCTURED QUESTION PAPER FORMS (Multi-field version)
# =============================================================================

from django.forms import inlineformset_factory

class StructuredQuestionPaperForm(FormSettings):
    class Meta:
        model = StructuredQuestionPaper
        fields = ["course", "academic_year", "semester", "regulation", "exam_month_year", 
                  "co1_description", "co2_description", "co3_description", "co4_description", "co5_description"]
        widgets = {
            "exam_month_year": TextInput(attrs={"placeholder": "e.g., NOV/DEC 2023"}),
            "co1_description": forms.Textarea(attrs={"rows": 2}),
            "co2_description": forms.Textarea(attrs={"rows": 2}),
            "co3_description": forms.Textarea(attrs={"rows": 2}),
            "co4_description": forms.Textarea(attrs={"rows": 2}),
            "co5_description": forms.Textarea(attrs={"rows": 2}),
        }

class QPQuestionForm(forms.ModelForm):
    class Meta:
        model = QPQuestion
        fields = ["question_text", "has_subdivisions", "subdivision_1_text", "subdivision_1_marks",
                  "subdivision_2_text", "subdivision_2_marks", "course_outcome", "bloom_level"]

PartAFormSet = inlineformset_factory(StructuredQuestionPaper, QPQuestion, form=QPQuestionForm,
    extra=10, max_num=10, can_delete=False, fields=["question_text", "course_outcome", "bloom_level"])
PartBFormSet = inlineformset_factory(StructuredQuestionPaper, QPQuestion, form=QPQuestionForm,
    extra=10, max_num=10, can_delete=False, fields=["question_text", "has_subdivisions", "subdivision_1_text",
    "subdivision_1_marks", "subdivision_2_text", "subdivision_2_marks", "course_outcome", "bloom_level"])
PartCFormSet = inlineformset_factory(StructuredQuestionPaper, QPQuestion, form=QPQuestionForm,
    extra=1, max_num=1, can_delete=False, fields=["question_text", "course_outcome", "bloom_level"])
