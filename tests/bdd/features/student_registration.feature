Feature: Student registration

  Scenario: Student registers for an available section
    Given a student with an open registration semester
    And a curriculum section available for registration
    When the student selects the section and saves the registration
    Then an invoice is created with the initial amount due
