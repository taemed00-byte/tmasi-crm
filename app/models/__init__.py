from app.models.user import User
from app.models.whatsapp import WhatsAppLine, Conversation, Message, MediaFile
from app.models.patient import Patient, PatientDocument
from app.models.doctor import Doctor
from app.models.clinic import Clinic
from app.models.appointment import Appointment
from app.models.portal import PatientPortalOTP

__all__ = [
    "User", "WhatsAppLine", "Conversation", "Message", "MediaFile",
    "Patient", "PatientDocument", "Doctor", "Clinic", "Appointment",
    "PatientPortalOTP",
]
