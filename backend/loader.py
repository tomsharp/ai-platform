import logging
from typing import Callable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

MAX_NEW_TOKENS = 150
TEMPERATURE = 0.7
TOP_P = 0.9

def load_model_predictor(model_id: str, device_pref: str) -> Callable[[str], str]:
    logger.info(f"Loading model {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    device = device_pref if device_pref in ["cpu", "cuda"] else ("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForCausalLM.from_pretrained(model_id).to(device)
    logger.info(f"Model {model_id} loaded on {device}")

    def predict(prompt: str) -> str:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
        return tokenizer.decode(outputs[0], skip_special_tokens=True)

    return predict
