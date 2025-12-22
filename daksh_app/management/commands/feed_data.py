import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from daksh_app.models import Student, Exam, Question, Concept, Cohort

# --- PLANE A: SYLLABUS DEFINITION ---
# Keywords map to topics for auto-tagging questions
SYLLABUS_MAP = {
    "Physics": {
        "Mechanics": ["acceleration", "velocity", "friction", "collision", "momentum", "projectile", "kinematics", "force", "motion", "newton"],
        "Rotational Motion": ["inertia", "torque", "angular", "rolling", "cylinder", "disc", "sphere", "rotation", "moment"],
        "Gravitation": ["satellite", "orbit", "planet", "escape velocity", "kepler", "gravitational", "gravity"],
        "Thermodynamics": ["heat", "temperature", "carnot", "adiabatic", "isothermal", "gas", "efficiency", "entropy", "thermal"],
        "Electromagnetism": ["current", "voltage", "resistor", "capacitor", "magnetic", "flux", "induction", "charge", "dipole", "electric", "circuit"],
        "Optics": ["lens", "mirror", "refraction", "interference", "diffraction", "slit", "polaroid", "light", "ray"],
        "Modern Physics": ["nucleus", "atom", "photoelectric", "bohr", "decay", "proton", "alpha", "quantum", "photon"]
    },
    "Chemistry": {
        "Physical Chemistry": ["mole", "equilibrium", "kinetics", "activation", "solution", "electrochemistry", "enthalpy", "entropy", "rate", "concentration"],
        "Organic Chemistry": ["alcohol", "phenol", "aldehyde", "ketone", "amine", "carbocation", "nucleophile", "reaction", "isomer", "carbon", "organic", "hydrocarbon"],
        "Inorganic Chemistry": ["coordination", "complex", "ligand", "periodic", "boron", "oxide", "metal", "ionic", "covalent", "element"]
    },
    "Mathematics": {
        "Calculus": ["limit", "derivative", "integral", "continuity", "differential equation", "area bounded", "differentiation", "integration"],
        "Algebra": ["matrix", "determinant", "probability", "permutation", "combination", "complex number", "series", "root", "equation", "polynomial"],
        "Coordinate Geometry": ["circle", "parabola", "ellipse", "hyperbola", "line", "locus", "conic", "tangent", "normal"],
        "Trigonometry": ["sin", "cos", "tan", "theta", "angle", "triangle", "trigonometric"],
        "Vectors & 3D": ["vector", "plane", "direction", "cross product", "dot product", "3d", "dimension"]
    }
}


class Command(BaseCommand):
    help = 'Feed data into 3-Fold Architecture (Cohort ABC)'

    def handle(self, *args, **kwargs):
        base_path = os.path.join(settings.BASE_DIR, 'mock_data')
        
        self.stdout.write(self.style.WARNING("\n" + "="*60))
        self.stdout.write(self.style.WARNING("   3-FOLD HiRAG ARCHITECTURE DATA FEEDER"))
        self.stdout.write(self.style.WARNING("="*60 + "\n"))
        
        # Build concept cache for auto-tagging
        concept_cache = {}
        
        # ==========================================
        # PLANE A: KNOWLEDGE LAYER
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("--- 1. INITIALIZING PLANE A (KNOWLEDGE LAYER) ---"))
        
        for subject, topics in SYLLABUS_MAP.items():
            # Create Subject node (top-level concept)
            existing_subj = Concept.nodes.first_or_none(name=subject)
            if existing_subj:
                subj_node = existing_subj
            else:
                subj_node = Concept(name=subject).save()
            concept_cache[subject] = subj_node
            self.stdout.write(f"  [OK] Created: {subject}")
            
            for topic, keywords in topics.items():
                # Create Topic node (child of subject)
                existing_topic = Concept.nodes.first_or_none(name=topic)
                if existing_topic:
                    topic_node = existing_topic
                else:
                    topic_node = Concept(name=topic).save()
                
                # Link topic -> subject (PART_OF relationship)
                if not topic_node.part_of.is_connected(subj_node):
                    topic_node.part_of.connect(subj_node)
                
                concept_cache[topic] = topic_node
                
                # Map all keywords to this topic for auto-tagging
                for kw in keywords:
                    concept_cache[kw.lower()] = topic_node
                
                self.stdout.write(f"    +-- {topic} ({len(keywords)} keywords)")
        
        self.stdout.write(self.style.SUCCESS(f"  [OK] Plane A Complete: {len([k for k in concept_cache.keys() if k in SYLLABUS_MAP or k in sum([list(t.keys()) for t in SYLLABUS_MAP.values()], [])])} concepts created\n"))
        
        # ==========================================
        # PLANE B: ASSESSMENT LAYER
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("--- 2. INITIALIZING PLANE B (ASSESSMENT LAYER) ---"))
        
        exams_file = os.path.join(base_path, 'exams', 'exams.json')
        with open(exams_file, 'r', encoding='utf-8') as f:
            exams_data = json.load(f)
        
        total_questions = 0
        tagged_questions = 0
        
        for item in exams_data:
            # Create Exam node
            existing_exam = Exam.nodes.first_or_none(exam_id=item['exam_id'])
            if existing_exam:
                exam = existing_exam
            else:
                exam = Exam(
                    exam_id=item['exam_id'],
                    name=item['exam_name'],
                    duration=str(item['duration'])
                ).save()
            self.stdout.write(f"  [OK] Exam {item['exam_id']} - {item['exam_name']}")
            
            # Load questions for this exam
            q_file = os.path.join(base_path, 'exams', f'questions_exam_{item["exam_id"]}.json')
            if os.path.exists(q_file):
                with open(q_file, 'r', encoding='utf-8') as qf:
                    q_data = json.load(qf)
                    
                    for q_item in q_data:
                        total_questions += 1
                        
                        # Create global unique ID: exam_id * 1000 + question_id
                        global_q_id = item['exam_id'] * 1000 + q_item['question_id']
                        
                        # Create Question node
                        existing_q = Question.nodes.first_or_none(global_question_id=global_q_id)
                        if existing_q:
                            question = existing_q
                        else:
                            question = Question(
                                global_question_id=global_q_id,
                                exam_id=item['exam_id'],
                                question_id=q_item['question_id'],
                                text=q_item['question_text'],
                                options=q_item['options'],
                                correct_option=q_item['correct_option']
                            ).save()
                        
                        # Link Exam -> Question (INCLUDES relationship)
                        if not exam.includes.is_connected(question):
                            exam.includes.connect(question)
                        
                        # AUTO-TAGGING: Link Question -> Concept (TESTS relationship)
                        text_lower = q_item['question_text'].lower()
                        classified = False
                        
                        # Try keyword matching first
                        for kw, node in concept_cache.items():
                            # Skip subject-level matches, prefer topic-level
                            if kw not in ["physics", "chemistry", "mathematics"] and kw in text_lower:
                                if not question.tests_concept.is_connected(node):
                                    question.tests_concept.connect(node)
                                classified = True
                                tagged_questions += 1
                                break
                        
                        # Fallback: Tag by question ID range (JEE structure)
                        if not classified:
                            q_id = q_item['question_id']
                            if q_id <= 30:
                                fallback = concept_cache.get('Physics')
                            elif q_id <= 60:
                                fallback = concept_cache.get('Chemistry')
                            else:
                                fallback = concept_cache.get('Mathematics')
                            
                            if fallback and not question.tests_concept.is_connected(fallback):
                                question.tests_concept.connect(fallback)
                            tagged_questions += 1
                
                self.stdout.write(f"    +-- {len(q_data)} questions loaded")
        
        self.stdout.write(self.style.SUCCESS(f"  [OK] Plane B Complete: {len(exams_data)} exams, {total_questions} questions ({tagged_questions} tagged)\n"))
        
        # ==========================================
        # PLANE C: LEARNER LAYER
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("--- 3. INITIALIZING PLANE C (LEARNER LAYER) ---"))
        
        # Create the Cohort node
        existing_cohort = Cohort.nodes.first_or_none(name='ABC')
        if existing_cohort:
            cohort_abc = existing_cohort
        else:
            cohort_abc = Cohort(name='ABC').save()
        self.stdout.write(f"  [OK] Created: Cohort ABC")
        
        students_dir = os.path.join(base_path, 'students')
        student_count = 0
        attempt_count = 0
        
        for filename in sorted(os.listdir(students_dir)):
            if filename.startswith('student_') and filename.endswith('.json'):
                with open(os.path.join(students_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                s_info = data['student_info']
                
                # Create Student node
                existing_student = Student.nodes.first_or_none(student_id=s_info['student_id'])
                if existing_student:
                    student = existing_student
                else:
                    student = Student(
                        student_id=s_info['student_id'],
                        name=s_info['student_name'],
                        enrollment_id=s_info['enrollment_id']
                    ).save()
                student_count += 1
                
                # Link Student -> Cohort (MEMBER_OF relationship)
                if not student.member_of.is_connected(cohort_abc):
                    student.member_of.connect(cohort_abc)
                
                self.stdout.write(f"  [OK] Student: {s_info['student_name']} (ID: {s_info['student_id']})")
                
                # Link Student -> Question (ATTEMPTED relationship with details)
                student_attempts = 0
                for report in data.get('exams_report', []):
                    exam_id = report.get('exam_info', {}).get('exam_id', 0)
                    for q_attempt in report.get('questions', []):
                        try:
                            # Use global question ID
                            global_q_id = exam_id * 1000 + q_attempt['question_id']
                            q_node = Question.nodes.get(global_question_id=global_q_id)
                            
                            # Determine outcome
                            outcome = 'skipped'
                            if q_attempt.get('response_status') == 'answered':
                                selected = str(q_attempt.get('selected_option', ''))
                                correct = str(q_attempt.get('correct_options', ''))
                                outcome = 'correct' if selected == correct else 'incorrect'
                            
                            # Create the rich ATTEMPTED relationship
                            if not student.attempted.is_connected(q_node):
                                student.attempted.connect(q_node, {
                                    'selected_option': str(q_attempt.get('selected_option', '')),
                                    'time_spent': str(q_attempt.get('time_spent', '0')),
                                    'outcome': outcome
                                })
                                student_attempts += 1
                                attempt_count += 1
                                
                        except Question.DoesNotExist:
                            continue
                
                self.stdout.write(f"    +-- {student_attempts} question attempts recorded")
        
        self.stdout.write(self.style.SUCCESS(f"  [OK] Plane C Complete: {student_count} students, {attempt_count} attempts\n"))
        
        # ==========================================
        # SUMMARY
        # ==========================================
        self.stdout.write(self.style.WARNING("="*60))
        self.stdout.write(self.style.SUCCESS("   [SUCCESS] 3-FOLD HiRAG ARCHITECTURE SUCCESSFULLY LOADED!"))
        self.stdout.write(self.style.WARNING("="*60))
        self.stdout.write(f"""
  [STATS] Graph Statistics:
     * Plane A (Knowledge): {len(SYLLABUS_MAP)} subjects, {sum(len(t) for t in SYLLABUS_MAP.values())} topics
     * Plane B (Assessment): {len(exams_data)} exams, {total_questions} questions
     * Plane C (Learner): 1 cohort, {student_count} students, {attempt_count} attempts
  
  [LINKS] Key Relationships:
     * Concept -[PART_OF]-> Concept (hierarchy)
     * Question -[TESTS]-> Concept (what it measures)
     * Exam -[INCLUDES]-> Question (exam structure)
     * Student -[MEMBER_OF]-> Cohort (grouping)
     * Student -[ATTEMPTED]-> Question (with outcome data)
  
  [TIP] Sample Query in Neo4j Browser:
     MATCH (s:Student)-[a:ATTEMPTED]->(q:Question)-[:TESTS]->(c:Concept)
     WHERE a.outcome = 'incorrect'
     RETURN s.name, c.name, count(*) as weak_areas
     ORDER BY weak_areas DESC
        """)

