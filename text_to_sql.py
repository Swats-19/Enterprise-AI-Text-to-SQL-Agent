# text_to_sql.py

from langchain_core.messages import SystemMessage, HumanMessage

from llm import llm
from prompt import SYSTEM_PROMPT


def generate_sql(question: str):

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=question)
    ]

    # Use the new LLMClient interface
    response = llm.invoke_generator(messages)

    sql_query = response["content"].strip()

    usage = response.get("usage", {})

    return sql_query, usage