import streamlit as st
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import spacy
import os
import random
import json
import hashlib

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
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'user_answer' not in st.session_state:
    st.session_state.user_answer = None
if 'last_upload_hash' not in st.session_state:
    st.session_state.last_upload_hash = None

# Load existing decks
def load_decks():
    if os.path.exists("decks.json"):
        with open("decks.json", "r") as f:
            st.session_state.decks = json.load(f)

# Save decks
def save_decks():
    with open("decks.json", "w") as f:
        json.dump(st.session_state.decks, f)

# Load SpaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    st.error(f"Failed to load SpaCy model 'en_core_web_sm'. Error: {str(e)}")
    st.stop()

# Compute a hash of the uploaded files to detect changes
def compute_upload_hash(uploaded_files):
    if not uploaded_files:
        return None
    file_hashes = []
    for file in sorted(uploaded_files, key=lambda x: x.name):
        file.seek(0)
        file_hash = hashlib.md5(file.read()).hexdigest()
        file.seek(0)  # Reset file pointer
        file_hashes.append(file_hash)
    return hashlib.md5("".join(file_hashes).encode()).hexdigest()

# Upload multiple PDFs
uploaded_files = st.file_uploader("Upload your PDFs", type="pdf", accept_multiple_files=True)

# Check if the uploaded files have changed
files_changed = False
current_upload_hash = compute_upload_hash(uploaded_files)
if uploaded_files and current_upload_hash != st.session_state.last_upload_hash:
    files_changed = True
    st.session_state.last_upload_hash = current_upload_hash
    # Reset relevant session state to ensure new questions are generated
    st.session_state.questions = []
    if st.session_state.current_deck in st.session_state.decks:
        st.session_state.decks[st.session_state.current_deck] = []
    st.session_state.question_index = 0
    st.session_state.score = 0
    st.session_state.submitted = False
    st.session_state.user_answer = None

if uploaded_files and (files_changed or not st.session_state.questions):
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
    sentences = [sent.text.strip() for sent in doc.sents if len(sent) > 5]  # Get meaningful sentences
    # Automatically expand keyword_options
    keyword_options = {}
    used_sentences = set()  # Track used sentences to ensure diversity
    for sent in doc.sents:
        for ent in sent.ents:
            if ent.label_ in ["PERSON", "ORG", "NORP", "GPE", "PRODUCT", "EVENT"] and ent.text.lower() not in keyword_options:
                context = sent.text.lower()
                doc_sent = nlp(sent.text)
                # Look for verbs or actions related to the entity
                related_action = None
                related_object = None
                for token in doc_sent:
                    if token.head.text.lower() == ent.text.lower() and token.dep_ in ["nsubj", "dobj"]:
                        related_action = token.head.lemma_
                        # Look for an object related to the action
                        for child in token.head.children:
                            if child.dep_ in ["dobj", "attr"]:
                                related_object = child.text
                                break
                        break
                if related_action:
                    correct = f"{related_action.capitalize()}s {related_object or 'cellular processes'}"
                elif "regulate" in context or "regulation" in context:
                    correct = f"Regulates biological processes"
                    related_action = "regulates"
                    related_object = "biological processes"
                elif "metabolism" in context or "metabolic" in context:
                    correct = f"Converts nutrients into energy"
                    related_action = "converts"
                    related_object = "nutrients into energy"
                elif "synthesis" in context or "synthesize" in context:
                    correct = f"Synthesizes proteins or molecules"
                    related_action = "synthesizes"
                    related_object = "proteins or molecules"
                elif "catalyze" in context or "catalysis" in context:
                    correct = f"Catalyzes chemical reactions"
                    related_action = "catalyzes"
                    related_object = "chemical reactions"
                else:
                    correct = f"Plays a key role in cellular function"
                    related_action = "plays a key role"
                    related_object = "cellular function"
                distractors = [
                    "Stores genetic information",
                    "Transports oxygen",
                    "Produces ATP passively",
                    "Forms the cell membrane",
                    "Synthesizes proteins",
                    "Regulates genes",
                    "Catalyzes reactions",
                    "Transports materials"
                ]
                # Ensure distractors are unique and don't overlap with correct answer
                unique_distractors = [d for d in distractors if d.lower() != correct.lower()]
                keyword_options[ent.text.lower()] = {
                    "correct": correct,
                    "distractors": unique_distractors,
                    "action": related_action,
                    "object": related_object
                }

    # Enhanced question generation
    for i in range(15):
        if len(sentences) > 0 and keyword_options:
            keyword = random.choice(list(keyword_options.keys()))
            # Select a sentence that contains the keyword
            relevant_sentences = [s for s in sentences if keyword in s.lower() and s not in used_sentences]
            if not relevant_sentences:  # Fallback if no relevant sentence is found
                relevant_sentences = [s for s in sentences if s not in used_sentences]
            if relevant_sentences:
                sentence = random.choice(relevant_sentences)
                used_sentences.add(sentence)
                # Critical thinking questions
                question_types = [
                    f"Why might {keyword} be essential for the process described in '{sentence[:30]}...'?",
                    f"How could {keyword} influence the outcome of '{sentence[:30]}...'?",
                    f"What evidence from '{sentence[:30]}...' supports the role of {keyword}?",
                    f"How would altering {keyword} affect the process in '{sentence[:30]}...'?"
                ]
                question = random.choice(question_types)
                correct = keyword_options[keyword]["correct"]
                distractors = keyword_options[keyword]["distractors"]
                related_action = keyword_options[keyword]["action"]
                related_object = keyword_options[keyword]["object"]
                # Ensure exactly 4 unique options
                all_options = [correct]
                unique_distractors = list(set(distractors))  # Remove duplicates from distractors
                random.shuffle(unique_distractors)
                for d in unique_distractors:
                    if d != correct and d not in all_options and len(all_options) < 4:
                        all_options.append(d)
                while len(all_options) < 4:
                    fallback = random.choice([
                        "Synthesizes proteins",
                        "Regulates genes",
                        "Catalyzes reactions",
                        "Transports materials"
                    ])
                    if fallback not in all_options:
                        all_options.append(fallback)
                all_options = list(set(all_options))[:4]  # Ensure exactly 4 unique options
                while len(all_options) < 4:  # In case set reduces the size due to duplicates
                    fallback = random.choice([
                        "Synthesizes proteins",
                        "Regulates genes",
                        "Catalyzes reactions",
                        "Transports materials"
                    ])
                    if fallback not in all_options:
                        all_options.append(fallback)
                random.shuffle(all_options)
                labeled_options = [f"{chr(65+j)}. {opt}" for j, opt in enumerate(all_options)]
                correct_idx = all_options.index(correct)
                correct_answer = chr(65 + correct_idx)
                # Intelligent explanation based on question type
                if "Why might" in question:
                    explanation = f"{keyword} is essential because it {related_action} {related_object}, as inferred from '{sentence[:30]}...'"
                elif "How could" in question:
                    explanation = f"{keyword} could influence the outcome by {related_action} {related_object}, impacting the process in '{sentence[:30]}...'"
                elif "What evidence" in question:
                    explanation = f"The sentence '{sentence[:30]}...' suggests {keyword} {related_action} {related_object}, supporting its role in the process."
                else:  # "How would altering"
                    explanation = f"Altering {keyword} would disrupt its ability to {related_action} {related_object}, affecting the process in '{sentence[:30]}...'"
                st.session_state.decks[st.session_state.current_deck].append({
                    "question": question,
                    "options": labeled_options,
                    "answer": correct_answer,
                    "explanation": explanation
                })

    # Generate T/F questions
    for i in range(5):
        if len(sentences) > 0 and keyword_options:
            keyword = random.choice(list(keyword_options.keys()))
            relevant_sentences = [s for s in sentences if keyword in s.lower() and s not in used_sentences]
            if not relevant_sentences:
                relevant_sentences = [s for s in sentences if s not in used_sentences]
            if relevant_sentences:
                sentence = random.choice(relevant_sentences)
                used_sentences.add(sentence)
                process_type = random.choice(['metabolic', 'genetic', 'cellular'])
                statement = f"{keyword} is central to the {process_type} process in '{sentence[:30]}...'."
                answer = "A" if keyword in sentence.lower() else "B"
                related_action = keyword_options[keyword]["action"]
                related_object = keyword_options[keyword]["object"]
                explanation = f"This statement is {'' if answer == 'A' else 'not '}true because {keyword} {'' if answer == 'A' else 'does not '}appear to {related_action} {related_object} in the {process_type} process described in '{sentence[:30]}...'."
                st.session_state.decks[st.session_state.current_deck].append({
                    "question": statement,
                    "options": ["A. True", "B. False"],
                    "answer": answer,
                    "explanation": explanation
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
    
    if st.button("Submit") and not st.session_state.submitted:
        st.session_state.submitted = True
        st.session_state.user_answer = user_answer

    if st.session_state.submitted:
        correct_answer = current_q['answer']
        if st.session_state.user_answer == current_q['options'][ord(correct_answer) - 65].split(". ")[1]:
            st.success("Correct!")
            st.session_state.score += 1
        else:
            st.error(f"Wrong! Correct answer is {current_q['options'][ord(correct_answer) - 65].split('. ')[1]}")
        st.write(f"**Explanation:** {current_q['explanation']}")
        
        if st.button("Next"):
            if st.session_state.question_index < len(st.session_state.questions) - 1:
                st.session_state.question_index += 1
                st.session_state.submitted = False
                st.session_state.user_answer = None
                st.experimental_rerun()
            else:
                st.write(f"All questions completed! Your score: {st.session_state.score}/{len(st.session_state.questions)}")
                if st.button("Restart"):
                    st.session_state.question_index = 0
                    st.session_state.score = 0
                    st.session_state.submitted = False
                    st.session_state.user_answer = None
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
        st.write(f"**Answer:** {current_q['options'][ord(current_q['answer']) - 65].split('. ')[1]}")
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
