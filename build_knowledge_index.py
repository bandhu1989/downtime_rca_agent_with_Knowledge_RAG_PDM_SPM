from dotenv import load_dotenv
load_dotenv() 
from knowledge_base import build_or_refresh_index
if __name__ == "__main__":
    print("Knowledge index:", build_or_refresh_index())
