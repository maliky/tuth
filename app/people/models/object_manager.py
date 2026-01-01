"""Object Manger for People classes."""

import logging
from typing import Any, Dict, Mapping, Optional, Tuple, cast

from django.contrib.auth.models import User
from django.db.models import Manager

from app.shared.fuzzy_matching import top_name_matches
from app.people.utils import mk_username
from app.shared.utils import get_in_row

logger = logging.getLogger(__name__)


class PersonManager(Manager):
    """Custom creation Management."""

    USER_KWARGS = {
        "user",
        "username",
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

    def _get_long_name(self, person: Any) -> str:
        user_obj = getattr(person, "user", None)
        return " ".join(
            [
                getattr(user_obj, "first_name", "") or "",
                getattr(person, "middle_name", "") or "",
                getattr(user_obj, "last_name", "") or "",
            ]
        ).strip()

    def _find_by_name(self, **user_kwargs: Any) -> Optional[User]:
        """Return an existing user matched on first/last/middle names (case-insensitive)."""
        first = get_in_row("first_name", user_kwargs)
        last = get_in_row("last_name", user_kwargs)
        middle = get_in_row("middle_name", user_kwargs)

        if not first or not last:
            return None

        base_name = " ".join([first, middle, last]).strip()

        # iexact : case insensitive
        candidates = self.get_queryset().filter(user__last_name__iexact=last)

        if not candidates.exists():
            # > the problem here is that we already assume that
            # the first 3 char will be similare
            # At the same time we need to filter out some candidates
            candidates = self.get_queryset().filter(user__last_name__istartswith=last[:3])

        ranked_matches = top_name_matches(
            base_name, candidates, self._get_long_name, threshold=0.9, limit=2
        )
        if not ranked_matches:
            return None

        best_person, best_score = ranked_matches[0]
        best_user: Optional[User] = cast(
            Optional[User], getattr(best_person, "user", None)
        )
        second_score = ranked_matches[1][1] if len(ranked_matches) > 1 else 0.0

        if best_user and best_score >= 0.92:
            if (best_score - second_score) >= 0.05:
                return best_user
            else:
                logger.info(
                    "Ambiguous duplicate for %s '%s %s %s'; best=%s '%s' (%.2f), second=%.50s (%.2f); skipping auto-merge",
                    self.model.__name__,
                    first,
                    middle,
                    last,
                    getattr(best_user, "username", ""),
                    getattr(best_user, "get_full_name", lambda: "")(),
                    best_score,
                    base_name,
                    second_score,
                )

        return None

    def _create_user(self, **user_kwargs: Any) -> User:
        """Create or get the User and set /update password."""
        password = user_kwargs.pop("password", None)
        username = user_kwargs.pop("username", "")
        if not username:
            existing_user = cast(Optional[User], user_kwargs.pop("user", None))
            username = (
                existing_user.username
                if existing_user
                else self._get_username(**user_kwargs)
            )

        found_user = self._find_by_name(**user_kwargs)
        if found_user:
            return found_user

        user = User.objects.create_user(
            username=username, password=password, **user_kwargs
        )

        return user

    def _get_or_create(self, username: str, **user_kwargs: Any) -> User:
        """Create or get the User and set/update password."""
        _ = user_kwargs.pop("password", None)
        existing_user = cast(Optional[User], user_kwargs.pop("user", None))
        if existing_user:
            return existing_user

        found_user = self._find_by_name(**user_kwargs)
        if found_user:
            return found_user

        user, _ = User.objects.get_or_create(username=username, defaults=user_kwargs)
        # there some loop hole here
        # if password:
        #     # can I pass a hashed value directly to the password field of the user ?
        #     user.set_password(password)  # to make sure it is hashed

        return user

    def _update_or_create(self, username: str, **user_kwargs: Any) -> User:
        """Get the User from username and set/update password or create it."""

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

        found_user = self._find_by_name(**user_kwargs)
        if found_user:
            user_kwargs.pop("username", None)
            if password:
                found_user.set_password(password)
                found_user.save(update_fields=["password"])
            return found_user

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
            username = mk_username(first, last, prefix_len=2, unique=True)
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

        username = (
            defaults.pop("username", False) or kwargs.pop("username", False)
            if "username" in defaults or "username" in kwargs
            else self._get_username(**defaults, **kwargs)
        )

        user_kwargs, person_kwargs = self._split_kwargs(lookup_kwargs)
        user_default, person_default = self._split_kwargs(defaults)

        combined_kwargs = {**user_default, **user_kwargs}

        user = self._update_or_create(username=username, **combined_kwargs)

        merged_person_defaults = {**person_default, **person_kwargs}

        return super().update_or_create(user=user, defaults=merged_person_defaults)

    def get_or_create(self, defaults: Mapping[str, Any] | None = None, **kwargs):
        """Get or Create the user and the person."""
        defaults = defaults or {}

        username = (
            defaults.pop("username", False) or kwargs.pop("username", False)
            if "username" in defaults or "username" in kwargs
            else self._get_username(**defaults, **kwargs)
        )

        user_kwargs, person_kwargs = self._split_kwargs({**kwargs, **defaults})

        user = self._get_or_create(username=username, **user_kwargs)

        return super().get_or_create(user=user, defaults=person_kwargs)
