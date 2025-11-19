from rest_framework.routers import DefaultRouter
from .api_views import StudentViewSet, StudentMarkViewSet

router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='api-students')
router.register(r'marks', StudentMarkViewSet, basename='api-marks')

urlpatterns = router.urls
