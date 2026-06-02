Feature: Landing page
  As a prospective student
  I want to see the landing page content
  So I can navigate to the portal

  Scenario: Visitor sees the landing page hero
    Given the visitor is on the landing page
    Then the landing page hero is visible
    And the service status card is visible

  Scenario: Visitor uses the Tusis button
    Given the visitor is on the landing page
    When the visitor clicks the Tusis button
    Then the portal login form is shown
