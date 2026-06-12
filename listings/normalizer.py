import re

def normalize_phone(phone_str: str) -> str:
   
    if not phone_str:
        return ""
    
    arabic_indic_to_western = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    cleaned = "".join(arabic_indic_to_western.get(c, c) for c in phone_str)
    
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
    else:
        pass
        
    return f"+{digits}"
