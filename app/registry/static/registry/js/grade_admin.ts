// Minimal Select2/jQuery types for this file (we avoid bundling @types here).
type GradeSelect2AjaxParamsT = {
  term?: string;
  page?: number;
};

type GradeSelect2AjaxDataT = Record<string, unknown>;

type GradeSelect2AjaxOptionsT = {
  data?: (params: GradeSelect2AjaxParamsT) => GradeSelect2AjaxDataT;
};

type GradeSelect2OptionsT = {
  ajax?: GradeSelect2AjaxOptionsT;
};

type GradeSelect2InstanceT = {
  options?: {
    options?: GradeSelect2OptionsT;
  };
};

type GradeJQueryInstanceT = {
  length: number;
  attr: (name: string) => string | undefined;
  val: ((value: string | number | null) => GradeJQueryInstanceT) &
    (() => string | number | null | undefined);
  data: (key: string) => unknown;
  on: (events: string, handler: () => void) => GradeJQueryInstanceT;
  select2: (arg?: string | GradeSelect2OptionsT) => GradeJQueryInstanceT;
  trigger: (event: string) => GradeJQueryInstanceT;
};

type GradeJQueryStaticT = ((selector: string) => GradeJQueryInstanceT) &
  ((handler: () => void) => void);

type GradeDjangoAdminT = {
  jQuery?: GradeJQueryStaticT;
};

type GradeAdminWindowT = Window &
  typeof globalThis & {
    django?: GradeDjangoAdminT;
    jQuery?: GradeJQueryStaticT;
  };

function gradeAdminWindow(): GradeAdminWindowT {
  /** Return a typed window with optional admin jQuery handles. */
  return window as GradeAdminWindowT;
}

function resolveGradeAdminJQuery(): GradeJQueryStaticT | null {
  /** Resolve Django admin jQuery without assuming load order or global $. */
  var currentWindow = gradeAdminWindow();
  return currentWindow.django?.jQuery || currentWindow.jQuery || null;
}

function runWhenGradeAdminJQueryIsReady(
  callback: (jquery: GradeJQueryStaticT) => void,
  attemptsLeft: number
) {
  /** Retry briefly because Django admin media ordering can vary by form widget. */
  var jquery = resolveGradeAdminJQuery();
  if (jquery) {
    callback(jquery);
    return;
  }
  if (attemptsLeft <= 0) {
    return;
  }
  window.setTimeout(function () {
    runWhenGradeAdminJQueryIsReady(callback, attemptsLeft - 1);
  }, 100);
}

function initGradeAdmin($: GradeJQueryStaticT) {
  /** Initialize Grade admin autocomplete scoping. */
  (function ($: GradeJQueryStaticT) {
    function initGradeStudentField() {
      /** Keep Grade.student options scoped to the selected Grade.section. */
      var $student = $("#id_student");
      var $section = $("#id_section");
      if (!$student.length || !$section.length) {
        return;
      }

      var previousSection = $section.val() || "";
      function clearStudentIfSectionChanged() {
        var currentSection = $section.val() || "";
        if (currentSection === previousSection) {
          return;
        }
        $student.val(null).trigger("change");
        previousSection = currentSection;
      }

      function configureStudentAutocomplete(): boolean {
        var select2 = $student.data("select2") as GradeSelect2InstanceT | null;
        if (!select2 || !select2.options || !select2.options.options) {
          return false;
        }
        var options = select2.options.options;
        var ajaxOptions: GradeSelect2AjaxOptionsT = options.ajax || {};
        var baseData = ajaxOptions.data;
        ajaxOptions.data = function (params: GradeSelect2AjaxParamsT) {
          var data: GradeSelect2AjaxDataT = baseData
            ? baseData(params)
            : {
                term: params.term,
                page: params.page,
                app_label: $student.attr("data-app-label"),
                model_name: $student.attr("data-model-name"),
                field_name: $student.attr("data-field-name"),
              };
          data.section = $section.val() || "";
          return data;
        };
        options.ajax = ajaxOptions;
        $student.select2("destroy").select2(options);
        return true;
      }

      (function retryConfigure(attemptsLeft: number) {
        if (configureStudentAutocomplete()) {
          return;
        }
        if (attemptsLeft <= 0) {
          return;
        }
        window.setTimeout(function () {
          retryConfigure(attemptsLeft - 1);
        }, 200);
      })(10);

      $section.on("change select2:select select2:clear", function () {
        window.requestAnimationFrame(clearStudentIfSectionChanged);
      });
    }

    $(function () {
      initGradeStudentField();
    });
  })($);
}

runWhenGradeAdminJQueryIsReady(initGradeAdmin, 20);
