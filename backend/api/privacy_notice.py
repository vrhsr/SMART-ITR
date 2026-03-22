from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter()


PRIVACY_NOTICES = {
    "en": "SmartITR processes your financial documents only with your consent, solely for tax computation and compliance, and stores structured data in encrypted form in India (AWS Mumbai).",
    "ta": "SmartITR உங்கள் ஒப்புதலுடன் மட்டுமே உங்கள் நிதி ஆவணங்களை வரி கணக்கீடு மற்றும் இணக்கத்திற்காக செயலாக்குகிறது. அனைத்து தரவும் இந்தியாவில் (AWS மும்பை) குறியாக்கம் செய்யப்பட்ட வடிவில் சேமிக்கப்படுகிறது.",
    "ml": "SmartITR നിങ്ങളുടെ സമ്മതത്തോടെ മാത്രമേ നിങ്ങളുടെ ധനകാര്യ രേഖകള്‍ നികുതി കണക്കുകൂട്ടലിനും അനുസരണത്തിനും വേണ്ടി പ്രോസസ് ചെയ്യുകയുള്ളു. എല്ലാ ഡാറ്റയും ഇന്ത്യയിലെ (AWS മുംബൈ) എന്‍ക്രിപ്റ്റ് ചെയ്ത രൂപത്തില്‍ സൂക്ഷിക്കുന്നു."
}


@router.get("/api/privacy-notice")
def privacy_notice(lang: str = Query("en", pattern="^(en|ta|ml)$")) -> dict[str, str]:
    text = PRIVACY_NOTICES.get(lang, PRIVACY_NOTICES["en"])
    return {"lang": lang, "text": text, "version": "2026-03-19-v1"}

