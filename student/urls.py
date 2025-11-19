from django.urls import path
from . import views

urlpatterns = [
    path('master/', views.master, name='master'),
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('logout/', views.user_logout, name='logout'),
    path('admin/create-user/', views.admin_create_user, name='admin_create_user'),

    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),

    # Course
    path('insertcourse/', views.insertcourse, name='insertcourse'),
    path('delete1/<int:pk>/', views.delete1, name='delete1'),
    path('deletecourse/', views.deletecourse, name='deletecourse'),
    path('update1/<int:course_id>/', views.update1, name='update1'),
    path('updatecourse/', views.updatecourse, name='updatecourse'),
    path('displaycourse/', views.displaycourse, name='displaycourse'),

    # Batch
    path('insertbatch/', views.insertbatch, name='insertbatch'),
    path('delete2/<int:pk>/', views.delete2, name='delete2'),
    path('deletebatch/', views.deletebatch, name='deletebatch'),
    path('update2/<int:batch_id>/', views.update2, name='update2'),
    path('updatebatch/', views.updatebatch, name='updatebatch'),
    path('displaybatch/', views.displaybatch, name='displaybatch'),

    # Paper
    path('insertpaper/', views.insertpaper, name='insertpaper'),
    path('delete3/<int:pk>/', views.delete3, name='delete3'),
    path('deletepaper/', views.deletepaper, name='deletepaper'),
    path('update3/<int:paper_id>/', views.update3, name='update3'),
    path('updatepaper/', views.updatepaper, name='updatepaper'),
    path('displaypaper/', views.displaypaper, name='displaypaper'),

    # Student
    path('insertstudent/', views.insertstudent, name='insertstudent'),
    path('delete4/<int:pk>/', views.delete4, name='delete4'),
    path('deletestudent/', views.deletestudent, name='deletestudent'),
    path('update4/<int:student_id>/', views.update4, name='update4'),
    path('updatestudent/', views.updatestudent, name='updatestudent'),
    path('displaystudent/', views.displaystudent, name='displaystudent'),

    # StudentMark (transactions)
    path('insertstudentmarks/', views.insertstudentmarks, name='insertstudentmarks'),
    path('delete5/<int:pk>/', views.delete5, name='delete5'),
    path('deletestudentmarks/', views.deletestudentmarks, name='deletestudentmarks'),
    path('update5/<int:mark_id>/', views.update5, name='update5'),
    path('updatestudentmarks/', views.updatestudentmarks, name='updatestudentmarks'),
    path('displaystudentmarks/', views.displaystudentmarks, name='displaystudentmarks'),
    
    # Reports
    path('reports/', views.reports_home, name='reports_home'),
    path('export/courses/', views.export_courses_csv, name='export_courses_csv'),
    path('export/batches/', views.export_batches_csv, name='export_batches_csv'),
    path('export/papers/',  views.export_papers_csv,  name='export_papers_csv'),
    path('export/students/',views.export_students_csv, name='export_students_csv'),
    path('reports/export/marks/', views.export_marks_csv, name='export_marks_csv'),
]
