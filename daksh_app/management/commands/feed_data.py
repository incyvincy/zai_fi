"""
Purpose: Load exam/student data into Neo4j with safe handling of missing metadata.

HARD RULES:
1. Never fake/guess missing concept/skill/difficulty
2. If tags missing -> flag needs_ai_tagging=True
3. Store time_spent only if present (None, not 0, if missing)
4. Client-provided tags stored with source='client'
5. NO HARDCODING for specific exams (works with JEE, NEET, CUET, etc.)
"""

import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from daksh_app.models import Student, Exam, Question, Concept, Cohort, Skill, Difficulty


class Command(BaseCommand):
    help = 'Feed data with safe missing-data handling (Day 1 Schema)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tag-with-ai',
            action='store_true',
            help='Run AI tagging after ingestion for questions missing tags'
        )

    def _detect_exam_type(self, exam_name: str) -> str:
        """Auto-detect exam type from name (flexible, not hardcoded)."""
        name_lower = exam_name.lower()
        type_keywords = {
            'jee': ['jee', 'iit'], 'neet': ['neet', 'medical'], 'cuet': ['cuet'],
            'board': ['board', 'cbse', 'icse', 'state'], 'olympiad': ['olympiad', 'imo'],
            'sat': ['sat'], 'gre': ['gre'], 'cat': ['cat'], 'gate': ['gate'],
        }
        for exam_type, keywords in type_keywords.items():
            if any(kw in name_lower for kw in keywords):
                return exam_type
        return 'general'

    def handle(self, *args, **options):
        base_path = os.path.join(settings.BASE_DIR, 'mock_data')
        
        self.stdout.write(self.style.WARNING("\n" + "="*90))
        self.stdout.write(self.style.WARNING("   SAFE DATA INGESTION (Day 1 - Missing Data Handling)"))
        self.stdout.write(self.style.WARNING("="*90 + "\n"))
        
        stats = {
            'exams': 0, 'questions': 0, 'questions_with_client_tags': 0,
            'questions_needing_ai': 0, 'students': 0, 'attempts': 0, 'attempts_with_time': 0,
        }
        
        # ==========================================
        # PHASE 1: LOAD EXAMS & QUESTIONS (Plane B)
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("--- PHASE 1: INGESTING EXAMS & QUESTIONS ---"))
        
        exams_file = os.path.join(base_path, 'exams', 'exams.json')
        if not os.path.exists(exams_file):
            self.stdout.write(self.style.ERROR(f"  [ERROR] Exams file not found: {exams_file}"))
            return
        
        with open(exams_file, 'r', encoding='utf-8') as f:
            exams_data = json.load(f)
        
        for exam_item in exams_data:
            exam_id = exam_item['exam_id']
            exam_name = exam_item.get('exam_name', f'Exam {exam_id}')
            exam_type = self._detect_exam_type(exam_name)
            
            # Create/Get Exam node
            exam = Exam.nodes.first_or_none(exam_id=exam_id)
            if not exam:
                exam = Exam(
                    exam_id=exam_id, name=exam_name, exam_type=exam_type,
                    duration=int(exam_item.get('duration', 0)) or None
                ).save()
            stats['exams'] += 1
            
            self.stdout.write(f"  [EXAM] {exam_id}: {exam_name} (type: {exam_type})")
            
            # Load Questions for this Exam
            q_file = os.path.join(base_path, 'exams', f'questions_exam_{exam_id}.json')
            if not os.path.exists(q_file):
                self.stdout.write(self.style.WARNING(f"    [WARN] No questions file for exam {exam_id}"))
                continue
            
            with open(q_file, 'r', encoding='utf-8') as qf:
                questions_data = json.load(qf)
            
            for q_item in questions_data:
                question_id = q_item['question_id']
                global_q_id = exam_id * 1000 + question_id
                q_text = q_item.get('question_text', '')
                
                if not q_text:
                    self.stdout.write(self.style.WARNING(f"    [WARN] Q{question_id} has no text, skipping"))
                    continue
                
                # Create/Update Question node with TEXT (required for AI tagging)
                question = Question.nodes.first_or_none(global_question_id=global_q_id)
                if not question:
                    question = Question(global_question_id=global_q_id, text=q_text).save()
                elif question.text != q_text:
                    question.text = q_text
                    question.save()
                
                stats['questions'] += 1
                
                # Link Exam -> Question
                if not exam.includes.is_connected(question):
                    exam.includes.connect(question)
                
                # --- HANDLE TAGS (Safe Logic - NO GUESSING) ---
                client_concept = q_item.get('concept') or q_item.get('topic')
                client_skill = q_item.get('skill') or q_item.get('skill_required')
                client_difficulty = q_item.get('difficulty')
                
                has_any_client_tag = any([client_concept, client_skill, client_difficulty])
                has_all_client_tags = all([client_concept, client_skill, client_difficulty])
                
                if has_any_client_tag:
                    stats['questions_with_client_tags'] += 1
                    
                    if client_concept:
                        parent = q_item.get('parent_concept') or q_item.get('subject', 'General')
                        c_node = Concept.nodes.first_or_none(name=client_concept)
                        if not c_node:
                            c_node = Concept(name=client_concept, parent_concept=parent).save()
                        if not question.topics.is_connected(c_node):
                            question.topics.connect(c_node, {'tag_source': 'client', 'confidence': 1.0, 'version': 1})
                    
                    if client_skill:
                        s_node = Skill.nodes.first_or_none(name=client_skill)
                        if not s_node:
                            s_node = Skill(name=client_skill).save()
                        if not question.skills.is_connected(s_node):
                            question.skills.connect(s_node, {'tag_source': 'client', 'confidence': 1.0, 'version': 1})
                    
                    if client_difficulty:
                        d_node = Difficulty.nodes.first_or_none(name=client_difficulty)
                        if not d_node:
                            d_node = Difficulty(name=client_difficulty).save()
                        if not question.difficulties.is_connected(d_node):
                            question.difficulties.connect(d_node, {'tag_source': 'client', 'confidence': 1.0, 'version': 1})
                
                # Flag for AI if ANY tag is missing (don't guess!)
                if not has_all_client_tags:
                    question.needs_ai_tagging = True
                    question.tagging_status = 'untagged'
                    stats['questions_needing_ai'] += 1
                else:
                    question.needs_ai_tagging = False
                    question.tagging_status = 'tagged'
                
                question.save()
            
            self.stdout.write(f"    +-- {len(questions_data)} questions loaded")
        
        self.stdout.write(self.style.SUCCESS(f"\n  [OK] Phase 1 Complete: {stats['exams']} exams, {stats['questions']} questions"))
        self.stdout.write(f"       -> {stats['questions_with_client_tags']} with client tags")
        self.stdout.write(f"       -> {stats['questions_needing_ai']} flagged for AI tagging\n")
        
        # ==========================================
        # PHASE 2: LOAD STUDENTS & ATTEMPTS (Plane C)
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("--- PHASE 2: INGESTING STUDENTS & ATTEMPTS ---"))
        
        # Create default cohort
        cohort = Cohort.nodes.first_or_none(name='Default')
        if not cohort:
            cohort = Cohort(name='Default').save()
        
        students_dir = os.path.join(base_path, 'students')
        if not os.path.exists(students_dir):
            self.stdout.write(self.style.WARNING("  [WARN] No students directory found"))
        else:
            for filename in sorted(os.listdir(students_dir)):
                if not filename.startswith('student_') or not filename.endswith('.json'):
                    continue
                
                with open(os.path.join(students_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                s_info = data.get('student_info', {})
                if not s_info.get('student_id'):
                    continue
                
                # Create/Get Student node
                student = Student.nodes.first_or_none(student_id=s_info['student_id'])
                if not student:
                    student = Student(
                        student_id=s_info['student_id'],
                        name=s_info.get('student_name', f"Student {s_info['student_id']}")
                    ).save()
                stats['students'] += 1
                
                # Link to Cohort
                cohort_name = s_info.get('cohort', 'Default')
                student_cohort = Cohort.nodes.first_or_none(name=cohort_name)
                if not student_cohort:
                    student_cohort = Cohort(name=cohort_name).save()
                if not student.member_of.is_connected(student_cohort):
                    student.member_of.connect(student_cohort)
                
                self.stdout.write(f"  [STUDENT] {s_info['student_id']}: {s_info.get('student_name', 'Unknown')}")
                
                # Process Exam Reports (Attempts)
                student_attempts = 0
                for report in data.get('exams_report', []):
                    exam_id = report.get('exam_info', {}).get('exam_id', 0)
                    
                    for q_attempt in report.get('questions', []):
                        try:
                            global_q_id = exam_id * 1000 + q_attempt['question_id']
                            q_node = Question.nodes.get(global_question_id=global_q_id)
                            
                            # Determine outcome
                            outcome = 'skipped'
                            if q_attempt.get('response_status') == 'answered':
                                selected = str(q_attempt.get('selected_option', ''))
                                correct = str(q_attempt.get('correct_options', ''))
                                outcome = 'correct' if selected == correct else 'incorrect'
                            
                            # Handle time_spent: store None if missing (NOT 0)
                            time_spent = q_attempt.get('time_spent')
                            time_spent_seconds = None
                            if time_spent is not None and time_spent != '':
                                try:
                                    time_spent_seconds = int(time_spent)
                                    stats['attempts_with_time'] += 1
                                except (ValueError, TypeError):
                                    time_spent_seconds = None
                            
                            # Create attempt relationship
                            if not student.attempted.is_connected(q_node):
                                student.attempted.connect(q_node, {
                                    'outcome': outcome,
                                    'time_spent_seconds': time_spent_seconds
                                })
                                student_attempts += 1
                                stats['attempts'] += 1
                        
                        except Question.DoesNotExist:
                            continue
                
                self.stdout.write(f"    +-- {student_attempts} attempts recorded")
        
        self.stdout.write(self.style.SUCCESS(f"\n  [OK] Phase 2 Complete: {stats['students']} students, {stats['attempts']} attempts"))
        self.stdout.write(f"       -> {stats['attempts_with_time']} attempts have time data\n")
        
        # ==========================================
        # PHASE 3: OPTIONAL AI TAGGING
        # ==========================================
        if options.get('tag_with_ai') and stats['questions_needing_ai'] > 0:
            self.stdout.write(self.style.HTTP_INFO("--- PHASE 3: AI TAGGING ---"))
            try:
                from daksh_app.ai_tagging import batch_tag_questions
                result = batch_tag_questions(limit=stats['questions_needing_ai'])
                self.stdout.write(self.style.SUCCESS(
                    f"  [OK] AI Tagging: {result['success']}/{result['processed']} successful"
                ))
                if result['errors']:
                    for err in result['errors'][:5]:
                        self.stdout.write(self.style.WARNING(f"    [FAIL] Q{err['question_id']}: {err['error']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [ERROR] AI Tagging failed: {e}"))
        
        # ==========================================
        # SUMMARY
        # ==========================================
        self.stdout.write(self.style.WARNING("\n" + "="*90))
        self.stdout.write(self.style.SUCCESS("   INGESTION COMPLETE"))
        self.stdout.write(self.style.WARNING("="*90))
        self.stdout.write(f"""
  STATISTICS:
    Exams:     {stats['exams']}
    Questions: {stats['questions']} ({stats['questions_with_client_tags']} tagged, {stats['questions_needing_ai']} need AI)
    Students:  {stats['students']}
    Attempts:  {stats['attempts']} ({stats['attempts_with_time']} with time data)
  
  NEXT STEPS:
    - Run AI tagging: python manage.py feed_data --tag-with-ai
    - Repair existing data: python manage.py repair_data
""")


