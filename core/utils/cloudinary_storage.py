# backend/core/utils/cloudinary_storage.py
import cloudinary
import cloudinary.uploader
from django.conf import settings
import io
from PIL import Image
import base64

class CloudinaryStorage:
    """
    Utility class for uploading files to Cloudinary
    """
    
    @staticmethod
    def upload_image(image_file, folder="advision/images", public_id=None):
        """
        Upload image to Cloudinary
        
        Args:
            image_file: File object, PIL Image, or file path
            folder: Cloudinary folder path
            public_id: Optional custom public ID
            
        Returns:
            dict: Upload response with 'url' and 'public_id'
        """
        try:
            upload_options = {
                'folder': folder,
                'resource_type': 'image',
                'format': 'png',
                'quality': 'auto:best',
            }
            
            if public_id:
                upload_options['public_id'] = public_id
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                image_file,
                **upload_options
            )
            
            return {
                'success': True,
                'url': result.get('secure_url'),
                'public_id': result.get('public_id'),
                'format': result.get('format'),
                'width': result.get('width'),
                'height': result.get('height'),
            }
            
        except Exception as e:
            print(f"Cloudinary upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def upload_base64_image(base64_string, folder="advision/images", public_id=None):
        """
        Upload base64 encoded image to Cloudinary
        
        Args:
            base64_string: Base64 encoded image string
            folder: Cloudinary folder path
            public_id: Optional custom public ID
            
        Returns:
            dict: Upload response
        """
        try:
            # Remove data:image prefix if present
            if base64_string.startswith('data:image'):
                base64_string = base64_string.split(',')[1]
            
            # Decode base64
            image_data = base64.b64decode(base64_string)
            
            # Upload to Cloudinary
            return CloudinaryStorage.upload_image(
                io.BytesIO(image_data),
                folder=folder,
                public_id=public_id
            )
            
        except Exception as e:
            print(f"Base64 upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def upload_pil_image(pil_image, folder="advision/images", public_id=None):
        """
        Upload PIL Image to Cloudinary
        
        Args:
            pil_image: PIL Image object
            folder: Cloudinary folder path
            public_id: Optional custom public ID
            
        Returns:
            dict: Upload response
        """
        try:
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return CloudinaryStorage.upload_image(
                img_byte_arr,
                folder=folder,
                public_id=public_id
            )
            
        except Exception as e:
            print(f"PIL upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def upload_pdf_report(pdf_file, folder="advision/reports", public_id=None):
        """
        Upload PDF report to Cloudinary
        
        Args:
            pdf_file: PDF file object or path
            folder: Cloudinary folder path
            public_id: Optional custom public ID
            
        Returns:
            dict: Upload response
        """
        try:
            upload_options = {
                'folder': folder,
                'resource_type': 'raw',  # For PDFs
                'format': 'pdf',
            }
            
            if public_id:
                upload_options['public_id'] = public_id
            
            result = cloudinary.uploader.upload(
                pdf_file,
                **upload_options
            )
            
            return {
                'success': True,
                'url': result.get('secure_url'),
                'public_id': result.get('public_id'),
            }
            
        except Exception as e:
            print(f"PDF upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def delete_file(public_id, resource_type='image'):
        """
        Delete file from Cloudinary
        
        Args:
            public_id: Cloudinary public ID
            resource_type: 'image' or 'raw'
            
        Returns:
            dict: Deletion result
        """
        try:
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type
            )
            return {
                'success': result.get('result') == 'ok',
                'result': result
            }
        except Exception as e:
            print(f"Cloudinary delete error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_optimized_url(public_id, width=None, height=None, quality='auto'):
        """
        Get optimized image URL from Cloudinary
        
        Args:
            public_id: Cloudinary public ID
            width: Desired width
            height: Desired height
            quality: Image quality
            
        Returns:
            str: Optimized image URL
        """
        try:
            transformation = []
            
            if width:
                transformation.append(f'w_{width}')
            if height:
                transformation.append(f'h_{height}')
            if quality:
                transformation.append(f'q_{quality}')
            
            url = cloudinary.CloudinaryImage(public_id).build_url(
                transformation=transformation
            )
            
            return url
        except Exception as e:
            print(f"URL generation error: {str(e)}")
            return None