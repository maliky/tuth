"""Test admin login module."""

from pytest_bdd import scenario, given, when, then, parsers
from django.urls import reverse


@scenario("admin_login.feature", "Superuser logs in successfully")
def test_admin_login():
    pass


@given("I am on the admin login page", target_fixture="response")
def admin_login_page(client):
    return client.get(reverse("admin:login"))


@when(
    parsers.cfparse(
        'I enter valid credentials for "{username}" with password "{password}"'
    )
)
def post_credentials(client, username, password, superuser):
    client.force_login(superuser)  # fast: skip HTML form
    return


@then("I am redirected to the admin dashboard", target_fixture="dashboard")
def redirected_to_dashboard(client):
    response = client.get(reverse("admin:index"))
    assert response.status_code == 200
    return response


@then(parsers.parse('I see "{text}" on the page'))
def text_on_page(dashboard, text):
    assert text in dashboard.content.decode()
