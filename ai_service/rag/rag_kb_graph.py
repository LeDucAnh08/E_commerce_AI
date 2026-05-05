import argparse 
import os 
from datetime import datetime 
from pathlib import Path 
 
try: 
    from dotenv import load_dotenv 
except ModuleNotFoundError as exc: 
    raise SystemExit( 
        "Missing dependency: python-dotenv. Run: pip install -r requirements_assignment.txt" 
    ) from exc 
 
try: 
    from langchain_community.graphs import Neo4jGraph 
except ModuleNotFoundError as exc: 
    raise SystemExit( 
        "Missing dependency: langchain-community. Run: pip install -r requirements_assignment.txt" 
    ) from exc 
 
try: 
    from langchain.chains import GraphCypherQAChain 
except Exception: 
    from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain 
 
def build_llm(): 
    gemini_api_key = os.getenv("GEMINI_API_KEY") 
    openai_api_key = os.getenv("OPENAI_API_KEY") 
 
    if gemini_api_key: 
        from langchain_google_genai import ChatGoogleGenerativeAI 
 
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash") 
        llm = ChatGoogleGenerativeAI( 
            model=model_name, 
            temperature=0, 
            google_api_key=gemini_api_key, 
        ) 
        return llm, f"Gemini ({model_name})" 
 
    if openai_api_key: 
        from langchain_openai import ChatOpenAI 
 
 
        model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo") 
        llm = ChatOpenAI( 
            model=model_name, 
            temperature=0, 
            api_key=openai_api_key, 
        ) 
        return llm, f"OpenAI ({model_name})" 
 
    raise RuntimeError( 
        "No API key found. Set GEMINI_API_KEY (preferred) or OPENAI_API_KEY in .env" 
    ) 