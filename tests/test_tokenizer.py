import pytest
from tokenwise import count_tokens 

def test_openai_tokenization():
    text = "Hello, world!"
    result = count_tokens(text, model="gpt-4")
    
    # Assert against the specific attribute
    assert result.token_count == 4 
    assert result.provider == "OpenAI"
    assert isinstance(result.token_count, int)

def test_anthropic_tokenization():
    text = "Hello, world!"
    result = count_tokens(text, model="claude-3-5-sonnet")
    
    # Claude tokenizes this slightly differently (usually 3 tokens)
    assert result.token_count == 3
    assert result.provider == "Anthropic"

def test_empty_string():
    result = count_tokens("", model="gpt-4")
    assert result.token_count == 0