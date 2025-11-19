from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("staff", "Staff"),
        ("student", "Student"),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="student")

    def __str__(self):
        return f"{self.user.username} ({self.role})"

@receiver(post_save, sender=User)
def ensure_profile_for_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

class Course(models.Model):
    name = models.CharField(max_length=64, unique=True)  
    courseid = models.CharField(max_length=12, unique=True)  
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self): return f"{self.courseid} - {self.name}"


class Batch(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='batches')
    name = models.CharField(max_length=32)   
    year = models.CharField(max_length=9)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("course", "name"),)

    def __str__(self): return f"{self.name} - {self.course}"


class Paper(models.Model):
    code = models.CharField(max_length=16, unique=True)  
    name = models.CharField(max_length=120)
    paper_type = models.CharField(max_length=30, blank=True)  
    max_marks = models.IntegerField(default=100)

    def __str__(self): return f"{self.name} ({self.code})"


class Student(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name='students')
    regno = models.CharField(max_length=32, unique=True)  
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self): return f"{self.regno} - {self.name}"


class StudentMark(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    paper = models.ForeignKey(Paper, on_delete=models.PROTECT)
    exam_type = models.CharField(max_length=32)   
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT)
    marks = models.DecimalField(max_digits=5, decimal_places=2)  
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = (('student','paper','exam_type','batch'),)

    def __str__(self): return f"{self.student.regno} | {self.paper.name} : {self.marks}"
