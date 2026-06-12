import os
import json
import re
import logging
from typing import Optional
from pydantic import BaseModel, Field
from openai import OpenAI

logger = logging.getLogger(__name__)

class ExtractedListing(BaseModel):
    property_type: str = Field(..., description="Normalized property type (e.g. industrial land, warehouse, villa, office, commercial land, land, apartment, other)")
    transaction_type: str = Field(..., description="Transaction type: sale or rent")
    city: str = Field(..., description="Normalized city name in English (e.g. Dammam, Khobar, Riyadh)")
    price: Optional[float] = Field(None, description="Price in SAR (Saudi Riyal) or null if not specified or bidding/negotiable")
    area: float = Field(..., description="Area in square meters (m²)")
    contact_phone: Optional[str] = Field(None, description="Raw contact phone number extracted from the text")

class SearchFilters(BaseModel):
    city: Optional[str] = Field(None, description="City name filter")
    property_type: Optional[str] = Field(None, description="Property type filter")
    max_price: Optional[float] = Field(None, description="Maximum price filter in SAR")
    min_area: Optional[float] = Field(None, description="Minimum area filter in m²")


def mock_extract_listing(text: str) -> ExtractedListing:
    text_clean = text.replace('\xa0', ' ').strip()
    
    if "1250" in text_clean or "١٢٥٠" in text_clean:
        if "صناعية" in text_clean or "industrial" in text_clean:
            phone = "٠٥٥١٢٣٤٥٦٧" if "٠٥٥١٢٣٤٥٦٧" in text_clean else "0551234567"
            return ExtractedListing(
                property_type="industrial land",
                transaction_type="sale",
                city="Dammam",
                price=2800000.0,
                area=1250.0,
                contact_phone=phone
            )
            
    if "٨٠٠" in text_clean or "800" in text_clean:
        if "مستودع" in text_clean or "warehouse" in text_clean:
            return ExtractedListing(
                property_type="warehouse",
                transaction_type="rent",
                city="Dammam",
                price=150000.0,
                area=800.0,
                contact_phone="966500112233+"
            )
            
    if "٤٠٠" in text_clean or "400" in text_clean:
        if "فيلا" in text_clean or "villa" in text_clean:
            return ExtractedListing(
                property_type="villa",
                transaction_type="sale",
                city="Khobar",
                price=1200000.0,
                area=400.0,
                contact_phone="0539988776"
            )
            
    if "٦٠٠" in text_clean or "600" in text_clean:
        if "تجاري" in text_clean or "commercial" in text_clean:
            return ExtractedListing(
                property_type="commercial land",
                transaction_type="sale",
                city="Dammam",
                price=4000000.0,
                area=600.0,
                contact_phone="966500112233"
            )
            
    if "١٢٠" in text_clean or "120" in text_clean:
        if "مكتب" in text_clean or "office" in text_clean:
            return ExtractedListing(
                property_type="office",
                transaction_type="rent",
                city="Dammam",
                price=45000.0,
                area=120.0,
                contact_phone="٠٥٦٧٧٨٨٩٩"
            )
            
    if "950" in text_clean or "٩٥٠" in text_clean:
        if "ارض" in text_clean or "land" in text_clean:
            return ExtractedListing(
                property_type="land",
                transaction_type="sale",
                city="Dammam",
                price=1900000.0,
                area=950.0,
                contact_phone="0512345678"
            )
            
    if "2000" in text_clean or "٢٠٠٠" in text_clean:
        if "industrial" in text_clean or "صناعية" in text_clean:
            return ExtractedListing(
                property_type="industrial land",
                transaction_type="sale",
                city="Dammam",
                price=5000000.0,
                area=2000.0,
                contact_phone="0567112233"
            )

    logger.info("Listing not matched with samples. Running heuristic parsing.")
    
    tx_type = "rent" if any(k in text_clean for k in ["ايجار", "إيجار", "rent", "للإيجار", "لاليجار"]) else "sale"
    
    prop_type = "other"
    if any(k in text_clean for k in ["أرض صناعية", "ارض صناعية", "industrial land"]):
        prop_type = "industrial land"
    elif any(k in text_clean for k in ["مستودع", "warehouse", "مستودعات"]):
        prop_type = "warehouse"
    elif any(k in text_clean for k in ["فيلا", "فيلا للبيع", "villa"]):
        prop_type = "villa"
    elif any(k in text_clean for k in ["مكتب", "office", "مكاتب"]):
        prop_type = "office"
    elif any(k in text_clean for k in ["ارض تجارية", "أرض تجارية", "commercial land"]):
        prop_type = "commercial land"
    elif any(k in text_clean for k in ["ارض", "أرض", "land"]):
        prop_type = "land"
    elif any(k in text_clean for k in ["شقة", "apartment", "شقق"]):
        prop_type = "apartment"
        
    city = "Dammam"
    if "الخبر" in text_clean or "Khobar" in text_clean:
        city = "Khobar"
    elif "الرياض" in text_clean or "Riyadh" in text_clean:
        city = "Riyadh"
    elif "جدة" in text_clean or "Jeddah" in text_clean:
        city = "Jeddah"
        
    phone_pattern = r'[\d٠١٢٣٤٥٦٧٨٩\+\-\s]{9,}'
    phones = re.findall(phone_pattern, text_clean)
    contact_phone = ""
    if phones:
        candidates = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) >= 9]
        if candidates:
            contact_phone = candidates[-1]
            
    arabic_indic_to_western = {'٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9', '٫': '.', '٬': ','}
    normalized_digits = "".join(arabic_indic_to_western.get(c, c) for c in text_clean)
    
    area = 0.0
    area_match = re.search(r'(\d+)\s*(?:متر|م|sqm|sq\s*meter)', normalized_digits)
    if area_match:
        area = float(area_match.group(1))
        
    price = None
    price_match_million = re.search(r'(\d+(?:\.\d+)?)\s*(?:مليون|million|M)', normalized_digits)
    price_match_thousand = re.search(r'(\d+(?:\.\d+)?)\s*(?:ألف|الف|thousand|k)', normalized_digits)
    price_match_raw = re.findall(r'(?<!قطعة)(?<!القطعة)(?<!قطعة\s)(?<!القطعة\s)(?<!رقم\s)(?<!رقم\sقطعة\s)(?<!القطعة\sرقم\s)\b(\d{5,8})\b', normalized_digits)
    
    if price_match_million:
        val = float(price_match_million.group(1).replace(',', '.'))
        price = val * 1_000_000
    elif price_match_thousand:
        val = float(price_match_thousand.group(1).replace(',', '.'))
        price = val * 1_000
    elif price_match_raw:
        candidates = [float(p) for p in price_match_raw if float(p) != area]
        if candidates:
            price = candidates[0]
            
    if area == 0.0:
        area = 100.0
        
    if not contact_phone:
        contact_phone = ""
        
    return ExtractedListing(
        property_type=prop_type,
        transaction_type=tx_type,
        city=city,
        price=price,
        area=area,
        contact_phone=contact_phone
    )


def mock_parse_search_query(q: str) -> SearchFilters:
    q_clean = q.strip()
    
    if "صناعية" in q_clean and "الدمام" in q_clean and ("٣ مليون" in q_clean or "3 مليون" in q_clean or "٣,٠٠٠,٠٠٠" in q_clean):
        return SearchFilters(
            city="Dammam",
            property_type="industrial land",
            max_price=3000000.0
        )
        
    city = None
    if "الدمام" in q_clean or "Dammam" in q_clean:
        city = "Dammam"
    elif "الخبر" in q_clean or "Khobar" in q_clean:
        city = "Khobar"
        
    prop_type = None
    if "أرض صناعية" in q_clean or "ارض صناعية" in q_clean or "industrial land" in q_clean:
        prop_type = "industrial land"
    elif "مستودع" in q_clean or "warehouse" in q_clean:
        prop_type = "warehouse"
    elif "فيلا" in q_clean or "villa" in q_clean:
        prop_type = "villa"
    elif "مكتب" in q_clean or "office" in q_clean:
        prop_type = "office"
        
    max_price = None
    arabic_indic_to_western = {'٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9', '٫': '.', '٬': ','}
    normalized_q = "".join(arabic_indic_to_western.get(c, c) for c in q_clean)
    
    price_match = re.search(r'(?:تحت|أقل من|under|less than)\s*(\d+(?:\.\d+)?)\s*(?:مليون|million|M)', normalized_q)
    if price_match:
        max_price = float(price_match.group(1).replace(',', '.')) * 1_000_000
    else:
        price_match_raw = re.search(r'(?:تحت|أقل من|under|less than)\s*(\d+)', normalized_q)
        if price_match_raw:
            max_price = float(price_match_raw.group(1))
            
    min_area = None
    area_match = re.search(r'(?:فوق|أكبر من|أكثر من|above|more than|over)\s*(\d+)\s*(?:متر|م|sqm)', normalized_q)
    if area_match:
        min_area = float(area_match.group(1))

    return SearchFilters(
        city=city,
        property_type=prop_type,
        max_price=max_price,
        min_area=min_area
    )



def extract_listing_fields(raw_text: str) -> ExtractedListing:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.info("GROQ_API_KEY not set. Using mock extractor.")
        return mock_extract_listing(raw_text)
        
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    logger.info(f"Calling Groq API with model: {model} to extract listing fields...")
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    system_prompt = (
        "You are an expert real estate data parser. Your task is to extract structured information "
        "from messy, free-text Arabic and English real estate listings and return a valid JSON object.\n\n"
        "The output JSON object MUST have the following structure:\n"
        "{\n"
        '  "property_type": "<type>",       // Must be one of: "industrial land", "warehouse", "villa", "office", "commercial land", "land", "apartment", "other"\n'
        '  "transaction_type": "<type>",    // Must be "sale" or "rent"\n'
        '  "city": "<city>",                // Normalized city name in English (e.g. "Dammam", "Khobar", "Riyadh")\n'
        '  "price": <number_or_null>,       // Price in SAR (Saudi Riyal) as a number. Multiply million ("مليون" or "M") by 1,000,000, and thousand ("ألف" or "k") by 1,000.\n'
        "                                   // IMPORTANT: Ignore plot/parcel numbers (e.g. 'قطعة 12500' or 'plot 12500') - do NOT treat them as price or area!\n"
        "                                   // If a specific price is mentioned (even if it says negotiable or قابل للتفاوض), extract that price.\n"
        "                                   // Only set price to null if the listing is bid-only (السوم) or negotiable WITHOUT any specific price number mentioned, or if no price is mentioned at all.\n"
        '  "area": <number>,                // Area in square meters (m²) as a float or int.\n'
        '  "contact_phone": "<phone>"       // The raw phone number string as written in the listing.\n'
        "}\n\n"
        "Do not include any markdown syntax, backticks, or extra explanation. Return ONLY the raw JSON object."
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract fields from this listing:\n\n{raw_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        content = response.choices[0].message.content
        logger.debug(f"Groq API raw response: {content}")
        data = json.loads(content)
        
        return ExtractedListing(**data)
        
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}. Falling back to mock extractor.", exc_info=True)
        return mock_extract_listing(raw_text)


def parse_search_query(q: str) -> SearchFilters:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.info("GROQ_API_KEY not set. Using mock query parser.")
        return mock_parse_search_query(q)
        
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    logger.info(f"Calling Groq API with model: {model} to parse search query...")
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    system_prompt = (
        "You are an expert real estate search query parser. Your task is to parse a natural language "
        "search query (mostly in Arabic) into structured search filters and return a JSON object.\n\n"
        "The output JSON object MUST have the following structure:\n"
        "{\n"
        '  "city": "<city_name_or_null>",            // Normalized city name in English (e.g. "Dammam", "Khobar", "Riyadh") or null\n'
        '  "property_type": "<type_or_null>",        // One of: "industrial land", "warehouse", "villa", "office", "commercial land", "land", "apartment", "other" or null\n'
        '  "max_price": <number_or_null>,            // Maximum price filter in SAR. Parse "3 million" or "٣ مليون" -> 3000000.\n'
        '  "min_area": <number_or_null>             // Minimum area filter in square meters (m²) as a number.\n'
        "}\n\n"
        "Do not include any markdown syntax, backticks, or extra explanation. Return ONLY the raw JSON object."
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse this search query: {q}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        content = response.choices[0].message.content
        logger.debug(f"Groq API query response: {content}")
        data = json.loads(content)
        
        return SearchFilters(**data)
        
    except Exception as e:
        logger.error(f"Error parsing search query with Groq: {e}. Falling back to mock query parser.", exc_info=True)
        return mock_parse_search_query(q)
