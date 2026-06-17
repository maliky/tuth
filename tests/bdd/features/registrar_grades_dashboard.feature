Feature: Registrar grades dashboard
  As a registrar
  I want to manage grades efficiently
  So I can review student performance

  Scenario: Defaults to all semesters for transcript search
    Given a registrar user
    And the registrar data includes graded students in multiple semesters
    When the registrar opens the grades dashboard
    Then the semester filter defaults to all semesters

  Scenario: Dashboard link and row expand
    Given a registrar user
    And the registrar data includes graded students in the current semester
    When the registrar opens the grades dashboard
    Then the dashboard link is visible
    And the registrar can expand the student row

  Scenario: Pagination shows counts and last link
    Given a registrar user
    And the grades dashboard has two graded students in the current semester
    When the registrar opens the grades dashboard
    Then the pagination shows counts and last link

  Scenario: Transcript button
    Given a registrar user
    And the registrar data includes graded students in the current semester
    When the registrar opens the grades dashboard
    Then the official transcript page is shown for the student

  Scenario: Go-to preserves semester
    Given a registrar user
    And the grades dashboard has two graded students in the current semester
    When the registrar opens the grades dashboard filtered by the current semester
    Then the go-to pagination keeps the semester filter
