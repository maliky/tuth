Feature: Portal role dashboards
  As a portal user
  I want to land on the right dashboard
  So I can access my role-specific tools

  Scenario Outline: User lands on the correct dashboard
    Given a portal user "<username>" with role "<role>" and student "<student>"
    When the user logs in to the portal
    Then the dashboard heading includes "<heading>"

    Examples:
      | username             | role                | student | heading                  |
      | instructor_user      | Instructor          | no      | Instruction Hub          |
      | student_user         |                     | yes     | Student Dashboard        |
      | chair_user           | Chair               | no      | Chair Curriculum Center  |
      | dean_user            | Dean                | no      | Dean Oversight           |
      | vpaa_user            | VPAA                | no      | VPAA Approval Hub        |
      | registrar_user       | Registrar           | no      | Registrar Lifecycle Ops  |
      | scholarship_user     | Scholarship Officer | no      | Scholarship Office       |
      | finance_user         | Finance             | no      | Finance & Holds          |
      | finance_officer_user | Finance Officer     | no      | Finance Officer Control  |

  Scenario Outline: Role dashboards show expected actions
    Given a portal user "<username>" with role "<role>" and student "no"
    When the user logs in to the portal
    Then the dashboard actions include "<actions>"

    Examples:
      | username               | role               | actions                                                       |
      | registrar_officer_user | Registrar Officer  | registrar_course_windows                                      |
      | enrollment_user        | Enrollment         | student_list,admin:people_student_add,student_admin_edit      |
      | enrollment_officer_user| Enrollment Officer | student_list,admin:people_student_add,student_admin_edit,admin:people_student_changelist |

  Scenario: Registrar without officer permissions cannot manage semester windows
    Given a portal user "registrar_basic" with role "Registrar" and student "no"
    When the user logs in to the portal
    Then the dashboard actions do not include "registrar_course_windows"
