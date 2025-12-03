from rest_framework import serializers
from django.db import transaction
from .models import Movie, MovieSession, CinemaHall, Order, Ticket, Genre, Actor

# Movie nested read serializer
class MovieSimpleSerializer(serializers.ModelSerializer):
    genres = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    actors = serializers.SlugRelatedField(many=True, read_only=True, slug_field="full_name")

    class Meta:
        model = Movie
        fields = ("id", "title", "description", "duration", "genres", "actors")


class CinemaHallSerializer(serializers.ModelSerializer):
    capacity = serializers.IntegerField(source="get_capacity", read_only=True)

    class Meta:
        model = CinemaHall
        fields = ("id", "name", "rows", "seats_in_row", "capacity")


# Serializer used inside OrderTicket read representation
class MovieSessionForTicketSerializer(serializers.ModelSerializer):
    movie_title = serializers.CharField(source="movie.title", read_only=True)
    cinema_hall_name = serializers.CharField(source="cinema_hall.name", read_only=True)
    cinema_hall_capacity = serializers.IntegerField(source="cinema_hall.get_capacity", read_only=True)

    class Meta:
        model = MovieSession
        fields = ("id", "show_time", "movie_title", "cinema_hall_name", "cinema_hall_capacity")


class TicketReadSerializer(serializers.ModelSerializer):
    movie_session = MovieSessionForTicketSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "row", "seat", "movie_session")


# Ticket input serializer (used in Order create)
class TicketWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("row", "seat", "movie_session")  # movie_session is expected as ID

    # Optionally add validation: seat/row within hall limits, seat already taken etc.
    def validate(self, attrs):
        movie_session = attrs.get("movie_session")
        row = attrs.get("row")
        seat = attrs.get("seat")
        if row < 1 or seat < 1:
            raise serializers.ValidationError("Row and seat must be positive integers.")
        # Check within hall bounds if model provides rows/seats_in_row
        hall = movie_session.cinema_hall
        if hall.rows and hall.seats_in_row:
            if row > hall.rows or seat > hall.seats_in_row:
                raise serializers.ValidationError("Row or seat is outside of hall dimensions.")
        # Check if seat already taken for this session
        if Ticket.objects.filter(movie_session=movie_session, row=row, seat=seat).exists():
            raise serializers.ValidationError("This seat is already taken for this session.")
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    tickets = TicketReadSerializer(many=True, read_only=True)
    # write uses nested TicketWriteSerializer
    tickets_data = TicketWriteSerializer(many=True, write_only=True, required=True, source="tickets")

    class Meta:
        model = Order
        fields = ("id", "tickets", "tickets_data", "created_at")
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        # reuse default but ensure tickets are serialized with full TicketReadSerializer
        rep = super().to_representation(instance)
        # remove write-only key if present
        rep.pop("tickets_data", None)
        return rep

    @transaction.atomic
    def create(self, validated_data):
        tickets_data = validated_data.pop("tickets", [])  # because source="tickets"
        user = self.context["request"].user
        order = Order.objects.create(user=user, **validated_data)
        tickets_objs = []
        for t in tickets_data:
            ticket = Ticket(order=order, **t)
            # Optionally reuse the serializer validation already done by TicketWriteSerializer
            ticket.save()
            tickets_objs.append(ticket)
        # bulk_create could be used but we used save() so signals/validation run
        return order
