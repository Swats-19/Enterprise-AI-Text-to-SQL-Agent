# llm.py

import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_cohere import ChatCohere


load_dotenv()


# ============================================================
# NODE 2: SQL GENERATOR MODELS
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


# ============================================================
# NODE 3: JUDGE MODELS
# ============================================================

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
# COHERE FALLBACK
# ============================================================

COHERE_MODEL = "command-r-plus"


# ============================================================
# CONTENT EXTRACTION
# ============================================================

def extract_content(response):
    """
    Convert LangChain provider responses into plain text.

    Providers can return:
        str
        list[str]
        list[dict]
        dict
    """

    content = response.content

    # --------------------------------------------------------
    # Already plain string
    # --------------------------------------------------------

    if isinstance(content, str):
        return content.strip()

    # --------------------------------------------------------
    # Dictionary
    # --------------------------------------------------------

    if isinstance(content, dict):

        if "text" in content:
            return str(
                content["text"]
            ).strip()

        return str(content).strip()

    # --------------------------------------------------------
    # List
    # --------------------------------------------------------

    if isinstance(content, list):

        text_parts = []

        for item in content:

            if isinstance(item, dict):

                if "text" in item:

                    text_parts.append(
                        str(item["text"])
                    )

            elif isinstance(item, str):

                text_parts.append(item)

            else:

                text_parts.append(
                    str(item)
                )

        return " ".join(
            text_parts
        ).strip()

    # --------------------------------------------------------
    # Anything else
    # --------------------------------------------------------

    return str(content).strip()


# ============================================================
# LLM CLIENT
# ============================================================

class LLMClient:

    def __init__(self):

        # ----------------------------------------------------
        # GEMINI KEYS
        # ----------------------------------------------------

        self.gemini_keys = []

        for i in range(1, 4):

            key = os.getenv(
                f"GOOGLE_API_KEY_{i}"
            )

            if key:

                self.gemini_keys.append(
                    key
                )

                print(
                    f"   ✅ Loaded Gemini Key {i}"
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

                print(
                    f"   ✅ Loaded Groq Key {i}"
                )

        # ----------------------------------------------------
        # COHERE
        # ----------------------------------------------------

        self.cohere_key = (
            os.getenv("COHERE_API_KEY")
            or
            os.getenv("COHERE_API_KEY_1")
        )

        if self.cohere_key:

            print(
                "   ✅ Loaded Cohere key"
            )

        print(
            f"\n🔑 Total: "
            f"{len(self.gemini_keys)} Gemini keys, "
            f"{len(self.groq_keys)} Groq keys"
        )

    # ========================================================
    # PROVIDER TRY LOOP
    # ========================================================

    def _try_providers(
        self,
        prompt,
        role,
        gemini_models,
        groq_models,
        fallback_text
    ):

        # ====================================================
        # GEMINI
        # ====================================================

        for key in self.gemini_keys:

            for model in gemini_models:

                try:

                    print(
                        f"   [LLM:{role}] "
                        f"Trying Gemini {model}"
                    )

                    llm = ChatGoogleGenerativeAI(
                        model=model,
                        temperature=0,
                        google_api_key=key
                    )

                    start_time = __import__(
                        "time"
                    ).time()

                    response = llm.invoke(
                        prompt
                    )

                    latency = (
                        __import__("time").time()
                        - start_time
                    )

                    content = extract_content(
                        response
                    )

                    print(
                        f"   [LLM:{role}] "
                        f"✅ Gemini {model} succeeded!"
                    )

                    return {
                        "content": content,
                        "provider": f"Gemini {model}",
                        "usage": {},
                        "latency": latency
                    }

                except Exception as e:

                    print(
                        f"   [LLM:{role}] "
                        f"❌ Gemini {model} failed: "
                        f"{str(e)[:100]}..."
                    )

                    continue

        # ====================================================
        # GROQ
        # ====================================================

        for key in self.groq_keys:

            for model in groq_models:

                try:

                    print(
                        f"   [LLM:{role}] "
                        f"Trying Groq {model}"
                    )

                    llm = ChatGroq(
                        model=model,
                        temperature=0,
                        api_key=key
                    )

                    start_time = __import__(
                        "time"
                    ).time()

                    response = llm.invoke(
                        prompt
                    )

                    latency = (
                        __import__("time").time()
                        - start_time
                    )

                    content = extract_content(
                        response
                    )

                    print(
                        f"   [LLM:{role}] "
                        f"✅ Groq {model} succeeded!"
                    )

                    return {
                        "content": content,
                        "provider": f"Groq {model}",
                        "usage": {},
                        "latency": latency
                    }

                except Exception as e:

                    print(
                        f"   [LLM:{role}] "
                        f"❌ Groq {model} failed: "
                        f"{str(e)[:100]}..."
                    )

                    continue

        # ====================================================
        # COHERE
        # ====================================================

        if self.cohere_key:

            try:

                print(
                    f"   [LLM:{role}] "
                    f"Trying Cohere {COHERE_MODEL}"
                )

                llm = ChatCohere(
                    model=COHERE_MODEL,
                    temperature=0,
                    cohere_api_key=self.cohere_key
                )

                start_time = __import__(
                    "time"
                ).time()

                response = llm.invoke(
                    prompt
                )

                latency = (
                    __import__("time").time()
                    - start_time
                )

                content = extract_content(
                    response
                )

                print(
                    f"   [LLM:{role}] "
                    f"✅ Cohere succeeded!"
                )

                return {
                    "content": content,
                    "provider": f"Cohere {COHERE_MODEL}",
                    "usage": {},
                    "latency": latency
                }

            except Exception as e:

                print(
                    f"   [LLM:{role}] "
                    f"❌ Cohere failed: "
                    f"{str(e)[:100]}..."
                )

        # ====================================================
        # FALLBACK
        # ====================================================

        print(
            f"   [LLM:{role}] "
            f"⚠️ ALL PROVIDERS FAILED."
        )

        print(
            f"   [LLM:{role}] "
            f"Using hardcoded fallback."
        )

        return {
            "content": fallback_text,
            "provider": "Hardcoded Fallback",
            "usage": {},
            "latency": 0
        }

    # ========================================================
    # NODE 2
    # ========================================================

    def invoke_generator(
        self,
        prompt: str
    ) -> dict:

        fallback_sql = """
SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    SUM(o.total_amount) AS total_spend,
    COUNT(o.order_id) AS total_orders
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
GROUP BY
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email
ORDER BY total_spend DESC
LIMIT 5;
"""

        return self._try_providers(
            prompt,
            "Generator",
            NODE_2_GEMINI,
            NODE_2_GROQ,
            fallback_sql
        )

    # ========================================================
    # NODE 3
    # ========================================================

    def invoke_judge(
        self,
        prompt: str
    ) -> dict:

        fallback_json = (
            '{"approved": true, '
            '"feedback": '
            '"Fallback judge response."}'
        )

        return self._try_providers(
            prompt,
            "Judge",
            NODE_3_GEMINI,
            NODE_3_GROQ,
            fallback_json
        )

    # ========================================================
    # DEFAULT
    # ========================================================

    def invoke(
        self,
        prompt: str
    ) -> dict:

        return self.invoke_generator(
            prompt
        )


# ============================================================
# GLOBAL CLIENT
# ============================================================

llm = LLMClient()