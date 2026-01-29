Feature: Student dashboard sidebar links

  Scenario: Student can open invoice and payment statements
    Given a student with an active semester
    When the student logs in to the portal
    Then the sidebar shows invoice and payment statement links
    When the student opens the invoice statement
    Then the invoice statement page is shown
    When the student opens the payment receipt
    Then the payment receipt page is shown

  Scenario: Payment receipt shows the date paid column
    Given a student with a paid invoice
    When the student logs in to the portal
    When the student opens the payment receipt
    Then the payment receipt shows the date paid column
