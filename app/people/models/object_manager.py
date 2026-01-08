"""Object Manger for People classes."""

import logging
from typing import Any, Dict, Mapping, Optional, Tuple, cast

from django.contrib.auth.models import User
from django.db.models import Manager

from app.people.utils import NameParts, mk_username
from app.shared.fuzzy_matching import top_name_matches
from app.shared.types import AbstractPersonT

logger = logging.getLogger(__name__)
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


def _get_match(
    no: int, ranked_matches: list[tuple[AbstractPersonT, float]]
) -> Tuple[Optional[User], float]:
    """Given the list of ranked matches return the first or second based on no."""
    _person, _score = ranked_matches[no] if len(ranked_matches) > no else (None, 0.0)
    _user: Optional[User] = cast(Optional[User], getattr(_person, "user", None))
    return _user, float(_score)


def _get_name(**kwargs) -> NameParts:
    """Extract for the passed dict the element making a name."""
    named_parts = ["prefix", "first", "middle", "last", "suffix"]
    parts = {f"{np}_name": kwargs.get(f"{np}_name", "") for np in named_parts}
    return NameParts(**parts)


def _get_username(name: NameParts | None, **kwargs) -> str:
    """Look into the kwargs for elements to build the username.

    if username exists remove it from kwargs.
    """
    username = str(kwargs.pop("username", "") or "")

    if username:
        return username

    if name is not None:
        first, middle, last = name.parts()
    else:
        first = kwargs.get("first_name", "")
        last = kwargs.get("last_name", "")
        middle = kwargs.get("middle_name", "")

    username = mk_username(first, last, middle, unique=True)
    return username


def _split_kwargs(**kwargs) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Returns user_kwargs, person_kwargs. username if exists goes to user_kwargs."""
    user_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in USER_KWARGS}
    return user_kwargs, kwargs


def _get_full_name(person: Any) -> str:
    """Return the full name for the user."""
    user_obj = getattr(person, "user", None)
    return " ".join(
        [
            getattr(person, "prefix_name", "") or "",
            getattr(user_obj, "first_name", "") or "",
            getattr(person, "middle_name", "") or "",
            getattr(user_obj, "last_name", "") or "",
            getattr(person, "suffix_name", "") or "",
        ]
    ).strip()


class PersonManager(Manager[AbstractPersonT]):
    """Custom creation Management."""

    def _find_by_name(self, name: NameParts, threshold: float = 0.9) -> Optional[User]:
        """Return an existing user matched on Person fullname.

        Only attached user is returned.
        """

        if not name.first or not name.last:
            return None

        base_name = name.to_string(full=False)

        # iexact : case insensitive
        candidates = self.get_queryset().filter(user__last_name__iexact=name.last)

        if not candidates.exists():
            # > the problem here is that we already assume that
            # the first 3 char will be similare
            # At the same time we need to filter out some candidates
            candidates = self.get_queryset().filter(
                user__last_name__istartswith=name.last[:3]
            )

        ranked_matches = top_name_matches(
            base_name, candidates, _get_full_name, threshold=threshold, limit=2
        )
        if not ranked_matches:
            return None

        best_user, best_score = _get_match(0, ranked_matches)
        second_user, second_score = _get_match(1, ranked_matches)

        if best_user and best_score >= threshold:
            if (best_score - second_score) >= 0.05:  # .05 ~ arbitraire
                return best_user
            else:
                logger.info(
                    "Ambiguous duplicate for %s '%s'; best=%s '%s' (%.2f), second=%.50s (%.2f); skipping auto-merge",
                    self.model.__name__,
                    base_name,
                    getattr(best_user, "username", ""),
                    getattr(best_user, "get_full_name", lambda: "")(),
                    best_score,
                    getattr(second_user, "username", ""),
                    getattr(second_user, "get_full_name", lambda: "")(),
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
                existing_user.username if existing_user else _get_username(**user_kwargs)
            )

        found_user = self._find_by_name(**user_kwargs)
        if found_user:
            return found_user

        user = User.objects.create_user(
            username=username, password=password, **user_kwargs
        )

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
            # user_kwargs.pop("username", None)
            if password:
                found_user.set_password(password)
                found_user.save(update_fields=["password"])
            return found_user

        # > ! pb here how am I sure that the username is not duplicated ?
        user, _ = User.objects.update_or_create(username=username, defaults=user_kwargs)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user

    # public API ----------------------------------------------------
    def create(self, **kwargs):
        """Create a user and the person."""
        user_kwargs, person_kwargs = _split_kwargs(**kwargs)
        user = self._create_user(**user_kwargs)
        return super().create(user=user, **person_kwargs)

    def update_or_create(
        self,
        defaults: Mapping[str, Any] | None = None,
        create_defaults: Mapping[str, Any] | None = None,
        **kwargs,
    ):
        """Update or Create a Person and the associated user.

        The defaults is used for updating and creating if create_defaults
        is not there. Kwargs is used to search for the Person to update.

        The lookup is done wih kwargs in this order. user, username, name search,
        built username from name.
        """
        defaults = dict(defaults or {})
        create_defaults = dict(create_defaults or {})
        lookup_kwargs = dict(kwargs)

        user_lookup, person_lookup = _split_kwargs(**lookup_kwargs)
        user_def, person_def = _split_kwargs(**defaults)
        user_create_def, person_create_def = _split_kwargs(**create_defaults)

        # If we have a user we use it
        provided_user = cast(Optional[User], user_lookup.pop("user", None))
        if provided_user:
            # This can be a creation if no super is attached ot the user
            return super().update_or_create(
                user=provided_user, defaults=person_def, create_defaults=person_create_def
            )

        # If we have a username we use it
        provided_username = user_lookup.pop("username", None)

        if provided_username:
            # Could be a creation if username is not in db.
            # in such case user_create should not create duplicate.
            user, _ = User.objects.update_or_create(
                username=provided_username,
                defaults=user_def,
                create_defaults=user_create_def,
            )

        # In other case we use look by name
        name = _get_name(**user_lookup, **person_lookup)
        found_user = self._find_by_name(name=name)

        if found_user:
            user = found_user
        else:
            # Finaly we prepare a lookup with a built username
            user, _ = User.objects.update_or_create(
                username=_get_username(name=name),
                defaults=user_def,
                create_defaults=user_create_def,
            )
        return super().update_or_create(
            user=user, defaults=person_def, create_defaults=person_create_def
        )

    def get_or_create(self, defaults: Mapping[str, Any] | None = None, **kwargs):
        """Get or Create the user and the person."""
        defaults = dict(defaults or {})

        user_kwargs, person_kwargs = _split_kwargs(**kwargs, **defaults)

        provided_user = cast(Optional[User], user_kwargs.pop("user", None))
        if provided_user:
            return super().get_or_create(user=provided_user, defaults=person_kwargs)

        _ = user_kwargs.pop("password", None)  # Why 07/01/26 ?
        provided_username = user_kwargs.pop("username", None)

        if provided_username:
            user, _ = User.objects.get_or_create(
                username=provided_username, defaults=user_kwargs
            )

        name = _get_name(**user_kwargs, **person_kwargs)
        found_user = self._find_by_name(name=name)

        if found_user:
            return super().get_or_create(user=found_user, defaults=person_kwargs)

        username = _get_username(name=name)
        user, _ = User.objects.get_or_create(username=username, defaults=user_kwargs)

        # Is There some loop hole here ?
        # if password:
        #     # can I pass a hashed value directly to the password field of the user ?
        #     user.set_password(password)  # to make sure it is hashed

        return super().get_or_create(user=user, defaults=person_kwargs)
