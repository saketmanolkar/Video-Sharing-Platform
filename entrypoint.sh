#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput
# Create a compatibility layer for TTS API
# cat > /app/tts_compatibility.py << 'EOF'
# # Create compatibility layer for different TTS versions
# import sys
# import importlib.util

# # Check if TTS.api module exists
# if importlib.util.find_spec("TTS.api") is None:
#     print("Creating TTS.api compatibility layer")
#     # If TTS.api doesn't exist, create it
#     import TTS
#     import types
    
#     # Create the api module
#     TTS.api = types.ModuleType("TTS.api")
#     sys.modules["TTS.api"] = TTS.api
    
#     # Create the TTS module
#     from TTS.utils.synthesizer import Synthesizer
#     TTS.api.TTS = Synthesizer
    
#     print("TTS compatibility layer created successfully")
# else:
#     print("Using existing TTS.api module")
# EOF

# Run the command provided as arguments
exec "$@"
