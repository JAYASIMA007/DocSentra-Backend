# from pymongo import MongoClient
# import os
# import subprocess
# import numpy as np
# import soundfile as sf
# from resemblyzer import VoiceEncoder, preprocess_wav
# from sklearn.metrics.pairwise import cosine_similarity
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.core.files.storage import default_storage
# from django.conf import settings
# import whisper
# import logging

# # Setup logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler(os.path.join(settings.BASE_DIR, 'debug.log'))
#     ]
# )
# logger = logging.getLogger(__name__)

# # MongoDB connection setup
# client = MongoClient("mongodb+srv://ihub:ihub@harlee.6sokd.mongodb.net/")
# db = client["DocSentra"]
# collection = db["Doctor_Voice_embeddings"]

# # ==== Setup ====
# UPLOAD_DIR = os.path.join(settings.BASE_DIR, 'Uploads')
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# USER1_PATH = os.path.join(UPLOAD_DIR, 'Doctor_audio.wav')
# USER2_PATH = os.path.join(UPLOAD_DIR, 'Patient_audio.wav')
# LIVE_PATH = os.path.join(UPLOAD_DIR, 'live_audio.wav')

# encoder = VoiceEncoder()
# user1_embedding = None
# user2_embedding = None

# # Initialize Whisper model
# try:
#     logger.info("Loading Whisper model")
#     whisper_model = whisper.load_model("base")  # Use 'base' for efficiency
#     logger.info("Whisper model loaded successfully")
# except Exception as e:
#     logger.error(f"Failed to load Whisper model: {str(e)}")
#     raise

# def convert_to_wav(src_path, dest_path):
#     logger.info(f"Converting {src_path} to {dest_path}")
#     try:
#         result = subprocess.run(
#             ['ffmpeg', '-y', '-i', src_path, '-ar', '16000', '-ac', '1', dest_path],
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE
#         )
#         if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
#             error_msg = f"FFmpeg failed. Log:\n{result.stderr.decode()}"
#             logger.error(error_msg)
#             return {'error': error_msg}
#         os.remove(src_path)
#         logger.info(f"Converted to {dest_path}")
#         return dest_path
#     except Exception as e:
#         logger.error(f"Error in convert_to_wav: {str(e)}")
#         return {'error': str(e)}

# @csrf_exempt
# def upload_live_audio(request):
#     logger.info("Entering upload_live_audio")
#     try:
#         logger.info(f"Request method: {request.method}, Files: {request.FILES}")
#         if request.method != 'POST':
#             logger.error(f"Invalid request method: {request.method}")
#             return JsonResponse({"error": "Method not allowed"}, status=405)

#         if not request.FILES.get('live_audio'):
#             logger.error("No live_audio file in request")
#             return JsonResponse({"error": "No audio file provided"}, status=400)

#         uploaded_file = request.FILES['live_audio']
#         logger.info(f"Uploaded file: name={uploaded_file.name}, size={uploaded_file.size}")
#         live_audio_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
#         logger.info(f"Saving uploaded file to {live_audio_path}")

#         with open(live_audio_path, 'wb') as f:
#             for chunk in uploaded_file.chunks():
#                 f.write(chunk)
#         logger.info(f"Saved uploaded file to {live_audio_path}")

#         result = convert_to_wav(live_audio_path, LIVE_PATH)
#         if not isinstance(result, str):
#             logger.error(f"Audio conversion failed: {result['error']}")
#             return JsonResponse({"error": result['error']}, status=500)
#         logger.info(f"Audio converted to {result}")

#         # Fetch doctor embedding from MongoDB
#         logger.info("Fetching doctor embedding from MongoDB")
#         doctor_doc = collection.find_one({}, sort=[('_id', -1)])
#         if not doctor_doc or 'embedding' not in doctor_doc:
#             logger.error("Doctor embedding not found in the database")
#             return JsonResponse({"error": "Doctor embedding not found in the database"}, status=500)
#         doctor_embedding = np.array(doctor_doc['embedding'])
#         logger.info("Doctor embedding fetched successfully")

#         # Process live audio
#         logger.info(f"Reading audio file: {LIVE_PATH}")
#         wav, sr = sf.read(LIVE_PATH)
#         if wav.ndim > 1:
#             wav = np.mean(wav, axis=1)
#         wav_preprocessed = preprocess_wav(wav, source_sr=sr)
#         _, cont_embeds, _ = encoder.embed_utterance(wav_preprocessed, return_partials=True)

#         segment_duration = len(wav_preprocessed) / sr / len(cont_embeds)
#         logger.info(f"Segment duration: {segment_duration}, Number of segments: {len(cont_embeds)}")
#         transcription_result = []

#         # Transcribe the entire audio
#         logger.info(f"Transcribing audio: {LIVE_PATH}")
#         transcription = whisper_model.transcribe(LIVE_PATH)
#         segments = transcription['segments']
#         logger.info(f"Transcription completed: {len(segments)} segments")

#         # Track processed segment ends to avoid duplication
#         processed_ends = set()
#         # Match Whisper segments with voice embeddings
#         for i, embed in enumerate(cont_embeds):
#             similarity = cosine_similarity([embed], [doctor_embedding])[0][0]
#             speaker = "Doctor" if similarity > 0.70 else "Patient"
#             segment_start = i * segment_duration
#             segment_end = (i + 1) * segment_duration
#             logger.info(f"Processing segment {i}: start={segment_start}, end={segment_end}, speaker={speaker}")

#             # Find corresponding transcription segment
#             segment_text = ""
#             for seg in segments:
#                 if seg['end'] not in processed_ends and seg['start'] <= segment_end and seg['end'] >= segment_start:
#                     segment_text += seg['text'] + " "
#                     processed_ends.add(seg['end'])
#             segment_text = segment_text.strip()

#             if segment_text and segment_text not in [res['text'] for res in transcription_result]:
#                 transcription_result.append({
#                     "speaker": speaker,
#                     "text": segment_text,
#                     "value": round(similarity, 3)
#                 })
#                 logger.info(f"Segment {i} transcribed: {speaker}: {segment_text}")

#         # Format output
#         formatted_output = [f"{res['speaker']}: {res['text']}" for res in transcription_result]
#         if not formatted_output:
#             logger.warning("No valid transcriptions produced")
#             return JsonResponse({"error": "No valid transcriptions produced"}, status=500)

#         logger.info(f"Returning transcription result: {formatted_output}")
#         return JsonResponse({"transcription_result": formatted_output})

#     except Exception as e:
#         logger.error(f"Unexpected error in upload_live_audio: {str(e)}")
#         return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)