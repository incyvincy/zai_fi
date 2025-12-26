import os
import json
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# Import Neo4j service layer (Day 3 - API Connector)
from . import neo4j_service


# --- HELPER FUNCTION ---
def get_mock_data(subpath):
    """
    Helper to safely load JSON data from the studybud/mock_data directory.
    """
    # Construct absolute path: BASE_DIR/studybud/mock_data/subpath
    file_path = os.path.join(settings.BASE_DIR, 'mock_data', subpath)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in file: {file_path}")
        return None


# ==========================================
# DAY 3: INGEST API (POST /ingest/attempt/)
# ==========================================
@method_decorator(csrf_exempt, name='dispatch')
class IngestAttemptView(View):
    """
    Minimal API endpoint to ingest attempt data into Neo4j.
    
    POST /ingest/attempt/
    
    JSON Body:
    {
        "student_id": 1,
        "student_name": "Alice",      // optional
        "cohort": "Batch-A",          // optional
        "exam_id": 1,
        "exam_name": "JEE Mock 1",    // optional
        "question_id": 1,
        "question_text": "A block...",
        "selected_option": "A",
        "correct_option": "B",
        "marks": 4,
        "time_spent": 45,             // nullable (offline exams)
        "concept": "Mechanics",       // optional (flags AI tagging if missing)
        "skill": "Application",       // optional
        "difficulty": "Medium"        // optional
    }
    
    Response:
    {
        "success": true,
        "needs_ai_tagging": true,     // true if metadata missing
        "question_text": "..."        // included if needs_ai_tagging
    }
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        
        # Validate required fields
        required = ['student_id', 'exam_id', 'question_id', 'question_text', 'selected_option', 'correct_option']
        missing = [f for f in required if f not in data]
        if missing:
            return JsonResponse({
                'success': False, 
                'error': f'Missing required fields: {missing}'
            }, status=400)
        
        # Extract data
        student_id = data['student_id']
        exam_id = data['exam_id']
        question_id = data['question_id']
        question_text = data['question_text']
        
        # Global question ID: exam_id * 1000 + question_id
        global_question_id = exam_id * 1000 + question_id
        
        # Determine outcome
        if data.get('selected_option') == data.get('correct_option'):
            outcome = 'correct'
        elif data.get('selected_option') is None or data.get('selected_option') == '':
            outcome = 'skipped'
        else:
            outcome = 'incorrect'
        
        # Time is nullable (offline exams)
        time_spent = data.get('time_spent')  # None if not provided
        
        # Optional metadata
        concept = data.get('concept') or data.get('topic')
        skill = data.get('skill') or data.get('skill_required')
        difficulty = data.get('difficulty')
        
        # --- CREATE NODES ---
        
        # 1. Student
        neo4j_service.create_student_if_not_exists(
            student_id=student_id,
            name=data.get('student_name'),
            cohort_name=data.get('cohort')
        )
        
        # 2. Exam
        neo4j_service.create_exam_if_not_exists(
            exam_id=exam_id,
            name=data.get('exam_name')
        )
        
        # 3. Question (with optional tags)
        question_result = neo4j_service.create_question_if_not_exists(
            global_question_id=global_question_id,
            text=question_text,
            concept_name=concept,
            skill_name=skill,
            difficulty_name=difficulty
        )
        
        # 4. Link Question to Exam
        neo4j_service.link_question_to_exam(exam_id, global_question_id)
        
        # 5. Create Attempt
        neo4j_service.create_attempt(
            student_id=student_id,
            question_id=global_question_id,
            outcome=outcome,
            time_spent_seconds=time_spent
        )
        
        # Response
        return JsonResponse({
            'success': True,
            'outcome': outcome,
            'needs_ai_tagging': question_result['needs_ai_tagging'],
            'question_text': question_result['question_text']  # For AI tagging queue
        })


# --- EXISTING VIEWS ---


class StudentListView(View):
    def get(self, request):
        return render(request, 'daksh_app/students.html')
    
    def post(self, request):
        # Load directly from students.json
        data = get_mock_data(os.path.join('students', 'students.json'))
        
        if data:
            return JsonResponse({'success': True, 'data': data, 'count': len(data)})
        return JsonResponse({'success': False, 'error': 'Students data not found'}, status=404)


class ExamListView(View):
    def get(self, request):
        return render(request, 'daksh_app/exams.html')
    
    def post(self, request):
        # Load directly from exams.json
        data = get_mock_data(os.path.join('exams', 'exams.json'))
        
        if data:
            return JsonResponse({'success': True, 'data': data, 'count': len(data)})
        return JsonResponse({'success': False, 'error': 'Exams data not found'}, status=404)


class ExamQuestionsView(View):
    def get(self, request, exam_id):
        return render(request, 'daksh_app/exam_questions.html', {'exam_id': exam_id})
    
    def post(self, request, exam_id):
        # Load specific question file: questions_exam_1.json
        filename = f"questions_exam_{exam_id}.json"
        data = get_mock_data(os.path.join('exams', filename))
        
        if data:
            return JsonResponse({'success': True, 'exam_id': exam_id, 'data': data, 'count': len(data)})
        return JsonResponse({'success': False, 'error': f'Questions for exam {exam_id} not found'}, status=404)


class ExamReportView(View):
    def get(self, request):
        return render(request, 'daksh_app/exam_report.html')
    
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            exam_id = body.get('exam_id')
            
            if not exam_id:
                return JsonResponse({'success': False, 'error': 'exam_id is required'}, status=400)
            
            # Load specific report file: exam_report_1.json
            filename = f"exam_report_{exam_id}.json"
            data = get_mock_data(os.path.join('reports', filename))
            
            if data:
                return JsonResponse(data)
            return JsonResponse({'success': False, 'error': f'Report for exam {exam_id} not found'}, status=404)
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StudentSummaryView(View):
    def get(self, request):
        return render(request, 'daksh_app/student_summary.html')
    
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            student_id = body.get('student_id')
            
            if not student_id:
                return JsonResponse({'success': False, 'error': 'student_id is required'}, status=400)
            
            # Load specific student file: student_1.json
            filename = f"student_{student_id}.json"
            data = get_mock_data(os.path.join('students', filename))
            
            if data:
                return JsonResponse(data)
            return JsonResponse({'success': False, 'error': f'Summary for student {student_id} not found'}, status=404)
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

def home(request):
    return render(request, 'daksh_app/home.html')