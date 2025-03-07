from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
import boto3
from botocore.exceptions import ClientError
import os
from io import BytesIO
import time

# Function to directly upload string content to DO Spaces
def upload_content_to_spaces(content, object_name):
    """Upload string content directly to DigitalOcean Spaces and return its URL"""
    # Create a Spaces session with DO credentials
    session = boto3.session.Session()
    client = session.client('s3',
                           region_name=settings.AWS_S3_REGION_NAME,
                           endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                           aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                           aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
    
    # Convert string content to bytes
    content_bytes = content.encode('utf-8')
    
    # Upload the content
    try:
        # Add reports/ prefix to object name
        object_name = f"reports/{object_name}"
        
        # Upload directly from memory
        client.upload_fileobj(
            BytesIO(content_bytes), 
            settings.AWS_STORAGE_BUCKET_NAME, 
            object_name,
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'text/plain'}
        )
        
        # Return the URL
        if hasattr(settings, 'AWS_S3_CUSTOM_DOMAIN') and settings.AWS_S3_CUSTOM_DOMAIN:
            url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{object_name}"
        else:
            url = f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_STORAGE_BUCKET_NAME}/{object_name}"
        
        return url
    except ClientError as e:
        print(f"Error uploading content to DO Spaces: {e}")
        return None
    

def upload_file_to_spaces(file_content, filepath):
    """Upload file content to DigitalOcean Spaces and return the URL"""
    from django.conf import settings
    import boto3
    
    print(f"📤 UPLOAD REQUEST - Path: {filepath}, Size: {len(file_content)} bytes")
    print(f"📤 Timestamp: {time.time()}")
    
    try:
        # Get DO Spaces settings
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        endpoint = settings.AWS_S3_ENDPOINT_URL
        access_key = settings.AWS_ACCESS_KEY_ID
        secret_key = settings.AWS_SECRET_ACCESS_KEY
        region = settings.AWS_S3_REGION_NAME
        
        print(f"📊 USING DO SETTINGS: Bucket={bucket}")
        
        # Create S3 client
        s3 = boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region)
            
        # Set content type
        content_type = 'application/octet-stream'
        if filepath.endswith('.wav'):
            content_type = 'audio/wav'
        elif filepath.endswith('.txt'):
            content_type = 'text/plain'
        elif filepath.endswith('.mp3'):
            content_type = 'audio/mpeg'
            
        # Upload file
        response = s3.put_object(
            Bucket=bucket,
            Key=filepath,
            Body=file_content,
            ACL='public-read',
            ContentType=content_type
        )
        
        # Verify the upload was successful by checking response
        if 'ETag' in response:
            # Get URL to file
            url = f"https://{bucket}.{region}.digitaloceanspaces.com/{filepath}"
            print(f"✅ UPLOAD SUCCESS: {url}")
            
            # Verify file exists
            try:
                head = s3.head_object(Bucket=bucket, Key=filepath)
                print(f"✅ VERIFIED: File exists in bucket, size={head['ContentLength']}")
            except Exception as e:
                print(f"⚠️ File verification warning: {str(e)}")
                
            return url
        else:
            print(f"❌ UPLOAD FAILED: Response did not contain ETag: {response}")
            return None
            
    except Exception as e:
        print(f"❌ UPLOAD ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def delete_file_from_spaces(filepath):
    """Delete a file from DigitalOcean Spaces"""
    from django.conf import settings
    import boto3
    
    print(f"🗑️ DELETE REQUEST - Path: {filepath}")
    
    try:
        # Get DO Spaces settings
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        endpoint = settings.AWS_S3_ENDPOINT_URL
        access_key = settings.AWS_ACCESS_KEY_ID
        secret_key = settings.AWS_SECRET_ACCESS_KEY
        region = settings.AWS_S3_REGION_NAME
        
        # Create S3 client
        s3 = boto3.client('s3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region)
            
        # Delete the file
        s3.delete_object(
            Bucket=bucket,
            Key=filepath
        )
        
        print(f"✅ DELETE SUCCESS: Removed {filepath} from bucket {bucket}")
        return True
            
    except Exception as e:
        print(f"❌ DELETE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False