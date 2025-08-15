"""Object Manger for People classes."""

from typing import Any, Dict, Mapping, Tuple
from app.people.utils import mk_username
from django.db.models import Manager
from django.contrib.auth.models import User


class PersonManager(Manager):
    """Custom creation Management."""

    USER_KWARGS = {
        "user",
        # "username",
        "password",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
    }

    def _split_kwargs(
        self, kwargs: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Returns user_kwargs, person_kwargs."""
        user_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in self.USER_KWARGS}
        return user_kwargs, kwargs

    def _create_user(self, **user_kwargs) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)
        username = user_kwargs.pop("username", "") or user_kwargs.pop("user").username

        user = User.objects.create_user(
            username=username, password=password, **user_kwargs
        )
        # there some loop hole here
        # if password:
        #     user.set_password(password)  # to make sure it is hashed

        return user

    def _get_or_create(self, username, **user_kwargs) -> User:
        """Create or get the User and set /update password."""
        _ = user_kwargs.pop("password", None)
        user, _ = User.objects.get_or_create(username=username, defaults=user_kwargs)
        # there some loop hole here
        # if password:
        #     # can I pass a hashed value directly to the password field of the user ?
        #     user.set_password(password)  # to make sure it is hashed

        return user

    def _update_or_create(self, username, **user_kwargs) -> User:
        """Create or get the User and set /update password."""
        _ = user_kwargs.pop("password", None)

        user, created = User.objects.update_or_create(
            username=username, defaults=user_kwargs
        )
        # there some loop hole here
        # if password:
        #     user.set_password(password)  # to make sure it is hashed

        return user

    def _get_username(self, **kwargs) -> str:
        """Look into the kwargs for elements to build the username."""
        username = kwargs.pop("username", "")
        if not username:
            first = kwargs.get("first_name", "")
            last = kwargs.get("last_name", "")
            username = mk_username(first, last, prefix_len=2)
        return str(username)

    # public API ----------------------------------------------------
    def create(self, **kwargs):
        """Create a user and the person."""
        user_kwargs, person_kwargs = self._split_kwargs(kwargs)
        user = self._create_user(**user_kwargs)
        return super().create(user=user, **person_kwargs)

    def update_or_create(
        self,
        defaults: Mapping[str, Any] | None = None,
        create_defaults: Mapping[str, Any] | None = None,
        **kwargs,
    ):
        """Update or Create a user and the person."""
        defaults = defaults or {}
        username = self._get_username(**defaults, **kwargs)
        user_kwargs, person_kwargs = self._split_kwargs(kwargs)
        user = self._update_or_create(username=username, **user_kwargs)
        # user.save()
        return super().update_or_create(user=user, defaults=person_kwargs)

    def get_or_create(self, defaults: Mapping[str, Any] | None = None, **kwargs):
        """Get or Create the user and the person."""
        defaults = defaults or {}
        username = self._get_username(**defaults, **kwargs)
        user_kwargs, person_kwargs = self._split_kwargs({**kwargs, **defaults})

        user = self._get_or_create(username=username, **user_kwargs)
        return super().get_or_create(user=user, defaults=person_kwargs)
