from . import views
from django.urls import path

urlpatterns = [
    # Existing routes
    path('', views.home, name='home'),    
    path('neo4j-test', views.neo4j_test, name='neo4j-test'),
    path('ingest/attempt/', views.IngestAttemptView.as_view(), name='ingest-attempt'),
    path('exam-insights/students', views.StudentListView.as_view(), name='student-list'),
    path('exam-insights/exams', views.ExamListView.as_view(), name='exam-list'),
    path('exam-insights/<int:exam_id>/questions', views.ExamQuestionsView.as_view(), name='exam-questions'),
    path('exam-insights/exam-report', views.ExamReportView.as_view(), name='exam-report'),
    path('exam-insights/student-summary', views.StudentSummaryView.as_view(), name='student-summary'),
]

