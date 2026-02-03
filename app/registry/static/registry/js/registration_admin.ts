// Minimal Select2/jQuery types for this file (we avoid bundling @types here).
type Select2AjaxParamsT = {
  term?: string;
  page?: number;
};

type Select2AjaxDataT = Record<string, unknown>;

type Select2AjaxOptionsT = {
  data?: (params: Select2AjaxParamsT) => Select2AjaxDataT;
};

type Select2OptionsT = {
  ajax?: Select2AjaxOptionsT;
};

type Select2InstanceT = {
  options?: {
    options?: Select2OptionsT;
  };
};

type JQueryInstanceT = {
  length: number;
  attr: (name: string) => string | undefined;
  val: ((value: string | number | null) => JQueryInstanceT) &
    (() => string | number | null | undefined);
  data: (key: string) => unknown;
  on: (events: string, handler: () => void) => JQueryInstanceT;
  select2: (arg?: string | Select2OptionsT) => JQueryInstanceT;
  trigger: (event: string) => JQueryInstanceT;
};

type JQueryStaticT = ((selector: string) => JQueryInstanceT) &
  ((handler: () => void) => void);

// django.jQuery is the admin-safe jQuery instance (no global $).
declare const django: {
  jQuery: JQueryStaticT;
};

// Wrap in an IIFE to keep admin globals clean.
(function ($: JQueryStaticT) {
  /** Keep the section field synced with the currently selected student. */
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

    /** Patch Select2's AJAX data payload to include the student id. */
    function configureSectionAutocomplete(): boolean {
      var select2 = $section.data("select2") as Select2InstanceT | null;
      if (!select2 || !select2.options || !select2.options.options) {
        return false;
      }
      var options = select2.options.options;
      var ajaxOptions: Select2AjaxOptionsT = options.ajax || {};
      var baseData = ajaxOptions.data;
      ajaxOptions.data = function (params: Select2AjaxParamsT) {
        var data: Select2AjaxDataT = baseData
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

    // Select2 can initialize after this script runs; retry a few times.
    (function retryConfigure(attemptsLeft: number) {
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

  /** Redirect the multi-section admin page when the student filter changes. */
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
        url.searchParams.set("student", String(nextStudent));
      } else {
        url.searchParams.delete("student");
      }
      window.location.assign(url.toString());
    }
    $student.on("change select2:select select2:clear", redirectForStudent);
  }

  // DOM-ready hook for Django admin pages.
  $(function () {
    initRegistrationSectionField();
    initRegistrationSectionsField();
  });
})(django.jQuery);
