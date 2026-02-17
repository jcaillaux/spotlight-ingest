from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env', override=True)

ROOT = Path(__file__).parent

SPOTLIGHT_REPO = os.getenv('SPOTLIGHT_REPO')

DATA = ROOT / 'data'

LOGS = ROOT / 'logs'

metadata = DATA / "metadata.db"

IMG = DATA / 'images'