import os
import time

from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_cohere import ChatCohere


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# MODEL CONFIGURATION
# ============================================================

NODE_2_GEMINI = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]

NODE_2_GROQ = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
]


NODE_3_GEMINI = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
]

NODE_3_GROQ = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]


# ============================================================
# RESPONSE CONTENT EXTRACTION
# ============================================================

def extract_content(response):
    """
    Extract text content from LangChain responses.

    Supports:
    - string
    - dict
    - list
    """

    content = getattr(
        response,
        "content",
        response
    )

    if isinstance(content, str):
        return content

    if isinstance(content, dict):

        return content.get(
            "text",
            str(content)
        )

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, str):

                parts.append(item)

            elif isinstance(item, dict):

                text = item.get(
                    "text"
                )

                if text:
                    parts.append(text)

        return "".join(parts)

    return str(content)


# ============================================================
# TOKEN USAGE EXTRACTION
# ============================================================

def extract_usage(response):
    """
    Extract token usage from LangChain/provider responses.

    Supports:

    1. LangChain usage_metadata
    2. response_metadata.token_usage
    3. response_metadata.usage
    4. prompt_tokens/completion_tokens
    """

    # ========================================================
    # METHOD 1: usage_metadata
    # ========================================================

    usage = getattr(
        response,
        "usage_metadata",
        None
    )

    if isinstance(usage, dict):

        input_tokens = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or 0
        )

        output_tokens = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or 0
        )

        total_tokens = (
            usage.get("total_tokens")
            or (
                input_tokens
                + output_tokens
            )
        )

        return {
            "input_tokens": int(
                input_tokens
            ),

            "output_tokens": int(
                output_tokens
            ),

            "total_tokens": int(
                total_tokens
            )
        }

    # ========================================================
    # METHOD 2: response_metadata
    # ========================================================

    response_metadata = getattr(
        response,
        "response_metadata",
        {}
    )

    if isinstance(
        response_metadata,
        dict
    ):

        token_usage = (
            response_metadata.get(
                "token_usage"
            )
            or response_metadata.get(
                "usage"
            )
            or {}
        )

        if isinstance(
            token_usage,
            dict
        ):

            input_tokens = (
                token_usage.get(
                    "input_tokens"
                )
                or token_usage.get(
                    "prompt_tokens"
                )
                or 0
            )

            output_tokens = (
                token_usage.get(
                    "output_tokens"
                )
                or token_usage.get(
                    "completion_tokens"
                )
                or 0
            )

            total_tokens = (
                token_usage.get(
                    "total_tokens"
                )
                or (
                    input_tokens
                    + output_tokens
                )
            )

            return {
                "input_tokens": int(
                    input_tokens
                ),

                "output_tokens": int(
                    output_tokens
                ),

                "total_tokens": int(
                    total_tokens
                )
            }

    # ========================================================
    # NO USAGE FOUND
    # ========================================================

    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    }


# ============================================================
# LLM CLIENT
# ============================================================

class LLMClient:

    def __init__(self):

        # ----------------------------------------------------
        # GEMINI KEYS
        # ----------------------------------------------------

        self.gemini_keys = []

        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            key = os.getenv(name)
            if key and key not in self.gemini_keys:
                self.gemini_keys.append(key)

        for i in range(1, 4):

            key = os.getenv(
                f"GEMINI_API_KEY_{i}"
            )

            if key and key not in self.gemini_keys:
                self.gemini_keys.append(
                    key
                )

        # ----------------------------------------------------
        # GROQ KEYS
        # ----------------------------------------------------

        self.groq_keys = []

        for i in range(1, 4):

            key = os.getenv(
                f"GROQ_API_KEY_{i}"
            )

            if key:
                self.groq_keys.append(
                    key
                )

        # ----------------------------------------------------
        # COHERE
        # ----------------------------------------------------

        self.cohere_keys = []

        cohere_key = (
            os.getenv(
                "COHERE_API_KEY"
            )
            or os.getenv(
                "COHERE_API_KEY_1"
            )
        )

        if cohere_key:

            self.cohere_keys.append(
                cohere_key
            )

    # ========================================================
    # PROVIDER EXECUTION
    # ========================================================

    def _try_providers(
        self,
        prompt,
        gemini_models,
        groq_models,
    ):

        if not self.gemini_keys and not self.groq_keys and not self.cohere_keys:
            raise RuntimeError(
                "No LLM API key is configured. Add GEMINI_API_KEY_1 to .env."
            )

        # ====================================================
        # GEMINI
        # ====================================================

        for api_key in self.gemini_keys:

            for model_name in gemini_models:

                try:

                    model = ChatGoogleGenerativeAI(
                        model=model_name,
                        google_api_key=api_key,
                        temperature=0
                    )

                    start = time.time()

                    response = model.invoke(
                        prompt
                    )

                    latency = (
                        time.time()
                        - start
                    )

                    content = extract_content(
                        response
                    )

                    usage = extract_usage(
                        response
                    )

                    print(
                        f"[LLM] Gemini "
                        f"{model_name} "
                        f"successful | "
                        f"Tokens: "
                        f"{usage['input_tokens']}"
                        f"+"
                        f"{usage['output_tokens']}"
                    )

                    return {
                        "content": content,

                        "provider":
                            f"gemini/{model_name}",

                        "usage": usage,

                        "latency": latency
                    }

                except Exception as e:

                    print(
                        f"[LLM] Gemini "
                        f"{model_name} "
                        f"failed: {e}"
                    )

        # ====================================================
        # GROQ
        # ====================================================

        for api_key in self.groq_keys:

            for model_name in groq_models:

                try:

                    model = ChatGroq(
                        model=model_name,
                        groq_api_key=api_key,
                        temperature=0
                    )

                    start = time.time()

                    response = model.invoke(
                        prompt
                    )

                    latency = (
                        time.time()
                        - start
                    )

                    content = extract_content(
                        response
                    )

                    usage = extract_usage(
                        response
                    )

                    print(
                        f"[LLM] Groq "
                        f"{model_name} "
                        f"successful | "
                        f"Tokens: "
                        f"{usage['input_tokens']}"
                        f"+"
                        f"{usage['output_tokens']}"
                    )

                    return {
                        "content": content,

                        "provider":
                            f"groq/{model_name}",

                        "usage": usage,

                        "latency": latency
                    }

                except Exception as e:

                    print(
                        f"[LLM] Groq "
                        f"{model_name} "
                        f"failed: {e}"
                    )

        # ====================================================
        # COHERE
        # ====================================================

        for api_key in self.cohere_keys:

            try:

                model = ChatCohere(
                    model="command-r-plus",
                    cohere_api_key=api_key,
                    temperature=0
                )

                start = time.time()

                response = model.invoke(
                    prompt
                )

                latency = (
                    time.time()
                    - start
                )

                content = extract_content(
                    response
                )

                usage = extract_usage(
                    response
                )

                print(
                    "[LLM] Cohere successful | "
                    f"Tokens: "
                    f"{usage['input_tokens']}"
                    f"+"
                    f"{usage['output_tokens']}"
                )

                return {
                    "content": content,

                    "provider":
                        "cohere/command-r-plus",

                    "usage": usage,

                    "latency": latency
                }

            except Exception as e:

                print(
                    f"[LLM] Cohere failed: {e}"
                )

        # ====================================================
        # ALL PROVIDERS FAILED
        # ====================================================

        raise RuntimeError(
            "All configured LLM providers failed."
        )

    # ========================================================
    # GENERATOR
    # ========================================================

    def invoke_generator(
        self,
        prompt
    ):

        return self._try_providers(
            prompt,
            NODE_2_GEMINI,
            NODE_2_GROQ
        )

    # ========================================================
    # JUDGE
    # ========================================================

    def invoke_judge(
        self,
        prompt
    ):

        return self._try_providers(
            prompt,
            NODE_3_GEMINI,
            NODE_3_GROQ
        )


# ============================================================
# GLOBAL CLIENT
# ============================================================

llm = LLMClient()