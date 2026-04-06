from django.urls import path
from . import views

urlpatterns = [
    path("sessions/", views.create_session, name="create_session"),
    path("sessions/<uuid:session_id>/", views.get_session, name="get_session"),
    path("sessions/<uuid:session_id>/validate/", views.validate_session, name="validate_session"),
    path("sessions/<uuid:session_id>/research/", views.start_research, name="start_research"),
    path("sessions/<uuid:session_id>/stream/", views.stream_session, name="stream_session"),
    path("sessions/<uuid:session_id>/results/", views.get_results, name="get_results"),
]
