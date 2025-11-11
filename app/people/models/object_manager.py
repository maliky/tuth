"""Object Manger for People classes."""

from typing import Any, Dict, Mapping, Optional, Tuple, cast
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

    def _create_user(self, **user_kwargs: Any) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)
        existing_user = cast(Optional[User], user_kwargs.pop("user", None))
        username = user_kwargs.pop("username", "")
        if not username and existing_user:
            username = existing_user.username

        user = User.objects.create_user(
            username=username, password=password, **user_kwargs
        )
        # there some loop hole here
        # if password:
        #     user.set_password(password)  # to make sure it is hashed

        return user

    def _get_or_create(self, username: str, **user_kwargs: Any) -> User:
        """Create or get the User and set /update password."""
        _ = user_kwargs.pop("password", None)
        user, _ = User.objects.get_or_create(username=username, defaults=user_kwargs)
        # there some loop hole here
        # if password:
        #     # can I pass a hashed value directly to the password field of the user ?
        #     user.set_password(password)  # to make sure it is hashed

        return user

    def _update_or_create(self, username: str, **user_kwargs: Any) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)
        existing_user = cast(Optional[User], user_kwargs.pop("user", None))

        if existing_user:
            existing_user.username = username
            for field, value in user_kwargs.items():
                setattr(existing_user, field, value)
            if password:
                existing_user.set_password(password)
            existing_user.save()
            return existing_user

        user, _ = User.objects.update_or_create(username=username, defaults=user_kwargs)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
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
        lookup_kwargs = dict(kwargs)
        username = self._get_username(**defaults, **lookup_kwargs)

        user_lookup_kwargs, person_lookup_kwargs = self._split_kwargs(lookup_kwargs)

        defaults_copy = dict(defaults)
        user_default_kwargs, person_default_kwargs = self._split_kwargs(defaults_copy)

        combined_user_kwargs = {**user_default_kwargs, **user_lookup_kwargs}
        user = self._update_or_create(username=username, **combined_user_kwargs)

        merged_person_defaults = {**person_default_kwargs, **person_lookup_kwargs}

        return super().update_or_create(user=user, defaults=merged_person_defaults)

    def get_or_create(self, defaults: Mapping[str, Any] | None = None, **kwargs):
        """Get or Create the user and the person."""
        defaults = defaults or {}
        username = self._get_username(**defaults, **kwargs)
        user_kwargs, person_kwargs = self._split_kwargs({**kwargs, **defaults})

        user = self._get_or_create(username=username, **user_kwargs)

        return super().get_or_create(user=user, defaults=person_kwargs)
