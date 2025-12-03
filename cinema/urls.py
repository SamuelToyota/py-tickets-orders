from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, MovieViewSet, MovieSessionViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"movies", MovieViewSet, basename="movies")
router.register(r"movie_sessions", MovieSessionViewSet, basename="movie_sessions")

urlpatterns = router.urls
