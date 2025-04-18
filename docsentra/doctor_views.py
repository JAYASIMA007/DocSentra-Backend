import json
import jwt
from datetime import datetime, timedelta
from pymongo import MongoClient
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
import base64
from django.conf import settings
import logging

# MongoDB connection setup
client = MongoClient("mongodb+srv://ihub:ihub@harlee.6sokd.mongodb.net/")
db = client["DocSentra"]

# Collections
doctor_collection = db["doctors"]
patients_collection = db["patients"]

# JWT config
JWT_SECRET = "secret"
JWT_ALGORITHM = "HS256"

def generate_tokens(user_id, name, role):
    access_payload = {
        "id": str(user_id),
        "name": name,
        "role": role,
        "exp": (datetime.now() + timedelta(hours=10)).timestamp(),
        "iat": datetime.now().timestamp(),
    }
    token = jwt.encode(access_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"jwt": token}

# ========================== Utility ============================
def generate_custom_id(prefix, collection):
    count = collection.count_documents({}) + 1
    return f"{prefix}{str(count).zfill(3)}"

# Set up logging
logger = logging.getLogger(__name__)

# Doctor Register
@csrf_exempt
def doctor_register(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        if doctor_collection.find_one({"email": email}):
            return JsonResponse({"error": "Doctor already exists"}, status=400)

        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")
        if password != confirm_password:
            return JsonResponse({"error": "Passwords do not match"}, status=400)

        doctor_data = {
            "doctor_id": generate_custom_id("DSD", doctor_collection),
            "first_name": data.get("first_name", "").strip(),
            "last_name": data.get("last_name", "").strip(),
            "email": email,
            "phone_number": data.get("phone_number", "").strip(),
            "password": make_password(password),
            "specialty": data.get("specialty", "").strip(),
            "role": "doctor",
            "created_at": datetime.now(),
            "last_login": None,
        }
        doctor_collection.insert_one(doctor_data)
        return JsonResponse({"message": "Doctor registered successfully"}, status=201)

    except Exception:
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)

# Doctor Login
@csrf_exempt
def doctor_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return JsonResponse({"error": "Email and password are required"}, status=400)

        doctor = doctor_collection.find_one({"email": email})
        if not doctor:
            return JsonResponse({"error": "Email not found"}, status=404)

        if check_password(password, doctor["password"]):
            doctor_collection.update_one({"email": email}, {"$set": {"last_login": datetime.now()}})
            token = generate_tokens(doctor["doctor_id"], doctor["first_name"], "doctor")
            return JsonResponse({"message": "Login successful", "token": token}, status=200)
        else:
            return JsonResponse({"error": "Invalid password"}, status=401)

    except Exception:
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)

@csrf_exempt
def update_doctor_status(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        doctor_id = data.get("doctor_id")
        new_status = data.get("status")

        if not doctor_id or not new_status:
            return JsonResponse({"error": "Doctor ID and Status are required."}, status=400)

        if new_status not in ["Available", "Unavailable"]:
            return JsonResponse({"error": "Invalid status value. Must be 'Available' or 'Unavailable'."}, status=400)

        result = doctor_collection.update_one(
            {"doctor_id": doctor_id},
            {"$set": {"status": new_status}}
        )

        if result.matched_count == 0:
            return JsonResponse({"error": "Doctor not found."}, status=404)

        return JsonResponse({"message": f"Doctor status updated to {new_status}."}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
# Manage Doctor Profile
@csrf_exempt
def update_doctor_profile(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Verify JWT token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({"error": "Authorization header missing or invalid"}, status=401)

        token = auth_header.split(' ')[1]
        try:
            decoded_token = jwt.decode(token, settings.JWT_SECRET, algorithms=settings.JWT_ALGORITHM)
            user_doctor_id = decoded_token.get('id')
        except jwt.InvalidTokenError:
            return JsonResponse({"error": "Invalid token"}, status=401)

        # Parse request body
        try:
            # Handle multipart/form-data for file uploads
            if 'application/json' in request.content_type:
                data = json.loads(request.body)
            else:
                # For FormData, extract JSON fields
                data = {}
                for key in ['doctor_id', 'full_name', 'specialization', 'qualifications', 'years_of_experience', 'email', 'phone_number']:
                    if key in request.POST:
                        data[key] = request.POST[key]
                if 'available_days_time_slots' in request.POST:
                    data['available_days_time_slots'] = json.loads(request.POST['available_days_time_slots'])
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

        doctor_id = data.get("doctor_id")
        print('doctor_id:', doctor_id)
        if not doctor_id:
            return JsonResponse({"error": "Doctor ID is required"}, status=400)

        # Ensure the user can only update their own profile
        if doctor_id != user_doctor_id:
            return JsonResponse({"error": "Unauthorized to update this profile"}, status=403)

        # Find the doctor
        doctor = doctor_collection.find_one({"doctor_id": doctor_id})
        if not doctor:
            return JsonResponse({"error": "Doctor not found"}, status=404)

        # Validate input data
        full_name = data.get("full_name", f"{doctor['first_name']} {doctor['last_name']}")
        if not full_name.strip():
            return JsonResponse({"error": "Full name is required"}, status=400)

        qualifications = data.get("qualifications", doctor.get("qualifications"))
        if not qualifications:
            return JsonResponse({"error": "Qualifications are required"}, status=400)

        years_of_experience = data.get("years_of_experience", doctor.get("years_of_experience"))
        try:
            years_of_experience = int(years_of_experience)
            if years_of_experience < 0:
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({"error": "Years of experience must be a non-negative integer"}, status=400)

        # Validate available_days_time_slots
        available_days_time_slots = data.get("available_days_time_slots", doctor.get("available_days_time_slots", {}))
        if not isinstance(available_days_time_slots, dict):
            return JsonResponse({"error": "Available days and time slots must be a dictionary"}, status=400)
        valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
        for day, slots in available_days_time_slots.items():
            if day not in valid_days:
                return JsonResponse({"error": f"Invalid day: {day}"}, status=400)
            if not isinstance(slots, list):
                return JsonResponse({"error": f"Time slots for {day} must be a list"}, status=400)
            for slot in slots:
                if not isinstance(slot, str) or not slot.strip():
                    return JsonResponse({"error": f"Invalid time slot for {day}: {slot}"}, status=400)

        # Prepare profile data
        profile_data = {
            "full_name": full_name,
            "email": data.get("email", doctor.get("email")),
            "phone_number": data.get("phone_number", doctor.get("phone_number")),
            "specialization": data.get("specialization", doctor.get("specialty")),
            "qualifications": qualifications,
            "years_of_experience": years_of_experience,
            "available_days_time_slots": available_days_time_slots,
        }

        # Handle profile photo
        if "profile_photo" in request.FILES:
            profile_photo = request.FILES["profile_photo"]
            # Validate file size (e.g., max 2MB) and type
            if profile_photo.size > 2 * 1024 * 1024:
                return JsonResponse({"error": "Profile photo must be less than 2MB"}, status=400)
            if not profile_photo.content_type.startswith('image/'):
                return JsonResponse({"error": "Profile photo must be an image file"}, status=400)
            try:
                image_base64 = base64.b64encode(profile_photo.read()).decode('utf-8')
                profile_data["profile_photo"] = image_base64
            except Exception as e:
                logger.error(f"Error processing image file: {str(e)}")
                return JsonResponse({"error": f"Error processing image file: {str(e)}"}, status=400)
        else:
            # Retain existing photo if not provided
            profile_data["profile_photo"] = doctor.get("profile_photo", '')

        profile_data["updated_at"] = datetime.now()

        # Log the update attempt
        logger.info(f"Updating profile for doctor_id: {doctor_id} with data: {profile_data}")

        # Update the doctor profile
        result = doctor_collection.update_one({"doctor_id": doctor_id}, {"$set": profile_data})

        if result.modified_count == 0:
            logger.warning(f"No changes made to profile for doctor_id: {doctor_id}")
            return JsonResponse({"message": "No changes made to profile"}, status=200)

        # Fetch the updated profile to return
        updated_doctor = doctor_collection.find_one({"doctor_id": doctor_id})
        response_data = {
            "message": "Doctor profile updated successfully",
            "profile": {
                "doctor_id": updated_doctor["doctor_id"],
                "full_name": updated_doctor["full_name"],
                "email": updated_doctor.get("email"),
                "phone_number": updated_doctor.get("phone_number"),
                "specialization": updated_doctor.get("specialty"),
                "qualifications": updated_doctor["qualifications"],
                "years_of_experience": updated_doctor["years_of_experience"],
                "available_days_time_slots": updated_doctor["available_days_time_slots"],
                "profile_photo": updated_doctor.get("profile_photo"),
                "updated_at": updated_doctor["updated_at"].isoformat(),
            }
        }

        logger.info(f"Profile updated successfully for doctor_id: {doctor_id}")
        return JsonResponse(response_data, status=200)

    except Exception as e:
        logger.error(f"Error updating doctor profile: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def get_doctor_profile(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({"error": "Authorization token missing or invalid"}, status=401)

        token = auth_header.split(' ')[1]

        try:
            decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            doctor_id = decoded_token.get("id")
        except jwt.ExpiredSignatureError:
            return JsonResponse({"error": "Token has expired"}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({"error": "Invalid token"}, status=401)

        if not doctor_id:
            return JsonResponse({"error": "Doctor ID not found in token"}, status=400)

        doctor = doctor_collection.find_one({"doctor_id": doctor_id})
        if not doctor:
            return JsonResponse({"error": "Doctor not found"}, status=404)

        profile_data = {
            "doctor_id": doctor["doctor_id"],
            "full_name": doctor.get("full_name"),
            "profile_photo": doctor.get("profile_photo"),
            "email": doctor["email"],
            "phone_number": doctor["phone_number"],
            "specialization": doctor.get("specialization"),
            "qualifications": doctor.get("qualifications"),
            "years_of_experience": doctor.get("years_of_experience"),
            "available_days_time_slots": doctor.get("available_days_time_slots"),
        }

        return JsonResponse({"profile": profile_data}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
# ========================== Get All Doctors ==========================
@csrf_exempt
def get_all_doctors(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        doctors = doctor_collection.find({}, {"_id": 0, "doctor_id": 1, "first_name": 1, "last_name": 1, "specialty": 1, "status": 1})
        doctor_list = []
        for doc in doctors:
            doctor_list.append({
                "doctor_id": doc.get("doctor_id"),
                "full_name": f"{doc.get('first_name')} {doc.get('last_name')}",
                "specialty": doc.get("specialty"),
                "status": doc.get("status", "Unavailable")  
            })
        return JsonResponse({"doctors": doctor_list}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# ========================== Get Patient Info ==========================
@csrf_exempt
def get_assigned_patients(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Extract Bearer token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({"error": "Authorization token missing or invalid"}, status=401)

        token = auth_header.split(' ')[1]

        try:
            decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            doctor_id = decoded_token.get("id")
        except jwt.ExpiredSignatureError:
            return JsonResponse({"error": "Token has expired"}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({"error": "Invalid token"}, status=401)

        if not doctor_id:
            return JsonResponse({"error": "Doctor ID not found in token"}, status=400)

        # Find assigned patients
        patients_cursor = patients_collection.find({}, {"_id": 0})
        assigned_patients = []

        def normalize_timestamp(timestamp):
            if isinstance(timestamp, datetime):
                return timestamp
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.min  # fallback if parsing fails

        for patient in patients_cursor:
            visits = patient.get("visits", [])
            if visits:
                latest_visit = max(visits, key=lambda v: normalize_timestamp(v.get("timestamp", datetime.min)))
                if latest_visit.get("assigned_doctor_id") == doctor_id:
                    assigned_patients.append(patient)

        return JsonResponse({"patients": assigned_patients}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt
def get_specific_patient(request, patient_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Find the specific patient
        patient = patients_collection.find_one({"patient_id": patient_id}, {"_id": 0})

        if not patient:
            return JsonResponse({"error": "Patient not found"}, status=404)

        return JsonResponse({"patient": patient}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)