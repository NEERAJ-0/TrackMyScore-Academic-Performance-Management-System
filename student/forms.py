from django import forms
from django.contrib.auth.models import User
import re
from student.models import Profile

from .models import *


class SignupForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, initial="student")
    password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'role']

    def __init__(self, *args, show_role=False, **kwargs):
        """
        show_role: if False, remove the role field from the form (useful for public signup)
        """
        super().__init__(*args, **kwargs)
        if not show_role:
            # hide role input from UI but keep a default value for view logic
            self.fields.pop('role', None)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            # do not set profile role here blindly — view will handle it
        return user


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class CourseSearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'Enter Course'}))


class BatchSearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'Enter BatchNo'}))


class PaperSearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'Enter Papercode'}))


class StudentSearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'Enter StudentName'}))

class TransactionSearchForm(forms.Form):
    query = forms.CharField(
        label='Search',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter Student name or regno / other'})
    )


# ---- Model forms matching your models.py ----

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'courseid']  
        labels = {
            'courseid': 'Course ID',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MCA'}),
            'courseid': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MCA01'}),
        }

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name')
        courseid = cleaned.get('courseid')

        if name and not re.match(r'^[A-Za-z0-9\s&\-\(\)]+$', name):
            self.add_error('name', 'Course name contains invalid characters.')

        if courseid and not re.match(r'^[A-Z0-9\-\_]{2,12}$', str(courseid)):
            self.add_error('courseid', 'Course ID should be uppercase/digits/hyphen (2-12 chars).')

        return cleaned


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['course', 'name', 'year', 'is_active']
        widgets = {
            'course': forms.Select(attrs={
                'class': 'form-select'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2023-24-A'
            }),
            'year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2023-2024'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        return name

    def clean_year(self):
        year = self.cleaned_data.get('year', '').strip()

        if not year:
            raise forms.ValidationError("Year is required.")

        if not re.match(r'^\d{4}-\d{4}$', year):
            raise forms.ValidationError("Year should be in format YYYY-YYYY (e.g. 2023-2024).")

        return year


class PaperForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = ['code', 'name', 'paper_type', 'max_marks']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. MCA-101'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Paper Name'
            }),
            'paper_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Core / Elective / Lab'
            }),
            'max_marks': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '100'
            }),
        }

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('code')
        name = cleaned.get('name')
        max_marks = cleaned.get('max_marks')

        if code and not re.match(r'^[A-Z0-9\-\s]{2,16}$', code):
            self.add_error('code', 'Paper code should be uppercase letters/digits/hyphen and 2-16 chars.')

        if name and len(name) > 120:
            self.add_error('name', 'Paper name is too long (max 120).')

        if max_marks is not None:
            try:
                mm = int(max_marks)
            except (ValueError, TypeError):
                self.add_error('max_marks', 'Max marks must be an integer.')
            else:
                if mm <= 0 or mm > 1000:
                    self.add_error('max_marks', 'Max marks must be a positive number (reasonable limit).')

        return cleaned


class StudentForm(forms.ModelForm):
    # populate batches dynamically
    batch = forms.ModelChoiceField(queryset=Batch.objects.none(), widget=forms.Select(attrs={'class':'form-select'}))

    class Meta:
        model = Student
        fields = ['batch', 'regno', 'name', 'email', 'is_active']
        widgets = {
            'regno': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 23MCA001'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Student Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'student@example.com'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # show all batches by default 
        self.fields['batch'].queryset = Batch.objects.select_related('course').all()
        self.fields['batch'].empty_label = "Select batch"

    def clean(self):
        cleaned = super().clean()
        regno = cleaned.get('regno')
        name = cleaned.get('name')

        if regno and not re.match(r'^[A-Za-z0-9\-\_]+$', str(regno)):
            self.add_error('regno', 'Registration number can contain letters, digits, hyphen and underscore only.')

        if name and (len(name) > 100):
            self.add_error('name', 'Student name is too long (max 100).')

        return cleaned


class StudentMarkForm(forms.ModelForm):
    student = forms.ModelChoiceField(queryset=Student.objects.none(), widget=forms.Select(attrs={'class':'form-select'}))
    paper = forms.ModelChoiceField(queryset=Paper.objects.none(), widget=forms.Select(attrs={'class':'form-select'}))
    batch = forms.ModelChoiceField(queryset=Batch.objects.none(), widget=forms.Select(attrs={'class':'form-select'}))

    class Meta:
        model = StudentMark
        fields = ['student', 'paper', 'exam_type', 'batch', 'marks']
        widgets = {
            'exam_type': forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. Internal-I / External'}),
            'marks': forms.NumberInput(attrs={'class':'form-control','step':'0.01','placeholder':'Enter marks'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # populate selects
        self.fields['student'].queryset = Student.objects.select_related('batch__course').all().order_by('regno')
        self.fields['paper'].queryset = Paper.objects.all().order_by('code', 'name')
        self.fields['batch'].queryset = Batch.objects.select_related('course').all().order_by('course__courseid', 'name')
        self.fields['student'].empty_label = "Select student"
        self.fields['paper'].empty_label = "Select paper"
        self.fields['batch'].empty_label = "Select batch"

    def clean(self):
        cleaned = super().clean()
        marks = cleaned.get('marks')
        paper = cleaned.get('paper')

        # marks validation
        if marks is not None:
            try:
                m = float(marks)
            except (ValueError, TypeError):
                self.add_error('marks', 'Marks must be a number.')
                return cleaned

            if m < 0:
                self.add_error('marks', 'Marks cannot be negative.')

            if paper and hasattr(paper, 'max_marks'):
                try:
                    max_m = float(paper.max_marks)
                    if m > max_m:
                        self.add_error('marks', f'Marks cannot exceed the paper max ({paper.max_marks}).')
                except (ValueError, TypeError):
                    pass

        # uniqueness check (pre-DB)
        student = cleaned.get('student')
        exam_type = cleaned.get('exam_type')
        batch = cleaned.get('batch')
        if student and paper and exam_type and batch:
            qs = StudentMark.objects.filter(student=student, paper=paper, exam_type=exam_type, batch=batch)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(None, 'A mark entry for this student / paper / exam / batch already exists.')

        return cleaned