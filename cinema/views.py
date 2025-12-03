from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch
from .models import Movie, MovieSession, Order, Ticket
from .serializers import (
    MovieSerializer,
    MovieSessionListSerializer,
    MovieSessionDetailSerializer,
    OrderSerializer,
)

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Retorna todos os pedidos do usuário autenticado (order por created_at desc)
        return Order.objects.filter(user=self.request.user).order_by("-created_at").prefetch_related(
            Prefetch("tickets", queryset=Ticket.objects.select_related("movie_session__movie", "movie_session__cinema_hall"))
        )

    def perform_create(self, serializer):
        # serializer.create() já usa request.user via context, mas podemos garantir:
        serializer.save()

    def list(self, request, *args, **kwargs):
        # usa paginação/configurações REST_FRAMEWORK
        return super().list(request, *args, **kwargs)


class MovieViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = []  # we use custom filter via query params
    search_fields = ["title"]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("genres", "actors")
        # filters via query params: ?genres=drama,comedy&actors=John Doe,Someone&title=part
        genres = self.request.query_params.get("genres")
        actors = self.request.query_params.get("actors")
        title = self.request.query_params.get("title")
        if title:
            qs = qs.filter(title__icontains=title)
        if genres:
            genre_list = [g.strip() for g in genres.split(",") if g.strip()]
            if genre_list:
                qs = qs.filter(genres__name__in=genre_list).distinct()
        if actors:
            actor_list = [a.strip() for a in actors.split(",") if a.strip()]
            if actor_list:
                qs = qs.filter(actors__full_name__in=actor_list).distinct()
        return qs


class MovieSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovieSession.objects.select_related("movie", "cinema_hall").prefetch_related("tickets")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    serializer_class = MovieSessionListSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MovieSessionDetailSerializer
        return MovieSessionListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        date = self.request.query_params.get("date")
        movie = self.request.query_params.get("movie")
        if date:
            # espera format yyyy-mm-dd
            from django.utils.dateparse import parse_date
            parsed = parse_date(date)
            if parsed:
                # filtrar sessão com show_time no dia (considerar timezone) -> use date range
                from datetime import datetime, time, timedelta
                start = datetime.combine(parsed, time.min)
                end = datetime.combine(parsed, time.max)
                qs = qs.filter(show_time__range=(start, end))
        if movie:
            qs = qs.filter(movie_id=movie)
        return qs
