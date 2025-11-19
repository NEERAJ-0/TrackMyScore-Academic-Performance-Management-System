from rest_framework import serializers
from .models import Student, StudentMark, Paper, Batch, Course

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "courseid", "name"]

class BatchSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(write_only=True, source="course", queryset=Course.objects.all())

    class Meta:
        model = Batch
        fields = ["id", "name", "year", "is_active", "course", "course_id"]

class PaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paper
        fields = ["id", "code", "name", "paper_type", "max_marks"]

class StudentSerializer(serializers.ModelSerializer):
    batch = BatchSerializer(read_only=True)
    batch_id = serializers.PrimaryKeyRelatedField(write_only=True, source="batch", queryset=Batch.objects.all())

    class Meta:
        model = Student
        fields = ["id", "regno", "name", "email", "is_active", "created_at", "batch", "batch_id"]
        read_only_fields = ["created_at"]

class StudentMarkSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(write_only=True, source="student", queryset=Student.objects.all())

    paper = PaperSerializer(read_only=True)
    paper_id = serializers.PrimaryKeyRelatedField(write_only=True, source="paper", queryset=Paper.objects.all())

    batch = BatchSerializer(read_only=True)
    batch_id = serializers.PrimaryKeyRelatedField(write_only=True, source="batch", queryset=Batch.objects.all())

    class Meta:
        model = StudentMark
        fields = ["id", "student", "student_id", "paper", "paper_id",
                  "exam_type", "batch", "batch_id", "marks", "created_at"]
        read_only_fields = ["created_at"]

    def validate_marks(self, value):
        # ensure not negative
        if value < 0:
            raise serializers.ValidationError("Marks cannot be negative.")
        # if paper provided in context (paper_id), check max_marks
        paper = None
        if "paper" in self.initial_data:
            # but we expect paper_id field; the PrimaryKeyRelatedField will set the instance later
            pass
        # if instance is being created, validated_data will have 'paper'
        paper_obj = self.initial_data.get("paper_id") or self.initial_data.get("paper")
        # attempt to resolve numeric max if we can
        try:
            pid = int(paper_obj) if paper_obj else None
            if pid:
                p = Paper.objects.filter(pk=pid).first()
                if p and p.max_marks is not None and float(value) > float(p.max_marks):
                    raise serializers.ValidationError(f"Marks cannot exceed paper max ({p.max_marks}).")
        except (ValueError, TypeError):
            # ignore
            pass
        return value

    def validate(self, attrs):
        # ensure unique_together (student, paper, exam_type, batch)
        student = attrs.get("student") or getattr(self.instance, "student", None)
        paper = attrs.get("paper") or getattr(self.instance, "paper", None)
        exam_type = attrs.get("exam_type") or getattr(self.instance, "exam_type", None)
        batch = attrs.get("batch") or getattr(self.instance, "batch", None)
        if student and paper and exam_type and batch:
            qs = StudentMark.objects.filter(student=student, paper=paper, exam_type=exam_type, batch=batch)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("A marks entry for this student/paper/exam/batch already exists.")
        return attrs
