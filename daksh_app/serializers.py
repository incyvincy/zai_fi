"""
Custom serializers for Neo4j graph database models
Not using Django's ModelSerializer since we're not using SQL models
"""


class BaseSerializer:
    """
    Base serializer for graph database objects
    """
    fields = []

    def __init__(self, instance=None, data=None, many=False):
        self.instance = instance
        self.data_input = data
        self.many = many
        self._validated_data = None

    def to_dict(self, obj):
        """
        Convert object to dictionary
        """
        result = {}
        for field in self.fields:
            if hasattr(obj, field):
                result[field] = getattr(obj, field)
        return result

    @property
    def data(self):
        """
        Get serialized data
        """
        if self.instance is not None:
            if self.many:
                return [self.to_dict(item) for item in self.instance]
            return self.to_dict(self.instance)
        return self._validated_data

    def is_valid(self):
        """
        Validate input data
        """
        if self.data_input is None:
            return False
        self._validated_data = self.data_input
        return True

    @property
    def validated_data(self):
        """
        Get validated data
        """
        return self._validated_data


class StudentSerializer(BaseSerializer):
    """
    Serializer for Student nodes
    """
    fields = ['student_id', 'student_name', 'enrollment_id']

    def to_dict(self, obj):
        """
        Convert Student object to dictionary
        """
        return {
            'student_id': getattr(obj, 'student_id', None),
            'student_name': getattr(obj, 'student_name', None),
            'enrollment_id': getattr(obj, 'enrollment_id', None),
        }


class ExamSerializer(BaseSerializer):
    """
    Serializer for Exam nodes
    """
    fields = ['exam_id', 'exam_name', 'total_questions', 'duration']

    def to_dict(self, obj):
        """
        Convert Exam object to dictionary
        """
        return {
            'exam_id': getattr(obj, 'exam_id', None),
            'exam_name': getattr(obj, 'exam_name', None),
            'total_questions': getattr(obj, 'total_questions', None),
            'duration': getattr(obj, 'duration', None),
        }


class QuestionSerializer(BaseSerializer):
    """
    Serializer for Question nodes
    """
    fields = ['question_id', 'question_text', 'options', 'correct_options', 'marks']

    def to_dict(self, obj):
        """
        Convert Question object to dictionary
        """
        return {
            'question_id': getattr(obj, 'question_id', None),
            'question_text': getattr(obj, 'question_text', None),
            'options': getattr(obj, 'options', None),
            'correct_options': getattr(obj, 'correct_options', None),
            'marks': getattr(obj, 'marks', None),
        }


class ResponseSerializer(BaseSerializer):
    """
    Serializer for Response nodes
    """
    fields = ['response_id', 'student_test_id', 'question_id', 
              'selected_option', 'correct_options', 'time_spent', 'response_status']

    def to_dict(self, obj):
        """
        Convert Response object to dictionary
        """
        return {
            'response_id': getattr(obj, 'response_id', None),
            'student_test_id': getattr(obj, 'student_test_id', None),
            'question_id': getattr(obj, 'question_id', None),
            'selected_option': getattr(obj, 'selected_option', None),
            'correct_options': getattr(obj, 'correct_options', None),
            'time_spent': getattr(obj, 'time_spent', None),
            'response_status': getattr(obj, 'response_status', None),
        }


class StudentTestSerializer(BaseSerializer):
    """
    Serializer for StudentTest nodes
    """
    fields = ['student_test_id', 'student_id', 'exam_id', 'total_questions',
              'total_attempt', 'total_marks', 'correct_answers', 'incorrect_answers',
              'score', 'time_spent']

    def to_dict(self, obj):
        """
        Convert StudentTest object to dictionary
        """
        return {
            'student_test_id': getattr(obj, 'student_test_id', None),
            'student_id': getattr(obj, 'student_id', None),
            'exam_id': getattr(obj, 'exam_id', None),
            'total_questions': getattr(obj, 'total_questions', None),
            'total_attempt': getattr(obj, 'total_attempt', None),
            'total_marks': getattr(obj, 'total_marks', None),
            'correct_answers': getattr(obj, 'correct_answers', None),
            'incorrect_answers': getattr(obj, 'incorrect_answers', None),
            'score': getattr(obj, 'score', None),
            'time_spent': getattr(obj, 'time_spent', None),
        }


class ExamReportSerializer(BaseSerializer):
    """
    Serializer for exam report data
    """
    def to_dict(self, obj):
        """
        Convert exam report to dictionary
        """
        if isinstance(obj, dict):
            return obj
        return super().to_dict(obj)


class StudentSummarySerializer(BaseSerializer):
    """
    Serializer for student summary data
    """
    def to_dict(self, obj):
        """
        Convert student summary to dictionary
        """
        if isinstance(obj, dict):
            return obj
        return super().to_dict(obj)
