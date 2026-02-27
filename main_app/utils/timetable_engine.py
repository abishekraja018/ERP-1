"""
Timetable Auto-Fill Engine
==========================
Ported and refactored from generate_timetable.py into a reusable class
that integrates with the wizard's TimetableConfig, LabRoom, LabRestriction,
and FixedSlotReservation models.

Features:
- Respects pre-reserved (pinned) slots from FixedSlotReservation
- Respects blocked slots (free periods, library hour, etc.)
- Uses only selected labs (TimetableConfigLab) instead of hardcoded NUM_LABS
- Enforces LabRestriction (program/year/course level)
- Faculty conflict detection across all batches
- Lab session scheduling (2-period and 4-period)
- Theory class distribution across days
"""

from collections import defaultdict
from datetime import date
import random

from django.db import transaction

from main_app.models import (
    TimeSlot, Timetable, TimetableEntry, Course_Assignment,
    ProgramBatch, FixedSlotReservation, TimetableConfig,
    TimetableConfigLab, LabRoom, LabRestriction, Course, Faculty_Profile,
)


DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']
NUM_PERIODS = 8

# 2-period lab slots — consecutive periods without breaks between them
LAB_SLOT_2_PERIOD = [(1, 2), (3, 4), (5, 6), (7, 8)]

# 4-period lab slots — morning half (1-4) or afternoon half (5-8)
LAB_SLOT_4_PERIOD = [(1, 2, 3, 4), (5, 6, 7, 8)]


def get_required_periods(course):
    """
    Calculate how many periods per week a course needs.
    Returns dict with theory periods, lab sessions count, lab type (2 or 4 periods).
    """
    if course.course_type in ['L', 'LIT']:
        practical_hrs = course.practical_hours or 0
        if practical_hrs >= 4:
            lab_type = 4
            lab_sessions = 1
        else:
            lab_type = 2
            lab_sessions = max(1, practical_hrs // 2)
        theory_periods = course.lecture_hours or 0
        return {
            'theory': theory_periods,
            'lab_sessions': lab_sessions,
            'lab_type': lab_type,
            'total': theory_periods + (lab_sessions * lab_type),
        }
    else:
        theory = (course.lecture_hours or 0) + (course.tutorial_hours or 0)
        return {
            'theory': theory,
            'lab_sessions': 0,
            'lab_type': 0,
            'total': theory,
        }


class TimetableEngine:
    """
    Auto-fill engine that generates timetable entries for every batch
    within a TimetableConfig, respecting pinned/blocked slots and
    lab restrictions.
    """

    def __init__(self, config: TimetableConfig, exclude_batch_ids=None):
        self.config = config
        self.time_slots = list(TimeSlot.objects.all().order_by('slot_number'))
        self.warnings = []  # Collect scheduling warnings

        # Selected labs for this run
        selected_lab_ids = TimetableConfigLab.objects.filter(
            config=config,
        ).values_list('lab_id', flat=True)

        if selected_lab_ids:
            self.labs = list(LabRoom.objects.filter(id__in=selected_lab_ids, is_active=True).order_by('room_code'))
        else:
            # Fall back to all active labs
            self.labs = list(LabRoom.objects.filter(is_active=True).order_by('room_code'))

        self.num_labs = len(self.labs)

        # Pre-load restrictions for quick lookup
        # {lab_id: [{'program_id': ..., 'year_of_study': ..., 'course_id': ...}, ...]}
        self.lab_restrictions = defaultdict(list)
        for r in LabRestriction.objects.filter(lab__in=self.labs):
            self.lab_restrictions[r.lab_id].append({
                'program_id': r.program_id,
                'year_of_study': r.year_of_study,
                'course_id': r.course_id,
            })

        # ── Global tracking structures (shared across batches) ──
        # {faculty_id: {(day, slot_num), ...}}
        self.faculty_schedule = defaultdict(set)
        # {(day, slot_pair_tuple): {lab_id: batch_label_or_None}}
        self.lab_schedule_2p = defaultdict(lambda: {lab.id: None for lab in self.labs})

        # ── Per-batch blocked/occupied slots (seeded from reservations) ──
        # {timetable_id: {(day, slot_num), ...}}
        self.occupied = defaultdict(set)

        # ── Pre-populate faculty schedule from EXISTING active timetables ──
        # This ensures generating timetable for Year 2 won't conflict with
        # faculty already assigned in Year 1's active timetable.
        self._load_existing_faculty_commitments(exclude_batch_ids=exclude_batch_ids)

    # ─── Pre-load existing faculty commitments ─────────────────

    def _load_existing_faculty_commitments(self, exclude_batch_ids=None):
        """
        Populate faculty_schedule from all active timetables that are NOT
        part of the batches being regenerated. This prevents the engine
        from double-booking a faculty member who is already scheduled
        elsewhere.
        
        Args:
            exclude_batch_ids: Set of ProgramBatch IDs that will be regenerated
                               (their existing entries are ignored).
                               If None, excludes the current config's program+year batches.
        """
        if exclude_batch_ids is None:
            exclude_batch_ids = set(
                ProgramBatch.objects.filter(
                    academic_year=self.config.academic_year,
                    program=self.config.program,
                    year_of_study=self.config.year_of_study,
                ).values_list('id', flat=True)
            )

        existing_entries = TimetableEntry.objects.filter(
            timetable__is_active=True,
            faculty__isnull=False,
        ).exclude(
            timetable__program_batch_id__in=exclude_batch_ids,
        ).values_list(
            'faculty_id', 'day', 'time_slot__slot_number'
        )

        for faculty_id, day, slot_num in existing_entries:
            self.faculty_schedule[faculty_id].add((day, slot_num))

    # ─── Lab availability helpers ────────────────────────────────

    def _lab_is_allowed(self, lab_id, program, year_of_study, course=None):
        """
        Check whether a lab is allowed for a given program/year/course.
        If the lab has NO restrictions, it is open to everyone.
        If restrictions exist, at least one must match.
        """
        restrictions = self.lab_restrictions.get(lab_id, [])
        if not restrictions:
            return True  # No restrictions → open to all

        for r in restrictions:
            program_ok = r['program_id'] is None or r['program_id'] == program.id
            year_ok = r['year_of_study'] is None or r['year_of_study'] == year_of_study
            course_ok = r['course_id'] is None or (course and r['course_id'] == course.pk)
            if program_ok and year_ok and course_ok:
                return True
        return False

    def _get_preferred_lab_for_course(self, course):
        """If any lab has a course-level restriction matching this course, prefer it."""
        for lab in self.labs:
            for r in self.lab_restrictions.get(lab.id, []):
                if r['course_id'] and r['course_id'] == course.pk:
                    return lab
        return None

    def _get_available_lab_2p(self, day, slot_pair, program, year_of_study, course=None):
        """
        Get an available lab for a 2-period session.
        Returns LabRoom instance or None.
        """
        preferred = self._get_preferred_lab_for_course(course) if course else None
        schedule = self.lab_schedule_2p[(day, slot_pair)]

        # Try preferred lab first
        if preferred and preferred.id in schedule and schedule[preferred.id] is None:
            if self._lab_is_allowed(preferred.id, program, year_of_study, course):
                return preferred

        # Try all other labs
        for lab in self.labs:
            if lab == preferred:
                continue
            if schedule.get(lab.id) is None and self._lab_is_allowed(lab.id, program, year_of_study, course):
                return lab
        return None

    def _get_available_lab_4p(self, day, slot_tuple, program, year_of_study, course=None):
        """
        Get an available lab for a 4-period session.
        Needs to be free for BOTH underlying 2-period slots.
        """
        if slot_tuple == (1, 2, 3, 4):
            pair1, pair2 = (1, 2), (3, 4)
        else:
            pair1, pair2 = (5, 6), (7, 8)

        sched1 = self.lab_schedule_2p[(day, pair1)]
        sched2 = self.lab_schedule_2p[(day, pair2)]

        preferred = self._get_preferred_lab_for_course(course) if course else None
        if preferred:
            if (sched1.get(preferred.id) is None and sched2.get(preferred.id) is None
                    and self._lab_is_allowed(preferred.id, program, year_of_study, course)):
                return preferred

        for lab in self.labs:
            if lab == preferred:
                continue
            if (sched1.get(lab.id) is None and sched2.get(lab.id) is None
                    and self._lab_is_allowed(lab.id, program, year_of_study, course)):
                return lab
        return None

    def _book_lab_2p(self, day, slot_pair, lab, batch_label):
        self.lab_schedule_2p[(day, slot_pair)][lab.id] = batch_label

    def _book_lab_4p(self, day, slot_tuple, lab, batch_label):
        if slot_tuple == (1, 2, 3, 4):
            self.lab_schedule_2p[(day, (1, 2))][lab.id] = batch_label
            self.lab_schedule_2p[(day, (3, 4))][lab.id] = batch_label
        else:
            self.lab_schedule_2p[(day, (5, 6))][lab.id] = batch_label
            self.lab_schedule_2p[(day, (7, 8))][lab.id] = batch_label

    # ─── Faculty helpers ─────────────────────────────────────────

    def _is_faculty_available(self, faculty_id, day, slot_num):
        return (day, slot_num) not in self.faculty_schedule[faculty_id]

    def _is_faculty_available_for_slots(self, faculty_id, day, slots):
        for s in slots:
            if (day, s) in self.faculty_schedule[faculty_id]:
                return False
        return True

    def _book_faculty(self, faculty_id, day, slot_num):
        self.faculty_schedule[faculty_id].add((day, slot_num))

    # ─── Seed from existing reservations ─────────────────────────

    def _seed_from_reservations(self, timetable, batch, reservations):
        """
        Populate tracking structures from FixedSlotReservation entries
        that have already been written into TimetableEntry.
        """
        for res in reservations:
            slot_num = res.time_slot.slot_number
            day = res.day
            self.occupied[timetable.id].add((day, slot_num))

            if not res.is_blocked and res.faculty:
                self._book_faculty(res.faculty.id, day, slot_num)

    # ─── Schedule labs ─────────────────────────────────────────

    def _schedule_labs(self, timetable, course_requirements, batch, program):
        """Schedule all lab sessions — 4-period first, then 2-period."""
        lab_courses = [c for c in course_requirements
                       if c['is_lab_course'] and c['lab_sessions_remaining'] > 0]
        if not lab_courses:
            return

        lab_4p = [c for c in lab_courses if c['lab_type'] == 4]
        lab_2p = [c for c in lab_courses if c['lab_type'] == 2]

        random.shuffle(lab_4p)
        for cr in lab_4p:
            self._schedule_4_period_lab(timetable, cr, batch, program)

        random.shuffle(lab_2p)
        for cr in lab_2p:
            self._schedule_2_period_lab(timetable, cr, batch, program)

    def _schedule_4_period_lab(self, timetable, course_req, batch, program):
        assignment = course_req['assignment']
        course = assignment.course

        while course_req['lab_sessions_remaining'] > 0:
            scheduled = False
            day_order = DAYS.copy()
            random.shuffle(day_order)

            for day in day_order:
                if scheduled:
                    break
                slot_options = list(LAB_SLOT_4_PERIOD)
                random.shuffle(slot_options)

                for slot_tuple in slot_options:
                    slots = list(slot_tuple)

                    # Any slot already occupied?
                    if any((day, s) in self.occupied[timetable.id] for s in slots):
                        continue

                    # Faculty available?
                    if not self._is_faculty_available_for_slots(assignment.faculty.id, day, slots):
                        continue

                    # Lab assistant?
                    if assignment.lab_assistant:
                        if not self._is_faculty_available_for_slots(assignment.lab_assistant.id, day, slots):
                            continue

                    # Lab room available?
                    lab = self._get_available_lab_4p(
                        day, slot_tuple, program, batch.year_of_study, course
                    )
                    if lab is None:
                        continue

                    # ── All checks passed — schedule ──
                    session_label = "Morning" if slot_tuple == (1, 2, 3, 4) else "Afternoon"
                    for i, slot_num in enumerate(slots):
                        ts = TimeSlot.objects.get(slot_number=slot_num)
                        note = f"{lab.room_code} ({session_label})" if i == 0 else (
                            f"{lab.room_code} (End)" if i == len(slots) - 1 else lab.room_code)
                        TimetableEntry.objects.create(
                            timetable=timetable,
                            day=day,
                            time_slot=ts,
                            course=course,
                            faculty=assignment.faculty,
                            is_lab=True,
                            lab_room=lab,
                            special_note=note,
                        )
                        self._book_faculty(assignment.faculty.id, day, slot_num)
                        if assignment.lab_assistant:
                            self._book_faculty(assignment.lab_assistant.id, day, slot_num)
                        self.occupied[timetable.id].add((day, slot_num))

                    self._book_lab_4p(day, slot_tuple, lab, batch.batch_name)
                    course_req['lab_sessions_remaining'] -= 1
                    scheduled = True
                    break

            if not scheduled:
                self.warnings.append(
                    f"Could not schedule 4-period lab for {course.course_code} "
                    f"(batch {batch.batch_name})"
                )
                break

    def _schedule_2_period_lab(self, timetable, course_req, batch, program):
        assignment = course_req['assignment']
        course = assignment.course

        while course_req['lab_sessions_remaining'] > 0:
            scheduled = False
            day_order = DAYS.copy()
            random.shuffle(day_order)

            for day in day_order:
                if scheduled:
                    break
                slot_options = list(LAB_SLOT_2_PERIOD)
                random.shuffle(slot_options)

                for slot_pair in slot_options:
                    start_slot, end_slot = slot_pair

                    # Any slot already occupied?
                    if ((day, start_slot) in self.occupied[timetable.id]
                            or (day, end_slot) in self.occupied[timetable.id]):
                        continue

                    # Faculty?
                    if not self._is_faculty_available(assignment.faculty.id, day, start_slot):
                        continue
                    if not self._is_faculty_available(assignment.faculty.id, day, end_slot):
                        continue

                    # Lab assistant?
                    if assignment.lab_assistant:
                        if not self._is_faculty_available(assignment.lab_assistant.id, day, start_slot):
                            continue
                        if not self._is_faculty_available(assignment.lab_assistant.id, day, end_slot):
                            continue

                    # Lab room?
                    lab = self._get_available_lab_2p(
                        day, slot_pair, program, batch.year_of_study, course
                    )
                    if lab is None:
                        continue

                    # ── Schedule ──
                    start_ts = TimeSlot.objects.get(slot_number=start_slot)
                    end_ts = TimeSlot.objects.get(slot_number=end_slot)

                    TimetableEntry.objects.create(
                        timetable=timetable,
                        day=day,
                        time_slot=start_ts,
                        course=course,
                        faculty=assignment.faculty,
                        is_lab=True,
                        lab_end_slot=end_ts,
                        lab_room=lab,
                        special_note=lab.room_code,
                    )
                    TimetableEntry.objects.create(
                        timetable=timetable,
                        day=day,
                        time_slot=end_ts,
                        course=course,
                        faculty=assignment.faculty,
                        is_lab=True,
                        lab_room=lab,
                        special_note=lab.room_code,
                    )

                    for s in (start_slot, end_slot):
                        self._book_faculty(assignment.faculty.id, day, s)
                        if assignment.lab_assistant:
                            self._book_faculty(assignment.lab_assistant.id, day, s)
                        self.occupied[timetable.id].add((day, s))

                    self._book_lab_2p(day, slot_pair, lab, batch.batch_name)
                    course_req['lab_sessions_remaining'] -= 1
                    scheduled = True
                    break

            if not scheduled:
                self.warnings.append(
                    f"Could not schedule 2-period lab for {course.course_code} "
                    f"(batch {batch.batch_name})"
                )
                break

    # ─── Schedule theory ─────────────────────────────────────────

    def _schedule_theory(self, timetable, course_requirements, batch):
        theory_courses = [c for c in course_requirements if c['theory_remaining'] > 0]
        if not theory_courses:
            return

        for course_req in theory_courses:
            assignment = course_req['assignment']
            course_days = set()

            while course_req['theory_remaining'] > 0:
                scheduled = False
                day_order = DAYS.copy()
                random.shuffle(day_order)
                # Prefer days where this course is not yet scheduled
                day_order = sorted(day_order, key=lambda d: d in course_days)

                for day in day_order:
                    if scheduled:
                        break
                    for ts in self.time_slots:
                        if ts.is_break:
                            continue
                        slot = ts.slot_number
                        if (day, slot) in self.occupied[timetable.id]:
                            continue
                        if not self._is_faculty_available(assignment.faculty.id, day, slot):
                            continue

                        TimetableEntry.objects.create(
                            timetable=timetable,
                            day=day,
                            time_slot=ts,
                            course=assignment.course,
                            faculty=assignment.faculty,
                            is_lab=False,
                        )
                        self._book_faculty(assignment.faculty.id, day, slot)
                        self.occupied[timetable.id].add((day, slot))
                        course_req['theory_remaining'] -= 1
                        course_days.add(day)
                        scheduled = True
                        break

                if not scheduled:
                    self.warnings.append(
                        f"Could not schedule theory for {assignment.course.course_code} "
                        f"(batch {batch.batch_name}, {course_req['theory_remaining']} periods remaining)"
                    )
                    break

    # ─── Count already-reserved periods per course ───────────────

    @staticmethod
    def _count_reserved_for_course(reservations, course_code):
        """Count how many reservation slots already cover a given course."""
        return sum(1 for r in reservations
                   if not r.is_blocked and r.course and r.course.course_code == course_code)

    # ─── Main generation entry point ─────────────────────────────

    def generate(self, effective_date=None):
        """
        Run full generation:
        1. Copy reserved/blocked slots into TimetableEntry.
        2. Auto-fill remaining slots for each batch.
        Returns dict with results and warnings.
        """
        if effective_date is None:
            effective_date = date.today()

        config = self.config
        program = config.program

        batches = ProgramBatch.objects.filter(
            academic_year=config.academic_year,
            program=program,
            year_of_study=config.year_of_study,
            is_active=True,
        )

        if not batches.exists():
            return {'success': False, 'error': 'No batches found', 'timetables': [], 'warnings': []}

        timetables_created = []

        with transaction.atomic():
            for batch in batches:
                # Create or reset timetable record
                timetable, created = Timetable.objects.update_or_create(
                    academic_year=config.academic_year,
                    semester=config.semester,
                    year=config.year_of_study,
                    program_batch=batch,
                    defaults={
                        'batch': batch.batch_name,
                        'effective_from': effective_date,
                        'created_by': config.created_by,
                        'is_active': True,
                    },
                )
                if not created:
                    timetable.entries.all().delete()

                # ── Phase 1: Copy fixed reservations ──
                reservations = list(
                    FixedSlotReservation.objects.filter(
                        config=config, batch=batch,
                    ).select_related('course', 'faculty', 'time_slot')
                )

                for res in reservations:
                    TimetableEntry.objects.create(
                        timetable=timetable,
                        day=res.day,
                        time_slot=res.time_slot,
                        course=res.course if not res.is_blocked else None,
                        faculty=res.faculty if not res.is_blocked else None,
                        special_note=res.special_note if not res.is_blocked else res.block_reason,
                        is_blocked=res.is_blocked,
                        block_reason=res.block_reason if res.is_blocked else None,
                    )

                # Seed tracking from reservations
                self._seed_from_reservations(timetable, batch, reservations)

                # ── Phase 2: Auto-fill ──
                assignments = Course_Assignment.objects.filter(
                    academic_year=config.academic_year,
                    batch=batch,
                    semester=config.semester,
                    is_active=True,
                ).select_related('course', 'faculty', 'lab_assistant')

                course_requirements = []
                for asgn in assignments:
                    req = get_required_periods(asgn.course)
                    already_reserved = self._count_reserved_for_course(
                        reservations, asgn.course.course_code
                    )

                    # Subtract already-reserved theory / lab periods
                    theory_remaining = max(0, req['theory'] - already_reserved)
                    lab_remaining = req['lab_sessions']
                    # If course is lab type and some periods already reserved,
                    # assume each lab_type-worth of reserved slots is one session
                    if req['lab_type'] > 0 and already_reserved > 0:
                        lab_used = already_reserved // req['lab_type']
                        lab_remaining = max(0, req['lab_sessions'] - lab_used)
                        # Leftover reserved slots that didn't make a full lab session
                        leftover = already_reserved - lab_used * req['lab_type']
                        theory_remaining = max(0, req['theory'] - leftover)

                    course_requirements.append({
                        'assignment': asgn,
                        'theory_remaining': theory_remaining,
                        'lab_sessions_remaining': lab_remaining,
                        'lab_type': req['lab_type'],
                        'is_lab_course': asgn.course.course_type in ['L', 'LIT'],
                    })

                # Schedule labs first (most constrained), then theory
                self._schedule_labs(timetable, course_requirements, batch, program)
                self._schedule_theory(timetable, course_requirements, batch)

                timetables_created.append({
                    'id': timetable.id,
                    'batch_name': batch.batch_name,
                    'entries_count': timetable.entries.count(),
                })

            # Mark config as generated
            config.is_generated = True
            config.save()

        return {
            'success': True,
            'timetables': timetables_created,
            'warnings': self.warnings,
        }

    # ─── Preview (dry-run) ───────────────────────────────────────

    def preview(self):
        """
        Analyse what the generation would produce without writing to DB.
        Returns course requirements, lab availability, and potential warnings.
        """
        config = self.config
        program = config.program

        batches = ProgramBatch.objects.filter(
            academic_year=config.academic_year,
            program=program,
            year_of_study=config.year_of_study,
            is_active=True,
        )

        result = {
            'batches': [],
            'total_labs_available': self.num_labs,
            'lab_names': [l.room_code for l in self.labs],
        }

        for batch in batches:
            reservations = FixedSlotReservation.objects.filter(
                config=config, batch=batch,
            )
            reserved_count = reservations.filter(is_blocked=False).count()
            blocked_count = reservations.filter(is_blocked=True).count()

            assignments = Course_Assignment.objects.filter(
                academic_year=config.academic_year,
                batch=batch,
                semester=config.semester,
                is_active=True,
            ).select_related('course')

            total_needed = 0
            for asgn in assignments:
                req = get_required_periods(asgn.course)
                total_needed += req['total']

            total_slots = len(DAYS) * NUM_PERIODS  # 40 per batch
            remaining = total_slots - reserved_count - blocked_count

            result['batches'].append({
                'batch_name': batch.batch_name,
                'batch_id': batch.id,
                'reserved_count': reserved_count,
                'blocked_count': blocked_count,
                'remaining_slots': remaining,
                'total_periods_needed': total_needed,
                'courses_count': assignments.count(),
            })

        return result

    # ─── Multi-config generation (all programs at once) ───────

    @staticmethod
    def generate_all(configs, created_by=None):
        """
        Generate timetables for multiple TimetableConfigs at once.
        
        1. Collects ALL batch IDs across all configs.
        2. Excludes them from existing-faculty-commitment loading.
        3. Generates configs sequentially; each subsequent config sees
           the faculty bookings from previously generated configs
           because they share the engine's faculty_schedule (via DB).
        
        Args:
            configs: QuerySet or list of TimetableConfig objects
            created_by: Account_User for created_by field
        
        Returns:
            dict with overall results, per-config breakdown, and warnings.
        """
        configs = list(configs)
        if not configs:
            return {'success': False, 'error': 'No configs provided', 'results': []}

        # Collect ALL batch IDs that will be (re)generated
        all_batch_ids = set()
        for cfg in configs:
            batch_ids = ProgramBatch.objects.filter(
                academic_year=cfg.academic_year,
                program=cfg.program,
                year_of_study=cfg.year_of_study,
                is_active=True,
            ).values_list('id', flat=True)
            all_batch_ids.update(batch_ids)

        all_results = []
        all_warnings = []

        with transaction.atomic():
            for cfg in configs:
                engine = TimetableEngine(cfg, exclude_batch_ids=all_batch_ids)
                result = engine.generate(effective_date=date.today())

                if result['success']:
                    all_results.extend(result['timetables'])
                    all_warnings.extend(result.get('warnings', []))
                else:
                    all_warnings.append(
                        f"{cfg.program.code} Year {cfg.year_of_study}: {result.get('error', 'Failed')}"
                    )

        return {
            'success': True,
            'timetables': all_results,
            'warnings': all_warnings,
        }
