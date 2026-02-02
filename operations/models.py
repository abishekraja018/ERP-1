"""
Operations Models
LeaveRequest, Lab_Issue_Log, QuestionPaperAssignment, SemesterPromotion, PromotionSchedule
"""

from datetime import timedelta
from django.db import models
from django.utils import timezone
from core.models import Account_User
from academics.models import AcademicYear, Semester, Course, Regulation
from users.models import Faculty_Profile, NonTeachingStaff_Profile, Student_Profile


# =============================================================================
# LEAVE REQUEST
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
        db_table = 'main_app_leaverequest'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1


# =============================================================================
# LAB ISSUE LOG
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
        db_table = 'main_app_lab_issue_log'
        ordering = ['-reported_at']
        verbose_name = 'Lab Issue Log'
        verbose_name_plural = 'Lab Issue Logs'
    
    def __str__(self):
        return f"{self.get_lab_name_display()} - {self.place_code} - {self.get_issue_category_display()}"


# =============================================================================
# QUESTION PAPER ASSIGNMENT
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
        db_table = 'main_app_questionpaperassignment'
        ordering = ['-created_at']
        verbose_name = 'Question Paper Assignment'
        verbose_name_plural = 'Question Paper Assignments'
        unique_together = ('course', 'academic_year', 'semester', 'exam_type', 'regulation')
    
    def __str__(self):
        return f"{self.course.course_code} - {self.get_exam_type_display()} ({self.academic_year})"
    
    @property
    def is_overdue(self):
        return self.deadline < timezone.now().date() and self.status not in ['SUBMITTED', 'APPROVED']
    
    @property
    def days_remaining(self):
        delta = self.deadline - timezone.now().date()
        return delta.days


# =============================================================================
# SEMESTER PROMOTION
# =============================================================================

class SemesterPromotion(models.Model):
    """
    Tracks semester promotions for audit purposes.
    Auto-promotion happens 5 days before next semester starts.
    """
    
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
        db_table = 'main_app_semesterpromotion'
        ordering = ['-promoted_at']
        verbose_name = 'Semester Promotion'
        verbose_name_plural = 'Semester Promotions'
    
    def __str__(self):
        return f"{self.student.register_no}: Sem {self.from_semester} → {self.to_semester}"


class PromotionSchedule(models.Model):
    """
    Stores scheduled promotions to avoid repeated processing.
    When semester.start_date - 5 days arrives, students are promoted.
    """
    
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='promotion_schedules')
    target_semester_number = models.IntegerField(help_text="Students currently in this sem will be promoted")
    scheduled_date = models.DateField(help_text="5 days before semester start")
    executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    students_promoted = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'main_app_promotionschedule'
        unique_together = ('semester', 'target_semester_number')
        ordering = ['-scheduled_date']
    
    def __str__(self):
        status = "✓ Done" if self.executed else "⏳ Pending"
        return f"Promote Sem {self.target_semester_number} → {self.target_semester_number + 1} on {self.scheduled_date} [{status}]"


# =============================================================================
# PROMOTION HELPER FUNCTIONS
# =============================================================================

def check_and_promote_students(promoted_by=None, force=False):
    """
    Automatically promotes students 5 days before the next semester starts.
    """
    from django.db import transaction
    
    today = timezone.now().date()
    
    results = {
        'total_promoted': 0,
        'semesters_processed': [],
        'errors': [],
        'already_executed': []
    }
    
    # Check PromotionSchedule for scheduled promotions
    pending_schedules = PromotionSchedule.objects.filter(
        scheduled_date__lte=today,
        executed=False
    ).select_related('semester', 'semester__academic_year')
    
    with transaction.atomic():
        for schedule in pending_schedules:
            try:
                # Find students in the target semester who haven't graduated
                students_to_promote = Student_Profile.objects.filter(
                    current_sem=schedule.target_semester_number
                ).exclude(current_sem=8)  # Don't promote 8th sem (final)
                
                promoted_count = 0
                for student in students_to_promote:
                    old_sem = student.current_sem
                    old_year = student.year_of_study
                    
                    # Increment semester
                    student.current_sem += 1
                    student.save()
                    
                    # Log the promotion
                    SemesterPromotion.objects.create(
                        student=student,
                        from_semester=old_sem,
                        to_semester=student.current_sem,
                        from_year=old_year,
                        to_year=student.year_of_study,
                        academic_year=schedule.semester.academic_year,
                        promotion_type='AUTO' if promoted_by is None else 'MANUAL',
                        promoted_by=promoted_by,
                        remarks=f"Auto-promoted for {schedule.semester}"
                    )
                    promoted_count += 1
                
                # Mark schedule as executed
                schedule.executed = True
                schedule.executed_at = timezone.now()
                schedule.students_promoted = promoted_count
                schedule.save()
                
                results['total_promoted'] += promoted_count
                results['semesters_processed'].append({
                    'semester': str(schedule.semester),
                    'students': promoted_count,
                    'from_sem': schedule.target_semester_number,
                    'to_sem': schedule.target_semester_number + 1
                })
                
            except Exception as e:
                results['errors'].append({
                    'schedule': str(schedule),
                    'error': str(e)
                })
    
    return results


def create_promotion_schedules_for_semester(semester):
    """
    Creates promotion schedules when a new semester is added.
    """
    if not semester.start_date:
        return []
    
    scheduled_date = semester.start_date - timedelta(days=5)
    created_schedules = []
    
    # Determine which students should be promoted to this semester
    target_from_sem = semester.semester_number - 1
    
    if target_from_sem > 0:
        schedule, created = PromotionSchedule.objects.get_or_create(
            semester=semester,
            target_semester_number=target_from_sem,
            defaults={
                'scheduled_date': scheduled_date,
            }
        )
        if created:
            created_schedules.append(schedule)
    
    return created_schedules


def promote_students_manually(students, to_semester, promoted_by, academic_year=None):
    """
    Manually promote a list of students to a specific semester.
    """
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
                    student=student,
                    from_semester=old_sem,
                    to_semester=to_semester,
                    from_year=old_year,
                    to_year=student.year_of_study,
                    academic_year=academic_year,
                    promotion_type='MANUAL',
                    promoted_by=promoted_by,
                    remarks="Manual bulk promotion by HOD"
                )
                results['success'] += 1
            except Exception as e:
                results['errors'].append({
                    'student': str(student),
                    'error': str(e)
                })
    
    return results
