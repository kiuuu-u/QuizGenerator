import streamlit as st
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import spacy
import os
import random
import json

st.title("Free Quiz Generator")

# Initialize session state
if 'question_index' not in st.session_state:
    st.session_state.question_index = 0
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'decks' not in st.session_state:
    st.session_state.decks = {}
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'current_deck' not in st.session_state:
    st.session_state.current_deck = ""
if 'mode' not in st.session_state:
    st.session_state.mode = "Answer Mode"
if 'show_answer' not in st.session_state:
    st.session_state.show_answer = False

# Load existing decks
def load_decks():
    if os.path.exists("decks.json"):
        with open("decks.json", "r") as f:
            st.session_state.decks = json.load(f)

# Save decks
def save_decks():
    with open("decks.json", "w") as f:
        json.dump(st.session_state.decks, f)

# Load SpaCy model from local directory
try:
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    st.error(f"Failed to load SpaCy model 'en_core_web_sm'. Error: {str(e)}")
    st.stop()
# Upload multiple PDFs
uploaded_files = st.file_uploader("Upload your PDFs", type="pdf", accept_multiple_files=True)
if uploaded_files and not st.session_state.questions:
    load_decks()
    all_text = ""
    for uploaded_file in uploaded_files:
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.read())
        
        # Extract text using PyPDF2
        with open("temp.pdf", "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            for page in pdf.pages:
                text = page.extract_text()
                all_text += text if text else ""

        # Attempt image processing only if needed (optional and skippable)
        if "diagram" in all_text.lower() or "pathway" in all_text.lower():
            try:
                images = convert_from_path("temp.pdf", poppler_path="/opt/homebrew/bin", first_page=1, last_page=1)
                for i, image in enumerate(images):
                    img_text = pytesseract.image_to_string(Image.open(f"page_{i}.png"))
                    all_text += img_text if img_text else ""
            except Exception as e:
                st.warning("Image processing skipped due to missing Poppler/Tesseract. Proceeding with text-based questions only.")

    # Create or select custom deck
    new_deck_name = st.text_input("Create a new deck name (or press Enter to use existing):")
    if new_deck_name and new_deck_name not in st.session_state.decks:
        st.session_state.decks[new_deck_name] = []
        st.success(f"Created new deck: {new_deck_name}")
    deck_options = list(st.session_state.decks.keys()) + ["Create New Deck"]
    st.session_state.current_deck = st.selectbox("Select Deck", deck_options, index=0 if st.session_state.current_deck in deck_options else 0)
    if st.session_state.current_deck == "Create New Deck":
        st.session_state.current_deck = new_deck_name if new_deck_name else "Default Deck"
    if st.session_state.current_deck not in st.session_state.decks:
        st.session_state.decks[st.session_state.current_deck] = []

    # Generate questions
    doc = nlp(all_text)
    keywords = [token.text for token in doc if token.is_alpha and not token.is_stop]

    # Define keyword-to-options mapping for LIFS 2210 topics
    keyword_options = {
        "enzyme": {
            "correct": "lowers activation energy",
            "distractors": ["stores genetic information", "transports oxygen", "synthesizes carbohydrates"]
        },
        "dna": {
            "correct": "stores genetic information",
            "distractors": ["catalyzes reactions", "produces ATP", "forms cell membrane"]
        },
        "metabolism": {
            "correct": "converts nutrients into energy",
            "distractors": ["transcribes RNA", "builds cell walls", "transports ions"]
        },
        "protein": {
            "correct": "functions as an enzyme or structural component",
            "distractors": ["stores energy as fat", "carries genetic code", "forms microtubules"]
        },
        "gene": {
            "correct": "encodes a functional product like protein",
            "distractors": ["produces energy", "forms cell membrane", "transports glucose"]
        },
        "glycolysis": {
            "correct": "converts glucose into pyruvate",
            "distractors": ["synthesizes DNA", "produces ribosomes", "transports lipids"]
        },
        "mitosis": {
            "correct": "divides the nucleus to form two daughter cells",
            "distractors": ["synthesizes proteins", "produces ATP", "transcribes RNA"]
        }
    }

    # Generate MCQs with improved options
    for i in range(15):
        if len(keywords) > 4:
            keyword = random.choice(keywords).lower()
            if keyword in keyword_options:
                correct = keyword_options[keyword]["correct"]
                distractors = keyword_options[keyword]["distractors"]
                options = [f"A. {correct}"]
                random.shuffle(distractors)
                options.extend([f"{chr(66+j)}. {distractors[j]}" for j in range(3)])
                random.shuffle(options)
                correct_answer = "A"
                st.session_state.decks[st.session_state.current_deck].append({
                    "question": f"What is the primary function of {keyword}?",
                    "options": options,
                    "answer": "A",
                    "explanation": f"{keyword} {correct} in cellular processes."
                })
            else:
                options = [f"A. {keyword} catalyzes reactions"]
                while len(options) < 4:
                    opt = random.choice(["stores energy", "transports oxygen", "synthesizes proteins", "regulates genes"])
                    if opt not in options:
                        options.append(f"D. {keyword} {opt}")
                random.shuffle(options)
                st.session_state.decks[st.session_state.current_deck].append({
                    "question": f"What is the role of {keyword}?",
                    "options": options,
                    "answer": "A",
                    "explanation": f"{keyword} is a key component."
                })

    # Generate T/F questions with better relevance
    for i in range(5):
        if keywords:
            keyword = random.choice(keywords).lower()
            if keyword in keyword_options:
                correct_function = keyword_options[keyword]["correct"]
                statement = f"{keyword} {correct_function}."
                answer = "A"
                st.session_state.decks[st.session_state.current_deck].append({
                    "question": statement,
                    "options": ["A. True", "B. False"],
                    "answer": answer,
                    "explanation": f"This statement is true based on the role of {keyword}."
                })
            else:
                statement = f"{keyword} is in the nucleus."
                answer = "A" if keyword == "dna" else "B"
                st.session_state.decks[st.session_state.current_deck].append({
                    "question": statement,
                    "options": ["A. True", "B. False"],
                    "answer": answer,
                    "explanation": f"{keyword} is in the {'nucleus' if keyword == 'dna' else 'cytoplasm'}."
                })
    save_decks()
    st.session_state.questions = st.session_state.decks[st.session_state.current_deck]

# Select mode
st.session_state.mode = st.selectbox("Select Mode", ["Answer Mode", "Flashcard Mode"], index=["Answer Mode", "Flashcard Mode"].index(st.session_state.mode))

# Answer Mode
if st.session_state.questions and st.session_state.mode == "Answer Mode":
    current_q = st.session_state.questions[st.session_state.question_index]
    st.write(f"**Q{st.session_state.question_index + 1}.** {current_q['question']}")
    for opt in current_q['options']:
        st.write(opt)

    user_answer = st.radio("Your Answer:", [opt.split(". ")[1] for opt in current_q['options']], key=f"answer_{st.session_state.question_index}")
    if st.button("Submit"):
        correct_answer = current_q['answer'].split(". ")[1]
        if user_answer == correct_answer:
            st.success("Correct!")
            st.session_state.score += 1
        else:
            st.error(f"Wrong! Correct answer is {correct_answer}")
        st.write(f"**Explanation:** {current_q['explanation']}")
        if st.session_state.question_index < len(st.session_state.questions) - 1:
            st.session_state.question_index += 1
            st.experimental_rerun()
        else:
            st.write(f"All questions completed! Your score: {st.session_state.score}/{len(st.session_state.questions)}")
            if st.button("Restart"):
                st.session_state.question_index = 0
                st.session_state.score = 0
                st.experimental_rerun()

# Flashcard Mode
if st.session_state.questions and st.session_state.mode == "Flashcard Mode":
    current_q = st.session_state.questions[st.session_state.question_index]
    st.write(f"**Card {st.session_state.question_index + 1}/{len(st.session_state.questions)}**")
    
    # Show question (front of the card)
    st.write(f"**Question:** {current_q['question']}")
    
    # Flip to show answer
    if st.button("Flip Card"):
        st.session_state.show_answer = not st.session_state.show_answer
    
    if st.session_state.show_answer:
        st.write(f"**Answer:** {current_q['answer'].split('. ')[1]}")
        st.write(f"**Explanation:** {current_q['explanation']}")
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Previous"):
            if st.session_state.question_index > 0:
                st.session_state.question_index -= 1
                st.session_state.show_answer = False
                st.experimental_rerun()
    with col2:
        if st.button("Next"):
            if st.session_state.question_index < len(st.session_state.questions) - 1:
                st.session_state.question_index += 1
                st.session_state.show_answer = False
                st.experimental_rerun()
            else:
                st.write("You've reached the end of the deck!")
                if st.button("Restart Deck"):
                    st.session_state.question_index = 0
                    st.session_state.show_answer = False
                    st.experimental_rerun()

# Liberal Arts Article
if uploaded_files:
    st.subheader("Liberal Arts Article (100-150 words)")
    article = f"Cellular metabolism drives life, with enzymes accelerating reactions like nitrogenous compound breakdown. DNA, housed in the nucleus, directs protein synthesis via gene expression. These processes, central to LIFS 2210, adapt to environmental changes, influencing cell function."
    st.write(article)
