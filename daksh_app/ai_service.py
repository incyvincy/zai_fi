import os
import json
import time
import google.generativeai as genai
from django.conf import settings

# Configure API Key
GOOGLE_API_KEY = getattr(settings, 'GEMINI_API_KEY', os.getenv('GEMINI_API_KEY'))
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Directory for caching
MOCK_DATA_DIR = os.path.join(settings.BASE_DIR, 'mock_data')
os.makedirs(MOCK_DATA_DIR, exist_ok=True)

class AIService:
    
    @staticmethod
    def _get_cached_or_generate(filename, generator_func, *args):
        """
        Generic caching wrapper.
        If file exists -> Load and return.
        If not -> Run the generator_func (API calls), Save, Return.
        """
        file_path = os.path.join(MOCK_DATA_DIR, filename)

        if os.path.exists(file_path):
            print(f"LOADING FROM CACHE: {filename}")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Cache corrupt, regenerating: {e}")

        print(f"GENERATING NEW DATA: {filename}")
        data = generator_func(*args)
        
        if data:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"SAVED TO CACHE: {filename}")
        
        return data

    @staticmethod
    def _call_llm(prompt):
        if not GOOGLE_API_KEY:
            raise Exception("GEMINI_API_KEY is not set.")
            
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        full_prompt = (
            f"{prompt}\n\n"
            "CRITICAL: Return ONLY valid JSON. No markdown, no ```json, no explanations. "
            "Just the raw JSON array/object."
        )
        
        try:
            response = model.generate_content(full_prompt)
            text_response = response.text.strip()
            
            # Debug: Print first 200 chars of response
            print(f"      API Response Preview: {text_response[:200]}...")
            
            # Clean markdown wrappers
            if text_response.startswith("```json"): text_response = text_response[7:]
            if text_response.startswith("```"): text_response = text_response[3:]
            if text_response.endswith("```"): text_response = text_response[:-3]
            
            text_response = text_response.strip()
            
            parsed = json.loads(text_response)
            print(f"      ✓ Successfully parsed JSON ({len(parsed) if isinstance(parsed, list) else 'N/A'} items)")
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"      ✗ JSON Parse Error: {e}")
            print(f"      Raw Response: {text_response[:500]}")
            return []
        except Exception as e:
            print(f"      ✗ LLM Error: {e}")
            return []

    @staticmethod
    def get_students():
        def generate():
            return AIService._call_llm(
                "Generate a JSON array of 5 fictional Indian students for JEE Mains. "
                "Keys: 'student_id' (int), 'student_name' (string), 'enrollment_id' (string)."
            )
        return AIService._get_cached_or_generate("students/students.json", generate)

    @staticmethod
    def get_exams():
        def generate():
            return AIService._call_llm(
                "Generate a JSON array of 15 distinct JEE Mains Mock Exams (Jan/Apr 2024). "
                "Keys: 'exam_id' (int 1-15), 'exam_name' (string), 'duration' ('180'), 'total_questions' (90)."
            )
        return AIService._get_cached_or_generate("exams/exams.json", generate)

    @staticmethod
    def get_questions(exam_id):
        # We define a custom generator to make 3 separate calls (Phy, Chem, Math)
        def generate_full_paper(exam_id):
            print(f"\n=== Generating 90 Questions for Exam {exam_id} ===")
            
            print("  [1/3] Generating Physics Questions (Q1-Q30)...")
            phy = AIService._generate_subject_questions("Physics", 1, 30)
            print(f"      ✓ Generated {len(phy)} Physics questions")
            time.sleep(2)  # Rate limiting
            
            print("  [2/3] Generating Chemistry Questions (Q31-Q60)...")
            chem = AIService._generate_subject_questions("Chemistry", 31, 60)
            print(f"      ✓ Generated {len(chem)} Chemistry questions")
            time.sleep(2)  # Rate limiting
            
            print("  [3/3] Generating Mathematics Questions (Q61-Q90)...")
            math = AIService._generate_subject_questions("Mathematics", 61, 90)
            print(f"      ✓ Generated {len(math)} Mathematics questions")
            
            all_questions = phy + chem + math
            print(f"\n=== TOTAL: {len(all_questions)} Questions Generated ===\n")
            
            if len(all_questions) < 90:
                print(f"WARNING: Only {len(all_questions)}/90 questions generated!")
            
            return all_questions

        return AIService._get_cached_or_generate(f"exams/questions_exam_{exam_id}.json", generate_full_paper, exam_id)

    @staticmethod
    def _generate_subject_questions(subject, start_id, end_id):
        # Syllabus Content
        syllabi = {
            "Physics": "Kinematics, Laws of Motion, Work/Energy/Power, Rotational Motion, Gravitation, Thermodynamics, Electrostatics, Current Electricity, Magnetic Effects, EMI, Optics, Atoms/Nuclei",
            "Chemistry": "Atomic Structure, Chemical Bonding, Thermodynamics, Equilibrium, Redox, Periodic Table, p-block, d-block, Organic Chemistry, Hydrocarbons, Alcohols, Aldehydes/Ketones",
            "Mathematics": "Complex Numbers, Matrices, Permutations/Combinations, Calculus, Differential Equations, Coordinate Geometry, 3D Geometry, Vector Algebra, Probability, Trigonometry"
        }
        
        count = end_id - start_id + 1
        syllabus_text = syllabi.get(subject, "General JEE Syllabus")
        
        prompt = (
            f"Generate EXACTLY {count} JEE Mains {subject} questions.\n"
            f"Topics: {syllabus_text}\n\n"
            f"Return a JSON array with {count} objects. Each object:\n"
            "{\n"
            f'  "question_id": {start_id},\n'
            '  "question_text": "A detailed JEE-level problem statement",\n'
            '  "options": {"Option 1": "answer A", "Option 2": "answer B", "Option 3": "answer C", "Option 4": "answer D"},\n'
            '  "correct_option": "Option 1",\n'
            '  "marks": 4\n'
            "}\n\n"
            f"Question IDs must range from {start_id} to {end_id}.\n"
            "NO markdown. Return raw JSON array only."
        )
        
        result = AIService._call_llm(prompt)
        
        if not result or len(result) == 0:
            print(f"      ERROR: No questions returned for {subject}!")
            # Return empty array instead of None to avoid concatenation errors
            return []
        
        return result

    @staticmethod
    def get_exam_report(exam_id):
        """
        Load pre-generated exam report directly from exam_report_[1-15].json files.
        No LLM generation needed - these files contain complete student performance data.
        """
        file_path = os.path.join(MOCK_DATA_DIR, "reports", f"exam_report_{exam_id}.json")
        
        if not os.path.exists(file_path):
            print(f"ERROR: Exam report file not found: {file_path}")
            return None
        
        try:
            print(f"LOADING EXAM REPORT: exam_report_{exam_id}.json")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ Successfully loaded report for {data.get('exam_info', {}).get('exam_name', f'Exam {exam_id}')}")
            return data
        except Exception as e:
            print(f"ERROR loading exam report: {e}")
            return None

    @staticmethod
    def get_student_summary(student_id):
        """
        Load pre-generated student summary directly from student_[1-5].json files.
        No LLM generation needed - these files contain complete exam history for each student.
        """
        file_path = os.path.join(MOCK_DATA_DIR, "students", f"student_{student_id}.json")
        
        if not os.path.exists(file_path):
            print(f"ERROR: Student summary file not found: {file_path}")
            return None
        
        try:
            print(f"LOADING STUDENT SUMMARY: student_{student_id}.json")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ Successfully loaded summary for {data.get('student_info', {}).get('student_name', f'Student {student_id}')}")
            return data
        except Exception as e:
            print(f"ERROR loading student summary: {e}")
            return None