import transformers
import spacy

def main():
    print("Downloading piiranha-v1-detect-personal-information (Transformer NER)...")
    transformers.pipeline(
        "ner", 
        model="iiiorg/piiranha-v1-detect-personal-information",
        aggregation_strategy="simple"
    )
    
    print("Loading en_core_web_lg (spaCy NLP Engine)...")
    try:
        spacy.load("en_core_web_lg")
    except OSError:
        print("Error: en_core_web_lg not found. Did you run 'python -m spacy download en_core_web_lg'?")
        return

    print("✅ Models cached successfully for offline demo!")

if __name__ == "__main__":
    main()
