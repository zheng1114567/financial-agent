from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from rag.utils.utils import api_key, base_url

model_dir = r"C:\Users\Administrator\Desktop\financial agent\rag\AI-ModelScope\m3e-base"
embeddings = HuggingFaceEmbeddings(model_name=model_dir)

persist_directory = "data_base/vector_db/chroma"
vectordb = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings
)
llm = ChatDeepSeek(
    model = "deepseek-chat",
    temperature = 0.5,
    max_tokens = 512,
    timeout = 30,
    api_key = api_key,
    base_url = base_url
)

history_system_prompt = (
    '''
    1.仅仅根据用户的提出的问题和你本轮的回复进行关键词提取
    2.将提取出来的关键词组合生成你对本轮对话的记忆
    3.将新记忆与历史记忆进行比对，生成你对本次所有对话的记忆
    4.内容适当短(50字以内纯文字无任何标点换行符等)并且保证不会错过任何关键点
    5.绝对不生成不存在的对话
    '''
)

history_prompt_template = ChatPromptTemplate.from_messages([
    ("system", history_system_prompt),
    ("human","历史记忆:{chat_history}\n本轮对话:{input}")
])

history_chain = history_prompt_template|llm|StrOutputParser()

contextualization_system_prompt = (
    '''
    1.根据用户最新的询问记录以及聊天记录
    2.生成一个独立并且可以检索的问题
    3.不要回答问题，只改写
    '''
)

contextualization_prompt_template = ChatPromptTemplate.from_messages([
    ("system", contextualization_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human","{input}")
])
history_aware_retrieval = create_history_aware_retriever(
    llm,
    vectordb.as_retriever(search_kwargs={"k":3}),
    contextualization_prompt_template
)

qa_system_prompt = (
    '''
    你是专业金融顾问:
    {context}
    规则:
    1.仅使用上下文信息和检索到的信息
    2.回答口吻简洁专业，符合金融行业标准
    3.若用户询问非金融的其他专业相关问题并且不是日常问好则回答“暂无相关信息可解答此问题”
    4.如果用户想停止对话请告诉他让他按Q
    '''
)
qa_prompt_template = ChatPromptTemplate.from_messages([
    ("system", qa_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human","{input}")
])

question_chain = create_stuff_documents_chain(llm, qa_prompt_template)
rag_chain = create_retrieval_chain(retriever=history_aware_retrieval,
                                   combine_docs_chain=question_chain)

chat_history_str = ""
chat_history_messages = []


def ask_question(question: str, chat_history_messages: list, chat_history_str: str = ""):
    """
    Args:
        question: 用户当前问题
        chat_history_messages: 完整的 LangChain 消息列表（用于 retriever）
        chat_history_str: 压缩后的记忆字符串（用于 history_chain）
    Returns:
        (answer, new_chat_history_messages, new_chat_history_str)
    """
    if question.strip().lower() == "q":
        return "感谢咨询，祝您生活愉快!", [], ""

    try:
        response = rag_chain.invoke({
            "input": question,
            "chat_history": chat_history_messages
        })
        answer = response['answer']

        new_messages = chat_history_messages + [
            HumanMessage(content=question),
            AIMessage(content=answer)
        ]

        current_chat = f"用户：{question}\n顾问：{answer}"
        new_memory_str = history_chain.invoke({
            "input": current_chat,
            "chat_history": chat_history_str
        })

        return answer, new_messages, new_memory_str

    except Exception as e:
        error_msg = f"抱歉，处理您的问题时出错：{str(e)}，请重试！"
        return error_msg, chat_history_messages, chat_history_str

if __name__ == "__main__":
    chat_history_msgs = []
    chat_history_str = ""
    print("您好，我是您的金融顾问")
    while True:
        question = input("你: ")
        if question.lower() == "q":
            print("顾问: 感谢咨询，祝您生活愉快!")
            break
        answer, chat_history_msgs, chat_history_str = ask_question(
            question, chat_history_msgs, chat_history_str
        )
        print(f"顾问: {answer}\n")