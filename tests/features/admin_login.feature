Feature: Admin site authentication

  Scenario: Superuser logs in successfully
    Given I am on the admin login page
    When I enter valid credentials for "super" with password "secret123"
    Then I am redirected to the admin dashboard
    And I see "Site administration" on the page
