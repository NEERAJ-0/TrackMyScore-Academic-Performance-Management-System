from django.core.management.base import BaseCommand
from student.models import Course, Batch, Paper, Student, StudentMark
from django.utils import timezone
import random

class Command(BaseCommand):
    help = "Create sample data for TrackMyScore"

    def handle(self, *args, **options):
        # Courses
        c1, _ = Course.objects.get_or_create(courseid="MCA-FT", defaults={"name":"MCA Full Time"})
        c2, _ = Course.objects.get_or_create(courseid="BCA-FT", defaults={"name":"BCA Full Time"})

        # Batches
        b1, _ = Batch.objects.get_or_create(course=c1, name="MCA 2023-25", defaults={"year":"2023-2025"})
        b2, _ = Batch.objects.get_or_create(course=c2, name="BCA 2023-25", defaults={"year":"2023-2025"})

        # Papers
        p1, _ = Paper.objects.get_or_create(code="MCA101", defaults={"name":"Programming I", "max_marks":100})
        p2, _ = Paper.objects.get_or_create(code="MCA102", defaults={"name":"Data Structures", "max_marks":100})

        # Students
        s1, _ = Student.objects.get_or_create(regno="S2023001", defaults={"name":"Alice", "email":"alice@example.com", "batch":b1})
        s2, _ = Student.objects.get_or_create(regno="S2023002", defaults={"name":"Bob", "email":"bob@example.com", "batch":b1})

        # Marks (some random)
        for student in (s1, s2):
            for paper in (p1, p2):
                for exam in ("Internal-I","Internal-II","External"):
                    StudentMark.objects.get_or_create(
                        student=student,
                        paper=paper,
                        exam_type=exam,
                        batch=b1,
                        defaults={"marks": random.randint(40,95), "created_at": timezone.now()}
                    )

        self.stdout.write(self.style.SUCCESS("Sample data created."))
