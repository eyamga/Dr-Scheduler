from flask import Blueprint, request, jsonify
from flask_restful import Resource
from werkzeug.utils import secure_filename
import os
from app.services.flashcard_service import FlashcardService
from app.utils.error_handler import handle_errors, ProcessingError
from config import Config

bp = Blueprint('api', __name__)

class FlashcardGenerator(Resource):
    @handle_errors()
    async def post(self):
        """Generate flashcards from provided text or file"""
        service = FlashcardService()
        
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return {'error': 'No file selected'}, 400
                
            filename = secure_filename(file.filename)
            filepath = os.path.join(Config.OUTPUT_DIR, filename)
            file.save(filepath)
            
            try:
                flashcards = await service.generate_flashcards_from_file(
                    file_path=filepath,
                    title=request.form.get('title', 'Untitled'),
                    model=request.form.get('model'),
                    mode=request.form.get('mode', 'default'),
                    chunking_method=request.form.get('chunking_method'),
                    topic=request.form.get('topic', 'default')
                )
                
                return {'flashcards': flashcards}, 200
                
            finally:
                # Clean up uploaded file
                os.remove(filepath)
                
        elif request.is_json:
            data = request.get_json()
            if not data or 'text' not in data:
                return {'error': 'No text provided'}, 400
                
            flashcards = await service.generate_flashcards(
                text=data['text'],
                title=data.get('title', 'Untitled'),
                model=data.get('model'),
                mode=data.get('mode', 'default'),
                chunking_method=data.get('chunking_method'),
                topic=data.get('topic', 'default')
            )
            
            return {'flashcards': flashcards}, 200
            
        else:
            return {'error': 'Invalid request'}, 400