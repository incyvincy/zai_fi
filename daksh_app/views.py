from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
import json
import traceback

# Import the AI Service for dynamic data generation
from .ai_service import AIService


class StudentListView(View):
    def get(self, request):
        return render(request, 'daksh_app/students.html')
    
    def post(self, request):
        try:
            # Dynamically generate students via LLM
            data = AIService.get_students()
            return JsonResponse({'success': True, 'data': data, 'count': len(data)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ExamListView(View):
    def get(self, request):
        return render(request, 'daksh_app/exams.html')
    
    def post(self, request):
        try:
            # Dynamically generate exams via LLM
            data = AIService.get_exams()
            return JsonResponse({'success': True, 'data': data, 'count': len(data)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ExamQuestionsView(View):
    def get(self, request, exam_id):
        return render(request, 'daksh_app/exam_questions.html', {'exam_id': exam_id})
    
    def post(self, request, exam_id):
        try:
            # Dynamically generate questions for this specific exam
            data = AIService.get_questions(exam_id)
            return JsonResponse({'success': True, 'exam_id': exam_id, 'data': data, 'count': len(data)})
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ExamReportView(View):
    def get(self, request):
        return render(request, 'daksh_app/exam_report.html')
    
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            exam_id = body.get('exam_id')
            
            if not exam_id:
                return JsonResponse({'success': False, 'error': 'exam_id is required'}, status=400)
            
            # Load pre-generated exam report (includes all student data)
            data = AIService.get_exam_report(exam_id)
            
            if data is None:
                return JsonResponse({'success': False, 'error': f'Exam report {exam_id} not found'}, status=404)
            
            return JsonResponse(data)  # Return the complete report structure
        except Exception as e:
            print(f"Error in ExamReportView: {e}")
            print(traceback.format_exc())
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
            
            # Load pre-generated student summary (includes all 15 exam performances)
            data = AIService.get_student_summary(student_id)
            
            if data is None:
                return JsonResponse({'success': False, 'error': f'Student summary {student_id} not found'}, status=404)
            
            return JsonResponse(data)  # Return the complete student summary structure
        except Exception as e:
            print(f"Error in StudentSummaryView: {e}")
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Keep existing views
def home(request):
    return render(request, 'daksh_app/home.html')