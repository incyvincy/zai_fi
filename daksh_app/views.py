import os
import json
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from studybud.neo4j_driver import run_cypher

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

# --- VIEWS ---


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


# Neo4j Connection Test View
def neo4j_test(request):
    """
    Test Neo4j database connection.
    Expected output: [{"ok": 1}]
    """
    try:
        data = run_cypher("RETURN 1 AS ok")
        return JsonResponse({
            'success': True,
            'message': '✅ Neo4j connection successful!',
            'data': data
        }, safe=False)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': '❌ Neo4j connection failed!'
        }, status=500)


def home(request):
    return render(request, 'daksh_app/home.html')