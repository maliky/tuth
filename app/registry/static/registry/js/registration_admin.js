(function ($) {
  function initRegistrationSectionField() {
    var $section = $("#id_section");
    if (!$section.length) {
      return;
    }
    var studentFieldId = $section.attr("data-student-field");
    if (!studentFieldId) {
      return;
    }
    var $student = $("#" + studentFieldId);
    if (!$student.length) {
      return;
    }

    var previousStudent = $student.val() || "";
    function toggleSection() {
      var currentStudent = $student.val() || "";
      if (currentStudent !== previousStudent) {
        $section.val(null).trigger("change");
        previousStudent = currentStudent;
      }
    }

    function configureSectionAutocomplete() {
      var select2 = $section.data("select2");
      if (!select2 || !select2.options || !select2.options.options) {
        return false;
      }
      var options = select2.options.options;
      var ajaxOptions = options.ajax || {};
      var baseData = ajaxOptions.data;
      ajaxOptions.data = function (params) {
        var data = baseData
          ? baseData(params)
          : {
              term: params.term,
              page: params.page,
              app_label: $section.attr("data-app-label"),
              model_name: $section.attr("data-model-name"),
              field_name: $section.attr("data-field-name"),
            };
        data.student = $student.val() || "";
        data.requires_student = "1";
        return data;
      };
      options.ajax = ajaxOptions;
      $section.select2("destroy").select2(options);
      return true;
    }

    (function retryConfigure(attemptsLeft) {
      if (configureSectionAutocomplete()) {
        return;
      }
      if (attemptsLeft <= 0) {
        return;
      }
      window.setTimeout(function () {
        retryConfigure(attemptsLeft - 1);
      }, 200);
    })(10);

    toggleSection();
    // Wait for select2 to sync the value before resetting section choices.
    function handleStudentChange() {
      window.requestAnimationFrame(toggleSection);
    }
    $student.on("change select2:select select2:clear", handleStudentChange);
  }

  function initRegistrationSectionsField() {
    var $sections = $("#id_sections");
    if (!$sections.length) {
      return;
    }
    var $student = $("#id_student");
    if (!$student.length) {
      return;
    }
    var currentStudent = $student.val() || "";
    function redirectForStudent() {
      var nextStudent = $student.val() || "";
      if (nextStudent === currentStudent) {
        return;
      }
      currentStudent = nextStudent;
      var url = new URL(window.location.href);
      if (nextStudent) {
        url.searchParams.set("student", nextStudent);
      } else {
        url.searchParams.delete("student");
      }
      window.location.assign(url.toString());
    }
    $student.on("change select2:select select2:clear", redirectForStudent);
  }

  $(function () {
    initRegistrationSectionField();
    initRegistrationSectionsField();
  });
})(django.jQuery);
