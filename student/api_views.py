from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Student, StudentMark
from .serializers import StudentSerializer, StudentMarkSerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('batch__course').all().order_by('regno')
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['regno', 'name', 'email', 'batch__name', 'batch__course__name']
    ordering_fields = ['regno', 'name']

class StudentMarkViewSet(viewsets.ModelViewSet):
    queryset = StudentMark.objects.select_related('student__batch__course', 'paper', 'batch').all().order_by('-created_at')
    serializer_class = StudentMarkSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['student__regno', 'student__name', 'paper__code', 'paper__name', 'exam_type', 'batch__name']

    def get_queryset(self):
        qs = super().get_queryset()
        # allow query params: ?student_regno=XXX or ?student_id= or ?batch_id=, ?paper_id=
        student_regno = self.request.GET.get('student_regno')
        if student_regno:
            qs = qs.filter(student__regno__iexact=student_regno)
        student_id = self.request.GET.get('student_id')
        if student_id:
            qs = qs.filter(student__id=student_id)
        batch_id = self.request.GET.get('batch_id')
        if batch_id:
            qs = qs.filter(batch__id=batch_id)
        paper_id = self.request.GET.get('paper_id')
        if paper_id:
            qs = qs.filter(paper__id=paper_id)
        return qs

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my(self, request):
        # returns marks for logged in user mapped by regno/email -> Student
        user = request.user
        student_qs = Student.objects.filter(regno__iexact=user.username)
        if not student_qs.exists() and user.email:
            student_qs = Student.objects.filter(email__iexact=user.email)
        if not student_qs.exists():
            return Response({"detail": "No student record found for this user."}, status=404)
        student = student_qs.first()
        qs = self.get_queryset().filter(student=student)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
