#!/usr/bin/env python3
"""
Test script for ChatCore - verifies two-step conversation works.

Demonstrates multi-vendor LLM support:
- OpenAI-compatible (DeepSeek)
- Claude (through proxy)
- Gemini (through proxy)

Usage:
    python test_chatbot_core.py
"""

import sys
import io
from pathlib import Path

# Fix Windows console Unicode issues
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from chatbot_core import ChatCore


def test_two_step_conversation(model_name: str):
    """Test two-step conversation with a specific model."""
    print(f"\n{'=' * 60}")
    print(f"Testing: {model_name}")
    print('=' * 60)
    
    # Initialize ChatCore
    core = ChatCore(system_prompt="You are a helpful assistant.")
    
    # Get available models
    models = core.get_available_models("text-chat")
    
    if model_name not in models:
        print(f"[SKIP] Model {model_name} not found in config")
        return None
    
    # Get provider
    from chatbot_core.model_resolver import ModelResolver
    resolver = ModelResolver()
    provider = resolver.get_provider_for_model(model_name)
    
    if not provider:
        print(f"[SKIP] No provider found for {model_name}")
        return None
    
    # Set model
    if not core.set_model(model_name, provider):
        print(f"[FAIL] Could not set model {model_name}")
        return False
    
    print(f"[OK] Model set: {model_name} @ {provider}")
    
    # Step 1: Say hi
    print("\n--- Step 1: Say hi ---")
    print("User: hi")
    
    response1 = core.send("hi")
    if not response1:
        print("[FAIL] No response received")
        return False
    print(f"Assistant: {response1}")
    
    # Step 2: Ask name
    print("\n--- Step 2: Ask name ---")
    print("User: what's your name?")
    
    response2 = core.send("what's your name?")
    if not response2:
        print("[FAIL] No response received")
        return False
    print(f"Assistant: {response2}")
    
    print(f"\n[OK] {model_name} - Two-step conversation successful!")
    return True


def test_streaming(model_name: str):
    """Test streaming with a specific model."""
    print(f"\n{'=' * 60}")
    print(f"Streaming Test: {model_name}")
    print('=' * 60)
    
    core = ChatCore(system_prompt="You are helpful. Keep responses brief.")
    
    # Get provider
    from chatbot_core.model_resolver import ModelResolver
    resolver = ModelResolver()
    provider = resolver.get_provider_for_model(model_name)
    
    if not provider or not core.set_model(model_name, provider):
        print(f"[SKIP] Could not set model {model_name}")
        return None
    
    print(f"\nModel: {model_name} @ {provider}")
    print("User: Count from 1 to 5")
    print("Assistant: ", end="", flush=True)
    
    for chunk in core.send_stream("Count from 1 to 5"):
        print(chunk, end="", flush=True)
    
    print(f"\n\n[OK] {model_name} - Streaming successful!")
    return True


def main():
    print("=" * 60)
    print("ChatCore Multi-Vendor Test Suite")
    print("=" * 60)
    
    # Test models - one from each vendor
    test_models = [
        "gemini-2.5-flash",    # Google Gemini
        "claude-4-sonnet",     # Anthropic Claude
        "deepseek-chat",       # DeepSeek (OpenAI-compatible)
    ]
    
    results = {}
    
    # Two-step conversation tests
    for model in test_models:
        results[model] = test_two_step_conversation(model)
    
    # Streaming test (use first successful model)
    for model in test_models:
        if results.get(model):
            test_streaming(model)
            break
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for model, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
            all_passed = False
        else:
            status = "[SKIP]"
        print(f"{status} {model}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
