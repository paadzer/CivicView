# Auth views: register, me (current user + role), assignable users (manager/admin only)
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework.permissions import IsAuthenticated

from .models import Profile
from .permissions import IsManagerOrAdmin
from .serializers import AssignableUserSerializer

User = get_user_model()


class RegisterView(APIView):
    """POST with username, password, email (optional). Creates User, Profile(role=citizen), Token. Returns token key."""

    permission_classes = []  # Allow unauthenticated registration
    authentication_classes = []

    def post(self, request: Request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = (request.data.get("email") or "").strip() or ""

        if not username or not password:
            return Response(
                {"error": "username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "A user with that username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(password)
        except ValidationError as e:
            return Response(
                {"error": list(e.messages) if e.messages else "Invalid password"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email or f"{username}@civicview.local",
        )
        Profile.objects.get_or_create(user=user, defaults={"role": Profile.ROLE_CITIZEN})
        token, _ = Token.objects.get_or_create(user=user)
        profile = user.profile
        return Response(
            {"token": token.key, "username": user.username, "role": profile.role},
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    """GET /api/auth/me/ - Return current user id, username, role (requires auth)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
        profile = getattr(user, "profile", None)
        role = profile.role if profile else "citizen"
        return Response({"id": user.id, "username": user.username, "role": role})


class AssignableUsersView(APIView):
    """GET /api/auth/assignable-users/ - List users that can be assigned to reports (staff, council, manager). Manager/admin only."""

    permission_classes = [IsAuthenticated, IsManagerOrAdmin]

    def get(self, request: Request):
        users = User.objects.filter(
            profile__role__in=Profile.ASSIGNABLE_ROLES
        ).select_related("profile").order_by("username")
        serializer = AssignableUserSerializer(users, many=True)
        return Response(serializer.data)
