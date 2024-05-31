import streamlit as st
import os
from pinecone import Pinecone, ServerlessSpec
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import HuggingFaceHub
from langchain.memory import ConversationBufferMemory
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.DEBUG)

def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def get_text_chunks(text):
    text_splitter = CharacterTextSplitter(separator="\n", chunk_size=5, chunk_overlap=3, length_function=len)
    chunks = text_splitter.split_text(text)
    return chunks

def get_vectorstore(text_chunks):
    pc = Pinecone(
        api_key=os.environ.get("d3dd74f5-80b3-45ea-84c1-6bffde9b76c3")
    )

    index_name = "chatbot-1"
    
    # Create index if it doesn't exist
    if index_name not in [index.name for index in pc.list_indexes().names]:
        pc.create_index(
            name=index_name,
            dimension=1024,  # Adjust based on your embedding model dimension
            metric='cosine',
            spec=ServerlessSpec(
                cloud='gcp',
                region='Iowa (us-central1)'
            )
        )

    index = pc.index(index_name)
    
    embeddings = SentenceTransformer("hkunlp/instructor-xl")
    
    for i, chunk in enumerate(text_chunks):
        embedding = embeddings.encode(chunk)
        index.upsert([(f"id_{i}", embedding.tolist())])
    
    return index

def get_conversation_chain(vectorstore):
    llm = HuggingFaceHub(repo_id="google/flan-t5-xxl", model_kwargs={"temperature": 0.5, "max_length": 512}, task='text-generation')
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    
    retriever = vectorstore.as_retriever()  # Adjust this line to the correct method if needed
    
    conversation_chain = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever, memory=memory)
    return conversation_chain

def handle_userinput(user_question):
    response = st.session_state.conversation({'question': user_question})
    st.session_state.chat_history = response['chat_history']
    
    for i, message in enumerate(st.session_state.chat_history):
        if i % 2 == 0:
            st.write(user_template.replace("{{MSG}}", message.content), unsafe_allow_html=True)
        else:
            st.write(bot_template.replace("{{MSG}}", message.content), unsafe_allow_html=True)

def main():
    load_dotenv()
    st.set_page_config(page_title='First APP', page_icon='books')
    st.write(css, unsafe_allow_html=True)
    
    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None
    
    st.header("Ask Me Anything")
    user_question = st.text_input("Ask your question on your pdf")
    if user_question:
        handle_userinput(user_question)
    
    with st.sidebar:
        st.subheader('Your Documents')
        pdf_docs = st.file_uploader('Upload your docs here', accept_multiple_files=True)
        if st.button('Process'):
            with st.spinner('Processing'):
                raw_text = get_pdf_text(pdf_docs)
                text_chunks = get_text_chunks(raw_text)
                vectorstore = get_vectorstore(text_chunks)
                st.session_state.conversation = get_conversation_chain(vectorstore)

main()
