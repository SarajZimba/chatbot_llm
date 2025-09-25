import streamlit as st
import tempfile
import os
from langchain.document_loaders import TextLoader, Docx2txtLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.llms import HuggingFacePipeline
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import warnings
warnings.filterwarnings("ignore")


class DocumentQA:
    def __init__(self):
        self.embeddings = None
        self.vectorstore = None
        self.qa_chain = None
        self.llm = None

    def setup_embeddings(self):
        """Setup free sentence embeddings"""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

    def setup_llm(self):
        """Setup LLM (distilgpt2)"""
        try:
            model_name = "distilgpt2"
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name)

            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=200,
                temperature=0.1
            )

            self.llm = HuggingFacePipeline(pipeline=pipe)
            return True
        except Exception as e:
            st.error(f"Failed to load LLM: {str(e)}")
            return False

    def load_document(self, file_path):
        """Load document based on file type"""
        if file_path.endswith('.txt'):
            loader = TextLoader(file_path)
        elif file_path.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
        elif file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        else:
            raise ValueError("Unsupported file format")

        return loader.load()

    def process_document(self, documents):
        """Split document into chunks and create vector store"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            length_function=len
        )

        chunks = text_splitter.split_documents(documents)

        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory="./chroma_db"
        )

        return len(chunks)

    def setup_qa_chain(self):
        """Set up the question answering chain"""
        if not self.llm:
            success = self.setup_llm()
            if not success:
                return False

        retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": 2}
        )

        prompt_template = """Answer the question based only on the following context.
If you cannot answer from the context, say "I cannot find this information in the document."

Context: {context}

Question: {question}

Answer:"""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": PROMPT},
            return_source_documents=True
        )

        return True

    def ask_question(self, question):
        """Ask a question about the document"""
        if not self.qa_chain:
            return "Please process a document first!", []

        try:
            result = self.qa_chain({"query": question})
            return result["result"], result["source_documents"]
        except Exception as e:
            return f"Error generating answer: {str(e)}", []


# -------------------- Streamlit UI --------------------
def main():
    st.set_page_config(page_title="Document Q&A", page_icon="📄", layout="wide")
    st.title("📄 Document Question Answering")
    st.write("Upload a document and ask questions about its content!")

    # Initialize session state
    if 'qa_system' not in st.session_state:
        st.session_state.qa_system = DocumentQA()
        st.session_state.qa_system.setup_embeddings()
    if 'document_processed' not in st.session_state:
        st.session_state.document_processed = False

    # Sidebar for file upload
    with st.sidebar:
        st.header("Upload Document")

        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["txt", "pdf", "docx"]
        )

        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            try:
                with st.spinner("Processing document..."):
                    documents = st.session_state.qa_system.load_document(tmp_file_path)
                    num_chunks = st.session_state.qa_system.process_document(documents)

                    with st.spinner("Initializing LLM..."):
                        success = st.session_state.qa_system.setup_qa_chain()

                    if success:
                        st.session_state.document_processed = True
                        st.success(f"Document processed successfully! Created {num_chunks} chunks.")
                    else:
                        st.error("Failed to initialize the AI model.")

            except Exception as e:
                st.error(f"Error processing document: {str(e)}")
            finally:
                os.unlink(tmp_file_path)

    # Main content
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("Ask Questions")

        if st.session_state.document_processed:
            question = st.text_input("Enter your question:")
            if question:
                with st.spinner("Thinking..."):
                    answer, sources = st.session_state.qa_system.ask_question(question)
                    st.subheader("Answer:")
                    st.write(answer)

                    if sources:
                        st.subheader("Relevant Sources:")
                        for i, source in enumerate(sources[:2]):
                            with st.expander(f"Source {i+1}"):
                                st.write(source.page_content[:300] + "..." if len(source.page_content) > 300 else source.page_content)
        else:
            st.info("Please upload a document to get started.")

    with col2:
        st.header("System Info")
        st.markdown("""
        **LLM:** distilgpt2 (CPU-friendly)
        **Embeddings:** sentence-transformers/all-MiniLM-L6-v2
        **Vector Store:** ChromaDB
        """)


if __name__ == "__main__":
    main()

