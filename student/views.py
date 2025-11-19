from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import  Avg, Count, Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import csv
from functools import wraps
from django.http import HttpResponseForbidden

from .models import *
from .forms import *


# --- auth + master ---
@login_required
def master(request):
    return render(request, "master.html")

def role_required(roles):
    """
    Decorator to require user's profile.role to be one of roles.
    Usage: @login_required @role_required(['admin'])
    """
    def _check(user):
        prof = getattr(user, "profile", None)
        return bool(prof and prof.role in roles)

    def decorator(view_func):
        decorated = user_passes_test(_check)(view_func)
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return decorated(request, *args, **kwargs)  # will redirect to login
            prof = getattr(request.user, "profile", None)
            if not (prof and prof.role in roles):
                return HttpResponseForbidden("Forbidden")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

@login_required
@role_required(['admin'])
def admin_create_user(request):
    """
    Admin-only page to create users and set role (admin/staff/student).
    Uses SignupForm(show_role=True)
    """
    if request.method == "POST":
        form = SignupForm(request.POST, show_role=True)
        if form.is_valid():
            user = form.save(commit=False)
            pwd = form.cleaned_data.get('password')
            if pwd:
                user.set_password(pwd)
            user.save()

            # set profile role
            role_to_set = form.cleaned_data.get('role') or 'student'
            if role_to_set not in dict(Profile.ROLE_CHOICES):
                role_to_set = 'student'
            Profile.objects.update_or_create(user=user, defaults={"role": role_to_set})

            messages.success(request, f"User {user.username} created as {role_to_set}.")
            # stay on the same page so admin can create multiple users
            return redirect('admin_create_user')
        else:
            messages.error(request, "Please fix the form errors.")
    else:
        form = SignupForm(show_role=True)

    return render(request, "admin_create_user.html", {"form": form})


def user_signup(request):
    if request.method == "POST":
        # decide whether role should be shown for this request
        show_role = False
        if request.user.is_authenticated:
            prof = getattr(request.user, "profile", None)
            if prof and prof.role == "admin":
                show_role = True

        form = SignupForm(request.POST, show_role=show_role)
        if form.is_valid():
            user = form.save(commit=False)
            pwd = form.cleaned_data.get('password')
            if pwd: user.set_password(pwd)
            user.save()

            # set role: if admin submitted a role and show_role True, use it
            role_to_set = 'student'
            if show_role:
                submitted_role = form.cleaned_data.get('role')
                if submitted_role in dict(Profile.ROLE_CHOICES):
                    role_to_set = submitted_role

            Profile.objects.update_or_create(user=user, defaults={"role": role_to_set})
            messages.success(request, "User created. Please login.")
            return redirect('login')
    else:
        show_role = False
        if request.user.is_authenticated and getattr(request.user, "profile", None) and request.user.profile.role == "admin":
            show_role = True
        form = SignupForm(show_role=show_role)

    return render(request, "signup.html", {"form": form, "show_role": show_role})

def user_login(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                # Redirect based on role
                role = getattr(user, "profile", None) and user.profile.role or "student"
                if role == "admin":
                    return redirect('master')
                if role == "staff":
                    return redirect('master')   # staff goes to same master 
                return redirect('student_dashboard')
            else:
                messages.error(request, "Invalid credentials.")
    else:
        form = LoginForm()
    return render(request, "login.html", {"form": form})

@login_required
def user_logout(request):
    logout(request)
    return redirect('login')

@login_required
@role_required(['student'])
def student_dashboard(request):
    """
    Student dashboard:
     - Students see their own dashboard by default.
     - If they enter a RegNo in the input, we attempt to find that student and show it
       (this enables download-by-RegNo from the UI).
    NOTE: If you want to forbid students from viewing others, revert the small block
    that allows requested_regno for student role.
    """
    user = request.user
    profile = getattr(user, "profile", None)

    requested_regno = request.GET.get("regno", "").strip()
    student = None

    # find helper 
    def find_student(regno):
        r = regno.strip()
        s = Student.objects.filter(regno__iexact=r).first()
        if s:
            return s
        return Student.objects.filter(regno__icontains=r).first()

    # If the logged-in user has a Student record, fetch it
    logged_user_student = find_student(user.username) if user.username else None

    # --- RULES ---
    # By default show own student record (if linked)
    student = logged_user_student

    # If a regno is entered:
    if requested_regno:
        # ALLOW students to lookup by regno (so they can download other's CSV if you want)
        # If you want to prohibit this, replace the next block with the commented alternative.
        student = find_student(requested_regno)
        if not student:
            messages.info(request, f"No student found for RegNo '{requested_regno}'.")
            # keep student as logged_user_student (so dashboard still shows own)
            student = logged_user_student

        # ---------- ALTERNATIVE: Restrict students to only their own regno ----------
        # if requested_regno.lower() != (user.username or "").lower():
        #     messages.warning(request, "You can only view your own results.")
        #     requested_regno = ""
        #     student = logged_user_student
        # ---------------------------------------------------------------------------

    # If still no student found at all, render empty dashboard
    if not student:
        return render(request, "student_dashboard.html", {
            "student": None,
            "requested_regno": requested_regno,
            "last_marks": [],
            "avg_mark": 0,
            "total_tests": 0,
            "pass_percent": 0,
            "subject_stats": [],
        })

    # Compute marks and stats for `student`
    marks_qs = StudentMark.objects.filter(student=student).select_related("paper", "batch")
    last_marks = marks_qs.order_by("-created_at")[:5]
    agg = marks_qs.aggregate(avg=Avg("marks"), total=Count("id"))
    avg_mark = agg.get("avg") or 0
    total_tests = agg.get("total") or 0

    # pass % using paper.max_marks (40% rule)
    passed = 0
    total = 0
    for m in marks_qs:
        total += 1
        try:
            if m.paper and m.paper.max_marks and float(m.marks) >= 0.35 * float(m.paper.max_marks):
                passed += 1
        except Exception:
            pass
    pass_percent = (passed / total * 100) if total else 0

    subject_stats = marks_qs.values("paper__name").annotate(
        avg=Avg("marks"),
        taken=Count("id")
    ).order_by("-avg")[:6]

    return render(request, "student_dashboard.html", {
        "student": student,
        "requested_regno": requested_regno,
        "last_marks": last_marks,
        "avg_mark": round(avg_mark, 2),
        "total_tests": total_tests,
        "pass_percent": round(pass_percent, 1),
        "subject_stats": subject_stats,
    })

# ----- Course CRUD -----
# ---------- Insert ----------
@login_required
@role_required(['admin','staff'])
def insertcourse(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Course added successfully.")
            return redirect('insertcourse')
    else:
        form = CourseForm()

    return render(request, "course/insertcourse.html", {"form": form})


# ---------- Delete ----------
@require_POST
@login_required
@role_required(['admin'])
def delete1(request, pk):
    obj = get_object_or_404(Course, pk=pk)
    obj.delete()
    messages.success(request, "Course deleted successfully.")
    return redirect('deletecourse')

@login_required
@role_required(['admin'])
def deletecourse(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Course.objects.all().order_by('courseid')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(courseid__icontains=q))

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "course/deletecourse.html", {"page_obj": page_obj, "query": q})



# ---------- Update ----------
@login_required
@role_required(['admin','staff'])
def update1(request, course_id):
    course = get_object_or_404(Course, pk=course_id)

    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated successfully.")
            return redirect("updatecourse")
    else:
        form = CourseForm(instance=course)

    return render(request, "course/update1.html", {"form": form})

@login_required
@role_required(['admin','staff'])
def updatecourse(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Course.objects.all().order_by('courseid')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(courseid__icontains=q))

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    operation = request.GET.get('operation')  
    return render(request, "course/updatecourse.html", {"page_obj": page_obj, "query": q, "operation": operation})


# ---------- Display ----------
@login_required
def displaycourse(request):
    course_list = Course.objects.all().order_by('courseid')  # queryset
    per_page = 10  

    paginator = Paginator(course_list, per_page)
    page = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "course/displaycourse.html", {"page_obj": page_obj})


# ----- Batch CRUD -----
# ---------- Insert ----------
@login_required
@role_required(['admin','staff'])
def insertbatch(request):
    if request.method == "POST":
        form = BatchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Batch added successfully.")
            return redirect('insertbatch')
    else:
        form = BatchForm()
    return render(request, "batch/insertbatch.html", {"form": form})


# ---------- Delete ----------
@require_POST
@login_required
@role_required(['admin'])
def delete2(request, pk):
    obj = get_object_or_404(Batch, pk=pk)
    obj.delete()
    messages.success(request, "Batch deleted successfully.")
    return redirect('deletebatch')

@login_required
@role_required(['admin'])
def deletebatch(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Batch.objects.select_related('course').all().order_by('course__courseid', 'name')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(course__courseid__icontains=q) |
            Q(course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "batch/deletebatch.html", {"page_obj": page_obj, "query": q})


# ---------- Update ----------
@login_required
@role_required(['admin','staff'])
def update2(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)

    if request.method == "POST":
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, "Batch updated successfully.")
            return redirect("updatebatch")
    else:
        form = BatchForm(instance=batch)

    return render(request, "batch/update2.html", {"form": form})

@login_required
@role_required(['admin','staff'])
def updatebatch(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Batch.objects.select_related('course').all().order_by('course__courseid', 'name')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(course__courseid__icontains=q) |
            Q(course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    operation = request.GET.get('operation')
    return render(request, "batch/updatebatch.html", {"page_obj": page_obj, "query": q, "operation": operation})


# ---------- Display ----------
@login_required
def displaybatch(request):
    batch_list = Batch.objects.select_related('course').all().order_by('course__courseid', 'name')
    per_page = 10

    paginator = Paginator(batch_list, per_page)
    page = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "batch/displaybatch.html", {"page_obj": page_obj})


# ----- Paper CRUD -----
# ---------- Insert ----------
@login_required
@role_required(['admin','staff'])
def insertpaper(request):
    if request.method == "POST":
        form = PaperForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Paper added successfully.")
            return redirect('insertpaper')
    else:
        form = PaperForm()
    return render(request, "paper/insertpaper.html", {"form": form})


# ---------- Delete ----------
@require_POST
@login_required
@role_required(['admin'])
def delete3(request, pk):
    obj = get_object_or_404(Paper, pk=pk)
    obj.delete()
    messages.success(request, "Paper deleted successfully.")
    return redirect('deletepaper')

@login_required
@role_required(['admin'])
def deletepaper(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Paper.objects.all().order_by('code', 'name')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(paper_type__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "paper/deletepaper.html", {"page_obj": page_obj, "query": q})


# ---------- Update ----------
@login_required
@role_required(['admin','staff'])
def update3(request, paper_id):
    paper = get_object_or_404(Paper, pk=paper_id)
    if request.method == "POST":
        form = PaperForm(request.POST, instance=paper)
        if form.is_valid():
            form.save()
            messages.success(request, "Paper updated successfully.")
            return redirect("updatepaper")
    else:
        form = PaperForm(instance=paper)
    return render(request, "paper/update3.html", {"form": form})

@login_required
@role_required(['admin','staff'])
def updatepaper(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Paper.objects.all().order_by('code', 'name')
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(paper_type__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    operation = request.GET.get('operation')
    return render(request, "paper/updatepaper.html", {"page_obj": page_obj, "query": q, "operation": operation})


# ---------- Display ----------
@login_required
def displaypaper(request):
    paper_list = Paper.objects.all().order_by('code', 'name')
    per_page = 10

    paginator = Paginator(paper_list, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "paper/displaypaper.html", {"page_obj": page_obj})


# ----- Student CRUD -----
# ---------- Insert ----------
@login_required
@role_required(['admin','staff'])
def insertstudent(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Student added successfully.")
            return redirect('insertstudent')
    else:
        form = StudentForm()
    return render(request, "student/insertstudent.html", {"form": form})

# ---------- Delete ----------
@require_POST
@login_required
@role_required(['admin'])
def delete4(request, pk):
    obj = get_object_or_404(Student, pk=pk)
    obj.delete()
    messages.success(request, "Student deleted successfully.")
    return redirect('deletestudent')

@login_required
@role_required(['admin'])
def deletestudent(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Student.objects.select_related('batch__course').all().order_by('regno')
    if q:
        qs = qs.filter(
            Q(regno__icontains=q) |
            Q(name__icontains=q) |
            Q(batch__name__icontains=q) |
            Q(batch__course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "student/deletestudent.html", {"page_obj": page_obj, "query": q})


# ---------- Update ----------
@login_required
@role_required(['admin','staff'])
def update4(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Student updated successfully.")
            return redirect("updatestudent")
    else:
        form = StudentForm(instance=student)

    return render(request, "student/update4.html", {"form": form})

@login_required
@role_required(['admin','staff'])
def updatestudent(request):
    q = request.GET.get('query', '').strip()
    per_page = 10

    qs = Student.objects.select_related('batch__course').all().order_by('regno')
    if q:
        qs = qs.filter(
            Q(regno__icontains=q) |
            Q(name__icontains=q) |
            Q(batch__name__icontains=q) |
            Q(batch__course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    operation = request.GET.get('operation')
    return render(request, "student/updatestudent.html", {"page_obj": page_obj, "query": q, "operation": operation})

# ---------- Display ----------
@login_required
def displaystudent(request):
    student_list = Student.objects.select_related('batch__course').all().order_by('regno')
    per_page = 10

    paginator = Paginator(student_list, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "student/displaystudent.html", {"page_obj": page_obj})


# ----- StudentMark (transactions) -----
# ---------- Insert mark ----------
@login_required
@role_required(['admin','staff'])
def insertstudentmarks(request):
    if request.method == "POST":
        form = StudentMarkForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Marks entry added successfully.")
            return redirect('insertstudentmarks')
    else:
        form = StudentMarkForm()
    return render(request, "studentmarks/insertstudentmarks.html", {"form": form})


# ---------- Delete ----------
@require_POST
@login_required
@role_required(['admin'])
def delete5(request, pk):
    obj = get_object_or_404(StudentMark, pk=pk)
    obj.delete()
    messages.success(request, "Marks entry deleted successfully.")
    return redirect('delete5')

@login_required
@role_required(['admin'])
def deletestudentmarks(request):
    q = request.GET.get('query', '').strip()
    per_page = 12

    qs = StudentMark.objects.select_related('student__batch__course', 'paper', 'batch').all().order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(student__regno__icontains=q) |
            Q(student__name__icontains=q) |
            Q(paper__code__icontains=q) |
            Q(paper__name__icontains=q) |
            Q(exam_type__icontains=q) |
            Q(batch__name__icontains=q) |
            Q(batch__course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "studentmarks/deletestudentmarks.html", {"page_obj": page_obj, "query": q})


# ---------- Update ----------
@login_required
@role_required(['admin','staff'])
def update5(request, mark_id):
    mark = get_object_or_404(StudentMark, pk=mark_id)
    if request.method == "POST":
        form = StudentMarkForm(request.POST, instance=mark)
        if form.is_valid():
            form.save()
            messages.success(request, "Marks entry updated successfully.")
            return redirect("updatestudentmarks")
    else:
        form = StudentMarkForm(instance=mark)
    return render(request, "studentmarks/update5.html", {"form": form})

@login_required
@role_required(['admin','staff'])
def updatestudentmarks(request):
    q = request.GET.get('query', '').strip()
    per_page = 12

    qs = StudentMark.objects.select_related('student__batch__course', 'paper', 'batch').all().order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(student__regno__icontains=q) |
            Q(student__name__icontains=q) |
            Q(paper__code__icontains=q) |
            Q(paper__name__icontains=q) |
            Q(exam_type__icontains=q) |
            Q(batch__name__icontains=q) |
            Q(batch__course__name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    operation = request.GET.get('operation')
    return render(request, "studentmarks/updatestudentmarks.html", {"page_obj": page_obj, "query": q, "operation": operation})


# ---------- Display ----------
@login_required
def displaystudentmarks(request):
    """
    If logged-in user is a student, show only their marks.
    We resolve the Student object by trying, in order:
      1) Student.regno == request.user.username
      2) Student.email == request.user.email (if user.email present)
    If none found, show empty list + hint message.

    Admin/staff see all marks (paginated).
    """
    user = request.user
    per_page = 20

    # If user is a student role -> filter
    profile = getattr(user, "profile", None)
    if profile and profile.role == "student":
        # try to find Student object
        student_qs = None
        try:
            student_qs = Student.objects.filter(regno__iexact=user.username)
            if not student_qs.exists() and user.email:
                student_qs = Student.objects.filter(email__iexact=user.email)
        except Exception:
            student_qs = Student.objects.none()

        if student_qs.exists():
            student_obj = student_qs.first()
            mark_list = StudentMark.objects.select_related('student__batch__course', 'paper', 'batch')\
                                          .filter(student=student_obj).order_by('-created_at')
        else:
            # No matching Student found for this user -> empty queryset and message
            messages.info(request, "No student record found for your account. Contact admin to link your profile.")
            mark_list = StudentMark.objects.none()
    else:
        # admin / staff: show all (optionally support a query filter)
        q = request.GET.get('query', '').strip()
        qs = StudentMark.objects.select_related('student__batch__course', 'paper', 'batch').all().order_by('-created_at')
        if q:
            qs = qs.filter(
                Q(student__regno__icontains=q) |
                Q(student__name__icontains=q) |
                Q(paper__code__icontains=q) |
                Q(paper__name__icontains=q) |
                Q(exam_type__icontains=q) |
                Q(batch__name__icontains=q) |
                Q(batch__course__name__icontains=q)
            )
        mark_list = qs

    # Pagination
    paginator = Paginator(mark_list, per_page)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "studentmarks/displaystudentmarks.html", {"page_obj": page_obj})


# ------------- REPORTS -------------------
@login_required
def reports_home(request):
    return render(request, "reports_home.html", {})

# helper: create filename with timestamp
def _csv_filename(prefix):
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.csv"

# ---------------- Courses ----------------
@login_required
def export_courses_csv(request):
    # Optional: filter by query param 'query'
    q = request.GET.get('query','').strip()
    qs = Course.objects.all().order_by('courseid')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(courseid__icontains=q))

    filename = _csv_filename("courses")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['id','courseid','name','created_at'])
    for c in qs:
        writer.writerow([c.id, c.courseid, c.name, c.created_at.isoformat()])

    return response

# ---------------- Batches ----------------
@login_required
def export_batches_csv(request):
    q = request.GET.get('query','').strip()
    qs = Batch.objects.select_related('course').all().order_by('course__courseid','name')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(year__icontains=q) |
                       Q(course__courseid__icontains=q) | Q(course__name__icontains=q))

    filename = _csv_filename("batches")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['id','courseid','course_name','batch_name','year','is_active'])
    for b in qs:
        writer.writerow([b.id, b.course.courseid if b.course else '', b.course.name if b.course else '',
                         b.name, b.year or '', b.is_active])

    return response

# ---------------- Papers ----------------
@login_required
def export_papers_csv(request):
    q = request.GET.get('query','').strip()
    qs = Paper.objects.all().order_by('code')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(paper_type__icontains=q))

    filename = _csv_filename("papers")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['id','code','name','paper_type','max_marks'])
    for p in qs:
        writer.writerow([p.id, p.code, p.name, p.paper_type, p.max_marks])

    return response

# ---------------- Students ----------------
@login_required
def export_students_csv(request):
    q = request.GET.get('query','').strip()
    qs = Student.objects.select_related('batch__course').all().order_by('regno')
    if q:
        qs = qs.filter(Q(regno__icontains=q) | Q(name__icontains=q) |
                       Q(batch__name__icontains=q) | Q(batch__course__name__icontains=q))

    filename = _csv_filename("students")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['id','regno','name','email','batch_name','course_name','is_active','created_at'])
    for s in qs:
        writer.writerow([s.id, s.regno, s.name, s.email or '', s.batch.name if s.batch else '',
                         s.batch.course.name if s.batch and s.batch.course else '', s.is_active, s.created_at.isoformat()])

    return response

# ---------------- Student Marks ----------------
@login_required
def export_marks_csv(request):
    """
    Export student marks as CSV.
    Accepts:
      - regno=REG123   -> export marks for that student regno
      - query=...      -> a general text filter (regno/name/paper/batch etc)
    Admin/staff can export arbitrary sets. Students can use this too (see privacy note).
    """

    user = request.user
    q_regno = request.GET.get('regno', '').strip()
    q = request.GET.get('query', '').strip()

    # build base queryset
    qs = StudentMark.objects.select_related('student__batch__course', 'paper', 'batch').all().order_by('-created_at')

    # Prefer regno param
    if q_regno:
        qs = qs.filter(student__regno__iexact=q_regno)
    elif q:
        qs = qs.filter(
            Q(student__regno__icontains=q) |
            Q(student__name__icontains=q) |
            Q(paper__code__icontains=q) |
            Q(paper__name__icontains=q) |
            Q(exam_type__icontains=q) |
            Q(batch__name__icontains=q) |
            Q(batch__course__name__icontains=q)
        )

    # -----------------------------
    # SECURITY / PRIVACY: optional restriction for students
    # If you want to ensure students can only download:
    #   - their own marks, or
    #   - marks from their own batch,
    # uncomment and adjust the block below.
    #
    # profile = getattr(user, "profile", None)
    # if profile and profile.role == "student":
    #     # OPTION A: only allow the student's own regno
    #     qs = qs.filter(student__regno__iexact=user.username)
    #
    #     # OPTION B (alternative): allow students to download marks only for students in the *same batch*
    #     # student_obj = Student.objects.filter(regno__iexact=user.username).first()
    #     # if student_obj:
    #     #     qs = qs.filter(batch=student_obj.batch)
    #     # else:
    #     #     qs = StudentMark.objects.none()
    # -----------------------------

    # Build CSV response
    filename = "student_marks"
    if q_regno:
        filename = f"marks_{q_regno}"
    elif q:
        filename = f"marks_filtered"
    filename = f"{filename}.csv"

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # header
    writer.writerow([
        "RegNo", "Student Name", "Course", "Batch", "Paper Code", "Paper Name",
        "Exam Type", "Marks", "Max Marks", "Created At"
    ])

    for m in qs:
        writer.writerow([
            m.student.regno,
            m.student.name,
            (m.student.batch.course.name if m.student.batch and m.student.batch.course else ""),
            (m.batch.name if m.batch else ""),
            (m.paper.code if m.paper and getattr(m.paper, 'code', None) else ""),
            (m.paper.name if m.paper else ""),
            m.exam_type,
            str(m.marks),
            (str(m.paper.max_marks) if m.paper and getattr(m.paper, 'max_marks', None) else ""),
            m.created_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return response