
from dremio_simple_query.connect import get_token
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv(dotenv_path=".env")

def dremio_token():
    """Retrieves a Dremio authentication token based on the environment setup."""
    try:
        environment = os.getenv("DREMIO_ENV")
        
        if not environment:
            raise ValueError("DREMIO_ENV is not set.")

        if environment == "software":
            login_endpoint = os.getenv("DREMIO_LOGIN_END")
            username = os.getenv("DREMIO_USERNAME")
            password = os.getenv("DREMIO_PASSWORD")

            if not all([login_endpoint, username, password]):
                raise ValueError("Missing required environment variables for Dremio Software login.")

            payload = {"userName": username, "password": password}
            print("PAYLOAD:",payload)
            token = get_token(uri=login_endpoint, payload=payload)

        else:
            token = os.getenv("DREMIO_TOKEN")
            if not token:
                raise ValueError("DREMIO_TOKEN is not set for Dremio Cloud authentication.")

            token = get_token(token)

        if not token:
            raise ValueError("Failed to retrieve a valid Dremio token.")

        return token

    except Exception as e:
        print(f"Error retrieving Dremio token: {e}", file=sys.stderr)
        return None