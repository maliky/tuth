"""Resource mapping for common data."""

# UM_STUDENT -> Student
UM_STUDENT__STUDENT_MAP = {
    # all other fields should go to bio
    "bio": ["Comments", "Denomination", "EducationLevel", "Occupation", "Scholarship", "Dormitory", "MealType"],
    "birth_date": "DateOfBirth",
    "birth_place": "PlaceOfBirth",
    "current_enrolled_semester": ["YearOfEntry", "SemesterOfEntry"],  # ->
    "curriculum": [
        "Curriculum",
        "College",
        "Major",
        "Minor",
        "ProgramID",
        "EnrollmentType",
    ],  # ->
    "emergency_contact": ["EmergencyContact"],
    "entry_semester": ["DateOfEntry", "DateOfEnrollment", "DateAmitted"],  # ->
    "father_address": ["FatherAddress"],
    "father_name": ["FatherName"],
    "gender": ["Sex"],
    "last_school_attended": ["LastSchoolAttended", "LastSchoolType"],
    "marital_status": ["MaritalStatus"],
    "mother_address": ["MotherAdress"],
    "mother_name": ["MotherName"],
    "nationality": ["Nationality"],
    "origin_county": ["CountyOfOrigin"],
    "phone_number": ["Phone"],
    "physical_address": ["AddressLine1", "AddressLine2", "AddressLine3", "District"],
    "reason_for_leaving": ["ReasonForLeaving"],
    "student_id": ["StudnetID"],  #
    "user": ["FirstName", "Lastname", "MiddleName", "Email"],  # ->
    # "AdmissionStatus": "admissionstatus",
    # "DebutFeeUploaded": "debutfeeuploaded",
    # "Dormitory": "dormitory",
    # "PresentStatus": "presentstatus",
    # "TotCrHrsComp": "totcrhrscomp",
    # "Uploaded": "uploaded",
    # "ImageAppLetter":"imageappletter",
    # "ImageMedCertificate":"imagemedcertificate",
    # "ImageRecomComm":"imagerecomcomm",
    # "ImageRecomLastSch":"imagerecomlastsch",
    # "ImageRecomReli":"imagerecomreli",
    # "ImageReportCard":"imagereportcard",
    # "ImageTranscript":"imagetranscript",
    # "ImageWaecCert":"imagewaeccert",
    # "Password":"password",
    # "Photo":"photo",  # exists but need to check content format
    # "Salt":"salt",
}
