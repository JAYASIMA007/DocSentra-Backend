import json
import jwt
from datetime import datetime, timedelta, date
from pymongo import MongoClient
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
import google.generativeai as genai

# MongoDB connection setup
client = MongoClient("mongodb+srv://ihub:ihub@harlee.6sokd.mongodb.net/")
db = client["DocSentra"]

# Collections
receptionist_collection = db["receptionists"]
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
    token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"jwt": token}

# ========================== Utility ============================
def generate_custom_id(prefix, collection):
    count = collection.count_documents({}) + 1
    return f"{prefix}{str(count).zfill(3)}"

def calculate_age(dob_str):
    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

GEMINI_API_KEY = "AIzaSyBx-wloOHkhhg4CCOAPyISy3SOk2CVFO80"
genai.configure(api_key=GEMINI_API_KEY)

# Receptionist Register
@csrf_exempt
def receptionist_register(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        if receptionist_collection.find_one({"email": email}):
            return JsonResponse({"error": "Receptionist already exists"}, status=400)

        password = data.get("password", "")
        confirm_password = data.get("confirm_password", "")
        if password != confirm_password:
            return JsonResponse({"error": "Passwords do not match"}, status=400)

        receptionist_data = {
            "receptionist_id": generate_custom_id("DSR", receptionist_collection),
            "first_name": data.get("first_name", "").strip(),
            "last_name": data.get("last_name", "").strip(),
            "email": email,
            "phone_number": data.get("phone_number", "").strip(),
            "password": make_password(password),
            "role": "receptionist",
            "created_at": datetime.now(),
            "last_login": None,
        }
        receptionist_collection.insert_one(receptionist_data)
        return JsonResponse({"message": "Receptionist registered successfully"}, status=201)

    except Exception:
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)

# Receptionist Login
@csrf_exempt
def receptionist_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return JsonResponse({"error": "Email and password are required"}, status=400)

        receptionist = receptionist_collection.find_one({"email": email})
        if not receptionist:
            return JsonResponse({"error": "Email not found"}, status=404)

        if check_password(password, receptionist["password"]):
            receptionist_collection.update_one({"email": email}, {"$set": {"last_login": datetime.now()}})
            token = generate_tokens(receptionist["_id"], receptionist["first_name"], "receptionist")
            return JsonResponse({"message": "Login successful", "token": token}, status=200)
        else:
            return JsonResponse({"error": "Invalid password"}, status=401)

    except Exception:
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)

# ========================== Patient Entry ==========================
@csrf_exempt
def create_patient(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)

        # Ensure no patient_id is passed to avoid accidental updates
        if data.get("patient_id"):
            return JsonResponse({"error": "Cannot update existing patient in this endpoint"}, status=400)

        # Prepare visit info
        visit_data = {
            "reason": data.get("reason"),
            "duration": data.get("duration"),
            "referred_department": data.get("referred_department"),
            "first_time_or_followup": data.get("first_time_or_followup"),
            "symptoms": data.get("symptoms", {}),
            "medical_history": data.get("medical_history", {}),
            "consent": data.get("consent", {}),
            "timestamp": datetime.now()
        }

        # Create patient data
        new_id = generate_custom_id("DSP", patients_collection)
        age = calculate_age(data.get("dob"))

        patient_data = {
            "patient_id": new_id,
            "full_name": data.get("full_name"),
            "dob": data.get("dob"),
            "gender": data.get("gender"),
            "contact_number": data.get("contact_number"),
            "created_at": datetime.now(),
            "age": age,
            "visits": [visit_data]
        }

        patients_collection.insert_one(patient_data)
        return JsonResponse({"message": "New patient created", "patient_id": new_id}, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def get_patient_info(request, patient_id):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        patient = patients_collection.find_one({"patient_id": patient_id})
        if not patient:
            return JsonResponse({"error": "Patient not found"}, status=404)

        visits = patient.get("visits", [])
        last_visit = visits[-1] if visits else {}

        basic_info = {
            "full_name": patient.get("full_name"),
            "dob": patient.get("dob"),
            "gender": patient.get("gender"),
            "contact_number": patient.get("contact_number"),
            "last_visit": patient.get("visits", [])[-1] if patient.get("visits") else {}
        }
        

        return JsonResponse({"patient": basic_info}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def update_patient(request):
    if request.method == "GET":
        try:
            patient_id = request.GET.get("patient_id")
            print(patient_id)
            if not patient_id:
                return JsonResponse({"error": "patient_id is required"}, status=400)

            patient = patients_collection.find_one({"patient_id": patient_id}, {"_id": 0})
            if not patient:
                return JsonResponse({"error": "Patient not found"}, status=404)

            return JsonResponse(patient, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            patient_id = data.get("patient_id")

            if not patient_id:
                return JsonResponse({"error": "patient_id is required"}, status=400)

            patient = patients_collection.find_one({"patient_id": patient_id})
            if not patient:
                return JsonResponse({"error": "Patient not found"}, status=404)

            # Allowed personal detail fields only
            personal_fields = ["full_name", "dob", "gender", "contact_number"]
            update_fields = {}

            for field in personal_fields:
                if field in data and data[field]:
                    update_fields[field] = data[field]

            if "dob" in update_fields:
                update_fields["age"] = calculate_age(update_fields["dob"])

            if not update_fields:
                return JsonResponse({"error": "No valid fields to update"}, status=400)

            patients_collection.update_one({"patient_id": patient_id}, {"$set": update_fields})

            return JsonResponse({"message": "Personal details updated successfully", "patient_id": patient_id}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    else:
        return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def add_visit_to_existing_patient(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        patient_id = data.get("patient_id")

        if not patient_id:
            return JsonResponse({"error": "Patient ID is required."}, status=400)

        patient = patients_collection.find_one({"patient_id": patient_id})
        if not patient:
            return JsonResponse({"error": "Patient not found."}, status=404)

        # Correctly extract medical history
        medical_history_data = data.get("medical_history", {})

        medical_history = {
            "allergies": medical_history_data.get("allergies", ""),
            "family_history": medical_history_data.get("family_history", ""),
            "past_surgeries": medical_history_data.get("past_surgeries", ""),
            "smoking_alcohol": medical_history_data.get("smoking_alcohol", "")
        }

        visit_data = {
            "reason": data.get("reason", ""),
            "duration": data.get("duration", ""),
            "referred_department": data.get("referred_department", ""),
            "first_time_or_followup": data.get("first_time_or_followup", ""),
            "assigned_doctor_id": data.get("assigned_doctor_id", ""),
            "symptoms": data.get("symptoms", []),  # List
            "medical_history": medical_history,      # Correct medical history object
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Push visit entry into visits array
        patients_collection.update_one(
            {"patient_id": patient_id},
            {"$push": {"visits": visit_data}}
        )

        return JsonResponse({
            "message": "New visit added successfully.",
            "patient_id": patient_id,
            "visit_summary": visit_data
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# ========================== Doctor Recommendation ==========================
def recommend_doctor(symptoms, age):
    description = symptoms.get('description', '')
    prompt = f"""
You are a medical specialist recommendation system. Your task is to analyze a patient's symptoms and age, then recommend the most appropriate medical specialist from a predefined list. Consider the symptoms' severity, the patient's age, and standard medical guidelines for specialist referrals. If the symptoms or age suggest a general evaluation is sufficient, recommend a General Practitioner.

**Input**:
- Symptoms: "{description}"
- Age: "{age}" years

**Available Specialists**:
- Pediatrician (for children, typically under 14, with general or specific pediatric conditions)
- Cardiologist (for heart-related issues, e.g., chest pain, palpitations)
- Neurologist (for neurological issues, e.g., severe headaches, seizures)
- General Practitioner (for general or non-specific symptoms, or when no specialist is clearly indicated)

**Instructions**:
1. Analyze the symptoms and age to determine the most appropriate specialist.
2. Use the following guidelines (but adapt based on medical reasoning):
   - For patients under 14 with symptoms like headache, nausea, or general illness, recommend a Pediatrician.
   - For symptoms like chest pain or heart-related issues, recommend a Cardiologist.
   - For symptoms like severe headaches with neurological signs (e.g., dizziness, vision changes), recommend a Neurologist.
   - For non-specific or mild symptoms, or when no specialist is clearly needed, recommend a General Practitioner.
3. Return the recommendation in JSON format with a single field:
{{"recommended_specialist": "<specialist_name>"}}
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash-8b")
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        result = json.loads(raw_text)
        recommended_specialist = result.get("recommended_specialist")

        doctors = list(doctor_collection.find({
            "specialty": recommended_specialist
        }))

        if doctors:
            doctor_list = [
                {
                    "doctor_id": doc.get("doctor_id"),
                    "name": f"{doc.get('first_name')} {doc.get('last_name')}"
                } for doc in doctors
            ]
            return JsonResponse({
                "recognized_text": description,
                "specialty": recommended_specialist,
                "doctors": doctor_list,
            })
        else:
            return JsonResponse({
                "recognized_text": description,
                "specialty": recommended_specialist,
                "message": "No doctor found for this specialization."
            })

    except json.JSONDecodeError:
        return JsonResponse({
            "recognized_text": description,
            "structured_output": "Could not parse model response as JSON.",
            "raw_response": response.text
        }, status=500)
    except Exception as e:
        return JsonResponse({
            "error": "Failed to connect to Gemini or generate content.",
            "details": str(e)
        }, status=500)

@csrf_exempt
def auto_recommend_doctor_from_patient(request):
    if request.method == "GET":
        try:
            patient_id = request.GET.get("patient_id")
            if not patient_id:
                return JsonResponse({"error": "Missing patient_id"}, status=400)

            patient = patients_collection.find_one({"patient_id": patient_id})
            if not patient:
                return JsonResponse({"error": "Patient not found"}, status=404)

            visits = patient.get("visits", [])
            if not visits:
                return JsonResponse({"error": "No visits found for this patient"}, status=404)

            latest_visit = visits[-1]
            symptoms = latest_visit.get("symptoms", {})
            age = patient.get("age", 0)

            # Normalize if symptoms is a list
            if isinstance(symptoms, list):
                symptoms = {"description": ", ".join(symptoms)}

            return recommend_doctor(symptoms, age)

        except Exception as e:
            return JsonResponse({
                "error": "Failed to process request.",
                "details": str(e)
            }, status=500)
    else:
        return JsonResponse({"message": "Only GET method is allowed."}, status=405)
    
#========================== Assign Doctor to Visit ==========================
@csrf_exempt
def get_all_patients(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        patients = patients_collection.find({}, {"_id": 0})  # Exclude Mongo _id
        patient_list = list(patients)

        return JsonResponse({"patients": patient_list}, status=200)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt
def assign_doctor_to_visit(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")

        if not patient_id or not doctor_id:
            return JsonResponse({"error": "Patient ID and Doctor ID are required."}, status=400)

        # Find the patient
        patient = patients_collection.find_one({"patient_id": patient_id})
        if not patient:
            return JsonResponse({"error": "Patient not found."}, status=404)

        visits = patient.get("visits", [])
        if not visits:
            return JsonResponse({"error": "No visits found for this patient."}, status=400)

        # Normalize timestamp
        def normalize_timestamp(timestamp):
            if isinstance(timestamp, datetime):
                return timestamp
            try:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.min

        # Find latest visit (by latest normalized timestamp)
        latest_visit = max(visits, key=lambda v: normalize_timestamp(v.get("timestamp", datetime.min)))
        latest_timestamp = latest_visit["timestamp"]

        # Update the assigned_doctor_id for the visit with matching timestamp
        patients_collection.update_one(
            {"patient_id": patient_id, "visits.timestamp": latest_timestamp},
            {"$set": {"visits.$.assigned_doctor_id": doctor_id}}
        )

        return JsonResponse({"message": "Doctor assigned successfully."}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
