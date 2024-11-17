def add_zero_wide_char_to_str(input_str: str) -> str:
    """
    Add zero-width spaces after specific characters to allow text wrapping.
    
    Args:
        input_str: The input string to process
        
    Returns:
        String with zero-width spaces added after slashes, hyphens, and underscores
    """
    return (input_str.replace('/', '/\u200b')
                    .replace('-', '-\u200b')
                    .replace('_', '_\u200b'))