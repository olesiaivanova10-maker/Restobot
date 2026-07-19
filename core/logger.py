import sys
import os
import glob
from loguru import logger

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

MAX_LOG_FILES = 5

def cleanup_old_logs():
    """Оставляет только MAX_LOG_FILES последних лог-файлов (включая .zip)"""
    log_files = glob.glob(os.path.join(log_dir, "bot_*.log*"))
    # Сортируем по имени (дата в имени обеспечивает хронологический порядок)
    log_files.sort()
    
    if len(log_files) > MAX_LOG_FILES:
        files_to_delete = log_files[:-MAX_LOG_FILES]
        for f in files_to_delete:
            try:
                os.remove(f)
            except OSError:
                pass

# Чистим старые логи при запуске бота
cleanup_old_logs()

# Remove standard console logger
logger.remove()

# Add customized console logger
logger.add( 
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# Add rotating file logger (daily rotation, compression, keep 5 latest via cleanup_old_logs)
logger.add(
    os.path.join(log_dir, "bot_{time:YYYY-MM-DD}.log"),
    rotation="00:00",
    retention=None,
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    encoding="utf-8"
)
