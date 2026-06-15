import re

def normalize_phone(phone_str: str) -> str:
    if not phone_str:
        return ""
    
    arabic_indic_to_western = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    cleaned = "".join(arabic_indic_to_western.get(c, c) for c in phone_str)
    
    # Try to extract the first valid-looking Saudi number sequence (mobile or landline)
    # Saudi mobile format: (00966|966|+966|0)?5\d{8}
    # Saudi landline format: (00966|966|+966|0)?1\d{7}
    # We clean formatting characters like spaces and dashes first
    cleaned_digits = "".join(c for c in cleaned if c.isdigit() or c == '+')
    match = re.search(r'(?:\+?966|00966|0)?(5\d{8}|1\d{7})', cleaned_digits)
    if match:
        local_part = match.group(1)
        return f"+966{local_part}"
    
    # Fallback for shorter/other numbers (backward compatibility with tests)
    digits = "".join(c for c in cleaned if c.isdigit())
    if not digits:
        return ""
    
    if digits.startswith("00966"):
        digits = "966" + digits[5:]
    elif digits.startswith("966"):
        pass
    elif digits.startswith("05"):
        digits = "966" + digits[1:]
    elif digits.startswith("5"):
        digits = "966" + digits
        
    return f"+{digits}"

