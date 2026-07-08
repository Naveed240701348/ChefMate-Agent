"""
ChefMate-Agent Configuration
Loads all settings from environment variables via .env
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    """Base configuration class."""

    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "chefmate-dev-secret-key")
    DEBUG      = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    # ---------------------------------------------------------------
    # IBM watsonx Orchestrate
    #
    # ORCHESTRATE_API_KEY   — IBM Cloud API Key (IAM authentication)
    # ORCHESTRATE_URL       — Full instance-scoped base URL
    #                         Format: https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<instance-id>
    #                         Example: https://api.au-syd.watson-orchestrate.cloud.ibm.com/instances/70df4f03-c326-4482-89a7-aef56ddfb202
    # ORCHESTRATE_AGENT_ID  — The agent ID shown in the Orchestrate console
    # IBM_INSTANCE_ID       — The Orchestrate service instance UUID (metadata only, embedded in ORCHESTRATE_URL)
    # ---------------------------------------------------------------
    ORCHESTRATE_API_KEY  = os.getenv("ORCHESTRATE_API_KEY", "")
    ORCHESTRATE_URL      = os.getenv(
        "ORCHESTRATE_URL",
        "https://api.au-syd.watson-orchestrate.cloud.ibm.com/instances/70df4f03-c326-4482-89a7-aef56ddfb202",
    )
    ORCHESTRATE_AGENT_ID = os.getenv("ORCHESTRATE_AGENT_ID", "")
    IBM_INSTANCE_ID      = os.getenv("IBM_INSTANCE_ID", "")   # metadata — already embedded in ORCHESTRATE_URL

    # Request settings
    REQUEST_TIMEOUT = 60    # seconds before giving up on AI response
    MAX_RETRIES     = 3     # number of retry attempts on failure
    RETRY_DELAY     = 2     # seconds to wait between retries (linear back-off)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


# Active config — change to ProductionConfig when deploying
config = DevelopmentConfig()
