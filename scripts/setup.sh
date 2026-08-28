#!/usr/bin/env bash
# ControlPlane.ai Setup Script
# Run this from the root of the repository: ./scripts/setup.sh

set -e

echo "=== ControlPlane.ai Environment Setup ==="

# 1. Install pip dependencies
echo "=> Installing python dependencies from requirements.txt..."
pip install -r requirements.txt

# 2. Download the Spacy sentence segmentation model
echo "=> Downloading Spacy en_core_web_sm model..."
python -m spacy download en_core_web_sm

# 3. Cache the DeBERTa NLI model locally
echo "=> Caching SelfCheckGPT NLI model (this might take a minute)..."
python -c "
from transformers import AutoTokenizer, AutoModelForSequenceClassification;
print('Downloading tokenizer...');
AutoTokenizer.from_pretrained('potsawee/deberta-v3-large-mnli');
print('Downloading model...');
AutoModelForSequenceClassification.from_pretrained('potsawee/deberta-v3-large-mnli');
print('Done!')
"

echo "=== Setup Complete! ==="
