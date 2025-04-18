from django.urls import path
from .receptionist_views import *
from .doctor_views import *
from .speech import *

urlpatterns = [
    # Authentication routes
    path("receptionist/register/", receptionist_register, name="receptionist_register"),
    path("receptionist/login/", receptionist_login, name="receptionist_login"),
    path("doctor/register/", doctor_register, name="doctor_register"),
    path("doctor/login/", doctor_login, name="doctor_login"),

    # Receptionist API routes
    path('patient/create/', create_patient, name='create_patient'),
    path('patient/update/', update_patient, name='update_patient'),
    path('add-visit/', add_visit_to_existing_patient),
    path('assign-doctor/', assign_doctor_to_visit, name="assign_doctor_to_patient"),
    path("patient/<str:patient_id>/", get_patient_info, name="get_patient_info"),
    path('get-all-patients/', get_all_patients, name='get_all_patients'),
    path("auto-recommend-doctor/", auto_recommend_doctor_from_patient, name="auto_recommend_doctor"),
    
    # Doctor API routes
    path('doctor/profile/update/', update_doctor_profile, name='manage_doctor_profile'),
    path('update-doctor-status/', update_doctor_status, name='update_doctor_status'),
    path('doctor/profile/', get_doctor_profile, name='get_doctor_profile'),
    path('doctors/', get_all_doctors, name='get_all_doctors'),
    path('get-assigned-patients/',get_assigned_patients, name='get_assigned_patients'),
    # path('upload_live_audio/', upload_live_audio, name='upload_live_audio'),
   
]
