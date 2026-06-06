import sys
import os

# Add the backend directory to sys.path so that `app.*` imports resolve
# when running pytest from the backend/ directory.
sys.path.insert(0, os.path.dirname(__file__))