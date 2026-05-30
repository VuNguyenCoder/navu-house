import logging
import tempfile
import time
from pathlib import Path

from rest_framework.views import APIView
from rest_framework.parsers import BaseParser, MultiPartParser
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

