from langchain_core.messages import SystemMessage, HumanMessage

from llm import llm
from prompt import SYSTEM_PROMPT


def generate_sql(question: str):

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=question)
    ]

    response = llm.invoke(messages)

    sql_query = response.content.strip()

    usage = response.usage_metadata

    return sql_query, usage