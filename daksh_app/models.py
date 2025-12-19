from .database import Neo4jConnection
from datetime import datetime


class BaseNode:
    """
    Base class for Neo4j nodes
    """
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def create(cls, properties):
        """
        Create a node in Neo4j
        """
        label = cls.__name__
        query = f"""
        CREATE (n:{label} $properties)
        RETURN n
        """
        result = Neo4jConnection.execute_write(query, {'properties': properties})
        return cls(**properties)

    @classmethod
    def find_by_id(cls, node_id):
        """
        Find node by ID
        """
        label = cls.__name__
        query = f"""
        MATCH (n:{label})
        WHERE n.id = $id
        RETURN n
        """
        result = Neo4jConnection.execute_read(query, {'id': node_id})
        if result:
            return cls(**result[0]['n'])
        return None

    @classmethod
    def all(cls):
        """
        Get all nodes of this type
        """
        label = cls.__name__
        query = f"MATCH (n:{label}) RETURN n"
        result = Neo4jConnection.execute_read(query)
        return [cls(**record['n']) for record in result]

    def save(self):
        """
        Save or update node
        """
        label = self.__class__.__name__
        properties = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        
        if hasattr(self, 'id') and self.id:
            # Update existing node
            query = f"""
            MATCH (n:{label})
            WHERE n.id = $id
            SET n += $properties
            RETURN n
            """
            Neo4jConnection.execute_write(query, {'id': self.id, 'properties': properties})
        else:
            # Create new node
            query = f"""
            CREATE (n:{label} $properties)
            RETURN n
            """
            Neo4jConnection.execute_write(query, {'properties': properties})


class Student(BaseNode):
    """
    Student node in Neo4j graph database
    """
    def __init__(self, student_id=None, student_name=None, enrollment_id=None, **kwargs):
        self.student_id = student_id
        self.student_name = student_name
        self.enrollment_id = enrollment_id
        super().__init__(**kwargs)

    @classmethod
    def create_or_update(cls, student_data):
        """
        Create or update student node
        """
        query = """
        MERGE (s:Student {student_id: $student_id})
        SET s.student_name = $student_name,
            s.enrollment_id = $enrollment_id,
            s.updated_at = datetime()
        RETURN s
        """
        result = Neo4jConnection.execute_write(query, student_data)
        return cls(**student_data)

    def get_exams(self):
        """
        Get all exams attempted by this student
        """
        query = """
        MATCH (s:Student {student_id: $student_id})-[:ATTEMPTED]->(e:Exam)
        RETURN e
        """
        result = Neo4jConnection.execute_read(query, {'student_id': self.student_id})
        return [Exam(**record['e']) for record in result]


class Exam(BaseNode):
    """
    Exam node in Neo4j graph database
    """
    def __init__(self, exam_id=None, exam_name=None, total_questions=None, duration=None, **kwargs):
        self.exam_id = exam_id
        self.exam_name = exam_name
        self.total_questions = total_questions
        self.duration = duration
        super().__init__(**kwargs)

    @classmethod
    def create_or_update(cls, exam_data):
        """
        Create or update exam node
        """
        query = """
        MERGE (e:Exam {exam_id: $exam_id})
        SET e.exam_name = $exam_name,
            e.total_questions = $total_questions,
            e.duration = $duration,
            e.updated_at = datetime()
        RETURN e
        """
        result = Neo4jConnection.execute_write(query, exam_data)
        return cls(**exam_data)

    def get_questions(self):
        """
        Get all questions for this exam
        """
        query = """
        MATCH (e:Exam {exam_id: $exam_id})-[:HAS_QUESTION]->(q:Question)
        RETURN q
        ORDER BY q.question_id
        """
        result = Neo4jConnection.execute_read(query, {'exam_id': self.exam_id})
        return [Question(**record['q']) for record in result]

    def add_question(self, question_data):
        """
        Add a question to this exam
        """
        query = """
        MATCH (e:Exam {exam_id: $exam_id})
        MERGE (q:Question {question_id: $question_id})
        SET q += $properties
        MERGE (e)-[:HAS_QUESTION]->(q)
        RETURN q
        """
        params = {
            'exam_id': self.exam_id,
            'question_id': question_data['question_id'],
            'properties': question_data
        }
        Neo4jConnection.execute_write(query, params)


class Question(BaseNode):
    """
    Question node in Neo4j graph database
    """
    def __init__(self, question_id=None, question_text=None, options=None, 
                 correct_options=None, marks=None, **kwargs):
        self.question_id = question_id
        self.question_text = question_text
        self.options = options
        self.correct_options = correct_options
        self.marks = marks
        super().__init__(**kwargs)


class Response(BaseNode):
    """
    Student response to exam questions
    """
    def __init__(self, response_id=None, student_test_id=None, question_id=None, 
                 selected_option=None, correct_options=None, time_spent=None, 
                 response_status=None, **kwargs):
        self.response_id = response_id
        self.student_test_id = student_test_id
        self.question_id = question_id
        self.selected_option = selected_option
        self.correct_options = correct_options
        self.time_spent = time_spent
        self.response_status = response_status
        super().__init__(**kwargs)

    @classmethod
    def create_response(cls, response_data):
        """
        Create a response and link to student test and question
        """
        query = """
        MATCH (st:StudentTest {student_test_id: $student_test_id})
        MATCH (q:Question {question_id: $question_id})
        CREATE (r:Response $properties)
        CREATE (st)-[:HAS_RESPONSE]->(r)
        CREATE (r)-[:ANSWERED]->(q)
        RETURN r
        """
        result = Neo4jConnection.execute_write(query, {
            'student_test_id': response_data['student_test_id'],
            'question_id': response_data['question_id'],
            'properties': response_data
        })
        return cls(**response_data)


class StudentTest(BaseNode):
    """
    Represents a student's attempt at an exam
    """
    def __init__(self, student_test_id=None, student_id=None, exam_id=None,
                 total_questions=None, total_attempt=None, total_marks=None,
                 correct_answers=None, incorrect_answers=None, score=None,
                 time_spent=None, **kwargs):
        self.student_test_id = student_test_id
        self.student_id = student_id
        self.exam_id = exam_id
        self.total_questions = total_questions
        self.total_attempt = total_attempt
        self.total_marks = total_marks
        self.correct_answers = correct_answers
        self.incorrect_answers = incorrect_answers
        self.score = score
        self.time_spent = time_spent
        super().__init__(**kwargs)

    @classmethod
    def create_or_update(cls, test_data):
        """
        Create or update student test attempt
        """
        query = """
        MERGE (st:StudentTest {student_test_id: $student_test_id})
        SET st.student_id = $student_id,
            st.exam_id = $exam_id,
            st.total_questions = $total_questions,
            st.total_attempt = $total_attempt,
            st.total_marks = $total_marks,
            st.correct_answers = $correct_answers,
            st.incorrect_answers = $incorrect_answers,
            st.score = $score,
            st.time_spent = $time_spent,
            st.updated_at = datetime()
        WITH st
        MATCH (s:Student {student_id: $student_id})
        MATCH (e:Exam {exam_id: $exam_id})
        MERGE (s)-[:ATTEMPTED]->(st)
        MERGE (st)-[:FOR_EXAM]->(e)
        RETURN st
        """
        result = Neo4jConnection.execute_write(query, test_data)
        return cls(**test_data)

    def add_response(self, response_data):
        """
        Add a question response to this student test
        """
        response_data['student_test_id'] = self.student_test_id
        return Response.create_response(response_data)

    def get_responses(self):
        """
        Get all responses for this student test
        """
        query = """
        MATCH (st:StudentTest {student_test_id: $student_test_id})-[:HAS_RESPONSE]->(r:Response)
        RETURN r
        ORDER BY r.question_id
        """
        result = Neo4jConnection.execute_read(query, {'student_test_id': self.student_test_id})
        return [Response(**record['r']) for record in result]


class ExamReportProcessor:
    """
    Helper class to process exam report data and store in Neo4j
    """
    
    @staticmethod
    def process_exam_report(report_data):
        """
        Process the complete exam report and store in Neo4j
        
        Args:
            report_data (dict): The exam report data with structure:
                {
                    "success": bool,
                    "exam_info": {...},
                    "students_report": [...]
                }
        
        Returns:
            dict: Summary of processed data
        """
        if not report_data.get('success'):
            return {'success': False, 'message': 'Report data marked as unsuccessful'}
        
        # Process exam info
        exam_info = report_data.get('exam_info', {})
        exam = Exam.create_or_update(exam_info)
        
        # Process each student report
        students_processed = 0
        responses_processed = 0
        
        for student_report in report_data.get('students_report', []):
            # Process student info
            student_info = student_report.get('student_info', {})
            if student_info:
                Student.create_or_update(student_info)
            
            # Process student test
            test_data = {
                'student_test_id': student_report.get('student_test_id'),
                'student_id': student_info.get('student_id'),
                'exam_id': exam_info.get('exam_id'),
                'total_questions': student_report.get('total_questions'),
                'total_attempt': student_report.get('total_attempt'),
                'total_marks': student_report.get('total_marks'),
                'correct_answers': student_report.get('correct_answers'),
                'incorrect_answers': student_report.get('incorrect_answers'),
                'score': student_report.get('score'),
                'time_spent': student_report.get('time_spent')
            }
            
            student_test = StudentTest.create_or_update(test_data)
            students_processed += 1
            
            # Process each question response
            for question_response in student_report.get('questions', []):
                # Create/update question if it has correct_options
                if question_response.get('correct_options') is not None:
                    question_data = {
                        'question_id': question_response.get('question_id'),
                        'correct_options': question_response.get('correct_options')
                    }
                    exam.add_question(question_data)
                
                # Create response
                response_data = {
                    'student_test_id': student_report.get('student_test_id'),
                    'question_id': question_response.get('question_id'),
                    'selected_option': question_response.get('selected_option'),
                    'correct_options': question_response.get('correct_options'),
                    'time_spent': question_response.get('time_spent'),
                    'response_status': question_response.get('response_status')
                }
                
                student_test.add_response(response_data)
                responses_processed += 1
        
        return {
            'success': True,
            'exam_id': exam_info.get('exam_id'),
            'exam_name': exam_info.get('exam_name'),
            'students_processed': students_processed,
            'responses_processed': responses_processed
        }
