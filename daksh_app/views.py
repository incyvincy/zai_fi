from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
import requests
import json

# PRATHAM API Configuration
PRATHAM_API_BASE_URL = "https://lms.prathamonline.com/api/api/"
PRATHAM_API_TOKEN = "D9skL3eS0P0jPv52xAigzbPA7WkqTQjdHj59Y1FeNWHv0lMq5c9jW2YkSn2D4LJr"


def get_api_headers():
    """
    Get headers for PRATHAM API requests
    """
    return {
        'X-API-TOKEN': PRATHAM_API_TOKEN,
        'Content-Type': 'application/json'
    }


class StudentListView(View):
    def get(self, request):
        return render(request, 'daksh_app/students.html')
    
    def post(self, request):
        try:
            url = f"{PRATHAM_API_BASE_URL}exam-insights/students"
            response = requests.post(url, headers=get_api_headers())
            
            if response.status_code != 200:
                return JsonResponse({'success': False, 'error': 'Failed to fetch students'}, status=response.status_code)

            api_json = response.json()
            data_array = api_json.get('data') if isinstance(api_json, dict) and 'data' in api_json else api_json
            count = len(data_array) if isinstance(data_array, list) else 0
            
            return JsonResponse({'success': True, 'data': data_array, 'count': count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ExamListView(View):
    def get(self, request):
        return render(request, 'daksh_app/exams.html')
    
    def post(self, request):
        try:
            url = f"{PRATHAM_API_BASE_URL}exam-insights/exams"
            response = requests.post(url, headers=get_api_headers())

            if response.status_code != 200:
                return JsonResponse({'success': False, 'error': 'Failed to fetch exams'}, status=response.status_code)

            api_json = response.json()
            data_array = api_json.get('data') if isinstance(api_json, dict) and 'data' in api_json else api_json
            
            # Map API keys to Frontend keys based on actual API format
            cleaned_data = []
            if isinstance(data_array, list):
                for item in data_array:
                    cleaned_item = {
                        # Map 'id' (API) to 'exam_id' (Frontend)
                        'exam_id': item.get('id') or item.get('exam_id') or item.get('ExamId'),
                        # Map 'name' (API) to 'exam_name' (Frontend)
                        'exam_name': item.get('name') or item.get('exam_name') or item.get('Name'),
                        'duration': item.get('duration', '120'),
                        'total_questions': item.get('total_questions') or item.get('total_question', 0)
                    }
                    cleaned_data.append(cleaned_item)
            
            return JsonResponse({'success': True, 'data': cleaned_data, 'count': len(cleaned_data)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ExamQuestionsView(View):
    def get(self, request, exam_id):
        return render(request, 'daksh_app/exam_questions.html', {'exam_id': exam_id})
    
    def post(self, request, exam_id):
        try:
            url = f"{PRATHAM_API_BASE_URL}exam-insights/{exam_id}/questions"
            response = requests.post(url, headers=get_api_headers())
            
            if response.status_code != 200:
                # Attempt to read error message from API
                try:
                    err_json = response.json()
                    err_msg = err_json.get('message', 'Failed to fetch questions')
                except:
                    err_msg = 'Failed to fetch questions'
                return JsonResponse({'success': False, 'error': err_msg}, status=response.status_code)

            api_json = response.json()
            data_array = api_json.get('data') if isinstance(api_json, dict) and 'data' in api_json else api_json
            
            # Map Questions Format based on actual API response
            cleaned_questions = []
            if isinstance(data_array, list):
                for q in data_array:
                    # Parse Options List into a Dictionary for frontend
                    options_map = {}
                    raw_options = q.get('options', [])
                    if isinstance(raw_options, list):
                        for idx, opt in enumerate(raw_options):
                            # API returns list of objects: [{'id':..., 'option': 'HTML...'}]
                            key_name = f"Option {idx + 1}"
                            # Extract text from 'option' key
                            val_text = opt.get('option', '') if isinstance(opt, dict) else str(opt)
                            options_map[key_name] = val_text

                    clean_q = {
                        # API uses 'question', frontend expects 'question_text'
                        'question_text': q.get('question') or q.get('question_text', 'N/A'),
                        'marks': q.get('marks', 1),
                        'options': options_map
                    }
                    cleaned_questions.append(clean_q)

            return JsonResponse({'success': True, 'exam_id': exam_id, 'data': cleaned_questions, 'count': len(cleaned_questions)})
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ExamReportView(View):
    def get(self, request):
        return render(request, 'daksh_app/exam_report.html')
    
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            exam_id = body.get('exam_id')
            
            url = f"{PRATHAM_API_BASE_URL}exam-insights/exam-report"
            response = requests.post(url, headers=get_api_headers(), json={'exam_id': exam_id})
            
            report_data = {}
            try:
                report_data = response.json()
            except:
                pass
                
            if response.status_code != 200:
                # Pass the actual API error message to the frontend
                error_message = report_data.get('message', 'Failed to fetch exam report from API')
                return JsonResponse({'success': False, 'error': error_message}, status=response.status_code)

            # Check for logical success: false inside 200 OK
            if isinstance(report_data, dict) and report_data.get('success') is False:
                return JsonResponse({'success': False, 'error': report_data.get('message', 'Unknown API Error')})

            return JsonResponse({'success': True, 'exam_id': exam_id, 'data': report_data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StudentSummaryView(View):
    def get(self, request):
        return render(request, 'daksh_app/student_summary.html')
    
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            student_id = body.get('student_id')
            url = f"{PRATHAM_API_BASE_URL}exam-insights/student-summary"
            response = requests.post(url, headers=get_api_headers(), json={'student_id': student_id})
            
            if response.status_code != 200:
                return JsonResponse({'success': False, 'error': 'Failed to fetch student summary'}, status=response.status_code)
                 
            return JsonResponse({'success': True, 'data': response.json()})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Keep existing views
def home(request):
    return render(request, 'daksh_app/home.html')